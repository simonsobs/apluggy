from collections.abc import Iterable
from typing import Generic, Protocol, TypeVar

from apluggy.stack import GenCtxMngr

T = TypeVar('T', covariant=True)


class Stack(Protocol, Generic[T]):
    def __call__(self, ctxs: Iterable[GenCtxMngr[T]]) -> GenCtxMngr[list[T]]:
        ...
