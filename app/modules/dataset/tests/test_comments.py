"""
Tests for Dataset Comments functionality
"""

import pytest

from app import db
from app.modules.auth.models import User
from app.modules.conftest import login, logout
from app.modules.dataset.models import DataSet, DatasetComment, DSMetaData, DSMetrics, PublicationType
from app.modules.profile.models import UserProfile


@pytest.fixture(scope="module")
def test_client(test_client):
    """Setup test client with necessary data."""
    with test_client.application.app_context():
        # Create test users
        user1 = User.query.filter_by(email="testuser@example.com").first()
        if not user1:
            user1 = User(email="testuser@example.com", password="password123")
            db.session.add(user1)
            db.session.flush()

            profile1 = UserProfile(user_id=user1.id, name="Test", surname="User")
            db.session.add(profile1)

        user2 = User.query.filter_by(email="testuser2@example.com").first()
        if not user2:
            user2 = User(email="testuser2@example.com", password="password123")
            db.session.add(user2)
            db.session.flush()

            profile2 = UserProfile(user_id=user2.id, name="Test2", surname="User2")
            db.session.add(profile2)

        # Create test dataset
        metrics = DSMetrics(number_of_models="1", number_of_features="10")
        metadata = DSMetaData(
            title="Test Dataset for Comments",
            description="A test dataset",
            publication_type=PublicationType.NONE,
            ds_metrics=metrics,
        )
        db.session.add(metadata)
        db.session.flush()

        dataset = DataSet(user_id=user1.id, ds_meta_data_id=metadata.id)
        db.session.add(dataset)
        db.session.commit()

    yield test_client


def test_get_comments_empty(test_client):
    """Test getting comments for a dataset with no comments"""
    with test_client.application.app_context():
        dataset = DataSet.query.first()
        dataset_id = dataset.id

    response = test_client.get(f"/dataset/{dataset_id}/comments")
    assert response.status_code == 200
    data = response.get_json()
    assert "comments" in data


def test_create_comment_unauthenticated(test_client):
    """Test that unauthenticated users cannot create comments"""
    with test_client.application.app_context():
        dataset = DataSet.query.first()
        dataset_id = dataset.id

    response = test_client.post(
        f"/dataset/{dataset_id}/comments",
        json={"content": "Test comment"},
    )
    # Should redirect to login or return 401
    assert response.status_code in [302, 401]


def test_create_comment_authenticated(test_client):
    """Test creating a comment as authenticated user"""
    login_response = login(test_client, "testuser@example.com", "password123")
    assert login_response.status_code == 200

    with test_client.application.app_context():
        dataset = DataSet.query.first()
        dataset_id = dataset.id

    response = test_client.post(
        f"/dataset/{dataset_id}/comments",
        json={"content": "This is a great dataset!"},
        content_type="application/json",
    )
    assert response.status_code == 201
    data = response.get_json()
    assert data["message"] == "Comment posted successfully"
    assert "comment" in data
    assert data["comment"]["content"] == "This is a great dataset!"

    logout(test_client)


def test_create_comment_empty_content(test_client):
    """Test that empty comments are rejected"""
    login_response = login(test_client, "testuser@example.com", "password123")
    assert login_response.status_code == 200

    with test_client.application.app_context():
        dataset = DataSet.query.first()
        dataset_id = dataset.id

    response = test_client.post(
        f"/dataset/{dataset_id}/comments",
        json={"content": "   "},
        content_type="application/json",
    )
    assert response.status_code == 400
    data = response.get_json()
    assert "message" in data

    logout(test_client)


def test_update_comment_owner(test_client):
    """Test updating own comment"""
    # Create comment first
    with test_client.application.app_context():
        dataset = DataSet.query.first()
        user = User.query.filter_by(email="testuser@example.com").first()

        # Create a comment
        comment = DatasetComment(
            dataset_id=dataset.id,
            user_id=user.id,
            content="Original content",
        )
        db.session.add(comment)
        db.session.commit()
        comment_id = comment.id

    # Now login and update
    login_response = login(test_client, "testuser@example.com", "password123")
    assert login_response.status_code == 200

    response = test_client.put(
        f"/dataset/comments/{comment_id}",
        json={"content": "Updated content"},
        content_type="application/json",
    )
    assert response.status_code == 200
    data = response.get_json()
    assert data["message"] == "Comment updated successfully"
    assert data["comment"]["content"] == "Updated content"

    logout(test_client)


def test_update_comment_not_owner(test_client):
    """Test that users cannot update others' comments"""
    # Create comment as user1
    login_response = login(test_client, "testuser@example.com", "password123")
    assert login_response.status_code == 200

    with test_client.application.app_context():
        dataset = DataSet.query.first()
        user1 = User.query.filter_by(email="testuser@example.com").first()

        comment = DatasetComment(
            dataset_id=dataset.id,
            user_id=user1.id,
            content="Original content",
        )
        db.session.add(comment)
        db.session.commit()
        comment_id = comment.id

    logout(test_client)

    # Try to update as user2
    login_response = login(test_client, "testuser2@example.com", "password123")
    assert login_response.status_code == 200

    response = test_client.put(
        f"/dataset/comments/{comment_id}",
        json={"content": "Hacked content"},
        content_type="application/json",
    )
    assert response.status_code == 400
    data = response.get_json()
    assert "only edit your own comments" in data["message"].lower()

    logout(test_client)


def test_delete_comment_owner(test_client):
    """Test deleting own comment"""
    # Create comment first
    with test_client.application.app_context():
        dataset = DataSet.query.first()
        user = User.query.filter_by(email="testuser@example.com").first()

        comment = DatasetComment(
            dataset_id=dataset.id,
            user_id=user.id,
            content="To be deleted",
        )
        db.session.add(comment)
        db.session.commit()
        comment_id = comment.id

    # Now login and delete
    login_response = login(test_client, "testuser@example.com", "password123")
    assert login_response.status_code == 200

    response = test_client.delete(f"/dataset/comments/{comment_id}")
    assert response.status_code == 200
    data = response.get_json()
    assert data["message"] == "Comment deleted successfully"

    # Verify comment is deleted
    with test_client.application.app_context():
        deleted_comment = DatasetComment.query.filter_by(id=comment_id).first()
        assert deleted_comment is None

    logout(test_client)


def test_delete_comment_not_owner(test_client):
    """Test that users cannot delete others' comments"""
    # Create comment as user1
    login_response = login(test_client, "testuser@example.com", "password123")
    assert login_response.status_code == 200

    with test_client.application.app_context():
        dataset = DataSet.query.first()
        user1 = User.query.filter_by(email="testuser@example.com").first()

        comment = DatasetComment(
            dataset_id=dataset.id,
            user_id=user1.id,
            content="Protected comment",
        )
        db.session.add(comment)
        db.session.commit()
        comment_id = comment.id

    logout(test_client)

    # Try to delete as user2
    login_response = login(test_client, "testuser2@example.com", "password123")
    assert login_response.status_code == 200

    response = test_client.delete(f"/dataset/comments/{comment_id}")
    assert response.status_code == 400
    data = response.get_json()
    assert "only delete your own comments" in data["message"].lower()

    logout(test_client)


def test_get_comments_with_data(test_client):
    """Test getting multiple comments"""
    with test_client.application.app_context():
        dataset = DataSet.query.first()
        user1 = User.query.filter_by(email="testuser@example.com").first()
        user2 = User.query.filter_by(email="testuser2@example.com").first()

        # Clear existing comments
        DatasetComment.query.filter_by(dataset_id=dataset.id).delete()

        # Create multiple comments
        comment1 = DatasetComment(
            dataset_id=dataset.id,
            user_id=user1.id,
            content="First comment",
        )
        comment2 = DatasetComment(
            dataset_id=dataset.id,
            user_id=user2.id,
            content="Second comment",
        )
        db.session.add_all([comment1, comment2])
        db.session.commit()
        dataset_id = dataset.id

    response = test_client.get(f"/dataset/{dataset_id}/comments")
    assert response.status_code == 200
    data = response.get_json()
    assert len(data["comments"]) >= 2


def test_comment_cascade_delete_with_dataset(test_client):
    """Test that comments are deleted when dataset is deleted"""
    with test_client.application.app_context():
        user = User.query.filter_by(email="testuser@example.com").first()

        # Create a new dataset for this test
        metrics = DSMetrics(number_of_models="1", number_of_features="10")
        metadata = DSMetaData(
            title="Dataset to Delete",
            description="Will be deleted with comments",
            publication_type=PublicationType.NONE,
            ds_metrics=metrics,
        )
        db.session.add(metadata)
        db.session.flush()

        dataset = DataSet(user_id=user.id, ds_meta_data_id=metadata.id)
        db.session.add(dataset)
        db.session.flush()

        # Create a comment
        comment = DatasetComment(
            dataset_id=dataset.id,
            user_id=user.id,
            content="This will be deleted",
        )
        db.session.add(comment)
        db.session.commit()

        comment_id = comment.id
        dataset_id = dataset.id

        # Delete the dataset
        db.session.delete(dataset)
        db.session.commit()

        # Verify comment is also deleted
        deleted_comment = DatasetComment.query.filter_by(id=comment_id).first()
        assert deleted_comment is None
