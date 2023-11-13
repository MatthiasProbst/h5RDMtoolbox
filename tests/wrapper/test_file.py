import h5py
import numpy as np
import pathlib
import pint
import time
import unittest
import uuid
import yaml
from datetime import datetime
from pathlib import Path

import h5rdmtoolbox as h5tbx
from h5rdmtoolbox import tutorial
from h5rdmtoolbox import use
from h5rdmtoolbox.utils import generate_temporary_filename
from h5rdmtoolbox.wrapper.core import File


class TestFile(unittest.TestCase):

    def setUp(self) -> None:
        """setup"""
        use(None)
        with File(mode='w') as h5:
            h5.attrs['one'] = 1
            g = h5.create_group('grp_1')
            g.attrs['one'] = 1
            h5.attrs['two'] = 2
            h5.attrs['three'] = 3
            h5.create_dataset('ds', shape=(4,), attrs=dict(one=1))
            h5.create_group('grp_2')
            h5.create_group('grp_3')
            h5.create_group('grp_X')
            h5.create_dataset('ds1', shape=(3,))
            h5.create_dataset('ds2', shape=(3,))
            h5.create_dataset('dsY', shape=(3,))
            self.test_filename = h5.hdf_filename

        self.lay_filename = generate_temporary_filename(prefix='lay', suffix='.hdf')
        self.other_filename = generate_temporary_filename(prefix='other', suffix='.hdf')

    def tearDown(self) -> None:
        for fname in Path(__file__).parent.glob('*'):
            if fname.suffix not in ('py', '.py', '.yaml'):
                if fname.is_file():
                    fname.unlink()

    def test_filename(self):
        with h5tbx.File() as h5:
            with self.assertRaises(AttributeError):
                h5.hdf_filename = 3
        self.assertIsInstance(h5.hdf_filename, pathlib.Path)
        self.assertTrue(h5.hdf_filename.exists())
        h5tbx.clean_temp_data()
        self.assertFalse(h5.hdf_filename.exists())
        if pathlib.Path('test.hdf').exists():
            # just in case ...
            pathlib.Path('test.hdf').unlink()
        with h5tbx.File('test.hdf') as h5:
            self.assertEqual('r+', h5.mode)
            self.assertEqual('test.hdf', h5.hdf_filename.name)
        if h5.hdf_filename.exists():
            h5.hdf_filename.unlink()

    def test_reopen_file(self):
        cv_yaml_filename = tutorial.get_standard_attribute_yaml_filename()
        cv = h5tbx.conventions.from_yaml(cv_yaml_filename, overwrite=True)
        h5tbx.use(cv)
        with h5tbx.File(data_type='experimental',
                        contact=h5tbx.__author_orcid__) as h5:
            pass
        # reopen file with read-only mode works fine
        with h5tbx.File(h5.hdf_filename, 'r') as h5:
            self.assertTrue('data_type' in h5.attrs.raw)
            self.assertTrue('contact' in h5.attrs.raw)

        # reopen file with read-write mode must also. the mandatory root attributes are set earlier...
        with h5tbx.File(h5.hdf_filename, 'r+') as h5:
            self.assertTrue('data_type' in h5.attrs.raw)
            self.assertTrue('contact' in h5.attrs.raw)

    def test_scale(self):
        h5tbx.use(None)
        cv_yaml_filename = tutorial.get_standard_attribute_yaml_filename()
        cv = h5tbx.conventions.from_yaml(cv_yaml_filename, overwrite=True)
        h5tbx.use(cv)

        self.assertTrue('scale' in cv.properties[h5tbx.Dataset])

        for scale in (0.2 * pint.Unit('Pa/V'), 0.2 * pint.Unit('Pa/V'), '0.2 Pa/V', '0.2Pa/V'):
            with h5tbx.File(data_type='experimental',
                            contact=h5tbx.__author_orcid__) as h5:
                ds = h5.create_dataset('pressure',
                                       data=4.3,
                                       units='V',
                                       offset='0.1 V',
                                       scale=scale,
                                       long_name='pressure')
                self.assertEqual(ds.units, h5tbx.get_ureg().Unit('V'))
                self.assertEqual(ds.scale, pint.Quantity(0.2, 'Pa/V'))
                self.assertEqual(ds.offset, pint.Quantity(0.1, 'V'))
                arr = ds[()]
                self.assertEqual(arr.units, 'Pa')
                self.assertEqual(arr.values, (4.3 + 0.1) * 0.2)

    def test_offset(self):
        from h5rdmtoolbox import tutorial
        cv_yaml_filename = tutorial.get_standard_attribute_yaml_filename()
        cv = h5tbx.conventions.from_yaml(cv_yaml_filename, overwrite=True)
        h5tbx.use(cv)
        with h5tbx.File(data_type='experimental',
                        contact=h5tbx.__author_orcid__) as h5:
            # offset follows equation y=m*x+b or y=(m/v*x) + b depending on the units
            # pressure stores 4.3 V. offset is 0.1 V and scale is 0.2 Pa/V
            # so return data is (4.3V+0.1V)*0.2Pa/V = 0.88 Pa
            ds_offset = h5.create_dataset('pressure_offset',
                                          data=4.3 * 0.2,
                                          units='Pa')

            with self.assertRaises(h5tbx.errors.StandardAttributeError):
                h5.create_dataset('pressure',
                                  data=4.3 * 0.2,
                                  units='Pa',
                                  offset='pressure_offset',
                                  scale='pressure_scale',
                                  long_name='offset pressure')

            self.assertFalse('pressure_scale' in h5)
            ds_scale = h5.create_dataset('pressure_scale',
                                         data=0.2,
                                         units='Pa/V')
            self.assertTrue('pressure_scale' in h5)

            ds = h5.create_dataset('pressure',
                                   data=4.3,
                                   units='V',
                                   offset='pressure_offset',
                                   scale='pressure_scale',
                                   long_name='pressure')
            self.assertEqual('/pressure_offset', ds.offset)
            self.assertEqual('/pressure_scale', ds.scale)
            self.assertEqual('Pa', ds[()].units)

            ds2 = h5.create_dataset('pressure2',
                                   data=4.3,
                                   units='V',
                                   offset=ds_offset.name,
                                   scale=ds_scale.name,
                                   long_name='pressure')
            self.assertEqual('/pressure_offset', ds2.offset)
            self.assertEqual('/pressure_scale', ds2.scale)
            self.assertEqual('Pa', ds2[()].units)


    def test_dumps(self):
        with h5tbx.File() as h5:
            h5.dumps()

    def test_create_dataset(self):
        """File has more parameters to pass as H5Base"""
        with File() as h5:
            ds = h5.create_dataset('u', shape=())
            self.assertEqual(ds.name, '/u')

    def test_uuid4(self):
        with File() as h5:
            uuid4 = uuid.uuid4()
            h5.write_uuid(uuid4)
            self.assertEqual(h5.attrs['uuid'], str(uuid4))
            h5.write_uuid(uuid4, name='uuid4')
            self.assertEqual(h5.attrs['uuid4'], str(uuid4))
            with self.assertRaises(ValueError):
                h5.write_uuid(overwrite=False)
            with self.assertRaises(ValueError):
                h5.write_uuid(uuid4, name='uuid4', overwrite=False)
            uuid4new = uuid.uuid4()
            h5.write_uuid(uuid4new, name='uuid4', overwrite=True)
            self.assertNotEqual(h5.attrs['uuid4'], str(uuid4))
            self.assertEqual(h5.attrs['uuid4'], str(uuid4new))
            h5.write_uuid(overwrite=True)
            self.assertNotEqual(h5.attrs['uuid'], str(uuid4))
            self.assertNotEqual(h5.attrs['uuid'], str(uuid4new))

    def test_timestamp(self):
        with File() as h5:
            h5.write_iso_timestamp()
            self.assertIsInstance(h5.attrs['timestamp'], str)
            h5.write_iso_timestamp(name='timestamp2')
            dt2 = h5.attrs['timestamp2']
            self.assertIsInstance(dt2, str)
            with self.assertRaises(ValueError):
                h5.write_iso_timestamp(name='timestamp2', overwrite=False)
            time.sleep(0.01)
            h5.write_iso_timestamp(name='timestamp2', overwrite=True)
            self.assertNotEqual(dt2, h5.attrs['timestamp2'])

            dtnow = datetime.now()
            dtnow_iso = dtnow.isoformat()
            time.sleep(0.01)
            h5.write_iso_timestamp(name='now', dt=dtnow)
            self.assertEqual(h5.attrs['now'], dtnow_iso)

    def test_attrs(self):
        with File(mode='w') as h5:
            h5.create_dataset('ds', shape=(), attrs={'mean': 1.2})

            h5tbx.set_config(natural_naming=False)

            h5tbx.set_config(natural_naming=True)
            self.assertEqual(h5tbx.get_config('natural_naming'), True)
            with h5tbx.set_config(natural_naming=False):
                self.assertEqual(h5tbx.get_config('natural_naming'), False)
                with self.assertRaises(AttributeError):
                    self.assertEqual(h5.attrs.mean, 1.2)
            self.assertEqual(h5tbx.get_config('natural_naming'), True)

            h5.attrs.title = 'title of file'
            self.assertEqual(h5.attrs['title'], 'title of file')

            dset = h5.create_dataset('ds', data=1,
                                     attrs={
                                         'long_name': 'a long name',
                                         'a1': 1, 'a2': 'str', 'a3': {'a': 2}
                                     })
            self.assertEqual(dset.attrs.get('a1'), 1)
            self.assertEqual(dset.attrs.get('a2'), 'str')

            h5.attrs['a dict'] = {'key1': 'value1', 'key2': 1239.2}
            self.assertDictEqual(h5.attrs['a dict'], {'key1': 'value1', 'key2': 1239.2})

            dset.attrs['a dict'] = {'key1': 'value1', 'key2': 1239.2, 'subdict': {'subkey': 99}}
            self.assertDictEqual(dset.attrs['a dict'], {'key1': 'value1', 'key2': 1239.2, 'subdict': {'subkey': 99}})

    def test_attrs_find(self):
        with File(self.test_filename, mode='r') as h5:
            self.assertEqual(
                h5['/grp_1'],
                h5.find_one(
                    {
                        '$basename': {
                            '$regex': 'grp_[0-1]'
                        }
                    },
                    '$group'
                )
            )
            #
            self.assertListEqual(
                [h5['/grp_1'], h5['/grp_2'], h5['/grp_3']],
                sorted(
                    h5.find(
                        {'$basename': {'$regex': 'grp_[0-3]'}
                         },
                        '$group'
                    )
                )
            )
            self.assertListEqual(
                [h5['/ds1'], h5['/ds2'], ],
                sorted(
                    h5.find(
                        {'$basename': {'$regex': 'ds[0-9]'}},
                        '$dataset')
                )
            )
            self.assertEqual(
                h5['/ds'], h5.find_one({'one': 1}, '$dataset')
            )
            self.assertEqual(
                [h5['/'], h5['/ds'], h5['grp_1']],
                sorted(h5.find({'one': 1}))
            )
            self.assertListEqual(
                [], h5.find({'one': {'$gt': 1}})
            )
            self.assertListEqual(
                [h5['/'], h5['ds'], h5['grp_1']],
                sorted(h5.find({'one': {'$gte': 1}}))
            )

    def test_find_group_data(self):
        with File(self.test_filename, mode='r') as h5:
            self.assertEqual(h5.find({'$basename': 'grp_1'}, '$group')[0],
                             h5.find_one({'$basename': 'grp_1'}, '$group'))
            self.assertEqual([h5['grp_1'], ], h5.find({'$basename': 'grp_1'}, '$group'))
            self.assertEqual(h5['ds'], h5.find_one({'$shape': (4,)}, "$dataset"))
            self.assertEqual(h5.find({'$ndim': 1}, "$dataset")[0], h5.find_one({'$ndim': 1}, "$dataset"))

    def test_find_dataset_data(self):
        with File(self.test_filename, mode='r') as h5:
            self.assertEqual(h5['ds'], h5.find_one({'$basename': 'ds'}, '$dataset'))
            self.assertEqual(h5['ds'], h5.find_one({'$basename': 'ds'}, '$dataset'))
            self.assertEqual([h5['ds'], ], h5.find({'$basename': 'ds'}))
            self.assertEqual([h5['ds'], ], h5.find({'$shape': (4,)}, '$dataset'))
            self.assertEqual(h5['ds'], h5.find_one({'$shape': (4,)}, '$dataset'))
            r = h5.find_one({'$ndim': 1}, '$dataset')
            self.assertEqual(h5['ds'].ndim, 1)
            self.assertIsInstance(h5['ds'], h5py.Dataset)
            self.assertEqual([h5['ds'], h5['ds1'], h5['ds2'], h5['dsY']],
                             sorted(h5.find({'$ndim': 1}, '$dataset')))

    def test_open(self):
        with File(mode='w') as h5:
            h5.attrs['one'] = 1
        with File(h5.hdf_filename, mode='w') as h5:
            self.assertTrue('one' not in h5.attrs)
            h5.attrs['one'] = 1
        with File(h5.hdf_filename, mode='r+') as h5:
            self.assertTrue('one' in h5.attrs)
            h5.attrs['two'] = 2
            self.assertTrue('two' in h5.attrs)

        with File(mode='w') as h5:
            pass
        h5.reopen('r+')
        self.assertEqual(h5.mode, 'r+')
        h5.close()

    def test_groups(self):
        with File() as h5:
            groups = h5.get_groups()
            self.assertEqual(groups, [])
            h5.create_group('grp_1', attrs=dict(a=1))
            h5.create_group('grp_2', attrs=dict(a=1))
            h5.create_group('grpXYZ', attrs=dict(b=2))
            h5.create_group('mygrp_2')

            groups = h5.get_groups()
            self.assertEqual(len(groups), 4)
            self.assertEqual(groups, [h5['grpXYZ'], h5['grp_1'], h5['grp_2'], h5['mygrp_2']])

            groups = h5.get_groups('^grp_[0-9]$')
            self.assertEqual(len(groups), 2)
            self.assertEqual(sorted(groups), sorted([h5['grp_1'], h5['grp_2']]))
            self.assertEqual(sorted([h5['grp_1'], h5['grp_2']]), sorted(h5.find({'a': 1}, rec=True)))

            h5.create_group('grpXYZ/grp123', attrs=dict(a=1))
            self.assertEqual(sorted([h5['grpXYZ/grp123'],
                                     h5['grp_1'],
                                     h5['grp_2'], ]),
                             sorted(h5.find({'a': 1}, rec=True)))
            self.assertEqual(sorted([h5['grp_1'], h5['grp_2']]),
                             sorted(h5.find({'a': 1}, rec=False)))

    def test_tree_structur(self):
        with File() as h5:
            h5.attrs['one'] = 1
            h5.attrs['two'] = 2
            h5.create_dataset('rootds', shape=(2, 40, 3))
            grp = h5.create_group('grp',
                                  attrs={'description': 'group description'})
            grp.create_dataset('grpds',
                               shape=(2, 40, 3))
            tree = h5.get_tree_structure()

    def test_rename(self):
        with File(mode='w') as h5:
            h5.create_dataset('testds',
                              data=np.random.rand(10, 10))
            h5.testds.rename('newname')
            ds = h5.create_dataset('testds_scale',
                                   data=np.random.rand(10, 10))
            ds.make_scale()
            with self.assertRaises(KeyError):
                ds.rename('newname')

    def test_dimension_scales(self):
        with File(mode='w') as h5:
            _ = h5.create_dataset('x', data=[1, 2, 3], make_scale=True)
            with self.assertRaises(ValueError):  # because name already exists
                _ = h5.create_dataset('x', data=[1, 2, 3], make_scale=True)
            del h5['x']
            with self.assertRaises(TypeError):
                _ = h5.create_dataset('x', data=[1, 2, 3], make_scale=[1, 2])

    def test_scale_manipulation(self):
        with File(mode='w') as h5:
            h5.create_dataset('x',
                              data=np.random.rand(10),
                              attrs=dict(long_name='x-coordinate',
                                         units='m', ), )
            h5.create_dataset('time', data=np.random.rand(10), attrs=dict(long_name='time', units='s'))
            h5.create_dataset('temp', data=np.random.rand(10), attrs=dict(long_name='temperature', units='K'),
                              attach_scale=((h5['x'], h5['time']),))
            self.assertTrue(h5['temp'].dims[0])
            h5['temp'].set_primary_scale(0, 1)

    def test_xr_dataset(self):
        import xarray as xr
        # from https://docs.xarray.dev/en/v0.9.5/examples/quick-overview.html#datasets
        ds = xr.Dataset({'foo': [1, 2, 3], 'bar': ('x', [1, 2]), 'baz': np.pi})
        ds.foo.attrs['units'] = 'm'
        ds.foo.attrs['long_name'] = 'foo'

        ds.bar.attrs['units'] = 'm'
        ds.bar.attrs['long_name'] = 'bar'

        ds.baz.attrs['units'] = 'm'
        ds.baz.attrs['long_name'] = 'baz'

        with File() as h5:
            h5.create_dataset_from_xarray_dataset(ds)

    def test_attrs(self):
        with File(mode='w') as h5:
            h5tbx.set_config(natural_naming=False)

            with self.assertRaises(AttributeError):
                self.assertEqual(h5.attrs.mean, 1.2)

            h5tbx.set_config(natural_naming=True)

            h5.attrs.title = 'title of file'

            self.assertEqual(h5.attrs['title'], 'title of file')
            #
            # h5.attrs['gr'] = h5['/']
            # self.assertEqual(h5.attrs['gr'].name, '/')

            # h5.attrs.gr2 = h5['/']
            # self.assertEqual(h5.attrs['gr2'].name, '/')

            dset = h5.create_dataset('ds', data=1,
                                     attrs={'a1': 1, 'a2': 'str',
                                            'a3': {'a': 2}})
            self.assertEqual(dset.attrs.get('a1'), 1)
            self.assertEqual(dset.attrs.get('a2'), 'str')

            h5.attrs['a dict'] = {'key1': 'value1', 'key2': 1239.2}
            self.assertDictEqual(h5.attrs['a dict'], {'key1': 'value1', 'key2': 1239.2})

            dset.attrs['a dict'] = {'key1': 'value1', 'key2': 1239.2}
            self.assertDictEqual(dset.attrs['a dict'], {'key1': 'value1', 'key2': 1239.2})

    def test_assign_data_to_existing_dset(self):
        h5tbx.set_config(natural_naming=True)
        with File(mode='w') as h5:
            ds = h5.create_dataset('ds', shape=(2, 3))
            ds[0, 0] = 5
            self.assertEqual(ds[0, 0], 5)

    def test_from_yaml_to_hdf(self):
        dictionary = {
            'boundary/outlet boundary/y':
                {'data': 2, 'attrs': {'units': 'm', 'standard_name': 'y_coordinate',
                                      'comment': 'test', 'another_attr': 100.2,
                                      'array': [1, 2, 3]}},
            'test/grp': {'attrs': {'long_name': 'a test group'}}
        }
        yaml_file = generate_temporary_filename(suffix='.yaml')
        with open(yaml_file, 'w') as f:
            yaml.safe_dump(dictionary, f)

        hdf_filename = generate_temporary_filename(suffix='.hdf')
        with File(hdf_filename, 'w') as h5:
            h5.create_from_yaml(yaml_file)
            self.assertIn('test/grp', h5)
            self.assertIn('boundary/outlet boundary/y', h5)
            self.assertTrue(h5['boundary/outlet boundary/y'].attrs['units'], 'm')

    def test_dataset_value_comparison(self):
        with File(mode='w') as h5:
            ds1 = h5.create_dataset('ds1', data=4.4)
            ds2 = h5.create_dataset('ds2', data=4.5)
            self.assertEqual(0, ds1.ndim)
            self.assertEqual(0, ds2.ndim)
            self.assertTrue(ds1 < float(ds2[()]))
            self.assertFalse(ds1 > float(ds2[()]))
            self.assertFalse(ds1 == float(ds2[()]))

    def test_get_group_names(self):
        with File(mode='w') as h5:
            g = h5.create_group('one', 'one')
            g.create_group('two', 'two')

            g = g.create_group('three', 'three')
            g.create_group('four', 'four')
            self.assertEqual(h5['one'].get_group_names(), ['three', 'three/four', 'two'])
            self.assertEqual(sorted(h5['one'].get_group_names(recursive=False)), sorted(['two', 'three']))
            self.assertEqual(sorted(h5['/'].get_group_names(recursive=False)), sorted(['one', ]))
            self.assertEqual(sorted(h5.get_group_names(recursive=False)), sorted(['one', ]))

    def test_get_dataset_names(self):
        with File(mode='w') as h5:
            h5.create_dataset('one', data=1, attrs=dict(long_name='long name', units=''))
            h5.create_dataset('two', data=1, attrs=dict(long_name='long name', units=''))
            h5.create_dataset('grp/three', data=1, attrs=dict(long_name='long name', units=''))
            h5.create_dataset('grp/two', data=1, attrs=dict(long_name='long name', units=''))
            self.assertEqual(h5.get_dataset_names(),
                             ['grp/three', 'grp/two', 'one', 'two'])

    def test_multi_dim_scales(self):
        fname = generate_temporary_filename(suffix='.hdf')
        with h5py.File(fname, 'w') as h5:
            x = h5.create_dataset('x', data=[0.0, 10.5, 20.13])
            ix = h5.create_dataset('ix', data=[0, 16, 32])
            y = h5.create_dataset('y', data=[0.0, 4.5, 23.13])
            iy = h5.create_dataset('iy', data=[0, 16, 32])

            signal = h5.create_dataset('signal', data=np.ones((3, 3)))

            x.make_scale('x')
            ix.make_scale('ix')
            y.make_scale('y')
            iy.make_scale('iy')

            signal.dims[0].attach_scale(h5['x'])
            signal.dims[0].attach_scale(h5['ix'])
            signal.dims[1].attach_scale(h5['y'])
            signal.dims[1].attach_scale(h5['iy'])

        with File(fname) as h5:
            x = h5['x'][:]
            ix = h5['ix'][:]
            s = h5['signal'][:, :]
