import abc
import collections


class EvaluationEnvironment(object):
    __metaclass__ = abc.ABCMeta

    def __init__(self):
        self.generators = dict((gen.__class__.key, gen) for gen in self.get_generators())

    def get_set_ops(self):
        return SetOperations()

    @abc.abstractmethod
    def get_generators(self):
        pass

    def get_generator(self, key):
        if key in self.generators:
            return self.generators[key]
        else:
            raise RuntimeError("Invalid generator: {}".format(key))

    def union(self, source, o1, o2, positive1, positive2):
        gen1 = o1.eval(self, source, positive1)
        gen2 = o2.eval(self, source, positive2)
        return self.get_set_ops().union(gen1, gen2)

    def intersection(self, source, o1, o2, positive1, positive2):
        gen1 = o1.eval(self, source, positive1)
        gen2 = o2.eval(self, gen1, positive2)
        return gen2


class SetOperations(object):
    def union(self, gen1, gen2):
        ret = self.union_impl(gen1, gen2)
        assert isinstance(ret, collections.Iterable)
        return ret

    def union_impl(self, gen1, gen2):
        set1 = set()
        for item1 in gen1:
            yield item1
            set1.add(item1)

        for item2 in gen2:
            if item2 not in set1:
                yield item2
