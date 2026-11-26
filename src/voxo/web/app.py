from importlib.metadata import version

from fastapi import FastAPI
from fastapi.middleware.trustedhost import TrustedHostMiddleware


def create_app() -> FastAPI:
    """The HTTP interface of the local port: it asks for no token, so only this machine may reach it."""
    app = FastAPI(title="voxo", version=version("voxo"))
    # Without it a page of any site could use the service: it points its own host name at 127.0.0.1 (DNS rebinding).
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=["127.0.0.1", "localhost"])
    return app
