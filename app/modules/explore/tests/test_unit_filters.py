"""
Tests for advanced dataset search using the ExploreRepository.

These tests validate that the ExploreRepository.filter() method correctly applies
all supported filters: query (title/description), author, publication type, tags,
date ranges, and combinations thereof.

The tests use unique identifiers in titles and tags to ensure test isolation
and avoid side effects from existing database seeds.
"""

from datetime import datetime, timedelta

import pytest
from werkzeug.security import generate_password_hash

from app import db
from app.modules.auth.models import User
from app.modules.dataset.models import Author, DataSet, DSMetaData, PublicationType
from app.modules.explore.repositories import ExploreRepository


@pytest.fixture
def test_user(test_client):
    """Fixture that returns or creates a test user for dataset ownership."""
    user = User.query.filter_by(email="test_explore@example.com").first()
    if not user:
        user = User(
            email="test_explore@example.com",
            password=generate_password_hash("test_password_123"),
            twofa_enabled=False,
        )
        db.session.add(user)
        db.session.commit()
    return user


def _create_dataset_with_authors(
    user,
    title,
    description="Test dataset",
    tags_str="",
    publication_type=PublicationType.OTHER,
    created_at=None,
    authors_data=None,
):
    """
    Create a dataset with metadata, tags, and optional author records.

    Parameters
    ----------
    user : User
        The owner of the dataset.
    title : str
        The title of the dataset.
    description : str
        The description of the dataset.
    tags_str : str
        Comma-separated tags (e.g., "tag1, tag2").
    publication_type : PublicationType
        The publication type enum.
    created_at : datetime, optional
        Creation timestamp. If None, uses datetime.utcnow().
    authors_data : list of dict, optional
        List of author dictionaries with keys: name, affiliation, orcid.
        Example: [{"name": "John Doe", "affiliation": "MIT", "orcid": "1234-5678"}]

    Returns
    -------
    DataSet
        The created dataset object.
    """
    meta = DSMetaData(
        title=title,
        description=description,
        publication_type=publication_type,
        publication_doi="10.1234/test-doi",
        dataset_doi=None,
        tags=tags_str,
        ds_metrics_id=None,
    )
    db.session.add(meta)
    db.session.flush()

    if authors_data:
        for author_info in authors_data:
            author = Author(
                name=author_info.get("name"),
                affiliation=author_info.get("affiliation"),
                orcid=author_info.get("orcid"),
                ds_meta_data_id=meta.id,
            )
            db.session.add(author)

    dataset = DataSet(
        user_id=user.id,
        ds_meta_data_id=meta.id,
        created_at=created_at or datetime.utcnow(),
    )
    db.session.add(dataset)
    db.session.commit()
    return dataset


# ===== Test: Filter by Query (Title) =====


def test_search_filter_by_query_in_title(test_client, test_user):
    """Filter should return only datasets whose title contains the query string (case-insensitive)."""
    repo = ExploreRepository()

    unique_token = "query_title_test_xyz123"
    ds_matching = _create_dataset_with_authors(
        user=test_user,
        title=f"Security Analysis {unique_token}",
        description="A dataset about security",
        tags_str="analysis",
    )
    ds_not_matching = _create_dataset_with_authors(
        user=test_user,
        title=f"Weather Data {unique_token}",
        description="A dataset about weather",
        tags_str="climate",
    )

    results = repo.filter(query="security")
    result_ids = [d.id for d in results]

    assert ds_matching.id in result_ids, "Dataset with 'security' in title should be in results"
    assert ds_not_matching.id not in result_ids, "Dataset without 'security' should not be in results"

    for dataset in results:
        title_lower = dataset.ds_meta_data.title.lower()
        desc_lower = dataset.ds_meta_data.description.lower()
        assert "security" in title_lower or "security" in desc_lower


def test_search_filter_by_query_in_description(test_client, test_user):
    """Filter should return datasets whose description (not just title) contains the query string."""
    repo = ExploreRepository()

    unique_token = "query_desc_test_abc456"
    ds_matching = _create_dataset_with_authors(
        user=test_user,
        title=f"Weather Data {unique_token}",
        description="This dataset contains security protocols for data transmission",
        tags_str="weather",
    )
    ds_not_matching = _create_dataset_with_authors(
        user=test_user,
        title=f"Climate Analysis {unique_token}",
        description="Historical climate records",
        tags_str="climate",
    )

    results = repo.filter(query="security")
    result_ids = [d.id for d in results]

    assert ds_matching.id in result_ids, "Dataset with 'security' in description should be in results"
    assert ds_not_matching.id not in result_ids, "Dataset without 'security' should not be in results"


# ===== Test: Filter by Author =====


def test_search_filter_by_author(test_client, test_user):
    """Filter should return only datasets authored by the specified author."""
    repo = ExploreRepository()

    unique_token = "author_test_xyz789"
    author_name = f"Dr. Alice Smith {unique_token}"

    ds_by_alice = _create_dataset_with_authors(
        user=test_user,
        title=f"Ocean Dataset {unique_token}",
        tags_str="ocean,data",
        authors_data=[{"name": author_name, "affiliation": "MIT", "orcid": "1234-5678"}],
    )

    ds_by_bob = _create_dataset_with_authors(
        user=test_user,
        title=f"Land Dataset {unique_token}",
        tags_str="land,data",
        authors_data=[{"name": "Dr. Bob Johnson", "affiliation": "Stanford", "orcid": "9876-5432"}],
    )

    results = repo.filter(query=author_name)
    result_ids = [d.id for d in results]

    assert ds_by_alice.id in result_ids, "Dataset authored by Alice should be in results"
    assert ds_by_bob.id not in result_ids, "Dataset authored by Bob should not be in results"


# ===== Test: Filter by Tags =====


def test_search_filter_by_single_tag(test_client, test_user):
    """Filter should return only datasets containing the specified tag."""
    repo = ExploreRepository()

    unique_tag = "climate_tag_test_def123"

    ds_with_tag = _create_dataset_with_authors(
        user=test_user,
        title="Climate Dataset",
        tags_str=f"weather, {unique_tag}, precipitation",
    )
    ds_without_tag = _create_dataset_with_authors(
        user=test_user,
        title="Ocean Dataset",
        tags_str="water, salinity, temperature",
    )

    results = repo.filter(tags=[unique_tag])
    result_ids = [d.id for d in results]

    assert ds_with_tag.id in result_ids, "Dataset with matching tag should be in results"
    assert ds_without_tag.id not in result_ids, "Dataset without matching tag should not be in results"


def test_search_filter_by_multiple_tags(test_client, test_user):
    """Filter with multiple tags should return datasets containing ALL specified tags (AND logic)."""
    repo = ExploreRepository()

    unique_token = "multi_tag_test_ghi456"
    tag1 = f"weather_{unique_token}"
    tag2 = f"climate_{unique_token}"

    ds_both_tags = _create_dataset_with_authors(
        user=test_user,
        title="Complete Dataset",
        tags_str=f"{tag1}, {tag2}, other",
    )
    ds_one_tag = _create_dataset_with_authors(
        user=test_user,
        title="Partial Dataset",
        tags_str=f"{tag1}, partial",
    )
    ds_no_tags = _create_dataset_with_authors(
        user=test_user,
        title="Different Dataset",
        tags_str="unrelated, tags",
    )

    results = repo.filter(tags=[tag1, tag2])
    result_ids = [d.id for d in results]

    assert ds_both_tags.id in result_ids, "Dataset with both tags should be in results"
    assert ds_one_tag.id not in result_ids, "Dataset with only one tag should not be in results"
    assert ds_no_tags.id not in result_ids, "Dataset with neither tag should not be in results"


# ===== Test: Filter by Publication Type =====


def test_search_filter_by_publication_type(test_client, test_user):
    """Filter should return only datasets of the specified publication type."""
    repo = ExploreRepository()

    unique_token = "pubtype_test_jkl789"

    ds_national = _create_dataset_with_authors(
        user=test_user,
        title=f"National Dataset {unique_token}",
        publication_type=PublicationType.NATIONAL,
    )
    ds_continental = _create_dataset_with_authors(
        user=test_user,
        title=f"Continental Dataset {unique_token}",
        publication_type=PublicationType.CONTINENTAL,
    )

    results = repo.filter(publication_type="national")
    result_ids = [d.id for d in results]

    assert ds_national.id in result_ids, "Dataset with NATIONAL type should be in results"
    assert ds_continental.id not in result_ids, "Dataset with CONTINENTAL type should not be in results"


# ===== Test: Filter by Date Range =====


def test_search_filter_by_date_range(test_client, test_user):
    """Filter should respect start_date and end_date boundaries."""
    repo = ExploreRepository()

    now = datetime.utcnow()

    ds_recent = _create_dataset_with_authors(
        user=test_user,
        title="Recent Dataset",
        tags_str="recent",
        created_at=now - timedelta(days=1),
    )
    ds_old = _create_dataset_with_authors(
        user=test_user,
        title="Old Dataset",
        tags_str="old",
        created_at=now - timedelta(days=30),
    )

    start_date = now - timedelta(days=5)
    end_date = now

    results = repo.filter(start_date=start_date.strftime("%Y-%m-%d"), end_date=end_date.strftime("%Y-%m-%d"))
    result_ids = [d.id for d in results]

    assert ds_recent.id in result_ids, "Recent dataset should be within date range"
    assert ds_old.id not in result_ids, "Old dataset should be outside date range"


def test_search_filter_by_start_date_only(test_client, test_user):
    """Filter with only start_date should return datasets from that date onwards."""
    repo = ExploreRepository()

    now = datetime.utcnow()

    ds_after = _create_dataset_with_authors(
        user=test_user,
        title="Dataset After",
        created_at=now - timedelta(days=2),
    )
    ds_before = _create_dataset_with_authors(
        user=test_user,
        title="Dataset Before",
        created_at=now - timedelta(days=10),
    )

    start_date = now - timedelta(days=5)
    results = repo.filter(start_date=start_date.strftime("%Y-%m-%d"))
    result_ids = [d.id for d in results]

    assert ds_after.id in result_ids, "Dataset after start_date should be in results"
    assert ds_before.id not in result_ids, "Dataset before start_date should not be in results"


# ===== Test: Combined Filters =====


def test_search_combined_query_and_tags(test_client, test_user):
    """Filter with both query and tags should return datasets matching ALL conditions (AND logic)."""
    repo = ExploreRepository()

    unique_token = "combined_query_tags_mno123"
    unique_tag = f"climate_{unique_token}"

    ds_matching = _create_dataset_with_authors(
        user=test_user,
        title=f"Security and Climate {unique_token}",
        description="Important security protocols for climate data",
        tags_str=f"{unique_tag}, data",
    )
    ds_query_only = _create_dataset_with_authors(
        user=test_user,
        title=f"Security Info {unique_token}",
        tags_str="network, protocols",
    )
    ds_tags_only = _create_dataset_with_authors(
        user=test_user,
        title=f"Weather Data {unique_token}",
        tags_str=f"{unique_tag}, temperature",
    )

    results = repo.filter(query="security", tags=[unique_tag])
    result_ids = [d.id for d in results]

    assert ds_matching.id in result_ids, "Dataset matching both query AND tags should be in results"
    assert ds_query_only.id not in result_ids, "Dataset matching only query should not be in results"
    assert ds_tags_only.id not in result_ids, "Dataset matching only tags should not be in results"


def test_search_combined_query_publication_type_and_date_range(test_client, test_user):
    """Filter with query, publication type, and date range should apply all conditions."""
    repo = ExploreRepository()

    unique_token = "combined_all_pqr456"
    now = datetime.utcnow()

    ds_matching = _create_dataset_with_authors(
        user=test_user,
        title=f"Security Report {unique_token}",
        description="National security analysis",
        publication_type=PublicationType.NATIONAL,
        created_at=now - timedelta(days=2),
    )
    ds_wrong_type = _create_dataset_with_authors(
        user=test_user,
        title=f"Security Report {unique_token}",
        description="Regional security analysis",
        publication_type=PublicationType.REGIONAL,
        created_at=now - timedelta(days=2),
    )
    ds_wrong_date = _create_dataset_with_authors(
        user=test_user,
        title=f"Security Report {unique_token}",
        description="Old national security",
        publication_type=PublicationType.NATIONAL,
        created_at=now - timedelta(days=30),
    )

    start_date = now - timedelta(days=5)
    end_date = now

    results = repo.filter(
        query="security",
        publication_type="national",
        start_date=start_date.strftime("%Y-%m-%d"),
        end_date=end_date.strftime("%Y-%m-%d"),
    )
    result_ids = [d.id for d in results]

    assert ds_matching.id in result_ids, "Dataset matching all conditions should be in results"
    assert ds_wrong_type.id not in result_ids, "Dataset with wrong type should not be in results"
    assert ds_wrong_date.id not in result_ids, "Dataset outside date range should not be in results"


# ===== Test: No Filters Returns All =====


def test_search_no_filters_returns_all_datasets(test_client, test_user):
    """Filter with no parameters should return all datasets."""
    repo = ExploreRepository()

    unique_token = "no_filter_test_stu789"

    ds1 = _create_dataset_with_authors(
        user=test_user,
        title=f"Dataset A {unique_token}",
        tags_str="tag_a",
    )
    ds2 = _create_dataset_with_authors(
        user=test_user,
        title=f"Dataset B {unique_token}",
        tags_str="tag_b",
    )
    ds3 = _create_dataset_with_authors(
        user=test_user,
        title=f"Dataset C {unique_token}",
        tags_str="tag_c",
    )

    results = repo.filter()
    result_ids = [d.id for d in results]

    assert ds1.id in result_ids, "Dataset 1 should be in results"
    assert ds2.id in result_ids, "Dataset 2 should be in results"
    assert ds3.id in result_ids, "Dataset 3 should be in results"


# ===== Test: Invalid/Empty Filter Values =====


def test_search_empty_query_string(test_client, test_user):
    """Filter with empty query string should not break and should return results."""
    repo = ExploreRepository()

    _create_dataset_with_authors(
        user=test_user,
        title="Test Dataset",
        tags_str="test",
    )

    results = repo.filter(query="")
    assert isinstance(results, list), "Results should be a list"


def test_search_empty_tags_list(test_client, test_user):
    """Filter with empty tags list should not break and should return results."""
    repo = ExploreRepository()

    _create_dataset_with_authors(
        user=test_user,
        title="Test Dataset",
        tags_str="test",
    )

    results = repo.filter(tags=[])
    assert isinstance(results, list), "Results should be a list"


def test_search_empty_tags_none(test_client, test_user):
    """Filter with tags=None should not break and should return results."""
    repo = ExploreRepository()

    _create_dataset_with_authors(
        user=test_user,
        title="Test Dataset",
        tags_str="test",
    )

    results = repo.filter(tags=None)
    assert isinstance(results, list), "Results should be a list"


def test_search_invalid_publication_type(test_client, test_user):
    """Filter with invalid publication type should return no results or all results based on implementation."""
    repo = ExploreRepository()

    _create_dataset_with_authors(
        user=test_user,
        title="Test Dataset",
        publication_type=PublicationType.NATIONAL,
    )

    results = repo.filter(publication_type="invalid_type_xyz")
    assert isinstance(results, list), "Results should be a list"


def test_search_invalid_date_format(test_client, test_user):
    """Filter with invalid date format should not break; invalid dates should be ignored."""
    repo = ExploreRepository()

    _create_dataset_with_authors(
        user=test_user,
        title="Test Dataset",
        created_at=datetime.utcnow(),
    )

    results = repo.filter(start_date="not-a-date", end_date="also-invalid")
    assert isinstance(results, list), "Results should be a list"


# ===== Test: Ordering =====


def test_search_results_ordered_by_newest_first(test_client, test_user):
    """Results should be ordered by creation date, newest first."""
    repo = ExploreRepository()

    now = datetime.utcnow()

    _create_dataset_with_authors(
        user=test_user,
        title="Oldest Dataset",
        created_at=now - timedelta(days=10),
    )
    _create_dataset_with_authors(
        user=test_user,
        title="Middle Dataset",
        created_at=now - timedelta(days=5),
    )
    _create_dataset_with_authors(
        user=test_user,
        title="Newest Dataset",
        created_at=now - timedelta(days=1),
    )

    results = repo.filter(sorting="newest")

    result_dates = [d.created_at for d in results]
    assert result_dates == sorted(result_dates, reverse=True), "Results should be ordered newest first"


def test_search_results_ordered_by_oldest_first(test_client, test_user):
    """Results should respect 'oldest' sorting."""
    repo = ExploreRepository()

    now = datetime.utcnow()

    _create_dataset_with_authors(
        user=test_user,
        title="Oldest Dataset",
        created_at=now - timedelta(days=10),
    )
    _create_dataset_with_authors(
        user=test_user,
        title="Newest Dataset",
        created_at=now - timedelta(days=1),
    )

    results = repo.filter(sorting="oldest")
    result_dates = [d.created_at for d in results]
    assert result_dates == sorted(result_dates), "Results should be ordered oldest first"
