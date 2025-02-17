__all__ = ['asynccontextmanager']

import warnings
from contextlib import asynccontextmanager as _asynccontextmanager


def asynccontextmanager(func):

    warnings.warn(
        'apluggy.asynccontextmanager is now the same as contextlib.asynccontextmanager',
        DeprecationWarning,
        stacklevel=2,
    )
    return _asynccontextmanager(func)
