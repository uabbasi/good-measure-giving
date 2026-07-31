"""The primary source carries the whole income statement; we read two fields.

Charity Navigator leads the income-statement election because it has the full
functional-expense breakdown and ProPublica does not -- ProPublica supplies
exactly two of five fields for 158 of 169 charities. The IRS e-file XML that
both of them are downstream of has all five, in one group, internally
consistent to the dollar:

    <TotalFunctionalExpensesGrp>
      <TotalAmt>36818000</TotalAmt>
      <ProgramServicesAmt>34365532</ProgramServicesAmt>
      <ManagementAndGeneralAmt>1198626</ManagementAndGeneralAmt>
      <FundraisingAmt>1253842</FundraisingAmt>
    </TotalFunctionalExpensesGrp>

We read revenue and total expenses and stop. program_expenses is looked up at
CYProgramServiceExpenseAmt, which is not a tag in this schema, so it comes back
None for every charity -- a path that never matched anything.

Sample is EIN 36-4476244's FY2024 filing (object 202631349349308303), the
filing that was unreadable until the bundle fixes landed.
"""

import sys
from pathlib import Path
from xml.etree import ElementTree

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.collectors.form990_grants import Form990GrantsCollector

NS = "http://www.irs.gov/efile"

# Part IX as the IRS actually ships it: per-line rows carrying the same tag
# names as the totals row, and the totals last.
XML = f"""<?xml version="1.0"?>
<Return xmlns="{NS}">
  <ReturnHeader><TaxYr>2024</TaxYr></ReturnHeader>
  <ReturnData>
    <IRS990>
      <CYTotalRevenueAmt>34923926</CYTotalRevenueAmt>
      <CYTotalExpensesAmt>36818000</CYTotalExpensesAmt>
      <FeesForServicesLegalGrp>
        <TotalAmt>52867</TotalAmt>
        <ProgramServicesAmt>7660</ProgramServicesAmt>
        <ManagementAndGeneralAmt>38852</ManagementAndGeneralAmt>
        <FundraisingAmt>34807</FundraisingAmt>
      </FeesForServicesLegalGrp>
      <TotalProgramServiceExpensesAmt>34365532</TotalProgramServiceExpensesAmt>
      <TotalFunctionalExpensesGrp>
        <TotalAmt>36818000</TotalAmt>
        <ProgramServicesAmt>34365532</ProgramServicesAmt>
        <ManagementAndGeneralAmt>1198626</ManagementAndGeneralAmt>
        <FundraisingAmt>1253842</FundraisingAmt>
      </TotalFunctionalExpensesGrp>
    </IRS990>
  </ReturnData>
</Return>"""


def _financials(xml=XML):
    root = ElementTree.fromstring(xml)
    return Form990GrantsCollector()._extract_summary_financials(root)


class TestTheFullIncomeStatementIsRead:
    def test_revenue(self):
        assert _financials()["total_revenue"] == 34923926

    def test_total_expenses(self):
        assert _financials()["total_expenses"] == 36818000

    def test_program_expenses(self):
        """The defect: CYProgramServiceExpenseAmt is not a tag in this schema."""
        assert _financials()["program_expenses"] == 34365532

    def test_admin_expenses(self):
        assert _financials()["admin_expenses"] == 1198626

    def test_fundraising_expenses(self):
        assert _financials()["fundraising_expenses"] == 1253842

    def test_the_breakdown_reconciles_to_the_total(self):
        """The reason to prefer this source: it agrees with itself."""
        f = _financials()
        parts = f["program_expenses"] + f["admin_expenses"] + f["fundraising_expenses"]
        assert parts == f["total_expenses"]

    def test_admin_is_not_taken_from_a_line_item(self):
        """ManagementAndGeneralAmt appears on every Part IX row. An unscoped
        .//search would return the first one -- $38,852 of legal fees read as
        the organisation's entire administrative expense."""
        assert _financials()["admin_expenses"] != 38852

    def test_fundraising_is_not_taken_from_a_line_item(self):
        assert _financials()["fundraising_expenses"] != 34807


class TestAFilingWithoutPartIxStaysSilent:
    """990-EZ has no functional-expense breakdown. Missing must read as
    missing, not as zero -- a zero program expense would score as a charity
    that spends nothing on its programs."""

    EZ = f"""<?xml version="1.0"?>
<Return xmlns="{NS}">
  <ReturnHeader><TaxYr>2024</TaxYr></ReturnHeader>
  <ReturnData><IRS990EZ>
    <TotalRevenueAmt>250749</TotalRevenueAmt>
    <TotalExpensesAmt>201430</TotalExpensesAmt>
  </IRS990EZ></ReturnData>
</Return>"""

    def test_no_breakdown_is_absent_not_zero(self):
        f = _financials(self.EZ)
        assert f.get("program_expenses") is None
        assert f.get("admin_expenses") is None
        assert f.get("fundraising_expenses") is None

    def test_the_totals_it_does_have_are_still_read(self):
        f = _financials(self.EZ)
        assert f["total_revenue"] == 250749
        assert f["total_expenses"] == 201430
