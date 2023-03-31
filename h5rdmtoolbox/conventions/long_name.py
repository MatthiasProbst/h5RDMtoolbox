import re
from typing import Union

from .standard_attribute import StandardAttribute


class LongNameError(ValueError):
    """An error associated with the long_name property"""


class LongName(str):
    """Long Name class. Implements convention (rules) for usage"""
    MIN_LENGTH = 1
    PATTERN = '^[0-9 ].*'

    name = 'long_name'

    def __new__(cls, value):
        # 1. Must be longer than MIN_LENGTH
        if len(value) < cls.MIN_LENGTH:
            raise LongNameError(f'Name is too short. Must at least have {cls.MIN_LENGTH} character')
        if re.match(cls.PATTERN, value):
            raise LongNameError(f'Name must not start with a number or a space: "{value}"')
        return str.__new__(cls, value)


class LongNameAttribute(StandardAttribute):
    """Long name attribute"""

    name = 'long_name'

    def set(self, long_name: str) -> None:
        """Set the long_name"""
        ln = LongName(long_name)  # runs check automatically during initialization
        super().set(value=ln.__str__())

    def get(self) -> Union[str, None]:
        """Get the long_name"""
        long_name = super().get()
        if long_name:
            return LongName(long_name)
        return None
