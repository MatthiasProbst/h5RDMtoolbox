import re

from ..accessory import register_special_property
from ..h5file import H5File


class TitleError(ValueError):
    """An error associated with the title property"""


@register_special_property(H5File)
class title:

    def set(self, value):
        if value[0] == ' ':
            raise TitleError('Title must not start with a space')
        if value[-1] == ' ':
            raise TitleError('Title must not end with a space')
        if value[-1] == ' ':
            raise TitleError('Title must not end with a space')
        if re.match('^[0-9 ].*', value):
            raise ValueError('Title must not start with a number')
        self.attrs.create('title', value)

    def get(self):
        return self.attrs.get('title', None)

    def delete(self):
        self.attrs.__delitem__('title')