from app import db
from app.modules.auth.models import User
from app.modules.auth.repositories import RoleRepository


def test_role_repository_create_and_idempotent(test_client):
    # Use test_client to ensure application context and database setup
    role_repo = RoleRepository()
    role_repo.create_if_not_exists("admin", "Administrator")
    assert role_repo.count() == 1

    # idempotent create
    role_repo.create_if_not_exists("admin", "Administrator")
    assert role_repo.count() == 1


def test_assign_role_to_user(test_client):
    # test_client fixture creates a test user (test@example.com)
    user = User.query.filter_by(email="test@example.com").first()
    assert user is not None

    role_repo = RoleRepository()
    role = role_repo.create_if_not_exists("curator", "Curator role")

    user.roles.append(role)
    db.session.add(user)
    db.session.commit()

    user_refreshed = User.query.get(user.id)
    assert any(r.name == "curator" for r in user_refreshed.roles)
