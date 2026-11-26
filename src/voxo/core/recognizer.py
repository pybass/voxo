import threading
from pathlib import Path

import numpy as np
import sherpa_onnx
from numpy.typing import NDArray


class Recognizer:
    """A speech model in memory, run by sherpa-onnx: it turns speech into text.

    Building one loads the model, which is slow: build it once and keep it. It runs one recognition at a time, so
    the threads of two never fight for the same cores.
    """

    def __init__(self, encoder: Path, decoder: Path, joiner: Path, tokens: Path, threads: int) -> None:
        self._recognizer = sherpa_onnx.OfflineRecognizer.from_transducer(
            encoder=str(encoder),
            decoder=str(decoder),
            joiner=str(joiner),
            tokens=str(tokens),
            model_type="nemo_transducer",
            num_threads=threads,
        )
        self._lock = threading.Lock()

    def recognize(self, speech: NDArray[np.float32]) -> str:
        """The text of *speech*: mono 16 kHz samples from -1 to 1, about 20 seconds at most.

        Waits while another recognition runs.
        """
        with self._lock:
            stream = self._recognizer.create_stream()
            stream.accept_waveform(16000, speech)
            self._recognizer.decode_stream(stream)
            text: str = stream.result.text
        return text.strip()
