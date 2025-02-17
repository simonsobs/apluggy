__all__ = ['asynccontextmanager']

import warnings
from contextlib import asynccontextmanager as _asynccontextmanager
from contextlib import contextmanager as _contextmanager


def asynccontextmanager(func):
    warnings.warn(
        'apluggy.asynccontextmanager is now the same as contextlib.asynccontextmanager',
        DeprecationWarning,
        stacklevel=2,
    )
    return _asynccontextmanager(func)


def contextmanager(func):
    warnings.warn(
        'apluggy.contextmanager is now the same as contextlib.contextmanager',
        DeprecationWarning,
        stacklevel=2,
    )
    return _contextmanager(func)
