"""Part VI (Governance) + Part VII Section A (officers/board), read from the
same e-file XML the grants collector already fetches.

Board-size fields prefer the Part VI Section A tags (GoverningBodyVotingMembersCnt
/ IndependentVotingMemberCnt) over the near-duplicate Part I summary tags
(VotingMembersGoverningBodyCnt / VotingMembersIndependentCnt); both are present
on real filings and report the same number, but Part VI is the section these
answers actually belong to. 'Ind' fields are '1'/'0' for Part VI Line 1-16
answers and a bare 'X' (present) / omitted (absent) for the Line 18 disclosure
checkboxes -- both mean the same yes/no here.

Field names and shapes are taken directly from a real filing (EIN 13-1685039,
CARE USA, object 202523579349300712), not from the schema docs.
"""

import sys
from pathlib import Path
from xml.etree import ElementTree

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.collectors.form990_grants import Form990GrantsCollector  # noqa: E402

NS = "http://www.irs.gov/efile"

FULL_XML = f"""<?xml version="1.0"?>
<Return xmlns="{NS}">
  <ReturnHeader><TaxYr>2024</TaxYr></ReturnHeader>
  <ReturnData>
    <IRS990>
      <Filer>
        <BusinessName><BusinessNameLine1Txt>SAMPLE CHARITY</BusinessNameLine1Txt></BusinessName>
      </Filer>
      <VotingMembersGoverningBodyCnt>25</VotingMembersGoverningBodyCnt>
      <VotingMembersIndependentCnt>24</VotingMembersIndependentCnt>
      <GoverningBodyVotingMembersCnt>25</GoverningBodyVotingMembersCnt>
      <IndependentVotingMemberCnt>24</IndependentVotingMemberCnt>
      <FamilyOrBusinessRlnInd>0</FamilyOrBusinessRlnInd>
      <DelegationOfMgmtDutiesInd>0</DelegationOfMgmtDutiesInd>
      <ChangeToOrgDocumentsInd>0</ChangeToOrgDocumentsInd>
      <MaterialDiversionOrMisuseInd>1</MaterialDiversionOrMisuseInd>
      <MembersOrStockholdersInd>0</MembersOrStockholdersInd>
      <ElectionOfBoardMembersInd>0</ElectionOfBoardMembersInd>
      <DecisionsSubjectToApprovaInd>0</DecisionsSubjectToApprovaInd>
      <MinutesOfGoverningBodyInd>1</MinutesOfGoverningBodyInd>
      <MinutesOfCommitteesInd>1</MinutesOfCommitteesInd>
      <LocalChaptersInd>0</LocalChaptersInd>
      <Form990ProvidedToGvrnBodyInd>1</Form990ProvidedToGvrnBodyInd>
      <ConflictOfInterestPolicyInd>1</ConflictOfInterestPolicyInd>
      <AnnualDisclosureCoveredPrsnInd>1</AnnualDisclosureCoveredPrsnInd>
      <RegularMonitoringEnfrcInd>1</RegularMonitoringEnfrcInd>
      <WhistleblowerPolicyInd>1</WhistleblowerPolicyInd>
      <DocumentRetentionPolicyInd>1</DocumentRetentionPolicyInd>
      <CompensationProcessCEOInd>1</CompensationProcessCEOInd>
      <CompensationProcessOtherInd>1</CompensationProcessOtherInd>
      <InvestmentInJointVentureInd>0</InvestmentInJointVentureInd>
      <OwnWebsiteInd>X</OwnWebsiteInd>
      <UponRequestInd>X</UponRequestInd>
      <Form990PartVIISectionAGrp>
        <PersonNm>JANE DOE</PersonNm>
        <TitleTxt>PRESIDENT AND CEO</TitleTxt>
        <AverageHoursPerWeekRt>58.00</AverageHoursPerWeekRt>
        <IndividualTrusteeOrDirectorInd>X</IndividualTrusteeOrDirectorInd>
        <OfficerInd>X</OfficerInd>
        <ReportableCompFromOrgAmt>501805</ReportableCompFromOrgAmt>
        <ReportableCompFromRltdOrgAmt>0</ReportableCompFromRltdOrgAmt>
        <OtherCompensationAmt>37412</OtherCompensationAmt>
      </Form990PartVIISectionAGrp>
      <Form990PartVIISectionAGrp>
        <PersonNm>JOHN SMITH</PersonNm>
        <TitleTxt>BOARD MEMBER</TitleTxt>
        <AverageHoursPerWeekRt>3.00</AverageHoursPerWeekRt>
        <IndividualTrusteeOrDirectorInd>X</IndividualTrusteeOrDirectorInd>
        <ReportableCompFromOrgAmt>0</ReportableCompFromOrgAmt>
        <ReportableCompFromRltdOrgAmt>0</ReportableCompFromRltdOrgAmt>
        <OtherCompensationAmt>0</OtherCompensationAmt>
      </Form990PartVIISectionAGrp>
    </IRS990>
  </ReturnData>
</Return>"""

# A small org that skipped Line 12-15 entirely (common when Schedule O carries
# a narrative answer instead), reporting only board size.
SPARSE_XML = f"""<?xml version="1.0"?>
<Return xmlns="{NS}">
  <ReturnHeader><TaxYr>2024</TaxYr></ReturnHeader>
  <ReturnData>
    <IRS990>
      <Filer><BusinessName><BusinessNameLine1Txt>SMALL ORG</BusinessNameLine1Txt></BusinessName></Filer>
      <GoverningBodyVotingMembersCnt>5</GoverningBodyVotingMembersCnt>
      <IndependentVotingMemberCnt>5</IndependentVotingMemberCnt>
    </IRS990>
  </ReturnData>
</Return>"""


def _governance(xml):
    root = ElementTree.fromstring(xml)
    return Form990GrantsCollector()._parse_governance(root)


class TestPartVIFields:
    def test_board_size_from_part_vi_section_a(self):
        gov = _governance(FULL_XML)
        assert gov["voting_board_members"] == 25
        assert gov["independent_voting_board_members"] == 24

    def test_policy_flags_read_as_booleans(self):
        gov = _governance(FULL_XML)
        assert gov["has_conflict_of_interest_policy"] is True
        assert gov["has_whistleblower_policy"] is True
        assert gov["has_document_retention_policy"] is True
        assert gov["material_diversion_or_misuse"] is True
        assert gov["family_or_business_relationships"] is False

    def test_line_18_checkbox_style_ind_is_also_read(self):
        gov = _governance(FULL_XML)
        assert gov["discloses_via_own_website"] is True
        assert gov["discloses_upon_request"] is True

    def test_unanswered_questions_stay_none_not_false(self):
        gov = _governance(SPARSE_XML)
        assert gov["voting_board_members"] == 5
        assert gov["has_conflict_of_interest_policy"] is None
        assert gov["has_whistleblower_policy"] is None
        assert gov["material_diversion_or_misuse"] is None


class TestPartVIISectionA:
    def test_officers_parsed_with_role_flags(self):
        gov = _governance(FULL_XML)
        assert len(gov["officers"]) == 2
        ceo = gov["officers"][0]
        assert ceo.name == "JANE DOE"
        assert ceo.title == "PRESIDENT AND CEO"
        assert ceo.is_officer is True
        assert ceo.is_trustee_or_director is True
        assert ceo.reportable_comp_from_org == 501805.0

    def test_board_member_with_no_compensation(self):
        gov = _governance(FULL_XML)
        member = gov["officers"][1]
        assert member.is_officer is False
        assert member.is_trustee_or_director is True
        assert member.reportable_comp_from_org == 0.0


class TestFullFilingParse:
    def test_parse_emits_governance_profile_alongside_grants_profile(self):
        collector = Form990GrantsCollector()
        import json

        raw = f'<!-- FORM990_METADATA: {json.dumps({"object_id": "123", "tax_year": 2024})} -->\n{FULL_XML}'
        result = collector.parse(raw, "13-1685039")

        assert result.success is True
        assert "grants_profile" in result.parsed_data
        gov = result.parsed_data["governance_profile"]
        assert gov["ein"] == "13-1685039"
        assert gov["voting_board_members"] == 25
        assert gov["has_conflict_of_interest_policy"] is True
        assert len(gov["officers"]) == 2

    def test_no_xml_sentinel_has_no_governance_profile(self):
        collector = Form990GrantsCollector()
        result = collector.parse(collector.NO_XML_SENTINEL, "85-3964369")

        assert result.success is True
        assert "governance_profile" not in result.parsed_data
