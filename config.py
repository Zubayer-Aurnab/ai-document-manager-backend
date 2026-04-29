"""Application configuration loaded from environment."""
import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
# Always load backend/.env (not cwd), and override stale shell exports so DATABASE_URL matches the file.
load_dotenv(BASE_DIR / ".env", override=True)


def normalize_sqlite_database_uri(uri: str) -> str:
    """
    Resolve relative SQLite paths against BASE_DIR (this package root), not the process cwd.

    A relative URL like ``sqlite:///dev.db`` would otherwise create a different empty file whenever
    you start the app from another working directory — that looks like "all data disappeared".
    """
    from sqlalchemy.engine.url import make_url

    try:
        url = make_url(uri)
    except Exception:
        return uri
    if not url.drivername.startswith("sqlite"):
        return uri
    database = url.database
    if not database or database == ":memory:":
        return uri
    path = Path(database)
    if not path.is_absolute():
        # Single-segment names (e.g. dev.db) live under backend/instance/, same as the default URI.
        if len(path.parts) == 1:
            inst = BASE_DIR / "instance"
            inst.mkdir(parents=True, exist_ok=True)
            path = (inst / path).resolve()
        else:
            path = (BASE_DIR / path).resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    return str(url.set(database=str(path)))


def normalize_mysql_pymysql_uri(uri: str) -> str:
    """
    Railway (and others) often supply ``mysql://...``, which SQLAlchemy resolves to the ``MySQLdb``
    driver. This project uses PyMySQL only — coerce to ``mysql+pymysql``.
    """
    from sqlalchemy.engine.url import make_url

    try:
        url = make_url(uri)
    except Exception:
        return uri
    if url.drivername in ("mysql", "mysql+mysqldb"):
        return str(url.set(drivername="mysql+pymysql"))
    return uri


def _stripped_env(key: str) -> str | None:
    v = os.environ.get(key)
    if v is None:
        return None
    s = str(v).strip()
    return s if s else None


def _mysql_url_from_discrete_railway_vars() -> str | None:
    """Build mysql+pymysql URL from Railway-style MYSQLHOST / MYSQLUSER / MYSQLPASSWORD / MYSQLDATABASE / MYSQLPORT."""
    from sqlalchemy.engine.url import URL

    host = _stripped_env("MYSQLHOST")
    user = _stripped_env("MYSQLUSER")
    db = _stripped_env("MYSQLDATABASE")
    if not host or not user or not db:
        return None
    if "MYSQLPASSWORD" not in os.environ:
        return None
    password = os.environ.get("MYSQLPASSWORD", "")
    port_s = _stripped_env("MYSQLPORT")
    try:
        port = int(port_s) if port_s else 3306
    except ValueError:
        port = 3306
    return str(
        URL.create(
            "mysql+pymysql",
            username=user,
            password=password,
            host=host,
            port=port,
            database=db,
            query={"charset": "utf8mb4"},
        )
    )


def resolve_database_url_from_env() -> str | None:
    """
    First non-empty wins: DATABASE_URL, then Railway public / private URL vars, then discrete MYSQL_*.
    Returns None to use the SQLite default path.
    """
    for key in (
        "DATABASE_URL",
        "MYSQL_PUBLIC_URL",
        "DATABASE_PUBLIC_URL",
        "MYSQL_URL",
        "DATABASE_PRIVATE_URL",
    ):
        u = _stripped_env(key)
        if u:
            return u
    return _mysql_url_from_discrete_railway_vars()


def _mysql_ssl_connect_args(db_uri: str) -> dict:
    """
    Railway’s public MySQL TCP proxy (hostnames under *.rlwy.net) expects TLS. PyMySQL may not
    negotiate that unless ``ssl`` is passed — some setups surface that as 1045 instead of a TLS error.

    MYSQL_SSL: ``1``/``true`` force TLS (insecure verify, dev-friendly); ``0``/``false`` disable;
    default ``auto`` enables for *.rlwy.net hosts only.
    """
    flag = os.environ.get("MYSQL_SSL", "auto").strip().lower()
    if flag in ("0", "false", "no", "off"):
        return {}
    from sqlalchemy.engine.url import make_url

    try:
        url = make_url(db_uri)
    except Exception:
        return {}
    host = (url.host or "").lower()
    if not host:
        return {}
    force = flag in ("1", "true", "yes", "on")
    auto = flag in ("", "auto") and "rlwy.net" in host
    if not (force or auto):
        return {}
    import ssl

    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return {"ssl": ctx}


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-change-me")
    JWT_SECRET_KEY = os.environ.get("JWT_SECRET_KEY", "dev-jwt-secret-change-me")
    JWT_ACCESS_TOKEN_EXPIRES = int(os.environ.get("JWT_ACCESS_EXPIRES_MIN", "60")) * 60
    JWT_REFRESH_TOKEN_EXPIRES = int(os.environ.get("JWT_REFRESH_EXPIRES_DAYS", "30")) * 86400

    # Prefer DATABASE_URL (e.g. MySQL). Example:
    #   mysql+pymysql://user:password@127.0.0.1:3306/document_manager?charset=utf8mb4
    # If true (default), startup runs CREATE DATABASE IF NOT EXISTS for that name (user needs CREATE privilege).
    AUTO_CREATE_MYSQL_DATABASE = os.environ.get("AUTO_CREATE_MYSQL_DATABASE", "true").lower() in (
        "1",
        "true",
        "yes",
    )

    _db_url = resolve_database_url_from_env()
    if not _db_url:
        instance_dir = BASE_DIR / "instance"
        instance_dir.mkdir(exist_ok=True)
        _db_url = os.environ.get(
            "SQLITE_URI",
            f"sqlite:///{instance_dir / 'dev.db'}",
        )
    _db_url = normalize_sqlite_database_uri(_db_url)
    _db_url = normalize_mysql_pymysql_uri(_db_url)
    SQLALCHEMY_DATABASE_URI = _db_url
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    _mysql_family = _db_url.startswith(("mysql", "mariadb"))
    if _mysql_family:
        _mysql_opts: dict = {"pool_pre_ping": True, "pool_recycle": 280}
        _ssl = _mysql_ssl_connect_args(_db_url)
        if _ssl:
            _mysql_opts["connect_args"] = _ssl
        SQLALCHEMY_ENGINE_OPTIONS = _mysql_opts
    else:
        SQLALCHEMY_ENGINE_OPTIONS = {}

    # Default admin (created on startup if no user with this email exists). Override in production.
    DEFAULT_ADMIN_EMAIL = os.environ.get("DEFAULT_ADMIN_EMAIL", "admin@apptriangle.com")
    DEFAULT_ADMIN_PASSWORD = os.environ.get("DEFAULT_ADMIN_PASSWORD", "admin123")
    DEFAULT_ADMIN_NAME = os.environ.get("DEFAULT_ADMIN_NAME", "System Admin")

    MAX_CONTENT_LENGTH = int(os.environ.get("MAX_UPLOAD_MB", "50")) * 1024 * 1024
    STORAGE_PATH = Path(os.environ.get("STORAGE_PATH", BASE_DIR / "storage" / "uploads"))
    FRONTEND_URL = os.environ.get("FRONTEND_URL", "http://localhost:3000")

    # Brevo transactional email (https://app.brevo.com/settings/keys/api)
    BREVO_API_KEY = os.environ.get("BREVO_API_KEY", "")
    BREVO_SENDER_EMAIL = os.environ.get("BREVO_SENDER_EMAIL", "")
    BREVO_SENDER_NAME = os.environ.get("BREVO_SENDER_NAME", "Document Manager")

    ALLOWED_EXTENSIONS = frozenset(
        {
            "pdf",
            "doc",
            "docx",
            "xls",
            "xlsx",
            "csv",
            "jpg",
            "jpeg",
            "png",
        }
    )
    ALLOWED_MIME_PREFIXES = ("image/", "application/pdf", "text/csv")
    ALLOWED_MIME_TYPES = frozenset(
        {
            "application/pdf",
            "application/msword",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "application/vnd.ms-excel",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            "text/csv",
            "image/jpeg",
            "image/png",
        }
    )

    # Groq (https://console.groq.com/) — AI search re-ranking over authorized keyword matches
    GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "").strip()
    GROQ_MODEL = os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile").strip()
    GROQ_AI_SEARCH_CANDIDATE_LIMIT = int(os.environ.get("GROQ_AI_SEARCH_CANDIDATE_LIMIT", "40"))
    GROQ_TIMEOUT_SEC = int(os.environ.get("GROQ_TIMEOUT_SEC", "45"))
