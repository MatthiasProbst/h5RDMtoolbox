import logging
import numpy as np
import pandas as pd
import unittest
from pint_xarray import unit_registry as ureg

import h5rdmtoolbox as h5tbx
from h5rdmtoolbox.config import CONFIG
from h5rdmtoolbox.wrapper import set_loglevel

logger = logging.getLogger('h5rdmtoolbox.wrapper')
set_loglevel('ERROR')

ureg.default_format = CONFIG.UREG_FORMAT

h5tbx.use('default')


class TestCore(unittest.TestCase):

    def test_from_csv(self):
        df = pd.DataFrame({'x': [1, 5, 10], 'y': [-3, 20, 0]})
        csv_filename = h5tbx.utils.generate_temporary_filename(suffix='.csv')
        df.to_csv(csv_filename)
        with h5tbx.H5File() as h5:
            h5.create_datasets_from_csv(csv_filename=csv_filename)

    def test_modify_static_properties(self):
        with h5tbx.H5File() as h5:
            ds = h5.create_dataset('grp/data', shape=(10, 20, 30),
                                   data=np.random.rand(10, 20, 30),
                                   chunks=(1, 20, 30))
            ds0 = ds[:]

            new_ds = ds.modify_chunks((2, 5, 6))
            ds1 = new_ds[:]

            self.assertEqual(ds.chunks, (1, 20, 30))
            self.assertEqual(new_ds.chunks, (2, 5, 6))

        self.assertTrue(np.all(ds1 == ds0))

        with h5tbx.H5File() as h5:
            ds = h5.create_dataset('data', shape=(10, 20, 30),
                                   data=np.random.rand(10, 20, 30),
                                   chunks=(1, 20, 30))
            ds0 = ds[:]

            new_ds = ds.modify_chunks((2, 5, 6))
            ds1 = new_ds[:]

            self.assertEqual(ds.chunks, (1, 20, 30))
            self.assertEqual(new_ds.chunks, (2, 5, 6))
        self.assertTrue(np.all(ds1 == ds0))

        with h5tbx.H5File() as h5:
            ds = h5.create_dataset('data', shape=(10, 20, 30),
                                   data=np.random.rand(10, 20, 30),
                                   chunks=(1, 20, 30),
                                   dtype=np.int)
            new_ds = h5['/']._modify_static_dataset_properties(dataset=ds,
                                                               dtype=np.float)
            self.assertEqual(ds.dtype, np.int)
            self.assertEqual(new_ds.dtype, np.float)

            ds1 = new_ds[:]
            new_ds2 = h5['/']._modify_static_dataset_properties(dataset=new_ds,
                                                                name='data2')
            ds2 = new_ds2[:]
            self.assertEqual(new_ds2.name, '/data2')
            self.assertTrue('data' not in h5)
            self.assertTrue('data2' in h5)
            self.assertTrue(np.all(ds1 == ds2))

        with h5tbx.H5File() as h5:
            ds = h5.create_dataset('data', shape=(10, 20, 30),
                                   data=np.random.rand(10, 20, 30),
                                   chunks=(1, 20, 30),
                                   dtype=np.int)
            new_ds = ds.modify_dtype(np.float)
            self.assertEqual(ds.dtype, np.int)
            self.assertEqual(new_ds.dtype, np.float)

            ds1 = new_ds[:]
            new_ds2 = new_ds.rename('data2')
            ds2 = new_ds2[:]
            self.assertEqual(new_ds2.name, '/data2')
            self.assertTrue('data' not in h5)
            self.assertTrue('data2' in h5)
            self.assertTrue(np.all(ds1 == ds2))
