import importlib

import pytest


@pytest.mark.unit
def test_server_bootstrap_imports_without_circular_dependency() -> None:
    importlib.import_module("backend.bootstrap.api")
