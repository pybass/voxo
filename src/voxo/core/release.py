import hashlib
import urllib.request
from collections.abc import Callable
from pathlib import Path

from voxo.core.errors import VoxoError


def fetch(file: str, sha256: str, target: Path, on_progress: Callable[[int], None]) -> None:
    """Fetch *file* of the `asr-models` release of the sherpa-onnx project from GitHub and write it as *target*.

    *sha256* is of the file voxo was tried with: the release may get another file under the same name. Calls
    *on_progress* with the bytes fetched so far, about once per megabyte. Raises `VoxoError` when the download
    fails or the file is another one; *target* may then hold a part of it.
    """
    digest = hashlib.sha256()
    try:
        with (
            urllib.request.urlopen(
                f"https://github.com/k2-fsa/sherpa-onnx/releases/download/asr-models/{file}",
                timeout=60,  # seconds without a byte, not the whole download
            ) as response,
            target.open("wb") as out,
        ):
            while chunk := response.read(1 << 20):
                out.write(chunk)
                digest.update(chunk)
                on_progress(out.tell())
    except OSError as e:
        raise VoxoError(f"cannot download {file}: {e}") from e
    if digest.hexdigest() != sha256:
        raise VoxoError(f"{file}: the downloaded file is not the one voxo was tried with")
