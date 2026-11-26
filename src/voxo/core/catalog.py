"""The speech models voxo knows, and how the files of each get into the data dir."""

import hashlib
import tarfile
import tempfile
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from voxo.core.errors import VoxoError


@dataclass(frozen=True)
class Model:
    """A speech model, as one archive of the `asr-models` release of the sherpa-onnx project."""

    id: str  # the name an app gives in a request
    archive: str  # the file in the release without `.tar.bz2`, which is also the one folder inside it
    sha256: str  # of the archive voxo was tried with: the release may get another file under the same name

    def folder(self, data_dir: Path) -> Path:
        """Where the files of the model are in the data dir. It exists only when the model is downloaded, and whole."""
        return data_dir / "models" / self.id

    def is_downloaded(self, data_dir: Path) -> bool:
        """Whether the files of the model are in the data dir."""
        return self.folder(data_dir).is_dir()

    def download(self, data_dir: Path, on_progress: Callable[[int], None]) -> None:
        """Fetch the archive from GitHub, check it, and unpack it as `folder`, which must not exist yet.

        Calls *on_progress* with the bytes fetched so far, about once per megabyte. Raises `VoxoError` when the
        download fails or the archive is not the one voxo was tried with. A failed download leaves nothing behind.
        """
        folder = self.folder(data_dir)
        folder.parent.mkdir(parents=True, exist_ok=True)
        # Beside the folder: the rename at the end stays on one disk, so the folder appears whole or not at all.
        with tempfile.TemporaryDirectory(dir=folder.parent, prefix=".download-") as tmp:
            archive = Path(tmp) / "archive.tar.bz2"
            digest = hashlib.sha256()
            try:
                with (
                    urllib.request.urlopen(
                        f"https://github.com/k2-fsa/sherpa-onnx/releases/download/asr-models/{self.archive}.tar.bz2",
                        timeout=60,  # seconds without a byte, not the whole download
                    ) as response,
                    archive.open("wb") as out,
                ):
                    while chunk := response.read(1 << 20):
                        out.write(chunk)
                        digest.update(chunk)
                        on_progress(out.tell())
            except OSError as e:
                raise VoxoError(f"cannot download {self.id}: {e}") from e
            if digest.hexdigest() != self.sha256:
                raise VoxoError(f"{self.id}: the downloaded archive is not the one voxo was tried with")
            with tarfile.open(archive) as tar:
                tar.extractall(tmp, filter="data")
            (Path(tmp) / self.archive).rename(folder)


MODELS = {
    model.id: model
    for model in (
        # GigaAM v3 of Sber, the variant that writes punctuation: Russian only. The encoder is int8.
        Model(
            "gigaam-v3",
            "sherpa-onnx-nemo-transducer-punct-giga-am-v3-russian-2025-12-16",
            "f9620a0099019c6afcee26525ef9ed3297fa50dd5691c1902af0c948fc1a470b",
        ),
        # Parakeet TDT 0.6B v3 of NVIDIA: 25 European languages, Russian and English among them. All of it is int8.
        Model(
            "parakeet-v3",
            "sherpa-onnx-nemo-parakeet-tdt-0.6b-v3-int8",
            "1495e91b59d7fc53ddca91f3431758ec99f8fa253fdb0e1e851be0f72b14b0f9",
        ),
    )
}
