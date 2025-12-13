import pytest
from flask import url_for

from app.modules.auth.repositories import UserRepository
from app.modules.auth.services import AuthenticationService
from app.modules.profile.repositories import UserProfileRepository


@pytest.fixture(scope="module")
def test_client(test_client):
    """
    Extends the test_client fixture to add additional specific data for module testing.
    """
    with test_client.application.app_context():
        # Add HERE new elements to the database that you want to exist in the test context.
        # DO NOT FORGET to use db.session.add(<element>) and db.session.commit() to save the data.
        pass

    yield test_client


def test_login_success(test_client):
    response = test_client.post(
        "/login", data=dict(email="test@example.com", password="test1234"), follow_redirects=True
    )

    assert response.request.path != url_for("auth.login"), "Login was unsuccessful"

    test_client.get("/logout", follow_redirects=True)


def test_login_unsuccessful_bad_email(test_client):
    response = test_client.post(
        "/login", data=dict(email="bademail@example.com", password="test1234"), follow_redirects=True
    )

    assert response.request.path == url_for("auth.login"), "Login was unsuccessful"

    test_client.get("/logout", follow_redirects=True)


def test_login_unsuccessful_bad_password(test_client):
    response = test_client.post(
        "/login", data=dict(email="test@example.com", password="basspassword"), follow_redirects=True
    )

    assert response.request.path == url_for("auth.login"), "Login was unsuccessful"

    test_client.get("/logout", follow_redirects=True)


def test_signup_user_no_name(test_client):
    response = test_client.post(
        "/signup", data=dict(surname="Foo", email="test@example.com", password="test1234"), follow_redirects=True
    )
    assert response.request.path == url_for("auth.show_signup_form"), "Signup was unsuccessful"
    assert b"This field is required" in response.data, response.data


def test_signup_user_unsuccessful(test_client):
    email = "test@example.com"
    response = test_client.post(
        "/signup", data=dict(name="Test", surname="Foo", email=email, password="test1234"), follow_redirects=True
    )
    assert response.request.path == url_for("auth.show_signup_form"), "Signup was unsuccessful"
    assert f"Email {email} in use".encode("utf-8") in response.data


def test_signup_user_successful(test_client):
    response = test_client.post(
        "/signup",
        data=dict(name="Foo", surname="Example", email="foo@example.com", password="foo1234"),
        follow_redirects=True,
    )
    assert response.request.path == url_for("public.index"), "Signup was unsuccessful"


def test_service_create_with_profie_success(clean_database):
    data = {"name": "Test", "surname": "Foo", "email": "service_test@example.com", "password": "test1234"}

    AuthenticationService().create_with_profile(**data)

    assert UserRepository().count() == 1
    assert UserProfileRepository().count() == 1


def test_service_create_with_profile_fail_no_email(clean_database):
    data = {"name": "Test", "surname": "Foo", "email": "", "password": "1234"}

    with pytest.raises(ValueError, match="Email is required."):
        AuthenticationService().create_with_profile(**data)

    assert UserRepository().count() == 0
    assert UserProfileRepository().count() == 0


def test_service_create_with_profile_fail_no_password(clean_database):
    data = {"name": "Test", "surname": "Foo", "email": "test@example.com", "password": ""}

    with pytest.raises(ValueError, match="Password is required."):
        AuthenticationService().create_with_profile(**data)

    assert UserRepository().count() == 0
    assert UserProfileRepository().count() == 0


def test_service_create_with_profile_fail_no_name(clean_database):
    data = {"name": "", "surname": "Foo", "email": "test@example.com", "password": "test1234"}

    with pytest.raises(ValueError, match="Name is required."):
        AuthenticationService().create_with_profile(**data)

    assert UserRepository().count() == 0
    assert UserProfileRepository().count() == 0


def test_service_create_with_profile_fail_no_surname(clean_database):
    data = {"name": "Test", "surname": "", "email": "test@example.com", "password": "test1234"}

    with pytest.raises(ValueError, match="Surname is required."):
        AuthenticationService().create_with_profile(**data)

    assert UserRepository().count() == 0
    assert UserProfileRepository().count() == 0


def test_service_is_email_available_true(clean_database):
    auth_service = AuthenticationService()
    assert auth_service.is_email_available("newemail@example.com") is True


def test_service_is_email_available_false(clean_database):
    auth_service = AuthenticationService()
    auth_service.create_with_profile(email="existing@example.com", password="password123", name="Test", surname="User")
    assert auth_service.is_email_available("existing@example.com") is False


def test_service_temp_folder_by_user(clean_database):
    auth_service = AuthenticationService()
    user = auth_service.create_with_profile(
        email="test@example.com", password="password123", name="Test", surname="User"
    )
    temp_folder = auth_service.temp_folder_by_user(user)
    assert str(user.id) in temp_folder
    assert "temp" in temp_folder


def test_service_extract_device_info_mobile():
    auth_service = AuthenticationService()
    device_info = auth_service._extract_device_info("Mozilla/5.0 (iPhone; CPU iPhone OS 14_0)")
    assert device_info == "Mobile Device"


def test_service_extract_device_info_android():
    auth_service = AuthenticationService()
    device_info = auth_service._extract_device_info("Mozilla/5.0 (Linux; Android 10)")
    assert device_info == "Mobile Device"


def test_service_extract_device_info_tablet():
    auth_service = AuthenticationService()
    device_info = auth_service._extract_device_info("Mozilla/5.0 (iPad; CPU OS 14_0)")
    assert device_info == "Tablet"


def test_service_extract_device_info_desktop():
    auth_service = AuthenticationService()
    device_info = auth_service._extract_device_info("Mozilla/5.0 (Windows NT 10.0; Win64; x64)")
    assert device_info == "Desktop"


def test_service_extract_device_info_unknown():
    auth_service = AuthenticationService()
    device_info = auth_service._extract_device_info("")
    assert device_info == "Unknown Device"


def test_service_get_authenticated_user_none():
    auth_service = AuthenticationService()
    user = auth_service.get_authenticated_user()
    assert user is None


def test_service_get_authenticated_user_profile_none():
    auth_service = AuthenticationService()
    profile = auth_service.get_authenticated_user_profile()
    assert profile is None


def test_user_temp_folder(clean_database):
    auth_service = AuthenticationService()
    user = auth_service.create_with_profile(
        email="test@example.com", password="password123", name="Test", surname="User"
    )
    temp_folder = user.temp_folder()
    assert str(user.id) in temp_folder
    assert "temp" in temp_folder


def test_service_login_session_creation_exception(test_client, clean_database):
    """Test login continues even if session creation fails"""
    from unittest.mock import patch

    auth_service = AuthenticationService()

    # Pre-create a valid user so login can succeed
    auth_service.create_with_profile(
        email="exception@example.com",
        password="password123",
        name="Exception",
        surname="Test",
    )

    # Mock session creation to raise exception
    with patch.object(auth_service, "_create_session_record", side_effect=Exception("Session error")):
        with patch("flask.request"):
            with patch("flask.session", {}):
                result = auth_service.login("exception@example.com", "password123")
                # Login should succeed despite session error
                assert result is not None


def test_service_create_session_with_existing_session(test_client, clean_database):
    """Test creating session when one already exists updates it"""
    from unittest.mock import patch

    from app.modules.auth.models import UserSession

    auth_service = AuthenticationService()

    # Create user
    user = auth_service.create_with_profile(
        email="existing@example.com", password="password123", name="Existing", surname="Session"
    )

    # Create an existing session
    existing_session = UserSession(
        user_id=user.id, session_id="existing_session_123", ip_address="192.168.1.1", user_agent="Old Agent"
    )

    with test_client.application.app_context():
        from app import db

        db.session.add(existing_session)
        db.session.commit()

        with patch("flask.session", {"session_id": "existing_session_123"}):
            with patch("flask.request") as mock_request:
                mock_request.remote_addr = "127.0.0.1"
                mock_request.headers.get.return_value = "New Agent"

                result = auth_service._create_session_record(user)
                assert result is not None


def test_service_create_session_rollback_on_error(test_client, clean_database):
    """Test session creation handles rollback on error"""
    from unittest.mock import patch

    auth_service = AuthenticationService()

    # Create user
    user = auth_service.create_with_profile(
        email="rollback@example.com", password="password123", name="Rollback", surname="Test"
    )

    with patch("flask.session", {"session_id": "test_session"}):
        with patch("flask.request") as mock_request:
            mock_request.remote_addr = "127.0.0.1"
            mock_request.headers.get.return_value = "Test Agent"

            # Mock repository to raise exception
            with patch.object(auth_service.session_repository, "create", side_effect=Exception("DB Error")):
                with patch.object(auth_service.session_repository, "get_by_session_id", return_value=None):
                    result = auth_service._create_session_record(user)
                    # Should return None after all attempts fail
                    assert result is None


def test_service_update_profile_success(clean_database):
    """Test updating user profile successfully"""
    from unittest.mock import Mock

    auth_service = AuthenticationService()

    # Create user
    user = auth_service.create_with_profile(
        email="profile@example.com", password="password123", name="Profile", surname="Test"
    )

    # Mock form with valid data
    mock_form = Mock()
    mock_form.validate.return_value = True
    mock_form.data = {"name": "Updated", "surname": "Name"}

    updated, errors = auth_service.update_profile(user.profile.id, mock_form)
    assert updated is not None
    assert errors is None


def test_service_update_profile_validation_error(clean_database):
    """Test updating profile with validation errors"""
    from unittest.mock import Mock

    auth_service = AuthenticationService()

    # Create user
    user = auth_service.create_with_profile(
        email="validation@example.com", password="password123", name="Validation", surname="Test"
    )

    # Mock form with validation errors
    mock_form = Mock()
    mock_form.validate.return_value = False
    mock_form.errors = {"name": ["Name is required"]}

    updated, errors = auth_service.update_profile(user.profile.id, mock_form)
    assert updated is None
    assert errors is not None
    assert "name" in errors


def test_session_management_update_activity(test_client, clean_database):
    """Test updating session activity"""
    from app import db
    from app.modules.auth.models import UserSession
    from app.modules.auth.services import SessionManagementService

    auth_service = AuthenticationService()
    session_service = SessionManagementService()

    # Create user
    user = auth_service.create_with_profile(
        email="activity@example.com", password="password123", name="Activity", surname="Test"
    )

    with test_client.application.app_context():
        # Create session
        user_session = UserSession(user_id=user.id, session_id="activity_session", ip_address="127.0.0.1")
        db.session.add(user_session)
        db.session.commit()

        # Update activity
        result = session_service.update_session_activity("activity_session")
        assert result is True


def test_session_management_close_session_success(test_client, clean_database):
    """Test closing a session successfully"""
    from app import db
    from app.modules.auth.models import UserSession
    from app.modules.auth.services import SessionManagementService

    auth_service = AuthenticationService()
    session_service = SessionManagementService()

    # Create user
    user = auth_service.create_with_profile(
        email="closesession@example.com", password="password123", name="Close", surname="Session"
    )

    with test_client.application.app_context():
        # Create session
        user_session = UserSession(user_id=user.id, session_id="close_session_123", ip_address="127.0.0.1")
        db.session.add(user_session)
        db.session.commit()

        # Close session
        result = session_service.close_session("close_session_123", user.id)
        assert result is True


def test_session_management_close_session_wrong_user(test_client, clean_database):
    """Test closing a session that belongs to different user"""
    from app import db
    from app.modules.auth.models import UserSession
    from app.modules.auth.services import SessionManagementService

    auth_service = AuthenticationService()
    session_service = SessionManagementService()

    # Create user
    user = auth_service.create_with_profile(
        email="wronguser@example.com", password="password123", name="Wrong", surname="User"
    )

    with test_client.application.app_context():
        # Create session
        user_session = UserSession(user_id=user.id, session_id="wrong_user_session", ip_address="127.0.0.1")
        db.session.add(user_session)
        db.session.commit()

        # Try to close with different user ID
        result = session_service.close_session("wrong_user_session", 99999)
        assert result is False


def test_session_management_close_all_others(test_client, clean_database):
    """Test closing all sessions except current one"""
    from app import db
    from app.modules.auth.models import UserSession
    from app.modules.auth.services import SessionManagementService

    auth_service = AuthenticationService()
    session_service = SessionManagementService()

    # Create user
    user = auth_service.create_with_profile(
        email="closeall@example.com", password="password123", name="CloseAll", surname="Test"
    )

    with test_client.application.app_context():
        # Create multiple sessions
        session1 = UserSession(user_id=user.id, session_id="session_1", ip_address="127.0.0.1")
        session2 = UserSession(user_id=user.id, session_id="session_2", ip_address="127.0.0.1")
        session3 = UserSession(user_id=user.id, session_id="session_3", ip_address="127.0.0.1")
        db.session.add_all([session1, session2, session3])
        db.session.commit()

        # Close all except session_1
        count = session_service.close_all_other_sessions(user.id, "session_1")
        assert count == 2


def test_role_model_repr(clean_database):
    """Test Role model __repr__ method"""
    from app import db
    from app.modules.auth.models import Role

    role = Role(name="admin", description="Administrator role")
    db.session.add(role)
    db.session.commit()

    assert repr(role) == "<Role admin>"


def test_user_with_roles(clean_database):
    """Test User model with roles relationship"""
    from app import db
    from app.modules.auth.models import Role, User

    # Create roles
    admin_role = Role(name="admin", description="Administrator")
    user_role = Role(name="user", description="Regular user")
    db.session.add_all([admin_role, user_role])
    db.session.commit()

    # Create user
    user = User(email="roletest@example.com", password="test1234")
    user.roles.append(admin_role)
    user.roles.append(user_role)
    db.session.add(user)
    db.session.commit()

    # Verify
    assert len(user.roles) == 2
    assert admin_role in user.roles
    assert user_role in user.roles


def test_user_session_get_browser_name_with_user_agent(clean_database):
    """Test UserSession get_browser_name with valid user agent"""
    from app import db
    from app.modules.auth.models import UserSession

    auth_service = AuthenticationService()
    user = auth_service.create_with_profile(
        email="browser@example.com", password="test1234", name="Browser", surname="Test"
    )

    session = UserSession(
        user_id=user.id,
        session_id="browser_test",
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/91.0.4472.124 Safari/537.36",
    )
    db.session.add(session)
    db.session.commit()

    browser = session.get_browser_name()
    assert browser == "Chrome"


def test_user_session_get_browser_name_no_user_agent(clean_database):
    """Test UserSession get_browser_name without user agent"""
    from app import db
    from app.modules.auth.models import UserSession

    auth_service = AuthenticationService()
    user = auth_service.create_with_profile(
        email="nobrowser@example.com", password="test1234", name="NoBrowser", surname="Test"
    )

    session = UserSession(user_id=user.id, session_id="no_browser", user_agent="")
    db.session.add(session)
    db.session.commit()

    browser = session.get_browser_name()
    assert browser == "Unknown Browser"


def test_user_session_get_os_name_with_user_agent(clean_database):
    """Test UserSession get_os_name with valid user agent"""
    from app import db
    from app.modules.auth.models import UserSession

    auth_service = AuthenticationService()
    user = auth_service.create_with_profile(email="os@example.com", password="test1234", name="OS", surname="Test")

    session = UserSession(
        user_id=user.id, session_id="os_test", user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    )
    db.session.add(session)
    db.session.commit()

    os_name = session.get_os_name()
    assert "Windows" in os_name


def test_user_session_get_os_name_no_user_agent(clean_database):
    """Test UserSession get_os_name without user agent"""
    from app import db
    from app.modules.auth.models import UserSession

    auth_service = AuthenticationService()
    user = auth_service.create_with_profile(email="noos@example.com", password="test1234", name="NoOS", surname="Test")

    session = UserSession(user_id=user.id, session_id="no_os", user_agent="")
    db.session.add(session)
    db.session.commit()

    os_name = session.get_os_name()
    assert os_name == "Unknown OS"


def test_user_session_is_current_session(clean_database):
    """Test UserSession is_current_session method"""
    from app import db
    from app.modules.auth.models import UserSession

    auth_service = AuthenticationService()
    user = auth_service.create_with_profile(
        email="current@example.com", password="test1234", name="Current", surname="Session"
    )

    session = UserSession(user_id=user.id, session_id="current_session_123")
    db.session.add(session)
    db.session.commit()

    assert session.is_current_session("current_session_123") is True
    assert session.is_current_session("other_session") is False


def test_user_session_repr(clean_database):
    """Test UserSession __repr__ method"""
    from app import db
    from app.modules.auth.models import UserSession

    auth_service = AuthenticationService()
    user = auth_service.create_with_profile(email="repr@example.com", password="test1234", name="Repr", surname="Test")

    session = UserSession(user_id=user.id, session_id="repr_session_123")
    db.session.add(session)
    db.session.commit()

    repr_str = repr(session)
    assert "repr_session_123" in repr_str
    assert f"User {user.id}" in repr_str
