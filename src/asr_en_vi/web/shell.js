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
const createButton = document.querySelector("#create-meeting");
const uploadButton = document.querySelector("#start-upload");
const retryUploadButton = document.querySelector("#retry-upload");
const cancelUploadButton = document.querySelector("#cancel-upload");
const closeDialogButton = document.querySelector("#close-dialog");
const workflowState = document.querySelector("#workflow-state");
const stateCode = document.querySelector("#state-code");
const validationState = document.querySelector("#validation-state");
const createGuidance = document.querySelector("#create-guidance");
const formError = document.querySelector("#form-error");
const transferProgress = document.querySelector("#transfer-progress");
const uploadProgress = document.querySelector("#upload-progress");
const uploadProgressValue = document.querySelector("#upload-progress-value");
const appState = {
  state: "idle",
  policy: null,
  file: null,
  uploadId: null,
  uploadRequest: null,
  completeController: null,
  startingUpload: false,
  runId: 0,
  policyRunId: 0,
  retryableUpload: false,
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
  if (status === 401) return "Phiên truy cập không còn hợp lệ. Hãy mở lại link trong terminal.";
  if (status === 403) return "Yêu cầu bị từ chối. Hãy tải lại workspace rồi thử lại.";
  if (status === 404) return "Không tìm thấy dữ liệu yêu cầu.";
  if (status === 409) return "Dữ liệu đã thay đổi hoặc đang được sử dụng. Hãy tải lại rồi thử lại.";
  if (status === 413) return "File vượt quá giới hạn dung lượng được công bố.";
  if (status === 415) return "Định dạng file này chưa được hỗ trợ. Hãy chọn định dạng trong danh sách.";
  if (status === 422) return "File không đạt yêu cầu. Hãy kiểm tra định dạng, thời lượng và nội dung file.";
  if (status >= 500) return "Máy chủ chưa thể hoàn tất yêu cầu. Hãy thử lại sau.";
  return "Máy chủ chưa thể hoàn tất yêu cầu. Hãy kiểm tra thông tin rồi thử lại.";
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
    const networkError = new Error("Không kết nối được với máy chủ trên máy này.");
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
  if (!source || typeof source !== "object") throw new Error("Chính sách file không đúng định dạng.");
  const rawExtensions = policyField(source, ["supported_extensions", "extensions", "allowed_extensions"]);
  const maxBytes = Number(policyField(source, ["max_bytes", "max_size_bytes", "max_file_size_bytes"]));
  const maxDurationSeconds = Number(policyField(source, ["max_duration_seconds", "max_duration_s"]));
  if (!Array.isArray(rawExtensions) || !Number.isFinite(maxBytes) || maxBytes <= 0 || !Number.isFinite(maxDurationSeconds) || maxDurationSeconds <= 0) {
    throw new Error("Chính sách chưa công bố đủ định dạng, dung lượng và thời lượng tối đa.");
  }
  const extensions = rawExtensions
    .map((extension) => String(extension).trim().toLowerCase())
    .map((extension) => (extension.startsWith(".") ? extension : `.${extension}`))
    .filter((extension) => /^\.[a-z0-9][a-z0-9.+_-]*$/.test(extension));
  if (extensions.length === 0) throw new Error("Chính sách chưa công bố định dạng file được hỗ trợ.");
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
  return `${new Intl.NumberFormat("vi-VN", { maximumFractionDigits: 1 }).format(amount)} ${unit}`;
}

function formatDuration(seconds) {
  if (seconds >= 3600 && seconds % 3600 === 0) return `${seconds / 3600} giờ`;
  if (seconds >= 60 && seconds % 60 === 0) return `${seconds / 60} phút`;
  if (seconds >= 60) return `${new Intl.NumberFormat("vi-VN", { maximumFractionDigits: 1 }).format(seconds / 60)} phút`;
  return `${seconds} giây`;
}

function showFormError(message) {
  formError.textContent = message;
  formError.hidden = !message;
}

function setState(state, message) {
  appState.state = state;
  dialog.dataset.state = state;
  stateCode.textContent = state.toUpperCase();
  workflowState.textContent = message;
  updateActions();
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
  const validFile = Boolean(appState.policy && appState.file && !fileError.textContent);
  const selected = appState.state === "selected";
  const retryingUncertainCreate = appState.createUncertain && Boolean(appState.createRetryPayload);
  const canSubmit = appState.serverReady && (retryingUncertainCreate || formValuesAreValid()) && !active;

  fileInput.disabled = active || retryingUncertainCreate || !appState.policy;
  fileDrop.setAttribute("aria-disabled", String(fileInput.disabled));
  document.querySelector("#change-file").disabled = active || retryingUncertainCreate;
  uploadButton.disabled = !validFile || !selected || appState.startingUpload;
  uploadButton.hidden = !selected && appState.state !== "idle";
  retryUploadButton.hidden = !appState.retryableUpload || !appState.file || active;
  cancelUploadButton.hidden = !["uploading", "checking"].includes(appState.state);
  createButton.disabled = !canSubmit;
  createButton.textContent = retryingUncertainCreate
    ? "Xác minh và thử lại"
    : appState.createAttemptFailed
      ? "Thử tạo lại"
      : "Tạo cuộc họp";
  closeDialogButton.disabled = appState.state === "creating" || appState.startingUpload;
  titleInput.disabled = active || retryingUncertainCreate;
  dateInput.disabled = active || retryingUncertainCreate;
  for (const languageInput of form.querySelectorAll('input[name="language_hint"]')) {
    languageInput.disabled = active || retryingUncertainCreate;
  }

  if (!appState.policy) {
    createGuidance.textContent = "Đang tải giới hạn file của ứng dụng…";
  } else if (!appState.file) {
    createGuidance.textContent = "Chọn file, nhập tên và chọn ngôn ngữ để tiếp tục.";
  } else if (!appState.serverReady) {
    createGuidance.textContent = "Tạo cuộc họp sẽ mở sau khi máy chủ xác nhận file đã sẵn sàng.";
  } else if (!titleInput.value.trim()) {
    createGuidance.textContent = "Nhập tên cuộc họp để tiếp tục.";
  } else if (!currentLanguage()) {
    createGuidance.textContent = "Chọn English hoặc Tiếng Việt để tiếp tục.";
  } else if (appState.createUncertain) {
    createGuidance.textContent = "Gửi lại đúng yêu cầu để xác minh kết quả; máy chủ sẽ không tạo bản trùng.";
  } else {
    createGuidance.textContent = "File đã sẵn sàng và thông tin cuộc họp đã đầy đủ.";
  }
}

function renderPolicy(policy) {
  appState.policy = policy;
  fileInput.accept = policy.extensions.join(",");
  fileInput.disabled = false;
  fileLimits.textContent = `Định dạng: ${policy.extensions.join(", ")} · Tối đa ${formatBytes(policy.maxBytes)} · Tối đa ${formatDuration(policy.maxDurationSeconds)}.`;
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
  appState.createAttemptFailed = false;
  appState.createUncertain = false;
  appState.createRetryPayload = null;
  const previousUpload = appState.uploadId;
  if (previousUpload) void cleanupCurrentUpload();
  void cleanupPendingUploads();
  appState.file = file;
  showSelectedFile(file);

  if (!appState.policy) {
    fileError.textContent = "Không thể chọn file trước khi tải được chính sách định dạng và giới hạn.";
    setState("error", "Chưa thể kiểm tra file.");
    updateActions();
    return;
  }
  const extension = fileExtension(file.name);
  if (!appState.policy.extensions.includes(extension)) {
    fileError.textContent = `Định dạng ${extension || "không có phần mở rộng"} chưa được hỗ trợ. Chọn một trong: ${appState.policy.extensions.join(", ")}.`;
    setState("error", "File chưa đạt giới hạn đã công bố.");
    updateActions();
    return;
  }
  if (file.size > appState.policy.maxBytes) {
    fileError.textContent = `File lớn hơn giới hạn ${formatBytes(appState.policy.maxBytes)}. Hãy chọn file nhỏ hơn.`;
    setState("error", "File chưa đạt giới hạn đã công bố.");
    updateActions();
    return;
  }
  setState("selected", "Đã chọn file. Nhập thông tin rồi tải lên để kiểm tra.");
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
        uploadProgressValue.textContent = `${formatBytes(event.loaded)} đã gửi`;
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
      reject(new TransferError("Mất kết nối trong lúc truyền file.", "network"));
    };
    xhr.ontimeout = () => {
      appState.uploadRequest = null;
      reject(new TransferError("Thời gian truyền file đã hết.", "timeout"));
    };
    xhr.onabort = () => {
      appState.uploadRequest = null;
      reject(new TransferError("Đã hủy lượt truyền file.", "aborted"));
    };
    xhr.send(file);
  });
}

function uploadFailureCopy(error, cleanupSucceeded) {
  let reason = error && error.message ? error.message : "Máy chủ chưa thể nhận file.";
  if (error && error.status === 413) reason = "File vượt giới hạn dung lượng. Hãy chọn file nhỏ hơn.";
  if (error && error.status === 415) reason = "Định dạng file chưa được hỗ trợ. Hãy chọn định dạng trong danh sách.";
  if (error && error.status === 422) reason = `${reason} Hãy chọn file phù hợp rồi tải lại từ đầu.`;
  let message = `Không tạo cuộc họp. ${reason} File chưa được đưa vào xử lý.`;
  if (cleanupSucceeded) message += " Phần upload dở đã được dọn.";
  else message += " Ứng dụng chưa xác nhận đã dọn phần upload dở; hãy thử lại để tạo lượt upload mới.";
  return message;
}

async function startUpload() {
  if (!appState.policy || !appState.file || fileError.textContent || appState.startingUpload || ["uploading", "checking", "creating"].includes(appState.state)) return;
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
  workflowState.textContent = "Đang tạo lượt upload. Chưa truyền byte nào.";
  updateActions();
  await cleanupCurrentUpload();
  await cleanupPendingUploads();
  if (runId !== appState.runId) {
    appState.startingUpload = false;
    updateActions();
    return;
  }

  setState("selected", "File đã chọn. Đang chuẩn bị lượt upload mới từ byte đầu tiên.");
  try {
    const created = await requestJson("/api/uploads", {
      method: "POST",
      body: JSON.stringify({ filename: file.name, size_bytes: file.size }),
    });
    const uploadId = created && typeof created.id === "string" ? created.id : "";
    if (!uploadId) throw new Error("Máy chủ không trả về mã upload.");
    appState.uploadId = uploadId;
    appState.startingUpload = false;
    setState("uploading", "Đang tải file lên bằng byte progress thực tế.");
    transferProgress.hidden = false;
    await uploadWithProgress(uploadId, file, runId);
    if (runId !== appState.runId) return;

    appState.uploadRequest = null;
    setState("checking", "Đã truyền xong byte. Máy chủ đang kiểm tra định dạng, thời lượng và nội dung file.");
    validationState.textContent = "Đang kiểm tra file trên máy chủ. Đây là bước xác nhận file, không phải tiến độ xử lý transcript.";
    appState.completeController = new AbortController();
    const completed = await requestJson(`/api/uploads/${encodeURIComponent(uploadId)}/complete`, {
      method: "POST",
      body: JSON.stringify({}),
      signal: appState.completeController.signal,
    });
    appState.completeController = null;
    if (runId !== appState.runId) return;
    if (!completed || completed.status !== "ready") {
      throw new Error("Máy chủ chưa xác nhận file ở trạng thái ready. Không thể tạo cuộc họp lúc này.");
    }
    appState.serverReady = true;
    appState.retryableUpload = false;
    uploadProgress.value = 100;
    uploadProgressValue.textContent = "100%";
    validationState.textContent = "File đã qua kiểm tra và sẵn sàng tạo cuộc họp.";
    setState("ready", "File đã sẵn sàng. Bạn có thể tạo cuộc họp.");
  } catch (error) {
    appState.startingUpload = false;
    appState.completeController = null;
    if (runId !== appState.runId) return;
    appState.uploadRequest = null;
    appState.serverReady = false;
    const cleanupSucceeded = await cleanupCurrentUpload();
    if (runId !== appState.runId) return;
    const retryable = !(error instanceof ApiError) || error.status >= 500 || error.status === 401 || error.status === 403;
    appState.retryableUpload = retryable && Boolean(appState.file);
    const message = uploadFailureCopy(error, cleanupSucceeded);
    showFormError(message);
    validationState.textContent = "File chưa sẵn sàng; không có cuộc họp nào được tạo.";
    setState(error && error.kind === "aborted" ? "aborted" : "error", "Upload chưa hoàn tất.");
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
  showFormError(`Đã hủy upload. Không tạo cuộc họp. File chưa được xử lý.${cleanupSucceeded ? " Phần upload dở đã được dọn." : " Chưa xác nhận được việc dọn upload dở; lần thử lại sẽ bắt đầu bằng một upload mới."}`);
  validationState.textContent = "File chưa sẵn sàng; không có cuộc họp nào được tạo.";
  setState("aborted", "Upload đã bị hủy. Có thể tải lại từ đầu.");
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
  if (!value) return { label: "Chưa đặt ngày", dateTime: "" };
  const date = String(value).slice(0, 10);
  const match = date.match(/^(\d{4})-(\d{2})-(\d{2})$/);
  if (!match) return { label: "Chưa đặt ngày", dateTime: "" };
  const year = Number(match[1]);
  const month = Number(match[2]);
  const day = Number(match[3]);
  const parsed = new Date(Date.UTC(year, month - 1, day));
  if (parsed.getUTCFullYear() !== year || parsed.getUTCMonth() !== month - 1 || parsed.getUTCDate() !== day) {
    return { label: "Chưa đặt ngày", dateTime: "" };
  }
  return {
    label: new Intl.DateTimeFormat("vi-VN", { day: "numeric", month: "long", year: "numeric", timeZone: "UTC" }).format(parsed),
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
  appState.uploadId = null;
  appState.uploadRequest = null;
  appState.completeController = null;
  appState.startingUpload = false;
  appState.retryableUpload = false;
  appState.serverReady = false;
  appState.createAttemptFailed = false;
  appState.createUncertain = false;
  appState.createRetryPayload = null;
  form.reset();
  fileInput.value = "";
  fileInput.accept = "";
  fileInput.disabled = true;
  fileDrop.setAttribute("aria-disabled", "true");
  fileLimits.textContent = "Đang tải giới hạn của ứng dụng…";
  fileError.textContent = "";
  showSelectedFile(null);
  showFormError("");
  clearProgress();
  validationState.textContent = "";
  dialog.dataset.state = "idle";
  stateCode.textContent = "IDLE";
  workflowState.textContent = "Chưa chọn file.";
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
    setState("idle", "Chưa chọn file.");
  } catch (error) {
    if (!dialog.open || policyRunId !== appState.policyRunId) return;
    const message = error instanceof ApiError ? error.message : (error && error.message) || "Không tải được chính sách file.";
    fileLimits.textContent = "Không tải được giới hạn file.";
    showFormError(`${message} Đóng hộp thoại rồi mở lại để tải chính sách mới.`);
    setState("error", "Chưa thể bắt đầu vì thiếu chính sách file.");
  }
}

async function createMeeting(event) {
  event.preventDefault();
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
  setState("creating", "Đang lưu cuộc họp và metadata.");
  try {
    const result = await requestJson("/api/meetings", {
      method: "POST",
      body: JSON.stringify(payload),
    });
    const meeting = result && result.meeting && typeof result.meeting === "object" ? result.meeting : result;
    if (!meeting || typeof meeting.id !== "string" || !meeting.id) {
      throw new Error("Máy chủ không trả về mã cuộc họp sau khi lưu.");
    }
    setState("saved", "Cuộc họp đã được lưu.");
    appState.serverReady = false;
    appState.createRetryPayload = null;
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
      showFormError("File không còn ở trạng thái sẵn sàng. Không có cuộc họp mới được tạo; hãy tải file lại từ đầu.");
      setState("error", "File không còn sẵn sàng.");
      return;
    }
    appState.createAttemptFailed = true;
    appState.createUncertain = !definiteResponse;
    appState.createRetryPayload = definiteResponse ? null : payload;
    const message = error instanceof ApiError ? error.message : (error && error.message) || "Không thể xác nhận kết quả lưu cuộc họp.";
    if (appState.createUncertain) {
      showFormError(`${message} Không thể xác nhận cuộc họp đã được tạo hay chưa. Hãy dùng “Xác minh và thử lại”; yêu cầu được gửi lại an toàn với cùng thông tin. Bạn cũng có thể đóng hộp thoại và kiểm tra lại sau.`);
    } else {
      showFormError(`${message} Cuộc họp chưa được lưu. File vẫn sẵn sàng; sửa thông tin nếu cần rồi thử lại.`);
    }
    setState("error", appState.createUncertain ? "Chưa thể xác nhận kết quả lưu." : "Máy chủ từ chối tạo cuộc họp.");
  }
}

for (const button of document.querySelectorAll("[data-open-meeting-dialog]")) {
  button.addEventListener("click", () => void openDialog());
}

document.querySelector("#workspace-link").setAttribute("aria-current", "page");
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
    fileError.textContent = "Chọn từng file một để tạo cuộc họp.";
    setState("error", "Chỉ nhận một file cho mỗi cuộc họp.");
    return;
  }
  void selectFile(files[0]);
});

uploadButton.addEventListener("click", () => void startUpload());
retryUploadButton.addEventListener("click", () => void startUpload());
cancelUploadButton.addEventListener("click", () => void abortUpload());
form.addEventListener("submit", createMeeting);

function onFormChange() {
  if (appState.createAttemptFailed && appState.serverReady) {
    appState.createAttemptFailed = false;
    setState("ready", "File đã sẵn sàng. Kiểm tra thông tin rồi thử tạo cuộc họp lại.");
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
