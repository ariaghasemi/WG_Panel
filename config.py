import hashlib
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
INSTANCE_DIR = os.path.join(BASE_DIR, "instance")
os.makedirs(INSTANCE_DIR, exist_ok=True)

def _norm_sqlite(uri: str) -> str:
    if not uri or not uri.startswith("sqlite:///"):
        return uri
    path = uri[len("sqlite:///"):]
    if not os.path.isabs(path):
        if path.startswith("instance/"):
            path = os.path.join(INSTANCE_DIR, path.split("instance/", 1)[1])
        else:
            path = os.path.join(BASE_DIR, path)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    return "sqlite:///" + path

def _session_secret() -> str | None:
    """Return a stable Flask session key.

    An explicitly configured FLASK_SECRET_KEY is preferred. Push-to-deploy
    dashboards commonly create this variable with an empty value, though. In
    that case derive a domain-separated key from the required FERNET_KEY. A
    Fernet key already has sufficient entropy and is stable across restarts, so
    this is safer than either disabling sessions or generating an ephemeral key.
    """
    configured = os.environ.get("FLASK_SECRET_KEY", "").strip()
    if configured:
        return configured

    fernet_key = os.environ.get("FERNET_KEY", "").strip()
    if not fernet_key:
        return None

    return hashlib.sha256(
        b"WG_Panel Flask session key\x00" + fernet_key.encode("utf-8")
    ).hexdigest()


class Config:
    SECRET_KEY = _session_secret()
    SQLALCHEMY_DATABASE_URI = _norm_sqlite(
        os.environ.get("DATABASE_URL", f"sqlite:///{os.path.join(INSTANCE_DIR, 'wg_panel.db')}")
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    WG_CONF_PATH = os.environ.get("WIREGUARD_CONF_PATH", "/etc/wireguard/")
    API_KEY = os.environ.get("API_KEY", "")
    LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO")
    SECURE_COOKIES = bool(int(os.environ.get("SECURE_COOKIES", "0")))
    SETUP_TOKEN = os.environ.get("SETUP_TOKEN", "")
    TG_HEARTBEAT_SEC = int(os.environ.get("TG_HEARTBEAT_SEC", "60"))
