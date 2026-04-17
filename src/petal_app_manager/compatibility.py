"""
Dependency compatibility checker for the Petal ecosystem.

This module validates at runtime that every loaded petal has the correct
library versions in the current virtual-environment, and that
``petal-app-manager`` itself sees the expected petal + library versions.

Design
------
Each petal declares a ``__compatibility__`` dict in its package
``__init__.py``.  The keys are *distribution* names (the ``name`` field in
``pyproject.toml``) and the values are :pep:`440` version-specifier strings::

    # petal_flight_log/__init__.py
    __compatibility__ = {
        "petal-app-manager": ">=0.2.3,<0.3.0",
        "leaf-pymavlink":    ">=0.1.11",
    }

``petal-app-manager`` itself declares its expected petal versions in its
own ``__compatibility__`` dict (or the ``prod`` dependency group) so the
same checker can validate the whole stack symmetrically.

Public API
----------
* :func:`check_package_compatibility` — verify one package's declared
  requirements against the live environment.
* :func:`check_all_petals` — bulk-check a list of petal modules.
* :func:`check_environment` — full-stack check (app-manager + petals).
"""

from __future__ import annotations

import importlib
import importlib.metadata as md
import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence

from packaging.specifiers import InvalidSpecifier, SpecifierSet
from packaging.version import InvalidVersion, Version

logger = logging.getLogger(__name__)

# ──────────────────────────────────────── data classes ─────────────────────

@dataclass
class CompatIssue:
    """One compatibility problem."""

    package: str
    """The package being checked (e.g. ``"petal-flight-log"``)."""

    dependency: str
    """The dependency that failed (e.g. ``"leaf-pymavlink"``)."""

    required: str
    """The version specifier string that was expected."""

    installed: Optional[str]
    """The version actually installed, or ``None`` if missing."""

    @property
    def is_missing(self) -> bool:
        return self.installed is None

    def __str__(self) -> str:
        if self.is_missing:
            return (
                f"[{self.package}] requires {self.dependency}{self.required} "
                f"but it is NOT installed"
            )
        return (
            f"[{self.package}] requires {self.dependency}{self.required} "
            f"but found {self.installed}"
        )


@dataclass
class CompatReport:
    """Aggregation of all compatibility issues for a check run."""

    issues: List[CompatIssue] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return len(self.issues) == 0

    def log(self, level: int = logging.WARNING) -> None:
        """Log every issue at *level*."""
        for issue in self.issues:
            logger.log(level, str(issue))

    def summary(self) -> str:
        if self.ok:
            return "All dependency checks passed."
        lines = [f"{len(self.issues)} compatibility issue(s) found:"]
        for issue in self.issues:
            lines.append(f"  • {issue}")
        return "\n".join(lines)

    def __str__(self) -> str:
        return self.summary()


# ──────────────────────────────── helpers ──────────────────────────────────

def _installed_version(dist_name: str) -> Optional[str]:
    """Return the installed version string of *dist_name*, or ``None``."""
    try:
        return md.version(dist_name)
    except md.PackageNotFoundError:
        return None


def _satisfies(installed: str, specifier: str) -> bool:
    """Return ``True`` if *installed* satisfies the PEP 440 *specifier*."""
    try:
        spec = SpecifierSet(specifier)
    except InvalidSpecifier:
        logger.warning("Invalid specifier %r — skipping check", specifier)
        return True
    try:
        ver = Version(installed)
    except InvalidVersion:
        logger.warning("Invalid version %r — skipping check", installed)
        return True
    return ver in spec


# ──────────────────────────────── public API ──────────────────────────────

def check_package_compatibility(
    package_name: str,
    compat_dict: Dict[str, str],
    *,
    skip_missing: bool = False,
) -> CompatReport:
    """Check that every entry in *compat_dict* is satisfied by what is
    currently installed.

    Parameters
    ----------
    package_name:
        Human-readable label for the package being checked (used in
        log messages).
    compat_dict:
        ``{distribution_name: specifier_string}`` mapping, typically
        taken from ``some_package.__compatibility__``.
    skip_missing:
        If ``True``, packages that are not installed at all are silently
        skipped instead of flagged as issues.  Useful for *optional*
        peer-dependency checks (e.g. petal-app-manager checking which
        petals happen to be present).

    Returns
    -------
    CompatReport
    """
    report = CompatReport()

    for dep_name, specifier in compat_dict.items():
        installed = _installed_version(dep_name)
        if installed is None:
            if skip_missing:
                logger.debug(
                    "[%s] %s not installed — skipping (optional)",
                    package_name,
                    dep_name,
                )
                continue
            report.issues.append(
                CompatIssue(
                    package=package_name,
                    dependency=dep_name,
                    required=specifier,
                    installed=None,
                )
            )
        elif not _satisfies(installed, specifier):
            report.issues.append(
                CompatIssue(
                    package=package_name,
                    dependency=dep_name,
                    required=specifier,
                    installed=installed,
                )
            )
        else:
            logger.debug(
                "[%s] %s%s ✓ (installed %s)",
                package_name,
                dep_name,
                specifier,
                installed,
            )

    return report


def check_module_compatibility(module) -> CompatReport:
    """Load and check the ``__compatibility__`` dict of *module*.

    If the module has no ``__compatibility__`` attribute an empty (passing)
    report is returned.
    """
    compat = getattr(module, "__compatibility__", None)
    if compat is None:
        mod_name = getattr(module, "__name__", str(module))
        logger.debug("Module %s has no __compatibility__; skipping", mod_name)
        return CompatReport()

    package_name = getattr(module, "__name__", str(module))
    return check_package_compatibility(package_name, compat)


def check_all_petals(
    petal_import_names: Sequence[str],
) -> CompatReport:
    """Import each petal by its *Python import name* and check compatibility.

    Parameters
    ----------
    petal_import_names:
        e.g. ``["petal_flight_log", "petal_leafsdk", ...]``

    Returns
    -------
    CompatReport
        Merged report for all petals.
    """
    merged = CompatReport()

    for name in petal_import_names:
        try:
            mod = importlib.import_module(name)
        except ImportError as exc:
            logger.warning("Cannot import %s for compatibility check: %s", name, exc)
            continue
        report = check_module_compatibility(mod)
        merged.issues.extend(report.issues)

    return merged


def check_environment(
    petal_import_names: Optional[Sequence[str]] = None,
    strict: bool = False,
) -> CompatReport:
    """Full-stack compatibility check.

    1. Check ``petal-app-manager``'s own ``__compatibility__`` against the
       installed libraries (hard requirements).
    2. Check ``petal-app-manager``'s ``__petal_compatibility__`` against
       whichever petals happen to be installed (soft / optional — only
       version-checked if present).
    3. Check each loaded petal's ``__compatibility__`` against the installed
       libraries.

    Parameters
    ----------
    petal_import_names:
        If ``None``, auto-discovers petals from the ``petal.plugins``
        entry-point group.
    strict:
        If ``True``, raise :class:`RuntimeError` when issues are found
        instead of just returning them.

    Returns
    -------
    CompatReport
    """
    merged = CompatReport()

    # 1) petal-app-manager's own hard requirements (libraries)
    try:
        import petal_app_manager as pam
        report = check_module_compatibility(pam)
        merged.issues.extend(report.issues)

        # 2) petal-app-manager's optional petal version expectations
        petal_compat = getattr(pam, "__petal_compatibility__", None)
        if petal_compat:
            report = check_package_compatibility(
                "petal_app_manager (petal versions)",
                petal_compat,
                skip_missing=True,
            )
            merged.issues.extend(report.issues)
    except ImportError:
        logger.warning("petal_app_manager not importable; skipping self-check")

    # 3) Each petal's own library requirements
    if petal_import_names is None:
        # Auto-discover from entry-points
        eps = md.entry_points(group="petal.plugins")
        petal_import_names = []
        for ep in eps:
            # entry-point value is "module.path:ClassName"
            mod_path = ep.value.split(":")[0]
            # We want the top-level package (e.g. "petal_flight_log")
            top_pkg = mod_path.split(".")[0]
            if top_pkg not in petal_import_names:
                petal_import_names.append(top_pkg)

    report = check_all_petals(petal_import_names)
    merged.issues.extend(report.issues)

    if not merged.ok:
        merged.log(logging.WARNING)
        if strict:
            raise RuntimeError(
                f"Compatibility check failed:\n{merged.summary()}"
            )
    else:
        logger.info("All compatibility checks passed")

    return merged
