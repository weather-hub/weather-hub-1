import pytest

from app import db
from app.modules.auth.models import User
from app.modules.auth.repositories import UserRepository
from app.modules.comments.services import CommentService
from app.modules.dataset.models import DataSet, DSMetaData

# ----------------------------
# Fixtures
# ----------------------------


@pytest.fixture
def comment_service():
    return CommentService()


@pytest.fixture
def user(test_app, clean_database):
    """Usuario principal para tests"""
    with test_app.app_context():
        u = User(email="test@example.com", password="1234")
        db.session.add(u)
        db.session.commit()
        # Return a session-bound instance
        return db.session.get(User, u.id)


@pytest.fixture
def comment_user(test_app, clean_database):
    """Otro usuario para comentar"""
    with test_app.app_context():
        u = UserRepository().create(email="commenter@example.com", password="1234")
        db.session.commit()
        return db.session.get(User, u.id)


@pytest.fixture
def dataset(test_app, user):
    """Dataset de prueba"""
    with test_app.app_context():
        meta = DSMetaData(title="Test Dataset", description="Description", publication_type="NONE")
        db.session.add(meta)
        db.session.commit()

        ds = DataSet(user_id=user.id, ds_meta_data_id=meta.id)
        db.session.add(ds)
        db.session.commit()
        return db.session.get(DataSet, ds.id)


# ----------------------------
# Tests de CommentService
# ----------------------------


def test_create_comment_success(comment_service, dataset, comment_user, test_app):
    with test_app.app_context():
        comment = comment_service.create_comment(dataset.id, comment_user.id, "This is a test comment")
        assert comment.id is not None
        assert comment.content == "This is a test comment"
        assert comment.dataset_id == dataset.id
        assert comment.author_id == comment_user.id


def test_approve_comment_success(comment_service, dataset, user, test_app):
    with test_app.app_context():
        comment = comment_service.create_comment(dataset.id, user.id, "Approve me")
        approved_comment = comment_service.approve_comment(comment.id)
        assert approved_comment.approved is True


def test_approve_comment_nonexistent_returns_none(comment_service, test_app):
    with test_app.app_context():
        result = comment_service.approve_comment(9999)
        assert result is None


def test_get_comments_for_dataset_owner(comment_service, dataset, user, comment_user, test_app):
    with test_app.app_context():
        comment_service.create_comment(dataset.id, user.id, "Owner comment")
        comment_service.create_comment(dataset.id, comment_user.id, "Other comment")

        comments = comment_service.get_comments_for_dataset(dataset, user)
        assert len(comments) == 2  # El dueño ve todos los comentarios


def test_get_comments_for_dataset_non_owner(comment_service, dataset, user, comment_user, test_app):
    with test_app.app_context():
        comment_service.create_comment(dataset.id, user.id, "Owner comment")  # no aprobado
        comment_service.create_comment(dataset.id, comment_user.id, "User comment")  # no aprobado

        comments = comment_service.get_comments_for_dataset(dataset, comment_user)
        assert len(comments) == 1  # solo su comentario visible
