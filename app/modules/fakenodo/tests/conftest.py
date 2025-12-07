"""
Pytest configuration for Fakenodo module HTTP tests.

This module provides fixtures for testing Fakenodo HTTP endpoints.
It uses the project's centralized conftest.py which provides test_client fixture.
"""
import pytest
import os


@pytest.fixture(autouse=True)
def use_fake_zenodo_for_tests(monkeypatch):
    """Force USE_FAKE_ZENODO=true for all Fakenodo tests"""
    monkeypatch.setenv('USE_FAKE_ZENODO', 'true')


@pytest.fixture(autouse=True)
def reset_fakenodo_state(test_app):
    """Reset Fakenodo state before and after each test"""
    # Import inside fixture to ensure proper initialization
    from app.modules.fakenodo.services import FakenodoService
    
    # Reset before test
    FakenodoService._instance = None
    
    yield
    
    # Reset after test
    FakenodoService._instance = None
