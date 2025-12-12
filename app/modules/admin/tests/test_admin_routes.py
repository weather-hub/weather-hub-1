import pytest

from app import db
from app.modules.auth.models import Role, User


@pytest.fixture(scope="module")
def test_client(test_client):
    """
    Extends the test_client fixture to add admin and regular users with roles.
    """
    with test_client.application.app_context():
        # Create roles if they don't exist
        for role_name, role_desc in [
            ("admin", "Administrator"),
            ("standard", "Standard user"),
            ("curator", "Curator"),
            ("guest", "Guest"),
        ]:
            if not Role.query.filter_by(name=role_name).first():
                role = Role(name=role_name, description=role_desc)
                db.session.add(role)

        db.session.commit()

        # Create admin user
        admin_role = Role.query.filter_by(name="admin").first()
        admin = User(email="admin@test.com", password="admin123")
        db.session.add(admin)
        db.session.flush()
        admin.roles.append(admin_role)

        # Create regular user with multiple roles (standard + curator)
        standard_role = Role.query.filter_by(name="standard").first()
        curator_role = Role.query.filter_by(name="curator").first()
        regular = User(email="regular@test.com", password="user123")
        db.session.add(regular)
        db.session.flush()
        regular.roles.append(standard_role)
        regular.roles.append(curator_role)

        db.session.commit()

    yield test_client


def test_admin_users_page_requires_login(test_client):
    """Test that admin users page requires authentication."""
    response = test_client.get("/admin/users", follow_redirects=False)
    assert response.status_code in [302, 401]


def test_admin_users_page_requires_admin_role(test_client):
    """Test that non-admin users get 403."""
    # Login as regular user
    test_client.post("/login", data={"email": "regular@test.com", "password": "user123"}, follow_redirects=True)

    response = test_client.get("/admin/users")
    assert response.status_code == 403

    # Cleanup
    test_client.get("/logout", follow_redirects=True)


def test_admin_users_page_accessible_by_admin(test_client):
    """Test that admin users can access the admin panel."""
    # Login as admin
    response = test_client.post(
        "/login", data={"email": "admin@test.com", "password": "admin123"}, follow_redirects=True
    )

    # Verify we're logged in (redirected to index)
    assert response.status_code == 200

    # Now access admin page
    response = test_client.get("/admin/users")
    assert response.status_code == 200
    assert b"Gesti" in response.data or b"users" in response.data.lower()

    # Cleanup
    test_client.get("/logout", follow_redirects=True)


def test_update_user_roles_as_admin(test_client):
    """Test that admin can update user roles."""
    # Login as admin
    test_client.post("/login", data={"email": "admin@test.com", "password": "admin123"}, follow_redirects=True)

    # Get regular user ID and curator role ID
    with test_client.application.app_context():
        regular_user = User.query.filter_by(email="regular@test.com").first()
        curator_role = Role.query.filter_by(name="curator").first()
        regular_user_id = regular_user.id
        curator_role_id = curator_role.id

    # Update regular user to have curator role
    response = test_client.post(
        f"/admin/users/{regular_user_id}/roles", json={"role_ids": [curator_role_id]}, content_type="application/json"
    )

    assert response.status_code == 200
    data = response.get_json()
    assert data["success"] is True
    assert len(data["roles"]) == 1
    assert data["roles"][0]["name"] == "curator"

    # Cleanup
    test_client.get("/logout", follow_redirects=True)


def test_update_user_roles_rejects_empty_roles(test_client):
    """Test that admin cannot update a user with an empty role list."""
    # Login as admin
    test_client.post("/login", data={"email": "admin@test.com", "password": "admin123"}, follow_redirects=True)

    # Get regular user ID
    with test_client.application.app_context():
        regular_user = User.query.filter_by(email="regular@test.com").first()
        regular_user_id = regular_user.id
        roles_before = len(regular_user.roles)

    # Try to update user with empty role list
    response = test_client.post(
        f"/admin/users/{regular_user_id}/roles", json={"role_ids": []}, content_type="application/json"
    )

    # Should reject with 400
    assert response.status_code == 400
    data = response.get_json()
    assert "error" in data
    assert "at least one role" in data["error"]

    # Verify user still has their original roles (DB unchanged)
    with test_client.application.app_context():
        regular_user = User.query.filter_by(email="regular@test.com").first()
        assert len(regular_user.roles) == roles_before

    # Cleanup
    test_client.get("/logout", follow_redirects=True)


def test_add_guest_role_rejected_if_user_has_other_roles(test_client):
    """Adding 'guest' to a user that already has another role should be rejected (400)."""
    # Login as admin
    test_client.post("/login", data={"email": "admin@test.com", "password": "admin123"}, follow_redirects=True)

    # Get IDs
    with test_client.application.app_context():
        regular_user = User.query.filter_by(email="regular@test.com").first()
        guest_role = Role.query.filter_by(name="guest").first()
        regular_user_id = regular_user.id
        guest_role_id = guest_role.id

    response = test_client.post(f"/admin/users/{regular_user_id}/roles/{guest_role_id}")

    assert response.status_code == 400
    data = response.get_json()
    assert "error" in data

    # Cleanup
    test_client.get("/logout", follow_redirects=True)


def test_remove_role_from_user(test_client):
    """Test removing a role from a user when they have multiple roles."""
    # Login as admin
    test_client.post("/login", data={"email": "admin@test.com", "password": "admin123"}, follow_redirects=True)

    # Ensure user has 2 roles (standard + curator) using the bulk update endpoint
    with test_client.application.app_context():
        regular_user = User.query.filter_by(email="regular@test.com").first()
        standard_role = Role.query.filter_by(name="standard").first()
        curator_role = Role.query.filter_by(name="curator").first()
        regular_user_id = regular_user.id
        standard_role_id = standard_role.id
        curator_role_id = curator_role.id

    # Set user to have both standard and curator roles
    test_client.post(
        f"/admin/users/{regular_user_id}/roles",
        json={"role_ids": [standard_role_id, curator_role_id]},
        content_type="application/json",
    )

    # Now remove one role (should succeed since user will still have curator role)
    response = test_client.delete(f"/admin/users/{regular_user_id}/roles/{standard_role_id}")

    assert response.status_code == 200
    data = response.get_json()
    assert data["success"] is True

    # Cleanup
    test_client.get("/logout", follow_redirects=True)


def test_cannot_remove_last_role_from_user(test_client):
    """Test that removing the last role from a user is rejected (regression test for INC-01)."""
    # Login as admin
    test_client.post("/login", data={"email": "admin@test.com", "password": "admin123"}, follow_redirects=True)

    # Get IDs and ensure user has exactly one role
    with test_client.application.app_context():
        regular_user = User.query.filter_by(email="regular@test.com").first()
        guest_role = Role.query.filter_by(name="guest").first()
        regular_user_id = regular_user.id
        guest_role_id = guest_role.id

    # Set user to have only guest role
    test_client.post(
        f"/admin/users/{regular_user_id}/roles",
        json={"role_ids": [guest_role_id]},
        content_type="application/json",
    )

    # Attempt to remove the only role (should fail with 400)
    response = test_client.delete(f"/admin/users/{regular_user_id}/roles/{guest_role_id}")

    assert response.status_code == 400
    data = response.get_json()
    assert "error" in data
    assert "last role" in data["error"].lower() or "at least one" in data["error"].lower()

    # Verify role was NOT removed
    with test_client.application.app_context():
        user = User.query.get(regular_user_id)
        assert len(user.roles) == 1
        assert user.roles[0].name == "guest"

    # Cleanup
    test_client.get("/logout", follow_redirects=True)


def test_update_roles_reject_guest_combo_and_allow_guest_alone(test_client):
    """Bulk update should reject guest+other combo (400) and allow guest alone (200)."""
    # Login as admin
    test_client.post("/login", data={"email": "admin@test.com", "password": "admin123"}, follow_redirects=True)

    with test_client.application.app_context():
        regular_user = User.query.filter_by(email="regular@test.com").first()
        guest_role = Role.query.filter_by(name="guest").first()
        standard_role = Role.query.filter_by(name="standard").first()
        regular_user_id = regular_user.id
        guest_role_id = guest_role.id
        standard_role_id = standard_role.id

    # Try to set guest + standard -> should be 400
    response = test_client.post(
        f"/admin/users/{regular_user_id}/roles",
        json={"role_ids": [guest_role_id, standard_role_id]},
        content_type="application/json",
    )
    assert response.status_code == 400
    data = response.get_json()
    assert "guest" in data.get("error", "").lower()

    # Set only guest -> 200
    response = test_client.post(
        f"/admin/users/{regular_user_id}/roles", json={"role_ids": [guest_role_id]}, content_type="application/json"
    )
    assert response.status_code == 200
    data = response.get_json()
    assert data["success"] is True
    assert len(data["roles"]) == 1
    assert data["roles"][0]["name"] == "guest"

    # Cleanup
    test_client.get("/logout", follow_redirects=True)


def test_non_admin_cannot_update_roles(test_client):
    """Test that non-admin users cannot update roles."""
    # Login as regular user
    test_client.post("/login", data={"email": "regular@test.com", "password": "user123"}, follow_redirects=True)

    # Get admin user ID
    with test_client.application.app_context():
        admin_user = User.query.filter_by(email="admin@test.com").first()
        admin_user_id = admin_user.id

    response = test_client.post(
        f"/admin/users/{admin_user_id}/roles", json={"role_ids": [1]}, content_type="application/json"
    )

    assert response.status_code == 403

    # Cleanup
    test_client.get("/logout", follow_redirects=True)


def test_admin_cannot_modify_own_roles(test_client):
    """
    Regression test for INC-04: Admin cannot modify their own roles.
    Verifies that admins are prevented from changing their own roles to avoid self-lockout.
    """
    # Login as admin
    test_client.post("/login", data={"email": "admin@test.com", "password": "admin123"}, follow_redirects=True)

    # Get admin user and a different role
    with test_client.application.app_context():
        admin_user = User.query.filter_by(email="admin@test.com").first()
        admin_user_id = admin_user.id
        standard_role = Role.query.filter_by(name="standard").first()
        standard_role_id = standard_role.id

    # Attempt to modify own roles
    response = test_client.post(
        f"/admin/users/{admin_user_id}/roles",
        json={"role_ids": [standard_role_id]},
        content_type="application/json",
    )

    # Should return 403 Forbidden
    assert response.status_code == 403
    data = response.get_json()
    assert "error" in data
    assert "own roles" in data["error"].lower()

    # Verify roles were not changed
    with test_client.application.app_context():
        admin_user = User.query.filter_by(email="admin@test.com").first()
        assert any(r.name == "admin" for r in admin_user.roles)

    # Cleanup
    test_client.get("/logout", follow_redirects=True)


def test_update_user_roles_rejects_invalid_role_ids(test_client):
    """
    Regression test for INC-03: Strong validation of invalid role IDs.
    Verifies that the endpoint explicitly identifies and rejects invalid role IDs.
    """
    # Login as admin
    test_client.post("/login", data={"email": "admin@test.com", "password": "admin123"}, follow_redirects=True)

    # Get regular user and existing roles
    with test_client.application.app_context():
        regular_user = User.query.filter_by(email="regular@test.com").first()
        regular_user_id = regular_user.id
        standard_role = Role.query.filter_by(name="standard").first()
        standard_role_id = standard_role.id

    # Attempt to assign a mix of valid and invalid role IDs
    # Using IDs that are extremely unlikely to exist (9999, 10000)
    invalid_ids = [9999, 10000]
    mixed_role_ids = [standard_role_id] + invalid_ids

    response = test_client.post(
        f"/admin/users/{regular_user_id}/roles",
        json={"role_ids": mixed_role_ids},
        content_type="application/json",
    )

    # Should return 400 Bad Request
    assert response.status_code == 400

    # Response should contain error details
    data = response.get_json()
    assert "error" in data
    assert "invalid_role_ids" in data

    # The invalid_role_ids should contain the non-existent IDs
    returned_invalid_ids = data["invalid_role_ids"]
    assert set(returned_invalid_ids) == set(invalid_ids)

    # Cleanup
    test_client.get("/logout", follow_redirects=True)
