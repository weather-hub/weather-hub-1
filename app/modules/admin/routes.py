from flask import jsonify, render_template, request
from flask_login import login_required

from app import db
from app.modules.admin import admin_bp
from app.modules.auth.models import Role, User
from app.modules.auth.repositories import RoleRepository
from core.decorators.decorators import admin_required

role_repository = RoleRepository()


@admin_bp.route("/admin/users", methods=["GET"])
@login_required
@admin_required
def list_users():
    """
    List all users with their assigned roles.
    Only accessible by admin users.
    """
    users = User.query.all()
    roles = Role.query.order_by(Role.name).all()

    return render_template("admin/users.html", users=users, available_roles=roles)


@admin_bp.route("/admin/users/<int:user_id>/roles", methods=["POST"])
@login_required
@admin_required
def update_user_roles(user_id):
    """
    Update roles for a specific user.
    Expects JSON payload with 'role_ids' array.
    """
    user = User.query.get_or_404(user_id)
    data = request.get_json()

    if not data or "role_ids" not in data:
        return jsonify({"error": "Missing role_ids in request"}), 400

    role_ids = data["role_ids"]

    # Validate that all role_ids exist
    roles = Role.query.filter(Role.id.in_(role_ids)).all()
    if len(roles) != len(role_ids):
        return jsonify({"error": "One or more invalid role IDs"}), 400

    # Business rule: 'guest' role is exclusive. It cannot be combined with any other role
    if any(r.name == "guest" for r in roles) and len(roles) > 1:
        return jsonify({"error": "'guest' role cannot be combined with other roles"}), 400

    # Update user roles
    user.roles = roles
    db.session.commit()

    return jsonify({"success": True, "user_id": user.id, "roles": [{"id": r.id, "name": r.name} for r in user.roles]})


@admin_bp.route("/admin/users/<int:user_id>/roles/<int:role_id>", methods=["POST"])
@login_required
@admin_required
def add_user_role(user_id, role_id):
    """
    Add a single role to a user.
    """
    user = User.query.get_or_404(user_id)
    role = Role.query.get_or_404(role_id)

    # Business rule: 'guest' role is exclusive
    if role.name == "guest" and len(user.roles) > 0:
        return jsonify({"error": "'guest' role cannot be assigned together with other roles"}), 400
    if role.name != "guest" and any(r.name == "guest" for r in user.roles):
        return jsonify({"error": "Cannot add other roles to a 'guest' user"}), 400

    if role not in user.roles:
        user.roles.append(role)
        db.session.commit()

    return jsonify({"success": True, "user_id": user.id, "roles": [{"id": r.id, "name": r.name} for r in user.roles]})


@admin_bp.route("/admin/users/<int:user_id>/roles/<int:role_id>", methods=["DELETE"])
@login_required
@admin_required
def remove_user_role(user_id, role_id):
    """
    Remove a single role from a user.
    Business rule: A user must have at least one role at all times.
    """
    user = User.query.get_or_404(user_id)
    role = Role.query.get_or_404(role_id)

    # Prevent removing the last role from a user (RBAC invariant)
    if len(user.roles) <= 1:
        return jsonify({"error": "Cannot remove last role. User must have at least one role"}), 400

    if role in user.roles:
        user.roles.remove(role)
        db.session.commit()

    return jsonify({"success": True, "user_id": user.id, "roles": [{"id": r.id, "name": r.name} for r in user.roles]})
