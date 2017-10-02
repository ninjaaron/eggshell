#!/usr/bin/env python3
import os
import io
import re
import sys
import tokenize
import functools
from collections import abc
from pprint import pprint
from tokenize import NEWLINE, NL, NAME, OP, STRING, COMMENT
COMMANDS = set()


class Tokens(abc.Iterator):
    def __init__(self, filename):
        self.file = open(filename, 'rb')
        self.tokens = tokenize.tokenize(self.file.readline)
        self.stack = []

    def __next__(self):
        if self.stack:
            return self.stack.pop()
        else:
            try:
                return next(self.tokens)
            except StopIteration:
                self.file.close()
                raise

    def unget(self, t):
        self.stack.append(t)


def do_shimport(tokens, t):
    COMMANDS.update(re.split('[(),\s]+', t.line))
    linenum = t.start[0]
    for t in tokens:
        if t.type == NEWLINE:
            COMMANDS.discard('shimport')
            COMMANDS.discard('')
            break
        elif t.start[0] == linenum:
            continue
        COMMANDS.update(re.split('[(),\s]+', t.line))
        linenum = t.start[0]


def maketree(tokens):
    """parse everything that matters for eggshell into a tree"""
    tree = []
    # encoding string
    tree.append([next(tokens)])
    # import easyproc
    tok = next(tokens)
    while tok.type in {COMMENT, NL, STRING}:
        tree[0].append(tok)
        tok = next(tokens)
    tokens.unget(tok)
    tree[0].extend(maketok('from eggshell import proc\n'
                           'from glob import iglob as glob\n'))
    node = True
    while node:
        node = buildnodes(tokens)
        tree.append(node)
    return tree


def buildnodes(tokens):
    # build the tree
    node = []
    stack = []
    for tok in tokens:
        if tok.line.startswith('shimport'):
            do_shimport(tokens, tok)
        elif tok.string == '(':
            stack.append(node)
            node.append([tok])
            node = node[-1]
        else:
            node.append(tok)

        if tok.string == ')':
            node = stack.pop()
            node.append(process_parens(node.pop()))
        elif tok.type == NEWLINE:
            return process_line(node)
    return node


def get_arg(token):
    return token.line[token.start[1]:].split(maxsplit=1)[0]


def processor(func):
    def wrapper(node):
        new_node = []
        for i, t in enumerate(node):
            if isinstance(t, tokenize.TokenInfo):
                if t.type == NL or t.string == '(':
                    new_node.append(t)
                else:
                    break
            else:
                return node

        if not (t.type == NAME and t.string in COMMANDS):
            return node

        new_node.append(func(node))

        args = []
        for j, t in enumerate(node[i:]):
            if isinstance(t, tokenize.TokenInfo):
                if t.type == STRING:
                    new_node.extend(split_args(args))
                    new_node.extend((t, (OP, ',')))
                elif t.type == NL:
                    new_node.extend(split_args(args))
                    new_node.append(t)
                elif t.type == NEWLINE or t.string == ')':
                    new_node.extend(split_args(args))
                    new_node.append('])')
                    break
                else:
                    args.append(t)
            else:
                new_node.extend(split_args(args))
                new_node.extend((t, (OP, ',')))

        new_node.extend(node[i+j:])
        return new_node
    return wrapper


@processor
def process_line(node):
    return 'proc.run(['


@processor
def process_parens(node):
    return 'proc.grab(['


def split_args(args):
    """Take collected shell arguments and split them correctly.

    Beware that this function has the side-effect of clearning the argument
    list!
    """
    if args:
        start = args[0].start
        sargs = []
        for i, arg in enumerate(args):
            if arg.end[0] == start[0]:
                endarg = arg
            else:
                end = endarg.end[1]
                sargs.extend(endarg.line[start[1]:end].split())
                start = arg.start
        end = endarg.end[1]
        sargs.extend(endarg.line[start[1]:end].split())
        args.clear()
        new_args = []
        for arg in sargs:
            arg = os.path.expanduser(arg)
            if '*' in arg:
                new_args.extend(maketok(
                    'glob({!r}, recursive=True),'.format(arg)))
            else:
                new_args.extend(((STRING, repr(arg)), (OP, ',')))
        return new_args
    else:
        return []


def flatten(tree):
    """flatten the tree returned by maketree"""
    for i in tree:
        if isinstance(i, list):
            yield from flatten(i)
        elif isinstance(i, str):
            yield from maketok(i)
        else:
            yield i


def maketok(string):
    toks = tokenize.tokenize(io.BytesIO(string.encode()).readline)
    tokens = []
    try:
        for t in toks:
            tokens.append(t)
    except tokenize.TokenError:
        pass
    else:
        del tokens[-1]
    del tokens[0]
    return tuple(t[:2] for t in tokens)


def main():
    tree = maketree(Tokens(sys.argv[1]))
    try:
        code = tokenize.untokenize(flatten(tree)).decode()
    except tokenize.TokenError:
        pprint(tree, indent=4)
        raise
    print(code)
    try:
        exec(code, {'__name__': '__main__'})
    except Exception:
        # pprint(tree, indent=4)
        print(code)
        raise
