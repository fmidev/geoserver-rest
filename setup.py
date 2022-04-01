#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Author(s):
#   Panu Lahtinen <panu.lahtinen@fmi.fi>

"""Setup file for georest."""

from georest import __version__
from setuptools import find_packages, setup

requires = ['requests', 'gisdata', 'six', 'future', 'pyyaml',
            'geoserver-restconfig', 'trollsift']

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
      python_requires='>=3.4',
      data_files=[],
      zip_safe=False,
      scripts=['bin/create_layers.py',
               'bin/add_granule.py',
               'bin/delete_granule.py',
               'bin/delete_old_granules_and_files.py',
               'bin/posttroll_adder.py',
               'bin/create_layer_directories.py'],
      )
