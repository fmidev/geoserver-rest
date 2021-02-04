#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Author(s):
#
#     Panu Lahtinen <panu.lahtinen@fmi.fi>

"""Add a file (granule) to a Geoserver ImageMosaic layer via REST API."""

import sys
import logging

import georest


def main():
    """Add granule."""
    config = georest.utils.read_config(sys.argv[1])

    if "log_config" in config:
        logging.config.dictConfig(config["log_config"])

    georest.add_file_to_mosaic(config, sys.argv[2])


if __name__ == "__main__":
    main()
