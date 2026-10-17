"use strict";

// Meeting history: sidebar recent/search, synced month calendars, meeting
// navigation and metadata editing. Depends on shell.js globals (requestJson,
// ApiError, formatMeetingDate, sameOriginAudioSource, meetingIdFromPath).
(() => {
  const $ = (selector) => document.querySelector(selector);
  const MIN_YEAR = 1000;
  const MAX_YEAR = 9999;
  const WEEKDAYS = ["T2", "T3", "T4", "T5", "T6", "T7", "CN"];
  const LANGUAGES = { en: "English", vi: "Tiếng Việt" };
  const VIEWS = {
    home: "#home-view",
    loading: "#meeting-loading",
    error: "#meeting-error",
    meeting: "#meeting-view",
    calendar: "#calendar-view",
  };

  // ---- date-only helpers: pure year/month/day arithmetic, never local time ----
  const pad = (value, width = 2) => String(value).padStart(width, "0");
  const dateKey = (year, month, day) => `${pad(year, 4)}-${pad(month + 1)}-${pad(day)}`;
  function utcDate(year, month, day) {
    const value = new Date(0);
    value.setUTCFullYear(year, month, day);
    return value;
  }
  const keyOf = (value) => dateKey(value.getUTCFullYear(), value.getUTCMonth(), value.getUTCDate());
  function parseKey(key) {
    const [year, month, day] = key.split("-").map(Number);
    return { year, month: month - 1, day };
  }
  function addDays(key, count) {
    const { year, month, day } = parseKey(key);
    return keyOf(utcDate(year, month, day + count));
  }
  function todayKey() {
    const now = new Date();
    return dateKey(now.getFullYear(), now.getMonth(), now.getDate());
  }
  function displayDate(key) {
    const { year, month, day } = parseKey(key);
    return `${pad(day)}/${pad(month + 1)}/${pad(year, 4)}`;
  }
  // Six Monday-first weeks covering the month, including out-of-month days.
  function monthGrid(year, month) {
    const lead = (utcDate(year, month, 1).getUTCDay() + 6) % 7;
    return Array.from({ length: 42 }, (_, index) => keyOf(utcDate(year, month, 1 - lead + index)));
  }

  // Recording length only ("1 giờ 24 phút", "12 phút", "45 giây"); never a clock time.
  function formatRecordingDuration(seconds) {
    const whole = Math.round(seconds); // round first so 59.5 s reads "1 phút", never "60 giây"
    if (whole < 60) return `${Math.max(1, whole)} giây`;
    const minutes = Math.round(whole / 60);
    if (minutes < 60) return `${minutes} phút`;
    return `${Math.floor(minutes / 60)} giờ ${pad(minutes % 60)} phút`;
  }

  const today = parseKey(todayKey());
  const state = {
    meetings: [],
    recent: [],
    total: 0,
    query: "",
    results: [],
    searchFailed: false,
    searchSeq: 0,
    loadSeq: 0, // bumps on every load/leave so a stale load never repaints
    saveSeq: 0,
    calendar: { year: today.year, month: today.month, selected: todayKey() },
    meeting: null,
    draft: null,
    taskPollTimer: 0,
    taskPollId: null,
    taskRequestInFlight: false,
    pendingTaskRequestId: null,
    taskRequestError: null,
  };

  // ---- views ----
  function showView(name) {
    for (const [key, selector] of Object.entries(VIEWS)) $(selector).hidden = key !== name;
    state.view = name;
  }

  function setHeading(eyebrow, title, documentTitle) {
    $("#page-eyebrow").textContent = eyebrow;
    $("#page-title").textContent = title;
    document.title = documentTitle;
  }

  function showHome() {
    state.loadSeq += 1; // a meeting load still in flight must not repaint over home
    stopTaskPolling();
    showView("home");
    setHeading("LOCAL WORKSPACE", "Cuộc họp", "Workspace · ASR EN VI");
    $("#workspace-link").setAttribute("aria-current", "page");
    renderSidebar();
  }

  function showMeetingError(message) {
    $("#meeting-error-copy").textContent = message;
    showView("error");
  }

  // ---- history data ----
  async function refreshHistory() {
    try {
      const data = await requestJson("/api/meetings");
      state.meetings = data.meetings;
      state.recent = data.recent;
      state.total = data.total;
    } catch {
      // Keep the last known list; a failed refresh must not blank the sidebar.
    }
    if (state.query) await runSearch();
    renderSidebar();
    renderCalendars();
  }

  async function runSearch() {
    const sequence = ++state.searchSeq;
    const query = state.query;
    try {
      const data = await requestJson(`/api/meetings?q=${encodeURIComponent(query)}`);
      if (sequence !== state.searchSeq) return;
      state.results = data.meetings;
      state.searchFailed = false;
    } catch {
      if (sequence !== state.searchSeq) return;
      state.results = [];
      state.searchFailed = true;
    }
  }

  // ---- sidebar ----
  function renderSidebar() {
    const searching = state.query.trim() !== "";
    const items = searching ? state.results : state.recent;
    $("#recent-heading").textContent = searching ? "Kết quả" : "Gần đây";
    const noMeetings = !searching && state.total === 0;
    const noDated = !searching && state.total > 0 && state.recent.length === 0;
    const empty = $("#sidebar-empty");
    empty.hidden = !(noMeetings || noDated);
    empty.textContent = noMeetings
      ? "Cuộc họp đã lưu sẽ xuất hiện tại đây."
      : "Chưa có cuộc họp nào có ngày. Mở nhóm Chưa đặt ngày trong lịch.";
    $("#search-error").hidden = !(searching && state.searchFailed);
    const noResults = $("#search-empty");
    noResults.hidden = !(searching && !state.searchFailed && items.length === 0);
    noResults.textContent = `Không tìm thấy cuộc họp nào khớp “${state.query.trim()}”.`;
    $("#workspace-empty").hidden = state.total > 0;

    const openId = state.meeting && state.view === "meeting" ? state.meeting.id : null;
    const list = $("#recent-list");
    list.replaceChildren(
      ...items.map((meeting) => {
        const link = meetingLink(meeting, "recent-link");
        if (meeting.id === openId) link.setAttribute("aria-current", "page");
        const item = document.createElement("li");
        item.append(link);
        return item;
      }),
    );
  }

  function meetingLink(meeting, className) {
    const link = document.createElement("a");
    link.className = className;
    link.href = `/meetings/${encodeURIComponent(meeting.id)}`;
    link.dataset.meetingLink = meeting.id;
    const title = document.createElement("span");
    title.className = "link-title";
    title.textContent = meeting.title;
    const date = document.createElement("span");
    date.className = "link-date";
    const parts = [meeting.meeting_date ? displayDate(meeting.meeting_date) : "Chưa đặt ngày"];
    if (meeting.duration_seconds > 0) parts.push(formatRecordingDuration(meeting.duration_seconds));
    date.textContent = parts.join(" · ");
    link.append(title, date);
    return link;
  }

  // ---- calendars (small + large share one state) ----
  const CALENDAR_TEMPLATE = `
    <div class="cal-nav">
      <button type="button" class="cal-step" data-step="-1" aria-label="Tháng trước">‹</button>
      <strong class="cal-title" aria-live="polite"></strong>
      <button type="button" class="cal-step" data-step="1" aria-label="Tháng sau">›</button>
    </div>
    <div class="cal-pick">
      <select class="cal-month" aria-label="Tháng"></select>
      <input class="cal-year" type="number" inputmode="numeric" aria-label="Năm" min="${MIN_YEAR}" max="${MAX_YEAR}" />
      <button type="button" class="cal-today">Hôm nay</button>
    </div>
    <p class="cal-summary"></p>
    <div class="cal-weekdays" aria-hidden="true">${WEEKDAYS.map((name) => `<span>${name}</span>`).join("")}</div>
    <div class="cal-days"></div>
    <button type="button" class="cal-undated"><span>Chưa đặt ngày</span><span class="cal-undated-count"></span></button>`;

  function buildCalendar(root) {
    root.innerHTML = CALENDAR_TEMPLATE;
    const select = root.querySelector(".cal-month");
    for (let month = 0; month < 12; month += 1) select.add(new Option(`Tháng ${month + 1}`, String(month)));
  }

  function meetingsByDate() {
    const map = new Map();
    for (const meeting of state.meetings) {
      if (!meeting.meeting_date) continue;
      if (!map.has(meeting.meeting_date)) map.set(meeting.meeting_date, []);
      map.get(meeting.meeting_date).push(meeting);
    }
    return map;
  }

  function renderCalendar(root, large, byDate) {
    const { year, month, selected } = state.calendar;
    const todayValue = todayKey();
    const activeElement = document.activeElement;
    const focusedDate =
      activeElement && root.contains(activeElement) && activeElement.classList.contains("cal-day")
        ? activeElement.dataset.date
        : null;
    root.querySelector(".cal-title").textContent = `Tháng ${month + 1} · ${year}`;
    root.querySelector(".cal-month").value = String(month);
    // A background refresh must not overwrite what the user is typing in the year box.
    const yearInput = root.querySelector(".cal-year");
    if (document.activeElement !== yearInput) yearInput.value = String(year);
    const monthKey = `${pad(year, 4)}-${pad(month + 1)}-`;
    const monthCount = state.meetings.filter(
      (meeting) => meeting.meeting_date && meeting.meeting_date.startsWith(monthKey),
    ).length;
    root.querySelector(".cal-summary").textContent = monthCount
      ? `${monthCount} cuộc họp trong tháng`
      : "Không có cuộc họp trong tháng này.";

    const cells = monthGrid(year, month).map((key) => {
      const meetings = byDate.get(key) || [];
      const inMonth = key.startsWith(monthKey);
      const cell = document.createElement("div");
      cell.className = "cal-cell";
      const day = document.createElement("button");
      day.type = "button";
      day.className = "cal-day";
      day.dataset.date = key;
      day.classList.toggle("is-outside", !inMonth);
      day.classList.toggle("is-today", key === todayValue);
      day.classList.toggle("is-selected", key === selected);
      day.classList.toggle("has-meetings", meetings.length > 0);
      day.setAttribute("aria-pressed", String(key === selected));
      day.setAttribute(
        "aria-label",
        `${displayDate(key)}, ${meetings.length ? `${meetings.length} cuộc họp` : "không có cuộc họp"}`,
      );
      day.tabIndex = key === selected ? 0 : -1;
      const number = document.createElement("span");
      number.className = "cal-number";
      number.textContent = String(parseKey(key).day);
      day.append(number);
      if (meetings.length) {
        const count = document.createElement("span");
        count.className = "cal-count";
        count.textContent = String(meetings.length);
        day.append(count);
      }
      cell.append(day);
      if (large) {
        for (const meeting of meetings.slice(0, 2)) {
          const chip = document.createElement("a");
          chip.className = "cal-chip";
          chip.href = `/meetings/${encodeURIComponent(meeting.id)}`;
          chip.dataset.meetingLink = meeting.id;
          chip.textContent = meeting.title;
          cell.append(chip);
        }
        if (meetings.length > 2) {
          const more = document.createElement("button");
          more.type = "button";
          more.className = "cal-more";
          more.dataset.date = key;
          more.textContent = `+${meetings.length - 2} khác`;
          cell.append(more);
        }
      }
      return cell;
    });
    root.querySelector(".cal-days").replaceChildren(...cells);
    // Roving tabindex: keep one stop in the grid even when the selection is off-screen.
    const days = root.querySelectorAll(".cal-day");
    if (!root.querySelector('.cal-day[tabindex="0"]')) {
      const fallback = root.querySelector(`.cal-day[data-date="${monthKey}01"]`) || days[0];
      fallback.tabIndex = 0;
    }
    if (focusedDate) root.querySelector(`.cal-day[data-date="${focusedDate}"]`)?.focus();
    const undated = state.meetings.filter((meeting) => !meeting.meeting_date).length;
    root.querySelector(".cal-undated-count").textContent = String(undated);
    root.querySelector(".cal-undated").classList.toggle("is-selected", selected === "undated");
    root.querySelector(".cal-undated").setAttribute("aria-pressed", String(selected === "undated"));
  }

  function renderDayPanel(byDate) {
    const { selected } = state.calendar;
    const undated = selected === "undated";
    const meetings = undated
      ? state.meetings.filter((meeting) => !meeting.meeting_date)
      : byDate.get(selected) || [];
    $("#day-panel-kicker").textContent = undated ? "NHÓM" : "NGÀY ĐANG CHỌN";
    $("#day-panel-title").textContent = undated ? "Chưa đặt ngày" : displayDate(selected);
    $("#day-panel-count").textContent = String(meetings.length);
    const empty = $("#day-panel-empty");
    empty.hidden = meetings.length > 0;
    empty.textContent = undated
      ? "Mọi cuộc họp đều đã có ngày."
      : "Không có cuộc họp trong ngày này.";
    $("#day-panel-list").replaceChildren(
      ...meetings.map((meeting) => {
        const item = document.createElement("li");
        item.append(meetingLink(meeting, "day-meeting"));
        return item;
      }),
    );
  }

  function renderCalendars() {
    const byDate = meetingsByDate();
    renderCalendar($("#mini-calendar"), false, byDate);
    renderCalendar($("#large-calendar"), true, byDate);
    renderDayPanel(byDate);
  }

  function shiftMonth(count) {
    const index = state.calendar.year * 12 + state.calendar.month + count;
    const year = Math.floor(index / 12);
    if (year < MIN_YEAR || year > MAX_YEAR) return;
    state.calendar.year = year;
    state.calendar.month = index - year * 12;
  }

  function selectDate(key, root, { focus = false } = {}) {
    const { year, month } = parseKey(key);
    state.calendar = { year, month, selected: key };
    renderCalendars();
    if (focus) root.querySelector(`.cal-day[data-date="${key}"]`).focus();
  }

  function onCalendarClick(event) {
    const root = event.currentTarget;
    const target = event.target.closest("button");
    if (!target || !root.contains(target)) return;
    const opensCalendar = root.dataset.calendar === "mini";
    if (target.dataset.step) {
      shiftMonth(Number(target.dataset.step));
      renderCalendars();
    } else if (target.classList.contains("cal-today")) {
      selectDate(todayKey(), root);
    } else if (target.classList.contains("cal-undated")) {
      state.calendar.selected = "undated";
      renderCalendars();
      if (opensCalendar) openCalendar();
    } else if (target.dataset.date) {
      selectDate(target.dataset.date, root, { focus: true });
      if (opensCalendar) openCalendar();
    }
  }

  // The year box commits as soon as it holds a complete 4-digit year in range (typing,
  // paste, spinner), so Enter/blur never depend on the browser firing `change`.
  // Partial or out-of-range text is left alone while editing and reverted on Enter/blur.
  function validYear(text) {
    const year = /^\d{4}$/.test(text) ? Number(text) : NaN;
    return year >= MIN_YEAR && year <= MAX_YEAR ? year : null;
  }

  function onCalendarInput(event) {
    if (!event.target.classList.contains("cal-year")) return;
    const year = validYear(event.target.value);
    if (year === null || year === state.calendar.year) return;
    state.calendar.year = year;
    renderCalendars();
  }

  // Enter/blur: keep a valid year, otherwise put the real year back into the box. The grid
  // is only rebuilt when the year actually changes, so a blur caused by clicking a day
  // never replaces the button under the pointer.
  function commitYear(input) {
    const year = validYear(input.value);
    if (year !== null && year !== state.calendar.year) {
      state.calendar.year = year;
      renderCalendars();
    }
    input.value = String(state.calendar.year);
  }

  function onCalendarChange(event) {
    if (event.target.classList.contains("cal-month")) {
      state.calendar.month = Number(event.target.value);
      renderCalendars();
    }
  }

  function onCalendarFocusout(event) {
    if (event.target.classList.contains("cal-year")) commitYear(event.target);
  }

  const ARROW_STEPS = { ArrowLeft: -1, ArrowRight: 1, ArrowUp: -7, ArrowDown: 7 };
  function onCalendarKeydown(event) {
    if (event.key === "Enter" && event.target.classList.contains("cal-year")) {
      event.preventDefault();
      commitYear(event.target);
      return;
    }
    const day = event.target.closest(".cal-day");
    if (!day || !(event.key in ARROW_STEPS)) return;
    event.preventDefault();
    const key = addDays(day.dataset.date, ARROW_STEPS[event.key]);
    const { year } = parseKey(key);
    if (year < MIN_YEAR || year > MAX_YEAR) return;
    selectDate(key, event.currentTarget, { focus: true });
  }

  // ---- meeting navigation ----
  function openCalendar() {
    if (state.view === "calendar") return;
    state.loadSeq += 1; // same reason as showHome
    showView("calendar");
    setHeading("MEETING HISTORY", "Lịch cuộc họp", "Lịch cuộc họp · ASR EN VI");
    $("#workspace-link").removeAttribute("aria-current");
    renderSidebar();
    renderCalendars();
    void refreshHistory();
    $("#calendar-title").focus();
  }

  // The calendar never changes the URL, so the address bar is the return target: it
  // already points at the meeting (or home) we came from, and leaving pushes no entry.
  async function leaveCalendar() {
    const id = meetingIdFromPath();
    let target = "#page-title";
    if (id) {
      const painted = await loadMeeting(id);
      if (!painted) return; // superseded by newer navigation; it owns focus
      target = state.view === "meeting" ? "#meeting-title" : "#meeting-error-title";
    } else {
      showHome();
    }
    $(target).focus();
  }

  function navigateToMeeting(id) {
    const path = `/meetings/${encodeURIComponent(id)}`;
    if (window.location.pathname !== path) window.history.pushState({}, "", path);
    void loadMeeting(id);
  }

  function renderMeeting(meeting) {
    setHeading("SAVED MEETING", meeting.title, `${meeting.title} · ASR EN VI`);
    $("#meeting-title").textContent = meeting.title;
    const date = formatMeetingDate(meeting.meeting_date);
    const dateElement = $("#meeting-date");
    dateElement.textContent = date.label;
    if (date.dateTime) dateElement.setAttribute("datetime", date.dateTime);
    else dateElement.removeAttribute("datetime");
    $("#meeting-language").textContent = LANGUAGES[meeting.language_hint];
    renderTranscription(meeting.transcription);
  }

  const ACTIVE_TASK_STATES = new Set(["accepted", "running", "stopping"]);
  const TASK_STAGES = {
    accepted: "Đã nhận",
    starting: "Đang bắt đầu",
    starting_runner: "Khởi chạy runner",
    loading_model: "Nạp model local",
    transcribing: "Đang chép lời",
    publishing: "Lưu transcript hoàn chỉnh",
    stopping: "Đang dừng runner",
    complete: "Hoàn tất transcript",
    failed: "Thất bại",
    canceled: "Đã hủy",
    interrupted: "Bị gián đoạn",
  };

  function formatElapsedSeconds(value) {
    const seconds = Math.max(0, Number(value) || 0);
    return `${seconds.toFixed(1)} giây`;
  }

  function formatTimestamp(secondsValue) {
    const milliseconds = Math.max(0, Math.round((Number(secondsValue) || 0) * 1000));
    const hours = Math.floor(milliseconds / 3_600_000);
    const minutes = Math.floor((milliseconds % 3_600_000) / 60_000);
    const seconds = Math.floor((milliseconds % 60_000) / 1000);
    const fraction = Math.floor((milliseconds % 1000) / 10);
    const clock = hours > 0
      ? `${hours}:${String(minutes).padStart(2, "0")}:${String(seconds).padStart(2, "0")}`
      : `${minutes}:${String(seconds).padStart(2, "0")}`;
    return `${clock}.${String(fraction).padStart(2, "0")}`;
  }

  function renderMeetingProcessingStatus(task, generation) {
    let status = "Đã lưu, chưa xử lý";
    if (task && ACTIVE_TASK_STATES.has(task.status)) {
      status = task.status === "stopping" ? "Đang dừng xử lý" : "Đang chép lời";
    } else if (task && task.status === "succeeded") {
      status = "Đã có transcript · chưa có notes";
    } else if (task && task.status === "failed") {
      status = generation ? "Lần chạy mới thất bại · transcript trước vẫn còn" : "Xử lý thất bại";
    } else if (task && task.status === "interrupted") {
      status = generation ? "Bị gián đoạn · transcript trước vẫn còn" : "Bị gián đoạn";
    } else if (task && task.status === "canceled") {
      status = generation ? "Đã hủy · transcript trước vẫn còn" : "Đã hủy";
    } else if (generation) {
      status = "Đã có transcript · chưa có notes";
    }
    $("#meeting-status-text").textContent = status;
  }

  function renderTranscriptGeneration(generation) {
    const panel = $("#transcript-generation");
    const list = $("#transcript-segments");
    list.replaceChildren();
    panel.hidden = !generation;
    if (!generation) return;

    $("#generation-title").textContent = `Transcript #${generation.generation_number}`;
    const meta = [
      `Gợi ý: ${LANGUAGES[generation.language_hint] || generation.language_hint}`,
      generation.model_name,
      `${generation.segment_count} đoạn`,
    ].filter(Boolean);
    if (typeof generation.language_probability === "number") {
      meta.push(`language_probability ${generation.language_probability.toFixed(3)}`);
    }
    $("#generation-meta").textContent = meta.join(" · ");
    const segments = Array.isArray(generation.segments) ? generation.segments : [];
    $("#transcript-empty").hidden = segments.length > 0;

    for (const segment of segments) {
      const item = document.createElement("li");
      item.className = "transcript-segment";
      item.dataset.segmentId = segment.id;

      const timestamp = document.createElement("button");
      timestamp.className = "segment-timestamp";
      timestamp.type = "button";
      timestamp.dataset.seekSeconds = String(segment.start_seconds);
      timestamp.textContent = formatTimestamp(segment.start_seconds);

      const speaker = document.createElement("span");
      speaker.className = "segment-speaker";
      speaker.textContent = segment.speaker_id || segment.original_speaker_id || "Speaker chưa được gán";

      const text = document.createElement("p");
      text.className = "segment-text";
      text.textContent = segment.text;
      item.append(timestamp, speaker, text);

      if (segment.uncertain) {
        const reviewCue = document.createElement("span");
        reviewCue.className = "segment-review-cue";
        reviewCue.textContent = "Nên nghe lại";
        item.append(reviewCue);
      }

      const measures = [];
      if (typeof segment.avg_logprob === "number") measures.push(`avg_logprob ${segment.avg_logprob.toFixed(3)}`);
      if (typeof segment.no_speech_prob === "number") measures.push(`no_speech_prob ${segment.no_speech_prob.toFixed(3)}`);
      if (typeof segment.compression_ratio === "number") measures.push(`compression_ratio ${segment.compression_ratio.toFixed(3)}`);
      if (measures.length) {
        const modelMeasures = document.createElement("span");
        modelMeasures.className = "segment-model-measures";
        modelMeasures.textContent = `Chỉ số model, không phải độ chính xác đã hiệu chuẩn: ${measures.join(" · ")}`;
        item.append(modelMeasures);
      }
      list.append(item);
    }
  }

  function renderRuntimeProfile(runtime) {
    const panel = $("#runtime-profile");
    const device = runtime && runtime.device;
    panel.dataset.device = device || "unavailable";
    if (device === "cuda") {
      $("#runtime-backend").textContent = `GPU · CUDA · ${runtime.compute_type}`;
    } else if (device === "cpu") {
      $("#runtime-backend").textContent = `CPU fallback · ${runtime.compute_type}`;
    } else {
      $("#runtime-backend").textContent = "Worker chưa sẵn sàng";
    }
    $("#runtime-model").textContent = runtime && runtime.model_name
      ? runtime.model_name
      : "Chưa xác định";
  }

  function renderTranscription(transcription) {
    const task = transcription && transcription.task;
    const generation = transcription && transcription.generation;
    const active = Boolean(task && ACTIVE_TASK_STATES.has(task.status));
    const workerChecking = active && task.worker_state === "checking-worker";
    const startButton = $("#start-transcription");
    const cancelButton = $("#cancel-transcription");
    const measurements = $("#task-measurements");
    const error = $("#transcription-error");

    renderRuntimeProfile(transcription && transcription.runtime);

    startButton.hidden = active;
    startButton.disabled = state.taskRequestInFlight;
    startButton.textContent = generation ? "Chạy lại bản ghi" : "Bắt đầu chép lời";
    cancelButton.hidden = !active;
    cancelButton.disabled = !task || task.status === "stopping";
    cancelButton.textContent = task && task.status === "stopping" ? "Đang dừng…" : "Hủy xử lý";
    measurements.hidden = !task;
    const taskFailed = task && ["failed", "interrupted"].includes(task.status);
    error.hidden = !taskFailed && !state.taskRequestError;
    error.textContent = state.taskRequestError || (taskFailed ? task.error_message || "Tác vụ chưa hoàn tất." : "");

    if (!task) {
      $("#transcription-status").textContent = generation
        ? "Transcript hoàn chỉnh đã được lưu. Bạn có thể nghe lại các mốc hoặc chủ động chạy lại bản ghi."
        : "Bản ghi đã lưu. Bấm “Bắt đầu chép lời” khi bạn muốn chạy nhận dạng local.";
    } else {
      const statusText = {
        accepted: "Tác vụ đã được nhận. Worker sẽ bắt đầu xử lý.",
        running: "Đang chép lời bằng model local. Tác vụ tiếp tục nếu bạn đóng tab.",
        stopping: "Đang dừng và thu hồi runner. Slot chỉ được nhường sau khi runner đã kết thúc.",
        succeeded: "Transcript đã được lưu hoàn chỉnh. Kết quả hiện tại là transcript_only; chưa có notes.",
        failed: task.error_message || "Tác vụ thất bại. Transcript hoàn chỉnh trước đó vẫn được giữ.",
        canceled: "Đã hủy sau khi runner dừng. Transcript hoàn chỉnh trước đó vẫn được giữ.",
        interrupted: "Worker đã dừng giữa tác vụ. Không tự chạy lại; hãy bấm để thử lại.",
      };
      $("#transcription-status").textContent = workerChecking
        ? task.status === "accepted"
          ? "Đang kiểm tra worker trước khi bắt đầu xử lý."
          : "Đang kiểm tra worker vì heartbeat tác vụ đã cũ."
        : statusText[task.status] || "Đang tải trạng thái tác vụ.";
      $("#task-stage").textContent = TASK_STAGES[task.stage] || task.stage || "Chưa bắt đầu";
      $("#task-elapsed").textContent = formatElapsedSeconds(task.elapsed_seconds);
      $("#task-segment-count").textContent = String(task.segment_count || 0);
      $("#task-transcript-end").textContent = formatTimestamp(task.transcript_end_seconds || 0);
    }
    const status = $("#transcription-status");
    status.dataset.workerState = task && task.worker_state ? task.worker_state : "";
    status.classList.toggle("is-checking-worker", workerChecking);
    renderMeetingProcessingStatus(task, generation);
    renderTranscriptGeneration(generation);
  }

  function newTaskRequestId() {
    if (window.crypto && typeof window.crypto.randomUUID === "function") {
      return window.crypto.randomUUID();
    }
    return `task-${Date.now()}-${Math.random().toString(16).slice(2)}`;
  }

  function taskRequestStorageKey(meetingId) {
    return `asr-en-vi:transcription-request:${meetingId}`;
  }

  function getPendingTaskRequestId(meetingId) {
    const key = taskRequestStorageKey(meetingId);
    try {
      const stored = window.sessionStorage.getItem(key);
      if (stored) return stored;
      const requestId = newTaskRequestId();
      window.sessionStorage.setItem(key, requestId);
      return requestId;
    } catch {
      if (state.pendingTaskRequestId && state.pendingTaskRequestId.meetingId === meetingId) {
        return state.pendingTaskRequestId.requestId;
      }
      const requestId = newTaskRequestId();
      state.pendingTaskRequestId = { meetingId, requestId };
      return requestId;
    }
  }

  function clearPendingTaskRequestId(meetingId) {
    try {
      window.sessionStorage.removeItem(taskRequestStorageKey(meetingId));
    } catch {
      // The in-memory fallback is cleared below.
    }
    if (state.pendingTaskRequestId && state.pendingTaskRequestId.meetingId === meetingId) {
      state.pendingTaskRequestId = null;
    }
  }

  function rotateTerminalTaskRequestId(meetingId, task) {
    if (task && !ACTIVE_TASK_STATES.has(task.status)) clearPendingTaskRequestId(meetingId);
  }

  function stopTaskPolling() {
    if (state.taskPollTimer) window.clearTimeout(state.taskPollTimer);
    state.taskPollTimer = 0;
    state.taskPollId = null;
  }

  function scheduleTaskPoll(meetingId, taskId, delay = document.hidden ? 3000 : 1000) {
    if (state.taskPollTimer) window.clearTimeout(state.taskPollTimer);
    state.taskPollTimer = window.setTimeout(() => void pollTask(meetingId, taskId), delay);
  }

  function startTaskPolling(meetingId, task) {
    if (!task || !ACTIVE_TASK_STATES.has(task.status)) {
      stopTaskPolling();
      return;
    }
    if (state.taskPollId !== task.id) stopTaskPolling();
    state.taskPollId = task.id;
    if (!state.taskPollTimer) scheduleTaskPoll(meetingId, task.id);
  }

  async function refreshMeetingTranscription(meetingId) {
    const payload = await requestJson(`/api/meetings/${encodeURIComponent(meetingId)}`);
    const meeting = payload && payload.meeting && typeof payload.meeting === "object" ? payload.meeting : payload;
    if (!state.meeting || state.meeting.id !== meetingId || !meeting || !meeting.transcription) return;
    rotateTerminalTaskRequestId(meetingId, meeting.transcription.task);
    state.meeting = meeting;
    renderTranscription(meeting.transcription);
    renderSidebar();
  }

  async function pollTask(meetingId, taskId) {
    state.taskPollTimer = 0;
    if (state.taskPollId !== taskId || !state.meeting || state.meeting.id !== meetingId) return;
    try {
      const task = await requestJson(`/api/tasks/${encodeURIComponent(taskId)}`);
      if (state.taskPollId !== taskId || !state.meeting || state.meeting.id !== meetingId) return;
      state.meeting.transcription = {
        ...(state.meeting.transcription || {}),
        task,
      };
      renderTranscription(state.meeting.transcription);
      if (ACTIVE_TASK_STATES.has(task.status)) {
        scheduleTaskPoll(meetingId, taskId);
      } else {
        rotateTerminalTaskRequestId(meetingId, task);
        stopTaskPolling();
        if (task.status === "succeeded") {
          try {
            await refreshMeetingTranscription(meetingId);
          } catch {
            $("#transcription-status").textContent = "Tác vụ đã hoàn tất; không tải được transcript mới. Mở lại cuộc họp để thử lại.";
          }
        }
      }
    } catch {
      if (state.taskPollId !== taskId) return;
      $("#transcription-status").textContent = "Tạm mất kết nối khi đọc tiến độ. Tác vụ vẫn thuộc worker; đang thử đọc lại.";
      scheduleTaskPoll(meetingId, taskId, 3000);
    }
  }

  async function startTranscription() {
    const meeting = state.meeting;
    if (!meeting || state.taskRequestInFlight) return;
    const requestId = getPendingTaskRequestId(meeting.id);
    state.taskRequestInFlight = true;
    state.taskRequestError = null;
    renderTranscription(meeting.transcription);
    try {
      const task = await requestJson("/api/tasks", {
        method: "POST",
        body: JSON.stringify({ meeting_id: meeting.id, request_id: requestId }),
      });
      clearPendingTaskRequestId(meeting.id);
      state.taskRequestError = null;
      meeting.transcription = { ...(meeting.transcription || {}), task };
      renderTranscription(meeting.transcription);
      startTaskPolling(meeting.id, task);
      if (task.status === "succeeded") await refreshMeetingTranscription(meeting.id);
    } catch (requestError) {
      const definitiveError = Number.isInteger(requestError && requestError.status)
        && requestError.status >= 400
        && requestError.status < 500;
      if (definitiveError) clearPendingTaskRequestId(meeting.id);
      const retryGuidance = definitiveError
        ? "Bấm lại để gửi một yêu cầu mới."
        : "Bấm lại để xác minh bằng cùng request ID.";
      state.taskRequestError = `${requestError && requestError.message ? requestError.message : "Không thể xác nhận yêu cầu."} ${retryGuidance}`;
      $("#transcription-status").textContent = "Chưa xác nhận được việc nhận tác vụ. Yêu cầu chưa được tự gửi lại.";
    } finally {
      state.taskRequestInFlight = false;
      if (state.meeting && state.meeting.id === meeting.id) renderTranscription(state.meeting.transcription);
    }
  }

  async function cancelTranscription() {
    const meeting = state.meeting;
    const task = meeting && meeting.transcription && meeting.transcription.task;
    if (!meeting || !task || !ACTIVE_TASK_STATES.has(task.status) || task.status === "stopping") return;
    $("#cancel-transcription").disabled = true;
    try {
      const updated = await requestJson(`/api/tasks/${encodeURIComponent(task.id)}/cancel`, {
        method: "POST",
        body: JSON.stringify({}),
      });
      state.taskRequestError = null;
      meeting.transcription.task = updated;
      renderTranscription(meeting.transcription);
      startTaskPolling(meeting.id, updated);
    } catch (requestError) {
      state.taskRequestError = requestError && requestError.message
        ? requestError.message
        : "Không thể gửi yêu cầu hủy. Trạng thái tác vụ chưa được thay đổi trên giao diện.";
      renderTranscription(meeting.transcription);
    }
  }

  // Resolves true when this call painted the final view, false when newer navigation won.
  async function loadMeeting(meetingId) {
    const sequence = ++state.loadSeq;
    const sameMeeting = state.meeting && state.meeting.id === meetingId;
    if (!sameMeeting) stopTaskPolling();
    if (!sameMeeting) closeEditor(); // drops the draft, which orphans any save still in flight
    $("#workspace-link").removeAttribute("aria-current");
    if (sameMeeting) {
      renderMeeting(state.meeting); // show what we already know while the refresh runs
      showView("meeting");
    } else {
      setHeading("SAVED MEETING", "Cuộc họp", "Cuộc họp · ASR EN VI");
      showView("loading");
    }
    try {
      const payload = await requestJson(`/api/meetings/${encodeURIComponent(meetingId)}`);
      if (sequence !== state.loadSeq) return false;
      let meeting = payload && payload.meeting && typeof payload.meeting === "object" ? payload.meeting : payload;
      if (!meeting || typeof meeting.title !== "string" || typeof meeting.id !== "string") {
        throw new Error("Máy chủ không trả về metadata cuộc họp hợp lệ.");
      }
      if (!LANGUAGES[meeting.language_hint]) throw new Error("Cuộc họp chưa có gợi ý ngôn ngữ hợp lệ.");
      // A read issued before a save landed can answer after it; never step back a version.
      const known = state.meeting;
      if (known && known.id === meeting.id && known.metadata_version > meeting.metadata_version) meeting = known;
      rotateTerminalTaskRequestId(meetingId, meeting.transcription && meeting.transcription.task);
      state.meeting = meeting;
      renderMeeting(meeting);
      const audio = $("#meeting-audio");
      if (audio.dataset.meetingId !== meeting.id) {
        const audioUrl = meeting.audio_url || (meeting.recording && meeting.recording.audio_url);
        audio.src = sameOriginAudioSource(audioUrl, meeting.id);
        audio.dataset.meetingId = meeting.id;
        audio.load();
      }
      showView("meeting");
      startTaskPolling(meeting.id, meeting.transcription && meeting.transcription.task);
      renderSidebar();
      if (!state.meetings.length) void refreshHistory();
      return true;
    } catch (error) {
      if (sequence !== state.loadSeq) return false;
      const message = error instanceof ApiError ? error.message : (error && error.message) || "Không thể tải dữ liệu cuộc họp.";
      showMeetingError(`${message} Hãy kiểm tra phiên truy cập hoặc mở lại cuộc họp từ workspace.`);
      return true;
    }
  }

  // ---- metadata editing ----
  function showEditError(message) {
    $("#edit-error").textContent = message;
    $("#edit-error").hidden = !message;
  }

  function closeEditor() {
    state.draft = null;
    state.saveSeq += 1; // an in-flight save may no longer touch this editor
    setEditorBusy(false);
    $("#meeting-edit").hidden = true;
    $("#edit-meeting").hidden = false;
    $("#edit-conflict").hidden = true;
    showEditError("");
  }

  function openEditor() {
    const meeting = state.meeting;
    if (!meeting) return;
    // `original` is what the user started from; a field counts as edited only when
    // its input differs from it. `version` is the baseline the next save is checked against.
    state.draft = {
      original: { title: meeting.title, meeting_date: meeting.meeting_date },
      version: meeting.metadata_version,
    };
    $("#edit-title").value = meeting.title;
    $("#edit-date").value = meeting.meeting_date || "";
    $("#edit-status").textContent = "";
    $("#edit-conflict").hidden = true;
    $("#edit-save").textContent = "Lưu thay đổi";
    showEditError("");
    $("#meeting-edit").hidden = false;
    $("#edit-meeting").hidden = true;
    $("#edit-title").focus();
  }

  function setEditorBusy(busy) {
    for (const selector of ["#edit-save", "#edit-cancel", "#edit-title", "#edit-date", "#edit-clear-date"]) {
      $(selector).disabled = busy;
    }
  }

  async function saveMeeting(event) {
    event.preventDefault();
    const draft = state.draft;
    if (!draft) return;
    const title = $("#edit-title").value.trim();
    if (!title || Array.from(title).length > 200) {
      showEditError("Tên cuộc họp phải có từ 1 đến 200 ký tự.");
      return;
    }
    // A half-typed date reads as "" but is not a deletion: only "Xóa ngày" or an
    // empty field removes the date.
    if ($("#edit-date").validity.badInput) {
      showEditError("Ngày họp chưa đầy đủ hoặc không hợp lệ. Nhập đủ ngày, tháng, năm hoặc bấm “Xóa ngày” để bỏ ngày.");
      $("#edit-date").focus();
      return;
    }
    const meetingDate = $("#edit-date").value || null;
    const fields = {};
    if (title !== draft.original.title) fields.title = title;
    if (meetingDate !== draft.original.meeting_date) fields.meeting_date = meetingDate;
    if (Object.keys(fields).length === 0) {
      closeEditor();
      return;
    }
    showEditError("");
    setEditorBusy(true);
    // The save outlives navigation. Its editor session is this meeting plus this draft
    // object: opening another meeting drops the draft, but a calendar detour keeps it.
    // While the session lives, results are applied to the model and editor DOM even if the
    // calendar is showing (so a result or conflict is never lost); only the visible
    // meeting heading is repainted, and only when the meeting view is up.
    const id = state.meeting.id;
    const saveId = ++state.saveSeq;
    const sameSession = () => state.meeting && state.meeting.id === id && state.draft === draft;
    try {
      const updated = await requestJson(`/api/meetings/${encodeURIComponent(id)}`, {
        method: "PATCH",
        body: JSON.stringify({ expected_metadata_version: draft.version, ...fields }),
      });
      if (sameSession()) {
        state.meeting = updated;
        closeEditor();
        $("#edit-status").textContent = "Đã lưu tên và ngày họp.";
        if (state.view === "meeting") {
          renderMeeting(updated);
          $("#edit-meeting").focus();
        }
      }
      void refreshHistory();
    } catch (error) {
      const code = error instanceof ApiError && error.payload && error.payload.detail ? error.payload.detail.code : "";
      if (code === "stale_version") await showConflict(id, sameSession);
      else if (sameSession()) showEditError(error && error.message ? error.message : "Không thể lưu thay đổi.");
    } finally {
      if (saveId === state.saveSeq) setEditorBusy(false);
    }
  }

  // Another tab saved first. Fields the user edited keep their draft; untouched fields
  // follow the stored values so they are neither shown stale nor re-sent. Only the
  // version baseline moves, and the user must save again explicitly.
  async function showConflict(id, sameSession) {
    const conflict = $("#edit-conflict");
    try {
      const current = await requestJson(`/api/meetings/${encodeURIComponent(id)}`);
      if (!sameSession()) {
        void refreshHistory(); // the user moved on; only the lists may learn about it
        return;
      }
      const draft = state.draft;
      const titleEdited = $("#edit-title").value.trim() !== draft.original.title;
      const dateEdited = ($("#edit-date").value || null) !== draft.original.meeting_date;
      if (!titleEdited) {
        $("#edit-title").value = current.title;
        draft.original.title = current.title;
      }
      if (!dateEdited) {
        $("#edit-date").value = current.meeting_date || "";
        draft.original.meeting_date = current.meeting_date;
      }
      draft.version = current.metadata_version;
      state.meeting = current;
      if (state.view === "meeting") renderMeeting(current);
      const date = current.meeting_date ? displayDate(current.meeting_date) : "Chưa đặt ngày";
      const kept = [titleEdited && "tên", dateEdited && "ngày họp"].filter(Boolean).join(" và ");
      conflict.textContent = `Cuộc họp đã được cập nhật ở nơi khác: “${current.title}” · ${date}. ${kept ? `Bản nháp ${kept} của bạn vẫn được giữ; lưu lại để ghi đè phần đó` : "Bạn chưa sửa trường nào khác bản đã lưu"}, hoặc hủy để dùng bản đã lưu.`;
      $("#edit-save").textContent = "Lưu bản nháp lên bản mới nhất";
      void refreshHistory();
    } catch {
      if (!sameSession()) return;
      conflict.textContent = "Cuộc họp đã được cập nhật ở nơi khác và chưa tải được bản mới. Bản nháp của bạn được giữ nguyên.";
    }
    conflict.hidden = false;
  }

  // ---- wiring ----
  for (const root of document.querySelectorAll("[data-calendar]")) {
    buildCalendar(root);
    root.addEventListener("click", onCalendarClick);
    root.addEventListener("input", onCalendarInput);
    root.addEventListener("change", onCalendarChange);
    root.addEventListener("focusout", onCalendarFocusout);
    root.addEventListener("keydown", onCalendarKeydown);
  }

  document.addEventListener("click", (event) => {
    const link = event.target.closest("a[data-meeting-link]");
    if (!link || event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
    event.preventDefault();
    navigateToMeeting(link.dataset.meetingLink);
  });
  $("#open-calendar").addEventListener("click", openCalendar);
  $("#mini-open-calendar").addEventListener("click", openCalendar);
  $("#calendar-back").addEventListener("click", leaveCalendar);
  $("#edit-meeting").addEventListener("click", openEditor);
  $("#edit-cancel").addEventListener("click", () => {
    closeEditor();
    $("#edit-meeting").focus();
  });
  $("#edit-clear-date").addEventListener("click", () => {
    $("#edit-date").value = "";
    $("#edit-date").focus();
  });
  $("#meeting-edit").addEventListener("submit", saveMeeting);
  $("#start-transcription").addEventListener("click", () => void startTranscription());
  $("#cancel-transcription").addEventListener("click", () => void cancelTranscription());
  $("#transcript-segments").addEventListener("click", (event) => {
    const timestamp = event.target.closest("button[data-seek-seconds]");
    if (!timestamp) return;
    const audio = $("#meeting-audio");
    const seconds = Number(timestamp.dataset.seekSeconds);
    if (!Number.isFinite(seconds) || seconds < 0) return;
    audio.currentTime = seconds;
    const playback = audio.play();
    if (playback && typeof playback.catch === "function") playback.catch(() => {});
  });
  document.addEventListener("visibilitychange", () => {
    if (!state.taskPollId) return;
    const task = state.meeting && state.meeting.transcription && state.meeting.transcription.task;
    if (task && ACTIVE_TASK_STATES.has(task.status)) {
      scheduleTaskPoll(state.meeting.id, task.id);
    }
  });

  let searchTimer = 0;
  const searchInput = $("#history-search");
  searchInput.addEventListener("input", () => {
    window.clearTimeout(searchTimer);
    state.query = searchInput.value;
    searchTimer = window.setTimeout(async () => {
      if (state.query.trim()) await runSearch();
      renderSidebar();
    }, 120);
    if (!state.query.trim()) renderSidebar();
  });
  searchInput.addEventListener("keydown", (event) => {
    if (event.key !== "Escape" || !searchInput.value) return;
    searchInput.value = "";
    state.query = "";
    renderSidebar();
  });

  window.addEventListener("popstate", () => {
    const id = meetingIdFromPath();
    if (id) void loadMeeting(id);
    else showHome();
  });

  renderCalendars();
  const initialId = meetingIdFromPath();
  if (initialId) void loadMeeting(initialId);
  else showHome();
  void refreshHistory();
})();
