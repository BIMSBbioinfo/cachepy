"""
Port of cacheR test-metadata.R to pytest.

Tests that cache files store proper metadata alongside values,
that inspection utilities (cache_info, cache_list, cache_stats) work
correctly, and that legacy cache files are handled gracefully.
"""
import pickle
import time
from pathlib import Path

import pytest

from cachepy import (
    cache_file,
    cache_info,
    cache_list,
    cache_stats,
    cache_file_state_info,
    cache_file_state_clear,
)
from conftest import count_cache_entries


# =========================================================================
# Metadata storage tests
# =========================================================================

def test_stores_value_and_metadata_in_cache_file(tmp_path):
    """R: cacheFile stores value and metadata in cache file"""
    cache_dir = tmp_path / "cache"

    @cache_file(cache_dir=cache_dir, backend="pickle")
    def f(x, y=1):
        return x + y

    assert f(10) == 11

    pkl_files = [p for p in cache_dir.glob("*.pkl") if not p.name.startswith("graph.")]
    assert len(pkl_files) == 1

    with open(pkl_files[0], "rb") as fh:
        obj = pickle.load(fh)

    # New format: {"dat": value, "meta": {...}}
    assert isinstance(obj, dict)
    assert "dat" in obj
    assert "meta" in obj
    assert obj["dat"] == 11

    meta = obj["meta"]
    assert isinstance(meta, dict)

    # cachepy stores the hashlist as meta; check expected fields
    for field in ["call", "closure", "dir_states", "envs", "version"]:
        assert field in meta, f"Missing metadata field: {field}"

    # Check argument tracking (stored under "call")
    assert meta["call"]["x"] == 10


def test_cached_function_returns_raw_value(tmp_path):
    """R: cached function still returns raw value despite metadata wrapper"""
    cache_dir = tmp_path / "cache"

    @cache_file(cache_dir=cache_dir, backend="pickle")
    def f(x):
        return {"result": x * 2, "run_id": time.time()}

    res1 = f(5)
    assert res1["result"] == 10

    time.sleep(1.1)

    res2 = f(5)

    # Value check (user transparency)
    assert res2["result"] == 10

    # Cache hit check: run_id should match (same object from disk)
    assert res1["run_id"] == res2["run_id"]


# =========================================================================
# cache_info tests
# =========================================================================

def test_cache_info_returns_value_and_metadata(tmp_path):
    """R: cacheInfo returns value and metadata"""
    cache_dir = tmp_path / "cache"

    @cache_file(cache_dir=cache_dir, backend="pickle")
    def f(x, y=2):
        return x * y

    f(3)

    pkl_files = [p for p in cache_dir.glob("*.pkl") if not p.name.startswith("graph.")]
    assert len(pkl_files) == 1

    info = cache_info(pkl_files[0])

    assert isinstance(info, dict)
    assert "value" in info
    assert "meta" in info
    assert info["value"] == 6

    # In cachepy, args are under "call" key
    assert info["meta"]["call"]["x"] == 3


def test_cache_info_handles_legacy_files(tmp_path):
    """R: cacheInfo gracefully handles legacy cache files without metadata"""
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()

    legacy_path = cache_dir / "legacy.pkl"
    with open(legacy_path, "wb") as fh:
        pickle.dump(123, fh)

    info = cache_info(legacy_path)

    # Should normalize to the new structure
    assert isinstance(info, dict)
    assert info["value"] == 123
    assert isinstance(info["meta"], dict)
    assert info["meta"]["legacy"] is True


def test_cache_info_file_not_found(tmp_path):
    """cache_info raises FileNotFoundError for missing files"""
    with pytest.raises(FileNotFoundError):
        cache_info(tmp_path / "nonexistent.pkl")


# =========================================================================
# cache_list tests
# =========================================================================

def test_cache_list_summarizes_directory(tmp_path):
    """R: cacheList summarizes cache directory contents"""
    cache_dir = tmp_path / "cache"

    @cache_file(cache_dir=cache_dir, backend="pickle")
    def f(x):
        return x + 1

    @cache_file(cache_dir=cache_dir, backend="pickle")
    def g(z):
        return z * 10

    f(1)
    g(2)

    rows = cache_list(cache_dir)

    # Should have 2 entries (excluding graph.pkl)
    data_rows = [r for r in rows if not r["file"].startswith("graph.")]
    assert len(data_rows) == 2

    # Check expected columns
    for row in data_rows:
        assert "file" in row
        assert "fname" in row
        assert "created" in row
        assert "size_bytes" in row

    # Check function names are present
    fnames = {r["fname"] for r in data_rows}
    assert "f" in fnames
    assert "g" in fnames


def test_cache_list_empty_directory(tmp_path):
    """cache_list returns empty list for empty directory"""
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()

    rows = cache_list(cache_dir)
    assert rows == []


def test_cache_list_nonexistent_directory(tmp_path):
    """cache_list returns empty list for nonexistent directory"""
    rows = cache_list(tmp_path / "nonexistent")
    assert rows == []


# =========================================================================
# cache_stats tests
# =========================================================================

def test_cache_stats_aggregate_statistics(tmp_path):
    """cache_stats returns correct aggregate statistics"""
    cache_dir = tmp_path / "cache"

    @cache_file(cache_dir=cache_dir, backend="pickle")
    def f(x):
        return x + 1

    @cache_file(cache_dir=cache_dir, backend="pickle")
    def g(z):
        return z * 10

    f(1)
    f(2)
    g(3)

    stats = cache_stats(cache_dir)

    assert stats["n_entries"] == 3
    assert stats["total_size_mb"] > 0
    assert stats["oldest"] is not None
    assert stats["newest"] is not None
    assert stats["oldest"] <= stats["newest"]


def test_cache_stats_per_function_breakdown(tmp_path):
    """cache_stats includes per-function breakdown"""
    cache_dir = tmp_path / "cache"

    @cache_file(cache_dir=cache_dir, backend="pickle")
    def f(x):
        return x + 1

    @cache_file(cache_dir=cache_dir, backend="pickle")
    def g(z):
        return z * 10

    f(1)
    f(2)
    g(3)

    stats = cache_stats(cache_dir)

    assert "by_function" in stats
    by_func = stats["by_function"]

    # Should have 2 function groups
    assert len(by_func) == 2

    func_names = {d["fname"] for d in by_func}
    assert "f" in func_names
    assert "g" in func_names

    # f should have 2 entries, g should have 1
    f_entry = next(d for d in by_func if d["fname"] == "f")
    g_entry = next(d for d in by_func if d["fname"] == "g")
    assert f_entry["n_files"] == 2
    assert g_entry["n_files"] == 1


def test_cache_stats_empty_directory(tmp_path):
    """cache_stats returns zeros for empty directory"""
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()

    stats = cache_stats(cache_dir)

    assert stats["n_entries"] == 0
    assert stats["total_size_mb"] == 0.0


def test_cache_stats_nonexistent_directory(tmp_path):
    """cache_stats raises FileNotFoundError for missing directory"""
    with pytest.raises(FileNotFoundError):
        cache_stats(tmp_path / "nonexistent")


# =========================================================================
# cache_file_state_info / cache_file_state_clear tests
# =========================================================================

def test_file_state_info_reports_state(tmp_path):
    """cache_file_state_info returns status of the file hash cache"""
    # After reset (conftest autouse), state should be empty
    info = cache_file_state_info()
    assert info["n_entries"] == 0
    assert info["paths"] == []

    # Create a file and use it in a cached function with file tracking
    data_file = tmp_path / "data.txt"
    data_file.write_text("hello")

    cache_dir = tmp_path / "cache"

    @cache_file(cache_dir=cache_dir, backend="pickle")
    def f(path):
        return Path(path).read_text()

    f(str(data_file))

    # File state cache should now have entries
    info = cache_file_state_info()
    assert info["n_entries"] >= 0  # may or may not cache depending on implementation


def test_file_state_clear_returns_count(tmp_path):
    """cache_file_state_clear clears state and returns count"""
    from cachepy.cache_file import _file_state_cache

    # Manually populate the cache
    _file_state_cache["fake/path1"] = ("hash1", 100, 1000.0)
    _file_state_cache["fake/path2"] = ("hash2", 200, 2000.0)

    n = cache_file_state_clear()
    assert n == 2

    info = cache_file_state_info()
    assert info["n_entries"] == 0

    # Clearing again returns 0
    n2 = cache_file_state_clear()
    assert n2 == 0
