"""
LLM-powered website data extraction.

Uses centralized LLMClient with task-based model selection.
Task: WEBSITE_EXTRACTION (Gemini 3 Flash + JSON Schema)
"""

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import yaml
from bs4 import BeautifulSoup
from pydantic import BaseModel

from ..validators.llm_responses import PAGE_TYPE_SCHEMAS
from .llm_client import MODEL_GPT52, LLMClient, LLMTask


def _is_empty(val: Any) -> bool:
    """Check if a value is empty, including LLM artifacts like the string 'null'."""
    if val is None or val == "" or val == []:
        return True
    if isinstance(val, str) and val.strip().lower() in ("null", "none", "n/a"):
        return True
    return False


def repair_json(json_str: str) -> str:
    """
    Attempt to repair common JSON syntax errors from LLM output.

    Handles:
    - Trailing commas before } or ]
    - Control characters in strings
    - Truncated JSON (attempts to close brackets)
    """
    json_str = json_str.strip()

    # Remove trailing commas before closing brackets
    json_str = re.sub(r",\s*}", "}", json_str)
    json_str = re.sub(r",\s*]", "]", json_str)

    # Remove control characters except valid whitespace
    json_str = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", json_str)

    # Try to close unclosed brackets
    open_braces = json_str.count("{") - json_str.count("}")
    open_brackets = json_str.count("[") - json_str.count("]")

    if open_braces > 0 or open_brackets > 0:
        stripped = json_str.rstrip()
        if stripped and stripped[-1] not in '{}[],":\n':
            quote_count = len(re.findall(r'(?<!\\)"', json_str))
            if quote_count % 2 == 1:
                json_str += '"'
        json_str += "]" * open_brackets
        json_str += "}" * open_braces

    return json_str


class WebsiteExtractor:
    """
    Extract structured data from charity websites using LLMs.

    Uses LLMTask.WEBSITE_EXTRACTION for optimal model selection:
    - Primary: Gemini 2.5 Flash-Lite (cheap, fast)
    - Fallback: Claude Haiku 4.5 (strict JSON)
    """

    def __init__(
        self,
        provider: str = "gemini",  # Kept for backward compatibility, ignored
        api_key: Optional[str] = None,  # Kept for backward compatibility, ignored
        logger=None,
    ):
        """
        Initialize website extractor.

        Args:
            provider: Ignored (kept for backward compatibility)
            api_key: Ignored (kept for backward compatibility)
            logger: Logger instance
        """
        self.logger = logger

        # Initialize LLMClient with WEBSITE_EXTRACTION task
        self.llm_client = LLMClient(task=LLMTask.WEBSITE_EXTRACTION, logger=logger)

        # Load page-specific prompts from YAML (T051)
        self.page_prompts = self._load_page_prompts()

    # Fields where Flash is known to hallucinate — require GPT-5.2 confirmation
    HALLUCINATION_PRONE_FIELDS = {
        "systemic_leverage_data",
        "absorptive_capacity_data",
        "ummah_gap_data",
        "evidence_of_impact_data",
        "geographic_coverage",
        "founded_year",
        "populations_served",
    }

    # Fields that are safe to trust from Flash alone (URLs, names, simple facts)
    TRUSTED_FIELDS = {
        "url",
        "ein",
        "ein_mentioned",
        "name",
        "mission",
        "vision_statement",
        "donate_url",
        "donation_page_url",
        "donation_methods",
        "tax_deductible",
        "contact_email",
        "contact_phone",
        "address",
        "has_annual_report",
        "annual_report_url",
        "has_impact_report",
        "impact_report_url",
        "transparency_info",
        "volunteer_opportunities",
        "volunteer_page_url",
        "social_media",
        "accepts_zakat",
        "zakat_evidence",
        "zakat_url",
        "llm_extracted_pdfs",
        "pdf_outcomes",
        "outcomes_data",
        "pdf_extraction_sources",
    }

    def extract(self, pages: List[Tuple[str, str]], base_url: str) -> Tuple[Dict[str, Any], float]:
        """
        Extract structured data using dual-model ensemble.

        Flash extracts first (high recall, cheap), then GPT-5.2 validates
        hallucination-prone fields. Fields both models agree on are kept;
        Flash-only claims in prone fields are dropped.

        Args:
            pages: List of (url, html) tuples
            base_url: Base URL of website

        Returns:
            Tuple of (extracted_data dict, total cost in USD)
        """
        page_contents = self._prepare_pages(pages)
        prompt = self._build_prompt(page_contents, base_url)

        # 1. Flash extraction (primary — high recall)
        flash_data, flash_cost = self._extract_with_llm(prompt)
        if "error" in flash_data:
            return flash_data, flash_cost

        # 2. GPT-5.2 extraction (validator — high precision)
        verifier_data, verifier_cost = self._extract_with_verifier(prompt)
        total_cost = flash_cost + verifier_cost

        if "error" in verifier_data:
            if self.logger:
                self.logger.warning("Verifier extraction failed, using Flash-only (unverified)")
            return flash_data, total_cost

        # 3. Merge: Flash baseline, verified by GPT-5.2
        merged = self._merge_ensemble(flash_data, verifier_data)

        if self.logger:
            # Count leaf-level values to capture nested drops
            def count_values(d):
                n = 0
                for v in d.values():
                    if isinstance(v, dict):
                        n += count_values(v)
                    elif isinstance(v, list):
                        n += len(v) if v else 0
                    elif v is not None and v != "":
                        n += 1
                return n

            flash_vals = count_values(flash_data)
            merged_vals = count_values(merged)
            dropped = flash_vals - merged_vals
            self.logger.info(
                f"Ensemble merge: Flash {flash_vals} leaf values, "
                f"kept {merged_vals}, dropped {dropped} unverified "
                f"(cost: ${total_cost:.4f})"
            )

        return merged, total_cost

    def _extract_with_verifier(self, prompt: str) -> Tuple[Dict[str, Any], float]:
        """Run GPT-5.2 as a precision verifier."""
        try:
            verifier = LLMClient(
                model=MODEL_GPT52,
                logger=self.logger,
            )
            if self.logger:
                self.logger.info(f"Running verifier ({MODEL_GPT52}) for ensemble...")

            llm_response = verifier.generate(prompt=prompt, temperature=0, max_tokens=8192, json_mode=True)

            response_text = llm_response.text
            json_str = None
            try:
                if "```json" in response_text:
                    parts = response_text.split("```json")
                    if len(parts) > 1:
                        inner = parts[1].split("```")
                        json_str = inner[0].strip() if inner else parts[1].strip()
                elif "```" in response_text:
                    parts = response_text.split("```")
                    if len(parts) > 1:
                        json_str = parts[1].strip()
                else:
                    json_str = response_text.strip()
            except (IndexError, AttributeError):
                json_str = response_text.strip()

            if not json_str:
                raise ValueError("Empty JSON from verifier")

            try:
                data = json.loads(json_str)
            except json.JSONDecodeError:
                repaired = repair_json(json_str)
                data = json.loads(repaired)

            return data, llm_response.cost_usd

        except Exception as e:
            if self.logger:
                self.logger.warning(f"Verifier extraction failed: {e}")
            return {"error": str(e)}, 0.0

    def _merge_ensemble(self, flash: Dict[str, Any], verifier: Dict[str, Any]) -> Dict[str, Any]:
        """
        Merge Flash (high recall) with GPT-5.2 (high precision).

        Strategy:
        - Trusted fields: keep Flash value (URLs, contact info, etc.)
        - Hallucination-prone fields: only keep if verifier confirms
        - Other fields: keep Flash, prefer verifier if both have data
        """
        # Defensive: ensure both inputs are dicts
        if not isinstance(flash, dict):
            flash = {}
        if not isinstance(verifier, dict):
            verifier = {}

        merged = {}

        all_keys = set(flash.keys()) | set(verifier.keys())

        for key in all_keys:
            flash_val = flash.get(key)
            verifier_val = verifier.get(key)

            flash_empty = _is_empty(flash_val)
            verifier_empty = _is_empty(verifier_val)

            if key in self.TRUSTED_FIELDS:
                # Trust Flash for safe fields (URLs, contact, etc.)
                merged[key] = flash_val if not flash_empty else verifier_val
            elif key in self.HALLUCINATION_PRONE_FIELDS:
                # Require verifier confirmation for prone fields
                if flash_empty and verifier_empty:
                    merged[key] = None
                elif flash_empty and not verifier_empty:
                    merged[key] = verifier_val
                elif not flash_empty and verifier_empty:
                    # Flash claims something, verifier doesn't — drop it
                    merged[key] = self._null_for_type(flash_val)
                else:
                    # Both have values — merge intelligently
                    merged[key] = self._merge_field(key, flash_val, verifier_val)
            else:
                # Default: keep Flash, use verifier as supplement
                if not flash_empty:
                    merged[key] = flash_val
                else:
                    merged[key] = verifier_val

        return merged

    def _merge_field(self, key: str, flash_val: Any, verifier_val: Any) -> Any:
        """Merge two non-empty values for a hallucination-prone field."""
        # Lists: intersection (keep items the verifier also found)
        if isinstance(flash_val, list) and isinstance(verifier_val, list):
            if all(isinstance(x, str) for x in flash_val):
                return self._intersect_string_lists(flash_val, verifier_val)
            # Complex lists (dicts) — prefer verifier
            return verifier_val

        # Dicts: merge, preferring verifier for nested values
        if isinstance(flash_val, dict) and isinstance(verifier_val, dict):
            return self._merge_dicts(flash_val, verifier_val)

        # Scalars: prefer verifier (more conservative)
        return verifier_val

    def _intersect_string_lists(self, flash_list: List[str], verifier_list: List[str]) -> List[str]:
        """Keep Flash items that have a fuzzy match in verifier list."""
        if not verifier_list:
            return []

        verifier_lower = {v.lower() for v in verifier_list}
        verifier_words = set()
        for v in verifier_list:
            verifier_words.update(w.lower() for w in v.split() if len(w) > 3)

        result = []
        for item in flash_list:
            item_lower = item.lower()
            # Exact match
            if item_lower in verifier_lower:
                result.append(item)
                continue
            # Fuzzy: >50% of significant words appear in verifier corpus
            words = [w.lower() for w in item.split() if len(w) > 3]
            if words:
                overlap = sum(1 for w in words if w in verifier_words)
                if overlap >= len(words) * 0.5:
                    result.append(item)

        return result

    def _merge_dicts(self, flash_dict: Dict, verifier_dict: Dict) -> Dict:
        """Merge dicts: only keep sub-fields the verifier also populated."""
        merged = {}
        for key in set(flash_dict.keys()) | set(verifier_dict.keys()):
            fv = flash_dict.get(key)
            vv = verifier_dict.get(key)
            fv_empty = _is_empty(fv) or fv == {}
            vv_empty = _is_empty(vv) or vv == {}

            if not vv_empty and not fv_empty:
                # Both have values — intersect lists, prefer verifier for scalars
                if isinstance(fv, list) and isinstance(vv, list):
                    if all(isinstance(x, str) for x in fv):
                        merged[key] = self._intersect_string_lists(fv, vv)
                    else:
                        merged[key] = vv
                else:
                    merged[key] = vv
            elif not vv_empty:
                # Only verifier has it — trust it
                merged[key] = vv
            elif not fv_empty:
                # Only Flash has it — drop it (unverified)
                merged[key] = self._null_for_type(fv)
            else:
                merged[key] = None
        return merged

    @staticmethod
    def _null_for_type(val: Any) -> Any:
        """Return the appropriate empty value for the type."""
        if isinstance(val, list):
            return []
        if isinstance(val, dict):
            return {}
        return None

    def _prepare_pages(self, pages: List[Tuple[str, str]]) -> List[Dict[str, str]]:
        """Convert HTML pages to clean text for LLM."""
        page_contents = []

        for url, html in pages[:10]:  # Limit to 10 pages max
            soup = BeautifulSoup(html, "html.parser")

            # Remove non-content elements
            for element in soup(["script", "style", "nav", "footer", "header", "aside"]):
                element.decompose()

            # Get clean text
            text = soup.get_text(separator="\n", strip=True)

            # Clean whitespace
            text = re.sub(r"\n\s*\n+", "\n\n", text)

            # Limit length (avoid token limits)
            max_chars = 4000  # ~1000 tokens per page
            if len(text) > max_chars:
                text = text[:max_chars] + "\n...[truncated]"

            page_contents.append({"url": url, "content": text})

        return page_contents

    def _build_prompt(self, page_contents: List[Dict[str, str]], base_url: str) -> str:
        """Build extraction prompt."""
        pages_text = "\n\n---PAGE SEPARATOR---\n\n".join(
            [f"URL: {page['url']}\n\nCONTENT:\n{page['content']}" for page in page_contents]
        )

        prompt = f"""You are analyzing a charity/nonprofit organization's website to extract structured information.
This is for a ZAKAT donation platform, so pay special attention to Islamic giving options.

Website Base URL: {base_url}

Here are the key pages from the website:

{pages_text}

Please extract the following information and return it as a valid JSON object. Be thorough and extract as much information as possible.

⚠️ CRITICAL ANTI-HALLUCINATION RULES:
- Only extract information that is EXPLICITLY stated on the page
- Do NOT infer, assume, or guess values for any field
- If a field is not clearly present, use null (do not make up values)
- For external evaluations (GiveWell, Charity Navigator, BBB): only include if the page EXPLICITLY mentions being rated or evaluated by that organization
- For zakat eligibility: only set to true if the page explicitly uses the word "zakat" or "zakah"
- For scholarly endorsements: only include names of scholars or institutions EXPLICITLY mentioned as endorsing the charity
- For accreditations: only include certifications EXPLICITLY claimed on the website
- For impact metrics and beneficiary counts: only include numbers EXPLICITLY stated, never estimate or calculate
- For third_party_evaluations: only include evaluations the charity EXPLICITLY mentions having received

⚠️ CRITICAL INSTRUCTION FOR DATA QUALITY:

This extraction is for the ORGANIZATION'S OWN programs and services, NOT client cases or third-party beneficiary statistics.

If website content describes CLIENT CASES, NEWS STORIES, or ADVOCACY WORK:
  - Extract the organization's SERVICE (e.g., "legal defense", "advocacy", "awareness campaigns")
  - DO NOT extract client case outcomes, news event statistics, or third-party beneficiary data as the org's direct impact

RED FLAGS for client/advocacy data (extract SERVICE only, not outcomes):
  ❌ News posts about specific lawsuits, court cases, or advocacy campaigns for other groups
  ❌ Statistics about events the organization advocates for (e.g., Gaza casualties, protest arrests)
  ❌ Client success stories where outcomes belong to the client, not the organization's direct service delivery
  ❌ Blog posts describing third-party beneficiaries (people the org supports indirectly through advocacy)

EXAMPLES:
✓ CORRECT: "MLFA provided legal defense to 150 Muslim clients facing immigration charges"
  → Extract service="Legal Defense Services", outcome="150 clients served"

✗ WRONG: "MLFA filed brief in support of student protesters. 3,100 students arrested."
  → DO NOT extract "3,100 students" as MLFA's beneficiaries
  → Extract service="Civil Rights Advocacy" only

If you see advocacy/news content but are unsure if data is organizational vs. client/event data, note it in the extraction without inflating beneficiary counts.

EXTRACTION PRIORITIES (CRITICAL for Amal Impact Matrix scoring):
1. **SYSTEMIC LEVERAGE DATA**: Look for policy wins, advocacy victories, scalable models, training programs, economic sovereignty initiatives (endowments, Awqaf), legal aid work, media influence. Classify if work is GENERATIVE (policy/systems change), SCALABLE (replicable models), or CONSUMPTIVE (one-off relief).

2. **UMMAH GAP DATA**: Look for WHO is served (specific demographics + numbers), WHERE they operate (specific locations), WHY this population is underserved (quantifiable gap evidence), and whether they serve stigmatized/orphaned causes. Examples:
   - "Serves 5,000 Muslim inmates annually in 30 federal prisons"
   - "Only Islamic mental health provider serving 150K Muslims in Detroit area"
   - "Muslims are 9% of federal inmates but <1% receive chaplaincy services"

3. **EVIDENCE OF IMPACT DATA**: Look for theory of change, RCTs/experimental research, longitudinal tracking, third-party evaluations, whether they track OUTCOMES (life improvement) vs just OUTPUTS (# served). Extract specific outcome metrics with numbers.

4. **ABSORPTIVE CAPACITY DATA**: Look for independent audits, board composition (independent vs affiliated members), total revenue/budget, financial controls, foundation grants.

5. **ZAKAT/ISLAMIC INFO**: Zakat funds, Islamic giving, Ramadan campaigns, shariah compliance, Muslim-led governance.

IMPORTANT:
- If a field is not found, use null for complex fields or empty string "" for simple text fields
- For social_media, omit the key entirely if that platform is not found (do NOT set to null)
- Search carefully for the donate/give page URL - check navigation, footers, and buttons
- For ALL scoring data fields (systemic_leverage_data, ummah_gap_data, evidence_of_impact_data, absorptive_capacity_data), extract SPECIFIC, QUANTITATIVE information with numbers, names, and concrete examples - not vague statements

CRITICAL: You MUST extract the EIN (Employer Identification Number / Tax ID). Look for patterns like:
- "EIN: 12-3456789"
- "Tax ID: 12-3456789"
- "Federal Tax ID"
- Any 9-digit number in format XX-XXXXXXX or XXXXXXXXX

Required JSON schema:
{{
  "ein": "string (REQUIRED - Tax ID/EIN in format XX-XXXXXXX, search carefully for this)",
  "name": "string (official organization name)",
  "mission_statement": "string (mission statement)",
  "vision_statement": "string (vision statement if different from mission)",
  "programs": ["array of program/service names only - e.g., 'Food Distribution', 'Education Support'"],
  "program_descriptions": ["array of detailed descriptions for each program - align with programs array"],
  "beneficiaries": ["array of populations served - e.g., 'refugees', 'children', 'elderly'"],
  "geographic_coverage": ["array of locations where they DELIVER PROGRAMS to beneficiaries (NOT HQ/office/fundraising locations). For US-based charities working overseas, list the overseas countries they serve. Only include USA if they have domestic service programs."],
  "impact_metrics": {{
    "description": "string describing impact",
    "metrics": {{"metric_name": "value"}}
  }},
  "beneficiaries_served": number (total number of people served, if mentioned),

  "_comment_ummah_gap": "=== CRITICAL: Ummah Gap Data (for scoring) ===",
  "ummah_gap_data": {{
    "beneficiary_count": number (HOW MANY people served annually - e.g., '5,000 Muslim inmates', '10,000 refugees'),
    "beneficiary_demographics": "string (WHO specifically - e.g., 'Muslim inmates in federal prisons', 'Syrian refugees', 'low-income Muslim families', 'incarcerated Muslims', 'Muslim women facing domestic violence')",
    "geographic_specificity": "string (WHERE specifically - e.g., '30 federal prisons across 12 states', 'rural Pakistan', 'Detroit area with 150K+ Muslims', 'conflict zones in Gaza and Syria')",
    "gap_evidence": "string (WHY underserved - quantifiable evidence of the gap, e.g., 'only 3 Islamic food banks serve 150K Muslims in Detroit', 'Muslims are 9% of federal inmates but <1% receive chaplaincy services', 'no Islamic mental health services in rural Texas where 50K+ Muslims live')",
    "muslim_specific_focus": boolean (explicitly targets Muslims vs. general public),
    "orphaned_causes": ["array of stigmatized/neglected causes if mentioned: 'addiction recovery', 'prison re-entry', 'domestic violence', 'mental health', 'disability support', 'homelessness'],
    "underserved_regions": ["array if mentioned: 'rural areas', 'conflict zones', 'neglected communities', 'climate-vulnerable regions']
  }},

  "_comment_systemic_leverage": "=== CRITICAL: Systemic Leverage Data (for scoring) ===",
  "systemic_leverage_data": {{
    "policy_wins": ["array of policy changes, legislation passed, or advocacy victories - e.g., 'Passed AB-123 to protect Muslim students', 'Won lawsuit against surveillance program'"],
    "media_coverage": ["array of major media mentions, campaigns, or narrative work - e.g., 'Featured in NYT op-ed on Islamophobia', 'Launched #MuslimVoicesMatter campaign'"],
    "scalable_models": ["array of franchises, train-the-trainer programs, or replicable systems - e.g., 'Curriculum adopted by 50 schools', 'Training model replicated in 10 cities'"],
    "training_programs": ["array of capacity-building or knowledge-transfer programs - e.g., 'Imam leadership training', 'Community organizer bootcamp'"],
    "economic_sovereignty_initiatives": ["array of endowments, Awqaf, riba-free financing, or wealth-building - e.g., 'Established $5M endowment fund', 'Launched Islamic microfinance program'"],
    "legal_aid_services": ["array of civil rights work, litigation, or legal advocacy - e.g., 'Defended 200 Muslims from workplace discrimination', 'Filed amicus brief in Supreme Court case'"],
    "climate_adaptation_programs": ["array of resilience-building (not just relief) in climate-vulnerable regions - e.g., 'Built flood-resistant housing in Bangladesh', 'Drought-resistant farming training in Sahel'"],
    "program_type_classification": "string (overall classification: GENERATIVE (policy/systems change), SCALABLE (replicable models), MIXED (relief + some structural), CONSUMPTIVE (one-off goods only))"
  }},

  "_comment_evidence_impact": "=== CRITICAL: Evidence of Impact Data (for scoring) ===",
  "evidence_of_impact_data": {{
    "theory_of_change": "string (How does the organization believe their work creates lasting change? Look for logic models, intervention theory, or explicit input→outcome chains)",
    "has_rcts": boolean (Does the org mention randomized controlled trials or experimental research?),
    "longitudinal_tracking": boolean (Do they track beneficiaries over multiple years to measure long-term outcomes?),
    "third_party_evaluations": ["array of independent evaluations, academic research, or external assessments - e.g., 'Harvard study found 40% employment increase', 'Evaluated by J-PAL'"],
    "comparison_groups": boolean (Do they use control groups or compare to baseline/counterfactual?),
    "tracks_outcomes_vs_outputs": boolean (Do they report OUTCOMES (behavior change, life improvement) vs just OUTPUTS (meals served, workshops held)?),
    "outcome_examples": ["array of specific outcome metrics mentioned - e.g., '85% of graduates employed after 6 months', '60% reduction in recidivism', 'Students improved reading by 2 grade levels'"],
    "measurement_methodology": "string (How do they measure impact? Surveys, follow-up interviews, administrative data, etc.)"
  }},

  "_comment_absorptive_capacity": "=== CRITICAL: Absorptive Capacity Data (for scoring) ===",
  "absorptive_capacity_data": {{
    "has_independent_audit": boolean (Does the org undergo independent financial audits? Look for mentions of 'audited financial statements', 'CPA firm', or 'independent audit'),
    "independent_board_members": number (How many independent board members? Look for board composition details),
    "total_revenue": number (Total annual revenue if mentioned - e.g., from annual reports, impact pages, or About sections),
    "financial_controls_mentioned": boolean (Do they mention internal controls, financial policies, or governance frameworks?),
    "receives_foundation_grants": boolean (Do they receive grants from major foundations? Evidence of external vetting)
  }},

  "_comment_policy_influence": "=== Policy Influence Data (for RESEARCH_POLICY track organizations) ===",
  "policy_influence": {{
    "publications": ["array of publications - reports, white papers, research papers, policy briefs (include titles if available)"],
    "peer_reviewed_count": number (count of peer-reviewed academic publications if mentioned),
    "media_mentions": ["array of significant media coverage - outlet names and topics (e.g., 'NYT op-ed on civil rights', 'NPR interview on policy reform')"],
    "policy_wins": ["array of policy changes, legislation passed, or regulations influenced by the organization's work (be specific: 'Contributed to AB-123 passage', 'Helped draft FDA guidance')"],
    "government_citations": ["array of government/institutional citations - congressional testimony, agency briefs, court amicus briefs (e.g., 'Testified before Senate Judiciary Committee', 'Cited in DOJ report')"],
    "testimony_count": number (count of congressional or legislative testimony appearances if mentioned),
    "academic_citations": number (count of academic citations if mentioned on site)
  }},

  "_comment_donation": "=== Donation Information (Note: Zakat handled by discover.py) ===",
  "donation_methods": ["array of accepted donation methods - credit card, PayPal, check, wire, DAF, etc."],
  "donation_page_url": "string (URL to donation page, if different from donate_url)",
  "donate_url": "string (URL to donation page)",
  "tax_deductible": "boolean (whether donations are tax-deductible)",
  "accepts_stock_donations": "boolean (accepts stock/securities donations)",
  "stock_donation_url": "string (URL to stock donation page)",
  "accepts_crypto": "boolean (accepts cryptocurrency donations)",
  "accepts_daf": "boolean (accepts donor advised fund grants)",
  "matching_gift_info": "string (employer matching gift program information)",
  "recurring_donation_available": "boolean (can set up recurring/monthly donations)",
  "minimum_donation": number (minimum donation amount if stated),

  "_comment_contact": "=== Contact Information ===",
  "ein_mentioned": "string (EIN as mentioned on website, may be formatted differently)",
  "contact_email": "string (main contact email)",
  "contact_phone": "string (main phone number)",
  "address": "string (full mailing address)",

  "_comment_org": "=== Organization Details ===",
  "founded_year": number (year organization was founded/established),
  "staff_count": number (number of full-time staff if mentioned),
  "volunteer_count": number (number of active volunteers if mentioned),
  "board_size": number (number of board members),
  "years_operating": number (years in operation),
  "accreditations": ["array of certifications - BBB Wise Giving, GuideStar Seal, Charity Navigator rated, etc."],
  "leadership": [
    {{
      "name": "string (leader name)",
      "title": "string (leadership title)"
    }}
  ],

  "_comment_engagement": "=== Engagement & Transparency ===",
  "volunteer_opportunities": "boolean (whether volunteer opportunities are available)",
  "volunteer_page_url": "string (URL to volunteer page)",
  "newsletter_signup_url": "string (URL to email newsletter signup)",
  "events_page_url": "string (URL to events/campaigns page)",
  "careers_page_url": "string (URL to careers/jobs page)",
  "social_media": {{
    "facebook": "string (URL)",
    "twitter": "string (URL)",
    "instagram": "string (URL)",
    "linkedin": "string (URL)",
    "youtube": "string (URL)"
  }},

  "_comment_transparency": "=== Financial Transparency ===",
  "annual_report_url": "string (URL to annual report PDF)",
  "form_990_url": "string (URL to Form 990 on website)",
  "financial_statements_url": "string (URL to audited financial statements)",
  "audit_report_url": "string (URL to independent audit report)",
  "transparency_info": "string (information about transparency/accountability)"
}}

NOTES:
- Remove the "_comment_*" fields from your output - they are just for organization
- For boolean fields, use true/false not strings
- Zakat/Islamic finance fields are handled by discover.py via web search, not website extraction

Return ONLY the JSON object, no additional text."""

        return prompt

    def _extract_with_llm(self, prompt: str) -> Tuple[Dict[str, Any], float]:
        """Extract using LLMClient (CHEAPEST tier)."""
        try:
            if self.logger:
                self.logger.info(f"Calling LLM API ({self.llm_client.model_name}) for website extraction...")

            # Call LLMClient with JSON mode
            llm_response = self.llm_client.generate(prompt=prompt, temperature=0, max_tokens=8192, json_mode=True)

            # Extract JSON from response
            response_text = llm_response.text

            # Handle markdown code blocks (some models ignore json_mode)
            # Safe parsing to avoid IndexError with malformed markdown
            json_str = None
            try:
                if "```json" in response_text:
                    parts = response_text.split("```json")
                    if len(parts) > 1:
                        inner = parts[1].split("```")
                        json_str = inner[0].strip() if inner else parts[1].strip()
                elif "```" in response_text:
                    parts = response_text.split("```")
                    if len(parts) > 1:
                        # Get content between first pair of backticks
                        json_str = parts[1].strip()
                else:
                    json_str = response_text.strip()
            except (IndexError, AttributeError) as e:
                if self.logger:
                    self.logger.warning(f"Failed to parse markdown blocks: {e}. Using raw text.")
                json_str = response_text.strip()

            # Parse JSON
            if not json_str:
                raise ValueError("Empty JSON string after markdown parsing")

            # Try parsing JSON, with repair fallback
            try:
                data = json.loads(json_str)
            except json.JSONDecodeError as first_error:
                # Try repairing common LLM JSON errors
                repaired_str = repair_json(json_str)
                try:
                    data = json.loads(repaired_str)
                    if self.logger:
                        self.logger.info(f"JSON repaired successfully (original error: {first_error})")
                except json.JSONDecodeError:
                    if self.logger:
                        self.logger.error(f"JSON repair failed. Raw response (first 500 chars): {json_str[:500]}")
                    raise first_error

            # Get cost from LLMResponse
            cost = llm_response.cost_usd

            if self.logger:
                self.logger.info(f"LLM extraction successful (cost: ${cost:.4f})")

            return data, cost

        except json.JSONDecodeError as e:
            if self.logger:
                self.logger.error(f"JSON parsing failed: {e}")
            return {"error": f"JSON parsing failed: {str(e)}"}, 0.0
        except Exception as e:
            if self.logger:
                self.logger.error(f"LLM extraction failed: {e}")
            return {"error": f"LLM extraction failed: {str(e)}"}, 0.0

    def _load_page_prompts(self) -> Dict[str, str]:
        """
        Load page-specific prompts from YAML config (T051).

        Returns:
            Dictionary mapping page_type -> prompt template
        """
        config_path = Path(__file__).parent.parent.parent / "config" / "page_prompts.yaml"

        if not config_path.exists():
            if self.logger:
                self.logger.warning(f"page_prompts.yaml not found at {config_path}, using default prompts")
            return {}

        try:
            with open(config_path, "r") as f:
                prompts = yaml.safe_load(f)
                if self.logger:
                    self.logger.debug(f"Loaded {len(prompts)} page-specific prompts from YAML")
                return prompts
        except Exception as e:
            if self.logger:
                self.logger.error(f"Failed to load page_prompts.yaml: {e}")
            return {}

    def extract_with_schema(
        self, page_text: str, page_type: str, page_url: str, max_retries: int = 1
    ) -> Tuple[Optional[BaseModel], float]:
        """
        Extract semantic fields from a single page using page-specific prompt and schema validation (T052, T053, T054).

        This method:
        1. Selects the appropriate prompt based on page_type
        2. Calls LLM with the prompt
        3. Validates response against the page_type's Pydantic schema using instructor
        4. Retries once on validation failure with stricter prompt

        Args:
            page_text: Cleaned markdown text from TextCleaner
            page_type: Page classification (homepage, about, programs, impact, donate, contact)
            page_url: URL of the page being extracted
            max_retries: Maximum retry attempts (default 1)

        Returns:
            Tuple of (validated_response_model or None, cost_in_usd)
        """
        # Get prompt template for this page type
        prompt_key = f"{page_type}_prompt"
        if prompt_key not in self.page_prompts:
            if self.logger:
                self.logger.warning(f"No prompt found for page type: {page_type}")
            return None, 0.0

        # Get schema for this page type
        if page_type not in PAGE_TYPE_SCHEMAS:
            if self.logger:
                self.logger.warning(f"No schema found for page type: {page_type}")
            return None, 0.0

        schema_class = PAGE_TYPE_SCHEMAS[page_type]
        prompt_template = self.page_prompts[prompt_key]

        # Build full prompt
        full_prompt = f"{prompt_template}\n\nPage URL: {page_url}\n\nPage Content:\n{page_text}"

        # Call LLM with retries
        for attempt in range(max_retries + 1):
            try:
                if self.logger:
                    retry_msg = f" (retry {attempt}/{max_retries})" if attempt > 0 else ""
                    self.logger.debug(f"Extracting {page_type} page with {self.llm_client.model_name}{retry_msg}")

                # Call LLM using unified client (CHEAPEST tier)
                response_text, cost = self._call_llm_for_json(full_prompt)

                # Parse and validate with Pydantic schema
                try:
                    # Try direct parse first, then repair if needed
                    try:
                        response_data = json.loads(response_text)
                    except json.JSONDecodeError:
                        repaired = repair_json(response_text)
                        response_data = json.loads(repaired)
                        if self.logger:
                            self.logger.info(f"JSON repaired successfully for {page_type}")

                    validated_response = schema_class(**response_data)
                    if self.logger:
                        self.logger.debug(f"Successfully validated {page_type} response")
                    return validated_response, cost
                except json.JSONDecodeError as e:
                    if attempt < max_retries:
                        if self.logger:
                            self.logger.warning(f"JSON parse error, retrying with stricter prompt: {e}")
                        full_prompt = (
                            f"CRITICAL: Return ONLY valid JSON. No markdown, no explanations.\n\n{full_prompt}"
                        )
                        continue
                    else:
                        if self.logger:
                            self.logger.error(f"JSON parse failed after {max_retries} retries: {e}")
                        return None, cost
                except Exception as e:
                    if attempt < max_retries:
                        if self.logger:
                            self.logger.warning(f"Validation error, retrying: {e}")
                        full_prompt = (
                            f"CRITICAL: Ensure all required fields are present and types are correct.\n\n{full_prompt}"
                        )
                        continue
                    else:
                        if self.logger:
                            self.logger.error(f"Validation failed after {max_retries} retries: {e}")
                        return None, cost

            except Exception as e:
                if self.logger:
                    self.logger.error(f"LLM call failed: {e}")
                return None, 0.0

        return None, 0.0

    def _call_llm_for_json(self, prompt: str) -> Tuple[str, float]:
        """Call LLM for JSON response using unified client (CHEAPEST tier)."""
        llm_response = self.llm_client.generate(prompt=prompt, temperature=0.1, max_tokens=4096, json_mode=True)

        return llm_response.text, llm_response.cost_usd

    @classmethod
    def get_cost_comparison(cls) -> str:
        """Get formatted cost comparison table."""
        lines = ["LLM Provider Cost Comparison (per 1M tokens):", ""]
        lines.append(f"{'Provider':<15} {'Input':<10} {'Output':<10} {'Est. per Website':<20}")
        lines.append("-" * 60)

        for provider, costs in cls.COSTS.items():
            est_cost = (5000 * costs["input"] / 1_000_000) + (2000 * costs["output"] / 1_000_000)
            lines.append(f"{costs['name']:<15} ${costs['input']:<9.3f} ${costs['output']:<9.2f} ${est_cost:<.4f}")

        return "\n".join(lines)
