"""The errors of core. Each client translates them in its own way."""


class VoxoError(Exception):
    """An error whose message is written for the user of a command, or for the app that sent a request."""


class UnauthorizedError(VoxoError):
    """The request does not carry the token of the service."""


class NotFoundError(VoxoError):
    """The request names something voxo does not have, such as a model or a dictation."""


class ConflictError(VoxoError):
    """The request is well formed, but voxo cannot do it as things are, such as with a model that is not downloaded."""


class InvalidError(VoxoError):
    """The data of the request is not in the form voxo takes."""
