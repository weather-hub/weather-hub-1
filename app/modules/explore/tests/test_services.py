"""
Tests for Explore services.
"""

from app.modules.explore.repositories import ExploreRepository
from app.modules.explore.services import ExploreService


def test_explore_service_initializes_repository():
    """
    ExploreService should initialize with an ExploreRepository instance.
    """
    service = ExploreService()
    assert isinstance(service.repository, ExploreRepository)
