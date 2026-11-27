"""The `voxo` command line. The docstring of each command's function is its `--help`: write it for that reader."""

import argparse
import inspect
import sys
from collections.abc import Callable
from importlib.metadata import version
from pathlib import Path

import uvicorn

from voxo.core.core import Core
from voxo.core.errors import VoxoError
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
    command(download, data_dir).add_argument("model", help="the name of the model; a wrong one lists the names voxo knows")
    command(token, data_dir).add_argument("--new", action="store_true", help="make a new token: the old one stops working")
    args = parser.parse_args()
    if args.command == "serve":
        serve(args.port, args.data_dir)
    elif args.command == "start":
        start(args.port, args.data_dir)
    elif args.command == "stop":
        stop(args.data_dir)
    elif args.command == "download":
        download(args.model, args.data_dir)
    elif args.command == "token":
        token(args.new, args.data_dir)


def serve(port: int, data_dir: Path) -> None:
    """Run the service in this terminal, until Ctrl+C."""
    core = Core(data_dir)
    try:
        core.start()
    except VoxoError as e:
        sys.exit(str(e))
    uvicorn.run(create_app(core), host="127.0.0.1", port=port)


def download(model: str, data_dir: Path) -> None:
    """Fetch the files of a model into the data dir. The only command that needs the network.

    Works while the service runs: it sees the model as soon as the download ends.
    """

    def show(fetched: int) -> None:
        # The cursor goes back to the start of the line, so the message that follows writes over the progress.
        sys.stderr.write(f"{fetched >> 20} MB\r")

    try:
        Core(data_dir).download(model, show)
    except VoxoError as e:
        sys.exit(str(e))
    sys.stdout.write(f"{model} is downloaded\n")


def token(new: bool, data_dir: Path) -> None:
    """Print the token of the service; the first call makes it.

    Every request to the service carries it as `Authorization: Bearer <token>`: give it to each app. Works while
    the service runs.
    """
    sys.stdout.write(f"{Core(data_dir).token(new=new)}\n")


if __name__ == "__main__":
    main()
