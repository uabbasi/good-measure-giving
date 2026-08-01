"""Correcting a website in pilot_charities.txt must actually correct it.

EIN 88-0405956 is Islamic Foundation Of Nevada, 485 E Eldorado Ln, Las Vegas.
The list gave its website as ifnv.org, which belongs to the Ivy Foundation of
Northern Virginia — a different organisation sharing the initialism. The
citation judge caught it ("programs for senior citizens, cotillion leadership,
and fashion shows rather than elementary and secondary education"), in
February and again in July.

Fixing the list did nothing. sync_websites_to_db only writes when the stored
value is NULL, empty, or not a URL, so a stored-but-WRONG url is exactly the
case it skips — the database keeps the first value it ever saw and the curated
file cannot correct it. Worse, the run still logged "Synced 1 websites", because
the count was incremented per statement attempted rather than per row changed:
the one signal a curator would check said the correction had landed.

The file is the only curated writer of this column — nothing else updates
charities.website — so it wins.
"""

import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent))

from streaming_runner import sync_websites_to_db, website_for_ein

NEVADA = [{"ein": "88-0405956", "website": "https://lvislamicacademy.org"}]


class _Recorder:
    """Stands in for the database, remembering what each EIN holds."""

    def __init__(self, stored):
        self.stored = dict(stored)
        self.statements = []

    def __call__(self, sql, params=None):
        self.statements.append((" ".join(sql.split()), params))
        if len(params) == 1:  # the invalidation statement
            return 1
        website, ein = params[0], params[1]
        if self.stored.get(ein) == website:
            return 0
        self.stored[ein] = website
        return 1


def _sync(charities, stored):
    from unittest.mock import MagicMock

    recorder = _Recorder(stored)
    with patch("src.db.dolt_client.execute_query", recorder):
        count = sync_websites_to_db(charities, MagicMock())
    return count, recorder


class TestAWrongUrlIsCorrected:
    def test_the_stored_url_is_replaced(self):
        _, rec = _sync(NEVADA, {"88-0405956": "https://ifnv.org"})
        assert rec.stored["88-0405956"] == "https://lvislamicacademy.org"

    def test_the_query_does_not_exclude_existing_urls(self):
        """The defect: the WHERE clause skipped exactly the rows that were
        wrong."""
        _, rec = _sync(NEVADA, {"88-0405956": "https://ifnv.org"})
        sql = rec.statements[0][0].lower()
        assert "website is null" not in sql and "not like" not in sql

    def test_a_blank_is_still_filled(self):
        _, rec = _sync(NEVADA, {"88-0405956": None})
        assert rec.stored["88-0405956"] == "https://lvislamicacademy.org"


class TestTheCountReportsWhatChanged:
    def test_a_correction_counts(self):
        count, _ = _sync(NEVADA, {"88-0405956": "https://ifnv.org"})
        assert count == 1

    def test_an_unchanged_row_does_not(self):
        """This is the signal a curator reads to know the fix landed. It said
        'Synced 1' while nothing moved."""
        count, _ = _sync(NEVADA, {"88-0405956": "https://lvislamicacademy.org"})
        assert count == 0

    def test_a_charity_with_no_website_in_the_file_is_skipped(self):
        count, rec = _sync([{"ein": "88-0405956", "website": ""}], {"88-0405956": "https://ifnv.org"})
        assert count == 0 and not rec.statements


class TestTheFileIsConsultedEvenWhenTheDatabaseHasAnAnswer:
    """The same "only fill blanks" mistake, one level up.

    On the --ein path the website is read from the DATABASE, and
    pilot_charities.txt is consulted only `if not charities[0].get("website")`.
    So a stored-but-wrong URL is never compared against the curated file at
    all: the correction cannot even reach sync_websites_to_db, which is why
    fixing the SQL was necessary and not sufficient. EIN 88-0405956 kept
    crawling ifnv.org through two corrected runs.

    The file is the documented source of truth. It wins where it has an
    answer, and the database fills in where it does not.
    """

    def test_the_file_overrides_a_stale_database_value(self):
        assert website_for_ein(
            db_website="https://ifnv.org",
            file_website="https://lvislamicacademy.org",
        ) == "https://lvislamicacademy.org"

    def test_the_database_fills_a_gap_in_the_file(self):
        assert website_for_ein(
            db_website="https://example.org", file_website=None
        ) == "https://example.org"

    def test_neither_is_none(self):
        assert website_for_ein(db_website=None, file_website=None) is None

    def test_a_blank_file_entry_is_not_an_answer(self):
        assert website_for_ein(
            db_website="https://example.org", file_website="  "
        ) == "https://example.org"


class TestChangingTheUrlMakesTheOldPageStale:
    """The third layer. Correcting the URL still crawled nothing.

    A raw_scraped_data row records no URL, so nothing about it changes when
    the charity's website does — and _is_data_fresh judges on scraped_at age
    alone. EIN 88-0405956's stored page was fetched 2026-07-18 from ifnv.org
    and stayed "fresh" through --force-phase crawl, so the Ivy Foundation of
    Northern Virginia's site kept feeding a Las Vegas mosque school's page
    after both the file and the database had been corrected.

    Clearing scraped_at is what makes it stale (_is_data_fresh returns False
    on a missing timestamp). The CONTENT is deliberately left in place: a
    charity keeps its last-good page until a successful crawl replaces it,
    which is the same non-destructive rule the synthesize path follows.
    """

    def test_a_changed_website_invalidates_the_stored_page(self):
        _, rec = _sync(NEVADA, {"88-0405956": "https://ifnv.org"})
        stale = [s for s, _ in rec.statements if "raw_scraped_data" in s]
        assert stale, "the page fetched from the old URL is still fresh"

    def test_it_targets_only_the_website_source(self):
        _, rec = _sync(NEVADA, {"88-0405956": "https://ifnv.org"})
        stmt = next(s for s, _ in rec.statements if "raw_scraped_data" in s)
        assert "website" in stmt

    def test_the_stored_content_is_not_deleted(self):
        """Last-good content survives until a successful crawl replaces it."""
        _, rec = _sync(NEVADA, {"88-0405956": "https://ifnv.org"})
        stmt = next(s for s, _ in rec.statements if "raw_scraped_data" in s)
        assert "delete" not in stmt.lower() and "raw_content" not in stmt.lower()

    def test_an_unchanged_website_invalidates_nothing(self):
        _, rec = _sync(NEVADA, {"88-0405956": "https://lvislamicacademy.org"})
        assert not [s for s, _ in rec.statements if "raw_scraped_data" in s]
