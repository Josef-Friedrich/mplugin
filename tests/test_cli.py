import argparse

import pytest

from mplugin.cli import MultiArg, setup_argparser


class TestMultiarg:
    def test_len(self) -> None:
        m = MultiArg(["a", "b"])
        assert 2 == len(m)

    def test_iter(self) -> None:
        m = MultiArg(["a", "b"])
        assert ["a", "b"] == list(m)

    def test_split(self) -> None:
        m = MultiArg("a,b")
        assert ["a", "b"] == list(m)

    def test_explicit_fill_element(self) -> None:
        m = MultiArg(["0", "1"], fill="extra")
        assert "1" == m[1]
        assert "extra" == m[2]

    def test_fill_with_last_element(self) -> None:
        m = MultiArg(["0", "1"])
        assert "1" == m[1]
        assert "1" == m[2]

    def test_fill_empty_multiarg_returns_none(self) -> None:
        assert None is MultiArg([])[0]


class TestSetupArgparser:
    def test_basic_creation(self) -> None:
        parser = setup_argparser("test")
        assert isinstance(parser, argparse.ArgumentParser)
        assert parser.prog == "check_test"

    def test_name_already_prefixed(self) -> None:
        parser = setup_argparser("check_test")
        assert parser.prog == "check_test"

    def test_version_in_description(self) -> None:
        parser = setup_argparser("test", version="1.0.0")
        assert parser.description
        assert "version 1.0.0" in parser.description

    def test_license_in_description(self) -> None:
        parser = setup_argparser("test", license="MIT")
        assert parser.description
        assert "Licensed under the MIT." in parser.description

    def test_repository_in_description(self) -> None:
        parser = setup_argparser("test", repository="https://github.com/test/repo")
        assert parser.description
        assert "Repository: https://github.com/test/repo." in parser.description

    def test_copyright_in_description(self) -> None:
        parser = setup_argparser("test", copyright="Copyright 2024")
        assert parser.description
        assert "Copyright 2024" in parser.description

    def test_description_appended(self) -> None:
        parser = setup_argparser("test", description="A test plugin")
        assert parser.description
        assert "A test plugin" in parser.description

    def test_epilog(self) -> None:
        parser = setup_argparser("test", epilog="Some epilog text")
        assert parser.epilog == "Some epilog text"

    def test_verbose_flag(self) -> None:
        parser = setup_argparser("test", verbose=True)
        args = parser.parse_args(["-v"])
        assert args.verbose == 1

    def test_verbose_multiple(self) -> None:
        parser = setup_argparser("test", verbose=True)
        args = parser.parse_args(["-vvv"])
        assert args.verbose == 3

    def test_verbose_default(self) -> None:
        parser = setup_argparser("test", verbose=True)
        args = parser.parse_args([])
        assert args.verbose == 0

    def test_no_verbose_by_default(self) -> None:
        parser = setup_argparser("test", verbose=False)
        with pytest.raises(SystemExit):
            parser.parse_args(["-v"])

    def test_all_parameters(self) -> None:
        parser = setup_argparser(
            name="test",
            version="1.2.3",
            license="GPL",
            repository="https://example.com",
            copyright="Copyright 2024",
            description="Test description",
            epilog="Test epilog",
            verbose=True,
        )
        assert parser.prog == "check_test"
        assert parser.description
        assert "version 1.2.3" in parser.description
        assert "GPL" in parser.description
        assert "https://example.com" in parser.description
        assert "Copyright 2024" in parser.description
        assert "Test description" in parser.description
        assert parser.epilog == "Test epilog"

    def test_formatter_class(self) -> None:
        parser = setup_argparser("test")
        assert isinstance(
            parser.formatter_class(prog="prog"),
            argparse.RawDescriptionHelpFormatter,
        )

    def test_custom_exit_code(self) -> None:
        parser = setup_argparser("test", version="1.0")
        with pytest.raises(SystemExit) as exc_info:
            parser.parse_args(["--version"])
        assert exc_info.value.code == 3
