"use strict";

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
const createButton = document.querySelector("#create-meeting");
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
const STATE_LABELS = {
  idle: t("Chưa chọn file"),
  selected: t("Đã chọn file"),
  uploading: t("Đang tải lên"),
  checking: t("Đang kiểm tra"),
  ready: t("Sẵn sàng tạo"),
  creating: t("Đang tạo"),
  saved: t("Đã tạo"),
  error: t("Có lỗi"),
  aborted: t("Đã hủy"),
};
const LAST_LANGUAGE_KEY = "asr-en-vi:last-language-hint";
const AUTO_TRANSCRIBE_KEY = "asr-en-vi:auto-transcribe";
// history.js removes this one-shot key before it sends the transcription request.
const AUTO_TRANSCRIBE_HANDOFF_PREFIX = "asr-en-vi:auto-transcribe:";
const appState = {
  state: "idle",
  policy: null,
  file: null,
  autoTitle: "",
  uploadId: null,
  uploadRequest: null,
  completeController: null,
  startingUpload: false,
  runId: 0,
  policyRunId: 0,
  retryableUpload: false,
  fileRefused: false,
  serverReady: false,
  createAttemptFailed: false,
  createUncertain: false,
  createRetryPayload: null,
  pendingCleanup: new Set(),
};

class ApiError extends Error {
  constructor(message, status, payload) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.payload = payload;
  }
}

class TransferError extends Error {
  constructor(message, kind, status = 0) {
    super(message);
    this.name = "TransferError";
    this.kind = kind;
    this.status = status;
  }
}

function responseMessage(status, payload) {
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
  if (!response.ok) throw new ApiError(responseMessage(response.status, payload), response.status, payload);
  return payload;
}

function policyField(policy, names) {
  for (const name of names) {
    if (policy[name] !== undefined && policy[name] !== null) return policy[name];
  }
  return undefined;
}

function normalizePolicy(payload) {
  const source = payload && payload.policy && typeof payload.policy === "object" ? payload.policy : payload;
  if (!source || typeof source !== "object") throw new Error(t("Chính sách file không đúng định dạng."));
  const rawExtensions = policyField(source, ["supported_extensions", "extensions", "allowed_extensions"]);
  const maxBytes = Number(policyField(source, ["max_bytes", "max_size_bytes", "max_file_size_bytes"]));
  const maxDurationSeconds = Number(policyField(source, ["max_duration_seconds", "max_duration_s"]));
  if (!Array.isArray(rawExtensions) || !Number.isFinite(maxBytes) || maxBytes <= 0 || !Number.isFinite(maxDurationSeconds) || maxDurationSeconds <= 0) {
    throw new Error(t("Chính sách chưa công bố đủ định dạng, dung lượng và thời lượng tối đa."));
  }
  const extensions = rawExtensions
    .map((extension) => String(extension).trim().toLowerCase())
    .map((extension) => (extension.startsWith(".") ? extension : `.${extension}`))
    .filter((extension) => /^\.[a-z0-9][a-z0-9.+_-]*$/.test(extension));
  if (extensions.length === 0) throw new Error(t("Chính sách chưa công bố định dạng file được hỗ trợ."));
  return { extensions: [...new Set(extensions)], maxBytes, maxDurationSeconds };
}

function formatBytes(value) {
  if (value < 1024) return `${value} byte`;
  const units = ["KiB", "MiB", "GiB"];
  let amount = value;
  let unit = "byte";
  for (const nextUnit of units) {
    amount /= 1024;
    unit = nextUnit;
    if (amount < 1024 || nextUnit === "GiB") break;
  }
  return `${new Intl.NumberFormat(UI_LOCALE, { maximumFractionDigits: 1 }).format(amount)} ${unit}`;
}

function formatDuration(seconds) {
  if (seconds >= 3600 && seconds % 3600 === 0) return t("{n} giờ", { n: seconds / 3600 });
  if (seconds >= 60 && seconds % 60 === 0) return t("{n} phút", { n: seconds / 60 });
  if (seconds >= 60) return t("{n} phút", { n: new Intl.NumberFormat(UI_LOCALE, { maximumFractionDigits: 1 }).format(seconds / 60) });
  return t("{n} giây", { n: seconds });
}

function showFormError(message) {
  formError.textContent = message;
  formError.hidden = !message;
}

function setState(state, message) {
  appState.state = state;
  dialog.dataset.state = state;
  stateLabel.textContent = STATE_LABELS[state];
  workflowState.textContent = message;
  updateActions();
}

function readLocal(key) {
  try {
    return window.localStorage.getItem(key);
  } catch {
    return null;
  }
}

function writeLocal(key, value) {
  try {
    window.localStorage.setItem(key, value);
  } catch {
    // The choice is simply not remembered.
  }
}

// The last language and the auto-transcribe choice are the dialog's defaults.
function applyRememberedChoices() {
  const language = readLocal(LAST_LANGUAGE_KEY);
  if (["en", "vi"].includes(language)) {
    form.querySelector(`input[name="language_hint"][value="${language}"]`).checked = true;
  }
  autoTranscribeInput.checked = readLocal(AUTO_TRANSCRIBE_KEY) !== "0";
}

function currentLanguage() {
  const checked = form.querySelector('input[name="language_hint"]:checked');
  return checked ? checked.value : "";
}

function formValuesAreValid() {
  const title = titleInput.value.trim();
  const titleLength = Array.from(title).length;
  const language = currentLanguage();
  const meetingDate = dateInput.value;
  const dateIsValid = !meetingDate || /^\d{4}-\d{2}-\d{2}$/.test(meetingDate);
  return Boolean(title && titleLength <= 200 && ["en", "vi"].includes(language) && dateIsValid);
}

function updateActions() {
  const active = appState.startingUpload || ["uploading", "checking", "creating"].includes(appState.state);
  const validFile = Boolean(appState.policy && appState.file && !fileError.textContent && !appState.fileRefused);
  const retryingUncertainCreate = appState.createUncertain && Boolean(appState.createRetryPayload);
  // A valid file and form are enough: the one button uploads and checks first when needed.
  const canSubmit = !active && appState.state !== "saved"
    && (retryingUncertainCreate || (validFile && formValuesAreValid()));

  fileInput.disabled = active || retryingUncertainCreate || !appState.policy;
  fileDrop.setAttribute("aria-disabled", String(fileInput.disabled));
  document.querySelector("#change-file").disabled = active || retryingUncertainCreate;
  retryUploadButton.hidden = !appState.retryableUpload || !appState.file || active;
  retryUploadButton.disabled = !canSubmit;
  cancelUploadButton.hidden = !["uploading", "checking"].includes(appState.state);
  createButton.disabled = !canSubmit;
  createButton.textContent = retryingUncertainCreate
    ? t("Xác minh và thử lại")
    : appState.createAttemptFailed
      ? t("Thử tạo lại")
      : t("Tạo cuộc họp");
  closeDialogButton.disabled = appState.state === "creating" || appState.startingUpload;
  titleInput.disabled = active || retryingUncertainCreate;
  dateInput.disabled = active || retryingUncertainCreate;
  autoTranscribeInput.disabled = active || retryingUncertainCreate;
  for (const languageInput of form.querySelectorAll('input[name="language_hint"]')) {
    languageInput.disabled = active || retryingUncertainCreate;
  }

  if (!appState.policy) {
    createGuidance.textContent = t("Đang tải giới hạn file của ứng dụng…");
  } else if (!appState.file) {
    createGuidance.textContent = t("Chọn file, nhập tên và chọn ngôn ngữ để tiếp tục.");
  } else if (!validFile) {
    createGuidance.textContent = t("Chọn một file hợp lệ để tiếp tục.");
  } else if (!titleInput.value.trim()) {
    createGuidance.textContent = t("Nhập tên cuộc họp để tiếp tục.");
  } else if (!currentLanguage()) {
    createGuidance.textContent = t("Chọn English hoặc Tiếng Việt để tiếp tục.");
  } else if (appState.createUncertain) {
    createGuidance.textContent = t("Gửi lại đúng yêu cầu để xác minh kết quả; máy chủ sẽ không tạo bản trùng.");
  } else if (active) {
    createGuidance.textContent = t("Cuộc họp sẽ được tạo ngay khi máy chủ xác nhận file đã sẵn sàng.");
  } else if (appState.serverReady) {
    createGuidance.textContent = t("File đã sẵn sàng và thông tin cuộc họp đã đầy đủ.");
  } else {
    createGuidance.textContent = t("Thông tin đã đầy đủ. Bấm “Tạo cuộc họp” để tải lên, kiểm tra và tạo cuộc họp.");
  }
}

function renderPolicy(policy) {
  appState.policy = policy;
  fileInput.accept = policy.extensions.join(",");
  fileInput.disabled = false;
  fileLimits.textContent = t("Định dạng: {formats} · Tối đa {size} · Tối đa {duration}.", {
    formats: policy.extensions.join(", "),
    size: formatBytes(policy.maxBytes),
    duration: formatDuration(policy.maxDurationSeconds),
  });
  updateActions();
}

function clearProgress() {
  uploadProgress.value = 0;
  uploadProgressValue.textContent = "0%";
  transferProgress.hidden = true;
  validationState.textContent = "";
}

function showSelectedFile(file) {
  selectedFile.hidden = !file;
  if (!file) {
    selectedFileName.textContent = "";
    selectedFileSize.textContent = "";
    return;
  }
  selectedFileName.textContent = file.name;
  selectedFileSize.textContent = formatBytes(file.size);
}

function fileExtension(filename) {
  const finalDot = filename.lastIndexOf(".");
  return finalDot >= 0 ? filename.slice(finalDot).toLowerCase() : "";
}

// The name is only a suggestion: it never replaces a title the user typed.
function prefillTitle(filename) {
  const finalDot = filename.lastIndexOf(".");
  const stem = finalDot >= 0 ? filename.slice(0, finalDot) : filename;
  const suggestion = Array.from(stem.trim()).slice(0, 200).join("").trim();
  if (titleInput.value.trim() && titleInput.value !== appState.autoTitle) return;
  titleInput.value = suggestion;
  appState.autoTitle = suggestion;
}

async function cleanupUpload(uploadId) {
  if (!uploadId) return true;
  try {
    const response = await fetch(`/api/uploads/${encodeURIComponent(uploadId)}`, {
      method: "DELETE",
      headers: { Accept: "application/json", "Content-Type": "application/json" },
      credentials: "same-origin",
      cache: "no-store",
    });
    return response.ok || response.status === 404;
  } catch {
    return false;
  }
}

async function cleanupCurrentUpload() {
  const uploadId = appState.uploadId;
  if (!uploadId) return true;
  appState.uploadId = null;
  const cleaned = await cleanupUpload(uploadId);
  if (!cleaned) appState.pendingCleanup.add(uploadId);
  return cleaned;
}

async function cleanupPendingUploads() {
  const pending = [...appState.pendingCleanup];
  for (const uploadId of pending) {
    if (await cleanupUpload(uploadId)) appState.pendingCleanup.delete(uploadId);
  }
  return appState.pendingCleanup.size === 0;
}

async function selectFile(file) {
  if (!file || appState.createUncertain || ["uploading", "checking", "creating"].includes(appState.state)) return;
  fileInput.value = "";
  showFormError("");
  fileError.textContent = "";
  clearProgress();
  appState.serverReady = false;
  appState.retryableUpload = false;
  appState.fileRefused = false;
  appState.createAttemptFailed = false;
  appState.createUncertain = false;
  appState.createRetryPayload = null;
  const previousUpload = appState.uploadId;
  if (previousUpload) void cleanupCurrentUpload();
  void cleanupPendingUploads();
  appState.file = file;
  showSelectedFile(file);
  prefillTitle(file.name);

  if (!appState.policy) {
    fileError.textContent = t("Không thể chọn file trước khi tải được chính sách định dạng và giới hạn.");
    setState("error", t("Chưa thể kiểm tra file."));
    updateActions();
    return;
  }
  const extension = fileExtension(file.name);
  if (!appState.policy.extensions.includes(extension)) {
    fileError.textContent = t("Định dạng {extension} chưa được hỗ trợ. Chọn một trong: {formats}.", {
      extension: extension || t("không có phần mở rộng"),
      formats: appState.policy.extensions.join(", "),
    });
    setState("error", t("File chưa đạt giới hạn đã công bố."));
    updateActions();
    return;
  }
  if (file.size > appState.policy.maxBytes) {
    fileError.textContent = t("File lớn hơn giới hạn {size}. Hãy chọn file nhỏ hơn.", { size: formatBytes(appState.policy.maxBytes) });
    setState("error", t("File chưa đạt giới hạn đã công bố."));
    updateActions();
    return;
  }
  setState("selected", t("Đã chọn file. Nhập thông tin rồi bấm “Tạo cuộc họp”."));
}

function uploadWithProgress(uploadId, file, runId) {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    appState.uploadRequest = xhr;
    xhr.open("PUT", `/api/uploads/${encodeURIComponent(uploadId)}/content`, true);
    xhr.withCredentials = true;
    xhr.setRequestHeader("Content-Type", "application/octet-stream");
    xhr.upload.onprogress = (event) => {
      if (runId !== appState.runId) return;
      transferProgress.hidden = false;
      if (event.lengthComputable && event.total > 0) {
        const percent = Math.min(100, Math.round((event.loaded / event.total) * 100));
        uploadProgress.value = percent;
        uploadProgressValue.textContent = `${percent}%`;
      } else {
        uploadProgressValue.textContent = t("{size} đã gửi", { size: formatBytes(event.loaded) });
      }
    };
    xhr.onload = () => {
      appState.uploadRequest = null;
      if (xhr.status >= 200 && xhr.status < 300) {
        uploadProgress.value = 100;
        uploadProgressValue.textContent = "100%";
        resolve();
        return;
      }
      let payload = null;
      try {
        payload = JSON.parse(xhr.responseText);
      } catch {
        payload = null;
      }
      reject(new ApiError(responseMessage(xhr.status, payload), xhr.status, payload));
    };
    xhr.onerror = () => {
      appState.uploadRequest = null;
      reject(new TransferError(t("Mất kết nối trong lúc truyền file."), "network"));
    };
    xhr.ontimeout = () => {
      appState.uploadRequest = null;
      reject(new TransferError(t("Thời gian truyền file đã hết."), "timeout"));
    };
    xhr.onabort = () => {
      appState.uploadRequest = null;
      reject(new TransferError(t("Đã hủy lượt truyền file."), "aborted"));
    };
    xhr.send(file);
  });
}

function uploadFailureCopy(error, cleanupSucceeded) {
  let reason = error && error.message ? error.message : t("Máy chủ chưa thể nhận file.");
  if (error && error.status === 413) reason = t("File vượt giới hạn dung lượng. Hãy chọn file nhỏ hơn.");
  if (error && error.status === 415) reason = t("Định dạng file chưa được hỗ trợ. Hãy chọn định dạng trong danh sách.");
  if (error && error.status === 422) reason = t("{reason} Hãy chọn file phù hợp rồi tải lại từ đầu.", { reason });
  let message = t("Không tạo cuộc họp. {reason} File chưa được đưa vào xử lý.", { reason });
  if (cleanupSucceeded) message += t(" Phần upload dở đã được dọn.");
  else message += t(" Ứng dụng chưa xác nhận đã dọn phần upload dở; hãy thử lại để tạo lượt upload mới.");
  return message;
}

async function startUpload() {
  if (!appState.policy || !appState.file || fileError.textContent || appState.startingUpload || ["uploading", "checking", "creating"].includes(appState.state)) return false;
  const runId = ++appState.runId;
  const file = appState.file;
  appState.startingUpload = true;
  appState.retryableUpload = false;
  appState.serverReady = false;
  appState.createAttemptFailed = false;
  appState.createUncertain = false;
  appState.createRetryPayload = null;
  showFormError("");
  fileError.textContent = "";
  clearProgress();
  validationState.textContent = "";
  workflowState.textContent = t("Đang tạo lượt upload. Chưa truyền byte nào.");
  updateActions();
  await cleanupCurrentUpload();
  await cleanupPendingUploads();
  if (runId !== appState.runId) {
    appState.startingUpload = false;
    updateActions();
    return false;
  }

  setState("selected", t("File đã chọn. Đang chuẩn bị lượt upload mới từ byte đầu tiên."));
  try {
    const created = await requestJson("/api/uploads", {
      method: "POST",
      body: JSON.stringify({ filename: file.name, size_bytes: file.size }),
    });
    const uploadId = created && typeof created.id === "string" ? created.id : "";
    if (!uploadId) throw new Error(t("Máy chủ không trả về mã upload."));
    appState.uploadId = uploadId;
    appState.startingUpload = false;
    setState("uploading", t("Đang tải file lên bằng byte progress thực tế."));
    transferProgress.hidden = false;
    await uploadWithProgress(uploadId, file, runId);
    if (runId !== appState.runId) return false;

    appState.uploadRequest = null;
    setState("checking", t("Đã truyền xong byte. Máy chủ đang kiểm tra định dạng, thời lượng và nội dung file."));
    validationState.textContent = t("Đang kiểm tra file trên máy chủ. Đây là bước xác nhận file, không phải tiến độ xử lý transcript.");
    appState.completeController = new AbortController();
    const completed = await requestJson(`/api/uploads/${encodeURIComponent(uploadId)}/complete`, {
      method: "POST",
      body: JSON.stringify({}),
      signal: appState.completeController.signal,
    });
    appState.completeController = null;
    if (runId !== appState.runId) return false;
    if (!completed || completed.status !== "ready") {
      throw new Error(t("Máy chủ chưa xác nhận file ở trạng thái ready. Không thể tạo cuộc họp lúc này."));
    }
    appState.serverReady = true;
    appState.retryableUpload = false;
    uploadProgress.value = 100;
    uploadProgressValue.textContent = "100%";
    validationState.textContent = t("File đã qua kiểm tra và sẵn sàng tạo cuộc họp.");
    setState("ready", t("File đã sẵn sàng. Bạn có thể tạo cuộc họp."));
    return true;
  } catch (error) {
    appState.startingUpload = false;
    appState.completeController = null;
    if (runId !== appState.runId) return false;
    appState.uploadRequest = null;
    appState.serverReady = false;
    const cleanupSucceeded = await cleanupCurrentUpload();
    if (runId !== appState.runId) return false;
    const retryable = !(error instanceof ApiError) || error.status >= 500 || error.status === 401 || error.status === 403;
    appState.retryableUpload = retryable && Boolean(appState.file);
    appState.fileRefused = !retryable;
    const message = uploadFailureCopy(error, cleanupSucceeded);
    showFormError(message);
    validationState.textContent = t("File chưa sẵn sàng; không có cuộc họp nào được tạo.");
    setState(error && error.kind === "aborted" ? "aborted" : "error", t("Upload chưa hoàn tất."));
    return false;
  }
}

async function abortUpload() {
  if (!["uploading", "checking"].includes(appState.state)) return;
  appState.runId += 1;
  const xhr = appState.uploadRequest;
  const controller = appState.completeController;
  appState.uploadRequest = null;
  appState.completeController = null;
  appState.startingUpload = false;
  if (xhr) xhr.abort();
  if (controller) controller.abort();
  appState.serverReady = false;
  const cleanupSucceeded = await cleanupCurrentUpload();
  appState.retryableUpload = Boolean(appState.file);
  appState.createAttemptFailed = false;
  appState.createUncertain = false;
  appState.createRetryPayload = null;
  showFormError(t("Đã hủy upload. Không tạo cuộc họp. File chưa được xử lý.") + (cleanupSucceeded
    ? t(" Phần upload dở đã được dọn.")
    : t(" Chưa xác nhận được việc dọn upload dở; lần thử lại sẽ bắt đầu bằng một upload mới.")));
  validationState.textContent = t("File chưa sẵn sàng; không có cuộc họp nào được tạo.");
  setState("aborted", t("Upload đã bị hủy. Có thể tải lại từ đầu."));
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

function resetDialog() {
  appState.runId += 1;
  appState.policyRunId += 1;
  appState.state = "idle";
  appState.policy = null;
  appState.file = null;
  appState.autoTitle = "";
  appState.uploadId = null;
  appState.uploadRequest = null;
  appState.completeController = null;
  appState.startingUpload = false;
  appState.retryableUpload = false;
  appState.fileRefused = false;
  appState.serverReady = false;
  appState.createAttemptFailed = false;
  appState.createUncertain = false;
  appState.createRetryPayload = null;
  form.reset();
  applyRememberedChoices();
  fileInput.value = "";
  fileInput.accept = "";
  fileInput.disabled = true;
  fileDrop.setAttribute("aria-disabled", "true");
  fileLimits.textContent = t("Đang tải giới hạn của ứng dụng…");
  fileError.textContent = "";
  showSelectedFile(null);
  showFormError("");
  clearProgress();
  validationState.textContent = "";
  dialog.dataset.state = "idle";
  stateLabel.textContent = STATE_LABELS.idle;
  workflowState.textContent = t("Chưa chọn file.");
  updateActions();
}

async function closeDialog() {
  if (!dialog.open || appState.state === "creating" || appState.startingUpload) return;
  if (["uploading", "checking"].includes(appState.state)) {
    await abortUpload();
    return;
  }
  if (!appState.createUncertain) await cleanupCurrentUpload();
  appState.policyRunId += 1;
  dialog.close();
  resetDialog();
}

async function openDialog() {
  if (dialog.open) return;
  resetDialog();
  dialog.showModal();
  titleInput.focus();
  const policyRunId = ++appState.policyRunId;
  try {
    const payload = await requestJson("/api/uploads/policy");
    if (!dialog.open || policyRunId !== appState.policyRunId) return;
    renderPolicy(normalizePolicy(payload));
    setState("idle", t("Chưa chọn file."));
  } catch (error) {
    if (!dialog.open || policyRunId !== appState.policyRunId) return;
    const message = error instanceof ApiError ? error.message : (error && error.message) || t("Không tải được chính sách file.");
    fileLimits.textContent = t("Không tải được giới hạn file.");
    showFormError(t("{message} Đóng hộp thoại rồi mở lại để tải chính sách mới.", { message }));
    setState("error", t("Chưa thể bắt đầu vì thiếu chính sách file."));
  }
}

async function createMeeting() {
  if (!appState.serverReady || !appState.uploadId) return;
  if (!appState.createRetryPayload && !formValuesAreValid()) return;
  const payload = appState.createRetryPayload || {
      upload_id: appState.uploadId,
      title: titleInput.value.trim(),
      meeting_date: dateInput.value || null,
      language_hint: currentLanguage(),
    };
  appState.createAttemptFailed = false;
  appState.createUncertain = false;
  showFormError("");
  setState("creating", t("Đang lưu cuộc họp và metadata."));
  try {
    const result = await requestJson("/api/meetings", {
      method: "POST",
      body: JSON.stringify(payload),
    });
    const meeting = result && result.meeting && typeof result.meeting === "object" ? result.meeting : result;
    if (!meeting || typeof meeting.id !== "string" || !meeting.id) {
      throw new Error(t("Máy chủ không trả về mã cuộc họp sau khi lưu."));
    }
    setState("saved", t("Cuộc họp đã được lưu."));
    appState.serverReady = false;
    appState.createRetryPayload = null;
    writeLocal(LAST_LANGUAGE_KEY, payload.language_hint);
    if (autoTranscribeInput.checked) {
      try {
        window.sessionStorage.setItem(`${AUTO_TRANSCRIBE_HANDOFF_PREFIX}${meeting.id}`, "1");
      } catch {
        // Without the handoff the meeting opens with the manual start button.
      }
    }
    window.location.assign(`/meetings/${encodeURIComponent(meeting.id)}`);
  } catch (error) {
    const definiteResponse = error instanceof ApiError && error.status >= 400 && error.status < 500;
    const errorCode = error instanceof ApiError && error.payload && error.payload.detail
      ? error.payload.detail.code
      : "";
    if (definiteResponse && errorCode === "upload_not_ready") {
      appState.serverReady = false;
      appState.retryableUpload = Boolean(appState.file);
      appState.createAttemptFailed = false;
      appState.createUncertain = false;
      appState.createRetryPayload = null;
      showFormError(t("File không còn ở trạng thái sẵn sàng. Không có cuộc họp mới được tạo; hãy tải file lại từ đầu."));
      setState("error", t("File không còn sẵn sàng."));
      return;
    }
    appState.createAttemptFailed = true;
    appState.createUncertain = !definiteResponse;
    appState.createRetryPayload = definiteResponse ? null : payload;
    const message = error instanceof ApiError ? error.message : (error && error.message) || t("Không thể xác nhận kết quả lưu cuộc họp.");
    if (appState.createUncertain) {
      showFormError(t("{message} Không thể xác nhận cuộc họp đã được tạo hay chưa. Hãy dùng “Xác minh và thử lại”; yêu cầu được gửi lại an toàn với cùng thông tin. Bạn cũng có thể đóng hộp thoại và kiểm tra lại sau.", { message }));
    } else {
      showFormError(t("{message} Cuộc họp chưa được lưu. File vẫn sẵn sàng; sửa thông tin nếu cần rồi thử lại.", { message }));
    }
    setState("error", appState.createUncertain ? t("Chưa thể xác nhận kết quả lưu.") : t("Máy chủ từ chối tạo cuộc họp."));
  }
}

// One button: upload and check first when the file is not ready yet, then create the meeting.
async function createMeetingFlow() {
  if (createButton.disabled) return;
  if (!appState.serverReady && !(await startUpload())) return;
  await createMeeting();
}

for (const button of document.querySelectorAll("[data-open-meeting-dialog]")) {
  button.addEventListener("click", () => void openDialog());
}

closeDialogButton.addEventListener("click", () => void closeDialog());
document.querySelector("#change-file").addEventListener("click", () => fileInput.click());
fileInput.addEventListener("change", () => {
  if (fileInput.files && fileInput.files.length > 0) void selectFile(fileInput.files[0]);
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
  if (files.length > 1) {
    fileError.textContent = t("Chọn từng file một để tạo cuộc họp.");
    setState("error", t("Chỉ nhận một file cho mỗi cuộc họp."));
    return;
  }
  void selectFile(files[0]);
});

retryUploadButton.addEventListener("click", () => void createMeetingFlow());
cancelUploadButton.addEventListener("click", () => void abortUpload());
form.addEventListener("submit", (event) => {
  event.preventDefault();
  void createMeetingFlow();
});
autoTranscribeInput.addEventListener("change", () => {
  writeLocal(AUTO_TRANSCRIBE_KEY, autoTranscribeInput.checked ? "1" : "0");
});

function onFormChange() {
  if (appState.createAttemptFailed && appState.serverReady) {
    appState.createAttemptFailed = false;
    setState("ready", t("File đã sẵn sàng. Kiểm tra thông tin rồi thử tạo cuộc họp lại."));
    showFormError("");
  }
  updateActions();
}

titleInput.addEventListener("input", onFormChange);
dateInput.addEventListener("change", onFormChange);
for (const languageInput of form.querySelectorAll('input[name="language_hint"]')) {
  languageInput.addEventListener("change", onFormChange);
}

dialog.addEventListener("cancel", (event) => {
  event.preventDefault();
  void closeDialog();
});
dialog.addEventListener("click", (event) => {
  if (event.target === dialog) void closeDialog();
});
