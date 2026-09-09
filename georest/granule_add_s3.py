#!/usr/bin/env python
#
# Author(s):
#
#     Panu Lahtinen <panu.lahtinen@fmi.fi>

"""Add a file (granule) to a Geoserver ImageMosaic layer via REST API."""

import logging
import sys

from georest import add_file_to_mosaic
from georest.utils import read_config


def run():
    """Add granule."""
    config = read_config(sys.argv[1])

    if "log_config" in config:
        logging.config.dictConfig(config["log_config"])

    add_file_to_mosaic(config, sys.argv[2], filesystem='s3')
