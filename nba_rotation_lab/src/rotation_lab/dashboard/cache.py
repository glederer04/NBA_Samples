"""Bounded read cache invalidated when the analytical database changes."""

from collections import OrderedDict
from collections.abc import Callable
from copy import deepcopy
from functools import wraps
from pathlib import Path
from threading import RLock
from typing import ParamSpec, TypeVar

P = ParamSpec("P")
T = TypeVar("T")


def database_cached(path_getter: Callable[[], Path]) -> Callable[[Callable[P, T]], Callable[P, T]]:
    """Cache read results only; return copies so callers cannot mutate shared state."""

    def decorate(function: Callable[P, T]) -> Callable[P, T]:
        cache: OrderedDict[str, T] = OrderedDict()
        lock = RLock()

        @wraps(function)
        def wrapped(*args: P.args, **kwargs: P.kwargs) -> T:
            path = path_getter().resolve()
            signatures = []
            for source in (path, Path(str(path) + ".wal")):
                try:
                    stat = source.stat()
                    signatures.append((stat.st_ino, stat.st_mtime_ns, stat.st_size))
                except FileNotFoundError:
                    signatures.append(None)
            key = repr((str(path), signatures, args, sorted(kwargs.items())))
            with lock:
                if key in cache:
                    cache.move_to_end(key)
                    return deepcopy(cache[key])
            result = function(*args, **kwargs)
            with lock:
                cache[key] = deepcopy(result)
                cache.move_to_end(key)
                while len(cache) > 128:
                    cache.popitem(last=False)
            return result

        return wrapped

    return decorate
