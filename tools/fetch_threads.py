#!/usr/bin/env python3
"""Fetch a public Threads post from a Threads URL for evidence capture.

The original Threads URL remains the evidence source. FxThreads is used only as
a transport/resolution layer because Threads share URLs require a browser to
resolve reliably.

No third-party response is silently promoted to a primary source: output keeps
both the original Threads URL and the transport metadata.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

DEFAULT_TRANSPORT_BASE = "https://fx.akitsuki.me"
USER_AGENT = (
    "Mozilla/5.0 (compatible; politics-db-evidence-fetcher/1.0; "
    "+https://github.com/lichih/politics-db)"
)
MAX_RESPONSE_BYTES = 5 * 1024 * 1024


@dataclass(frozen=True)
class ThreadsTarget:
    original_url: str
    kind: str
    identifier: str


class FetchError(RuntimeError):
    pass


def parse_threads_url(url: str) -> ThreadsTarget:
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    if host.startswith("www."):
        host = host[4:]

    if parsed.scheme not in {"http", "https"} or host not in {"threads.com", "threads.net"}:
        raise ValueError("URL must be an http(s) Threads URL")

    parts = [part for part in parsed.path.split("/") if part]
    if len(parts) >= 2 and parts[0] == "share":
        return ThreadsTarget(url, "share", parts[1])

    if len(parts) >= 3 and parts[0].startswith("@") and parts[1] == "post":
        return ThreadsTarget(url, "post", parts[2])

    if len(parts) >= 2 and parts[0] == "t":
        return ThreadsTarget(url, "post", parts[1])

    raise ValueError("Unsupported Threads URL; expected /share/<id> or /@user/post/<id>")


def fetch_json(url: str, timeout: float) -> dict[str, Any]:
    request = Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "application/json",
        },
    )

    try:
        with urlopen(request, timeout=timeout) as response:
            raw = response.read(MAX_RESPONSE_BYTES + 1)
            if len(raw) > MAX_RESPONSE_BYTES:
                raise FetchError("transport response exceeded 5 MiB")
            charset = response.headers.get_content_charset() or "utf-8"
            text = raw.decode(charset, errors="replace")
    except HTTPError as exc:
        body = exc.read(4096).decode("utf-8", errors="replace")
        raise FetchError(f"transport HTTP {exc.code}: {body[:500]}") from exc
    except URLError as exc:
        raise FetchError(f"transport network error: {exc.reason}") from exc

    try:
        value = json.loads(text)
    except json.JSONDecodeError as exc:
        raise FetchError("transport returned non-JSON content") from exc

    if not isinstance(value, dict):
        raise FetchError("transport returned a non-object JSON value")
    return value


def validate_post_payload(payload: dict[str, Any]) -> None:
    author = payload.get("author")
    if not isinstance(author, dict) or not author.get("username"):
        raise FetchError("transport payload is missing author.username")
    if not payload.get("id"):
        raise FetchError("transport payload is missing post id")
    if not payload.get("url"):
        raise FetchError("transport payload is missing canonical post URL")
    if "content" not in payload:
        raise FetchError("transport payload is missing content")


def build_record(
    target: ThreadsTarget,
    payload: dict[str, Any],
    transport_url: str,
) -> dict[str, Any]:
    validate_post_payload(payload)
    return {
        "schema_version": 1,
        "observed_at": datetime.now(timezone.utc).isoformat(),
        "source": {
            "platform": "Threads",
            "source_type": "primary",
            "original_url": target.original_url,
            "canonical_url": payload.get("url"),
        },
        "retrieval": {
            "status": "reachable",
            "transport": "FxThreads public API",
            "transport_url": transport_url,
            "transport_role": "resolver/proxy only",
            "note": (
                "The Threads post is the evidence source. The transport service "
                "is recorded only because it was used to resolve/fetch the public post."
            ),
        },
        "post": {
            "id": payload.get("id"),
            "author": payload.get("author"),
            "content": payload.get("content"),
            "media": payload.get("medias", []),
            "stats": payload.get("stats"),
            "timestamp": payload.get("timestamp"),
        },
        "raw_transport_payload": payload,
    }


def fetch_threads_post(
    url: str,
    *,
    transport_base: str = DEFAULT_TRANSPORT_BASE,
    timeout: float = 30.0,
) -> dict[str, Any]:
    target = parse_threads_url(url)
    base = transport_base.rstrip("/")
    endpoint = "share" if target.kind == "share" else "post"
    transport_url = f"{base}/api/{endpoint}/{target.identifier}"
    payload = fetch_json(transport_url, timeout)
    return build_record(target, payload, transport_url)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Fetch a public Threads post while preserving evidence provenance."
    )
    parser.add_argument("url", help="Threads share or canonical post URL")
    parser.add_argument(
        "--transport-base",
        default=DEFAULT_TRANSPORT_BASE,
        help="Resolver/proxy base URL (default: %(default)s)",
    )
    parser.add_argument("--timeout", type=float, default=30.0)
    parser.add_argument("-o", "--output", type=Path)
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args()

    try:
        record = fetch_threads_post(
            args.url,
            transport_base=args.transport_base,
            timeout=args.timeout,
        )
    except ValueError as exc:
        print(json.dumps({"status": "invalid_url", "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2
    except FetchError as exc:
        failure = {
            "schema_version": 1,
            "observed_at": datetime.now(timezone.utc).isoformat(),
            "source": {
                "platform": "Threads",
                "original_url": args.url,
            },
            "retrieval": {
                "status": "blocked_or_unresolved",
                "transport": "FxThreads public API",
                "error": str(exc),
            },
        }
        print(json.dumps(failure, ensure_ascii=False, indent=2), file=sys.stderr)
        return 3

    rendered = json.dumps(
        record,
        ensure_ascii=False,
        indent=2 if args.pretty else None,
        sort_keys=False,
    )
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")
    else:
        print(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
