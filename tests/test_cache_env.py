"""
Port of cacheR test-cache-env.R to pytest.

Tests that the closure hasher and cache correctly detect changes in
mutable objects referenced by cached functions — dictionaries (R environments),
nested structures, and file paths stored in mutable containers.
"""
import time
from pathlib import Path

import pytest

from cachepy import cache_file
from conftest import count_cache_entries


# =========================================================================
# Tests
# =========================================================================

def test_modifying_dict_variable_invalidates_cache(tmp_path):
    """R: Modifying a variable inside a global environment invalidates cache"""
    cache_dir = tmp_path / "cache"

    config = {"threshold": 10}

    @cache_file(cache_dir=cache_dir, backend="pickle")
    def proc(x):
        return x * config["threshold"]

    # Run 1: 5 * 10 = 50
    assert proc(5) == 50

    # Modify content inside the dict
    config["threshold"] = 20

    # Run 2: should invalidate and re-run -> 5 * 20 = 100
    assert proc(5) == 100

    # Verify distinct cache files exist
    assert count_cache_entries(cache_dir) == 2


def test_detects_changes_in_nested_dicts(tmp_path):
    """R: Detects changes in Nested Environments"""
    cache_dir = tmp_path / "cache"

    settings = {"inner": {"val": 100}}

    @cache_file(cache_dir=cache_dir, backend="pickle")
    def proc():
        return settings["inner"]["val"]

    # Run 1
    assert proc() == 100

    # Modify deep value
    settings["inner"]["val"] = 999

    # Run 2: should detect change deep in the structure
    assert proc() == 999

    assert count_cache_entries(cache_dir) == 2


def test_detects_file_changes_referenced_through_argument(tmp_path):
    """R: Detects file changes when path is passed as argument"""
    cache_dir = tmp_path / "cache"

    # Create a dummy file
    f_path = tmp_path / "env_file.txt"
    f_path.write_text("version1")

    @cache_file(cache_dir=cache_dir, backend="pickle", file_args=["path"])
    def proc(path):
        return Path(path).read_text()

    # Run 1
    assert proc(str(f_path)) == "version1"

    # Modify the FILE content (not the variable)
    time.sleep(1.1)
    f_path.write_text("version2")

    # Run 2: should detect file content change and re-run
    assert proc(str(f_path)) == "version2"

    assert count_cache_entries(cache_dir) == 2


def test_detects_file_changes_via_depends_on_files(tmp_path):
    """File changes via depends_on_files invalidate cache"""
    cache_dir = tmp_path / "cache"

    f_path = tmp_path / "data.txt"
    f_path.write_text("version1")

    @cache_file(cache_dir=cache_dir, backend="pickle",
                depends_on_files=[str(f_path)])
    def proc():
        return f_path.read_text()

    assert proc() == "version1"

    time.sleep(1.1)
    f_path.write_text("version2")

    assert proc() == "version2"
    assert count_cache_entries(cache_dir) == 2


def test_does_not_recurse_into_package_modules(tmp_path):
    """R: Does NOT recurse into Locked/Package environments"""
    cache_dir = tmp_path / "cache"

    @cache_file(cache_dir=cache_dir, backend="pickle")
    def proc():
        import os
        return list(os.environ.keys())[:3]

    # Should run quickly and not crash/hang trying to hash all of os
    result = proc()
    assert isinstance(result, list)
    assert count_cache_entries(cache_dir) == 1


def test_list_mutation_invalidates_cache(tmp_path):
    """Modifying a list referenced by the function invalidates cache"""
    cache_dir = tmp_path / "cache"

    weights = [1.0, 2.0, 3.0]

    @cache_file(cache_dir=cache_dir, backend="pickle")
    def compute(x):
        return sum(w * x for w in weights)

    # Run 1: 1*5 + 2*5 + 3*5 = 30
    assert compute(5) == 30.0

    # Mutate the list
    weights[2] = 10.0

    # Run 2: 1*5 + 2*5 + 10*5 = 65
    assert compute(5) == 65.0

    assert count_cache_entries(cache_dir) == 2


def test_env_var_tracking(tmp_path, monkeypatch):
    """Cache invalidates when tracked environment variables change"""
    cache_dir = tmp_path / "cache"

    monkeypatch.setenv("MY_APP_MODE", "development")

    @cache_file(cache_dir=cache_dir, backend="pickle", env_vars=["MY_APP_MODE"])
    def get_mode():
        import os
        return os.getenv("MY_APP_MODE")

    assert get_mode() == "development"

    monkeypatch.setenv("MY_APP_MODE", "production")

    assert get_mode() == "production"

    assert count_cache_entries(cache_dir) == 2


def test_env_var_not_tracked_by_default(tmp_path, monkeypatch):
    """Without env_vars, environment variable changes don't invalidate cache"""
    cache_dir = tmp_path / "cache"

    monkeypatch.setenv("MY_APP_MODE", "development")

    @cache_file(cache_dir=cache_dir, backend="pickle")
    def get_mode():
        import os
        return os.getenv("MY_APP_MODE")

    result1 = get_mode()
    assert result1 == "development"

    monkeypatch.setenv("MY_APP_MODE", "production")

    # Without env_vars tracking, cache hit returns stale value
    result2 = get_mode()
    assert result2 == "development"  # cached result, not re-run

    assert count_cache_entries(cache_dir) == 1
