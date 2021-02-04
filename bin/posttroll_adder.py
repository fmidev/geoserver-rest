#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Author(s):
#
#     Panu Lahtinen <panu.lahtinen@fmi.fi>

"""Listen to Posttroll messages and add the files to Geoserver layer."""

import sys
import logging

import georest

from posttroll.subscriber import Subscribe


def main():
    """Main()"""
    config = georest.utils.read_config(sys.argv[1])

    if "log_config" in config:
        logging.config.dictConfig(config["log_config"])
    logger = logging.getLogger("posttroll_adder")
    logger.info("Posttroll Geoserver updater started")

    georest.utils.run_posttroll_adder(config, Subscribe)


if __name__ == "__main__":
    main()
