"""Name identifier classes

A name identifier class controls the usage of the HDF5 attribute "standard_name".
The attribute "standard_name" is used in the HDF5 files for all name identifier classes although, for example,
CGNS uses "name" in its convention.
The attribute "standard_name" describes a dataset which can have any dataset name. Example: The dataset "u" (name "u")
has the attribute standard_name="x_velocity". In this case the CF-convention is used, thus, "x_velocity" can be looked-
up in the standard_name_table to get further information about the dataset. It is further linked to a specific units,
here "m/s", which is also checked if the user creates the dataset "u".
Examples for naming tables:
    - standard name table (http://cfconventions.org/Data/cf-standard-names/current/build/cf-standard-name-table.html)
    - CGNS data name convention (https://cgns.github.io/CGNS_docs_current/sids/dataname.html)
"""
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Tuple, Dict, Union

import pandas as pd
import yaml
from IPython.display import display, HTML
from pint.errors import UndefinedUnitError
from pint_xarray import unit_registry as ureg
from tabulate import tabulate

from .utils import is_valid_email_address, dict2xml
from ..errors import StandardizedNameError

from .._user import user_dirs

STRICT = True

CF_DATETIME_STR = '%Y-%m-%dT%H:%M:%SZ%z'


def test_units(_units):
    try:
        ureg.Unit(_units)
    except UndefinedUnitError as e:
        raise UndefinedUnitError(f'Units cannot be understood using pint_xarray package: {_units}. --> {e}')


def _units_power_fix(_str: str):
    """Fixes strings like 'm s-1' to 'm s^-1'"""
    s = re.search('[a-zA-Z][+|-]', _str)
    if s:
        return _str[0:s.span()[0] + 1] + '^' + _str[s.span()[1] - 1:]
    return _str


class StandardizedNameTableWarning(Warning):
    """StandardizedNameTableWarning"""
    pass


def equal_base_units(unit1, unit2):
    """Return if two units are equivalent"""
    base_unit1 = ureg(unit1).to_base_units().units.__format__(ureg.default_format)
    base_unit2 = ureg(unit2).to_base_units().units.__format__(ureg.default_format)
    return base_unit1 == base_unit2


@dataclass
class _NameIdentifierConvention:
    """Basic name identifier convention class
    needed for typing hint
    """
    pass


@dataclass
class StandardizedName:
    """basic stndardized name class"""
    name: str
    description: Union[str, None]
    canonical_units: Union[str, None]
    convention: _NameIdentifierConvention

    def __post_init__(self):
        if self.canonical_units:
            self.canonical_units = ureg.Unit(_units_power_fix(self.canonical_units))

    def __format__(self, spec):
        return self.name.__format__(spec)

    def __str__(self):
        return self.name

    def __eq__(self, other):
        if isinstance(other, str):
            return self.name == other
        else:
            return any([self.name != other.name,
                        self.description != other.description,
                        self.canonical_units != other.canonical_units,
                        self.convention != other.convention])

    def check(self):
        """Run the name check of the convention."""
        self.convention.check_name(self.name)


class _StandardizedNameTable:
    pass


class EmailError(ValueError):
    pass


def xmlconvention2dict(xml_filename: Path) -> Tuple[dict, dict]:
    """reads an xml convention xml file and returns data and meta dictionaries"""
    tree = ET.parse(xml_filename)
    root = tree.getroot()
    standard_names = {}
    meta = {'name': root.tag, 'version_number': int(root.find('version_number').text),
            'contact': root.find('contact').text,
            'institution': root.find('institution').text, 'last_modified': root.find('last_modified').text}
    for child in root.iter('entry'):
        standard_names[child.attrib['id']] = {}
        for c in child:
            standard_names[child.attrib['id']][c.tag] = c.text
    return standard_names, meta


def meta_from_xml(xml_filename):
    _dict, meta = xmlconvention2dict(xml_filename)
    meta.update(dict(table_dict=_dict))
    return meta


class StandardizedNameTable(_StandardizedNameTable):
    """Base class of Standardized Name Tables"""

    def __init__(self, name: str, table_dict: Union[Dict, None], version_number: int,
                 institution: str, contact: str,
                 last_modified: Union[str, None] = None,
                 valid_characters: str = '', pattern: str = '',
                 translation_dict: dict = None):
        self._name = name
        self._version_number = version_number
        self._valid_characters = valid_characters
        self._pattern = pattern
        self._institution = institution
        self.contact = contact
        self._xml_filename = None
        if last_modified is None:
            now = datetime.now()
            self._last_modified = now.strftime(CF_DATETIME_STR)
        else:
            self._last_modified = last_modified
        if table_dict is None:
            self._dict = {}
        elif isinstance(table_dict, dict):
            self._dict = table_dict
        else:
            raise TypeError(f'Unexpected input type: {type(table_dict)}. Expecting '
                            f'StandardizedNameTable or dict.')
        if not self.has_valid_structure():
            raise KeyError(f'Invalid dictionary structure. Each entry must contain "description" and '
                           '"canonical units"')

        if translation_dict:
            for k, v in translation_dict.items():
                if not isinstance(v, dict):
                    raise ValueError(f'Unexpected translation dictionary structure')
                for kk, vv in v.items():
                    if not isinstance(vv, str):
                        raise ValueError(f'Unexpected translation dictionary structure')
        else:
            translation_dict = dict()
        self._translation_dict = translation_dict

    @property
    def names(self):
        return list(self._dict.keys())

    @property
    def versionname(self):
        return f'{self._name}-v{self._version_number}'

    @property
    def contact(self):
        return self._contact

    @property
    def name(self):
        return self._name

    @property
    def valid_characters(self):
        return self._valid_characters

    @property
    def pattern(self):
        return self._pattern

    @property
    def laset_modified(self):
        return self._laset_modified

    @property
    def institution(self):
        return self._institution

    @property
    def version_number(self):
        return self._version_number

    @property
    def has_translation_dictionary(self):
        """Return whether the table is associated with a translation dict"""
        return len(self._translation_dict) > 0

    @contact.setter
    def contact(self, contact):
        if not is_valid_email_address(contact):
            raise EmailError(f'Invalid email address: {contact}')
        self._contact = contact

    def __repr__(self) -> str:
        if self._name is None:
            name = self.__class__.__name__
        else:
            name = self._name
        if self._version_number is None:
            version = 'None'
        else:
            version = self._version_number
        return f"{name} (version number: {version})"

    def __str__(self):
        return self.name

    def __getitem__(self, item) -> StandardizedName:
        if item in self._dict:
            return StandardizedName(item, self._dict[item]['description'], self._dict[item]['canonical_units'],
                                    convention=self)
        else:
            # return a standard name that is not in the table
            return StandardizedName(item, None, None, convention=self)

    def __contains__(self, item):
        return item in self._dict

    def __eq__(self, other):
        eq1 = self._dict == other._dict
        eq2 = self.versionname == other.versionname
        return eq1 and eq2

    def __neg__(self, other):
        return not self.__eq__(other)

    def compare_versionname(self, other):
        """Compare versionname"""
        return self.versionname == other.versionname

    def set(self, name: str, description: str, canonical_units: str):
        """Sets the value of a standardized name"""
        if name in self._dict:
            raise StandardizedNameError(f'name "{name}" already exists in table. Use modify() '
                                        f'to change the content')
        test_units(canonical_units)
        self._dict[name] = dict(description=description, canonical_units=canonical_units)

    def modify(self, name: str, description: str, canonical_units: str):
        """modifies a standard name or creates one if non-existing"""
        if name not in self._dict:
            if not description or not canonical_units:
                raise ValueError(f'Name {name} does not exist yet. You must provide string values '
                                 f'for both description and canoncical_units')
            self._dict[name] = dict(description=description, canonical_units=canonical_units)
        else:
            if description:
                self._dict[name]['description'] = description
            if canonical_units:
                self._dict[name]['canonical_units'] = canonical_units

    def get_table(self, sort_by: str = 'name', maxcolwidths=None) -> str:
        """string representation of the convention in form of a table"""
        if self._name is None:
            name = self.__class__.__name__
        else:
            name = self._name
        if self._version_number:
            version = self._version_number
        else:
            version = 'None'
        df = pd.DataFrame(self._dict).T
        if sort_by.lower() in ('name', 'names', 'standard_name', 'standard_names'):
            sorted_df = df.sort_index()
        elif sort_by.lower() in ('units', 'unit', 'canoncial_units'):
            sorted_df = df.sort_values('canonical_units')
        else:
            sorted_df = df
        _table = tabulate(sorted_df, headers='keys', tablefmt='psql', maxcolwidths=maxcolwidths)
        return f"{name} (version: {version})\n{_table}"

    def sdump(self, sort_by: str = 'name', maxcolwidths=None) -> None:
        """Dumps (prints) the content as string"""
        print(self.get_table(sort_by=sort_by, maxcolwidths=maxcolwidths))

    def dump(self, sort_by: str = 'name', **kwargs):
        """pretty representation of the table for jupyter notebooks"""
        df = pd.DataFrame(self._dict).T
        if sort_by.lower() in ('name', 'names', 'standard_name', 'standard_names'):
            display(HTML(df.sort_index().to_html(**kwargs)))
        elif sort_by.lower() in ('units', 'unit', 'canoncial_units'):
            display(HTML(df.sort_values('canonical_units').to_html(**kwargs)))
        else:
            raise ValueError(f'Invalid value for sortby: {sort_by}')

    def has_valid_structure(self) -> bool:
        """verifies the structure of the standard name dictionary"""
        if self._dict:
            for v in self._dict.values():
                if isinstance(v, str):
                    return False
                if 'description' not in v.keys() and 'canonical_units' not in v.keys():
                    return False
        return True

    def copy(self):
        """Return a copy of the object"""
        return StandardizedNameTable(self._dict)

    def update(self, data: Union[Dict, _StandardizedNameTable]):
        if isinstance(data, StandardizedNameTable):
            self._dict.update(data)
        elif isinstance(data, dict):
            self._dict.update(data)

    @staticmethod
    def from_xml(xml_filename) -> "StandardizedNameTable":
        """read from xml file"""
        meta = meta_from_xml(xml_filename)
        snt = StandardizedNameTable(**meta)
        snt._xml_filename = xml_filename
        return snt

    @staticmethod
    def from_yaml(yml_filename) -> "StandardizedNameTable":
        """alias method of from_yml"""
        return StandardizedNameTable.from_yml(yml_filename)

    @staticmethod
    def from_yml(yml_filename) -> "StandardizedNameTable":
        """read from yaml file"""
        import yaml
        with open(yml_filename, 'r') as f:
            ymldict = yaml.safe_load(f)
        return StandardizedNameTable(**ymldict)

    @staticmethod
    def from_web(url: str, known_hash: str = None,
                 valid_characters: str = '[^a-zA-Z0-9_]',
                 pattern: str = '^[0-9 ].*'):
        """Init from an online resource. Provide a hash is recommended. For more info
        see documentation of pooch.retrieve()"""
        try:
            import pooch
        except ImportError:
            raise ImportError(f'Package "pooch" is needed to download the file cf-standard-name-table.xml')
        file_path = pooch.retrieve(
            url=url,
            known_hash=known_hash,
        )
        snt = StandardizedNameTable.from_xml(file_path)
        snt._valid_characters = valid_characters
        snt._pattern = pattern
        return snt

    @staticmethod
    def from_versionname(version_name: str):
        """reads the table from an xml file stored in this package"""
        # xml_filename = Path(__file__).parent / 'snxml' / f'{version_name}.xml'
        # if not xml_filename.exists():
        #     raise FileExistsError(f'Cannot find convention filename "{xml_filename}')
        # meta = meta_from_xml(xml_filename)
        # meta.update({'version_number': int(version_name.split('-v')[1])})
        # translation_xml = xml_filename.parent / 'translation' / xml_filename.name
        # if translation_xml.exists():
        #     translation_dict = xmlconvention2dict(translation_xml)[0]
        #     meta.update(dict(translation_dict=translation_dict))
        return StandardizedNameTable.from_name_and_version(*version_name.split('-v'))

    @staticmethod
    def from_name_and_version(name: str, version_number: int):
        """reads the table from an xml file stored in this package"""
        xml_filename = Path(__file__).parent / 'snxml' / f'{name}-v{version_number}.xml'
        if not xml_filename.exists():
            raise FileExistsError(f'Cannot find convention filename "{xml_filename}')
        meta = meta_from_xml(xml_filename)
        translation_xml = xml_filename.parent / 'translation' / xml_filename.name
        if translation_xml.exists():
            translation_dict = xmlconvention2dict(translation_xml)[0]
            meta.update(dict(translation_dict=translation_dict))
        return StandardizedNameTable(**meta)

    def to_xml(self, xml_filename: Path, datetime_str=None, parents=True) -> Path:
        """Save the convention in a XML file"""
        if not xml_filename.parent.exists() and parents:
            xml_filename.parent.mkdir(parents=parents)
        if datetime_str is None:
            datetime_str = '%Y-%m-%d_%H:%M:%S'
        last_modified = datetime.now().strftime(datetime_str)

        xml_parent = xml_filename.parent
        xml_name = xml_filename.name
        xml_translation_filename = xml_parent / 'translation' / xml_name
        if not xml_translation_filename.parent.exists():
            xml_translation_filename.parent.mkdir(parents=True)
        dict2xml(filename=xml_translation_filename,
                 name='tanslation',
                 dictionary=self._translation_dict,
                 metadata=dict(version_number=self.version_number,
                               contact=self.contact,
                               institution=self.institution,
                               last_modified=last_modified)
                 )
        return dict2xml(filename=xml_filename,
                        name=self.name,
                        dictionary=self._dict,
                        metadata=dict(version_number=self.version_number,
                                      contact=self.contact,
                                      institution=self.institution,
                                      last_modified=last_modified)
                        )

    def to_yml(self, *args, **kwargs) -> Path:
        """alias of to_yaml()"""
        return self.to_yaml(*args, **kwargs)

    def to_yaml(self, yml_filename: Path, datetime_str=None, parents=True) -> Path:
        """Save the convention in a XML file"""
        yml_filename = Path(yml_filename)
        if not yml_filename.parent.exists() and parents:
            yml_filename.parent.mkdir(parents=parents)
        if datetime_str is None:
            datetime_str = '%Y-%m-%d_%H:%M:%S'
        last_modified = datetime.now().strftime(datetime_str)
        with open(yml_filename, 'w') as f:
            yaml.dump({'name': self.name}, f)
            yaml.dump({'version_number': self.version_number}, f)
            yaml.dump({'institution': self.institution}, f)
            yaml.dump({'contact': self.contact}, f)
            yaml.dump({'valid_characters': self.valid_characters}, f)
            yaml.dump({'pattern': self.pattern}, f)
            yaml.dump({'last_modified': last_modified}, f)
            yaml.dump({'table_dict': self._dict}, f)
            yaml.dump({'translation_dict': self._translation_dict}, f)
        return yml_filename

    def check_name(self, name, strict=False) -> bool:
        """Verifies general requirements like lower-case writing and no
        invalid character exist in the name.
        If strict is True, it is further checked whether the name exists
        in the standard name table. This is a global setting which can be changed
        in `conventions.identifier.STRICT`"""

        if not len(name) > 0:
            raise StandardizedNameError(f'Name too short!')

        if name[0] == ' ':
            raise StandardizedNameError(f'Name must not start with a space!')

        if name[-1] == ' ':
            raise StandardizedNameError(f'Name must not end with a space!')

        if re.sub(self.valid_characters, '', name) != name:
            raise StandardizedNameError(f'Invalid special characters in name "{name}": Only "_" is allowed.')

        if self.pattern != '' and self.pattern is not None:
            if re.match(self.pattern, name):
                raise StandardizedNameError(f'Name must not start with a number!')

        if strict:
            if self._dict:
                if name not in self._dict:
                    raise StandardizedNameError(f'Standardized name "{name}" not in '
                                                'name table')
        return True

    def check_units(self, name, units) -> bool:
        """Raises an error if units is wrong. """
        self.check_name(name, strict=True)  # will raise an error if name not in self._dict
        if name in self._dict:
            if not equal_base_units(_units_power_fix(self._dict[name]['canonical_units']), units):
                raise StandardizedNameError(f'Unit of standard name "{name}" not as expected: '
                                            f'"{units}" != "{self[name].canonical_units}"')
        return True

    def translate(self, name: str, source: str) -> Union[str, None]:
        """If convention/xml file comes with translation entries, this method converts
        the input name into the convention's standardized name

        Parameters
        ----------
        name: str
            Name to be translated
        source:
            (sub) dictionary entry to use for translation. Per Standard Name Table
            there can be multiple translation dictionaries e.g. for different software.
        """
        if self._translation_dict:
            if source in self._translation_dict:
                if name in self._translation_dict[source]:
                    return self._translation_dict[source][name]
                return None
            else:
                AttributeError(f'No such translation dictionary: {source}')
        raise ValueError(f'Translation dictionary is empty!')

    def register(self):
        """Register the standard name table"""
        raise NotImplementedError

    @staticmethod
    def list_registered():
        """Return sorted list of standard names files"""
        return sorted(user_dirs['standard_names'].glob('*'))


Empty_Standard_Name_Table = StandardizedNameTable(name='EmptyStandardizedNameTable',
                                                  table_dict={},
                                                  version_number=0,
                                                  institution=None,
                                                  contact='none@none.none',
                                                  last_modified=None,
                                                  valid_characters='')


class CFStandardNameTable(StandardizedNameTable):
    """CF Standard Name Table"""

    def __init__(self, table_dict: Union[Dict, None], version_number: int,
                 institution: str, contact: str,
                 last_modified: Union[str, None] = None,
                 valid_characters: str = '[^a-zA-Z0-9_]',
                 pattern: str = '^[0-9 ].*'):
        name = 'CF-convention'
        super().__init__(name, table_dict, version_number, institution,
                         contact, last_modified, valid_characters, pattern)

    def check_name(self, name, strict=False) -> bool:
        """In addtion to check of base class, lowercase is checked first"""
        if not name.islower():
            raise StandardizedNameError(f'Standard name must be lowercase!')
        return super().check_name(name, strict)


class CGNSStandardNameTable(StandardizedNameTable):
    """CGNS Standard Name Table"""

    def __init__(self, table_dict: Union[Dict, None], version_number: int,
                 institution: str, contact: str,
                 last_modified: Union[str, None] = None,
                 valid_characters: str = '[^a-zA-Z0-9_]',
                 pattern: str = '^[0-9 ].*'):
        name = 'CGNS-convention'
        super().__init__(name, table_dict, version_number, institution,
                         contact, last_modified, valid_characters, pattern)


xml_dir = Path(__file__).parent / 'snxml'


def standard_name_table_to_xml(snt: StandardizedNameTable, overwrite=False):
    """writes standrad name table to package data"""
    _xml_filename = xml_dir / f'{snt.name}-v{snt.version_number}.xml'
    if overwrite:
        return snt.to_xml(_xml_filename)
    if not _xml_filename.exists():
        snt.to_xml(_xml_filename)


standard_name_table_to_xml(Empty_Standard_Name_Table)
