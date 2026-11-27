/**
 * The browser half of a voxo dictation: it takes the sound of the microphone and sends it, piece by piece, to the
 * server of the page, which passes each piece to voxo. It has no dependencies and draws nothing. An app gives its
 * pages this file from voxo, at an address of its own. The browser runs the file twice: the page imports it, and
 * `dictate` loads it into the audio thread, where only the block below does anything.
 */

const RATE = 16000; // samples in a second of the sound voxo takes

if (globalThis.AudioWorkletProcessor) {
  // The audio thread: pass each block of the sound of the microphone to the page.
  registerProcessor(
    "voxo",
    class extends AudioWorkletProcessor {
      process([[block]]) {
        // A copy: the browser fills the same memory with the next block.
        if (block) this.port.postMessage(block.slice());
        return true;
      }
    },
  );
}

/**
 * Start a dictation: ask for the microphone and send its sound in pieces of about half a second, each only after
 * the answer to the one before. When the server is slow, the pieces get longer and no sound is lost.
 *
 * A piece goes as `POST {url}?id={id}&piece={number}` with the sound as the body, and the last one adds
 * `last=true`: the same request voxo takes. The server of the page checks who asks, adds the token of voxo, and
 * passes the request on as it is.
 *
 * Rejects when the dictation cannot start, as when the user refuses the microphone.
 *
 * @param {object} options
 * @param {string | URL} [options.url] Where the server of the page takes dictations. By default `dictations`
 *   beside this file: `/dictations` for a file at `/voxo.js`.
 * @param {Record<string, string>} [options.params] More query parameters for every request, such as the model.
 * @param {Record<string, string>} [options.headers] More headers for every request. A page of an app needs none:
 *   its server adds the token of voxo.
 * @param {(answer: {ended: string[], current: string}, seconds: number) => void} options.onAnswer Called with the
 *   answer to each piece, and how long its request took. Add `ended` to the text; show `current` after the text
 *   until the next answer.
 * @param {(error: Error) => void} options.onError Called once when the dictation fails. It is then over, and the
 *   microphone is free.
 * @returns {Promise<() => Promise<void>>} A function that ends the dictation: it frees the microphone at once,
 *   and its promise resolves after the answer to the last piece, or after `onError`.
 */
export async function dictate({ url = new URL("dictations", import.meta.url), params = {}, headers = {}, onAnswer, onError }) {
  // At the rate voxo takes: the browser turns the sound of the microphone into it.
  const context = new AudioContext({ sampleRate: RATE });
  let stream;
  try {
    // The microphone comes last, so that nothing is said into it before the page listens.
    await context.audioWorklet.addModule(import.meta.url);
    stream = await navigator.mediaDevices.getUserMedia({ audio: true });
  } catch (error) {
    context.close();
    throw error;
  }
  const release = () => {
    for (const track of stream.getTracks()) track.stop();
    if (context.state !== "closed") context.close();
  };
  let blocks = []; // the sound not sent yet
  let heard = 0; // samples in `blocks`
  let stopped = false;
  let wake = () => {}; // ends the wait of the loop below
  const node = new AudioWorkletNode(context, "voxo", { numberOfOutputs: 0 });
  node.port.onmessage = ({ data }) => {
    blocks.push(data);
    heard += data.length;
    wake();
  };
  context.createMediaStreamSource(stream).connect(node);

  const id = crypto.randomUUID();
  const over = (async () => {
    for (let piece = 0; ; piece += 1) {
      while (!stopped && heard < RATE / 2) await new Promise((resolve) => (wake = resolve));
      const last = stopped;
      const sound = new Int16Array(heard);
      let at = 0;
      for (const block of blocks) {
        // Clamped: a sample past the range would wrap around in 16 bits.
        for (const sample of block) sound[at++] = Math.max(-1, Math.min(1, sample)) * 32767;
      }
      blocks = [];
      heard = 0;
      const started = performance.now();
      const address = `${url}?${new URLSearchParams({ ...params, id, piece, ...(last && { last }) })}`;
      const answer = await post(address, headers, sound);
      onAnswer(answer, (performance.now() - started) / 1000);
      if (last) return;
    }
  })().catch((error) => {
    release();
    onError(error);
  });
  return () => {
    stopped = true;
    release();
    wake();
    return over;
  };
}

/**
 * Send one piece and give the answer as an object. A request the network failed is sent again, three times in
 * all: voxo adds the sound of a piece it has got before only once. Throws when the network keeps failing, and
 * when the server answers with an error.
 */
async function post(address, headers, sound) {
  for (let attempt = 1; ; attempt += 1) {
    let response;
    try {
      response = await fetch(address, {
        method: "POST",
        headers: { ...headers, "Content-Type": "application/octet-stream" },
        body: sound,
      });
    } catch (error) {
      if (attempt === 3) throw error;
      await new Promise((resolve) => setTimeout(resolve, 500));
      continue;
    }
    if (!response.ok) throw new Error(`${response.status} ${await response.text()}`);
    return response.json();
  }
}
