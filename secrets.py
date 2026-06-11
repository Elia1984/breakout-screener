from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

try:
    import tomllib
except ModuleNotFoundError:
    import tomli as tomllib


LOGGER = logging.getLogger(__name__)
_LOCAL_SECRETS_CACHE: dict[Path, dict[str, Any]] = {}


def load_local_secrets(project_root: str | Path) -> dict[str, Any]:
    """Read local Streamlit secrets without ever committing them to source.

    Streamlit Cloud uses its own secrets UI. This local fallback is only for the
    user's Mac, and the file is covered by ``.gitignore``.
    """
    root = Path(project_root).resolve()
    if root in _LOCAL_SECRETS_CACHE:
        return _LOCAL_SECRETS_CACHE[root]

    path = root / ".streamlit" / "secrets.toml"
    if not path.exists():
        _LOCAL_SECRETS_CACHE[root] = {}
        return _LOCAL_SECRETS_CACHE[root]

    try:
        with path.open("rb") as file:
            data = tomllib.load(file)
    except Exception as exc:
        LOGGER.warning("Could not read local Streamlit secrets: %s", exc)
        data = {}

    _LOCAL_SECRETS_CACHE[root] = data
    return data


def read_secret(
    name: str,
    *,
    streamlit_secrets: Any = None,
    project_root: str | Path | None = None,
    default: str = "",
) -> str:
    """Read a secret from Streamlit, then environment, then local secrets.toml."""
    if streamlit_secrets is not None:
        try:
            value = streamlit_secrets.get(name)
        except Exception:
            value = None
        if value not in {None, ""}:
            return str(value)

    value = os.environ.get(name)
    if value:
        return str(value)

    if project_root is not None:
        value = load_local_secrets(project_root).get(name, default)
        return str(value or default)

    return str(default)

