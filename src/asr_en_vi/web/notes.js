"use strict";

(() => {
  const $ = (selector) => document.querySelector(selector);
  const ACTIVE_TASK_STATES = new Set(["accepted", "running", "stopping"]);
  const TASK_STATE_LABELS = {
    accepted: t("Đã nhận"),
    running: t("Đang xử lý"),
    stopping: t("Đang dừng"),
    succeeded: t("Đã lưu"),
    failed: t("Thất bại"),
    canceled: t("Đã hủy"),
    interrupted: t("Bị gián đoạn"),
  };
  // Position of each backend stage among the steps listed in #notes-steps (shell.html).
  const TASK_STEP_OF_STAGE = {
    accepted: 0,
    starting: 1,
    starting_notes: 1,
    starting_provider: 1,
    preparing_source: 1,
    generating: 2,
    generating_notes: 2,
    repairing: 2,
    publishing: 3,
    saving: 3,
  };
  const STEP_STATE_LABELS = {
    done: t("Đã xong"),
    current: t("Đang chạy"),
    upcoming: t("Chưa tới"),
    unknown: "",
    failed: TASK_STATE_LABELS.failed,
    canceled: TASK_STATE_LABELS.canceled,
    interrupted: TASK_STATE_LABELS.interrupted,
  };
  const SOURCE_STATE_LABELS = {
    current: t("Nguồn hiện tại"),
    stale: t("Nguồn đã thay đổi"),
    historical: t("Nguồn lịch sử"),
  };
  const OUTPUT_LANGUAGE_LABELS = {
    en: "English",
    vi: t("Tiếng Việt"),
  };
  const VIEW_MODE_KEY = "asr-en-vi:notes-view-mode";

  const PROVIDER_LABELS = { chatgpt: "ChatGPT", antigravity: "Google Antigravity" };
  const PROVIDER_IDS = ["chatgpt", "antigravity"];
  const NEXT_STEP = t("Hệ thống không tự đổi nhà cung cấp, tài khoản hay model. Bạn có thể chọn nhà cung cấp hoặc model khác rồi bắt đầu một lần chạy mới.");
  // Each entry names the pinned provider; the operator decides what to do next.
  const FAILURE_MESSAGES = {
    provider_disconnected: (name) => t("{name} chưa được kết nối. Hãy kết nối lại trong phần Kết nối.", { name }),
    reconnect_required: (name) => t("{name} cần được kết nối lại trước khi tạo notes.", { name }),
    connection_changed: (name) => t("Kết nối {name} đã đổi trong lúc chạy nên tác vụ dừng lại.", { name }),
    provider_quota: (name) => t("{name} đã hết hạn mức sử dụng.", { name }),
    model_unavailable: (name) => t("Model đã chọn không dùng được với {name}; gói hiện tại có thể không bao gồm model này.", { name }),
    thinking_level_unavailable: (name) => t("{name} không áp dụng được mức suy nghĩ đã chọn; tác vụ đã dừng trước khi gửi yêu cầu tiếp theo.", { name }),
    provider_unavailable: (name) => t("{name} tạm thời không khả dụng.", { name }),
    provider_invalid_response: (name) => t("{name} dừng mà không trả về kết quả dùng được nên không có notes mới nào được lưu.", { name }),
    provider_timeout: (name) => t("{name} không phản hồi kịp thời gian.", { name }),
    notes_invalid_output: (name) => t("{name} trả về notes không hợp lệ, kể cả sau một lần sửa tự động.", { name }),
    provider_in_use: (name) => t("{name} đang được một tác vụ notes khác sử dụng.", { name }),
    notes_model_unselected: (name) => t("Chưa chọn model cho {name}.", { name }),
    notes_preference_changed: () => t("Lựa chọn nhà cung cấp hoặc model đã đổi ở nơi khác nên yêu cầu chưa được gửi. Hãy xác nhận lại nhà cung cấp và model đang hiển thị rồi bấm tạo notes lần nữa."),
    login_in_progress: (name) => t("Phiên đăng nhập {name} đang chờ. Hãy hoàn tất hoặc hủy đăng nhập trước khi tạo notes; hệ thống chưa đổi gì.", { name }),
    provider_busy: (name) => t("{name} đang bận với một thao tác kết nối hoặc đăng nhập. Hãy hoàn tất hoặc hủy đăng nhập rồi thử lại; hệ thống chưa đổi gì.", { name }),
  };

  function providerLabel(provider) {
    return PROVIDER_LABELS[provider] || PROVIDER_LABELS.chatgpt;
  }

  // Returns "" when the code has no dedicated copy, so callers fall back to the server text.
  function failureMessage(code, provider) {
    const build = FAILURE_MESSAGES[code];
    return build ? `${build(providerLabel(provider))} ${NEXT_STEP}` : "";
  }

  // The last "view" or "write" choice survives reloads; blocked or bad storage keeps the default.
  function storedViewMode() {
    try {
      return window.localStorage.getItem(VIEW_MODE_KEY) === "write" ? "write" : "view";
    } catch {
      return "view";
    }
  }

  const state = {
    mode: storedViewMode(),
    // Provider choice for the next run; catalogs[provider] is null until a catalog loads.
    choice: {
      loaded: false,
      loadSeq: 0,
      loadedFor: "",
      provider: null,
      localProvider: null,
      preferences: { provider: null, models: {}, reasoning_effort: "default", reasoning_efforts: {} },
      status: { chatgpt: "disconnected", antigravity: "disconnected" },
      catalogs: { chatgpt: null, antigravity: null },
      catalogErrors: { chatgpt: "", antigravity: "" },
      saving: false,
      loading: false,
      message: "",
      open: false, // "Đổi…" is showing the selects and the description of what is sent
    },
    // The step each notes task was last seen running, by task id: the backend overwrites
    // the stage when a run fails, is canceled or is interrupted.
    taskSteps: new Map(),
    currentMeetingId: null,
    currentMeeting: null,
    transcriptionRequestInFlight: false,
    view: "",
    meetings: new Map(),
    drafts: new Map(),
    outputLanguages: new Map(),
    pendingRequests: new Map(),
    sourceCache: new Map(),
    readSeq: 0,
    pollSeq: 0,
    pollTimer: 0,
    selectionSeq: 0,
    sourceSeq: 0,
    sourceKey: "",
    currentSource: null,
  };

  function meetingNotes(meetingId) {
    if (!state.meetings.has(meetingId)) {
      state.meetings.set(meetingId, {
        revisions: [],
        task: null,
        sourceLocked: false,
        sourceLockKnown: false,
        known: false, // the server has answered a notes read (or failed one) since the meeting opened
        selectedNoteId: null,
        requestInFlight: false,
        cancelInFlight: false,
        saveInFlight: new Set(),
        readError: "",
        runError: "",
        runErrorUncertain: false,
        actionMessage: "",
      });
    }
    return state.meetings.get(meetingId);
  }

  function currentNotes() {
    return state.currentMeetingId ? meetingNotes(state.currentMeetingId) : null;
  }

  class NotesApiError extends Error {
    constructor(message, status = 0, payload = null) {
      super(message);
      this.name = "NotesApiError";
      this.status = status;
      this.payload = payload;
    }
  }

  function errorMessage(payload, status) {
    const detail = payload && payload.detail;
    if (typeof detail === "string" && detail.trim()) return detail.trim();
    if (detail && typeof detail.message === "string" && detail.message.trim()) return detail.message.trim();
    if (status === 401) return t("Phiên truy cập không còn hợp lệ. Hãy mở lại workspace.");
    if (status === 403) return t("Yêu cầu notes bị từ chối.");
    if (status === 404) return t("Không tìm thấy notes hoặc nguồn transcript đã lưu.");
    if (status === 409) return t("Dữ liệu đã thay đổi. Hãy tải bản mới nhất rồi thử lại.");
    if (status >= 500) return t("Máy chủ chưa thể hoàn tất yêu cầu notes.");
    return t("Máy chủ chưa thể hoàn tất yêu cầu notes.");
  }

  async function apiJson(path, options = {}) {
    const method = (options.method || "GET").toUpperCase();
    const headers = { Accept: "application/json" };
    if (method !== "GET" && method !== "HEAD") headers["Content-Type"] = "application/json";
    let response;
    try {
      response = await fetch(path, {
        method,
        headers,
        credentials: "same-origin",
        cache: "no-store",
        body: options.body,
      });
    } catch (error) {
      if (error && error.name === "AbortError") throw error;
      throw new NotesApiError(t("Không kết nối được với máy chủ trên máy này."));
    }
    let payload = null;
    try {
      payload = await response.json();
    } catch {
      payload = null;
    }
    if (!response.ok) throw new NotesApiError(errorMessage(payload, response.status), response.status, payload);
    return payload;
  }

  function unwrappedNotesPayload(payload) {
    return payload && payload.notes && typeof payload.notes === "object" ? payload.notes : payload;
  }

  function normalizeRevision(revision, meetingId) {
    if (
      !revision
      || typeof revision.id !== "string"
      || !revision.id
      || revision.meeting_id !== meetingId
      || typeof revision.source_snapshot_id !== "string"
      || typeof revision.markdown !== "string"
      || !Number.isInteger(revision.edit_version)
      || !["current", "stale", "historical"].includes(revision.source_state)
    ) return null;
    return {
      ...revision,
      output_language: ["en", "vi"].includes(revision.output_language)
        ? revision.output_language
        : "en",
      citations: normalizeCitations(revision.citations),
      // The source links of the saved Markdown that open no source; a server without the field names none.
      warnings: Array.isArray(revision.warnings)
        ? revision.warnings.filter((warning) => warning && typeof warning.href === "string")
        : [],
    };
  }

  // A revision made before citations were kept has none; an entry or source of another shape is dropped.
  function normalizeCitations(citations) {
    if (!Array.isArray(citations)) return [];
    return citations
      .filter((entry) => entry
        && typeof entry.section === "string"
        && typeof entry.text === "string"
        && Array.isArray(entry.sources))
      .map((entry) => ({
        section: entry.section,
        text: entry.text,
        sources: entry.sources.filter((source) => source
          && typeof source.id === "string"
          && source.id
          && Number.isFinite(source.start_seconds)
          && source.start_seconds >= 0),
      }));
  }

  function isNotesTask(task) {
    return Boolean(task && (task.kind === undefined || task.kind === "notes"));
  }

  function installNotesPayload(meetingId, payload) {
    const notes = unwrappedNotesPayload(payload);
    if (!notes || !Array.isArray(notes.revisions) || typeof notes.source_locked !== "boolean") {
      throw new Error(t("Máy chủ không trả về trạng thái notes theo API đã công bố."));
    }
    const revisions = notes.revisions
      .map((revision) => normalizeRevision(revision, meetingId))
      .filter(Boolean);
    const data = meetingNotes(meetingId);
    const wasActive = activeTask(data);
    data.revisions = revisions;
    data.task = isNotesTask(notes.task) ? notes.task || null : null;
    // A finished run frees its provider, so catalogs that were blocked can load again.
    if (wasActive && !activeTask(data)) {
      state.choice.message = "";
      void loadProviderChoice(meetingId);
    }
    if (!state.choice.loaded && !state.choice.loading) void loadProviderChoice(meetingId);
    data.sourceLocked = notes.source_locked;
    data.sourceLockKnown = true;
    data.known = true;
    data.readError = "";
    if (!data.selectedNoteId && revisions.length) data.selectedNoteId = revisions[0].id;
    const pending = getPendingRequest(meetingId, false);
    if (
      data.task
      && pending
      && (data.task.request_id === pending.request_id || ACTIVE_TASK_STATES.has(data.task.status))
    ) clearPendingRequest(meetingId);
    if (window.ASRMeetingHistory && typeof window.ASRMeetingHistory.setNotesSourceLock === "function") {
      window.ASRMeetingHistory.setNotesSourceLock(meetingId, data.sourceLocked, true);
    }
    render();
    startTaskPolling(meetingId, data.task);
  }

  function formatSeconds(value) {
    if (!Number.isFinite(value) || value < 0) return "00:00:00";
    const seconds = Math.floor(value);
    return `${String(Math.floor(seconds / 3600)).padStart(2, "0")}:${String(Math.floor((seconds % 3600) / 60)).padStart(2, "0")}:${String(seconds % 60).padStart(2, "0")}`;
  }

  function sourceStateLabel(sourceState) {
    return SOURCE_STATE_LABELS[sourceState] || t("Nguồn chưa xác định");
  }

  function outputLanguageLabel(language) {
    return OUTPUT_LANGUAGE_LABELS[language] || OUTPUT_LANGUAGE_LABELS.en;
  }

  function revisionProvenance(revision) {
    const provider = typeof revision.provider === "string" && revision.provider.trim()
      ? providerLabel(revision.provider.trim())
      : "";
    return [provider, revision.model, revision.reasoning_effort].filter(
      (value) => typeof value === "string" && value.trim(),
    );
  }

  function revisionOptionLabel(revision, index, count) {
    const number = count - index;
    const provenance = revisionProvenance(revision);
    return t("Bản {number} · {source}", { number, source: sourceStateLabel(revision.source_state) })
      + (provenance.length ? ` · ${provenance.join(" / ")}` : "");
  }

  function activeTask(data) {
    return Boolean(data && data.task && ACTIVE_TASK_STATES.has(data.task.status));
  }

  function currentGeneration(meeting) {
    const generation = meeting && meeting.transcription && meeting.transcription.generation;
    return generation && generation.status === "complete" ? generation : null;
  }

  function transcriptionBusy(meeting) {
    const task = meeting && meeting.transcription && meeting.transcription.task;
    return state.transcriptionRequestInFlight || Boolean(
      task && ACTIVE_TASK_STATES.has(task.status),
    );
  }

  function hasRequestVersions(meeting, generation) {
    return Boolean(
      generation
      && Number.isInteger(generation.source_version)
      && Number.isInteger(meeting && meeting.metadata_version),
    );
  }

  function isCompletePendingRequest(pending) {
    return Boolean(
      pending
      && typeof pending.expected_generation_id === "string"
      && Number.isInteger(pending.expected_source_version)
      && Number.isInteger(pending.expected_metadata_version)
    );
  }

  function savedModel(provider) {
    const model = state.choice.preferences.models[provider];
    return typeof model === "string" ? model : "";
  }

  function catalogModels(provider) {
    const catalog = state.choice.catalogs[provider];
    return catalog ? catalog.models : null;
  }

  function modelName(provider, modelId) {
    const models = catalogModels(provider);
    const model = models && models.find((item) => item.id === modelId);
    return model ? model.display_name : modelId;
  }

  function effortLabel(effort) {
    return effort === "medium" ? "Medium" : "High";
  }

  function effortFor(provider, modelId) {
    if (provider === "antigravity") {
      const saved = state.choice.preferences.reasoning_efforts.antigravity;
      return saved === "medium" ? "medium" : "high";
    }
    if (provider !== "chatgpt") return "default";
    const effort = state.choice.preferences.reasoning_effort;
    const models = catalogModels(provider);
    const model = models && models.find((item) => item.id === modelId);
    if (model && Array.isArray(model.reasoning_efforts) && !model.reasoning_efforts.includes(effort)) {
      return "default";
    }
    return typeof effort === "string" ? effort : "default";
  }

  // The provider for the next run: a pending retry keeps its provider, then the operator's choice,
  // the last saved provider, the only connected provider, and finally ChatGPT.
  function selectedProvider(pending) {
    const choice = state.choice;
    if (pending && PROVIDER_IDS.includes(pending.provider)) return pending.provider;
    if (PROVIDER_IDS.includes(choice.localProvider)) return choice.localProvider;
    if (PROVIDER_IDS.includes(choice.preferences.provider)) return choice.preferences.provider;
    const connected = PROVIDER_IDS.filter((id) => choice.status[id] === "connected");
    return connected.length === 1 ? connected[0] : "chatgpt";
  }

  // "ok" when the saved model is usable, otherwise why the operator must act first.
  function modelReadiness(provider) {
    const model = savedModel(provider);
    const models = catalogModels(provider);
    if (models === null) return { ready: true, model, missing: false };
    if (!model) return { ready: false, model, missing: false };
    return { ready: models.some((item) => item.id === model), model, missing: true };
  }

  function normalizeCatalog(payload) {
    const models = payload && Array.isArray(payload.models) ? payload.models : [];
    return {
      models: models
        .filter((item) => item && typeof item.id === "string" && item.id)
        .map((item) => ({
          id: item.id,
          display_name: typeof item.display_name === "string" && item.display_name ? item.display_name : item.id,
          reasoning_efforts: Array.isArray(item.reasoning_efforts) ? item.reasoning_efforts : null,
        })),
    };
  }

  function catalogUnavailableReason(provider, status) {
    const name = providerLabel(provider);
    if (status === "disconnected") return t("{name} chưa được kết nối nên chưa tải được danh sách model.", { name });
    if (status === "reconnect_required") return t("{name} cần được kết nối lại nên chưa tải được danh sách model.", { name });
    return "";
  }

  async function loadProviderChoice(meetingId) {
    const choice = state.choice;
    const seq = ++choice.loadSeq;
    // A run cannot start while the saved choice and catalogs are still loading.
    choice.loading = true;
    choice.loaded = false;
    render();
    try {
      const [providers, preferences] = await Promise.all([
        apiJson("/api/providers"),
        apiJson("/api/notes-preferences"),
      ]);
      if (seq !== choice.loadSeq) return;
      const list = providers && Array.isArray(providers.providers) ? providers.providers : [];
      for (const id of PROVIDER_IDS) {
        const found = list.find((item) => item && item.id === id);
        choice.status[id] = found && typeof found.status === "string" ? found.status : "disconnected";
      }
      choice.preferences = {
        provider: preferences && PROVIDER_IDS.includes(preferences.provider) ? preferences.provider : null,
        models: preferences && preferences.models && typeof preferences.models === "object"
          ? preferences.models : {},
        reasoning_effort: preferences && typeof preferences.reasoning_effort === "string"
          ? preferences.reasoning_effort : "default",
        reasoning_efforts: preferences && preferences.reasoning_efforts
          && typeof preferences.reasoning_efforts === "object" ? preferences.reasoning_efforts : {},
      };
      choice.loaded = true;
      choice.loadedFor = meetingId;
      render();
      await Promise.all(PROVIDER_IDS.map(async (id) => {
        if (choice.status[id] !== "connected") {
          choice.catalogs[id] = null;
          choice.catalogErrors[id] = catalogUnavailableReason(id, choice.status[id]);
          return;
        }
        try {
          const catalog = normalizeCatalog(await apiJson(`/api/providers/${id}/models`));
          if (seq !== choice.loadSeq) return;
          choice.catalogs[id] = catalog;
          choice.catalogErrors[id] = "";
        } catch (error) {
          if (seq !== choice.loadSeq) return;
          choice.catalogs[id] = null;
          const detail = error && error.payload && error.payload.detail;
          choice.catalogErrors[id] = detail && detail.code === "provider_in_use"
            ? t("{provider} đang chạy notes nên chưa tải lại được danh sách model. Model đã lưu vẫn được giữ.", { provider: providerLabel(id) })
            : t("Chưa tải được danh sách model của {provider}. Model đã lưu vẫn được giữ.", { provider: providerLabel(id) });
        }
      }));
      if (seq !== choice.loadSeq) return;
      choice.loading = false;
      render();
    } catch (error) {
      if (seq !== choice.loadSeq) return;
      choice.loaded = false;
      choice.loading = false;
      choice.message = t("Chưa đọc được lựa chọn nhà cung cấp và model đã lưu. Chưa thể tạo notes mới cho tới khi tải lại được.");
      render();
    }
  }

  async function savePreference(provider, model) {
    const choice = state.choice;
    const data = currentNotes();
    // The selects show the new choice at once; a run cannot start until it is saved.
    choice.localProvider = provider;
    choice.saving = true;
    render();
    const body = { provider, model, reasoning_effort: effortFor(provider, model) };
    try {
      const saved = await apiJson("/api/notes-preferences", { method: "PUT", body: JSON.stringify(body) });
      choice.preferences = {
        provider: PROVIDER_IDS.includes(saved && saved.provider) ? saved.provider : provider,
        models: saved && saved.models && typeof saved.models === "object" ? saved.models : { [provider]: model },
        reasoning_effort: provider === "chatgpt" && saved && typeof saved.reasoning_effort === "string"
          ? saved.reasoning_effort : choice.preferences.reasoning_effort,
        reasoning_efforts: saved && saved.reasoning_efforts && typeof saved.reasoning_efforts === "object"
          ? saved.reasoning_efforts : choice.preferences.reasoning_efforts,
      };
      const next = `${providerLabel(provider)} · ${modelName(provider, model)}`;
      choice.message = data && activeTask(data)
        ? t("Đã lưu lựa chọn {next}. Lựa chọn này chỉ áp dụng cho lần chạy tiếp theo; tác vụ đang chạy giữ {provider} · {model}.", {
          next,
          provider: providerLabel(data.task.provider),
          model: data.task.model || t("model đã ghim"),
        })
        : t("Đã lưu lựa chọn {next} cho lần chạy tiếp theo.", { next });
    } catch (error) {
      choice.message = t("Chưa lưu được lựa chọn: {error} Lựa chọn đã lưu trước đó vẫn được giữ.", {
        error: error && error.message ? error.message : t("lỗi không xác định"),
      });
    }
    choice.localProvider = null;
    choice.saving = false;
    render();
  }

  function renderChoice(data, pending) {
    const choice = state.choice;
    const provider = selectedProvider(pending);
    const providerSelect = $("#notes-provider");
    const modelSelect = $("#notes-model");
    const locked = Boolean(pending) || Boolean(data && data.requestInFlight) || choice.saving;
    providerSelect.value = provider;
    providerSelect.disabled = locked;
    const readiness = modelReadiness(provider);
    const models = catalogModels(provider);
    const key = `${provider}\u0000${readiness.model}\u0000${models ? models.map((item) => item.id).join("\u0001") : "-"}`;
    if (modelSelect.dataset.optionsKey !== key) {
      modelSelect.replaceChildren();
      const add = (value, text) => {
        const option = document.createElement("option");
        option.value = value;
        option.textContent = text;
        modelSelect.append(option);
      };
      if (models === null) add(readiness.model, readiness.model || t("Chưa có model"));
      else {
        if (!readiness.ready) add("", readiness.model ? t("Chọn model khác") : t("Chọn model"));
        for (const item of models) add(item.id, item.display_name);
      }
      modelSelect.dataset.optionsKey = key;
    }
    modelSelect.value = readiness.ready || models === null ? readiness.model : "";
    modelSelect.disabled = locked || models === null || models.length === 0;
    const name = providerLabel(provider);
    let effort = provider === "chatgpt" && choice.preferences.reasoning_effort !== "default"
      ? ` · effort ${choice.preferences.reasoning_effort}` : "";
    if (provider === "antigravity") effort = t(" · mức suy nghĩ {effort}", { effort: effortLabel(effortFor("antigravity")) });
    const plan = $("#notes-run-plan");
    const reload = $("#notes-choice-reload");
    reload.hidden = choice.loaded || !state.currentMeetingId;
    reload.disabled = choice.loading;
    if (!choice.loaded && !choice.loading && !pending) {
      plan.textContent = t("Chưa đọc được lựa chọn đã lưu nên chưa thể tạo notes mới. Hãy bấm “Tải lại lựa chọn”.");
    } else if (readiness.ready && readiness.model && models !== null) {
      plan.textContent = t("Lần chạy tiếp theo dùng {name} · {model}{effort}.", { name, model: modelName(provider, readiness.model), effort });
    } else if (readiness.missing) {
      plan.textContent = t("Model đã lưu “{model}” không còn trong danh sách của {name}. Hãy chọn model khác; hệ thống không tự chọn thay.", { model: readiness.model, name });
    } else if (models !== null) {
      plan.textContent = t("Chưa chọn model cho {name}. Hãy chọn một model trước khi tạo notes.", { name });
    } else {
      plan.textContent = t("Lần chạy tiếp theo dùng {name}{model}. {error}", {
        name,
        model: readiness.model ? ` · ${readiness.model}${effort}` : "",
        error: choice.catalogErrors[provider],
      }).trim();
    }
    const preferenceStatus = $("#notes-preference-status");
    preferenceStatus.textContent = choice.message;
    $("#notes-content-policy").textContent = t("Ngày họp, lời thoại, mốc thời gian và tên người nói được gửi tới {name} bằng model đã chọn. Với nguồn dài, các bản tóm tắt trung gian cũng được gửi để tổng hợp notes. File audio/video, tên cuộc họp và thông tin tài khoản không được gửi.", { name });
    // The plan line belongs to the open choice, except when the action cannot simply run and it says why.
    const stuck = needsConnection(data, provider, readiness, pending) || (!choice.loaded && !choice.loading && !pending);
    plan.hidden = !stuck && !choice.open;
    $("#notes-choice").hidden = !choice.open;
    $("#notes-change").setAttribute("aria-expanded", String(choice.open));
    return { provider, readiness };
  }

  // The chosen provider is not connected or has no usable model: Connections is the next step, not a run.
  // A run in progress keeps its own button; the choice only matters again once it ends.
  function needsConnection(data, provider, readiness, pending) {
    const choice = state.choice;
    return choice.loaded
      && !pending
      && !activeTask(data)
      && !(data && data.requestInFlight)
      && (choice.status[provider] !== "connected" || !readiness.ready || !readiness.model);
  }

  // What one press does, from the saved choice. Until that and the model names are read, only the rest.
  function runLabel(verb, language, provider, readiness) {
    const label = [verb, outputLanguageLabel(language)];
    if (state.choice.loaded && !state.choice.loading) {
      const model = readiness.model ? modelName(provider, readiness.model) : "";
      label.push([providerLabel(provider), model].filter(Boolean).join(" "));
    }
    return label.join(" · ");
  }

  // Until notes exist the action is the primary one on the tab; afterwards it is one secondary tool in the
  // notes toolbar. The whole group moves, so its choice and reminder stay beside the button.
  function placeRunControls(inToolbar) {
    const controls = $("#notes-run");
    const host = inToolbar ? $("#notes-toolbar") : $("#notes-create");
    if (controls.parentElement !== host) {
      const focused = controls.contains(document.activeElement) ? document.activeElement : null;
      host.append(controls);
      if (focused) focused.focus({ preventScroll: true });
    }
    $("#notes-start").classList.toggle("primary-button", !inToolbar);
    $("#notes-start").classList.toggle("secondary-button", inToolbar);
  }

  // A run copies the speaker names as they stand, so say which ones are still the system's own.
  function renderSpeakerReminder(meeting, data) {
    const history = window.ASRMeetingHistory;
    const generation = currentGeneration(meeting);
    const names = history && generation ? history.defaultSpeakerNames(generation) : [];
    // While a run holds the source the names cannot change, so there is nothing to do first.
    $("#notes-speaker-reminder").hidden = !names.length || activeTask(data) || Boolean(data && data.sourceLocked);
    $("#notes-speaker-names").textContent = names.length
      ? t("Notes sẽ dùng tên người nói hiện tại: {names}.", { names: names.join(", ") })
      : "";
  }

  // A new run needs the saved choice loaded for this meeting and a model to show for the provider.
  function newRunChoiceReady(meeting) {
    const choice = state.choice;
    if (!choice.loaded || choice.loadedFor !== meeting.id) return false;
    const readiness = modelReadiness(selectedProvider(null));
    return readiness.ready && Boolean(readiness.model);
  }

  function canStartNotes(meeting, data) {
    const generation = currentGeneration(meeting);
    if (
      !meeting
      || !data
      || !generation
      || transcriptionBusy(meeting)
      || !hasRequestVersions(meeting, generation)
      || !data.sourceLockKnown
      || data.sourceLocked
      || activeTask(data)
      || data.requestInFlight
      || state.choice.saving
    ) return false;
    const pending = getPendingRequest(meeting.id, false);
    return Boolean(
      (!state.choice.loading || isCompletePendingRequest(pending))
      && (pending || newRunChoiceReady(meeting)),
    );
  }

  function renderTaskSteps(task) {
    const items = [...$("#notes-steps").children];
    const end = items.pop();
    const ended = ["failed", "canceled", "interrupted"].includes(task.status);
    if (ACTIVE_TASK_STATES.has(task.status) && Object.hasOwn(TASK_STEP_OF_STAGE, task.stage)) {
      state.taskSteps.set(task.id, TASK_STEP_OF_STAGE[task.stage]);
    }
    const reached = state.taskSteps.get(task.id);
    items.forEach((item, index) => {
      let stepState = "unknown";
      if (task.status === "succeeded") stepState = "done";
      else if (reached !== undefined) {
        if (index < reached) stepState = "done";
        else if (index > reached) stepState = "upcoming";
        else stepState = ended ? task.status : "current";
      }
      item.dataset.stepState = stepState;
      item.querySelector(".notes-step-state").textContent = STEP_STATE_LABELS[stepState];
      if (stepState === "current") item.setAttribute("aria-current", "step");
      else item.removeAttribute("aria-current");
    });
    // A run first seen after it ended has no known step, so say only how it ended.
    end.hidden = !ended || reached !== undefined;
    end.dataset.stepState = end.hidden ? "" : task.status;
    end.firstElementChild.textContent = end.hidden ? "" : TASK_STATE_LABELS[task.status];
  }

  function renderTask(data) {
    const details = $("#notes-task-details");
    const status = $("#notes-status");
    const task = data && data.task;
    details.hidden = !task;
    if (!task) {
      if (data && data.readError) status.textContent = t("Chưa đọc được trạng thái notes đã lưu.");
      else if (!state.currentMeeting) status.textContent = t("Mở một cuộc họp để xem hoặc tạo notes.");
      else if (!currentGeneration(state.currentMeeting)) status.textContent = t("Cần transcript hoàn chỉnh trước khi tạo notes.");
      else status.textContent = t("Transcript hoàn chỉnh đã sẵn sàng. Notes dùng nhà cung cấp và model đang chọn.");
      $("#notes-cancel").hidden = true;
      return;
    }
    const taskProvider = PROVIDER_IDS.includes(task.provider) ? task.provider : "chatgpt";
    const taskProviderName = providerLabel(taskProvider);
    renderTaskSteps(task);
    const taskEffort = taskProvider === "antigravity"
      ? t("mức suy nghĩ {effort}", { effort: effortLabel(task.reasoning_effort === "medium" ? "medium" : "high") })
      : (taskProvider === "chatgpt" && task.reasoning_effort
        && task.reasoning_effort !== "default" ? `effort ${task.reasoning_effort}` : "");
    $("#notes-task-elapsed").textContent = t("Đã chạy {n} giây", { n: Math.max(0, Number(task.elapsed_seconds) || 0).toFixed(1) });
    $("#notes-task-provider-model").textContent = [taskProviderName, task.model, taskEffort]
      .filter(Boolean).join(" · ");
    const active = ACTIVE_TASK_STATES.has(task.status);
    if (task.status === "accepted") status.textContent = t("Tác vụ đã được nhận. Worker sẽ bắt đầu xử lý notes.");
    else if (task.status === "running") status.textContent = t("{taskProviderName} đang tạo notes. Tác vụ tiếp tục ở worker nếu bạn mở cuộc họp khác.", { taskProviderName });
    else if (task.status === "stopping") status.textContent = t("Đã gửi yêu cầu hủy. Tác vụ vẫn giữ slot cho đến khi worker xác nhận dừng.");
    else if (task.status === "succeeded") status.textContent = t("Notes đã được lưu. Chọn revision bên dưới để xem hoặc sửa.");
    else if (task.status === "failed") {
      status.textContent = failureMessage(task.error_code, taskProvider)
        || task.error_message
        || t("Tác vụ notes bằng {provider} thất bại. {next}", { provider: taskProviderName, next: NEXT_STEP });
    }
    else if (task.status === "canceled") status.textContent = t("Worker đã xác nhận hủy tác vụ notes.");
    else if (task.status === "interrupted") status.textContent = t("Worker đã dừng giữa tác vụ notes. Không tự chạy lại.");
    else status.textContent = t("Đang đọc trạng thái tác vụ notes.");
    if (task.error_message && !["failed", "interrupted"].includes(task.status)) {
      status.textContent += ` ${task.error_message}`;
    }
    const cancel = $("#notes-cancel");
    cancel.hidden = !active;
    cancel.disabled = !active || task.status === "stopping" || data.cancelInFlight;
    cancel.textContent = task.status === "stopping" || data.cancelInFlight ? t("Đang dừng…") : t("Hủy tạo notes");
  }

  function renderError(data) {
    const wrapper = $("#notes-error");
    const message = $("#notes-error-message");
    const text = data && (data.runError || data.readError);
    wrapper.hidden = !text;
    message.textContent = text || "";
  }

  function revisionDraft(revision) {
    let draft = state.drafts.get(revision.id);
    if (!draft) {
      draft = {
        value: revision.markdown,
        baselineMarkdown: revision.markdown,
        expectedEditVersion: revision.edit_version,
        conflict: null,
      };
      state.drafts.set(revision.id, draft);
    } else if (draft.value === draft.baselineMarkdown) {
      draft.value = revision.markdown;
      draft.baselineMarkdown = revision.markdown;
      draft.expectedEditVersion = revision.edit_version;
      draft.conflict = null;
    } else if (revision.edit_version !== draft.expectedEditVersion) {
      draft.conflict = {
        markdown: revision.markdown,
        editVersion: revision.edit_version,
      };
    }
    return draft;
  }

  function draftIsDirty(draft) {
    return Boolean(draft && draft.value !== draft.baselineMarkdown);
  }

  // The address of a saved source: the Transcript tab, where its card sits under the player.
  function sourceHref(meetingId, snapshotId, segmentId) {
    return `/meetings/${encodeURIComponent(meetingId)}?notes_source=${encodeURIComponent(snapshotId)}&segment=${encodeURIComponent(segmentId)}#transcript`;
  }

  // A source link is spelled with the literal notes_source=; the server names the broken ones by that spelling.
  function sourceReference(rawHref, expectedMeetingId = null, expectedSnapshotId = null) {
    if (typeof rawHref !== "string" || !rawHref.includes("notes_source=")) return null;
    if (!rawHref.startsWith("/") || rawHref.startsWith("//")) return null;
    let url;
    try {
      url = new URL(rawHref, window.location.origin);
    } catch {
      return null;
    }
    if (
      url.origin !== window.location.origin
      || (url.hash && url.hash !== "#transcript")
      || url.username
      || url.password
    ) return null;
    const pathMatch = url.pathname.match(/^\/meetings\/([^/]+)$/);
    if (!pathMatch) return null;
    let meetingId;
    try {
      meetingId = decodeURIComponent(pathMatch[1]);
    } catch {
      return null;
    }
    if (!meetingId || meetingId.includes("/")) return null;
    const params = [...url.searchParams.entries()];
    if (
      params.length !== 2
      || params[0][0] !== "notes_source"
      || params[1][0] !== "segment"
      || !params[0][1]
      || !params[1][1]
    ) return null;
    const snapshotId = params[0][1];
    const segmentId = params[1][1];
    if (
      (expectedMeetingId && meetingId !== expectedMeetingId)
      || (expectedSnapshotId && snapshotId !== expectedSnapshotId)
    ) return null;
    return { meetingId, snapshotId, segmentId, href: sourceHref(meetingId, snapshotId, segmentId) };
  }

  // mm:ss, or h:mm:ss from one hour on: the time a chip shows and says.
  function chipLabel(seconds) {
    const total = Math.floor(seconds);
    const minutes = String(Math.floor((total % 3600) / 60)).padStart(2, "0");
    const rest = String(total % 60).padStart(2, "0");
    return total >= 3600 ? `${Math.floor(total / 3600)}:${minutes}:${rest}` : `${minutes}:${rest}`;
  }

  // The chip is a link to the saved source, so a middle click or a copied address works as a click does.
  function citationChip(revision, source) {
    const label = chipLabel(source.start_seconds);
    const link = document.createElement("a");
    link.className = "notes-citation-chip";
    link.href = sourceHref(revision.meeting_id, revision.source_snapshot_id, source.id);
    link.dataset.notesSourceLink = "true";
    link.dataset.meetingId = revision.meeting_id;
    link.dataset.snapshotId = revision.source_snapshot_id;
    link.dataset.segmentId = source.id;
    link.setAttribute("aria-label", t("Nghe lại đoạn nguồn lúc {label}", { label }));
    link.textContent = label;
    return link;
  }

  // The citation sources that still belong to each bullet, by line index. A bullet keeps its chips only
  // while its section heading and its text are exactly what the notes were made with, so an edited bullet
  // shows none and never another bullet's. Each entry is used once, in order. Identical bullets cannot
  // be told apart, so a text keeps its chips only while the notes hold as many bullets with it as they
  // were made with: once one was edited or removed, or another was edited into a copy, none keeps a chip.
  function citedBullets(lines, citations) {
    const found = new Map();
    if (!citations.length) return found;
    const keyOf = (section, text) => `${section}\u0000${text}`;
    const groups = new Map();
    for (const entry of citations) {
      const key = keyOf(entry.section, entry.text);
      if (!groups.has(key)) groups.set(key, { size: 0, queue: [] });
      const group = groups.get(key);
      group.size += 1;
      group.queue.push(entry.sources);
    }
    const bullets = [];
    const counts = new Map();
    let section = "";
    lines.forEach((line, index) => {
      const heading = line.match(/^(#{1,6})\s+(.+)$/);
      if (heading) {
        section = heading[2].trim();
        return;
      }
      const bullet = line.match(/^\s*[-*]\s+(.+)$/);
      if (!bullet) return;
      const key = keyOf(section, bullet[1].trim());
      bullets.push({ index, key });
      counts.set(key, (counts.get(key) || 0) + 1);
    });
    for (const { index, key } of bullets) {
      const group = groups.get(key);
      if (!group || counts.get(key) !== group.size) continue;
      found.set(index, group.queue.shift());
    }
    return found;
  }

  function appendInline(parent, text, revision) {
    const token = /\[([^\]]+)\]\(([^)\s]+)\)|\*\*([^*]+)\*\*|`([^`]+)`|\*([^*]+)\*/g;
    const unescape = (value) => value.replace(/\\([\\`*_{}\[\]<>()#!|~+\-.>])/g, "$1");
    let previous = 0;
    let match;
    while ((match = token.exec(text))) {
      if (match.index > previous) parent.append(document.createTextNode(unescape(text.slice(previous, match.index))));
      if (match[1] !== undefined) {
        const source = sourceReference(match[2], revision.meeting_id, revision.source_snapshot_id);
        if (revision.warnings.some((warning) => warning.href === match[2])) {
          // Typed with a source the saved snapshot lacks: shown as text, never opened or repaired.
          const invalid = document.createElement("span");
          invalid.className = "notes-link-invalid";
          invalid.textContent = unescape(match[1]);
          const reason = document.createElement("span");
          reason.className = "visually-hidden";
          reason.textContent = t(" (liên kết nguồn không hợp lệ)");
          invalid.append(reason);
          parent.append(invalid);
        } else if (source) {
          const link = document.createElement("a");
          link.href = source.href;
          link.dataset.notesSourceLink = "true";
          link.dataset.meetingId = source.meetingId;
          link.dataset.snapshotId = source.snapshotId;
          link.dataset.segmentId = source.segmentId;
          link.setAttribute("aria-label", t("Mở nguồn transcript tại {time}", { time: unescape(match[1]) }));
          link.textContent = unescape(match[1]);
          parent.append(link);
        } else {
          parent.append(document.createTextNode(unescape(match[0])));
        }
      } else if (match[3] !== undefined) {
        const strong = document.createElement("strong");
        strong.textContent = unescape(match[3]);
        parent.append(strong);
      } else if (match[4] !== undefined) {
        const code = document.createElement("code");
        code.textContent = unescape(match[4]);
        parent.append(code);
      } else {
        const emphasis = document.createElement("em");
        emphasis.textContent = unescape(match[5]);
        parent.append(emphasis);
      }
      previous = token.lastIndex;
    }
    if (previous < text.length) parent.append(document.createTextNode(unescape(text.slice(previous))));
  }

  function renderMarkdown(markdown, revision) {
    const root = $("#notes-preview");
    root.replaceChildren();
    const lines = markdown.replace(/\r\n?/g, "\n").split("\n");
    // The panel's own heading is an h3, so the shallowest heading in the notes becomes an h4.
    const shallowest = Math.min(
      ...lines.map((line) => line.match(/^(#{1,6})\s+(.+)$/)).filter(Boolean).map((match) => match[1].length),
    );
    // Chips belong to Xem; the Markdown, Viết, the copy and the download never carry a reference.
    const cited = state.mode === "view" ? citedBullets(lines, revision.citations || []) : new Map();
    let list = null;
    let paragraph = null;
    const closeParagraph = () => { paragraph = null; };
    const closeList = () => { list = null; };
    for (const [index, line] of lines.entries()) {
      if (!line.trim()) {
        closeParagraph();
        closeList();
        continue;
      }
      const heading = line.match(/^(#{1,6})\s+(.+)$/);
      if (heading) {
        closeParagraph();
        closeList();
        const level = Math.min(6, heading[1].length - shallowest + 4);
        const element = document.createElement(`h${level}`);
        appendInline(element, heading[2], revision);
        root.append(element);
        continue;
      }
      const bullet = line.match(/^\s*[-*]\s+(.+)$/);
      if (bullet) {
        closeParagraph();
        if (!list) {
          list = document.createElement("ul");
          root.append(list);
        }
        const item = document.createElement("li");
        appendInline(item, bullet[1], revision);
        for (const source of cited.get(index) || []) item.append(citationChip(revision, source));
        list.append(item);
        continue;
      }
      closeList();
      if (!paragraph) {
        paragraph = document.createElement("p");
        root.append(paragraph);
      } else {
        paragraph.append(document.createElement("br"));
      }
      appendInline(paragraph, line, revision);
    }
  }

  function applyViewMode() {
    const write = state.mode === "write";
    $("#notes-mode-view").setAttribute("aria-pressed", String(!write));
    $("#notes-mode-write").setAttribute("aria-pressed", String(write));
    $("#notes-preview").hidden = write;
    $("#notes-markdown").hidden = !write;
  }

  // Everything that depends on whether the draft differs from the saved Markdown.
  function renderDraftState(data, revision, draft) {
    const dirty = draftIsDirty(draft);
    const busy = data.saveInFlight.has(revision.id);
    $("#notes-save").disabled = !dirty || busy;
    $("#notes-copy").disabled = dirty || Boolean(draft.conflict) || busy;
    $("#notes-export").disabled = dirty || Boolean(draft.conflict) || busy;
    $("#notes-draft-status").textContent = dirty
      ? t("Có thay đổi chưa lưu. Sao chép và tải xuống chỉ dùng Markdown đã lưu.")
      : t("Đang xem đúng Markdown đã lưu cho revision này.");
    $("#notes-unsaved-dot").hidden = !dirty;
    $("#notes-view-draft").hidden = !dirty || state.mode !== "view";
    const write = $("#notes-mode-write");
    write.setAttribute("aria-label", dirty ? t("Viết, có thay đổi chưa lưu") : t("Viết"));
  }

  function setViewMode(mode) {
    if (mode === state.mode) return;
    state.mode = mode;
    try {
      window.localStorage.setItem(VIEW_MODE_KEY, mode);
    } catch {
      // The choice still holds for this page session.
    }
    renderSelectedRevision(currentNotes());
    if (mode === "write") $("#notes-markdown").focus({ preventScroll: true });
  }

  // The saved Markdown's source links that open no source, said in words above the notes.
  function renderLinkWarning(revision) {
    const line = $("#notes-link-warning");
    const count = revision ? revision.warnings.length : 0;
    line.hidden = !count;
    if (!count) {
      line.replaceChildren();
      return;
    }
    const first = document.createElement("code");
    first.textContent = revision.warnings[0].href;
    line.replaceChildren(
      t("Markdown đã lưu có {count} liên kết nguồn không hợp lệ. Nội dung được giữ nguyên; Xem chỉ hiện chúng dưới dạng chữ và không mở nguồn nào. Liên kết đầu tiên: ", { count }),
      first,
    );
  }

  function renderSelectedRevision(data) {
    const wrapper = $("#notes-saved-work");
    const revision = data && data.revisions.find((item) => item.id === data.selectedNoteId);
    const selector = $("#notes-revision-selector");
    const optionsKey = data
      ? data.revisions.map((item) => `${item.id}\u0001${item.provider || ""}\u0001${item.model || ""}`).join("\u0000")
      : "";
    if (selector.dataset.optionsKey !== optionsKey) {
      selector.replaceChildren();
      if (data && data.selectedNoteId && !data.revisions.some((item) => item.id === data.selectedNoteId)) {
        const missing = document.createElement("option");
        missing.value = data.selectedNoteId;
        missing.textContent = t("Phiên bản đã chọn không còn trong danh sách");
        selector.append(missing);
      }
      if (data) {
        data.revisions.forEach((item, index) => {
          const option = document.createElement("option");
          option.value = item.id;
          option.textContent = revisionOptionLabel(item, index, data.revisions.length);
          selector.append(option);
        });
      }
      selector.dataset.optionsKey = optionsKey;
    }
    selector.value = data && data.selectedNoteId ? data.selectedNoteId : "";
    wrapper.hidden = !revision;
    applyViewMode();
    if (!revision) {
      $("#notes-revision-meta").textContent = data && data.selectedNoteId
        ? t("Phiên bản đã chọn chưa có trong danh sách notes mới nhất. Bản nháp được giữ trong phiên này.")
        : "";
      $("#notes-preview").replaceChildren();
      $("#notes-markdown").value = "";
      renderLinkWarning(null);
      return;
    }
    const draft = revisionDraft(revision);
    const textarea = $("#notes-markdown");
    textarea.disabled = data.saveInFlight.has(revision.id);
    if (textarea.value !== draft.value || document.activeElement !== textarea) textarea.value = draft.value;
    const provenance = revisionProvenance(revision).join(" · ");
    $("#notes-revision-meta").textContent = [
      sourceStateLabel(revision.source_state),
      t("Ngôn ngữ: {language}", { language: outputLanguageLabel(revision.output_language) }),
      provenance,
      `Edit ${revision.edit_version}`,
    ].filter(Boolean).join(" · ");
    renderLinkWarning(revision);
    renderMarkdown(draft.value, revision);
    renderDraftState(data, revision, draft);
    if (draft.conflict) {
      $("#notes-conflict").hidden = false;
      $("#notes-conflict-message").textContent = t("Bản đã lưu đã đổi thành edit {version}. Bản nháp của bạn vẫn được giữ; chọn cách xử lý trước khi lưu.", { version: draft.conflict.editVersion });
      $("#notes-keep-draft").disabled = data.saveInFlight.has(revision.id);
      $("#notes-use-latest").disabled = data.saveInFlight.has(revision.id);
    } else {
      $("#notes-conflict").hidden = true;
      $("#notes-conflict-message").textContent = "";
    }
  }

  // Without a complete transcript the tab offers no run controls at all, only the way to get one.
  function renderTranscriptNeeded(meeting) {
    const needed = Boolean(meeting) && !currentGeneration(meeting);
    $("#notes-empty").hidden = !needed;
    $("#notes-create").hidden = needed;
    $("#notes-run").hidden = needed; // it sits in the toolbar once notes exist
    $("#notes-status").hidden = needed;
    if (!needed) return;
    const task = meeting.transcription && meeting.transcription.task;
    $("#notes-empty-copy").textContent = transcriptionBusy(meeting)
      ? t("Đang chép lời. Notes tạo được sau khi transcript hoàn tất.")
      : task && ["failed", "canceled", "interrupted"].includes(task.status)
        ? t("Lần chép lời gần nhất chưa hoàn tất. Mở Transcript & bản ghi để xem chi tiết và chạy lại.")
        : t("Notes được tạo từ transcript hoàn chỉnh. Chép lời bản ghi trước.");
  }

  function render() {
    const data = currentNotes();
    const meeting = state.currentMeeting;
    if (meeting && window.ASRMeetingHistory) {
      window.ASRMeetingHistory.setNotesSummary(
        meeting.id,
        data ? data.revisions.length : 0,
        data && data.task && data.task.status,
        Boolean(data && data.known),
      );
    }
    renderTranscriptNeeded(meeting);
    const runButton = $("#notes-start");
    const waitForTranscript = transcriptionBusy(meeting);
    const waitMessage = t("Đang xử lý transcript. Chờ tác vụ kết thúc để tạo notes.");
    const pending = state.currentMeetingId
      ? getPendingRequest(state.currentMeetingId, false)
      : null;
    const activeOutputLanguage = activeTask(data)
      ? (data.task.output_language === "vi" ? "vi" : "en")
      : null;
    const outputLanguage = pending
      ? pending.output_language
      : activeOutputLanguage
        || (state.currentMeetingId ? getOutputLanguage(state.currentMeetingId) : "en");
    const languageSelect = $("#notes-output-language");
    languageSelect.value = outputLanguage;
    languageSelect.disabled = Boolean(
      transcriptionBusy(meeting)
      || (data && data.requestInFlight)
      || activeTask(data)
      || pending,
    );
    const { provider, readiness } = renderChoice(data, pending);
    // The one action either starts a run or, when the provider cannot make one yet, opens Connections.
    const connect = needsConnection(data, provider, readiness, pending);
    runButton.dataset.action = connect ? "connect" : "start";
    runButton.setAttribute("aria-describedby", connect ? "notes-run-plan" : "notes-status");
    runButton.disabled = !connect && !canStartNotes(meeting, data);
    runButton.title = !connect && waitForTranscript ? waitMessage : "";
    runButton.textContent = connect
      ? t("Kết nối {provider} để tạo notes", { provider: providerLabel(provider) })
      : data && data.requestInFlight
        ? t("Đang gửi yêu cầu…")
        : pending
          ? t("Xác minh yêu cầu notes")
          : runLabel(data && data.revisions.length ? t("Tạo lại notes") : t("Tạo notes"), outputLanguage, provider, readiness);
    renderSpeakerReminder(meeting, data);
    renderTask(data);
    renderError(data);
    renderSelectedRevision(data);
    // After the saved-work block has settled, so a focused control is not moved while it is hidden.
    placeRunControls(Boolean(data && data.revisions.some((item) => item.id === data.selectedNoteId)));
    if (waitForTranscript) {
      $("#notes-status").textContent = waitMessage;
    } else if (data && data.runErrorUncertain) {
      $("#notes-status").textContent = t("{error} Yêu cầu chưa được tự gửi lại. Bấm “Xác minh yêu cầu notes” để gửi lại cùng request ID.", { error: data.runError });
    }
    const copyStatus = $("#notes-copy-export-status");
    if (data && data.actionMessage) copyStatus.textContent = data.actionMessage;
  }

  function notesEndpoint(meetingId) {
    return `/api/meetings/${encodeURIComponent(meetingId)}/notes`;
  }

  async function readNotes(meetingId, pollToken = null) {
    const seq = ++state.readSeq;
    try {
      const payload = await apiJson(notesEndpoint(meetingId));
      if (
        seq !== state.readSeq
        || meetingId !== state.currentMeetingId
        || (pollToken !== null && pollToken !== state.pollSeq)
      ) return;
      const data = unwrappedNotesPayload(payload);
      installNotesPayload(meetingId, data);
    } catch (error) {
      if (
        seq !== state.readSeq
        || meetingId !== state.currentMeetingId
        || (pollToken !== null && pollToken !== state.pollSeq)
      ) return;
      const notes = meetingNotes(meetingId);
      notes.known = true;
      notes.readError = error && error.message ? error.message : t("Không thể đọc notes đã lưu.");
      if (!notes.sourceLockKnown && window.ASRMeetingHistory) {
        window.ASRMeetingHistory.setNotesSourceLock(meetingId, false, false);
      }
      render();
      if (pollToken !== null) scheduleTaskPoll(meetingId, 3000, pollToken);
    }
  }

  function stopTaskPolling() {
    if (state.pollTimer) window.clearTimeout(state.pollTimer);
    state.pollTimer = 0;
    state.pollSeq += 1;
  }

  function scheduleTaskPoll(meetingId, delay = (document.hidden ? 3000 : 1000), pollToken = state.pollSeq) {
    if (state.pollTimer) window.clearTimeout(state.pollTimer);
    state.pollTimer = window.setTimeout(() => {
      state.pollTimer = 0;
      if (
        pollToken !== state.pollSeq
        || meetingId !== state.currentMeetingId
        || !activeTask(meetingNotes(meetingId))
      ) return;
      void readNotes(meetingId, pollToken);
    }, delay);
  }

  function startTaskPolling(meetingId, task) {
    if (!task || !ACTIVE_TASK_STATES.has(task.status)) {
      if (state.currentMeetingId === meetingId) stopTaskPolling();
      return;
    }
    if (meetingId !== state.currentMeetingId) return;
    if (!state.pollTimer) scheduleTaskPoll(meetingId);
  }

  function requestStorageKey(meetingId) {
    return `asr-en-vi:notes-request:${meetingId}`;
  }

  function pendingRequestStorageKey(meetingId) {
    return `asr-en-vi:notes-request-v2:${meetingId}`;
  }

  function outputLanguageStorageKey(meetingId) {
    return `asr-en-vi:notes-output-language:${meetingId}`;
  }

  function browserStorages() {
    const storages = [];
    for (const name of ["localStorage", "sessionStorage"]) {
      try {
        if (window[name]) storages.push(window[name]);
      } catch {
        // The in-memory maps keep the current page session usable.
      }
    }
    return storages;
  }

  function readStoredValue(key) {
    for (const storage of browserStorages()) {
      try {
        const value = storage.getItem(key);
        if (value) return value;
      } catch {
        // Try the next browser storage area.
      }
    }
    return "";
  }

  function writeStoredValue(key, value) {
    let stored = false;
    for (const storage of browserStorages()) {
      try {
        storage.setItem(key, value);
        stored = true;
      } catch {
        // Keep trying, then rely on the in-memory value if both areas are blocked.
      }
    }
    return stored;
  }

  function removeStoredValue(key) {
    for (const storage of browserStorages()) {
      try {
        storage.removeItem(key);
      } catch {
        // The in-memory value is cleared even when browser storage is blocked.
      }
    }
  }

  function validRequestId(value) {
    return typeof value === "string" && /^[A-Za-z0-9._:-]{8,128}$/.test(value);
  }

  function normalizePendingRequest(value, { legacy = false } = {}) {
    if (typeof value !== "string" || !value) return null;
    let parsed = value;
    let isJson = false;
    try {
      parsed = JSON.parse(value);
      isJson = true;
    } catch {
      // Legacy storage contains a plain request ID.
    }
    if (isJson && parsed && typeof parsed === "object" && !Array.isArray(parsed)) {
      if (
        !validRequestId(parsed.request_id)
        || !["en", "vi"].includes(parsed.output_language)
      ) return null;
      if (parsed.provider !== undefined && !PROVIDER_IDS.includes(parsed.provider)) return null;
      // Stored requests from before provider choice were always ChatGPT requests.
      const result = {
        request_id: parsed.request_id,
        output_language: parsed.output_language,
        provider: parsed.provider || "chatgpt",
      };
      const hasExpectedFields = [
        "expected_generation_id",
        "expected_source_version",
        "expected_metadata_version",
      ].every((key) => Object.prototype.hasOwnProperty.call(parsed, key));
      const hasNoExpectedFields = [
        "expected_generation_id",
        "expected_source_version",
        "expected_metadata_version",
      ].every((key) => !Object.prototype.hasOwnProperty.call(parsed, key));
      if (hasExpectedFields) {
        if (
          typeof parsed.expected_generation_id !== "string"
          || !parsed.expected_generation_id
          || !Number.isInteger(parsed.expected_source_version)
          || parsed.expected_source_version < 1
          || !Number.isInteger(parsed.expected_metadata_version)
          || parsed.expected_metadata_version < 1
        ) return null;
        result.expected_generation_id = parsed.expected_generation_id;
        result.expected_source_version = parsed.expected_source_version;
        result.expected_metadata_version = parsed.expected_metadata_version;
        for (const key of ["expected_model", "expected_reasoning_effort"]) {
          if (typeof parsed[key] === "string" && parsed[key]) result[key] = parsed[key];
        }
      } else if (!hasNoExpectedFields && !legacy) {
        return null;
      }
      return result;
    }
    const requestId = isJson && typeof parsed === "string" ? parsed : value;
    if (!validRequestId(requestId)) return null;
    return { request_id: requestId, output_language: "en", provider: "chatgpt" };
  }

  function newRequestId() {
    if (window.crypto && typeof window.crypto.randomUUID === "function") return window.crypto.randomUUID();
    return `notes-${Date.now()}-${Math.random().toString(16).slice(2)}`;
  }

  function savePendingRequest(meetingId, pending) {
    state.pendingRequests.set(meetingId, pending);
    const encoded = JSON.stringify(pending);
    writeStoredValue(pendingRequestStorageKey(meetingId), encoded);
  }

  function getPendingRequest(meetingId, create = false) {
    if (state.pendingRequests.has(meetingId)) return state.pendingRequests.get(meetingId);
    const stored = normalizePendingRequest(
      readStoredValue(pendingRequestStorageKey(meetingId)),
    );
    if (stored) {
      state.pendingRequests.set(meetingId, stored);
      return stored;
    }
    const legacy = normalizePendingRequest(readStoredValue(requestStorageKey(meetingId)), {
      legacy: true,
    });
    if (legacy) {
      savePendingRequest(meetingId, legacy);
      return legacy;
    }
    if (!create) return null;
    const pending = {
      request_id: newRequestId(),
      output_language: getOutputLanguage(meetingId),
      provider: selectedProvider(null),
    };
    savePendingRequest(meetingId, pending);
    return pending;
  }

  function clearPendingRequest(meetingId) {
    state.pendingRequests.delete(meetingId);
    removeStoredValue(pendingRequestStorageKey(meetingId));
    removeStoredValue(requestStorageKey(meetingId));
  }

  function getOutputLanguage(meetingId) {
    if (state.outputLanguages.has(meetingId)) return state.outputLanguages.get(meetingId);
    const pending = getPendingRequest(meetingId, false);
    if (pending) {
      state.outputLanguages.set(meetingId, pending.output_language);
      return pending.output_language;
    }
    const stored = readStoredValue(outputLanguageStorageKey(meetingId));
    const language = ["en", "vi"].includes(stored) ? stored : "en";
    state.outputLanguages.set(meetingId, language);
    return language;
  }

  function setOutputLanguage(meetingId, language) {
    if (!meetingId || !["en", "vi"].includes(language)) return;
    if (getPendingRequest(meetingId, false)) return;
    state.outputLanguages.set(meetingId, language);
    writeStoredValue(outputLanguageStorageKey(meetingId), language);
  }

  function requestPayload(pending, meeting, generation) {
    if (isCompletePendingRequest(pending)) return pending;
    const complete = {
      request_id: pending.request_id,
      output_language: pending.output_language,
      provider: pending.provider,
      expected_generation_id: generation.id,
      expected_source_version: generation.source_version,
      expected_metadata_version: meeting.metadata_version,
    };
    // The confirmed choice is stored with the request so an HTTP retry resends the same body.
    const confirmed = savedModel(pending.provider);
    if (state.choice.loaded && confirmed) {
      complete.expected_model = confirmed;
      if (pending.provider === "chatgpt" || pending.provider === "antigravity") {
        complete.expected_reasoning_effort = effortFor(pending.provider, confirmed);
      }
    }
    savePendingRequest(meeting.id, complete);
    return complete;
  }

  function taskFromResponse(payload) {
    const task = payload && payload.task && typeof payload.task === "object" ? payload.task : payload;
    if (!task || typeof task.id !== "string" || typeof task.status !== "string") {
      throw new Error(t("Máy chủ không trả về task notes hợp lệ."));
    }
    if (task.kind !== "notes") throw new Error(t("Task được nhận không có kind notes theo API đã công bố."));
    return task;
  }

  async function startNotes() {
    const meeting = state.currentMeeting;
    const meetingId = state.currentMeetingId;
    const data = currentNotes();
    const generation = currentGeneration(meeting);
    if (!canStartNotes(meeting, data) || !generation || !meetingId) return;
    const body = requestPayload(getPendingRequest(meetingId, true), meeting, generation);
    // The run's progress, errors and result all live in the notes tab, wherever the run was started from.
    if (window.ASRMeetingHistory) window.ASRMeetingHistory.selectTab("notes");
    data.requestInFlight = true;
    data.runError = "";
    data.runErrorUncertain = false;
    data.actionMessage = "";
    render();
    try {
      const task = taskFromResponse(await apiJson(
        `/api/meetings/${encodeURIComponent(meetingId)}/notes-runs`,
        { method: "POST", body: JSON.stringify(body) },
      ));
      clearPendingRequest(meetingId);
      data.task = task;
      data.sourceLocked = ACTIVE_TASK_STATES.has(task.status);
      data.sourceLockKnown = true;
      if (window.ASRMeetingHistory) {
        window.ASRMeetingHistory.setNotesSourceLock(meetingId, data.sourceLocked, true);
      }
      data.actionMessage = t("Yêu cầu notes đã được worker xác nhận.");
      render();
      if (ACTIVE_TASK_STATES.has(task.status)) startTaskPolling(meetingId, task);
      else await readNotes(meetingId);
    } catch (error) {
      const definitive = error instanceof NotesApiError
        && Number.isInteger(error.status)
        && error.status >= 400
        && error.status < 500;
      if (definitive) clearPendingRequest(meetingId);
      const detail = error && error.payload && error.payload.detail;
      const mapped = definitive && detail && typeof detail === "object"
        ? failureMessage(detail.code, body.provider)
        : "";
      data.runError = mapped || (error && error.message ? error.message : t("Không thể xác nhận yêu cầu notes."));
      data.runErrorUncertain = !definitive;
      if (mapped) void loadProviderChoice(meetingId);
      data.actionMessage = "";
      if (definitive && error.status === 409) {
        if (window.ASRMeetingHistory) void window.ASRMeetingHistory.refreshMeeting(meetingId);
        void readNotes(meetingId);
      }
    } finally {
      data.requestInFlight = false;
      if (state.currentMeetingId === meetingId) render();
    }
  }

  async function cancelNotes() {
    const meetingId = state.currentMeetingId;
    const data = currentNotes();
    const task = data && data.task;
    if (!meetingId || !task || task.kind !== "notes" || !ACTIVE_TASK_STATES.has(task.status) || data.cancelInFlight) return;
    data.cancelInFlight = true;
    render();
    try {
      data.task = taskFromResponse(await apiJson(
        `/api/tasks/${encodeURIComponent(task.id)}/cancel`,
        { method: "POST", body: JSON.stringify({}) },
      ));
      data.runError = "";
      render();
      if (ACTIVE_TASK_STATES.has(data.task.status)) startTaskPolling(meetingId, data.task);
      else void readNotes(meetingId);
    } catch (error) {
      data.runError = error && error.message ? error.message : t("Không thể gửi yêu cầu hủy. Trạng thái worker chưa được xác nhận là đã đổi.");
      data.runErrorUncertain = false;
    } finally {
      data.cancelInFlight = false;
      if (state.currentMeetingId === meetingId) render();
    }
  }

  function replaceRevision(data, updated) {
    const normalized = normalizeRevision(updated, updated && updated.meeting_id);
    if (!normalized) return null;
    const index = data.revisions.findIndex((item) => item.id === normalized.id);
    if (index >= 0) data.revisions[index] = normalized;
    else data.revisions.unshift(normalized);
    return normalized;
  }

  function detailFromResponse(payload) {
    const note = payload && payload.note && typeof payload.note === "object" ? payload.note : payload;
    if (
      !note
      || typeof note.id !== "string"
      || typeof note.meeting_id !== "string"
      || typeof note.source_snapshot_id !== "string"
      || typeof note.markdown !== "string"
      || !Number.isInteger(note.edit_version)
      || !["current", "stale", "historical"].includes(note.source_state)
    ) throw new Error(t("Máy chủ không trả về revision notes hợp lệ."));
    return note;
  }

  function currentRevision(data, noteId) {
    return data && data.revisions.find((revision) => revision.id === noteId) || null;
  }

  async function saveSelectedNote() {
    const meetingId = state.currentMeetingId;
    const data = currentNotes();
    const revision = data && currentRevision(data, data.selectedNoteId);
    if (!meetingId || !revision) return;
    const draft = revisionDraft(revision);
    if (!draftIsDirty(draft) || data.saveInFlight.has(revision.id)) return;
    data.saveInFlight.add(revision.id);
    data.actionMessage = "";
    render();
    try {
      const saved = detailFromResponse(await apiJson(`/api/notes/${encodeURIComponent(revision.id)}`, {
        method: "PATCH",
        body: JSON.stringify({ expected_edit_version: draft.expectedEditVersion, markdown: draft.value }),
      }));
      if (saved.id !== revision.id || saved.meeting_id !== meetingId) throw new Error(t("Máy chủ lưu nhầm revision notes."));
      replaceRevision(data, saved);
      draft.value = saved.markdown;
      draft.baselineMarkdown = saved.markdown;
      draft.expectedEditVersion = saved.edit_version;
      draft.conflict = null;
      data.runError = "";
      data.actionMessage = t("Markdown đã được lưu.");
    } catch (error) {
      if (error instanceof NotesApiError && error.status === 409) {
        draft.conflict = { markdown: "", editVersion: draft.expectedEditVersion };
        try {
          const latest = detailFromResponse(await apiJson(`/api/notes/${encodeURIComponent(revision.id)}`));
          if (latest.id !== revision.id || latest.meeting_id !== meetingId) throw new Error(t("Revision notes mới nhất không khớp."));
          replaceRevision(data, latest);
          draft.conflict = { markdown: latest.markdown, editVersion: latest.edit_version };
          data.actionMessage = t("Bản đã lưu đổi ở nơi khác. Bản nháp được giữ nguyên.");
        } catch (readError) {
          data.actionMessage = t("{error} Bản nháp được giữ nguyên; chưa tải được phiên bản mới nhất.", { error: error.message });
        }
      } else {
        data.actionMessage = error && error.message ? error.message : t("Không thể lưu Markdown.");
      }
    } finally {
      data.saveInFlight.delete(revision.id);
      if (state.currentMeetingId === meetingId) render();
    }
  }

  async function keepDraftAndSaveLatest() {
    const data = currentNotes();
    const revision = data && currentRevision(data, data.selectedNoteId);
    const draft = revision && revisionDraft(revision);
    if (!revision || !draft || !draft.conflict) return;
    draft.expectedEditVersion = draft.conflict.editVersion;
    draft.baselineMarkdown = draft.conflict.markdown;
    draft.conflict = null;
    await saveSelectedNote();
  }

  function useLatestSavedNote() {
    const data = currentNotes();
    const revision = data && currentRevision(data, data.selectedNoteId);
    const draft = revision && revisionDraft(revision);
    if (!revision || !draft || !draft.conflict) return;
    draft.value = draft.conflict.markdown;
    draft.baselineMarkdown = draft.conflict.markdown;
    draft.expectedEditVersion = draft.conflict.editVersion;
    draft.conflict = null;
    data.actionMessage = t("Đã tải bản Markdown mới nhất đã lưu.");
    render();
  }

  async function authoritativeSelectedMarkdown(action) {
    const meetingId = state.currentMeetingId;
    const data = currentNotes();
    const revision = data && currentRevision(data, data.selectedNoteId);
    if (!meetingId || !revision) return null;
    const draft = revisionDraft(revision);
    if (draftIsDirty(draft) || draft.conflict || data.saveInFlight.has(revision.id)) {
      data.actionMessage = t("Lưu hoặc giải quyết bản nháp trước khi sao chép hay tải xuống.");
      render();
      return null;
    }
    const noteId = revision.id;
    const currentValue = draft.value;
    const expectedVersion = draft.expectedEditVersion;
    data.actionMessage = t("Đang đọc phiên bản đã lưu mới nhất…");
    render();
    try {
      const latest = detailFromResponse(await apiJson(`/api/notes/${encodeURIComponent(noteId)}`));
      if (latest.id !== noteId || latest.meeting_id !== meetingId) throw new Error(t("Revision notes mới nhất không khớp cuộc họp."));
      replaceRevision(data, latest);
      if (draft.value !== currentValue || draft.expectedEditVersion !== expectedVersion) {
        draft.conflict = { markdown: latest.markdown, editVersion: latest.edit_version };
        data.actionMessage = t("Bản nháp thay đổi trong lúc đồng bộ. Bản nháp được giữ; chưa sao chép hoặc tải xuống.");
        render();
        return null;
      }
      if (latest.edit_version !== expectedVersion || latest.markdown !== currentValue) {
        draft.value = latest.markdown;
        draft.baselineMarkdown = latest.markdown;
        draft.expectedEditVersion = latest.edit_version;
        draft.conflict = null;
      }
      if (state.currentMeetingId !== meetingId || currentNotes().selectedNoteId !== noteId) {
        data.actionMessage = t("Phiên bản notes đã đổi trong lúc đồng bộ. Hãy chọn lại để tiếp tục.");
        render();
        return null;
      }
      data.actionMessage = "";
      render();
      return { markdown: latest.markdown, noteId, editVersion: latest.edit_version, action };
    } catch (error) {
      data.actionMessage = error && error.message ? error.message : t("Không thể đọc bản notes đã lưu mới nhất.");
      render();
      return null;
    }
  }

  async function copySelectedNote() {
    const saved = await authoritativeSelectedMarkdown("copy");
    if (!saved) return;
    const data = meetingNotes(state.currentMeetingId);
    try {
      await navigator.clipboard.writeText(saved.markdown);
      data.actionMessage = t("Đã sao chép bản đã lưu · edit {version}.", { version: saved.editVersion });
    } catch {
      data.actionMessage = t("Không thể truy cập clipboard. Trình duyệt chưa sao chép nội dung.");
    }
    render();
  }

  function safeFilename(value) {
    const title = typeof value === "string" ? value : "meeting-notes";
    const cleaned = title
      .normalize("NFKC")
      .replace(/[\\/:*?"<>|\u0000-\u001f]/g, "-")
      .replace(/\s+/g, " ")
      .trim()
      .slice(0, 100);
    return `${cleaned || "meeting-notes"}.md`;
  }

  async function exportSelectedNote() {
    const saved = await authoritativeSelectedMarkdown("export");
    if (!saved) return;
    const data = meetingNotes(state.currentMeetingId);
    const blob = new Blob([saved.markdown], { type: "text/markdown;charset=utf-8" });
    const objectUrl = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = objectUrl;
    link.download = safeFilename(state.currentMeeting && state.currentMeeting.title);
    link.hidden = true;
    document.body.append(link);
    link.click();
    link.remove();
    window.setTimeout(() => URL.revokeObjectURL(objectUrl), 0);
    data.actionMessage = t("Đã tải bản đã lưu · edit {version}.", { version: saved.editVersion });
    render();
  }

  function validateSnapshot(snapshot, meetingId, snapshotId) {
    return Boolean(
      snapshot
      && snapshot.id === snapshotId
      && snapshot.meeting_id === meetingId
      && Array.isArray(snapshot.segments),
    );
  }

  function speakerForSnapshot(snapshot, segment) {
    if (typeof segment.speaker_name === "string" && segment.speaker_name) return segment.speaker_name;
    const speakerId = segment.speaker_id;
    const speaker = Array.isArray(snapshot.speakers)
      ? snapshot.speakers.find((item) => item.speaker_id === speakerId)
      : null;
    return speaker && speaker.display_name
      ? speaker.display_name
      : speakerId || t("Chưa xác định");
  }

  function dateLabel(date) {
    return date || t("Chưa đặt ngày");
  }

  // How the current meeting departs from the saved source, in words; "" while they agree or before the meeting loads.
  function sourceDifference(source) {
    const meeting = state.currentMeeting;
    if (!meeting) return "";
    const notes = [];
    const generation = currentGeneration(meeting);
    if (generation && generation.id !== source.generationId) {
      notes.push(t("Transcript hiện tại là một lần chép lời khác với bản chụp này, nên đoạn được đánh dấu chỉ khớp theo mốc thời gian."));
    } else if (generation) {
      const current = generation.segments.find((item) => item.id === source.segmentId);
      if (current && current.text !== source.text) notes.push(t("Văn bản của đoạn này đã được sửa trong transcript hiện tại."));
      if (current && speakerForSnapshot(generation, current) !== source.speaker) {
        notes.push(t("Người nói của đoạn này đã đổi trong transcript hiện tại."));
      }
    }
    if ((meeting.meeting_date || null) !== source.meetingDate) {
      notes.push(t("Ngày họp hiện tại ({current}) khác ngày họp trong bản chụp ({snapshot}).", {
        current: dateLabel(meeting.meeting_date || null),
        snapshot: dateLabel(source.meetingDate),
      }));
    }
    return notes.join(" ");
  }

  function renderSourceDifference() {
    const note = state.currentSource ? sourceDifference(state.currentSource) : "";
    const element = $("#notes-source-difference");
    element.textContent = note;
    element.hidden = !note;
  }

  function updateSourceView(snapshot, segment, meetingId) {
    const source = {
      snapshotId: snapshot.id,
      meetingId,
      generationId: snapshot.generation_id,
      segmentId: segment.id,
      startSeconds: Number(segment.start_seconds),
      text: segment.text,
      speaker: speakerForSnapshot(snapshot, segment),
      meetingDate: typeof snapshot.meeting_date === "string" && snapshot.meeting_date ? snapshot.meeting_date : null,
    };
    state.currentSource = source;
    const root = $("#notes-source-view");
    root.hidden = false;
    $("#notes-source-context").textContent = t("Đang xem bản chụp transcript bất biến. Nội dung này không đổi khi transcript hiện tại được sửa.");
    const time = $("#notes-source-time");
    time.textContent = formatSeconds(source.startSeconds);
    $("#notes-source-speaker").textContent = source.speaker;
    $("#notes-source-date").textContent = dateLabel(source.meetingDate);
    $("#notes-source-text").textContent = source.text;
    renderSourceDifference();
    $("#notes-source-status").textContent = "";
    $("#notes-source-seek").disabled = !Number.isFinite(source.startSeconds) || source.startSeconds < 0;
    $("#notes-source-heading").focus({ preventScroll: true });
    return source;
  }

  // One flow for a chip click and for a pasted or restored link: the Transcript tab, the saved source under the
  // player, the recording sought and played, and the transcript row it names marked and in view. A click first
  // makes the one history entry that Back returns from; a link already is one.
  async function showSourceReference(reference, { fromClick = false } = {}) {
    if (!reference || reference.meetingId !== state.currentMeetingId) return;
    const meetings = window.ASRMeetingHistory;
    if (fromClick && meetings) meetings.showNotesSourceTab(reference);
    const key = `${reference.meetingId}\u0000${reference.snapshotId}\u0000${reference.segmentId}`;
    const sequence = ++state.sourceSeq;
    state.sourceKey = key;
    $("#notes-source-status").textContent = t("Đang tải bản chụp transcript đã lưu…");
    try {
      let snapshot = state.sourceCache.get(reference.snapshotId);
      if (!snapshot) {
        snapshot = await apiJson(`/api/notes-sources/${encodeURIComponent(reference.snapshotId)}`);
        if (!validateSnapshot(snapshot, reference.meetingId, reference.snapshotId)) {
          throw new Error(t("Bản chụp nguồn không khớp cuộc họp hoặc mã nguồn đã chọn."));
        }
        state.sourceCache.set(reference.snapshotId, snapshot);
      }
      if (sequence !== state.sourceSeq || state.currentMeetingId !== reference.meetingId) return;
      if (!validateSnapshot(snapshot, reference.meetingId, reference.snapshotId)) {
        throw new Error(t("Bản chụp nguồn không khớp cuộc họp hoặc mã nguồn đã chọn."));
      }
      const segment = snapshot.segments.find((item) => item.id === reference.segmentId);
      if (
        !segment
        || typeof segment.text !== "string"
        || !Number.isFinite(Number(segment.start_seconds))
        || Number(segment.start_seconds) < 0
      ) throw new Error(t("Không tìm thấy đoạn trong bản chụp transcript đã lưu."));
      const source = updateSourceView(snapshot, segment, reference.meetingId);
      $("#notes-source-status").textContent = t("Đang đưa trình phát bản ghi tới mốc nguồn…");
      let sought = false;
      let playing = false;
      if (meetings) {
        meetings.markNotesSource(source.segmentId, source.startSeconds);
        sought = await meetings.seekNotesSource(source);
        if (sequence !== state.sourceSeq) return;
        playing = sought && await meetings.playRecording();
        if (sequence !== state.sourceSeq) return;
      }
      $("#notes-source-status").textContent = !sought
        ? t("Đã mở nguồn bất biến nhưng chưa thể tua bản ghi. Dùng nút tua để thử lại.")
        : playing
          ? t("Đã tua bản ghi cuộc họp tới {time} và đang phát.", { time: formatSeconds(source.startSeconds) })
          : t("Đã tua bản ghi cuộc họp tới {time}. Bấm phát trên trình phát để nghe.", { time: formatSeconds(source.startSeconds) });
    } catch (error) {
      if (sequence !== state.sourceSeq) return;
      state.currentSource = null;
      $("#notes-source-view").hidden = false;
      $("#notes-source-context").textContent = "";
      $("#notes-source-time").textContent = "";
      $("#notes-source-speaker").textContent = "";
      $("#notes-source-date").textContent = "";
      $("#notes-source-text").textContent = "";
      renderSourceDifference();
      $("#notes-source-status").textContent = error && error.message
        ? error.message
        : t("Không thể mở nguồn transcript đã lưu.");
      $("#notes-source-heading").focus({ preventScroll: true });
    }
  }

  function sourceFromLocation() {
    const url = new URL(window.location.href);
    const path = url.pathname.match(/^\/meetings\/([^/]+)\/?$/);
    if (!path) return null;
    const params = [...url.searchParams.entries()];
    if (!params.some(([key]) => key === "notes_source" || key === "segment")) return null;
    let meetingId;
    try {
      meetingId = decodeURIComponent(path[1]);
    } catch {
      return null;
    }
    if (
      !meetingId
      || meetingId.includes("/")
      || params.length !== 2
      || params[0][0] !== "notes_source"
      || params[1][0] !== "segment"
      || !params[0][1]
      || !params[1][1]
    ) return null;
    // The hash names a tab, not a source: #transcript (what a chip links to), #notes or none all open it.
    return {
      meetingId,
      snapshotId: params[0][1],
      segmentId: params[1][1],
      href: sourceHref(meetingId, params[0][1], params[1][1]),
    };
  }

  function handleLocation() {
    const reference = sourceFromLocation();
    if (!reference || reference.meetingId !== state.currentMeetingId || state.view !== "meeting") {
      if (!reference && state.sourceKey) closeSourceView(false);
      return;
    }
    const key = `${reference.meetingId}\u0000${reference.snapshotId}\u0000${reference.segmentId}`;
    if (state.sourceKey === key && (state.currentSource || $("#notes-source-status").textContent)) return;
    void showSourceReference(reference);
  }

  function closeSourceView(clearLocation = true) {
    state.sourceSeq += 1;
    state.sourceKey = "";
    state.currentSource = null;
    $("#notes-source-view").hidden = true;
    if (window.ASRMeetingHistory) window.ASRMeetingHistory.markNotesSource(null);
    if (!clearLocation) return;
    const reference = sourceFromLocation();
    if (reference && window.location.search) {
      window.history.replaceState(window.history.state, "", `${window.location.pathname}${window.location.hash}`);
    }
  }

  async function seekCurrentSource() {
    const source = state.currentSource;
    if (!source || !window.ASRMeetingHistory) return;
    const sought = await window.ASRMeetingHistory.seekNotesSource(source);
    $("#notes-source-status").textContent = sought
      ? t("Đã tua bản ghi cuộc họp tới {time}.", { time: formatSeconds(source.startSeconds) })
      : t("Chưa thể tua bản ghi tới mốc này. Hãy kiểm tra audio đã tải xong.");
    if (sought) window.ASRMeetingHistory.markNotesSource(source.segmentId, source.startSeconds);
  }

  function handleMeetingContext(event) {
    const detail = event.detail || {};
    const previousMeeting = state.currentMeeting;
    state.view = detail.view || "";
    state.currentMeeting = detail.view === "meeting" ? detail.meeting : null;
    state.transcriptionRequestInFlight = Boolean(detail.transcriptionRequestInFlight);
    if (state.currentSource) renderSourceDifference();
    const meetingId = state.currentMeeting && state.currentMeeting.id;
    if (!meetingId) {
      state.currentMeetingId = null;
      stopTaskPolling();
      return;
    }
    const changed = state.currentMeetingId !== meetingId;
    state.currentMeetingId = meetingId;
    const data = meetingNotes(meetingId);
    if (changed) {
      stopTaskPolling();
      state.choice.open = false;
      data.sourceLockKnown = false;
      data.known = false;
    }
    if (
      (changed || previousMeeting !== state.currentMeeting || !data.sourceLockKnown)
      && typeof state.currentMeeting.notes_source_locked === "boolean"
    ) {
      data.sourceLocked = state.currentMeeting.notes_source_locked;
      data.sourceLockKnown = true;
    }
    if (window.ASRMeetingHistory) {
      window.ASRMeetingHistory.setNotesSourceLock(meetingId, data.sourceLocked, data.sourceLockKnown);
    }
    render();
    void readNotes(meetingId);
    if (changed || !state.choice.loaded) void loadProviderChoice(meetingId);
    handleLocation();
  }

  $("#notes-start").addEventListener("click", (event) => {
    // The header launcher already opens Connections at its own provider's section.
    if (event.currentTarget.dataset.action === "connect") $(`#launcher-${selectedProvider(null)}`).click();
    else void startNotes();
  });
  $("#notes-change").addEventListener("click", () => {
    state.choice.open = !state.choice.open;
    render();
  });
  $("#notes-name-speakers").addEventListener("click", (event) => {
    if (event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
    event.preventDefault();
    if (window.ASRMeetingHistory) window.ASRMeetingHistory.focusSpeakerCatalog();
  });
  $("#notes-empty-open-transcript").addEventListener("click", () => {
    if (window.ASRMeetingHistory) window.ASRMeetingHistory.selectTab("transcript", { focus: true });
  });
  $("#notes-choice-reload").addEventListener("click", () => {
    if (state.currentMeetingId) void loadProviderChoice(state.currentMeetingId);
  });
  // Connections saved a model or changed a provider status: reload before a new run can start.
  window.addEventListener("asr:provider-choice-changed", () => {
    if (state.currentMeetingId) void loadProviderChoice(state.currentMeetingId);
  });
  $("#notes-output-language").addEventListener("change", (event) => {
    const meetingId = state.currentMeetingId;
    if (!meetingId) return;
    setOutputLanguage(meetingId, event.currentTarget.value);
    render();
  });
  $("#notes-provider").addEventListener("change", (event) => {
    const provider = event.currentTarget.value;
    if (!PROVIDER_IDS.includes(provider)) return;
    const model = savedModel(provider);
    state.choice.message = "";
    if (model) {
      void savePreference(provider, model);
    } else {
      // No saved model for this provider: the operator must pick one before anything is saved.
      state.choice.localProvider = provider;
      render();
    }
  });
  $("#notes-model").addEventListener("change", (event) => {
    const model = event.currentTarget.value;
    if (!model) return;
    void savePreference(selectedProvider(null), model);
  });
  $("#notes-cancel").addEventListener("click", () => void cancelNotes());
  $("#notes-revision-selector").addEventListener("change", (event) => {
    const data = currentNotes();
    if (!data) return;
    state.selectionSeq += 1;
    data.selectedNoteId = event.currentTarget.value || null;
    data.actionMessage = "";
    renderSelectedRevision(data);
  });
  $("#notes-markdown").addEventListener("input", (event) => {
    const data = currentNotes();
    const revision = data && currentRevision(data, data.selectedNoteId);
    if (!revision) return;
    const draft = revisionDraft(revision);
    draft.value = event.currentTarget.value;
    draft.conflict = draft.expectedEditVersion === revision.edit_version
      ? null
      : { markdown: revision.markdown, editVersion: revision.edit_version };
    data.actionMessage = "";
    renderMarkdown(draft.value, revision);
    renderDraftState(data, revision, draft);
  });
  // Same path as the save button. The textarea is disabled while the request runs, which drops its focus.
  $("#notes-markdown").addEventListener("keydown", async (event) => {
    if (event.key !== "Enter" || !(event.ctrlKey || event.metaKey)) return;
    event.preventDefault();
    const textarea = event.currentTarget;
    await saveSelectedNote();
    if (document.activeElement === document.body && !textarea.hidden && !textarea.disabled) {
      textarea.focus({ preventScroll: true });
    }
  });
  $("#notes-mode-view").addEventListener("click", () => setViewMode("view"));
  $("#notes-mode-write").addEventListener("click", () => setViewMode("write"));
  $("#notes-save").addEventListener("click", () => void saveSelectedNote());
  $("#notes-keep-draft").addEventListener("click", () => void keepDraftAndSaveLatest());
  $("#notes-use-latest").addEventListener("click", useLatestSavedNote);
  $("#notes-copy").addEventListener("click", () => void copySelectedNote());
  $("#notes-export").addEventListener("click", () => void exportSelectedNote());
  $("#notes-preview").addEventListener("click", (event) => {
    const link = event.target.closest("a[data-notes-source-link]");
    if (
      !link
      || event.defaultPrevented
      || event.button !== 0
      || event.metaKey
      || event.ctrlKey
      || event.shiftKey
      || event.altKey
    ) return;
    const reference = sourceReference(
      link.getAttribute("href"),
      link.dataset.meetingId,
      link.dataset.snapshotId,
    );
    if (!reference || reference.segmentId !== link.dataset.segmentId) return;
    event.preventDefault();
    void showSourceReference(reference, { fromClick: true });
  });
  $("#notes-source-close").addEventListener("click", () => closeSourceView());
  $("#notes-source-seek").addEventListener("click", () => void seekCurrentSource());

  document.addEventListener("asr:meeting-context", handleMeetingContext);
  // A deferred asset can load after history has already published its first context.
  if (window.ASRMeetingHistory && typeof window.ASRMeetingHistory.currentContext === "function") {
    handleMeetingContext({ detail: window.ASRMeetingHistory.currentContext() });
  }
  window.addEventListener("popstate", handleLocation);
  // A reload or close drops every in-memory draft, so warn while a notes or transcript draft is unsaved.
  window.addEventListener("beforeunload", (event) => {
    const meetings = window.ASRMeetingHistory;
    const unsaved = [...state.drafts.values()].some(draftIsDirty)
      || Boolean(meetings && meetings.hasUnsavedTranscriptDrafts());
    if (!unsaved) return;
    event.preventDefault();
    event.returnValue = "";
  });
  document.addEventListener("visibilitychange", () => {
    const data = currentNotes();
    if (state.currentMeetingId && activeTask(data)) {
      scheduleTaskPoll(state.currentMeetingId, document.hidden ? 3000 : 1000);
    }
  });
})();
