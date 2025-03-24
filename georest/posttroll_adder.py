#!/usr/bin/env python
#
# Author(s):
#
#     Panu Lahtinen <panu.lahtinen@fmi.fi>

"""Listen to Posttroll messages and add the files to Geoserver layer."""

import logging
import sys

from posttroll.subscriber import Subscribe

from georest.utils import read_config, run_posttroll_adder


def run():
    """Run Posttroll adder."""
    config = read_config(sys.argv[1])

    if "log_config" in config:
        logging.config.dictConfig(config["log_config"])
    logger = logging.getLogger("posttroll_adder")
    logger.info("Posttroll Geoserver updater started")

    run_posttroll_adder(config, Subscribe)
