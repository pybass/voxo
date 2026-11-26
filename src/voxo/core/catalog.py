"""The speech models voxo knows, and how the files of each get into the data dir."""

import tarfile
import tempfile
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from voxo.core.errors import NotFoundError
from voxo.core.release import fetch


@dataclass(frozen=True)
class Model:
    """A speech model, as one archive of the `asr-models` release of the sherpa-onnx project."""

    id: str  # the name an app gives in a request
    archive: str  # the file in the release without `.tar.bz2`, which is also the one folder inside it
    sha256: str  # of the archive voxo was tried with
    encoder: str  # this and the two below: the files of the three networks in the folder
    decoder: str
    joiner: str

    @staticmethod
    def named(model_id: str) -> Model:
        """The model an app calls *model_id*. Raises `NotFoundError` when voxo knows none by that name."""
        model = MODELS.get(model_id)
        if model is None:
            raise NotFoundError(f"unknown model {model_id}: voxo knows {', '.join(MODELS)}")
        return model

    def folder(self, data_dir: Path) -> Path:
        """Where the files of the model are in the data dir. It exists only when the model is downloaded, and whole."""
        return data_dir / "models" / self.id

    def is_downloaded(self, data_dir: Path) -> bool:
        """Whether the files of the model are in the data dir."""
        return self.folder(data_dir).is_dir()

    def files(self, data_dir: Path) -> dict[str, Path]:
        """The files of the downloaded model by what each holds: `encoder`, `decoder`, `joiner` and `tokens`."""
        folder = self.folder(data_dir)
        return {
            "encoder": folder / self.encoder,
            "decoder": folder / self.decoder,
            "joiner": folder / self.joiner,
            "tokens": folder / "tokens.txt",
        }

    def download(self, data_dir: Path, on_progress: Callable[[int], None]) -> None:
        """Fetch the archive, check it, and unpack it as `folder`, which must not exist yet.

        Calls *on_progress* and raises `VoxoError` as `fetch` does. A failed download leaves nothing behind.
        """
        folder = self.folder(data_dir)
        folder.parent.mkdir(parents=True, exist_ok=True)
        # Beside the folder: the rename at the end stays on one disk, so the folder appears whole or not at all.
        with tempfile.TemporaryDirectory(dir=folder.parent, prefix=".download-") as tmp:
            archive = Path(tmp) / "archive.tar.bz2"
            fetch(f"{self.archive}.tar.bz2", self.sha256, archive, on_progress)
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
            "encoder.int8.onnx",
            "decoder.onnx",
            "joiner.onnx",
        ),
        # Parakeet TDT 0.6B v3 of NVIDIA: 25 European languages, Russian and English among them. All of it is int8.
        Model(
            "parakeet-v3",
            "sherpa-onnx-nemo-parakeet-tdt-0.6b-v3-int8",
            "1495e91b59d7fc53ddca91f3431758ec99f8fa253fdb0e1e851be0f72b14b0f9",
            "encoder.int8.onnx",
            "decoder.int8.onnx",
            "joiner.int8.onnx",
        ),
    )
}
