import pint

from h5rdmtoolbox import get_ureg


def validate_units(value, handler, info):
    """validate units using pint package"""
    try:
        get_ureg().Unit(value)
    except (pint.UndefinedUnitError, TypeError) as e:
        raise ValueError(f'Units cannot be understood using ureg package: {value}. Original error: {e}')
    return str(value)
