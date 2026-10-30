import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

// Migrated files keep their rules by construction; these scans keep them from drifting back.
const web = (name) => readFileSync(new URL(`../../src/asr_en_vi/web/${name}`, import.meta.url), "utf8");
const code = (name) => web(name).replace(/\/\*[\s\S]*?\*\//g, "").replace(/(^|[^:"'`\\])\/\/.*$/gm, "$1");
// Text in quotes goes; the code inside a template literal's ${…} stays, so it is scanned too.
const noStrings = (source) => source
  .replace(/`(?:[^`\\]|\\.)*`/g, (template) => [...template.matchAll(/\$\{([^}]*)\}/g)].map((match) => match[1]).join(";"))
  .replace(/"(?:[^"\\\n]|\\.)*"/g, '""');
// assert.doesNotMatch prints the whole file on failure; say only what matched.
const absent = (source, pattern, label) => assert.equal(source.match(pattern)?.[0], undefined, label);

const VIEWS = ["shell.js", "connections.js", "antigravity.js", "notes.js", "history.js"]; // add each migrated view file here
const CORES = ["shell-core.js", "provider-core.js", "notes-core.js", "history-core.js", "task-core.js", "transcript-core.js", "playback-core.js"];

// Each rule is a pattern over the view source (comments stripped); `rules` returns the labels that match.
const STATE = String.raw`(?:state|(?:\w+\.)?getState\(\)|appState)`;
const rules = (source) => {
  const found = [];
  const hit = (label, pattern) => {
    if (pattern.test(source)) found.push(label);
  };
  hit("assigns into state", new RegExp(String.raw`\b${STATE}(\.[A-Za-z_$][\w$]*|\[[^\]]+\])+\s*(=(?!=)|[-+*/]=|\+\+|--)`));
  // Aliases of the state: const s = state / store.getState(), destructuring it, Object.assign into it.
  hit("aliases or destructures the state", new RegExp(String.raw`\b(const|let|var)\s+[\w$\{\}\s,:[\]]+=\s*${STATE}\s*[;\n]`));
  hit("assigns into state with Object.assign", new RegExp(String.raw`Object\.assign\(\s*${STATE}(?![\w$])`));
  hit("deletes from state", new RegExp(String.raw`\bdelete\s+${STATE}(?![\w$])`));
  hit("calls a mutating method on state", new RegExp(String.raw`\b${STATE}(\.[A-Za-z_$][\w$]*)*\.(push|pop|shift|unshift|splice|sort|reverse|fill|set|delete|add|clear)\(`));
  hit("has a module-level let/var", /(^|\n)(let|var)\s/);
  // Quoted text (a field name another script reads) is not a counter.
  if (/\b\w*(Seq|InFlight|Timer)\b/.test(noStrings(source))) found.push("brings back a request counter or flag");
  const mutates = (name, deep = false) => new RegExp(String.raw`\b${name}(\.[A-Za-z_$][\w$]*|\[[^\]]+\])${deep ? "+" : ""}\s*(=(?!=)|[-+*/]=|\+\+|--)|\b${name}(\.[A-Za-z_$][\w$]*)*\.(push|pop|shift|unshift|splice|sort|reverse|fill|set|delete|add|clear)\(|Object\.assign\(\s*${name}\b`).test(source);
  // A module-level object or collection that the file mutates is state kept outside the store.
  for (const [, name] of source.matchAll(/(?:^|\n)(?:export\s+)?const\s+(\w+)\s*=\s*(?:\{|\[|new\s+(?:Map|Set|WeakMap|WeakSet)\b)/g)) {
    if (mutates(name)) found.push(`mutates module-level ${name}`);
  }
  // A slice of the state held under another name (const s = state.chatgpt) is the state: writing to it is too.
  for (const [, name] of source.matchAll(new RegExp(String.raw`\b(?:const|let|var)\s+(\w+)\s*=\s*${STATE}(?:\.[A-Za-z_$][\w$]*|\[[^\]]+\])*\s*[;\n]`, "g"))) {
    if (mutates(name, true)) found.push(`mutates an alias of the state ${name}`);
  }
  return found;
};

const forbidden = /\b(document|window|fetch|XMLHttpRequest|setTimeout|setInterval|clearTimeout|localStorage|sessionStorage|Date\.now|new Date|Math\.random|navigator|location|crypto|performance|history|requestAnimationFrame)\b/;

test("core files are pure: no DOM, network, timer, storage, clock or randomness", () => {
  for (const name of CORES) absent(noStrings(code(name)), forbidden, name);
});

test("views do not assign into store state or keep module-level mutable state", () => {
  for (const name of VIEWS) assert.deepEqual(rules(code(name)), [], name);
});

test("core purity names crypto, performance, history and animation frames", () => {
  for (const line of ["crypto.randomUUID()", "performance.now()", "history.replaceState(null, '', u)", "requestAnimationFrame(f)"]) {
    assert.ok(forbidden.test(noStrings(line)), line);
  }
});

test("core purity sees code inside template literals", () => {
  assert.ok(forbidden.test(noStrings("const a = `x ${document.title} y`;")));
  assert.ok(!forbidden.test(noStrings('const a = `a fetch ${1}` + "window";')));
});

test("the view rules catch the shapes they exist for", () => {
  const bad = {
    "assigns into state": "state.count = 1;",
    "aliases or destructures the state": "const s = store.getState();\ns.count = 1;",
    "assigns into state with Object.assign": "Object.assign(state, { a: 1 });",
    "deletes from state": "delete state.a;",
    "calls a mutating method on state": "state.list.push(1);",
    "has a module-level let/var": "let current = null;",
    "brings back a request counter or flag": "const loadSeq = 0;",
    "mutates module-level cache": "const cache = {};\ncache.a = 1;",
  };
  for (const [label, source] of Object.entries(bad)) assert.ok(rules(source).includes(label), label);
  assert.ok(rules("const loadSeq = 0;").includes("brings back a request counter or flag"));
  assert.ok(!rules('const d = { "xInFlight": 1 };').includes("brings back a request counter or flag"));
  assert.ok(rules("const pollTimer = 0;").includes("brings back a request counter or flag"));
  assert.ok(rules("store.getState().x = 1;").includes("assigns into state"));
  assert.ok(rules("Object.assign(store.getState(), {});").includes("assigns into state with Object.assign"));
  assert.ok(rules("delete store.getState().a;").includes("deletes from state"));
  assert.ok(rules("export const cache = {};\ncache.a = 1;").includes("mutates module-level cache"));
  assert.ok(rules("const items = [];\nitems.push(1);").includes("mutates module-level items"));
  assert.ok(rules("const s = state.chatgpt;\ns.count = 1;").includes("mutates an alias of the state s"));
  assert.ok(rules("const c = store.getState().choice;\nc.status.chatgpt = 1;").includes("mutates an alias of the state c"));
  assert.ok(rules("const c = store.getState().choice;\nc.list[0].x++;").includes("mutates an alias of the state c"));
  assert.ok(rules("const list = store.getState().items;\nlist.push(1);").includes("mutates an alias of the state list"));
  assert.ok(rules("const { a } = store.getState();").includes("aliases or destructures the state"));
  // Reading a slice and writing DOM properties is what a view does.
  assert.deepEqual(rules("const els = { a: document.body };\nels.a.hidden = true;\nconst s = state.chatgpt;\nrender(s);"), []);
});

test("views touch storage only to read the remembered choices for the boot and open actions", () => {
  for (const name of VIEWS) {
    // The runner dependencies hand storage to the storage effect; nothing else may touch it.
    const source = code(name).replace(/\n\s*storage: \{.*\},/, "");
    absent(source, /\.(setItem|removeItem|clear)\(/, `${name} writes storage outside an effect`);
    const reader = source.match(/function readStored\([^)]*\) \{[\s\S]*?\n\}/);
    const outside = reader ? source.replace(reader[0], "") : source;
    absent(outside, /localStorage|sessionStorage|getItem/, `${name} reads storage outside readStored`);
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

test("shell.html loads each view as a module; the unmigrated scripts stay deferred", () => {
  const html = web("shell.html");
  const order = [...html.matchAll(/<script[^>]*src="\/assets\/([\w-]+\.js)"[^>]*>/g)].map((match) => [match[1], match[0]]);
  const names = order.map(([name]) => name);
  assert.ok(names.indexOf("shell.js") < names.indexOf("history.js"));
  assert.match(order[names.indexOf("shell.js")][1], /type="module"/);
  for (const [name, tag] of order.filter(([name]) => !["i18n.js", "theme.js", ...VIEWS].includes(name))) {
    assert.match(tag, /\bdefer\b/, name);
  }
  for (const name of VIEWS) assert.match(order[names.indexOf(name)][1], /type="module"/, name);
  // Both provider views run in document order, the core's owner first.
  assert.ok(names.indexOf("connections.js") < names.indexOf("antigravity.js"));
});
