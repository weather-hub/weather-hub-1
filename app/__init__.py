import os
from datetime import datetime, timedelta, timezone

from dotenv import load_dotenv
from flask import Flask, session
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy

from core.configuration.configuration import get_app_version
from core.managers.config_manager import ConfigManager
from core.managers.error_handler_manager import ErrorHandlerManager
from core.managers.logging_manager import LoggingManager
from core.managers.module_manager import ModuleManager

# Load environment variables
load_dotenv()

# Create the instances
db = SQLAlchemy()
migrate = Migrate()

limiter = Limiter(key_func=get_remote_address, default_limits=[])

MAX_LOGIN_ATTEMPTS = 5
BLOCK_TIME = 180  # 3 minutos


def get_attempts():
    return session.get("failed_attempts", 0)


def get_block_time():
    return session.get("block_until")


def increment_failed_attempts():
    attempts = get_attempts() + 1
    session["failed_attempts"] = attempts
    if attempts >= MAX_LOGIN_ATTEMPTS:
        block_time = datetime.now(timezone.utc) + timedelta(seconds=BLOCK_TIME)
        session["block_until"] = block_time.isoformat()  # Guardar como string
    return attempts


def reset_failed_attempts():
    session.pop("failed_attempts", None)
    session.pop("block_until", None)


def is_blocked():
    block_until = get_block_time()
    if block_until:
        # convertir a naive si es necesario
        if isinstance(block_until, str):
            # si session lo guardó como string ISO
            block_until = datetime.fromisoformat(block_until)
        if datetime.now(timezone.utc) < block_until:
            return True
        else:
            reset_failed_attempts()
    return False


def create_app(config_name="development"):
    app = Flask(__name__)

    # Load configuration according to environment
    config_manager = ConfigManager(app)
    config_manager.load_config(config_name=config_name)

    # Initialize SQLAlchemy and Migrate with the app
    db.init_app(app)
    migrate.init_app(app, db)
    limiter.init_app(app)
    # Register modules
    module_manager = ModuleManager(app)
    module_manager.register_modules()

    # Register login manager
    from flask_login import LoginManager

    login_manager = LoginManager()
    login_manager.init_app(app)
    login_manager.login_view = "auth.login"

    # Initialize Flask-Mail
    from app.modules.notifications.service import init_mail

    init_mail(app)

    @login_manager.user_loader
    def load_user(user_id):
        from app.modules.auth.models import User

        return User.query.get(int(user_id))

    # Set up logging
    logging_manager = LoggingManager(app)
    logging_manager.setup_logging()

    # Initialize error handler manager
    error_handler_manager = ErrorHandlerManager(app)
    error_handler_manager.register_error_handlers()

    # Injecting environment variables into jinja context
    @app.context_processor
    def inject_vars_into_jinja():
        return {
            "FLASK_APP_NAME": os.getenv("FLASK_APP_NAME"),
            "FLASK_ENV": os.getenv("FLASK_ENV"),
            "DOMAIN": os.getenv("DOMAIN", "localhost"),
            "APP_VERSION": get_app_version(),
        }

    return app


app = create_app()
