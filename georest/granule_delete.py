#!/usr/bin/env python
#
# Author(s):
#
#     Panu Lahtinen <panu.lahtinen@fmi.fi>

"""Delete a grenule from Geoserver ImageMosaic layer via REST API."""

import logging
import sys

from georest import delete_file_from_mosaic
from georest.utils import read_config


def run():
    """Delete granule."""
    config = read_config(sys.argv[1])

    if "log_config" in config:
        logging.config.dictConfig(config["log_config"])

    fname = sys.argv[2]
    delete_file_from_mosaic(config, fname)
