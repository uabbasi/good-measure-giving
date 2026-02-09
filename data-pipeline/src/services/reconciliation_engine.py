"""
Reconciliation Engine - Merges agent discoveries with structured source data.

Reads from:
- raw_scraped_data (ProPublica, CN, Candid, Website)
- agent_discoveries (Rating, Profile, Evidence, Reputation agents)

Produces:
- CharityDataBundle with all data merged and conflicts logged
"""

import logging
from datetime import datetime, timezone
from typing import Any, Optional

from ..db.repository import (
    AgentDiscoveryRepository,
    CharityRepository,
    RawDataRepository,
)
from ..models.reconciled_profile import (
    CharityDataBundle,
    ConflictRecord,
    ConflictType,
    EvidenceEntry,
    FinancialsBundle,
    LegalStatus,
    ProfileEntry,
    RatingEntry,
    ReputationEntry,
)
from .parameter_mapper import ParameterMapper

logger = logging.getLogger(__name__)


class ReconciliationEngine:
    """
    Merges data from structured sources and agent discoveries.

    Applies source priority matrix for field-level conflict resolution.
    """

    def __init__(self):
        self.charity_repo = CharityRepository()
        self.raw_repo = RawDataRepository()
        self.discovery_repo = AgentDiscoveryRepository()
        self.mapper = ParameterMapper()

    def reconcile(self, ein: str) -> Optional[CharityDataBundle]:
        """
        Reconcile all data sources for a charity.

        Args:
            ein: Charity EIN

        Returns:
            CharityDataBundle with merged data, or None if charity not found
        """
        # Get basic charity info
        charity = self.charity_repo.get(ein)
        if not charity:
            logger.warning(f"Charity not found: {ein}")
            return None

        logger.info(f"Reconciling data for {charity.get('name', ein)}")

        # Gather all data sources
        raw_data = self._load_raw_data(ein)
        discoveries = self._load_discoveries(ein)

        # Build the bundle
        bundle = CharityDataBundle(
            charity_ein=ein,
            charity_name=charity.get("name", "Unknown"),
        )

        # 1. Build financials from structured sources
        bundle.financials = self._reconcile_financials(raw_data)

        # 2. Build legal status
        bundle.legal_status = self._build_legal_status(ein, charity, raw_data)

        # 3. Process agent discoveries into typed lists
        bundle.ratings = self._process_rating_discoveries(discoveries.get("rating", []))
        bundle.profiles = self._process_profile_discoveries(discoveries.get("profile", []))
        bundle.evidence = self._process_evidence_discoveries(discoveries.get("evidence", []))
        bundle.reputation = self._process_reputation_discoveries(discoveries.get("reputation", []))

        # 4. Select primary values with conflict detection
        bundle.primary_mission, mission_conflicts = self._select_mission(raw_data, bundle.profiles)
        bundle.primary_programs = self._select_programs(raw_data, bundle.profiles)
        bundle.primary_rating = self._select_primary_rating(bundle.ratings)

        # 5. Detect and log all conflicts
        bundle.conflicts = self._detect_conflicts(raw_data, bundle)
        bundle.conflicts.extend(mission_conflicts)

        # 6. Calculate coverage score
        bundle.sources_discovered = self._list_sources(raw_data, discoveries)
        bundle.coverage_score = self._calculate_coverage(bundle)

        bundle.reconciled_at = datetime.now(timezone.utc)

        logger.info(
            f"Reconciled {ein}: {len(bundle.ratings)} ratings, "
            f"{len(bundle.evidence)} evidence, {len(bundle.conflicts)} conflicts"
        )

        return bundle

    # Mapping of source names to their nested keys in parsed_json
    SOURCE_NESTED_KEYS = {
        "propublica": "propublica_990",
        "charity_navigator": "cn_profile",
        "candid": "candid_profile",
        "website": "website_profile",
    }

    def _load_raw_data(self, ein: str) -> dict[str, dict]:
        """Load raw scraped data, keyed by source name.

        Handles nested structure where data is stored under source-specific keys
        (e.g., propublica -> parsed_json.propublica_990).
        """
        raw_records = self.raw_repo.get_for_charity(ein)
        result = {}
        for record in raw_records:
            if record.get("success") and record.get("parsed_json"):
                source = record["source"].lower()
                parsed = record["parsed_json"]

                # Extract nested data if it exists
                nested_key = self.SOURCE_NESTED_KEYS.get(source)
                if nested_key and nested_key in parsed:
                    result[source] = parsed[nested_key]
                else:
                    result[source] = parsed
        return result

    def _load_discoveries(self, ein: str) -> dict[str, list[dict]]:
        """Load agent discoveries, grouped by agent type."""
        all_discoveries = self.discovery_repo.get_for_charity(ein)
        result: dict[str, list[dict]] = {
            "rating": [],
            "profile": [],
            "evidence": [],
            "reputation": [],
        }
        for d in all_discoveries:
            agent_type = d.get("agent_type", "").lower()
            if "rating" in agent_type:
                result["rating"].append(d)
            elif "profile" in agent_type:
                result["profile"].append(d)
            elif "evidence" in agent_type:
                result["evidence"].append(d)
            elif "reputation" in agent_type:
                result["reputation"].append(d)
        return result

    def _reconcile_financials(self, raw_data: dict[str, dict]) -> Optional[FinancialsBundle]:
        """
        Reconcile financial data using source priority.

        Priority: ProPublica > Candid > Charity Navigator
        """
        # Priority order for financial fields
        priority = self.mapper.FIELD_PRIORITY["financial"]

        # Collect values from all sources
        fields = [
            "total_revenue", "total_expenses", "total_assets", "total_liabilities",
            "net_assets", "program_expenses", "admin_expenses", "fundraising_expenses"
        ]

        financials: dict[str, Any] = {}
        primary_source = None

        for field in fields:
            for source in priority:
                if source in raw_data:
                    # Map source field name to our unified name
                    mapped_data = self.mapper.map_source_to_unified(source, raw_data[source])
                    if field in mapped_data and mapped_data[field] is not None:
                        financials[field] = mapped_data[field]
                        if primary_source is None:
                            primary_source = source
                        break

        if not financials:
            return None

        # Calculate program expense ratio if we have the data
        if financials.get("program_expenses") and financials.get("total_expenses"):
            total = financials["total_expenses"]
            if total > 0:
                ratio = financials["program_expenses"] / total
                # Normalize to 0-1 range
                financials["program_expense_ratio"] = min(1.0, max(0.0, ratio))

        # Get fiscal year from ProPublica
        if "propublica" in raw_data:
            pp_data = self.mapper.map_source_to_unified("propublica", raw_data["propublica"])
            if "fiscal_year_end" in pp_data:
                financials["fiscal_year"] = self.mapper.extract_calendar_year(pp_data["fiscal_year_end"])

        return FinancialsBundle(
            source=primary_source or "unknown",
            **financials
        )

    def _build_legal_status(
        self, ein: str, charity: dict, raw_data: dict[str, dict]
    ) -> LegalStatus:
        """Build legal status from IRS data."""
        ntee_code = None
        subsection = None
        ruling_date = None

        # Get from ProPublica (IRS source)
        if "propublica" in raw_data:
            pp = raw_data["propublica"]
            ntee_code = pp.get("ntee_code")
            subsection = pp.get("subsection_code") or pp.get("subsection")
            ruling_date = pp.get("ruling_date")

        # Fallback to Candid
        if not ntee_code and "candid" in raw_data:
            candid = raw_data["candid"]
            ntee_code = candid.get("ntee_code")

        return LegalStatus(
            ein=ein,
            name=charity.get("name", "Unknown"),
            ntee_code=ntee_code,
            subsection_code=subsection,
            ruling_date=ruling_date,
        )

    def _process_rating_discoveries(self, discoveries: list[dict]) -> list[RatingEntry]:
        """Convert rating discoveries to RatingEntry list."""
        ratings = []
        for d in discoveries:
            parsed = d.get("parsed_data", {})
            if not parsed:
                continue

            ratings.append(RatingEntry(
                source_name=parsed.get("source_name", d.get("source_name", "Unknown")),
                source_url=d.get("source_url"),
                rating_value=parsed.get("rating_value"),
                rating_max=parsed.get("rating_max"),
                rating_type=parsed.get("rating_type"),
                confidence=d.get("confidence", 0.8),
            ))
        return ratings

    def _process_profile_discoveries(self, discoveries: list[dict]) -> list[ProfileEntry]:
        """Convert profile discoveries to ProfileEntry list."""
        profiles = []
        for d in discoveries:
            parsed = d.get("parsed_data", {})
            if not parsed:
                continue

            profiles.append(ProfileEntry(
                source_name=d.get("source_name", "Unknown"),
                source_url=d.get("source_url"),
                mission_statement=parsed.get("mission_statement"),
                programs=parsed.get("programs", []),
                geographic_scope=parsed.get("geographic_scope"),
                year_founded=parsed.get("year_founded"),
                leadership=parsed.get("leadership", []),
            ))
        return profiles

    def _process_evidence_discoveries(self, discoveries: list[dict]) -> list[EvidenceEntry]:
        """Convert evidence discoveries to EvidenceEntry list."""
        evidence = []
        for d in discoveries:
            parsed = d.get("parsed_data", {})
            if not parsed:
                continue

            evidence.append(EvidenceEntry(
                source_name=d.get("source_name", "Unknown"),
                source_url=d.get("source_url"),
                evidence_type=parsed.get("evidence_type", "anecdotal"),
                summary=parsed.get("summary"),
                evaluator=parsed.get("evaluator"),
                year=parsed.get("year"),
                confidence=d.get("confidence", 0.6),
            ))
        return evidence

    def _process_reputation_discoveries(self, discoveries: list[dict]) -> list[ReputationEntry]:
        """Convert reputation discoveries to ReputationEntry list."""
        reputation = []
        for d in discoveries:
            parsed = d.get("parsed_data", {})
            if not parsed:
                continue

            reputation.append(ReputationEntry(
                source_name=d.get("source_name", "Unknown"),
                source_url=d.get("source_url"),
                headline=parsed.get("headline"),
                summary=parsed.get("summary"),
                sentiment=parsed.get("sentiment", "neutral"),
                date=parsed.get("date"),
                resolved=parsed.get("resolved"),
                confidence=d.get("confidence", 0.7),
            ))
        return reputation

    def _select_mission(
        self, raw_data: dict[str, dict], profiles: list[ProfileEntry]
    ) -> tuple[Optional[str], list[ConflictRecord]]:
        """
        Select primary mission statement using source priority.

        Priority: website > candid > charity_navigator
        Returns mission and any conflicts detected.
        """
        candidates: dict[str, str] = {}
        conflicts: list[ConflictRecord] = []

        # Collect from structured sources
        priority = self.mapper.FIELD_PRIORITY["mission"]
        for source in priority:
            if source in raw_data:
                mapped = self.mapper.map_source_to_unified(source, raw_data[source])
                if mapped.get("mission"):
                    candidates[source] = mapped["mission"]

        # Collect from profile discoveries
        for p in profiles:
            if p.mission_statement:
                key = f"agent:{p.source_name}"
                candidates[key] = p.mission_statement

        if not candidates:
            return None, []

        # Select by priority
        selected_source = None
        selected_value = None

        for source in priority:
            if source in candidates:
                selected_source = source
                selected_value = candidates[source]
                break

        # If no structured source, use first agent discovery
        if not selected_source and candidates:
            selected_source = list(candidates.keys())[0]
            selected_value = candidates[selected_source]

        # Log conflict if multiple sources have different missions
        if len(candidates) > 1:
            # Check if missions are meaningfully different
            unique_missions = set(m.lower().strip()[:100] for m in candidates.values())
            if len(unique_missions) > 1:
                conflicts.append(ConflictRecord(
                    field_name="mission",
                    source_values=candidates,
                    selected_source=selected_source or "unknown",
                    selected_value=selected_value,
                    selection_reason=f"Selected by source priority: {priority}",
                    conflict_type=ConflictType.TEXT_DIFFERENCE,
                    flagged_for_review=False,
                ))

        return selected_value, conflicts

    def _select_programs(
        self, raw_data: dict[str, dict], profiles: list[ProfileEntry]
    ) -> list[str]:
        """Select and merge programs from all sources."""
        all_programs: list[str] = []
        seen: set[str] = set()

        # Priority order
        priority = self.mapper.FIELD_PRIORITY["programs"]

        for source in priority:
            if source in raw_data:
                mapped = self.mapper.map_source_to_unified(source, raw_data[source])
                programs = mapped.get("programs", [])
                if isinstance(programs, list):
                    for p in programs:
                        if p and p.lower() not in seen:
                            all_programs.append(p)
                            seen.add(p.lower())

        # Add from agent discoveries
        for profile in profiles:
            for p in profile.programs:
                if p and p.lower() not in seen:
                    all_programs.append(p)
                    seen.add(p.lower())

        return all_programs

    def _select_primary_rating(self, ratings: list[RatingEntry]) -> Optional[RatingEntry]:
        """Select highest-confidence rating as primary."""
        if not ratings:
            return None

        # Prefer Charity Navigator, then highest confidence
        cn_ratings = [r for r in ratings if "charity navigator" in r.source_name.lower()]
        if cn_ratings:
            return max(cn_ratings, key=lambda r: r.confidence)

        return max(ratings, key=lambda r: r.confidence)

    def _detect_conflicts(
        self, raw_data: dict[str, dict], bundle: CharityDataBundle
    ) -> list[ConflictRecord]:
        """Detect conflicts between structured sources for key fields."""
        conflicts = []

        # Check financial field conflicts (significant variance)
        financial_fields = ["total_revenue", "total_expenses", "program_expenses"]

        for field in financial_fields:
            values: dict[str, float] = {}

            for source, data in raw_data.items():
                mapped = self.mapper.map_source_to_unified(source, data)
                if field in mapped and mapped[field] is not None:
                    try:
                        values[source] = float(mapped[field])
                    except (ValueError, TypeError):
                        continue

            if len(values) >= 2:
                # Check for >20% variance
                vals = list(values.values())
                max_val = max(vals)
                min_val = min(vals)

                if max_val > 0 and (max_val - min_val) / max_val > 0.2:
                    # Select by priority
                    priority = self.mapper.FIELD_PRIORITY["financial"]
                    selected = None
                    for src in priority:
                        if src in values:
                            selected = src
                            break

                    conflicts.append(ConflictRecord(
                        field_name=field,
                        source_values={k: v for k, v in values.items()},
                        selected_source=selected or "unknown",
                        selected_value=values.get(selected) if selected else None,
                        selection_reason=f"Selected by financial priority, variance {((max_val - min_val) / max_val * 100):.1f}%",
                        conflict_type=ConflictType.NUMERIC_MISMATCH,
                        flagged_for_review=True,  # Flag large financial discrepancies
                    ))

        return conflicts

    def _list_sources(
        self, raw_data: dict[str, dict], discoveries: dict[str, list[dict]]
    ) -> list[str]:
        """List all sources that contributed data."""
        sources = list(raw_data.keys())

        for agent_type, disc_list in discoveries.items():
            for d in disc_list:
                src = d.get("source_name", f"agent:{agent_type}")
                if src not in sources:
                    sources.append(src)

        return sources

    def _calculate_coverage(self, bundle: CharityDataBundle) -> float:
        """Calculate data coverage score (0-1)."""
        checks = [
            bundle.charity_name is not None,
            bundle.financials is not None,
            bundle.financials and bundle.financials.total_revenue is not None,
            bundle.financials and bundle.financials.program_expense_ratio is not None,
            bundle.primary_mission is not None,
            len(bundle.primary_programs) > 0,
            len(bundle.ratings) > 0,
            len(bundle.evidence) > 0,
            bundle.legal_status is not None,
            bundle.legal_status and bundle.legal_status.ntee_code is not None,
        ]

        return sum(1 for c in checks if c) / len(checks)


def reconcile_charity(ein: str) -> Optional[CharityDataBundle]:
    """Convenience function to reconcile a single charity."""
    engine = ReconciliationEngine()
    return engine.reconcile(ein)
