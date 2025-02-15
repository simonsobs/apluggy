class Thrown(Exception):
    '''To be thrown to the context manager.

    An argument of `asynccontextmanager.gen.athrow()`.
    '''

    pass


class WithRaised(Exception):
    '''To be raised in the `with` block.'''

    pass


class GenRaised(Exception):
    '''To be raised by the generator context manager.'''

    pass
