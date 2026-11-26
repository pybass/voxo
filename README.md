# voxo

A speech-to-text service for your own server: an app sends it sound and gets the text back.

**Early development.** Dictation works on the local port; the rest of the goals is not built yet.

## Goals

What voxo is meant to become. Only what [Usage](#usage) shows works today.

- **A separate service.** Any app may use voxo, and voxo knows nothing about the apps. Users and
  rights are the work of each app.
- **Dictation with live text.** A page sends the sound of the microphone in pieces of about half a
  second. voxo finds the pauses itself and splits the speech into phrases. It recognizes the current
  phrase again with every piece, so the text updates as the user speaks and becomes final after a pause.
- **A whole recording.** An app sends a recording and gets its text back, in the common OpenAI format.
- **Several models.** The app names the model in every request, so the models can be compared on real
  speech. voxo is tied to none of them: a model is one entry in a list. A model is loaded into memory
  at its first use.
- **A plain server.** The models run on the processor; no graphics card is needed.
- **No network at work.** The internet is needed only to download a model.
- **Nothing to look after.** The state of a dictation lives in memory. There is no database.
- **Plain requests.** HTTP requests, no WebSocket: the time goes to the model, not to the transport.
- **Two ports.** The local port is for apps on the same machine and asks for no token. An outer port,
  off until the admin turns it on, always asks for one. Each app has its own token, and voxo keeps
  only a hash of it.
- **A page script.** One JavaScript file with no dependencies is the browser half of a dictation. It
  draws nothing, and an app takes a copy of it. The browser talks only to its own app, which passes
  the sound to voxo, so a token never reaches a browser.
- **Well-known libraries only.** voxo depends only on widely used libraries. The models run on
  sherpa-onnx.

Out of scope: text to speech, turning what was said into the fields of a record with an LLM, and
models that stream by themselves.

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

### Dictation

```sh
curl -X POST "http://127.0.0.1:7711/dictations/7f3a?model=gigaam-v3&piece=0" \
  -H "Content-Type: application/octet-stream" --data-binary @piece0.pcm
# {"ended":[],"current":"Привет, проверь"}
```

An app sends the sound of a dictation in pieces of about half a second, each as the body of a request: mono,
16 kHz, 16-bit little-endian samples with no header. It makes up the id of the dictation, new for each one,
and numbers the pieces from 0. It sends the next piece only after the answer to the one before.

- `ended` holds the phrases the piece ended. Their text is final: add it to the text of the dictation.
- `current` is the phrase still being said. Show it after that text, and replace it with the next `current`.
- `last=true` on a piece ends the dictation, and what was being said comes in `ended`.

`http://127.0.0.1:7711/docs` has the rest: a piece sent again, a forgotten dictation, and the errors.

## Development

You need `uv` and `just`.

```sh
just sync    # install dependencies and Git hooks
just check   # all checks: hooks, lint, types, tests, audit, build
```

[Architecture](docs/architecture.md) holds the rules the code follows.
