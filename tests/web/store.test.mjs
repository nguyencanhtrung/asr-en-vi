import assert from "node:assert/strict";
import test from "node:test";

import { combine, createRunner, createStore } from "../../src/asr_en_vi/web/store.js";

const tick = () => new Promise((resolve) => setImmediate(resolve));

function fakeFetch() {
  const calls = [];
  const fetch = (url, init) =>
    new Promise((resolve, reject) => {
      calls.push({ url, init, resolve, reject });
    });
  fetch.calls = calls;
  return fetch;
}

const reply = (status, body) => ({ ok: status < 400, status, text: async () => JSON.stringify(body) });

function fakeTimers() {
  const pending = new Map();
  let next = 1;
  return {
    setTimeout: (fn, delay) => (pending.set(next, { fn, delay }), next++),
    clearTimeout: (id) => pending.delete(id),
    pending,
    fire: () => [...pending.entries()].forEach(([id, { fn }]) => (pending.delete(id), fn())),
  };
}

// Feature: load an item; the reducer keeps the id of the latest request and ignores other replies.
function loader(runner) {
  const reduce = (state, action) => {
    switch (action.type) {
      case "load": {
        const id = state.lastId + 1;
        return {
          state: { ...state, lastId: id, loading: true },
          effects: [{ type: "fetch", key: action.key ?? "load", url: `/item/${action.name}`, ok: "loaded", error: "failed", meta: { id } }],
        };
      }
      case "stop":
        return { state, effects: [{ type: "cancel", key: "load" }] };
      case "loaded":
        if (action.meta.id !== state.lastId) return { state };
        return { state: { ...state, loading: false, value: action.response.body.name } };
      case "failed":
        if (action.meta.id !== state.lastId) return { state };
        return { state: { ...state, loading: false, error: action.error } };
      default:
        return { state };
    }
  };
  const initialState = { lastId: 0, loading: false, value: null, error: null };
  return { reduce, initialState, run: runner };
}

function setup() {
  const fetch = fakeFetch();
  const timers = fakeTimers();
  const run = createRunner({ fetch, ...timers });
  return { fetch, timers, store: createStore(loader(run)) };
}

test("reducer drops a reply whose request id is stale", () => {
  const { store } = setup();
  store.dispatch({ type: "load", name: "a" });
  store.dispatch({ type: "load", name: "b" });
  store.dispatch({ type: "loaded", meta: { id: 1 }, response: { body: { name: "a" } } });
  assert.equal(store.getState().value, null);
  assert.equal(store.getState().loading, true);
  store.dispatch({ type: "loaded", meta: { id: 2 }, response: { body: { name: "b" } } });
  assert.equal(store.getState().value, "b");
});

test("replies arriving out of order: the latest request wins", async () => {
  const { fetch, store } = setup();
  store.dispatch({ type: "load", name: "a", key: "k1" });
  store.dispatch({ type: "load", name: "b", key: "k2" }); // different key: both stay in flight
  fetch.calls[1].resolve(reply(200, { name: "b" }));
  await tick();
  fetch.calls[0].resolve(reply(200, { name: "a" }));
  await tick();
  assert.equal(store.getState().value, "b");
});

test("a new fetch with the same key aborts and silences the previous one", async () => {
  const { fetch, store } = setup();
  store.dispatch({ type: "load", name: "a" });
  store.dispatch({ type: "load", name: "b" });
  assert.equal(fetch.calls[0].init.signal.aborted, true);
  assert.equal(fetch.calls[1].init.signal.aborted, false);
  fetch.calls[0].reject(Object.assign(new Error("aborted"), { name: "AbortError" }));
  fetch.calls[1].resolve(reply(200, { name: "b" }));
  await tick();
  assert.equal(store.getState().value, "b");
  assert.equal(store.getState().error, null);
});

test("network failure becomes an error action", async () => {
  const { fetch, store } = setup();
  store.dispatch({ type: "load", name: "a" });
  fetch.calls[0].reject(new TypeError("Failed to fetch"));
  await tick();
  assert.deepEqual(store.getState().error, { message: "Failed to fetch" });
  assert.equal(store.getState().loading, false);
});

test("HTTP error status becomes an error action with status and body", async () => {
  const { fetch, store } = setup();
  store.dispatch({ type: "load", name: "a" });
  fetch.calls[0].resolve(reply(409, { detail: "busy" }));
  await tick();
  assert.deepEqual(store.getState().error, { message: "HTTP 409", status: 409, body: { detail: "busy" } });
});

test("cancel mid-flight aborts the request and dispatches nothing", async () => {
  const { fetch, store } = setup();
  store.dispatch({ type: "load", name: "a" });
  const seen = [];
  store.subscribe((state) => seen.push(state));
  store.dispatch({ type: "stop" });
  assert.equal(fetch.calls[0].init.signal.aborted, true);
  fetch.calls[0].resolve(reply(200, { name: "late" }));
  await tick();
  assert.deepEqual(seen, []);
  assert.equal(store.getState().value, null);
});

test("schedule fires its action; replacing or cancelling clears the timer", () => {
  const timers = fakeTimers();
  const run = createRunner({ fetch: fakeFetch(), ...timers });
  const dispatched = [];
  const dispatch = (action) => dispatched.push(action);
  run({ type: "schedule", key: "t", delay: 100, action: { type: "first" } }, dispatch);
  run({ type: "schedule", key: "t", delay: 200, action: { type: "second" } }, dispatch);
  assert.equal(timers.pending.size, 1);
  timers.fire();
  assert.deepEqual(dispatched, [{ type: "second" }]);
  run({ type: "schedule", key: "t", delay: 100, action: { type: "third" } }, dispatch);
  run({ type: "cancel", key: "t" }, dispatch);
  assert.equal(timers.pending.size, 0);
});

test("unknown effect type throws", () => {
  const run = createRunner({ fetch: fakeFetch(), ...fakeTimers() });
  assert.throws(() => run({ type: "nope", key: "k" }, () => {}), /unknown effect type/);
});

test("dispatch while busy is queued FIFO without re-entering the reducer", () => {
  const order = [];
  let depth = 0;
  const store = createStore({
    initialState: { log: [] },
    reduce: (state, action) => {
      assert.equal(++depth, 1, "reducer re-entered");
      order.push(action.type);
      depth--;
      const effects = action.type === "a" ? [{ type: "emit" }] : [];
      return { state: { log: [...state.log, action.type] }, effects };
    },
    run: (effect, dispatch) => dispatch({ type: "from-effect" }),
  });
  store.subscribe((state) => {
    if (state.log.length === 2) store.dispatch({ type: "from-subscriber" });
  });
  store.dispatch({ type: "a" });
  store.dispatch({ type: "b" });
  assert.deepEqual(order, ["a", "from-effect", "from-subscriber", "b"]);
  assert.deepEqual(store.getState().log, ["a", "from-effect", "from-subscriber", "b"]);
});

test("subscribers run once per drained dispatch and only when state changed", () => {
  const store = createStore({
    initialState: { n: 0 },
    reduce: (state, action) => (action.type === "inc" ? { state: { n: state.n + 1 } } : { state }),
  });
  const seen = [];
  const unsubscribe = store.subscribe((state) => seen.push(state.n));
  store.dispatch({ type: "noop" });
  assert.deepEqual(seen, []);
  store.dispatch({ type: "inc" });
  assert.deepEqual(seen, [1]);
  unsubscribe();
  store.dispatch({ type: "inc" });
  assert.deepEqual(seen, [1]);
});

test("a throwing reducer leaves the store usable", () => {
  const store = createStore({
    initialState: { n: 0 },
    reduce: (state, action) => {
      if (action.type === "boom") throw new Error("boom");
      return { state: { n: state.n + 1 } };
    },
  });
  assert.throws(() => store.dispatch({ type: "boom" }), /boom/);
  store.dispatch({ type: "inc" });
  assert.equal(store.getState().n, 1);
});

test("combine routes every action to every feature and joins their effects", () => {
  const counter = (state = 0, action) => ({ state: action.type === "inc" ? state + 1 : state });
  const logger = (state = [], action) => ({
    state: [...state, action.type],
    effects: action.type === "inc" ? [{ type: "cancel", key: "x" }] : undefined,
  });
  const reduce = combine({ counter, logger });
  const initial = { counter: 0, logger: [] };
  const result = reduce(initial, { type: "inc" });
  assert.deepEqual(result.state, { counter: 1, logger: ["inc"] });
  assert.deepEqual(result.effects, [{ type: "cancel", key: "x" }]);
  const same = combine({ counter })({ counter: 0 }, { type: "other" });
  assert.equal(same.state.counter, 0);
  const initialRef = { counter: 0 };
  assert.equal(combine({ counter })(initialRef, { type: "other" }).state, initialRef);
});

test("a stale error reply is ignored and error actions carry meta", async () => {
  const { fetch, store } = setup();
  store.dispatch({ type: "load", name: "a", key: "k1" });
  store.dispatch({ type: "load", name: "b", key: "k2" });
  fetch.calls[1].resolve(reply(200, { name: "b" }));
  await tick();
  fetch.calls[0].reject(new TypeError("late failure")); // meta id 1 is stale
  await tick();
  assert.equal(store.getState().error, null);
  const seen = [];
  const bad = fakeFetch();
  createRunner({ fetch: bad, ...fakeTimers() })({ type: "fetch", key: "m", url: "/x", ok: "ok", error: "bad", meta: { id: 7 } }, (action) => seen.push(action));
  bad.calls[0].reject(new Error("down"));
  await tick();
  assert.deepEqual(seen, [{ type: "bad", error: { message: "down" }, meta: { id: 7 } }]);
});

test("a non-JSON body falls back to text", async () => {
  const fetch = fakeFetch();
  const seen = [];
  createRunner({ fetch, ...fakeTimers() })({ type: "fetch", key: "t", url: "/x", ok: "ok", error: "bad" }, (action) => seen.push(action));
  fetch.calls[0].resolve({ ok: true, status: 200, text: async () => "plain text" });
  await tick();
  assert.equal(seen[0].response.body, "plain text");
});

test("fetch, schedule and cancel effects need a key", () => {
  const run = createRunner({ fetch: fakeFetch(), ...fakeTimers() });
  for (const type of ["fetch", "schedule", "cancel"]) assert.throws(() => run({ type }, () => {}), /needs a key/);
});

test("an exception thrown while handling a fetch result is not swallowed", async () => {
  const fetch = fakeFetch();
  const run = createRunner({ fetch, ...fakeTimers() });
  const saved = process.listeners("unhandledRejection"); // node:test would fail the run on it
  process.removeAllListeners("unhandledRejection");
  const caught = new Promise((resolve) => process.once("unhandledRejection", resolve));
  run({ type: "fetch", key: "u", url: "/x", ok: "ok", error: "bad" }, () => {
    throw new Error("render failed");
  });
  fetch.calls[0].resolve(reply(200, {}));
  const error = await caught;
  saved.forEach((listener) => process.on("unhandledRejection", listener));
  assert.match(error.message, /render failed/);
});

test("FIFO order holds across effects dispatching their own actions", () => {
  const order = [];
  const store = createStore({
    initialState: {},
    reduce: (state, action) => {
      order.push(action.type);
      const effects = { a: [{ emit: "x" }, { emit: "y" }], x: [{ emit: "z" }] }[action.type];
      return { state, effects };
    },
    run: (effect, dispatch) => dispatch({ type: effect.emit }),
  });
  store.dispatch({ type: "a" });
  assert.deepEqual(order, ["a", "x", "y", "z"]);
});

test("combine keeps the effects of every feature in order", () => {
  const feature = (name) => (state = 0, action) => ({ state, effects: [{ type: "cancel", key: name }] });
  const result = combine({ one: feature("one"), two: feature("two") })({ one: 0, two: 0 }, { type: "go" });
  assert.deepEqual(result.effects.map((effect) => effect.key), ["one", "two"]);
});

test("schedule passes its delay to setTimeout", () => {
  const timers = fakeTimers();
  createRunner({ fetch: fakeFetch(), ...timers })({ type: "schedule", key: "d", delay: 250, action: { type: "t" } }, () => {});
  assert.equal([...timers.pending.values()][0].delay, 250);
});

test("a throwing reducer drops the queued actions and keeps the last good state", () => {
  const seen = [];
  const store = createStore({
    initialState: { log: [] },
    reduce: (state, action) => {
      if (action.type === "boom") throw new Error("boom");
      return { state: { log: [...state.log, action.type] }, effects: action.type === "a" ? [{ emit: "boom" }, { emit: "later" }] : [] };
    },
    run: (effect, dispatch) => dispatch({ type: effect.emit }),
  });
  store.subscribe((state) => seen.push(state.log));
  assert.throws(() => store.dispatch({ type: "a" }), /boom/);
  assert.deepEqual(store.getState().log, ["a"]); // state kept up to the last action that ran
  assert.deepEqual(seen, []); // subscribers were not told about the half-drained batch
  store.dispatch({ type: "b" }); // "later" was dropped with the queue
  assert.deepEqual(store.getState().log, ["a", "b"]);
  assert.deepEqual(seen, [["a", "b"]]);
});

test("an error thrown by a schedule callback reaches the timer, not the store", () => {
  const timers = fakeTimers();
  const run = createRunner({ fetch: fakeFetch(), ...timers });
  run({ type: "schedule", key: "s", delay: 1, action: { type: "tick" } }, () => {
    throw new Error("render failed");
  });
  assert.throws(() => timers.fire(), /render failed/);
});

function fakeXhr() {
  const instances = [];
  class FakeXhr {
    constructor() {
      this.headers = {};
      this.upload = {};
      this.aborted = false;
      instances.push(this);
    }
    open(method, url, async) {
      Object.assign(this, { method, url, async });
    }
    setRequestHeader(name, value) {
      this.headers[name] = value;
    }
    send(body) {
      this.body = body;
    }
    abort() {
      this.aborted = true;
    }
  }
  FakeXhr.instances = instances;
  return FakeXhr;
}

test("upload effect reports progress and the final answer with meta", () => {
  const XMLHttpRequest = fakeXhr();
  const seen = [];
  const run = createRunner({ fetch: fakeFetch(), ...fakeTimers(), XMLHttpRequest });
  run({ type: "upload", key: "f/u", url: "/up", headers: { "Content-Type": "x/y" }, body: "FILE", ok: "ok", error: "bad", progress: "prog", meta: { run: 1 } }, (a) => seen.push(a));
  const [xhr] = XMLHttpRequest.instances;
  assert.deepEqual([xhr.method, xhr.url, xhr.async, xhr.withCredentials, xhr.body, xhr.headers], ["PUT", "/up", true, true, "FILE", { "Content-Type": "x/y" }]);
  xhr.upload.onprogress({ loaded: 5, total: 10, lengthComputable: true });
  xhr.status = 204;
  xhr.responseText = '{"a":1}';
  xhr.onload();
  assert.deepEqual(seen, [
    { type: "prog", loaded: 5, total: 10, lengthComputable: true, meta: { run: 1 } },
    { type: "ok", response: { status: 204, body: { a: 1 } }, meta: { run: 1 } },
  ]);
});

test("upload effect: HTTP error, network error and timeout become error actions", () => {
  const XMLHttpRequest = fakeXhr();
  const seen = [];
  const run = createRunner({ fetch: fakeFetch(), ...fakeTimers(), XMLHttpRequest });
  const start = (key) => {
    run({ type: "upload", key, url: "/up", body: "F", ok: "ok", error: "bad" }, (a) => seen.push(a));
    return XMLHttpRequest.instances.at(-1);
  };
  const http = start("a");
  Object.assign(http, { status: 413, responseText: "too big" });
  http.onload();
  start("b").onerror();
  start("c").ontimeout();
  assert.deepEqual(seen.map((a) => a.error), [
    { message: "HTTP 413", status: 413, body: "too big" },
    { message: "network", kind: "network" },
    { message: "timeout", kind: "timeout" },
  ]);
});

test("cancelling or replacing an upload aborts it and silences its late events", () => {
  const XMLHttpRequest = fakeXhr();
  const seen = [];
  const run = createRunner({ fetch: fakeFetch(), ...fakeTimers(), XMLHttpRequest });
  const dispatch = (a) => seen.push(a);
  run({ type: "upload", key: "u", url: "/1", body: "A", ok: "ok", error: "bad", progress: "prog" }, dispatch);
  run({ type: "upload", key: "u", url: "/2", body: "B", ok: "ok", error: "bad", progress: "prog" }, dispatch);
  const [first, second] = XMLHttpRequest.instances;
  assert.equal(first.aborted, true);
  first.upload.onprogress({ loaded: 1, total: 2, lengthComputable: true });
  Object.assign(first, { status: 200, responseText: "{}" });
  first.onload();
  run({ type: "cancel", key: "u" }, dispatch);
  assert.equal(second.aborted, true);
  second.onerror();
  assert.deepEqual(seen, []);
});

test("storage effect writes and removes in the named area; a throwing storage is ignored", () => {
  const data = { local: new Map(), session: new Map() };
  const area = (map) => ({ setItem: (k, v) => map.set(k, v), removeItem: (k) => map.delete(k) });
  const run = createRunner({
    fetch: fakeFetch(),
    ...fakeTimers(),
    storage: { local: () => area(data.local), session: () => area(data.session) },
  });
  run({ type: "storage", key: "k", area: "local", op: "write", value: "1" }, () => {});
  run({ type: "storage", key: "s", area: "session", op: "write", value: "2" }, () => {});
  assert.deepEqual([...data.local], [["k", "1"]]);
  assert.deepEqual([...data.session], [["s", "2"]]);
  run({ type: "storage", key: "k", area: "local", op: "remove" }, () => {});
  assert.equal(data.local.size, 0);
  const blocked = createRunner({ fetch: fakeFetch(), ...fakeTimers(), storage: { local: () => { throw new Error("denied"); } } });
  blocked({ type: "storage", key: "k", area: "local", op: "write", value: "1" }, () => {});
});

test("navigate effect calls the injected navigate", () => {
  const urls = [];
  createRunner({ fetch: fakeFetch(), ...fakeTimers(), navigate: (url) => urls.push(url) })({ type: "navigate", key: "n", url: "/next" }, () => {});
  assert.deepEqual(urls, ["/next"]);
});

test("upload, storage and navigate effects need a key", () => {
  const run = createRunner({ fetch: fakeFetch(), ...fakeTimers() });
  for (const type of ["upload", "extract", "storage", "navigate", "open-window", "call"]) assert.throws(() => run({ type }, () => {}), /needs a key/);
});

function fakeWindow() {
  const handle = { closed: false, opener: "x", document: { title: "", body: { textContent: "" } }, replaced: [], location: { replace: (url) => handle.replaced.push(url) } };
  handle.close = () => {
    handle.closed = true;
  };
  return handle;
}

test("open-window reserves a blank window, answers ok, then navigates and closes it", () => {
  const handle = fakeWindow();
  const opened = [];
  const run = createRunner({ fetch: fakeFetch(), ...fakeTimers(), open: (url, target) => (opened.push([url, target]), handle) });
  const actions = [];
  const dispatch = (action) => actions.push(action);
  run({ type: "open-window", key: "w", op: "reserve", title: "T", text: "body", ok: "w-ok", error: "w-blocked", meta: { m: 1 } }, dispatch);
  assert.deepEqual(opened, [["about:blank", "_blank"]]);
  assert.equal(handle.opener, null);
  assert.equal(handle.document.title, "T");
  assert.equal(handle.document.body.textContent, "body");
  assert.deepEqual(actions, [{ type: "w-ok", meta: { m: 1 } }]);
  run({ type: "open-window", key: "w", op: "navigate", url: "https://x.example/", closed: "w-closed", meta: { m: 1 } }, dispatch);
  assert.deepEqual(handle.replaced, ["https://x.example/"]);
  run({ type: "open-window", key: "w", op: "close" }, dispatch);
  assert.equal(handle.closed, true);
  // The user already closed it: navigating reports `closed` instead.
  run({ type: "open-window", key: "w", op: "navigate", url: "https://y.example/", closed: "w-closed", meta: { m: 2 } }, dispatch);
  assert.deepEqual(actions.at(-1), { type: "w-closed", meta: { m: 2 } });
  assert.deepEqual(handle.replaced, ["https://x.example/"]);
});

test("open-window answers blocked when the browser refuses or the window throws", () => {
  const actions = [];
  const dispatch = (action) => actions.push(action);
  const blocked = createRunner({ fetch: fakeFetch(), ...fakeTimers(), open: () => null });
  blocked({ type: "open-window", key: "w", op: "reserve", ok: "ok", error: "no", meta: 1 }, dispatch);
  const throwing = createRunner({ fetch: fakeFetch(), ...fakeTimers(), open: () => ({ get document() { throw new Error("cross-origin"); } }) });
  throwing({ type: "open-window", key: "w", op: "reserve", ok: "ok", error: "no", meta: 2 }, dispatch);
  assert.deepEqual(actions, [{ type: "no", meta: 1 }, { type: "no", meta: 2 }]);
  // Without a reserved window, navigate reports closed and close does nothing.
  blocked({ type: "open-window", key: "w", op: "navigate", url: "/", closed: "gone", meta: 3 }, dispatch);
  blocked({ type: "open-window", key: "w", op: "close" }, dispatch);
  assert.deepEqual(actions.at(-1), { type: "gone", meta: 3 });
  assert.throws(() => blocked({ type: "open-window", key: "w", op: "other" }, dispatch), /unknown open-window op/);
});

test("deps.now stamps the clock on schedule, fetch and window actions; without it nothing is added", async () => {
  const fetch = fakeFetch();
  const timers = fakeTimers();
  const actions = [];
  const dispatch = (action) => actions.push(action);
  let clock = 100;
  const run = createRunner({ fetch, ...timers, now: () => clock, open: () => fakeWindow() });
  run({ type: "schedule", key: "s", delay: 5, action: { type: "tick" } }, dispatch);
  clock = 200;
  timers.fire();
  run({ type: "fetch", key: "f", url: "/x", init: {}, ok: "ok", error: "err", meta: 1 }, dispatch);
  clock = 300;
  fetch.calls[0].resolve(reply(200, {}));
  await tick();
  run({ type: "open-window", key: "w", op: "reserve", ok: "opened", error: "no" }, dispatch);
  assert.deepEqual(actions.map((a) => [a.type, a.now]), [["tick", 200], ["ok", 300], ["opened", 300]]);

  const plain = [];
  const plainTimers = fakeTimers();
  createRunner({ fetch: fakeFetch(), ...plainTimers })({ type: "schedule", key: "s", delay: 0, action: { type: "tick" } }, (a) => plain.push(a));
  plainTimers.fire();
  assert.deepEqual(plain, [{ type: "tick" }]); // no `now` key when the dep is missing
});

test("runner call: runs a registered function, answers ok, and throws on an unknown name", async () => {
  const actions = [];
  const run = createRunner({ calls: { twice: (n) => n * 2, none: () => {} } });
  run({ type: "call", key: "a", name: "twice", args: [4], ok: "ok", meta: { n: 1 } }, (a) => actions.push(a));
  await tick();
  assert.deepEqual(actions, [{ type: "ok", value: 8, meta: { n: 1 } }]);
  run({ type: "call", key: "b", name: "none" }, (a) => actions.push(a)); // fire and forget: no action
  await tick();
  assert.equal(actions.length, 1);
  assert.throws(() => run({ type: "call", key: "c", name: "missing" }, () => {}), /unknown call/);
});

test("runner call: a sync throw or a rejection becomes the error action, also without an ok handler", async () => {
  const actions = [];
  const run = createRunner({ calls: { boom: () => { throw new Error("nope"); }, reject: async () => { throw new Error("later"); } } });
  run({ type: "call", key: "e", name: "boom", ok: "ok", error: "err", meta: { n: 1 } }, (a) => actions.push(a));
  run({ type: "call", key: "f", name: "reject", error: "err", meta: { n: 2 } }, (a) => actions.push(a));
  await tick();
  assert.deepEqual(actions, [
    { type: "err", error: { message: "nope" }, meta: { n: 1 } },
    { type: "err", error: { message: "later" }, meta: { n: 2 } },
  ]);
});

test("runner call: the newest call of a key wins and a cancel drops a late result", async () => {
  const actions = [];
  const late = [];
  const run = createRunner({ calls: { slow: () => new Promise((resolve) => late.push(resolve)) } });
  const dispatch = (a) => actions.push(a);
  run({ type: "call", key: "k", name: "slow", ok: "ok", meta: 1 }, dispatch);
  run({ type: "call", key: "k", name: "slow", ok: "ok", meta: 2 }, dispatch);
  late[0]("first");
  late[1]("second");
  await tick();
  assert.deepEqual(actions, [{ type: "ok", value: "second", meta: 2 }]);
  actions.length = 0;
  run({ type: "call", key: "z", name: "slow", ok: "ok", meta: 3 }, dispatch);
  run({ type: "cancel", key: "z" }, dispatch);
  late[2]("dropped");
  await tick();
  assert.deepEqual(actions, []);
});

test("deps.now stamps call results, ok and error", async () => {
  const actions = [];
  const run = createRunner({ now: () => 7, calls: { ok: () => 1, boom: async () => { throw new Error("x"); } } });
  run({ type: "call", key: "a", name: "ok", ok: "ok" }, (a) => actions.push(a));
  run({ type: "call", key: "b", name: "boom", error: "err" }, (a) => actions.push(a));
  await tick();
  assert.deepEqual(actions.map((a) => [a.type, a.now]), [["ok", 7], ["err", 7]]);
});

test("extract effect: progress, value, error kind, and replace/cancel abort it and silence it", async () => {
  const tick = () => new Promise((resolve) => setImmediate(resolve));
  const jobs = [];
  const extract = (file, options) => new Promise((resolve, reject) => jobs.push({ file, options, resolve, reject }));
  const run = createRunner({ fetch: fakeFetch(), ...fakeTimers(), extract });
  const seen = [];
  const dispatch = (a) => seen.push(a);
  run({ type: "extract", key: "e", file: "F", ok: "ok", error: "bad", progress: "prog", meta: 1 }, dispatch);
  await tick();
  jobs[0].options.onProgress(0.5);
  jobs[0].resolve("AUDIO");
  await tick();
  run({ type: "extract", key: "e", file: "G", ok: "ok", error: "bad", meta: 2 }, dispatch);
  await tick();
  jobs[1].reject(Object.assign(new Error("boom"), { kind: "codec" }));
  await tick();
  assert.deepEqual(seen, [
    { type: "prog", ratio: 0.5, meta: 1 },
    { type: "ok", value: "AUDIO", meta: 1 },
    { type: "bad", error: { message: "boom", kind: "codec" }, meta: 2 },
  ]);
  seen.length = 0;
  run({ type: "extract", key: "e", file: "H", ok: "ok", error: "bad", progress: "prog", meta: 3 }, dispatch);
  await tick();
  run({ type: "cancel", key: "e" }, dispatch);
  assert.equal(jobs[2].options.signal.aborted, true);
  jobs[2].options.onProgress(0.9);
  jobs[2].resolve("LATE");
  await tick();
  assert.deepEqual(seen, []);
});
