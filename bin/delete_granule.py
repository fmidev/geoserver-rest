#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Author(s):
#
#     Panu Lahtinen <panu.lahtinen@fmi.fi>

"""Delete a grenule from Geoserver ImageMosaic layer via REST API."""

import sys
import logging

import georest


def main():
    """Delete granule."""
    config = georest.utils.read_config(sys.argv[1])

    if "log_config" in config:
        logging.config.dictConfig(config["log_config"])

    fname = sys.argv[2]
    georest.delete_file_from_mosaic(config, fname)


if __name__ == "__main__":
    main()
