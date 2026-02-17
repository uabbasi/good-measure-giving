#!/usr/bin/env python3
"""Validate charity JSON data for integrity and consistency.

Reads all charity JSONs from website/data/charities/ and the master index
website/data/charities.json, validates against 11 rule categories, and
outputs a severity-grouped report.

Usage:
    python website/scripts/validate_charity_data.py
"""

import json
import os
import re
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

VALID_WALLET_TAGS = {
    "ZAKAT-ELIGIBLE",
    "SADAQAH-ELIGIBLE",
    "SADAQAH-STRATEGIC",
    "SADAQAH-GENERAL",
    "INSUFFICIENT-DATA",
}

REQUIRED_TOP_LEVEL = {"name", "ein", "id", "category", "tier", "amalEvaluation", "mission", "ui_signals_v1"}

LLM_ARTIFACTS = [
    "As an AI",
    "I cannot",
    "I don't have",
    "I'm an AI",
    "As a language model",
]

TEMPLATE_MARKERS = ["{{", "[INSERT", "PLACEHOLDER"]

URL_PATTERN = re.compile(r"^https?://\S+$")
EIN_PATTERN = re.compile(r"^\d{2}-\d{7}$")
CITE_TAG_PATTERN = re.compile(r'<cite\s+id="(\d+)"')
CITE_BRACKET_PATTERN = re.compile(r"\[(\d+)\]")


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class Violation:
    charity_id: str
    category: str
    severity: str  # CRITICAL, WARNING, INFO
    message: str


@dataclass
class ValidationContext:
    violations: list = field(default_factory=list)

    def add(self, charity_id: str, category: str, severity: str, message: str):
        self.violations.append(Violation(charity_id, category, severity, message))

    def critical(self, charity_id: str, category: str, message: str):
        self.add(charity_id, category, "CRITICAL", message)

    def warning(self, charity_id: str, category: str, message: str):
        self.add(charity_id, category, "WARNING", message)

    def info(self, charity_id: str, category: str, message: str):
        self.add(charity_id, category, "INFO", message)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def safe_float(val):
    """Convert a value to float, returning None if not possible."""
    if val is None:
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return None


def collect_narrative_text(narrative: dict) -> str:
    """Collect all string values from a narrative dict recursively."""
    if not isinstance(narrative, dict):
        return ""
    parts = []
    for v in narrative.values():
        if isinstance(v, str):
            parts.append(v)
        elif isinstance(v, list):
            for item in v:
                if isinstance(item, str):
                    parts.append(item)
                elif isinstance(item, dict):
                    parts.append(collect_narrative_text(item))
        elif isinstance(v, dict):
            parts.append(collect_narrative_text(v))
    return " ".join(parts)


def collect_urls_from_obj(obj, urls: list):
    """Recursively collect all string values that look like URLs."""
    if isinstance(obj, str):
        if URL_PATTERN.match(obj):
            urls.append(obj)
    elif isinstance(obj, dict):
        for v in obj.values():
            collect_urls_from_obj(v, urls)
    elif isinstance(obj, list):
        for item in obj:
            collect_urls_from_obj(item, urls)


# ---------------------------------------------------------------------------
# Checks
# ---------------------------------------------------------------------------

def check_schema_completeness(cid: str, data: dict, ctx: ValidationContext):
    """Check 1: Schema completeness (CRITICAL)."""
    for field_name in REQUIRED_TOP_LEVEL:
        if field_name not in data or data[field_name] is None:
            ctx.critical(cid, "Schema", f"missing field '{field_name}'")

    amal = data.get("amalEvaluation")
    if isinstance(amal, dict):
        bn = amal.get("baseline_narrative")
        if not isinstance(bn, dict):
            ctx.critical(cid, "Schema", "missing amalEvaluation.baseline_narrative")
        else:
            if not bn.get("summary"):
                ctx.critical(cid, "Schema", "missing baseline_narrative.summary")
            if not bn.get("headline"):
                ctx.critical(cid, "Schema", "missing baseline_narrative.headline")

        if "confidence_scores" not in amal or not isinstance(amal.get("confidence_scores"), dict):
            ctx.critical(cid, "Schema", "missing amalEvaluation.confidence_scores")


def check_score_validity(cid: str, data: dict, ctx: ValidationContext):
    """Check 2: Score validity (CRITICAL)."""
    amal = data.get("amalEvaluation")
    if not isinstance(amal, dict):
        return

    amal_score = amal.get("amal_score")
    if amal_score is not None:
        score = safe_float(amal_score)
        if score is None or score < 0 or score > 100:
            ctx.critical(cid, "Score", f"amal_score {amal_score} out of range 0-100")

    cs = amal.get("confidence_scores", {})
    if isinstance(cs, dict):
        impact = safe_float(cs.get("impact"))
        alignment = safe_float(cs.get("alignment"))
        # Handle both snake_case (detail files) and camelCase (possible variants)
        data_conf = safe_float(cs.get("data_confidence") or cs.get("dataConfidence"))

        if impact is not None and (impact < 0 or impact > 50):
            ctx.critical(cid, "Score", f"impact score {impact} out of range 0-50")
        if alignment is not None and (alignment < 0 or alignment > 50):
            ctx.critical(cid, "Score", f"alignment score {alignment} out of range 0-50")
        if data_conf is not None and (data_conf < 0 or data_conf > 1):
            ctx.critical(cid, "Score", f"dataConfidence {data_conf} out of range 0-1")

        # Pillar sum check: impact + alignment + risk_deduction ~ amal_score
        # Note: risk_deduction is stored as a negative number (e.g. -2, -5)
        if impact is not None and alignment is not None and amal_score is not None:
            score_details = amal.get("score_details", {})
            risk_deduction = safe_float(score_details.get("risk_deduction", 0)) or 0
            expected = impact + alignment + risk_deduction
            actual = safe_float(amal_score)
            if actual is not None and abs(expected - actual) > 2:
                ctx.critical(
                    cid, "Score",
                    f"pillar sum mismatch: impact({impact}) + alignment({alignment}) "
                    f"- risk_deduction({risk_deduction}) = {expected}, but amal_score = {actual}"
                )


def check_financial_consistency(cid: str, data: dict, ctx: ValidationContext):
    """Check 3: Financial consistency (WARNING)."""
    fin = data.get("financials")
    if not isinstance(fin, dict):
        return

    total_exp = safe_float(fin.get("totalExpenses"))
    prog_exp = safe_float(fin.get("programExpenses"))
    admin_exp = safe_float(fin.get("adminExpenses"))
    fund_exp = safe_float(fin.get("fundraisingExpenses"))

    # Check for negatives
    for name, val in [("totalExpenses", total_exp), ("programExpenses", prog_exp),
                      ("adminExpenses", admin_exp), ("fundraisingExpenses", fund_exp)]:
        if val is not None and val < 0:
            ctx.warning(cid, "Financial", f"{name} is negative: {val}")

    # Expense sum check
    if all(v is not None for v in [total_exp, prog_exp, admin_exp, fund_exp]) and total_exp > 0:
        component_sum = prog_exp + admin_exp + fund_exp
        tolerance = total_exp * 0.02
        if abs(component_sum - total_exp) > tolerance:
            ctx.warning(
                cid, "Financial",
                f"expense sum mismatch: program({prog_exp}) + admin({admin_exp}) + "
                f"fundraising({fund_exp}) = {component_sum}, total = {total_exp}"
            )

    # Program expense ratio check
    per = safe_float(fin.get("programExpenseRatio"))
    if per is not None and total_exp is not None and prog_exp is not None and total_exp > 0:
        computed_ratio = prog_exp / total_exp
        if abs(computed_ratio - per) > 0.02:
            ctx.warning(
                cid, "Financial",
                f"programExpenseRatio {per} != computed {computed_ratio:.4f}"
            )


def check_wallet_tag_consistency(cid: str, data: dict, ctx: ValidationContext):
    """Check 4: Wallet tag consistency (WARNING)."""
    amal = data.get("amalEvaluation")
    if not isinstance(amal, dict):
        return

    wallet_tag = amal.get("wallet_tag")
    if wallet_tag and wallet_tag not in VALID_WALLET_TAGS:
        ctx.warning(cid, "WalletTag", f"invalid wallet_tag: '{wallet_tag}'")

    if wallet_tag == "ZAKAT-ELIGIBLE":
        if not data.get("asnafServed"):
            ctx.warning(cid, "WalletTag", "ZAKAT-ELIGIBLE but missing asnafServed")

    # Check wallet_routing.tag matches if present
    routing = amal.get("wallet_routing")
    if isinstance(routing, dict) and routing.get("tag"):
        if routing["tag"] != wallet_tag:
            ctx.warning(
                cid, "WalletTag",
                f"wallet_routing.tag '{routing['tag']}' != wallet_tag '{wallet_tag}'"
            )


def check_url_format(cid: str, data: dict, ctx: ValidationContext):
    """Check 5: URL format (WARNING)."""
    # Specific known URL fields
    url_fields = {
        "website": data.get("website"),
        "donationUrl": data.get("donationUrl"),
    }
    awards = data.get("awards", {})
    if isinstance(awards, dict):
        url_fields["awards.cnUrl"] = awards.get("cnUrl")
        url_fields["awards.candidUrl"] = awards.get("candidUrl")
        url_fields["awards.bbbReviewUrl"] = awards.get("bbbReviewUrl")

    for field_name, val in url_fields.items():
        if val is not None and isinstance(val, str) and val.strip():
            if not URL_PATTERN.match(val):
                ctx.warning(cid, "URL", f"invalid URL in {field_name}: '{val}'")

    # Check citation source_urls
    amal = data.get("amalEvaluation", {})
    for narrative_key in ("baseline_narrative", "rich_narrative"):
        narrative = amal.get(narrative_key, {})
        if not isinstance(narrative, dict):
            continue
        for citation in narrative.get("all_citations", []):
            if isinstance(citation, dict):
                url = citation.get("source_url")
                if url is not None and isinstance(url, str) and url.strip():
                    if not URL_PATTERN.match(url):
                        ctx.warning(cid, "URL", f"invalid citation URL: '{url}'")

    # Check sourceAttribution URLs
    sa = data.get("sourceAttribution", {})
    if isinstance(sa, dict):
        for key, entry in sa.items():
            if isinstance(entry, dict):
                url = entry.get("source_url")
                if url is not None and isinstance(url, str) and url.strip():
                    if not URL_PATTERN.match(url):
                        ctx.warning(cid, "URL", f"invalid sourceAttribution URL in {key}: '{url}'")


def check_narrative_quality(cid: str, data: dict, ctx: ValidationContext):
    """Check 6: Narrative quality (CRITICAL)."""
    amal = data.get("amalEvaluation")
    if not isinstance(amal, dict):
        return

    for narrative_key in ("baseline_narrative", "rich_narrative"):
        narrative = amal.get(narrative_key)
        if not isinstance(narrative, dict):
            continue

        label = narrative_key.replace("_", " ")
        full_text = collect_narrative_text(narrative)

        # LLM artifact check
        for artifact in LLM_ARTIFACTS:
            if artifact.lower() in full_text.lower():
                ctx.critical(cid, "Narrative", f"LLM artifact in {label}: '{artifact}'")

        # Template marker check
        for marker in TEMPLATE_MARKERS:
            if marker in full_text:
                ctx.critical(cid, "Narrative", f"template marker in {label}: '{marker}'")

        # Summary length
        summary = narrative.get("summary", "")
        if isinstance(summary, str) and len(summary) < 20:
            ctx.critical(cid, "Narrative", f"{label} summary too short ({len(summary)} chars)")

        # Headline length
        headline = narrative.get("headline", "")
        if isinstance(headline, str) and len(headline) < 5:
            ctx.critical(cid, "Narrative", f"{label} headline too short ({len(headline)} chars)")

        # Strengths must be non-empty array
        strengths = narrative.get("strengths")
        if strengths is not None and (not isinstance(strengths, list) or len(strengths) == 0):
            ctx.critical(cid, "Narrative", f"{label} strengths is empty or not a list")


def check_citation_integrity(cid: str, data: dict, ctx: ValidationContext):
    """Check 7: Citation integrity (WARNING)."""
    amal = data.get("amalEvaluation")
    if not isinstance(amal, dict):
        return

    for narrative_key in ("baseline_narrative", "rich_narrative"):
        narrative = amal.get(narrative_key)
        if not isinstance(narrative, dict):
            continue

        label = narrative_key.replace("_", " ")
        full_text = collect_narrative_text(narrative)
        citations = narrative.get("all_citations", [])

        if not isinstance(citations, list):
            continue

        # Build set of citation IDs present in array
        citation_ids = set()
        urls_present = 0
        for c in citations:
            if isinstance(c, dict):
                cid_val = c.get("id", "")
                # Normalize: "[1]" -> "1", or just use the number
                match = re.search(r"(\d+)", str(cid_val))
                if match:
                    citation_ids.add(match.group(1))
                if c.get("source_url"):
                    urls_present += 1

        # Find all refs in text
        refs_in_text = set()
        for m in CITE_TAG_PATTERN.finditer(full_text):
            refs_in_text.add(m.group(1))
        for m in CITE_BRACKET_PATTERN.finditer(full_text):
            refs_in_text.add(m.group(1))

        # Orphaned refs (in text but not in citations)
        orphaned = refs_in_text - citation_ids
        if orphaned:
            ctx.warning(
                cid, "Citation",
                f"orphaned refs in {label}: {sorted(orphaned)} (in text but not in citations)"
            )

        # Check that majority of citations have source_url
        if len(citations) > 0 and urls_present / len(citations) <= 0.5:
            ctx.warning(
                cid, "Citation",
                f"{label}: only {urls_present}/{len(citations)} citations have source_url"
            )


def check_index_detail_consistency(
    cid: str, data: dict, index_entry: dict, ctx: ValidationContext
):
    """Check 8: Index-to-detail consistency (CRITICAL)."""
    # name
    if data.get("name") != index_entry.get("name"):
        ctx.critical(
            cid, "IndexSync",
            f"name mismatch: detail='{data.get('name')}' vs index='{index_entry.get('name')}'"
        )

    # tier
    if data.get("tier") != index_entry.get("tier"):
        ctx.critical(
            cid, "IndexSync",
            f"tier mismatch: detail='{data.get('tier')}' vs index='{index_entry.get('tier')}'"
        )

    # amalScore vs amal_score
    amal = data.get("amalEvaluation", {})
    detail_score = amal.get("amal_score") if isinstance(amal, dict) else None
    index_score = index_entry.get("amalScore")
    if detail_score is not None and index_score is not None:
        if safe_float(detail_score) != safe_float(index_score):
            ctx.critical(
                cid, "IndexSync",
                f"score mismatch: detail amal_score={detail_score} vs index amalScore={index_score}"
            )

    # walletTag vs wallet_tag
    detail_tag = amal.get("wallet_tag") if isinstance(amal, dict) else None
    index_tag = index_entry.get("walletTag")
    if detail_tag != index_tag:
        ctx.critical(
            cid, "IndexSync",
            f"wallet tag mismatch: detail='{detail_tag}' vs index='{index_tag}'"
        )


def check_tier_consistency(cid: str, data: dict, ctx: ValidationContext):
    """Check 9: Tier consistency (WARNING)."""
    tier = data.get("tier")
    amal = data.get("amalEvaluation")
    if not isinstance(amal, dict):
        return

    if tier == "rich" and not isinstance(amal.get("rich_narrative"), dict):
        ctx.warning(cid, "Tier", "tier is 'rich' but missing amalEvaluation.rich_narrative")

    if tier == "baseline" and not isinstance(amal.get("baseline_narrative"), dict):
        ctx.warning(cid, "Tier", "tier is 'baseline' but missing amalEvaluation.baseline_narrative")


def check_ein_format(cid: str, data: dict, filename: str, ctx: ValidationContext):
    """Check 10: EIN format (WARNING)."""
    ein = data.get("ein", "")
    id_val = data.get("id", "")

    if not EIN_PATTERN.match(str(ein)):
        ctx.warning(cid, "EIN", f"invalid EIN format: '{ein}'")

    if ein != id_val:
        ctx.warning(cid, "EIN", f"id '{id_val}' does not match ein '{ein}'")

    expected_filename = f"charity-{ein}.json"
    if filename != expected_filename:
        ctx.warning(cid, "EIN", f"filename '{filename}' does not match expected '{expected_filename}'")


def check_type_consistency(cid: str, data: dict, ctx: ValidationContext):
    """Check 11: Type consistency (INFO)."""
    fin = data.get("financials")
    if not isinstance(fin, dict):
        return

    per = fin.get("programExpenseRatio")
    if isinstance(per, str):
        ctx.info(cid, "Type", f"programExpenseRatio is string \"{per}\" not number")

    wcm = fin.get("workingCapitalMonths")
    if isinstance(wcm, str):
        ctx.info(cid, "Type", f"workingCapitalMonths is string \"{wcm}\" not number")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    # Resolve paths relative to this script
    script_dir = Path(__file__).resolve().parent
    website_dir = script_dir.parent
    charities_dir = website_dir / "data" / "charities"
    index_path = website_dir / "data" / "charities.json"

    if not charities_dir.is_dir():
        print(f"ERROR: charities directory not found: {charities_dir}", file=sys.stderr)
        sys.exit(2)

    if not index_path.is_file():
        print(f"ERROR: index file not found: {index_path}", file=sys.stderr)
        sys.exit(2)

    # Load index
    with open(index_path, "r", encoding="utf-8") as f:
        index_data = json.load(f)

    index_charities = index_data.get("charities", [])
    index_by_id = {}
    for entry in index_charities:
        eid = entry.get("id") or entry.get("ein")
        if eid:
            index_by_id[eid] = entry

    # Load charity detail files
    charity_files = sorted(
        f for f in os.listdir(charities_dir)
        if f.startswith("charity-") and f.endswith(".json")
    )

    ctx = ValidationContext()

    for filename in charity_files:
        filepath = charities_dir / filename
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
        except json.JSONDecodeError as e:
            cid = filename.replace(".json", "")
            ctx.critical(cid, "Parse", f"invalid JSON: {e}")
            continue

        cid = data.get("id") or data.get("ein") or filename.replace(".json", "")

        # Run all per-charity checks
        check_schema_completeness(cid, data, ctx)
        check_score_validity(cid, data, ctx)
        check_financial_consistency(cid, data, ctx)
        check_wallet_tag_consistency(cid, data, ctx)
        check_url_format(cid, data, ctx)
        check_narrative_quality(cid, data, ctx)
        check_citation_integrity(cid, data, ctx)
        check_tier_consistency(cid, data, ctx)
        check_ein_format(cid, data, filename, ctx)
        check_type_consistency(cid, data, ctx)

        # Index-to-detail check
        index_entry = index_by_id.get(cid)
        if index_entry:
            check_index_detail_consistency(cid, data, index_entry, ctx)
        else:
            ctx.critical(cid, "IndexSync", "charity not found in charities.json index")

    # Check for index entries without detail files
    detail_ids = set()
    for filename in charity_files:
        filepath = charities_dir / filename
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
            detail_ids.add(data.get("id") or data.get("ein"))
        except (json.JSONDecodeError, KeyError):
            pass

    for eid, entry in index_by_id.items():
        if eid not in detail_ids:
            ctx.critical(eid, "IndexSync", "in charities.json index but no detail file found")

    # --- Report ---
    severity_order = ["CRITICAL", "WARNING", "INFO"]
    grouped = defaultdict(list)
    for v in ctx.violations:
        grouped[v.severity].append(v)

    for severity in severity_order:
        violations = grouped.get(severity, [])
        header = {
            "CRITICAL": "=== CRITICAL VIOLATIONS ===",
            "WARNING": "=== WARNINGS ===",
            "INFO": "=== INFO ===",
        }[severity]
        print(header)
        if not violations:
            print("  (none)")
        else:
            for v in sorted(violations, key=lambda x: (x.charity_id, x.category)):
                print(f"  [{v.charity_id}] {v.category}: {v.message}")
        print()

    # Summary
    print("=== SUMMARY ===")
    print(f"Total charities checked: {len(charity_files)}")
    for severity in severity_order:
        violations = grouped.get(severity, [])
        charity_ids = {v.charity_id for v in violations}
        label = {
            "CRITICAL": "CRITICAL",
            "WARNING": "WARNING",
            "INFO": "INFO",
        }[severity]
        count_word = "violations" if severity != "INFO" else "items"
        print(f"{label}: {len(violations)} {count_word} across {len(charity_ids)} charities")

    # Exit code
    if grouped.get("CRITICAL"):
        sys.exit(1)
    else:
        sys.exit(0)


if __name__ == "__main__":
    main()
