"""The token of the service: one for all apps, kept as it is in the file `token` of the data dir."""

import os
import secrets
import tempfile
from pathlib import Path

FILE = "token"


def read(data_dir: Path) -> str | None:
    """The token, or None when none was made yet."""
    try:
        return (data_dir / FILE).read_text().strip() or None
    except FileNotFoundError:
        return None


def make(data_dir: Path) -> str:
    """Make a new token and put it in place of the one before, which stops being the token at once."""
    token = secrets.token_urlsafe(32)
    # Written beside the file and renamed: a reader sees the old token or the new one, never a part. A file of
    # `mkstemp` is readable only by its owner.
    fd, tmp = tempfile.mkstemp(dir=data_dir, prefix=".token-")
    with os.fdopen(fd, "w") as file:
        file.write(f"{token}\n")
    Path(tmp).replace(data_dir / FILE)
    return token
