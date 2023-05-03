""""

This sub-package provides conventions such as standard_names

The concept of standard_names is adopted from the climate forecast community (see cfconventions.org)
The standrd name definitions (name, description, units) are to be provided in XML files. Two xml files
are provided by this sub-packages (fluid and piv). As the projec is under development, they are generated
in the fluid.py file but in later versions the conventions will only be provided as xml files.
"""

import forge
import h5py
from typing import Callable, Union

from . import standard_attribute
from . import units, long_name, standard_name, title, comment, references, source, contact
from ._logger import logger
from .standard_attribute import StandardAttribute
from .standard_name import StandardName, StandardNameTable
from .utils import dict2xml, is_valid_email_address
from .._repr import make_italic, make_bold

__all__ = ['units', 'long_name', 'standard_name', 'title', 'comment', 'references', 'source', 'contact.py']


# def list_standard_attributes(obj: Callable = None):
#     """List all registered standard attributes
#
#     Returns
#     -------
#     List[StandardAttribute]
#         List of all registered standard attributes
#     """
#     if None:
#         return standard_attribute.cache.REGISTERED_PROPERTIES
#     return standard_attribute.cache.REGISTERED_PROPERTIES.get(type(obj), {})


def set_loglevel(level):
    """setting the logging level of sub-package wrapper"""
    logger.setLevel(level)
    for handler in logger.handlers:
        handler.setLevel(level)


registered_conventions = {}


class StandardAttributeError(Exception):
    """Exception for standard attribute errors"""
    pass


class Convention:
    """A convention is a set of standard attributes that are used to describe the data in a file."""

    def __init__(self, name):
        self.name = name
        self._properties = {}
        self._methods = {'init_file': {},
                         'create_group': {},
                         'create_dataset': {},
                         'create_string_dataset': {}}

    def __repr__(self):
        header = f'Convention({self.name})'
        out = f'{make_bold(header)}\n'

        header = make_bold('\n> Properties')
        out += f'{header}:'

        if len(self._properties) == 0:
            out += f' ({make_italic("Nothing registered")})'

        for k, v in self._properties.items():
            out += f'\n{k.__name__}:'
            for k2, v2 in v.items():
                out += f'\n    * {k2}: {v2.__name__}'

        header = make_bold('\n> Methods')
        out += f'{header}:'

        for k, v in self._methods.items():
            out += f'\n  {k}:'
            if len(v) == 0:
                out += f' ({make_italic("Nothing registered")})'
            for k2, v2 in v.items():
                if v2['optional']:
                    out += f'\n    * {k2} (opt={v2["default"]})'
                else:
                    out += f'\n    * {k2}'
        out += '\n'
        return out

    #
    # def make_optional(self, method, attr_name, default_value=None):
    #     """Make a standard attribute optional in the signature of a method.
    #
    #     Parameters
    #     ----------
    #     attr_name : str
    #         The name of the standard attribute
    #     """
    #     if method not in self._methods:
    #         raise ValueError(f'Cannot make {attr_name} optional because method {method} is not registered.'
    #                          f'Allowed methods are: {self._methods.keys()}')
    #     if attr_name not in self._methods[method]:
    #         raise ValueError(f'Cannot make {attr_name} optional because it is not registered.')
    #     self._methods[method][attr_name]['optional'] = True
    #     self._methods[method][attr_name]['default'] = default_value
    #
    # def make_required(self, method, attr_name):
    #     """Make a standard attribute required in the signature of a method."""
    #     if method not in self._methods:
    #         raise ValueError(f'Cannot make {attr_name} optional because method {method} is not registered. '
    #                          f'Allowed methods are: {self._methods.keys()}')
    #     if attr_name not in self._methods[method]:
    #         raise ValueError(f'Cannot make {attr_name} required because it is not registered.')
    #     self._methods[method][attr_name]['optional'] = False

    def add(self,
            attr_cls: StandardAttribute,
            target_cls: Callable,
            add_to_method: Union[bool, str] = False,
            position: dict = None,
            optional: bool = False,
            alt: str = None,
            default_value: str = None,
            name: str = None,
            overwrite: bool = False
            ):
        """Add a standard attribute to a class and modify signature of the methods if required.

        Parameters
        ----------
        attr_cls : StandardAttribute
            The standard attribute class to be added
        target_cls : Callable
            The class to which the standard attribute is added
        add_to_method : bool, optional
            If True, the standard attribute is added to the signature the respected method, thus it can be
            passed to the method. Depending on the following parameters, the standard attribute is optional
            or required and has a specific default value.
        position : dict, optional
            The position of the standard attribute in the signature of the method.
            E.g. {'index': 1} or {'position': {'after': 'name'}}
        optional : bool, optional
            If True, the standard attribute is optional in the signature of the method.
        alt : str, optional
            The name of an alternative standard attribute that is used if the standard attribute is not provided.
            If neither the standard attribute nor the alternative attribute is provided, an error is raised.
            Only valid if `optional` is False.
        default_value : str, optional
            The default value of the standard attribute in the signature of the method.
        name : str, optional
            The name of the standard attribute. If None, the name of the class is used.
        overwrite : bool, optional
            If True, the standard attribute is overwritten if it already exists.
        """
        if name is None:
            if hasattr(attr_cls, 'name'):
                name = attr_cls.name
            else:
                name = attr_cls.__name__

        if not hasattr(attr_cls, 'set'):
            raise TypeError(f'Cannot register standard attribute {attr_cls} to {target_cls} because it does not '
                            'have a setter method.')

        if not hasattr(attr_cls, 'get'):
            raise TypeError(f'Cannot register standard attribute {attr_cls} to {target_cls} because it does not '
                            'have a getter method.')

        if StandardAttribute not in attr_cls.__bases__:
            raise TypeError(f'Cannot register standard attribute {attr_cls} to {target_cls} because it is not a '
                            'subclass of `StandardAttribute`.')

        if not isinstance(target_cls, (tuple, list)):
            # make it a list
            target_cls = [target_cls]

        for cls in target_cls:
            # if hasattr(cls, '__get_cls__'):
            #     cls = type(cls())
            # if not issubclass(cls, (h5py.File, h5py.Group, h5py.Dataset)) and not hasattr(cls, '__get_cls__'):
            if not issubclass(cls, (h5py.File, h5py.Group, h5py.Dataset)):
                raise TypeError(f'{cls} is not a valid HDF5 class')

            if cls not in self._properties:
                self._properties[cls] = {}

            if overwrite and name in self._properties[cls]:
                del self._properties[cls][name]

            if name in self._properties[cls] and not overwrite:
                raise AttributeError(
                    f'Cannot register property {name} to {cls} because it has already a property with this name.')
            self._properties[cls][name] = attr_cls
            logger.debug(f'Register special hdf std_attr {name} to {cls}')

            if add_to_method:
                from ..wrapper.core import Dataset, Group, File
                if Dataset in cls.__mro__:
                    if isinstance(add_to_method, str):
                        method = add_to_method
                    else:
                        method = 'create_dataset'
                    if name not in self._methods[method]:
                        self._methods[method][name] = {'cls': cls,
                                                       'optional': optional,
                                                       'default': default_value,
                                                       'position': position,
                                                       'alt': alt}
                    continue
                if File in cls.__mro__:
                    if name not in self._methods['init_file']:
                        self._methods['init_file'][name] = {'cls': cls,
                                                            'optional': optional,
                                                            'default': default_value,
                                                            'position': position,
                                                            'alt': alt}
                    continue
                if Group in cls.__mro__:
                    if name not in self._methods['create_group']:
                        self._methods['create_group'][name] = {'cls': cls,
                                                               'optional': optional,
                                                               'default': default_value,
                                                               'position': position,
                                                               'alt': alt}

    def _add_signature(self):
        for name, values in self._methods['create_string_dataset'].items():
            from ..wrapper.core import Group
            Group.create_string_dataset = forge.insert(forge.arg(f'{name}', default=values['default']),
                                                       **values['position'])(Group.create_string_dataset)
        for name, values in self._methods['create_dataset'].items():
            from ..wrapper.core import Group
            Group.create_dataset = forge.insert(forge.arg(f'{name}', default=values['default']),
                                                **values['position'])(Group.create_dataset)
        for name, values in self._methods['create_group'].items():
            from ..wrapper.core import Group
            Group.create_group = forge.insert(forge.arg(f'{name}', default=values['default']),
                                              **values['position'])(Group.create_group)
        for name, values in self._methods['init_file'].items():
            from ..wrapper.core import File
            File.__init__ = forge.insert(forge.arg(f'{name}', default=values['default']),
                                         **values['position'])(File.__init__)

    def _delete_signature(self):
        for name, values in self._methods['create_string_dataset'].items():
            from ..wrapper.core import Group
            Group.create_string_dataset = forge.delete(f'{name}')(Group.create_string_dataset)
        for name, values in self._methods['create_dataset'].items():
            from ..wrapper.core import Group
            Group.create_dataset = forge.delete(f'{name}')(Group.create_dataset)
        for name, values in self._methods['create_group'].items():
            from ..wrapper.core import Group
            Group.create_group = forge.delete(f'{name}')(Group.create_group)
        for name, values in self._methods['init_file'].items():
            from ..wrapper.core import File
            File.__init__ = forge.delete(f'{name}')(File.__init__)

    def register(self):
        registered_conventions[self.name] = self


def use(convention_name: str) -> None:
    """Use a convention by name"""
    global current_convention
    if convention_name is None:
        convention_name = 'h5py'
    if convention_name not in registered_conventions:
        raise ValueError(f'Convention "{convention_name}" is not registered')
    if current_convention is not None:
        if convention_name == current_convention.name:
            return  # nothing to do
        current_convention._delete_signature()
    current_convention = registered_conventions[convention_name]
    current_convention._add_signature()


current_convention: Union[None, Convention] = None

datetime_str = '%Y-%m-%dT%H:%M:%SZ%z'
__all__ = ['datetime_str', 'set_loglevel',
           'StandardName', 'StandardNameTable', 'StandardAttribute']
