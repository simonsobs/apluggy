from collections.abc import Iterable, Sequence
from functools import partial
from typing import Optional, Union

from hypothesis import note
from hypothesis import strategies as st

from .ctx_id import CtxId
from .exc import (
    AsyncGenAsendWithoutYield,
    AsyncGenRaiseOnASend,
    ExceptionExpectation,
    GeneratorDidNotYield,
    GenSendWithoutYield,
    wrap_exc,
)
from .except_ import ExceptActionName, ExceptionHandler, st_exception_handler


class ExitHandler:
    def __init__(
        self,
        data: st.DataObject,
        async_: bool,
        enabled_except_actions_on_enter: Sequence[ExceptActionName],
        enabled_except_actions_on_sent: Sequence[ExceptActionName],
        enabled_except_actions_on_raised: Sequence[ExceptActionName],
    ) -> None:
        self._draw = data.draw
        self._async = async_
        self._SendWithoutYield = (
            AsyncGenAsendWithoutYield if async_ else GenSendWithoutYield
        )
        self._st_exc_handler_on_enter = partial(
            st_exception_handler,
            enabled_actions=enabled_except_actions_on_enter,
        )
        self._st_exc_handler_on_sent = partial(
            st_exception_handler,
            enabled_actions=enabled_except_actions_on_sent,
        )
        self._st_exc_handler_on_raised = partial(
            st_exception_handler,
            enabled_actions=enabled_except_actions_on_raised,
        )
        self.clear()

    def clear(self) -> None:
        self._expected: Optional[_Expected] = None
        self._exc_handler: Optional[ExceptionHandler] = None
        self._ctx_ids: list[CtxId] = []

    def expect_exit_on_enter(self, entered_ctx_ids: Sequence[CtxId]) -> None:
        '''A context exits without yielding on enter.'''
        self.expect_raise_on_enter(entered_ctx_ids, wrap_exc(GeneratorDidNotYield))

    def expect_raise_on_enter(
        self, entered_ctx_ids: Sequence[CtxId], exp_exc: ExceptionExpectation
    ) -> None:
        '''A context raises an exception on enter.

        The exception will be propagated to the contexts that have already been
        entered in reverse order.
        '''
        ctx_ids = list(reversed(entered_ctx_ids))
        suspended_ctx_ids = ctx_ids[1:]

        exc_handler = self._draw(
            self._st_exc_handler_on_enter(exp=exp_exc, ids=suspended_ctx_ids)
        )

        exp_on_handle = wrap_exc(GeneratorDidNotYield)
        exc_expected = exc_handler.expect_outermost_exc(exp_on_handle=exp_on_handle)

        #
        self._expected = _Expected(ctx_ids, exc_expected)
        self._exc_handler = exc_handler

    def expect_raise_in_with_block(
        self, entered_ctx_ids: Sequence[CtxId], exp_exc: ExceptionExpectation
    ):
        '''An exception is raised in the `with` block.

        The exception will be propagated from the innermost context to the outermost
        context.
        '''
        ctx_ids = list(reversed(entered_ctx_ids))
        exc_handler = self._draw(
            self._st_exc_handler_on_raised(exp=exp_exc, ids=ctx_ids)
        )
        exc_expected = exc_handler.expect_outermost_exc()

        #
        self._expected = _Expected(ctx_ids, exc_expected)
        self._exc_handler = exc_handler

    def expect_send_without_ctx(self) -> None:
        '''`gen.send()` is called while no context is entered.'''
        exc_expected = wrap_exc(self._SendWithoutYield)
        self._expected = _Expected([], exc_expected)

    def expect_exit_on_sent(
        self,
        exiting_ctx_id: CtxId,
        entered_ctx_ids: Sequence[CtxId],
    ) -> None:
        '''A context exits without yielding on sent.'''
        suspended_ctx_ids = [id for id in entered_ctx_ids if id != exiting_ctx_id]
        ctx_ids = [exiting_ctx_id, *reversed(suspended_ctx_ids)]
        exc_expected = wrap_exc(self._SendWithoutYield)
        self._expected = _Expected(ctx_ids, exc_expected)

    def expect_raise_on_sent(
        self,
        raising_ctx_id: CtxId,
        entered_ctx_ids: Sequence[CtxId],
        exp_exc: ExceptionExpectation,
    ) -> None:
        '''A context raises an exception on sent.'''
        suspended_ctx_ids = [id for id in entered_ctx_ids if id != raising_ctx_id]
        ctx_ids = [raising_ctx_id, *reversed(suspended_ctx_ids)]
        if not suspended_ctx_ids:
            if self._async:
                exp_exc = wrap_exc(AsyncGenRaiseOnASend)
            self._expected = _Expected(ctx_ids, exp_exc)
        else:
            exc_handler = self._draw(
                self._st_exc_handler_on_sent(
                    exp=exp_exc, ids=reversed(suspended_ctx_ids)
                )
            )
            exp_on_handle = wrap_exc(StopIteration())
            exc_expected = exc_handler.expect_outermost_exc(exp_on_handle=exp_on_handle)
            #
            self._expected = _Expected(ctx_ids, exc_expected)
            self._exc_handler = exc_handler

    def expect_to_exit(self, ctx_ids: Iterable[CtxId]) -> None:
        '''All contexts exit without raising an exception.'''
        self._expected = _Expected(ctx_ids)

    def on_error(self, id: CtxId, exc: Exception) -> None:
        assert self._exc_handler
        self._exc_handler.handle(id, exc)

    def on_exiting(self, ctx_id: CtxId) -> None:
        self._ctx_ids.append(ctx_id)

    def assert_on_entered(self) -> None:
        assert not self._expected

    def assert_on_sent(self) -> None:
        assert not self._expected

    def assert_on_exited(self, exc: Union[BaseException, None]) -> None:
        assert self._expected
        self._expected.assert_on_exited(self._ctx_ids, exc)
        if self._exc_handler:
            self._exc_handler.assert_on_exited(exc)


class _Expected:
    def __init__(
        self, ctx_ids: Iterable[CtxId], exc: Optional[ExceptionExpectation] = None
    ):
        self._ctx_ids = list(ctx_ids)

        if exc is None:
            exc = wrap_exc(None)
        self._exc = exc

    def assert_on_exited(
        self, ctx_ids: Iterable[CtxId], exc: Optional[BaseException] = None
    ) -> None:
        assert self._ctx_ids == list(ctx_ids)
        assert self._exc == exc
