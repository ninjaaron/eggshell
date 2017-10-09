import io
import subprocess
import easyproc
from collections import abc
from pathlib import Path
from . import _Arg, _Globject
from easyproc import run, grab


class Popen(easyproc.Popen):
    def __init__(self, cmd, stdin=None, stdout=None, stderr=None, **kwargs):
        if isinstance(cmd, abc.Iterable) and not isinstance(cmd, str):
            new_cmd = []
            for i in cmd:
                if isinstance(i, (_Arg, _Globject)):
                    new_cmd.extend(flatten(i))
                else:
                    new_cmd.append(i)
            cmd = new_cmd

        self.string2stdin = False
        self.string2stdout = False
        self.string2stderr = False
        if isinstance(stdin, (str, Path)):
            stdin = open(stdin)
            self.string2stdin = True

        if isinstance(stdout, (str, Path)):
            stdout = open(stdout, 'w')
            self.string2stdout = True

        if isinstance(stderr, (str, Path)):
            stderr = open(stdout, 'w')
            self.string2stderr = True

        super().__init__(cmd, stdin=stdin, stdout=stdout,
                         stderr=stderr, **kwargs)

    def wait(self, *args, **kwargs):
        val = super().wait(*args, **kwargs)
        if self.string2stdin and self.stdin:
            self.stdin.close()
        if self.string2stdout and self.stdout:
            self.stdout.close()
        if self.string2stderr and self.stderr:
            self.stderr.close()
        return val


class ProcStream(easyproc.ProcStream):
    def __or__(self, other):
        if isinstance(other, easyproc.ProcStream):
            other.kwargs['stdin'] = self
            return other
        return NotImplemented

    def __ror__(self, other):
        if isinstance(other, str):
            self.kwargs['input'] = other
        elif isinstance(other, subprocess.Popen):
            self.kwargs['stdin'] = other.stdout
        elif isinstance(other, io.IOBase):
            self.kwargs['stdin'] = other
        elif isinstance(other, abc.Iterable):
            self.kwargs['input'] = other
        else:
            return NotImplemented
        return self

    def __add__(self, other):
        try:
            return type(other)(self) + other
        except:
            return NotImplemented

    def __radd__(self, other):
        try:
            return other + type(other)(self)
        except:
            return NotImplemented


class _PipeRun:
    func = staticmethod(easyproc.run)

    def __init__(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs

    def __ror__(self, other):
        ProcStream.__ror__(self, other)
        return easyproc.run(*self.args, **self.kwargs)


easyproc.ProcStream = ProcStream
easyproc.Popen = Popen


def flatter(i):
    l = list(flatten(i))
    print(l)
    return l


def flatten(iterable):
    for i in iterable:
        if isinstance(i, abc.Iterable) and not isinstance(i, str):
            yield from flatten(i)
        else:
            yield i
