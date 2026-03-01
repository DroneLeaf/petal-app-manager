"""Tests for petal_app_manager.compatibility module."""

import types
from unittest.mock import patch

import pytest

from petal_app_manager.compatibility import (
    CompatIssue,
    CompatReport,
    check_all_petals,
    check_module_compatibility,
    check_package_compatibility,
    _installed_version,
    _satisfies,
)


# ─────────────────────────────────── helpers / fixtures ──────────────────

def _make_module(name: str, compat: dict | None = None) -> types.ModuleType:
    """Create a lightweight module-like object with __compatibility__."""
    mod = types.ModuleType(name)
    if compat is not None:
        mod.__compatibility__ = compat
    return mod


# ──────────────────────────────── _satisfies tests ──────────────────────

class TestSatisfies:
    def test_exact_match(self):
        assert _satisfies("1.2.3", "==1.2.3")

    def test_exact_mismatch(self):
        assert not _satisfies("1.2.4", "==1.2.3")

    def test_range(self):
        assert _satisfies("0.1.17", ">=0.1.17,<0.1.18")

    def test_range_too_low(self):
        assert not _satisfies("0.1.16", ">=0.1.17,<0.1.18")

    def test_range_too_high(self):
        assert not _satisfies("0.1.18", ">=0.1.17,<0.1.18")

    def test_gte_only(self):
        assert _satisfies("2.0.0", ">=0.1.11")

    def test_invalid_specifier_is_lenient(self):
        # Should return True (skip check) for unparseable specifiers
        assert _satisfies("1.0.0", "not-a-specifier!!!")


# ──────────────────────── check_package_compatibility ───────────────────

class TestCheckPackageCompatibility:
    @patch("petal_app_manager.compatibility._installed_version")
    def test_all_satisfied(self, mock_ver):
        mock_ver.side_effect = lambda name: {"leaf-pymavlink": "0.1.17", "LeafSDK": "0.3.5"}.get(name)
        report = check_package_compatibility(
            "test-pkg",
            {"leaf-pymavlink": ">=0.1.17,<0.1.18", "LeafSDK": ">=0.3.5,<0.3.6"},
        )
        assert report.ok

    @patch("petal_app_manager.compatibility._installed_version")
    def test_missing_dep(self, mock_ver):
        mock_ver.return_value = None
        report = check_package_compatibility(
            "test-pkg",
            {"leaf-pymavlink": ">=0.1.11"},
        )
        assert not report.ok
        assert len(report.issues) == 1
        assert report.issues[0].is_missing
        assert "leaf-pymavlink" in str(report.issues[0])

    @patch("petal_app_manager.compatibility._installed_version")
    def test_version_mismatch(self, mock_ver):
        mock_ver.return_value = "0.1.10"
        report = check_package_compatibility(
            "test-pkg",
            {"leaf-pymavlink": ">=0.1.11"},
        )
        assert not report.ok
        assert report.issues[0].installed == "0.1.10"

    @patch("petal_app_manager.compatibility._installed_version")
    def test_skip_missing_true(self, mock_ver):
        """With skip_missing=True, absent packages should not be flagged."""
        mock_ver.return_value = None
        report = check_package_compatibility(
            "test-pkg",
            {"leaf-pymavlink": ">=0.1.11"},
            skip_missing=True,
        )
        assert report.ok  # no issues — missing is silently skipped

    @patch("petal_app_manager.compatibility._installed_version")
    def test_skip_missing_still_checks_wrong_version(self, mock_ver):
        """skip_missing only skips absent deps; wrong versions still fail."""
        mock_ver.return_value = "0.1.10"
        report = check_package_compatibility(
            "test-pkg",
            {"leaf-pymavlink": ">=0.1.11"},
            skip_missing=True,
        )
        assert not report.ok
        assert report.issues[0].installed == "0.1.10"


# ──────────────────────── check_module_compatibility ────────────────────

class TestCheckModuleCompatibility:
    @patch("petal_app_manager.compatibility._installed_version")
    def test_module_with_compat(self, mock_ver):
        mock_ver.return_value = "0.2.3"
        mod = _make_module("my_petal", {"petal-app-manager": ">=0.2.3,<0.3.0"})
        report = check_module_compatibility(mod)
        assert report.ok

    def test_module_without_compat(self):
        mod = _make_module("bare_module")
        report = check_module_compatibility(mod)
        assert report.ok  # no __compatibility__ → pass silently

    @patch("petal_app_manager.compatibility._installed_version")
    def test_module_with_failing_dep(self, mock_ver):
        mock_ver.return_value = "0.1.0"
        mod = _make_module("bad_petal", {"petal-app-manager": ">=0.2.3,<0.3.0"})
        report = check_module_compatibility(mod)
        assert not report.ok


# ──────────────────────────── CompatReport ──────────────────────────────

class TestCompatReport:
    def test_empty_is_ok(self):
        r = CompatReport()
        assert r.ok
        assert "passed" in r.summary().lower()

    def test_with_issues(self):
        r = CompatReport(issues=[
            CompatIssue("pkg", "dep", ">=1.0", None),
            CompatIssue("pkg", "dep2", ">=2.0", "1.5"),
        ])
        assert not r.ok
        assert "2 compatibility issue" in r.summary()

    def test_str_missing(self):
        issue = CompatIssue("pkg", "dep", ">=1.0", None)
        assert "NOT installed" in str(issue)

    def test_str_mismatch(self):
        issue = CompatIssue("pkg", "dep", ">=1.0", "0.5")
        assert "found 0.5" in str(issue)


# ──────────────────────────── check_all_petals ──────────────────────────

class TestCheckAllPetals:
    @patch("petal_app_manager.compatibility.check_module_compatibility")
    @patch("petal_app_manager.compatibility.importlib")
    def test_import_failure_is_tolerated(self, mock_importlib, mock_check):
        mock_importlib.import_module.side_effect = ImportError("no such module")
        report = check_all_petals(["nonexistent_module"])
        assert report.ok  # Import failures should not cause issues
        mock_check.assert_not_called()

    @patch("petal_app_manager.compatibility.check_module_compatibility")
    @patch("petal_app_manager.compatibility.importlib")
    def test_merges_reports(self, mock_importlib, mock_check):
        mod = _make_module("a_petal")
        mock_importlib.import_module.return_value = mod
        mock_check.return_value = CompatReport(issues=[
            CompatIssue("a_petal", "lib", ">=1.0", "0.5"),
        ])
        report = check_all_petals(["a_petal"])
        assert not report.ok
        assert len(report.issues) == 1
