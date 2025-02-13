import sys
from collections.abc import Generator, Iterable, MutableMapping, Sequence
from contextlib import contextmanager
from typing import Literal, Union

from hypothesis import note
from hypothesis import strategies as st

from apluggy.stack import GenCtxMngr
from tests.utils import st_list_until

if sys.version_info >= (3, 10):
    from typing import TypeAlias
else:
    from typing_extensions import TypeAlias


from .ctx_id import ContextIdGenerator, CtxId
from .exc import ExceptionExpectation, GeneratorDidNotYield, MockException, wrap_exc
from .handle import (
    EXCEPT_ACTIONS,
    ExceptActionName,
    ExceptionHandler,
    ExceptionHandlerNull,
    st_exception_handler,
)

CtxActionName = Literal['yield', 'raise', 'exit']
CTX_ACTIONS: Sequence[CtxActionName] = ('yield', 'raise', 'exit')


_ActionItem: TypeAlias = Union[
    tuple[Literal['yield'], str],
    tuple[Literal['raise'], Exception],
    tuple[Literal['exit'], None],
]
_ActionMap: TypeAlias = MutableMapping[CtxId, _ActionItem]


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

        self._to_be_exited = False
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
        exc_handler = ExceptionHandlerNull()
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
        exc_handler = ExceptionHandlerNull()
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
            exc_handler: ExceptionHandler = ExceptionHandlerNull()
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
        exc_handler: ExceptionHandler,
    ) -> None:
        self._to_be_exited = True
        self._ctx_ids_expected = list(ctx_ids)
        self._exc_expected = exc_expected
        self._exc_handler = exc_handler

    def expect_to_exit(self, ctx_ids: Iterable[CtxId]) -> None:
        self._to_be_exited = True
        self._ctx_ids_expected = list(ctx_ids)
        self._exc_expected = wrap_exc(None)
        self._exc_handler = ExceptionHandlerNull()

    def on_error(self, id: CtxId, exc: Exception) -> None:
        self._exc_handler.handle(id, exc)

    def on_exiting(self, ctx_id: CtxId) -> None:
        self._ctx_ids.append(ctx_id)

    def assert_on_entered(self) -> None:
        assert not self._to_be_exited

    def assert_on_sent(self) -> None:
        assert not self._to_be_exited

    def assert_on_exited(self, exc: Union[BaseException, None]) -> None:
        assert self._to_be_exited
        assert self._ctx_ids == self._ctx_ids_expected
        assert self._exc_expected == exc
        self._exc_handler.assert_on_exited(exc)


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
        self._data = data
        self._draw = data.draw
        self._enabled_ctx_actions_on_enter = enabled_ctx_actions_on_enter
        self._enabled_except_actions_on_enter = enabled_except_actions_on_enter
        self._enabled_ctx_actions_on_sent = enabled_ctx_actions_on_sent
        self._enabled_except_actions_on_sent = enabled_except_actions_on_sent
        self._enabled_except_actions_on_raised = enabled_except_actions_on_raised

        self._generate_ctx_id = ContextIdGenerator()
        self._ctxs_map: dict[CtxId, GenCtxMngr] = {}

        self._created_ctx_ids: list[CtxId] = []
        self._entered_ctx_ids: list[CtxId] = []
        self._clear()

    def _clear(self) -> None:
        self._ctx_action_map: Union[_ActionMap, None] = None
        self._sent_expected: list[str] = []
        self._sent_actual: list[str] = []
        self._yields_expected: list[str] = []
        self._exit_handler = ExitHandler(
            self._data,
            enabled_except_actions_on_enter=self._enabled_except_actions_on_enter,
            enabled_except_actions_on_sent=self._enabled_except_actions_on_sent,
            enabled_except_actions_on_raised=self._enabled_except_actions_on_raised,
        )

    def __call__(self) -> GenCtxMngr[str]:
        id = self._generate_ctx_id()
        self._created_ctx_ids.append(id)

        @contextmanager
        def _ctx() -> Generator[str, str, None]:
            self._entered_ctx_ids.append(id)
            try:
                while True:
                    assert self._ctx_action_map is not None
                    action_item = self._ctx_action_map.pop(id, ('exit', None))
                    note(f'ctx {id=} {action_item=}')
                    if action_item[0] == 'raise':
                        raise action_item[1]
                    elif action_item[0] == 'exit':
                        break
                    elif action_item[0] == 'yield':
                        try:
                            sent = yield action_item[1]
                            self._sent_actual.append(sent)
                        except Exception as e:
                            note(f'ctx {id=} except: {e=}')
                            self._exit_handler.on_error(id, e)
                            break
                    else:  # pragma: no cover
                        raise ValueError(f'Unknown action: {action_item[0]!r}')
            finally:
                self._exit_handler.on_exiting(id)

        ctx = _ctx()
        self._ctxs_map[id] = ctx
        return ctx

    def assert_created(self, ctxs: Iterable[GenCtxMngr]) -> None:
        assert list(ctxs) == [self._ctxs_map[id] for id in self._created_ctx_ids]

    def before_enter(self) -> None:
        _name = f'{self.__class__.__name__}.{self.before_enter.__name__}'
        note(f'{_name}()')
        self._clear()

        if not self._created_ctx_ids:
            self._yields_expected = []
            return

        self._ctx_action_map = self._draw(
            _st_ctx_action_map(
                self._created_ctx_ids,
                enabled_actions=self._enabled_ctx_actions_on_enter,
            ),
            label=f'{_name}: _ctx_action_map',
        )

        last_action_item = list(self._ctx_action_map.values())[-1]
        if last_action_item[0] == 'yield':
            # All actions are `yield` when the last action is `yield`.
            # `e[0] == 'yield'` is to reduce the type of `e[1]` to `str`.
            self._yields_expected = [
                e[1] for e in self._ctx_action_map.values() if e[0] == 'yield'
            ]
            note(f'{_name}: {self._yields_expected=}')
            return

        entered_ctx_ids = list(self._ctx_action_map.keys())
        if last_action_item[0] == 'exit':
            self._exit_handler.expect_exit_on_enter(entered_ctx_ids)
            return

        if last_action_item[0] == 'raise':
            exp_exc = wrap_exc(last_action_item[1])
            self._exit_handler.expect_raise_on_enter(entered_ctx_ids, exp_exc)
            return

        raise ValueError(f'Unknown action: {last_action_item[0]!r}')  # pragma: no cover

    def on_entered(self, yields: Iterable[str]) -> None:
        yields = list(yields)
        _name = f'{self.__class__.__name__}.{self.on_entered.__name__}'
        note(f'{_name}({yields=!r})')
        self._exit_handler.assert_on_entered()
        assert self._entered_ctx_ids == self._created_ctx_ids
        assert not self._ctx_action_map
        assert yields == self._yields_expected

    def before_send(self, sent: str) -> None:
        _name = f'{self.__class__.__name__}.{self.before_send.__name__}'
        note(f'{_name}({sent=})')
        self._clear()

        if not self._created_ctx_ids:
            self._exit_handler.expect_send_without_ctx()
            return

        self._ctx_action_map = self._draw(
            _st_ctx_action_map(
                reversed(self._created_ctx_ids),
                enabled_actions=self._enabled_ctx_actions_on_sent,
            ),
            label=f'{_name}: _ctx_action_map',
        )
        id, last_action_item = list(self._ctx_action_map.items())[-1]
        if last_action_item[0] == 'yield':
            self._sent_expected = [sent] * len(self._created_ctx_ids)
            # All actions are `yield` when the last action is `yield`.
            # `e[0] == 'yield'` is to reduce the type of `e[1]` to `str`.
            self._yields_expected = [
                e[1] for e in self._ctx_action_map.values() if e[0] == 'yield'
            ]
            note(f'{_name}: {self._yields_expected=}')
            return

        if last_action_item[0] == 'exit':
            self._exit_handler.expect_exit_on_sent(id, self._entered_ctx_ids)
            return

        if last_action_item[0] == 'raise':
            exp_exc = wrap_exc(last_action_item[1])
            self._exit_handler.expect_raise_on_sent(id, self._entered_ctx_ids, exp_exc)
            return

        raise ValueError(f'Unknown action: {last_action_item[0]!r}')  # pragma: no cover

    def on_sent(self, yields: Iterable[str]) -> None:
        yields = list(yields)
        _name = f'{self.__class__.__name__}.{self.on_sent.__name__}'
        note(f'{_name}({yields=!r})')
        self._exit_handler.assert_on_sent()
        assert not self._ctx_action_map
        assert self._sent_actual == self._sent_expected
        assert yields == self._yields_expected

    def before_raise(self, exc: Exception) -> None:
        _name = f'{self.__class__.__name__}.{self.before_raise.__name__}'
        note(f'{_name}({exc=!r})')
        self._clear()

        self._ctx_action_map = {}

        entered_ctx_ids = self._entered_ctx_ids
        exp_exc = wrap_exc(exc)

        self._exit_handler.expect_raise_in_with_block(entered_ctx_ids, exp_exc)

    def before_exit(self) -> None:
        _name = f'{self.__class__.__name__}.{self.before_exit.__name__}'
        note(f'{_name}()')
        self._clear()

        self._ctx_action_map = {id: ('exit', None) for id in self._created_ctx_ids}
        self._exit_handler.expect_to_exit(reversed(self._created_ctx_ids))

    def on_exited(self, exc: Union[BaseException, None]) -> None:
        _name = f'{self.__class__.__name__}.{self.on_exited.__name__}'
        note(f'{_name}({exc=!r})')

        assert not self._ctx_action_map
        self._exit_handler.assert_on_exited(exc)


@st.composite
def _st_ctx_action_map(
    draw: st.DrawFn, ids: Iterable[CtxId], enabled_actions: Sequence[CtxActionName]
) -> _ActionMap:
    ids = list(ids)
    st_actions = st.sampled_from(enabled_actions)
    actions: list[CtxActionName] = draw(
        st_list_until(st_actions, last={'raise', 'exit'}, max_size=len(ids))
    )

    def _action_item(id: CtxId, action: CtxActionName) -> _ActionItem:
        if action == 'raise':
            return ('raise', MockException(f'{id}'))
        if action == 'yield':
            return ('yield', f'yield-{id}')
        if action == 'exit':
            return ('exit', None)
        raise ValueError(f'Unknown action: {action!r}')  # pragma: no cover

    return {id: _action_item(id, a) for id, a in zip(ids, actions)}
