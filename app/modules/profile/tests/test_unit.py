import pytest

from app import db
from app.modules.auth.models import User
from app.modules.conftest import login, logout
from app.modules.dataset.models import DataSet, DSMetaData, PublicationType
from app.modules.profile.models import UserProfile


@pytest.fixture(scope="module")
def test_client(test_client):
    """
    Extends the test_client fixture to add additional specific data for module testing.
    for module testing (por example, new users)
    """
    with test_client.application.app_context():
        user_test = User(email="user@example.com", password="test1234")
        db.session.add(user_test)
        db.session.commit()

        profile = UserProfile(user_id=user_test.id, name="Name", surname="Surname")
        db.session.add(profile)
        db.session.commit()

        # Create a second user for testing public profile view
        user_public = User(email="public@example.com", password="test1234")
        db.session.add(user_public)
        db.session.commit()

        profile_public = UserProfile(user_id=user_public.id, name="PublicName", surname="PublicSurname")
        db.session.add(profile_public)
        db.session.commit()

        # Create a dataset for the public user
        ds_meta = DSMetaData(title="Test Dataset", description="A test dataset", publication_type=PublicationType.OTHER)
        db.session.add(ds_meta)
        db.session.commit()

        dataset = DataSet(user_id=user_public.id, ds_meta_data_id=ds_meta.id, dataset_type="uvl")
        db.session.add(dataset)
        db.session.commit()

    yield test_client


def test_edit_profile_page_get(test_client):
    """
    Tests access to the profile editing page via a GET request.
    """
    login_response = login(test_client, "user@example.com", "test1234")
    assert login_response.status_code == 200, "Login was unsuccessful."

    response = test_client.get("/profile/edit")
    assert response.status_code == 200, "The profile editing page could not be accessed."
    assert b"Edit profile" in response.data, "The expected content is not present on the page"

    logout(test_client)


def test_view_public_profile(test_client):
    """
    Tests viewing a public user's profile with their datasets.
    """
    with test_client.application.app_context():
        public_user = db.session.query(User).filter_by(email="public@example.com").first()
        assert public_user is not None, "Public user not found in database"

    response = test_client.get(f"/profile/{public_user.id}")
    assert response.status_code == 200, "Could not access public profile page"
    assert b"PublicName" in response.data, "User profile name not found on page"
    assert b"PublicSurname" in response.data, "User profile surname not found on page"
    assert b"Test Dataset" in response.data, "User's dataset not found on profile page"
    assert b"User datasets" in response.data, "User datasets section not found"


def test_view_nonexistent_profile(test_client):
    """
    Tests that accessing a non-existent user profile redirects.
    """
    response = test_client.get("/profile/99999", follow_redirects=False)
    assert response.status_code == 302, "Expected redirect for non-existent user"


def test_my_profile_page_get(test_client):
    """
    Tests that authenticated user can view their own profile.
    """
    login_response = login(test_client, "user@example.com", "test1234")
    assert login_response.status_code == 200, "Login was unsuccessful."

    response = test_client.get("/profile/summary")
    assert response.status_code == 200, "Could not access my profile page"
    assert b"Name" in response.data, "User profile name not found on page"
    assert b"Surname" in response.data, "User profile surname not found on page"
    assert b"Manage Active Sessions" in response.data, "Owner should see manage sessions button"

    logout(test_client)


def test_manage_sessions_hidden_on_other_profile_when_authenticated(test_client):
    """
    Ensure the manage sessions button is hidden when viewing another user's profile while logged in.
    """
    login_response = login(test_client, "user@example.com", "test1234")
    assert login_response.status_code == 200, "Login was unsuccessful."

    with test_client.application.app_context():
        public_user = db.session.query(User).filter_by(email="public@example.com").first()
        assert public_user is not None, "Public user not found in database"

    response = test_client.get(f"/profile/{public_user.id}")
    assert response.status_code == 200, "Could not access other user's profile"
    assert b"Manage Active Sessions" not in response.data, "Button should not be visible on other user's profile"

    logout(test_client)
