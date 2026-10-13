#!/usr/bin/env python3
"""Fetch a public Threads post while preserving evidence provenance.

Preferred path: render the original Threads URL in Chromium and extract the
public post data embedded by Threads itself. A third-party API is optional
fallback transport only; it is never promoted to the evidence source.
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
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "Chrome/141.0 Safari/537.36"
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


def find_threads_post(value: Any, post_id: str) -> dict[str, Any] | None:
    """Find the Threads post object with code=post_id in nested bootstrap JSON."""
    if isinstance(value, dict):
        if (
            value.get("code") == post_id
            and isinstance(value.get("user"), dict)
            and (
                isinstance(value.get("text_post_app_info"), dict)
                or "caption" in value
            )
        ):
            return value
        for child in value.values():
            found = find_threads_post(child, post_id)
            if found is not None:
                return found
    elif isinstance(value, list):
        for child in value:
            found = find_threads_post(child, post_id)
            if found is not None:
                return found
    return None


def _first_url(items: Any) -> str | None:
    if not isinstance(items, list) or not items:
        return None
    first = items[0]
    if isinstance(first, dict):
        value = first.get("url")
        return value if isinstance(value, str) else None
    return None


def normalize_threads_post(post: dict[str, Any]) -> dict[str, Any]:
    user = post.get("user") if isinstance(post.get("user"), dict) else {}
    info = (
        post.get("text_post_app_info")
        if isinstance(post.get("text_post_app_info"), dict)
        else {}
    )
    code = post.get("code")
    username = user.get("username")
    if not isinstance(code, str) or not code:
        raise FetchError("Threads bootstrap post is missing code")
    if not isinstance(username, str) or not username:
        raise FetchError("Threads bootstrap post is missing user.username")

    caption = post.get("caption")
    content = caption.get("text") if isinstance(caption, dict) else None
    if content is None:
        content = ""

    media_items = post.get("carousel_media")
    if not isinstance(media_items, list):
        media_items = [post] if isinstance(post.get("image_versions2"), dict) else []

    medias: list[dict[str, Any]] = []
    for media in media_items:
        if not isinstance(media, dict):
            continue
        image_versions = media.get("image_versions2")
        image_candidates = (
            image_versions.get("candidates")
            if isinstance(image_versions, dict)
            else None
        )
        video_url = _first_url(media.get("video_versions"))
        image_url = _first_url(image_candidates)
        is_video = bool(video_url)
        medias.append(
            {
                "is_video": is_video,
                "url": video_url or image_url,
                "cover_image": image_url if is_video else None,
                "width": media.get("original_width"),
                "height": media.get("original_height"),
            }
        )

    return {
        "id": code,
        "url": f"https://www.threads.com/@{username}/post/{code}",
        "author": {
            "full_name": user.get("full_name"),
            "username": username,
            "avatar_url": user.get("profile_pic_url"),
            "url": f"https://www.threads.com/@{username}",
        },
        "content": content,
        "medias": medias,
        "stats": {
            "likes": post.get("like_count"),
            "comments": info.get("direct_reply_count"),
            "reposts": info.get("repost_count"),
            "shares": info.get("reshare_count"),
        },
        "timestamp": post.get("taken_at"),
    }


def fetch_with_browser(url: str, timeout: float) -> dict[str, Any]:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise FetchError(
            "browser transport requires Playwright; install requirements-tools.txt "
            "and run `python -m playwright install chromium`"
        ) from exc

    timeout_ms = max(1, int(timeout * 1000))
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            page = browser.new_page(user_agent=USER_AGENT)
            page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)

            try:
                page.wait_for_function(
                    "() => /\\/@[^/]+\\/post\\/[A-Za-z0-9_-]+/.test(location.pathname)",
                    timeout=timeout_ms,
                )
            except Exception:
                pass

            page.wait_for_timeout(1500)
            final_url = page.url
            try:
                final_target = parse_threads_url(final_url)
            except ValueError as exc:
                raise FetchError(
                    f"browser did not resolve to a Threads post URL: {final_url}"
                ) from exc
            if final_target.kind != "post":
                raise FetchError(
                    f"browser did not resolve share URL to a post: {final_url}"
                )

            post_id = final_target.identifier
            script_texts = page.locator("script").all_text_contents()
            raw_post: dict[str, Any] | None = None
            for text in script_texts:
                if '"thread_items"' not in text and f'"code":"{post_id}"' not in text:
                    continue
                try:
                    payload = json.loads(text)
                except json.JSONDecodeError:
                    continue
                raw_post = find_threads_post(payload, post_id)
                if raw_post is not None:
                    break

            if raw_post is None:
                raise FetchError(
                    f"browser resolved {final_url} but Threads bootstrap post data was not found"
                )

            normalized = normalize_threads_post(raw_post)
            return {
                "normalized": normalized,
                "raw_post": raw_post,
                "final_url": final_url,
            }
        finally:
            browser.close()


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
                raise FetchError("proxy response exceeded 5 MiB")
            charset = response.headers.get_content_charset() or "utf-8"
            text = raw.decode(charset, errors="replace")
    except HTTPError as exc:
        body = exc.read(4096).decode("utf-8", errors="replace")
        raise FetchError(f"proxy HTTP {exc.code}: {body[:500]}") from exc
    except URLError as exc:
        raise FetchError(f"proxy network error: {exc.reason}") from exc

    try:
        value = json.loads(text)
    except json.JSONDecodeError as exc:
        raise FetchError("proxy returned non-JSON content") from exc
    if not isinstance(value, dict):
        raise FetchError("proxy returned a non-object JSON value")
    return value


def validate_proxy_payload(payload: dict[str, Any]) -> None:
    author = payload.get("author")
    if not isinstance(author, dict) or not author.get("username"):
        raise FetchError("proxy payload is missing author.username")
    if not payload.get("id"):
        raise FetchError("proxy payload is missing post id")
    if not payload.get("url"):
        raise FetchError("proxy payload is missing canonical post URL")
    if "content" not in payload:
        raise FetchError("proxy payload is missing content")


def build_record(
    target: ThreadsTarget,
    normalized: dict[str, Any],
    *,
    transport: str,
    transport_url: str | None = None,
    final_url: str | None = None,
    raw_payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "observed_at": datetime.now(timezone.utc).isoformat(),
        "source": {
            "platform": "Threads",
            "source_type": "primary",
            "original_url": target.original_url,
            "canonical_url": normalized.get("url"),
        },
        "retrieval": {
            "status": "reachable",
            "transport": transport,
            "transport_url": transport_url,
            "final_url": final_url,
            "transport_role": "retrieval mechanism only",
            "note": (
                "The Threads post is the evidence source. Retrieval transport "
                "metadata is preserved separately for provenance."
            ),
        },
        "post": {
            "id": normalized.get("id"),
            "author": normalized.get("author"),
            "content": normalized.get("content"),
            "media": normalized.get("medias", []),
            "stats": normalized.get("stats"),
            "timestamp": normalized.get("timestamp"),
        },
        "raw_threads_post": raw_payload,
    }


def fetch_via_proxy(
    target: ThreadsTarget,
    *,
    transport_base: str,
    timeout: float,
) -> dict[str, Any]:
    base = transport_base.rstrip("/")
    endpoint = "share" if target.kind == "share" else "post"
    transport_url = f"{base}/api/{endpoint}/{target.identifier}"
    payload = fetch_json(transport_url, timeout)
    validate_proxy_payload(payload)
    return build_record(
        target,
        payload,
        transport="FxThreads public API",
        transport_url=transport_url,
        final_url=payload.get("url"),
        raw_payload=payload,
    )


def fetch_threads_post(
    url: str,
    *,
    mode: str = "auto",
    transport_base: str = DEFAULT_TRANSPORT_BASE,
    timeout: float = 30.0,
) -> dict[str, Any]:
    target = parse_threads_url(url)
    errors: list[str] = []

    if mode in {"auto", "browser"}:
        try:
            result = fetch_with_browser(url, timeout)
            return build_record(
                target,
                result["normalized"],
                transport="Playwright/Chromium direct Threads browser",
                final_url=result["final_url"],
                raw_payload=result["raw_post"],
            )
        except FetchError as exc:
            errors.append(f"browser: {exc}")
            if mode == "browser":
                raise

    if mode in {"auto", "proxy"}:
        try:
            return fetch_via_proxy(
                target,
                transport_base=transport_base,
                timeout=timeout,
            )
        except FetchError as exc:
            errors.append(f"proxy: {exc}")
            if mode == "proxy":
                raise

    raise FetchError("; ".join(errors) or "no retrieval transport attempted")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Fetch a public Threads post while preserving evidence provenance."
    )
    parser.add_argument("url", help="Threads share or canonical post URL")
    parser.add_argument(
        "--mode",
        choices=("auto", "browser", "proxy"),
        default="auto",
        help="retrieval mode (default: %(default)s)",
    )
    parser.add_argument(
        "--transport-base",
        default=DEFAULT_TRANSPORT_BASE,
        help="proxy base URL used by proxy/auto fallback (default: %(default)s)",
    )
    parser.add_argument("--timeout", type=float, default=30.0)
    parser.add_argument("-o", "--output", type=Path)
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args()

    try:
        record = fetch_threads_post(
            args.url,
            mode=args.mode,
            transport_base=args.transport_base,
            timeout=args.timeout,
        )
    except ValueError as exc:
        print(
            json.dumps({"status": "invalid_url", "error": str(exc)}, ensure_ascii=False),
            file=sys.stderr,
        )
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
