"""A board size we derived from markup we misread should not be published.

_extract_board_members splits each entry on runs of whitespace and calls the
first piece a name and the second a title. When Candid renders a person's given
and family names in separate elements, get_text() puts a gap between them and
the split lands mid-name:

    {"name": "Ayman", "title": "Khalil"}     EIN 23-7065716
    {"name": "Emran", "title": "Gazi"}

Every charity whose Candid board came back under three shows this, and wherever
Charity Navigator has a figure it is larger (1 vs 3, 1 vs 6, 2 vs 5, 2 vs 5).
Six of them publish the small number, which costs -2 through `board_under_3`
and prints "Board too small: N members" on the page.

The count is what the DOM contained, so this does not prove the board is bigger
— it proves we are not reading the section we think we are reading. A number
sourced from a misparse should not drive a risk deduction. Board size becomes
unknown, which is what it is; nothing is invented, and `board_under_3` already
skips a null.

A single-word title is NOT the signal: "Chairman" and "Treasurer" are real
one-word titles. The signal is a title with no role vocabulary in it at all.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.collectors.candid_beautifulsoup import board_extraction_is_reliable


class TestTheMisparseIsRecognized:
    def test_the_isgh_pair(self):
        assert not board_extraction_is_reliable([
            {"name": "Ayman", "title": "Khalil", "affiliation": "ISGH"},
            {"name": "Emran", "title": "Gazi", "affiliation": "ISGH"},
        ])

    def test_one_surname_among_real_titles_is_still_a_misparse(self):
        assert not board_extraction_is_reliable([
            {"name": "Ahmed Azam", "title": "SECRETARY"},
            {"name": "Fatima", "title": "Rahman"},
        ])


class TestRealTitlesSurvive:
    def test_one_word_roles_are_not_surnames(self):
        assert board_extraction_is_reliable([
            {"name": "Ahmed Azam", "title": "Chairman"},
            {"name": "Sara Khan", "title": "Treasurer"},
            {"name": "Lee Wong", "title": "Secretary"},
        ])

    def test_the_documented_messy_title_survives(self):
        assert board_extraction_is_reliable([
            {"name": "Ahmed Azam", "title": "SECRETARY THRU 11/1/23, CHAIRMAN"},
        ])

    def test_board_member_and_trustee_are_roles(self):
        assert board_extraction_is_reliable([
            {"name": "A B", "title": "Board Member"},
            {"name": "C D", "title": "Vice President"},
            {"name": "E F", "title": "Trustee"},
        ])

    def test_members_with_no_title_at_all_are_not_a_misparse(self):
        """Candid often lists a name and nothing else. That is missing data,
        not evidence the split went wrong."""
        assert board_extraction_is_reliable([{"name": "Ahmed Azam"}, {"name": "Sara Khan"}])

    def test_an_empty_board_is_not_a_misparse(self):
        assert board_extraction_is_reliable([])


class TestScope:
    def test_a_large_board_with_surname_titles_is_still_a_misparse(self):
        """Nothing here keys on the count; the misparse is the misparse."""
        assert not board_extraction_is_reliable(
            [{"name": f"First{i}", "title": f"Last{i}"} for i in range(20)]
        )

    def test_junk_entries_do_not_raise(self):
        assert board_extraction_is_reliable([None, "not a dict", {}])
