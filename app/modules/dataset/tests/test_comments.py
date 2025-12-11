"""
Tests for Dataset Comments functionality
"""

import pytest

from app.modules.dataset.models import DatasetComment


class TestDatasetComments:
    """Test suite for dataset comments feature"""

    def test_get_comments_empty(self, client, test_dataset):
        """Test getting comments for a dataset with no comments"""
        response = client.get(f"/dataset/{test_dataset.id}/comments")
        assert response.status_code == 200
        data = response.get_json()
        assert "comments" in data
        assert len(data["comments"]) == 0

    def test_create_comment_unauthenticated(self, client, test_dataset):
        """Test that unauthenticated users cannot create comments"""
        response = client.post(
            f"/dataset/{test_dataset.id}/comments",
            json={"content": "Test comment"},
        )
        # Should redirect to login
        assert response.status_code in [302, 401]

    def test_create_comment_authenticated(self, client, test_dataset, test_user):
        """Test creating a comment as authenticated user"""
        # Login
        with client.session_transaction() as sess:
            sess["_user_id"] = str(test_user.id)

        response = client.post(
            f"/dataset/{test_dataset.id}/comments",
            json={"content": "This is a great dataset!"},
        )
        assert response.status_code == 201
        data = response.get_json()
        assert data["message"] == "Comment posted successfully"
        assert "comment" in data
        assert data["comment"]["content"] == "This is a great dataset!"

    def test_create_comment_empty_content(self, client, test_dataset, test_user):
        """Test that empty comments are rejected"""
        with client.session_transaction() as sess:
            sess["_user_id"] = str(test_user.id)

        response = client.post(
            f"/dataset/{test_dataset.id}/comments",
            json={"content": "   "},
        )
        assert response.status_code == 400
        data = response.get_json()
        assert "message" in data

    def test_update_comment_owner(self, client, test_dataset, test_user, db_session):
        """Test updating own comment"""
        # Create a comment
        comment = DatasetComment(
            dataset_id=test_dataset.id,
            user_id=test_user.id,
            content="Original content",
        )
        db_session.add(comment)
        db_session.commit()

        # Login and update
        with client.session_transaction() as sess:
            sess["_user_id"] = str(test_user.id)

        response = client.put(
            f"/dataset/comments/{comment.id}",
            json={"content": "Updated content"},
        )
        assert response.status_code == 200
        data = response.get_json()
        assert data["message"] == "Comment updated successfully"
        assert data["comment"]["content"] == "Updated content"

    def test_update_comment_not_owner(self, client, test_dataset, test_user, test_user2, db_session):
        """Test that users cannot update others' comments"""
        # Create a comment by user1
        comment = DatasetComment(
            dataset_id=test_dataset.id,
            user_id=test_user.id,
            content="Original content",
        )
        db_session.add(comment)
        db_session.commit()

        # Login as user2 and try to update
        with client.session_transaction() as sess:
            sess["_user_id"] = str(test_user2.id)

        response = client.put(
            f"/dataset/comments/{comment.id}",
            json={"content": "Hacked content"},
        )
        assert response.status_code == 400
        data = response.get_json()
        assert "only edit your own comments" in data["message"].lower()

    def test_delete_comment_owner(self, client, test_dataset, test_user, db_session):
        """Test deleting own comment"""
        # Create a comment
        comment = DatasetComment(
            dataset_id=test_dataset.id,
            user_id=test_user.id,
            content="To be deleted",
        )
        db_session.add(comment)
        db_session.commit()
        comment_id = comment.id

        # Login and delete
        with client.session_transaction() as sess:
            sess["_user_id"] = str(test_user.id)

        response = client.delete(f"/dataset/comments/{comment_id}")
        assert response.status_code == 200
        data = response.get_json()
        assert data["message"] == "Comment deleted successfully"

        # Verify comment is deleted
        assert db_session.query(DatasetComment).filter_by(id=comment_id).first() is None

    def test_delete_comment_not_owner(self, client, test_dataset, test_user, test_user2, db_session):
        """Test that users cannot delete others' comments"""
        # Create a comment by user1
        comment = DatasetComment(
            dataset_id=test_dataset.id,
            user_id=test_user.id,
            content="Protected comment",
        )
        db_session.add(comment)
        db_session.commit()

        # Login as user2 and try to delete
        with client.session_transaction() as sess:
            sess["_user_id"] = str(test_user2.id)

        response = client.delete(f"/dataset/comments/{comment.id}")
        assert response.status_code == 400
        data = response.get_json()
        assert "only delete your own comments" in data["message"].lower()

    def test_get_comments_with_data(self, client, test_dataset, test_user, test_user2, db_session):
        """Test getting multiple comments"""
        # Create multiple comments
        comment1 = DatasetComment(
            dataset_id=test_dataset.id,
            user_id=test_user.id,
            content="First comment",
        )
        comment2 = DatasetComment(
            dataset_id=test_dataset.id,
            user_id=test_user2.id,
            content="Second comment",
        )
        db_session.add_all([comment1, comment2])
        db_session.commit()

        response = client.get(f"/dataset/{test_dataset.id}/comments")
        assert response.status_code == 200
        data = response.get_json()
        assert len(data["comments"]) == 2

        # Comments should be ordered by created_at descending
        assert data["comments"][0]["content"] == "Second comment"
        assert data["comments"][1]["content"] == "First comment"

    def test_comment_cascade_delete_with_dataset(self, client, test_dataset, test_user, db_session):
        """Test that comments are deleted when dataset is deleted"""
        # Create a comment
        comment = DatasetComment(
            dataset_id=test_dataset.id,
            user_id=test_user.id,
            content="This will be deleted",
        )
        db_session.add(comment)
        db_session.commit()
        comment_id = comment.id

        # Delete the dataset
        db_session.delete(test_dataset)
        db_session.commit()

        # Verify comment is also deleted
        assert db_session.query(DatasetComment).filter_by(id=comment_id).first() is None


# Fixtures needed (add to conftest.py if not present)
@pytest.fixture
def test_user(db_session):
    """Create a test user"""
    from app.modules.auth.models import User
    from app.modules.profile.models import UserProfile

    user = User(email="testuser@example.com")
    user.set_password("password123")
    profile = UserProfile(name="Test", surname="User", user=user)
    db_session.add(user)
    db_session.add(profile)
    db_session.commit()
    return user


@pytest.fixture
def test_user2(db_session):
    """Create a second test user"""
    from app.modules.auth.models import User
    from app.modules.profile.models import UserProfile

    user = User(email="testuser2@example.com")
    user.set_password("password123")
    profile = UserProfile(name="Test2", surname="User2", user=user)
    db_session.add(user)
    db_session.add(profile)
    db_session.commit()
    return user


@pytest.fixture
def test_dataset(db_session, test_user):
    """Create a test dataset"""
    from app.modules.dataset.models import DataSet, DSMetaData, DSMetrics, PublicationType

    metrics = DSMetrics(number_of_models="1", number_of_features="10")
    metadata = DSMetaData(
        title="Test Dataset",
        description="A test dataset",
        publication_type=PublicationType.NONE,
        ds_metrics=metrics,
    )
    dataset = DataSet(user_id=test_user.id, ds_meta_data=metadata)
    db_session.add(dataset)
    db_session.commit()
    return dataset
