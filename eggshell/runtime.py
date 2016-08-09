#!/usr/bin/env python3
"""
this module builds the runtime environment for eggshell scripts, mostly through
importing a bunch of modules (especially items from easyproc) and some extra
functions, classes and types.

Then, it executes the code.
"""
import fileinput as _fileinput
import shlex as _shlex
import glob
import os
import re
from easyproc import (grab, run, Popen, ProcStream, CalledProcessError,
                      STDOUT, PIPE, DEVNULL, ALL)
from .compiler import Compiler as _Compiler
import sys as _sys
import io as _io
_sys.path.append('.')

ARGV = _sys.argv[1:]

_glob = glob.glob
glob = glob.iglob


class _EnvWrapper:
    def __getattr__(self, name):
        return os.environ[name]

    def __setattr__(self, name, value):
        os.environ[name] = value


env = _EnvWrapper()


class _Redirector:
    def __gt__(self, filename):
        return open(filename, 'w')

    def __rshift__(self, filename):
        return open(filename, 'a')


redirect = _Redirector()


def obj2args(obj):
    """return a suitably quoted string from obj. If obj is a string, quote it
    as one arg. If it's an iterable, each item is a separately quoted arg.
    """
    if isinstance(obj, list):
        return obj
    elif isinstance(obj, str):
        return [obj]
    elif isinstance(obj, ProcStream):
        return list(obj.tuple)
    else:
        return list(obj)


class GlobError(Exception):
    """zsh does the service of throwing an error if a glob has no matches.
    eggshell does the same.
    """
    def __init__(self, globstring):
        self.string = globstring

    def __str__(self):
        return 'No files matching %s.' % repr(self.string)


def globarg(string):
    """takes a string with glob characters as input, returns a string with
    results as properly quoted args.
    """
    matches = obj2args(glob(string))

    if not matches:
        raise GlobError(string)

    return matches


class Pipe():
    """Special object that holds onto a command and runs it when it sees the
    `|` operator, piping the return-value of the previous expression to stdin
    doesn't keep the output. Just an implementation detail of eggshell.
    """
    def __init__(self, cmd, *args, **kwargs):
        self.cmd = cmd
        self.args = args
        self.kwargs = kwargs
        self._set_func()

    def _set_func(self):
        self.func = run

    def __ror__(self, stdin):
        self._reslove(stdin)
        return self.func(self.cmd, *self.args, **self.kwargs)

    def _reslove(self, stdin):

        if isinstance(stdin, ProcStream):
            self.kwargs['stdin'] = stdin.stream

        else:
            try:
                stdin.fileno()
                self.kwargs['stdin'] = stdin
            except (_io.UnsupportedOperation, AttributeError):

                if not isinstance(stdin, str):
                    stdin = '\n'.join(stdin)

                self.kwargs['input'] = stdin


class GrabPipe(Pipe):
    def _set_func(self):
        self.func = grab



class _RegexStarter:
    """_RegexStarter is initialized with a subclass of _RegexOp. When it sees the
    `/` operator, it returns a new instance of that class with the string
    following the `/` as pattern. This is how eggshell "regex operators", 'm',
    's', and 'split' are implemented.
    """
    def __init__(self, Class):
        self.Class = Class

    def __truediv__(self, pattern):
        return self.Class(pattern)

    def __repr__(self):
        string = str(self.Class)
        string = string[string.find('.')+1:-2]
        return '_RegexStarter(%s)' % string


class _RegexOp:
    "base-class for the three 'real' regex operators"
    def __init__(self, pattern):
        self.pattern = pattern


class _Substituter(_RegexOp):
    '''acts a bit like `s` in sed or perl, but not. If you put it on the right
    side of &= with a string on the left, it replaces everything in the string.
    pipe an iterable into it, and it returns a iterator that yeilds each item
    with the substitution.
    '''
    def __truediv__(self, argument):
        if hasattr(self, 'replacement'):
            if 'g' in argument:
                self.count = 0

            if 'g' != argument:
                argument = argument.replace('g', '')
                self.pattern = ('(?%s)' % argument + self.pattern)

        else:
            self.replacement = argument
            self.count = 1

        return self

    def __rand__(self, string):
        if isinstance(self.pattern, str):
            self.pattern = re.compile(self.pattern)
        return self.pattern.sub(self.replacement, string, self.count)

    def __ror__(self, iterable):
        if isinstance(iterable, str):
            return iterable & self

        return map(self.__rand__, iterable)


class _Matcher(_RegexOp):
    """acts a bit like /PATTERN/ in perl (and awk), or like grep if you pipe an
    iterable into it. If you put it on the right side of & with a string on the
    right, it returns a match object (if there is a match). This can be used as
    a test, since a match will evaluate to True in a boolean context. If you
    use it with `==`, it will only return a match if the pattern matches the
    entire string.
    """
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
        return filter(self.__rand__, iterable)


class _Splitter(_RegexOp):
    """this is a bit like the split function in perl with &=, and a bit like
    awk -F with a iterable piped in.
    """
    def __truediv__(self, options):
        self.pattern = ('(?%s)' % options) + self.pattern
        return self

    def __rand__(self, string):
        if isinstance(self.pattern, str):
            self.pattern = re.compile(self.pattern)
        return self.pattern.split(string)

    def __ror__(self, iterable):
        return map(self.__rand__, iterable)


class _SplitStart(_RegexStarter):
    """add some extra functions to the split-starter so you can pipe objects
    into without specifying a regex. This is more or less like awk.
    """
    def __rand__(self, string):
        return string.split()

    def __ror__(self, iterable):
        return map(str.split, iterable)


s = _RegexStarter(_Substituter)
m = _RegexStarter(_Matcher)
split = _SplitStart(_Splitter)


def cd(directory):
    """got to have cd, right? cd() will expand '~' before calling os.chdir()
    this may eventually be implemented as if it were a shell command for
    interactive use in the future
    """
    directory = os.path.expanduser(directory)
    os.chdir(directory)
    return os.getcwd()


#def _main():
_code = _Compiler(open(_sys.argv[1], 'rb'))
try:
    exec(_code.output)
#    print(_code.output)
except:
    print(_code.output)
    raise


#if __name__ == '__main__':
#    main()
