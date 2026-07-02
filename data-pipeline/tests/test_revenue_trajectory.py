"""Tests for revenue_trajectory_guidance — the growth-framing guard (#8).

Ensures stale/one-off/small-base revenue movements are not narrated as durable
growth, while genuine steady growth is still allowed.
"""

from src.services.rich_narrative_generator import revenue_trajectory_guidance


def _text(years, revenue, cagr):
    return "\n".join(revenue_trajectory_guidance(years, revenue, cagr)).lower()


def test_recent_decline_suppresses_growth():
    # Intl Aid: grew to 2023 then declined in 2024 (corrected CAGR is negative).
    t = _text([2022, 2023, 2024], [952352, 1481959, 851150], -5.5)
    assert "declined" in t
    assert "do not describe the organization as growing" in t


def test_decline_with_positive_window_cagr_flags_predates():
    # Recent decline but the multi-year window is still net-positive: the CAGR
    # must be explicitly called out as predating the decline.
    t = _text([2022, 2023, 2024], [500_000, 2_000_000, 1_000_000], 41.4)
    assert "declined" in t
    assert "predates" in t


def test_monotonic_decline_flagged():
    # UNICEF: declining each year.
    t = _text([2022, 2023, 2024], [1061946827, 829050932, 720404955], -17.6)
    assert "declined" in t
    assert "growing, scaling, or expanding" in t


def test_one_time_spike_not_sustained_growth():
    # Spike in the middle year, ends lower — decline takes priority but must not tout growth.
    t = _text([2022, 2023, 2024], [105000, 4559370, 181050], 31.3)
    assert "do not describe the organization as growing" in t or "one-time" in t
    assert "sustained growth" in t or "declined" in t


def test_small_base_growth_is_early_stage():
    # Saylani: real growth but from a tiny base.
    t = _text([2022, 2023, 2024], [126706, 1727397, 2954546], 382.9)
    assert "early-stage" in t
    assert "do not lead with the raw cagr" in t


def test_steady_growth_allows_cagr():
    # Substantial base, real sustained growth.
    t = _text([2021, 2022, 2023], [10_000_000, 12_000_000, 14_000_000], 18.3)
    assert "multi-year growth" in t
    assert "18.3% cagr" in t or "~18.3%" in t


def test_insufficient_data_suppresses_all_growth_language():
    t = _text([2023], [1_000_000], None)
    assert "insufficient" in t
    assert "do not mention cagr" in t


def test_flat_revenue_no_growth_emphasis():
    t = _text([2022, 2023, 2024], [1_000_000, 1_000_000, 1_000_000], 0.0)
    assert "flat" in t
    assert "do not emphasize growth" in t
