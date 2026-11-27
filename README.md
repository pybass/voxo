# voxo

A speech-to-text service for your own server: an app sends it sound and gets the text back.

- **Dictation with live text.** The text appears on the page while the user speaks.
- **A whole recording.** A file in, its text out, in the format of the OpenAI API.
- **A plain server.** The models run on the processor: 4 cores and 2 GB of memory are enough. There is no
  graphics card and no database, and the network is needed only to download a model.

## Install

On a Linux or macOS machine with [uv](https://docs.astral.sh/uv/):

```sh
uv tool install voxo
voxo download parakeet-v3   # a model: 25 European languages, English among them
voxo start                  # the service, at http://127.0.0.1:7711
voxo token                  # the token of the service: every request must carry it
```

`http://127.0.0.1:7711/` is a page to try a dictation by voice: type the token and press Start.

- `voxo stop` stops the service. `voxo token --new` replaces the token. `voxo --help` lists the rest.
- The models and the token are in `~/.local/share/voxo`.
- A whole recording needs `ffmpeg` on the machine.
- `gigaam-v3` is another model, for Russian only.

## Run on a server

`voxo start` does not start again after a reboot. On a server, run `voxo stop` and let systemd run the service.
Here the user `voxo` installed it; the file is `/etc/systemd/system/voxo.service`:

```ini
[Unit]
Description=voxo
After=network.target

[Service]
User=voxo
ExecStart=/home/voxo/.local/bin/voxo serve
Restart=on-failure

[Install]
WantedBy=multi-user.target
```

```sh
systemctl enable --now voxo
```

voxo listens only on `127.0.0.1`, which is all an app on the same machine needs. For an app on another machine,
or to open the test page from your own, put Caddy in front. It gives HTTPS: without it the token crosses the
network in the open, and a browser gives no microphone.

```caddyfile
voxo.example.com {
	reverse_proxy 127.0.0.1:7711
}
```

## Connect an app

The browser talks only to your app, and the app passes its requests to voxo with the token. So the token never
reaches a browser, and your app decides who may dictate.

**1.** Give the app the address of voxo and the token.

**2.** Add two routes that pass a request to voxo as it is. With FastAPI and httpx:

```python
voxo = httpx.AsyncClient(base_url=VOXO_URL, headers={"Authorization": f"Bearer {VOXO_TOKEN}"})


@app.get("/voxo.js")  # the script of the page
async def voxo_script() -> Response:
    answer = await voxo.get("/voxo.js")
    return Response(answer.content, media_type="text/javascript")


@app.post("/dictations")  # the sound: check the sign-in of the user here
async def dictations(request: Request) -> Response:
    answer = await voxo.post("/dictations", params=request.query_params, content=await request.body())
    return Response(answer.content, answer.status_code, media_type="application/json")
```

The two addresses may have any prefix, the same for both: the script sends the sound to `dictations` beside
itself.

**3.** On the page, start and stop a dictation, and put the text where it belongs:

```html
<button id="mic">Dictate</button>
<textarea id="text"></textarea>
<script type="module">
  import { dictate } from "/voxo.js";

  const mic = document.querySelector("#mic");
  const text = document.querySelector("#text");
  let stop = null;
  mic.onclick = async () => {
    if (stop) {
      await stop(); // frees the microphone and waits for the last answer
      stop = null;
      return;
    }
    let done = text.value;
    stop = await dictate({
      params: { model: "parakeet-v3" },
      onAnswer({ ended, current }) {
        done = [done, ...ended].filter(Boolean).join(" "); // the phrases that ended: their text is final
        text.value = [done, current].filter(Boolean).join(" "); // and the phrase still being said
      },
      onError: (error) => alert(error.message),
    });
  };
</script>
```

## A whole recording

```sh
curl http://127.0.0.1:7711/v1/audio/transcriptions -H "Authorization: Bearer $(voxo token)" \
  -F file=@meeting.m4a -F model=parakeet-v3
# {"text":"Hi, please check the last commit."}
```

The recording may be in any format `ffmpeg` reads. A program written for the OpenAI API works too: give it
`http://127.0.0.1:7711/v1` as the address, the token as the key, and a voxo model. An hour of speech takes
minutes, so give the request no short timeout.

`http://127.0.0.1:7711/docs` describes every request.
