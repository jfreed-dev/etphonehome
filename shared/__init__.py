"""Shared protocol definitions for ET Phone Home."""

from .protocol import (
    Request,
    Response,
    ClientInfo,
    METHOD_RUN_COMMAND,
    METHOD_READ_FILE,
    METHOD_WRITE_FILE,
    METHOD_LIST_FILES,
    METHOD_HEARTBEAT,
    METHOD_REGISTER,
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
