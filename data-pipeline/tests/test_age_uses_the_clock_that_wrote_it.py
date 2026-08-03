"""Ages are measured against the clock that wrote the timestamp.

scraped_at and last_attempt_at are written by the Dolt server as
CURRENT_TIMESTAMP — naive, in the SERVER's timezone. Every age helper then does

    datetime.now(dt.tzinfo) - dt

and dt.tzinfo is always None for a value the driver hands back, so
datetime.now(None) returns the PIPELINE HOST's local wall clock. The subtraction
silently applies whatever gap exists between the two zones.

Observed on 2026-07-31: a failure recorded 23 minutes earlier measured as
1h23m, and a 4-hour backoff window reported 2.7h remaining instead of 3.6h.
The host was -0600 and the server PDT. Hours later the same host reported PDT
and the gap was zero — which is the point: the error is not a constant to
correct for, it is whatever the two clocks disagree by at that moment. On a
UTC host it would be seven hours, and the 1h and 4h backoff windows would be
defeated outright.

It errs toward retrying too soon, which is why it never surfaced as a failure:
a politeness guarantee quietly weaker than it reads. The day-scale TTLs are
unaffected in practice; the hours-scale backoffs are the whole quantity.
"""

import sys
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.utils import freshness


class TestAgeIsMeasuredOnTheServerClock:
    def test_a_timestamp_just_written_by_the_server_is_not_hours_old(self):
        """The defect: the server writes 'now', we call it an hour old."""
        with patch.object(freshness, "_server_offset", return_value=timedelta(hours=-1)):
            server_now = datetime.now() - timedelta(hours=1)
            age = freshness._age(server_now)
        assert age is not None and age < timedelta(minutes=1), age

    def test_a_genuinely_old_timestamp_still_reads_old(self):
        with patch.object(freshness, "_server_offset", return_value=timedelta(hours=-1)):
            server_now = datetime.now() - timedelta(hours=1)
            age = freshness._age(server_now - timedelta(hours=4))
        assert timedelta(hours=3, minutes=59) < age < timedelta(hours=4, minutes=1)

    def test_no_skew_behaves_exactly_as_before(self):
        with patch.object(freshness, "_server_offset", return_value=timedelta(0)):
            age = freshness._age(datetime.now() - timedelta(hours=2))
        assert timedelta(hours=1, minutes=59) < age < timedelta(hours=2, minutes=1)


class TestItDoesNotBreakWhatAlreadyWorked:
    def test_an_aware_timestamp_is_left_alone(self):
        """A value carrying its own zone needs no correction — the offset
        applies only to the naive values the driver returns."""
        from datetime import timezone

        aware = datetime.now(timezone.utc) - timedelta(hours=3)
        with patch.object(freshness, "_server_offset", return_value=timedelta(hours=-7)):
            age = freshness._age(aware)
        assert timedelta(hours=2, minutes=59) < age < timedelta(hours=3, minutes=1)

    def test_missing_and_unparseable_still_return_none(self):
        assert freshness._age(None) is None
        assert freshness._age("not a date") is None

    def test_an_unreachable_database_falls_back_to_the_host_clock(self):
        """Age math must never depend on the database being up."""
        with patch("src.db.client.execute_query", side_effect=OSError("no db")):
            freshness._reset_server_offset()
            assert freshness._server_offset() == timedelta(0)
        freshness._reset_server_offset()
