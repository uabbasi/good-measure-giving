# Field Mappings Reference

Complete mapping between ProPublica API fields, IRS Form 990 lines, and zakaat codebase fields.

## ProPublica API to Form 990 to Codebase

### Financial Fields

| ProPublica API | Form 990 Location | Codebase Field | DB Column |
|----------------|-------------------|----------------|-----------|
| `totrevenue` | Part I, Line 12 | `total_revenue` | `total_revenue` |
| `totfuncexpns` | Part I, Line 18 / Part IX, Line 25 | `total_expenses` | `total_expenses` |
| `totcntrbgfts` | Part VIII, Line 1h | `total_contributions` | `total_contributions` |
| `totprgmrevnue` | Part VIII, Line 2g | `program_service_revenue` | `program_service_revenue` |
| `invstmntinc` | Part VIII, Line 3 | `investment_income` | `investment_income` |
| `othrevnue` | Part VIII, Line 11e | `other_revenue` | `other_revenue` |
| `totassetsend` | Part X, Line 16 (EOY) | `total_assets` | `total_assets` |
| `totliabend` | Part X, Line 26 (EOY) | `total_liabilities` | `total_liabilities` |
| `totnetassetend` | Part X, Line 33 (EOY) | `net_assets` | `net_assets` |

### Expense Breakdown

| ProPublica API | Form 990 Location | Codebase Field | DB Column |
|----------------|-------------------|----------------|-----------|
| `progrevnue` | Part IX, Line 25 Column B | `program_expenses` | `program_expense` |
| `mgmtgenexp` | Part IX, Line 25 Column C | `admin_expenses` | `administrative_expense` |
| `fundrsngexp` | Part IX, Line 25 Column D | `fundraising_expenses` | `fundraising_expense` |

### Compensation

| ProPublica API | Form 990 Location | Codebase Field | DB Column |
|----------------|-------------------|----------------|-----------|
| `compnsatncurrofcr` | Part VII, Column D total | `officer_compensation` | `compensation_current_officers` |
| `othrsalwages` | Part IX, Line 7 | `other_salaries` | `other_salaries_wages` |
| `pensionplancontrb` | Part IX, Line 8 | `pension_contributions` | `pension_plan_contributions` |
| `othremam` | Part IX, Line 9 | `other_benefits` | `other_employee_benefits` |

### Organizational Info

| ProPublica API | Form 990 Location | Codebase Field | DB Column |
|----------------|-------------------|----------------|-----------|
| `name` | Part I, Header | `name` | `name` |
| `ein` | Part I, Header | `ein` | `ein` |
| `city` | Part I, Header | `city` | `city` |
| `state` | Part I, Header | `state` | `state` |
| `zipcode` | Part I, Header | `zip_code` | `zip_code` |
| `ntee_code` | Classification | `ntee_code` | `ntee_code` |
| `subseccd` | Subsection code | `subsection_code` | `subsection_code` |
| `totemploy` | Part I, Line 5 | `employees_count` | `employees_count` |
| `totvolunteers` | Part I, Line 6 | `volunteers_count` | `volunteers_count` |
| `formtype` | Form header | `filing_type` | `filing_type` |
| `tax_prd_yr` | Form header | `fiscal_year_end` | `tax_year` |
| `tax_prd` | Form header | `tax_period` | `tax_period` |

### Classification Codes

| ProPublica API | Form 990 Location | Description |
|----------------|-------------------|-------------|
| `ntee_code` | Various | National Taxonomy of Exempt Entities code |
| `subseccd` | Header | IRC subsection (3=501(c)(3), 4=501(c)(4), etc.) |
| `affession_code` | Header | Affiliation code (1=central, 3=independent, etc.) |
| `foundation` | Derived | Foundation status code |
| `ruling` | Header | IRS ruling date (YYYYMM) |

## Form 990 PDF Parser Mappings

### Header Info (`_extract_header_info`)

| Regex Pattern | Form 990 Field | Extracted To |
|---------------|----------------|--------------|
| `A For the \d{4} calendar year` | Tax Year | `fiscal_year` |
| `Name of the organization` | Part I header | `organization_name` |
| `Employer identification number` | Part I header | `ein` |
| `City or town` | Part I header | `city` |
| `State` | Part I header | `state` |
| `ZIP code` | Part I header | `zip_code` |
| `Website` | Part I header | `website` |

### Financial Data (`_extract_financial_data`)

| Regex Pattern | Form 990 Line | Extracted To |
|---------------|---------------|--------------|
| `Total revenue` | Part I, Line 12 | `total_revenue` |
| `Total expenses` | Part I, Line 18 | `total_expenses` |
| `Total assets.*end of year` | Part X, Line 16 | `total_assets` |
| `Total liabilities.*end of year` | Part X, Line 26 | `total_liabilities` |
| `Program service expenses` | Part IX, Line 25B | `program_expenses` |
| `Management.*general expenses` | Part IX, Line 25C | `admin_expenses` |
| `Fundraising expenses` | Part IX, Line 25D | `fundraising_expenses` |
| `Contributions and grants` | Part VIII, Line 1h | `total_contributions` |
| `Net assets.*end of year` | Part X, Line 33 | `net_assets` |

### Officers (`_extract_officers`)

| Regex Pattern | Form 990 Section | Extracted To |
|---------------|------------------|--------------|
| Part VII table rows | Part VII, Section A | `officers[]` |
| Name column | Column (A) | `officer.name` |
| Title column | Column (A) | `officer.title` |
| Hours column | Column (B) | `officer.hours_per_week` |
| Compensation column | Column (D) | `officer.compensation` |

### Programs (`_extract_programs`)

| Regex Pattern | Form 990 Section | Extracted To |
|---------------|------------------|--------------|
| `4a.*Program` | Part III, Line 4a | `programs[0]` |
| `4b.*Program` | Part III, Line 4b | `programs[1]` |
| `4c.*Program` | Part III, Line 4c | `programs[2]` |
| Expenses line | Each program section | `program.expenses` |
| Description | Each program section | `program.description` |

### Schedule O (`_extract_schedule_o`)

| Regex Pattern | Schedule Section | Extracted To |
|---------------|------------------|--------------|
| Country/region names | Geographic areas | `service_areas[]` |

## Database Schema to Form 990

### charities table

| Column | Form 990 Source | Notes |
|--------|-----------------|-------|
| `ein` | Part I header | Primary key (XX-XXXXXXX format) |
| `name` | Part I header | Organization name |
| `city` | Part I header | |
| `state` | Part I header | |
| `zip_code` | Part I header | |
| `website` | Part I header | |
| `mission_statement` | Part I, Line 1 / Part III | |
| `tax_year` | Form header | Fiscal year end |
| `total_revenue` | Part I, Line 12 | |
| `total_expenses` | Part I, Line 18 | |
| `program_expense` | Part IX, Line 25B | |
| `administrative_expense` | Part IX, Line 25C | |
| `fundraising_expense` | Part IX, Line 25D | |
| `total_assets` | Part X, Line 16 | |
| `total_liabilities` | Part X, Line 26 | |
| `net_assets` | Part X, Line 33 | |
| `employees_count` | Part I, Line 5 | |
| `volunteers_count` | Part I, Line 6 | |

### evaluations table (derived)

| Column | Formula / Source | Notes |
|--------|------------------|-------|
| `program_expense_ratio` | program_expense / total_expenses | From Part IX |
| `overhead_ratio` | (admin + fundraising) / total_expenses | From Part IX |
| `fundraising_efficiency` | total_contributions / fundraising_expense | Part VIII / Part IX |

## ProPublica API Field Abbreviations

Reference for understanding ProPublica's abbreviated field names:

| Abbreviation | Full Name | Form 990 Context |
|--------------|-----------|------------------|
| `tot` | Total | Aggregate/sum |
| `rev` | Revenue | Part VIII income |
| `exp` | Expenses | Part IX expenses |
| `func` | Functional | Program/admin/fundraising split |
| `cntrbgfts` | Contributions and gifts | Part VIII, Line 1 |
| `prgm` | Program | Program services |
| `invstmnt` | Investment | Part VIII, Line 3 |
| `oth` | Other | Miscellaneous category |
| `compnsatn` | Compensation | Part VII / Part IX |
| `currofcr` | Current officers | Part VII, Section A |
| `end` | End of year | Balance sheet EOY |
| `beg` | Beginning of year | Balance sheet BOY |

## Fields Not Yet Mapped in Codebase

These ProPublica fields are available but not currently extracted:

| ProPublica API | Form 990 Location | Potential Use |
|----------------|-------------------|---------------|
| `grsrcptsrelated` | Part VIII, Line 2 | Program revenue by type |
| `grsincfndrsng` | Part VIII, Line 8a | Fundraising event revenue |
| `grsincgaming` | Part VIII, Line 9a | Gaming revenue |
| `grsalesinvent` | Part VIII, Line 10a | Inventory sales |
| `grsamtsalesast` | Part VIII, Line 7a | Asset sale proceeds |
| `lessdirfndrsng` | Part IX, Line 25D detail | Fundraising direct costs |
| `compnsatnandothr` | Part IX, Line 5-10 | Total compensation |
| `contraccash` | Part IX, Line 11g | Contract services |
| `payaboression` | Part IX, Line 11a-b | Professional fees |
| `totpayabrpttam` | Part IX, Line 11 | Total professional fees |
| `neaboression` | Part IX, Line 11a | Legal fees |
| `accession` | Part IX, Line 11c | Accounting fees |
| `naboression` | Part IX, Line 11b | Lobbying fees |
| `occupession` | Part IX, Line 16 | Occupancy |
| `intaboression` | Part IX, Line 20 | Interest |
| `deprecession` | Part IX, Line 22 | Depreciation |
| `naession` | Part IX, Line 23 | Insurance |
| `taboression` | Part IX, Line 14 | Information technology |
| `confmtgession` | Part IX, Line 19 | Conferences |
| `advrtession` | Part IX, Line 12 | Advertising |
| `officession` | Part IX, Line 13 | Office expenses |
| `travlession` | Part IX, Line 17 | Travel |

## Form 990 Variant Differences

### 990 vs 990-EZ Field Availability

| Field | Form 990 | Form 990-EZ | Notes |
|-------|----------|-------------|-------|
| Functional expense breakdown | Yes (Part IX) | No | EZ only reports total |
| Officer compensation detail | Yes (Part VII) | Limited (Part IV) | EZ has less detail |
| Balance sheet detail | Yes (Part X) | Yes (Part II) | Similar |
| Program descriptions | Yes (Part III) | Yes (Part III) | Similar |
| Revenue breakdown | Full (Part VIII) | Limited (Part I) | EZ combines categories |

### 990-PF Differences (Private Foundations)

| 990-PF Part | Equivalent 990 Part | Notes |
|-------------|---------------------|-------|
| Part I | Part VIII + IX | Revenue and expenses |
| Part II | Part X | Balance sheet |
| Part IX-A | Part VII | Compensation |
| Part XV | Schedule I | Grants paid |
| Part XIV | N/A | Private operating foundation test |

## Reconciliation Logic

### Source Priority (parameter_mapper.py)

When multiple sources have the same field:

```python
SOURCE_PRIORITY = {
    "total_revenue": ["propublica", "charity_navigator", "candid"],
    "total_expenses": ["propublica", "charity_navigator", "candid"],
    "program_expenses": ["propublica", "form_990_pdf", "charity_navigator"],
    "mission_statement": ["website", "charity_navigator", "propublica"],
    "employees_count": ["propublica", "charity_navigator"],
}
```

### Field Name Normalization

| Source | Source Field | Normalized Field |
|--------|--------------|------------------|
| ProPublica | `totrevenue` | `total_revenue` |
| Charity Navigator | `revenue` | `total_revenue` |
| Candid | `total_revenue` | `total_revenue` |
| Form 990 PDF | `total_revenue` | `total_revenue` |
