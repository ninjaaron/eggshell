#!/usr/bin/env python3
import os
import io
import re
import shlex
import keyword
import builtins
from tokenize import tokenize, untokenize, TokenError
from token import NAME, OP, STRING, NUMBER, ENDMARKER, INDENT, DEDENT

# GLOBCHARS is used to detect if arguments for shell commands need to
# be expanded. WORD is a regex to match the ends of args in a shell command
GLOBCHARS = set('[]*?')
WORD = re.compile('[\'|,"()\s]')
REDIR_FILE = re.compile(r'[\'|,"()\n]')
CLOSE_REGEX = set('\n|):,+-*/%@!=[]{}')
REGEX_OPTS = re.compile(r'=~(s|m|split) /')
ARG_END = re.compile(r'[,\n|;]')


def str2tok(string):
    "generate tokens for arbitrary string input."
    tokens = []
    try:
        for t in tokenize(io.BytesIO(string.encode('utf-8')).readline):
            tokens.append(t)
    except TokenError:
        pass
    # delete the first and last tokens generated. They are unique to
    # to the beginning and end of the file.
    else:
        del tokens[-1]
    del tokens[0]
    return tokens


# generate some tokens for special functions and classes in the
# execution environment.
RUNPROC = str2tok('run(')
CAPTUREPROC = str2tok('grab(')
PIPE = str2tok('Pipe(')
CAPTUREPIPE = str2tok('GrabPipe(')


class Compiler:
    """This class takes a file of "eggshell" python and generates regular
    python from it by tokenizing it, examining the tokens, producing new
    tokens, and untokenizing.
    """
    def __init__(self, bytes_file_object):
        # We start by looking for all executables in PATH, so we'll know a
        # shell command when we see it.
        _builtins = set(dir(builtins) + keyword.kwlist)
        _builtins.discard('[')
        self.commands = set(i for path in os.environ['PATH'].split(os.pathsep)
                            for i in os.listdir(path)
                            if os.access(path+'/'+i, os.X_OK)
                            and i not in _builtins)
        self.source = bytes_file_object
        self._unbind()
        self.tokens = tokenize(self.source.readline)
        self.result = []
        self.regexen = []
        self._toplevel()
        try:
            self.output = untokenize(self.result).decode()
        except TypeError:
            print(*self.result, sep='\n')
            raise
        self._regex_op()

    def bytecode(self):
        return compile(self.output)


    def extendtok(self, token_list):
        """basically a wrapper on list.extend. I wrote it as a method in case I
        want to change the implementation in the future. Also, tries to get rid
        of names used from the command list to try and avoid conflicts of that
        sort. shell commands that looked like names originally have already
        been converted to strings at this point.
        """
        for t in token_list:
            if t[0] == NAME:
                self.commands.discard(t[1])
        self.result.extend(token_list)


    def _toplevel(self):
        r"""To the eggshell compiler, there are basically only two levels that
        matter: outside of parentheses (toplevel) and inside of parentheses.
        Compiler._toplevel() looks at all tokens that occur outside of
        parentheses and decides what to do with them. Most are unchanged, but
        there are three characters that might indicate the beginning of a shell
        command: \n, (, and |. When we encounter these characters, we call the
        appropriate function to deal with each scenario.
        """
        t = next(self.tokens)
        # go through any codeless header info, like encoding
        while t.line == '':
            self.extendtok([t[:2]])
            t = next(self.tokens)

        self._newline(t)
        while True:
            try:
                t = next(self.tokens)
            except StopIteration:
                return
            self.extendtok([t[:2]])
            if t.string == '\n':
                t = next(self.tokens)
                if t.type == ENDMARKER:
                    self.extendtok([t])
                    break
                self._newline(t)

            elif t.string == '(':
                self._parentheses()

            elif t.string == '|':
                self._pipe('\n')

            self._regex_gen(t)


    def _newline(self, t):
        """checks if the new line begins with a shell command, if so, send it
        along to Compiler._makeproc to generate the proper python.
        """
        t = self._eatwhitespace(t)
        # get intend and dedent out of the way first.
        if t.type in {INDENT, DEDENT}:
            self.extendtok([t])
            t = next(self.tokens)

        if self._isexecutable(t, '\n'):
            # command output outside of parentheses is not captured unless it
            # precedes a pipe.
            function = self._grab_or_not(t)
            self._makeproc(t, '\n', function)
        else:
            self.extendtok([t])
            self._regex_gen(t)


    def _parentheses(self):
        """Similar to Compiler._newline(), but for parentheses. This is really
        the only function that where recursion comes in because parentheses are
        really the only nestable code structure that eggshell needs to care
        about. It's like Lisp, only different in every way.
        """
        while True:
            t = next(self.tokens)
            t = self._eatwhitespace(t)
            if self._isexecutable(t, ')'):
                self._makeproc(t, ')', CAPTUREPROC)

            else:
                self.extendtok([t[:2]])
                if t.string == '(':
                    self._parentheses()
                elif t.string == '|':
                    self._pipe(')')
                elif t.string == ')':
                    break
                else:
                    self._regex_gen(t)
        return t


    def _pipe(self, closer):
        """Similar to Compiler._newline, but for things following a pipe. In
        keeping with eggshell's policy of doing as little as possible in the
        compiler, the only thing this does is instantiate some special classes
        that overload the `|` operator
        """
        t = next(self.tokens)
        t = self._eatwhitespace(t)
        if self._isexecutable(t, closer):
            # determine runtime function (or class) to use based on context.
            if closer == '\n' and self._grab_or_not(t) == RUNPROC:
                function = PIPE
            else:
                function = CAPTUREPIPE
            self._makeproc(t, closer, function)

        elif t.string in {'s', 'm', 'split'}:
            self.extendtok([t[:2]])
            self._regex_gen(t)
        else:
            self.extendtok([t[:2]])


    def _eatwhitespace(self, t):
        r"""go through any blank lines after trigger tokens [\n, (, and |] and
        returns the next token with any meaningful code.
        """
        while t.string == '\n':
            self.extendtok([t[:2]])
            t = next(self.tokens)
        return t


    def _isexecutable(self, t, closer):
        "check if the next bit of line looks like an executable"
        word = t.line[t.start[1]:].split(maxsplit=1)
        word = word[0] if word else ''
        word = word.split(closer, maxsplit=1)[0]
        word = word = word.split('|', maxsplit=1)[0]
        word = word = word.split(',', maxsplit=1)[0]
        return (word in self.commands
                or ('/' in word and os.access(word, os.X_OK))
                ) # and t.line[t.start[1]:]


    def _add_args(self, closer):
        closers = {closer, '|'}
        t = next(self.tokens)
        self.extendtok([t[:2]])
        while self._next_char(t) not in closers:

            if t.string == '(':
                t = self._parentheses()

            elif t.string in {'stdout', 'stderr'} \
            and self._next_char(t) == '>':
                self.extendtok(str2tok('=redirect'))
                self.extendtok([next(self.tokens)])
                t = next(self.tokens)

                if t.type != STRING and t.type != NUMBER:
                    word, longword, wordend = self._get_word(t, REDIR_FILE)

                    self.extendtok(str2tok(repr(longword)))

                    while t.end[1] < wordend:
                        t = next(self.tokens)

                else:
                    self.extendtok([t[:2]])

            else:
                t = next(self.tokens)
                self.extendtok([t[:2]])

        ext = [(OP, ')')]
        self.extendtok(ext)


    def _makeproc(self, t, closer, function):
        """This is where the magic happens. This is where lines that look like
        shell commands get stuck in the right constructs (depending on context)
        to make the execute (more or less) like shell commands. However, these
        commands are never actually given a shell. eggshell makes an effort to
        be safe.
        """
        self.extendtok(function)
        # does not consume the closing character. Closing characters are
        # characters that will mark the end of a shell command.
        closers = {closer, '|', '\n'}
        start = t.start[1]

        # iterate until we see that the next token will be a closing character
        while self._next_char(t) not in closers:
            t = next(self.tokens)

            # what to do for unquoted arguments
            if t.string == ',':
                self.extendtok(str2tok('%s,' % 
                            repr(shlex.split(t.line[start:t.start[1]]))))
                self._add_args(closer)
                return
            elif t.type != STRING and t.string != '(':
                word, longword, wordend = self._get_word(t)

                # if there are glob characters in the argument, glob 'em. This
                # happens at runtime. We just generate the function call here.
                if GLOBCHARS.intersection(word):
                    self.extendtok(str2tok(
                        '{}+_glob({})'.format(
                        repr(shlex.split(t.line[start:t.start[1]])),
                        repr(longword))))
                    if t.line[t.start[1]+len(word)] not in closers:
                        self.extendtok([(OP, '+')])
                    else:
                        self.extendtok([(OP, ')')])
                        while t.end[1] < wordend:
                            t = next(self.tokens)
                        return

                    while t.end[1] < wordend:
                        t = next(self.tokens)

                    start = t.end[1]

                else:
                    while t.end[1] < wordend:
                        t = next(self.tokens)
            # expand expressions in parentheses. Look at eggshell.obj2args for
            # more info.
            elif t.string == '(':
                self.extendtok(
                    str2tok('%s+obj2args(' %
                        repr(shlex.split(t.line[start:t.start[1]]))))
                t = self._parentheses()

                if t.line[t.end[1]] not in closers:
                    self.extendtok([(OP, '+')])

                else:
                    self.extendtok([(OP, ')')])
                    return

                start = t.start[1] + 1

            elif t.type == STRING:
                part = '{}+[{}]'.format \
                      (repr(shlex.split(t.line[start:t.start[1]])), t.string)
                self.extendtok(str2tok(part))

                # This crazy crap is how you find the letter after a multi-line
                # token (i.e., a triple-quoted string with literal newlines).
                if t.line[t.start[1]+len(t.string):] not in closers:
                    self.extendtok([(OP, '+')])

                else:
                    self.extendtok([(OP, ')')])
                    return

                start = t.end[1]

        # close up the command function
        self.extendtok(str2tok('%s)' %
            repr(shlex.split(t.line[start:t.end[1]]))))


    def _grab_or_not(self, t):
        """figure out whether to just run a command, or whether to keep its
        output
        """
        tokens = str2tok(t.line[t.start[1]:])
        parens = 0
        for tok in (tok.string for tok in tokens):
            if tok == '(':
                parens += 1

            elif tok == ')':
                parens -= 1

            elif tok == '|' and parens >= 0:
                return CAPTUREPROC
        return RUNPROC


    def _regex_gen(self, t):
        """generate the special, pre-compiled regex commands"""
        # the complier does as little as possible -- but, it does compile regex
        # before runtime where it can.
        if (self._next_char(t) == '/'
            and t.string in {'m', 's', 'split'}):
            maxslash = 3 if t.string == 's' else 2
            self.extendtok([next(self.tokens)])
            t = next(self.tokens)
            if t.type == STRING and self._next_char(t) == '/':
                self.extendtok(str2tok(
                    '_code.regexen[%d]' % len(self.regexen)
                    ))
                regex = eval(t.string)
            else:
                self.extendtok([t[:2]])
                if t.string == '(':
                    self._parentheses()
                regex = None

            slashcount = 1
            while True:
                t = next(self.tokens)

                if t.string == '/':
                    slashcount += 1
                    if slashcount >= maxslash:
                        break

                self.extendtok([t[:2]])

                if t.string == '(':
                    self._parentheses()

            if self._next_char(t) not in CLOSE_REGEX:
                t = next(self.tokens)

                if regex:
                    if 'g' in t.string:
                        flags = t.string.replace('g', '')
                        regex = '(?%s)%s' % (flags, regex) if flags else regex
                        self.extendtok(str2tok("/'g'"))
                    else:
                        regex = '(?%s)%s' % (t.string, regex)

                    self.regexen.append(re.compile(regex))

                else:
                    self.extendtok(str2tok('/'+repr(t.string)))

            elif regex:
                self.regexen.append(re.compile(regex))


    def _regex_op(self):
        """change perl-like regex operator (not that it's technically a regex
        oerpator in perl...) to some ops I overloaded for special regex objects
        """
        def subs(match):
            sub = {
                's': '&= s/',
                'split': '&= split/',
                'm': '& m/'}[match.group(1)]
            return sub

        self.output = REGEX_OPTS.sub(subs, self.output)


    def _unbind(self):
        source = self.source.read()
        unbind = re.compile(br'unbind\s')

        for line in source.splitlines():
            if unbind.match(line):
                for name in line.split()[1:]:
                    self.commands.discard(name.decode())

        source = re.sub(br'unbind\s.*?\n', b'', source)
        self.source = io.BytesIO(source)

    def _next_char(self, t):
        return t.line[t.end[1]:].lstrip(' ')[0:1]

    def _get_word(self, t, endpattern=WORD):
        word = endpattern.split(t.line[t.start[1]:], maxsplit=1)[0]
        longword = os.path.expanduser(word)
        wordend = t.start[1] + len(word)
        return (word, longword, wordend)
