#!/usr/bin/env python
#
# Author(s):
#
#     Panu Lahtinen <panu.lahtinen@fmi.fi>

"""Create Geoserver ImageMosaic layers via REST API."""

import logging
import sys

from georest import create_layers
from georest.utils import read_config


def run():
    """Create layers."""
    config = read_config(sys.argv[1])

    if "log_config" in config:
        logging.config.dictConfig(config["log_config"])
    logger = logging.getLogger("create_layers")
    create_layers(config)
    logger.info("Layer creation finished")
