"""
Tests for Explore routes.
"""

from datetime import datetime

from werkzeug.security import generate_password_hash

from app import db
from app.modules.auth.models import User
from app.modules.dataset.models import DataSet, DSMetaData, PublicationType


def test_explore_index_route_with_latest_dataset(test_client):
    """
    Ensure the author enrichment loop is executed when datasets exist.
    """

    user = User(
        email="explore_route_test@example.com",
        password=generate_password_hash("test_password"),
        twofa_enabled=False,
    )
    db.session.add(user)
    db.session.flush()

    meta = DSMetaData(
        title="Latest dataset",
        description="Test dataset",
        publication_type=PublicationType.OTHER,
        publication_doi="10.1234/test",
        dataset_doi=None,
        tags="test",
        ds_metrics_id=None,
    )
    db.session.add(meta)
    db.session.flush()

    dataset = DataSet(
        user_id=user.id,
        ds_meta_data_id=meta.id,
        created_at=datetime.utcnow(),
    )
    db.session.add(dataset)
    db.session.commit()

    response = test_client.get("/explore/")
    assert response.status_code == 200


def test_explore_index_route_basic(test_client):
    """
    Basic GET /explore/ should return HTTP 200.
    """
    response = test_client.get("/explore/")
    assert response.status_code == 200


def test_explore_index_route_with_filters(test_client):
    """
    GET /explore/ with query parameters should return HTTP 200.
    """
    response = test_client.get("/explore/?query=test&sort_by=newest")
    assert response.status_code == 200


def test_explore_index_route_with_date_filters(test_client):
    """
    GET /explore/ with date filters should return HTTP 200.
    """
    response = test_client.get("/explore/?start_date=2024-01-01&end_date=2024-12-31")
    assert response.status_code == 200


def test_explore_index_route_without_any_filters(test_client):
    response = test_client.get("/explore/")
    assert response.status_code == 200
