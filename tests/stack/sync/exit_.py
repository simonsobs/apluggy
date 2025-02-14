from collections.abc import Iterable, Sequence
from typing import Optional, Union

from hypothesis import strategies as st

from .ctx_id import CtxId
from .exc import ExceptionExpectation, GeneratorDidNotYield, wrap_exc
from .except_ import ExceptActionName, ExceptionHandler, st_exception_handler


class ExitHandler:
    def __init__(
        self,
        data: st.DataObject,
        enabled_except_actions_on_enter: Sequence[ExceptActionName],
        enabled_except_actions_on_sent: Sequence[ExceptActionName],
        enabled_except_actions_on_raised: Sequence[ExceptActionName],
    ) -> None:
        self._draw = data.draw
        self._enabled_except_actions_on_enter = enabled_except_actions_on_enter
        self._enabled_except_actions_on_sent = enabled_except_actions_on_sent
        self._enabled_except_actions_on_raised = enabled_except_actions_on_raised
        self.clear()

    def clear(self) -> None:
        self._expected: Optional[_Expected] = None
        self._exc_handler: Optional[ExceptionHandler] = None
        self._ctx_ids: list[CtxId] = []

    def expect_exit_on_enter(self, entered_ctx_ids: Sequence[CtxId]) -> None:
        # The last entered context exits without yielding.
        self.expect_raise_on_enter(entered_ctx_ids, wrap_exc(GeneratorDidNotYield))

    def expect_raise_on_enter(
        self, entered_ctx_ids: Sequence[CtxId], exp_exc: ExceptionExpectation
    ) -> None:
        # The last entered context raises an exception.
        ctx_ids_reversed = list(reversed(entered_ctx_ids))
        suspended_ctx_ids = ctx_ids_reversed[1:]

        exc_handler = self._draw(
            st_exception_handler(
                exp=exp_exc,
                ids=suspended_ctx_ids,
                enabled_actions=self._enabled_except_actions_on_enter,
            )
        )

        exp_on_handle = wrap_exc(GeneratorDidNotYield)
        exc_expected = exc_handler.expect_outermost_exc(exp_on_handle=exp_on_handle)

        self.expect_to_exit_on_error(
            ctx_ids=ctx_ids_reversed,
            exc_expected=exc_expected,
            exc_handler=exc_handler,
        )

    def expect_raise_in_with_block(
        self, entered_ctx_ids: Sequence[CtxId], exp_exc: ExceptionExpectation
    ):
        exc_handler = self._draw(
            st_exception_handler(
                exp=exp_exc,
                ids=reversed(entered_ctx_ids),
                enabled_actions=self._enabled_except_actions_on_raised,
            )
        )

        exc_expected = exc_handler.expect_outermost_exc()

        self.expect_to_exit_on_error(
            ctx_ids=reversed(entered_ctx_ids),
            exc_expected=exc_expected,
            exc_handler=exc_handler,
        )

    def expect_send_without_ctx(self) -> None:
        exc_handler: Optional[ExceptionHandler] = None
        exc_expected = wrap_exc(StopIteration())
        self.expect_to_exit_on_error(
            ctx_ids=[], exc_expected=exc_expected, exc_handler=exc_handler
        )

    def expect_exit_on_sent(
        self,
        exiting_ctx_id: CtxId,
        entered_ctx_ids: Sequence[CtxId],
    ) -> None:
        suspended_ctx_ids = [id for id in entered_ctx_ids if id != exiting_ctx_id]
        exc_handler: Optional[ExceptionHandler] = None
        exc_expected = wrap_exc(StopIteration())
        self.expect_to_exit_on_error(
            ctx_ids=[exiting_ctx_id, *reversed(suspended_ctx_ids)],
            exc_expected=exc_expected,
            exc_handler=exc_handler,
        )

    def expect_raise_on_sent(
        self,
        raising_ctx_id: CtxId,
        entered_ctx_ids: Sequence[CtxId],
        exp_exc: ExceptionExpectation,
    ) -> None:
        suspended_ctx_ids = [id for id in entered_ctx_ids if id != raising_ctx_id]
        if not suspended_ctx_ids:
            exc_handler: Optional[ExceptionHandler] = None
            exc_expected = exp_exc
        else:
            exc_handler = self._draw(
                st_exception_handler(
                    exp=exp_exc,
                    ids=reversed(suspended_ctx_ids),
                    enabled_actions=self._enabled_except_actions_on_sent,
                )
            )
            exp_on_handle = wrap_exc(StopIteration())
            exc_expected = exc_handler.expect_outermost_exc(exp_on_handle=exp_on_handle)

        self.expect_to_exit_on_error(
            ctx_ids=[raising_ctx_id, *reversed(suspended_ctx_ids)],
            exc_expected=exc_expected,
            exc_handler=exc_handler,
        )

    def expect_to_exit_on_error(
        self,
        ctx_ids: Iterable[CtxId],
        exc_expected: ExceptionExpectation,
        exc_handler: Optional[ExceptionHandler],
    ) -> None:
        self._expected = _Expected(ctx_ids, exc_expected)
        self._exc_handler = exc_handler

    def expect_to_exit(self, ctx_ids: Iterable[CtxId]) -> None:
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
