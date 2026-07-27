"""Fixtures for EDF Tempo tests running against Home Assistant."""

from __future__ import annotations

from collections.abc import Generator

import pytest


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(
    enable_custom_integrations: None,
) -> Generator[None]:
    """Allow Home Assistant to load EDF Tempo from custom_components."""
    yield
