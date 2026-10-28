// View of the create-meeting dialog: reads store state, renders the DOM, dispatches actions.
// All state and rules live in shell-core.js (contract: docs/adr/0010-frontend-reducer-core.md).
// Unmigrated scripts (history.js, ...) still use the helpers published on window at the bottom.
import { createRunner, createStore } from "./store.js";
import {
  AUTO_TRANSCRIBE_KEY,
  LAST_LANGUAGE_KEY,
  STATE_LABELS,
  formatBytes,
  initialState,
  reduce,
  responseMessage,
  selectView,
} from "./shell-core.js";

const dialog = document.querySelector("#meeting-dialog");
const form = document.querySelector("#meeting-form");
const fileInput = document.querySelector("#recording-file");
const fileDrop = document.querySelector("#file-drop");
const fileLimits = document.querySelector("#file-limits");
const fileError = document.querySelector("#file-error");
const selectedFile = document.querySelector("#selected-file");
const selectedFileName = document.querySelector("#selected-file-name");
const selectedFileSize = document.querySelector("#selected-file-size");
const titleInput = document.querySelector("#meeting-name");
const dateInput = document.querySelector("#meeting-date-input");
const autoTranscribeInput = document.querySelector("#auto-transcribe");
const languageInputs = [...form.querySelectorAll('input[name="language_hint"]')];
const createButton = document.querySelector("#create-meeting");
const changeFileButton = document.querySelector("#change-file");
const retryUploadButton = document.querySelector("#retry-upload");
const cancelUploadButton = document.querySelector("#cancel-upload");
const closeDialogButton = document.querySelector("#close-dialog");
const workflowState = document.querySelector("#workflow-state");
const stateLabel = document.querySelector("#state-label");
const validationState = document.querySelector("#validation-state");
const createGuidance = document.querySelector("#create-guidance");
const formError = document.querySelector("#form-error");
const transferProgress = document.querySelector("#transfer-progress");
const uploadProgress = document.querySelector("#upload-progress");
const uploadProgressValue = document.querySelector("#upload-progress-value");

// Core text is data ({text, params}); t() turns it into the page language.
function tr(message) {
  if (message === null || message === undefined) return "";
  if (typeof message !== "object") return String(message);
  if (Array.isArray(message)) return message.map(tr).join("");
  if (message.fmt === "bytes") return formatBytes(message.value, UI_LOCALE);
  if (message.fmt === "decimal") return new Intl.NumberFormat(UI_LOCALE, { maximumFractionDigits: 1 }).format(message.value);
  const params = message.params && Object.fromEntries(Object.entries(message.params).map(([name, value]) => [name, tr(value)]));
  return t(message.text, params);
}

// Write only what changed: a rewrite with the same value still fires observers and live regions.
function setProp(element, name, value) {
  if (element[name] !== value) element[name] = value;
}

function setAttr(element, name, value) {
  if (element.getAttribute(name) !== value) element.setAttribute(name, value);
}

function render(state) {
  const view = selectView(state);
  setAttr(dialog, "data-state", state.phase);
  setProp(stateLabel, "textContent", tr(STATE_LABELS[state.phase]));
  setProp(workflowState, "textContent", tr(state.workflow));
  setProp(validationState, "textContent", tr(state.validation));
  setProp(createGuidance, "textContent", tr(view.guidance));
  setProp(fileLimits, "textContent", tr(view.limits));
  setProp(fileInput, "accept", view.accept);
  setProp(fileInput, "disabled", view.fileInputDisabled);
  setAttr(fileDrop, "aria-disabled", String(view.fileInputDisabled));
  setProp(changeFileButton, "disabled", view.changeFileDisabled);

  setProp(fileError, "textContent", tr(state.fileError));
  const message = tr(state.formError);
  setProp(formError, "textContent", message);
  setProp(formError, "hidden", !message);
  setProp(transferProgress, "hidden", !state.progress.visible);
  setProp(uploadProgress, "value", state.progress.percent);
  setProp(uploadProgressValue, "textContent", tr(state.progress.text));
  setProp(selectedFile, "hidden", !state.file);
  setProp(selectedFileName, "textContent", state.file ? state.file.name : "");
  setProp(selectedFileSize, "textContent", state.file ? formatBytes(state.file.size, UI_LOCALE) : "");

  // Typing already matches the state, so only a programmatic change touches the inputs.
  setProp(titleInput, "value", state.form.title);
  setProp(dateInput, "value", state.form.date);
  for (const input of languageInputs) setProp(input, "checked", input.value === state.form.language);
  setProp(autoTranscribeInput, "checked", state.form.autoTranscribe);
  for (const input of [titleInput, dateInput, autoTranscribeInput, ...languageInputs]) setProp(input, "disabled", view.fieldsDisabled);

  setProp(retryUploadButton, "hidden", view.retryHidden);
  setProp(retryUploadButton, "disabled", view.retryDisabled);
  setProp(cancelUploadButton, "hidden", view.cancelHidden);
  setProp(createButton, "disabled", view.createDisabled);
  setProp(createButton, "textContent", tr(view.createLabel));
  setProp(closeDialogButton, "disabled", view.closeDisabled);

  if (state.open && !dialog.open) {
    dialog.showModal();
    titleInput.focus();
  } else if (!state.open && dialog.open) {
    dialog.close();
  }
}

const run = createRunner({
  fetch: (url, init) => fetch(url, init),
  setTimeout: (callback, delay) => window.setTimeout(callback, delay),
  clearTimeout: (id) => window.clearTimeout(id),
  XMLHttpRequest,
  storage: { local: () => window.localStorage, session: () => window.sessionStorage },
  navigate: (url) => window.location.assign(url),
});
const store = createStore({ reduce, initialState, run });
const { dispatch } = store;
store.subscribe(render);

// The remembered choices enter the state through the open action; writes go through storage effects.
function readStored() {
  const read = (key) => {
    try {
      return window.localStorage.getItem(key);
    } catch {
      return null;
    }
  };
  return { language: read(LAST_LANGUAGE_KEY), autoTranscribe: read(AUTO_TRANSCRIBE_KEY) };
}

function readForm() {
  const checked = languageInputs.find((input) => input.checked);
  return { title: titleInput.value, date: dateInput.value, language: checked ? checked.value : "" };
}

for (const button of document.querySelectorAll("[data-open-meeting-dialog]")) {
  button.addEventListener("click", () => dispatch({ type: "shell/dialog-opened", stored: readStored() }));
}

const requestClose = () => dispatch({ type: "shell/dialog-close-requested" });
closeDialogButton.addEventListener("click", requestClose);
changeFileButton.addEventListener("click", () => fileInput.click());
fileInput.addEventListener("change", () => {
  const file = fileInput.files && fileInput.files[0];
  fileInput.value = "";
  if (file) dispatch({ type: "shell/file-selected", file });
});

fileDrop.addEventListener("dragenter", (event) => {
  event.preventDefault();
  if (!fileInput.disabled) fileDrop.classList.add("is-dragging");
});
fileDrop.addEventListener("dragover", (event) => {
  event.preventDefault();
  if (!fileInput.disabled && event.dataTransfer) event.dataTransfer.dropEffect = "copy";
});
fileDrop.addEventListener("dragleave", (event) => {
  if (!fileDrop.contains(event.relatedTarget)) fileDrop.classList.remove("is-dragging");
});
fileDrop.addEventListener("drop", (event) => {
  event.preventDefault();
  fileDrop.classList.remove("is-dragging");
  if (fileInput.disabled) return;
  const files = event.dataTransfer && event.dataTransfer.files;
  if (!files || files.length === 0) return;
  if (files.length > 1) dispatch({ type: "shell/multiple-files-dropped" });
  else dispatch({ type: "shell/file-selected", file: files[0] });
});

retryUploadButton.addEventListener("click", () => dispatch({ type: "shell/submit-requested" }));
cancelUploadButton.addEventListener("click", () => dispatch({ type: "shell/upload-cancel-requested" }));
form.addEventListener("submit", (event) => {
  event.preventDefault();
  dispatch({ type: "shell/submit-requested" });
});
autoTranscribeInput.addEventListener("change", () => {
  dispatch({ type: "shell/auto-transcribe-toggled", value: autoTranscribeInput.checked });
});

const editForm = () => dispatch({ type: "shell/form-edited", form: readForm() });
titleInput.addEventListener("input", editForm);
dateInput.addEventListener("change", editForm);
for (const input of languageInputs) input.addEventListener("change", editForm);

dialog.addEventListener("cancel", (event) => {
  event.preventDefault();
  requestClose();
});
// The browser can close the dialog on its own (a second Escape); the state must follow.
dialog.addEventListener("close", () => dispatch({ type: "shell/dialog-closed" }));
dialog.addEventListener("click", (event) => {
  if (event.target === dialog) requestClose();
});

// Helpers that history.js and the other unmigrated scripts still call; published on window until phase 5.
class ApiError extends Error {
  constructor(message, status, payload) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.payload = payload;
  }
}

async function requestJson(path, options = {}) {
  const method = (options.method || "GET").toUpperCase();
  const headers = { Accept: "application/json" };
  if (method !== "GET" && method !== "HEAD") headers["Content-Type"] = "application/json";
  const requestOptions = {
    method,
    headers,
    credentials: "same-origin",
    cache: "no-store",
  };
  if (options.body !== undefined) requestOptions.body = options.body;
  if (options.signal) requestOptions.signal = options.signal;

  let response;
  try {
    response = await fetch(path, requestOptions);
  } catch (error) {
    if (error && error.name === "AbortError") throw error;
    const networkError = new Error(t("Không kết nối được với máy chủ trên máy này."));
    networkError.kind = "network";
    throw networkError;
  }

  let payload = null;
  try {
    payload = await response.json();
  } catch {
    payload = null;
  }
  if (!response.ok) throw new ApiError(tr(responseMessage(response.status, payload)), response.status, payload);
  return payload;
}

function meetingIdFromPath() {
  const match = window.location.pathname.match(/^\/meetings\/([^/]+)\/?$/);
  if (!match) return null;
  try {
    const id = decodeURIComponent(match[1]);
    return id && !id.includes("/") ? id : null;
  } catch {
    return null;
  }
}

function formatMeetingDate(value) {
  if (!value) return { label: t("Chưa đặt ngày"), dateTime: "" };
  const date = String(value).slice(0, 10);
  const match = date.match(/^(\d{4})-(\d{2})-(\d{2})$/);
  if (!match) return { label: t("Chưa đặt ngày"), dateTime: "" };
  const year = Number(match[1]);
  const month = Number(match[2]);
  const day = Number(match[3]);
  const parsed = new Date(Date.UTC(year, month - 1, day));
  if (parsed.getUTCFullYear() !== year || parsed.getUTCMonth() !== month - 1 || parsed.getUTCDate() !== day) {
    return { label: t("Chưa đặt ngày"), dateTime: "" };
  }
  return {
    label: new Intl.DateTimeFormat(UI_LOCALE, { day: "numeric", month: "long", year: "numeric", timeZone: "UTC" }).format(parsed),
    dateTime: date,
  };
}

function sameOriginAudioSource(audioUrl, meetingId) {
  const fallback = `/api/meetings/${encodeURIComponent(meetingId)}/audio`;
  if (typeof audioUrl !== "string" || !audioUrl.trim()) return fallback;
  try {
    const parsed = new URL(audioUrl, window.location.origin);
    if (parsed.origin !== window.location.origin || !/^\/api\/meetings\/[^/]+\/audio\/?$/.test(parsed.pathname)) return fallback;
    return `${parsed.pathname}${parsed.search}`;
  } catch {
    return fallback;
  }
}

Object.assign(window, { ApiError, requestJson, meetingIdFromPath, formatMeetingDate, sameOriginAudioSource });
