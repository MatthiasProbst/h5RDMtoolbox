"""Testing the standard attributes"""
import requests
import unittest
import warnings
from pint.errors import UndefinedUnitError

import h5rdmtoolbox as h5tbx
from h5rdmtoolbox import conventions, tutorial
from h5rdmtoolbox.conventions import tbx
from h5rdmtoolbox.conventions import units
from h5rdmtoolbox.conventions.layout.tbx import IsValidVersionString, IsValidUnit
from h5rdmtoolbox.conventions.layout.tbx import is_valid_unit
from h5rdmtoolbox.conventions.tbx.errors import StandardNameError
from h5rdmtoolbox.conventions.tbx.utils import update_datasets
from h5rdmtoolbox.conventions.utils import check_url


class TestStandardAttributes(unittest.TestCase):

    def setUp(self) -> None:
        h5tbx.use(None)

    def test_registration(self):

        class shortyname(h5tbx.conventions.StandardAttribute):
            """Shorty name attribute"""

            def set(self, value):
                """Only take the first 3 characters"""
                super().set(value[0:3])

            def get(self, src=None, name=None, default=None):
                """Get the short_name and add a '!'"""
                return super().get() + '!'

        class ShortyAttribute(h5tbx.conventions.StandardAttribute):
            """Shorty name attribute"""

            name = 'another_shorty_name'

            def set(self, value):
                """Only take the first 3 characters"""
                super().set(value[0:4])

            def get(self, src=None, name=None, default=None):
                """Get the short_name and add a '!'"""
                return super().get() + '!!'

        cv = conventions.Convention('short_name_convention')
        cv['create_group'].add(shortyname,
                               add_to_method=True,
                               position={'after': 'name'},
                               optional=True)

        # this shall be a required attribute:
        cv['create_group'].add(ShortyAttribute,
                               add_to_method=True,
                               position={'after': 'name'},
                               optional=False)
        cv['create_dataset'].add(ShortyAttribute,
                                 add_to_method=True,
                                 position={'after': 'name'},
                                 optional=False)

        cv.register()
        self.assertIn(cv.name, h5tbx.conventions.registered_conventions)
        h5tbx.use(cv.name)
        self.assertEqual(cv, h5tbx.conventions.current_convention)

        with h5tbx.File() as h5:
            h5.short_name = 'short'
            h5.shortyname = 'not_effect'
            self.assertNotIn('short_name', h5.attrs.keys())
            self.assertNotIn('shortyname', h5.attrs.keys())

            h5['/'].short_name = 'short'
            h5['/'].shortyname = 'shorty'
            h5['/'].another_shorty_name = 'shorty'
            self.assertEqual(h5.attrs['shortyname'], 'sho')
            self.assertEqual(h5['/'].attrs['shortyname'], 'sho!')
            self.assertEqual(h5['/'].attrs['another_shorty_name'], 'shor!!')

            with self.assertRaises(h5tbx.conventions.StandardAttributeError):
                h5.create_dataset('test', data=1)
            h5.create_dataset('test', data=1, another_shorty_name='shorty')
            self.assertEqual(h5['test'].another_shorty_name, 'shor!!')

            self.assertEqual(h5['/'].shortyname, 'sho!')
            self.assertEqual(h5['/'].another_shorty_name, 'shor!!')

            self.assertEqual(h5.shortyname, 'not_effect')
            h5tbx.use(None)
            with self.assertRaises(AttributeError):
                self.assertNotEqual(h5['/'].shortyname, 'sho!')
            self.assertEqual(h5.attrs['shortyname'], 'sho')

    def test_references(self):
        # bibtex dict example taken from https://bibtexparser.readthedocs.io/en/master/tutorial.html#step-2-parse-it
        bibtex_entry = {'journal': 'Nice Journal',
                        'comments': 'A comment',
                        'pages': '12--23',
                        'month': 'jan',
                        'abstract': 'This is an abstract. This line should be long enough to test\nmultilines...',
                        'title': 'An amazing title',
                        'year': '2013',
                        'volume': '12',
                        'ID': 'Cesar2013',
                        'author': 'Jean Cesar',
                        'keyword': 'keyword1, keyword2',
                        'ENTRYTYPE': 'article'}
        url = 'https://h5rdmtoolbox.readthedocs.io/en/latest/'

        cv = conventions.Convention('test_references')
        cv['__init__'].add(attr_cls=conventions.references.ReferencesAttribute,
                           add_to_method=True,
                           position={'before': 'layout'},
                           optional=True)
        cv.register()
        h5tbx.use(cv.name)

        with h5tbx.File() as h5:
            h5.references = bibtex_entry
            self.assertDictEqual(h5.references, bibtex_entry)

            h5.references = url
            self.assertEqual(h5.references, url)

            h5.references = (bibtex_entry, url)
            self.assertTupleEqual(h5.references, (url, bibtex_entry))

            h5.references = (url, bibtex_entry)
            self.assertTupleEqual(h5.references, (url, bibtex_entry))

            h5.references = (url, bibtex_entry, url)
            self.assertTupleEqual(h5.references, (url, url, bibtex_entry))

            h5.references = (bibtex_entry, url, bibtex_entry)
            self.assertTupleEqual(h5.references, (url, bibtex_entry, bibtex_entry))

            h5.references = (url, bibtex_entry, url, url)
            self.assertTupleEqual(h5.references, (url, url, url, bibtex_entry))

            h5.references = (url, url, bibtex_entry, url, url)
            self.assertTupleEqual(h5.references, (url, url, url, url, bibtex_entry))

            h5.references = (url, url, bibtex_entry, bibtex_entry, url, url)
            self.assertTupleEqual(h5.references, (url, url, url, url, bibtex_entry, bibtex_entry))

            h5.references = (url, url, url, url, bibtex_entry, bibtex_entry, bibtex_entry)
            self.assertTupleEqual(h5.references, (url, url, url, url, bibtex_entry, bibtex_entry, bibtex_entry))
        h5tbx.use(None)

    def test_is_valid_unit(self):
        self.assertTrue(is_valid_unit('m/s'))
        self.assertTrue(is_valid_unit('1 m/s'))
        self.assertTrue(is_valid_unit('kg m/s^-1'))
        self.assertFalse(is_valid_unit('kg m/s-1'))
        self.assertFalse(is_valid_unit('kgm/s-1'))
        self.assertTrue(is_valid_unit('pixel'))

    def test_comment(self):
        h5tbx.use('tbx')
        with h5tbx.File() as h5:
            self.assertEqual(h5.comment, None)
            with self.assertRaises(conventions.comment.CommentError):
                h5.comment = ' This is a comment, which starts with a space.'
            with self.assertRaises(conventions.comment.CommentError):
                h5.comment = '9 This is a comment, which starts with a number.'
            with self.assertRaises(conventions.comment.CommentError):
                h5.comment = 'Too short'
            with self.assertRaises(conventions.comment.CommentError):
                h5.comment = 'Too long' * 100

            h5.comment = 'This comment is ok.'
            self.assertEqual(h5.comment, 'This comment is ok.')

    def test_units(self):
        """Test title attribute"""
        h5tbx.use('tbx')
        with h5tbx.File() as h5:
            ds = h5.create_dataset('test', data=[1, 2, 3], units='m', long_name='test')
            with self.assertRaises(UndefinedUnitError):
                ds.units = 'test'
            with self.assertRaises(units.UnitsError):
                ds.units = ('test',)
            self.assertEqual(ds.units, 'm')
            # creat pint unit object:
            ds.units = h5tbx.get_ureg().mm
            self.assertEqual(ds.units, 'mm')
            del ds.units
            self.assertEqual(ds.units, None)

    def test_source(self):
        h5tbx.use('tbx')

        htwr = conventions.source.Hardware(device='PressureSensorX',
                                           manufacturer='PressureCompany',
                                           serial_number='1234567890',
                                           description='Pressure senor for testing',
                                           temperature_range=[0, 50],
                                           temperature_range_unit=['C', 'C'])
        self.assertEqual(htwr.device, 'PressureSensorX')
        self.assertEqual(htwr.manufacturer, 'PressureCompany')
        self.assertEqual(htwr.serial_number, '1234567890')
        self.assertEqual(htwr.description, 'Pressure senor for testing')
        self.assertEqual(htwr.temperature_range, [0, 50])
        self.assertEqual(htwr.temperature_range_unit, ['C', 'C'])
        self.assertEqual(sorted(htwr.required_items()),
                         sorted([('device', 'PressureSensorX'),
                                 ('manufacturer', 'PressureCompany'),
                                 ('serial_number', '1234567890')]))
        self.assertEqual(htwr._pattern, '^[0-9].*')
        self.assertEqual(sorted(htwr.optional_items()),
                         sorted([('description', 'Pressure senor for testing'),
                                 ('temperature_range', [0, 50]),
                                 ('temperature_range_unit', ['C', 'C'])]))

        with h5tbx.File() as h5:
            h5.create_dataset('test', data=[1, 2, 3],
                              source=htwr, units='m', long_name='test')
            self.assertIsInstance(h5['test'].source, conventions.source.Hardware)

        with self.assertRaises(ValueError):
            conventions.source.Hardware(device='1PressureSensorX',
                                        manufacturer='PressureCompany',
                                        serial_number='1234567890',
                                        description='Pressure senor for testing',
                                        temperature_range=[0, 50],
                                        temperature_range_unit=['C', 'C'])

        with self.assertRaises(ValueError):
            conventions.source.Hardware(device=None,
                                        manufacturer='PressureCompany',
                                        serial_number='1234567890',
                                        description='Pressure senor for testing',
                                        temperature_range=[0, 50],
                                        temperature_range_unit=['C', 'C'])

        sftw = conventions.source.Software(name='h5rdmtoolbox',
                                           version='1.0',
                                           url='https://h5rdmtoolbox.readthedocs.io/en/latest/',
                                           description='This is my software')
        self.assertEqual(sftw.name, 'h5rdmtoolbox')
        self.assertEqual(sftw.version, '1.0')
        self.assertEqual(sftw.url, 'https://h5rdmtoolbox.readthedocs.io/en/latest/')
        self.assertEqual(sftw.description, 'This is my software')
        self.assertEqual(sorted(sftw.required_items()),
                         sorted([('name', 'h5rdmtoolbox'),
                                 ('version', '1.0'),
                                 ('url', 'https://h5rdmtoolbox.readthedocs.io/en/latest/')]))
        self.assertEqual(sorted(sftw.optional_items()),
                         sorted([('author', None),
                                 ('description', 'This is my software'),
                                 ('lic', None),
                                 ('language', None),
                                 ('platform', None)]))
        self.assertEqual(sftw._pattern, '^[0-9].*')

        with self.assertRaises(ValueError):
            conventions.source.Software(name='1h5rdmtoolbox',
                                        version='1.0',
                                        url='https://h5rdmtoolbox.readthedocs.io/en/latest/',
                                        description='This is my software')

        with self.assertRaises(ValueError):
            conventions.source.Software(name='1h5rdmtoolbox',
                                        version='1.0',
                                        url='ww.h5rmtoolbox.de',
                                        description='This is my software')

        with h5tbx.File() as h5:
            ds1 = h5.create_dataset('test1', data=[1, 2, 3], units='m', long_name='test')
            ds2 = h5.create_dataset('test2', data=[1, 2, 3], units='m', long_name='test',
                                    source=sftw)
            self.assertEqual(ds1.source, None)
            self.assertEqual(ds2.source, sftw)

            h5tbx.use(None)
            h5.create_dataset('test3', data=[1, 2, 3], attrs={'source': None})
            h5.create_dataset('test4', data=[1, 2, 3], attrs={'source': {'name': 'h5rdmtoolbox'}})
            h5.create_dataset('test5', data=[1, 2, 3], attrs={'source': 1.5})
            h5tbx.use('tbx')
            with self.assertRaises(RuntimeError):
                print(h5.test3.source)
            with self.assertRaises(ValueError):
                print(h5.test4.source)
            with self.assertRaises(RuntimeError):
                print(h5.test5.source)
            h5.test5.source = sftw
            self.assertIsInstance(h5.test5.source, conventions.source.Software)

    def test_standard_name(self):
        with self.assertRaises(tbx.errors.StandardNameError):
            sn_fail = tbx.StandardName(name='', units='m')

        with self.assertRaises(StandardNameError):
            tbx.StandardName(name=' x', units='m', description='a description')

        with self.assertRaises(StandardNameError):
            sn_fail = tbx.StandardName(name='x ', units='m', description='a description')

        sn1 = tbx.StandardName(name='acc',
                               description='a description',
                               units='m**2/s')
        self.assertEqual(sn1.units, h5tbx.get_ureg().Unit('m**2/s'))

        with self.assertRaises(StandardNameError):
            tutorial.get_standard_name_table()['z_coord']

    def test_validversion(self):
        self.assertTrue(IsValidVersionString()('v0.1.0'))
        self.assertFalse(IsValidVersionString()('a.b.c'))

    def test_validunit(self):
        self.assertTrue(IsValidUnit()('m/s'))
        self.assertTrue(IsValidUnit()('1 m/s'))
        self.assertFalse(IsValidUnit()('hello/world'))

    def test_responsible_person(self):
        orcid = '0000-0001-8729-0482'
        self.assertTrue(conventions.contact.is_valid_orcid_pattern(orcid))
        self.assertFalse(conventions.contact.is_valid_orcid_pattern('123-123-123-123'))
        self.assertFalse(conventions.contact.is_valid_orcid_pattern(orcid[0:-1]))
        self.assertTrue(conventions.contact.exist(orcid))
        not_existing_orcid = '0000-0001-5747-0739'
        self.assertFalse(conventions.contact.exist(not_existing_orcid))

    def test_standard_name_assignment(self):
        translation_dict = {'u': 'x_velocity'}

        with h5tbx.File() as h5:
            h5.create_dataset('u', data=[1, 2, 3])
            h5.create_dataset('grp/u', data=[1, 2, 3])
            update_datasets(h5, translation_dict, rec=False)
            self.assertEqual(h5['u'].attrs['standard_name'], 'x_velocity')
            self.assertFalse('standard_name' in h5['grp/u'].attrs)
            update_datasets(h5, translation_dict, rec=True)
            self.assertTrue('standard_name' in h5['grp/u'].attrs)
            self.assertEqual(h5['grp/u'].attrs['standard_name'], 'x_velocity')

    try:
        import pooch
        run_tests = True
    except ImportError:
        run_tests = False
        warnings.warn(f'Cannot test certain things about standard name table because "pooch" is not installed.')

    if run_tests:
        def test_StandardNameTableFromYaml(self):
            table = tbx.StandardNameTable.from_yaml(tutorial.testdir / 'sntable.yml')
            self.assertEqual(table.name, 'test')
            self.assertEqual(table.version_number, 1)
            self.assertEqual(table.institution, 'ITS')
            self.assertEqual(table.contact, 'https://orcid.org/0000-0001-8729-0482')
            self.assertEqual(table.valid_characters, '')
            self.assertEqual(table.pattern, '')
            # table.rename('mean_particle_diameter', 'mean_particle_diameter2')
            # self.assertFalse('mean_particle_diameter' in table)
            # self.assertTrue('mean_particle_diameter2' in table)

            # self.assertListEqual(table.names, ['synthetic_particle_image', 'mean_particle_diameter2'])

            table.table = {'synthetic_particle_image': {
                'units': 'pixel',
            },
                'mean_particle_diameter2': {
                    'description': 'The mean particle diameter of an image particle. The diameter is defined as the 2 sigma with of the gaussian intensity profile of the particle image.',
                    'units': 'pixel'}
            }
            # with self.assertRaises(tbx.DescriptionMissing):
            #     table.check_table()

            table.table = {
                'synthetic_particle_image': {
                    'units': 'pixel',
                    'description': 'Synthetic particle image velocimetry image containing image particles of a single '
                                   'synthetic recording.'},
                'mean_particle_diameter2': {
                    'description': 'The mean particle diameter of an image particle. The diameter is defined as the 2 '
                                   'sigma with of the gaussian intensity profile of the particle image.',
                    'units': 'pixel'}
            }

            table.update(a_velocity={
                'description': 'velocity in a direction',
                'units': 'm/s'
            })
            self.assertEqual(table['a_velocity'].description, 'velocity in a direction')
            from h5rdmtoolbox import get_ureg
            self.assertEqual(table['a_velocity'].units, get_ureg()('m/s'))

        def test_StandardNameTableVersion(self):
            versions = [
                ("v79", True),
                ("v1.2", True),
                ("v2.3a", True),
                ("v3.0dev", True),
                ("v3.0.1dev", False),
                ("v4.5rc", True),
                ("v4.5.6rc", False),
                ("v7.8b", True),
                ("v10", True),
                ("invalid_version", False),
            ]
            for version, valid in versions:
                if valid:
                    self.assertEqual(tbx.StandardNameTable.validate_version(version), version)
                else:
                    with self.assertRaises(ValueError):
                        tbx.StandardNameTable.validate_version(version)

        def test_StandardNameTableFromWeb(self):
            cf = tbx.StandardNameTable.from_web(
                url='https://cfconventions.org/Data/cf-standard-names/79/src/cf-standard-name-table.xml',
                name='standard_name_table')
            self.assertEqual(cf.name, 'standard_name_table')
            self.assertEqual(cf.versionname, 'standard_name_table-v79')
            self.assertTrue(check_url(cf.url))
            self.assertFalse(check_url(cf.url + '123'))

            try:
                requests.get('https://git.scc.kit.edu', timeout=5)
                connected = True
            except (requests.ConnectionError,
                    requests.Timeout) as e:
                connected = False
                warnings.warn('Cannot check Standard name table from '
                              f'gitlab: {e}')
            if connected:
                opencefa = tbx.StandardNameTable.from_gitlab(url='https://git.scc.kit.edu',
                                                             file_path='open_centrifugal_fan_database-v1.yaml',
                                                             project_id='35443',
                                                             ref_name='main')
                self.assertEqual(opencefa.name, 'open_centrifugal_fan_database')
                self.assertEqual(opencefa.versionname, 'open_centrifugal_fan_database-v1')

    def test_StandardNameTableFromYaml_special(self):
        table = tbx.StandardNameTable.from_yaml(tutorial.testdir / 'sntable_with_split.yml')
        self.assertEqual(table.name, 'test')
        self.assertEqual(table.version_number, 1)
        self.assertEqual(table.institution, 'ITS')
        self.assertEqual(table.contact, 'https://orcid.org/0000-0001-8729-0482')
        self.assertEqual(table.valid_characters, '')
        self.assertEqual(table.pattern, '')
        self.assertDictEqual(
            table.table,
            {
                'synthetic_particle_image': {
                    'units': 'counts',
                    'description':
                        'Synthetic particle image velocimetry image containing image particles '
                        'of a single synthetic recording.'
                },
                'mean_particle_diameter': {
                    'units': 'pixel',
                    'description':
                        'The mean particle diameter of an image particle. The diameter is defined '
                        'as the 2 sigma with of the gaussian intensity profile of the particle image.'
                }
            })
        self.assertDictEqual(table.alias, {'particle_image': 'synthetic_particle_image'}
                             )
        self.assertTrue(table.check_name('synthetic_particle_image'))
        self.assertFalse(table.check_name('particle_image'))
        self.assertIsInstance(table['synthetic_particle_image'], tbx.StandardName)

    # def test_merge(self):
    #     registered_snts = tbx.StandardNameTable.get_registered()
    #     new_snt = tbx.merge(registered_snts, name='newtable', institution=None,
    #                         version_number=1, contact='https://orcid.org/0000-0001-8729-0482')
    #     self.assertTrue(new_snt.name, 'newtable')

    def test_empty_SNT(self):
        snt = tbx.StandardNameTable('test_snt',
                                    table={},
                                    version_number=1,
                                    institution='my_institution',
                                    contact='https://orcid.org/0000-0001-8729-0482')
        # self.assertIsInstance(snt.table, dict)
        # self.assertEqual(snt.filename, None)
