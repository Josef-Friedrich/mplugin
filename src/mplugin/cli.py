from __future__ import annotations

import sys
from argparse import ArgumentParser, RawDescriptionHelpFormatter
from typing import Iterator, NoReturn, Optional, Union

"""Helper classes and functions to setup the Command Line Interface (cli) of
monitoring plugins."""


class MultiArg:
    """
    A container class for handling multiple arguments that can be indexed and iterated.

    This class is designed to be used as a type converter in argparse for arguments
    that accept comma-separated or otherwise delimited values. It provides convenient
    access to individual arguments with optional fill values for missing indices.


    .. code-block:: python

        argp.add_argument(
            "--tw",
            "--ttot-warning",
            metavar="RANGE[,RANGE,...]",
            type=mplugin.MultiArg,
            default="",
        )

    :param args: The list of parsed argument strings.
    :param fill: An optional default value to return for indices
        beyond the length of the args list. If not provided, the last argument
        is returned instead, or None if the list is empty.
    :param splitchar:
    """

    args: list[str]
    """The list of parsed argument strings."""

    fill: Optional[str]
    """An optional default value to return for indices
    beyond the length of the args list. If not provided, the last argument
    is returned instead, or None if the list is empty."""

    def __init__(
        self,
        args: Union[list[str], str],
        fill: Optional[str] = None,
        splitchar: str = ",",
    ) -> None:
        if isinstance(args, list):
            self.args = args
        else:
            self.args = args.split(splitchar)
        self.fill = fill

    def __len__(self) -> int:
        return self.args.__len__()

    def __iter__(self) -> Iterator[str]:
        return self.args.__iter__()

    def __getitem__(self, key: int) -> Optional[str]:
        try:
            return self.args.__getitem__(key)
        except IndexError:
            pass
        if self.fill is not None:
            return self.fill
        try:
            return self.args.__getitem__(-1)
        except IndexError:
            return None


class __CustomArgumentParser(ArgumentParser):
    """
    Override the exit method for the options ``--help``, ``-h`` and ``--version``,
    ``-V`` with ``Unknown`` (exit code 3), according to the
    `Monitoring Plugin Guidelines
    <https://github.com/monitoring-plugins/monitoring-plugin-guidelines/blob/main/monitoring_plugins_interface/02.Input.md>`__.
    """

    def exit(self, status: int = 3, message: Optional[str] = None) -> NoReturn:
        if message:
            self._print_message(message, sys.stderr)
        sys.exit(status)


def setup_argparser(
    name: Optional[str],
    version: Optional[str] = None,
    license: Optional[str] = None,
    repository: Optional[str] = None,
    copyright: Optional[str] = None,
    description: Optional[str] = None,
    epilog: Optional[str] = None,
    verbose: bool = False,
) -> ArgumentParser:
    """
    Set up and configure an argument parser for a monitoring plugin
    according the
    `Monitoring Plugin Guidelines
    <https://github.com/monitoring-plugins/monitoring-plugin-guidelines/blob/main/monitoring_plugins_interface/02.Input.md>`__.

    This function creates a customized ArgumentParser instance with metadata
    and formatting suitable for monitoring plugins. It automatically prefixes
    the plugin name with ``check_`` if not already present.

    :param name: The name of the plugin. If provided and doesn't start with
        ``check``, it will be prefixed with ``check_``.
    :param version: The version number of the plugin. If provided, it will be
        included in the parser description. In addition, an option ``-V``,
        ``--version`` is provided, which outputs the version number.
    :param license: The license type of the plugin. If provided, it will be
        included in the parser description.
    :param repository: The repository URL of the plugin. If provided, it will
        be included in the parser description.
    :param copyright: The copyright information for the plugin. If provided,
        it will be included in the parser description.
    :param description: A detailed description of the plugin's functionality.
        If provided, it will be appended to the parser description after a
        blank line.
    :param epilog: Additional information to display after the help message.
    :param verbose: Provide a ``-v``, ``--verbose`` option. The option can be
        specified multiple times, e. g. ``-vvv``

    :returns: A configured ArgumentParser instance with RawDescriptionHelpFormatter,
        80 character width, and metadata assembled from the provided parameters.
    """
    description_lines: list[str] = []

    if name is not None and not name.startswith("check"):
        name = f"check_{name}"

    if version is not None:
        description_lines.append(f"version {version}")

    if license is not None:
        description_lines.append(f"Licensed under the {license}.")

    if repository is not None:
        description_lines.append(f"Repository: {repository}.")

    if copyright is not None:
        description_lines.append(copyright)

    if description is not None:
        description_lines.append("")
        description_lines.append(description)

    parser: ArgumentParser = __CustomArgumentParser(
        prog=name,
        formatter_class=lambda prog: RawDescriptionHelpFormatter(prog, width=80),
        description="\n".join(description_lines),
        epilog=epilog,
    )

    if version is not None:
        parser.add_argument(
            "-V",
            "--version",
            action="version",
            version=f"%(prog)s {version}",
        )

    if verbose:
        # https://github.com/monitoring-plugins/monitoring-plugin-guidelines/blob/main/monitoring_plugins_interface/02.Input.md
        parser.add_argument(
            "-v",
            "--verbose",
            action="count",
            default=0,
            help="Increase the output verbosity.",
        )

    return parser
