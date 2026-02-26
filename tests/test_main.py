"""Tests for tx_lsp/__main__.py — CLI argument parsing."""

import pytest
from unittest.mock import patch, MagicMock

from tx_lsp.__main__ import parse_extra_patterns


# ── parse_extra_patterns ──────────────────────────────────────


class TestParseExtraPatterns:
    def test_none_input(self):
        assert parse_extra_patterns(None) == {}

    def test_empty_list(self):
        assert parse_extra_patterns([]) == {}

    def test_single_pattern(self):
        result = parse_extra_patterns(["*.auto=smauto"])
        assert result == {"*.auto": "smauto"}

    def test_multiple_patterns(self):
        result = parse_extra_patterns(["*.auto=smauto", "*.rob=robodsl"])
        assert result == {"*.auto": "smauto", "*.rob": "robodsl"}

    def test_invalid_pattern_skipped(self, capsys):
        result = parse_extra_patterns(["invalid_no_equals"])
        assert result == {}
        captured = capsys.readouterr()
        assert "Invalid pattern format" in captured.err

    def test_mixed_valid_and_invalid(self, capsys):
        result = parse_extra_patterns(["*.auto=smauto", "bad", "*.rob=robodsl"])
        assert result == {"*.auto": "smauto", "*.rob": "robodsl"}

    def test_pattern_with_spaces(self):
        result = parse_extra_patterns(["  *.auto  =  smauto  "])
        assert result == {"*.auto": "smauto"}

    def test_pattern_with_multiple_equals(self):
        result = parse_extra_patterns(["*.auto=smauto=extra"])
        assert result == {"*.auto": "smauto=extra"}


# ── CLI argparse ──────────────────────────────────────────────


class TestMainArgparse:
    def test_default_args(self):
        """main() with --help should not crash."""
        import argparse

        from tx_lsp.__main__ import main

        parser = argparse.ArgumentParser()
        parser.add_argument("--tcp", action="store_true")
        parser.add_argument("--ws", action="store_true")
        parser.add_argument("--host", default="127.0.0.1")
        parser.add_argument("--port", type=int, default=2087)
        parser.add_argument("--api", action="store_true")
        parser.add_argument("--api-port", type=int, default=8080)
        parser.add_argument("--api-key", default=None)
        parser.add_argument("--log-level", default="INFO")

        args = parser.parse_args([])
        assert args.tcp is False
        assert args.ws is False
        assert args.host == "127.0.0.1"
        assert args.port == 2087
        assert args.api is False
        assert args.api_port == 8080
        assert args.api_key is None
        assert args.log_level == "INFO"

    def test_tcp_args(self):
        import argparse

        parser = argparse.ArgumentParser()
        parser.add_argument("--tcp", action="store_true")
        parser.add_argument("--port", type=int, default=2087)
        parser.add_argument("--host", default="127.0.0.1")

        args = parser.parse_args(["--tcp", "--port", "3000", "--host", "0.0.0.0"])
        assert args.tcp is True
        assert args.port == 3000
        assert args.host == "0.0.0.0"

    def test_api_args(self):
        import argparse

        parser = argparse.ArgumentParser()
        parser.add_argument("--api", action="store_true")
        parser.add_argument("--api-port", type=int, default=8080)
        parser.add_argument("--api-key", default=None)

        args = parser.parse_args(["--api", "--api-port", "9090", "--api-key", "SECRET"])
        assert args.api is True
        assert args.api_port == 9090
        assert args.api_key == "SECRET"


# ── _start_api ────────────────────────────────────────────────


class TestStartApi:
    def test_missing_uvicorn_exits(self):
        from tx_lsp.__main__ import _start_api
        import argparse

        args = argparse.Namespace(host="127.0.0.1", api_port=8080, api_key=None, log_level="INFO")

        with patch.dict("sys.modules", {"uvicorn": None}):
            with patch("builtins.__import__", side_effect=ImportError):
                with pytest.raises(SystemExit):
                    _start_api(args, {})


class TestMainFunction:
    def test_main_stdio_mode(self):
        from tx_lsp.__main__ import main

        mock_server = MagicMock()
        with patch("tx_lsp.__main__.create_server", return_value=mock_server):
            with patch("sys.argv", ["tx-lsp"]):
                main()
                mock_server.start_io.assert_called_once()

    def test_main_tcp_mode(self):
        from tx_lsp.__main__ import main

        mock_server = MagicMock()
        with patch("tx_lsp.__main__.create_server", return_value=mock_server):
            with patch("sys.argv", ["tx-lsp", "--tcp", "--port", "3000"]):
                main()
                mock_server.start_tcp.assert_called_once_with("127.0.0.1", 3000)

    def test_main_ws_mode(self):
        from tx_lsp.__main__ import main

        mock_server = MagicMock()
        with patch("tx_lsp.__main__.create_server", return_value=mock_server):
            with patch("sys.argv", ["tx-lsp", "--ws", "--host", "0.0.0.0", "--port", "9000"]):
                main()
                mock_server.start_ws.assert_called_once_with("0.0.0.0", 9000)

    def test_main_api_mode(self):
        from tx_lsp.__main__ import _start_api
        import argparse

        args = argparse.Namespace(host="127.0.0.1", api_port=9090, api_key=None, log_level="INFO")

        mock_uvicorn = MagicMock()
        mock_app = MagicMock()
        with patch("tx_lsp.__main__.create_app", return_value=mock_app, create=True):
            with patch.dict("sys.modules", {"uvicorn": mock_uvicorn}):
                _start_api(args, {})

    def test_main_with_extra_patterns(self):
        from tx_lsp.__main__ import main

        mock_server = MagicMock()
        with patch("tx_lsp.__main__.create_server", return_value=mock_server) as mock_create:
            with patch("sys.argv", ["tx-lsp", "--extra-pattern", "*.auto=smauto"]):
                main()
                mock_create.assert_called_once_with(extra_patterns={"*.auto": "smauto"})

    def test_main_log_level(self):
        from tx_lsp.__main__ import main

        mock_server = MagicMock()
        with patch("tx_lsp.__main__.create_server", return_value=mock_server):
            with patch("sys.argv", ["tx-lsp", "--log-level", "DEBUG"]):
                main()
