#!/usr/bin/env python3
import os
import io
import re
import sys
import tokenize
from . import builtin
from collections import abc
from pprint import pprint
from tokenize import NEWLINE, NL, NAME, STRING, COMMENT, INDENT, DEDENT
COMMANDS = set()
PREAMBLE = '''\
from eggshell.proc import run, grab, _PipeRun, Popen
from eggshell.builtin import env, _dir_stack
from eggshell import builtin
from eggshell.rewrap import _Matcher, Subber
from easyproc import CalledProcessError, PIPE, STDOUT, DEVNULL
from glob import iglob as glob\n'''


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


def maketree(tokens, preamble=False):
    """parse everything that matters for eggshell into a tree"""
    tree = []
    # encoding string
    tree.append([next(tokens)])
    # if preamble:
    if preamble:
        tok = next(tokens)
        while tok.type in {COMMENT, NL, STRING}:
            tree[0].append(tok)
            tok = next(tokens)
        tokens.unget(tok)
        tree[0].append(PREAMBLE)
    else:
        tree[0].append((NEWLINE, ''))
    tree.extend(buildnodes(tokens))
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
            node.append(prep(node.pop()))
        elif tok.type in {NEWLINE, INDENT}:
            yield prep(node)
            stack.clear()
            node = []
    yield node


def get_arg(token):
    remainder = token.line[token.start[1]:]
    word = re.split('[\s,|()]', remainder, maxsplit=1)[0]
    return word


def prep(node):
    # skip characters that don't matter
    new_node = []
    for i, t in enumerate(node):
        if isinstance(t, list):
            break
        elif t.type in {NL, COMMENT, DEDENT} or t.string == '(':
            new_node.append(t)
        else:
            break

    new_node.extend(make_pipe_groups(node[i:]))
    return new_node


def make_pipe_groups(node_part):
    new_part= []
    segment = []
    for t in node_part:
        segment.append(t)
        if isinstance(t, tokenize.TokenInfo) and t.string == '|':
            new_part.extend(process(segment, 'grab'))
            segment.clear()
    if segment[-1].string == ')':
        new_part.extend(process(segment, 'grab'))
    elif new_part:
        new_part.extend(process(segment, '_PipeRun'))
    else:
        new_part.extend(process(segment, 'run'))
    return new_part


def process(segment, runfunc):
    new_seg = []

    if isinstance(segment[0], list):
        return segment

    arg = get_arg(segment[0])
    if arg in COMMANDS:
        new_seg.append(runfunc + '([')
        i, args = gen_args(segment)
        new_seg.extend(args)
        new_seg.append(']')

    elif arg in builtin.REGISTERED:
        new_seg.append('builtin.{}('.format(segment.pop(0).string))
        i, args = gen_args(segment)
        new_seg.extend(args[:-1])

    else:
        return regex_scan(segment)

    if segment[i+1] is not segment[-1]:
        new_seg.extend(segment[i:-1])
    new_seg.extend((')', segment[-1]))
    return new_seg


def gen_args(segment):
    args = []
    new_seg = []
    i = -1
    for i, t in enumerate(segment[:-1]):
        if isinstance(t, list) or t.type == STRING:
            new_seg.extend(split_args(args))
            start, end = interpolate(t)
            try:
                del new_seg[-1] # comma
            except IndexError:
                start = ''
            new_seg.extend((start, t, end))

        elif t.type == NL:
            new_seg.extend(split_args(args))
            new_seg.append(t)
        elif t.string == ',':
            break
        else:
            args.append(t)

    new_seg.extend(split_args(args))
    return i, new_seg


def interpolate(t):
    if isinstance(t, list):
        schar = t[0].line[t[0].start[1]-1]
        echar = t[-1].line[t[-1].end[1]]
    else:
        schar = t.line[t.start[1]-1]
        echar = t.line[t.end[1]]

    if schar not in ' \t':
        start = '+'
    else:
        start = ','
    if echar not in ' \t\n),|':
        end = '+'
    else:
        end = ','

    return start, end


def split_args(args):
    """Take collected shell arguments and split them correctly.

    Beware that this function has the side-effect of clearning the argument
    list!
    """
    if not args:
        return []

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
        match = re.search(r'env.\w+', arg)
        if match:
            start, end = match.span()
            arg = ''.join((repr(arg[:start]), '+',
                           match.group(), '+',
                           repr(arg[end:])))
        else:
            arg = repr(arg)

        if '*' in arg:
            new_args.extend(('glob({}, recursive=True)'.format(arg),
                             ','))
        else:
            new_args.extend((arg, ','))
    return new_args


def regex_scan(segment):
    # segment = iter(segment)
    # new_seg = []
    # for t in segment:
    #     if t.isinstance(list):
    #         new_seg.append(t)
    #         continue

    #     remaining_line = 
    #     elif t.line[t.start:t.start+2] == '=~':
    #         next(t)
    #         new_seg.append('&=')
    #         new_seg.append(post_op_remake(segment, next(t)))
    #         continue
    #     else:
    #         elements = rematch(t)
    #         if elements is not None:
    return segment



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
    import tempfile
    tree = maketree(Tokens(sys.argv[1]))
    try:
        code = tokenize.untokenize(flatten(tree)).decode()
    except:
        pprint(tree, indent=4)
        raise
    print(code)
    del sys.argv[0]

    tf = tempfile.NamedTemporaryFile('w')
    tf.write(code)
    tf.flush()
    ns = {'__name__': '__main__'}
    exec(PREAMBLE, ns)
    try:
        exec(compile(code, tf.name, 'exec'), ns)
    except Exception as e:
        # pprint(tree, indent=4)
        print(code)
        raise
