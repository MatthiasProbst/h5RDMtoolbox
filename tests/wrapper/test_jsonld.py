import json
import pathlib
import rdflib
import unittest

import h5rdmtoolbox as h5tbx
import ontolutils
from h5rdmtoolbox import __version__
from h5rdmtoolbox.convention import rdf
from h5rdmtoolbox.convention.hdf_ontology import HDF5
from h5rdmtoolbox.convention.rdf import RDF_SUBJECT_ATTR_NAME
from h5rdmtoolbox.wrapper import jsonld
from h5rdmtoolbox.wrapper.jsonld import build_node_list
from ontolutils import M4I
from ontolutils import namespaces, urirefs, Thing

logger = h5tbx.logger

__this_dir__ = pathlib.Path(__file__).parent


class TestCore(unittest.TestCase):

    def setUp(self):
        LEVEL = 'WARNING'
        logger.setLevel(LEVEL)
        for h in logger.handlers:
            h.setLevel(LEVEL)

    def tearDown(self):
        pathlib.Path('test.hdf').unlink(missing_ok=True)

    def test_build_node_list(self):
        g = rdflib.Graph()
        base_node = rdflib.BNode()
        g.add((base_node, rdflib.RDF.type, HDF5.Attribute))
        list_node = build_node_list(g, [1, 2, 3])
        g.add((base_node, HDF5.value, list_node))

        print(g.serialize(format='json-ld', indent=2))
        sparql_str = """PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
PREFIX HDF5: <http://purl.allotrope.org/ontologies/hdf5/1.8#>

SELECT ?item
WHERE {
    ?id a HDF5:Attribute .
    ?id HDF5:value ?list .
    ?list rdf:rest*/rdf:first ?item
}"""
        qres = g.query(sparql_str)
        list_values = [int(row[0]) for row in qres]
        self.assertEqual(list_values, [1, 2, 3])

        g = rdflib.Graph()
        base_node = rdflib.BNode()
        g.add((base_node, rdflib.RDF.type, HDF5.Attribute))
        list_node = build_node_list(g, [1, 'str', 3.4, True])
        g.add((base_node, HDF5.value, list_node))

        print(g.serialize(format='json-ld', indent=2))
        sparql_str = """PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
PREFIX HDF5: <http://purl.allotrope.org/ontologies/hdf5/1.8#>

SELECT ?item
WHERE {
    ?id a HDF5:Attribute .
    ?id HDF5:value ?list .
    ?list rdf:rest*/rdf:first ?item
}"""
        qres = g.query(sparql_str)
        list_values = [row[0].value for row in qres]
        self.assertEqual(list_values, [1, 'str', 3.4, True])

    def test_dump_hdf_to_json(self):
        """similar yet different to https://hdf5-json.readthedocs.io/en/latest/index.html"""
        with h5tbx.File(name=None, mode='w') as h5:
            # h5.attrs['test_attr'] = 123
            del h5['h5rdmtoolbox']
            ds = h5.create_dataset('grp/test_dataset',
                                   data=[1, 2, 3],
                                   attrs={'standard_name': 'x_velocity',
                                          'standard_name_non_iri': 'x_velocity',
                                          'unit': 'm/s'})
            ds.rdf.subject = str(M4I.NumericalVariable)
            ds.rdf.predicate['standard_name'] = 'https://matthiasprobst.github.io/ssno#standardName'
            ds.rdf.object['standard_name'] = 'https://matthiasprobst.github.io/pivmeta#x_velocity'
            ds.rdf.object['standard_name_non_iri'] = 'https://matthiasprobst.github.io/pivmeta#x_velocity'

            ds.attrs['a list'] = [0, 1, 2, 3]
            ds.attrs['a 1D list'] = (-2.3,)

        # def dump_hdf_to_json(h5_filename):
        with h5tbx.File(h5.hdf_filename, 'r') as h5:
            json_str = jsonld.dumps(h5, indent=2, compact=False)

        get_all_datasets_with_standard_name = """PREFIX hdf5: <http://purl.allotrope.org/ontologies/hdf5/1.8#>
        PREFIX ssno: <https://matthiasprobst.github.io/ssno#>
        
        SELECT  ?name ?sn
        {
            ?obj a hdf5:Dataset .
            ?obj hdf5:name ?name .
            ?obj ssno:standardName ?sn .
        }"""
        g = rdflib.Graph().parse(data=json_str, format='json-ld')
        qres = g.query(get_all_datasets_with_standard_name)
        self.assertEqual(len(qres), 1)
        for name, sn in qres:
            self.assertEqual(str(name), '/grp/test_dataset')
            self.assertEqual(str(sn), 'https://matthiasprobst.github.io/pivmeta#x_velocity')

        # get list 1
        sparql_str = """PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
PREFIX pivmeta: <https://matthiasprobst.github.io/pivmeta#>
PREFIX hdf5: <http://purl.allotrope.org/ontologies/hdf5/1.8#>

SELECT ?item
WHERE {
  ?id a hdf5:Attribute .
  ?id hdf5:value ?list .
  ?id hdf5:name "a list" .
  ?list rdf:rest*/rdf:first ?item
}"""
        qres = g.query(sparql_str)
        for i, row in enumerate(qres):
            print(row)
            self.assertEqual(int(row[0]), i)

        # get list 2
        sparql_str = """PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
PREFIX pivmeta: <https://matthiasprobst.github.io/pivmeta#>
PREFIX hdf5: <http://purl.allotrope.org/ontologies/hdf5/1.8#>

SELECT ?item
WHERE {
  ?id a hdf5:Attribute .
  ?id hdf5:value ?list .
  ?id hdf5:name "a 1D list" .
  ?list rdf:rest*/rdf:first ?item
}"""
        qres = g.query(sparql_str)
        for i, row in enumerate(qres):
            print(row)
            self.assertEqual(float(row[0]), -2.3)

    def test_json_to_hdf(self):
        @namespaces(foaf='http://xmlns.com/foaf/0.1/',
                    prov='http://www.w3.org/ns/prov#')
        @urirefs(Person='prov:Person',
                 name='foaf:firstName',
                 lastName='foaf:lastName')
        class Person(Thing):
            name: str = None
            lastName: str

        p = Person(name='John', lastName='Doe')

        # def dump_hdf_to_json(h5_filename):
        with h5tbx.File('test.hdf', 'w') as h5:
            jsonld.to_hdf(h5.create_group('contact'),
                          data=json.loads(p.model_dump_jsonld(resolve_keys=False)),
                          predicate='m4i:contact')
            self.assertTrue('contact' in h5)
            self.assertEqual(h5['contact'].attrs['name'], 'John')
            self.assertEqual(h5['contact'].attrs['lastName'], 'Doe')
            self.assertEqual(h5['contact'].rdf['name'].predicate, 'http://xmlns.com/foaf/0.1/firstName')
            self.assertEqual(h5['contact'].rdf['lastName'].predicate, 'http://xmlns.com/foaf/0.1/lastName')
            h5.dumps()

        # def dump_hdf_to_json(h5_filename):
        with h5tbx.File('test.hdf', 'w') as h5:
            jsonld.to_hdf(h5.create_group('contact'),
                          data=p.model_dump_jsonld(resolve_keys=False),
                          predicate='m4i:contact')
            h5.dumps()
            self.assertTrue('contact' in h5)
            self.assertEqual(h5['contact'].attrs['name'], 'John')
            self.assertEqual(h5['contact'].attrs['lastName'], 'Doe')
            self.assertEqual(h5['contact'].rdf['name'].predicate, 'http://xmlns.com/foaf/0.1/firstName')
            self.assertEqual(h5['contact'].rdf['lastName'].predicate, 'http://xmlns.com/foaf/0.1/lastName')

        # def dump_hdf_to_json(h5_filename):
        with h5tbx.File('test.hdf', 'w') as h5:
            jsonld.to_hdf(h5.create_group('contact'),
                          source=p,
                          predicate='m4i:contact',
                          resolve_keys=False)
            self.assertTrue('contact' in h5)
            self.assertEqual(h5['contact'].attrs['name'], 'John')
            self.assertEqual(h5['contact'].attrs['lastName'], 'Doe')
            self.assertEqual(h5['contact'].rdf['name'].predicate, 'http://xmlns.com/foaf/0.1/firstName')
            self.assertEqual(h5['contact'].rdf['lastName'].predicate, 'http://xmlns.com/foaf/0.1/lastName')
            h5.dumps()

    def test_jsonld_dumps(self):
        sn_iri = 'https://matthiasprobst.github.io/ssno#standardName'
        with h5tbx.File(mode='w') as h5:
            h5.create_dataset('test_dataset', shape=(3,))
            grp = h5.create_group('grp')
            grp.attrs['test', sn_iri] = 'test'
            sub_grp = grp.create_group('Fan')
            ds = sub_grp.create_dataset('D3', data=300)
            sub_grp['D3'].attrs['units', 'http://w3id.org/nfdi4ing/metadata4ing#hasUnits'] = 'mm'
            sub_grp['D3'].rdf['units'].object = 'https://qudt.org/vocab/unit/MilliM'
            sub_grp['D3'].attrs['standard_name', sn_iri] = 'blade_diameter3'
            ds.rdf.subject = 'https://w3id.org/nfdi4ing/metadata4ing#NumericalVariable'
            self.assertEqual(ds.rdf.subject, 'https://w3id.org/nfdi4ing/metadata4ing#NumericalVariable')
            self.assertEqual(ds.attrs[RDF_SUBJECT_ATTR_NAME],
                             'https://w3id.org/nfdi4ing/metadata4ing#NumericalVariable')
            h5.dumps()
        from pprint import pprint
        out_dict = h5tbx.jsonld.dumpd(h5.hdf_filename,
                                      context={'schema': 'http://schema.org/',
                                               "ssno": "https://matthiasprobst.github.io/ssno#",
                                               "m4i": "http://w3id.org/nfdi4ing/metadata4ing#"},
                                      resolve_keys=True)

        pprint(out_dict)
        found_m4iNumericalVariable = False
        for g in out_dict['@graph']:
            if 'https://w3id.org/nfdi4ing/metadata4ing#NumericalVariable' in g['@type']:
                self.assertDictEqual(g['m4i:hasUnits'], {'@id': 'https://qudt.org/vocab/unit/MilliM'})
                self.assertEqual(g['ssno:standardName'], 'blade_diameter3')
                found_m4iNumericalVariable = True
        self.assertTrue(found_m4iNumericalVariable)

    def test_to_hdf_with_graph(self):
        test_data = """{
  "@context": {
    "foaf": "http://xmlns.com/foaf/0.1/",
    "prov": "http://www.w3.org/ns/prov#",
    "rdfs": "http://www.w3.org/2000/01/rdf-schema#",
    "schema": "http://schema.org/",
    "local": "http://example.org/"
  },
  "@graph": [
    {
      "@id": "local:testperson1",
      "@type": "prov:Person",
      "foaf:firstName": "John",
      "foaf:lastName": "Doe",
      "age": 21,
      "schema:affiliation": {
        "@id": "Nef657ff40e464dd09580db3f32de2cf1",
        "@type": "schema:Organization",
        "rdfs:label": "MyAffiliation"
      }
    },
    {
      "@id": "local:testperson2",
      "@type": "prov:Person",
      "foaf:firstName": "Jane",
      "foaf:lastName": "Doe",
      "age": 20,
      "schema:affiliation": {
        "@type": "schema:Organization",
        "rdfs:label": "MyAffiliation"
      }
    }
  ]
}"""
        with open('graph.json', 'w') as f:
            f.write(test_data)
        jsondict = json.loads(test_data)
        self.assertTrue(jsondict['@graph'][0]['@id'].startswith('local:testperson'))
        with h5tbx.File('graph.hdf', 'w') as h5:
            grp = h5.create_group('person')
            jsonld.to_hdf(grp=grp, source='graph.json')
            self.assertTrue('@graph' not in grp)
            self.assertTrue('Person' in grp)
            self.assertTrue('Person2' in grp)
            h5.dumps()
        # cleanup:
        pathlib.Path('graph.json').unlink(missing_ok=True)
        h5.hdf_filename.unlink(missing_ok=True)

    def test_download_context(self):
        from h5rdmtoolbox.utils import download_context
        from h5rdmtoolbox import UserDir
        url = "https://w3id.org/nfdi4ing/metadata4ing/m4i_context.jsonld"
        cache_dir = UserDir['cache']
        UserDir.clear_cache(delta_days=0)
        self.assertEqual(len(list(cache_dir.glob('*'))), 0)
        ctx = download_context(url)
        self.assertEqual(ctx.vocab, "http://w3id.org/nfdi4ing/metadata4ing#")
        self.assertEqual(len(list(cache_dir.glob('*'))), 1)
        ctx = download_context(url)
        self.assertEqual(ctx.vocab, "http://w3id.org/nfdi4ing/metadata4ing#")

    def test_to_hdf_with_graph2(self):
        test_data = """{
  "@context": {
    "@import": "https://w3id.org/nfdi4ing/metadata4ing/m4i_context.jsonld",
    "foaf": "http://xmlns.com/foaf/0.1/",
    "prov": "http://www.w3.org/ns/prov#",
    "rdfs": "http://www.w3.org/2000/01/rdf-schema#",
    "schema": "http://schema.org/",
    "local": "http://example.org/"
  },
  "@graph": [
    {
      "@id": "local:preparation_0001",
      "@type": "processing step",
      "label": "Sample preparation and parameter definition",
      "has participant": "local:testperson1",
      "start time": "2022-09-22T10:31:22"
    },
    {
      "@id": "local:testperson1",
      "@type": "prov:Person",
      "foaf:firstName": "John",
      "foaf:lastName": "Doe",
      "age": 21,
      "schema:affiliation": {
        "@id": "Nef657ff40e464dd09580db3f32de2cf1",
        "@type": "schema:Organization",
        "rdfs:label": "MyAffiliation"
      }
    },
    {
      "@id": "local:testperson2",
      "@type": "prov:Person",
      "rdfs:label": "Jane Doe",
      "foaf:firstName": "Jane",
      "foaf:lastName": "Doe",
      "age": 20,
      "schema:affiliation": {
        "@type": "schema:Organization",
        "rdfs:label": "MyAffiliation"
      }
    }
  ]
}"""
        with open('graph.json', 'w') as f:
            f.write(test_data)
        jsondict = json.loads(test_data)
        assert isinstance(jsondict, dict)

        with h5tbx.File('graph.hdf', 'w') as h5:
            grp = h5.create_group('person')
            jsonld.to_hdf(grp=grp, source='graph.json')
            self.assertTrue('@graph' not in grp)
            self.assertTrue('Person' in grp)
            self.assertTrue('Jane Doe' in grp)
            self.assertEqual(grp['Jane Doe'].attrs['age'], 20)
            h5.dumps()
        # cleanup:
        pathlib.Path('graph.json').unlink(missing_ok=True)
        h5.hdf_filename.unlink(missing_ok=True)

    def test_to_hdf(self):
        test_data = """{"@context": {"foaf": "http://xmlns.com/foaf/0.1/", "prov": "http://www.w3.org/ns/prov#",
"rdfs": "http://www.w3.org/2000/01/rdf-schema#",
 "schema": "http://schema.org/",
 "local": "http://example.org/"},
"@id": "local:testperson",
"@type": "prov:Person",
"foaf:firstName": "John",
"foaf:lastName": "Doe",
"age": 21,
"schema:affiliation": {
    "@id": "Nef657ff40e464dd09580db3f32de2cf1",
    "@type": "schema:Organization",
    "rdfs:label": "MyAffiliation"
    }
}"""
        with open('test.json', 'w') as f:
            f.write(test_data)

        with h5tbx.File('test.hdf', 'w') as h5:
            jsonld.to_hdf(grp=h5.create_group('person'), source='test.json')
            self.assertTrue('person' in h5)
            self.assertTrue('firstName' in h5['person'].attrs)
            self.assertTrue('lastName' in h5['person'].attrs)
            self.assertEqual(h5['person'].attrs['firstName'], 'John')
            self.assertEqual(h5['person'].attrs['age'], 21)

        h5tbx.dumps('test.hdf')
        pathlib.Path('test.json').unlink(missing_ok=True)
        h5.hdf_filename.unlink(missing_ok=True)

    def test_codemeta_to_hdf(self):
        codemeta_filename = __this_dir__ / '../../codemeta.json'

        data = ontolutils.dquery(
            'schema:SoftwareSourceCode',
            codemeta_filename,
            context={'schema': 'http://schema.org/'})  # Note, that codemeta uses the unsecure http

        self.assertIsInstance(data, list)
        self.assertTrue(len(data) == 1)
        self.assertTrue(data[0]['version'] == __version__)
        self.assertTrue('author' in data[0])
        self.assertIsInstance(data[0]['author'], list)
        with h5tbx.File('test.hdf', 'w') as h5:
            jsonld.to_hdf(grp=h5.create_group('person'), data=data[0],
                          context={'@import': "https://doi.org/10.5063/schema/codemeta-2.0"})
            self.assertEqual(h5['person']['author1'].attrs[rdf.RDF_PREDICATE_ATTR_NAME]['SELF'],
                             'http://schema.org/author')

        h5tbx.dumps('test.hdf')

        h5.hdf_filename.unlink(missing_ok=True)
