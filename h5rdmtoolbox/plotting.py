"""plotting module
Matplotlib labels are manipulated to set the units representation correctly. See build_label_unit_str
"""

# xarray does not allow to change the unit representation in axis labels. The following is a workaround:
import matplotlib.projections as proj
import matplotlib.pyplot as plt

from .config import CONFIG as config


def build_label_unit_str(name: str, units: str,
                         units_format: str = config.XARRAY_UNIT_REPR_IN_PLOTS) -> str:
    """generates the label string from a name and a units based on the units format"""
    units = units.replace("**", "^")
    if units_format == 'in':
        return f'{name} in ${units}$'
    if units_format == '/':
        return f'{name} / ${units}$'
    if units_format in ('[', ']', '[]'):
        return f'{name} [${units}$]'
    if units_format in ('(', ')', '()'):
        return f'{name} (${units}$)'


class XarrayLabelManipulation(plt.Axes):
    """Label manipulation axis class"""

    @staticmethod
    def _adjust_units_label(label, units_format=config.XARRAY_UNIT_REPR_IN_PLOTS):
        # other formats: '(', '[', '/', 'in'
        if label:
            if not label[-1] == ']':
                return label
            if units_format == '[':
                return label
            idx0 = label.rfind('[', 1)
            units_string = label[idx0:]
            if units_string[1:-1] in ('', ' ', None):
                _raw_unit = '-'
            else:
                _raw_unit = f"${units_string[1:-1].replace('**', '^')}$"

            if units_format == 'in':
                return label.replace(units_string, f' in {_raw_unit}')
            if units_format == '/':
                return label.replace(units_string, f' / {_raw_unit}')
            if units_format in ('(', ')', '()'):
                return label.replace(units_string, f' ({_raw_unit})')
            return label
        return label

    def set_xlabel(self, xlabel, *args, **kwargs):
        """set the (adjusted) xlabel"""
        super().set_xlabel(self._adjust_units_label(xlabel), *args, **kwargs)

    def set_ylabel(self, ylabel, *args, **kwargs):
        """set the (adjusted) ylabel"""
        super().set_ylabel(self._adjust_units_label(ylabel), *args, **kwargs)


# register the axis class
proj.register_projection(XarrayLabelManipulation)
