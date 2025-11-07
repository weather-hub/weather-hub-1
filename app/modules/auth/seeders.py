import os

from core.seeders.BaseSeeder import BaseSeeder


class AuthSeeder(BaseSeeder):
    """Seeder that creates the fixed roles and some example users (idempotent).

    - Creates roles: admin, curator, standard, guest
    - Creates example users only if they don't already exist
    - Optionally creates an admin user from ENV vars
    """

    priority = 5

    def run(self):
        from app.modules.auth.repositories import RoleRepository, UserRepository
        from app.modules.auth.models import Role
        from app.modules.auth.services import AuthenticationService
        from app.modules.profile.models import UserProfile

        role_repo = RoleRepository()
        user_repo = UserRepository()
        auth_service = AuthenticationService()

        roles = [
            ("admin", "Platform administrator with full access"),
            ("curator", "Can manage and curate datasets"),
            ("standard", "Standard registered user"),
            ("guest", "Read-only guest user"),
        ]

        # Create roles idempotently
        created_roles = []
        for name, desc in roles:
            existing = role_repo.get_by_name(name)
            if not existing:
                created_roles.append(Role(name=name, description=desc))

        if created_roles:
            self.seed(created_roles)

        # Example users to create (only if missing)
        example_users = [
            {"email": "user1@example.com", "password": "1234", "name": "John", "surname": "Doe"},
            {"email": "user2@example.com", "password": "1234", "name": "Jane", "surname": "Doe"},
        ]

        for u in example_users:
            existing = user_repo.get_by_email(u["email"])
            if existing:
                continue
            try:
                user = auth_service.create_with_profile(
                    email=u["email"], password=u["password"], name=u["name"], surname=u["surname"]
                )
            except Exception:
                # If creation fails, skip and continue with next
                continue

        # Optionally create an initial admin user if env vars are provided
        admin_email = os.getenv("ADMIN_EMAIL")
        admin_password = os.getenv("ADMIN_PASSWORD")
        admin_name = os.getenv("ADMIN_NAME")
        admin_surname = os.getenv("ADMIN_SURNAME")

        if admin_email and admin_password and admin_name and admin_surname:
            existing_admin = user_repo.get_by_email(admin_email)
            if not existing_admin:
                try:
                    user = auth_service.create_with_profile(
                        email=admin_email,
                        password=admin_password,
                        name=admin_name,
                        surname=admin_surname,
                    )
                except Exception:
                    user = user_repo.get_by_email(admin_email)

            # assign admin role if missing
            if user:
                role = role_repo.get_by_name("admin")
                if role and role not in user.roles:
                    user.roles.append(role)
                    self.db.session.add(user)
                    self.db.session.commit()
