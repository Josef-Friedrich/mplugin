#!python

"""Hello world monitoring check."""

import mplugin


class World(mplugin.Resource):
    def probe(self):
        return [mplugin.Metric("world", True, context="null")]


def main():
    check = mplugin.Check(World())
    check.main()


if __name__ == "__main__":
    main()
