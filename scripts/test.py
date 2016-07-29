#!/usr/bin/env eggshell
for i in (ls| m/'py'/i | m/'e'/i):
    i =~ s/'py'/'PY'/ig
    print(i)


open('balls', 'w').write(ls)
