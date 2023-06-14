"""package configuration"""
from pint import UnitRegistry
from typing import Dict, Union

ureg = UnitRegistry()


def is_valid_logger_level(level: Union[str, int]):
    if not isinstance(level, (str, int)):
        # raise TypeError(f'Invalid type for the logger: {type(logger_value)}')
        return False
    if isinstance(level, str):
        return level.lower() in ('error', 'debug', 'critical', 'warning', 'info', 'fatal', 'warning', 'warn')
    return level in (0, 10, 20, 30, 40, 50)


CONFIG = dict(return_xarray=True,
              advanced_shape_repr=True,
              natural_naming=True,
              hdf_compression='gzip',
              hdf_compression_opts=5,
              xarray_unit_repr_in_plots='/',
              require_unit=True,  # datasets require units
              ureg_format='C~',
              default_convention='h5py',
              init_logger_level='ERROR',
              dtime_fmt='%Y%m%d%H%M%S%f',
              expose_user_prop_to_attrs=True,
              scale_attribute_name='scale',
              offset_attribute_name='offset')

_VALIDATORS = {
    'return_xarray': lambda x: isinstance(x, bool),
    'advanced_shape_repr': lambda x: isinstance(x, bool),
    'natural_naming': lambda x: isinstance(x, bool),
    'hdf_compression': lambda x: isinstance(x, str),
    'hdf_compression_opts': lambda x: isinstance(x, int),
    'xarray_unit_repr_in_plots': lambda x: x in ('', '/', '(', '['),
    'require_unit': lambda x: isinstance(x, bool),
    'ureg_format': lambda x: isinstance(x, str),
    'default_convention': lambda x: isinstance(x, str) or x is None,  # and in ('h5py', 'h5tbx')
    'init_logger_level': lambda x: x in is_valid_logger_level(x),
    'dtime_fmt': lambda x: isinstance(x, str),
    'expose_user_prop_to_attrs': lambda x: isinstance(x, bool),
    'scale_attribute_name': lambda x: isinstance(x, str),
    'offset_attribute_name': lambda x: isinstance(x, str)
}


class ConfigSetter:
    """Set the configuration parameters."""

    def __enter__(self):
        return

    def __exit__(self, *args, **kwargs):
        self._update(self.old)

    def __init__(self):
        self.old = {}

    def __call__(self, **kwargs):
        self.old = {}
        for k, v in kwargs.items():
            if k in _VALIDATORS and not _VALIDATORS[k](v):
                raise ValueError(f'PIV parameter {k} has invalid value: {v}')
            if k not in CONFIG:
                raise KeyError(f'Not a configuration key: {k}')
            self.old[k] = CONFIG[k]
            if k == 'ureg_format':
                get_ureg().default_format = str(v)
        self._update(kwargs)

    def _update(self, options_dict: Dict):
        CONFIG.update(options_dict)


set_config = ConfigSetter()


def get_config(key=None):
    """Return the configuration parameters."""
    if key is None:
        return CONFIG
    else:
        return CONFIG[key]


def get_ureg() -> UnitRegistry:
    """get unit registry"""
    return ureg


set_config(ureg_format=CONFIG['ureg_format'])