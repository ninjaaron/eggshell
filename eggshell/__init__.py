import glob as _glob
import pathlib
from collections import abc


def glob(pattern, recursive=True):
    return map(pathlib.Path, _glob.iglob(pattern, recursive=recursive))


class _Arg(abc.Iterable):
    def __init__(self, data):
        self.data = data

    def __repr__(self):
        return "_Arg(%r)" % self.data

    def __iter__(self):
        if isinstance(self.data, str):
            yield self.data
        elif isinstance(self.data, abc.Iterable):
            yield from self.data
        else:
            yield str(self.data)

    def __add__(self, other):
        return _Arg((str(i) if isinstance(i, int) else i) + other
                    for i in self)

    def __radd__(self, other):
        return _Arg(other + (str(i) if isinstance(i, int) else i)
                    for i in self)


class _Globject:
    def __init__(self, pattern, recursive=True):
        self.pattern = pattern
        self.rec = recursive

    def __str__(self):
        return self.pattern

    def __repr__(self):
        return 'Globject({!r}, recursive={!r})'.format(self.pattern, self.rec)

    def __add__(self, other):
        if isinstance(other, (str, pathlib.Path, _Globject)):
            self.pattern += str(other)
            return self
        else:
            return NotImplemented

    def __radd__(self, other):
        if isinstance(other, (str, pathlib.Path, _Globject)):
            self.pattern = str(other) + self.pattern
            return self
        else:
            return NotImplemented

    def __iter__(self):
        return _glob.iglob(self.pattern, recursive=self.rec)
