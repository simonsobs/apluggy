from collections.abc import Iterable
from typing import Generic, Protocol, TypeVar

from apluggy.stack import AGenCtxMngr

T = TypeVar('T', covariant=True)


class AStack(Protocol, Generic[T]):
    def __call__(
        self,
        ctxs: Iterable[AGenCtxMngr[T]],
        fix_reraise: bool = True,
    ) -> AGenCtxMngr[list[T]]:
        ...
