// Pure core of the create-meeting dialog: state, reducer, selectors. No DOM, fetch, timer, storage
// or clock: node --test loads this file directly. Contract: docs/adr/0010-frontend-reducer-core.md;
// state table: docs/frontend-design-v1.md §11.5.
//
// User-visible text is data: t(text, params) here only keeps the Vietnamese source string, and the view
// translates it with the real t(). The name matches the call sites in the other scripts so the i18n
// test finds every string. A param is a primitive, a t() result, a bytes()/decimal() marker, or an array of those.

export const LAST_LANGUAGE_KEY = "asr-en-vi:last-language-hint";
export const AUTO_TRANSCRIBE_KEY = "asr-en-vi:auto-transcribe";
// history.js removes this one-shot key before it sends the transcription request.
export const AUTO_TRANSCRIBE_HANDOFF_PREFIX = "asr-en-vi:auto-transcribe:";

const t = (text, params) => (params ? { text, params } : { text });
export const bytes = (value) => ({ fmt: "bytes", value });
export const decimal = (value) => ({ fmt: "decimal", value });

export const STATE_LABELS = {
  idle: t("Chưa chọn file"),
  selected: t("Đã chọn file"),
  extracting: t("Đang tách audio"),
  uploading: t("Đang tải lên"),
  checking: t("Đang kiểm tra"),
  ready: t("Sẵn sàng tạo"),
  creating: t("Đang tạo"),
  saved: t("Đã tạo"),
  error: t("Có lỗi"),
  aborted: t("Đã hủy"),
};

export function formatBytes(value, locale) {
  if (value < 1024) return `${value} byte`;
  const units = ["KiB", "MiB", "GiB"];
  let amount = value;
  let unit = "byte";
  for (const nextUnit of units) {
    amount /= 1024;
    unit = nextUnit;
    if (amount < 1024 || nextUnit === "GiB") break;
  }
  return `${new Intl.NumberFormat(locale, { maximumFractionDigits: 1 }).format(amount)} ${unit}`;
}

function formatDuration(seconds) {
  if (seconds >= 3600 && seconds % 3600 === 0) return t("{n} giờ", { n: seconds / 3600 });
  if (seconds >= 60 && seconds % 60 === 0) return t("{n} phút", { n: seconds / 60 });
  if (seconds >= 60) return t("{n} phút", { n: decimal(seconds / 60) });
  return t("{n} giây", { n: seconds });
}

// A string is the server's own detail; a t() result is ours.
export function responseMessage(status, payload) {
  const rawDetail = payload && payload.detail;
  const detail = typeof rawDetail === "string"
    ? rawDetail.trim()
    : rawDetail && typeof rawDetail.message === "string"
      ? rawDetail.message.trim()
      : "";
  if (detail) return detail;
  if (status === 401) return t("Phiên truy cập không còn hợp lệ. Hãy mở lại link trong terminal.");
  if (status === 403) return t("Yêu cầu bị từ chối. Hãy tải lại workspace rồi thử lại.");
  if (status === 404) return t("Không tìm thấy dữ liệu yêu cầu.");
  if (status === 409) return t("Dữ liệu đã thay đổi hoặc đang được sử dụng. Hãy tải lại rồi thử lại.");
  if (status === 413) return t("File vượt quá giới hạn dung lượng được công bố.");
  if (status === 415) return t("Định dạng file này chưa được hỗ trợ. Hãy chọn định dạng trong danh sách.");
  if (status === 422) return t("File không đạt yêu cầu. Hãy kiểm tra định dạng, thời lượng và nội dung file.");
  if (status >= 500) return t("Máy chủ chưa thể hoàn tất yêu cầu. Hãy thử lại sau.");
  return t("Máy chủ chưa thể hoàn tất yêu cầu. Hãy kiểm tra thông tin rồi thử lại.");
}

function policyField(policy, names) {
  for (const name of names) {
    if (policy[name] !== undefined && policy[name] !== null) return policy[name];
  }
  return undefined;
}

// -> { policy } or { error: t() }
function normalizePolicy(payload) {
  const source = payload && payload.policy && typeof payload.policy === "object" ? payload.policy : payload;
  if (!source || typeof source !== "object") return { error: t("Chính sách file không đúng định dạng.") };
  const rawExtensions = policyField(source, ["supported_extensions", "extensions", "allowed_extensions"]);
  const maxBytes = Number(policyField(source, ["max_bytes", "max_size_bytes", "max_file_size_bytes"]));
  const maxDurationSeconds = Number(policyField(source, ["max_duration_seconds", "max_duration_s"]));
  if (!Array.isArray(rawExtensions) || !Number.isFinite(maxBytes) || maxBytes <= 0 || !Number.isFinite(maxDurationSeconds) || maxDurationSeconds <= 0) {
    return { error: t("Chính sách chưa công bố đủ định dạng, dung lượng và thời lượng tối đa.") };
  }
  const extensions = rawExtensions
    .map((extension) => String(extension).trim().toLowerCase())
    .map((extension) => (extension.startsWith(".") ? extension : `.${extension}`))
    .filter((extension) => /^\.[a-z0-9][a-z0-9.+_-]*$/.test(extension));
  if (extensions.length === 0) return { error: t("Chính sách chưa công bố định dạng file được hỗ trợ.") };
  return { policy: { extensions: [...new Set(extensions)], maxBytes, maxDurationSeconds } };
}

function fileExtension(filename) {
  const finalDot = filename.lastIndexOf(".");
  return finalDot >= 0 ? filename.slice(finalDot).toLowerCase() : "";
}

function formValuesAreValid(form) {
  const title = form.title.trim();
  const dateIsValid = !form.date || /^\d{4}-\d{2}-\d{2}$/.test(form.date);
  return Boolean(title && Array.from(title).length <= 200 && ["en", "vi"].includes(form.language) && dateIsValid);
}

const NO_PROGRESS = { visible: false, percent: 0, text: "0%" };
const BUSY_PHASES = ["extracting", "uploading", "checking", "creating"];
const CANCELLABLE_PHASES = ["extracting", "uploading", "checking"];
// Video containers whose audio track the browser copies out before the upload.
const VIDEO_EXTENSIONS = [".mp4", ".mov", ".webm"];

export const initialState = {
  open: false,
  phase: "idle",
  workflow: t("Chưa chọn file."),
  policy: null,
  policyFailed: false,
  policyRequest: 0, // id of the latest policy fetch; other replies are stale
  file: null,
  fileError: null,
  fileRefused: false,
  form: { title: "", date: "", language: "", autoTranscribe: true },
  autoTitle: "",
  uploadId: null,
  sendFile: null, // what the upload sends: the file itself, or the audio the browser extracted from it
  notice: null, // result of the extraction step, shown beside the validation line
  runId: 0, // id of the latest upload run; replies of other runs are stale
  starting: false, // cleaning old uploads and creating the new upload slot
  cancelling: false,
  cleanupWait: [], // upload ids whose DELETE the starting run waits for
  pendingCleanup: [], // upload ids whose DELETE failed; retried on the next file or run
  failure: null, // upload error waiting for its cleanup to finish
  serverReady: false,
  retryable: false,
  createAttemptFailed: false,
  createUncertain: false,
  createRetryPayload: null,
  createRequest: 0, // id of the latest create request
  progress: NO_PROGRESS,
  validation: null,
  formError: null,
};

const isBusy = (state) => BUSY_PHASES.includes(state.phase);
export const isActive = (state) => state.starting || isBusy(state);
const retryingUncertain = (state) => state.createUncertain && Boolean(state.createRetryPayload);
const validFile = (state) => Boolean(state.policy && state.file && !state.fileError && !state.fileRefused);

// A valid file and form are enough: the one button uploads and checks first when needed.
export const canSubmit = (state) =>
  !isActive(state) && state.phase !== "saved" && (retryingUncertain(state) || (validFile(state) && formValuesAreValid(state.form)));

function guidance(state) {
  const { form } = state;
  if (!state.policy) return t("Đang tải giới hạn file của ứng dụng…");
  if (!state.file) return t("Chọn file, nhập tên và chọn ngôn ngữ để tiếp tục.");
  if (!validFile(state)) return t("Chọn một file hợp lệ để tiếp tục.");
  if (!form.title.trim()) return t("Nhập tên cuộc họp để tiếp tục.");
  if (!form.language) return t("Chọn English hoặc Tiếng Việt để tiếp tục.");
  if (state.createUncertain) return t("Gửi lại đúng yêu cầu để xác minh kết quả; máy chủ sẽ không tạo bản trùng.");
  if (isActive(state)) return t("Cuộc họp sẽ được tạo ngay khi máy chủ xác nhận file đã sẵn sàng.");
  if (state.serverReady) return t("File đã sẵn sàng và thông tin cuộc họp đã đầy đủ.");
  return t("Thông tin đã đầy đủ. Bấm “Tạo cuộc họp” để tải lên, kiểm tra và tạo cuộc họp.");
}

function limits(state) {
  if (state.policy) {
    return t("Định dạng: {formats} · Tối đa {size} · Tối đa {duration}.", {
      formats: state.policy.extensions.join(", "),
      size: bytes(state.policy.maxBytes),
      duration: formatDuration(state.policy.maxDurationSeconds),
    });
  }
  return state.policyFailed ? t("Không tải được giới hạn file.") : t("Đang tải giới hạn của ứng dụng…");
}

// Everything the view shows, derived from state.
export function selectView(state) {
  const active = isActive(state);
  const locked = active || retryingUncertain(state);
  const submit = canSubmit(state);
  return {
    limits: limits(state),
    guidance: guidance(state),
    accept: state.policy ? state.policy.extensions.join(",") : "",
    fileInputDisabled: locked || !state.policy,
    changeFileDisabled: locked,
    fieldsDisabled: locked,
    retryHidden: !state.retryable || !state.file || active,
    retryDisabled: !submit,
    cancelHidden: !CANCELLABLE_PHASES.includes(state.phase),
    createDisabled: !submit,
    createLabel: retryingUncertain(state)
      ? t("Xác minh và thử lại")
      : state.createAttemptFailed
        ? t("Thử tạo lại")
        : t("Tạo cuộc họp"),
    closeDisabled: state.phase === "creating" || state.starting,
  };
}

const jsonRequest = (method, body) => ({
  method,
  headers: body === undefined ? { Accept: "application/json" } : { Accept: "application/json", "Content-Type": "application/json" },
  credentials: "same-origin",
  cache: "no-store",
  ...(body === undefined ? {} : { body: JSON.stringify(body) }),
});

const cleanupEffect = (uploadId, purpose) => ({
  type: "fetch",
  key: `shell/cleanup/${uploadId}`,
  url: `/api/uploads/${encodeURIComponent(uploadId)}`,
  init: { method: "DELETE", headers: { Accept: "application/json", "Content-Type": "application/json" }, credentials: "same-origin", cache: "no-store" },
  ok: "shell/upload-cleaned",
  error: "shell/upload-cleanup-failed",
  meta: { uploadId, purpose },
});

const NETWORK = t("Không kết nối được với máy chủ trên máy này.");

// A runner error as the reducer reasons about it: an HTTP answer (api, status, body) or a failed transport.
// fallback is the text for a failure that carries no message at all.
function failureOf(error, fallback) {
  if (error.status !== undefined) return { api: true, status: error.status, body: error.body, message: responseMessage(error.status, error.body) };
  if (error.kind === "network") return { api: false, message: t("Mất kết nối trong lúc truyền file.") };
  if (error.kind === "timeout") return { api: false, message: t("Thời gian truyền file đã hết.") };
  if (error.kind === "aborted") return { api: false, message: t("Đã hủy lượt truyền file.") };
  return { api: false, message: error.message ? NETWORK : fallback };
}
const otherFailure = (message) => ({ api: false, message });

const live = (state, meta) => meta?.runId === state.runId;
const set = (state, patch, effects) => ({ state: { ...state, ...patch }, effects });
const same = (state) => ({ state });

function fresh(state, patch) {
  return {
    ...initialState,
    pendingCleanup: state.pendingCleanup,
    runId: state.runId + 1,
    policyRequest: state.policyRequest + 1,
    createRequest: state.createRequest,
    ...patch,
  };
}

const without = (list, item) => list.filter((entry) => entry !== item);
const withItem = (list, item) => (list.includes(item) ? list : [...list, item]);

function prefillTitle(state, filename) {
  const finalDot = filename.lastIndexOf(".");
  const stem = finalDot >= 0 ? filename.slice(0, finalDot) : filename;
  const suggestion = Array.from(stem.trim()).slice(0, 200).join("").trim();
  // The name is only a suggestion: it never replaces a title the user typed.
  if (state.form.title.trim() && state.form.title !== state.autoTitle) return {};
  return { form: { ...state.form, title: suggestion }, autoTitle: suggestion };
}

function startUpload(state) {
  if (!state.policy || !state.file || state.fileError || isActive(state)) return same(state);
  const stale = [...(state.uploadId ? [state.uploadId] : []), ...without(state.pendingCleanup, state.uploadId)];
  const next = {
    ...state,
    runId: state.runId + 1,
    starting: true,
    retryable: false,
    serverReady: false,
    createAttemptFailed: false,
    createUncertain: false,
    createRetryPayload: null,
    failure: null,
    formError: null,
    progress: NO_PROGRESS,
    validation: null,
    notice: null,
    sendFile: null,
    workflow: t("Đang tạo lượt upload. Chưa truyền byte nào."),
    uploadId: null,
    cleanupWait: stale,
  };
  if (stale.length === 0) return proceed(next);
  return { state: next, effects: stale.map((uploadId) => cleanupEffect(uploadId, "start")) };
}

// After the old uploads are gone: a video goes through the extraction step first.
function proceed(state) {
  if (VIDEO_EXTENSIONS.includes(fileExtension(state.file.name))) return startExtract(state);
  return createUploadSlot({ ...state, sendFile: state.file });
}

function startExtract(state) {
  return {
    state: {
      ...state,
      starting: false,
      phase: "extracting",
      workflow: t("Đang tách audio khỏi video ngay trên trình duyệt (copy luồng, không mã hóa lại). Chưa truyền byte nào."),
      progress: { visible: true, percent: 0, text: "0%" },
    },
    effects: [{
      type: "extract",
      key: "shell/extract",
      file: state.file,
      ok: "shell/extract-done",
      error: "shell/extract-failed",
      progress: "shell/extract-progressed",
      meta: { runId: state.runId },
    }],
  };
}

const EXTRACT_REASONS = {
  unsupported: t("trình duyệt này chưa hỗ trợ"),
  "no-audio": t("video không có luồng audio"),
  codec: t("codec audio không copy được sang file audio"),
};

function createUploadSlot(state) {
  const sent = state.sendFile;
  return {
    state: { ...state, phase: "selected", workflow: t("File đã chọn. Đang chuẩn bị lượt upload mới từ byte đầu tiên.") },
    effects: [{
      type: "fetch",
      key: "shell/upload-create",
      url: "/api/uploads",
      init: jsonRequest("POST", { filename: sent.name, size_bytes: sent.size }),
      ok: "shell/upload-created",
      error: "shell/upload-create-failed",
      meta: { runId: state.runId },
    }],
  };
}

function uploadFailureMessage(failure, cleaned) {
  let reason = failure.message;
  if (failure.status === 413) reason = t("File vượt giới hạn dung lượng. Hãy chọn file nhỏ hơn.");
  if (failure.status === 415) reason = t("Định dạng file chưa được hỗ trợ. Hãy chọn định dạng trong danh sách.");
  if (failure.status === 422) reason = t("{reason} Hãy chọn file phù hợp rồi tải lại từ đầu.", { reason });
  return [
    t("Không tạo cuộc họp. {reason} File chưa được đưa vào xử lý.", { reason }),
    cleaned
      ? t(" Phần upload dở đã được dọn.")
      : t(" Ứng dụng chưa xác nhận đã dọn phần upload dở; hãy thử lại để tạo lượt upload mới."),
  ];
}

// An upload step failed: the old upload is cleaned first, then the message says whether that worked.
function failUpload(state, failure) {
  const base = { ...state, starting: false, serverReady: false, failure };
  if (!state.uploadId) return finishFailure(base, true);
  return {
    state: { ...base, uploadId: null, pendingCleanup: withItem(state.pendingCleanup, state.uploadId), failure: { ...failure, uploadId: state.uploadId } },
    effects: [cleanupEffect(state.uploadId, "failure")],
  };
}

function finishFailure(state, cleaned) {
  const { failure } = state;
  const retryable = !failure.api || failure.status >= 500 || failure.status === 401 || failure.status === 403;
  return set(state, {
    failure: null,
    retryable: retryable && Boolean(state.file),
    fileRefused: !retryable,
    formError: uploadFailureMessage(failure, cleaned),
    validation: t("File chưa sẵn sàng; không có cuộc họp nào được tạo."),
    phase: "error",
    workflow: t("Upload chưa hoàn tất."),
  });
}

function cancelUpload(state) {
  if (!CANCELLABLE_PHASES.includes(state.phase) || state.cancelling) return same(state);
  // The id stays pending until its DELETE is confirmed, so closing while that hangs does not lose it.
  // A failure still waiting for its own DELETE is dropped: the cancel result stands.
  const base = {
    ...state,
    runId: state.runId + 1,
    starting: false,
    serverReady: false,
    cancelling: true,
    uploadId: null,
    failure: null,
    pendingCleanup: state.uploadId ? withItem(state.pendingCleanup, state.uploadId) : state.pendingCleanup,
  };
  const effects = ["extract", "upload", "upload-complete"].map((name) => ({ type: "cancel", key: `shell/${name}` }));
  if (!state.uploadId) return { ...finishCancel(base, true), effects }; // an extraction in flight has no upload id
  return { state: base, effects: [...effects, cleanupEffect(state.uploadId, "cancel")] };
}

function finishCancel(state, cleaned) {
  return set(state, {
    cancelling: false,
    retryable: Boolean(state.file),
    createAttemptFailed: false,
    createUncertain: false,
    createRetryPayload: null,
    formError: [
      t("Đã hủy upload. Không tạo cuộc họp. File chưa được xử lý."),
      cleaned
        ? t(" Phần upload dở đã được dọn.")
        : t(" Chưa xác nhận được việc dọn upload dở; lần thử lại sẽ bắt đầu bằng một upload mới."),
    ],
    validation: t("File chưa sẵn sàng; không có cuộc họp nào được tạo."),
    phase: "aborted",
    workflow: t("Upload đã bị hủy. Có thể tải lại từ đầu."),
  });
}

// A DELETE of a half-made upload ended. A failure keeps the id for a later retry.
function cleanupSettled(state, uploadId, purpose, cleaned) {
  const waited = state.cleanupWait.includes(uploadId);
  const next = {
    ...state,
    pendingCleanup: cleaned ? without(state.pendingCleanup, uploadId) : withItem(state.pendingCleanup, uploadId),
    cleanupWait: without(state.cleanupWait, uploadId),
  };
  if (purpose === "failure" && next.failure) return finishFailure(next, cleaned);
  if (purpose === "cancel" && next.cancelling) return finishCancel(next, cleaned);
  // Only the reply that empties the wait list creates the slot; a repeat for the same id cannot.
  if (waited && next.starting && next.cleanupWait.length === 0) return proceed(next);
  return same(next);
}

function startCreate(state) {
  if (!state.serverReady || !state.uploadId) return same(state);
  if (!state.createRetryPayload && !formValuesAreValid(state.form)) return same(state);
  const payload = state.createRetryPayload || {
    upload_id: state.uploadId,
    title: state.form.title.trim(),
    meeting_date: state.form.date || null,
    language_hint: state.form.language,
  };
  const createRequest = state.createRequest + 1;
  return {
    state: {
      ...state,
      createRequest,
      createAttemptFailed: false,
      createUncertain: false,
      formError: null,
      phase: "creating",
      workflow: t("Đang lưu cuộc họp và metadata."),
    },
    effects: [{
      type: "fetch",
      key: "shell/create",
      url: "/api/meetings",
      init: jsonRequest("POST", payload),
      ok: "shell/meeting-created",
      error: "shell/meeting-create-failed",
      meta: { id: createRequest, payload },
    }],
  };
}

function createFailed(state, failure, payload) {
  const definite = failure.api && failure.status >= 400 && failure.status < 500;
  const code = failure.api && failure.body && failure.body.detail ? failure.body.detail.code : "";
  if (definite && code === "upload_not_ready") {
    return set(state, {
      serverReady: false,
      retryable: Boolean(state.file),
      createAttemptFailed: false,
      createUncertain: false,
      createRetryPayload: null,
      formError: t("File không còn ở trạng thái sẵn sàng. Không có cuộc họp mới được tạo; hãy tải file lại từ đầu."),
      phase: "error",
      workflow: t("File không còn sẵn sàng."),
    });
  }
  const uncertain = !definite;
  const { message } = failure;
  return set(state, {
    createAttemptFailed: true,
    createUncertain: uncertain,
    createRetryPayload: uncertain ? payload : null,
    formError: uncertain
      ? t("{message} Không thể xác nhận cuộc họp đã được tạo hay chưa. Hãy dùng “Xác minh và thử lại”; yêu cầu được gửi lại an toàn với cùng thông tin. Bạn cũng có thể đóng hộp thoại và kiểm tra lại sau.", { message })
      : t("{message} Cuộc họp chưa được lưu. File vẫn sẵn sàng; sửa thông tin nếu cần rồi thử lại.", { message }),
    phase: "error",
    workflow: uncertain ? t("Chưa thể xác nhận kết quả lưu.") : t("Máy chủ từ chối tạo cuộc họp."),
  });
}

function policyFailed(state, message) {
  return set(state, {
    policyFailed: true,
    formError: t("{message} Đóng hộp thoại rồi mở lại để tải chính sách mới.", { message }),
    phase: "error",
    workflow: t("Chưa thể bắt đầu vì thiếu chính sách file."),
  });
}

function selectFile(state, file) {
  if (!file || state.createUncertain || isBusy(state)) return same(state);
  const previous = state.uploadId;
  const retry = without(state.pendingCleanup, previous);
  const effects = [...(previous ? [previous] : []), ...retry].map((uploadId) => cleanupEffect(uploadId, "select"));
  const base = {
    ...state,
    ...prefillTitle(state, file.name),
    file,
    fileError: null,
    fileRefused: false,
    formError: null,
    progress: NO_PROGRESS,
    validation: null,
    serverReady: false,
    retryable: false,
    createAttemptFailed: false,
    createUncertain: false,
    createRetryPayload: null,
    uploadId: null,
    sendFile: null,
    notice: null,
  };
  const refuse = (fileError, workflow) => ({ state: { ...base, fileError, phase: "error", workflow }, effects });
  if (!state.policy) {
    return refuse(t("Không thể chọn file trước khi tải được chính sách định dạng và giới hạn."), t("Chưa thể kiểm tra file."));
  }
  const extension = fileExtension(file.name);
  if (!state.policy.extensions.includes(extension)) {
    return refuse(
      t("Định dạng {extension} chưa được hỗ trợ. Chọn một trong: {formats}.", {
        extension: extension || t("không có phần mở rộng"),
        formats: state.policy.extensions.join(", "),
      }),
      t("File chưa đạt giới hạn đã công bố."),
    );
  }
  if (file.size > state.policy.maxBytes) {
    return refuse(
      t("File lớn hơn giới hạn {size}. Hãy chọn file nhỏ hơn.", { size: bytes(state.policy.maxBytes) }),
      t("File chưa đạt giới hạn đã công bố."),
    );
  }
  return {
    state: { ...base, phase: "selected", workflow: t("Đã chọn file. Nhập thông tin rồi bấm “Tạo cuộc họp”.") },
    effects,
  };
}

function closeDialog(state) {
  if (!state.open || state.phase === "creating" || state.starting) return same(state);
  // A cancel still waiting for its DELETE does not hold the dialog: close leaves that id pending.
  if (!state.cancelling && CANCELLABLE_PHASES.includes(state.phase)) return cancelUpload(state);
  const effects = [{ type: "cancel", key: "shell/policy" }];
  if (!state.createUncertain && state.uploadId) effects.push(cleanupEffect(state.uploadId, "close"));
  return { state: fresh(state, { open: false }), effects };
}

// The browser closed the dialog by itself (a second Escape): make the state agree and stop what is in flight.
function dialogClosed(state) {
  if (!state.open) return same(state);
  // A save in flight finishes and navigates; only the open flag follows the dialog.
  if (state.phase === "creating") return set(state, { open: false });
  const effects = ["policy", "extract", "upload-create", "upload", "upload-complete"].map((name) => ({ type: "cancel", key: `shell/${name}` }));
  const leftover = state.createUncertain ? null : state.uploadId;
  if (leftover) effects.push(cleanupEffect(leftover, "close"));
  const pendingCleanup = leftover ? withItem(state.pendingCleanup, leftover) : state.pendingCleanup;
  return { state: fresh({ ...state, pendingCleanup }, { open: false }), effects };
}

export function reduce(state, action) {
  switch (action.type) {
    // action.stored: the remembered choices the view read from storage.
    case "shell/dialog-opened": {
      if (state.open) return same(state);
      const stored = action.stored ?? {};
      const next = fresh(state, {
        open: true,
        form: {
          ...initialState.form,
          language: ["en", "vi"].includes(stored.language) ? stored.language : "",
          autoTranscribe: stored.autoTranscribe !== "0",
        },
      });
      return {
        state: next,
        effects: [{
          type: "fetch",
          key: "shell/policy",
          url: "/api/uploads/policy",
          init: jsonRequest("GET"),
          ok: "shell/policy-loaded",
          error: "shell/policy-load-failed",
          meta: { id: next.policyRequest },
        }],
      };
    }
    case "shell/policy-loaded": {
      if (!state.open || action.meta.id !== state.policyRequest) return same(state);
      const { policy, error } = normalizePolicy(action.response.body);
      if (error) return policyFailed(state, error);
      return set(state, { policy, phase: "idle", workflow: t("Chưa chọn file.") });
    }
    case "shell/policy-load-failed":
      if (!state.open || action.meta.id !== state.policyRequest) return same(state);
      return policyFailed(state, failureOf(action.error, t("Không tải được chính sách file.")).message);
    case "shell/dialog-close-requested":
      return closeDialog(state);
    case "shell/dialog-closed":
      return dialogClosed(state);
    case "shell/file-selected":
      return selectFile(state, action.file);
    case "shell/multiple-files-dropped":
      return set(state, {
        fileError: t("Chọn từng file một để tạo cuộc họp."),
        phase: "error",
        workflow: t("Chỉ nhận một file cho mỗi cuộc họp."),
      });
    // action.form: { title, date, language } as the view reads them.
    case "shell/form-edited": {
      const form = { ...state.form, title: action.form.title, date: action.form.date, language: action.form.language };
      if (state.createAttemptFailed && state.serverReady) {
        return set(state, {
          form,
          createAttemptFailed: false,
          phase: "ready",
          workflow: t("File đã sẵn sàng. Kiểm tra thông tin rồi thử tạo cuộc họp lại."),
          formError: null,
        });
      }
      return set(state, { form });
    }
    case "shell/auto-transcribe-toggled":
      return set(state, { form: { ...state.form, autoTranscribe: action.value } }, [
        { type: "storage", key: AUTO_TRANSCRIBE_KEY, area: "local", op: "write", value: action.value ? "1" : "0" },
      ]);
    case "shell/submit-requested":
      if (!canSubmit(state)) return same(state);
      return state.serverReady ? startCreate(state) : startUpload(state);
    case "shell/upload-cancel-requested":
      return cancelUpload(state);
    case "shell/extract-progressed": {
      if (!live(state, action.meta) || state.phase !== "extracting") return same(state);
      const percent = Math.min(100, Math.max(0, Math.round(action.ratio * 100)));
      return set(state, { progress: { visible: true, percent, text: `${percent}%` } });
    }
    case "shell/extract-done": {
      if (!live(state, action.meta) || state.phase !== "extracting") return same(state);
      const audio = action.value;
      return createUploadSlot({
        ...state,
        starting: true,
        sendFile: audio,
        notice: t("Đã tách audio khỏi video: gửi {after} thay vì {before}.", { after: bytes(audio.size), before: bytes(state.file.size) }),
      });
    }
    case "shell/extract-failed": {
      if (!live(state, action.meta) || state.phase !== "extracting") return same(state);
      const reason = EXTRACT_REASONS[action.error.kind] ?? t("lỗi khi đọc file video");
      return createUploadSlot({
        ...state,
        starting: true,
        sendFile: state.file,
        notice: t("Không tách được audio trên trình duyệt ({reason}); gửi nguyên file video, có thể lâu hơn.", { reason }),
      });
    }
    case "shell/upload-created": {
      if (!live(state, action.meta) || !state.starting) return same(state);
      const id = action.response.body && action.response.body.id;
      if (typeof id !== "string" || !id) return failUpload(state, otherFailure(t("Máy chủ không trả về mã upload.")));
      return {
        state: {
          ...state,
          uploadId: id,
          starting: false,
          phase: "uploading",
          workflow: t("Đang tải file lên bằng byte progress thực tế."),
          progress: { visible: true, percent: 0, text: "0%" },
        },
        effects: [{
          type: "upload",
          key: "shell/upload",
          url: `/api/uploads/${encodeURIComponent(id)}/content`,
          headers: { "Content-Type": "application/octet-stream" },
          body: state.sendFile,
          ok: "shell/upload-sent",
          error: "shell/upload-failed",
          progress: "shell/upload-progressed",
          meta: { runId: state.runId },
        }],
      };
    }
    case "shell/upload-create-failed":
    case "shell/upload-failed":
    case "shell/upload-completion-failed":
      if (!live(state, action.meta)) return same(state);
      return failUpload(state, failureOf(action.error, t("Máy chủ chưa thể nhận file.")));
    case "shell/upload-progressed": {
      if (!live(state, action.meta) || state.phase !== "uploading") return same(state);
      if (action.lengthComputable && action.total > 0) {
        const percent = Math.min(100, Math.round((action.loaded / action.total) * 100));
        return set(state, { progress: { visible: true, percent, text: `${percent}%` } });
      }
      return set(state, { progress: { ...state.progress, visible: true, text: t("{size} đã gửi", { size: bytes(action.loaded) }) } });
    }
    case "shell/upload-sent":
      if (!live(state, action.meta) || state.phase !== "uploading") return same(state);
      return {
        state: {
          ...state,
          phase: "checking",
          workflow: t("Đã truyền xong byte. Máy chủ đang kiểm tra định dạng, thời lượng và nội dung file."),
          validation: t("Đang kiểm tra file trên máy chủ. Đây là bước xác nhận file, không phải tiến độ xử lý transcript."),
          progress: { visible: true, percent: 100, text: "100%" },
        },
        effects: [{
          type: "fetch",
          key: "shell/upload-complete",
          url: `/api/uploads/${encodeURIComponent(state.uploadId)}/complete`,
          init: jsonRequest("POST", {}),
          ok: "shell/upload-completed",
          error: "shell/upload-completion-failed",
          meta: { runId: state.runId },
        }],
      };
    case "shell/upload-completed": {
      if (!live(state, action.meta) || state.phase !== "checking") return same(state);
      const body = action.response.body;
      if (!body || body.status !== "ready") {
        return failUpload(state, otherFailure(t("Máy chủ chưa xác nhận file ở trạng thái ready. Không thể tạo cuộc họp lúc này.")));
      }
      // The one button goes on to create the meeting.
      return startCreate({
        ...state,
        serverReady: true,
        retryable: false,
        progress: { visible: true, percent: 100, text: "100%" },
        validation: t("File đã qua kiểm tra và sẵn sàng tạo cuộc họp."),
        phase: "ready",
        workflow: t("File đã sẵn sàng. Bạn có thể tạo cuộc họp."),
      });
    }
    case "shell/meeting-created": {
      if (state.phase !== "creating" || action.meta.id !== state.createRequest) return same(state);
      const { body } = action.response;
      const meeting = body && body.meeting && typeof body.meeting === "object" ? body.meeting : body;
      if (!meeting || typeof meeting.id !== "string" || !meeting.id) {
        return createFailed(state, otherFailure(t("Máy chủ không trả về mã cuộc họp sau khi lưu.")), action.meta.payload);
      }
      return {
        state: { ...state, phase: "saved", workflow: t("Cuộc họp đã được lưu."), serverReady: false, createRetryPayload: null },
        effects: [
          { type: "storage", key: LAST_LANGUAGE_KEY, area: "local", op: "write", value: action.meta.payload.language_hint },
          ...(state.form.autoTranscribe
            ? [{ type: "storage", key: `${AUTO_TRANSCRIBE_HANDOFF_PREFIX}${meeting.id}`, area: "session", op: "write", value: "1" }]
            : []),
          { type: "navigate", key: "shell/navigate", url: `/meetings/${encodeURIComponent(meeting.id)}` },
        ],
      };
    }
    case "shell/meeting-create-failed":
      if (state.phase !== "creating" || action.meta.id !== state.createRequest) return same(state);
      return createFailed(state, failureOf(action.error, t("Không thể xác nhận kết quả lưu cuộc họp.")), action.meta.payload);
    case "shell/upload-cleaned":
      return cleanupSettled(state, action.meta.uploadId, action.meta.purpose, true);
    case "shell/upload-cleanup-failed":
      // The server no longer has the upload: that is as clean as it gets.
      return cleanupSettled(state, action.meta.uploadId, action.meta.purpose, action.error.status === 404);
    default:
      return same(state);
  }
}
