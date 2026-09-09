#!/usr/bin/env python
#
# Author(s):
#
#     Panu Lahtinen <panu.lahtinen@fmi.fi>

"""Create Geoserver ImageMosaic layers via REST API when the files are in an S3 bucket."""

import logging
import sys

from georest import create_s3_layers
from georest.utils import read_config


def run():
    """Run S3 layer creation."""
    config = read_config(sys.argv[1])

    if "log_config" in config:
        logging.config.dictConfig(config["log_config"])
    logger = logging.getLogger("create_s3_layers")
    create_s3_layers(config)
    logger.info("Layer creation finished")
