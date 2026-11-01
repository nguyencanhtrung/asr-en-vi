import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import vm from "node:vm";

const script = readFileSync(new URL("../../src/asr_studio/web/i18n.js", import.meta.url), "utf8");
function storage(entries = {}) {
  const values = new Map(Object.entries(entries));
  return {
    get length() { return values.size; },
    key: (index) => [...values.keys()][index] ?? null,
    getItem: (key) => values.get(key) ?? null,
    setItem: (key, value) => values.set(key, String(value)),
    removeItem: (key) => values.delete(key),
  };
}
function load(window) {
  const document = { documentElement: {}, addEventListener() {} };
  const context = vm.createContext({ window, document });
  vm.runInContext(script, context);
  return document;
}

test("rebrand migrates preferences and pending requests before selecting language", () => {
  const localStorage = storage({
    "asr-en-vi:lang": "en", "asr-en-vi:theme": "dark",
    "asr-en-vi:notes-request-v2:m1": '{"request_id":"keep-me"}', unrelated: "keep",
  });
  const sessionStorage = storage({ "asr-en-vi:auto-transcribe:m1": "0" });
  assert.equal(load({ localStorage, sessionStorage }).documentElement.lang, "en");
  assert.equal(localStorage.getItem("asr-studio:theme"), "dark");
  assert.equal(localStorage.getItem("asr-studio:notes-request-v2:m1"), '{"request_id":"keep-me"}');
  assert.equal(sessionStorage.getItem("asr-studio:auto-transcribe:m1"), "0");
  assert.equal(localStorage.getItem("asr-en-vi:theme"), null);
  assert.equal(localStorage.getItem("unrelated"), "keep");
  // Clearing a preference remains cleared on the next load.
  localStorage.removeItem("asr-studio:theme");
  load({ localStorage, sessionStorage });
  assert.equal(localStorage.getItem("asr-studio:theme"), null);
});

test("rebrand preserves newer preferences over legacy values", () => {
  const localStorage = storage({ "asr-en-vi:lang": "en", "asr-studio:lang": "vi" });
  assert.equal(load({ localStorage, sessionStorage: storage() }).documentElement.lang, "vi");
  assert.equal(localStorage.getItem("asr-en-vi:lang"), null);
});

test("blocked storage does not prevent opening the page", () => {
  const window = {};
  for (const key of ["localStorage", "sessionStorage"]) {
    Object.defineProperty(window, key, { get() { throw new Error("Storage blocked"); } });
  }
  assert.equal(load(window).documentElement.lang, "vi");
});

test("a failed storage copy retains the original pending request", () => {
  const localStorage = storage({ "asr-en-vi:notes-request-v2:m1": "request" });
  localStorage.setItem = () => { throw new Error("Quota exceeded"); };
  load({ localStorage, sessionStorage: storage() });
  assert.equal(localStorage.getItem("asr-en-vi:notes-request-v2:m1"), "request");
});
