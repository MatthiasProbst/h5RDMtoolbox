import unittest

from h5rdmtoolbox import generate_temporary_filename
from h5rdmtoolbox.conventions import utils
from h5rdmtoolbox.conventions.standard_name import xmlsnt2dict, StandardNameTable


class TestTranslation(unittest.TestCase):

    def test_xml(self):
        piv_snt = StandardNameTable.load_registered('piv-v1')
        xml_filename = utils.dict2xml(generate_temporary_filename(suffix='.xml'),
                                      name=piv_snt.name,
                                      dictionary=piv_snt.table,
                                      versionname=piv_snt.versionname)
        data, meta = xmlsnt2dict(xml_filename=xml_filename)
        self.assertEqual(meta['name'], piv_snt.name, )
        self.assertEqual(meta['versionname'], piv_snt.versionname)
