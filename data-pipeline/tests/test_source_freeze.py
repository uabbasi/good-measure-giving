"""H12: BBB source frozen by default, opt back in with --sources bbb."""

from src.collectors.orchestrator import FROZEN_SOURCES, resolve_skip_sources


def test_bbb_is_the_frozen_source():
    assert FROZEN_SOURCES == {"bbb"}


def test_bbb_skipped_by_default():
    assert "bbb" in resolve_skip_sources(None)
    assert "bbb" in resolve_skip_sources([])


def test_explicit_include_unfreezes_bbb():
    assert "bbb" not in resolve_skip_sources(None, include_sources=["bbb"])


def test_user_skips_are_preserved_and_merged():
    assert resolve_skip_sources(["website"]) == {"website", "bbb"}
    assert resolve_skip_sources(["website"], include_sources=["bbb"]) == {"website"}


def test_explicit_skip_wins_over_include():
    # skipping and including the same source: skip wins (explicit skip is intentional)
    assert "bbb" in resolve_skip_sources(["bbb"], include_sources=["bbb"])
