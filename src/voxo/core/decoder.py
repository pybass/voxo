"""Reads a recording in any format with ffmpeg, a program that must be installed beside voxo."""

import shutil
import subprocess
import tempfile
from collections.abc import Iterator
from typing import BinaryIO

import numpy as np
from numpy.typing import NDArray

from voxo.core.errors import InvalidError, VoxoError


def decode(recording: BinaryIO) -> Iterator[NDArray[np.float32]]:
    """Give the sound of *recording* in pieces of about half a minute: mono 16 kHz samples from -1 to 1.

    *recording* is a file in any format ffmpeg reads; of a video, its sound is taken. The sound is read as the
    pieces are asked for, so a long recording never sits in memory whole. Raises `VoxoError` when ffmpeg is not
    installed, and `InvalidError` when it cannot read the recording; that error may come after some pieces.
    """
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg is None:
        raise VoxoError("ffmpeg is not installed: voxo reads a recording with it")
    # A copy with a name: ffmpeg must seek in the file, as an m4a keeps its index at the end.
    with tempfile.NamedTemporaryFile() as file, tempfile.TemporaryFile() as errors:
        shutil.copyfileobj(recording, file)
        file.flush()
        # Local files only: a recording may be a playlist, and ffmpeg would fetch what it names from the network.
        source = ["-protocol_whitelist", "file", "-i", file.name]
        # The errors go to a file: a pipe nobody reads would fill up and stop ffmpeg.
        with subprocess.Popen(  # noqa: S603 -- fixed argv, no shell
            [ffmpeg, "-nostdin", "-v", "error", *source, "-f", "s16le", "-ac", "1", "-ar", "16000", "pipe:1"],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=errors,
        ) as process:
            try:
                if process.stdout is None:
                    raise VoxoError("ffmpeg gave no output to read")
                while sound := process.stdout.read(1 << 20):
                    yield np.frombuffer(sound, dtype="<i2").astype(np.float32) / np.float32(32768)
                if process.wait():
                    errors.seek(0)
                    lines = errors.read().decode(errors="replace").strip().splitlines()
                    raise InvalidError(f"cannot read the recording: {lines[-1] if lines else 'ffmpeg failed'}")
            finally:
                # ffmpeg is still at work here when the caller stops asking for pieces.
                process.kill()
