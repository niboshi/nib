import os
import sys
import tempfile
import hashlib
import errno
import subprocess
import shutil

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
    if len(path) == 0: return
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
        raise Exception("External program '%s' exited with: %d" % (cmd[0], proc.returncode))
    return stdoutdata,stderrdata

def progress(prev, current, max, str='|----+----|----+----|----+----|----+----|----+----|', out=sys.stdout):
    l = len(str)
    i0 = prev    * l / max
    i1 = current * l / max
    out.write(str[i0:i1])
    if i0 < i1:
        out.flush()

class TempDir(object):
    def __init__(self, keep=False, *args):
        self.args = args
        self.keep = keep
        self.path = None

    def __del__(self):
        self._close()

    def __enter__(self):
        self.path = tempfile.mkdtemp(*args)
        return self

    def __exit__(self, type, value, traceback):
        self._close()

    def _close(self):
        if self.path is not None and not self.keep:
            shutil.rmtree(self.path, True)
            self.path = None
