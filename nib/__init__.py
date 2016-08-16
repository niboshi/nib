import os
import sys
import tempfile
import hashlib
import errno
import subprocess
import shutil
import logging
import datetime


if sys.version < '3':
    def u(s):
        return s.decode('utf-8')
else:
    def u(s):
        return s

def encodePath(path):
    if isinstance(path, str):
        path = path.encode('utf-8')
    return path

def makeRelativePath(targetPath, sourcePath):
    #print(targetPath, sourcePath)
    if targetPath == sourcePath:
        return ''
    isabs1 = os.path.isabs(targetPath)
    isabs2 = os.path.isabs(sourcePath)
    assert isabs1 == isabs2

    if isabs1:
        drv1, targetPath = os.path.splitdrive(targetPath)
        drv2, sourcePath = os.path.splitdrive(sourcePath)
        assert drv1 == drv2

    sep = os.sep
    if isinstance(targetPath, bytes):
        sep = sep.encode('utf-8')

    parts1 = targetPath.split(sep)
    parts2 = sourcePath.split(sep)
    while len(parts1) > 0 and len(parts2) > 0 and parts1[0] == parts2[0]:
        parts1.pop(0)
        parts2.pop(0)

    if parts2 == ['']:
        parts2 = []
    parts1 = ['..'] * len(parts2) + parts1
    return os.path.join(*parts1)

def md5(path, file=True):
    m = hashlib.md5()

    if file:
        f = open(encodePath(path), 'rb')
        while True:
            data = f.read(8192)
            if not data: break
            m.update(data)
        f.close()
    else:
        m.update(path)

    return m.hexdigest()

def mkdir(path):
    if len(path) == 0:
        return path
    try:
        os.makedirs(encodePath(path))
    except OSError as e:
        if e.errno != errno.EEXIST:
            raise

    return path

def mkparent(path):
    dirpath = os.path.dirname(os.path.realpath(path))
    if not os.path.exists(dirpath):
        mkdir(dirpath)
    return path

def execute(cmd, **kwargs):
    proc = subprocess.Popen(cmd, **kwargs)
    stdoutdata,stderrdata = proc.communicate()
    if proc.returncode != 0:
        raise RuntimeError("External program '%s' exited with: %d" % (cmd[0], proc.returncode))
    return stdoutdata,stderrdata

def progress(prev, current, max, str='|----+----|----+----|----+----|----+----|----+----|', out=sys.stdout):
    l = len(str)
    i0 = prev    * l / max
    i1 = current * l / max
    out.write(str[i0:i1])
    if i0 < i1:
        out.flush()

class TempDir(object):
    def __init__(self, keep=False, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs.copy()
        self.keep = keep
        self.path = None

        if 'prefix' in self.kwargs:
            prefix = self.kwargs['prefix']
            if prefix is None:
                del self.kwargs['prefix']

        self.path = tempfile.mkdtemp(*self.args, **self.kwargs)

    def __del__(self):
        self.close()

    def __enter__(self):
        return self

    def __exit__(self, type, value, traceback):
        self.close()

    def close(self):
        if self.path is not None and not self.keep:
            shutil.rmtree(self.path, True)
            self.path = None

class ExtraLogFilter(logging.Filter):
    def filter(self, record):
        if hasattr(record, 'info'):
            obj = record.info
            if isinstance(obj, list):
                for i in obj:
                    record.msg += "\n\t{}".format(i)
            elif isinstance(obj, dict):
                for k,v in obj.items():
                    record.msg += "\n\t{}: {}".format(k, v)
            else:
                record.msg += str(obj)

        return super().filter(record)

from .async import (Async, BindingAsync)

class ColorFormatter(logging.Formatter):
    RESET = "\033[0m"
    LRED   = "\033[1;31m"
    RED    = "\033[0;31m"
    YELLOW = "\033[1;33m"
    GRAY   = "\033[1;30m"

    def format(self, record):
        s = super().format(record)
        level = record.levelno
        if level >= logging.ERROR:
            s = self.LRED + s + self.RESET
        elif level >= logging.WARNING:
            s = self.YELLOW + s + self.RESET
        elif level >= logging.INFO:
            pass
        else:
            s = self.GRAY + s + self.RESET
        return s

class utc(datetime.tzinfo):
    ZERO = datetime.timedelta(0)

    def utcoffset(self, dt):
        return self.ZERO

    def dst(self, dt):
        return self.ZERO

    def tzname(self, dt):
        return 'UTC'
