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

### Models

```sh
voxo download gigaam-v3     # Russian
voxo download parakeet-v3   # 25 European languages, Russian and English among them
```

`voxo download` fetches the files of a model into the data dir. It is the only command that needs the
network, and it works while the service runs. `GET /models` lists the models and says which are downloaded.

## Development

You need `uv` and `just`.

```sh
just sync    # install dependencies and Git hooks
just check   # all checks: hooks, lint, types, tests, audit, build
```

[Architecture](docs/architecture.md) holds the rules the code follows.
