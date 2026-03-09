from pathlib import Path

from export import prune_charity_detail_files


def test_prune_charity_detail_files_removes_out_of_scope_entries(tmp_path: Path):
    charities_dir = tmp_path / "charities"
    charities_dir.mkdir()
    keep_file = charities_dir / "charity-12-3456789.json"
    stale_file = charities_dir / "charity-98-7654321.json"
    keep_file.write_text("{}")
    stale_file.write_text("{}")

    removed = prune_charity_detail_files(tmp_path, {"12-3456789"})

    assert removed == 1
    assert keep_file.exists()
    assert not stale_file.exists()
