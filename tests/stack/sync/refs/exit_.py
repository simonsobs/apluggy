import contextlib
from collections.abc import Generator, Sequence
from typing import Any, TypeVar

from apluggy.stack import GenCtxMngr

T = TypeVar('T')


@contextlib.contextmanager
def exit_stack(ctxs: Sequence[GenCtxMngr[T]]) -> Generator[list[T], Any, Any]:
    with contextlib.ExitStack() as stack:
        yield [stack.enter_context(ctx) for ctx in ctxs]
