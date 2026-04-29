"""Database migrations on startup and optional default admin seeding."""
from __future__ import annotations

import logging
import os
import re
from datetime import datetime, timezone
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from flask import Flask

logger = logging.getLogger(__name__)

MYSQL_UNKNOWN_DATABASE = 1049
MYSQL_ACCESS_DENIED = 1045


def _mysql_errno_from_exception(exc: BaseException, errno: int) -> bool:
    """True if this exception chain includes the given MySQL errno (PyMySQL / SQLAlchemy)."""
    seen: set[int] = set()
    cur: BaseException | None = exc
    for _ in range(8):
        if cur is None or id(cur) in seen:
            break
        seen.add(id(cur))
        args = getattr(cur, "args", ())
        if len(args) >= 1 and args[0] == errno:
            return True
        cur = getattr(cur, "orig", None) or getattr(cur, "__cause__", None)
    return False


def _running_on_railway() -> bool:
    return bool(os.environ.get("RAILWAY_ENVIRONMENT") or os.environ.get("RAILWAY_PROJECT_ID"))


def _mysql_access_denied_help_text() -> str:
    if _running_on_railway():
        return (
            "MySQL refused login (error 1045: access denied). This is running on Railway, so DATABASE_URL on "
            "your **API service** does not match the credentials the **MySQL** service expects (wrong password, "
            "stale copy, or not wired to the right database).\n\n"
            "Fix:\n"
            "  1. In Railway, open your **MySQL** plugin → Variables — note the canonical URL variable name.\n"
            "  2. Open your **Flask/API** service → Variables: either reference **MYSQL_URL** from the MySQL "
            "service (Railway’s canonical URL), or reference DATABASE_URL if your template exposes it — "
            "do not paste an old URL from your laptop.\n"
            "  3. If both DATABASE_URL and MYSQL_URL exist, DATABASE_URL wins; remove a wrong DATABASE_URL "
            "so the app can use MYSQL_URL, or fix DATABASE_URL to match the MySQL service.\n"
            "  4. Redeploy the API after saving.\n\n"
            "If you must paste a raw URL and the password contains @ : / ? # % or spaces, URL-encode those "
            "characters in the user:password segment."
        )
    return (
        "MySQL refused login (error 1045: access denied). Usually the password in the URL is wrong or "
        "broken by special characters (e.g. @ in the password must be written as %40 in the user:password part).\n\n"
        "For Railway from your PC: copy **MYSQL_PUBLIC_URL** (or DATABASE_PUBLIC_URL) from the MySQL service → "
        "Variables into backend/.env as DATABASE_URL=... or MYSQL_PUBLIC_URL=... (either key works; "
        "DATABASE_URL wins if both are set). No quotes. TLS for *.rlwy.net is enabled automatically; "
        "set MYSQL_SSL=1 to force TLS on other hosts, MYSQL_SSL=0 to turn off."
    )


def _mysql_unknown_database_message(exc: BaseException) -> str | None:
    """Return server message if exc is MySQL errno 1049 (unknown database), else None."""
    seen: set[int] = set()
    cur: BaseException | None = exc
    for _ in range(8):
        if cur is None or id(cur) in seen:
            break
        seen.add(id(cur))
        args = getattr(cur, "args", ())
        if len(args) >= 1 and args[0] == MYSQL_UNKNOWN_DATABASE:
            return str(args[1]) if len(args) > 1 else "Unknown database"
        cur = getattr(cur, "orig", None) or getattr(cur, "__cause__", None)
    return None


def _ensure_mysql_database(uri: str) -> None:
    """
    CREATE DATABASE IF NOT EXISTS for the DB name in DATABASE_URL.
    Connects to the built-in `mysql` schema using the same credentials (needs CREATE privilege).
    """
    from sqlalchemy import create_engine, text
    from sqlalchemy.engine.url import make_url

    if not uri.startswith(("mysql", "mariadb")):
        return

    url = make_url(uri)
    dbname = url.database
    if not dbname:
        return
    if not re.fullmatch(r"[A-Za-z0-9_]{1,64}", dbname):
        raise ValueError(
            "DATABASE_URL database segment must be 1-64 characters, letters, digits, or underscore only."
        )

    server_url = url.set(database="mysql")
    engine = create_engine(server_url, isolation_level="AUTOCOMMIT")
    try:
        with engine.connect() as conn:
            conn.execute(
                text(
                    f"CREATE DATABASE IF NOT EXISTS `{dbname}` "
                    "CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
                )
            )
        logger.info("MySQL database ready: %s", dbname)
    finally:
        engine.dispose()


def ensure_admin_user(email: str, password: str, full_name: str) -> bool:
    """
    Ensure a department exists and create the user if no account with this email exists.
    Must run inside Flask application context.
    Returns True if a new user was created, False if skipped (already exists).
    """
    from models.department import Department
    from models.user import User, UserRole
    from repositories.department_repository import DepartmentRepository
    from repositories.user_repository import UserRepository

    email = email.strip().lower()
    user_repo = UserRepository()
    if user_repo.get_by_email(email):
        return False

    dept_repo = DepartmentRepository()
    depts = dept_repo.list_all()
    if not depts:
        dept_repo.create(Department(name="General", description="Default department"))
        depts = dept_repo.list_all()
    dept = depts[0]

    u = User(
        email=email,
        full_name=full_name.strip() or "Admin",
        role=UserRole.ADMIN.value,
        department_id=dept.id,
        is_active=True,
        email_verified_at=datetime.now(timezone.utc),
    )
    u.set_password(password)
    user_repo.create(u)
    return True


def bootstrap_database(app: Flask) -> None:
    """
    Apply pending Alembic migrations, then seed default admin if missing.

    Migrations are the supported way to add tables/columns: each revision runs once and uses
    operations like ``CREATE TABLE`` / ``ADD COLUMN`` — they do not erase existing rows unless a
    migration script explicitly does so (avoid that in production). Use ``flask db migrate`` to
    autogenerate schema diffs, review them, then ``flask db upgrade`` (also runs on API startup).
    """
    from flask_migrate import upgrade
    from sqlalchemy.exc import OperationalError

    from config import Config

    with app.app_context():
        uri = str(app.config["SQLALCHEMY_DATABASE_URI"])
        if app.config.get("AUTO_CREATE_MYSQL_DATABASE", True) and uri.startswith(("mysql", "mariadb")):
            try:
                _ensure_mysql_database(uri)
            except Exception as e:
                if _mysql_errno_from_exception(e, MYSQL_ACCESS_DENIED):
                    logger.warning(
                        "Auto-create MySQL database skipped: access denied (1045). "
                        "Fix DATABASE_URL — migrations will fail until auth succeeds."
                    )
                else:
                    logger.warning("Auto-create MySQL database failed: %s", e)

        try:
            upgrade()
            logger.info(
                "Alembic upgrade finished: schema is up to date. "
                "Existing data is preserved; new migrations only add/alter what their scripts define."
            )
        except OperationalError as e:
            hint = _mysql_unknown_database_message(e)
            if hint is not None:
                raise RuntimeError(
                    "MySQL cannot use the database in DATABASE_URL (error 1049). "
                    "Either create it manually:\n"
                    "  CREATE DATABASE document_manager CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;\n"
                    "or enable AUTO_CREATE_MYSQL_DATABASE=true (default) and use a user with CREATE privilege.\n"
                    f"Server message: {hint}"
                ) from e
            if _mysql_errno_from_exception(e, MYSQL_ACCESS_DENIED):
                msg = _mysql_access_denied_help_text()
                logger.critical("%s", msg)
                raise RuntimeError(msg) from e
            raise
        email = app.config.get("DEFAULT_ADMIN_EMAIL", Config.DEFAULT_ADMIN_EMAIL)
        password = app.config.get("DEFAULT_ADMIN_PASSWORD", Config.DEFAULT_ADMIN_PASSWORD)
        name = app.config.get("DEFAULT_ADMIN_NAME", Config.DEFAULT_ADMIN_NAME)
        if ensure_admin_user(email, password, name):
            logger.info("Default admin created: %s", email.strip().lower())
        else:
            logger.debug("Default admin seed skipped (user already exists).")
