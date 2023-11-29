import contextlib
from collections.abc import Sequence
from typing import Generic, Protocol, TypeVar

T = TypeVar('T')

GenCtxMngr = contextlib._GeneratorContextManager


class Stack(Protocol, Generic[T]):
    def __call__(self, ctxs: Sequence[GenCtxMngr[T]]) -> GenCtxMngr[list[T]]:
        ...
