#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable

import yaml
from jinja2 import Environment, FileSystemLoader, select_autoescape
from jsonschema import Draft202012Validator


ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT / "schema" / "evidence.schema.json"
TEMPLATE_DIR = ROOT / "renderer" / "templates"
STATIC_DIR = ROOT / "renderer" / "static"
LEGACY_SESSION_TIMESTAMPS_PATH = ROOT / "schema" / "legacy-session-timestamps.json"

CANONICAL_SESSION_TIMESTAMP_RE = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})$"
)
LEGACY_SESSION_DATE_RE = re.compile(
    r"^(?P<date>\d{4}-\d{2}-\d{2})(?P<offset>[+-]\d{2}:\d{2})?$"
)
LEGACY_DEFAULT_TIMEZONE = timezone(timedelta(hours=8))


@dataclass
class EvidenceDocument:
    path: Path
    rel_dir: Path
    data: dict[str, Any]


def load_schema() -> dict[str, Any]:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def discover_documents(root: Path = ROOT) -> list[EvidenceDocument]:
    docs: list[EvidenceDocument] = []
    for area in ("sessions", "cases", "comparators", "research", "proposals"):
        base = root / area
        if not base.exists():
            continue
        for path in sorted(base.rglob("evidence.yaml")):
            if "_template" in path.parts:
                continue
            data = yaml.safe_load(path.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                raise ValueError(f"{path}: root must be a mapping")
            docs.append(
                EvidenceDocument(
                    path=path,
                    rel_dir=path.parent.relative_to(root),
                    data=data,
                )
            )
    return docs


@dataclass(frozen=True)
class SessionTimestamp:
    instant: datetime
    precision_rank: int
    precision: str


def _timezone_from_offset(value: str | None) -> timezone:
    if value is None:
        return LEGACY_DEFAULT_TIMEZONE

    sign = 1 if value[0] == "+" else -1
    hours = int(value[1:3])
    minutes = int(value[4:6])
    if hours > 23 or minutes > 59:
        raise ValueError(f"invalid UTC offset: {value}")
    return timezone(sign * timedelta(hours=hours, minutes=minutes))


def parse_session_timestamp(value: str) -> SessionTimestamp:
    """Parse canonical timestamps plus legacy day-precision compatibility values."""
    if CANONICAL_SESSION_TIMESTAMP_RE.fullmatch(value):
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            raise ValueError("canonical session timestamp must include a timezone")
        return SessionTimestamp(
            instant=parsed,
            precision_rank=1,
            precision="time",
        )

    legacy = LEGACY_SESSION_DATE_RE.fullmatch(value)
    if legacy:
        calendar_date = date.fromisoformat(legacy.group("date"))
        tz = _timezone_from_offset(legacy.group("offset"))
        return SessionTimestamp(
            instant=datetime.combine(calendar_date, time.min, tzinfo=tz),
            precision_rank=0,
            precision="day",
        )

    raise ValueError(
        "expected RFC3339 timestamp with timezone, YYYY-MM-DD, "
        "or legacy YYYY-MM-DD+HH:MM"
    )


def load_legacy_session_timestamps(
    path: Path = LEGACY_SESSION_TIMESTAMPS_PATH,
) -> dict[str, dict[str, str]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    legacy_values = data.get("legacy_values")
    if not isinstance(legacy_values, dict):
        raise ValueError(f"{path}: legacy_values must be an object")

    normalized: dict[str, dict[str, str]] = {}
    for document_path, fields in legacy_values.items():
        if not isinstance(fields, dict):
            raise ValueError(f"{path}: {document_path} must map to an object")
        normalized[str(document_path)] = {
            str(field): str(value) for field, value in fields.items()
        }
    return normalized


def _document_relative_path(doc: EvidenceDocument) -> str:
    try:
        return doc.path.relative_to(ROOT).as_posix()
    except ValueError:
        return doc.path.as_posix()


def validate_session_timestamps(
    doc: EvidenceDocument,
    legacy_values: dict[str, dict[str, str]],
) -> list[str]:
    errors: list[str] = []
    session = doc.data.get("session", {})
    document_path = _document_relative_path(doc)
    allowed_legacy = legacy_values.get(document_path, {})

    for field in ("started_at", "updated_at"):
        value = session.get(field)
        if not isinstance(value, str):
            continue
        try:
            parsed = parse_session_timestamp(value)
        except ValueError as exc:
            errors.append(f"{doc.path}: session.{field}: {exc}")
            continue

        if parsed.precision == "day" and allowed_legacy.get(field) != value:
            errors.append(
                f"{doc.path}: session.{field}: legacy day-precision timestamp "
                "is compatibility-only; new writes must use RFC3339 date-time "
                "with explicit timezone"
            )

    return errors


def validate_legacy_session_timestamp_registry(
    docs: list[EvidenceDocument],
    legacy_values: dict[str, dict[str, str]],
) -> list[str]:
    errors: list[str] = []
    documents_by_path = {_document_relative_path(doc): doc for doc in docs}

    for document_path, fields in legacy_values.items():
        doc = documents_by_path.get(document_path)
        if doc is None:
            errors.append(
                f"{LEGACY_SESSION_TIMESTAMPS_PATH}: stale document path {document_path}"
            )
            continue

        session = doc.data.get("session", {})
        for field, expected in fields.items():
            if field not in ("started_at", "updated_at"):
                errors.append(
                    f"{LEGACY_SESSION_TIMESTAMPS_PATH}: unsupported field "
                    f"{document_path}.{field}"
                )
                continue

            actual = session.get(field)
            if actual != expected:
                errors.append(
                    f"{LEGACY_SESSION_TIMESTAMPS_PATH}: stale legacy value "
                    f"{document_path}.{field}; expected {expected!r}, found {actual!r}"
                )
                continue

            try:
                parsed = parse_session_timestamp(expected)
            except ValueError as exc:
                errors.append(
                    f"{LEGACY_SESSION_TIMESTAMPS_PATH}: "
                    f"{document_path}.{field}: {exc}"
                )
                continue

            if parsed.precision != "day":
                errors.append(
                    f"{LEGACY_SESSION_TIMESTAMPS_PATH}: {document_path}.{field} "
                    "must contain only a legacy day-precision value"
                )

    return errors


def unique_ids(items: Iterable[dict[str, Any]], label: str, path: Path) -> set[str]:
    ids: list[str] = [str(x["id"]) for x in items]
    duplicates = sorted({x for x in ids if ids.count(x) > 1})
    if duplicates:
        raise ValueError(f"{path}: duplicate {label} ids: {', '.join(duplicates)}")
    return set(ids)


def validate_cross_references(doc: EvidenceDocument) -> list[str]:
    data = doc.data
    errors: list[str] = []

    sources = data.get("sources", [])
    facts = data.get("facts", [])
    claims = data.get("claims", [])
    searches = data.get("searches", [])

    try:
        source_ids = unique_ids(sources, "source", doc.path)
        fact_ids = unique_ids(facts, "fact", doc.path)
        unique_ids(claims, "claim", doc.path)
        unique_ids(searches, "search", doc.path)
    except ValueError as exc:
        return [str(exc)]

    for fact in facts:
        missing = sorted(set(fact.get("source_ids", [])) - source_ids)
        if missing:
            errors.append(
                f"{doc.path}: {fact['id']} references missing sources: {', '.join(missing)}"
            )

    for claim in claims:
        for field in ("supports", "contradicts", "related_facts"):
            missing = sorted(set(claim.get(field, [])) - fact_ids)
            if missing:
                errors.append(
                    f"{doc.path}: {claim['id']}.{field} references missing facts: "
                    + ", ".join(missing)
                )

    return errors


def validate_documents(docs: list[EvidenceDocument]) -> None:
    schema = load_schema()
    validator = Draft202012Validator(schema)
    errors: list[str] = []

    try:
        legacy_values = load_legacy_session_timestamps()
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        print(f"Evidence validation failed:\n  - {exc}", file=sys.stderr)
        raise SystemExit(1) from exc

    seen_session_ids: dict[str, Path] = {}

    for doc in docs:
        for err in sorted(validator.iter_errors(doc.data), key=lambda e: list(e.path)):
            location = ".".join(str(x) for x in err.path) or "<root>"
            errors.append(f"{doc.path}: {location}: {err.message}")

        errors.extend(validate_cross_references(doc))
        errors.extend(validate_session_timestamps(doc, legacy_values))

        session_id = str(doc.data.get("session", {}).get("id", ""))
        if session_id:
            if session_id in seen_session_ids:
                errors.append(
                    f"{doc.path}: duplicate session.id {session_id!r}; "
                    f"already used by {seen_session_ids[session_id]}"
                )
            else:
                seen_session_ids[session_id] = doc.path

    errors.extend(validate_legacy_session_timestamp_registry(docs, legacy_values))

    if errors:
        print("Evidence validation failed:", file=sys.stderr)
        for err in errors:
            print(f"  - {err}", file=sys.stderr)
        raise SystemExit(1)


def index_document(doc: EvidenceDocument) -> dict[str, Any]:
    data = doc.data
    sources_by_id = {x["id"]: x for x in data.get("sources", [])}
    facts_by_id = {x["id"]: x for x in data.get("facts", [])}

    claims = []
    for claim in data.get("claims", []):
        enriched = dict(claim)
        enriched["support_facts"] = [
            facts_by_id[x] for x in claim.get("supports", []) if x in facts_by_id
        ]
        enriched["contradict_facts"] = [
            facts_by_id[x] for x in claim.get("contradicts", []) if x in facts_by_id
        ]
        enriched["related_fact_items"] = [
            facts_by_id[x] for x in claim.get("related_facts", []) if x in facts_by_id
        ]
        claims.append(enriched)

    facts = []
    for fact in data.get("facts", []):
        enriched = dict(fact)
        enriched["source_items"] = [
            sources_by_id[x] for x in fact.get("source_ids", []) if x in sources_by_id
        ]
        facts.append(enriched)

    return {
        **data,
        "facts": facts,
        "claims": claims,
        "_meta": {
            "source_count": len(data.get("sources", [])),
            "fact_count": len(facts),
            "claim_count": len(claims),
            "search_count": len(data.get("searches", [])),
            "relative_dir": doc.rel_dir.as_posix(),
            "area": doc.rel_dir.parts[0] if doc.rel_dir.parts else "",
            "root_prefix": "../" * len(doc.rel_dir.parts),
        },
    }



def _session_timestamp_sort_key(
    item: tuple[EvidenceDocument, dict[str, Any]],
    field: str,
) -> tuple[datetime, int]:
    value = str(item[1].get("session", {}).get(field, ""))
    parsed = parse_session_timestamp(value)
    return parsed.instant, parsed.precision_rank


def sort_indexed_documents(
    indexed: list[tuple[EvidenceDocument, dict[str, Any]]],
) -> list[tuple[EvidenceDocument, dict[str, Any]]]:
    """Sort homepage documents by evidence recency, independent of storage area."""
    ordered = sorted(indexed, key=lambda item: item[0].rel_dir.as_posix())
    ordered.sort(key=lambda item: str(item[1].get("session", {}).get("id", "")))
    ordered.sort(
        key=lambda item: _session_timestamp_sort_key(item, "started_at"),
        reverse=True,
    )
    ordered.sort(
        key=lambda item: _session_timestamp_sort_key(item, "updated_at"),
        reverse=True,
    )
    return ordered


def site_base_url(root: Path = ROOT) -> str:
    cname_path = root / "CNAME"
    if not cname_path.exists():
        return ""
    domain = cname_path.read_text(encoding="utf-8").strip().splitlines()[0].strip()
    if not domain:
        return ""
    return f"https://{domain.rstrip('/')}"


def write_sitemap(indexed: list[tuple[EvidenceDocument, dict[str, Any]]], output_dir: Path) -> None:
    base_url = site_base_url()
    if not base_url:
        return

    urls = [f"{base_url}/"]
    urls.extend(
        f"{base_url}/{doc.rel_dir.as_posix().strip('/')}/"
        for doc, _ in indexed
    )

    urlset = ET.Element("urlset", {"xmlns": "http://www.sitemaps.org/schemas/sitemap/0.9"})
    for location in urls:
        url = ET.SubElement(urlset, "url")
        ET.SubElement(url, "loc").text = location

    tree = ET.ElementTree(urlset)
    ET.indent(tree, space="  ")
    tree.write(output_dir / "sitemap.xml", encoding="utf-8", xml_declaration=True)

    (output_dir / "robots.txt").write_text(
        "User-agent: *\n"
        "Allow: /\n"
        f"Sitemap: {base_url}/sitemap.xml\n",
        encoding="utf-8",
    )


def build_site(docs: list[EvidenceDocument], output_dir: Path) -> None:
    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True)

    env = Environment(
        loader=FileSystemLoader(TEMPLATE_DIR),
        autoescape=select_autoescape(("html", "xml")),
        trim_blocks=True,
        lstrip_blocks=True,
    )
    env.filters["tojson_pretty"] = lambda value: json.dumps(
        value, ensure_ascii=False, indent=2
    )

    indexed = sort_indexed_documents(
        [(doc, index_document(doc)) for doc in docs]
    )
    base_url = site_base_url()
    for doc, data in indexed:
        data["_meta"]["canonical_url"] = (
            f"{base_url}/{doc.rel_dir.as_posix().strip('/')}/" if base_url else ""
        )

    session_template = env.get_template("session.html.j2")
    for doc, data in indexed:
        target_dir = output_dir / doc.rel_dir
        target_dir.mkdir(parents=True, exist_ok=True)
        (target_dir / "index.html").write_text(
            session_template.render(data=data),
            encoding="utf-8",
        )

    index_template = env.get_template("index.html.j2")
    (output_dir / "index.html").write_text(
        index_template.render(documents=[data for _, data in indexed]),
        encoding="utf-8",
    )

    if STATIC_DIR.exists():
        shutil.copytree(STATIC_DIR, output_dir / "static")

    write_sitemap(indexed, output_dir)

    (output_dir / ".nojekyll").write_text("", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate and render politics-db evidence")
    parser.add_argument(
        "--check",
        action="store_true",
        help="validate only; do not generate HTML",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "site",
        help="output directory (default: ./site)",
    )
    args = parser.parse_args()

    docs = discover_documents()
    if not docs:
        print("No evidence documents found.", file=sys.stderr)
        raise SystemExit(1)

    validate_documents(docs)
    print(f"Validated {len(docs)} evidence document(s).")

    if args.check:
        return

    build_site(docs, args.output)
    print(f"Rendered site to {args.output}")


if __name__ == "__main__":
    main()
