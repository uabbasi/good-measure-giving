"""
Form 990 PDF parser for extracting charity data.

Enhanced extraction (004-smart-crawler):
- Organization info: name, EIN, address, website
- Mission statement (Part I)
- Program descriptions (Part III)
- Financial data: revenue, expenses, assets, breakdown by category
- Officers and key employees (Part VII-A)
- Compensation data
- Calculated ratios (program expense ratio, overhead ratio)
- Geographic service areas (Schedule O)
"""

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

import pdfplumber

# Reasonable bounds for Form 990 financial values to catch parsing errors
# Min values: small charities may have modest budgets, but zero is suspicious
# Max values: even the largest nonprofits (universities, hospitals) rarely exceed $50B
FINANCIAL_BOUNDS = {
    "total_revenue": (100.0, 50_000_000_000.0),  # $100 to $50 billion
    "total_expenses": (100.0, 50_000_000_000.0),  # $100 to $50 billion
    "program_expenses": (0.0, 50_000_000_000.0),  # Can be $0 for new orgs
    "net_assets": (-10_000_000_000.0, 100_000_000_000.0),  # Can be negative
}


@dataclass
class Officer:
    """Officer or key employee from Form 990 Part VII."""

    name: str
    title: str
    hours_per_week: Optional[float] = None
    compensation: Optional[float] = None
    other_compensation: Optional[float] = None
    is_former: bool = False


@dataclass
class Form990Data:
    """Extracted data from Form 990 (enhanced)."""

    # Header information
    organization_name: Optional[str] = None
    ein: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    zip_code: Optional[str] = None
    website: Optional[str] = None
    fiscal_year: Optional[int] = None
    tax_year_start: Optional[str] = None
    tax_year_end: Optional[str] = None

    # Part I - Summary
    mission_statement: Optional[str] = None
    number_of_employees: Optional[int] = None
    number_of_volunteers: Optional[int] = None

    # Part III - Program Service Accomplishments
    programs: List[Dict[str, Any]] = None

    # Part VII - Officers and Key Employees
    officers: List[Officer] = None
    highest_compensated_employee: Optional[str] = None
    highest_compensation: Optional[float] = None

    # Financial data (Part I / Part IX)
    total_revenue: Optional[float] = None
    total_expenses: Optional[float] = None
    net_assets: Optional[float] = None

    # Revenue breakdown (Part VIII)
    contributions_gifts: Optional[float] = None
    program_service_revenue: Optional[float] = None
    investment_income: Optional[float] = None
    other_revenue: Optional[float] = None

    # Expense breakdown (Part IX)
    program_expenses: Optional[float] = None
    management_expenses: Optional[float] = None
    fundraising_expenses: Optional[float] = None
    compensation_expenses: Optional[float] = None

    # Assets (Part X)
    total_assets: Optional[float] = None
    total_liabilities: Optional[float] = None

    # Calculated ratios
    program_expense_ratio: Optional[float] = None
    overhead_ratio: Optional[float] = None
    fundraising_efficiency: Optional[float] = None

    # Geographic information (Schedule O/I)
    geographic_areas: List[str] = None
    foreign_activities: bool = False

    # Metadata
    form_type: str = "Form 990"
    form_variant: Optional[str] = None  # "990", "990-EZ", "990-PF"
    page_count: Optional[int] = None

    def __post_init__(self):
        if self.programs is None:
            self.programs = []
        if self.officers is None:
            self.officers = []
        if self.geographic_areas is None:
            self.geographic_areas = []

    def calculate_ratios(self):
        """Calculate financial efficiency ratios."""
        # Program expense ratio = Program expenses / Total expenses
        if self.total_expenses and self.total_expenses > 0 and self.program_expenses:
            self.program_expense_ratio = round((self.program_expenses / self.total_expenses) * 100, 1)

        # Overhead ratio = (Management + Fundraising) / Total expenses
        if self.total_expenses and self.total_expenses > 0:
            overhead = (self.management_expenses or 0) + (self.fundraising_expenses or 0)
            if overhead > 0:
                self.overhead_ratio = round((overhead / self.total_expenses) * 100, 1)

        # Fundraising efficiency = Contributions / Fundraising expenses
        if self.fundraising_expenses and self.fundraising_expenses > 0 and self.contributions_gifts:
            self.fundraising_efficiency = round(self.contributions_gifts / self.fundraising_expenses, 2)


class Form990Parser:
    """Parse Form 990 PDFs to extract charity data (enhanced)."""

    def __init__(self, logger=None):
        """Initialize parser."""
        self.logger = logger

    def _log_parse_warning(self, field_name: str, raw_value: str, ein: str = None):
        """Log a warning when parsing fails for a field."""
        if self.logger:
            ein_info = f" (EIN: {ein})" if ein else ""
            self.logger.warning(f"Failed to parse {field_name}{ein_info}: raw value = {raw_value!r}")

    def _validate_financial_value(
        self, field_name: str, value: float, ein: str = None
    ) -> Optional[float]:
        """Validate financial value is within reasonable bounds.

        Rejects values that are suspiciously low (likely parse errors) or
        impossibly high (likely decimal point errors).

        Args:
            field_name: Name of the field for logging
            value: The parsed financial value
            ein: EIN of the organization for logging context

        Returns:
            The value if valid, None if out of bounds
        """
        bounds = FINANCIAL_BOUNDS.get(field_name)
        if not bounds:
            return value  # No bounds defined, accept as-is

        min_val, max_val = bounds
        if value < min_val:
            self._log_parse_warning(
                field_name,
                f"{value:,.0f} below minimum ${min_val:,.0f}",
                ein,
            )
            return None
        if value > max_val:
            self._log_parse_warning(
                field_name,
                f"{value:,.0f} above maximum ${max_val:,.0f}",
                ein,
            )
            return None
        return value

    def parse_pdf(self, pdf_path: Path) -> Optional[Form990Data]:
        """
        Parse Form 990 PDF and extract comprehensive data.

        Enhanced extraction includes:
        - Header info (page 1)
        - Part I summary and mission
        - Part III program descriptions
        - Part VII officers and compensation
        - Part VIII revenue breakdown
        - Part IX expense breakdown
        - Part X assets/liabilities
        - Schedule O geographic info

        Args:
            pdf_path: Path to Form 990 PDF

        Returns:
            Form990Data with extracted information, or None if parsing failed
        """
        try:
            with pdfplumber.open(pdf_path) as pdf:
                data = Form990Data(page_count=len(pdf.pages))

                # Collect all text from PDF for comprehensive extraction
                all_text = ""
                page_texts = []
                for page in pdf.pages:
                    text = page.extract_text() or ""
                    page_texts.append(text)
                    all_text += text + "\n"

                # Detect form variant (990, 990-EZ, 990-PF)
                if "Form 990-EZ" in all_text:
                    data.form_variant = "990-EZ"
                elif "Form 990-PF" in all_text:
                    data.form_variant = "990-PF"
                else:
                    data.form_variant = "990"

                # Extract from first page (header + Part I)
                if len(page_texts) > 0:
                    self._extract_header(page_texts[0], data)
                    self._extract_part_i(page_texts[0], data)

                # Extract Part III - Program descriptions (usually pages 2-4)
                for page_num in range(min(5, len(page_texts))):
                    if "Part III" in page_texts[page_num]:
                        self._extract_part_iii(page_texts[page_num], data)
                        break

                # Extract Part VII - Officers (scan several pages)
                for page_num in range(min(10, len(page_texts))):
                    if "Part VII" in page_texts[page_num] or "Officers" in page_texts[page_num]:
                        self._extract_part_vii(page_texts[page_num], data)
                        # May span multiple pages
                        if page_num + 1 < len(page_texts) and "Section A" in page_texts[page_num + 1]:
                            self._extract_part_vii(page_texts[page_num + 1], data)
                        break

                # Extract Part VIII - Revenue (usually around page 9-10)
                for page_num in range(min(15, len(page_texts))):
                    if "Part VIII" in page_texts[page_num] or "Statement of Revenue" in page_texts[page_num]:
                        self._extract_part_viii(page_texts[page_num], data)
                        break

                # Extract Part IX - Expenses (usually around page 10-11)
                for page_num in range(min(15, len(page_texts))):
                    if "Part IX" in page_texts[page_num] or "Statement of Functional Expenses" in page_texts[page_num]:
                        self._extract_part_ix(page_texts[page_num], data)
                        break

                # Extract Schedule O or I for geographic info
                for page_num in range(len(page_texts)):
                    if "Schedule O" in page_texts[page_num] or "Schedule I" in page_texts[page_num]:
                        self._extract_schedule_o(page_texts[page_num], data)
                        break

                # Calculate efficiency ratios
                data.calculate_ratios()

                if self.logger:
                    self.logger.debug(
                        f"Parsed Form 990 ({data.form_variant}): {data.organization_name} "
                        f"({data.ein}) - {len(data.officers)} officers, "
                        f"program ratio: {data.program_expense_ratio}%"
                    )

                return data

        except Exception as e:
            if self.logger:
                self.logger.error(f"Failed to parse Form 990 {pdf_path}: {e}")
            return None

    def _extract_header(self, text: str, data: Form990Data):
        """Extract header information from page 1."""
        # Organization name (line after "Name of organization")
        name_match = re.search(r"Name of organization\s*\n\s*([A-Z][A-Z\s&,.-]+?)\s*\n", text, re.IGNORECASE)
        if name_match:
            name = name_match.group(1).strip()
            # Remove common suffixes that might be on the same line
            name = re.sub(r"\s+INC$", " INC", name)
            data.organization_name = name

        # EIN (format: XX-XXXXXXX) - look after "Doing business as"
        ein_match = re.search(r"Doing business as\s+(\d{2}-?\d{7})", text)
        if ein_match:
            ein = ein_match.group(1).replace("-", "")
            data.ein = f"{ein[:2]}-{ein[2:]}"

        # Address - line after "Number and street" but before "Telephone"
        # Pattern: "2461 EISENHOWER AVE 2ND FLOOR (888) 755-1556"
        address_match = re.search(r"Number and street[^\n]*\n\s*(.+?)\s+\(\d{3}\)", text, re.IGNORECASE)
        if address_match:
            data.address = address_match.group(1).strip()

        # City, State, ZIP - line that starts with city name and ends with ZIP
        # Pattern: "ALEXANDRIA, VA 22314 Is this a group return"
        city_match = re.search(r"\n([A-Z\s]+),\s*([A-Z]{2})\s+(\d{5}(?:-\d{4})?)\s+Is this", text)
        if city_match:
            data.city = city_match.group(1).strip()
            data.state = city_match.group(2).strip()
            data.zip_code = city_match.group(3).strip()

        # Website - look for WWW.CHARITYNAME.ORG pattern (not irs.gov)
        website_match = re.search(r"WWW\.([A-Z0-9.-]+\.[A-Z]{2,})", text, re.IGNORECASE)
        if website_match:
            domain = website_match.group(1).lower()
            # Filter out irs.gov
            if "irs.gov" not in domain:
                data.website = f"https://www.{domain}"

        # Fiscal year - from "2024 calendar year" or year in form title
        year_match = re.search(r"(\d{4})\s*\n\s*Form", text)
        if year_match:
            data.fiscal_year = int(year_match.group(1))

    def _extract_part_i(self, text: str, data: Form990Data):
        """Extract Part I - Summary (mission statement and financial data)."""
        # Mission statement (after "Briefly describe")
        mission_match = re.search(
            r"Briefly describe.*?activities[:\s]+(.+?)(?:\n\d+|$)", text, re.IGNORECASE | re.DOTALL
        )
        if mission_match:
            mission = mission_match.group(1).strip()
            # Clean up mission text
            mission = re.sub(r"\s+", " ", mission)  # Normalize whitespace
            mission = re.sub(r"[O]+$", "", mission)  # Remove trailing O's (form artifacts)
            if len(mission) > 20:  # Reasonable minimum length
                data.mission_statement = mission

        # Financial data - extract from lines like:
        # "Total revenue - add lines 8 through 11 (must equal Part VIII, column (A), line 12)  10,943,897. 7,168,898."
        # The LAST number is current year

        # Total revenue (line 12 in Part I)
        revenue_match = re.search(r"Total revenue[^\n]+?(\d{1,3}(?:,\d{3})*)\.\s*$", text, re.MULTILINE)
        if revenue_match:
            revenue_str = revenue_match.group(1).replace(",", "")
            try:
                revenue = float(revenue_str)
                # Validate bounds before storing
                validated = self._validate_financial_value("total_revenue", revenue, data.ein)
                if validated is not None:
                    data.total_revenue = validated
            except ValueError:
                self._log_parse_warning("total_revenue", revenue_str, data.ein)

        # Total expenses (line 18 in Part I)
        expenses_match = re.search(r"Total expenses[^\n]+?(\d{1,3}(?:,\d{3})*)\.\s*$", text, re.MULTILINE)
        if expenses_match:
            expenses_str = expenses_match.group(1).replace(",", "")
            try:
                expenses = float(expenses_str)
                # Validate bounds before storing
                validated = self._validate_financial_value("total_expenses", expenses, data.ein)
                if validated is not None:
                    data.total_expenses = validated
            except ValueError:
                self._log_parse_warning("total_expenses", expenses_str, data.ein)

        # Net assets (line 22 in Part I)
        net_assets_match = re.search(
            r"Net assets or fund balances[^\n]+?(\d{1,3}(?:,\d{3})*)\.\s*$", text, re.MULTILINE
        )
        if net_assets_match:
            net_assets_str = net_assets_match.group(1).replace(",", "")
            try:
                net_assets = float(net_assets_str)
                # Validate bounds before storing
                validated = self._validate_financial_value("net_assets", net_assets, data.ein)
                if validated is not None:
                    data.net_assets = validated
            except ValueError:
                self._log_parse_warning("net_assets", net_assets_str, data.ein)

    def _extract_part_iii(self, text: str, data: Form990Data):
        """Extract Part III - Program Service Accomplishments."""
        # Look for program descriptions (usually numbered 4a, 4b, 4c)
        # Pattern: program code, description, expenses

        # Try to find program sections

        # For now, let's extract program text blocks
        # Split by common section markers
        parts = re.split(r"\n\s*4[abc]\s*", text)

        for i, part in enumerate(parts[1:], 1):  # Skip first split (before 4a)
            # Extract first paragraph as program description
            desc_match = re.search(r"([A-Z][^\.]+\.[^\n]{20,500})", part, re.DOTALL)
            if desc_match:
                description = desc_match.group(1).strip()
                # Clean up
                description = re.sub(r"\s+", " ", description)

                # Try to extract expenses for this program
                expense_match = re.search(r"(\d{1,3}(?:,\d{3})*)\s*\)", part)
                expenses = None
                if expense_match:
                    expense_str = expense_match.group(1).replace(",", "")
                    try:
                        expenses = float(expense_str)
                    except ValueError:
                        self._log_parse_warning(f"program_{i}_expenses", expense_str, data.ein)

                data.programs.append({"name": f"Program {i}", "description": description, "expenses": expenses})

                if len(data.programs) >= 3:  # Most 990s have 3-4 programs max
                    break

    def _extract_part_vii(self, text: str, data: Form990Data):
        """Extract Part VII - Officers, Directors, and Key Employees."""
        # Part VII lists officers with format:
        # Name | Title | Hours | Compensation | Other Comp

        # Look for officer entries - usually in table format
        # Pattern: NAME (in caps) followed by title and numbers
        officer_pattern = r"([A-Z][A-Z\s,.-]{5,40})\s+((?:PRESIDENT|CEO|CFO|COO|DIRECTOR|EXECUTIVE|SECRETARY|TREASURER|BOARD|CHAIR|VICE|CHIEF)[A-Z\s,./]*)\s*(\d+(?:\.\d+)?)\s+(\d{1,3}(?:,\d{3})*)\."

        matches = re.findall(officer_pattern, text, re.IGNORECASE)

        for match in matches[:10]:  # Limit to top 10 officers
            name = match[0].strip()
            title = match[1].strip().title()
            hours = float(match[2]) if match[2] else None
            comp_str = match[3].replace(",", "")

            try:
                compensation = float(comp_str)
            except ValueError:
                self._log_parse_warning(f"officer_compensation ({name})", comp_str, data.ein)
                compensation = None

            # Check for duplicates
            existing_names = [o.name for o in data.officers]
            if name not in existing_names:
                officer = Officer(name=name, title=title, hours_per_week=hours, compensation=compensation)
                data.officers.append(officer)

                # Track highest compensated
                if compensation and (data.highest_compensation is None or compensation > data.highest_compensation):
                    data.highest_compensation = compensation
                    data.highest_compensated_employee = name

    def _extract_part_viii(self, text: str, data: Form990Data):
        """Extract Part VIII - Statement of Revenue."""
        # Look for key revenue lines

        # Line 1h - Contributions and grants
        contrib_match = re.search(
            r"(?:Contributions|grants|and|similar|amounts|received)[^\n]*?(\d{1,3}(?:,\d{3})*)\.\s*$",
            text,
            re.MULTILINE | re.IGNORECASE,
        )
        if contrib_match:
            contrib_str = contrib_match.group(1).replace(",", "")
            try:
                data.contributions_gifts = float(contrib_str)
            except ValueError:
                self._log_parse_warning("contributions_gifts", contrib_str, data.ein)

        # Line 2g - Program service revenue
        program_rev_match = re.search(
            r"Program service revenue[^\n]*?(\d{1,3}(?:,\d{3})*)\.\s*$", text, re.MULTILINE | re.IGNORECASE
        )
        if program_rev_match:
            prog_rev_str = program_rev_match.group(1).replace(",", "")
            try:
                data.program_service_revenue = float(prog_rev_str)
            except ValueError:
                self._log_parse_warning("program_service_revenue", prog_rev_str, data.ein)

        # Investment income
        invest_match = re.search(
            r"Investment income[^\n]*?(\d{1,3}(?:,\d{3})*)\.\s*$", text, re.MULTILINE | re.IGNORECASE
        )
        if invest_match:
            invest_str = invest_match.group(1).replace(",", "")
            try:
                data.investment_income = float(invest_str)
            except ValueError:
                self._log_parse_warning("investment_income", invest_str, data.ein)

    def _extract_part_ix(self, text: str, data: Form990Data):
        """Extract Part IX - Statement of Functional Expenses."""
        # Key expense categories

        # Total functional expenses by category
        # Column (B) = Program, (C) = Management, (D) = Fundraising

        # Line 25 - Total functional expenses
        # Format: Line Total | Program | Management | Fundraising
        expense_line_pattern = r"Total functional expenses[^\n]*?(\d{1,3}(?:,\d{3})*)\.\s+(\d{1,3}(?:,\d{3})*)\.\s+(\d{1,3}(?:,\d{3})*)\.\s+(\d{1,3}(?:,\d{3})*)\."

        expense_match = re.search(expense_line_pattern, text, re.IGNORECASE)
        if expense_match:
            # Parse each expense field individually for better error tracking
            # Fields with bounds validation use _validate_financial_value
            fields = [
                ("total_expenses", 1, True),   # has bounds
                ("program_expenses", 2, True),  # has bounds
                ("management_expenses", 3, False),
                ("fundraising_expenses", 4, False),
            ]
            for field_name, group_num, needs_validation in fields:
                raw_val = expense_match.group(group_num).replace(",", "")
                try:
                    value = float(raw_val)
                    if needs_validation:
                        validated = self._validate_financial_value(field_name, value, data.ein)
                        if validated is not None:
                            setattr(data, field_name, validated)
                    else:
                        setattr(data, field_name, value)
                except ValueError:
                    self._log_parse_warning(field_name, raw_val, data.ein)

        # Line 5-10 - Compensation expenses
        comp_match = re.search(r"Compensation of current officers[^\n]*?(\d{1,3}(?:,\d{3})*)\.", text, re.IGNORECASE)
        if comp_match:
            comp_exp_str = comp_match.group(1).replace(",", "")
            try:
                data.compensation_expenses = float(comp_exp_str)
            except ValueError:
                self._log_parse_warning("compensation_expenses", comp_exp_str, data.ein)

    def _extract_schedule_o(self, text: str, data: Form990Data):
        """Extract Schedule O/I - Geographic and supplemental information."""
        # Look for geographic areas mentioned
        geo_patterns = [
            r"serves?\s+(?:the\s+)?([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\s+(?:area|region|community)",
            r"operating in\s+([A-Z][a-z]+(?:,\s*[A-Z][a-z]+)*)",
            r"programs?\s+in\s+([A-Z][a-z]+(?:,\s*[A-Z][a-z]+)*)",
        ]

        for pattern in geo_patterns:
            matches = re.findall(pattern, text)
            for match in matches:
                areas = [a.strip() for a in match.split(",")]
                for area in areas:
                    if area and area not in data.geographic_areas:
                        data.geographic_areas.append(area)

        # Check for foreign activities
        if re.search(r"foreign\s+(?:activities|operations|grants)", text, re.IGNORECASE):
            data.foreign_activities = True

        # Look for country names
        countries = [
            "Afghanistan",
            "Bangladesh",
            "Egypt",
            "Ethiopia",
            "Gaza",
            "India",
            "Indonesia",
            "Iraq",
            "Jordan",
            "Kenya",
            "Lebanon",
            "Morocco",
            "Pakistan",
            "Palestine",
            "Somalia",
            "Sudan",
            "Syria",
            "Turkey",
            "Uganda",
            "Yemen",
        ]
        for country in countries:
            if country.lower() in text.lower() and country not in data.geographic_areas:
                data.geographic_areas.append(country)
                data.foreign_activities = True

    def to_dict(self, data: Form990Data) -> Dict[str, Any]:
        """Convert Form990Data to comprehensive dictionary (enhanced)."""
        result = {
            "organization_name": data.organization_name,
            "ein": data.ein,
            "address": None,
            "mission_statement": data.mission_statement,
            "programs": [],
            "website": data.website,
            "fiscal_year": data.fiscal_year,
            "form_variant": data.form_variant,
            # Enhanced financial data
            "financial_data": {
                "total_revenue": data.total_revenue,
                "total_expenses": data.total_expenses,
                "net_assets": data.net_assets,
                "total_assets": data.total_assets,
                "total_liabilities": data.total_liabilities,
                # Revenue breakdown
                "revenue_breakdown": {
                    "contributions_gifts": data.contributions_gifts,
                    "program_service_revenue": data.program_service_revenue,
                    "investment_income": data.investment_income,
                    "other_revenue": data.other_revenue,
                },
                # Expense breakdown
                "expense_breakdown": {
                    "program_expenses": data.program_expenses,
                    "management_expenses": data.management_expenses,
                    "fundraising_expenses": data.fundraising_expenses,
                    "compensation_expenses": data.compensation_expenses,
                },
                # Calculated ratios
                "ratios": {
                    "program_expense_ratio": data.program_expense_ratio,
                    "overhead_ratio": data.overhead_ratio,
                    "fundraising_efficiency": data.fundraising_efficiency,
                },
            },
            # Organizational data
            "organizational": {
                "number_of_employees": data.number_of_employees,
                "number_of_volunteers": data.number_of_volunteers,
                "highest_compensated_employee": data.highest_compensated_employee,
                "highest_compensation": data.highest_compensation,
            },
            # Officers
            "officers": [
                {
                    "name": o.name,
                    "title": o.title,
                    "hours_per_week": o.hours_per_week,
                    "compensation": o.compensation,
                }
                for o in data.officers
            ],
            # Geographic coverage
            "geographic_coverage": data.geographic_areas,
            "foreign_activities": data.foreign_activities,
            # Metadata
            "page_count": data.page_count,
        }

        # Build full address if available
        if data.address:
            address_parts = [data.address]
            if data.city:
                address_parts.append(data.city)
            if data.state:
                address_parts.append(data.state)
            if data.zip_code:
                address_parts.append(data.zip_code)
            result["address"] = ", ".join(address_parts)

        # Convert programs to list with expenses
        if data.programs:
            result["programs"] = [
                {
                    "name": p.get("name"),
                    "description": p.get("description"),
                    "expenses": p.get("expenses"),
                }
                for p in data.programs
                if p.get("description")
            ]

        return result
