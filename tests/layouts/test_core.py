"""Test the mongoDB interface"""
import h5py
import numpy as np
import unittest

from h5rdmtoolbox import layouts
from h5rdmtoolbox.databases import hdfdb


class TestCore(unittest.TestCase):

    def test_number_of_datasets(self):
        with h5py.File('test.hdf', 'w') as h5:
            ds = h5.create_dataset('u', shape=(3, 4), dtype='float32')
            h5.create_dataset('a/b/c/u', shape=(3, 4), dtype='float64')

            lay = layout.Layout()
            spec_number_of_specific_datasets = lay.add(
                hdfdb.FileDB.find,
                flt={'$name': {'$regex': '.*/u$'}}, n=2, recursive=True,
                comment='/u exists'
            )
            res = lay.validate(h5)
            self.assertFalse(spec_number_of_specific_datasets.failed)
            self.assertEqual(spec_number_of_specific_datasets.n_fails, 0)

            lay = layout.Layout()
            spec_number_of_specific_datasets = lay.add(
                hdfdb.FileDB.find,
                flt={'$name': {'$regex': '.*/u$'}}, n=1, recursive=True,
                comment='/u exists'
            )
            res = lay.validate(h5)
            self.assertTrue(spec_number_of_specific_datasets.failed)
            self.assertEqual(spec_number_of_specific_datasets.n_fails, 0)

            self.assertEqual(lay.specifications[0].n_calls, 1)
            lay.reset()
            self.assertEqual(lay.specifications[0].n_calls, 0)
            res = lay.validate(h5.filename)
            self.assertTrue(spec_number_of_specific_datasets.failed)
            self.assertEqual(spec_number_of_specific_datasets.n_fails, 0)

            # self.assertTrue(spec1.failed)

    def test_all_dtypes(self):
        with h5py.File('test.hdf', 'w') as h5:
            ds = h5.create_dataset('u', shape=(3, 4), dtype='float32')
            h5.create_dataset('a/u', shape=(3, 4), dtype='float64')
            h5.create_dataset('a/v', shape=(3, 4), dtype='float32')
            h5.create_dataset('a/b/c/u', shape=(3, 4), dtype='float64')

            lay = layout.Layout()
            spec_all_ds = lay.add(hdfdb.FileDB.find,
                                  comment='Any dataset',
                                  n=None,
                                  flt={'$shape': {'$exists': True}},
                                  objfilter='dataset')  # all datasets
            spec_all_ds_are_float32 = spec_all_ds.add(hdfdb.FileDB.find_one,
                                                      comment='Is float32',
                                                      flt={'$dtype': np.dtype(
                                                          '<f4')})  # applies all these on spec_all_ds results
            with self.assertRaises(RuntimeError):
                lay(h5)

            res = lay.validate(h5)
            self.assertEqual(spec_all_ds_are_float32.n_calls, 4)
            self.assertEqual(spec_all_ds_are_float32.n_fails, 2)
            self.assertEqual(spec_all_ds_are_float32.n_successes, 2)

            self.assertFalse(res.is_valid())
            self.assertEqual(len(res.list_of_failed_specs), 1)

    # def test_core(self):
    #     lay = layout.Layout()
    #
    #     # spec1 = lay.add(hdfdb.FileDB.find_one, flt={'$name': '/u'}, comment='/u exists')
    #     spec1 = lay.add(
    #         hdfdb.FileDB.find,
    #         flt={'$name': {'$regex': '.*/u$'}}, n=2, recursive=True,
    #         comment='/u exists'
    #     )
    #     #
    #     # spec2 = lay.add(hdfdb.FileDB.find_one, flt={'$name': '/v'}, comment='/v exists')
    #
    #     # spec3 = lay.add(hdfdb.FileDB.find, flt={'$name': {'$regex': '.*'},
    #     #                                         '$dtype': np.dtype('<f4')},
    #     #                 objfilter='dataset',
    #     #                 comment='every dataset is float32')
    #
    #     # spec_all_ds = lay.add(hdfdb.FileDB.find,
    #     #                       comment='Any dataset',
    #     #                       n=None,
    #     #                       flt={'$shape': {'$exists': True}},
    #     #                       objfilter='dataset')  # all datasets
    #     # spec_all_ds_are_float32 = spec_all_ds.add(hdfdb.FileDB.find_one,
    #     #                                           comment='Is float32',
    #     #                                           flt={'$dtype': np.dtype(
    #     #                                               '<f4')})  # applies all these on spec_all_ds results
    #
    #     #
    #     # spec_has_units = spec_all_ds.add(hdfdb.FileDB.find, flt={'units': 'm/s'},
    #     #                                  comment='every dataset must have a unit attribute')  # all datasets must have units
    #
    #     # assert spec_all_ds.id == spec_has_units.parent.id
    #
    #     with h5py.File('test.hdf', 'w') as h5:
    #         ds = h5.create_dataset('u', shape=(3, 4), dtype='float32')
    #         ds.attrs['units'] = 'm/s'
    #         h5.create_dataset('v', shape=(3, 4), dtype='float64')
    #         h5.create_dataset('w', shape=(3, 4), dtype='float64')
    #         h5.create_dataset('a/b/c/u', shape=(3, 4), dtype='float64')
    #
    #         res = lay(h5)
    #
    #     # print(lay.is_valid)
    #     # print('--- summary ---')
    #     lay.print_summary()
    #     # for r in lay.get_failed_spec():
    #     #     print(r.id, r.kwargs, r.comment)
