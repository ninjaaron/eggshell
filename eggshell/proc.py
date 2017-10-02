import subprocess
import easyproc
from easyproc import run, grab
import io
from collections import abc


class Popen(easyproc.Popen):
    def __init__(self, cmd, *args, **kwargs):
        if isinstance(cmd, abc.Iterable) and not isinstance(cmd, str):
            new_cmd = []
            for i in cmd:
                if isinstance(i, abc.Iterable) and not isinstance(i, str):
                    new_cmd.extend(i)
                else:
                    new_cmd.append(i)
            cmd = new_cmd
        super().__init__(cmd, *args, **kwargs)


class ProcStream(easyproc.ProcStream):
    def __ror__(self, other):
        if isinstance(other, str):
            self.kwargs['input'] = other
        elif isinstance(other, (subprocess.Popen, easyproc.ProcStream)):
            self.kwargs['stdin'] = other.stdout
        elif isinstance(other, io.IOBase):
            self.kwargs['stdin'] = other
        elif isinstance(other, abc.Iterable):
            self.kwargs['input'] = other


class RunProc:
    def __init__(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs

    def __ror__(self, other):
        ProcStream.__ror__(self, other)
        return easyproc.run(*self.args, **self.kwargs)



easyproc.Popen = Popen
easyproc.ProcStream = ProcStream
