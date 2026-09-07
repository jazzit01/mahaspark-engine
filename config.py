import os
from pathlib import Path


def load_env_file(env_path: str | os.PathLike[str] | None = None) -> None:
    """Load environment variables from a local .env file when present."""
    target = Path(env_path) if env_path else Path(".env")

    if not target.exists():
        return

    for line in target.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")

        os.environ.setdefault(key, value)


def get_env_value(name: str, default: str | None = None) -> str:
    """Return environment variable if set, else default."""
    value = os.getenv(name)
    if value is not None:
        return value
    return default if default is not None else ""


load_env_file()
