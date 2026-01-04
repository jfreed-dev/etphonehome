"""Shared protocol definitions for ET Phone Home."""

from .protocol import (
    METHOD_HEARTBEAT,
    METHOD_LIST_FILES,
    METHOD_READ_FILE,
    METHOD_REGISTER,
    METHOD_RUN_COMMAND,
    METHOD_WRITE_FILE,
    ClientInfo,
    Request,
    Response,
)

__all__ = [
    "Request",
    "Response",
    "ClientInfo",
    "METHOD_RUN_COMMAND",
    "METHOD_READ_FILE",
    "METHOD_WRITE_FILE",
    "METHOD_LIST_FILES",
    "METHOD_HEARTBEAT",
    "METHOD_REGISTER",
]
