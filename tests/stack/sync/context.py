from collections.abc import Generator, Iterable, Sequence
from contextlib import contextmanager
from typing import Optional

from hypothesis import strategies as st

from apluggy.stack import GenCtxMngr

from .action import CTX_ACTIONS, ContextActionStrategy, CtxActionName
from .exc import wrap_exc
from .except_ import EXCEPT_ACTIONS, ExceptActionName
from .exit_ import ExitHandler
from .states import Created, Entered, Sent


class MockContext:
    def __init__(
        self,
        data: st.DataObject,
        enabled_ctx_actions_on_enter: Sequence[CtxActionName] = CTX_ACTIONS,
        enabled_except_actions_on_enter: Sequence[ExceptActionName] = EXCEPT_ACTIONS,
        enabled_ctx_actions_on_sent: Sequence[CtxActionName] = CTX_ACTIONS,
        enabled_except_actions_on_sent: Sequence[ExceptActionName] = EXCEPT_ACTIONS,
        enabled_except_actions_on_raised: Sequence[ExceptActionName] = EXCEPT_ACTIONS,
    ) -> None:
        self._draw = data.draw
        self._ctx_action = ContextActionStrategy(
            data,
            enabled_actions_on_enter=enabled_ctx_actions_on_enter,
            enabled_actions_on_sent=enabled_ctx_actions_on_sent,
        )
        self._exit_handler = ExitHandler(
            data,
            enabled_except_actions_on_enter=enabled_except_actions_on_enter,
            enabled_except_actions_on_sent=enabled_except_actions_on_sent,
            enabled_except_actions_on_raised=enabled_except_actions_on_raised,
        )
        self._created = Created()
        self._clear()

    def _clear(self) -> None:
        self._ctx_action.clear()
        self._sent: Optional[Sent] = None
        self._exit_handler.clear()

    def __call__(self) -> GenCtxMngr[str]:
        @contextmanager
        def _ctx() -> Generator[str, str, None]:
            self._entered.add(ctx_id)
            try:
                while True:
                    action_item = self._ctx_action.pop(ctx_id)
                    if action_item[0] == 'raise':
                        raise action_item[1]
                    elif action_item[0] == 'exit':
                        break
                    elif action_item[0] == 'yield':
                        try:
                            sent = yield action_item[1]
                            if self._sent:
                                self._sent.add(sent)
                        except Exception as e:
                            self._exit_handler.on_error(ctx_id, e)
                            break
                    else:  # pragma: no cover
                        raise ValueError(f'Unknown action: {action_item[0]!r}')
            finally:
                self._exit_handler.on_exiting(ctx_id)

        ctx = _ctx()
        ctx_id = self._created.add(ctx)
        return ctx

    def assert_created(self, ctxs: Iterable[GenCtxMngr]) -> None:
        self._created.assert_on_created(ctxs)

    def before_enter(self) -> None:
        self._clear()

        # Expect to enter when no context is created.
        if not self._created:
            self._entered = Entered()
            return

        self._ctx_action.before_enter(self._created.ctx_ids)

        last_action_item = self._ctx_action.last_action_item

        # Expect to enter if all contexts yield.
        if last_action_item[0] == 'yield':
            self._entered = Entered(self._created.ctx_ids, self._ctx_action.yields)
            return

        entered_ctx_ids = self._ctx_action.ctx_ids

        # Expect to fail to enter if a context exits.
        if last_action_item[0] == 'exit':
            self._entered = Entered()
            self._exit_handler.expect_exit_on_enter(entered_ctx_ids)
            return

        # Expect to fail to enter if a context raises an exception.
        if last_action_item[0] == 'raise':
            self._entered = Entered()
            exp_exc = wrap_exc(last_action_item[1])
            self._exit_handler.expect_raise_on_enter(entered_ctx_ids, exp_exc)
            return

        raise ValueError(f'Unknown action: {last_action_item[0]!r}')  # pragma: no cover

    def on_entered(self, yields: Iterable[str]) -> None:
        self._exit_handler.assert_on_entered()
        assert not self._ctx_action
        self._entered.assert_on_entered(yields)

    def before_send(self, sent: str) -> None:
        self._clear()

        # Expect to exit if no context is entered.
        if not self._entered:
            self._exit_handler.expect_send_without_ctx()
            return

        self._ctx_action.before_send(reversed(self._entered.ctx_ids))

        last_action_item = self._ctx_action.last_action_item

        # Expect `gen.send()` to return if all contexts yield.
        if last_action_item[0] == 'yield':
            self._sent = Sent(sent, self._ctx_action.yields)
            return

        ctx_id = self._ctx_action.last_ctx_id

        # Expect to exit if a contest exits.
        if last_action_item[0] == 'exit':
            self._exit_handler.expect_exit_on_sent(ctx_id, self._entered.ctx_ids)
            return

        # Expect to exit if a context raises an exception.
        if last_action_item[0] == 'raise':
            exp_exc = wrap_exc(last_action_item[1])
            self._exit_handler.expect_raise_on_sent(
                ctx_id, self._entered.ctx_ids, exp_exc
            )
            return

        raise ValueError(f'Unknown action: {last_action_item[0]!r}')  # pragma: no cover

    def on_sent(self, yields: Iterable[str]) -> None:
        self._exit_handler.assert_on_sent()
        assert not self._ctx_action
        assert self._sent
        self._sent.assert_on_sent(yields)

    def before_raise(self, exc: Exception) -> None:
        self._clear()
        self._ctx_action.before_raise(exc)
        entered_ctx_ids = self._entered.ctx_ids
        exp_exc = wrap_exc(exc)
        self._exit_handler.expect_raise_in_with_block(entered_ctx_ids, exp_exc)

    def before_exit(self) -> None:
        self._clear()
        self._ctx_action.before_exit()
        self._exit_handler.expect_to_exit(reversed(self._created.ctx_ids))

    def on_exited(self, exc: Optional[BaseException] = None) -> None:
        assert not self._ctx_action
        self._exit_handler.assert_on_exited(exc)
