""""

This sub-package provides conventions such as standard_names

The concept of standard_names is adopted from the climate forecast community (see cfconventions.org)
The standrd name definitions (name, description, units) are to be provided in XML files. Two xml files
are provided by this sub-packages (fluid and piv). As the projec is under development, they are generated
in the fluid.py file but in later versions the conventions will only be provided as xml files.
"""

from . import data
from ._logger import logger
from .custom import PIVStandardNameTable, FluidStandardNameTable
from .identifier import StandardizedNameTable, StandardizedNameError, StandardizedName, Empty_Standard_Name_Table
from .layout import H5Layout
from .longname import LongName
from .utils import dict2xml, is_valid_email_address


def set_loglevel(level):
    """setting the log level of the sub-package conventions"""
    if isinstance(level, str):
        logger.setLevel(level.upper())
    else:
        logger.setLevel(level)



datetime_str = '%Y-%m-%dT%H:%M:%SZ%z'
__all__ = ['H5Layout', 'datetime_str', 'set_loglevel',
           'StandardizedNameTable', 'StandardizedNameError', 'StandardizedName',
           'Empty_Standard_Name_Table', 'LongName',
           'FluidStandardNameTable',
           'PIVStandardNameTable',
           'UnitsError']
