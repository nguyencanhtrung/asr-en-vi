// Cuts the audio track out of a video file in the browser by copying its packets (no decode, no re-encode),
// so a long meeting video reaches the server as a small audio file. Loaded on the first video file only.
// Any problem throws an Error with a `kind` ("unsupported" | "no-audio" | "codec" | "failed"); the caller then
// uploads the original file. The vendored library is unmodified: see vendor/mediabunny/PROVENANCE.md.
import {
  ALL_FORMATS,
  BlobSource,
  BufferTarget,
  Conversion,
  Input,
  Mp4OutputFormat,
  Output,
  WebMOutputFormat,
} from "./vendor/mediabunny/mediabunny.min.mjs";

const fail = (kind, message) => Object.assign(new Error(message), { kind });

// container of the source -> the audio codec we can copy and the file we write it into.
const TARGETS = {
  ".mp4": { codec: "aac", format: () => new Mp4OutputFormat(), extension: ".m4a", type: "audio/mp4" },
  ".mov": { codec: "aac", format: () => new Mp4OutputFormat(), extension: ".m4a", type: "audio/mp4" },
  ".webm": { codec: "opus", format: () => new WebMOutputFormat(), extension: ".webm", type: "audio/webm" },
};

export async function extractAudio(file, { signal, onProgress } = {}) {
  const dot = file.name.lastIndexOf(".");
  const target = TARGETS[dot >= 0 ? file.name.slice(dot).toLowerCase() : ""];
  if (!target) throw fail("unsupported", "not a video container");
  signal?.throwIfAborted();
  const input = new Input({ source: new BlobSource(file), formats: ALL_FORMATS });
  let conversion = null;
  const onAbort = () => conversion?.cancel();
  signal?.addEventListener("abort", onAbort);
  try {
    const track = await input.getPrimaryAudioTrack();
    if (!track) throw fail("no-audio", "no audio track");
    if (track.codec !== target.codec) throw fail("codec", `audio codec ${track.codec} cannot be copied`);
    const bufferTarget = new BufferTarget();
    const output = new Output({ format: target.format(), target: bufferTarget });
    conversion = await Conversion.init({
      input,
      output,
      video: { discard: true },
      audio: { forceTranscode: false },
      copy: { mode: "forced" }, // never fall back to a transcode
      showWarnings: false,
    });
    if (!conversion.isValid || conversion.discardedTracks.some((entry) => entry.track === track)) {
      throw fail("codec", "audio track cannot be copied");
    }
    conversion.onProgress = (ratio) => onProgress?.(ratio);
    signal?.throwIfAborted();
    await conversion.execute();
    signal?.throwIfAborted();
    const stem = dot >= 0 ? file.name.slice(0, dot) : file.name;
    return new File([bufferTarget.buffer], `${stem}${target.extension}`, { type: target.type });
  } catch (error) {
    if (signal?.aborted) throw signal.reason ?? error;
    throw error.kind ? error : fail("failed", String(error?.message ?? error));
  } finally {
    signal?.removeEventListener("abort", onAbort);
    input.dispose();
  }
}
