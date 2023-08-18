import pathlib
from typing import Union

from .table import StandardNameTable
from .. import logger
from ..validator import StandardAttributeValidator


def _parse_snt(snt: Union[str, dict, StandardNameTable]) -> StandardNameTable:
    """Returns a StandardNameTable object from a string, dict or StandardNameTable object"""
    if isinstance(snt, StandardNameTable):
        return snt
    if isinstance(snt, dict):
        return StandardNameTable(**snt)
    if isinstance(snt, str):
        # could be web address or local file
        if snt.startswith('https://zenodo.org/record/') or snt.startswith('10.5281/zenodo.'):
            return StandardNameTable.from_zenodo(snt)
        fname = pathlib.Path(snt)
        logger.debug(f'Reading standard name table from file {snt}')
        if fname.exists() and fname.suffix in ('.yaml', '.yml'):
            return StandardNameTable.from_yaml(fname)
        raise FileNotFoundError(f'File {fname} not found or not a yaml file')
    raise TypeError(f'Invalid type for standard_name_table: {type(snt)}')


class StandardNameTableValidator(StandardAttributeValidator):
    """Validates a standard name table"""

    def __call__(self, standard_name_table, *args, **kwargs):
        # return parse_snt(standard_name_table).to_sdict()
        snt = _parse_snt(standard_name_table)
        if 'zenodo_doi' in snt.meta:
            return snt.meta['zenodo_doi']
        return snt.to_sdict()


class StandardNameValidator(StandardAttributeValidator):
    """Validator for attribute standard_name"""

    def __call__(self, standard_name, parent, **kwargs):
        snt = parent.rootparent.attrs.get('standard_name_table', None)

        if snt is None:
            raise KeyError('No standard name table defined for this file!')

        snt = _parse_snt(snt)

        units = parent.attrs.get('units', None)
        if units is None:
            raise KeyError('No units defined for this variable!')

        # check if scale is provided:
        scale = parent.attrs.get('scale', None)
        if scale is not None:
            units = str(scale * units)

        if not snt.check(standard_name, units):
            if not snt.check_name(standard_name):
                raise ValueError(f'Standard name {standard_name} is invalid.')
            expected_units = snt[standard_name].units
            raise ValueError(f'Standard name {standard_name} has incompatible units {units}. '
                             f'Expected units: {expected_units} but got {units}.')
        return standard_name