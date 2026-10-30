"""Enabled app tests use a disposable real SQLite file for concurrency evidence."""

import os
import tempfile
from pathlib import Path

from .settings import *  # noqa: F403

DATABASES["default"]["TEST"] = {  # noqa: F405
    "NAME": Path(tempfile.gettempdir()) / f"macromapper-mcp-test-{os.getpid()}.sqlite3"
}
