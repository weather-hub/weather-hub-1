import pytest

from app import db
from app.modules.auth.models import User
from app.modules.conftest import login, logout
from app.modules.dataset.models import DataSet, DataSetConcept, DSMetaData, PublicationType
from app.modules.dataset.repositories import DSMetaDataEditLogRepository
from app.modules.dataset.services import DSMetaDataEditLogService
from app.modules.profile.models import UserProfile


@pytest.fixture
def edit_log_service():
    return DSMetaDataEditLogService()


@pytest.fixture
def sample_user(test_client):
    """Create a sample user. test_client already provides app context."""
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

    # Return user - context is handled by test_client
    return user


@pytest.fixture
def sample_dataset(test_client, sample_user):
    """Create a sample dataset. test_client already provides app context."""
    ds_meta = DSMetaData(
        title="Test Dataset",
        description="A test dataset for editing",
        publication_type=PublicationType.NONE,
        tags="test,sample",
        dataset_doi="10.1234/test.dataset.1",
    )
    db.session.add(ds_meta)
    db.session.flush()

    dataset = DataSet(user_id=sample_user.id, ds_meta_data_id=ds_meta.id)
    db.session.add(dataset)
    db.session.commit()

    return dataset


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


def test_get_changelog_by_dataset_id(test_app, edit_log_service, sample_dataset, sample_user):
    """Test that get_changelog_by_dataset_id returns logs for a dataset."""
    with test_app.app_context():
        edit_log_service.log_edit(
            ds_meta_data_id=sample_dataset.ds_meta_data_id,
            user_id=sample_user.id,
            field_name="title",
            old_value="Old Title",
            new_value="New Title",
        )

        changelog = edit_log_service.get_changelog_by_dataset_id(sample_dataset.id)

        assert len(changelog) >= 1
        assert changelog[0].field_name == "title"


def test_get_changelog_by_dataset_id_empty(test_app, edit_log_service, sample_user):
    """Test that get_changelog_by_dataset_id returns empty list for dataset with no logs."""
    with test_app.app_context():
        concept = DataSetConcept(conceptual_doi="10.1234/test.empty.concept")
        db.session.add(concept)
        db.session.flush()

        ds_meta = DSMetaData(
            title="Empty Dataset",
            description="A test dataset with no logs",
            publication_type=PublicationType.NONE,
            tags="test",
            dataset_doi="10.1234/test.empty",
        )
        db.session.add(ds_meta)
        db.session.flush()

        dataset = DataSet(
            user_id=sample_user.id,
            ds_meta_data_id=ds_meta.id,
            ds_concept_id=concept.id,
            version_number="v1.0.0",
        )
        db.session.add(dataset)
        db.session.commit()

        changelog = edit_log_service.get_changelog_by_dataset_id(dataset.id)
        assert changelog == []


def test_get_changelog_by_dataset_id_with_multiple_versions(test_app, edit_log_service, sample_user):
    """Test that get_changelog_by_dataset_id returns logs from multiple versions in same major version."""
    with test_app.app_context():
        concept = DataSetConcept(conceptual_doi="10.1234/test.concept.1")
        db.session.add(concept)
        db.session.flush()

        ds_meta1 = DSMetaData(
            title="Test Dataset v1",
            description="A test dataset",
            publication_type=PublicationType.NONE,
            tags="test",
            dataset_doi="10.1234/test.concept.1",
        )
        db.session.add(ds_meta1)
        db.session.flush()

        dataset1 = DataSet(
            user_id=sample_user.id,
            ds_meta_data_id=ds_meta1.id,
            ds_concept_id=concept.id,
            version_number="v1.0.0",
        )
        db.session.add(dataset1)
        db.session.flush()

        edit_log_service.log_edit(
            ds_meta_data_id=ds_meta1.id,
            user_id=sample_user.id,
            field_name="title",
            old_value="Old",
            new_value="New v1",
        )

        ds_meta2 = DSMetaData(
            title="Test Dataset v2",
            description="A test dataset",
            publication_type=PublicationType.NONE,
            tags="test",
            dataset_doi="10.1234/test.concept.1.v2",
        )
        db.session.add(ds_meta2)
        db.session.flush()

        dataset2 = DataSet(
            user_id=sample_user.id,
            ds_meta_data_id=ds_meta2.id,
            ds_concept_id=concept.id,
            version_number="v1.0.1",
        )
        db.session.add(dataset2)
        db.session.commit()

        edit_log_service.log_edit(
            ds_meta_data_id=ds_meta2.id,
            user_id=sample_user.id,
            field_name="title",
            old_value="New v1",
            new_value="New v2",
        )

        changelog = edit_log_service.get_changelog_by_dataset_id(dataset2.id)

        assert len(changelog) >= 2


def test_repository_get_by_dataset_id(test_app, sample_user):
    """Test that repository get_by_dataset_id returns logs grouped by major version."""
    with test_app.app_context():
        from app.modules.dataset.models import DSMetaDataEditLog

        repository = DSMetaDataEditLogRepository()

        concept = DataSetConcept(conceptual_doi="10.1234/test.concept.2")
        db.session.add(concept)
        db.session.flush()

        ds_meta1 = DSMetaData(
            title="Test Dataset",
            description="A test dataset",
            publication_type=PublicationType.NONE,
            tags="test",
            dataset_doi="10.1234/test.concept.2",
        )
        db.session.add(ds_meta1)
        db.session.flush()

        dataset1 = DataSet(
            user_id=sample_user.id,
            ds_meta_data_id=ds_meta1.id,
            ds_concept_id=concept.id,
            version_number="v1.0.0",
        )
        db.session.add(dataset1)
        db.session.commit()

        log1 = DSMetaDataEditLog(
            ds_meta_data_id=ds_meta1.id,
            user_id=sample_user.id,
            field_name="title",
            old_value="Old",
            new_value="New",
        )
        db.session.add(log1)
        db.session.commit()

        logs = repository.get_by_dataset_id(dataset1.id)

        assert len(logs) >= 1
        assert logs[0].field_name == "title"


def test_repository_get_by_dataset_id_nonexistent(test_app):
    """Test that repository get_by_dataset_id returns empty list for nonexistent dataset."""
    with test_app.app_context():
        repository = DSMetaDataEditLogRepository()
        logs = repository.get_by_dataset_id(99999)
        assert logs == []


def test_repository_get_by_dataset_id_no_concept(test_app, sample_user):
    """Test that repository get_by_dataset_id handles dataset without concept."""
    with test_app.app_context():
        repository = DSMetaDataEditLogRepository()

        ds_meta = DSMetaData(
            title="Test Dataset",
            description="A test dataset",
            publication_type=PublicationType.NONE,
            tags="test",
            dataset_doi="10.1234/test.concept.4",
        )
        db.session.add(ds_meta)
        db.session.flush()

        dataset = DataSet(
            user_id=sample_user.id, ds_meta_data_id=ds_meta.id, ds_concept_id=None, version_number="v1.0.0"
        )
        db.session.add(dataset)
        db.session.commit()

        logs = repository.get_by_dataset_id(dataset.id)

        assert isinstance(logs, list)


def test_view_dataset_changelog_route_requires_login(test_client, sample_dataset):
    """Test that view_dataset_changelog route requires authentication."""
    dataset_id = sample_dataset.id
    response = test_client.get(f"/dataset/{dataset_id}/changelog")
    assert response.status_code in [302, 401]


def test_view_dataset_changelog_route_success(test_client, sample_user, sample_dataset):
    """Test that view_dataset_changelog route renders template with changelog data."""
    from app.modules.dataset.services import DSMetaDataEditLogService

    # test_client already provides app context, no need to open another
    edit_log_service = DSMetaDataEditLogService()
    edit_log_service.log_edit(
        ds_meta_data_id=sample_dataset.ds_meta_data_id,
        user_id=sample_user.id,
        field_name="title",
        old_value="Old Title",
        new_value="New Title",
    )
    db.session.commit()
    dataset_id = sample_dataset.id

    login_response = login(test_client, "test@example.com", "test1234")
    assert login_response.status_code == 200

    response = test_client.get(f"/dataset/{dataset_id}/changelog")
    assert response.status_code == 200
    assert b"Edit Changelog" in response.data

    logout(test_client)


def test_view_dataset_changelog_with_version_groups(test_client, sample_user):
    """Test that view_dataset_changelog groups logs by version correctly."""
    from app.modules.dataset.services import DSMetaDataEditLogService

    # test_client already provides app context
    edit_log_service = DSMetaDataEditLogService()

    concept = DataSetConcept(conceptual_doi="10.1234/test.concept.3")
    db.session.add(concept)
    db.session.flush()

    ds_meta = DSMetaData(
        title="Test Dataset",
        description="A test dataset",
        publication_type=PublicationType.NONE,
        tags="test",
        dataset_doi="10.1234/test.concept.3",
    )
    db.session.add(ds_meta)
    db.session.flush()

    dataset = DataSet(
        user_id=sample_user.id,
        ds_meta_data_id=ds_meta.id,
        ds_concept_id=concept.id,
        version_number="v1.0.0",
    )
    db.session.add(dataset)
    db.session.commit()

    edit_log_service.log_edit(
        ds_meta_data_id=ds_meta.id,
        user_id=sample_user.id,
        field_name="version",
        old_value="v1.0.0",
        new_value="v1.0.1",
    )

    edit_log_service.log_edit(
        ds_meta_data_id=ds_meta.id,
        user_id=sample_user.id,
        field_name="title",
        old_value="Old",
        new_value="New",
    )
    db.session.commit()
    dataset_id = dataset.id

    login_response = login(test_client, "test@example.com", "test1234")
    assert login_response.status_code == 200

    response = test_client.get(f"/dataset/{dataset_id}/changelog")
    assert response.status_code == 200
    assert b"Edit Changelog" in response.data

    logout(test_client)


def test_view_dataset_changelog_empty_changelog(test_client, sample_user, sample_dataset):
    """Test that view_dataset_changelog handles empty changelog gracefully."""
    dataset_id = sample_dataset.id

    login_response = login(test_client, "test@example.com", "test1234")
    assert login_response.status_code == 200

    response = test_client.get(f"/dataset/{dataset_id}/changelog")
    assert response.status_code == 200
    assert b"Edit Changelog" in response.data

    logout(test_client)


def test_view_dataset_changelog_logs_without_version_group(test_client, sample_user):
    """Test that view_dataset_changelog handles logs without version changes."""
    from app.modules.dataset.services import DSMetaDataEditLogService

    # test_client already provides app context
    edit_log_service = DSMetaDataEditLogService()

    concept = DataSetConcept(conceptual_doi="10.1234/test.concept.4")
    db.session.add(concept)
    db.session.flush()

    ds_meta = DSMetaData(
        title="Test Dataset",
        description="A test dataset",
        publication_type=PublicationType.NONE,
        tags="test",
        dataset_doi="10.1234/test.concept.4",
    )
    db.session.add(ds_meta)
    db.session.flush()

    dataset = DataSet(
        user_id=sample_user.id,
        ds_meta_data_id=ds_meta.id,
        ds_concept_id=concept.id,
        version_number="v1.0.0",
    )
    db.session.add(dataset)
    db.session.commit()

    edit_log_service.log_edit(
        ds_meta_data_id=ds_meta.id,
        user_id=sample_user.id,
        field_name="title",
        old_value="Old Title",
        new_value="New Title",
    )

    edit_log_service.log_edit(
        ds_meta_data_id=ds_meta.id,
        user_id=sample_user.id,
        field_name="description",
        old_value="Old Desc",
        new_value="New Desc",
    )
    db.session.commit()
    dataset_id = dataset.id

    login_response = login(test_client, "test@example.com", "test1234")
    assert login_response.status_code == 200

    response = test_client.get(f"/dataset/{dataset_id}/changelog")
    assert response.status_code == 200
    assert b"Edit Changelog" in response.data

    logout(test_client)


def test_view_dataset_changelog_multiple_version_groups(test_client, sample_user):
    """Test that view_dataset_changelog correctly handles multiple version groups."""
    from app.modules.dataset.services import DSMetaDataEditLogService

    # test_client already provides app context
    edit_log_service = DSMetaDataEditLogService()

    concept = DataSetConcept(conceptual_doi="10.1234/test.concept.5")
    db.session.add(concept)
    db.session.flush()

    ds_meta = DSMetaData(
        title="Test Dataset",
        description="A test dataset",
        publication_type=PublicationType.NONE,
        tags="test",
        dataset_doi="10.1234/test.concept.5",
    )
    db.session.add(ds_meta)
    db.session.flush()

    dataset = DataSet(
        user_id=sample_user.id,
        ds_meta_data_id=ds_meta.id,
        ds_concept_id=concept.id,
        version_number="v1.0.0",
    )
    db.session.add(dataset)
    db.session.commit()

    edit_log_service.log_edit(
        ds_meta_data_id=ds_meta.id,
        user_id=sample_user.id,
        field_name="version",
        old_value="v1.0.0",
        new_value="v1.0.1",
    )

    edit_log_service.log_edit(
        ds_meta_data_id=ds_meta.id,
        user_id=sample_user.id,
        field_name="title",
        old_value="Old",
        new_value="New",
    )

    edit_log_service.log_edit(
        ds_meta_data_id=ds_meta.id,
        user_id=sample_user.id,
        field_name="version",
        old_value="v1.0.1",
        new_value="v1.0.2",
    )

    edit_log_service.log_edit(
        ds_meta_data_id=ds_meta.id,
        user_id=sample_user.id,
        field_name="description",
        old_value="Old Desc",
        new_value="New Desc",
    )
    db.session.commit()
    dataset_id = dataset.id

    login_response = login(test_client, "test@example.com", "test1234")
    assert login_response.status_code == 200

    response = test_client.get(f"/dataset/{dataset_id}/changelog")
    assert response.status_code == 200
    assert b"Edit Changelog" in response.data

    logout(test_client)
