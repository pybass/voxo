# voxo

A speech-to-text service for your own server: an app sends it sound and gets the text back.

**Early development.** Dictation and a whole recording work, with a page to try a dictation.

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
- **One token.** Every request that does work carries the token of the service, one for all apps, so
  no stranger uses it. The port listens only on the machine itself; a reverse proxy gives HTTPS to apps
  on other machines.
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
voxo token          # the token every request must carry
voxo stop
```

`voxo start` runs the service in the background and writes its output to `voxo.log` in the data dir. It
does not start again after a reboot or a crash. `voxo serve` runs the service in the terminal. One data dir
takes one service at a time. `--port` and `--data-dir` after a command change the defaults.

### Token

Every request that does work carries the token of the service, one for all apps, as
`Authorization: Bearer <token>`. `voxo token` prints it, and the first call makes it: until then voxo refuses
every request. `voxo token --new` replaces the token, and the old one stops working at once. The token lies in
the file `token` of the data dir.

The port listens only on `127.0.0.1`. For an app on another machine, put a reverse proxy such as Caddy in front
of it: without HTTPS the token would cross the network in the open.

### Models

```sh
voxo download gigaam-v3     # Russian
voxo download parakeet-v3   # 25 European languages, Russian and English among them
```

`voxo download` fetches the files of a model into the data dir. It is the only command that needs the
network, and it works while the service runs. `GET /models` lists the models and says which are downloaded.
The [test page](#test-page) downloads a model too, with a button.

### Dictation

```sh
curl -X POST "http://127.0.0.1:7711/dictations/7f3a?model=gigaam-v3&piece=0" \
  -H "Authorization: Bearer $(voxo token)" \
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

### A whole recording

```sh
curl http://127.0.0.1:7711/v1/audio/transcriptions -H "Authorization: Bearer $(voxo token)" \
  -F file=@meeting.m4a -F model=gigaam-v3
# {"text":"Привет. Проверь, пожалуйста, последний коммит."}
```

An app sends a recording and gets all its text in one answer. The request and the answer are those of the
OpenAI API: a program written for it works with voxo when it is given `http://127.0.0.1:7711/v1` as the address,
the token as the key, and a voxo model. Of the fields of that request, voxo reads only `file` and `model`, and
the answer is always JSON.

- The recording may be in any format `ffmpeg` reads. `ffmpeg` must be installed on the machine
  (`apt install ffmpeg`); nothing else in voxo needs it.
- The answer comes when the whole recording is recognized. An hour of speech takes minutes, so give the request
  no short timeout.

### Test page

`http://127.0.0.1:7711/` is a page to try a dictation by voice: type the token, pick a model, press Start and
speak. The browser keeps the token. For a model that is not downloaded, the button downloads it first. The page
shows the text as it comes, and how long the answers took. Each dictation stays on the page, so the same words
can be said to another model.

For a voxo on a server, open the page at the address of its reverse proxy, or pass the port to your machine
first: `ssh -L 7711:127.0.0.1:7711 <server>`. A browser gives the microphone only to a page of `127.0.0.1` or
of an HTTPS address.

### Page script

`http://127.0.0.1:7711/voxo.js` is the page script. An app takes a copy of it, and gives its pages a route that
passes each request to voxo with the token added.

```js
import { dictate } from "./voxo.js";

const stop = await dictate({
  url: "/dictations", // the route of the app
  params: { model: "gigaam-v3" },
  onAnswer: ({ ended, current }) => {}, // put the text on the page
  onError: (error) => {},
});
await stop(); // frees the microphone and waits for the last answer
```

The comment on `dictate` in the file describes the options.

## Development

You need `uv` and `just`.

```sh
just sync    # install dependencies and Git hooks
just check   # all checks: hooks, lint, types, tests, audit, build
```

[Architecture](docs/architecture.md) holds the rules the code follows.
