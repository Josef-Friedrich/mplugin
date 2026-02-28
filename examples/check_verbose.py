#! /usr/bin/env python

import argparse

import mplugin
from mplugin import log


class Logging(mplugin.Resource):
    def probe(self):
        log.warning("warning message")
        log.info("info message")
        log.debug("debug message")
        return [mplugin.Metric("zero", 0, context="default")]


@mplugin.guarded
def main():
    argp = argparse.ArgumentParser()
    argp.add_argument("-v", "--verbose", action="count", default=0)
    args = argp.parse_args()
    check = mplugin.Check(Logging())
    check.main(args.verbose)


if __name__ == "__main__":
    main()
