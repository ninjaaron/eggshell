#!/usr/bin/env eggshell
shimport ls, grep

reg = '\x1b[0;3%dm'
bold = '\x1b[1;3%dm'


def nested_commands_and_pipes():
    for i, path in enumerate(ls (ls | grep i)):
        color = i % 6 + 1
        if i % 12 < 6:
            echo --end='\t' f'{reg%color}{path}'
        else:
            echo f'{bold%color}{path}', end='\t'
    echo


def python_interpolation():
    cd ~
    ls --color='auto' (d for d in ('src', 'doc', 'dls'))


def environment_variables():
    echo env.HOME/src


def redirection():
    ls, stdout='foo.txt'

def globbing():
    echo (range(9))(range(5))
    echo env.HOME/('%0.2d' % i for i in range(1, 11))
    echo "/etc/"*
    echo
    echo env.HOME/*
    echo
    cd ~
    echo src/*

nested_commands_and_pipes()
python_interpolation()
environment_variables()
redirection()
globbing()
