"""`Core`, the API of the whole app, and the types its methods return."""

import fcntl
import os
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from voxo.core import pauses
from voxo.core.catalog import MODELS, Model
from voxo.core.errors import ConflictError, InvalidError, NotFoundError, VoxoError
from voxo.core.pauses import Phrases
from voxo.core.recognizer import Recognizer


@dataclass(frozen=True)
class ModelStatus:
    """A model voxo knows, and whether it can be used."""

    id: str  # the name an app gives in a request
    downloaded: bool  # whether all it needs is in the data dir; only then the model can be used
    downloading: int | None  # bytes fetched so far of the file a download in this process fetches now; None when none runs


@dataclass(frozen=True)
class DictationText:
    """What a piece of sound changed in the text of a dictation."""

    ended: list[str]  # the phrases the piece ended, in the order said; the text of each is final
    current: str  # the phrase still being said, as far as it got: the next piece gives it anew; empty in a pause


@dataclass
class _Dictation:
    """What voxo keeps of one dictation between its pieces."""

    phrases: Phrases
    used: float  # `time.monotonic()` of the latest piece
    lock: threading.Lock = field(default_factory=threading.Lock)  # held while a piece is worked on
    pieces: int = 0  # how many pieces were taken, which is the number of the next one
    answer: DictationText | None = None  # to the latest piece, for when it is sent again
    over: bool = False  # the last piece was taken


class Core:
    """The whole app without an interface: every operation is a method here, for the command line and the web app.

    The data dir holds `voxo.lock`, held by the server that runs on it; the rest of it belongs to the modules beside
    this one. Building a Core starts no work; only the server calls `start`. The methods may be called from several
    threads at once. A method raises `VoxoError` with a message for the user.
    """

    def __init__(self, data_dir: Path) -> None:
        self._data_dir = data_dir.resolve()
        self._data_dir.mkdir(parents=True, exist_ok=True)
        self._recognizers: dict[str, Recognizer] = {}  # by model id; a model stays in memory once loaded
        self._recognizers_lock = threading.Lock()  # held while a model loads, so no model is loaded twice
        self._dictations: dict[str, _Dictation] = {}
        self._dictations_lock = threading.Lock()
        self._downloading: dict[str, int] = {}  # by model id: the bytes fetched so far of the file being fetched
        self._download_lock = threading.Lock()  # held by a download: the next one waits, then skips what is there

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
        vad = pauses.is_downloaded(self._data_dir)
        return [
            ModelStatus(model.id, vad and model.is_downloaded(self._data_dir), self._downloading.get(model.id))
            for model in MODELS.values()
        ]

    def download(self, model_id: str, on_progress: Callable[[int], None]) -> None:
        """Fetch into the data dir the files of a model, and what finds the pauses; skips what is there. Needs the network.

        Calls *on_progress* with the bytes fetched so far of the file being fetched, about once per megabyte; `models`
        gives the same number meanwhile. Works while a server runs on the data dir: it sees the model as soon as this
        returns. One download runs at a time in a process: the next one waits. Raises `VoxoError` for an unknown
        model, a failed download, or a file that is not the one voxo was tried with.
        """
        model = Model.named(model_id)

        def progress(fetched: int) -> None:
            self._downloading[model_id] = fetched
            on_progress(fetched)

        with self._download_lock:
            try:
                pauses.download(self._data_dir, progress)
                if not model.is_downloaded(self._data_dir):
                    model.download(self._data_dir, progress)
            finally:
                self._downloading.pop(model_id, None)

    def dictate(self, dictation_id: str, model_id: str, piece: int, sound: bytes, *, last: bool) -> DictationText:
        """Add a piece of sound to a dictation and recognize what it changed.

        *sound* is mono 16 kHz speech as 16-bit little-endian samples. The caller makes up *dictation_id* and
        numbers the pieces from 0. Piece 0 starts the dictation. The piece with *last* ends it: what was being said
        is given as an ended phrase. The latest piece sent again, as after a network failure, adds no sound and
        gets the same answer. A dictation is forgotten 30 seconds after its latest piece.

        The model may differ from piece to piece. It is loaded into memory at its first use, which makes that call
        slower, and stays there. Raises `NotFoundError` for an unknown model or dictation, `ConflictError` for a model
        that is not downloaded or a piece out of turn, and `InvalidError` for sound that is not whole samples.
        """
        model = Model.named(model_id)
        if len(sound) % 2:
            raise InvalidError("the sound must be 16-bit samples, but its length in bytes is odd")
        with self._recognizers_lock:
            if model_id not in self._recognizers:
                if not model.is_downloaded(self._data_dir):
                    raise ConflictError(f"{model_id} is not downloaded: run `voxo download {model_id}`")
                # 4 threads were about 2.5 times faster than one, and the server voxo is meant for has 4 cores.
                threads = min(4, os.process_cpu_count() or 1)
                self._recognizers[model_id] = Recognizer(**model.files(self._data_dir), threads=threads)
            recognizer = self._recognizers[model_id]
        now = time.monotonic()
        with self._dictations_lock:
            for stale in [key for key, dictation in self._dictations.items() if now - dictation.used > 30]:
                del self._dictations[stale]
            dictation = self._dictations.get(dictation_id)
            if dictation is None:
                if piece:
                    raise NotFoundError(
                        f"unknown dictation {dictation_id}: one starts with piece 0 and is forgotten after 30 idle seconds"
                    )
                dictation = self._dictations[dictation_id] = _Dictation(Phrases(self._data_dir), now)
            dictation.used = now
        with dictation.lock:
            if dictation.answer is not None and piece == dictation.pieces - 1:
                return dictation.answer
            if dictation.over:
                raise ConflictError(f"dictation {dictation_id} is over: piece {dictation.pieces - 1} was its last")
            if piece != dictation.pieces:
                raise ConflictError(f"dictation {dictation_id} waits for piece {dictation.pieces}, not {piece}")
            samples = np.frombuffer(sound, dtype="<i2").astype(np.float32) / np.float32(32768)
            ended, current = dictation.phrases.add(samples, last=last)
            # The VAD takes some noise for speech, and the model then hears no words in it: such a phrase is left out.
            texts = [text for phrase in ended if (text := recognizer.recognize(phrase))]
            dictation.answer = DictationText(texts, "" if current is None else recognizer.recognize(current))
            dictation.pieces += 1
            dictation.over = last
            return dictation.answer
