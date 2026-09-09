#!/usr/bin/env python
#
# Author(s):
#
#     Panu Lahtinen <panu.lahtinen@fmi.fi>

"""Create Geoserver directory for eac configured layer."""

import os
import sys

from georest.utils import get_exposed_layer_directories, read_config


def run():
    """Create Geoserver layer director(y|ies)."""
    config = read_config(sys.argv[1])

    dirs = get_exposed_layer_directories(config)
    for _, path in dirs.items():
        print(path)
        try:
            os.makedirs(path)
        except FileExistsError:
            pass
