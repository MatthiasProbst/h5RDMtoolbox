import pathlib
from typing import Union, Dict

from h5rdmtoolbox.utils import create_tbx_logger
from . import lazy
from .file import File
from .files import Files

logger = create_tbx_logger('wrapper')


class Folder:
    """Folder with HDF5 files as a database

    Parameters
    ----------
    folder : pathlib.Path
        folder with HDF5 files
    pattern : str, optional
        pattern to search for, by default '*.hdf'
    rec : bool, optional
        search recursively for hdf files within the given folder, by default True
    """

    def __init__(self, folder: pathlib.Path, pattern='*.hdf', rec: bool = True):
        folder = pathlib.Path(folder)
        if not folder.is_dir():
            raise ValueError(f'{folder} is not a directory')
        self.folder = folder
        if rec:
            self.filenames = list(self.folder.rglob(pattern))
        else:
            self.filenames = list(self.folder.glob(pattern))

    def find(self,
             flt: Union[Dict, str],
             objfilter=None, rec: bool = True,
             ignore_attribute_error: bool = False):
        """Find"""
        with Files(self.filenames, file_instance=File) as h5:
            return h5.find(flt, objfilter, rec, ignore_attribute_error)

    def find_one(self,
                 flt: Union[Dict, str],
                 objfilter=None,
                 rec: bool = True,
                 ignore_attribute_error: bool = False):
        """Find one occurrence"""
        with Files(self.filenames, file_instance=File) as h5:
            return h5.find_one(flt, objfilter, rec, ignore_attribute_error)


__all__ = ['logger', 'Files']
