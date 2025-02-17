import contextlib
from collections.abc import Generator, Iterable
from typing import Any, TypeVar

from apluggy.stack import GenCtxMngr

T = TypeVar('T')


@contextlib.contextmanager
def stack_exit_stack(ctxs: Iterable[GenCtxMngr[T]]) -> Generator[list[T], Any, Any]:
    '''A reference implementation of `stack_gen_ctxs` for tests.'''
    with contextlib.ExitStack() as stack:
        yield [stack.enter_context(ctx) for ctx in ctxs]
