#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shutil
import sys
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

import yaml
from jinja2 import Environment, FileSystemLoader, select_autoescape
from jsonschema import Draft202012Validator


ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT / "schema" / "evidence.schema.json"
TEMPLATE_DIR = ROOT / "renderer" / "templates"
STATIC_DIR = ROOT / "renderer" / "static"


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

    seen_session_ids: dict[str, Path] = {}

    for doc in docs:
        for err in sorted(validator.iter_errors(doc.data), key=lambda e: list(e.path)):
            location = ".".join(str(x) for x in err.path) or "<root>"
            errors.append(f"{doc.path}: {location}: {err.message}")

        errors.extend(validate_cross_references(doc))

        session_id = str(doc.data.get("session", {}).get("id", ""))
        if session_id:
            if session_id in seen_session_ids:
                errors.append(
                    f"{doc.path}: duplicate session.id {session_id!r}; "
                    f"already used by {seen_session_ids[session_id]}"
                )
            else:
                seen_session_ids[session_id] = doc.path

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

    indexed = [(doc, index_document(doc)) for doc in docs]

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
