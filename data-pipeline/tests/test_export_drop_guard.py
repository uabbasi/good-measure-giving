"""Guard against silently dropping a published charity from the index.

export.py writes charities.json from whatever survived the run. A charity
blocked by the judge gate used to vanish from the index while the run still
reported success -- that is how the v6.0.0 regen (commit 6ec44bd) wrote 162
charities under a commit message claiming 166/166, and how the 2026-08-03 run
lost five before a follow-up pass restored them.

The guard reads the roster the previous export published, subtracts what this
run produced, and treats anything left over as a drop that has to be declared
in curation_overrides.yaml before the index may be overwritten.
"""

import json
from pathlib import Path

import pytest
from export import (
    find_undeclared_drops,
    load_delisted,
    load_published_roster,
)


def _write_index(path: Path, eins: list[str]) -> Path:
    index = path / "charities.json"
    index.write_text(
        json.dumps({"source_commit": "abc", "charities": [{"ein": e} for e in eins]})
    )
    return index


class TestLoadPublishedRoster:
    def test_reads_the_eins_the_previous_export_published(self, tmp_path: Path):
        _write_index(tmp_path, ["12-3456789", "98-7654321"])

        assert load_published_roster(tmp_path) == {"12-3456789", "98-7654321"}

    def test_missing_index_is_an_empty_roster(self, tmp_path: Path):
        """A first export into a fresh directory has nothing to protect."""
        assert load_published_roster(tmp_path) == set()

    def test_unreadable_index_is_an_empty_roster(self, tmp_path: Path):
        """A corrupt index must not wedge the export; there is no roster to trust."""
        (tmp_path / "charities.json").write_text("{ not json")

        assert load_published_roster(tmp_path) == set()

    def test_entries_without_an_ein_are_skipped(self, tmp_path: Path):
        index = tmp_path / "charities.json"
        index.write_text(
            json.dumps({"charities": [{"ein": "12-3456789"}, {"name": "no ein"}]})
        )

        assert load_published_roster(tmp_path) == {"12-3456789"}


class TestFindUndeclaredDrops:
    def test_reports_a_charity_that_fell_out_of_the_index(self):
        drops = find_undeclared_drops(
            previous={"12-3456789", "98-7654321"},
            exported={"12-3456789"},
            delisted={},
        )

        assert drops == ["98-7654321"]

    def test_a_declared_removal_is_not_a_drop(self):
        drops = find_undeclared_drops(
            previous={"12-3456789", "98-7654321"},
            exported={"12-3456789"},
            delisted={"98-7654321": {"reason": "duplicate EIN", "date": "2026-08-24"}},
        )

        assert drops == []

    def test_additions_are_never_drops(self):
        drops = find_undeclared_drops(
            previous={"12-3456789"},
            exported={"12-3456789", "55-5555555"},
            delisted={},
        )

        assert drops == []

    def test_a_clean_run_reports_nothing(self):
        drops = find_undeclared_drops(
            previous={"12-3456789"},
            exported={"12-3456789"},
            delisted={},
        )

        assert drops == []

    def test_multiple_drops_are_sorted_for_a_stable_message(self):
        drops = find_undeclared_drops(
            previous={"33-3333333", "11-1111111", "22-2222222"},
            exported=set(),
            delisted={},
        )

        assert drops == ["11-1111111", "22-2222222", "33-3333333"]

    def test_delisting_a_charity_that_still_exports_is_not_a_drop(self):
        """Declaring a removal does not itself remove anything; export decides."""
        drops = find_undeclared_drops(
            previous={"12-3456789"},
            exported={"12-3456789"},
            delisted={"12-3456789": {"reason": "pending", "date": "2026-08-24"}},
        )

        assert drops == []


class TestTheV6RegenIncident:
    """The concrete regression: 2026-08-16, commit 6ec44bd, 166 -> 162.

    Four charities were blocked by the judge gate (three of them on a single
    error, two of those a known judge false positive), omitted from the index,
    and the run reported success under a commit message reading 166/166.
    """

    BLOCKED = {
        "22-3382037",  # Islamic Educational Foundation - program expense ratio
        "46-2431099",  # Bayan Islamic Graduate School - zakat citation contradiction
        "63-0598743",  # Southern Poverty Law Center - sadaqah judge false positive
        "99-3373484",  # Yateem Foundation - invented cost-per-person
    }

    def test_the_four_blocked_charities_would_have_aborted_the_export(self):
        published = {f"00-000{n:04d}" for n in range(162)} | self.BLOCKED

        drops = find_undeclared_drops(
            previous=published,
            exported=published - self.BLOCKED,
            delisted={},
        )

        assert set(drops) == self.BLOCKED

    def test_the_same_run_passes_once_the_removals_are_declared(self):
        published = {f"00-000{n:04d}" for n in range(162)} | self.BLOCKED
        delisted = {
            ein: {"reason": "reviewed and delisted", "date": "2026-08-24"}
            for ein in self.BLOCKED
        }

        drops = find_undeclared_drops(
            previous=published, exported=published - self.BLOCKED, delisted=delisted
        )

        assert drops == []


class TestLoadDelisted:
    def test_parses_declared_removals(self, tmp_path: Path):
        cfg = tmp_path / "curation_overrides.yaml"
        cfg.write_text(
            "version: 1\n"
            "delisted:\n"
            '  "98-7654321":\n'
            '    reason: "Ceased operations, IRS revoked exemption"\n'
            '    date: "2026-08-24"\n'
        )

        delisted = load_delisted(cfg)

        assert delisted["98-7654321"]["reason"].startswith("Ceased operations")
        assert delisted["98-7654321"]["date"] == "2026-08-24"

    def test_absent_section_means_nothing_is_delisted(self, tmp_path: Path):
        cfg = tmp_path / "curation_overrides.yaml"
        cfg.write_text("version: 1\nnames: {}\n")

        assert load_delisted(cfg) == {}

    def test_missing_file_means_nothing_is_delisted(self, tmp_path: Path):
        assert load_delisted(tmp_path / "nope.yaml") == {}

    def test_a_removal_without_a_reason_is_rejected(self, tmp_path: Path):
        """An undocumented delisting is the thing this guard exists to prevent."""
        cfg = tmp_path / "curation_overrides.yaml"
        cfg.write_text('delisted:\n  "98-7654321":\n    date: "2026-08-24"\n')

        with pytest.raises(ValueError, match="98-7654321.*reason"):
            load_delisted(cfg)

    def test_a_removal_without_a_date_is_rejected(self, tmp_path: Path):
        cfg = tmp_path / "curation_overrides.yaml"
        cfg.write_text('delisted:\n  "98-7654321":\n    reason: "gone"\n')

        with pytest.raises(ValueError, match="98-7654321.*date"):
            load_delisted(cfg)

    def test_a_blank_reason_is_rejected(self, tmp_path: Path):
        cfg = tmp_path / "curation_overrides.yaml"
        cfg.write_text('delisted:\n  "98-7654321":\n    reason: "  "\n    date: "2026-08-24"\n')

        with pytest.raises(ValueError, match="98-7654321.*reason"):
            load_delisted(cfg)

    def test_a_bare_string_removal_is_rejected(self, tmp_path: Path):
        """`"98-7654321": "gone"` loses the date; require the mapping form."""
        cfg = tmp_path / "curation_overrides.yaml"
        cfg.write_text('delisted:\n  "98-7654321": "gone"\n')

        with pytest.raises(ValueError, match="98-7654321"):
            load_delisted(cfg)
