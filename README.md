# HDF5 Research Data Management Toolbox

![Tests](https://github.com/matthiasprobst/h5RDMtoolbox/actions/workflows/tests.yml/badge.svg)
![DOCS](https://codecov.io/gh/matthiasprobst/h5RDMtoolbox/branch/dev/graph/badge.svg)
[![Documentation Status](https://readthedocs.org/projects/h5rdmtoolbox/badge/?version=latest)](https://h5rdmtoolbox.readthedocs.io/en/latest/?badge=latest)
![pyvers](https://img.shields.io/badge/python-3.8%20%7C%203.9%20%7C%203.10-blue)

*Note, that the project is still under development!*

The "HDF5 Research Data Management Toolbox" (h5RDMtoolbox) is a python package supporting everybody who is working with
HDF5 to achieve a sustainable data lifecycle which follows
the [FAIR (Findable, Accessible, Interoperable, Reusable)](https://www.nature.com/articles/sdata201618)
principles. It specifically supports the five main steps of

1. Planning (defining a internal layout for HDF5 a metadata convention for attribute usage)
2. Collecting data (creating HDF5 files or converting to HDF5 files from other sources)
3. Analyzing and processing data (Plotting, deriving data, ...)
4. Sharing data (publishing, archiving, ... e.g. to databases like [mongoDB](https://www.mongodb.com/) or repositories
   like [Zenodo](https://zenodo.org/))
5. Reusing data (Searching data in databases, local file structures or online repositories
   like [Zenodo](https://zenodo.org)).

## Documentation

Please click on the image clicke [here](h5rdmtoolbox.readthedocs.io/en/latest/) to find a comprehensive documentation
with examples

<a href="https://h5rdmtoolbox.readthedocs.io/en/latest/"><img src="docs/_static/new_icon_with_text.svg" alt="RDM lifecycle" style="widht:600px;"></a>

## Quickstart

Get a first idea of how the `h5RDMtoolbox` supports the FAIR research data lifecycle of
`planning`,
`collecting`,
`analyzing`,
`sharing` and
`reusing` with a minimal example:

### 1. Planning

- Decide to use HDF5 as your core file format
- Define important attributes and their usage in a metadata convention (e.g. a YAML file)
- Publish your convention on a repository like [Zenodo](https://zenodo.org/)

```python
# import the package
import h5rdmtoolbox as h5tbx

# Assume we published a convention here: https://zenodo.org/record/8281285
cv = h5tbx.conventions.from_zenodo(doi='8281285')

# enable the convention:
h5tbx.use(cv)
```

### 2. Collecting

- Fill an HDF5 file with the required data and mandatory metadata
- Data may come various sources, e.g. from a measurement, a simulation or a database
- HDF5 is best for multidimensional data, but can also be used for 1D data
- When writing the HDF5 files, the convention is automatically validating the metadata input, which are the attributes
  or the datasets and groups

```python
with h5tbx.File('my_file.h5',
                data_type='experimental',
                contact='https://orcid.org/0000-0001-8729-0482') as h5:
    # create a dataset
    h5.create_dataset(name='u',
                      data=[1, 42, 101],
                      standard_name='x_velocity',
                      units='m/s')
```

### 3. Analyzing

 - Open the file, make computations or just plot the data

```python
with h5tbx.File('my_file.h5') as h5:
    h5['u'][1:2].plot()
```

### 4. Sharing your data
 - Share your data by storing it in a local directory or in a database
 - The `h5rdmtoolbox` supports both options by providing search queries for local directories and the non-relational 
   database [mongoDB](https://www.mongodb.com/)
```python
from pymongo import MongoClient

client = MongoClient()
collection = client['my_database']['my_collection']
with h5tbx.File('my_file.h5') as h5:
    h5['u'][1:2].mongo.insert(0, collection)
```

### 5. Reusing

 - Find the data by searching for the metadata in the [mongoDB](https://www.mongodb.com/)

```python
arr = collection.find_one({'standard_name': {'$eq': 'x_velocity'}})
# plot it again
arr.plot()
# or if the file is local, find it within a folder:
arr = h5tbx.database.Folder('db_folder').find_one({'standard_name': {'$eq': 'x_velocity'}})
arr[()].plot()
```

## Installation

Use python 3.8 or higher (tested until 3.10).

### Install from source:

Clone the repository first:

    git clone https://github.com/matthiasprobst/h5RDMtoolbox.git

Then, run

    pip install h5RDMtoolbox

Add `--user` if you do not have root access.

For development installation run

    pip install -e h5RDMtoolbox

### Dependencies

The core functionality depends on the following packages:

- `appdirs>=1.4.4`: Managing user and application directories
- `numpy>=1.20,<1.23.0`: Scientific computing, handling of arrays
- `h5py>=3.7.0`: HDF5 file interface
- `matplotlib>=3.5.2`: Plotting
- `pandas>=1.4.3`: Mainly used for reading csv and pretty printing
- `IPython>=8.4.0`: Pretty display of data in notebooks
- `pyyaml`: Reading and writing of yaml files
- `xarray>=2022.3.0`: Working with scientific arrays in combination with attributes
- `pint>=0.19.2`: Working with units
- `pint_xarray>=0.2.1`: Working with units in xarray
- `regex>=2020.7.9`: Regular expressions
- `packaging`: Version handling
- `python-forge==18.6.0`: Used to update function signatures when using the h5rdmtoolbox conventions
- `requests`: Used to download files from the internet

#### Optional dependencies

To run unit tests or to enable certain features, additional dependencies must be installed.

Install optional dependencies by specifying them in square brackets after the package name, e.g.:

    pip install h5RDMtoolbox[mongodb]

[mongodb]

- `pymongo>=4.2.0`: Database solution for HDF5 files

[io]

- `pco_tools>=1.0.0`: Reading of pco image files
- `opencv-python>=4.5.3.56`: Reading of image files (other than pco)

[snt]

- `xmltodict`: Reading of xml files
- `tabulate>=0.8.10`: Pretty printing of tables
- `python-gitlab`: Access to gitlab repositories
- `pandoc>=2.3`: Conversion of markdown files to html

## Contribution

Feel free to contribute. Make sure to write `docstrings` to your methods and classes and please write tests and use PEP
8 (https://peps.python.org/pep-0008/)

Please use the **numpy style for the docstrings**:
https://sphinxcontrib-napoleon.readthedocs.io/en/latest/example_numpy.html#example-numpy


