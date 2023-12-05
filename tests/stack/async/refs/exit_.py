import asyncio
import contextlib
from collections.abc import AsyncGenerator, Iterable
from typing import Any, TypeVar

from .types import AGenCtxMngr

T = TypeVar('T')


@contextlib.asynccontextmanager
async def exit_stack(
    ctxs: Iterable[AGenCtxMngr[T]],
    fix_reraise: bool = False,
) -> AsyncGenerator[list[T], Any]:
    # assert not fix_reraise
    async with contextlib.AsyncExitStack() as stack:
        # yield [await stack.enter_async_context(ctx) for ctx in ctxs]
        yield list(
            await asyncio.gather(*(stack.enter_async_context(ctx) for ctx in ctxs))
        )
