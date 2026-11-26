"""Finds the pauses in speech with Silero VAD, run by sherpa-onnx, to split a dictation into phrases."""

import tempfile
from collections.abc import Callable
from pathlib import Path

import numpy as np
import sherpa_onnx
from numpy.typing import NDArray

from voxo.core.errors import ConflictError
from voxo.core.release import fetch

FILE = "silero_vad.onnx"  # the model of the VAD: its name in the data dir and in the release it comes from
RATE = 16000  # samples in a second of sound
WINDOW = 512  # samples the VAD hears at once: Silero VAD takes no other number at 16 kHz
PAUSE = RATE // 2  # samples of silence that end a phrase

type Sound = NDArray[np.float32]  # mono samples from -1 to 1


def download(data_dir: Path, on_progress: Callable[[int], None]) -> None:
    """Fetch the model of the VAD into the data dir; does nothing when it is there.

    Calls *on_progress* and raises `VoxoError` as `fetch` does. A failed download leaves nothing behind.
    """
    if (data_dir / FILE).exists():
        return
    # Beside the file: the rename at the end stays on one disk, so the file appears whole or not at all.
    with tempfile.TemporaryDirectory(dir=data_dir, prefix=".download-") as tmp:
        fetch(FILE, "9e2449e1087496d8d4caba907f23e0bd3f78d91fa552479bb9c23ac09cbb1fd6", Path(tmp) / FILE, on_progress)
        (Path(tmp) / FILE).rename(data_dir / FILE)


class Phrases:
    """Splits the sound of one dictation into phrases, as the sound comes piece by piece.

    A phrase ends at half a second of silence. One that lasts 20 seconds is cut there, and what follows is a new
    phrase.
    """

    def __init__(self, data_dir: Path) -> None:
        """Raises `ConflictError` when the model of the VAD is not in *data_dir*: `download` fetches it."""
        if not (data_dir / FILE).exists():
            raise ConflictError("voxo cannot find pauses yet: run `voxo download` with any model, it fetches what is needed")
        self._vad = sherpa_onnx.VadModel.create(
            sherpa_onnx.VadModelConfig(
                silero_vad=sherpa_onnx.SileroVadModelConfig(model=str(data_dir / FILE), min_silence_duration=PAUSE / RATE),
                sample_rate=RATE,
            )
        )
        self._speaking = False  # whether a phrase is being said
        # The windows of the phrase being said. In a pause, the last few windows heard: the start of the next phrase.
        self._windows: list[Sound] = []
        self._rest: Sound = np.empty(0, dtype=np.float32)  # the end of the sound, too short to fill a window

    def add(self, sound: Sound, *, last: bool) -> tuple[list[Sound], Sound | None]:
        """Take the next piece of the sound, of any length.

        Gives the phrases the piece ended, in the order said, and the phrase still being said as far as it got,
        or None when there is none. With *last* the sound is over: what was being said is an ended phrase, and
        this object is done.
        """
        sound = np.concatenate([self._rest, sound])
        ended: list[Sound] = []
        for start in range(0, len(sound) - WINDOW + 1, WINDOW):
            self._windows.append(sound[start : start + WINDOW])
            speech = self._vad.is_speech(self._windows[-1])
            if not self._speaking:
                if speech:
                    self._speaking = True
                else:
                    # The VAD says "speech" a quarter of a second into it: a third of a second kept from the pause
                    # holds the first sound of the phrase.
                    del self._windows[:-10]
            elif not speech:
                # The VAD says "no speech" when the silence has lasted as long as a pause: that silence is left out.
                ended.append(np.concatenate(self._windows)[:-PAUSE])
                self._windows = []
                self._speaking = False
            elif len(self._windows) * WINDOW >= 20 * RATE:  # the speech models take about 20 seconds at once
                ended.append(np.concatenate(self._windows))
                self._windows = []
        self._rest = sound[len(sound) - len(sound) % WINDOW :]
        if not (self._speaking and self._windows):
            return ended, None
        if last:
            return [*ended, np.concatenate([*self._windows, self._rest])], None
        return ended, np.concatenate(self._windows)
