import os
from collections import abc
REGISTERED = {}
_dir_stack = []
VALUES = {
    't': True,
    'true': True,
    'f': False,
    'false': False,
    'none': None,
    'null': None
}


class EnvObj:
    def __getattr__(self, key):
        return os.environ[key]

    def __setattr__(self, key, value):
        os.environ[key] = value

    def __delattr__(self, key):
        del os.environ[key]

    def __repr__(self):
        return repr(os.environ)


env = EnvObj()


def register(func):
    REGISTERED[func.__name__] = func
    return func


@register
def cd(directory):
    os.chdir(os.path.expanduser(directory))
    env.PWD = os.getcwd()
    return env.PWD


@register
def pushd(directory):
    _dir_stack.append(cd(directory))


@register
def popd(directory):
    return cd(_dir_stack.pop())

@register
def echo(*args, **kwargs):
    nargs, nkwargs = muddle(args, kwargs)
    print(*unpacker(nargs), **nkwargs)


def unpacker(args):
    for a in args:
        if isinstance(a, (str, int)):
            yield a
        else:
            yield from a


def muddle(args, kwargs):
    args = iter(args)
    nargs, nkwargs = [], {}
    for arg in args:
        if isinstance(arg, str) and arg.startswith('--'):
            key, *val = arg[2:].split('=', maxsplit=1)
            if not val:
                val = next(args)
            else:
                val = val[0]
            try:
                val = int(val)
            except ValueError:
                val = VALUES.get(val.lower(), val)
            nkwargs[key] = val
        else:
            nargs.append(arg)
    nkwargs.update(kwargs)
    return nargs, nkwargs

