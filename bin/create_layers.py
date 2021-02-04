#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Author(s):
#
#     Panu Lahtinen <panu.lahtinen@fmi.fi>

"""Create Geoserver ImageMosaic layers via REST API."""

import sys
import logging

import georest


def main():
    """Main()"""
    config = georest.utils.read_config(sys.argv[1])

    if "log_config" in config:
        logging.config.dictConfig(config["log_config"])
    logger = logging.getLogger("create_layers")
    georest.create_layers(config)
    logger.info("Layer creation finished")


if __name__ == "__main__":
    main()
