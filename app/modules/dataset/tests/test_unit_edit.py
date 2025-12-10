import pytest

from app import db
from app.modules.auth.models import User
from app.modules.dataset.models import DataSet, DSMetaData, PublicationType
from app.modules.dataset.services import DSMetaDataEditLogService
from app.modules.profile.models import UserProfile


@pytest.fixture
def edit_log_service():
    return DSMetaDataEditLogService()


@pytest.fixture
def sample_user(test_client, test_app):
    with test_app.app_context():
        user = User.query.filter_by(email="test@example.com").first()
        if not user:
            user = User(email="test@example.com", password="test1234")
            db.session.add(user)
            db.session.flush()

        profile = UserProfile.query.filter_by(user_id=user.id).first()
        if not profile:
            profile = UserProfile(user_id=user.id, name="Editor", surname="Test")
            db.session.add(profile)

        db.session.commit()
        yield user


@pytest.fixture
def sample_dataset(test_client, test_app, sample_user):
    with test_app.app_context():
        ds_meta = DSMetaData(
            title="Test Dataset",
            description="A test dataset for editing",
            publication_type=PublicationType.NONE,
            tags="test,sample",
        )
        db.session.add(ds_meta)
        db.session.flush()

        dataset = DataSet(user_id=sample_user.id, ds_meta_data_id=ds_meta.id)
        db.session.add(dataset)
        db.session.commit()

        yield dataset


def test_log_edit_creates_record(test_app, edit_log_service, sample_dataset, sample_user):
    """Test that log_edit creates a DSMetaDataEditLog record."""
    with test_app.app_context():
        log = edit_log_service.log_edit(
            ds_meta_data_id=sample_dataset.ds_meta_data_id,
            user_id=sample_user.id,
            field_name="title",
            old_value="Old Title",
            new_value="New Title",
        )

        assert log is not None
        assert log.field_name == "title"
        assert log.old_value == "Old Title"
        assert log.new_value == "New Title"
        assert log.user_id == sample_user.id


def test_log_multiple_edits(test_app, edit_log_service, sample_dataset, sample_user):
    """Test logging multiple edits at once."""
    with test_app.app_context():
        changes = [
            {"field": "title", "old": "Old Title", "new": "New Title"},
            {"field": "description", "old": "Old Desc", "new": "New Desc"},
            {"field": "tags", "old": "old,tags", "new": "new,tags"},
        ]

        logs = edit_log_service.log_multiple_edits(
            ds_meta_data_id=sample_dataset.ds_meta_data_id,
            user_id=sample_user.id,
            changes=changes,
        )

        assert len(logs) == 3
        assert logs[0].field_name == "title"
        assert logs[1].field_name == "description"
        assert logs[2].field_name == "tags"


def test_get_changelog_returns_logs(test_app, edit_log_service, sample_dataset, sample_user):
    """Test that get_changelog returns all logs for a dataset."""
    with test_app.app_context():
        edit_log_service.log_edit(
            ds_meta_data_id=sample_dataset.ds_meta_data_id,
            user_id=sample_user.id,
            field_name="title",
            old_value="V1",
            new_value="V2",
        )

        changelog = edit_log_service.get_changelog(sample_dataset.ds_meta_data_id)

        assert len(changelog) >= 1
        assert changelog[0].field_name == "title"


def test_edit_log_to_dict(test_app, edit_log_service, sample_dataset, sample_user):
    """Test that to_dict returns correct format."""
    with test_app.app_context():
        log = edit_log_service.log_edit(
            ds_meta_data_id=sample_dataset.ds_meta_data_id,
            user_id=sample_user.id,
            field_name="description",
            old_value="Old",
            new_value="New",
            change_summary="Updated description",
        )

        log_dict = log.to_dict()

        assert "id" in log_dict
        assert "field_name" in log_dict
        assert "old_value" in log_dict
        assert "new_value" in log_dict
        assert "edited_at" in log_dict
        assert "edited_by" in log_dict
        assert log_dict["field_name"] == "description"
        assert log_dict["change_summary"] == "Updated description"
