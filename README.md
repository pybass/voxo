# voxo

A speech-to-text service for your own server: an app sends it sound and gets the text back.

**Early development.** The service starts and stops, but recognizes nothing yet.

## Usage

```sh
uv tool install .   # in a checkout of this repository
voxo start          # http://127.0.0.1:7711, data in ~/.local/share/voxo
voxo stop
```

`voxo start` runs the service in the background and writes its output to `voxo.log` in the data dir. It
does not start again after a reboot or a crash. `voxo serve` runs the service in the terminal. One data dir
takes one service at a time. `--port` and `--data-dir` after a command change the defaults.

The port listens only on `127.0.0.1` and asks for no token: it is for apps on the same machine.

## Development

You need `uv` and `just`.

```sh
just sync    # install dependencies and Git hooks
just check   # all checks: hooks, lint, types, tests, audit, build
```
