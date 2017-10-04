eggshell - Python for sys admins
================================

.. image:: doc/eggshell.svg
   :height: 300 px

Eggshell is undergoing a complete rewrite at the moment. This documents
the old version.

.. contents::

``eggshell`` is a non-interactive (for now) command shell that aims
to be a pure superset of Python (i.e. it should run any valid Python
script -- provided names in the script don't conflict with names of
system commands).

An eggshell script compiles to Python, which is then executed in the
Python interpreter. The compiler itself aims to do as little as possible
and leaves most of the work to special Python functions and types added
to its execution environment at runtime. The most useful of these are
available separately in the easyproc_ module, on which eggshell is
built. eggshell also offers some sed/awk/Perl-inspired regex
operations that try to compile before runtime. I miss regex as built-in
type from the wonderful scripting languages mentioned above.

eggshell never implicitely runs anything in the system shell, and
therefore is safe from injection by default.

installation
------------
You can install eggshell with pip3. It *might* work with python2 as
well, but no promises! After installation, any script with an eggshell
shebang should work: ``#!/usr/bin/env eggshell``.

syntax
------
eggshell syntax is Python syntax with one or two add-ons. The main thing
you'll notice is that you can run shell commands.

.. code:: python

  #!/usr/bin/env eggshell
  ls -l

That does about what you'd expect with any ordinary shell. You can also
capture the output of the command using parentheses. This is about like
using backticks or ``$(command)`` substitution in POSIX shells.

.. code:: python

  for line in (ls -l):
      col = line.split()
      print(col[2], col[8])

This prints the owner and filename of each file (with gnu's ``ls``). You
will notice that iterating on command output returns lines (with
trailing newline removed). Many shell commands print tabular data where
each line represents a row. For this reason, when you do iteration or
index operations on command output, it looks like a list of lines. In
other cases, it acts like a string. This is the dao of the shell.

By the way, the parentheses for function calls count as a place where
you can capture command output, so ``print(ls -l)`` works as expected.

You can also pipe commands together in the usual way. This is
implemented with Python operators, not the system shell.

.. code:: python

  for filename in (ls|fgrep '.py'):
      mv (filename) destination-directory

You may note that here, I have a Python variable in parentheses inside
of a shell command. Parentheses work both ways in eggshell. You can put
Python variables or expressions inside of parentheses to substitute its
return value into the command. Any string passed in this way will count
as one argument (no quotation-mark shenanigans) Any other kind of
iterable will be turned into a list of arguments. You can also use the
output of commands in this way. Just remember that commands that output
more than one line will turn each line into a new argument! Therefore,
``ls (ls)`` is the same as ``ls *``.

Yes, globbing also works inside of a shell command. If you want file
globbing in a Python expression, use ``glob()`` (an alias to
``glob.iglob()``)

Getting back to pipes, you can also pipe Python expressions into a
process.

.. code:: python

  newlist = list_of_strings | sed 's/py/PY/g'

If you pipe a string into the process, it goes in unmodified. If you
pipe in another type of iterable, the items are joined with newlines
before being sent to stdin.

Note that if a process exits with an error, it will raise an
``CalledProcessError`` exception, which you need to handle. This is very
Pythonic ("errors should never pass silently -- unless explicitly
silenced"), but this is not typical shell behavior. Code accordingly!

That about covers the built-in support for running processes in Python.
eggshell has no special support for shell-like redirection. However, it
does import the ``run()`` function from easyproc_, which allows any
redirection you can imagine, courtesy of subprocess.Popen

Redirection HowTo
~~~~~~~~~~~~~~~~~
For more complex redirection that involves more than capturing or piping
stdout, use the ``run()`` function, an alias of ``easyproc.run()``,
which takes all the standard ``subprocess.Popen()`` arguments and a
couple of its own.

- If you want to stick a string into the stdin in a ``run()`` call, put in
  the ``input`` paremeter; ``run('sed "s/py/PY/g", input='my cool py
  string')``. To send a file to stdin, do ``run('sed "s/py/PY/g",
  stdin=open('inputfile.txt'))``
- To capture output you also have the ``grab()`` function from easyproc,
  which returns the stdout by default, but can return stdout and stderr
  in a single stream (like ``2>&1``) if you set the ``both`` paramether
  to ``True``.
- To capture streams separately use ``run('command', stdout=PIPE,
  stderr=PIPE)``. This function returns a ``CompletedProcess`` instance,
  with ``stdout`` and ``stderr`` attributes which can be dealt with
  separately.
- For redirection to files, you can use Python file objects
  ``run('command', stdout=open('outputfile.txt', 'w'))`` (mode 'w' will
  clobber the file contents like ``>`` in a POSIX shell, 'a' will append
  like ``>>`` in a POSIX shell.
- Redirect stderr to /dev/null ``run('command', stderr=DEVNULL)``
- combine stdout and stderr and append the result to a log file:
  ``run('command', stderr=STDOUT, stdout=open('logfile', 'a'))``

These operations are identical to how they work with the subprocess
module. The only difference is that ``run`` and ``grab`` can take
commands in the form of strings or lists of args, where subprocess
commands require a list of arguments unless they grant a shell. ``run``
in particular is a clone of ``subprocess.run()`` that defaults to
unicode, can take a string as a command, and returns special strings for
stdout and stderr that you can iterate on as lists of lines. You can
learn more about options with the ``run`` function by reading the
subprocess documentations for 3.5+

Regex Objects
~~~~~~~~~~~~~
One handy thing eggshell is that, if you're new to Python and you need
to bang out a quick and dirty script, you can pipe command output or
Python objects to external filters such as ``sed``, ``grep``, ``awk`` or
whatever. eggshell is all about bring the power of tools you already
know from the shell into Python. However, there are good reasons not to
use external programs like these. In particular, if you're in a loop,
and you're calling one of these filters thousands or millions of times,
your program will be orders of magnitude slower than if you use Python
objects. Even using Python regex in loops can be expensive if you don't
know what you're doing (i.e. you need to compile the regex before the
loop begins).

eggshell provides some special regex objects that will be familiar to
people who already know sed, awk or especially Perl (I really love Perl
-- almost as much as I hate it!). In addition to providing a terse, more
traditional way to write common regex operations, the eggshell compiler
compiles regex objects ahead of time if possible, to save the user from
worrying about whether they are using the operation in a loop (there are
still cases where regexes will need to be compiled manually, but they
will be fewer; i.e. basically the same situations where you'd need to
compile a regex in Perl). These are the special eggshell regex
operations:

.. code:: python

  s/'pattern'/'replacement'/flags # preform sed-like substitutions
  m/'pattern'/flags # check if a string matches the pattern
  split/'pattern'/flags # split a string to a list on pattern

Note that unlike regex literals in awk, Perl, Ruby, etc., these patterns
(and replacement in the case of ``s``) are quoted string. Be sure to use
raw strings (``r'string'``) to "unescape" the usual escape characters,
so backslashes will be passed to the regex engine.

The basic thing to remember with these expressions is that, when used
with the ``=~`` operator, they work with strings, and when used with the
``|`` operator, they work on iterables containing strings.

.. code:: python

  # =~ with the substitutor reasigns the variable to the output, as in
  # Perl, and similar to `mystring += otherstring` in Python.
  for filename in (ls):
      filename =~ s/'py'/'PY'/g
      print(filename)

  # Do the same thing in a terser way with a pipe:
  for filename in (ls) | s/'py'/'PY'/g 
      print(filename)


  # use the matcher operation in tests:
  if 'great string' =~ m/'\w*\s*\w*'/:
      (do stuff)

  # piping into the matcher works like grep; returns an iterable that
  # contains only matching strings.
  for filename in (ls) | m/'\.py$'/i:
      print(filename)


  # split splits stuff. split on commas:
  mycvsrow =~ split/','/

  # split all the lines in a cvs file with a pipe. This is a bit like
  # your awk
  for col in open('mydata.cvs') | split/','/:
      print(col[0], col[3])

  # you can also pipe to split without a pattern, which will split on
  # whitespace. This is implemented with str.split(), rather than regex.
  for line in (ls -l) | split:
      (do stuff with fields)

If you are familiar with the ``re`` module, you will see that the
eggshell regex operations with ``=~`` are little more that pre-compiled,
perl-inspired syntactic sugar for the functions they wrap; ``re.sub()``,
``re.search()`` and ``re.split()`` respectively. When combined with
iterables and a pipe, their convenience is multiplied.

Note that the 'pattern' in these operations need not actually be a
string literal. Any Python expression which evaluates to a string (or
compiled regex object) will work. However, the pattern must be a string
literal for the ahead-of-time regex compilation to work, as in Perl or
Ruby. (How can you compile before runtime if you don't know what the
variables are?)

Likewise, the 'replacement' in a substitutor operation can also be a
Python expression. Like ``re.sub``, the replacement argument can be a
function that takes a ``re.Match`` instance as an argument and returns a
string. When using a lambda expression be sure to put the entire thing
in parentheses because lambda precedence will screw with the ``/``
operators (which are overloaded in the runtime, not dealt with by the
compiler).

Flags are implemented internally with ``(?aiLmsux)`` syntax (see the
documentations for the ``re`` module), so any letter you'd put in there
is a valid flag. Additionally, the substitutor supports the ``g`` flag
for global substitution. Without, it substitutes only the first
match. I personally think Perl and sed are stupid for not defaulting to
global substitution, but, eh, ``ed``, and I'm not going to break the
time honored convention of not doing global by default just because I
have an opinion.

Performance
-----------
A smart man (habnabit) once said to me, "If you care that much about
performance, you shouldn't use Python." Python is not *too* slow for an
interpreted language, and it is much faster than bash by all accounts,
but it's slower than almost any language that compiles to machine code,
and is typically also slower than Java or Lua (though pypy is sometimes
competitive). Python and similar languages optimize development time at
the cost of machine time. That is usually a good trade on modern
hardware.

Anything that can be said about Python performance pretty-much goes
double for eggshell. eggshell performance should be just about identical
to normal Python performance, except for the fraction of a second extra
it takes at startup to pre-compile the eggshell code down to "normal"
Python, which then gets compliled down again to Python VM bytecode.

The real "problem" with eggshell is that it makes forking a process
extremely easy, and forking a process is rather expensive for the OS,
especially if you're doing it thousands or millions of times. Granted
eggshell will probably still be faster than bash in most cases (minus
startup time).

It's interesting that Python, known for it's clarity and
simple-yet-expressive syntax, makes "shelling out" to an external
process very verbose and (arguably) rather ugly. The Popen interface is
very complete and very powerful, but it ain't pretty! One must wonder if
there isn't a degree to which the developers are trying to discourage
using external processes.

In any case, eggshell makes it very easy to delegate tasks to forked
processes, so be careful not to over-do it. The general rule should be,
if performance is an issue, use pure python in the bottlenecks,
especially in loops that are repeated many times in a short amount of
time. There are exceptions to this:

- If you're not in a loop forking isn't exactly cheap, but it's fast
  enough on modern hardware that you won't notice unless you're doing it
  thousands of times.
- If your script spends more time in one instance of the forked process
  than it does in python, and the external processes is highly
  optimized. An example might be grepping through a file with tens of
  thousands of lines. GNU ``grep`` is highly optimized, and nothing you
  write in python will be faster, **provided you only run grep once, and
  don't create a new instance for every line**. Another example would be
  using imagemagick or ffmpeg. If you're generating media in a program
  like that, the time and resources spent creating a new process is
  trivial compared to the time spent inside of these heavily optimized
  programs.

There are also cases where creating a new process isn't necessarily good
or bad. If your program waits on input from a server or a user, or even
from a slow disk, creating extra processes isn't a big deal.
additionally, some system commands do things that are non-trivial to
reproduce in pure python. I like to use ``dmenu`` as my "GUI" for
everything that needs user interaction. It's both IO-bound, and it does
something that would take many lines to replicate in pure python, and so
it gets crammed into my python scripts frequently.

On the other hand, eggshell, like any shell, is targetted primarily at
administrative scripting, where convenience for the author trumps almost
any performance concern. eggshell aims to bring the power of python to
bear on such tasks, while reproducing most of the convenience of a
traditional shell language, and also providing an extral level of safety
from injection.

Regex Performance
~~~~~~~~~~~~~~~~~
Python's bundled regex module is pretty awesome and provides some
extremely useful interfaces. However, it isn't the fastest game in town.
Part of the flexibility is due to the fact that most of the user-exposed
interface is written in Python, sitting on top of a C engine, as opposed
to languages where regex is a built-in type implemented in C or C++ from
top to bottom. It's still pretty fast, but there are faster
implementations out there.

Pure string operations are always faster than regex. For one, there is
less logic involved, and for two, Python string methods are implemented
entirely in fairly (eh, mostly) optimized C. The rule should be, if you
don't need pattern matching, always use a string method/operation.

.. code:: python

  # instead of:
  if re.search('string', mystring):
  # aka `if mystring =~ m/'string'/:`
      (do stuff)
  # do this:
  if 'string' in mystring:
      (do stuff)


  # instead of:
  mystring = re.sub('string', 'STRING', mystring)
  # or mystring =~ s/'string/'STRING'/g

  # do this:
  mystring = mystring.replace('string', 'STRING')


  # instead of:
  for cols in iterable | split/','/:
      (do stuff)
  # do this:
  for cols in (i.split(',') for i in iterable):
      (do stuff)

Don't get me wrong. I love regex. If I didn't, I wouldn't have added all
that syntactic sugar for it in eggshell -- BUT, if you don't need
pattern matching, string operations will smoke regex every time, and are
typically easier to read. Get to know string methods and operations
well, and your scripts will ever be the speedier for it. That goes for
any built-in type, really.

Motivation
----------
When I started learning Python, I was already quite advanced in bash. I
began learning Python because I began trying to shoe-horn
nested data structures into associative arrays. This *might* be possible
in AWK, but it sucks real bad in bash, and certainly, dealing with
nested data is the most natural thing in the world in Python. It didn't
take me long to realize how powerful Python was for dealing with complex
data, especially when my only basis for comparision was bash!

This is

.. _easyproc: https://github.com/ninjaaron/easyproc
