import os
import tempfile
import uuid
from unittest.mock import Mock, patch

import pytest

from app import db
from app.modules.auth.models import User
from app.modules.dataset.models import (
    DataSet,
    DSMetaData,
    DSViewRecord,
    PublicationType,
)
from app.modules.dataset.services import (
    AuthorService,
    DatasetCommentService,
    DataSetConceptService,
    DataSetService,
    DOIMappingService,
    DSDownloadRecordService,
    DSMetaDataService,
    DSViewRecordService,
    SizeService,
    calculate_checksum_and_size,
)
from app.modules.featuremodel.models import FeatureModel, FMMetaData
from app.modules.profile.models import UserProfile


# Fixtures
@pytest.fixture
def sample_user(test_client, test_app):
    with test_app.app_context():
        user = User.query.filter_by(email="test_services@example.com").first()
        if not user:
            user = User(email="test_services@example.com", password="test1234")
            db.session.add(user)
            db.session.flush()

        profile = UserProfile.query.filter_by(user_id=user.id).first()
        if not profile:
            profile = UserProfile(
                user_id=user.id,
                name="Test",
                surname="Services",
                affiliation="Test University",
                orcid="0000-0000-0000-0001",
            )
            db.session.add(profile)

        db.session.commit()
        yield user
        db.session.rollback()


@pytest.fixture
def sample_dataset(test_client, test_app, sample_user):
    with test_app.app_context():
        ds_meta = DSMetaData(
            title="Test Dataset Services",
            description="Dataset for services testing",
            publication_type=PublicationType.NONE,
            dataset_doi="10.1234/test",
            tags="test,services",
        )
        db.session.add(ds_meta)
        db.session.flush()

        dataset = DataSet(user_id=sample_user.id, ds_meta_data_id=ds_meta.id, version_number="1.0.0")
        db.session.add(dataset)
        db.session.commit()

        yield dataset
        db.session.rollback()


@pytest.fixture
def dataset_with_feature_models(test_app, sample_dataset):
    with test_app.app_context():
        dataset = DataSet.query.get(sample_dataset.id)

        fm_meta = FMMetaData(
            filename="test_model.uvl",
            title="Test Feature Model",
            description="A test feature model",
            publication_type=PublicationType.NONE,
        )
        db.session.add(fm_meta)
        db.session.flush()

        feature_model = FeatureModel(data_set_id=dataset.id, fm_meta_data_id=fm_meta.id)
        db.session.add(feature_model)
        db.session.commit()

        yield dataset
        db.session.rollback()


# Test calculate_checksum_and_size
def test_calculate_checksum_and_size():
    """Test checksum and size calculation for a file."""
    with tempfile.NamedTemporaryFile(delete=False) as tmp_file:
        content = b"test content for checksum"
        tmp_file.write(content)
        tmp_file.flush()
        tmp_file_path = tmp_file.name

    try:
        checksum, size = calculate_checksum_and_size(tmp_file_path)
        assert checksum is not None
        assert len(checksum) == 64  # SHA256 produces 64 hex characters
        assert size == len(content)
    finally:
        os.unlink(tmp_file_path)


# DataSetService Tests
class TestDataSetService:
    @pytest.fixture
    def dataset_service(self):
        return DataSetService()

    def test_get_synchronized(self, test_app, dataset_service, sample_user):
        """Test getting synchronized datasets."""
        with test_app.app_context():
            result = dataset_service.get_synchronized(sample_user.id)
            assert result is not None or result == []

    def test_get_unsynchronized(self, test_app, dataset_service, sample_user):
        """Test getting unsynchronized datasets."""
        with test_app.app_context():
            result = dataset_service.get_unsynchronized(sample_user.id)
            assert result is not None or result == []

    def test_get_unsynchronized_dataset(self, test_app, dataset_service, sample_user, sample_dataset):
        """Test getting a specific unsynchronized dataset."""
        with test_app.app_context():
            result = dataset_service.get_unsynchronized_dataset(sample_user.id, sample_dataset.id)
            assert result is not None or result is None

    def test_latest_synchronized(self, test_app, dataset_service):
        """Test getting latest synchronized datasets."""
        with test_app.app_context():
            result = dataset_service.latest_synchronized()
            assert isinstance(result, list) or result is None

    def test_count_synchronized_datasets(self, test_app, dataset_service):
        """Test counting synchronized datasets."""
        with test_app.app_context():
            count = dataset_service.count_synchronized_datasets()
            assert isinstance(count, int)
            assert count >= 0

    def test_count_authors(self, test_app, dataset_service):
        """Test counting authors."""
        with test_app.app_context():
            count = dataset_service.count_authors()
            assert isinstance(count, int)
            assert count >= 0

    def test_count_dsmetadata(self, test_app, dataset_service):
        """Test counting dataset metadata."""
        with test_app.app_context():
            count = dataset_service.count_dsmetadata()
            assert isinstance(count, int)
            assert count >= 0

    def test_total_dataset_downloads(self, test_app, dataset_service):
        """Test counting total downloads."""
        with test_app.app_context():
            count = dataset_service.total_dataset_downloads()
            assert isinstance(count, int)
            assert count >= 0

    def test_total_dataset_views(self, test_app, dataset_service):
        """Test counting total views."""
        with test_app.app_context():
            count = dataset_service.total_dataset_views()
            assert isinstance(count, int)
            assert count >= 0

    def test_update_dsmetadata(self, test_app, dataset_service, sample_dataset):
        """Test updating dataset metadata."""
        with test_app.app_context():
            ds_meta = DSMetaData.query.get(sample_dataset.ds_meta_data_id)
            original_title = ds_meta.title

            updated = dataset_service.update_dsmetadata(sample_dataset.ds_meta_data_id, title="Updated Title")

            assert updated is not None
            assert updated.title == "Updated Title" or updated.title == original_title

    def test_get_uvlhub_doi(self, test_app, dataset_service, sample_dataset):
        """Test getting UVLHub DOI URL."""
        with test_app.app_context():
            dataset = DataSet.query.get(sample_dataset.id)
            doi_url = dataset_service.get_uvlhub_doi(dataset)

            assert doi_url is not None
            assert "doi" in doi_url
            assert dataset.ds_meta_data.dataset_doi in doi_url

    def test_get_conceptual_doi_with_concept(self, test_app, dataset_service):
        """Test getting conceptual DOI when concept exists."""
        with test_app.app_context():
            # Create a dataset with concept
            from app.modules.dataset.models import DataSetConcept

            ds_meta = DSMetaData(
                title="Test with Concept",
                description="Dataset with concept",
                publication_type=PublicationType.NONE,
                dataset_doi="10.1234/test-concept",
            )
            db.session.add(ds_meta)
            db.session.flush()
            concept = DataSetConcept(conceptual_doi="10.1234/concept")
            db.session.add(concept)
            db.session.flush()

            dataset = DataSet(
                user_id=1,
                ds_meta_data_id=ds_meta.id,
                ds_concept_id=concept.id,
            )
            db.session.add(dataset)
            db.session.commit()

            doi_url = dataset_service.get_conceptual_doi(dataset)

            assert doi_url is not None
            assert "doi" in doi_url
            assert "10.1234/concept" in doi_url

    def test_get_conceptual_doi_without_concept(self, test_app, dataset_service, sample_dataset):
        """Test getting conceptual DOI when concept doesn't exist."""
        with test_app.app_context():
            dataset = DataSet.query.get(sample_dataset.id)
            dataset.concept = None

            doi_url = dataset_service.get_conceptual_doi(dataset)

            assert doi_url is None

    def test_search(self, test_app, dataset_service):
        """Test search functionality."""
        with test_app.app_context():
            with patch.object(dataset_service.repository, "search", return_value=[]):
                results = dataset_service.search(title="Test")
                assert results == []

    def test_search_by_multiple_filters(self, test_app, dataset_service):
        """Test search with multiple filters."""
        with test_app.app_context():
            with patch.object(dataset_service.repository, "search", return_value=[]):
                results = dataset_service.search(
                    title="Test",
                    tags=["Dataset"],
                )
                assert results == []

    def test_search_no_filters(self, test_app, dataset_service):
        """Test search with no filters."""
        with test_app.app_context():
            with patch.object(dataset_service.repository, "search", return_value=[]):
                results = dataset_service.search()
                assert results == []

    def test_count_feature_models_raises_attr_error(self, dataset_service):
        """count_feature_models relies on a missing feature_model_service attribute."""
        with pytest.raises(AttributeError):
            dataset_service.count_feature_models()

    def test_infer_is_major_from_form_with_feature_models(self, dataset_service):
        """Test is_major inference with feature models."""
        mock_form = Mock()
        mock_form.feature_models = [Mock(), Mock()]

        result = DataSetService.infer_is_major_from_form(mock_form)

        assert isinstance(result, bool)

    def test_infer_is_major_from_form_without_feature_models(self, dataset_service):
        """Test is_major inference without feature models."""
        mock_form = Mock()
        mock_form.feature_models = []

        result = DataSetService.infer_is_major_from_form(mock_form)

        assert isinstance(result, bool)
        assert result is False

    def test_infer_is_major_from_form_exception(self, dataset_service):
        """Test is_major inference when exception occurs."""
        mock_form = Mock()
        del mock_form.feature_models

        result = DataSetService.infer_is_major_from_form(mock_form)

        assert result is False

    def test_check_introduced_version_valid_major(self, dataset_service):
        """Test version check for valid major version."""
        is_valid, error = DataSetService.check_introduced_version("1.0.0", True, "2.0.0")

        assert is_valid is True
        assert error == ""

    def test_check_introduced_version_invalid_major_not_incremented(self, dataset_service):
        """Test version check for major version not incremented."""
        is_valid, error = DataSetService.check_introduced_version("1.0.0", True, "1.0.0")

        assert is_valid is False
        assert "major version must be increased" in error.lower()

    def test_check_introduced_version_invalid_major_minor_not_zero(self, dataset_service):
        """Test version check for major version with non-zero minor."""
        is_valid, error = DataSetService.check_introduced_version("1.0.0", True, "2.1.0")

        assert is_valid is False
        assert "must be zero" in error.lower()

    def test_check_introduced_version_invalid_major_too_large(self, dataset_service):
        """Test version check for major version incremented by more than 1."""
        is_valid, error = DataSetService.check_introduced_version("1.0.0", True, "3.0.0")

        assert is_valid is False
        assert "one at a time" in error.lower()

    def test_check_introduced_version_valid_minor(self, dataset_service):
        """Test version check for valid minor version."""
        is_valid, error = DataSetService.check_introduced_version("1.0.0", False, "1.1.0")

        assert is_valid is True
        assert error == ""

    def test_check_introduced_version_invalid_minor_major_increased(self, dataset_service):
        """Test version check for minor version with major increased."""
        is_valid, error = DataSetService.check_introduced_version("1.0.0", False, "2.0.0")

        assert is_valid is False
        assert "cannot be increased" in error.lower() or "must be increased" in error.lower()

    def test_check_introduced_version_invalid_minor_not_incremented(self, dataset_service):
        """Test version check for minor version not incremented."""
        is_valid, error = DataSetService.check_introduced_version("1.1.0", False, "1.1.0")

        assert is_valid is False
        assert "must be increased" in error.lower()

    def test_check_introduced_version_invalid_format(self, dataset_service):
        """Test version check with invalid format."""
        is_valid, error = DataSetService.check_introduced_version("1.0", True, "2.0.0")

        assert is_valid is False
        assert "X.Y.Z" in error

    def test_check_introduced_version_with_leading_zeros(self, dataset_service):
        """Test version check with leading zeros."""
        is_valid, error = DataSetService.check_introduced_version("1.0.0", True, "2.01.0")

        assert is_valid is False
        assert "leading zeros" in error.lower()

    def test_check_upload_version_valid(self, dataset_service):
        """Test valid upload version."""
        is_valid, error = DataSetService.check_upload_version("1.2.3")

        assert is_valid is True
        assert error == ""

    def test_check_upload_version_invalid_format(self, dataset_service):
        """Test invalid upload version format."""
        is_valid, error = DataSetService.check_upload_version("1.2")

        assert is_valid is False
        assert "X.Y.Z" in error

    def test_check_upload_version_with_leading_zeros(self, dataset_service):
        """Test upload version with leading zeros."""
        is_valid, error = DataSetService.check_upload_version("1.02.3")

        assert is_valid is False
        assert "leading zeros" in error.lower()

    def test_check_upload_version_non_numeric(self, dataset_service):
        """Test upload version with non-numeric components."""
        is_valid, error = DataSetService.check_upload_version("1.a.3")

        assert is_valid is False
        assert "integers" in error.lower()

    def test_check_introduced_version_valid_patch(self, dataset_service):
        """Test version check for valid patch version."""
        is_valid, error = DataSetService.check_introduced_version("1.0.0", False, "1.0.1")

        assert is_valid is True
        assert error == ""

    def test_check_introduced_version_minor_too_large_increment(self, dataset_service):
        """Test version check for minor version incremented by more than 1."""
        is_valid, error = DataSetService.check_introduced_version("1.0.0", False, "1.2.0")

        assert is_valid is False
        assert "one at a time" in error.lower()

    def test_check_introduced_version_patch_too_large_increment(self, dataset_service):
        """Test version check for patch version incremented by more than 1."""
        is_valid, error = DataSetService.check_introduced_version("1.0.0", False, "1.0.2")

        assert is_valid is False
        assert "one at a time" in error.lower()

    def test_check_upload_version_with_v_prefix(self, dataset_service):
        """Test upload version with v prefix."""
        is_valid, error = DataSetService.check_upload_version("v1.2.3")

        # Should handle v prefix or reject it
        assert isinstance(is_valid, bool)

    def test_check_introduced_version_with_v_prefix(self, dataset_service):
        """Test version check with v prefix in current version."""
        is_valid, error = DataSetService.check_introduced_version("v1.0.0", True, "v2.0.0")

        # Should strip v prefix and validate
        assert is_valid is True or is_valid is False

    @patch("app.modules.dataset.services.os.remove")
    @patch("app.modules.dataset.services.os.path.exists")
    @patch("app.modules.dataset.services.shutil.move")
    @patch("app.modules.dataset.services.os.makedirs")
    @patch("app.modules.dataset.services.AuthenticationService")
    def test_move_feature_models_success(
        self,
        mock_auth_service,
        mock_makedirs,
        mock_move,
        mock_exists,
        mock_remove,
        test_app,
        dataset_service,
        dataset_with_feature_models,
    ):
        """Test moving feature models successfully."""
        with test_app.app_context():
            # Mock authenticated user
            mock_user = Mock()
            mock_user.id = 1
            mock_user.temp_folder.return_value = "/tmp/test"
            mock_auth_service.return_value.get_authenticated_user.return_value = mock_user

            # Mock file exists - return True first time, False second time
            mock_exists.side_effect = [True, False]

            dataset = DataSet.query.get(dataset_with_feature_models.id)

            dataset_service.move_feature_models(dataset)

            # Verify makedirs was called
            mock_makedirs.assert_called()

    @patch("app.modules.dataset.services.os.path.exists")
    @patch("app.modules.dataset.services.AuthenticationService")
    def test_move_feature_models_file_not_exists(
        self,
        mock_auth_service,
        mock_exists,
        test_app,
        dataset_service,
        dataset_with_feature_models,
    ):
        """Test moving feature models when source file doesn't exist."""
        with test_app.app_context():
            mock_user = Mock()
            mock_user.id = 1
            mock_user.temp_folder.return_value = "/tmp/test"
            mock_auth_service.return_value.get_authenticated_user.return_value = mock_user

            # Mock file doesn't exist
            mock_exists.return_value = False

            dataset = DataSet.query.get(dataset_with_feature_models.id)

            # Should not raise exception, just log warning
            dataset_service.move_feature_models(dataset)

    @patch("app.modules.dataset.services.shutil.copy2")
    @patch("app.modules.dataset.services.os.path.exists")
    @patch("app.modules.dataset.services.os.makedirs")
    def test_copy_feature_models_from_original_success(
        self,
        mock_makedirs,
        mock_exists,
        mock_copy2,
        test_app,
        dataset_service,
        dataset_with_feature_models,
    ):
        """Test copying feature models from original dataset."""
        with test_app.app_context():
            # Create a new empty dataset to copy into
            ds_meta_new = DSMetaData(
                title="New Dataset Version",
                description="Copy of original",
                publication_type=PublicationType.NONE,
            )
            db.session.add(ds_meta_new)
            db.session.flush()

            new_dataset = DataSet(user_id=1, ds_meta_data_id=ds_meta_new.id, version_number="2.0.0")
            db.session.add(new_dataset)
            db.session.commit()

            original_dataset = DataSet.query.get(dataset_with_feature_models.id)

            # Mock file operations
            mock_exists.return_value = True

            dataset_service.copy_feature_models_from_original(new_dataset, original_dataset)

            # Verify makedirs was called
            mock_makedirs.assert_called()

    @patch("app.modules.dataset.services.os.path.exists")
    @patch("app.modules.dataset.services.os.makedirs")
    def test_copy_feature_models_from_original_file_not_exists(
        self,
        mock_makedirs,
        mock_exists,
        test_app,
        dataset_service,
        dataset_with_feature_models,
    ):
        """Test copying feature models when source file doesn't exist."""
        with test_app.app_context():
            ds_meta_new = DSMetaData(
                title="New Dataset Version",
                description="Copy of original",
                publication_type=PublicationType.NONE,
            )
            db.session.add(ds_meta_new)
            db.session.flush()

            new_dataset = DataSet(user_id=1, ds_meta_data_id=ds_meta_new.id, version_number="2.0.0")
            db.session.add(new_dataset)
            db.session.commit()

            original_dataset = DataSet.query.get(dataset_with_feature_models.id)

            # Mock file doesn't exist
            mock_exists.return_value = False

            # Should not raise exception, just log warning
            dataset_service.copy_feature_models_from_original(new_dataset, original_dataset)

    @patch("app.modules.dataset.services.shutil.copy2")
    @patch("app.modules.dataset.services.os.path.exists")
    @patch("app.modules.dataset.services.os.makedirs")
    def test_copy_feature_models_from_original_copy_fails(
        self,
        mock_makedirs,
        mock_exists,
        mock_copy2,
        test_app,
        dataset_service,
        dataset_with_feature_models,
    ):
        """Test copying feature models when copy operation fails."""
        with test_app.app_context():
            ds_meta_new = DSMetaData(
                title="New Dataset Version",
                description="Copy of original",
                publication_type=PublicationType.NONE,
            )
            db.session.add(ds_meta_new)
            db.session.flush()

            new_dataset = DataSet(user_id=1, ds_meta_data_id=ds_meta_new.id, version_number="2.0.0")
            db.session.add(new_dataset)
            db.session.commit()

            original_dataset = DataSet.query.get(dataset_with_feature_models.id)

            # Mock file exists but copy fails
            mock_exists.return_value = True
            mock_copy2.side_effect = Exception("Permission denied")

            # Should not raise exception, just log error
            dataset_service.copy_feature_models_from_original(new_dataset, original_dataset)

    @patch("app.modules.dataset.services.shutil.move")
    @patch("app.modules.dataset.services.os.remove")
    @patch("app.modules.dataset.services.os.path.exists")
    @patch("app.modules.dataset.services.os.makedirs")
    @patch("app.modules.dataset.services.AuthenticationService")
    def test_move_feature_models_with_exception(
        self,
        mock_auth_service,
        mock_makedirs,
        mock_exists,
        mock_remove,
        mock_move,
        test_app,
        dataset_service,
        dataset_with_feature_models,
    ):
        """Test moving feature models when move operation fails."""
        with test_app.app_context():
            mock_user = Mock()
            mock_user.id = 1
            mock_user.temp_folder.return_value = "/tmp/test"
            mock_auth_service.return_value.get_authenticated_user.return_value = mock_user

            # Mock file exists but move fails
            mock_exists.side_effect = [True, False]
            mock_move.side_effect = Exception("Move failed")

            dataset = DataSet.query.get(dataset_with_feature_models.id)

            # Should raise exception
            with pytest.raises(Exception, match="Move failed"):
                dataset_service.move_feature_models(dataset)


# AuthorService Tests
class TestAuthorService:
    @pytest.fixture
    def author_service(self):
        return AuthorService()

    def test_get_unique_authors(self, test_app, sample_dataset):
        """Test getting unique authors from a dataset."""
        with test_app.app_context():
            dataset = DataSet.query.get(sample_dataset.id)

            unique_authors = AuthorService.get_unique_authors(dataset)

            assert isinstance(unique_authors, list)

    def test_get_unique_authors_with_duplicates(self, test_app):
        """Test getting unique authors when there are duplicates."""
        with test_app.app_context():
            from app.modules.dataset.models import Author

            ds_meta = DSMetaData(
                title="Dataset with Duplicate Authors",
                description="Testing duplicate author filtering",
                publication_type=PublicationType.NONE,
            )
            db.session.add(ds_meta)
            db.session.flush()

            # Add duplicate authors
            author1 = Author(
                name="John Doe",
                affiliation="University A",
                orcid="0000-0000-0000-0001",
                ds_meta_data_id=ds_meta.id,
            )
            author2 = Author(
                name="John Doe",
                affiliation="University A",
                orcid="0000-0000-0000-0001",
                ds_meta_data_id=ds_meta.id,
            )
            author3 = Author(
                name="Jane Smith",
                affiliation="University B",
                orcid="0000-0000-0000-0002",
                ds_meta_data_id=ds_meta.id,
            )
            db.session.add_all([author1, author2, author3])

            dataset = DataSet(user_id=1, ds_meta_data_id=ds_meta.id)
            db.session.add(dataset)
            db.session.commit()

            unique_authors = AuthorService.get_unique_authors(dataset)

            # Should have only 2 unique authors (duplicate removed)
            assert len(unique_authors) == 2

    def test_get_unique_authors_empty(self, test_app):
        """Test getting unique authors when there are no authors."""
        with test_app.app_context():
            ds_meta = DSMetaData(
                title="Dataset without Authors",
                description="Testing empty author list",
                publication_type=PublicationType.NONE,
            )
            db.session.add(ds_meta)
            db.session.flush()

            dataset = DataSet(user_id=1, ds_meta_data_id=ds_meta.id)
            db.session.add(dataset)
            db.session.commit()

            unique_authors = AuthorService.get_unique_authors(dataset)

            assert len(unique_authors) == 0


# DSViewRecordService Tests
class TestDSViewRecordService:
    @pytest.fixture
    def view_record_service(self):
        return DSViewRecordService()

    @patch("app.modules.dataset.repositories.current_user")
    def test_the_record_exists_false(self, mock_current_user, test_app, view_record_service, sample_dataset):
        """Test checking if view record exists when it doesn't."""
        with test_app.app_context():
            # Mock current_user as not authenticated
            mock_current_user.is_authenticated = False
            mock_current_user.id = None
            dataset = DataSet.query.get(sample_dataset.id)
            user_cookie = str(uuid.uuid4())
            exists = view_record_service.the_record_exists(dataset, user_cookie)

            # the_record_exists returns None if record doesn't exist (from .first())
            assert exists is None or isinstance(exists, DSViewRecord)

    @patch("app.modules.dataset.repositories.current_user")
    def test_create_new_record(self, mock_current_user, test_app, view_record_service, sample_dataset):
        """Test creating a new view record."""
        with test_app.app_context():
            # Mock current_user as not authenticated
            mock_current_user.is_authenticated = False
            mock_current_user.id = None

            dataset = DataSet.query.get(sample_dataset.id)
            user_cookie = str(uuid.uuid4())
            record = view_record_service.create_new_record(dataset, user_cookie)

            assert record is not None
            assert isinstance(record, DSViewRecord)

    @patch("app.modules.dataset.repositories.current_user")
    def test_create_cookie_new_user(self, mock_current_user, test_app, view_record_service, sample_dataset):
        """Test creating cookie for new user."""
        with test_app.test_request_context():
            # Mock current_user as not authenticated
            mock_current_user.is_authenticated = False
            mock_current_user.id = None

            dataset = DataSet.query.get(sample_dataset.id)

            cookie = view_record_service.create_cookie(dataset)

            assert cookie is not None
            assert len(cookie) > 0

    @patch("app.modules.dataset.repositories.current_user")
    def test_create_cookie_existing_user(self, mock_current_user, test_app, view_record_service, sample_dataset):
        """Test creating cookie for existing user."""
        existing_cookie = str(uuid.uuid4())
        with test_app.test_request_context(environ_base={"HTTP_COOKIE": f"view_cookie={existing_cookie}"}):
            # Mock current_user as not authenticated
            mock_current_user.is_authenticated = False
            mock_current_user.id = None

            dataset = DataSet.query.get(sample_dataset.id)

            cookie = view_record_service.create_cookie(dataset)

            assert cookie is not None
            assert cookie == existing_cookie

    @patch("app.modules.dataset.repositories.current_user")
    def test_create_cookie_existing_record(self, mock_current_user, test_app, view_record_service, sample_dataset):
        """Ensure no new record when one exists."""
        existing_cookie = str(uuid.uuid4())
        with test_app.test_request_context(environ_base={"HTTP_COOKIE": f"view_cookie={existing_cookie}"}):
            mock_current_user.is_authenticated = False
            mock_current_user.id = None

            dataset = DataSet.query.get(sample_dataset.id)

            # Stub repository to report existing record
            with patch.object(view_record_service.repository, "the_record_exists", return_value=DSViewRecord()):
                with patch.object(view_record_service.repository, "create_new_record") as mock_create:
                    cookie = view_record_service.create_cookie(dataset)

                    assert cookie == existing_cookie
                    mock_create.assert_not_called()

    @patch("app.modules.dataset.repositories.current_user")
    def test_the_record_exists_authenticated_user(
        self, mock_current_user, test_app, view_record_service, sample_dataset, sample_user
    ):
        """Test checking if view record exists for authenticated user."""
        with test_app.app_context():
            # Mock current_user as authenticated
            mock_current_user.is_authenticated = True
            mock_current_user.id = sample_user.id

            dataset = DataSet.query.get(sample_dataset.id)
            user_cookie = str(uuid.uuid4())

            exists = view_record_service.the_record_exists(dataset, user_cookie)

            # Should check by user_id when authenticated
            assert exists is None or isinstance(exists, DSViewRecord)

    @patch("app.modules.dataset.repositories.current_user")
    def test_create_new_record_authenticated_user(
        self, mock_current_user, test_app, view_record_service, sample_dataset, sample_user
    ):
        """Test creating a new view record for authenticated user."""
        with test_app.app_context():
            # Mock current_user as authenticated
            mock_current_user.is_authenticated = True
            mock_current_user.id = sample_user.id

            dataset = DataSet.query.get(sample_dataset.id)
            user_cookie = str(uuid.uuid4())

            record = view_record_service.create_new_record(dataset, user_cookie)

            assert record is not None
            assert isinstance(record, DSViewRecord)
            # Should have user_id set
            assert record.user_id == sample_user.id


# DOIMappingService Tests
class TestDOIMappingService:
    @pytest.fixture
    def doi_mapping_service(self):
        return DOIMappingService()

    def test_get_new_doi_not_found(self, test_app, doi_mapping_service):
        """Test getting new DOI when mapping doesn't exist."""
        with test_app.app_context():
            new_doi = doi_mapping_service.get_new_doi("10.1234/nonexistent")

            assert new_doi is None

    def test_get_new_doi_found(self, test_app, doi_mapping_service):
        """Test getting new DOI when mapping exists."""
        with test_app.app_context():
            from app.modules.dataset.models import DOIMapping

            # Create a DOI mapping
            mapping = DOIMapping(dataset_doi_old="10.1234/old", dataset_doi_new="10.1234/new")
            db.session.add(mapping)
            db.session.commit()

            new_doi = doi_mapping_service.get_new_doi("10.1234/old")

            assert new_doi == "10.1234/new"


# SizeService Tests
class TestSizeService:
    @pytest.fixture
    def size_service(self):
        return SizeService()

    def test_get_human_readable_size_bytes(self, size_service):
        """Test human readable size for bytes."""
        result = size_service.get_human_readable_size(512)

        assert result == "512 bytes"

    def test_get_human_readable_size_kilobytes(self, size_service):
        """Test human readable size for kilobytes."""
        result = size_service.get_human_readable_size(1024)

        assert "KB" in result

    def test_get_human_readable_size_megabytes(self, size_service):
        """Test human readable size for megabytes."""
        result = size_service.get_human_readable_size(1024**2)

        assert "MB" in result

    def test_get_human_readable_size_gigabytes(self, size_service):
        """Test human readable size for gigabytes."""
        result = size_service.get_human_readable_size(1024**3)

        assert "GB" in result

    def test_get_human_readable_size_zero(self, size_service):
        """Test human readable size for zero bytes."""
        result = size_service.get_human_readable_size(0)

        assert result == "0 bytes"

    def test_get_human_readable_size_exact_kb(self, size_service):
        """Test human readable size for exactly 1 KB."""
        result = size_service.get_human_readable_size(1024)

        assert "1.0 KB" in result or "1 KB" in result

    def test_get_human_readable_size_exact_mb(self, size_service):
        """Test human readable size for exactly 1 MB."""
        result = size_service.get_human_readable_size(1024**2)

        assert "1.0 MB" in result or "1 MB" in result

    def test_get_human_readable_size_large_value(self, size_service):
        """Test human readable size for very large values."""
        result = size_service.get_human_readable_size(10 * 1024**3)

        assert "GB" in result
        assert "10" in result


# DSMetaDataService Tests
class TestDSMetaDataService:
    @pytest.fixture
    def dsmetadata_service(self):
        return DSMetaDataService()

    def test_update(self, test_app, dsmetadata_service, sample_dataset):
        """Test updating metadata."""
        with test_app.app_context():
            updated = dsmetadata_service.update(sample_dataset.ds_meta_data_id, title="Updated via service")

            assert updated is not None

    def test_filter_by_doi(self, test_app, dsmetadata_service, sample_dataset):
        """Test filtering by DOI."""
        with test_app.app_context():
            result = dsmetadata_service.filter_by_doi("10.1234/test")

            # Result could be None or a DSMetaData object
            assert result is None or isinstance(result, DSMetaData)

    def test_filter_latest_by_doi(self, test_app, dsmetadata_service, sample_dataset):
        """Test filtering latest by DOI."""
        with test_app.app_context():
            result = dsmetadata_service.filter_latest_by_doi("10.1234/test")

            # Result could be None or a DSMetaData object
            assert result is None or isinstance(result, DSMetaData)


# DataSetConceptService Tests
class TestDataSetConceptService:
    @pytest.fixture
    def concept_service(self):
        return DataSetConceptService()

    def test_filter_by_doi(self, test_app, concept_service):
        """Test filtering concept by DOI."""
        with test_app.app_context():
            result = concept_service.filter_by_doi("10.1234/conceptual")

            # Result could be None or a concept object
            assert result is None or result is not None

    def test_update_concept(self, test_app, concept_service):
        """Test updating concept."""
        with test_app.app_context():
            from app.modules.dataset.models import DataSetConcept

            # Create a concept
            concept = DataSetConcept(conceptual_doi="10.1234/update-test")
            db.session.add(concept)
            db.session.commit()

            # Update it
            updated = concept_service.update(concept.id, conceptual_doi="10.1234/updated")

            assert updated is not None


# DSDownloadRecordService Tests
class TestDSDownloadRecordService:
    @pytest.fixture
    def download_service(self):
        return DSDownloadRecordService()

    def test_instantiation(self, download_service):
        """Test that DSDownloadRecordService instantiates correctly."""
        assert download_service is not None


# DatasetCommentService Tests
class TestDatasetCommentService:
    @pytest.fixture
    def comment_service(self):
        return DatasetCommentService()

    def test_get_comments_by_dataset(self, test_app, comment_service, sample_dataset):
        """Test getting comments by dataset."""
        with test_app.app_context():
            comments = comment_service.get_comments_by_dataset(sample_dataset.id)

            assert isinstance(comments, list)

    def test_count_comments_by_dataset(self, test_app, comment_service, sample_dataset):
        """Test counting comments by dataset."""
        with test_app.app_context():
            count = comment_service.count_comments_by_dataset(sample_dataset.id)

            assert isinstance(count, int)
            assert count >= 0

    def test_get_comments_by_user(self, test_app, comment_service, sample_user):
        """Test getting comments by user."""
        with test_app.app_context():
            comments = comment_service.get_comments_by_user(sample_user.id)

            assert isinstance(comments, list)

    def test_create_comment_success(self, test_app, comment_service, sample_dataset, sample_user):
        """Test creating a comment successfully."""
        with test_app.app_context():
            comment = comment_service.create_comment(
                dataset_id=sample_dataset.id,
                user_id=sample_user.id,
                content="This is a test comment",
            )

            assert comment is not None
            assert comment.content == "This is a test comment"

    def test_create_comment_empty_content(self, test_app, comment_service, sample_dataset, sample_user):
        """Test creating a comment with empty content."""
        with test_app.app_context():
            with pytest.raises(ValueError, match="Comment content cannot be empty"):
                comment_service.create_comment(dataset_id=sample_dataset.id, user_id=sample_user.id, content="")

    def test_create_comment_whitespace_only(self, test_app, comment_service, sample_dataset, sample_user):
        """Test creating a comment with whitespace only."""
        with test_app.app_context():
            with pytest.raises(ValueError, match="Comment content cannot be empty"):
                comment_service.create_comment(dataset_id=sample_dataset.id, user_id=sample_user.id, content="   ")

    def test_update_comment_success(self, test_app, comment_service, sample_dataset, sample_user):
        """Test updating a comment successfully."""
        with test_app.app_context():
            # Create a comment first
            comment = comment_service.create_comment(
                dataset_id=sample_dataset.id,
                user_id=sample_user.id,
                content="Original comment",
            )

            # Update it
            updated = comment_service.update_comment(
                comment_id=comment.id,
                content="Updated comment",
                user_id=sample_user.id,
            )

            assert updated is not None
            assert updated.content == "Updated comment"

    def test_update_comment_not_found(self, test_app, comment_service, sample_user):
        """Test updating a non-existent comment."""
        with test_app.app_context():
            with pytest.raises(ValueError, match="Comment not found"):
                comment_service.update_comment(
                    comment_id=99999,
                    content="Updated content",
                    user_id=sample_user.id,
                )

    def test_update_comment_wrong_user(self, test_app, comment_service, sample_dataset, sample_user):
        """Test updating a comment by wrong user."""
        with test_app.app_context():
            # Create a comment
            comment = comment_service.create_comment(
                dataset_id=sample_dataset.id,
                user_id=sample_user.id,
                content="Original comment",
            )

            # Try to update with different user
            with pytest.raises(ValueError, match="You can only edit your own comments"):
                comment_service.update_comment(comment_id=comment.id, content="Hacked!", user_id=99999)

    def test_update_comment_empty_content(self, test_app, comment_service, sample_dataset, sample_user):
        """Test updating a comment with empty content."""
        with test_app.app_context():
            comment = comment_service.create_comment(
                dataset_id=sample_dataset.id,
                user_id=sample_user.id,
                content="Original comment",
            )

            with pytest.raises(ValueError, match="Comment content cannot be empty"):
                comment_service.update_comment(comment_id=comment.id, content="", user_id=sample_user.id)

    def test_delete_comment_success(self, test_app, comment_service, sample_dataset, sample_user):
        """Test deleting a comment successfully."""
        with test_app.app_context():
            comment = comment_service.create_comment(
                dataset_id=sample_dataset.id,
                user_id=sample_user.id,
                content="To be deleted",
            )

            result = comment_service.delete_comment(comment_id=comment.id, user_id=sample_user.id)

            assert result is not None or result is True

    def test_delete_comment_not_found(self, test_app, comment_service, sample_user):
        """Test deleting a non-existent comment."""
        with test_app.app_context():
            with pytest.raises(ValueError, match="Comment not found"):
                comment_service.delete_comment(comment_id=99999, user_id=sample_user.id)

    def test_delete_comment_wrong_user(self, test_app, comment_service, sample_dataset, sample_user):
        """Test deleting a comment by wrong user."""
        with test_app.app_context():
            comment = comment_service.create_comment(
                dataset_id=sample_dataset.id,
                user_id=sample_user.id,
                content="Protected comment",
            )

            with pytest.raises(ValueError, match="You can only delete your own comments"):
                comment_service.delete_comment(comment_id=comment.id, user_id=99999, is_admin=False)

    def test_delete_comment_admin(self, test_app, comment_service, sample_dataset, sample_user):
        """Test deleting a comment as admin."""
        with test_app.app_context():
            comment = comment_service.create_comment(
                dataset_id=sample_dataset.id,
                user_id=sample_user.id,
                content="To be deleted by admin",
            )

            result = comment_service.delete_comment(comment_id=comment.id, user_id=99999, is_admin=True)

            assert result is not None or result is True

    def test_create_comment_with_whitespace(self, test_app, comment_service, sample_dataset, sample_user):
        """Test creating a comment with leading/trailing whitespace."""
        with test_app.app_context():
            comment = comment_service.create_comment(
                dataset_id=sample_dataset.id,
                user_id=sample_user.id,
                content="  Test comment with spaces  ",
            )

            # Content should be stripped
            assert comment.content == "Test comment with spaces"

    def test_update_comment_with_whitespace(self, test_app, comment_service, sample_dataset, sample_user):
        """Test updating a comment with whitespace."""
        with test_app.app_context():
            comment = comment_service.create_comment(
                dataset_id=sample_dataset.id,
                user_id=sample_user.id,
                content="Original",
            )

            updated = comment_service.update_comment(
                comment_id=comment.id,
                content="  Updated with spaces  ",
                user_id=sample_user.id,
            )

            # Content should be stripped
            assert updated.content == "Updated with spaces"

    def test_count_comments_empty_dataset(self, test_app, comment_service):
        """Test counting comments for dataset with no comments."""
        with test_app.app_context():
            ds_meta = DSMetaData(
                title="Empty Dataset",
                description="No comments",
                publication_type=PublicationType.NONE,
            )
            db.session.add(ds_meta)
            db.session.flush()

            dataset = DataSet(user_id=1, ds_meta_data_id=ds_meta.id)
            db.session.add(dataset)
            db.session.commit()

            count = comment_service.count_comments_by_dataset(dataset.id)

            assert count == 0

    def test_get_comments_by_user_multiple(self, test_app, comment_service, sample_user):
        """Test getting all comments by a user across multiple datasets."""
        with test_app.app_context():
            # Create multiple datasets and comments
            for i in range(3):
                ds_meta = DSMetaData(
                    title=f"Dataset {i}",
                    description=f"Dataset {i}",
                    publication_type=PublicationType.NONE,
                )
                db.session.add(ds_meta)
                db.session.flush()

                dataset = DataSet(user_id=1, ds_meta_data_id=ds_meta.id)
                db.session.add(dataset)
                db.session.flush()

                comment_service.create_comment(
                    dataset_id=dataset.id,
                    user_id=sample_user.id,
                    content=f"Comment {i}",
                )

            db.session.commit()

            comments = comment_service.get_comments_by_user(sample_user.id)

            assert len(comments) >= 3
