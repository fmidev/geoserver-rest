#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Author(s):
#
#     Panu Lahtinen <panu.lahtinen@fmi.fi>

"""Delete old granules from Geoserver and filesystem."""

import sys
import logging
import time

import georest


def main():
    """Delete granule."""
    config = georest.utils.read_config(sys.argv[1])

    if "log_config" in config:
        logging.config.dictConfig(config["log_config"])

    logger = logging.getLogger("delete_old_granules_and_files")
    start_time = time.time()
    georest.delete_old_files_from_mosaics_and_fs(config)
    logger.info("Cleaning for %s completed in %.1f s",
                sys.argv[1], (time.time() - start_time))


if __name__ == "__main__":
    main()
