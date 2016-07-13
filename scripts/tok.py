#!/usr/bin/env python3
from tokenize import tokenize, untokenize
import fileinput

stuff = (t for t in tokenize(fileinput.input(mode='rb').readline))
[print((t[0], t[1], t[4])) for t in stuff]
