// The one channel between stores: what history.js and connections.js announce to notes.js.
// Contract: docs/adr/0010-frontend-reducer-core.md. Subscribers run inside dispatch, in publish order.
import { createStore } from "./store.js";

// state = the last published context ({meeting, view, "transcriptionRequestInFlight"}); history.js
// passes a new object on every publish, so even an identical context reaches every subscriber.
export const meetingContext = createStore({
  initialState: null,
  reduce: (state, action) => (action.type === "channel/meeting-context" ? { state: action.detail } : { state }),
});

// state = how many times the provider choice changed (Connections saved a model or a status moved).
export const providerChoice = createStore({
  initialState: 0,
  reduce: (state, action) => (action.type === "channel/provider-choice-changed" ? { state: state + 1 } : { state }),
});
