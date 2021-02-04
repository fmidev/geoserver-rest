#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Author(s):
#
#     Panu Lahtinen <panu.lahtinen@fmi.fi>

"""Create Geoserver directory for eac configured layer."""

import sys
import os

from georest.utils import read_config, get_exposed_layer_directories


def main():
    """Create Geoserver layer director(y|ies)."""
    config = read_config(sys.argv[1])

    dirs = get_exposed_layer_directories(config)
    for _, path in dirs.items():
        print(path)
        try:
            os.makedirs(path)
        except FileExistsError:
            pass


if __name__ == "__main__":
    main()
