import inspect
import requests
import unittest
import warnings

import h5rdmtoolbox as h5tbx
from h5rdmtoolbox import tutorial
from h5rdmtoolbox.conventions.standard_attributes import StandardNameTable, StandardName
from h5rdmtoolbox.conventions.standard_attributes.errors import StandardNameError
from h5rdmtoolbox.conventions.standard_attributes.utils import check_url

try:
    import pooch

    pooch_is_available = True
except ImportError:
    pooch_is_available = False
    warnings.warn(f'Cannot test certain things about standard name table because "pooch" is not installed.')


class TestStandardAttributes(unittest.TestCase):

    def setUp(self) -> None:
        try:
            requests.get('https://git.scc.kit.edu', timeout=5)
            self.connected = True
        except (requests.ConnectionError,
                requests.Timeout) as e:
            self.connected = False
            warnings.warn('No internet connection', UserWarning)

    def test_standard_name(self):
        with self.assertRaises(StandardNameError):
            sn_fail = StandardName(name='', units='m')

        with self.assertRaises(StandardNameError):
            StandardName(name=' x', units='m', description='a description')

        with self.assertRaises(StandardNameError):
            sn_fail = StandardName(name='x ', units='m', description='a description')

        sn1 = StandardName(name='acc',
                           description='a description',
                           units='m**2/s')
        self.assertEqual(sn1.units, h5tbx.get_ureg().Unit('m**2/s'))

        with self.assertRaises(StandardNameError):
            tutorial.get_standard_name_table()['z_coord']

    # if pooch_is_available:
    def test_StandardNameTableFromYaml(self):
        table = StandardNameTable.from_yaml(tutorial.get_standard_name_table_yaml_file())
        self.assertEqual(table.name, 'Test')
        self.assertEqual(table.version, 'v1.0')
        self.assertEqual(table.institution, 'my_institution')
        self.assertEqual(table.contact, 'https://orcid.org/0000-0001-8729-0482')
        self.assertEqual(table.valid_characters, '[^a-zA-Z0-9_]')
        self.assertEqual(table.pattern, '^[0-9 ].*')
        self.assertEqual(table.devices, ['fan', 'orifice'])
        self.assertEqual(table.locations, ['fan_inlet', 'fan_outlet'])
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
                self.assertEqual(StandardNameTable.validate_version(version), version)
            else:
                with self.assertRaises(ValueError):
                    StandardNameTable.validate_version(version)

    def test_StandardNameTableFromWeb(self):
        cf = StandardNameTable.from_web(
            url='https://cfconventions.org/Data/cf-standard-names/79/src/cf-standard-name-table.xml',
            name='standard_name_table')
        self.assertEqual(cf.name, 'standard_name_table')
        self.assertEqual(cf.versionname, 'standard_name_table-v79')
        if self.connected:
            self.assertTrue(check_url(cf.url))
            self.assertFalse(check_url(cf.url + '123'))

        if self.connected:
            opencefa = StandardNameTable.from_gitlab(url='https://git.scc.kit.edu',
                                                     file_path='open_centrifugal_fan_database-v1.yaml',
                                                     project_id='35443',
                                                     ref_name='main')
            self.assertEqual(opencefa.name, 'open_centrifugal_fan_database')
            self.assertEqual(opencefa.versionname, 'open_centrifugal_fan_database-v1')

    def test_StandardNameTableFromYaml_special(self):
        table = StandardNameTable.from_yaml(tutorial.testdir / 'sntable_with_split.yml')
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
        self.assertIsInstance(table['synthetic_particle_image'], StandardName)

    def test_empty_SNT(self):
        snt = StandardNameTable(name='test_snt',
                                table={},
                                version='v1.0dev',
                                institution='my_institution',
                                contact='https://orcid.org/0000-0001-8729-0482')
        self.assertIsInstance(snt.table, dict)

    def test_standard_name_convention(self):
        h5tbx.use(None)
        units_attr = h5tbx.conventions.StandardAttribute('units',
                                                         validator='$pintunit',
                                                         method={'create_dataset': {'optional': False}},
                                                         description='A unit of a dataset',
                                                         )
        standard_name = h5tbx.conventions.StandardAttribute('standard_name',
                                                            validator='$standard_name',
                                                            method={'create_dataset': {'optional': False}},
                                                            description='A standard name of a dataset',
                                                            )
        snt_yaml_filename = h5tbx.tutorial.get_standard_attribute_yaml_filename()
        snt = h5tbx.conventions.StandardAttribute('standard_name_table',
                                                  validator='$standard_name_table',
                                                  method={'__init__': {'optional': True, }},
                                                  # default_value='https://zenodo.org/record/8158764',
                                                  default_value=snt_yaml_filename,
                                                  description='A standard name table',
                                                  requirements=['standard_name', 'units'],
                                                  return_type='standard_name_table'
                                                  )

        cv = h5tbx.conventions.Convention('test_standard_name')
        cv.add(units_attr)
        cv.add(standard_name)
        cv.add(snt)
        cv.register()
        h5tbx.use(cv.name)

        self.assertIn('standard_name', inspect.signature(h5tbx.Group.create_dataset).parameters.keys())
        self.assertIn('units', inspect.signature(h5tbx.Group.create_dataset).parameters.keys())
        self.assertIn('standard_name_table', inspect.signature(h5tbx.File.__init__).parameters.keys())

        if self.connected:
            with h5tbx.File(standard_name_table='https://zenodo.org/record/8158764') as h5:
                print(h5.standard_name_table)

                h5.create_dataset('test', data=1, standard_name='x_velocity', units='m/s')
                print(h5['test'])

                snt = h5.standard_name_table
                snt.devices = ['fan', 'orifice']

                h5.standard_name_table = snt

                # check transformations:
                h5.create_dataset('test2', data=1,
                                  standard_name='difference_of_x_velocity_across_fan',
                                  units='m/s')
