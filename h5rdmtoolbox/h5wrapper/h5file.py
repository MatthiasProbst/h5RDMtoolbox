import datetime
import json
import logging
import os
import shutil
import warnings
from pathlib import Path
from typing import Dict
from typing import List
from typing import Union

import h5py
import numpy as np
import pint
import pint_xarray
import xarray as xr
import yaml
from IPython.display import HTML, display
from h5py import h5i
from h5py._hl.base import phil, with_phil
from h5py._objects import ObjectID
from pint_xarray import unit_registry as ureg
from tqdm import tqdm

from . import config
from ._hdf_constants import H5_DIM_ATTRS
from .html_repr import h5file_html_repr
from .. import conventions
from .. import utils
from .._version import __version__
from ..utils import user_data_dir
from ..x2hdf import xr2hdf

logger = logging.getLogger(__package__)

# the following two lines are needed, otherwise automating formatting of the code will remove pint and xarray2hdf accessors
assert pint_xarray.__version__ >= '0.2.1'
assert xr2hdf.__version__ == '0.1.0'

ureg.default_format = 'C~'

_SNC_LS = {}


def get_rootparent(obj):
    """Returns the root group instance."""

    def get_root(parent):
        global found
        found = parent.parent

        def search(parent):
            global found
            parent = parent.parent
            if parent.name == '/':
                found = parent
            else:
                _ = search(parent)

        search(parent)
        return found

    return get_root(obj.parent)


def pop_hdf_attributes(attrs: Dict) -> dict:
    """removes HDF attributes like NAME, CLASS, ...."""
    return {k: v for k, v in attrs.items() if k not in H5_DIM_ATTRS}


def _is_not_valid_natural_name(instance, name, is_natural_naming_enabled):
    """checks if name is already a function call or a property"""
    if is_natural_naming_enabled:
        if isinstance(name, str):
            return hasattr(instance, name)
        else:
            return hasattr(instance, name.decode("utf-8"))


class WrapperAttributeManager(h5py.AttributeManager):
    """
    Subclass of h5py's Attribute Manager.
    Allows to store dictionaries as json strings and to store a dataset or a group as an
    attribute. The latter uses the name of the object. When __getitem__() is called and
    the name (string) is identified as a dataset or group, then this object is returned.
    """

    def __init__(self, parent, identifier_convention: conventions.StandardizedNameTable):
        """ Private constructor."""
        super().__init__(parent)
        self.identifier_convention = identifier_convention  # standard_name_convention

    @with_phil
    def __getitem__(self, name):
        ret = super(WrapperAttributeManager, self).__getitem__(name)
        if isinstance(ret, str):
            if ret:
                if ret[0] == '{':
                    dictionary = json.loads(ret)
                    for k, v in dictionary.items():
                        if isinstance(v, str):
                            if v[0] == '/':
                                if isinstance(self._id, h5py.h5g.GroupID):
                                    rootgrp = get_rootparent(h5py.Group(self._id))
                                    dictionary[k] = rootgrp.get(v)
                                elif isinstance(self._id, h5py.h5d.DatasetID):
                                    rootgrp = get_rootparent(h5py.Dataset(self._id).parent)
                                    dictionary[k] = rootgrp.get(v)
                    return dictionary
                elif ret[0] == '/':  # it may be group or dataset path
                    if isinstance(self._id, h5py.h5g.GroupID):
                        # call like this, otherwise recursive call!
                        rootgrp = get_rootparent(h5py.Group(self._id))
                        return rootgrp.get(ret)
                    else:
                        rootgrp = get_rootparent(h5py.Dataset(self._id).parent)
                        return rootgrp.get(ret)
                else:
                    return ret
            else:
                return ret
        else:
            return ret

    @with_phil
    def __setitem__(self, name, value):
        """ Set a new attribute, overwriting any existing attribute.

        The type and shape of the attribute are determined from the data.  To
        use a specific type or shape, or to preserve the type of attribute,
        use the methods create() and modify().
        """
        if not isinstance(name, str):
            raise TypeError(f'Attribute name must be a str but got {type(name)}')
        if name == conventions.NAME_IDENTIFIER_ATTR_NAME:
            if h5i.get_type(self._id) in (h5i.GROUP, h5i.FILE):
                raise AttributeError(f'Attribute name {name} is reserverd '
                                     'for dataset only.')
            if h5i.get_type(self._id) == h5i.DATASET:
                # check for standardized data-name identifiers
                self.identifier_convention.check_name(value, strict=conventions.identifier.STRICT)

        if isinstance(value, dict):
            # some value might be changed to a string first, like h5py objects
            for k, v in value.items():
                if isinstance(v, (h5py.Dataset, h5py.Group)):
                    value[k] = v.name
            _value = json.dumps(value)
        elif isinstance(value, Path):
            _value = str(value)
        elif isinstance(value, (h5py.Dataset, h5py.Group)):
            return self.create(name, data=value.name)
        else:
            _value = value
        try:
            self.create(name, data=_value)
        except TypeError:
            try:
                self.create(name, data=str(_value))
            except Exception as e2:
                raise RuntimeError(f'Could not set attribute due to: {e2}')

    def __repr__(self):
        return self.__str__()

    def __str__(self):
        outstr = ''
        adict = dict(self.items())
        key_lens = [len(k) for k in adict.keys()]
        if len(key_lens) == 0:
            return None
        keylen = max([len(k) for k in adict.keys()])
        for k, v in adict.items():
            outstr += f'{k:{keylen}}  {v}\n'
        return outstr[:-1]

    def __getattr__(self, item):
        if config.natural_naming:
            if item in self.__dict__:
                return super().__getattribute__(item)
            if item in self.keys():
                return self[item]
            return super().__getattribute__(item)
        return super().__getattribute__(item)

    def __setattr__(self, key, value):
        if key == 'identifier_convention':
            super().__setattr__(key, value)
            return
        if not isinstance(value, ObjectID):
            self.__setitem__(key, value)
            return
        super().__setattr__(key, value)


class DatasetValues:
    """helper class to work around xarray"""

    def __init__(self, h5dataset):
        self.h5dataset = h5dataset

    def __getitem__(self, args, new_dtype=None):
        return self.h5dataset.__getitem__(args, new_dtype=new_dtype, nparray=True)

    def __setitem__(self, args, val):
        return self.h5dataset.__setitem__(args, val)


class H5Dataset(h5py.Dataset):
    """
    Subclass of h5py.Dataset implementing a model.
    This core version enforces the user to use units and
    long_name or standard_name when creating datasets.
    The property standard_name return a standard name
    model.
    """

    @property
    def attrs(self):
        """Exact copy of parent class:
        Attributes attached to this object """
        with phil:
            return WrapperAttributeManager(self, self.standard_name_table)

    @property
    def rootparent(self):
        """Returns the root group instance."""

        def get_root(parent):
            global found
            found = parent.parent

            def search(parent):
                global found
                parent = parent.parent
                if parent.name == '/':
                    found = parent
                else:
                    _ = search(parent)

            search(parent)
            return found

        return get_root(self.parent)

    @property
    def values(self):
        """avoiding using xarray"""
        return DatasetValues(self)

    @property
    def units(self):
        """Returns the attribute units. Returns None if it does not exist."""
        return self.attrs.get('units')

    @property
    def standard_name_table(self):
        """returns the standard name convention associated with the file instance"""
        return _SNC_LS[self.file.id.id]

    @standard_name_table.setter
    def standard_name_table(self, convention: conventions.StandardizedNameTable):
        """returns the standard name convention associated with the file instance"""
        _SNC_LS[self.id.id] = convention

    @units.setter
    def units(self, units):
        """Sets the attribute units to attribute 'units'
        default unit registry format of pint is used."""
        if units:
            if isinstance(units, str):
                _units = ureg.Unit(units).__format__(ureg.default_format)
            elif isinstance(units, pint.Unit):
                _units = units.__format__(ureg.default_format)
            else:
                raise TypeError(f'Unit must be a string or pint.Unit but not {type(units)}')
        else:
            _units = units
        standard_name = self.attrs.get('standard_name')
        if standard_name:
            self.standard_name_table.check_units(standard_name, _units)

        self.attrs.modify('units', _units)

    @property
    def long_name(self):
        """Returns the attribute long_name. Returns None if it does not exist."""
        return self.attrs.get('long_name')

    @long_name.setter
    def long_name(self, long_name):
        """Writes attribute long_name if passed string is not None"""
        if long_name:
            self.attrs.modify('long_name', long_name)
        else:
            raise TypeError('long_name must not be type None.')

    @property
    def standard_name(self) -> Union[str, None]:
        """Returns the standardized name of the dataset. The attribute name is `standard_name`.
        Returns `None` if it does not exist."""
        attrs_string = self.attrs.get('standard_name')
        if attrs_string is None:
            return None
        return self.standard_name_table[attrs_string]

    @standard_name.setter
    def standard_name(self, new_standard_name):
        """Writes attribute standard_name if passed string is not None.
        The rules for the standard_name is checked before writing to file."""
        if new_standard_name:
            if self.standard_name_table.check_name(new_standard_name):
                self.attrs['standard_name'] = new_standard_name

    def __setitem__(self, key, value):
        if isinstance(value, xr.DataArray):
            self.attrs.update(value.attrs)
            super().__setitem__(key, value.data)
        else:
            super().__setitem__(key, value)

    def __getitem__(self, args, new_dtype=None, nparray=False) -> xr.DataArray:
        """Returns sliced HDF dataset as xr.DataArray.
        By passing nparray=True the return array is forced
        to be of type np.array and the super method of
        __getitem__ is called. Alternatively, call .values[:,...]"""
        args = args if isinstance(args, tuple) else (args,)
        if nparray:
            return super().__getitem__(args, new_dtype=new_dtype)
        if Ellipsis in args:
            warnings.warn(
                'Ellipsis not supported at this stage. returning numpy array')
            return super().__getitem__(args, new_dtype=new_dtype)
        else:
            arr = super().__getitem__(args, new_dtype=new_dtype)
            attrs = pop_hdf_attributes(self.attrs)

            if 'DIMENSION_LIST' in self.attrs:
                # there are coordinates to attach...

                myargs = [slice(None) for _ in range(self.ndim)]
                for ia, a in enumerate(args):
                    myargs[ia] = a

                # remember the first dimension name for all axis:
                dims_names = [Path(d[0].name).stem if len(
                    d) > 0 else 'None' for d in self.dims]

                coords = {}
                used_dims = []
                for dim, dim_name, arg in zip(self.dims, dims_names, myargs):
                    for iax, _ in enumerate(dim):
                        dim_ds = dim[iax]
                        coord_name = Path(dim[iax].name).stem
                        if dim_ds.ndim == 0:
                            if isinstance(arg, int):
                                coords[coord_name] = xr.DataArray(name=coord_name,
                                                                  dims=(
                                                                  ), data=dim_ds[()],
                                                                  attrs=pop_hdf_attributes(dim_ds.attrs))
                            else:
                                coords[coord_name] = xr.DataArray(name=coord_name, dims=coord_name,
                                                                  data=[
                                                                      dim_ds[()], ],
                                                                  attrs=pop_hdf_attributes(dim_ds.attrs))
                        else:
                            used_dims.append(dim_name)
                            _data = dim_ds[arg]
                            if isinstance(_data, np.ndarray):
                                coords[coord_name] = xr.DataArray(name=coord_name, dims=dim_name,
                                                                  data=_data,
                                                                  attrs=pop_hdf_attributes(dim_ds.attrs))
                            else:
                                coords[coord_name] = xr.DataArray(name=coord_name, dims=(),
                                                                  data=_data,
                                                                  attrs=pop_hdf_attributes(dim_ds.attrs))

                used_dims = [dim_name for arg, dim_name in zip(
                    myargs, dims_names) if isinstance(arg, slice)]

                COORDINATES = self.attrs.get('COORDINATES')
                if COORDINATES is not None:
                    if isinstance(COORDINATES, str):
                        COORDINATES = [COORDINATES, ]
                    for c in COORDINATES:
                        if c[0] == '/':
                            _data = self.rootparent[c]
                        else:
                            _data = self.parent[c]
                        _name = Path(c).stem
                        coords.update({_name: xr.DataArray(name=_name, dims=(),
                                                           data=_data,
                                                           attrs=pop_hdf_attributes(self.parent[c].attrs))})

                return xr.DataArray(name=Path(self.name).stem, data=arr, dims=used_dims,
                                    coords=coords, attrs=attrs)
            return xr.DataArray(name=Path(self.name).stem, data=arr, attrs=attrs)

    def __str__(self):
        out = f'{self.__class__.__name__} "{self.name}"'
        out += f'\n{"-" * len(out)}'
        out += f'\n{"shape:":14} {self.shape}'
        out += f'\n{"long_name:":14} {self.long_name}'
        out += f'\n{"standard_name:":14} {self.attrs.get("standard_name")}'
        out += f'\n{"units:":14} {self.units}'

        has_dim = False
        dim_str = f'\n\nDimensions'
        for _id, d in enumerate(self.dims):
            naxis = len(d)
            if naxis > 0:
                has_dim = True
                for iaxis in range(naxis):
                    if naxis > 1:
                        dim_str += f'\n   [{_id}({iaxis})] {utils._make_bold(d[iaxis].name)} {d[iaxis].shape}'
                    else:
                        dim_str += f'\n   [{_id}] {utils._make_bold(d[iaxis].name)} {d[iaxis].shape}'
                    dim_str += f'\n       long_name:     {d[iaxis].attrs.get("long_name")}'
                    dim_str += f'\n       standard_name: {d[iaxis].attrs.get("standard_name")}'
                    dim_str += f'\n       units:         {d[iaxis].attrs.get("units")}'
        if has_dim:
            out += dim_str
        return out

    def __init__(self, _id):
        if isinstance(_id, h5py.Dataset):
            _id = _id.id
        if isinstance(_id, h5py.h5d.DatasetID):
            super().__init__(_id)
        else:
            ValueError('Could not initialize Dataset. A h5py.h5f.FileID object must be passed')

        super().__init__(_id)

    def to_units(self, units):
        """Changes the physical unit of the dataset using pint_xarray.
        Loads to full dataset into RAM!"""
        self[()] = self[()].pint.quantify().pint.to(units).pint.dequantify()

    def rename(self, newname):
        """renames the dataset. Note this may be a process that kills your RAM"""
        # hard copy:
        if 'CLASS' and 'NAME' in self.attrs:
            raise RuntimeError(
                'Cannot rename {self.name} because it is a dimension scale!')

        self.parent[newname] = self
        del self.parent[self.name]

    def set_primary_scale(self, axis, iscale: int):
        """define the axis for which the first scale should be set. iscale is the index
        of the available scales to be set as primary.
        Make sure you have write intent on file"""
        nscales = len(self.dims[axis])
        if iscale >= nscales:
            raise ValueError(
                f'The target scale index "iscale" is out of range [0, {nscales - 1}]')
        backup_scales = self.dims[axis].items()
        for _, ds in backup_scales:
            self.dims[axis].detach_scale(ds)
        ils = [iscale, *[i for i in range(nscales) if i != iscale]]
        for i in ils:
            self.dims[axis].attach_scale(backup_scales[i][1])
        logger.debug(f'new primary scale: {self.dims[axis][0]}')


class H5Group(h5py.Group):
    """
    It enforces the usage of units
    and standard_names for every dataset and informative meta data at
    root level (creation time etc).

     It provides and long_name for every group.
    Furthermore, methods that facilitate the work with HDF files are provided,
    such as
    * create_dataset_from_image
    * create_dataset_from_csv
    * stack()
    * concatenate()
    * ...

    Automatic generation of root attributes:
    (a) creation_time: Date time when file was created. Default format see meta_standard.time.datetime_str
    (b) modification_time: Date time when file was used in mode ('r+' or 'a')
    (c) h5wrapper_version: version of this package

    providing additional features through
    specific properties such as units and long_name or through special or
    adapted methods like create_dataset, create_external_link.
    """

    @property
    def attrs(self):
        """Calls the wrapper attibute manager"""
        with phil:
            return WrapperAttributeManager(self, self.standard_name_table)

    @property
    def rootparent(self):
        """Returns the root group instance."""

        def get_root(parent):
            global found
            found = None

            def search(parent):
                global found
                parent = parent.parent
                if parent.name == '/':
                    found = parent
                else:
                    _ = search(parent)

            search(parent)
            return found

        return get_root(self.parent)

    @property
    def datasets(self) -> List[h5py.Dataset]:
        """returns list of the group's datasets"""
        return [v for k, v in self.items() if isinstance(v, h5py.Dataset)]

    @property
    def groups(self):
        """returns list of the group's groups"""
        return [v for v in self.values() if isinstance(v, h5py.Group)]

    @property
    def long_name(self):
        """Returns the attribute long_name. Returns None if it does not exist."""
        return self.attrs.get('long_name')

    @long_name.setter
    def long_name(self, long_name):
        """Writes attribute long_name if passed string is not None"""
        if long_name:
            self.attrs.modify('long_name', long_name)
        else:
            raise TypeError('long_name must not be type None.')

    @property
    def data_source_type(self) -> conventions.data.DataSourceType:
        """returns data source type as DataSourceType"""
        ds_value = self.attrs.get(conventions.data.DataSourceType.get_attr_name())
        if ds_value is None:
            return conventions.data.DataSourceType.none
        try:
            return conventions.data.DataSourceType[ds_value.lower()]
        except KeyError:
            warnings.warn(f'Data source type is unknown to meta convention: "{ds_value}"')
            return conventions.data.DataSourceType.unknown

    @property
    def standard_name_table(self) -> conventions.StandardizedNameTable:
        """returns the standar name convention associated with the file instance"""
        if self.file.id.id in _SNC_LS:
            return _SNC_LS[self.file.id.id]
        return None

    @standard_name_table.setter
    def standard_name_table(self, convention: conventions.StandardizedNameTable):
        """returns the standard name convention associated with the file instance"""
        _SNC_LS[self.id.id] = convention

    def __init__(self, _id):
        if isinstance(_id, h5py.Group):
            _id = _id.id
        if isinstance(_id, h5py.h5g.GroupID):
            super().__init__(_id)
        else:
            ValueError('Could not initialize Group. A h5py.h5f.FileID object must be passed')

    def __setitem__(self, name, obj):
        if isinstance(obj, xr.DataArray):
            return obj.hdf.to_group(self, name)
        super().__setitem__(name, obj)

    def __getitem__(self, name):
        ret = super().__getitem__(name)
        if isinstance(ret, h5py.Dataset):
            return self._h5ds(ret.id)
        elif isinstance(ret, h5py.Group):
            return self._h5grp(ret.id)
        return ret

    def __getattr__(self, item):
        if config.natural_naming:
            if item in self.__dict__:
                return super().__getattribute__(item)
            try:
                if item in self:
                    if isinstance(self[item], h5py.Group):
                        return self._h5grp(self[item].id)
                    else:
                        return self._h5ds(self[item].id)
                else:
                    # try replacing underscores with spaces:
                    _item = item.replace('_', ' ')
                    if _item in self:
                        if isinstance(self[_item], h5py.Group):
                            return self.__class__(self[_item].id)
                        else:
                            return self._h5ds(self[_item].id)
                    else:
                        return super().__getattribute__(item)
            except AttributeError:
                raise AttributeError(item)
        else:
            return super().__getattribute__(item)

    def __str__(self):
        return self.sdump(ret=True)

    def create_group(self, name, long_name=None, overwrite=None,
                     attrs=None, track_order=None):
        """
        Overwrites parent methods. Additional parameters are "long_name" and "attrs".
        Besides, it does and behaves the same. Differently to dataset creating
        long_name is not mandatory (i.e. will not raise a warning).

        Parameters
        ----------
        name : str
            Name of group
        long_name : str
            The long name of the group. Rules for long_name is checked in method
            check_long_name
        overwrite : bool, optional=None
            If the group does not already exist, the new group is written and this parameter has no effect.
            If the group exists and ...
            ... overwrite is None: h5py behaviour is enabled meaning that if a group exists h5py will raise
            ... overwrite is True: group is deleted and rewritten according to method parameters
            ... overwrite is False: group creation has no effect. Existing group is returned.
        attrs : dict, optional
            Attributes of the group, default is None which is an empty dict
        track_order : bool or None
            Track creation order under this group. Default is None.
        """
        if name in self:
            if overwrite is True:
                del self[name]
            elif overwrite is False:
                return self[name]
            else:
                # let h5py.Group raise the error...
                h5py.Group.create_group(self, name, track_order=track_order)

        if _is_not_valid_natural_name(self, name, config.natural_naming):
            raise ValueError(f'The group name "{name}" is not valid. It is an '
                             f'attribute of the class and cannot be used '
                             f'while natural naming is enabled')

        subgrp = super().create_group(name, track_order=track_order)

        # new_subgroup = h5py.Group.create_group(self, name, track_order=track_order)
        logger.debug(f'Created group "{name}" at "{self.name}"-level.')

        if attrs:
            for k, v in attrs.items():
                subgrp.attrs[k] = v

        if attrs is not None:
            long_name = attrs.pop('long_name', long_name)
        if long_name is not None:
            subgrp.attrs['long_name'] = long_name
        return self._h5grp(subgrp)

    def create_dataset(self, name, shape=None, dtype=None, data=None,
                       units=None, long_name=None,
                       standard_name: Union[str, conventions.StandardizedName] = None,
                       overwrite=None, chunks=True,
                       attrs=None, attach_scales=None, make_scale=False,
                       **kwargs):
        """
        Adapting parent dataset creation:
        Additional parameters are
            - long_name or standard_name (either is required. possible to pass both though)
            - units

        Parameters
        ----------
        name : str
            Name of dataset
        shape : tuple, optional
            Dataset shape. see h5py doc. Default None. Required if data=None.
        dtype : str, optional
            dtype of dataset. see h5py doc. Default is dtype('f')
        data : numpy ndarray, optional=None
            Provide data to initialize the dataset.  If not used,
            provide shape and optionally dtype via kwargs (see more in
            h5py documentation regarding arguments for create_dataset
        long_name : str
            The long name (human readable description of the dataset).
            If None, standard_name must be provided
        standard_name: str or conventions.StandardizedName
            The standard name of the dataset. If None, long_name must be provided
        units : str, optional=None
            Physical units of the data. Can only be None if data is not attached with such attribute,
            e.g. through xarray.
        overwrite : bool, optional=None
            If the dataset does not already exist, the new dataset is written and this parameter has no effect.
            If the dataset exists and ...
            ... overwrite is None: h5py behaviour is enabled meaning that if a dataset exists h5py will raise
            ... overwrite is True: dataset is deleted and rewritten according to method parameters
            ... overwrite is False: dataset creation has no effect. Existing dataset is returned.
        chunks : bool or according to h5py.File.create_dataset documentation
            Needs to be True if later resizing is planned
        attrs : dict, optional
            Allows to set attributes directly after dataset creation. Default is
            None, which is an empty dict
        attach_scales : tuple, optional
            Tuple defining the datasets to attach scales to. Content of tuples are
            internal hdf paths. If an axis should not be attached to any axis leave it
            empty (''). Default is ('',) which attaches no scales
            Note: internal hdf5 path is relative w.r.t. this dataset, so be careful
            where to create the dataset and to which to attach the scales!
            Also note, that if data is a xr.DataArray and attach_scales is not None,
            coordinates of xr.DataArray are ignored and only attach_scales is
            considered.
        make_scale: bool, optional=False
            Makes this dataset scale. The parameter attach_scale must be uses, thus be None.
        **kwargs
            see documentation of h5py.File.create_dataset

        Returns
        -------
        ds : h5py.Dataset
            created dataset
        """
        if attrs is None:
            attrs = {}
        else:
            if isinstance(data, xr.DataArray):
                data.attrs.update(attrs)

        if isinstance(data, xr.DataArray):
            if units is None:  # maybe DataArray has pint accessor
                try:
                    data = data.pint.dequantify()
                except:
                    pass
                if 'units' in data.attrs:
                    data.attrs['units'] = ureg.Unit(data.attrs['units']).__format__(ureg.default_format)
                    units = data.attrs.get('units')

                if units is None:  # xr.DataArray had no units!
                    units = attrs.get('units', None)  # is it in function parameter attrs?
                    if units is None:  # let's check for a typo:
                        units = kwargs.get('unit', None)
                else:  # xr.DataArray had units ...
                    if 'units' in attrs:  # ...but also there is units in attrs!
                        units = attrs.get('units')
                        warnings.warn(
                            '"units" is over-defined. Your data array is associated with the attribute "units" and '
                            'you passed the parameter "units". Will use the units that has been passed via the '
                            f'function call: {units}')
            else:
                data.attrs['units'] = units

            if long_name is not None and 'long_name' in data.attrs:
                warnings.warn(
                    f'"long_name" is over-defined in dataset "{name}". \nYour data array is already associated '
                    f'with the attribute "long_name" and you passed the parameter "long_name".\n'
                    f'The latter will overwrite the data array attribute long_name!'
                )

            if 'standard_name' in data.attrs:
                attrs['standard_name'] = data.attrs['standard_name']
            if 'long_name' in data.attrs:
                attrs['long_name'] = conventions.LongName(data.attrs['long_name'])

        if units is None:
            if attrs:
                units = attrs.get('units', None)
            else:
                units = kwargs.get('unit', None)  # forgive the typo!
        else:
            if 'units' in attrs:
                warnings.warn('"units" is over-defined. Your data array is associated with the attribute "units" and '
                              'you passed the parameter "units". The latter will overwrite the data array units!')
        if units is None:
            if config.require_units:
                raise conventions.UnitsError('Units cannot be None. A dimensionless dataset has units "''"')
            attrs['units'] = ''
        else:
            attrs['units'] = units

        if 'long_name' in attrs and long_name is not None:
            warnings.warn('"long_name" is over-defined.\nYour data array is already associated with the attribute '
                          '"long_name" and you passed the parameter "long_name".\nThe latter will overwrite '
                          'the data array units!')
        if long_name is not None:
            attrs['long_name'] = conventions.LongName(long_name)

        if 'standard_name' in attrs and standard_name is not None:
            warnings.warn(f'"standard_name" is over-defined for dataset "{name}". '
                          f'Your data array is associated with the attribute '
                          '"standard_name" and you passed the parameter "standard_name". The latter will overwrite '
                          'the data array units!')
        if standard_name is not None:
            self.standard_name_table.check_units(standard_name, attrs['units'])
            attrs['standard_name'] = standard_name

        if attrs.get('standard_name') is None and attrs.get('long_name') is None:
            raise RuntimeError('No long_name or standard_name is given. Either must be provided')

        if name:
            if name in self:
                if overwrite is True:
                    del self[name]  # delete existing dataset
                elif overwrite is False:
                    return self[name]  # return existing dataset
                else:
                    # let h5py run into the error...
                    super().create_dataset(name, shape, dtype, data, **kwargs)

        # take compression from kwargs or config:
        compression = kwargs.pop('compression', config.hdf_compression)
        compression_opts = kwargs.pop('compression_opts', config.hdf_compression_opts)
        if shape is not None:
            if len(shape) == 0:
                compression, compression_opts, chunks = None, None, None

        if attrs is None:
            attrs = {}

        if isinstance(data, xr.DataArray):
            attrs.update(data.attrs)

            dset = data.hdf.to_group(self, name=name, overwrite=overwrite,
                                     compression=compression,
                                     compression_opts=compression_opts, attrs=attrs)

            # for k, v in attrs.items():
            #     dset.attrs.modify(k, v)

            return dset

        if attach_scales is None:
            # maybe there's a typo:
            attach_scales = kwargs.pop('attach_scale', None)

        if name:
            if _is_not_valid_natural_name(self, name, config.natural_naming):
                raise ValueError(f'The dataset name "{name}" is not a valid. It is an '
                                 f'attribute of the class and cannot be used '
                                 f'while natural naming is enabled')

        if isinstance(shape, np.ndarray):  # need if no keyword is used
            data = shape
            shape = None

        if data is not None:
            _data = np.asarray(data)
        else:
            _data = data

        _maxshape = kwargs.get('maxshape', shape)

        if attach_scales:
            if not isinstance(attach_scales, (list, tuple)):
                attach_scales = (attach_scales,)
            if any([True for a in attach_scales if a]) and make_scale:
                raise ValueError(
                    'Cannot make scale and attach scale at the same time!')

        logger.debug(
            f'Creating H5DatasetModel "{name}" in "{self.name}" with maxshape {_maxshape} " '
            f'and using compression "{compression}" with opt "{compression_opts}"')

        if _data is not None:
            if _data.ndim == 0:
                _ds = super().create_dataset(name, shape=shape, dtype=dtype, data=_data,
                                             **kwargs)
            else:
                _ds = super().create_dataset(name, shape=shape, dtype=dtype, data=_data,
                                             chunks=chunks,
                                             compression=compression,
                                             compression_opts=compression_opts,
                                             **kwargs)
        else:
            _ds = super().create_dataset(name, shape=shape, dtype=dtype, data=_data,
                                         compression=compression,
                                         compression_opts=compression_opts,
                                         chunks=chunks,
                                         **kwargs)

        ds = self._h5ds(_ds.id)

        if attrs:
            for k, v in attrs.items():
                ds.attrs[k] = v

        # make scale
        if make_scale:
            ds.make_scale()

        # attach scales:
        if attach_scales:
            for i, s in enumerate(attach_scales):
                if s:
                    if not isinstance(s, (tuple, list)):
                        _s = (s,)
                    else:
                        _s = s
                    for ss in _s:
                        if isinstance(ss, h5py.Dataset):
                            ds.dims[i].attach_scale(ss)
                        else:
                            if ss in self:
                                ds.dims[i].attach_scale(self[ss])
                            else:
                                raise ValueError(f'Cannot assign {ss} to {ds.name} because it seems not '
                                                 f'to exist!')

        return self._h5ds(ds.id)

    def get_dataset_by_standard_name(self, standard_name: str, n: int = None) -> h5py.Dataset or None:
        """Returns the dataset with a specific standard_name within the current group.
        Raises error if multiple datasets are found!
        To recursive scan through all datasets, use
        get_by_attribute('standard_name', <your_value>, 'ds').
        Returns None if no matching dataset has been found."""
        candidats = self.get_datasets_by_attribute('standard_name', standard_name, False)
        if n is None:
            if len(candidats) == 0:
                return None
            if len(candidats) > 1:
                raise ValueError(f'Multiple datasets found with standard name "{standard_name}": {candidats}')
            return candidats[0]
        else:
            if len(candidats) == n:
                if len(candidats) == 1:
                    return candidats[0]
                return candidats
            else:
                raise NameError(f'Could not find standard_name "{standard_name}"')

    def create_datasets_from_csv(self, csv_filename, shape=None, overwrite=False,
                                 combine_opt='stack', axis=0, chunks=None, **kwargs):
        """
        Reads data from a csv and adds a dataset according to column names.
        Pandas.read_csv() is used. So all arguments for this function may be passed.

        Parameters
        ----------
        csv_filename : Path or list of Path
            CSV filename or list of filenames.
            If list is passed, structure must be the same for all
        shape : tuple
            Target shape of data. Default is None.
            As data is column data. it can be reshaped to desired shape.
        overwrite : bool
            Whether to overwrite an existing dataset. Default is False.
        combine_opt : str
            Defines the method how to combine data from multiple files.
            Therefore, csv_filename must be a list. Default is stack.
            If set, make sure, axis is set accordingly.
            Other input can be concatenate
        axis : int
            Stacking or concatenating according to combine_opt along
            if multiple csv files are passes
        chunks : tuple
            Chunking option for HDF5 dataset creation. Equal for all
            datasets

        Returns
        -------
        ds : HDF Dataset
            The created dataset

        """
        from pandas import read_csv as pd_read_csv
        if 'names' in kwargs.keys():
            if 'header' not in kwargs.keys():
                raise RuntimeError('if you pass names also pass header=...')

        if isinstance(csv_filename, (list, tuple)):
            # depending on the meaning of multiple csv_filename axis can be 0 (z-plane)
            # or 1 (time-plane)
            axis = kwargs.pop('axis', 0)
            csv_fname = csv_filename[0]
            is_single_file = False
        elif isinstance(csv_filename, (str, Path)):
            is_single_file = True
            csv_fname = csv_filename
        else:
            raise ValueError(
                f'Wrong input for "csv_filename: {type(csv_filename)}')

        df = pd_read_csv(csv_fname, **kwargs)
        # ncols = len(df.columns)

        compression, compression_opts = config.hdf_compression, config.hdf_compression_opts

        if is_single_file:
            for variable_name in df.columns:
                ds_name = utils.remove_special_chars(str(variable_name))
                data = df[str(variable_name)].values.reshape(shape)
                try:
                    self.create_dataset(name=ds_name,
                                        data=data,
                                        overwrite=overwrite, compression=compression,
                                        compression_opts=compression_opts)
                except RuntimeError as e:
                    logger.error(
                        f'Could not read {variable_name} from csv file due to: {e}')
        else:
            _data = df[df.columns[0]].values.reshape(shape)
            nfiles = len(csv_filename)
            for variable_name in df.columns:
                ds_name = utils.remove_special_chars(str(variable_name))
                if combine_opt == 'concatenate':
                    _shape = list(_data.shape)
                    _shape[axis] = nfiles
                    self.create_dataset(name=ds_name, shape=_shape,
                                        compression=compression,
                                        compression_opts=compression_opts,
                                        chunks=chunks)
                elif combine_opt == 'stack':
                    if axis == 0:
                        self.create_dataset(name=ds_name, shape=(nfiles, *_data.shape),
                                            compression=compression,
                                            compression_opts=compression_opts,
                                            chunks=chunks)
                    elif axis == 1:
                        self.create_dataset(name=ds_name, shape=(_data.shape[0], nfiles, *_data.shape[1:]),
                                            compression=compression,
                                            compression_opts=compression_opts,
                                            chunks=chunks)
                    else:
                        raise ValueError('axis must be 0 or -1')

                else:
                    raise ValueError(
                        f'"combine_opt" must be "concatenate" or "stack", not {combine_opt}')

            for i, csv_fname in enumerate(csv_filename):
                df = pd_read_csv(csv_fname, **kwargs)
                for c in df.columns:
                    ds_name = utils.remove_special_chars(str(c))
                    data = df[str(c)].values.reshape(shape)

                    if combine_opt == 'concatenate':
                        if axis == 0:
                            self[ds_name][i, ...] = data[0, ...]
                        elif axis == 1:
                            self[ds_name][:, i, ...] = data[0, ...]
                    elif combine_opt == 'stack':
                        if axis == 0:
                            self[ds_name][i, ...] = data
                        elif axis == 1:
                            self[ds_name][:, i, ...] = data

    def create_dataset_from_image(self, img_filename, name=None,
                                  overwrite=False, dtype=None, ufunc=None,
                                  axis=0, **kwargs):
        """
        Creates a dataset for a single or multiple files. If a list of filenames is passed
        All images are stacked (thus shape of all images must be equal!)

        Parameters
        ----------
        img_filename : {Path, list}
            Image filename or list of image file names. See also axis in case of multiple files
        name : str
            Name of create dataset
        units : string
            Unit of image. Typically, pixels which is also default.
        long_name : str
            long_name of dataset
        overwrite : bool
            Whether to overwrite an existing dataset with this name
        dtype : str
            Data type used for hdf dataset creation
        axis: int, optional
            Axis along which to stack images in case of multiple ones.
            Valid axis values are either 0 or -1.
            Default is 0.

        Returns
        -------
        ds : hdf Dataset
            The created dataset.

        """

        # take compression from kwargs or config:
        _compression, _compression_opts = config.hdf_compression, config.hdf_compression_opts
        compression = kwargs.pop('compression', _compression)
        compression_opts = kwargs.pop('compression_opts', _compression_opts)
        units = kwargs.pop('units', 'px')
        ds = None

        if isinstance(img_filename, (str, Path)):
            if name is None:
                name = utils.remove_special_chars(
                    os.path.basename(img_filename).rsplit('.', 1)[0])
            img = utils.load_img(img_filename)
            if ufunc is not None:
                if isinstance(ufunc, (list, tuple)):
                    _ufunc = ufunc[0]
                    _ufunc_param = ufunc[1:]
                    raise NotImplementedError(
                        'user function with parameter not implemented yet')
                elif hasattr(ufunc, '__call__'):
                    try:
                        img_processed = ufunc(img)
                    except RuntimeError as e:
                        raise logger.error(f'Failed running user function {ufunc} '
                                           f'with this error: {e}')
                    if img_processed is not None:
                        ds = self.create_dataset(name=name, data=img_processed,
                                                 overwrite=overwrite,
                                                 dtype=dtype, compression=compression,
                                                 compression_opts=compression_opts,
                                                 units=units,
                                                 **kwargs)
                        return ds

            else:
                ds = self.create_dataset(name=name, data=img,
                                         overwrite=overwrite, dtype=dtype,
                                         compression=compression, compression_opts=compression_opts)
                return ds
        elif isinstance(img_filename, (list, tuple)):
            if not name:  # take the first image name
                name = os.path.commonprefix(img_filename)
            nimg = len(img_filename)

            if ufunc is not None:  # user function given. final size of dataset unknown
                if isinstance(ufunc, (list, tuple)):
                    _ufunc = ufunc[0]
                    _ufunc_param = ufunc[1:]
                    # raise NotImplementedError('user function with parameter not implemented yet')
                else:
                    _ufunc = ufunc
                    _ufunc_param = list()

                if hasattr(_ufunc, '__call__'):
                    for i, img_fname in tqdm(enumerate(img_filename)):
                        img = utils.load_img(img_fname)
                        img_shape = img.shape
                        try:
                            if hasattr(ufunc, '__call__'):
                                img_processed = _ufunc(img)
                            else:
                                img_processed = _ufunc(img, *_ufunc_param)
                        except RuntimeError as e:
                            raise logger.error(f'Failed running user function {_ufunc} '
                                               f'with this error: {e}')
                        if img_processed is not None:
                            if name in self:  # dataset already exists
                                ds = self[name]
                                ds_shape = list(ds.shape)
                                if axis == 0:
                                    ds_shape[0] += 1
                                else:
                                    ds_shape[-1] += 1
                                ds.resize(tuple(ds_shape))
                                if axis == 0:
                                    ds[-1, ...] = img_processed
                                else:
                                    ds[..., -1] = img_processed
                            else:  # dataset must be created first
                                if axis == 0:
                                    dataset_shape = (1, *img_shape)
                                    _maxshape = (None, *img_shape)
                                    _chunks = (1, *img_shape)
                                elif axis == -1:
                                    dataset_shape = (*img_shape, 1)
                                    _maxshape = (*img_shape, None)
                                    _chunks = (*img_shape, 1)
                                else:
                                    raise ValueError(
                                        f'Other axis than 0 or -1 not accepted!')
                                ds = self.create_dataset(name, shape=dataset_shape, overwrite=overwrite,
                                                         maxshape=_maxshape, dtype=dtype, compression=compression,
                                                         compression_opts=compression_opts, chunks=_chunks)
                                if axis == 0:
                                    ds[0, ...] = img
                                else:
                                    ds[..., 0] = img
                else:
                    raise ValueError(f'Wrong ufunc type: {type(ufunc)}')
                return ds
            else:  # no user function passed. shape of dataset is known and can be pre-allocated
                img = utils.load_img(img_filename[0])
                img_shape = img.shape
                if axis == 0:
                    dataset_shape = (nimg, *img_shape)
                elif axis == -1:
                    dataset_shape = (*img_shape, nimg)
                else:
                    raise ValueError(f'Other axis than 0 or -1 not accepted!')

                # pre-allocate dataset with shape:
                ds = self.create_dataset(name, shape=dataset_shape, overwrite=overwrite,
                                         dtype=dtype, compression=compression, compression_opts=compression_opts)

                # fill dataset with data:
                if ds is not None:
                    if axis == 0:
                        ds[0, ...] = img
                        for i, img_fname in tqdm(enumerate(img_filename[1:]), unit='file', desc='processing images'):
                            img = utils.load_img(img_fname)
                            if img.shape == img_shape:
                                ds[i + 1, ...] = img
                            else:
                                logger.critical(
                                    f'Shape of {img_fname} has wrong shape {img.shape}. Expected shape: {img_shape}'
                                    f' Dataset will be deleted again!')
                                del self[ds.name]
                    elif axis == -1:
                        ds[..., 0] = img
                        for i, img_fname in tqdm(enumerate(img_filename[1:]), unit='file', desc='processing images'):
                            img = utils.load_img(img_filename[0])
                            if img.shape == img_shape:
                                ds[..., i + 1] = img
                            else:
                                logger.critical(
                                    f'Shape if {img_fname} has wrong shape {img.shape}. Expected shape: {img_shape}'
                                    f' Dataset will be deleted again!')
                                del self[ds.name]
                    return ds
                else:
                    logger.critical(
                        'Could not create dataset because it already exists and overwritr=False.')

    def create_dataset_from_xarray_dataset(self, dataset: xr.Dataset) -> None:
        """creates the xr.DataArrays of the passed xr.Dataset, writes all attributes
        and handles the dimension scales."""
        """creates the xr.DataArrays of the passed xr.Dataset, writes all attributes
        and handles the dimension scales."""
        ds_coords = {}
        for coord in dataset.coords.keys():
            ds = self.create_dataset(coord, data=dataset.coords[coord].values,
                                     attrs=dataset.coords[coord].attrs, overwrite=False)
            ds.make_scale()
            ds_coords[coord] = ds
        for data_var in dataset.data_vars.keys():
            ds = self.create_dataset(data_var, data=dataset[data_var].values,
                                     attrs=dataset[data_var].attrs, overwrite=False)
            for idim, dim in enumerate(dataset[data_var].dims):
                ds.dims[idim].attach_scale(ds_coords[dim])

    def create_external_link(self, name, filename, path, overwrite=False,
                             keep_relative=False):
        """
        Creates a group which points to group in another file. See h5py.ExternalLink()
        for more information.

        Parameters
        ----------
        name : str
            Group name that is created in this hdf file
        filename : Path
            File name of remote HDF5 file
        path : Path
            HDF5 internal path to group that should be linked to
        overwrite : bool, optional
            Whether to overwrite an existing dataset. Default is False.
        keep_relative : bool, optional
            If true, path is untouched. If False, it os.path.abspath() is applied.
        """
        logger.debug(f'Trying to create external link group with name "{name}". Source is filename="{filename}" and '
                     f'path="{path}". Overwrite is set to {overwrite} and keep_relative to {keep_relative}')
        if not keep_relative:
            filename = os.path.abspath(filename)
        if name in self:
            if overwrite:
                del self[name]
                self[name] = h5py.ExternalLink(filename, path)
                return self[name]
            else:
                logger.debug(f'External link {name} was not created. A Dataset with this name'
                             f' already exists and overwrite is set to False! '
                             f'You can pass overwrite=True in order to overwrite the '
                             f'existing dataset')
                raise ValueError(f'External link {name} was not created. A Dataset with this name'
                                 f' already exists and overwrite is set to False! '
                                 f'You can pass overwrite=True in order to overwrite the '
                                 f'existing dataset')
        else:
            self[name] = h5py.ExternalLink(filename, path)
            return self[name]

    def from_yaml(self, yamlfile: Path):
        """creates groups, datasets and attributes defined in a yaml file. Creations
        is performed relative to the current group level.

        Note the required yaml file structure, e.g.
        datasets:
          grp/supgrp/y:
            data: 2
            standard_name: y_coordinate
            units: m
            overwrite: True
        groups:
          grp/supgrp:
            attrs:
        attrs:
          grp/supgrp:
            comment: This is a group comment
        """
        with open(yamlfile, 'r') as f:
            data = yaml.safe_load(f)

        if 'groups' in data:
            for grp in data['groups']:
                kwargs = data['groups'][grp]
                logger.debug(
                    f"dumping group defined by yaml file. name: {grp}, kwargs: {kwargs}")
                try:
                    self.create_group(grp, **kwargs)
                except Exception as e:
                    logger.critical(
                        f'Group {grp} from yaml definition not written due to {e}')

        if 'datasets' in data:
            for ds in data['datasets']:
                kwargs = data['datasets'][ds]
                logger.debug(
                    f"dumping dataset defined by yaml file. name: {ds}, kwargs: {kwargs}")
                try:
                    self.create_dataset(ds, **kwargs)
                except Exception as e:
                    logger.critical(
                        f'Dataset {ds} from yaml definition not written due to {e}')

        if 'attrs' in data:
            for objname in data['attrs']:
                kwargs = data['attrs'][objname]
                logger.debug(
                    f"dumping attribute data defined by yaml file for {objname}: {kwargs}")
                for ak, av in data['attrs'][objname].items():
                    try:
                        self[objname].attrs[ak] = av
                    except Exception as e:
                        logger.critical(
                            f'Could not write attribute {ak} to {objname} due to {e}')

    def get_by_attribute(self, attribute_name, attribute_value=None,
                         h5type=None, recursive=True):
        """returns the object(s) (dataset or group) with a certain attribute name
        and if specified a specific value.
        Via h5type it can be filtered for only datasets or groups

        Parameters
        ----------
        attribute_name: str
            Name of the attribute
        attribute_value: any, optional=None
            Value of the attribute. If None, the value is not checked
        h5type: str, optional=None
            If specified, looking only for groups or datasets.
            To look only for groups, pass 'group' or 'grp'.
            To look only for datasets, pass 'dataset' or 'ds'.
            Default is None, which looks in both object types.
        recursive: bool, optional=True
            If True, scans recursively through all groups below current.

        Returns
        ------
        names: List[str]
            List of dataset and/or group names
        """
        names = []

        def _get_grp(name, node):
            if isinstance(node, h5py.Group):
                if attribute_name in node.attrs:
                    if attribute_value is None:
                        names.append(name)
                    else:
                        if node.attrs[attribute_name] == attribute_value:
                            names.append(name)

        def _get_ds(name, node):
            if isinstance(node, h5py.Dataset):
                if attribute_name in node.attrs:
                    if attribute_value is None:
                        names.append(name)
                    else:
                        if node.attrs[attribute_name] == attribute_value:
                            names.append(name)

        def _get_ds_grp(name, node):
            if attribute_name in node.attrs:
                if attribute_value is None:
                    names.append(name)
                else:
                    if node.attrs[attribute_name] == attribute_value:
                        names.append(name)

        if recursive:
            if h5type is None:
                self.visititems(_get_ds_grp)
            elif h5type.lower() in ('dataset', 'ds'):
                self.visititems(_get_ds)
            elif h5type.lower() in ('group', 'grp', 'gr'):
                self.visititems(_get_grp)
        else:
            if h5type is None:
                for ds in self.values():
                    if attribute_name in ds.attrs:
                        if ds.attrs[attribute_name] == attribute_value:
                            names.append(ds)
            elif h5type.lower() in ('dataset', 'ds'):
                for ds in self.values():
                    if isinstance(ds, h5py.Dataset):
                        if attribute_name in ds.attrs:
                            if ds.attrs[attribute_name] == attribute_value:
                                names.append(ds)
            elif h5type.lower() in ('group', 'grp', 'gr'):
                for ds in self.values():
                    if isinstance(ds, h5py.Group):
                        if attribute_name in ds.attrs:
                            if ds.attrs[attribute_name] == attribute_value:
                                names.append(ds)
        return names

    def get_datasets_by_attribute(self, attribute_name, attribute_value=None, recursive=True):
        return self.get_by_attribute(attribute_name, attribute_value, 'dataset', recursive)

    def get_groups_by_attribute(self, attribute_name, attribute_value=None, recursive=True):
        return self.get_by_attribute(attribute_name, attribute_value, 'group', recursive)

    def _get_obj_names(self, obj_type, recursive):
        """returns all names of specified object type
        in this group and if recursive==True also
        all below"""
        _names = []

        def _get_obj_name(name, node):
            if isinstance(node, obj_type):
                _names.append(name)

        if recursive:
            self.visititems(_get_obj_name)
            return _names
        return [g for g in self.keys() if isinstance(self[g], obj_type)]

    def get_group_names(self, recursive=True):
        """returns all group names in this group and if recursive==True also
        all below"""
        return self._get_obj_names(h5py.Group, recursive)

    def get_dataset_names(self, recursive=True):
        """returns all dataset names in this group and if recursive==True also
        all below"""
        return self._get_obj_names(h5py.Dataset, recursive)

    def dump(self, max_attr_length=None, check=True, **kwargs):
        """Outputs xarray-inspired _html representation of the file content if a
        notebook environment is used"""
        if max_attr_length is None:
            max_attr_length = config.html_max_string_length
        if self.name == '/':
            preamble = f'<p>{Path(self.filename).name}</p>\n'
        else:
            preamble = f'<p>Group: {self.name}</p>\n'
        if check:
            preamble += f'<p>Check resuted in {self.check(silent=True)} issues.</p>\n'
        build_debug_html_page = kwargs.pop('build_debug_html_page', False)
        display(HTML(h5file_html_repr(self, max_attr_length, preamble=preamble,
                                      build_debug_html_page=build_debug_html_page)))

    def _repr_html_(self):
        return h5file_html_repr(self, config.html_max_string_length)

    def sdump(self, ret=False, nspaces=0, grp_only=False, hide_attributes=False, color_code_verification=True):
        """
        Generates string representation of the hdf5 file content (name, shape, units, long_name)

        Parameters
        ----------
        ret : bool, optional
            Whether to return the information string or
            print it. Default is False, which prints the string
        nspaces : int, optional
            number of spaces used as indentation. Default is 0
        grp_only : bool, optional=False
            Only gets group information
        hide_attributes : bool, optional=False
            Hides attributes in output string.
        color_code_verification: bool, optional=True

        Returns
        -------
        out : str
            Information string if asked

        Notes
        -----
        Working under notebooks, explore() gives a greater representation, including attributes.
        """

        def apply_color(_str, flag=1):
            if color_code_verification:
                if flag:
                    return utils._oktext(_str)
                else:
                    return utils._failtext(_str)
            else:
                return _str

        sp_name, sp_shape, sp_unit, sp_desc = eval(
            config.info_table_spacing)
        # out = f"Group ({__class__.__name__}): {self.name}\n"
        out = ''
        spaces = ' ' * nspaces

        if self.name == '/':  # only for root
            if isinstance(self, h5py.Group):
                out += f'> {self.__class__.__name__}: Group name: {self.name}.\n'
            else:
                out += f'> {self.__class__.__name__}: {self.filename}.\n'

            # if isinstance(self, h5py.File):
            #     nissues = self.check(silent=True)
            #     if nissues > 0:
            #         out += apply_color(f'> File has {nissues} issues.', 0)
            #     else:
            #         out += apply_color(f'> File has {nissues} issues.', 1)
            #     out += '\n'

        if not hide_attributes:
            # write attributes:
            for ak, av in self.attrs.items():
                if ak not in ('long_name', 'units', 'REFERENCE_LIST', 'NAME', 'CLASS', 'DIMENSION_LIST'):
                    _ak = f'{ak}:'
                    if isinstance(av, (h5py.Dataset, h5py.Group)):
                        _av = av.name
                    else:
                        _av = f'{av}'
                    if len(_av) > sp_desc:
                        _av = f'{_av[0:sp_desc]}...'
                    out += utils._make_italic(f'\n{spaces}a: {_ak:{sp_name}} {_av}')

        grp_keys = [k for k in self.keys() if isinstance(self[k], h5py.Group)]
        if not grp_only:
            dataset_names = [k for k in self.keys(
            ) if isinstance(self[k], h5py.Dataset)]
            for dataset_name in dataset_names:
                varname = utils._make_bold(os.path.basename(
                    self._h5ds(self[dataset_name]).name))
                shape = self[dataset_name].shape
                units = self[dataset_name].units
                if units is None:
                    units = 'NA'
                else:
                    if units == ' ':
                        units = '-'

                out += f'\n{spaces}{varname:{sp_name}} {str(shape):<{sp_shape}}  {units:<{sp_unit}}'

                if not hide_attributes:
                    # write attributes:
                    for ak, av in self[dataset_name].attrs.items():
                        if ak not in ('long_name', 'units', 'REFERENCE_LIST', 'NAME', 'CLASS', 'DIMENSION_LIST'):
                            _ak = f'{ak}:'
                            if isinstance(av, (h5py.Dataset, h5py.Group)):
                                _av = av.name
                            else:
                                _av = f'{av}'
                            if len(_av) > sp_desc:
                                _av = f'{_av[0:sp_desc]}...'
                            out += utils._make_italic(
                                f'\n\t{spaces}a: {_ak:{sp_name}} {_av}')
            out += '\n'
        nspaces += 2
        for k in grp_keys:
            _grp_name = utils._make_italic(utils._make_bold(f'{spaces}/{k}'))
            _grp_long_name = self[k].long_name
            if grp_only:
                if _grp_long_name is None:
                    out += f'\n{_grp_name}'
                else:
                    out += f'\n{_grp_name}  ({self[k].long_name})'
            else:
                if _grp_long_name is None:
                    out += f'{_grp_name}'
                else:
                    out += f'{_grp_name}  ({self[k].long_name})'

            if isinstance(self, h5py.Group):
                out += self[k].sdump(ret=True, nspaces=nspaces, grp_only=grp_only,
                                     color_code_verification=color_code_verification,
                                     hide_attributes=hide_attributes)
            # else:
            #     out += self[k].info(ret=True, nspaces=nspaces, grp_only=grp_only,
            #                         color_code_verification=color_code_verification,
            #                                         hide_attributes=hide_attributes)
        if ret:
            return out
        else:
            print(out)


class H5FileLayout:
    """class defining the static layout of the HDF5 file"""

    def __init__(self, filename: Path):
        self.filename = Path(filename)
        if not self.filename.exists():
            self.write()

    @property
    def File(self):
        """Returns h5py.File"""
        return h5py.File(self.filename, mode='r')

    def _repr_html_(self):
        preamble = f'<p>Layout File "{self.filename.stem}"</p>\n'
        with h5py.File(self.filename, mode='r') as h5:
            return h5file_html_repr(h5, max_attr_length=None, preamble=preamble,
                                    build_debug_html_page=False)

    def sdump(self, ret=False, nspaces=0, grp_only=False, hide_attributes=False, color_code_verification=True):
        sp_name, sp_shape, sp_unit, sp_desc = eval(config.info_table_spacing)

        with h5py.File(self.filename, mode='r') as h5:
            out = f'Layout File "{self.filename.stem}"\n'
            spaces = ' ' * nspaces

            if not hide_attributes:
                # write attributes:
                for ak, av in h5.attrs.items():
                    if ak not in ('long_name', 'units', 'REFERENCE_LIST', 'NAME', 'CLASS', 'DIMENSION_LIST'):
                        _ak = f'{ak}:'
                        if isinstance(av, (h5py.Dataset, h5py.Group)):
                            _av = av.name
                        else:
                            _av = f'{av}'
                        if len(_av) > sp_desc:
                            _av = f'{_av[0:sp_desc]}...'
                        out += utils._make_italic(f'\n{spaces}a: {_ak:{sp_name}} {_av}')

            grp_keys = [k for k in h5.keys() if isinstance(h5[k], h5py.Group)]
            if not grp_only:
                dataset_names = [k for k in h5.keys() if isinstance(h5[k], h5py.Dataset)]
                for dataset_name in dataset_names:
                    varname = utils._make_bold(os.path.basename(
                        h5[dataset_name].name))
                    # shape = h5[dataset_name].shape
                    # units = h5[dataset_name].attrs.get('units')
                    # if units is None:
                    #     units = 'NA'
                    # else:
                    #     if units == ' ':
                    #         units = '-'
                    # out += f'\n{spaces}{varname:{sp_name}} {str(shape):<{sp_shape}}  {units:<{sp_unit}}'
                    out += f'\n{spaces}{varname:{sp_name}} '

                    if not hide_attributes:
                        # write attributes:
                        for ak, av in h5[dataset_name].attrs.items():
                            if ak not in ('long_name', 'units', 'REFERENCE_LIST', 'NAME', 'CLASS', 'DIMENSION_LIST'):
                                _ak = f'{ak}:'
                                if isinstance(av, (h5py.Dataset, h5py.Group)):
                                    _av = av.name
                                else:
                                    _av = f'{av}'
                                if len(_av) > sp_desc:
                                    _av = f'{av[0:sp_desc]}...'
                                out += utils._make_italic(
                                    f'\n\t{spaces}a: {_ak:{sp_name}} {_av}')
                out += '\n'
            nspaces += 2
            for k in grp_keys:
                _grp_name = utils._make_italic(utils._make_bold(f'{spaces}/{k}'))
                _grp_long_name = h5[k].long_name
                if grp_only:
                    if _grp_long_name is None:
                        out += f'\n{_grp_name}'
                    else:
                        out += f'\n{_grp_name}  ({h5[k].long_name})'
                else:
                    if _grp_long_name is None:
                        out += f'{_grp_name}'
                    else:
                        out += f'{_grp_name}  ({h5[k].long_name})'

                out += h5[k].info(ret=True, nspaces=nspaces, grp_only=grp_only,
                                  color_code_verification=color_code_verification,
                                  hide_attributes=hide_attributes)
            if ret:
                return out
            else:
                print(out)

    def dump(self, max_attr_length=None, **kwargs):
        """dumps the layout to the screen (for jupyter notebooks)"""
        build_debug_html_page = kwargs.pop('build_debug_html_page', False)
        preamble = f'<p>Layout File "{self.filename.stem}"</p>\n'
        with h5py.File(self.filename, mode='r') as h5:
            display(HTML(h5file_html_repr(h5, max_attr_length, preamble=preamble,
                                          build_debug_html_page=build_debug_html_page)))

    def write(self):
        """write the static layout file to user data dir"""
        if not self.filename.parent.exists():
            self.filename.parent.mkdir(parents=True)
        logger.debug(
            f'Layout file for class {self.__class__.__name__} is written to {self.filename}')
        with h5py.File(self.filename, mode='w') as h5:
            h5.attrs['__h5rdmtoolbox_version__'] = '__version of this package'
            h5.attrs['creation_time'] = '__time of file creation'
            h5.attrs['modification_time'] = '__time of last file modification'

    def check_dynamic(self, root_grp: h5py.Group, silent: bool = False) -> int:
        return 0

    def check_static(self, root_grp: h5py.Group, silent: bool = False):
        return conventions.layout.layout_inspection(root_grp, self.filename, silent=silent)

    def check(self, root_grp: Path, silent: bool = False) -> int:
        """combined (static+dynamic) check

        Parameters
        ----------
        root_grp: h5py.Group
            HDF5 root group of the file to be inspected
        silent: bool, optional=False
            Control extra string output.

        Returns
        -------
        n_issues: int
            Number of issues
        silent: bool, optional=False
            Controlling verbose output to screen. If True issue information is printed,
            which is especcially helpful.
        """
        if not isinstance(root_grp, h5py.Group):
            raise TypeError(f'Expecting h5py.Group, not type {type(root_grp)}')
        return self.check_static(root_grp, silent) + self.check_dynamic(root_grp, silent)

    def write(self):
        if not self.filename.parent.exists():
            self.filename.parent.mkdir(parents=True)
        logger.debug(
            f'Layout file for class {self.__class__.__name__} is written to {self.filename}')
        with h5py.File(self.filename, mode='w') as h5:
            h5.attrs['__h5rdmtoolbox_version__'] = '__version of this package'
            h5.attrs['creation_time'] = '__time of file creation'
            h5.attrs['modification_time'] = '__time of last file modification'
        with h5py.File(self.filename, mode='r+') as h5:
            h5.attrs['title'] = '__Description of file content'

    @staticmethod
    def __check_group__(group, silent: bool = False) -> int:
        return 0

    @staticmethod
    def __check_dataset__(dataset, silent: bool = False) -> int:
        # check if dataset has units, long_name or standard_name
        nissues = 0
        if 'units' not in dataset.attrs:
            if not silent:
                print(f' [ds] {dataset.name} : attribute "units" missing')
            nissues += 1

        if 'long_name' not in dataset.attrs and 'standard_name' not in dataset.attrs:
            if not silent:
                print(f' [ds] {dataset.name} : attribute "long_name" and "standard_name" missing. Either of it must '
                      f'exist')
            nissues += 1

        return nissues

    def check_dynamic(self, h5root: h5py.Group, silent: bool = False) -> int:
        h5inspect = conventions.layout.H5Inspect(h5root, inspect_group=self.__check_group__,
                                                 inspect_dataset=self.__check_dataset__, silent=silent)
        h5root.visititems(h5inspect)
        return h5inspect.nissues


class H5File(h5py.File, H5Group):
    """H5File requires title as root attribute. It is not enforced but if not set
    an issue be shown due to it.
    """

    Layout: H5FileLayout = H5FileLayout(Path.joinpath(user_data_dir, f'layout/H5File.hdf'))

    @property
    def attrs(self):
        """Exact copy of parent class:
        Attributes attached to this object """
        with phil:
            return WrapperAttributeManager(self, self.standard_name_table)

    @property
    def version(self):
        """returns version stored in file"""
        return self.attrs.get('__h5rdmtoolbox_version__')

    @property
    def creation_time(self) -> datetime.datetime:
        """returns creation time from file"""
        from dateutil import parser
        return parser.parse(self.attrs.get('creation_time'))

    @property
    def filesize(self):
        """
        Returns file size in bytes (or other units if asked)

        Returns
        -------
        _bytes
            file size in byte

        """
        _bytes = os.path.getsize(self.filename)
        return _bytes * ureg.byte

    @property
    def title(self) -> Union[str, None]:
        """Returns the title (stored as HDF5 attribute) of the file. If it does not exist, None is returned"""
        return self.attrs.get('title')

    @title.setter
    def title(self, title):
        """Sets the title of the file"""
        self.attrs.modify('title', title)

    def __init__(self, name: Path = None, mode='r', title=None, standard_name_table=None,
                 driver=None, libver=None, userblock_size=None,
                 swmr=False, rdcc_nslots=None, rdcc_nbytes=None, rdcc_w0=None,
                 track_order=None, fs_strategy=None, fs_persist=False, fs_threshold=1,
                 **kwds):
        _depr_long_name = kwds.pop('long_name', None)
        if _depr_long_name is not None:
            warnings.warn('Using long name when initializing a H5File is deprecated. Use title instead!',
                          DeprecationWarning)
            title = _depr_long_name

        now_time_str = utils.generate_time_str(datetime.datetime.now(), conventions.datetime_str)
        if name is None:
            logger.debug("An empty H5File class is initialized")
            name = utils.touch_tmp_hdf5_file()
            # mode must be at w or r+ because there is no filename yet (temp willl be created)
            mode = 'r+'
        elif isinstance(name, ObjectID):
            pass
        elif not isinstance(name, (str, Path)):
            raise ValueError(
                f'It seems that no proper file name is passed: type of {name} is {type(name)}')
        else:
            if mode == 'r+':
                if not Path(name).exists():
                    # "touch" the file, so it exists
                    with h5py.File(name, mode='w', driver=driver,
                                   libver=libver, userblock_size=userblock_size, swmr=swmr,
                                   rdcc_nslots=rdcc_nslots, rdcc_nbytes=rdcc_nbytes, rdcc_w0=rdcc_w0,
                                   track_order=track_order, fs_strategy=fs_strategy, fs_persist=fs_persist,
                                   fs_threshold=fs_threshold,
                                   **kwds):
                        pass

        if not isinstance(name, ObjectID):
            self.hdf_filename = Path(name)
        super().__init__(name=name, mode=mode, driver=driver,
                         libver=libver, userblock_size=userblock_size, swmr=swmr,
                         rdcc_nslots=rdcc_nslots, rdcc_nbytes=rdcc_nbytes, rdcc_w0=rdcc_w0,
                         track_order=track_order, fs_strategy=fs_strategy, fs_persist=fs_persist,
                         fs_threshold=fs_threshold,
                         **kwds)

        this_class_name = type(self).__name__
        self.layout_file = Path.joinpath(
            user_data_dir, f'{this_class_name}_Layout.hdf')

        # update file creation/modification times and h5wrapper version
        if self.mode != 'r':
            if 'creation_time' not in self.attrs:
                self.attrs['creation_time'] = now_time_str
            self.attrs['modification_time'] = now_time_str
            self.attrs['__h5rdmtoolbox_version__'] = __version__
            self.attrs['__wrcls__'] = self.__class__.__name__

            if title is not None:
                self.attrs['title'] = title

        if isinstance(standard_name_table, str):
            snc = conventions.StandardizedNameTable.from_xml(standard_name_table)
        elif isinstance(standard_name_table, conventions.StandardizedNameTable):
            snc = standard_name_table
        elif standard_name_table is None:
            snc = conventions.empty_standardized_name_table
        else:
            raise TypeError(f'Unexpected type for standard_name_table: {type(standard_name_table)}')
        self.standard_name_table = snc

    def __setitem__(self, name, obj):
        if isinstance(obj, xr.DataArray):
            return obj.hdf.to_group(self, name)
        super().__setitem__(name, obj)

    def check(self, silent: bool = False) -> int:
        """runs a complete check (static+dynamic) and returns number of issues"""
        return self.Layout.check(self['/'], silent)

    def special_inspect(self, silent: bool = False) -> int:
        """Optional special inspection, e.g. conditional checks."""
        return 0

    def moveto(self, filename: Path, overwrite: bool = False) -> Path:
        """
        moves the file to a new location and optionally renames the file if asked.

        Parameters
        ----------
        target_dir : str
            Target directory to which file is moved.
        filename : str, optional=None
            Filename to be used. If None (default) original filename is not
            changed
        overwrite : bool
            Whether to overwrite an existing name at target_dir with name
            filename

        Return
        ------
        new_filepath : str
            Path to new file location
        """
        trg_fname = Path(filename)
        if trg_fname.exists() and not overwrite:
            raise FileExistsError(f'The target file "{trg_fname}" already exists and overwriting is set to False.'
                                  ' Not moving the file!')
        logger.debug(f'Moving file {self.hdf_filename} to {trg_fname}')

        if not trg_fname.parent.exists():
            Path.mkdir(trg_fname.parent, parents=True)
            logger.debug(f'Created directory {trg_fname.parent}')

        mode = self.mode
        self.close()
        shutil.move(self.hdf_filename, trg_fname)
        super().__init__(trg_fname, mode=mode)
        new_filepath = trg_fname.absolute()
        self.hdf_filename = new_filepath
        return new_filepath

    def saveas(self, filename: Path, overwrite: bool = False, keep_old: bool = True):
        """
        This method copies the current file to the new destination. If keep_old is True, the original
        file s kept.
        Closes the current H5Wrapper and returns a new and opened one wih previous file mode

        Parameters
        ----------
        filename: Path
            New filename.
        overwrite: bool, optional=False
            Whether to not to overwrite an existing filename.
        keep_old: bool, optional=True
            Wheher to keep to original file.

        Returns
        -------
        save_path : Path
            new filename

        """
        _filename = Path(filename)
        if _filename.is_file():
            if overwrite:
                os.remove(_filename)
                src = self.filename
                mode = self.mode
                self.close()  # close this instance
                if keep_old:
                    shutil.copy2(src, _filename)
                else:
                    shutil.move(src, _filename)
                self.hdf_filename = _filename
                return super().__init__(_filename, mode=mode)
            else:
                logger.info("Note: File was not moved to new location as a file already exists with this name"
                            " and overwriting was disabled")
                return None
        src = self.filename
        mode = self.mode
        self.close()  # close this instance

        if keep_old:
            shutil.copy2(src, _filename)
        else:
            shutil.move(src, _filename)

        self.hdf_filename = _filename
        super().__init__(_filename, mode=mode)
        save_path = self.hdf_filename.absolute()
        return save_path

    def open(self, mode="r+"):
        """Opens the closed file"""
        super().__init__(self.hdf_filename, mode=mode)


H5Dataset._h5grp = H5Group
H5Dataset._h5ds = H5Dataset

H5Group._h5grp = H5Group
H5Group._h5ds = H5Dataset
