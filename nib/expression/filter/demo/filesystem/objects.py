import os
import abc

from nib.expression.filter import environment


class Item(object):
    __metaclass__ = abc.ABCMeta

    def __init__(self):
        pass

    def __hash__(self):
        return hash(self.get_path())

    def __eq__(self, other):
        return self.get_path() == other.get_path()

    @abc.abstractmethod
    def recurse_file_items(self):
        pass

    @abc.abstractmethod
    def get_path(self):
        pass


class FileItem(Item):
    def __init__(self, path):
        self._path = path
        assert os.path.isfile(self._path)

    def get_path(self):
        return self._path

    def recurse_file_items(self):
        yield self

    def get_size(self):
        return os.path.getsize(self._path)


class DirItem(Item):
    def __init__(self, path):
        self._path = path

    def get_path(self):
        return self._path

    def list_subitems(self):
        for dirpath, dirnames, filenames in os.walk(self._path):
            for dirname in dirnames:
                dir_path = os.path.join(dirpath, dirname)
                if os.path.isdir(dir_path):
                    yield DirItem(dir_path)
            for filename in filenames:
                file_path = os.path.join(dirpath, filename)
                if os.path.isfile(file_path):
                    yield FileItem(file_path)
            break

    def recurse_file_items(self):
        for dirpath, dirnames, filenames in os.walk(self._path):
            for filename in filenames:
                file_path = os.path.join(dirpath, filename)
                if os.path.isfile(file_path):
                    yield FileItem(file_path)
