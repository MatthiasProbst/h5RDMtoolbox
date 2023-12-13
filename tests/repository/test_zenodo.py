import json
import logging
import pathlib
import requests
import unittest
from datetime import datetime

import h5rdmtoolbox as h5tbx
from h5rdmtoolbox.repository import zenodo, upload_file
from h5rdmtoolbox.repository.h5metamapper import hdf2json
from h5rdmtoolbox.repository.zenodo.metadata import Metadata, Creator, Contributor
from h5rdmtoolbox.repository.zenodo.tokens import get_api_token

logger = logging.getLogger(__name__)

CLEANUP_ZENODO_SANDBOX = False


class TestConfig(unittest.TestCase):

    def test_get_api(self):
        self.assertIsInstance(get_api_token(sandbox=True), str)

    def test_upload_hdf(self):
        z = zenodo.ZenodoSandboxDeposit(None)
        with h5tbx.File() as h5:
            h5.attrs['long_name'] = 'root'
            h5.create_dataset('test', data=1, attrs={'units': 'm/s', 'long_name': 'dataset 1'})
            h5.create_dataset('grp1/test2', data=2, attrs={'test': 1, 'long_name': 'dataset 2'})
        z.upload_hdf_file(h5.hdf_filename, metamapper=hdf2json)
        filenames = z.get_filenames()
        self.assertIn('tmp0.hdf', filenames)
        self.assertIn('tmp0.json', filenames)
        with self.assertRaises(KeyError):
            _ = z.download_file('test.hdf')
        hdf_filename = z.download_file('tmp0.hdf')

        self.assertTrue(hdf_filename.exists())

        with h5tbx.File(hdf_filename) as h5:
            self.assertEqual(h5.attrs['long_name'], 'root')
            self.assertEqual(h5['test'].attrs['units'], 'm/s')
            self.assertEqual(h5['test'].attrs['long_name'], 'dataset 1')
            self.assertEqual(h5['grp1/test2'].attrs['test'], 1)
            self.assertEqual(h5['grp1/test2'].attrs['long_name'], 'dataset 2')

        json_filename = z.download_file('tmp0.json')
        self.assertTrue(json_filename.exists())
        with open(json_filename) as f:
            json_dict = json.loads(f.read())

        self.assertEqual(json_dict['attrs'], {'__h5rdmtoolbox_version__': '1.0.0', 'long_name': 'root'})

    def test_ZenodoSandboxDeposit(self):
        z = zenodo.ZenodoSandboxDeposit(None)
        self.assertIsInstance(z.metadata, dict)
        self.assertEqual(z.get_doi(), f'10.5281/zenodo.{z.rec_id}')
        self.assertIn('access_right', z.metadata)
        self.assertIn('prereserve_doi', z.metadata)
        self.assertEqual('open', z.metadata['access_right'])
        self.assertEqual(z.rec_id, z.metadata['prereserve_doi']['recid'])
        self.assertTrue(z.exists())

        old_rec_id = z.rec_id

        z.delete()
        with self.assertRaises(ValueError):
            _ = zenodo.ZenodoSandboxDeposit(old_rec_id)

        z = zenodo.ZenodoSandboxDeposit(None)
        self.assertNotEqual(old_rec_id, z.rec_id)

        with self.assertRaises(TypeError):
            z.metadata = {'access_right': 'closed'}

        meta = Metadata(
            version="0.1.0-rc.1+build.1",
            title='[test]h5tbxZenodoInterface',
            description='A toolbox for managing HDF5-based research data management',
            creators=[Creator(name="Probst, Matthias",
                              affiliation="KIT - ITS",
                              orcid="0000-0001-8729-0482")],
            contributors=[Contributor(name="Probst, Matthias",
                                      affiliation="KIT - ITS",
                                      orcid="0000-0001-8729-0482",
                                      type="ContactPerson")],
            upload_type='image',
            image_type='photo',
            access_right='open',
            keywords=['hdf5', 'research data management', 'rdm'],
            publication_date=datetime.now(),
            embargo_date='2020'
        )
        z.metadata = meta
        ret_metadata = z.metadata
        self.assertEqual(ret_metadata['upload_type'],
                         meta.model_dump()['upload_type'])
        self.assertListEqual(ret_metadata['keywords'],
                             meta.model_dump()['keywords'])

        # add file:
        tmpfile = pathlib.Path('testfile.txt')
        with open(tmpfile, 'w') as f:
            f.write('This is a test file.')
        z.upload_file(tmpfile, overwrite=True)
        self.assertIn('testfile.txt', z.get_filenames())

        with self.assertWarns(UserWarning):
            z.upload_file('testfile.txt', overwrite=False)

        upload_file(z, tmpfile, overwrite=True)

        with self.assertWarns(UserWarning):
            upload_file(z, tmpfile, overwrite=False)

        # delete file locally:
        tmpfile.unlink()
        self.assertFalse(tmpfile.exists())

        filename = z.download_file('testfile.txt', target_folder='.')
        self.assertIsInstance(filename, pathlib.Path)
        self.assertTrue(filename.exists())
        filename.unlink()

        filenames = z.download_files(target_folder='.')
        self.assertIsInstance(filenames, list)
        self.assertIsInstance(filenames[0], pathlib.Path)
        for filename in filenames:
            self.assertTrue(filename.exists())
            filename.unlink()

        z.delete()
        self.assertFalse(z.exists())

    if CLEANUP_ZENODO_SANDBOX:
        def delete_sandbox_deposits(self):
            """Delete all deposits in the sandbox account."""
            r = requests.get(
                'https://sandbox.zenodo.org/api/deposit/depositions',
                params={'access_token': get_api_token(sandbox=True)}
            )
            r.raise_for_status()
            for deposit in r.json():
                # if deposit['title'].startswith('[test]'):
                if not deposit['submitted']:
                    logger.debug(f'deleting deposit {deposit["title"]} with id {deposit["id"]}')
                    r = requests.delete(
                        'https://sandbox.zenodo.org/api/deposit/depositions/{}'.format(deposit['id']),
                        params={'access_token': get_api_token(sandbox=True)}
                    )
                    self.assertEqual(204, r.status_code)
                else:
                    logger.debug(
                        f'Cannot delete {deposit["title"]} with id {deposit["id"]} because it is already published."')

    def setUp(self) -> None:
        """Delete all deposits in the sandbox account."""
        if CLEANUP_ZENODO_SANDBOX:
            self.delete_sandbox_deposits()

    def tearDown(self) -> None:
        """Delete all deposits in the sandbox account."""
        if CLEANUP_ZENODO_SANDBOX:
            self.delete_sandbox_deposits()
