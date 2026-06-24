#!/usr/bin/env python3
"""
ResearchAgent CLI - Command Line Interface.

Usage:
    python -m cli.main                 # Interactive mode
    python -m cli.main --query "..."   # Single query mode
    python -m cli.main --server        # Start API server
"""

import argparse
import asyncio
import sys


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="ResearchAgent - AI Research Assistant",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s                              Start interactive mode
  %(prog)s -q "Analyze AI trends 2024"  Run single query
  %(prog)s --server                     Start API server
  %(prog)s --server --port 8080         Start server on custom port
        """,
    )

    parser.add_argument(
        "-q", "--query",
        type=str,
        help="Run a single query (non-interactive mode)",
    )
    parser.add_argument(
        "--server",
        action="store_true",
        help="Start the FastAPI web server",
    )
    parser.add_argument(
        "--host",
        type=str,
        default="0.0.0.0",
        help="Server host (default: 0.0.0.0)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="Server port (default: 8000)",
    )
    parser.add_argument(
        "--version",
        action="version",
        version="ResearchAgent 1.0.0",
    )

    args = parser.parse_args()

    if args.server:
        # Start API server
        from backend.utils.config import settings
        settings.host = args.host
        settings.port = args.port
        from backend.api.main import run_server
        run_server()
    elif args.query:
        # Single query mode
        from cli.commands import ResearchCLI
        cli = ResearchCLI()
        result = asyncio.run(cli.run_single_query(args.query))
        print(result)
    else:
        # Interactive mode
        from cli.commands import main as cli_main
        asyncio.run(cli_main())


if __name__ == "__main__":
    main()
