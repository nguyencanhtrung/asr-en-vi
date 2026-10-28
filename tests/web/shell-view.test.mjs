import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

// Migrated files keep their rules by construction; these scans keep them from drifting back.
const web = (name) => readFileSync(new URL(`../../src/asr_en_vi/web/${name}`, import.meta.url), "utf8");
const code = (name) => web(name).replace(/\/\*[\s\S]*?\*\//g, "").replace(/(^|[^:"'`\\])\/\/.*$/gm, "$1");
const noStrings = (source) => source.replace(/"(?:[^"\\\n]|\\.)*"|`(?:[^`\\]|\\.)*`/g, '""');
// assert.doesNotMatch prints the whole file on failure; say only what matched.
const absent = (source, pattern, label) => assert.equal(source.match(pattern)?.[0], undefined, label);

const VIEWS = ["shell.js"]; // add each migrated view file here
const CORES = ["shell-core.js"];

test("core files are pure: no DOM, network, timer, storage, clock or randomness", () => {
  const forbidden = /\b(document|window|fetch|XMLHttpRequest|setTimeout|setInterval|clearTimeout|localStorage|sessionStorage|Date\.now|new Date|Math\.random|navigator|location)\b/;
  for (const name of CORES) absent(noStrings(code(name)), forbidden, name);
});

test("views do not assign into store state or keep module-level mutable state", () => {
  for (const name of VIEWS) {
    const source = code(name);
    const assignsState = /\b(state|getState\(\)|appState)(\.[A-Za-z_$][\w$]*|\[[^\]]+\])+\s*(=(?!=)|[-+*/]=|\+\+|--)/;
    absent(source, assignsState, `${name} assigns into state`);
    // Aliases of the state: const s = state / getState(), destructuring it, Object.assign into it.
    absent(source, /\b(const|let|var)\s+[\w${}\s,:[\]]+=\s*(state|getState\(\)|appState)\s*[;\n]/, `${name} aliases or destructures the state`);
    absent(source, /Object\.assign\(\s*(state|getState\(\)|appState)\b/, `${name} assigns into state with Object.assign`);
    absent(source, /(^|\n)(let|var)\s/, `${name} has a module-level let/var`);
    absent(source, /\b\w*(Seq|InFlight)\b/, `${name} brings back a request counter or flag`);
  }
});

test("views touch storage only to read the remembered choices for the open action", () => {
  for (const name of VIEWS) {
    // The runner dependencies hand storage to the storage effect; nothing else may touch it.
    const source = code(name).replace(/\n\s*storage: \{.*\},/, "");
    absent(source, /\.(setItem|removeItem|clear)\(/, `${name} writes storage outside an effect`);
    absent(source, /sessionStorage/, `${name} reads sessionStorage`);
    const readers = source.match(/function readStored\(\) \{[\s\S]*?\n\}/);
    assert.ok(readers, "readStored exists");
    const outside = source.replace(readers[0], "");
    absent(outside, /localStorage|getItem/, `${name} reads storage outside readStored`);
  }
});

test("shell.js publishes every helper the unmigrated scripts still call", () => {
  const published = web("shell.js").match(/Object\.assign\(window, \{([^}]*)\}\)/);
  assert.ok(published, "window publication exists");
  const names = published[1].split(",").map((name) => name.trim());
  for (const script of ["history.js", "notes.js", "connections.js", "antigravity.js"]) {
    const source = code(script);
    for (const name of ["ApiError", "requestJson", "meetingIdFromPath", "formatMeetingDate", "sameOriginAudioSource"]) {
      if (new RegExp(`\\b${name}\\b`).test(source)) assert.ok(names.includes(name), `${script} uses ${name}`);
    }
  }
  for (const name of ["ApiError", "requestJson", "meetingIdFromPath", "formatMeetingDate", "sameOriginAudioSource"]) {
    assert.ok(names.includes(name), name);
  }
});

test("shell.html loads the view as a module before the unmigrated deferred scripts", () => {
  const html = web("shell.html");
  const order = [...html.matchAll(/<script[^>]*src="\/assets\/([\w-]+\.js)"[^>]*>/g)].map((match) => [match[1], match[0]]);
  const names = order.map(([name]) => name);
  assert.ok(names.indexOf("shell.js") < names.indexOf("history.js"));
  assert.match(order[names.indexOf("shell.js")][1], /type="module"/);
  for (const [name, tag] of order.filter(([name]) => !["i18n.js", "theme.js", "shell.js"].includes(name))) {
    assert.match(tag, /\bdefer\b/, name);
  }
});
