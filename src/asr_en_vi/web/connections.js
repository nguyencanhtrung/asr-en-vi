"use strict";

// Header status buttons: OpenAI is the chatgpt provider, Google is antigravity.
const launcherElements = {
  chatgpt: { button: document.querySelector("#launcher-chatgpt"), name: "OpenAI" },
  antigravity: { button: document.querySelector("#launcher-antigravity"), name: "Google" },
};

const connectionElements = {
  dialog: document.querySelector("#connections-dialog"),
  close: document.querySelector("#connections-close"),
  badge: document.querySelector("#connection-state-badge"),
  status: document.querySelector("#connection-status"),
  account: document.querySelector("#connection-account"),
  verificationRow: document.querySelector("#connection-verification-row"),
  verificationSummary: document.querySelector("#connection-verification-summary"),
  message: document.querySelector("#connection-message"),
  error: document.querySelector("#connection-error"),
  errorMessage: document.querySelector("#connection-error-message"),
  retryPoll: document.querySelector("#connection-retry-poll"),
  signIn: document.querySelector("#connection-sign-in"),
  pendingActions: document.querySelector("#connection-pending-actions"),
  pendingCopy: document.querySelector("#connection-pending-copy"),
  cancelSignIn: document.querySelector("#connection-cancel-sign-in"),
  disconnect: document.querySelector("#connection-disconnect"),
  disconnectTrigger: document.querySelector("#connection-disconnect-trigger"),
  disconnectConfirm: document.querySelector("#connection-disconnect-confirm"),
  disconnectKeep: document.querySelector("#connection-disconnect-keep"),
  disconnectConfirmButton: document.querySelector("#connection-disconnect-confirm-button"),
  modelSection: document.querySelector("#connection-model-section"),
  modelForm: document.querySelector("#connection-model-form"),
  modelSelect: document.querySelector("#connection-model"),
  effortSelect: document.querySelector("#connection-effort"),
  modelStatus: document.querySelector("#connection-model-status"),
  modelSave: document.querySelector("#connection-model-save"),
  verify: document.querySelector("#connection-verify"),
  verificationResult: document.querySelector("#connection-verification-result"),
};

const connectionState = {
  provider: null,
  preferences: { provider: null, models: {}, reasoning_effort: "default" },
  models: [],
  selectedModel: "",
  savedModel: "",
  savedEffort: "default",
  activeLogin: null,
  pollTimer: null,
  pollGeneration: 0,
  loadGeneration: 0,
  savingModel: false,
  verifying: false,
  disconnecting: false,
};

class ConnectionApiError extends Error {
  constructor(message, code, status = 0) {
    super(message);
    this.name = "ConnectionApiError";
    this.code = code;
    this.status = status;
  }
}

function defaultErrorMessage(code, status) {
  const known = {
    revocation_unconfirmed: "Chưa xác nhận thu hồi phiên ChatGPT cũ. Hãy thử lại hoặc thu hồi quyền trong ChatGPT → Cài đặt → Mức sử dụng.",
    provider_busy: "Một thao tác ChatGPT khác đang chạy. Hãy đợi một chút rồi thử lại.",
    provider_timeout: "ChatGPT chưa phản hồi trong thời gian cho phép. Bạn có thể thử lại.",
    NETWORK_ERROR: "Không kết nối được với máy chủ trên máy này.",
    INVALID_AUTHORIZATION_URL: "Máy chủ trả về địa chỉ đăng nhập không hợp lệ.",
    UNSAFE_AUTHORIZATION_URL: "Máy chủ không được gửi thông tin nhận dạng nhạy cảm đến trình duyệt.",
    INVALID_LOGIN_SESSION: "Máy chủ trả về phiên đăng nhập không hợp lệ.",
    INVALID_LOGIN_STATUS: "Máy chủ trả về trạng thái phiên đăng nhập không hợp lệ.",
    CANCEL_NOT_CONFIRMED: "Máy chủ chưa hủy được phiên đăng nhập.",
    POPUP_BLOCKED: "Trình duyệt đang chặn cửa sổ đăng nhập. Cho phép mở cửa sổ cho không gian làm việc này rồi thử lại.",
    SIGN_IN_FAILED: "Không thể hoàn tất đăng nhập ChatGPT.",
    INVALID_PROVIDER_STATUS: "Máy chủ chưa công bố trạng thái kết nối ChatGPT hợp lệ.",
    DISCONNECT_NOT_CONFIRMED: "Máy chủ chưa xác nhận đã ngắt kết nối ChatGPT.",
    provider_reconnect_required: "Tài khoản ChatGPT cần đăng nhập lại trước khi tiếp tục.",
    chatgpt_reconnect_required: "Tài khoản ChatGPT cần đăng nhập lại trước khi tiếp tục.",
    reconnect_required: "Tài khoản ChatGPT cần đăng nhập lại trước khi tiếp tục.",
    provider_auth_error: "ChatGPT không chấp nhận thông tin đăng nhập hiện tại. Hãy kết nối lại tài khoản.",
    subscription_sharing_invalid_user: "ChatGPT không chấp nhận thông tin đăng nhập hiện tại. Hãy kết nối lại tài khoản.",
    chatpass_v2_scope_not_authorized: "Tài khoản chưa cấp quyền dùng gói ChatGPT. Hãy kết nối lại và cấp quyền cần thiết.",
    chatpass_v2_invalid_authorization_context: "Cấu hình cấp quyền ChatGPT không hợp lệ. Hãy kiểm tra cấu hình kết nối trước khi đăng nhập lại.",
    scope_not_authorized: "Tài khoản chưa cấp quyền dùng gói ChatGPT. Hãy kết nối lại và cấp quyền cần thiết.",
    invalid_grant: "Quyền đăng nhập ChatGPT đã hết hạn. Hãy kết nối lại tài khoản.",
    invalid_refresh_token: "Quyền đăng nhập ChatGPT đã hết hạn. Hãy kết nối lại tài khoản.",
    token_expired: "Quyền đăng nhập ChatGPT đã hết hạn. Hãy kết nối lại tài khoản.",
    refresh_token_expired: "Quyền đăng nhập ChatGPT đã hết hạn. Hãy kết nối lại tài khoản.",
    refresh_token_invalidated: "Quyền đăng nhập ChatGPT đã hết hạn. Hãy kết nối lại tài khoản.",
    refresh_token_reused: "Quyền đăng nhập ChatGPT đã hết hạn. Hãy kết nối lại tài khoản.",
    model_not_available: "Mô hình đã chọn không khả dụng với tài khoản ChatGPT này. Hãy chọn mô hình khác.",
    model_unavailable: "Mô hình đã chọn không khả dụng với tài khoản ChatGPT này. Hãy chọn mô hình khác.",
    invalid_reasoning_effort: "Mức suy luận này không được mô hình đã chọn hỗ trợ.",
  };
  if (known[code]) return known[code];
  if (status === 401) return "Phiên truy cập không gian làm việc không còn hợp lệ. Hãy mở lại liên kết trong terminal.";
  if (status === 403) return "ChatGPT đã từ chối yêu cầu. Hãy kiểm tra quyền truy cập tài khoản rồi thử lại.";
  if (status === 404) return "Không tìm thấy phiên hoặc dữ liệu yêu cầu.";
  if (status === 409) return "Trạng thái đã thay đổi. Hãy tải lại thông tin rồi thử lại.";
  if (status === 429) return "Yêu cầu đã chạm giới hạn hiện tại. Hãy kiểm tra mức sử dụng ChatGPT.";
  if (status >= 500) return "Máy chủ chưa thể hoàn tất yêu cầu. Hãy thử lại sau.";
  return "Không thể hoàn tất thao tác. Hãy kiểm tra trạng thái rồi thử lại.";
}

function localizedErrorMessage(code, message, status) {
  if (typeof message === "string" && /[À-ỹ]/u.test(message)) return message;
  return defaultErrorMessage(code, status);
}

function errorDetails(payload, status) {
  const detail = payload && (payload.detail || payload.error);
  if (detail && typeof detail === "object") {
    return {
      code: typeof detail.code === "string" ? detail.code : `HTTP_${status}`,
      message: localizedErrorMessage(
        typeof detail.code === "string" ? detail.code : `HTTP_${status}`,
        detail.message,
        status,
      ),
    };
  }
  if (typeof detail === "string" && detail.trim()) {
    return {
      code: `HTTP_${status}`,
      message: localizedErrorMessage(`HTTP_${status}`, detail.trim(), status),
    };
  }
  return {
    code: `HTTP_${status}`,
    message: localizedErrorMessage(`HTTP_${status}`, "", status),
  };
}

async function connectionRequest(path, options = {}) {
  const method = (options.method || "GET").toUpperCase();
  const headers = { Accept: "application/json" };
  const requestOptions = {
    method,
    headers,
    credentials: "same-origin",
    cache: "no-store",
  };
  if (method !== "GET" && method !== "HEAD") headers["Content-Type"] = "application/json";
  if (options.body !== undefined) requestOptions.body = JSON.stringify(options.body);
  if (options.signal) requestOptions.signal = options.signal;

  let response;
  try {
    response = await fetch(path, requestOptions);
  } catch (error) {
    if (error && error.name === "AbortError") throw error;
    throw new ConnectionApiError("Không kết nối được với máy chủ trên máy này.", "NETWORK_ERROR");
  }

  let payload = null;
  try {
    payload = await response.json();
  } catch {
    payload = null;
  }
  if (!response.ok) {
    const details = errorDetails(payload, response.status);
    throw new ConnectionApiError(details.message, details.code, response.status);
  }
  return payload;
}

function formatTimestamp(value) {
  const date = new Date(value);
  if (!Number.isFinite(date.getTime())) return String(value || "");
  return new Intl.DateTimeFormat("vi-VN", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(date);
}

function setConnectionMessage(message) {
  connectionElements.message.textContent = message || "";
}

function clearConnectionError() {
  connectionElements.error.hidden = true;
  connectionElements.error.dataset.code = "";
  connectionElements.errorMessage.textContent = "";
  connectionElements.retryPoll.hidden = true;
}

function showConnectionError(error, { retryPoll = false } = {}) {
  const code = error && error.code ? error.code : "CONNECTION_ERROR";
  const message = localizedErrorMessage(
    code,
    error && error.message,
    error && error.status,
  );
  connectionElements.error.dataset.code = code;
  connectionElements.errorMessage.textContent = message;
  connectionElements.retryPoll.hidden = !retryPoll;
  connectionElements.error.hidden = false;
}

function requiresProviderReconnect(error) {
  if (!error || error.status === 401) return false;
  const code = String(error.code || "").toLowerCase();
  return code.endsWith("reconnect_required")
    || ["provider_auth_error", "subscription_sharing_invalid_user", "scope_not_authorized",
      "chatpass_v2_scope_not_authorized", "chatpass_v2_invalid_authorization_context"].includes(code)
    || [
      "invalid_grant",
      "invalid_refresh_token",
      "token_expired",
      "refresh_token_expired",
      "refresh_token_invalidated",
      "refresh_token_reused",
    ].includes(code);
}

async function refreshProviderAfterAuthFailure(error) {
  if (!requiresProviderReconnect(error)) return false;
  try {
    const payload = await connectionRequest("/api/providers");
    const provider = Array.isArray(payload.providers)
      ? payload.providers.find((item) => item && item.id === "chatgpt")
      : null;
    if (!provider || !["connected", "disconnected", "reconnect_required"].includes(provider.status)) {
      return false;
    }
    connectionState.provider = provider;
    renderProvider();
    return true;
  } catch {
    return false;
  }
}

function providerStatusCopy(status) {
  if (status === "connected") return "Đã kết nối";
  if (status === "reconnect_required") return "Cần đăng nhập lại";
  if (status === "disconnected") return "Chưa kết nối";
  return "Chưa rõ trạng thái";
}

// Visible status text and the spoken equivalent for each launcher state.
const launcherCopy = {
  loading: ["Đang kiểm tra", "đang kiểm tra trạng thái"],
  connected: ["Đã kết nối", "đã kết nối"],
  reconnect_required: ["Cần đăng nhập lại", "cần đăng nhập lại"],
  disconnected: ["Chưa kết nối", "chưa kết nối"],
  error: ["Không khả dụng", "không đọc được trạng thái"],
};

function setLauncherState(provider, status, accountLabel = "") {
  const { button, name } = launcherElements[provider];
  const [label, spoken] = launcherCopy[status] || launcherCopy.error;
  const account = status === "connected" ? ` với ${accountLabel || "tài khoản"}` : "";
  button.dataset.state = status;
  button.querySelector(".connection-launcher-status").textContent = label;
  button.setAttribute("aria-label", `Kết nối ${name}: ${spoken}${account}`);
}

function modelIsAvailable(modelId) {
  return Boolean(modelId && connectionState.models.some((model) => model.id === modelId));
}

function renderEfforts(modelId, selectedEffort = "default") {
  const model = connectionState.models.find((item) => item.id === modelId);
  const supported = Array.isArray(model?.reasoning_efforts) ? model.reasoning_efforts : [];
  const labels = {
    none: "Không suy luận (none)",
    low: "Thấp (low)",
    medium: "Trung bình (medium)",
    high: "Cao (high)",
    xhigh: "Rất cao (xhigh)",
    max: "Tối đa (max)",
  };
  const select = connectionElements.effortSelect;
  select.replaceChildren();
  const fallback = document.createElement("option");
  fallback.value = "default";
  fallback.textContent = "Mặc định của mô hình";
  select.append(fallback);
  for (const effort of supported) {
    if (!Object.hasOwn(labels, effort)) continue;
    const option = document.createElement("option");
    option.value = effort;
    option.textContent = labels[effort];
    select.append(option);
  }
  select.value = supported.includes(selectedEffort) ? selectedEffort : "default";
}

function updateConnectionActions() {
  const connected = connectionState.provider?.status === "connected";
  const canUseSelectedModel = connected && modelIsAvailable(connectionElements.modelSelect.value);
  const selectedModel = connectionElements.modelSelect.value;
  const selectedEffort = connectionElements.effortSelect.value;
  // The last notes provider may be Antigravity; a saved ChatGPT model is still a saved preference.
  const preferenceIsActive = typeof connectionState.preferences.models.chatgpt === "string"
    && connectionState.preferences.models.chatgpt !== "";

  connectionElements.modelSelect.disabled = !connected || connectionState.savingModel || connectionState.models.length === 0;
  connectionElements.effortSelect.disabled = !canUseSelectedModel || connectionState.savingModel
    || connectionElements.effortSelect.options.length < 2;
  connectionElements.modelSave.disabled = !canUseSelectedModel
    || connectionState.savingModel
    || (selectedModel === connectionState.savedModel
      && selectedEffort === connectionState.savedEffort && preferenceIsActive);
  connectionElements.verify.disabled = !canUseSelectedModel || connectionState.verifying;
  connectionElements.signIn.hidden = Boolean(connectionState.activeLogin) || connected;
  connectionElements.pendingActions.hidden = !connectionState.activeLogin;
  connectionElements.cancelSignIn.disabled = !connectionState.activeLogin;
  connectionElements.disconnect.hidden = !connectionState.provider
    || connectionState.provider.status === "disconnected";
  connectionElements.disconnectConfirmButton.disabled = connectionState.disconnecting;
  connectionElements.disconnectTrigger.disabled = connectionState.disconnecting;
}

function renderProvider() {
  const provider = connectionState.provider;
  if (!provider) return;

  const status = provider.status;
  const statusCopy = providerStatusCopy(status);
  const badgeState = ["connected", "reconnect_required", "disconnected"].includes(status) ? status : "error";
  connectionElements.badge.dataset.state = badgeState;
  connectionElements.badge.textContent = statusCopy;
  connectionElements.status.textContent = statusCopy;
  connectionElements.account.textContent = provider.account?.label || "Chưa có thông tin";

  if (provider.verification && provider.verification.model && provider.verification.verified_at) {
    const name = modelName(provider.verification.model);
    const effort = provider.verification.reasoning_effort || "default";
    connectionElements.verificationSummary.textContent = `${name} · effort ${effort} · ${formatTimestamp(provider.verification.verified_at)}`;
    connectionElements.verificationRow.hidden = false;
  } else {
    connectionElements.verificationSummary.textContent = "Chưa kiểm tra";
    connectionElements.verificationRow.hidden = true;
  }

  setLauncherState("chatgpt", badgeState, provider.account?.label);

  connectionElements.modelSection.hidden = status !== "connected";
  updateConnectionActions();
}

function modelName(modelId) {
  const model = connectionState.models.find((item) => item.id === modelId);
  return model ? model.display_name : modelId;
}

function renderModels(catalog, preferences) {
  const models = Array.isArray(catalog.models) ? catalog.models : [];
  connectionState.models = models.filter(
    (model) => model && typeof model.id === "string" && typeof model.display_name === "string",
  );
  connectionState.preferences = {
    provider: ["chatgpt", "antigravity"].includes(preferences.provider) ? preferences.provider : null,
    models: preferences.models && typeof preferences.models === "object" ? preferences.models : {},
    reasoning_effort: typeof preferences.reasoning_effort === "string"
      ? preferences.reasoning_effort : "default",
  };

  const preferenceModel = connectionState.preferences.models.chatgpt;
  const catalogSelection = typeof catalog.selected_model === "string" ? catalog.selected_model : "";
  const selectedModel = typeof preferenceModel === "string" && preferenceModel
    ? preferenceModel
    : catalogSelection;
  connectionState.selectedModel = selectedModel;
  connectionState.savedModel = selectedModel;
  connectionState.savedEffort = connectionState.preferences.reasoning_effort;

  const select = connectionElements.modelSelect;
  select.replaceChildren();
  if (!selectedModel) {
    const placeholder = document.createElement("option");
    placeholder.value = "";
    placeholder.textContent = connectionState.models.length ? "Chọn mô hình" : "Chưa có mô hình khả dụng";
    select.append(placeholder);
  } else if (!modelIsAvailable(selectedModel)) {
    const unavailable = document.createElement("option");
    unavailable.value = selectedModel;
    unavailable.textContent = `${selectedModel} — không khả dụng với tài khoản này`;
    unavailable.disabled = true;
    unavailable.selected = true;
    select.append(unavailable);
  }

  for (const model of connectionState.models) {
    const option = document.createElement("option");
    option.value = model.id;
    option.textContent = model.display_name;
    option.selected = model.id === selectedModel;
    select.append(option);
  }
  renderEfforts(selectedModel, connectionState.savedEffort);
  if (selectedModel && !modelIsAvailable(selectedModel)) {
    connectionElements.modelStatus.dataset.state = "error";
    connectionElements.modelStatus.textContent = `Mô hình đã lưu “${selectedModel}” hiện không khả dụng. Hãy chọn mô hình khác để thay đổi lựa chọn.`;
  } else if (selectedModel) {
    connectionElements.modelStatus.dataset.state = "";
    connectionElements.modelStatus.textContent = "";
  } else {
    connectionElements.modelStatus.dataset.state = "";
    connectionElements.modelStatus.textContent = "Chọn mô hình rồi lưu để dùng cho ghi chú cuộc họp.";
  }
  updateConnectionActions();
}

function validateAuthorizationUrl(value) {
  let url;
  try {
    url = new URL(value);
  } catch {
    throw new ConnectionApiError("Máy chủ trả về địa chỉ đăng nhập không hợp lệ.", "INVALID_AUTHORIZATION_URL");
  }
  if (url.protocol !== "https:" || url.hostname !== "auth.openai.com" || url.username || url.password) {
    throw new ConnectionApiError("Địa chỉ đăng nhập không thuộc dịch vụ ChatGPT chính thức.", "INVALID_AUTHORIZATION_URL");
  }
  if (url.searchParams.has("id_token_hint")) {
    throw new ConnectionApiError("Máy chủ không được gửi thông tin nhận dạng nhạy cảm đến trình duyệt.", "UNSAFE_AUTHORIZATION_URL");
  }
  return url.href;
}

function reserveSignInWindow() {
  try {
    const popup = window.open("about:blank", "_blank");
    if (!popup) return null;
    popup.opener = null;
    popup.document.title = "Continue with ChatGPT";
    popup.document.body.textContent = "Đang chuẩn bị đăng nhập ChatGPT…";
    return popup;
  } catch {
    return null;
  }
}

function clearPollTimer() {
  if (connectionState.pollTimer !== null) {
    window.clearTimeout(connectionState.pollTimer);
    connectionState.pollTimer = null;
  }
}

const pendingLoginStorageKey = "asr.chatgpt.pendingLogin";

function persistPendingLogin(login) {
  try {
    if (login) sessionStorage.setItem(pendingLoginStorageKey, JSON.stringify(login));
    else sessionStorage.removeItem(pendingLoginStorageKey);
  } catch {
    // Login remains usable when browser storage is unavailable.
  }
}

function restorePendingLogin() {
  try {
    const login = JSON.parse(sessionStorage.getItem(pendingLoginStorageKey));
    if (!login || typeof login.id !== "string" || !login.id ||
        typeof login.expiresAt !== "string" || !Number.isFinite(Date.parse(login.expiresAt))) return;
    setPendingLogin({ id: login.id, expires_at: login.expiresAt });
    scheduleLoginPoll(connectionState.pollGeneration, 0);
  } catch {
    persistPendingLogin(null);
  }
}

function setPendingLogin(session) {
  connectionState.activeLogin = {
    id: session.id,
    expiresAt: session.expires_at,
  };
  persistPendingLogin(connectionState.activeLogin);
  connectionElements.pendingCopy.textContent = "Đang chờ bạn hoàn tất đăng nhập trong cửa sổ ChatGPT…";
  updateConnectionActions();
}

function finishLogin(status, payload = null) {
  clearPollTimer();
  connectionState.pollGeneration += 1;
  connectionState.activeLogin = null;
  persistPendingLogin(null);
  connectionElements.signIn.disabled = false;
  clearConnectionError();
  updateConnectionActions();

  if (status === "connected") {
    setConnectionMessage("Đã xác thực tài khoản ChatGPT.");
    void loadAccountData();
    window.dispatchEvent(new CustomEvent("asr:provider-choice-changed"));
    return;
  }
  if (status === "cancelled") {
    setConnectionMessage("Đã hủy đăng nhập ChatGPT.");
    return;
  }
  if (status === "expired") {
    setConnectionMessage("Phiên đăng nhập đã hết hạn. Hãy bắt đầu lại để kết nối ChatGPT.");
    return;
  }
  if (status === "failed") {
    const error = payload && payload.error ? payload.error : {};
    showConnectionError({
      code: typeof error.code === "string" ? error.code : "SIGN_IN_FAILED",
      message: typeof error.message === "string" ? error.message : "Không thể hoàn tất đăng nhập ChatGPT.",
    });
    setConnectionMessage("Đăng nhập ChatGPT chưa hoàn tất.");
  }
}

function scheduleLoginPoll(generation, delay = 1000) {
  clearPollTimer();
  connectionState.pollTimer = window.setTimeout(() => {
    void pollLoginSession(generation);
  }, delay);
}

function loginExpired(login) {
  const expires = Date.parse(login.expiresAt);
  return Number.isFinite(expires) && Date.now() >= expires;
}

async function pollLoginSession(generation) {
  if (generation !== connectionState.pollGeneration || !connectionState.activeLogin) return;
  const login = connectionState.activeLogin;
  if (loginExpired(login)) {
    finishLogin("expired");
    return;
  }

  try {
    const session = await connectionRequest(
      `/api/providers/chatgpt/login-sessions/${encodeURIComponent(login.id)}`,
    );
    if (generation !== connectionState.pollGeneration || !connectionState.activeLogin) return;
    if (session.status === "pending") {
      if (loginExpired(login)) {
        finishLogin("expired");
      } else {
        connectionElements.pendingCopy.textContent = "Đang chờ bạn hoàn tất đăng nhập trong cửa sổ ChatGPT…";
        scheduleLoginPoll(generation);
      }
      return;
    }
    if (["connected", "cancelled", "expired", "failed"].includes(session.status)) {
      finishLogin(session.status, session);
      return;
    }
    throw new ConnectionApiError("Máy chủ trả về trạng thái phiên đăng nhập không hợp lệ.", "INVALID_LOGIN_STATUS");
  } catch (error) {
    if (generation !== connectionState.pollGeneration || !connectionState.activeLogin) return;
    showConnectionError(error, { retryPoll: true });
    connectionElements.pendingCopy.textContent = "Chưa đọc được trạng thái đăng nhập. Bạn có thể thử kiểm tra lại.";
  }
}

async function startLogin() {
  clearConnectionError();
  setConnectionMessage("");
  connectionElements.signIn.disabled = true;
  const popup = reserveSignInWindow();
  if (!popup) {
    showConnectionError({ code: "POPUP_BLOCKED" });
    connectionElements.signIn.disabled = false;
    return;
  }

  try {
    const session = await connectionRequest("/api/providers/chatgpt/login-sessions", {
      method: "POST",
      body: {},
    });
    if (!session || session.status !== "pending" || !session.id || !session.expires_at) {
      throw new ConnectionApiError("Máy chủ trả về phiên đăng nhập không hợp lệ.", "INVALID_LOGIN_SESSION");
    }
    const authorizationUrl = validateAuthorizationUrl(session.authorization_url);
    setPendingLogin(session);
    if (session.replaced_previous === true) {
      setConnectionMessage(
        "Đã thay thế phiên đăng nhập đang chờ. Hãy tiếp tục ở cửa sổ ChatGPT mới; phản hồi từ cửa sổ cũ sẽ bị bỏ qua.",
      );
    }
    const generation = ++connectionState.pollGeneration;

    if (loginExpired(connectionState.activeLogin)) {
      if (!popup.closed) popup.close();
      finishLogin("expired");
      return;
    }
    if (!popup.closed) {
      popup.location.replace(authorizationUrl);
    } else {
      showConnectionError({
        code: "POPUP_BLOCKED",
        message: "Cửa sổ đăng nhập đã đóng. Hãy hủy phiên này rồi bắt đầu lại.",
      });
    }
    scheduleLoginPoll(generation, 500);
  } catch (error) {
    if (!popup.closed) popup.close();
    showConnectionError(error);
    connectionElements.signIn.disabled = false;
  }
}

async function cancelLogin() {
  const login = connectionState.activeLogin;
  if (!login) return;
  clearConnectionError();
  clearPollTimer();
  const generation = ++connectionState.pollGeneration;
  connectionElements.cancelSignIn.disabled = true;
  try {
    const session = await connectionRequest(
      `/api/providers/chatgpt/login-sessions/${encodeURIComponent(login.id)}`,
      { method: "DELETE" },
    );
    if (generation !== connectionState.pollGeneration) return;
    if (["cancelled", "expired", "failed", "connected"].includes(session.status)) {
      finishLogin(session.status, session);
      return;
    }
    throw new ConnectionApiError("Máy chủ chưa hủy được phiên đăng nhập.", "CANCEL_NOT_CONFIRMED");
  } catch (error) {
    if (generation !== connectionState.pollGeneration) return;
    showConnectionError(error);
    connectionElements.cancelSignIn.disabled = false;
    scheduleLoginPoll(generation, 1000);
  }
}

async function loadAccountData() {
  const generation = ++connectionState.loadGeneration;
  clearConnectionError();
  connectionElements.badge.dataset.state = "loading";
  connectionElements.badge.textContent = "Đang kiểm tra";
  setLauncherState("chatgpt", "loading");

  try {
    const payload = await connectionRequest("/api/providers");
    if (generation !== connectionState.loadGeneration) return;
    const providers = Array.isArray(payload.providers) ? payload.providers : [];
    const provider = providers.find((item) => item && item.id === "chatgpt");
    if (!provider || !["connected", "disconnected", "reconnect_required"].includes(provider.status)) {
      throw new ConnectionApiError("Máy chủ chưa công bố trạng thái kết nối ChatGPT hợp lệ.", "INVALID_PROVIDER_STATUS");
    }
    connectionState.provider = provider;
    renderProvider();

    const preferences = await connectionRequest("/api/notes-preferences");
    if (generation !== connectionState.loadGeneration) return;
    connectionState.preferences = {
      provider: ["chatgpt", "antigravity"].includes(preferences.provider) ? preferences.provider : null,
      models: preferences.models && typeof preferences.models === "object" ? preferences.models : {},
      reasoning_effort: typeof preferences.reasoning_effort === "string"
        ? preferences.reasoning_effort : "default",
    };
    if (provider.status === "connected") {
      const catalog = await connectionRequest("/api/providers/chatgpt/models");
      if (generation !== connectionState.loadGeneration) return;
      renderModels(catalog, preferences);
    } else {
      connectionState.models = [];
      connectionState.selectedModel = connectionState.preferences.models.chatgpt || "";
      connectionState.savedModel = connectionState.selectedModel;
      connectionState.savedEffort = connectionState.preferences.reasoning_effort;
      connectionElements.modelSelect.replaceChildren();
      const placeholder = document.createElement("option");
      placeholder.value = "";
      placeholder.textContent = "Kết nối ChatGPT để tải mô hình";
      connectionElements.modelSelect.append(placeholder);
      renderEfforts("");
      connectionElements.modelStatus.textContent = "";
      connectionElements.modelStatus.dataset.state = "";
      updateConnectionActions();
    }
  } catch (error) {
    if (generation !== connectionState.loadGeneration) return;
    await refreshProviderAfterAuthFailure(error);
    if (!connectionState.provider) {
      setLauncherState("chatgpt", "error");
      connectionElements.badge.dataset.state = "error";
      connectionElements.badge.textContent = "Không khả dụng";
      connectionElements.status.textContent = "Không đọc được trạng thái";
    } else {
      renderProvider(); // the last known status stands; drop the "loading" state
    }
    showConnectionError(error);
  }
}

// One /api/providers read on page load sets both header buttons.
async function refreshHeaderStatus() {
  const generation = connectionState.loadGeneration;
  let providers = [];
  try {
    const payload = await connectionRequest("/api/providers");
    if (Array.isArray(payload.providers)) providers = payload.providers;
  } catch {
    // Neither status is known; both buttons fall through to the error state.
  }
  const known = ["connected", "disconnected", "reconnect_required"];
  // A dialog or login read that started meanwhile is newer than this slower page-load answer.
  if (generation === connectionState.loadGeneration) {
    const chatgpt = providers.find((item) => item && item.id === "chatgpt");
    if (chatgpt && known.includes(chatgpt.status)) {
      connectionState.provider = chatgpt;
      renderProvider();
    } else {
      setLauncherState("chatgpt", "error");
    }
  }
  // loadAntigravity sets Google without moving the generation; a status already shown there is newer.
  if (launcherElements.antigravity.button.dataset.state) return;
  const antigravity = providers.find((item) => item && item.id === "antigravity");
  setLauncherState(
    "antigravity",
    antigravity && known.includes(antigravity.status) ? antigravity.status : "error",
    antigravity?.account?.label,
  );
}

async function saveModel(event) {
  event.preventDefault();
  const model = connectionElements.modelSelect.value;
  const reasoningEffort = connectionElements.effortSelect.value;
  if (!modelIsAvailable(model) || connectionState.savingModel) return;
  clearConnectionError();
  connectionElements.modelStatus.dataset.state = "";
  connectionElements.modelStatus.textContent = "Đang lưu mô hình…";
  connectionState.savingModel = true;
  updateConnectionActions();
  try {
    const preferences = await connectionRequest("/api/notes-preferences", {
      method: "PUT",
      body: { provider: "chatgpt", model, reasoning_effort: reasoningEffort },
    });
    connectionState.preferences = {
      provider: "chatgpt",
      models: preferences.models && typeof preferences.models === "object"
        ? preferences.models
        : { chatgpt: model },
      reasoning_effort: typeof preferences.reasoning_effort === "string"
        ? preferences.reasoning_effort : reasoningEffort,
    };
    connectionState.savedModel = connectionState.preferences.models.chatgpt || model;
    connectionState.selectedModel = connectionState.savedModel;
    connectionState.savedEffort = connectionState.preferences.reasoning_effort;
    connectionElements.modelSelect.value = connectionState.selectedModel;
    renderEfforts(connectionState.selectedModel, connectionState.savedEffort);
    connectionElements.modelStatus.dataset.state = "saved";
    connectionElements.modelStatus.textContent = `Đã lưu ${modelName(connectionState.selectedModel)} · effort ${connectionState.savedEffort} cho ghi chú cuộc họp.`;
    window.dispatchEvent(new CustomEvent("asr:provider-choice-changed"));
  } catch (error) {
    await refreshProviderAfterAuthFailure(error);
    connectionElements.modelStatus.dataset.state = "error";
    connectionElements.modelStatus.textContent = "Chưa lưu được mô hình. Lựa chọn đã lưu trước đó vẫn được giữ nguyên.";
    showConnectionError(error);
  } finally {
    connectionState.savingModel = false;
    updateConnectionActions();
  }
}

async function verifyConnection() {
  const model = connectionElements.modelSelect.value;
  const reasoningEffort = connectionElements.effortSelect.value;
  if (!modelIsAvailable(model) || connectionState.verifying) return;
  clearConnectionError();
  connectionElements.verificationResult.dataset.state = "";
  connectionElements.verificationResult.textContent = "Đang chạy một yêu cầu kiểm tra tổng hợp…";
  connectionState.verifying = true;
  updateConnectionActions();
  try {
    const result = await connectionRequest("/api/providers/chatgpt/verify", {
      method: "POST",
      body: { model, reasoning_effort: reasoningEffort },
    });
    connectionElements.verificationResult.dataset.state = "success";
    connectionElements.verificationResult.textContent = `Đã xác minh ${modelName(result.model)} · effort ${result.reasoning_effort || reasoningEffort} lúc ${formatTimestamp(result.verified_at)}.`;
    if (connectionState.provider) {
      connectionState.provider.verification = {
        model: result.model,
        reasoning_effort: result.reasoning_effort || reasoningEffort,
        verified_at: result.verified_at,
      };
      renderProvider();
    }
  } catch (error) {
    await refreshProviderAfterAuthFailure(error);
    connectionElements.verificationResult.dataset.state = "error";
    connectionElements.verificationResult.textContent = "Không xác minh được kết nối. Yêu cầu không được tự động gửi lại.";
    showConnectionError(error);
  } finally {
    connectionState.verifying = false;
    updateConnectionActions();
  }
}

function setDisconnectConfirmation(open) {
  connectionElements.disconnectConfirm.hidden = !open;
  connectionElements.disconnectTrigger.hidden = open;
  if (open) connectionElements.disconnectConfirmButton.focus();
  else connectionElements.disconnectTrigger.focus();
}

async function disconnectConnection() {
  if (connectionState.disconnecting) return;
  clearConnectionError();
  connectionState.disconnecting = true;
  connectionElements.disconnectConfirmButton.textContent = "Đang ngắt kết nối…";
  updateConnectionActions();
  try {
    const result = await connectionRequest("/api/providers/chatgpt/connection", { method: "DELETE" });
    if (result.status !== "disconnected") {
      throw new ConnectionApiError("Máy chủ chưa xác nhận đã ngắt kết nối ChatGPT.", "DISCONNECT_NOT_CONFIRMED");
    }
    connectionState.provider = {
      ...(connectionState.provider || {}),
      id: "chatgpt",
      status: "disconnected",
      account: null,
      verification: null,
    };
    connectionState.models = [];
    connectionElements.verificationResult.textContent = "";
    connectionElements.verificationResult.dataset.state = "";
    connectionElements.modelSelect.replaceChildren();
    const placeholder = document.createElement("option");
    placeholder.value = "";
      placeholder.textContent = "Kết nối ChatGPT để tải mô hình";
    connectionElements.modelSelect.append(placeholder);
    connectionElements.disconnectConfirm.hidden = true;
    connectionElements.disconnectTrigger.hidden = false;
    renderProvider();
    window.dispatchEvent(new CustomEvent("asr:provider-choice-changed"));
    if (result.remote_revocation_confirmed === true) {
      setConnectionMessage("Đã xóa thông tin đăng nhập trong không gian làm việc và xác nhận thu hồi quyền truy cập từ xa.");
    } else {
      setConnectionMessage("Đã ngắt kết nối trong không gian làm việc. ChatGPT chưa xác nhận thu hồi quyền từ xa; hãy kiểm tra ChatGPT → Cài đặt → Mức sử dụng.");
    }
    connectionElements.signIn.focus();
  } catch (error) {
    showConnectionError(error);
  } finally {
    connectionState.disconnecting = false;
    connectionElements.disconnectConfirmButton.textContent = "Ngắt kết nối";
    updateConnectionActions();
  }
}

for (const [provider, { button }] of Object.entries(launcherElements)) {
  button.addEventListener("click", async () => {
    if (!connectionElements.dialog.open) connectionElements.dialog.showModal();
    connectionElements.dialog.querySelector(".connections-body").scrollTop = 0; // a closed dialog keeps its scroll
    setConnectionMessage("");
    const loads = Promise.allSettled([loadAccountData(), loadAntigravity()]);
    if (provider !== "antigravity") return;
    const generation = connectionState.loadGeneration;
    document.querySelector("#antigravity-title").focus({ preventScroll: true });
    // The ChatGPT sections above and the Antigravity sections below change height as they load.
    await loads;
    if (generation === connectionState.loadGeneration) {
      document.querySelector("#antigravity-section").scrollIntoView({ block: "start" });
    }
  });
}
connectionElements.close.addEventListener("click", () => connectionElements.dialog.close());
connectionElements.dialog.addEventListener("click", (event) => {
  if (event.target === connectionElements.dialog) connectionElements.dialog.close();
});
connectionElements.signIn.addEventListener("click", () => void startLogin());
connectionElements.cancelSignIn.addEventListener("click", () => void cancelLogin());
connectionElements.retryPoll.addEventListener("click", () => {
  clearConnectionError();
  if (connectionState.activeLogin) scheduleLoginPoll(connectionState.pollGeneration, 0);
});
connectionElements.modelSelect.addEventListener("change", () => {
  connectionState.selectedModel = connectionElements.modelSelect.value;
  renderEfforts(
    connectionState.selectedModel,
    connectionState.selectedModel === connectionState.savedModel
      ? connectionState.savedEffort : "default",
  );
  if (connectionState.selectedModel !== connectionState.savedModel) {
    connectionElements.modelStatus.dataset.state = "";
    connectionElements.modelStatus.textContent = "Lựa chọn mới chưa được lưu.";
  }
  updateConnectionActions();
});
connectionElements.effortSelect.addEventListener("change", () => {
  connectionElements.modelStatus.dataset.state = "";
  connectionElements.modelStatus.textContent = "Mức suy luận mới chưa được lưu.";
  updateConnectionActions();
});
connectionElements.modelForm.addEventListener("submit", saveModel);
connectionElements.verify.addEventListener("click", () => void verifyConnection());
connectionElements.disconnectTrigger.addEventListener("click", () => setDisconnectConfirmation(true));
connectionElements.disconnectKeep.addEventListener("click", () => setDisconnectConfirmation(false));
connectionElements.disconnectConfirmButton.addEventListener("click", () => void disconnectConnection());

restorePendingLogin();
void refreshHeaderStatus();
