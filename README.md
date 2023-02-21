# apluggy

[![PyPI - Version](https://img.shields.io/pypi/v/apluggy.svg)](https://pypi.org/project/apluggy)
[![PyPI - Python Version](https://img.shields.io/pypi/pyversions/apluggy.svg)](https://pypi.org/project/apluggy)
[![Test Status](https://github.com/simonsobs/apluggy/actions/workflows/unit-test.yml/badge.svg)](https://github.com/simonsobs/apluggy/actions/workflows/unit-test.yml)
[![Test Status](https://github.com/simonsobs/apluggy/actions/workflows/type-check.yml/badge.svg)](https://github.com/simonsobs/apluggy/actions/workflows/type-check.yml)
[![codecov](https://codecov.io/gh/simonsobs/apluggy/branch/main/graph/badge.svg)](https://codecov.io/gh/simonsobs/apluggy)

A wrapper of [pluggy](https://pluggy.readthedocs.io/) to support asyncio and context managers.

This package provides a subclass of
[`pluggy.PluginManager`](https://pluggy.readthedocs.io/en/stable/api_reference.html#pluggy.PluginManager)
which

- allows async functions, context managers, and async context managers to be hooks
- and accepts plugin factories in addition to plugin instances for registration.

---

**Table of Contents**

- [apluggy](#apluggy)
  - [Installation](#installation)
  - [How to use](#how-to-use)
  - [Links](#links)
  - [License](#license)
  - [Contact](#contact)

---

## Installation

You can install apluggy with pip:

```console
pip install apluggy
```

---

## How to use

Here, we show a simple example of how to use apluggy.

We only describe the usage of additional features provided by apluggy. For the
usage of pluggy itself, please refer to the [pluggy
documentation](https://pluggy.readthedocs.io/).

### Start Python

You can try this example in a Python interpreter.

```console
$ python
Python 3.8.16 (...)
...
...
>>>
```

### Import packages

Import necessary packages of this example.

```python
>>> import asyncio
>>> import apluggy as pluggy
>>> from apluggy import asynccontextmanager, contextmanager

```

In this example, `apluggy` is imported with the alias `pluggy`.

The decorators `asynccontextmanager` and `contextmanager` are imported from
`apluggy`. They are wrappers of the decorators of the same names in the
[contextlib package](https://docs.python.org/3/library/contextlib.html). The
wrappers preserve the signatures of decorated functions, which are necessary for
pluggy to pass arguments to hook implementations correctly. (The decorator
`contextmanger` in `apluggy` is the same object as the decorator
`contextmanager` in the [decorator
package](https://pypi.org/project/decorator/). The decorator package does not
provide `asynccontextmanager` decorator as of version 5.1. The decorator
`asynccontextmanger` in `apluggy` is implemented in a similar way as the
decorator `contextmanager` in the decorator package.)

### Create hook specification and implementation decorators

```python
>>> hookspec = pluggy.HookspecMarker('project')
>>> hookimpl = pluggy.HookimplMarker('project')

```

### Define hook specifications

In this example, we define three hooks: async function, context manager, and
async context manager.

```python
>>> class Spec:
...     """A hook specification namespace."""
...
...     @hookspec
...     async def afunc(self, arg1, arg2):
...         pass
...
...     @hookspec
...     @contextmanager
...     def context(self, arg1, arg2):
...         pass
...
...     @hookspec
...     @asynccontextmanager
...     async def acontext(self, arg1, arg2):
...         pass

```

### Define plugins

We define two plugins as classes. Each plugin implements the three hooks
defined above.

```python
>>> class Plugin_1:
...     """A hook implementation namespace."""
...
...     @hookimpl
...     async def afunc(self, arg1, arg2):
...         print('inside Plugin_1.afunc()')
...         return arg1 + arg2
...
...     @hookimpl
...     @contextmanager
...     def context(self, arg1, arg2):
...         print('inside Plugin_1.context()')
...         yield arg1 + arg2
...
...     @hookimpl
...     @asynccontextmanager
...     async def acontext(self, arg1, arg2):
...         print('inside Plugin_1.acontext()')
...         yield arg1 + arg2

>>> class Plugin_2:
...     """A 2nd hook implementation namespace."""
...
...     @hookimpl
...     async def afunc(self, arg1, arg2):
...         print('inside Plugin_2.afunc()')
...         return arg1 - arg2
...
...     @hookimpl
...     @contextmanager
...     def context(self, arg1, arg2):
...         print('inside Plugin_2.context()')
...         yield arg1 - arg2
...
...     @hookimpl
...     @asynccontextmanager
...     async def acontext(self, arg1, arg2):
...         print('inside Plugin_2.acontext()')
...         yield arg1 - arg2

```

### Create a plugin manager and register plugins

Plugins can be registered as instances or factories. In the following
example, we register two plugins: `Plugin_1` as an instance, and `Plugin_2`
as a factory.

```python
>>> pm = pluggy.PluginManager('project')
>>> pm.add_hookspecs(Spec)
>>> _ = pm.register(Plugin_1())  # instantiation is optional.
>>> _ = pm.register(Plugin_2)  # callable is considered a plugin factory.

```

[Pluggy accepts a class or
module](https://pluggy.readthedocs.io/en/stable/#define-and-collect-hooks) as a
plugin. However, it actually accepts a class instance, not a class itself.
Consequently, when plugins are loaded with
[`load_setuptools_entrypoints()`](https://pluggy.readthedocs.io/en/stable/api_reference.html#pluggy.PluginManager.load_setuptools_entrypoints),
the entry points must be class instances or modules. Classes themselves cannot
be used as entry points (if understood correctly).

So that classes themselves can be entry points, apluggy accepts a class itself for
a plugin registration. When apluggy receives a callable object, apluggy considers
the object as a plugin factory.

### Call hooks

The following example shows how to call hooks.

#### Async function

```python
>>> async def call_afunc():
...     results = await pm.ahook.afunc(arg1=1, arg2=2)  # ahook instead of hook
...     print(results)

>>> asyncio.run(call_afunc())
inside Plugin_2.afunc()
inside Plugin_1.afunc()
[-1, 3]

```

#### Context manager

```python
>>> with pm.with_.context(arg1=1, arg2=2) as y:  # with_ instead of hook
...     print(y)
inside Plugin_2.context()
inside Plugin_1.context()
[-1, 3]

```

#### Async context manager

```python
>>> async def call_acontext():
...     async with pm.awith.acontext(arg1=1, arg2=2) as y:  # awith instead of hook
...         print(y)

>>> asyncio.run(call_acontext())
inside Plugin_2.acontext()
inside Plugin_1.acontext()
[-1, 3]

```

---

## Links

- [pluggy](https://pluggy.readthedocs.io/)
- [decorator](https://pypi.org/project/decorator/)

---

## License

- _apluggy_ is licensed under the [MIT](https://spdx.org/licenses/MIT.html) license.

---

## Contact

- [Tai Sakuma](https://github.com/TaiSakuma) <span itemscope
  itemtype="https://schema.org/Person"><a itemprop="sameAs"
  content="https://orcid.org/0000-0003-3225-9861"
  href="https://orcid.org/0000-0003-3225-9861" target="orcid.widget" rel="me
  noopener noreferrer" style="vertical-align:text-top;"><img
  src="https://orcid.org/sites/default/files/images/orcid_16x16.png"
  style="width:1em;margin-right:.5em;" alt="ORCID iD icon"></a></span>
