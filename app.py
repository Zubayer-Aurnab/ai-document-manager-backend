"""Flask application entrypoint."""
import os

import click
from flask import Flask

from config import Config
from extensions import cors, db, jwt, migrate
from modules.ai import ai_bp
from modules.auth import auth_bp
from modules.departments import departments_bp
from modules.categories import categories_bp
from modules.company import company_bp
from modules.documents import documents_bp
from modules.logs import logs_bp
from modules.notifications import notifications_bp
from modules.users import users_bp


def create_app(config_class: type = Config) -> Flask:
    app = Flask(__name__)
    app.config.from_object(config_class)

    db.init_app(app)
    migrate.init_app(app, db)
    jwt.init_app(app)
    origins = [o.strip() for o in app.config["FRONTEND_URL"].split(",") if o.strip()]
    if not origins:
        origins = ["http://localhost:3000"]
    cors.init_app(
        app,
        resources={r"/api/*": {"origins": origins, "supports_credentials": True}},
        allow_headers=["Content-Type", "Authorization"],
        methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    )

    @jwt.user_lookup_loader
    def user_lookup_callback(_jwt_header, jwt_data):
        from models.user import User

        return db.session.get(User, int(jwt_data["sub"]))

    app.register_blueprint(auth_bp, url_prefix="/api/auth")
    app.register_blueprint(users_bp, url_prefix="/api/v1/users")
    app.register_blueprint(departments_bp, url_prefix="/api/v1/departments")
    app.register_blueprint(documents_bp, url_prefix="/api/v1/documents")
    app.register_blueprint(categories_bp, url_prefix="/api/v1/categories")
    app.register_blueprint(company_bp, url_prefix="/api/v1/company")
    app.register_blueprint(notifications_bp, url_prefix="/api/v1/notifications")
    app.register_blueprint(logs_bp, url_prefix="/api/v1/activity-logs")
    app.register_blueprint(ai_bp, url_prefix="/api/v1/ai")

    import models  # noqa: F401 — register ORM mappers with SQLAlchemy metadata

    from db_bootstrap import bootstrap_database

    bootstrap_database(app)

    @app.get("/api/v1/health")
    def health():
        from utils.responses import success

        return success("OK.", {"status": "healthy"})

    @app.cli.command("seed-admin")
    @click.option("--email", default="admin@apptriangle.com")
    @click.option("--password", default="admin123")
    @click.option("--name", default="System Admin")
    def seed_admin(email, password, name):
        """Apply migrations, then create default department + admin if that email is not taken."""
        from flask_migrate import upgrade

        from db_bootstrap import ensure_admin_user

        with app.app_context():
            upgrade()
            if ensure_admin_user(email, password, name):
                click.echo(f"Admin created: {email}")
            else:
                click.echo("Admin already exists.")

    return app


app = create_app()


if __name__ == "__main__":
    # `.env` is read by `load_dotenv()` in config.py when this module loads — do not "run" the .env file itself.
    _port = int(os.environ.get("PORT", "5000"))
    _debug = os.environ.get("FLASK_ENV", "").lower() == "development" or os.environ.get("FLASK_DEBUG", "").lower() in (
        "1",
        "true",
        "yes",
    )
    print(f"Document Manager API → http://127.0.0.1:{_port}/  (Ctrl+C to stop)")
    app.run(host="0.0.0.0", port=_port, debug=_debug)
