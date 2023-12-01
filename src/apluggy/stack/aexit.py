import contextlib

from .types import AGenCtxMngr


@contextlib.contextmanager
def patch_aexit(ctx: AGenCtxMngr):
    _org_aexit = ctx.__aexit__

    async def aexit(*exc_info):
        with _patch_gen(ctx):
            return await _org_aexit(*exc_info)

    ctx.__aexit__ = aexit  # type: ignore
    try:
        yield
    finally:
        ctx.__aexit__ = _org_aexit  # type: ignore


@contextlib.contextmanager
def _patch_gen(ctx: AGenCtxMngr):
    _org_gen = ctx.gen

    class Gen:
        async def __anext__(self):
            return await anext(_org_gen)

        async def athrow(self, typ, val=None, tb=None):
            await _org_gen.athrow(typ, val, tb)
            # athrow() didn't raise.
            try:
                await anext(_org_gen)  # Check if the generator is exhausted.
            except StopAsyncIteration:
                # The generator is exhausted. But don't raise the exception
                # raised by anext() because __aexit__() distinguishes the
                # instances of StopAsyncIteration. Raise the original
                # exception instead.
                pass
            if isinstance(typ, type):  # The old signature deprecated in 3.12
                raise val.with_traceback(tb)
            raise typ  # The only argument is val in the new signature

    ctx.gen = Gen()  # type: ignore
    try:
        yield
    finally:
        ctx.gen = _org_gen
