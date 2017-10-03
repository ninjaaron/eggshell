import os
from collections import abc


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
REGISTERED = set()
_dir_stack = []

def register(func):
    REGISTERED.add(func.__name__)
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
    print(*unpacker(args), **kwargs)


def unpacker(args):
    for a in args:
        if isinstance(a, str):
            yield a
        else:
            yield from a
