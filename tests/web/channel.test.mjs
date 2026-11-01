import assert from "node:assert/strict";
import test from "node:test";

import { meetingChanges, meetingContext, providerChoice } from "../../src/asr_en_vi/web/channel.js";
import { reduce as reduceNotes, initialState as notesInitial } from "../../src/asr_en_vi/web/notes-core.js";
import { initialState as providerInitial, reduce as reduceProvider } from "../../src/asr_en_vi/web/provider-core.js";
import { createRunner, createStore } from "../../src/asr_en_vi/web/store.js";

const tick = () => new Promise((resolve) => setImmediate(resolve));
const reply = (status, body) => ({ ok: status < 400, status, text: async () => JSON.stringify(body) });
const ORIGIN = "http://asr.test";

// What history.js publishes: a new detail object every time, even for an unchanged meeting.
const publish = (id, extra = {}) => meetingContext.dispatch({
  type: "channel/meeting-context",
  detail: { view: id ? "meeting" : "list", meeting: id ? meeting(id) : null, "transcriptionRequestInFlight": false, ...extra },
});
const meeting = (id) => ({
  id,
  title: "Weekly",
  metadata_version: 1,
  meeting_date: null,
  notes_source_locked: false,
  transcription: { generation: { id: "g1", status: "complete", source_version: 1, segments: [] }, task: null },
});

// A subscriber for one test; the channel is a singleton, so every test lets go of it.
function listen(channel) {
  const log = [];
  const stop = channel.subscribe((state) => log.push(state));
  return { log, stop };
}

// ---- the channel ----

test("each publish reaches the subscriber at once and in order, an identical context included", () => {
  const { log, stop } = listen(meetingContext);
  publish("m1");
  assert.equal(log.length, 1, "delivered inside dispatch, not later");
  publish("m2");
  publish("m2"); // the same content in a new object is a new publish
  publish("m1");
  stop();
  assert.deepEqual(log.map((detail) => detail.meeting.id), ["m1", "m2", "m2", "m1"]);
  assert.notEqual(log[1], log[2]);
});

test("the very same object published twice is delivered once, which is why history.js builds a new detail each time", () => {
  const { log, stop } = listen(meetingContext);
  const detail = { view: "list", meeting: null };
  meetingContext.dispatch({ type: "channel/meeting-context", detail });
  meetingContext.dispatch({ type: "channel/meeting-context", detail });
  stop();
  assert.equal(log.length, 1);
});

test("getState is the last published context; a late subscriber hears only later publishes", () => {
  publish("m1");
  const early = listen(meetingContext);
  publish("m2");
  const late = listen(meetingContext);
  assert.equal(meetingContext.getState().meeting.id, "m2");
  assert.deepEqual(late.log, []);
  publish("m3");
  early.stop();
  late.stop();
  assert.deepEqual(early.log.map((detail) => detail.meeting.id), ["m2", "m3"]);
  assert.deepEqual(late.log.map((detail) => detail.meeting.id), ["m3"]);
});

test("a subscriber that let go hears nothing more; an unknown action changes nothing", () => {
  const { log, stop } = listen(meetingContext);
  meetingContext.dispatch({ type: "channel/other", detail: { view: "list" } });
  stop();
  publish("m1");
  assert.deepEqual(log, []);
});

test("every provider-choice change is delivered, one per publish, and counted", () => {
  const before = providerChoice.getState();
  const { log, stop } = listen(providerChoice);
  providerChoice.dispatch({ type: "channel/provider-choice-changed" });
  providerChoice.dispatch({ type: "channel/provider-choice-changed" });
  providerChoice.dispatch({ type: "channel/other" });
  stop();
  assert.equal(log.length, 2);
  assert.equal(providerChoice.getState(), before + 2);
  providerChoice.dispatch({ type: "channel/provider-choice-changed" });
  assert.equal(log.length, 2, "after stop nothing arrives");
});

test("meeting changes carry the mutation meeting and local provenance as data", () => {
  const { log, stop } = listen(meetingChanges);
  const detail = { meetingId: "m1", reason: "transcript", local: true };
  meetingChanges.dispatch({ type: "channel/meeting-changed", detail });
  meetingChanges.dispatch({ type: "channel/meeting-changed", detail });
  stop();
  assert.deepEqual(log, [detail]);
  assert.equal(meetingChanges.getState(), detail);
});

test("before the first publish there is no context and no change was counted", async () => {
  const fresh = await import("../../src/asr_en_vi/web/channel.js?fresh"); // a new module instance, not the singleton the other tests used
  assert.equal(fresh.meetingContext.getState(), null);
  assert.equal(fresh.providerChoice.getState(), 0);
  assert.equal(fresh.meetingChanges.getState(), null);
});

// ---- the channel wired the way notes.js wires it ----

// The real notes reducer and runner over a fake fetch; the subscriptions are the two lines of notes.js.
function notesPage() {
  const requests = [];
  const seen = [];
  const fetch = (url, init) => new Promise((resolve) => requests.push({ url, method: init.method, resolve, done: false }));
  const run = createRunner({
    fetch,
    setTimeout: () => 0,
    clearTimeout: () => {},
    storage: { local: () => ({ setItem() {}, removeItem() {} }), session: () => ({ setItem() {}, removeItem() {} }) },
    calls: new Proxy({}, { get: () => () => undefined }),
  });
  const store = createStore({ reduce: (state, action) => (seen.push(action), reduceNotes(state, action)), initialState: notesInitial, run });
  store.dispatch({ type: "notes/booted", mode: "view", hidden: false, origin: ORIGIN });
  const stops = [
    meetingContext.subscribe((detail) => store.dispatch({
      type: "notes/context",
      detail,
      speakerNames: [],
      href: detail.meeting ? `${ORIGIN}/meetings/${detail.meeting.id}` : `${ORIGIN}/`,
      stored: {},
    })),
    providerChoice.subscribe(() => store.dispatch({ type: "notes/provider-choice-changed" })),
  ];
  const answer = async (match, status, body) => {
    const request = requests.find((item) => !item.done && match(item));
    assert.ok(request, "no pending request");
    request.done = true;
    request.resolve(reply(status, body));
    await tick();
  };
  const types = (type) => seen.filter((action) => action.type === type);
  return { store, requests, seen, answer, types, stop: () => stops.forEach((stop) => stop()) };
}
const NOTES = (id) => (item) => item.method === "GET" && item.url.includes(`/api/meetings/${id}/notes`);
const revision = (meetingId) => ({ id: `r-${meetingId}`, meeting_id: meetingId, source_snapshot_id: "s1", markdown: "# Plan", edit_version: 1, source_state: "current", output_language: "en" });

test("notes see the contexts in the order they were published", () => {
  const page = notesPage();
  publish("m1");
  publish(null);
  publish("m2");
  publish("m1");
  page.stop();
  assert.deepEqual(page.types("notes/context").map((action) => action.detail.meeting?.id ?? null), ["m1", null, "m2", "m1"]);
  assert.equal(page.store.getState().meetingId, "m1");
});

test("a notes answer for the previous meeting is dropped after the channel delivered the next one", async () => {
  const page = notesPage();
  publish("m1");
  publish("m2");
  assert.equal(page.store.getState().meetingId, "m2");
  await page.answer(NOTES("m1"), 200, { revisions: [revision("m1")], task: null, source_locked: false });
  assert.equal(page.store.getState().notes.m1?.revisions.length ?? 0, 0, "the late answer for m1 changed nothing");
  await page.answer(NOTES("m2"), 200, { revisions: [revision("m2")], task: null, source_locked: false });
  assert.deepEqual(page.store.getState().notes.m2.revisions.map((item) => item.id), ["r-m2"]);
  assert.equal(page.store.getState().meetingId, "m2");
  page.stop();
});

test("a provider-core save publishes on the channel through its call effect and notes reload the choice", async () => {
  const page = notesPage();
  publish("m1");
  const loads = () => page.requests.filter((item) => item.url.endsWith("/api/providers")).length;
  const before = loads();
  // The real provider reducer and runner: connections.js maps the `call` effect to this dispatch.
  const answers = {
    "GET /api/providers": { providers: [{ id: "chatgpt", status: "connected" }, { id: "antigravity", status: "disconnected" }] },
    "GET /api/notes-preferences": { provider: "chatgpt", models: { chatgpt: "m1" }, reasoning_effort: "low" },
    "GET /api/providers/chatgpt/models": { models: [{ id: "m1", display_name: "M1" }, { id: "m2", display_name: "M2" }], selected_model: "m1" },
    "PUT /api/notes-preferences": { provider: "chatgpt", models: { chatgpt: "m2" }, reasoning_effort: "default" },
  };
  const sent = [];
  const run = createRunner({
    fetch: async (url, init) => {
      sent.push(`${init.method} ${url}`);
      const body = answers[`${init.method} ${url}`];
      return body ? reply(200, body) : reply(404, {});
    },
    setTimeout: () => 0,
    clearTimeout: () => {},
    storage: { local: () => ({ setItem() {}, removeItem() {} }), session: () => ({ setItem() {}, removeItem() {} }) },
    calls: { "provider.choice-changed": () => providerChoice.dispatch({ type: "channel/provider-choice-changed" }) },
    now: () => 0,
  });
  const provider = createStore({ reduce: reduceProvider, initialState: providerInitial, run });
  const published = listen(providerChoice);
  provider.dispatch({ type: "provider/dialog-opened", launcher: "chatgpt" });
  for (let i = 0; i < 6; i += 1) await tick();
  assert.equal(provider.getState().chatgpt.loading, false, `loaded (${sent.join(", ")})`);
  const settled = published.log.length;
  provider.dispatch({ type: "provider/choice-edited", provider: "chatgpt", field: "model", value: "m2" });
  provider.dispatch({ type: "provider/save-requested", provider: "chatgpt" });
  for (let i = 0; i < 3; i += 1) await tick();
  assert.equal(provider.getState().chatgpt.savedModel, "m2");
  assert.equal(published.log.length, settled + 1, "one publish for the save");
  assert.equal(page.types("notes/provider-choice-changed").length, published.log.length, "notes heard every publish");
  assert.equal(loads(), before + 1, "the open notes tab reloads the choice once for the save");
  published.stop();
  page.stop();
});

test("publishes made while a subscriber runs are queued and reach the others as one delivery of the last state", () => {
  const before = providerChoice.getState();
  const nested = [];
  const stopNester = providerChoice.subscribe((count) => {
    if (count === before + 1) for (let i = 0; i < 3; i += 1) providerChoice.dispatch({ type: "channel/provider-choice-changed" });
    nested.push(count);
  });
  const { log, stop } = listen(providerChoice);
  providerChoice.dispatch({ type: "channel/provider-choice-changed" });
  stopNester();
  stop();
  assert.equal(providerChoice.getState(), before + 4);
  assert.deepEqual(nested, [before + 1, before + 4], "the three nested publishes arrive as one delivery");
  assert.deepEqual(log, [before + 1, before + 4], "no delivery for the intermediate counts");
});
