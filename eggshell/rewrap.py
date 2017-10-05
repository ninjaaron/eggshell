import functools
from collections import abc
try:
    import regex as re
except ImportError:
    import re


class reify:
    """ Use as a class method decorator.  It operates almost exactly like the
    Python ``@property`` decorator, but it puts the result of the method it
    decorates into the instance dict after the first call, effectively
    replacing the function it decorates with an instance variable.  It is, in
    Python parlance, a non-data descriptor.

    Stolen from pyramid.
    http://docs.pylonsproject.org/projects/pyramid/en/latest/api/decorator.html#pyramid.decorator.reify
    """
    def __init__(self, wrapped):
        self.wrapped = wrapped
        functools.update_wrapper(self, wrapped)

    def __get__(self, inst, objtype=None):
        if inst is None:
            return self
        val = self.wrapped(inst)
        setattr(inst, self.wrapped.__name__, val)
        return val


def _make_regex(pattern, flag_string):
    flags = 0
    count = 1

    if flag_string:
        for c in map(str.upper, flag_string):
            if c == 'G':
                count = 0
            else:
                flags |= getattr(re, c)

    if isinstance(pattern, str):
        pattern = re.compile(pattern, flags)

    return pattern, count


class _Matcher:
    def __init__(self, pattern, flags=None):
        self.pat = pattern
        self.flags = flags

    @reify
    def re(self):
        regex, self.count = _make_regex(self.pat, self.flags)
        return regex

    def __rand__(self, other):
        if isinstance(other, str):
            return self.re.search(other)
        return NotImplemented

    def __ror__(self, other):
        if isinstance(other, abc.Iterable) and not isinstance(other, str):
            return (i for i in other if i & self)
        return NotImplemented


class _Subber(_Matcher):
    def __init__(self, pattern, replacement, flags=None):
        self.pat, self.rep, self.flags = pattern, replacement, flags

    @reify
    def count(self):
        self.re, count = _make_regex(self.pat, self.flags)
        return count

    def __rand__(self, other):
        if isinstance(other, str):
            return self.re.sub(self.rep, other, self.count)
        return NotImplemented

    def __ror__(self, other):
        if isinstance(other, abc.Iterable) and not isinstance(other, str):
            return (i & self for i in other)
        return NotImplemented


class Matcher(_Matcher):
    def __getitem__(self, val):
        if isinstance(val, str):
            return type(self)(val)
        return self(val.start, val.stop)

    def __getattr__(self, flags):
        return self(self.pat, flags)

    def __call__(self, *args, **kwargs):
        return type(self)(*args, **kwargs)


class Subber(_Subber, Matcher):
    def __getitem__(self, val):
        return self(val.start, val.stop, val.step)

    def __getattr__(self, flags):
        return self(self.pat, self.rep, flags)


s = Subber(None, None)
m = Matcher(None)


def rematch(string):
    type = string[0]
    sep = re.match(r'[!$%&,+*-:;=@_|~\\/]', string[1])
    if sep:
        sep = re.escape(sep.group())
    else:
        return

    print(sep)

    parts = re.split(r'(?<!\\)' + sep, string[2:])
    return parts
