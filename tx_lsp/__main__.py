"""Entry point for tx-lsp language server.

Usage:
    tx-lsp                          # stdio mode (default, for editor clients)
    tx-lsp --tcp --port 2087        # TCP mode (for debugging)
    tx-lsp --ws --port 2087         # WebSocket mode
    tx-lsp --extra-pattern '*.auto=smauto'  # register extra file patterns
"""

import argparse
import logging
import sys

from tx_lsp.server import create_server


def parse_extra_patterns(pattern_args):
    """Parse '--extra-pattern' arguments into a dict.

    Format: '*.ext=language_name'
    E.g., '*.auto=smauto' maps .auto files to the smauto language.
    """
    patterns = {}
    if not pattern_args:
        return patterns
    for arg in pattern_args:
        if "=" not in arg:
            print(
                f"Invalid pattern format: {arg!r} (expected '*.ext=language_name')",
                file=sys.stderr,
            )
            continue
        pattern, lang_name = arg.split("=", 1)
        patterns[pattern.strip()] = lang_name.strip()
    return patterns


def main():
    parser = argparse.ArgumentParser(
        description="tx-lsp: Generic Language Server for textX-based DSLs"
    )
    parser.add_argument("--tcp", action="store_true", help="Use TCP transport (default: stdio)")
    parser.add_argument("--ws", action="store_true", help="Use WebSocket transport")
    parser.add_argument(
        "--host", default="127.0.0.1", help="Host for TCP/WS transport (default: 127.0.0.1)"
    )
    parser.add_argument(
        "--port", type=int, default=2087, help="Port for TCP/WS transport (default: 2087)"
    )
    parser.add_argument(
        "--extra-pattern",
        action="append",
        dest="extra_patterns",
        metavar="'*.ext=lang'",
        help="Register extra file pattern for a language (repeatable)",
    )
    parser.add_argument(
        "--api",
        action="store_true",
        help="Start REST API server instead of LSP",
    )
    parser.add_argument(
        "--api-port",
        type=int,
        default=8080,
        help="Port for REST API (default: 8080)",
    )
    parser.add_argument(
        "--api-key",
        default=None,
        help="API key for REST API authentication (optional)",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging level (default: INFO)",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        stream=sys.stderr,
    )

    extra_patterns = parse_extra_patterns(args.extra_patterns)

    if args.api:
        _start_api(args, extra_patterns)
    else:
        server = create_server(extra_patterns=extra_patterns)
        if args.tcp:
            server.start_tcp(args.host, args.port)
        elif args.ws:
            server.start_ws(args.host, args.port)
        else:
            server.start_io()


def _start_api(args, extra_patterns):
    try:
        import uvicorn
    except ImportError:
        print("REST API requires uvicorn. Install with: pip install tx-lsp[api]", file=sys.stderr)
        sys.exit(1)

    from tx_lsp.api.app import create_app

    app = create_app(extra_patterns=extra_patterns, api_key=args.api_key)
    uvicorn.run(app, host=args.host, port=args.api_port, log_level=args.log_level.lower())


if __name__ == "__main__":
    main()
