try:
    import regex as re
else:
    import re

from collections import abc


def _make_regex(pattern, flag_string):
    flags = 0
    g = False

    if flag_string is not None:
        for c in map(str.upper, flag_string):
            if c == 'G':
                g = True
            else:
                flags |= getattr(re, c)

    if isinstance(pattern, str):
        pattern = re.compile(pattern, flags)

    return pattern, g


class SubMaker:
    def __getitem__(self, values):
        pattern, g = _make_regex(values.start, values.step)
        replacement = values.stop
        return Subber(pattern, replacement, g)


class Subber:
    def __init__(self, pattern, replacement, g=False):
        self.pat, self.rep, = pattern, replacement
        self.count = 0 if g else 1
            
    def __ror__(self, other):
        if isinstance(other, str):
            return self.pat.sub(self.rep, other, self.count)
        elif isinstance(other, abc.Iterable):
            return (self.pat.sub(self.rep, i, self.count) for i in other)
        else:
            return NotImplemented


class MatchMaker:
    def __getitem__(self, values):
        if isinstance(values, str):
            return Matcher(re.compile(values))
        else:
            regex, _ = _make_regex(self.start, self.stop)
            return Matcher(regex)


class Matcher:
    def __init__(self, regex):
        self.pat = regex

    def __ror__(self, other):
        if isinstance(other, str):
            return self.pat.search(other)
        elif isinstance(other, abc.Iterable):
            return (i for i in other if self.pat.search(i))
        else:
            return NotImplemented

s = SubMaker
m = MatchMaker
