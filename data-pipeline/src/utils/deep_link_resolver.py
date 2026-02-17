"""Utilities for upgrading generic source URLs to deeper evidence links."""

from __future__ import annotations

import re
from typing import Any, Iterable, Optional
from urllib.parse import ParseResult, urlparse

_URL_PATTERN = re.compile(r"https?://[^\s\"'<>)}\]]+", re.IGNORECASE)

_NEGATIVE_PATH = re.compile(
    r"/(donate|volunteer|contact|checkout|cart|login|signin|signup|privacy|terms|cookie|legal)\b", re.IGNORECASE
)
_DOCUMENT_PATH = re.compile(r"(/s/|\.pdf(?:$|[?#]))", re.IGNORECASE)

_TOPIC_HINTS: list[tuple[re.Pattern[str], re.Pattern[str], int]] = [
    (re.compile(r"(zakat|sadaq)", re.IGNORECASE), re.compile(r"/(zakat|sadaq)", re.IGNORECASE), 9),
    (
        re.compile(r"(beneficiar|outcome|impact|served annually|people served|students served)", re.IGNORECASE),
        re.compile(r"(impact|outcome|result|metric|report|evaluation|annual|/s/|\.pdf)", re.IGNORECASE),
        8,
    ),
    (
        re.compile(r"(financial|revenue|expense|asset|liabilit|audit|annual report|990|transparency)", re.IGNORECASE),
        re.compile(r"(financial|report|audit|annual|transparency|accountability|990|/s/|\.pdf)", re.IGNORECASE),
        8,
    ),
    (
        re.compile(r"(program|service|initiative|project)", re.IGNORECASE),
        re.compile(r"(program|service|initiative|our-work|what-we-do)", re.IGNORECASE),
        6,
    ),
    (
        re.compile(r"(about|mission|history|found|who we are)", re.IGNORECASE),
        re.compile(r"(about|mission|history|our-story|who-we-are)", re.IGNORECASE),
        5,
    ),
]

_CN_FINANCIAL_TOPIC = re.compile(
    r"(financial|revenue|expense|assets?|liabilit|working capital|fundraising|raise every|audit|990|ratio)",
    re.IGNORECASE,
)
_CN_RATING_TOPIC = re.compile(
    r"(rating|score|stars?|accountability|leadership|overall|board|governance|independent)",
    re.IGNORECASE,
)
_CANDID_PROFILE_PATH = re.compile(r"^/profile/\d+/?$", re.IGNORECASE)
_CANDID_TOPIC = re.compile(r"(candid|guidestar|seal of transparency)", re.IGNORECASE)


def _parse_url(value: str) -> Optional[ParseResult]:
    try:
        parsed = urlparse(value)
    except Exception:
        return None
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        return None
    return parsed


def _normalize_host(host: str) -> str:
    return host.lower().removeprefix("www.")


def _is_homepage_url(parsed: ParseResult) -> bool:
    return (parsed.path in ("", "/")) and not parsed.query and not parsed.fragment


def _is_deep_url(parsed: ParseResult) -> bool:
    return not _is_homepage_url(parsed)


def _url_depth(parsed: ParseResult) -> int:
    path = parsed.path.strip("/")
    return len([part for part in path.split("/") if part]) if path else 0


def _canonicalize_url(parsed: ParseResult) -> str:
    path = parsed.path or "/"
    query = f"?{parsed.query}" if parsed.query else ""
    fragment = f"#{parsed.fragment}" if parsed.fragment else ""
    return f"{parsed.scheme}://{_normalize_host(parsed.netloc)}{path}{query}{fragment}"


def _topic_text(source_name: str | None, claim: str | None, source_path: str | None) -> str:
    parts = [source_name or "", claim or "", source_path or ""]
    return " ".join(part for part in parts if part).strip().lower()


def _trim_url_candidate(url: str) -> str:
    return url.rstrip("),.;:!?")


def _collect_urls(value: Any, out: set[str], seen: set[int]) -> None:
    if value is None:
        return

    if isinstance(value, str):
        for match in _URL_PATTERN.findall(value):
            out.add(_trim_url_candidate(match))
        return

    if isinstance(value, (list, tuple, set)):
        obj_id = id(value)
        if obj_id in seen:
            return
        seen.add(obj_id)
        for item in value:
            _collect_urls(item, out, seen)
        return

    if isinstance(value, dict):
        obj_id = id(value)
        if obj_id in seen:
            return
        seen.add(obj_id)
        for nested in value.values():
            _collect_urls(nested, out, seen)
        return

    # Handle simple objects (e.g., dataclasses used in citation registry)
    if hasattr(value, "__dict__"):
        obj_id = id(value)
        if obj_id in seen:
            return
        seen.add(obj_id)
        _collect_urls(vars(value), out, seen)


def _index_deep_urls(*contexts: Any, additional_candidates: Iterable[str] | None = None) -> dict[str, list[str]]:
    discovered: set[str] = set()
    seen: set[int] = set()
    for context in contexts:
        _collect_urls(context, discovered, seen)
    if additional_candidates:
        for candidate in additional_candidates:
            if isinstance(candidate, str):
                discovered.add(_trim_url_candidate(candidate))

    by_host: dict[str, list[str]] = {}
    dedupe: dict[str, set[str]] = {}

    for raw in sorted(discovered):
        parsed = _parse_url(raw)
        if not parsed or not _is_deep_url(parsed):
            continue

        host = _normalize_host(parsed.netloc)
        canonical = _canonicalize_url(parsed)
        if host not in by_host:
            by_host[host] = []
            dedupe[host] = set()
        if canonical in dedupe[host]:
            continue
        dedupe[host].add(canonical)
        by_host[host].append(canonical)

    return by_host


def _score_candidate(url: str, topic_text: str) -> int:
    parsed = _parse_url(url)
    if not parsed:
        return -999

    path = f"{parsed.path or ''}?{parsed.query}#{parsed.fragment}".lower()
    score = max(0, _url_depth(parsed))

    if _DOCUMENT_PATH.search(path):
        score += 5

    if parsed.fragment:
        score += 2

    for topic_re, path_re, weight in _TOPIC_HINTS:
        if topic_re.search(topic_text) and path_re.search(path):
            score += weight

    # Penalize generic action pages for evidence claims, unless topic explicitly matches.
    if _NEGATIVE_PATH.search(path):
        if not re.search(r"(donat|volunteer|contact|support)", topic_text):
            score -= 3

    return score


def _pick_candid_profile_candidate(by_host: dict[str, list[str]]) -> Optional[str]:
    candid_candidates = by_host.get("app.candid.org", [])
    for candidate in candid_candidates:
        parsed_candidate = _parse_url(candidate)
        if parsed_candidate and _CANDID_PROFILE_PATH.match(parsed_candidate.path or ""):
            return candidate
    return None


def _upgrade_known_source(source_url: str, topic_text: str, by_host: dict[str, list[str]] | None = None) -> Optional[str]:
    parsed = _parse_url(source_url)
    if not parsed:
        return None

    if by_host and _CANDID_TOPIC.search(topic_text):
        candid_profile = _pick_candid_profile_candidate(by_host)
        if candid_profile:
            return candid_profile

    host = _normalize_host(parsed.netloc)
    if host.endswith("guidestar.org"):
        if not by_host:
            return None
        return _pick_candid_profile_candidate(by_host)

    if not host.endswith("charitynavigator.org"):
        return None

    if not re.match(r"^/ein/\d+/?$", parsed.path, re.IGNORECASE):
        return None

    if parsed.fragment:
        return None

    base = f"{parsed.scheme}://{parsed.netloc}{parsed.path.rstrip('/')}"
    if _CN_FINANCIAL_TOPIC.search(topic_text):
        return f"{base}#financials"
    if _CN_RATING_TOPIC.search(topic_text):
        return f"{base}#ratings"
    if "charity navigator" in topic_text:
        return f"{base}#ratings"
    return None


def _pick_best_candidate(candidates: list[str], topic_text: str) -> tuple[str | None, int]:
    best_url: str | None = None
    best_score = -999
    best_depth = -1

    for candidate in candidates:
        parsed = _parse_url(candidate)
        if not parsed:
            continue
        score = _score_candidate(candidate, topic_text)
        depth = _url_depth(parsed)
        if score > best_score or (score == best_score and depth > best_depth):
            best_url = candidate
            best_score = score
            best_depth = depth

    return best_url, best_score


def upgrade_source_url(
    source_url: str | None,
    *,
    source_name: str | None = None,
    claim: str | None = None,
    source_path: str | None = None,
    context: Any = None,
    additional_candidates: Iterable[str] | None = None,
) -> str | None:
    """Upgrade homepage-like URLs to deeper evidence links when possible."""
    if not source_url:
        return source_url

    parsed = _parse_url(source_url)
    if not parsed:
        return source_url

    topic_text = _topic_text(source_name, claim, source_path)
    by_host = _index_deep_urls(context, additional_candidates=additional_candidates)

    known = _upgrade_known_source(source_url, topic_text, by_host=by_host)
    if known:
        return known

    if not _is_homepage_url(parsed):
        return source_url

    host = _normalize_host(parsed.netloc)
    candidates = by_host.get(host, [])
    if not candidates:
        return source_url

    best_url, best_score = _pick_best_candidate(candidates, topic_text)
    if not best_url:
        return source_url

    return best_url if best_score > 0 else source_url


def choose_website_evidence_url(
    website_profile: dict[str, Any] | None,
    fallback_url: str | None,
    *,
    source_name: str | None = None,
    claim: str | None = None,
    source_path: str | None = None,
) -> str | None:
    """Pick a website evidence URL, preferring deep links over homepage URLs."""
    return upgrade_source_url(
        fallback_url,
        source_name=source_name,
        claim=claim,
        source_path=source_path,
        context=website_profile,
    )
