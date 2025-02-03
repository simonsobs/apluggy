from dataclasses import dataclass
from typing import ClassVar, Literal, Union


class Thrown(Exception):
    '''To be thrown to the context manager.

    An argument of `contextmanager.gen.throw()`.
    '''

    pass


class Raised(Exception):
    pass


class MockException(Exception):
    pass


@dataclass
class ExceptionExpectation:
    Method = Literal['is', 'type', 'type-msg']
    METHODS: ClassVar[tuple[Method, ...]] = ('is', 'type', 'type-msg')

    expected: Union[BaseException, None]
    method: Method = 'is'

    def __eq__(self, other: object) -> bool:
        if self.method == 'is':
            return self.expected is other
        if self.method == 'type':
            return isinstance(other, type(self.expected))
        if self.method == 'type-msg':
            if not isinstance(other, type(self.expected)):
                return False
            return str(other) == str(self.expected)
