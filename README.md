
<h1 text-align: center;><img src="docs/icons/icon4.svg" alt="" width="40"/> HDF5 Research Data Management Toolbox</h1>


![Tests](https://github.com/matthiasprobst/h5RDMtoolbox/actions/workflows/tests.yml/badge.svg)
![DOCS](https://codecov.io/gh/matthiasprobst/h5RDMtoolbox/branch/dev/graph/badge.svg)
[![Documentation Status](https://readthedocs.org/projects/h5rdmtoolbox/badge/?version=latest)](https://h5rdmtoolbox.readthedocs.io/en/latest/?badge=latest)

*Note, that the project is still beta!*

The "HDF5 Research Data Management Toolbox" (`h5RDMtoolbox`) is a python package that provides a set of tools to work
with HDF5 files. It is designed to be used in research and development projects. It supports the data creation,
processing and sharing of data using the HDF5 file format pursuing the
[FAIR](https://www.nature.com/articles/sdata201618) principles.

All functionalities are wrapped around the [`h5py` package](https://www.h5py.org/). Flexible, user-defined conventions, 
which are standardized attributes and file layout specifications achieve the goals of sustainable data management.

By including other packages such as `xarray`, visualization of data becomes fast 
and easy. Also, a database-solution for HDF5 files is provided.

## Documentation
Please find the comprehensive documentation with examples [here](h5rdmtoolbox.readthedocs.io/en/latest/).  


## Installation
Navigate to the repository directory.

Clone the repository

     git clone https://github.com/matthiasprobst/h5RDMtoolbox

Make sure you have python3.8 or higher installed. Then run:

    pip install h5RDMtoolbox
or for editable mode:

    pip install -e h5RDMtoolbox

There are optional dependencies, e.g. for PIV-specific features. Specify them in square brackets after the package 
name. Check the setup config (`setup.cfg`) or the [documentation](h5rdmtoolbox.readthedocs.io/en/latest/) for 
all optional dependencies. To install all dependencies, simply run

    pip install h5RDMtoolbox[complete]


## Contribution
Feel free to contribute. Make sure to write `docstrings` to your methods and classes and please write 
tests and use PEP 8 (https://peps.python.org/pep-0008/)

Please use the **numpy style for the docstrings**: 
https://sphinxcontrib-napoleon.readthedocs.io/en/latest/example_numpy.html#example-numpy


