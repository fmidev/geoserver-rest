#!/usr/bin/env python
#
# Author(s):
#
#     Panu Lahtinen <panu.lahtinen@fmi.fi>

"""Delete old granules from Geoserver and filesystem."""

import logging
import sys
import time

from georest import delete_old_files_from_mosaics_and_fs
from georest.utils import read_config


def run():
    """Delete granule."""
    config = read_config(sys.argv[1])

    if "log_config" in config:
        logging.config.dictConfig(config["log_config"])

    logger = logging.getLogger("delete_old_granules_and_files")
    start_time = time.time()
    delete_old_files_from_mosaics_and_fs(config)
    logger.info("Cleaning for %s completed in %.1f s",
                sys.argv[1], (time.time() - start_time))
