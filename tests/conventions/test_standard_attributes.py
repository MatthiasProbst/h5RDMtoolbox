"""Testing common funcitonality across all wrapper classs"""

import json
import unittest
from importlib.metadata import metadata
from typing import Union, Dict

from h5rdmtoolbox import use
from h5rdmtoolbox.conventions.cflike import software
from h5rdmtoolbox.conventions.cflike.errors import LongNameError
from h5rdmtoolbox.conventions.default.errors import OrcidError
from h5rdmtoolbox.conventions.registration import register_hdf_attr, UserAttr
from h5rdmtoolbox.wrapper.cflike import File, Group
from h5rdmtoolbox.wrapper.core import File as CoreFile


class TestOptAccessors(unittest.TestCase):

    def setUp(self) -> None:
        """setup"""

        @register_hdf_attr(Group, name='software', overwrite=True)
        class SoftwareAttribute(UserAttr):
            """property attach to a Group"""

            def set(self, sftw: Union[software.Software, Dict]):
                """Get `software` as group attribute"""
                if isinstance(sftw, (tuple, list)):
                    raise TypeError('Software information must be provided as dictionary '
                                    f'or object of class Software, not {type(sftw)}')
                if isinstance(sftw, dict):
                    # init the Software to check for errors
                    self.attrs.create('software', json.dumps(software.Software(**sftw).to_dict()))
                else:
                    self.attrs.create('software', json.dumps(sftw.to_dict()))

            @staticmethod
            def parse(raw, obj=None):
                if raw is None:
                    return software.Software(None, None, None, None)
                if isinstance(raw, dict):
                    return software.Software(**raw)
                try:
                    datadict = json.loads(raw)
                except json.JSONDecodeError:
                    # try figuring out from a string. assuming order and sep=','
                    keys = ('name', 'version', 'url', 'description')
                    datadict = {}
                    raw_split = raw.split(',')
                    n_split = len(raw_split)
                    for i in range(4):
                        if i >= n_split:
                            datadict[keys[i]] = None
                        else:
                            datadict[keys[i]] = raw_split[i].strip()

                return software.Software.from_dict(datadict)

            def get(self) -> software.Software:
                """Get `software` from group attribute. The value is expected
                to be a dictionary-string that can be decoded by json.
                However, if it is a real string it is expected that it contains
                name, version url and description separated by a comma.
                """
                return SoftwareAttribute.parse(self.attrs.get('software', None))

            def delete(self):
                """Delete attribute"""
                self.attrs.__delitem__('standard_name')

    def test_software(self):
        meta = metadata('numpy')

        s = software.Software(meta['Name'], version=meta['Version'], url=meta['Home-page'],
                              description=meta['Summary'])

        with File() as h5:
            h5.software = s

    def test_long_name(self):
        # is available per default
        with File() as h5:
            with self.assertRaises(LongNameError):
                h5.attrs['long_name'] = ' 1234'
            with self.assertRaises(LongNameError):
                h5.attrs['long_name'] = '1234'
            h5.attrs['long_name'] = 'a1234'
            with self.assertRaises(LongNameError):
                h5.create_dataset('ds1', shape=(2,), long_name=' a long name', units='m**2')
            with self.assertRaises(LongNameError):
                h5.create_dataset('ds3', shape=(2,), long_name='123a long name ', units='m**2')

    def test_units(self):
        # is available per default
        import pint
        with File() as h5:
            h5.attrs['units'] = ' '
            h5.attrs['units'] = 'hallo'

            h5.create_dataset('ds1', shape=(2,), long_name='a long name', units='m**2')

            with self.assertRaises(pint.errors.UndefinedUnitError):
                h5['ds1'].units = 'no unit'

            with self.assertRaises(pint.errors.UndefinedUnitError):
                h5.create_dataset('ds2', shape=(2,), long_name='a long name', units='nounit')

    def test_user(self):
        use('default')
        with CoreFile() as h5:
            self.assertEqual(h5.user, None)
            h5.attrs['user'] = '1123-0814-1234-2343'
            self.assertEqual(h5.user, '1123-0814-1234-2343')

        with CoreFile() as h5:
            with self.assertRaises(OrcidError):
                h5.user = '11308429'
            with self.assertRaises(OrcidError):
                h5.attrs['user'] = '11308429'
            with self.assertRaises(OrcidError):
                h5.user = '123-132-123-123'
            with self.assertRaises(OrcidError):
                h5.user = '1234-1324-1234-1234s'
            h5.user = '1234-1324-1234-1234'
            self.assertTrue(h5.user, '1234-1324-1234-1234')
            h5.user = ['1234-1324-1234-1234', ]
            self.assertTrue(h5.user, ['1234-1324-1234-1234', ])

            g = h5.create_group('g1')
            from h5rdmtoolbox import config
            config.natural_naming = False
            with self.assertRaises(RuntimeError):
                g.attrs.user = '123'
            config.natural_naming = True
        use('cflike')

    def test_set_attribute_to_higher_class(self):
        @register_hdf_attr(CoreFile, name=None, overwrite=True)
        class shortyname2(UserAttr):
            """Shorty name attribute"""
            pass

        with CoreFile() as h5:
            # shortyname2 only available for classes inherited from File
            h5.shortyname2 = 'my short name2'
            self.assertIn('shortyname2', h5.attrs.keys())
        with File() as h5:
            h5.shortyname2 = 'my short name2'
            self.assertNotIn('shortyname', h5.attrs.keys())
