import threading
import multiprocessing
import logging


logger = logging.getLogger(__name__)


class Async(object):
    def __init__(self, target=None, args=None, print_on_error=False, keep=None):
        """
        keep: any object to avoid GC
        """
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
        self.keep = keep

    @classmethod
    def from_asyncs(cls, asyncs, **kwargs):
        def target():
            results = []
            for asy in asyncs:
                results.append(asy.get())
            return results

        return cls(target=target, **kwargs)

    @classmethod
    def from_futures(cls, futures, **kwargs):
        def target():
            results = []
            for future in futures:
                results.append(future.result())
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
        logger.debug("Thread starts: async={} thread={}".format(id(self), threading.current_thread()))
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
        logger.debug("Thread exitting: async={} thread={}".format(id(self), threading.current_thread()))

    def start(self):
        self.run_thread()

    def run_thread(self):
        assert not self.started
        thread = threading.Thread(target=self.run)
        thread.daemon = True

        self.thread = thread
        thread.start()

    def join(self):
        logger.info("Joining: {}".format(self))
        assert self.thread is not None
        self.thread.join()
        logger.info("Join successfull: {}".format(self))

    def get(self):
        self.join()
        return self.result


class BindingAsync(Async):
    def __init__(self, asyncs, **kwargs):
        super(BindingAsync, self).__init__(**kwargs)
        pass
