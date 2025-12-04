from core.blueprints.base_blueprint import BaseBlueprint

profile_bp = BaseBlueprint("profile", __name__, template_folder="templates")

from . import routes  # noqa: E402,F401
