from app.modules.auth.models import User
from core.repositories.BaseRepository import BaseRepository
from app.modules.auth.models import Role


class UserRepository(BaseRepository):
    def __init__(self):
        super().__init__(User)

    def create(self, commit: bool = True, **kwargs):
        password = kwargs.pop("password")
        instance = self.model(**kwargs)
        instance.set_password(password)
        self.session.add(instance)
        if commit:
            self.session.commit()
        else:
            self.session.flush()
        return instance

    def get_by_email(self, email: str):
        return self.model.query.filter_by(email=email).first()


class RoleRepository(BaseRepository):
    def __init__(self):
        super().__init__(Role)

    def get_by_name(self, name: str):
        return self.model.query.filter_by(name=name).first()

    def create_if_not_exists(self, name: str, description: str = None):
        role = self.get_by_name(name)
        if role:
            return role
        return self.create(name=name, description=description)
