import h5py
import pandas as pd
import pathlib
import pint
import re
import requests
import warnings
import yaml
from IPython.display import display, HTML
from datetime import datetime, timezone
from typing import Callable, Dict, Union, List, Tuple

from h5rdmtoolbox import get_ureg
from . import StandardAttributeValidator
from .. import errors
from ..utils import dict2xml, get_similar_names_ratio
from ..._logger import logger
from ...._user import UserDir
from ....utils import generate_temporary_filename

__this_dir__ = pathlib.Path(__file__).parent

VERSION_PATTERN = r'^v\d+(\.\d+)?(a|b|rc|dev)?$'
README_HEADER = """---
title: Standard Name Table for Fan simulations and measurements
---

# Standard Name Table for Fan simulations and measurements

| Standard Name |     units     | Description |
|---------------|:-------------:|:------------|
"""

LATEX_UNDERSCORE = '\\_'

VALID_CHARACTERS = '[^a-zA-Z0-9_]'
PATTERN = '^[0-9 ].*'


def _units_power_fix(_str: str):
    """Fixes strings like 'm s-1' to 'm s^-1'"""
    s = re.search('[a-zA-Z][+|-]', _str)
    if s:
        return _str[0:s.span()[0] + 1] + '^' + _str[s.span()[1] - 1:]
    return _str


class StandardName:
    """Standard Name class"""

    def __init__(self, name: str,
                 units: Union[str, pint.Unit] = None,
                 description: str = None,
                 canonical_units: str = None,
                 alias: str = None):
        StandardName.check_syntax(name)
        self.name = name
        if canonical_units is not None:
            warnings.warn('Parameter "canonical_units" is depreciated. Use "units" instead.', DeprecationWarning)
            units = canonical_units
        if description is None:
            # TODO if canonical_units is removed, then default value None must be removed for description, too
            raise ValueError('A description must be provided')
        if isinstance(units, str):
            self.units = get_ureg().Unit(_units_power_fix(units))
        elif isinstance(units, pint.Unit):
            self.units = units
        else:
            raise TypeError(f"units must be a str or a pint.Unit, not {type(units)}")
        # convert units to base units:
        q = 1 * self.units
        self.unit = q.to_base_units().units
        self.description = description
        if alias is not None:
            self.check_syntax(alias)
        self.alias = alias

    def __str__(self):
        return self.name

    def __repr__(self):
        return f'<StandardName: "{self.name}" units="{self.units}", description="{self.description}">'

    def equal_unit(self, other_unit: pint):
        """compares the base units of this standard name with another unit provided as a string
        or pint.Unit"""
        from ..utils import equal_base_units
        return equal_base_units(self.units, other_unit)

    @staticmethod
    def check_syntax(standard_name: str):
        """formal check of the syntax"""
        if not isinstance(standard_name, str):
            raise TypeError(f'Standard name must be type string but is {type(standard_name)}')
        if len(standard_name) == 0:
            raise errors.StandardNameError('Name too short!')
        if re.sub(VALID_CHARACTERS, '', standard_name) != standard_name:
            raise errors.StandardNameError('Invalid special characters in name '
                                           f'"{standard_name}": Only "{VALID_CHARACTERS}" '
                                           'is allowed.')

        if PATTERN != '' and PATTERN is not None:
            if re.match(PATTERN, standard_name):
                raise errors.StandardNameError(f'Standard name "{standard_name}" does not match pattern "{PATTERN}"')

    def to_dict(self) -> Dict:
        """Return dictionary representation of StandardName"""
        return dict(name=self.name, units=self.units, description=self.description)


# wrapper that updates datetime in meta
def update_modification_date(func):
    def wrapper(self, *args, **kwargs):
        self._meta['last_modified'] = datetime.now(timezone.utc).isoformat()
        # self._meta['last_modified'] = datetime.now().isoformat()
        return func(self, *args, **kwargs)

    return wrapper


class StandardNameTable:
    """Standard Name Table class

    Examples
    --------
    >>> from h5rdmtoolbox.conventions.standard_attributes import StandardNameTable
    >>> table = StandardNameTable.from_yaml('standard_name_table.yaml')
    >>> # check a standard name
    >>> table.check('x_velocity')
    True
    >>> # check a transformed standard name
    >>> table.check('derivative_of_x_velocity_wrt_to_x_coordinate')
    True
    """
    __slots__ = ('table', '_meta', '_alias', '_name', '_version',
                 'devices', 'locations', 'transformations')

    def __init__(self,
                 name: str,
                 version: str,
                 table: Dict,
                 alias: Dict = None,
                 devices: List[str] = None,
                 locations: List[str] = None,
                 **meta):
        if table is None:
            table = {}
        self.table = table
        self._name = name
        if devices is None:
            devices = []
        self.devices = devices
        if locations is None:
            locations = []
        self.locations = locations
        if version is None and meta.get('version_number', None) is not None:
            version = f'v{meta["version_number"]}'
        meta['version'] = StandardNameTable.validate_version(version)
        # fix key canonical_units
        for k, v in self.table.items():
            if 'canonical_units' in v:
                v['units'] = v['canonical_units']
                del v['canonical_units']
        self._meta = meta
        self.transformations = (derivative_of_X_wrt_to_Y,
                                magnitude_of,
                                square_of,
                                product_of_X_and_Y,
                                ratio_of_X_and_Y,
                                difference_of_X_across_device,
                                difference_of_X_and_y_across_device)
        if alias is None:
            self._alias = {}
        else:
            self._alias = alias

    def __repr__(self):
        _meta = self.meta.pop('alias', None)
        meta_str = ', '.join([f'{key}: {value}' for key, value in self.meta.items()])
        return f'<StandardNameTable: ({meta_str})>'

    def __contains__(self, standard_name):
        return standard_name in self.table

    def __getitem__(self, standard_name: str) -> StandardName:
        """Return table entry"""
        if standard_name in self.table:
            entry = self.table[standard_name]
            if 'canonical_units' in entry:
                units = entry['canonical_units']
                import warnings
                warnings.warn(f'canonical_units is deprecated. Use units instead.',
                              DeprecationWarning)
            else:
                units = entry['units']
            return StandardName(name=standard_name,
                                units=units,
                                description=entry['description'],
                                alias=entry.get('alias', None))
        for transformation in self.transformations:
            sn = transformation(standard_name, self)
            if sn:
                return sn

        if standard_name in self.list_of_aliases:
            return self[self.aliases[standard_name]]

        # provide a suggestion for similar standard names
        similar_names = [k for k in [*self.table.keys(), *self.list_of_aliases] if
                         get_similar_names_ratio(standard_name, k) > 0.75]
        if similar_names:
            raise errors.StandardNameError(f'{standard_name} not found in Standard Name Table "{self.name}".'
                                           ' Did you mean one of these: '
                                           f'{similar_names}?')
        raise errors.StandardNameError(f'{standard_name} not found in Standard Name Table "{self.name}".')

    def __getattr__(self, item):
        if item in self.meta:
            return self.meta[item]
        return self.__getattribute__(item)

    @staticmethod
    def validate_version(version_string: str) -> str:
        """Validate version number. Must be MAJOR.MINOR(a|b|rc|dev). If validated, return version string, else
        raise ValueError."""
        if version_string is None:
            version_string = '0.0'
            warnings.warn(f'Version number is not set. Setting version number to {version_string}.')
        version_string = str(version_string)
        if not re.match(VERSION_PATTERN, version_string):
            raise ValueError(f'Version number "{version_string}" is not valid. Expecting MAJOR.MINOR(a|b|rc|dev).')
        return version_string

    @property
    def aliases(self) -> Dict:
        """returns a dictionary of alias names and the respective standard name"""
        return {v['alias']: k for k, v in self.table.items() if 'alias' in v}

    @property
    def list_of_aliases(self) -> Tuple[str]:
        """Returns list of available aliases"""
        return tuple([v['alias'] for v in self.table.values() if 'alias' in v])

    @property
    def alias(self) -> Dict:
        """Return alias dictionary"""
        return self._alias

    @property
    def name(self) -> str:
        """Return name of the Standard Name Table"""
        return self._name

    @property
    def meta(self) -> Dict:
        """Return meta data dictionary"""
        return self._meta

    @property
    def version(self) -> str:
        """Return version number of the Standard Name Table"""
        return self._meta.get('version', None)

    @property
    def versionname(self) -> str:
        """Return version name which is constructed like this: <name>-<version>"""
        return f'{self.name}-{self.version}'

    def update(self, **standard_names):
        """Update the table with new standard names"""
        for k, v in standard_names.items():
            self.set(k, **v)

    def check_name(self, standard_name: str) -> bool:
        """check the standard name against the table. If the name is not
        exactly in the table, check if it is a transformed standard name."""
        if standard_name in self.table:
            return True
        for transformation in self.transformations:
            if transformation(standard_name, self):
                return True
        return False

    def check(self, standard_name: str, units: Union[pint.Unit, str] = None) -> bool:
        """check the standard name against the table. If the name is not
        exactly in the table, check if it is a transformed standard name.
        If `units` is provided, check if the units are equal to the units"""
        valid_sn = self.check_name(standard_name)
        if not valid_sn:
            return False
        if units is None:
            return True
        return self[standard_name].equal_unit(units)

    def check_hdf_group(self, h5grp: h5py.Group, recursive: bool = True, raise_error: bool = True):
        """Check group datasets. Run recursively if requested.
        If raise_error is True, raise an error if a dataset has an invalid standard_name.
        If raise_error is False, log a warning if a dataset has an invalid standard_name.
        """

        valid_group = True

        def _check_ds(name, node):
            if isinstance(node, h5py.Dataset):
                if 'standard_name' in node.attrs:
                    units = node.attrs.get('units', '')

                    valid = self.check(node.attrs['standard_name'], units=units)
                    if not valid:
                        valid_group = False
                        if raise_error:
                            raise errors.StandardNameError(f'Dataset "{name}" has invalid standard_name '
                                                           f'"{node.attrs["standard_name"]}"')
                        else:
                            logger.error(f'Dataset "{name}" has invalid standard_name '
                                         f'"{node.attrs["standard_name"]}"')
                    # units = node.attrs['units']
                    # if units is None:
                    #     logger.warning(f'Dataset %s has not attribute %s! Assuming it is dimensionless', name,
                    #                    'units')
                    #     units = ''
                    # try:
                    #     self.check_units(node.attrs['standard_name'], units=units)
                    # except errors.StandardNameError as e:
                    #     if raise_error:
                    #         raise errors.StandardNameError(e)
                    #     else:
                    #         logger.error(' > ds: %s: %s', node.name, e)

        if recursive:
            h5grp.visititems(_check_ds)
        else:
            _check_ds(None, h5grp)

        return valid_group

    def check_hdf_file(self, filename,
                       recursive: bool = True,
                       raise_error: bool = True):
        """Check file for standard names"""
        with h5py.File(filename) as h5:
            self.check_hdf_group(h5['/'],
                                 recursive=recursive,
                                 raise_error=raise_error)

    def set(self, *args, **kwargs):
        """Set standard names in the table

        Examples
        --------
        >>> from h5rdmtoolbox.conventions.standard_attributes import StandardNameTable, StandardName
        >>> table = StandardNameTable.from_yaml('standard_name_table.yaml')
        >>> table.set('x_velocity', 'm s-1', 'x component of velocity')
        >>> # or
        >>> sn = StandardName('velocity', 'm s-1', 'velocity')
        >>> table.set(sn)
        """
        n_args = len(args)
        n_kwargs = len(kwargs)

        if n_args == 1 and n_kwargs == 0:
            sn = args[0]
            if not isinstance(sn, StandardName):
                raise TypeError(f'Expected a StandardName, got {type(sn)}')
        elif n_args + n_kwargs != 3:
            raise ValueError('Invalid arguments. Either a StandardName object or name, units and description '
                             'must be provided')
        else:
            _data = dict(name=None, units=None, description=None)
            for k, v in zip(_data.keys(), args):
                _data[k] = v
            _data.update(kwargs)
            sn = StandardName(**_data)
        self.table.update({sn.name: {'units': str(sn.units), 'description': sn.description}})
        return self

    def sort(self) -> "StandardNameTable":
        """Sorts the standard name table"""
        _tmp_yaml_filename = generate_temporary_filename(suffix='.yaml')
        self.to_yaml(_tmp_yaml_filename)
        return StandardNameTable.from_yaml(_tmp_yaml_filename)

    # Loader: ---------------------------------------------------------------
    @staticmethod
    def from_yaml(yaml_filename):
        """Initialize a StandardNameTable from a YAML file"""
        with open(yaml_filename, 'r') as f:
            _dict = {}
            for d in yaml.full_load_all(f):
                _dict.update(d)
            table = _dict.pop('table')
            if 'name' not in _dict:
                _dict['name'] = pathlib.Path(yaml_filename).stem
            version = _dict.pop('version', None)
            name = _dict.pop('name', None)
            return StandardNameTable(name=name, version=version, table=table, **_dict)

    @staticmethod
    def from_xml(xml_filename: Union[str, pathlib.Path],
                 name: str = None) -> "StandardNameTable":
        """Create a StandardNameTable from an xml file

        Parameters
        ----------
        xml_filename : str
            Filename of the xml file
        name : str, optional
            Name of the StandardNameTable, by default None. If None, the name of the xml file is used.

        Returns
        -------
        snt: StandardNameTable
            The StandardNameTable object

        Raises
        ------
        FileNotFoundError
            If the xml file does not exist
        """

        try:
            import xmltodict
        except ImportError:
            raise ImportError('Package "xmltodict" is missing, but required to import from XML files.')
        with open(str(xml_filename), 'r', encoding='utf-8') as file:
            my_xml = file.read()
        xmldict = xmltodict.parse(my_xml)
        _name = list(xmldict.keys())[0]
        if name is None:
            name = _name

        data = xmldict[_name]

        meta = {'name': name}
        for k in data.keys():
            if k not in ('entry', 'alias') and k[0] != '@':
                meta[k] = data[k]

        table = {}
        for entry in data['entry']:
            table[entry.pop('@id')] = entry

        _alias = data.get('alias', {})
        alias = {}
        if _alias:
            for aliasentry in _alias:
                k, v = list(aliasentry.values())
                alias[k] = v

        if 'version' not in meta:
            meta['version'] = f"v{meta.get('version_number', None)}"
        snt = StandardNameTable(table=table,
                                alias=alias,
                                **meta
                                )
        return snt

    @staticmethod
    def from_web(url: str, known_hash: str = None,
                 name: str = None,
                 **meta):
        """Create a StandardNameTable from an online resource.
        Provide a hash is recommended.

        Parameters
        ----------
        url : str
            URL of the file to download.

            .. note::

                You may read a table stored as a yaml file from a github repository by using the following url:
                https://raw.githubusercontent.com/<username>/<repository>/<branch>/<filepath>

        known_hash : str, optional
            Hash of the file, by default None
        name : str, optional
            Name of the StandardNameTable, by default None. If None, the name of the xml file is used.
        valid_characters : str, optional
            Regular expression for valid characters. If None, the default value from the config file is used.
        pattern : str, optional
            Regular expression for valid standard names. If None, the default value from the config file is used.

        Returns
        -------
        snt: StandardNameTable
            The StandardNameTable object

        Notes
        -----
        This method requires the package pooch to be installed.

        .. seealso::

            For more info see documentation of `pooch.retrieve()`

        """
        try:
            import pooch
        except ImportError:
            raise ImportError('Package "pooch" is needed to download the file cf-standard-name-table.xml')
        file_path = pooch.retrieve(
            url=url,
            known_hash=known_hash,
        )
        file_path = pathlib.Path(file_path)
        if file_path.suffix == '.xml':
            snt = StandardNameTable.from_xml(file_path, name)
        elif file_path.suffix in ('.yml', '.yaml'):
            snt = StandardNameTable.from_yaml(file_path)
        else:
            raise ValueError(f'Unexpected file suffix: {file_path.suffix}. Expected .xml, .yml or .yaml')
        meta['url'] = url
        snt.meta.update(meta)
        return snt

    @staticmethod
    def from_gitlab(url: str,
                    project_id: int,
                    ref_name: str,
                    file_path: Union[str, pathlib.Path],
                    private_token: str = None) -> "StandardNameTable":
        """
        Download a file from a gitlab repository and provide StandardNameTable based on this.

        Parameters
        ----------
        url: str
            gitlab url, e.g. https://gitlab.com
        project_id: str
            ID of gitlab project
        ref_name: str
            Name of branch or tag
        file_path: Union[str, pathlib.Path
            Path to file in gitlab project
        private_token: str
            Token if porject is not public

        Returns
        -------
        StandardNameTable

        Examples
        --------
        >>> StandardNameTable.from_gitlab(url='https://git.scc.kit.edu',
        >>>                               file_path='open_centrifugal_fan_database-v1.yaml',
        >>>                               project_id='35443',
        >>>                               ref_name='main')


        Notes
        -----
        This method requires the package python-gitlab to be installed.

        Equivalent curl statement:
        curl <url>/api/v4/projects/<project-id>/repository/files/<file-path>/raw?ref\=<ref_name> -o <output-filename>
        """
        try:
            import gitlab
        except ImportError:
            raise ImportError('python-gitlab not installed')
        gl = gitlab.Gitlab(url, private_token=private_token)
        pl = gl.projects.get(id=project_id)

        tmpfilename = generate_temporary_filename(suffix=f".{file_path.rsplit('.', 1)[1]}")
        with open(tmpfilename, 'wb') as f:
            pl.files.raw(file_path=file_path, ref=ref_name, streamed=True, action=f.write)

        if file_path.endswith('.yaml') or file_path.endswith('.yml'):
            snt = StandardNameTable.from_yaml(tmpfilename)
        elif file_path.endswith('.xml'):
            snt = StandardNameTable.from_xml(tmpfilename)
        else:
            raise NotImplementedError(f'Cannot handle file name extension {file_path.rsplit(".", 1)[1]}. '
                                      'Expected yml/yaml or xml')
        snt.meta['url'] = url
        snt.meta['gitlab_src_info'] = dict(url=url, project_id=project_id, ref_name=ref_name, file_path=file_path)
        return snt

    @staticmethod
    def from_zenodo(doi: str,
                    filename: str = None) -> "StandardNameTable":
        """Download standard name table from Zenodo based on URL

        Parameters
        ----------
        doi: str
            DOI
        filename: str
            If multiple files exist in the Zenodo repository, you must specify the exact name

        Returns
        -------
        snt: StandardNameTable
            Instance of this class


        Example
        -------
        >>> StandardNameTable.from_zenodo(doi="8158764")

        Notes
        -----
        Zenodo API: https://vlp-new.ur.de/developers/#using-access-tokens
        """
        if doi.startswith('https://zenodo.org/record/'):
            doi = doi.split('/')[-1]

        destination_filename = UserDir['standard_name_tables'] / f'{doi}.yaml'
        if destination_filename.exists():
            return StandardNameTable.from_yaml(destination_filename)

        base_url = "https://zenodo.org/api"
        record_url = f"{base_url}/records/{doi}"

        # Get the record metadata
        response = requests.get(record_url)
        if response.status_code != 200:
            raise ValueError(f"Unable to retrieve record metadata. Status code: {response.status_code}")

        record_data = response.json()

        # Find the file link
        if 'files' not in record_data:
            raise ValueError("Error: No files found in the record.")

        files = record_data['files']
        if len(files) > 1 and filename is None:
            raise ValueError('More than one file found. Specify the filename. '
                             f'Must be one of these: {[f["key"] for f in files]}')
        if filename is not None:
            for f in files:
                if f['key'] == filename:
                    file_data = f
                    break
        else:
            file_data = files[0]  # Assuming you want the first file

        if 'links' not in file_data or 'self' not in file_data['links']:
            raise ValueError("Unable to find download link for the file.")

        download_link = file_data['links']['self']

        # Download the file
        response = requests.get(download_link, stream=True)
        if response.status_code != 200:
            raise ValueError(f"Unable to download the file. Status code: {response.status_code}")

        with open(destination_filename, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)

        snt = StandardNameTable.from_yaml(destination_filename)
        snt._meta.update(dict(zenodo_doi=doi))

        return snt

    @staticmethod
    def load_registered(name: str) -> 'StandardNameTable':
        """Load from user data dir"""
        # search for names:
        candidates = list(UserDir['standard_name_tables'].glob(f'{name}.yml'))
        if len(candidates) == 1:
            return StandardNameTable.from_yaml(candidates[0])
        if len(candidates) == 0:
            raise FileNotFoundError(f'No file found under the name {name} at this location: '
                                    f'{UserDir["standard_name_tables"]}')
        list_of_reg_names = [snt.versionname for snt in StandardNameTable.get_registered()]
        raise FileNotFoundError(f'File {name} could not be found or passed name was not unique. '
                                f'Registered tables are: {list_of_reg_names}')

    # End Loader: -----------------------------------------------------------

    # Export: ---------------------------------------------------------------
    @update_modification_date
    def to_yaml(self, yaml_filename: Union[str, pathlib.Path]):
        """Export a StandardNameTable to a YAML file"""
        snt_dict = self.to_dict()

        with open(yaml_filename, 'w') as f:
            meta_lines = '\n'.join(f'{k}: {v}' for k, v in self.meta.items())
            f.writelines(meta_lines + '\n')

            yaml.safe_dump({'table': snt_dict['table']}, f)

    @update_modification_date
    def to_xml(self,
               xml_filename: pathlib.Path,
               datetime_str: Union[str, None] = None) -> pathlib.Path:
        """Save the SNT in a XML file

        Parameters
        ----------
        xml_filename: pathlib.Path
            Path to use for the XML file
        datetime_str: str, optional
            Datetime format to use for the last_modified field. If None, then
            ISO 6801 format is used.

        Returns
        -------
        pathlib.Path
            Path to the XML file
        """
        if datetime_str is None:
            last_modified = datetime.now(datetime.timezone.utc).isoformat()
        else:
            last_modified = datetime.now().strftime(datetime_str)

        xml_parent = xml_filename.parent
        xml_name = xml_filename.name
        xml_translation_filename = xml_parent / 'translation' / xml_name
        if not xml_translation_filename.parent.exists():
            xml_translation_filename.parent.mkdir(parents=True)

        meta = self.meta
        meta.update(last_modified=last_modified)

        meta.update(dict(version=self.version))

        return dict2xml(filename=xml_filename,
                        name=self.name,
                        dictionary=self.table,
                        **meta)

    def register(self, overwrite: bool = False) -> None:
        """Register the standard name table under its versionname."""
        trg = UserDir['standard_name_tables'] / f'{self.versionname}.yml'
        if trg.exists() and not overwrite:
            raise FileExistsError(f'Standard name table {self.versionname} already exists!')
        self.to_yaml(trg)

    def to_markdown(self, markdown_filename):
        markdown_filename = pathlib.Path(markdown_filename)
        with open(markdown_filename, 'w') as f:
            f.write(README_HEADER)
            for k, v in self.sort().table.items():
                f.write(f'| {k} | {v["units"]} | {v["description"]} |\n')
        return markdown_filename

    def to_html(self, html_filename, open_webbrwoser: bool = False):

        html_filename = pathlib.Path(html_filename)

        markdown_filename = self.to_markdown(generate_temporary_filename(suffix='.md'))

        # Read the Markdown file
        markdown_filename = pathlib.Path(markdown_filename)

        template_filename = __this_dir__ / 'html' / 'template.html'

        import subprocess
        # Convert Markdown to HTML using pandoc
        subprocess.call(['pandoc', str(markdown_filename.absolute()),
                         '--template',
                         str(template_filename),
                         '-o', str(html_filename.absolute())])

        if open_webbrwoser:
            import webbrowser
            webbrowser.open('file://' + str(html_filename.resolve()))
        return html_filename

    def to_latex(self, latex_filename,
                 column_parameter: str = 'p{0.4\\textwidth}lp{.40\\textwidth}',
                 caption: str = 'Standard Name Table',
                 with_header_and_footer: bool = True):
        """Export a StandardNameTable to a LaTeX file"""
        latex_filename = pathlib.Path(latex_filename)
        LATEX_HEADER = f"""\\begin{{table}}[htbp]
\\centering
\\caption{caption}
\\begin{{tabular}}{column_parameter}
"""
        LATEX_FOOTER = """\\end{tabular}"""
        with open(latex_filename, 'w') as f:
            if with_header_and_footer:
                f.write(LATEX_HEADER)
            for k, v in self.sort().table.items():
                desc = v["description"]
                desc[0].upper()
                f.write(
                    f'{k.replace("_", LATEX_UNDERSCORE)} & {v["units"]} & {desc.replace("_", LATEX_UNDERSCORE)} \\\\\n')
            if with_header_and_footer:
                f.write(LATEX_FOOTER)
        return latex_filename

    # End Export ---------------------------------------------------------------

    def to_dict(self):
        """Export a StandardNameTable to a dictionary"""
        d = dict(name=self.name, **self.meta, devices=self.devices, table=self.table)
        d.update(dict(last_modified=str(d['last_modified'])))
        return d

    def to_sdict(self):
        """Export a StandardNameTable to a dictionary as string"""
        import json
        return json.dumps(self.to_dict())

    def dump(self, sort_by: str = 'name', **kwargs):
        """pretty representation of the table for jupyter notebooks"""
        df = pd.DataFrame(self.table).T
        if sort_by.lower() in ('name', 'names', 'standard_name', 'standard_names'):
            display(HTML(df.sort_index().to_html(**kwargs)))
        elif sort_by.lower() in ('units', 'unit', 'canonical_units'):
            display(HTML(df.sort_values('canonical_units').to_html(**kwargs)))
        else:
            raise ValueError(f'Invalid value for sort by: {sort_by}')

    def get_pretty_table(self, sort_by: str = 'name', **kwargs) -> str:
        """string representation of the SNT in form of a table"""
        try:
            from tabulate import tabulate
        except ImportError:
            raise ImportError('Package "tabulate" is missing.')
        df = pd.DataFrame(self.table).T
        if sort_by.lower() in ('name', 'names', 'standard_name', 'standard_names'):
            sorted_df = df.sort_index()
        elif sort_by.lower() in ('units', 'unit', 'canonical_units'):
            sorted_df = df.sort_values('canonical_units')
        else:
            sorted_df = df
        tablefmt = kwargs.pop('tablefmt', 'psql')
        headers = kwargs.pop('headers', 'keys')
        return tabulate(sorted_df, headers=headers, tablefmt=tablefmt, **kwargs)

    def dumps(self, sort_by: str = 'name', **kwargs) -> None:
        """Dumps (prints) the content as string"""
        meta_str = '\n'.join([f'{key}: {value}' for key, value in self.meta.items()])
        print(f"{meta_str}\n{self.get_pretty_table(sort_by, **kwargs)}")

    @staticmethod
    def get_registered() -> List["StandardNameTable"]:
        """Return sorted list of standard names files"""
        return [StandardNameTable.from_yaml(f) for f in sorted(UserDir['standard_name_tables'].glob('*'))]

    @staticmethod
    def print_registered() -> None:
        """Return sorted list of standard names files"""
        for f in StandardNameTable.get_registered():
            print(f' > {f}')


class StandardNameValidator(StandardAttributeValidator):
    """Validator for attribute standard_name"""

    def __call__(self, standard_name, parent, **kwargs):
        snt = parent.rootparent.attrs.get('standard_name_table', None)

        if snt is None:
            raise KeyError('No standard name table defined for this file!')

        snt = parse_snt(snt)

        units = parent.attrs.get('units', None)
        if units is None:
            raise KeyError('No units defined for this variable!')

        if not snt.check(standard_name, units):
            raise ValueError(f'Standard name {standard_name} with units {units} is invalid')
        return standard_name


class StandardNameTableValidator(StandardAttributeValidator):
    """Validates a standard name table"""

    def __call__(self, standard_name_table, *args, **kwargs):
        return parse_snt(standard_name_table).to_sdict()


def parse_snt(standard_name_table: Union[str, dict, StandardNameTable]) -> StandardNameTable:
    """Returns a StandardNameTable object from a string, dict or StandardNameTable object"""
    if isinstance(standard_name_table, StandardNameTable):
        return standard_name_table
    if isinstance(standard_name_table, dict):
        return StandardNameTable(**standard_name_table)
    if isinstance(standard_name_table, str):
        # could be web address or local file
        if standard_name_table.startswith('https://zenodo.org/record/'):
            return StandardNameTable.from_zenodo(standard_name_table)
        else:
            fname = pathlib.Path(standard_name_table)
            if fname.exists() and fname.suffix in ('.yaml', '.yml'):
                return StandardNameTable.from_yaml(fname)
            else:
                raise FileNotFoundError(f'File {fname} not found or not a yaml file')
    raise TypeError(f'Invalid type for standard_name_table: {type(standard_name_table)}')


"""Transformation for standard names"""


class Transformation:
    """Transformation for standard names"""

    def __init__(self, snt, func: Callable):
        self.snt = snt
        self.func = func

    def __call__(self, standard_name):
        return self.func(standard_name, self.snt)


def magnitude_of(standard_name, snt) -> StandardName:
    match = re.match(r"^magnitude_of_(.*)$",
                     standard_name)
    if match:
        groups = match.groups()
        assert len(groups) == 1
        sn = groups[0]
        snt.check(sn)
        new_description = f"Magnitude of {sn.name}"
        return StandardName(standard_name, sn.units, new_description)
    return False


def square_of(standard_name, snt) -> StandardName:
    match = re.match(r"^square_of_(.*)$",
                     standard_name)
    if match:
        groups = match.groups()
        assert len(groups) == 1
        sn = groups[0]
        snt.check(sn)
        new_description = f"Square of {sn.name}"
        new_units = (1 * sn.units * sn.units).units
        return StandardName(standard_name, new_units, new_description)
    return False


def difference_of_X_across_device(standard_name, snt) -> StandardName:
    """Difference of X across device"""
    match = re.match(r"^difference_of_(.*)_across_(.*)$",
                     standard_name)
    if match:
        groups = match.groups()
        assert len(groups) == 2
        if groups[1] not in snt.devices:
            raise KeyError(f'Device {groups[1]} not found in registry of the standard name table. '
                           f'Available devices are: {snt.devices}')
        sn = groups[0]
        snt.check(sn)
        new_description = f"Difference of {sn} across the device {groups[1]}"
        return StandardName(standard_name, snt[sn].units, new_description)
    return False


def difference_of_X_and_y_across_device(standard_name, snt) -> StandardName:
    """Difference of X and Y across device"""
    match = re.match(r"^difference_of_(.*)_and(.*)_across_(.*)$",
                     standard_name)
    if match:
        groups = match.groups()
        assert len(groups) == 3
        if groups[2] not in snt.devices:
            raise KeyError(f'Device {groups[0]} not found in registry of the standard name table. '
                           f'Available devices are: {snt.devices}')
        sn1 = snt.check(groups[0])
        sn2 = snt.check(groups[1])
        new_description = f"Difference of {sn1.name} adn {sn2.name} across the device {groups[1]}"
        return StandardName(standard_name, sn1.units, new_description)
    return False


def derivative_of_X_wrt_to_Y(standard_name, snt) -> StandardName:
    """Check if a standard name is a derivative of X wrt to Y"""
    match = re.match(r"^derivative_of_(.*)_wrt_(.*)$",
                     standard_name)
    if match:
        groups = match.groups()
        assert len(groups) == 2
        if all([snt.check(n) for n in groups]):
            sn1 = snt[groups[0]]
            sn2 = snt[groups[1]]
            new_units = (1 * sn1.units / 1 * sn2.units).units
            new_description = f"Derivative of {sn1.name} wrt to {sn2.name}"
            return StandardName(standard_name, new_units, new_description)
    return False
    # raise ValueError(f"Standard name '{standard_name}' is not a derivative of X wrt to Y")


def product_of_X_and_Y(standard_name, snt) -> StandardName:
    """Check if a standard name is a derivative of X wrt to Y"""
    match = re.match(r"^product_of_(.*)_and_(.*)$",
                     standard_name)
    if match:
        groups = match.groups()
        assert len(groups) == 2
        if all([snt.check(n) for n in groups]):
            sn1 = snt[groups[0]]
            sn2 = snt[groups[1]]
            new_units = (1 * sn1.units * sn2.units).units
            new_description = f"Product of {sn1.name} and {sn2.name}"
            return StandardName(standard_name, new_units, new_description)
    return False
    # raise ValueError(f"Standard name '{standard_name}' is not a derivative of X wrt to Y")


def ratio_of_X_and_Y(standard_name, snt) -> StandardName:
    """Check if a standard name is a derivative of X wrt to Y"""
    match = re.match(r"^ratio_of_(.*)_and_(.*)$",
                     standard_name)
    if match:
        groups = match.groups()
        assert len(groups) == 2
        if all([snt.check(n) for n in groups]):
            sn1 = snt[groups[0]]
            sn2 = snt[groups[1]]
            new_units = (1 * sn1.units / sn2.units).units
            new_description = f"Ratio of {sn1.name} and {sn2.name}"
            return StandardName(standard_name, new_units, new_description)
    return False


"""Utils"""


def update_datasets(group_or_filename: Union[h5py.Group, str, pathlib.Path],
                    translation_dict: Dict,
                    rec: bool = True) -> None:
    """Walk through file and assign standard names to datasets with names indicated in
    the dictionary `translation_dict`

    Parameters
    ----------
    group_or_filename: Union[h5py.Group, str, pathlib.Path]
        The source in which to search for datasets and assign standard names to.
        If a string or pathlib.Path is passed, it is assumed to be an HDF5 filename.
    translation_dict: Dict
        Dictionary with keys being the dataset names and values the standard names
    rec: bool
        If True, recursively search for datasets

    Returns
    -------
    None

    Examples
    --------
    >>> # Assign "air_temperature" to all datasets with name "temperature":
    >>> translation_dict = {'temperature': 'air_temperature'}
    >>> update_datasets('myfile.hdf', translation_dict)
    """
    if isinstance(group_or_filename, (str, pathlib.Path)):
        with h5py.File(group_or_filename, 'r+') as h5:
            return update_datasets(h5['/'], translation_dict, rec=rec)

    def _assign(ds, sn):
        ds.attrs['standard_name'] = sn
        logger.debug(f'Added standard name "{sn}" to dataset "{ds.name}"')

    def sn_update(name: str, node):
        """function called when visiting HDF objects"""
        if isinstance(node, h5py.Dataset):
            if name in translation_dict:
                sn = translation_dict[name.strip('/')]
            elif name.rsplit('/', 1)[-1] in translation_dict:
                sn = translation_dict[name.rsplit('/', 1)[-1]]
            else:
                return
            _assign(node, sn)

    h5grp = group_or_filename
    if rec:
        return h5grp.visititems(sn_update)
    for key, obj in h5grp.items():
        sn_update(key, obj)
