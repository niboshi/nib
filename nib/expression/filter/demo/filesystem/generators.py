import os
import re

from nib.expression.filter.generator import (Generator, Filter, GeneratorSpec)

from .objects import (FileItem, DirItem)


def get_generator_classes():
    return [
        PathGenerator,
        SizeFilter,
        RegexFilter,
		SymlinkFilter,
		RecurseFilter,
		RealpathFilter,
    ]


@GeneratorSpec('path')
class PathGenerator(Generator, Filter):
    def generate_impl(self, qt, opts, positive):
        if not positive:
            raise RuntimeError("PathGenerator does not support negative generation.")

        path = qt
        yield DirItem(path)

    def filter_impl(self, input, qt, opts, positive):
        path = qt
        for item in input:
            item_path = item.get_path()
            match = (item_path == path or (item_path + '/').startswith(path))
            if positive == match:
                yield item


@GeneratorSpec('size')
class SizeFilter(Filter):
    def filter_impl(self, input, qt, opts, positive):
        size_str = qt
        if '-' not in size_str:
            min_size = max_size = int(size_str)
        else:
            minmax = size_str.split('-')
            if len(minmax) != 2:
                raise RuntimeError("Invalid size specification: " + qt)
            min_size = int(minmax[0]) if len(minmax[0]) > 0 else None
            max_size = int(minmax[1]) if len(minmax[1]) > 0 else None

        for item in input:
            for file_item in item.recurse_file_items():
                size = file_item.get_size()
                match = \
                        (min_size is None or min_size <= size) and \
                        (max_size is None or size <= max_size)

                if positive == match:
                    yield file_item


@GeneratorSpec('regex')
class RegexFilter(Filter):
    def filter_impl(self, input, qt, opts, positive):
        regex = re.compile(qt)

        for item in input:
            for file_item in item.recurse_file_items():
                match = regex.search(file_item.get_path()) is not None
                if positive == match:
                    yield file_item


@GeneratorSpec('symlink')
class SymlinkFilter(Filter):
    def filter_impl(self, input, qt, opts, positive):
        for item in input:
            for file_item in item.recurse_file_items():
                match = os.path.islink(file_item.get_path())
                if positive == match:
                    yield file_item


@GeneratorSpec('recurse')
class RecurseFilter(Filter):
    def filter_impl(self, input, qt, opts, positive):
        if not positive:
            raise RuntimeError("RecurseFilter does not support negative filtering.")
        for item in input:
            for file_item in item.recurse_file_items():
                yield file_item


@GeneratorSpec('realpath')
class RealpathFilter(Filter):
    def filter_impl(self, input, qt, opts, positive):
        if not positive:
            raise RuntimeError("RealpathFilter does not support negative filtering.")
        for item in input:
            realpath = os.path.realpath(item.get_path())
            if os.path.isfile(realpath):
                yield FileItem(realpath)
            else:
                yield DirItem(realpath)
