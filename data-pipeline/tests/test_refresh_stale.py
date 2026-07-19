"""--refresh-stale website selector (pure, fake repos).

select_stale_website_eins mirrors DataCollectionOrchestrator._is_data_fresh's
staleness math so CLI selection and in-run skip decisions agree.
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

from crawl import select_stale_website_eins


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
