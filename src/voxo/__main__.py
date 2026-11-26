"""The `voxo` command line. The docstring of each command's function is its `--help`: write it for that reader."""

import argparse
import inspect
import sys
from collections.abc import Callable
from importlib.metadata import version
from pathlib import Path

import uvicorn

from voxo.core import Core, VoxoError
from voxo.daemon import start, stop
from voxo.web.app import create_app


def main() -> None:
    """Parse the command line of `voxo` and run the command it names."""
    parser = argparse.ArgumentParser(prog="voxo", description="A speech-to-text service for your own server.")
    parser.add_argument("--version", action="version", version=f"%(prog)s {version('voxo')}")
    data_dir = argparse.ArgumentParser(add_help=False)
    default_data_dir = Path.home() / ".local/share/voxo"
    data_dir.add_argument("--data-dir", type=Path, default=default_data_dir, help="data root (default: ~/.local/share/voxo)")
    port = argparse.ArgumentParser(add_help=False)
    port.add_argument("--port", type=int, default=7711, help="port on 127.0.0.1 (default: 7711)")
    commands = parser.add_subparsers(dest="command", required=True)

    def command(handler: Callable[..., object], *parents: argparse.ArgumentParser) -> argparse.ArgumentParser:
        doc = inspect.cleandoc(handler.__doc__ or "")
        return commands.add_parser(handler.__name__, parents=parents, help=doc.split("\n")[0], description=doc)

    command(serve, port, data_dir)
    command(start, port, data_dir)
    command(stop, data_dir)
    args = parser.parse_args()
    if args.command == "serve":
        serve(args.port, args.data_dir)
    elif args.command == "start":
        start(args.port, args.data_dir)
    elif args.command == "stop":
        stop(args.data_dir)


def serve(port: int, data_dir: Path) -> None:
    """Run the service in this terminal, until Ctrl+C."""
    try:
        Core(data_dir).start()
    except VoxoError as e:
        sys.exit(str(e))
    uvicorn.run(create_app(), host="127.0.0.1", port=port)


if __name__ == "__main__":
    main()
