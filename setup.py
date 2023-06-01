#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Author(s):
#   Panu Lahtinen <panu.lahtinen@fmi.fi>

"""Setup file for georest."""

from setuptools import find_packages, setup

from georest import __version__

requires = [
    'pyyaml',
    'geoserver-restconfig',
    'trollsift',
]
extras_require = {
    'posttroll': ['pyzmq'],
    's3': ['requests'],

}
all_extras = []
for extra_deps in extras_require.values():
    all_extras.extend(extra_deps)
extras_require['all'] = list(set(all_extras))

NAME = 'georest'
README = open('README.md', 'r').read()

setup(name=NAME,
      description='Python package for interacting with Geoserver using REST API',
      long_description=README,
      author='Panu Lahtinen',
      author_email='panu.lahtinen@fmi.fi',
      url="https://github.fmi.fi/fmidev/geoserver-rest",
      version=__version__,
      packages=find_packages(),
      install_requires=requires,
      extras_require=extras_require,
      python_requires='>=3.4',
      data_files=[],
      zip_safe=False,
      scripts=['bin/create_layers.py',
               'bin/create_s3_layers.py',
               'bin/add_granule.py',
               'bin/delete_granule.py',
               'bin/delete_old_granules_and_files.py',
               'bin/posttroll_adder.py',
               'bin/create_layer_directories.py'],
      )
