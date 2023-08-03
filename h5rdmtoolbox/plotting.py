"""plotting module
Matplotlib labels are manipulated to set the units representation correctly. See build_label_unit_str
"""
import matplotlib.projections as proj
import matplotlib.pyplot as plt
import re
import warnings
import xarray as xr
from typing import Union

from . import get_config

# xarray does not allow to change the unit representation in axis labels. The following is a workaround:

__XARRAY_UNITS_PATTERN__ = r"(.*?)\[([^\[\]]*?)\]$"
__AV_UNIT_FORMATS__ = ('/', '()', '(', '[]', '[', '//', 'in')


def decode_label(label: str) -> (str, str):
    """Decodes the label into a name and a unit string. For this,
    the last occurrence of [<unit>] is searched. No opening or
    closing square brackets are allowed in the label.

    ..note: This function assumes that the units are written as [<unit>] at
        the end of the label. If this is not the case, the function will fail
        or return wrong results.

    Parameters
    ----------
    label: str
        label to be decoded, e.g. velocity [m/s]

    Returns
    -------
    name: str
        name of the label, e.g. velocity
    unit_string: str
        unit string, e.g. m/s
    """
    try:
        match = re.search(__XARRAY_UNITS_PATTERN__, label)
        return match.group(1), match.group(2)
    except RuntimeError as e:
        raise RuntimeError(
            f'Could not parse label {label} with pattern {__XARRAY_UNITS_PATTERN__}. Orig. err: {e}'
        ) from e


def build_label_unit_str(name: str, units: str,
                         units_format: str = None) -> str:
    """generates the label string from a name and a units based on the units format.
    
    Parameters
    ----------
    name: str
      Variable name
    units: Union[str, None]
      Variable unit. None takes the default from the configuration ("xarray_unit_repr_in_plots")
    units_format: str, None
      "in", "/", "[", "("

    Returns
    -------
    str
        Processed label string, e.g. "<name> in <units>"
    """
    if units_format is None:
        units_format = get_config('xarray_unit_repr_in_plots')
    units = units.replace("**", "^")
    if units_format == 'in':
        return f'{name} in ${units}$'
    if units_format == '/':
        return f'{name} / ${units}$'
    if units_format in ('[', ']', '[]'):
        return f'{name} [${units}$]'
    if units_format in ('(', ')', '()'):
        return f'{name} (${units}$)'
    raise ValueError(f'Unexpected value for "units_format": {units_format}. Must be one of the following: '
                     f'"in", "/", "[", "("')


class XarrayLabelManipulation(plt.Axes):
    """Label manipulation axis class"""

    @staticmethod
    def _adjust_units_label(label, units_format=None):
        if units_format is None:
            units_format = get_config('xarray_unit_repr_in_plots')

        if units_format not in __AV_UNIT_FORMATS__:
            raise ValueError(f'Unknown units format {units_format}.')

        if label:
            if not label[-1] == ']':
                return label.replace('**', '^')

            try:
                name, units_string = decode_label(label)
            except RuntimeError as e:
                warnings.warn(f'Could not change label due to {e}. Please open an issue for this and tell '
                              'the developers about it.', UserWarning)
                return label

            if units_format == '[':
                if units_string in ('', ' ', None, 'dimensionless'):
                    _raw_unit = '-'
                else:
                    _raw_unit = f"{units_string.replace('**', '^')}"

                return f"{name}[{_raw_unit.replace('**', '^')}]"

            if units_string in ('[]', '[ ]', '[dimensionless]', None):
                return build_label_unit_str(name.strip(), '-', units_format)

            return build_label_unit_str(name.strip(), units_string, units_format)
        return label

    def set_xylabel(self, xlabel, ylabel):
        """set the xlabel and ylabel"""
        self.set_xlabel(xlabel)
        self.set_ylabel(ylabel)

    def set_xlabel(self, xlabel: Union[str, xr.DataArray], *args, **kwargs):
        """set the (adjusted) xlabel"""
        if isinstance(xlabel, xr.DataArray):
            for plotting_name in get_config('plotting_name_order'):
                name = xlabel.attrs.get(plotting_name)
                if name:
                    xlabel = f'{name} [{xlabel.attrs.get("units", "")}]'
                    break
        super().set_xlabel(self._adjust_units_label(xlabel), *args, **kwargs)

    def set_ylabel(self, ylabel: Union[str, xr.DataArray], *args, **kwargs):
        """set the (adjusted) ylabel"""
        if isinstance(ylabel, xr.DataArray):
            for plotting_name in get_config('plotting_name_order'):
                name = ylabel.attrs.get(plotting_name)
                if name:
                    ylabel = f'{name} [{ylabel.attrs.get("units", "")}]'
                    break
        super().set_ylabel(self._adjust_units_label(ylabel), *args, **kwargs)


# register the axis class
proj.register_projection(XarrayLabelManipulation)

# altnative: inherit plot accessor:
# inherit plot accessor:

# with warnings.catch_warnings():
#     warnings.simplefilter("ignore")
#
#
#     @xr.register_dataarray_accessor("plot")
#     class PlotWrapper(xr.DataArray.plot):
#
#         def _wrap_xlabel(self):
#             # xlabel is a bit difficult because we don't know which dimension/coordinate was used.
#             # get the xlabel first:
#             xlabel
#             for label_name in get_config('plotting_name_order'):
#                 plotting_name = self._da.attrs.get(label_name)
#                 if plotting_name:
#                     plt.gca().set_xlabel(build_label_unit_str(plotting_name, self._da.attrs.get('units', '')))
#                     return
#             if self._da.name:
#                 plt.gca().set_xlabel(build_label_unit_str(self._da.name, self._da.attrs.get('units', '')))
#
#         def _wrap_ylabel(self):
#             for label_name in get_config('plotting_name_order'):
#                 plotting_name = self._da.attrs.get(label_name)
#                 if plotting_name:
#                     plt.gca().set_ylabel(build_label_unit_str(plotting_name, self._da.attrs.get('units', '')))
#                     return
#             if self._da.name:
#                 plt.gca().set_ylabel(build_label_unit_str(self._da.name, self._da.attrs.get('units', '')))
#
#         def __call__(self, *args, **kwargs):
#             ret = super().__call__(*args, **kwargs)
#
#
#             return ret
