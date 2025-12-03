import pytest
from datetime import datetime, timedelta, timezone

from app.modules.auth.repositories import UserRepository, UserSessionRepository
from app.modules.auth.services import SessionManagementService


@pytest.fixture
def user(clean_database):
    # create a user to attach sessions to
    user = UserRepository().create(email="user_sessions@example.com", password="pass1234")
    return user


def test_create_and_get_session(user):
    repo = UserSessionRepository()

    session = repo.create(user_id=user.id, session_id="sess-1", ip_address="127.0.0.1", user_agent="ua")

    fetched = repo.get_by_session_id("sess-1")
    assert fetched is not None
    assert fetched.id == session.id
    assert fetched.is_active is True


def test_get_active_sessions_ordering(user):
    repo = UserSessionRepository()
    now = datetime.now(timezone.utc)

    s1 = repo.create(user_id=user.id, session_id="s1", last_activity=now - timedelta(days=2))
    s2 = repo.create(user_id=user.id, session_id="s2", last_activity=now - timedelta(days=1))
    s3 = repo.create(user_id=user.id, session_id="s3", last_activity=now)

    sessions = repo.get_active_sessions_by_user(user.id)
    # Expect newest first
    assert [s.session_id for s in sessions] == ["s3", "s2", "s1"]


def test_deactivate_session_and_update_last_activity(user):
    repo = UserSessionRepository()
    now = datetime.now(timezone.utc)

    s = repo.create(user_id=user.id, session_id="to-deactivate", last_activity=now - timedelta(days=1))

    # update last activity
    orig_last = s.last_activity
    updated = repo.update_last_activity("to-deactivate")
    assert updated is True
    fetched = repo.get_by_session_id("to-deactivate")
    # Ensure last_activity was advanced (robust against small clock differences)
    assert fetched.last_activity > orig_last

    # deactivate
    deactivated = repo.deactivate_session("to-deactivate")
    assert deactivated is True
    fetched = repo.get_by_session_id("to-deactivate")
    # get_by_session_id only returns active sessions; after deactivation it should return None
    assert fetched is None


def test_cleanup_inactive_sessions(user):
    repo = UserSessionRepository()
    now = datetime.now(timezone.utc)

    # session older than cutoff
    old = repo.create(user_id=user.id, session_id="old-session", last_activity=now - timedelta(days=10))
    # recent session
    recent = repo.create(user_id=user.id, session_id="recent-session", last_activity=now)
    # use a cutoff that clearly separates old and recent sessions
    count = repo.cleanup_inactive_sessions(days=5)
    assert count >= 1

    # old session must now be inactive (get_by_session_id returns only active ones)
    assert repo.get_by_session_id("old-session") is None
    # recent session should still be active
    assert repo.get_by_session_id("recent-session") is not None


def test_session_management_close_all_other_sessions(user):
    repo = UserSessionRepository()
    svc = SessionManagementService()

    # create three sessions
    a = repo.create(user_id=user.id, session_id="a")
    b = repo.create(user_id=user.id, session_id="b")
    c = repo.create(user_id=user.id, session_id="c")

    closed = svc.close_all_other_sessions(user.id, current_session_id="b")
    # two sessions should be closed (a and c)
    assert closed == 2

    # ensure 'b' still active
    assert repo.get_by_session_id("b") is not None
    # a and c should be inactive
    assert repo.get_by_session_id("a") is None
    assert repo.get_by_session_id("c") is None


def test_close_session_only_if_belongs_to_user(clean_database):
    # create two users and a session for user1
    user1 = UserRepository().create(email="u1@example.com", password="pw1")
    user2 = UserRepository().create(email="u2@example.com", password="pw2")
    repo = UserSessionRepository()
    svc = SessionManagementService()

    s = repo.create(user_id=user1.id, session_id="only-user1")

    # user2 should not be able to close user1's session
    result = svc.close_session("only-user1", user2.id)
    assert result is False

    # user1 can close it
    result = svc.close_session("only-user1", user1.id)
    assert result is True
