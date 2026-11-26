from importlib.metadata import version

from fastapi import FastAPI
from fastapi.middleware.trustedhost import TrustedHostMiddleware

from voxo.core.core import Core, ModelStatus


def create_app(core: Core) -> FastAPI:
    """The app of the local port over *core*: it asks for no token, so only this machine may reach it."""
    app = FastAPI(title="voxo", version=version("voxo"))
    # Without it a page of any site could use the service: it points its own host name at 127.0.0.1 (DNS rebinding).
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=["127.0.0.1", "localhost"])

    @app.get("/models")
    def models() -> list[ModelStatus]:
        """The models voxo knows. `id` is the name to give in a request.

        Only a model with `downloaded` true can be used; `voxo download` on the server fetches one.
        """
        return core.models()

    return app
