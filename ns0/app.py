#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Module documentation goes here."""
import argparse
import time

from logzero import logger
from ns0 import NS0


def main(args):
    """ Main entry point of the app """
    # Create ns0 object
    # At this point we compute our initial set of records
    ns0 = NS0()

    while True:
        # ns0.providerUpdate()
        ns0.update()
        ns0.clean()
        logger.info(
            "Sleeping for {}s".format(ns0.config.resolve("ns0:update_interval"))
        )
        time.sleep(ns0.config.resolve("ns0:update_interval"))


if __name__ == "__main__":
    PARSER = argparse.ArgumentParser()

    # Required positional argument
    PARSER.add_argument("arg", help="Required positional argument")

    # Optional argument flag which defaults to False
    PARSER.add_argument("-f", "--flag", action="store_true", default=False)

    # Optional argument which requires a parameter (eg. -d test)
    PARSER.add_argument("-n", "--name", action="store", dest="name")

    # Optional verbosity counter (eg. -v, -vv, -vvv, etc.)
    PARSER.add_argument(
        "-v", "--verbose", action="count", default=0, help="Verbosity (-v, -vv, etc)"
    )

    # Specify output of "--version"
    PARSER.add_argument(
        "--version",
        action="version",
        version="%(prog)s (version {version})".format(version="0.1.0"),
    )

    MYARGS = PARSER.parse_args()
    main(MYARGS)
