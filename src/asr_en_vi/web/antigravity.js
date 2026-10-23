"use strict";

const antigravityElements = {
  badge: document.querySelector("#antigravity-badge"),
  status: document.querySelector("#antigravity-status"),
  account: document.querySelector("#antigravity-account"),
  verificationRow: document.querySelector("#antigravity-verification-row"),
  verificationSummary: document.querySelector("#antigravity-verification-summary"),
  message: document.querySelector("#antigravity-message"),
  error: document.querySelector("#antigravity-error"),
  errorMessage: document.querySelector("#antigravity-error-message"),
  signIn: document.querySelector("#antigravity-sign-in"),
  login: document.querySelector("#antigravity-login"),
  loginCopy: document.querySelector("#antigravity-login-copy"),
  loginLink: document.querySelector("#antigravity-login-link"),
  inputForm: document.querySelector("#antigravity-input-form"),
  inputLabel: document.querySelector("#antigravity-input-label"),
  input: document.querySelector("#antigravity-input"),
  cancel: document.querySelector("#antigravity-cancel"),
  disconnect: document.querySelector("#antigravity-disconnect"),
  modelSection: document.querySelector("#antigravity-model-section"),
  modelForm: document.querySelector("#antigravity-model-form"),
  modelSelect: document.querySelector("#antigravity-model"),
  effortSelect: document.querySelector("#antigravity-effort"),
  modelStatus: document.querySelector("#antigravity-model-status"),
  modelSave: document.querySelector("#antigravity-model-save"),
  verificationSection: document.querySelector("#antigravity-verification-section"),
  verificationResult: document.querySelector("#antigravity-verification-result"),
  verify: document.querySelector("#antigravity-verify"),
};

const antigravityState = {
  provider: null,
  models: [],
  selectedModel: "",
  savedModel: "",
  savedEffort: "high",
  activeLogin: null,
  pollTimer: null,
  busy: false,
};

const antigravityLoginStorageKey = "asr.antigravity.pendingLogin";

function antigravityErrorMessage(error) {
  const known = {
    omp_unavailable: t("Bản cài này chưa có OMP 18.5.0. Hãy dựng lại image có runner đã pin."),
    omp_invalid_runtime: t("OMP không đáp ứng cấu hình cô lập bắt buộc."),
    reconnect_required: t("Phiên Google Antigravity không còn hiệu lực. Hãy kết nối lại."),
    provider_disconnected: t("Hãy kết nối Google Antigravity trước."),
    provider_quota: t("Tài khoản hoặc model Antigravity đã chạm giới hạn hiện tại."),
    model_unavailable: t("Model này không còn khả dụng với tài khoản Antigravity."),
    provider_timeout: t("OMP hoặc Google Antigravity không phản hồi trong thời gian cho phép."),
    provider_busy: t("Một thao tác Antigravity khác đang chạy."),
  };
  if (error && known[error.code]) return known[error.code];
  if (error && error.status === 429) return known.provider_quota;
  if (error && error.status >= 500) return t("Không hoàn tất được thao tác Antigravity. Yêu cầu không được tự động gửi lại.");
  return (error && error.message) || t("Không hoàn tất được thao tác Antigravity.");
}

function clearAntigravityError() {
  antigravityElements.error.hidden = true;
  antigravityElements.errorMessage.textContent = "";
}

function showAntigravityError(error) {
  antigravityElements.errorMessage.textContent = antigravityErrorMessage(error);
  antigravityElements.error.hidden = false;
}

function antigravityStatusCopy(status) {
  if (status === "connected") return t("Đã kết nối");
  if (status === "reconnect_required") return t("Cần kết nối lại");
  if (status === "disconnected") return t("Chưa kết nối");
  return t("Không khả dụng");
}

function antigravityModelName(modelId) {
  return antigravityState.models.find((model) => model.id === modelId)?.display_name || modelId;
}

function updateAntigravityActions() {
  const connected = antigravityState.provider?.status === "connected";
  const available = antigravityState.models.some(
    (model) => model.id === antigravityElements.modelSelect.value,
  );
  antigravityElements.signIn.hidden = connected || Boolean(antigravityState.activeLogin);
  antigravityElements.login.hidden = !antigravityState.activeLogin;
  antigravityElements.disconnect.hidden = !connected;
  antigravityElements.modelSection.hidden = !connected;
  antigravityElements.verificationSection.hidden = !connected;
  antigravityElements.modelSelect.disabled = !connected || antigravityState.busy;
  antigravityElements.effortSelect.disabled = !connected || antigravityState.busy;
  antigravityElements.modelSave.disabled = !available || antigravityState.busy
    || (antigravityElements.modelSelect.value === antigravityState.savedModel
      && antigravityElements.effortSelect.value === antigravityState.savedEffort);
  antigravityElements.verify.disabled = !available || antigravityState.busy;
}

function renderAntigravityProvider() {
  const provider = antigravityState.provider;
  if (!provider) return;
  const status = provider.status;
  const state = ["connected", "disconnected", "reconnect_required"].includes(status)
    ? status : "error";
  antigravityElements.badge.dataset.state = state;
  setLauncherState("antigravity", state, provider.account?.label);
  antigravityElements.badge.textContent = antigravityStatusCopy(status);
  antigravityElements.status.textContent = antigravityStatusCopy(status);
  antigravityElements.account.textContent = provider.account?.label || t("Chưa có thông tin");
  const verification = provider.verification;
  if (verification?.model && verification?.verified_at) {
    antigravityElements.verificationSummary.textContent = `${antigravityModelName(verification.model)} · ${formatTimestamp(verification.verified_at)}`;
    antigravityElements.verificationRow.hidden = false;
  } else {
    antigravityElements.verificationRow.hidden = true;
  }
  updateAntigravityActions();
}

function renderAntigravityModels(catalog) {
  antigravityState.models = Array.isArray(catalog.models)
    ? catalog.models.filter((model) => model && typeof model.id === "string"
      && typeof model.display_name === "string")
    : [];
  antigravityState.savedModel = typeof catalog.selected_model === "string"
    ? catalog.selected_model : "";
  antigravityState.selectedModel = antigravityState.savedModel;
  antigravityState.savedEffort = catalog.reasoning_effort === "medium" ? "medium" : "high";
  antigravityElements.effortSelect.value = antigravityState.savedEffort;
  antigravityElements.modelSelect.replaceChildren();
  if (!antigravityState.savedModel) {
    const placeholder = document.createElement("option");
    placeholder.value = "";
    placeholder.textContent = antigravityState.models.length
      ? t("Chọn mô hình Antigravity") : t("Không có mô hình Antigravity khả dụng");
    antigravityElements.modelSelect.append(placeholder);
  } else if (!antigravityState.models.some((model) => model.id === antigravityState.savedModel)) {
    const unavailable = document.createElement("option");
    unavailable.value = antigravityState.savedModel;
    unavailable.textContent = t("{model} — không còn khả dụng", { model: antigravityState.savedModel });
    unavailable.disabled = true;
    unavailable.selected = true;
    antigravityElements.modelSelect.append(unavailable);
    antigravityElements.modelStatus.dataset.state = "error";
    antigravityElements.modelStatus.textContent = t("Model đã lưu không còn trong catalog. Hãy chọn model khác.");
  }
  for (const model of antigravityState.models) {
    const option = document.createElement("option");
    option.value = model.id;
    option.textContent = model.display_name;
    option.selected = model.id === antigravityState.savedModel;
    antigravityElements.modelSelect.append(option);
  }
  updateAntigravityActions();
}

function clearAntigravityModels() {
  antigravityState.models = [];
  antigravityState.selectedModel = "";
  antigravityState.savedModel = "";
  antigravityElements.modelSelect.replaceChildren();
  const placeholder = document.createElement("option");
  placeholder.value = "";
  placeholder.textContent = t("Kết nối Antigravity để tải model");
  antigravityElements.modelSelect.append(placeholder);
}

async function handleAntigravityReconnect(error) {
  if (!error || !["reconnect_required", "provider_disconnected"].includes(error.code)) return;
  const status = error.code === "provider_disconnected" ? "disconnected" : "reconnect_required";
  antigravityState.provider = {
    id: "antigravity",
    connection_version: 0,
    ...antigravityState.provider,
    status,
    account: null,
    verification: null,
  };
  clearAntigravityModels();
  renderAntigravityProvider();
  try {
    const payload = await connectionRequest("/api/providers");
    const provider = Array.isArray(payload.providers)
      ? payload.providers.find((item) => item?.id === "antigravity") : null;
    if (provider) {
      antigravityState.provider = provider;
      if (provider.status !== "connected") clearAntigravityModels();
      renderAntigravityProvider();
    }
  } catch {
    // Keep the conservative reconnect state when the refresh itself is unavailable.
  }
}

async function loadAntigravity() {
  clearAntigravityError();
  try {
    const payload = await connectionRequest("/api/providers");
    const provider = Array.isArray(payload.providers)
      ? payload.providers.find((item) => item?.id === "antigravity") : null;
    if (!provider) throw new ConnectionApiError(t("Thiếu trạng thái Antigravity."), "INVALID_PROVIDER_STATUS");
    antigravityState.provider = provider;
    renderAntigravityProvider();
    if (provider.status === "connected") {
      renderAntigravityModels(await connectionRequest("/api/providers/antigravity/models"));
    } else {
      clearAntigravityModels();
      updateAntigravityActions();
    }
  } catch (error) {
    await handleAntigravityReconnect(error);
    showAntigravityError(error);
    if (!["reconnect_required", "provider_disconnected"].includes(error.code)) {
      antigravityElements.badge.dataset.state = "error";
      antigravityElements.badge.textContent = t("Không khả dụng");
      setLauncherState("antigravity", "error");
    }
  }
}

function persistAntigravityLogin(login) {
  try {
    if (login) sessionStorage.setItem(antigravityLoginStorageKey, JSON.stringify(login));
    else sessionStorage.removeItem(antigravityLoginStorageKey);
  } catch {
    // Polling remains available for the current page without browser storage.
  }
}

function setAntigravityLogin(session) {
  antigravityState.activeLogin = { id: session.id, expiresAt: session.expires_at };
  persistAntigravityLogin(antigravityState.activeLogin);
  antigravityElements.loginCopy.textContent = session.instructions
    || t("Hoàn tất đăng nhập Google trong trang do OMP cung cấp.");
  if (typeof session.authorization_url === "string" && session.authorization_url) {
    let url;
    try {
      url = new URL(session.authorization_url);
    } catch {
      throw new ConnectionApiError(t("OMP trả về URL đăng nhập không hợp lệ."), "INVALID_AUTHORIZATION_URL");
    }
    if (!(["https:"].includes(url.protocol) || (url.protocol === "http:"
      && ["127.0.0.1", "localhost"].includes(url.hostname))) || url.username || url.password) {
      throw new ConnectionApiError(t("OMP trả về URL đăng nhập không an toàn."), "INVALID_AUTHORIZATION_URL");
    }
    antigravityElements.loginLink.href = url.href;
    antigravityElements.loginLink.hidden = false;
  }
  if (typeof session.input_prompt === "string" && session.input_prompt) {
    antigravityElements.inputLabel.textContent = session.input_prompt;
    antigravityElements.inputForm.hidden = false;
  }
  updateAntigravityActions();
}

function finishAntigravityLogin(status, error = null) {
  if (antigravityState.pollTimer !== null) window.clearTimeout(antigravityState.pollTimer);
  antigravityState.pollTimer = null;
  antigravityState.activeLogin = null;
  persistAntigravityLogin(null);
  antigravityElements.loginLink.hidden = true;
  antigravityElements.inputForm.hidden = true;
  if (status === "connected") {
    antigravityElements.message.textContent = t("Đã kết nối Google Antigravity qua OMP.");
    void loadAntigravity();
    window.dispatchEvent(new CustomEvent("asr:provider-choice-changed"));
  } else if (status === "cancelled") {
    antigravityElements.message.textContent = t("Đã hủy đăng nhập Antigravity.");
  } else if (status === "expired") {
    showAntigravityError({ code: "provider_timeout" });
  } else if (status === "failed") {
    showAntigravityError(error || { code: "provider_unavailable" });
  }
  updateAntigravityActions();
}

function antigravityLoginIsMissing(error) {
  return Boolean(error && (error.code === "login_session_not_found" || error.status === 404));
}

async function pollAntigravityLogin() {
  if (!antigravityState.activeLogin) return;
  try {
    const session = await connectionRequest(
      `/api/providers/antigravity/login-sessions/${encodeURIComponent(antigravityState.activeLogin.id)}`,
    );
    if (session.status === "pending") {
      setAntigravityLogin(session);
      antigravityState.pollTimer = window.setTimeout(pollAntigravityLogin, 1000);
      return;
    }
    finishAntigravityLogin(session.status, session.error);
  } catch (error) {
    if (antigravityLoginIsMissing(error)) {
      finishAntigravityLogin("expired");
      return;
    }
    showAntigravityError(error);
    antigravityState.pollTimer = window.setTimeout(pollAntigravityLogin, 2000);
  }
}

async function startAntigravityLogin() {
  clearAntigravityError();
  antigravityElements.signIn.disabled = true;
  try {
    const session = await connectionRequest("/api/providers/antigravity/login-sessions", {
      method: "POST", body: {},
    });
    setAntigravityLogin(session);
    void pollAntigravityLogin();
  } catch (error) {
    showAntigravityError(error);
  } finally {
    antigravityElements.signIn.disabled = false;
  }
}

async function cancelAntigravityLogin() {
  if (!antigravityState.activeLogin) return;
  try {
    const session = await connectionRequest(
      `/api/providers/antigravity/login-sessions/${encodeURIComponent(antigravityState.activeLogin.id)}`,
      { method: "DELETE" },
    );
    finishAntigravityLogin(session.status);
  } catch (error) {
    if (antigravityLoginIsMissing(error)) {
      finishAntigravityLogin("expired");
      return;
    }
    showAntigravityError(error);
  }
}

async function submitAntigravityInput(event) {
  event.preventDefault();
  if (!antigravityState.activeLogin || !antigravityElements.input.value.trim()) return;
  try {
    const session = await connectionRequest(
      `/api/providers/antigravity/login-sessions/${encodeURIComponent(antigravityState.activeLogin.id)}/input`,
      { method: "POST", body: { value: antigravityElements.input.value.trim() } },
    );
    antigravityElements.input.value = "";
    antigravityElements.inputForm.hidden = true;
    setAntigravityLogin(session);
  } catch (error) {
    showAntigravityError(error);
  }
}

async function saveAntigravityModel(event) {
  event.preventDefault();
  const model = antigravityElements.modelSelect.value;
  const reasoningEffort = antigravityElements.effortSelect.value;
  if (!model || antigravityState.busy) return;
  antigravityState.busy = true;
  updateAntigravityActions();
  try {
    await connectionRequest("/api/providers/antigravity/preference", {
      method: "PUT", body: { model, reasoning_effort: reasoningEffort },
    });
    antigravityState.savedModel = model;
    antigravityState.savedEffort = reasoningEffort;
    antigravityElements.modelStatus.dataset.state = "saved";
    antigravityElements.modelStatus.textContent = t("Đã lưu {model} · mức suy nghĩ {effort} cho Antigravity.", {
      model: antigravityModelName(model),
      effort: reasoningEffort === "medium" ? "Medium" : "High",
    });
    window.dispatchEvent(new CustomEvent("asr:provider-choice-changed"));
  } catch (error) {
    await handleAntigravityReconnect(error);
    showAntigravityError(error);
  } finally {
    antigravityState.busy = false;
    updateAntigravityActions();
  }
}

async function verifyAntigravity() {
  const model = antigravityElements.modelSelect.value;
  if (!model || antigravityState.busy) return;
  antigravityState.busy = true;
  antigravityElements.verificationResult.dataset.state = "";
  antigravityElements.verificationResult.textContent = t("Đang gửi một yêu cầu tổng hợp qua model đã chọn…");
  updateAntigravityActions();
  try {
    const result = await connectionRequest("/api/providers/antigravity/verify", {
      method: "POST", body: { model },
    });
    antigravityElements.verificationResult.dataset.state = "success";
    antigravityElements.verificationResult.textContent = t("Đã xác minh {model} lúc {time}.", { model: antigravityModelName(model), time: formatTimestamp(result.verified_at) });
    if (antigravityState.provider) {
      antigravityState.provider.verification = result;
      renderAntigravityProvider();
    }
  } catch (error) {
    antigravityElements.verificationResult.dataset.state = "error";
    antigravityElements.verificationResult.textContent = t("Kiểm tra thất bại; yêu cầu không được tự động gửi lại.");
    await handleAntigravityReconnect(error);
    showAntigravityError(error);
  } finally {
    antigravityState.busy = false;
    updateAntigravityActions();
  }
}

async function disconnectAntigravity() {
  if (antigravityState.busy) return;
  antigravityState.busy = true;
  updateAntigravityActions();
  try {
    await connectionRequest("/api/providers/antigravity/connection", { method: "DELETE" });
    antigravityElements.message.textContent = t("Đã ngắt kết nối Antigravity và vô hiệu hóa credential OMP đã lưu.");
    await loadAntigravity();
    window.dispatchEvent(new CustomEvent("asr:provider-choice-changed"));
  } catch (error) {
    showAntigravityError(error);
  } finally {
    antigravityState.busy = false;
    updateAntigravityActions();
  }
}

function markAntigravityChoiceEdited() {
  antigravityState.selectedModel = antigravityElements.modelSelect.value;
  antigravityElements.modelStatus.dataset.state = "";
  antigravityElements.modelStatus.textContent = antigravityState.selectedModel === antigravityState.savedModel
    && antigravityElements.effortSelect.value === antigravityState.savedEffort
    ? "" : t("Lựa chọn mới chưa được lưu.");
  updateAntigravityActions();
}

antigravityElements.signIn.addEventListener("click", () => void startAntigravityLogin());
antigravityElements.cancel.addEventListener("click", () => void cancelAntigravityLogin());
antigravityElements.inputForm.addEventListener("submit", submitAntigravityInput);
antigravityElements.modelSelect.addEventListener("change", () => {
  markAntigravityChoiceEdited();
});
antigravityElements.effortSelect.addEventListener("change", markAntigravityChoiceEdited);
antigravityElements.modelForm.addEventListener("submit", saveAntigravityModel);
antigravityElements.verify.addEventListener("click", () => void verifyAntigravity());
antigravityElements.disconnect.addEventListener("click", () => void disconnectAntigravity());

try {
  const saved = JSON.parse(sessionStorage.getItem(antigravityLoginStorageKey));
  if (saved && typeof saved.id === "string" && typeof saved.expiresAt === "string") {
    const expiresAt = Date.parse(saved.expiresAt);
    if (Number.isFinite(expiresAt) && expiresAt > Date.now()) {
      antigravityState.activeLogin = saved;
      updateAntigravityActions();
      void pollAntigravityLogin();
    } else {
      persistAntigravityLogin(null);
    }
  }
} catch {
  persistAntigravityLogin(null);
}
