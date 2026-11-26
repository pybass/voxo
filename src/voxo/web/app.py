from importlib.metadata import version
from typing import Annotated

from fastapi import Body, FastAPI, Path, Query, Request
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse

from voxo.core.core import Core, DictationText, ModelStatus
from voxo.core.errors import ConflictError, InvalidError, NotFoundError, VoxoError


def create_app(core: Core) -> FastAPI:
    """The app of the local port over *core*: it asks for no token, so only this machine may reach it."""
    app = FastAPI(title="voxo", version=version("voxo"))
    # Without it a page of any site could use the service: it points its own host name at 127.0.0.1 (DNS rebinding).
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=["127.0.0.1", "localhost"])

    @app.exception_handler(VoxoError)
    def refuse(_request: Request, error: VoxoError) -> JSONResponse:
        # The one place where an error of core becomes an HTTP code. The body has the shape FastAPI gives its own errors.
        codes: dict[type[VoxoError], int] = {NotFoundError: 404, ConflictError: 409, InvalidError: 422}
        return JSONResponse({"detail": str(error)}, codes.get(type(error), 500))

    @app.get("/models")
    def models() -> list[ModelStatus]:
        """The models voxo knows. `id` is the name to give in a request.

        Only a model with `downloaded` true can be used; `voxo download` on the server fetches one.
        """
        return core.models()

    @app.post("/dictations/{dictation_id}")
    def dictate(
        dictation_id: Annotated[str, Path(max_length=64)],
        model: str,
        piece: Annotated[int, Query(ge=0)],
        sound: Annotated[bytes, Body(media_type="application/octet-stream")] = b"",
        last: bool = False,
    ) -> DictationText:
        """Add a piece of sound to a dictation and get the text it changed.

        The body is the sound, about half a second of it: mono, 16 kHz, 16-bit little-endian samples, no header.
        Make up `dictation_id`, new for each dictation, and number the pieces from 0 in `piece`. Piece 0 starts
        the dictation. Send the next piece only after the answer to the one before.

        voxo splits the speech into phrases at its pauses. `ended` holds the phrases this piece ended: their text
        is final, so add it to the text of the dictation. `current` is the phrase still being said: show it after
        that text, and replace it with the `current` of the next answer.

        `last=true` ends the dictation: what was being said comes in `ended`. The body may then be empty. When an
        answer does not arrive, send the same piece again: it adds no sound and gets the same answer. A dictation
        that gets no piece for 30 seconds is forgotten, and its next piece gets a 404.

        `model` may differ from piece to piece. A model is loaded at its first use, so that request is slower.
        """
        return core.dictate(dictation_id, model, piece, sound, last=last)

    return app
