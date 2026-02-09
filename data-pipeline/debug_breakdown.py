#!/usr/bin/env python3
"""Debug breakdown: show component-level scoring for a charity."""

import sys

from baseline import build_charity_metrics
from src.db.repository import CharityDataRepository, CharityRepository, RawDataRepository
from src.scorers.v2_scorers import AmalScorerV2


def main():
    if len(sys.argv) < 2:
        print("Usage: debug_breakdown.py <EIN> [EIN2 ...]")
        sys.exit(1)

    charity_repo = CharityRepository()
    raw_repo = RawDataRepository()
    cd_repo = CharityDataRepository()

    for ein in sys.argv[1:]:
        charity = charity_repo.get(ein)
        if not charity:
            print(f"Charity {ein} not found in DB")
            continue

        charity_data = cd_repo.get(ein)

        # Build raw_sources dict keyed by source name
        raw_data = raw_repo.get_for_charity(ein)
        raw_sources: dict[str, dict] = {}
        for rd in raw_data:
            if rd.get("success") and rd.get("parsed_json"):
                raw_sources[rd["source"]] = rd["parsed_json"]
        metrics = build_charity_metrics(ein, charity, charity_data, raw_sources)

        # Score
        scorer = AmalScorerV2()
        result = scorer.evaluate(metrics)

        print(f"\n{'=' * 60}")
        print(f"  EIN {ein} ({metrics.name})")
        print(f"  GMG: {result.amal_score}/100 | Risk: {result.risk_deduction}")
        print(f"{'=' * 60}")

        # Key metrics
        print("\n--- Key Metrics ---")
        print(f"  cn_overall_score: {metrics.cn_overall_score}")
        print(f"  candid_seal: {metrics.candid_seal}")
        print(f"  program_expense_ratio: {metrics.program_expense_ratio}")
        print(f"  program_expenses: {metrics.program_expenses}")
        print(f"  beneficiaries_served_annually: {metrics.beneficiaries_served_annually}")
        print(
            f"  working_capital_ratio: {metrics.working_capital_ratio:.2f}"
            if metrics.working_capital_ratio
            else "  working_capital_ratio: N/A"
        )
        print(f"  detected_cause_area: {metrics.detected_cause_area}")
        print(f"  is_muslim_focused: {metrics.is_muslim_focused}")
        print(f"  zakat_claim_detected: {metrics.zakat_claim_detected}")
        print(f"  total_revenue: {metrics.total_revenue}")
        print(f"  board_size: {metrics.board_size}")
        print(f"  has_theory_of_change: {metrics.has_theory_of_change}")
        print(f"  mission: {metrics.mission[:100] if metrics.mission else 'None'}...")

        # Dimensions
        for dim_name, dim in [
            ("CREDIBILITY", result.credibility),
            ("IMPACT", result.impact),
            ("ALIGNMENT", result.alignment),
        ]:
            print(f"\n--- {dim_name} ({dim.score}/{33 if dim_name != 'ALIGNMENT' else 34} pts) ---")
            for c in dim.components:
                status = f" [{c.status.value}]" if c.status.value != "full" else ""
                improvement = f" [+{c.improvement_value}]" if c.improvement_value else ""
                print(f"  {c.name}: {c.scored}/{c.possible}{status}{improvement} -- {c.evidence}")
                if c.improvement_suggestion:
                    print(f"    → {c.improvement_suggestion}")

        # Risk
        if result.case_against and result.case_against.risks:
            print(f"\n--- RISK ({result.risk_deduction}) ---")
            for r in result.case_against.risks:
                print(f"  [{r.category.value}] {r.description} (severity={r.severity.value})")
        else:
            print("\n--- RISK: 0 (no flags) ---")


if __name__ == "__main__":
    main()
