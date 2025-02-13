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
from .exc import MockException, wrap_exc
from .except_ import EXCEPT_ACTIONS, ExceptActionName
from .exit_ import ExitHandler


class Created:
    def __init__(self) -> None:
        self._ctx_ids: list[CtxId] = []
        self._ctxs: list[GenCtxMngr] = []
        self._new_ctx_id = ContextIdGenerator()

    @property
    def ctx_ids(self) -> list[CtxId]:
        return list(self._ctx_ids)

    def add(self, ctx: GenCtxMngr) -> CtxId:
        ctx_id = self._new_ctx_id()
        self._ctx_ids.append(ctx_id)
        self._ctxs.append(ctx)
        return ctx_id

    def assert_on_created(self, ctxs: Iterable[GenCtxMngr]) -> None:
        assert list(ctxs) == self._ctxs


class Entered:
    def __init__(
        self,
        ctx_ids_expected: Iterable[CtxId] = (),
        yields_expected: Iterable[str] = (),
    ) -> None:
        self._ctx_ids_expected = list(ctx_ids_expected)
        self._yields_expected = list(yields_expected)
        self._ctx_ids: list[CtxId] = []

    @property
    def ctx_ids(self) -> list[CtxId]:
        return list(self._ctx_ids)

    def add(self, ctx_id: CtxId) -> None:
        self._ctx_ids.append(ctx_id)

    def assert_on_entered(self, yields: Iterable[str]) -> None:
        assert self._ctx_ids == self._ctx_ids_expected
        assert list(yields) == self._yields_expected


class Sent:
    def __init__(self, sent_expected: str, yields_expected: Iterable[str]) -> None:
        self._sent_expected = sent_expected
        self._yields_expected = list(yields_expected)
        self._sent_actual: list[str] = []

    def add(self, sent: str) -> None:
        self._sent_actual.append(sent)

    def assert_on_sent(self, yields: Iterable[str]) -> None:
        assert len(self._sent_actual) == len(self._yields_expected)
        assert set(self._sent_actual) == {self._sent_expected}
        assert list(yields) == self._yields_expected


class SentNull(Sent):
    def __init__(self) -> None:
        pass

    def add(self, sent: str) -> None:
        pass

    def assert_on_sent(self, yields: Iterable[str]) -> None:
        assert False  # pragma: no cover


CtxActionName = Literal['yield', 'raise', 'exit']
CTX_ACTIONS: Sequence[CtxActionName] = ('yield', 'raise', 'exit')


_ActionItem: TypeAlias = Union[
    tuple[Literal['yield'], str],
    tuple[Literal['raise'], Exception],
    tuple[Literal['exit'], None],
]
_ActionMap: TypeAlias = MutableMapping[CtxId, _ActionItem]


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

        self._created = Created()
        self._clear()

    def _clear(self) -> None:
        self._ctx_action_map: Union[_ActionMap, None] = None
        self._sent: Sent = SentNull()
        self._exit_handler = ExitHandler(
            self._data,
            enabled_except_actions_on_enter=self._enabled_except_actions_on_enter,
            enabled_except_actions_on_sent=self._enabled_except_actions_on_sent,
            enabled_except_actions_on_raised=self._enabled_except_actions_on_raised,
        )

    def __call__(self) -> GenCtxMngr[str]:
        @contextmanager
        def _ctx() -> Generator[str, str, None]:
            self._entered.add(ctx_id)
            try:
                while True:
                    assert self._ctx_action_map is not None
                    action_item = self._ctx_action_map.pop(ctx_id, ('exit', None))
                    note(f'{ctx_id=} {action_item=}')
                    if action_item[0] == 'raise':
                        raise action_item[1]
                    elif action_item[0] == 'exit':
                        break
                    elif action_item[0] == 'yield':
                        try:
                            sent = yield action_item[1]
                            self._sent.add(sent)
                        except Exception as e:
                            note(f'{ctx_id=} except: {e=}')
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

        if not self._created.ctx_ids:
            self._entered = Entered()
            return

        _name = f'{self.__class__.__name__}.{self.before_enter.__name__}'
        label = f'{_name}: _ctx_action_map'
        self._ctx_action_map = self._draw(
            _st_ctx_action_map(
                self._created.ctx_ids,
                enabled_actions=self._enabled_ctx_actions_on_enter,
            ),
            label=label,
        )

        last_action_item = list(self._ctx_action_map.values())[-1]
        if last_action_item[0] == 'yield':
            # All actions are `yield` when the last action is `yield`.
            yields_expected = _extract_yields(self._ctx_action_map)
            self._entered = Entered(
                ctx_ids_expected=self._created.ctx_ids,
                yields_expected=yields_expected,
            )
            return

        entered_ctx_ids = list(self._ctx_action_map.keys())
        if last_action_item[0] == 'exit':
            self._entered = Entered()
            self._exit_handler.expect_exit_on_enter(entered_ctx_ids)
            return

        if last_action_item[0] == 'raise':
            self._entered = Entered()
            exp_exc = wrap_exc(last_action_item[1])
            self._exit_handler.expect_raise_on_enter(entered_ctx_ids, exp_exc)
            return

        raise ValueError(f'Unknown action: {last_action_item[0]!r}')

    def on_entered(self, yields: Iterable[str]) -> None:
        self._exit_handler.assert_on_entered()
        assert not self._ctx_action_map
        self._entered.assert_on_entered(yields)

    def before_send(self, sent: str) -> None:
        self._clear()

        if not self._created.ctx_ids:
            self._exit_handler.expect_send_without_ctx()
            return

        _name = f'{self.__class__.__name__}.{self.before_send.__name__}'
        label = f'{_name}: _ctx_action_map'
        self._ctx_action_map = self._draw(
            _st_ctx_action_map(
                reversed(self._created.ctx_ids),
                enabled_actions=self._enabled_ctx_actions_on_sent,
            ),
            label=label,
        )
        id, last_action_item = list(self._ctx_action_map.items())[-1]
        if last_action_item[0] == 'yield':
            # All actions are `yield` when the last action is `yield`.
            yields_expected = _extract_yields(self._ctx_action_map)
            self._sent = Sent(sent_expected=sent, yields_expected=yields_expected)
            return

        if last_action_item[0] == 'exit':
            self._exit_handler.expect_exit_on_sent(id, self._entered.ctx_ids)
            return

        if last_action_item[0] == 'raise':
            exp_exc = wrap_exc(last_action_item[1])
            self._exit_handler.expect_raise_on_sent(id, self._entered.ctx_ids, exp_exc)
            return

        raise ValueError(f'Unknown action: {last_action_item[0]!r}')  # pragma: no cover

    def on_sent(self, yields: Iterable[str]) -> None:
        self._exit_handler.assert_on_sent()
        assert not self._ctx_action_map
        self._sent.assert_on_sent(yields)

    def before_raise(self, exc: Exception) -> None:
        self._clear()
        self._ctx_action_map = {}
        entered_ctx_ids = self._entered.ctx_ids
        exp_exc = wrap_exc(exc)
        self._exit_handler.expect_raise_in_with_block(entered_ctx_ids, exp_exc)

    def before_exit(self) -> None:
        self._clear()
        self._ctx_action_map = {id: ('exit', None) for id in self._created.ctx_ids}
        self._exit_handler.expect_to_exit(reversed(self._created.ctx_ids))

    def on_exited(self, exc: Union[BaseException, None]) -> None:
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


def _extract_yields(action_map: _ActionMap) -> tuple[str, ...]:
    return tuple(e[1] for e in action_map.values() if e[0] == 'yield')
