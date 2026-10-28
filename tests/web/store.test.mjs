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
