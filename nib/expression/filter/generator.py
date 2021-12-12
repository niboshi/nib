import abc
import collections


def GeneratorSpec(key, **kwargs):
    def f(cls):
        cls.key    = key
        return cls
    return f


class AbstractGenerator(object):
    __metaclass__ = abc.ABCMeta
    require_env = False

    def eval(self, env, input, qt, opts, positive):
        assert isinstance(opts, dict), type(opts)
        assert isinstance(positive, bool), type(positive)
        if input is not None:
            assert isinstance(input, collections.Iterable)

        ret = self._eval(env, input, qt, opts, positive)

        assert ret is None or isinstance(ret, collections.Iterable)
        return ret

    def _eval(self, env, input, qt, opts, positive):
        if input is None:
            if not isinstance(self, Generator):
                raise RuntimeError("This generator ({}) does not support object generation.".format(self.__class__.__name__))
            if self.require_env:
                return self.generate_impl(qt, opts, positive, env=env)
            return self.generate_impl(qt, opts, positive)
        else:
            if not isinstance(self, Filter):
                raise RuntimeError("This generator ({}) does not support object filtering.".format(self.__class__.__name__))
            if self.require_env:
                return self.filter_impl(input, qt, opts, positive, env=env)
            return self.filter_impl(input, qt, opts, positive)


class Generator(AbstractGenerator):
    @abc.abstractmethod
    def generate_impl(self, qt, opts, positive):
        pass


class Filter(AbstractGenerator):
    @abc.abstractmethod
    def filter_impl(self, input, qt, opts, positive):
        pass
