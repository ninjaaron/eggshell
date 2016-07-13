#!/usr/bin/env python3
import fileinput as _fileinput
import shlex as _shlex
from glob import iglob as glob
import os
from easyproc import (grab, run, ProcOutput, CalledProcessError,
                      STDOUT, PIPE, DEVNULL)
from compiler import Compiler as _Compiler
import sys as _sys

ARGV = _sys.argv[1:]


def _obj2args(obj):
    if isinstance(obj, str) and not isinstance(obj, ProcOutput):
        return _shlex.quote(obj)
    else:
        return ' '.join(_shlex.quote(i) for i in obj)


class GlobError(Exception):
    def __init__(self, globstring):
        self.string = globstring

    def __str__(self):
        return 'No files matching %s.' % repr(self.string)


def _globarg(string):
    matches = _obj2args(glob(string))

    if not matches:
        raise GlobError(string)

    return matches


class _Pipe():
    def __init__(self, cmd, **kwargs):
        self.cmd = cmd
        self.kwargs = kwargs

    def __ror__(self, stdin):
        stdin = self._reslove(stdin)
        return run(self.cmd, input=stdin, **self.kwargs)

    def _reslove(self, stdin):

        if not isinstance(stdin, (str, ProcOutput)):
            return '\n'.join(stdin)

        return stdin


class _GrabPipe(_Pipe):
    def __ror__(self, stdin):
        stdin = self._reslove(stdin)
        return grab(self.cmd, input=stdin, **self.kwargs)


class _SubStarter:
    def __truediv__(self, pattern):
        return _Substituter(pattern)


class _Substituter:
    def __init__(self, pattern):
        self.pattern = pattern
        self.replacement = None
        self.count = 1

    def __truediv__(self, argument):
        if self.replacement:
            if 'g' in argument:
                self.count = 0
            if 'g' != argument:
                argument = argument.replace('g', '')
                self.pattern = ('(?%s)' % argument + self.pattern)
        else:
            self.replacement = argument
        return self

    def __rand__(self, string):
        if isinstance(self.pattern, str):
            self.pattern = re.compile(self.pattern)
        return self.pattern.sub(self.replacement, string, self.count)

    def __ror__(self, iterable):
        return Stream()|(i & self for i in iterable)


class _MatchStarter:
    def __truediv__(self, pattern):
        return _Matcher(pattern)


class _Matcher:
    def __init__(self, pattern):
        self.pattern = pattern

    def __truediv__(self, options):
        self.pattern = ('(?%s)' % options) + self.pattern
        return self

    def __eq__(self, string):
        if isinstance(self.pattern, str):
            self.pattern = re.compile(self.pattern)
        return self.pattern.fullmatch(string)

    def __rand__(self, string):
        if isinstance(self.pattern, str):
            self.pattern = re.compile(self.pattern)
        return self.pattern.search(string)

    def __ror__(self, iterable):
        return (i for i in iterable if i & self)


s = _SubStarter()
m = _MatchStarter()


def cd(directory):
    directory = os.path.expanduser(directory)
    os.chdir(directory)
    return os.getcwd()


def _main():
    _code = _Compiler(open(_sys.argv[1], 'rb'))
    try:
        exec(_code.output)
    except:
        print(_code.output)
        raise


if __name__ == '__main__':
    _main()
