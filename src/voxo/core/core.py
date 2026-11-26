"""`Core`, the API of the whole app, and the types its methods return."""

import fcntl
import os
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from voxo.core.catalog import MODELS
from voxo.core.errors import VoxoError


@dataclass(frozen=True)
class ModelStatus:
    """A model voxo knows, and whether it can be used."""

    id: str  # the name an app gives in a request
    downloaded: bool  # whether its files are in the data dir; only then the model can be used


class Core:
    """The whole app without an interface: every operation is a method here, for the command line and the web app.

    The data dir holds `voxo.lock`, held by the server that runs on it; the rest of it belongs to the modules beside
    this one. Building a Core starts no work; only the server calls `start`. A method raises `VoxoError` with a
    message for the user.
    """

    def __init__(self, data_dir: Path) -> None:
        self._data_dir = data_dir.resolve()
        self._data_dir.mkdir(parents=True, exist_ok=True)

    def start(self) -> None:
        """Lock the data dir. Raises `VoxoError` when another server runs on it.

        The lock is held until the process exits, a crash included: `voxo stop` finds the server by it.
        """
        # A bare descriptor: a file object would drop the lock when collected. Nothing closes it; the exit of the
        # process does.
        fd = os.open(self._data_dir / "voxo.lock", os.O_RDWR | os.O_CREAT, 0o644)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as e:
            os.close(fd)
            raise VoxoError(f"{self._data_dir} is in use by another voxo: stop it first") from e
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

    def models(self) -> list[ModelStatus]:
        """Every model voxo knows."""
        return [ModelStatus(model.id, model.is_downloaded(self._data_dir)) for model in MODELS.values()]

    def download(self, model_id: str, on_progress: Callable[[int], None]) -> None:
        """Fetch the files of a model into the data dir; does nothing when they are there. Needs the network.

        Calls *on_progress* with the bytes fetched so far, about once per megabyte. Works while a server runs on
        the data dir: it sees the model as soon as this returns. Raises `VoxoError` for an unknown model, a failed
        download, or an archive that is not the one voxo was tried with.
        """
        model = MODELS.get(model_id)
        if model is None:
            raise VoxoError(f"unknown model {model_id}: voxo knows {', '.join(MODELS)}")
        if not model.is_downloaded(self._data_dir):
            model.download(self._data_dir, on_progress)
