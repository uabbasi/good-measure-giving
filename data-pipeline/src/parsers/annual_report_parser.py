"""
Annual Report PDF parser using LLM extraction.

For PDFs that aren't Form 990s (annual reports, impact reports, financial statements),
uses LLM to extract structured information including:
- Mission and vision
- Programs and their impact
- Geographic coverage
- Financial highlights
- Leadership information
- Beneficiary stories and testimonials
"""

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pdfplumber


def repair_json(json_str: str) -> str:
    """
    Attempt to repair common JSON syntax errors from LLM output.

    Handles:
    - Trailing commas before } or ]
    - Unescaped newlines in strings
    - Truncated JSON (attempts to close brackets)
    - Control characters in strings
    """
    # Remove any leading/trailing whitespace
    json_str = json_str.strip()

    # Remove trailing commas before closing brackets
    json_str = re.sub(r",\s*}", "}", json_str)
    json_str = re.sub(r",\s*]", "]", json_str)

    # Remove control characters except valid whitespace
    json_str = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", json_str)

    # Try to close unclosed brackets (for truncated output)
    open_braces = json_str.count("{") - json_str.count("}")
    open_brackets = json_str.count("[") - json_str.count("]")

    if open_braces > 0 or open_brackets > 0:
        # Find if we're inside a string (rough heuristic)
        # If last non-whitespace char is a letter/number, we might be mid-value
        stripped = json_str.rstrip()
        if stripped and stripped[-1] not in '{}[],":\n':
            # Likely mid-value, try to close with quote if in string context
            # Check if we have an odd number of unescaped quotes
            quote_count = len(re.findall(r'(?<!\\)"', json_str))
            if quote_count % 2 == 1:
                json_str += '"'

        # Close brackets in reverse order of typical nesting
        json_str += "]" * open_brackets
        json_str += "}" * open_braces

    return json_str


@dataclass
class AnnualReportData:
    """Extracted data from any PDF document (annual report, impact report, Form 990, etc.)."""

    # Organization info
    organization_name: Optional[str] = None
    ein: Optional[str] = None
    year: Optional[int] = None
    report_type: Optional[str] = None  # 'annual_report', 'impact_report', 'form_990', 'financial_statement', 'other'

    # Mission and programs
    mission_statement: Optional[str] = None
    vision_statement: Optional[str] = None
    theory_of_change: Optional[str] = None
    programs: List[Dict[str, Any]] = None  # Now includes outcomes per program

    # OUTCOMES - Critical priority (structured, quantifiable data)
    outcomes_summary: Dict[str, Any] = (
        None  # total_beneficiaries, key_outcomes (categorized), cost_effectiveness, methodology
    )
    impact_metrics: Dict[str, Any] = None  # All measurable metrics found as key-value pairs

    # Financial
    financials: Dict[str, Any] = None  # Full financial breakdown including cost_per_beneficiary

    # Geographic
    geographic_coverage: Dict[str, Any] = None  # countries, regions, focus_areas

    # Leadership
    leadership: Dict[str, Any] = None  # ceo_name, board_size, key_staff_count

    # Transparency
    transparency: Dict[str, Any] = None  # audited_financials, ratings, certifications

    # Amal-specific scoring indicators
    systemic_leverage_indicators: Dict[str, Any] = None  # policy, media, scalable models, etc.
    ummah_gap_indicators: Dict[str, Any] = None  # orphaned causes, Muslim focus, underserved regions
    evidence_of_impact_indicators: Dict[str, Any] = None  # RCTs, longitudinal, third-party evals
    zakat_islamic_indicators: Dict[str, Any] = None  # Muslim-led, Zakat policy, Islamic governance

    # Legacy fields for backward compatibility
    beneficiaries_served: Optional[int] = None
    total_revenue: Optional[float] = None
    total_expenses: Optional[float] = None
    program_expense_ratio: Optional[float] = None
    countries_served: List[str] = None
    regions_served: List[str] = None
    ceo_message: Optional[str] = None
    stories: List[str] = None
    program_highlights: List[str] = None

    # Metadata
    page_count: Optional[int] = None
    extraction_method: str = "llm"
    truncation_occurred: bool = False  # True if PDF text was truncated before extraction

    def __post_init__(self):
        if self.programs is None:
            self.programs = []
        if self.outcomes_summary is None:
            self.outcomes_summary = {}
        if self.impact_metrics is None:
            self.impact_metrics = {}
        if self.financials is None:
            self.financials = {}
        if self.geographic_coverage is None:
            self.geographic_coverage = {}
        if self.leadership is None:
            self.leadership = {}
        if self.transparency is None:
            self.transparency = {}
        if self.systemic_leverage_indicators is None:
            self.systemic_leverage_indicators = {}
        if self.ummah_gap_indicators is None:
            self.ummah_gap_indicators = {}
        if self.evidence_of_impact_indicators is None:
            self.evidence_of_impact_indicators = {}
        if self.zakat_islamic_indicators is None:
            self.zakat_islamic_indicators = {}
        if self.countries_served is None:
            self.countries_served = []
        if self.regions_served is None:
            self.regions_served = []
        if self.stories is None:
            self.stories = []
        if self.program_highlights is None:
            self.program_highlights = []


class AnnualReportParser:
    """
    Parse annual report PDFs using LLM extraction.

    Uses LLMTask.PDF_EXTRACTION for optimal model selection:
    - Primary: Gemini 2.5 Flash (good for document understanding)
    - Fallback: Claude Sonnet 4.5 (excellent PDF comprehension)
    """

    def __init__(self, logger=None, premium: bool = False):
        """
        Initialize parser.

        Args:
            logger: Optional logger instance
            premium: If True, use PREMIUM_PDF_EXTRACTION (Claude Sonnet 4.5)
        """
        self.logger = logger
        self.premium = premium
        self._llm_client = None

    def _get_llm_client(self):
        """Lazy initialization of LLM client with task-based selection."""
        if self._llm_client is None:
            from ..llm.llm_client import LLMClient, LLMTask

            task = LLMTask.PREMIUM_PDF_EXTRACTION if self.premium else LLMTask.PDF_EXTRACTION
            self._llm_client = LLMClient(task=task, logger=self.logger)
        return self._llm_client

    def parse_pdf(self, pdf_path: Path) -> Tuple[Optional[AnnualReportData], float]:
        """
        Parse annual report PDF and extract data using LLM.

        Args:
            pdf_path: Path to PDF file

        Returns:
            Tuple of (AnnualReportData, cost_in_usd) or (None, 0.0) if failed
        """
        try:
            # Extract text from PDF
            text = self._extract_pdf_text(pdf_path)
            if not text:
                if self.logger:
                    self.logger.warning(f"No text extracted from {pdf_path}")
                return None, 0.0

            # Count pages
            with pdfplumber.open(pdf_path) as pdf:
                page_count = len(pdf.pages)

            # Use LLM to extract structured data
            data, cost = self._extract_with_llm(text, page_count)

            if data and self.logger:
                self.logger.debug(
                    f"Parsed annual report: {data.organization_name or 'Unknown'} "
                    f"({data.year or 'Unknown year'}) - {len(data.programs)} programs"
                )

            return data, cost

        except Exception as e:
            if self.logger:
                self.logger.error(f"Failed to parse annual report {pdf_path}: {e}")
            return None, 0.0

    def _extract_pdf_text(self, pdf_path: Path, max_pages: int = 30) -> str:
        """Extract text from PDF, limiting to first N pages."""
        try:
            text_parts = []
            with pdfplumber.open(pdf_path) as pdf:
                for i, page in enumerate(pdf.pages[:max_pages]):
                    page_text = page.extract_text()
                    if page_text:
                        text_parts.append(f"--- PAGE {i + 1} ---\n{page_text}")

            return "\n\n".join(text_parts)
        except Exception as e:
            if self.logger:
                self.logger.error(f"PDF text extraction failed: {e}")
            return ""

    def _extract_with_llm(self, text: str, page_count: int) -> Tuple[Optional[AnnualReportData], float]:
        """Use LLM to extract structured data from report text."""
        # Truncate text if too long (limit to ~500k tokens / 2M chars for Gemini Flash)
        max_chars = 2_000_000
        truncation_occurred = False
        if len(text) > max_chars:
            truncation_occurred = True
            original_len = len(text)
            text = text[:max_chars] + "\n\n[TRUNCATED - Report continues...]"
            if self.logger:
                self.logger.warning(
                    f"PDF text truncated from {original_len:,} to {max_chars:,} chars "
                    f"({original_len - max_chars:,} chars lost). Critical outcome data may be missing."
                )

        prompt = f"""You are analyzing a PDF document from a charity/nonprofit organization.
This could be an annual report, impact report, Form 990, financial statement, zakat guide, or any other document.
Extract STRUCTURED information and return it as a valid JSON object.

⚠️ CRITICAL INSTRUCTION FOR DATA QUALITY:

This extraction is for the CHARITY'S OWN organizational data, NOT client cases or third-party statistics.

If this document describes CLIENTS the organization serves (not the organization's own programs):
  - Extract ONLY the organization's SERVICE (e.g., "legal defense services") in programs
  - DO NOT extract client case outcomes, client statistics, or beneficiary data from cases

RED FLAGS that indicate client/case data (DO NOT EXTRACT as organizational outcomes):
  ❌ Document describes a specific lawsuit, court case, or legal proceeding
  ❌ Statistics about people/events the organization advocates for (not people they directly serve)
  ❌ Third-party beneficiaries (e.g., "Palestinians in Gaza" for a US-based legal org)
  ❌ Case outcomes like "charges dropped", "lawsuits won" (unless org directly provides the service)
  ❌ Client organization names that differ from the charity being evaluated

EXAMPLES:
✓ CORRECT: "MLFA provided legal defense to 50 Muslim clients in immigration cases"
  → Extract program="Immigration Legal Defense", outcomes="50 clients served"

✗ WRONG: "MLFA filed brief supporting Palestine Solidarity Committee. PSC members: 200 students."
  → DO NOT extract beneficiaries=200 or outcomes about students
  → Extract program="Civil Rights Advocacy" only

If you are unsure whether data is organizational vs. client/case data, set this field in your JSON response:
"data_quality_concern": "Possible client case data, not organizational outcomes"

EXTRACTION PRIORITIES (in order):

1. PROGRAMS - Extract every distinct program/initiative with:
   - Official program name
   - Clear description of what it does
   - Target beneficiaries (who it helps)
   - Measurable outcomes specific to that program
   - **Program type**: Direct relief vs. structural change (education, policy, economic empowerment)

2. SYSTEMIC LEVERAGE INDICATORS - Look for evidence of:
   - **Policy advocacy** or legislative wins
   - **Media/narrative influence** (national coverage, messaging campaigns)
   - **Scalable models**: train-the-trainer, franchise, replicable IP
   - **Economic sovereignty**: endowments, Awqaf, riba-free financing
   - **Legal aid** or civil rights work
   - **Climate adaptation** work (not just disaster relief)

3. UMMAH GAP INDICATORS - Look for:
   - **Orphaned causes**: addiction, prison re-entry, domestic violence, mental health, disability
   - **Stigmatized populations** specifically mentioned
   - **Muslim-specific focus** vs. general public benefit
   - **Underserved regions**: rural areas, conflict zones, neglected communities
   - **Climate-vulnerable regions** (OIC nations, "Heat Belt")
   - **CRITICAL**: Extract QUANTITATIVE gap data:
     * HOW MANY beneficiaries served (e.g., "5,000 Muslim inmates annually")
     * WHO specifically (demographics: "low-income Muslim families", "Syrian refugees")
     * WHERE specifically (locations: "30 federal prisons in 12 states", "rural Pakistan")
     * WHY underserved (evidence of gap: "only 3 Islamic food banks for 150K Muslims", "Muslims are 9% of inmates but <1% receive chaplaincy")

4. THEORY OF CHANGE - How the organization believes their work creates lasting impact:
   - Input → Activity → Output → Outcome → Impact chain
   - Logic model or intervention theory
   - How they measure success

5. OUTCOMES (quantifiable results):
   - Specific numbers: people served, meals provided, schools built, etc.
   - Before/after metrics with percentages
   - Cost per beneficiary or cost per outcome
   - Long-term vs short-term impact measurements
   - Geographic reach (countries, regions, communities)

6. EVIDENCE OF IMPACT INDICATORS - Look for:
   - **RCTs** (randomized controlled trials) or experiments
   - **Longitudinal tracking** (multi-year follow-up of beneficiaries)
   - **Counterfactual analysis** (what would have happened without intervention)
   - **Third-party evaluations** or independent research
   - **Comparison groups** or control groups

7. FINANCIAL DATA - Program expenses, ratios, efficiency metrics

8. ZAKAT/ISLAMIC INDICATORS - Look for:
   - **Muslim-led** or Islamic governance structure
   - **Explicit Zakat policy** or segregated Zakat funds
   - **Islamic board members** or scholars
   - **Zakat-eligible beneficiaries** explicitly mentioned (Al-Fuqara, Al-Masakin, etc.)

EXTRACTION RULES:
- Focus on STRUCTURED, FACTUAL data - not marketing language or anecdotes
- Extract ALL programs mentioned, even if briefly described
- For numeric values, return numbers without commas or currency symbols
- For arrays, return empty array [] if no data found
- For optional fields, use null if not found
- Prioritize quantifiable metrics over qualitative descriptions
- **Be explicit about evidence** - if you find RCTs, policy wins, or Muslim governance, flag them clearly

PDF Text Content:
{text}

Return a JSON object with this structure:
{{
    "organization_name": "string (official organization name)",
    "ein": "string (EIN if found, format: XX-XXXXXXX)",
    "year": number (report year or fiscal year, e.g., 2023),
    "report_type": "string (annual_report, impact_report, form_990, financial_statement, other)",

    "mission_statement": "string (organization's mission)",
    "vision_statement": "string (organization's vision, if different from mission)",
    "theory_of_change": "string (how they believe their work creates change)",

    "programs": [
        {{
            "name": "string (program name)",
            "description": "string (what the program does)",
            "beneficiaries": "string (who it serves)",
            "program_type": "string (relief, education, policy_advocacy, legal_aid, economic_empowerment, climate_adaptation, other)",
            "budget": number (program budget if mentioned),
            "outcomes": [
                {{
                    "metric": "string (what is measured)",
                    "value": "string or number (the measurement)",
                    "period": "string (time period if specified)"
                }}
            ]
        }}
    ],

    "systemic_leverage_indicators": {{
        "policy_advocacy": ["array of policy wins, legislative changes, or advocacy campaigns"],
        "media_influence": ["array of media coverage, narrative campaigns, or messaging work"],
        "scalable_models": ["array of franchises, train-the-trainer, or replicable IP"],
        "economic_sovereignty": ["array of endowments, Awqaf, riba-free financing"],
        "legal_aid": ["array of legal services, civil rights work, or litigation"],
        "climate_adaptation": ["array of climate resilience programs (not relief)"]
    }},

    "ummah_gap_indicators": {{
        "orphaned_causes": ["array: addiction, prison, domestic violence, mental health, disability"],
        "muslim_specific_focus": boolean (explicitly targets Muslims vs. general public?),
        "underserved_regions": ["array: rural, conflict zones, neglected communities"],
        "climate_vulnerable_regions": ["array: OIC nations or Heat Belt countries"],

        // QUANTITATIVE GAP DATA (for scoring - extract specific numbers if present):
        "beneficiary_count": number (total people served annually, if mentioned),
        "beneficiary_demographics": "string (WHO specifically: 'Muslim inmates', 'Syrian refugees', 'low-income Muslim families')",
        "geographic_specificity": "string (WHERE: '30 federal prisons in 12 states', 'rural Pakistan', 'Detroit area with 150K+ Muslims')",
        "gap_evidence": "string (WHY underserved: quantifiable evidence of the gap, e.g., 'only 3 Islamic food banks serve 150K Muslims', 'Muslims are 9% of inmates but <1% receive chaplaincy')"
    }},

    "evidence_of_impact_indicators": {{
        "has_rcts": boolean (randomized controlled trials mentioned?),
        "longitudinal_tracking": boolean (multi-year follow-up of beneficiaries?),
        "counterfactual_analysis": boolean (compares to what would have happened without intervention?),
        "third_party_evaluations": ["array of independent evaluations or research"],
        "comparison_groups": boolean (uses control groups or comparison populations?)
    }},

    "zakat_islamic_indicators": {{
        "muslim_led": boolean (Muslim-led or Islamic governance?),
        "has_zakat_policy": boolean (explicit Zakat policy or segregated funds?),
        "islamic_board_members": boolean (Islamic scholars or Muslim board members mentioned?),
        "zakat_eligible_beneficiaries": ["array of 8 categories if mentioned: Al-Fuqara, Al-Masakin, etc."]
    }},

    "outcomes_summary": {{
        "total_beneficiaries": number (total people served if mentioned),
        "key_outcomes": [
            {{
                "category": "string (e.g., education, health, food security, shelter)",
                "metric": "string (specific measurable outcome)",
                "value": "number or string (the measurement)",
                "unit": "string (e.g., people, meals, schools, dollars)",
                "period": "string (time period if specified)"
            }}
        ],
        "cost_effectiveness": {{
            "cost_per_beneficiary": number,
            "cost_per_outcome": "string (e.g., '$5 per meal', '$200 per student/year')"
        }},
        "outcome_methodology": "string (how they measure/track outcomes - surveys, third-party evaluation, etc.)"
    }},

    "impact_metrics": {{
        "metric_name": "value (can be string or number) - include ALL metrics found"
    }},

    "financials": {{
        "total_revenue": number,
        "total_expenses": number,
        "program_expenses": number,
        "admin_expenses": number,
        "fundraising_expenses": number,
        "program_expense_ratio": number (percentage 0-100),
        "cost_per_beneficiary": number (if calculable)
    }},

    "geographic_coverage": {{
        "countries": ["array of country names where they operate"],
        "regions": ["array of regions/states/cities served"],
        "focus_areas": ["array of specific locations of major programs"]
    }},

    "leadership": {{
        "ceo_name": "string",
        "board_size": number,
        "key_staff_count": number
    }},

    "transparency": {{
        "audited_financials": boolean (mentions independent audit?),
        "ratings": ["array of third-party ratings: Charity Navigator, GuideStar, BBB, etc."],
        "certifications": ["array of certifications or accreditations"]
    }},

    "data_quality_concern": "string or null (OPTIONAL: Set only if you suspect this data is from a client case/third-party instead of the organization's own programs. Explain your concern.)"
}}

Return ONLY the JSON object, no additional text."""

        try:
            llm_client = self._get_llm_client()
            response = llm_client.generate(prompt=prompt, temperature=0.1, max_tokens=4096, json_mode=True)

            # Parse JSON response
            response_text = response.text
            if "```json" in response_text:
                json_str = response_text.split("```json")[1].split("```")[0].strip()
            elif "```" in response_text:
                json_str = response_text.split("```")[1].split("```")[0].strip()
            else:
                json_str = response_text.strip()

            # Try parsing JSON, with repair fallback
            try:
                extracted = json.loads(json_str)
            except json.JSONDecodeError as first_error:
                # Try repairing common LLM JSON errors
                repaired_str = repair_json(json_str)
                try:
                    extracted = json.loads(repaired_str)
                    if self.logger:
                        self.logger.info(f"JSON repaired successfully (original error: {first_error})")
                except json.JSONDecodeError:
                    # Log the raw response for debugging and re-raise original error
                    if self.logger:
                        self.logger.error(f"JSON repair failed. Raw response (first 500 chars): {json_str[:500]}")
                    raise first_error

            # Extract nested structures with defensive checks
            outcomes = extracted.get("outcomes_summary", {})
            if not isinstance(outcomes, dict):
                outcomes = {}

            financials = extracted.get("financials", {})
            if not isinstance(financials, dict):
                financials = {}

            geo = extracted.get("geographic_coverage", {})
            if not isinstance(geo, dict):
                geo = {}

            leadership_data = extracted.get("leadership", {})
            if not isinstance(leadership_data, dict):
                leadership_data = {}

            # Extract Amal-specific scoring indicators
            systemic_leverage = extracted.get("systemic_leverage_indicators", {})
            if not isinstance(systemic_leverage, dict):
                systemic_leverage = {}

            ummah_gap = extracted.get("ummah_gap_indicators", {})
            if not isinstance(ummah_gap, dict):
                ummah_gap = {}

            evidence_impact = extracted.get("evidence_of_impact_indicators", {})
            if not isinstance(evidence_impact, dict):
                evidence_impact = {}

            zakat_islamic = extracted.get("zakat_islamic_indicators", {})
            if not isinstance(zakat_islamic, dict):
                zakat_islamic = {}

            # Convert to AnnualReportData with new comprehensive structure
            data = AnnualReportData(
                organization_name=extracted.get("organization_name"),
                ein=extracted.get("ein"),
                year=extracted.get("year"),
                report_type=extracted.get("report_type"),
                mission_statement=extracted.get("mission_statement"),
                vision_statement=extracted.get("vision_statement"),
                theory_of_change=extracted.get("theory_of_change"),
                programs=extracted.get("programs", []),
                # New outcomes-focused fields
                outcomes_summary=outcomes,
                impact_metrics=extracted.get("impact_metrics", {}),
                financials=financials,
                geographic_coverage=geo,
                leadership=leadership_data,
                transparency=extracted.get("transparency", {}),
                # Amal-specific scoring indicators
                systemic_leverage_indicators=systemic_leverage,
                ummah_gap_indicators=ummah_gap,
                evidence_of_impact_indicators=evidence_impact,
                zakat_islamic_indicators=zakat_islamic,
                # Legacy compatibility - extract from nested structures
                beneficiaries_served=outcomes.get("total_beneficiaries"),
                total_revenue=financials.get("total_revenue"),
                total_expenses=financials.get("total_expenses"),
                program_expense_ratio=financials.get("program_expense_ratio"),
                countries_served=geo.get("countries", []),
                regions_served=geo.get("regions", []),
                ceo_message=None,  # Removed - focusing on structured data
                stories=[],  # Removed - focusing on structured outcomes instead
                program_highlights=[],  # Removed - using programs with outcomes
                page_count=page_count,
                extraction_method="llm",
                truncation_occurred=truncation_occurred,
            )

            return data, response.cost_usd

        except json.JSONDecodeError as e:
            if self.logger:
                self.logger.error(f"JSON parsing failed: {e}")
            return None, 0.0
        except Exception as e:
            if self.logger:
                self.logger.error(f"LLM extraction failed: {e}")
            return None, 0.0

    def to_dict(self, data: AnnualReportData) -> Dict[str, Any]:
        """Convert AnnualReportData to dictionary."""
        return {
            "organization_name": data.organization_name,
            "ein": data.ein,
            "year": data.year,
            "report_type": data.report_type,
            "mission_statement": data.mission_statement,
            "vision_statement": data.vision_statement,
            "theory_of_change": data.theory_of_change,
            "programs": data.programs,
            # OUTCOMES - Primary focus
            "outcomes_summary": data.outcomes_summary,
            "impact_metrics": data.impact_metrics,
            # Full structures
            "financials": data.financials,
            "geographic_coverage": data.geographic_coverage,
            "leadership": data.leadership,
            "transparency": data.transparency,
            # Legacy compatibility
            "beneficiaries_served": data.beneficiaries_served,
            "stories": data.stories,
            "financial_data": {
                "total_revenue": data.total_revenue,
                "total_expenses": data.total_expenses,
                "program_expense_ratio": data.program_expense_ratio,
            },
            "countries_served": data.countries_served,
            "regions_served": data.regions_served,
            "ceo_message": data.ceo_message,
            "page_count": data.page_count,
            "extraction_method": data.extraction_method,
            "truncation_occurred": data.truncation_occurred,
        }
