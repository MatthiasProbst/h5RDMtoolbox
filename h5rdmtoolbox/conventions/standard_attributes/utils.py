"""utilities of package conventions"""
import pathlib
import pint
import re
import requests
import warnings
import xml.etree.ElementTree as ET
from difflib import SequenceMatcher
from pathlib import Path
from typing import Dict, Union, Tuple

from ... import get_ureg

STANDARD_NAME_TABLE_FORMAT_FILE = Path(__file__).parent / 'standard_name_table_format.html'

EMAIL_REGREX = re.compile(r"([-!#-'*+/-9=?A-Z^-~]+(\.[-!#-'*+/-9=?A-Z^-~]+)*|\"([]!#-[^-~ \t]|(\\[\t -~]))+\")@"
                          r"([-!#-'*+/-9=?A-Z^-~]+(\.[-!#-'*+/-9=?A-Z^-~]+)*|\[[\t -Z^-~]*])")


def get_similar_names_ratio(a, b):
    """get the similarity of two strings. measure is between [0, 1]"""
    return SequenceMatcher(None, a, b).ratio()


# def equal_base_units(unit1, unit2):
#     """Return if two units are equivalent"""
#
#     base_unit1 = get_ureg()(unit1).to_base_units().units.__format__(get_ureg().default_format)
#     base_unit2 = get_ureg()(unit2).to_base_units().units.__format__(get_ureg().default_format)
#     return base_unit1 == base_unit2


def equal_base_units(u1: Union[str, pint.Unit, pint.Quantity],
                     u2: Union[str, pint.Unit, pint.Quantity]) -> bool:
    """Returns True if base units are equal, False otherwise"""

    def _convert(u):
        if isinstance(u, str):
            return 1 * get_ureg()(u)
        if isinstance(u, pint.Unit):
            return 1 * u
        if isinstance(u, pint.Quantity):
            return u
        raise TypeError(f"u must be a str, pint.Unit or pint.Quantity, not {type(u)}")

    return _convert(u1).to_base_units().units == _convert(u2).to_base_units().units


def is_valid_email_address(email: str) -> bool:
    """validates an email address.
    Taken from: https://stackabuse.com/python-validate-email-address-with-regular-expressions-regex/"""
    if re.fullmatch(EMAIL_REGREX, email):
        return True
    return False


def check_url(url, raise_error: bool = False, print_warning: bool = False, timeout: int = 2):
    """Check if URL is valid. Returns True if valid, False otherwise."""
    if print_warning and raise_error:
        raise ValueError("'print_warning' and 'raise_error' cannot both be True")
    try:
        response = requests.head(url, timeout=timeout)
        response.raise_for_status()
        return True
    except requests.exceptions.ConnectionError:
        msg = f"Error: Could not connect to URL {url}. Please check your internet connection."
    except requests.exceptions.HTTPError:
        msg = "Error: URL returned non-success status code."
    if raise_error:
        raise requests.exceptions.ConnectionError(msg)
    if print_warning:
        warnings.warn(msg, UserWarning)
    return False


def dict2xml(filename: Union[str, pathlib.Path],
             name: str,
             dictionary: Dict,
             **metadata) -> Path:
    """writes standard_names dictionary into a xml in style of cf-standard-name-table

    data must be a Tuple where first entry is the dictionary and the second one is metadata
    """

    root = ET.Element(name)

    for k, v in metadata.items():
        item = ET.Element(k)
        item.text = str(v)
        root.append(item)

    for k, v in dictionary.items():
        entry = ET.SubElement(root, "entry", attrib={'id': k})
        for kk, vv in v.items():
            item = ET.SubElement(entry, kk)
            item.text = vv

    tree = ET.ElementTree(root)
    tree.write(filename, encoding="utf-8", xml_declaration=True)
    return Path(filename)


def xmlsnt2dict(xml_filename: Path) -> Tuple[dict, dict]:
    """reads an SNT as xml file and returns data and meta dictionaries"""
    tree = ET.parse(xml_filename)
    root = tree.getroot()
    standard_names = {}
    meta = {'name': root.tag}
    for r in root:
        if r.tag != 'entry':
            meta.update({r.tag: r.text})

    for child in root.iter('entry'):
        standard_names[child.attrib['id']] = {}
        for c in child:
            standard_names[child.attrib['id']][c.tag] = c.text
    return standard_names, meta


def xml_to_html_table_view(xml_filename: Union[str, pathlib.Path],
                           html_filename: Union[str, pathlib.Path]) -> pathlib.Path:
    """creates a table view of standard xml file"""
    xml_filename = Path(xml_filename)
    if not xml_filename.exists():
        raise FileNotFoundError(f'File {xml_filename} does not exist')
    html_filename = Path(html_filename)
    if html_filename.exists():
        raise FileExistsError(f'File {html_filename} already exists')

    # read the xml file:
    with open(xml_filename, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    for i, line in enumerate(lines):
        if '{filename}' in line:
            lines[i] = line.format(filename=str(xml_filename))

    with open(html_filename, 'w', encoding='utf-8') as f:
        f.writelines(lines)

    return html_filename