// Reducer store and effect runner. No DOM access: node --test loads this file directly.
// Contract: docs/adr/0010-frontend-reducer-core.md.

// reduce(state, action) -> { state, effects? }. Effects are plain data run after the reducer.
export function createStore({ reduce, initialState, run }) {
  let state = initialState;
  const listeners = new Set();
  const queue = [];
  let draining = false;

  function dispatch(action) {
    queue.push(action);
    if (draining) return; // FIFO: a dispatch made while draining is processed by the running loop
    draining = true;
    try {
      while (queue.length) {
        const before = state;
        while (queue.length) {
          const result = reduce(state, queue.shift());
          state = result.state;
          for (const effect of result.effects ?? []) run?.(effect, dispatch);
        }
        if (state !== before) for (const listener of [...listeners]) listener(state);
      }
    } finally {
      queue.length = 0;
      draining = false;
    }
  }

  return {
    getState: () => state,
    dispatch,
    subscribe(listener) {
      listeners.add(listener);
      return () => listeners.delete(listener);
    },
  };
}

// Every feature reducer sees every action, so features talk through shared actions.
export function combine(features) {
  const names = Object.keys(features);
  return (state, action) => {
    let next = state;
    const effects = [];
    for (const name of names) {
      const result = features[name](state[name], action);
      if (result.state !== state[name]) next = { ...next, [name]: result.state };
      effects.push(...(result.effects ?? []));
    }
    return { state: next, effects };
  };
}

// Built-in effects: fetch {key, url, init, ok, error, meta}, schedule {key, delay, action}, cancel {key},
// upload {key, url, method?, headers?, body, ok, error, progress?, meta}, storage {key, area, op, value?},
// navigate {key, url}. key is required (feature-prefixed, e.g. shell/upload; a storage key for storage).
// A new effect with a live key replaces the previous one (latest wins).
// fetch: 2xx -> {type: ok, response: {status, body}, meta}; HTTP error or network failure ->
// {type: error, error: {message, status?, body?}, meta}; an aborted request dispatches nothing.
// upload: same ok/error/meta/latest-wins semantics over XHR; also {type: progress, loaded, total,
// lengthComputable, meta} while sending; a failed transfer is error {message, kind: network|timeout}.
// storage: area local|session, op write|remove; a storage that throws means the value is not remembered.
// navigate: calls deps.navigate(url).
// open-window {key, op, ...}: op reserve {title, text, ok, error, meta} opens a blank window through deps.open and
// answers ok or error (blocked); op navigate {url, closed, meta} sends the reserved window to url, or answers
// `closed` when the user already closed it; op close closes it. Handles live outside the cancel/latest-wins map.
// call {key, name, args?, ok?, error?, meta?}: calls deps.calls[name](...args) for what the core cannot reach
// (history.js commands, a message on the channel, clipboard, download, history.replaceState). Without ok/error it runs at once and returns nothing.
// With ok and/or error the result (a value or a promise) answers {type: ok, value, meta} or {type: error, error: {message}, meta}
// with the same latest-wins/cancel rules as fetch; a call whose name is unknown throws.
// deps.now (optional): stamps `now` on the actions it dispatches for fetch, schedule, open-window and call results (not upload), so reducers get the clock as data.
export function createRunner({ fetch, setTimeout, clearTimeout, XMLHttpRequest, storage, navigate, open, calls, now }) {
  const active = new Map(); // key -> { stop }
  const windows = new Map(); // key -> reserved window handle
  const stamp = (action) => (now ? { ...action, now: now() } : action);

  function start(key, stop) {
    active.get(key)?.stop();
    const entry = { stop };
    active.set(key, entry);
    return entry;
  }
  const alive = (key, entry) => active.get(key) === entry;

  return function run(effect, dispatch) {
    const { type, key } = effect;
    if (key === undefined) throw new Error(`${type} effect needs a key`); // keyless effects would share one slot
    if (type === "cancel") {
      active.get(key)?.stop();
      active.delete(key);
    } else if (type === "schedule") {
      const id = setTimeout(() => {
        active.delete(key);
        dispatch(stamp(effect.action));
      }, effect.delay);
      start(key, () => clearTimeout(id));
    } else if (type === "fetch") {
      const controller = new AbortController();
      const entry = start(key, () => controller.abort());
      const finish = (action) => {
        if (!alive(key, entry)) return; // cancelled or replaced: drop the late result
        active.delete(key);
        dispatch({ ...stamp(action), meta: effect.meta });
      };
      (async () => {
        const response = await fetch(effect.url, { ...effect.init, signal: controller.signal });
        const text = await response.text();
        let body = text;
        try {
          body = JSON.parse(text);
        } catch {
          // not JSON: keep the text
        }
        if (response.ok) return { type: effect.ok, response: { status: response.status, body } };
        return { type: effect.error, error: { message: `HTTP ${response.status}`, status: response.status, body } };
      })()
        .catch((error) => ({ type: effect.error, error: { message: String(error?.message ?? error) } }))
        .then(finish); // dispatch runs outside the try: a throwing reducer/subscriber is an unhandled rejection
    } else if (type === "upload") {
      const xhr = new XMLHttpRequest();
      const entry = start(key, () => xhr.abort());
      const finish = (action) => {
        if (!alive(key, entry)) return; // cancelled or replaced: drop the late result
        active.delete(key);
        dispatch({ ...action, meta: effect.meta });
      };
      const fail = (kind) => () => finish({ type: effect.error, error: { message: kind, kind } });
      xhr.open(effect.method ?? "PUT", effect.url, true);
      xhr.withCredentials = true;
      for (const [name, value] of Object.entries(effect.headers ?? {})) xhr.setRequestHeader(name, value);
      xhr.upload.onprogress = (event) => {
        if (!effect.progress || !alive(key, entry)) return;
        const { loaded, total, lengthComputable } = event;
        dispatch({ type: effect.progress, loaded, total, lengthComputable, meta: effect.meta });
      };
      xhr.onload = () => {
        let body = xhr.responseText;
        try {
          body = JSON.parse(body);
        } catch {
          // not JSON: keep the text
        }
        if (xhr.status >= 200 && xhr.status < 300) finish({ type: effect.ok, response: { status: xhr.status, body } });
        else finish({ type: effect.error, error: { message: `HTTP ${xhr.status}`, status: xhr.status, body } });
      };
      xhr.onerror = fail("network");
      xhr.ontimeout = fail("timeout");
      xhr.send(effect.body); // no onabort: an abort is always the reducer's own cancel
    } else if (type === "storage") {
      try {
        const area = storage[effect.area]();
        if (effect.op === "remove") area.removeItem(key);
        else area.setItem(key, effect.value);
      } catch {
        // the choice is simply not remembered
      }
    } else if (type === "navigate") {
      navigate(effect.url);
    } else if (type === "open-window") {
      const handle = windows.get(key);
      if (effect.op === "reserve") {
        let reserved = null;
        try {
          reserved = open("about:blank", "_blank");
          if (reserved) {
            reserved.opener = null;
            reserved.document.title = effect.title;
            reserved.document.body.textContent = effect.text;
          }
        } catch {
          reserved = null;
        }
        if (reserved) windows.set(key, reserved);
        else windows.delete(key);
        dispatch({ ...stamp({ type: reserved ? effect.ok : effect.error }), meta: effect.meta });
      } else if (effect.op === "navigate") {
        if (handle && !handle.closed) handle.location.replace(effect.url);
        else dispatch({ ...stamp({ type: effect.closed }), meta: effect.meta });
      } else if (effect.op === "close") {
        if (handle && !handle.closed) handle.close();
        windows.delete(key);
      } else {
        throw new Error(`unknown open-window op: ${effect.op}`);
      }
    } else if (type === "call") {
      const fn = calls?.[effect.name];
      if (typeof fn !== "function") throw new Error(`unknown call: ${effect.name}`);
      const args = effect.args ?? [];
      if (!effect.ok && !effect.error) {
        fn(...args);
      } else {
        const entry = start(key, () => {});
        const finish = (action) => {
          if (!alive(key, entry)) return; // cancelled or replaced: drop the late result
          active.delete(key);
          if (action) dispatch({ ...stamp(action), meta: effect.meta });
        };
        let result;
        try {
          result = Promise.resolve(fn(...args));
        } catch (error) {
          result = Promise.reject(error);
        }
        result.then(
          (value) => finish(effect.ok && { type: effect.ok, value }),
          (error) => finish(effect.error && { type: effect.error, error: { message: String(error?.message ?? error) } }),
        );
      }
    } else {
      throw new Error(`unknown effect type: ${type}`);
    }
  };
}
