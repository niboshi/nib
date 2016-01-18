import os
import sys
import tempfile
import hashlib
import errno
import subprocess
import shutil
import threading
import logging
import multiprocessing

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


class Async(object):
    def __init__(self, target=None, args=None, print_on_error=False):
        self.target = target
        self.args = args
        self.started = False
        self.finished = False
        self.error = False
        self.result = None
        self.print_on_error = print_on_error
        self.handlers_on_success = []
        self.handlers_on_error = []
        self.handlers_on_done = []
        self.thread = None
        self.process_name = "<unknown>"

    @classmethod
    def from_asyncs(cls, asyncs, **kwargs):
        def target():
            results = []
            for async in asyncs:
                results.append(async.get())
            return results

        return cls(target=target, **kwargs)

    def __repr__(self):
        return "Async(process=\"{}\" id={} started={} finished={} error={})".format(self.process_name, id(self), self.started, self.finished, self.error)

    def on_error(self, handler):
        self.handlers_on_error.append(handler)

    def on_success(self, handler):
        self.handlers_on_success.append(handler)

    def on_done(self, handler):
        self.handlers_on_done.append(handler)

    def call_handlers(self, handlers, args=()):
        for handler in handlers:
            handler(self, *args)

    def run(self):
        assert not self.started
        args = self.args
        self.process_name = multiprocessing.current_process().name
        if args is None:
            args = ()
        self.started = True
        try:
            res = self.target(*args)
        except Exception as e:
            self.error = True
            res = None
            self.call_handlers(self.handlers_on_error, (e,))

            if self.print_on_error:
                import traceback
                traceback.print_exc()

        self.result = res
        self.finished = True

        if not self.error:
            self.call_handlers(self.handlers_on_success)

        self.call_handlers(self.handlers_on_done)

    def start(self):
        self.run_thread()

    def run_thread(self):
        assert not self.started
        thread = threading.Thread(target=self.run)
        thread.daemon = True

        self.thread = thread
        thread.start()

    def join(self):
        assert self.thread is not None
        self.thread.join()

    def get(self):
        self.join()
        return self.result


class BindingAsync(Async):
    def __init__(self, asyncs, **kwargs):
        super(BindingAsync, self).__init__(**kwargs)
        pass
