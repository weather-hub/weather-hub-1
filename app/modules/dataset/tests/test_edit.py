import pytest

from app import db
from app.modules.auth.models import User
from app.modules.conftest import login, logout
from app.modules.dataset.models import DataSet, DSMetaData, PublicationType
from app.modules.profile.models import UserProfile


@pytest.fixture(scope="module")
def test_client(test_client):
    with test_client.application.app_context():
        user = User.query.filter_by(email="test@example.com").first()

        profile = UserProfile.query.filter_by(user_id=user.id).first()
        if not profile:
            profile = UserProfile(user_id=user.id, name="Test", surname="User")
            db.session.add(profile)
            db.session.commit()

        ds_meta = DSMetaData(
            title="Test Dataset for Editing",
            description="Dataset for testing edit functionality",
            publication_type=PublicationType.NONE,
            tags="test,edit",
            dataset_doi="10.1234/test.dataset.1",  # Add DOI so templates don't fail
        )
        db.session.add(ds_meta)
        db.session.flush()

        dataset = DataSet(
            user_id=user.id,
            ds_meta_data_id=ds_meta.id,
        )
        db.session.add(dataset)
        db.session.commit()

    yield test_client


def test_edit_dataset_get_returns_form(test_client):
    """Test GET /dataset/<id>/edit returns edit form."""
    login_response = login(test_client, "test@example.com", "test1234")
    assert login_response.status_code == 200, "Login was unsuccessful"

    with test_client.application.app_context():
        user = User.query.filter_by(email="test@example.com").first()
        dataset = DataSet.query.filter_by(user_id=user.id).first()
        assert dataset is not None, "Test dataset should exist"
        dataset_id = dataset.id

    response = test_client.get(f"/dataset/{dataset_id}/edit")
    assert response.status_code == 200, "The edit page could not be accessed"
    assert b"Edit Dataset" in response.data or b"edit" in response.data.lower(), "Expected content not present"

    logout(test_client)


def test_edit_dataset_post_updates_metadata(test_client):
    """Test POST /dataset/<id>/edit updates metadata."""
    login_response = login(test_client, "test@example.com", "test1234")
    assert login_response.status_code == 200, "Login was unsuccessful"

    with test_client.application.app_context():
        user = User.query.filter_by(email="test@example.com").first()
        dataset = DataSet.query.filter_by(user_id=user.id).first()
        dataset_id = dataset.id

    response = test_client.post(
        f"/dataset/{dataset_id}/edit",
        data={
            "title": "Updated Title",
            "description": "Updated description for testing",
            "tags": "updated,tags",
        },
    )

    assert response.status_code == 200, "Update was unsuccessful"

    with test_client.application.app_context():
        updated_dataset = DataSet.query.get(dataset_id)
        updated_meta = DSMetaData.query.get(updated_dataset.ds_meta_data_id)
        assert updated_meta.title == "Updated Title"
        assert updated_meta.description == "Updated description for testing"
        assert updated_meta.tags == "updated,tags"

    logout(test_client)


def test_edit_dataset_creates_changelog(test_client):
    """Test that editing creates changelog entries."""
    login_response = login(test_client, "test@example.com", "test1234")
    assert login_response.status_code == 200, "Login was unsuccessful"

    with test_client.application.app_context():
        user = User.query.filter_by(email="test@example.com").first()
        dataset = DataSet.query.filter_by(user_id=user.id).first()
        dataset_id = dataset.id
        meta = DSMetaData.query.get(dataset.ds_meta_data_id)
        description = meta.description
        tags = meta.tags or ""

    response = test_client.post(
        f"/dataset/{dataset_id}/edit",
        data={
            "title": "Changed Title",
            "description": description,
            "tags": tags,
        },
    )

    assert response.status_code == 200, "Update was unsuccessful"

    changelog_response = test_client.get(f"/dataset/{dataset_id}/changelog")
    assert changelog_response.status_code == 200, "Changelog page could not be accessed"
    assert b"title" in changelog_response.data.lower()

    logout(test_client)


def test_view_versions_returns_page(test_client):
    """Test GET /dataset/<id>/versions returns versions page."""
    login_response = login(test_client, "test@example.com", "test1234")
    assert login_response.status_code == 200, "Login was unsuccessful"

    with test_client.application.app_context():
        user = User.query.filter_by(email="test@example.com").first()
        dataset = DataSet.query.filter_by(user_id=user.id).first()
        dataset_id = dataset.id

    response = test_client.get(f"/dataset/{dataset_id}/versions")
    assert response.status_code == 200, "Versions page could not be accessed"
    assert b"Version" in response.data

    logout(test_client)


def test_view_changelog_returns_page(test_client):
    """Test GET /dataset/<id>/changelog returns changelog page."""
    login_response = login(test_client, "test@example.com", "test1234")
    assert login_response.status_code == 200, "Login was unsuccessful"

    with test_client.application.app_context():
        user = User.query.filter_by(email="test@example.com").first()
        dataset = DataSet.query.filter_by(user_id=user.id).first()
        dataset_id = dataset.id

    response = test_client.get(f"/dataset/{dataset_id}/changelog")
    assert response.status_code == 200, "Changelog page could not be accessed"
    assert b"changelog" in response.data.lower() or b"Edit" in response.data

    logout(test_client)


def test_api_changelog_returns_json(test_client):
    """Test API endpoint returns JSON changelog."""
    login_response = login(test_client, "test@example.com", "test1234")
    assert login_response.status_code == 200, "Login was unsuccessful"

    with test_client.application.app_context():
        user = User.query.filter_by(email="test@example.com").first()
        dataset = DataSet.query.filter_by(user_id=user.id).first()
        dataset_id = dataset.id

    response = test_client.get(f"/api/dataset/{dataset_id}/changelog")
    assert response.status_code == 200, "API endpoint was unsuccessful"
    assert response.content_type == "application/json"

    data = response.get_json()
    assert "dataset_id" in data
    assert "changelog" in data

    logout(test_client)


def test_edit_requires_ownership(test_client):
    """Test that editing requires ownership."""
    with test_client.application.app_context():
        other_user = User(email="other@test.com", password="test1234")
        db.session.add(other_user)
        db.session.commit()

    login_response = login(test_client, "test@example.com", "test1234")
    assert login_response.status_code == 200, "Login was unsuccessful"

    with test_client.application.app_context():
        user = User.query.filter_by(email="test@example.com").first()
        dataset = DataSet.query.filter_by(user_id=user.id).first()
        dataset_id = dataset.id

    response = test_client.get(f"/dataset/{dataset_id}/edit")
    assert response.status_code == 200, "Owner should be able to edit"

    logout_response = logout(test_client)
    assert logout_response.status_code == 200, "Logout should succeed"

    with test_client.session_transaction() as sess:
        sess.clear()

    login_response = login(test_client, "other@test.com", "test1234")
    assert login_response.status_code == 200, "Login as other user was unsuccessful"

    verify_response = test_client.get("/dataset/list", follow_redirects=False)
    if verify_response.status_code == 302:
        login_response = login(test_client, "other@test.com", "test1234")
        assert login_response.status_code == 200, "Second login attempt failed"

    response = test_client.get(f"/dataset/{dataset_id}/edit", follow_redirects=False)
    assert response.status_code == 403, f"Should return 403 Forbidden but got {response.status_code}"

    logout(test_client)


def test_no_changes_returns_message(test_client):
    """Test that submitting without changes returns appropriate message."""
    login_response = login(test_client, "test@example.com", "test1234")
    assert login_response.status_code == 200, "Login was unsuccessful"

    with test_client.application.app_context():
        user = User.query.filter_by(email="test@example.com").first()
        dataset = DataSet.query.filter_by(user_id=user.id).first()
        dataset_id = dataset.id
        current_meta = DSMetaData.query.get(dataset.ds_meta_data_id)
        title = current_meta.title
        description = current_meta.description
        tags = current_meta.tags or ""

    response = test_client.post(
        f"/dataset/{dataset_id}/edit",
        data={
            "title": title,
            "description": description,
            "tags": tags,
        },
    )

    assert response.status_code == 200, "Request was unsuccessful"
    data = response.get_json()
    assert "No changes" in data.get("message", "")

    logout(test_client)
