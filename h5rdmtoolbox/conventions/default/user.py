import re
from typing import Union, List

from . import errors
from ..registration import AbstractUserAttribute

ORCID_PATTERN: str = '^[0-9][0-9][0-9][0-9]-[0-9][0-9][0-9][0-9]-[0-9][0-9][0-9][0-9]-[0-9][0-9][0-9][0-9]$'


def is_invalid_orcid_pattern(orcid_str: str) -> bool:
    """Check if the pattern matches. Returns True if no match."""
    return re.match(ORCID_PATTERN, orcid_str) is None


class User(AbstractUserAttribute):
    """User can be one or multiple persons in charge or related to the
    file, group or dataset"""

    def set(self, orcid: Union[str, List[str]]):
        """Add user
        Parameters
        ----------
        orcid: str or List[str]
            ORCID of one or many responsible persons.

        Raises
        ------
        TypeError
            If input is not a string or a list of strings
        OrcidError
            If a string is not meeting the ORCID pattern of four times four numbers sparated with a dash.
        """
        if not isinstance(orcid, (list, tuple)):
            orcid = [orcid, ]
            for o in orcid:
                if not isinstance(o, str):
                    TypeError(f'Expecting a string or list of strings representing an ORCID but got {type(o)}')
                if is_invalid_orcid_pattern(o):
                    raise errors.OrcidError(f'Not an ORCID ID: {o}')
        if len(orcid) == 1:
            self.attrs.create('user', orcid[0])
        else:
            self.attrs.create('user', orcid)

    @staticmethod
    def parse(value, obj=None):
        return value

    def get(self) -> Union[str, List[str]]:
        """Get user attribute"""
        return self.attrs.get('user', None)

    def delete(self):
        """Get user attribute"""
        self.attrs.__delitem__('user')
