"""`voxo start` and `voxo stop`: the service in the background, so no terminal has to stay open for it.

The docstrings of `start` and `stop` are the `--help` of the two commands.
"""

import os
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path

from voxo.core import Core


def start(port: int, data_dir: Path) -> None:
    """Run the service in the background, detached from this terminal, and wait until it listens.

    Its output goes to voxo.log in the data dir. It does not start again after a reboot or a crash.
    """
    data_dir = data_dir.resolve()
    data_dir.mkdir(parents=True, exist_ok=True)
    if (pid := Core.server_pid(data_dir)) is not None:
        sys.exit(f"voxo already runs on {data_dir} (pid {pid})")
    # Checked first, or the wait below would take another server on this port for the service.
    if _listens(port):
        sys.exit(f"port {port} is in use")
    log = data_dir / "voxo.log"
    if log.exists():
        log.replace(data_dir / "voxo.log.1")  # the log of the start before, to read after a crash
    with log.open("w") as out:
        # A session of its own: closing the terminal hangs up its session, and that would stop the service.
        process = subprocess.Popen(  # noqa: S603 -- this Python, fixed argv, no shell
            [sys.executable, "-m", "voxo", "serve", "--port", str(port), "--data-dir", str(data_dir)],
            stdin=subprocess.DEVNULL,
            stdout=out,
            stderr=out,
            start_new_session=True,
        )
    while not _listens(port):
        if process.poll() is not None:
            sys.exit(f"voxo did not start:\n{log.read_text()}")
        time.sleep(0.2)
    sys.stdout.write(f"voxo runs at http://127.0.0.1:{port}, log: {log}\n")


def stop(data_dir: Path) -> None:
    """Stop the service that runs on the data dir, and wait until it exits."""
    data_dir = data_dir.resolve()
    pid = Core.server_pid(data_dir)
    if pid is None:
        sys.stdout.write(f"voxo is not running on {data_dir}\n")
        return
    os.kill(pid, signal.SIGTERM)
    while Core.server_pid(data_dir) is not None:
        time.sleep(0.2)
    sys.stdout.write("voxo stopped\n")


def _listens(port: int) -> bool:
    """Whether something takes connections on *port* of 127.0.0.1."""
    try:
        socket.create_connection(("127.0.0.1", port), timeout=1).close()
    except OSError:
        return False
    return True
