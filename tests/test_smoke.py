"""Smoke tests for the installed GridSight package."""

from importlib.metadata import version

import gridsight


def test_package_version_matches_installed_metadata() -> None:
    """The imported package and editable install expose the same version."""
    assert gridsight.__version__ == "0.1.0"
    assert gridsight.__version__ == version("gridsight")
