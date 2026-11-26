"""`Core`, the service without an interface, and `VoxoError`, what it tells its user."""

import fcntl
import os
from pathlib import Path


class VoxoError(Exception):
    """An error whose message is written for the user of a command."""


class Core:
    """Owns the data dir of one voxo.

    The data dir holds `voxo.lock`, held by the server that runs on it. Building a Core starts no work; only the
    server calls `start`.
    """

    def __init__(self, data_dir: Path) -> None:
        self.data_dir = data_dir.resolve()
        self.data_dir.mkdir(parents=True, exist_ok=True)

    def start(self) -> None:
        """Lock the data dir. Raises `VoxoError` when another server runs on it.

        The lock is held until the process exits, a crash included: `voxo stop` finds the server by it.
        """
        # A bare descriptor: a file object would drop the lock when collected. Nothing closes it; the exit of the
        # process does.
        fd = os.open(self.data_dir / "voxo.lock", os.O_RDWR | os.O_CREAT, 0o644)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as e:
            os.close(fd)
            raise VoxoError(f"{self.data_dir} is in use by another voxo: stop it first") from e
        # Written only under the lock, so a refused second server cannot wipe the pid of the first.
        os.ftruncate(fd, 0)
        os.write(fd, f"{os.getpid()}\n".encode())

    @staticmethod
    def server_pid(data_dir: Path) -> int | None:
        """The pid of the server that runs on *data_dir*, or None when none does."""
        lock = data_dir / "voxo.lock"
        if not lock.exists():
            return None
        with lock.open() as f:
            try:
                fcntl.flock(f, fcntl.LOCK_SH | fcntl.LOCK_NB)
            except BlockingIOError:
                return int(f.read())
        return None
