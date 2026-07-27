"""--refresh-stale website selector (pure, fake repos).

select_stale_website_eins mirrors DataCollectionOrchestrator._is_data_fresh's
staleness math so CLI selection and in-run skip decisions agree.
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import pytest
from crawl import (
    build_parser,
    parse_crawl_args,
    resolve_crawl_scope,
    resolve_force_sources,
    select_stale_website_eins,
)
from src.constants import SOURCE_TTL_DAYS
from src.utils.charity_loader import load_charities_from_file


def _charity(ein, name="Test Charity", website="https://example.org"):
    return {"ein": ein, "name": name, "website": website}


def _website_row(success=True, days_old=None):
    """Fake raw_scraped_data row shape (success, scraped_at)."""
    scraped_at = None
    if days_old is not None:
        scraped_at = (datetime.now(timezone.utc) - timedelta(days=days_old)).isoformat().replace("+00:00", "Z")
    return {"success": success, "scraped_at": scraped_at}


def _make_repos(charities, raw_rows_by_ein):
    charity_repo = MagicMock()
    charity_repo.get_all.return_value = charities
    raw_repo = MagicMock()
    raw_repo.get_by_source.side_effect = lambda ein, source: raw_rows_by_ein.get(ein)
    return charity_repo, raw_repo


class TestSelectStaleWebsiteEins:
    def test_selects_missing_failed_and_stale_not_fresh(self):
        charities = [
            _charity("11-1111111", name="Missing Row"),
            _charity("22-2222222", name="Failed Row"),
            _charity("33-3333333", name="Stale Row (40d)"),
            _charity("44-4444444", name="Fresh Row (5d)"),
        ]
        raw_rows = {
            # "11-1111111" intentionally absent -> missing website row
            "22-2222222": _website_row(success=False, days_old=5),
            "33-3333333": _website_row(success=True, days_old=40),
            "44-4444444": _website_row(success=True, days_old=5),
        }
        charity_repo, raw_repo = _make_repos(charities, raw_rows)

        result = select_stale_website_eins(charity_repo, raw_repo)

        eins = {r["ein"] for r in result}
        assert eins == {"11-1111111", "22-2222222", "33-3333333"}
        assert "44-4444444" not in eins

    def test_result_shape_is_name_ein_website(self):
        charities = [_charity("11-1111111", name="Missing Row", website="https://x.org")]
        charity_repo, raw_repo = _make_repos(charities, {})

        result = select_stale_website_eins(charity_repo, raw_repo)

        assert result == [{"name": "Missing Row", "ein": "11-1111111", "website": "https://x.org"}]

    def test_default_ttl_is_source_ttl_days_website(self):
        # 29 days old is fresh under the default 30-day website TTL.
        charities = [_charity("55-5555555")]
        raw_rows = {"55-5555555": _website_row(success=True, days_old=29)}
        charity_repo, raw_repo = _make_repos(charities, raw_rows)

        assert select_stale_website_eins(charity_repo, raw_repo) == []

    def test_older_than_days_widens_selection(self):
        # 10-day-old row: fresh under the default 30-day TTL...
        charities = [_charity("55-5555555", name="Ten Days Old")]
        raw_rows = {"55-5555555": _website_row(success=True, days_old=10)}
        charity_repo, raw_repo = _make_repos(charities, raw_rows)

        assert select_stale_website_eins(charity_repo, raw_repo) == []

        # ...but stale once --older-than narrows the TTL to 7 days.
        result = select_stale_website_eins(charity_repo, raw_repo, older_than_days=7)
        assert [r["ein"] for r in result] == ["55-5555555"]


class TestParseCrawlArgs:
    """--refresh-stale must accept an optional --charities/--ein scope (Fix C,
    Defect 1: it used to be crammed into a required mutually-exclusive group
    with --charities/--ein, so the canary command
    `--sources website --refresh-stale --charities <file>` was an argparse error."""

    def test_refresh_stale_with_charities_parses(self, tmp_path):
        charity_file = tmp_path / "charities.txt"
        charity_file.write_text("Fresh Charity | 44-4444444 | https://fresh.example.org\n")

        args = parse_crawl_args(["--refresh-stale", "--charities", str(charity_file)])

        assert args.refresh_stale is True
        assert args.charities == str(charity_file)
        assert args.ein is None

    def test_refresh_stale_with_ein_parses(self):
        args = parse_crawl_args(["--refresh-stale", "--ein", "95-4453134"])

        assert args.refresh_stale is True
        assert args.ein == "95-4453134"
        assert args.charities is None

    def test_no_scope_args_errors(self):
        with pytest.raises(SystemExit):
            parse_crawl_args([])

    def test_charities_and_ein_still_mutually_exclusive(self):
        with pytest.raises(SystemExit):
            build_parser().parse_args(["--charities", "x.txt", "--ein", "95-4453134"])

    def test_plain_charities_still_works(self):
        args = parse_crawl_args(["--charities", "pilot_charities.txt"])
        assert args.charities == "pilot_charities.txt"
        assert args.refresh_stale is False

    def test_plain_ein_still_works(self):
        args = parse_crawl_args(["--ein", "95-4453134"])
        assert args.ein == "95-4453134"
        assert args.refresh_stale is False


class TestResolveCrawlScope:
    """Pure arg->(scope, skip_sources) decision (Fix C, Defect 2): in
    --refresh-stale mode, every non-website source must be skipped so the
    orchestrator's required_sources collapses to {"website"} and nothing
    else is fetched or can hard-fail the run (e.g. form990_grants, whose
    TTL is 0 and is normally REQUIRED)."""

    def test_refresh_stale_alone_is_stale_scan_and_skips_non_website(self):
        args = parse_crawl_args(["--refresh-stale"])

        scope, skip_sources = resolve_crawl_scope(args)

        assert scope == "stale_scan"
        for source in SOURCE_TTL_DAYS:
            if source != "website":
                assert source in skip_sources, f"{source} should be skipped in --refresh-stale mode"
        assert "website" not in skip_sources
        assert "form990_grants" in skip_sources  # TTL=0, normally always-required

    def test_refresh_stale_with_charities_is_file_scope(self, tmp_path):
        charity_file = tmp_path / "charities.txt"
        charity_file.write_text(
            "Missing Row | 12-3456789 | https://a.example.org\n"
            "Fresh Row | 98-7654321 | https://fresh.example.org\n"
        )
        args = parse_crawl_args(["--refresh-stale", "--charities", str(charity_file)])

        scope, skip_sources = resolve_crawl_scope(args)

        assert scope == "file"  # exact file scope, NOT select_stale_website_eins's DB-wide scan
        assert "form990_grants" in skip_sources
        assert "website" not in skip_sources

        # scope == "file" always loads via load_charities_from_file, which has
        # no staleness filter — a fresh EIN in the file is selected too.
        charities = load_charities_from_file(str(charity_file))
        assert [c["ein"] for c in charities] == ["12-3456789", "98-7654321"]

    def test_refresh_stale_with_ein_is_ein_scope(self):
        args = parse_crawl_args(["--refresh-stale", "--ein", "95-4453134"])

        scope, skip_sources = resolve_crawl_scope(args)

        assert scope == "ein"
        assert "form990_grants" in skip_sources
        assert "website" not in skip_sources

    def test_refresh_stale_preserves_user_supplied_skip(self):
        args = parse_crawl_args(["--refresh-stale", "--skip", "candid"])

        _scope, skip_sources = resolve_crawl_scope(args)

        assert "candid" in skip_sources
        assert "form990_grants" in skip_sources

    def test_plain_charities_mode_does_not_restrict_sources(self):
        args = parse_crawl_args(["--charities", "pilot_charities.txt"])

        scope, skip_sources = resolve_crawl_scope(args)

        assert scope == "file"
        assert skip_sources == []

    def test_plain_ein_mode_does_not_restrict_sources(self):
        args = parse_crawl_args(["--ein", "95-4453134"])

        scope, skip_sources = resolve_crawl_scope(args)

        assert scope == "ein"
        assert skip_sources == []


class TestResolveForceSources:
    """Pure arg->force_sources decision (blocker 2B follow-up): --refresh-stale
    must force-bypass freshness/backoff for "website" regardless of scope
    (stale_scan/file/ein) -- this is what lets the mode re-crawl a
    terminally-failed (captcha) website row instead of respecting its 180-day
    skip. main() wires this in unconditionally on args.refresh_stale; this
    pure helper exists so that wiring is covered by a fast unit test instead
    of only exercised at runtime."""

    def test_refresh_stale_alone_forces_website(self):
        args = parse_crawl_args(["--refresh-stale"])
        assert resolve_force_sources(args) == {"website"}

    def test_refresh_stale_with_charities_forces_website(self, tmp_path):
        charity_file = tmp_path / "charities.txt"
        charity_file.write_text("Row | 12-3456789 | https://a.example.org\n")
        args = parse_crawl_args(["--refresh-stale", "--charities", str(charity_file)])
        assert resolve_force_sources(args) == {"website"}

    def test_refresh_stale_with_ein_forces_website(self):
        args = parse_crawl_args(["--refresh-stale", "--ein", "95-4453134"])
        assert resolve_force_sources(args) == {"website"}

    def test_plain_charities_mode_does_not_force(self):
        args = parse_crawl_args(["--charities", "pilot_charities.txt"])
        assert resolve_force_sources(args) is None

    def test_plain_ein_mode_does_not_force(self):
        args = parse_crawl_args(["--ein", "95-4453134"])
        assert resolve_force_sources(args) is None
