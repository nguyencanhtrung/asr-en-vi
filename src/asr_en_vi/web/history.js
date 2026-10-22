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
  const REVIEW_REASON_LABELS = {
    asr_uncertain: "Nhận dạng chưa chắc",
    overlap: "Có lời nói chồng lấn",
    multiple_speakers: "Nhiều người nói trong đoạn",
    low_speaker_dominance: "Người nói chưa rõ",
    unidentified_speaker: "Chưa xác định người nói",
  };
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
    selectedGenerationId: null,
    currentGenerationId: null,
    taskPollTimer: 0,
    taskPollId: null,
    taskRequestInFlight: false,
    transcriptMutationInFlight: false,
    notesSourceLocked: false,
    notesSourceLockKnown: false,
    notesCount: 0, // saved notes revisions, as notes.js last counted them
    notesKnown: false, // notes.js has answered for this meeting, so the count above means something
    notesTaskStatus: null,
    tab: null, // "notes" | "transcript"; null while the default waits for notes.js
    tabTimer: 0,
    editorBusy: false,
    transcriptMutationFocus: null,
    transcriptMutationFocusAfter: null,
    transcriptMutationFocusDescriptor: null,
    transcriptMutationStatusDescriptor: null,
    transcriptMutationError: null,
    transcriptReloadInFlight: false,
    transcriptDrafts: new Map(),
    editingSegment: null, // { generationId, segmentId }: the one segment whose editor is open
    renamingSpeaker: null, // { generationId, speakerId }: the one speaker chip being renamed
    pendingTaskRequestId: null,
    taskRequestError: null,
  };

  // ---- views ----
  function showView(name) {
    for (const [key, selector] of Object.entries(VIEWS)) $(selector).hidden = key !== name;
    state.view = name;
  }

  function sourceMutationUnavailable() {
    return !state.notesSourceLockKnown || state.notesSourceLocked;
  }

  function notifyMeetingContext() {
    document.dispatchEvent(new CustomEvent("asr:meeting-context", {
      detail: {
        meeting: state.view === "meeting" ? state.meeting : null,
        view: state.view,
        transcriptionRequestInFlight: state.taskRequestInFlight,
      },
    }));
  }

  function renderNotesSourceLock() {
    const status = $("#notes-lock-status");
    const unavailable = sourceMutationUnavailable();
    syncMetadataLockControls();
    if (!state.notesSourceLockKnown) {
      status.textContent = "Đang kiểm tra trạng thái khóa nguồn trước khi cho phép sửa transcript, người nói hoặc ngày họp.";
      status.hidden = false;
    } else if (state.notesSourceLocked) {
      status.textContent = "Nguồn đang được dùng để tạo notes. Chỉnh sửa transcript, người nói và ngày họp tạm thời bị khóa.";
      status.hidden = false;
    } else {
      status.textContent = "";
      status.hidden = true;
    }
    syncTranscriptMutationControls();
    if (state.meeting && state.meeting.transcription) {
      renderTranscription(state.meeting.transcription);
    }
    syncTranscriptMutationControls();
  }

  function syncMetadataLockControls() {
    const dateInput = $("#edit-date");
    const dateChanged = Boolean(
      state.draft
      && (dateInput.value || null) !== state.draft.original.meeting_date,
    );
    const locked = sourceMutationUnavailable();
    $("#edit-title").disabled = state.editorBusy;
    dateInput.disabled = state.editorBusy || (locked && !dateChanged);
    $("#edit-clear-date").disabled = state.editorBusy || (locked && !dateChanged);
    $("#edit-save").disabled = state.editorBusy || (locked && dateChanged);
    $("#edit-cancel").disabled = state.editorBusy;
  }

  function setNotesSourceLock(meetingId, locked, known = true) {
    if (!state.meeting || state.meeting.id !== meetingId) return;
    if (state.notesSourceLocked === Boolean(locked) && state.notesSourceLockKnown === Boolean(known)) return;
    state.notesSourceLocked = Boolean(locked);
    state.notesSourceLockKnown = Boolean(known);
    renderNotesSourceLock();
  }

  function setHeading(title, documentTitle) {
    $("#page-title").textContent = title;
    document.title = documentTitle;
  }

  // ---- meeting tabs: Meeting notes | Transcript & bản ghi ----
  const MEETING_TABS = ["notes", "transcript"];
  const TAB_PENDING_MS = 4000; // if notes.js never answers, the page falls back to the transcript

  // The tab the address names: a #notes or #transcript hash, the tab this history entry remembers (see
  // pushMeetingUrl), or, for a saved-source link with no hash, the notes tab where the source view lives.
  function locatedTab() {
    const named = window.location.hash.slice(1);
    if (MEETING_TABS.includes(named)) return named;
    const remembered = window.history.state && window.history.state.meetingTab;
    if (MEETING_TABS.includes(remembered)) return remembered;
    const params = new URLSearchParams(window.location.search);
    return params.has("notes_source") && params.has("segment") ? "notes" : null;
  }

  // With no tab in the address: notes when the meeting has saved notes or is making some, else transcript.
  // Unknown until notes.js has read the notes.
  function defaultTab() {
    if (!state.notesKnown) return null;
    return state.notesCount > 0 || ACTIVE_TASK_STATES.has(state.notesTaskStatus) ? "notes" : "transcript";
  }

  function resetTab() {
    window.clearTimeout(state.tabTimer);
    state.tabTimer = 0;
    state.tab = null;
  }

  // Paint a tab, or none (null) while the default is still unknown. Then no tab is selected and the notes
  // panel is hidden; the transcript panel, the likelier answer, is laid out but transparent, so the other
  // panel never flashes and the transcript's controls are already in place when it is the one.
  function setTab(tab) {
    state.tab = tab;
    for (const name of MEETING_TABS) {
      const selected = name === tab;
      $(`#meeting-tab-${name}`).setAttribute("aria-selected", String(selected));
      // Roving tabindex: only the chosen tab is a Tab stop (the first one, before any is chosen).
      $(`#meeting-tab-${name}`).tabIndex = selected || (tab === null && name === MEETING_TABS[0]) ? 0 : -1;
    }
    $("#meeting-panel-notes").hidden = tab !== "notes";
    $("#meeting-panel-transcript").hidden = tab === "notes";
    $("#meeting-panel-transcript").classList.toggle("is-pending", tab === null);
    if (tab !== null) {
      window.clearTimeout(state.tabTimer);
      state.tabTimer = 0;
    } else if (!state.tabTimer) {
      state.tabTimer = window.setTimeout(() => {
        state.tabTimer = 0;
        if (state.tab === null) setTab("transcript");
      }, TAB_PENDING_MS);
    }
  }

  // Shown whenever the meeting view appears: the address wins, then what the page already shows, then the default.
  function initMeetingTab() {
    setTab(locatedTab() ?? state.tab ?? defaultTab());
  }

  // A new history entry for the meeting page. The entry being left remembers its tab, so Back restores it
  // even if the default for an address without a hash has changed since.
  function pushMeetingUrl(url, tab = null) {
    if (state.tab && state.meeting && state.meeting.id === meetingIdFromPath()) {
      window.history.replaceState({ ...window.history.state, meetingTab: state.tab }, "");
    }
    window.history.pushState(tab ? { meetingTab: tab } : {}, "", url);
  }

  // Choose a tab as the user does: a new history entry with #tab, so Back returns to the previous tab.
  function selectTab(tab, { focus = false } = {}) {
    if (!MEETING_TABS.includes(tab) || state.view !== "meeting") return;
    if (tab !== state.tab) {
      pushMeetingUrl(`${window.location.pathname}${window.location.search}#${tab}`, tab);
      setTab(tab);
    }
    if (focus) $(`#meeting-tab-${tab}`).focus();
  }

  // The tab names what its panel holds: how many segments, and how many of them ask for a second look.
  function renderTabCounts(generation) {
    const segments = generation && Array.isArray(generation.segments) ? generation.segments : null;
    $("#meeting-tab-count").textContent = segments
      ? `${segments.length} đoạn · ${segments.filter(needsReview).length} cần kiểm tra`
      : "";
  }

  function showHome() {
    state.loadSeq += 1; // a meeting load still in flight must not repaint over home
    stopTaskPolling();
    resetTab();
    showView("home");
    setHeading("Cuộc họp", "Workspace · ASR EN VI");
    renderSidebar();
    notifyMeetingContext();
  }

  function showMeetingError(message) {
    $("#meeting-error-copy").textContent = message;
    showView("error");
    notifyMeetingContext();
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
    setHeading("Lịch cuộc họp", "Lịch cuộc họp · ASR EN VI");
    renderSidebar();
    renderCalendars();
    void refreshHistory();
    notifyMeetingContext();
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

  function waitForAudioMetadata(audio) {
    if (audio.readyState >= HTMLMediaElement.HAVE_METADATA) return Promise.resolve(true);
    return new Promise((resolve) => {
      let settled = false;
      const finish = (ready) => {
        if (settled) return;
        settled = true;
        window.clearTimeout(timer);
        audio.removeEventListener("loadedmetadata", onReady);
        audio.removeEventListener("error", onError);
        resolve(ready);
      };
      const onReady = () => finish(true);
      const onError = () => finish(false);
      const timer = window.setTimeout(() => finish(false), 5000);
      audio.addEventListener("loadedmetadata", onReady, { once: true });
      audio.addEventListener("error", onError, { once: true });
    });
  }

  async function seekNotesSource({ meetingId, snapshotId, segmentId, startSeconds }) {
    if (
      typeof meetingId !== "string"
      || !meetingId
      || typeof snapshotId !== "string"
      || !snapshotId
      || typeof segmentId !== "string"
      || !segmentId
      || !Number.isFinite(startSeconds)
      || startSeconds < 0
    ) return false;
    const path = `/meetings/${encodeURIComponent(meetingId)}`;
    const query = `?notes_source=${encodeURIComponent(snapshotId)}&segment=${encodeURIComponent(segmentId)}`;
    if (window.location.pathname !== path || window.location.search !== query) {
      // Opening a source does not change the tab: the new entry keeps the address's hash and the tab shown.
      const shown = state.meeting && state.meeting.id === meetingId && state.view === "meeting";
      const hash = window.location.pathname === path ? window.location.hash : "";
      pushMeetingUrl(`${path}${query}${hash}`, shown ? state.tab : null);
    }
    if (!state.meeting || state.meeting.id !== meetingId || state.view !== "meeting") {
      const painted = await loadMeeting(meetingId);
      if (!painted || !state.meeting || state.meeting.id !== meetingId || state.view !== "meeting") return false;
    }
    const audio = $("#meeting-audio");
    if (audio.dataset.meetingId !== meetingId || !(await waitForAudioMetadata(audio))) return false;
    try {
      audio.currentTime = startSeconds;
      updateActiveTranscriptIntervals();
      return true;
    } catch {
      return false;
    }
  }

  function renderMeeting(meeting) {
    // The name shows once, in #meeting-title; the page heading above it stays generic.
    setHeading("Cuộc họp", `${meeting.title} · ASR EN VI`);
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
    starting_diarization: "Chuẩn bị nhận dạng người nói",
    loading_diarization_model: "Nạp Community-1 local",
    decoding_input: "Đọc bản ghi local",
    diarizing: "Đang nhận dạng người nói",
    publishing: "Lưu transcript hoàn chỉnh",
    stopping: "Đang dừng runner",
    complete: "Hoàn tất transcript",
    failed: "Thất bại",
    canceled: "Đã hủy",
    interrupted: "Bị gián đoạn",
  };
  const TASK_ERROR_MESSAGES = {
    diarization_decoder_unavailable: "Bộ giải mã âm thanh local không khả dụng. Kiểm tra dependencies âm thanh của ứng dụng.",
    diarization_model_load_failed: "Không thể nạp model Community-1 local. Kiểm tra các model assets đã được cấp quyền và tải đầy đủ.",
    diarization_cuda_failed: "Community-1 không chạy được trên CUDA đã chọn. Kiểm tra CUDA hoặc chọn CPU.",
    diarization_input_decode_failed: "Không thể giải mã bản ghi. Tải lại file âm thanh hợp lệ rồi thử lại.",
    diarization_failed: "Nhận dạng người nói thất bại. Kiểm tra worker logs rồi thử lại.",
    publication_failed: "Không thể lưu transcript hoàn chỉnh. Kiểm tra bộ nhớ lưu trữ rồi thử lại.",
  };
  const SAFE_TASK_ID = /^[0-9a-f]{32}$/;

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

  function renderTaskError(task) {
    const container = $("#transcription-error");
    clearReloadLatestAction(container);
    const taskFailed = task && ["failed", "interrupted"].includes(task.status);
    container.hidden = !taskFailed && !state.taskRequestError;

    const details = $("#task-diagnostic-details");
    const commandWrap = $("#task-diagnostic-command-wrap");
    const commandInput = $("#task-diagnostic-command");
    const copyStatus = $("#task-diagnostic-copy-status");
    details.hidden = true;
    commandWrap.hidden = true;
    commandInput.value = "";
    copyStatus.textContent = "";

    const code = task && typeof task.error_code === "string" ? task.error_code : "";
    const diagnosticMessage = Object.hasOwn(TASK_ERROR_MESSAGES, code)
      ? TASK_ERROR_MESSAGES[code]
      : "";
    $("#transcription-error-message").textContent = state.taskRequestError || (
      taskFailed
        ? diagnosticMessage || task.error_message || "Tác vụ chưa hoàn tất."
        : ""
    );

    if (state.taskRequestError) return;
    if (!diagnosticMessage || !task || !SAFE_TASK_ID.test(task.id || "")) return;
    $("#task-diagnostic-code").textContent = code;
    $("#task-diagnostic-id").textContent = task.id;
    details.hidden = false;
    commandInput.value = `docker compose exec -T app python -m asr_en_vi.cli task diagnose ${task.id}`;
    commandWrap.hidden = false;
  }

  function renderTranscriptMutationError() {
    const panel = $("#transcript-mutation-error");
    const message = $("#transcript-mutation-error-message");
    const mutationError = state.transcriptMutationError;
    const meeting = state.meeting;
    const generationExists = Boolean(
      mutationError
      && meeting
      && meeting.id === mutationError.meetingId
      && state.selectedGenerationId === mutationError.generationId
      && generationsFor(meeting.transcription).some(
        (generation) => generation.id === mutationError.generationId,
      ),
    );
    panel.hidden = !generationExists;
    if (!generationExists) {
      clearReloadLatestAction(panel);
      return;
    }
    message.textContent = mutationError.message;
    if (mutationError.reloadLatest) {
      appendReloadLatestButton(panel, mutationError.generationId);
    } else {
      clearReloadLatestAction(panel);
    }
  }

  async function copyDiagnosticCommand() {
    const input = $("#task-diagnostic-command");
    const status = $("#task-diagnostic-copy-status");
    if (!input.value) return;
    try {
      if (!navigator.clipboard || !navigator.clipboard.writeText) throw new Error("Clipboard unavailable");
      await navigator.clipboard.writeText(input.value);
      status.textContent = "Đã sao chép lệnh.";
    } catch {
      input.focus();
      input.select();
      const copied = document.execCommand("copy");
      status.textContent = copied
        ? "Đã sao chép lệnh."
        : "Lệnh đã được chọn. Nhấn Ctrl+C hoặc ⌘C để sao chép.";
    }
  }

  // How a run that did not finish reads alone, and after "lần chạy mới" / "lần tạo mới".
  const RUN_END_LABELS = { failed: "Thất bại", canceled: "Đã hủy", interrupted: "Bị gián đoạn" };
  const NEW_RUN_END_WORDS = { failed: "thất bại", canceled: "bị hủy", interrupted: "bị gián đoạn" };

  function setStatusItem(id, name, value, itemState) {
    const item = $(`#status-${id}`);
    item.dataset.state = itemState; // idle | active | done | warning | problem: only repeats the words
    item.lastElementChild.textContent = `${name} · ${value}`;
  }

  // The header strip: one short line per stage. The words carry the state; the dot only repeats it.
  function renderMeetingProcessingStatus(task, generation) {
    const meeting = state.meeting;
    const seconds = Number(meeting && meeting.recording && meeting.recording.duration_seconds);
    setStatusItem(
      "recording",
      "Bản ghi",
      seconds > 0 ? `Đã lưu · ${formatRecordingDuration(seconds)}` : "Đã lưu",
      "done",
    );

    const transcriptEnd = task && Object.hasOwn(RUN_END_LABELS, task.status) ? task.status : null;
    if (task && ACTIVE_TASK_STATES.has(task.status)) {
      setStatusItem("transcript", "Transcript", task.status === "stopping" ? "Đang dừng" : "Đang chép lời", "active");
    } else if (generation) {
      setStatusItem(
        "transcript",
        "Transcript",
        transcriptEnd ? `Hoàn tất · lần chạy mới ${NEW_RUN_END_WORDS[transcriptEnd]}` : "Hoàn tất",
        transcriptEnd ? "warning" : "done",
      );
    } else if (transcriptEnd) {
      setStatusItem("transcript", "Transcript", RUN_END_LABELS[transcriptEnd], transcriptEnd === "failed" ? "problem" : "warning");
    } else {
      setStatusItem("transcript", "Transcript", "Chưa chép lời", "idle");
    }

    const notesEnd = Object.hasOwn(RUN_END_LABELS, state.notesTaskStatus) ? state.notesTaskStatus : null;
    if (!state.notesKnown) {
      setStatusItem("notes", "Notes", "Đang kiểm tra", "idle");
    } else if (ACTIVE_TASK_STATES.has(state.notesTaskStatus)) {
      setStatusItem("notes", "Notes", state.notesTaskStatus === "stopping" ? "Đang dừng" : "Đang tạo", "active");
    } else if (state.notesCount > 0) {
      setStatusItem(
        "notes",
        "Notes",
        `${state.notesCount} bản${notesEnd ? ` · lần tạo mới ${NEW_RUN_END_WORDS[notesEnd]}` : ""}`,
        notesEnd ? "warning" : "done",
      );
    } else if (notesEnd) {
      setStatusItem("notes", "Notes", RUN_END_LABELS[notesEnd], notesEnd === "failed" ? "problem" : "warning");
    } else {
      setStatusItem("notes", "Notes", "Chưa có", "idle");
    }
  }

  function generationsFor(transcription) {
    const current = transcription && transcription.generation;
    const history = transcription && Array.isArray(transcription.generation_history)
      ? transcription.generation_history
      : [];
    const byId = new Map();
    for (const generation of [...history, current].filter(Boolean)) byId.set(generation.id, generation);
    return [...byId.values()].sort(
      (left, right) => left.generation_number - right.generation_number,
    );
  }

  function transcriptDraftBucket(generationId, create = false) {
    let bucket = state.transcriptDrafts.get(generationId);
    if (!bucket && create) {
      bucket = {
        segmentText: new Map(),
        speakerName: new Map(),
        speakerAssignment: new Map(),
        speakerAddName: new Map(),
      };
      state.transcriptDrafts.set(generationId, bucket);
    }
    return bucket || null;
  }

  function transcriptDraft(generationId, field, itemId) {
    const bucket = transcriptDraftBucket(generationId);
    return bucket ? bucket[field].get(itemId) || null : null;
  }

  // The backend names a speaker nobody renamed "Speaker 3"; its chip invites a name.
  const DEFAULT_SPEAKER_NAME = /^Speaker \d+$/;

  // The default names a transcript still carries, for the notes reminder to name them.
  function defaultSpeakerNames(generation) {
    const speakers = generation && Array.isArray(generation.speakers) ? generation.speakers : [];
    return speakers.map((speaker) => speaker.display_name || "").filter((name) => DEFAULT_SPEAKER_NAME.test(name));
  }

  // Open the Transcript tab at the current transcript's speaker catalog, ready to name the speakers.
  function focusSpeakerCatalog() {
    if (state.view !== "meeting") return;
    selectTab("transcript");
    const transcription = state.meeting && state.meeting.transcription;
    const current = transcription && transcription.generation;
    // Only the current transcript takes names, so a past one on screen gives way to it.
    if (current && state.selectedGenerationId !== current.id) {
      const selector = $("#generation-selector");
      selector.value = current.id;
      selector.dispatchEvent(new Event("change", { bubbles: true }));
    }
    $("#speaker-catalog-title").focus();
  }

  function isEditingSegment(generationId, segmentId) {
    const editing = state.editingSegment;
    return Boolean(editing && editing.generationId === generationId && editing.segmentId === segmentId);
  }

  function isRenamingSpeaker(generationId, speakerId) {
    const renaming = state.renamingSpeaker;
    return Boolean(renaming && renaming.generationId === generationId && renaming.speakerId === speakerId);
  }

  function hasSegmentDraft(generationId, segmentId) {
    return Boolean(
      transcriptDraft(generationId, "segmentText", segmentId)
      || transcriptDraft(generationId, "speakerAssignment", segmentId),
    );
  }

  // A conflict-marked draft can be the only copy of what the user typed, so Hủy and Esc keep it.
  function isConflictedDraft(generationId, field, itemId) {
    const draft = transcriptDraft(generationId, field, itemId);
    return Boolean(draft && draft.conflictCode);
  }

  // A conflict marks the draft while the page still shows the value the draft started from. Once a
  // reload shows a different one, the review already holds the latest and no reload is due.
  function awaitsLatestReload(draft, currentValue) {
    return Boolean(draft && draft.conflictCode && draft.baseValue === currentValue);
  }

  // A closed row or chip cannot hold the reload (a read row keeps two tab stops), so a conflict still
  // waiting on it moves to the page's conflict panel when its editor closes, and back beside the
  // editor's buttons when it reopens.
  function placeLatestReload(generationId, field, itemId, currentValue, editorOpen) {
    const draft = transcriptDraft(generationId, field, itemId);
    if (!awaitsLatestReload(draft, currentValue)) return;
    if (editorOpen) clearTranscriptMutationError(generationId);
    else showTranscriptConflictNotice(generationId, draft.conflictCode);
  }

  // The generation on screen and whether it takes edits, as renderGenerationNavigation decides.
  function displayedGeneration() {
    const transcription = state.meeting && state.meeting.transcription;
    const current = transcription && transcription.generation;
    const generation = generationsFor(transcription).find((item) => item.id === state.selectedGenerationId);
    return {
      generation,
      editable: Boolean(
        generation && current && current.id === generation.id && generation.status === "complete",
      ),
    };
  }

  function speakerAddRecoveryReady(generation, draft) {
    return Boolean(
      generation
      && generation.status === "complete"
      && !sourceMutationUnavailable()
      && !(draft && draft.conflictCode)
      && !state.transcriptMutationInFlight
      && !state.transcriptReloadInFlight
    );
  }

  function transcriptDraftBucketIsEmpty(bucket) {
    return bucket.segmentText.size === 0
      && bucket.speakerName.size === 0
      && bucket.speakerAssignment.size === 0
      && bucket.speakerAddName.size === 0;
  }

  function rememberSpeakerAddDraft(generationId, value, conflictCode = null) {
    const generation = generationsFor(state.meeting && state.meeting.transcription)
      .find((item) => item.id === generationId);
    const bucket = transcriptDraftBucket(generationId, true);
    const previous = bucket.speakerAddName.get("speaker-add-name");
    const draft = {
      value,
      baseSourceVersion: previous ? previous.baseSourceVersion : Number(generation?.source_version) || 0,
      conflictCode: conflictCode || previous?.conflictCode || null,
    };
    bucket.speakerAddName.set("speaker-add-name", draft);
    return draft;
  }

  function clearSpeakerAddDraft(generationId) {
    const bucket = transcriptDraftBucket(generationId);
    if (!bucket) return;
    bucket.speakerAddName.delete("speaker-add-name");
    if (transcriptDraftBucketIsEmpty(bucket)) state.transcriptDrafts.delete(generationId);
  }

  function transcriptFieldValue(generationId, field, itemId) {
    const transcription = state.meeting && state.meeting.transcription;
    const generation = generationsFor(transcription).find((item) => item.id === generationId);
    if (!generation) return undefined;
    if (field === "segmentText" || field === "speakerAssignment") {
      const segment = generation.segments.find((item) => item.id === itemId);
      return segment && (field === "segmentText" ? segment.text : segment.speaker_id || "");
    }
    const speaker = generation.speakers.find((item) => item.speaker_id === itemId);
    return speaker && speaker.display_name;
  }

  function rememberTranscriptDraft(generationId, field, itemId, value, { reviewed = false } = {}) {
    const baseline = transcriptFieldValue(generationId, field, itemId);
    const generation = generationsFor(state.meeting && state.meeting.transcription)
      .find((item) => item.id === generationId);
    const sourceVersion = Number(generation && generation.source_version) || 0;
    const bucket = transcriptDraftBucket(generationId, true);
    const drafts = bucket[field];
    if (baseline === value) {
      drafts.delete(itemId);
      if (transcriptDraftBucketIsEmpty(bucket)) {
        state.transcriptDrafts.delete(generationId);
      }
      removeTranscriptDraftReview(generationId, field, itemId);
      return null;
    }
    const previous = drafts.get(itemId);
    const rebased = Boolean(
      reviewed
      && previous
      && previous.conflictCode === "source_version_changed"
      && (baseline !== previous.baseValue || sourceVersion > previous.baseSourceVersion)
    );
    const draft = {
      value,
      baseValue: rebased || !previous ? baseline : previous.baseValue,
      baseSourceVersion: rebased || !previous
        ? sourceVersion
        : previous.baseSourceVersion,
      conflictCode: rebased ? null : previous && previous.conflictCode,
    };
    drafts.set(itemId, draft);
    updateTranscriptDraftReview(generationId, field, itemId, draft, baseline);
    return draft;
  }

  function removeTranscriptDraftReview(generationId, field, itemId) {
    for (const review of document.querySelectorAll(".transcript-draft-review")) {
      if (
        review.dataset.generationId === generationId
        && review.dataset.draftField === field
        && review.dataset.draftItemId === itemId
      ) review.remove();
    }
  }

  function updateTranscriptDraftReview(generationId, field, itemId, draft, latestValue) {
    for (const review of document.querySelectorAll(".transcript-draft-review")) {
      if (
        review.dataset.generationId !== generationId
        || review.dataset.draftField !== field
        || review.dataset.draftItemId !== itemId
      ) continue;
      const latest = review.querySelector(".transcript-latest-value");
      if (latest && latestValue !== undefined) {
        const generation = generationsFor(state.meeting && state.meeting.transcription)
          .find((item) => item.id === generationId);
        latest.textContent = `Bản mới nhất đã lưu: ${draftReviewValue(field, latestValue, generation)}`;
      }
      const value = draftReviewValue(field, draft.value);
      review.querySelector(".transcript-draft-value").textContent = `Bản nháp chưa lưu: ${value}`;
    }
  }

  function transcriptSpeakerLabel(generation, speakerId) {
    if (!speakerId) return "Chưa xác định";
    const speaker = generation && generation.speakers.find((item) => item.speaker_id === speakerId);
    return speaker && speaker.display_name ? speaker.display_name : speakerId;
  }

  function draftReviewValue(field, value, generation = null) {
    if (field === "speakerName" && value === "") return "Khôi phục tên mặc định";
    if (field === "speakerAssignment") return transcriptSpeakerLabel(generation, value);
    return value;
  }

  function reconcileTranscriptDrafts(transcription, savedResult = null) {
    for (const [generationId, bucket] of state.transcriptDrafts) {
      const generation = generationsFor(transcription).find((item) => item.id === generationId);
      for (const [segmentId, draft] of bucket.segmentText) {
        const segment = generation && generation.segments.find((item) => item.id === segmentId);
        const saved = savedResult
          && savedResult.generationId === generationId
          && savedResult.field === "segmentText"
          && savedResult.itemId === segmentId
          && savedResult.draftValue === draft.value;
        if (saved || (segment && segment.text === draft.value)) {
          bucket.segmentText.delete(segmentId);
          removeTranscriptDraftReview(generationId, "segmentText", segmentId);
        } else if (segment && segment.text !== draft.baseValue) {
          draft.conflictCode = "source_version_changed";
        } else if (segment && draft.conflictCode === "source_version_changed") {
          draft.conflictCode = null;
        }
      }
      for (const [speakerId, draft] of bucket.speakerName) {
        const speaker = generation && generation.speakers.find((item) => item.speaker_id === speakerId);
        const saved = savedResult
          && savedResult.generationId === generationId
          && savedResult.field === "speakerName"
          && savedResult.itemId === speakerId
          && savedResult.draftValue === draft.value;
        if (saved || (speaker && speaker.display_name === draft.value)) {
          bucket.speakerName.delete(speakerId);
          removeTranscriptDraftReview(generationId, "speakerName", speakerId);
        } else if (speaker && speaker.display_name !== draft.baseValue) {
          draft.conflictCode = "source_version_changed";
        } else if (speaker && draft.conflictCode === "source_version_changed") {
          draft.conflictCode = null;
        }
      }
      for (const [segmentId, draft] of bucket.speakerAssignment) {
        const segment = generation && generation.segments.find((item) => item.id === segmentId);
        const saved = savedResult
          && savedResult.generationId === generationId
          && savedResult.field === "speakerAssignment"
          && savedResult.itemId === segmentId
          && savedResult.draftValue === draft.value;
        if (saved || (segment && (segment.speaker_id || "") === draft.value)) {
          bucket.speakerAssignment.delete(segmentId);
          removeTranscriptDraftReview(generationId, "speakerAssignment", segmentId);
        } else if (draft.conflictCode === "current_generation_changed") {
          // Keep the choice attached to its historical generation for review.
        } else if (segment && draft.conflictCode && draft.conflictCode !== "source_version_changed") {
          if (Number(generation.source_version) > (Number(draft.baseSourceVersion) || 0)) {
            draft.conflictCode = null;
          }
        } else if (segment && Number(generation.source_version) > (Number(draft.baseSourceVersion) || 0)) {
          draft.conflictCode = null;
        }
      }
      const currentGeneration = transcription && transcription.generation;
      for (const draft of bucket.speakerAddName.values()) {
        const currentGenerationChanged = currentGeneration && currentGeneration.id !== generationId;
        const sourceVersionAdvanced = currentGeneration
          && currentGeneration.id === generationId
          && Number(currentGeneration.source_version) > (Number(draft.baseSourceVersion) || 0);
        if (
          ["source_version_changed", "current_generation_changed"].includes(draft.conflictCode)
          && (currentGenerationChanged || sourceVersionAdvanced)
        ) {
          draft.conflictCode = null;
        }
      }
      if (transcriptDraftBucketIsEmpty(bucket)) {
        state.transcriptDrafts.delete(generationId);
      }
    }
  }

  function installServerMeeting(meeting) {
    const previous = state.meeting;
    if (!previous || !meeting || previous.id !== meeting.id) {
      state.notesCount = 0;
      state.notesKnown = false;
      state.notesTaskStatus = null;
    }
    if (meeting && typeof meeting.notes_source_locked === "boolean") {
      state.notesSourceLocked = meeting.notes_source_locked;
      state.notesSourceLockKnown = true;
    } else if (!previous || !meeting || previous.id !== meeting.id) {
      state.notesSourceLocked = false;
      state.notesSourceLockKnown = false;
    }
    const previousTranscription = previous && meeting && previous.id === meeting.id
      ? previous.transcription
      : null;
    const nextTranscription = meeting && meeting.transcription;
    if (previousTranscription && nextTranscription) {
      const merged = new Map(generationsFor(nextTranscription).map((item) => [item.id, item]));
      let current = nextTranscription.generation || null;
      const knownCurrent = previousTranscription.generation || null;
      for (const known of generationsFor(previousTranscription)) {
        const incoming = merged.get(known.id);
        const retained = !incoming
          || (Number(incoming.source_version) || 0) < (Number(known.source_version) || 0)
          ? known
          : incoming;
        merged.set(known.id, retained);
        if (
          knownCurrent
          && known.id === knownCurrent.id
          && (!current || known.generation_number > current.generation_number)
        ) {
          current = retained;
        } else if (current && current.id === known.id && retained !== current) {
          current = retained;
        }
      }
      nextTranscription.generation = current;
      nextTranscription.generation_history = [...merged.values()]
        .filter((item) => !current || item.id !== current.id)
        .sort((left, right) => left.generation_number - right.generation_number);
    }
    state.meeting = meeting;
    reconcileTranscriptDrafts(meeting && meeting.transcription);
    renderNotesSourceLock();
    notifyMeetingContext();
    return meeting;
  }

  function applyTranscriptMutationResult(
    meetingId,
    originalMeeting,
    generationId,
    field,
    itemId,
    draftValue,
    serverValue,
    sourceVersion,
  ) {
    const savedResult = { generationId, field, itemId, draftValue };
    const meeting = state.meeting;
    const transcription = meeting && meeting.id === meetingId ? meeting.transcription : null;
    const generation = generationsFor(transcription).find((item) => item.id === generationId);
    let appliedToRefreshedState = false;
    if (generation) {
      const item = field === "segmentText" || field === "speakerAssignment"
        ? generation.segments.find((segment) => segment.id === itemId)
        : generation.speakers.find((speaker) => speaker.speaker_id === itemId);
      const currentVersion = Number(generation.source_version) || 0;
      const resultVersion = Number(sourceVersion) || 0;
      if (item && resultVersion >= currentVersion) {
        const changed = field === "segmentText"
          ? item.text !== serverValue
          : field === "speakerAssignment"
            ? item.speaker_id !== serverValue.speaker_id
              || item.assignment_version !== serverValue.assignment_version
            : item.display_name !== serverValue;
        if (field === "segmentText") item.text = serverValue;
        else if (field === "speakerAssignment") {
          item.speaker_id = serverValue.speaker_id;
          item.assignment_version = serverValue.assignment_version;
        } else item.display_name = serverValue;
        if (resultVersion > currentVersion) generation.source_version = resultVersion;
        appliedToRefreshedState = meeting !== originalMeeting && (resultVersion > currentVersion || changed);
      }
    }
    reconcileTranscriptDrafts(transcription, savedResult);
    if (transcription) {
      const current = transcription.generation;
      renderTranscriptDraftRecovery(
        transcription,
        state.selectedGenerationId || (current && current.id),
      );
    }
    if (
      appliedToRefreshedState
      && state.view === "meeting"
      && state.selectedGenerationId === generation.id
    ) {
      const current = transcription.generation;
      const editable = Boolean(
        current && current.id === generation.id && generation.status === "complete",
      );
      if (editable && field === "speakerName") updateSpeakerLabelsInTranscript(generation, item);
      else if (editable) updateTranscriptRenderKey(generation);
      else renderTranscriptGeneration(generation, false);
    }
    notifyMeetingContext();
    return { meeting, generation };
  }

  function transcriptConflictCode(error) {
    const detail = error && error.payload && error.payload.detail;
    const code = detail && detail.code;
    return code === "source_version_changed" || code === "current_generation_changed"
      ? code
      : null;
  }

  function appendReloadLatestButton(container, generationId) {
    let button = container.querySelector("[data-reload-latest]");
    if (!button) {
      button = document.createElement("button");
      button.className = "secondary-button transcript-reload-latest";
      button.type = "button";
      button.dataset.reloadLatest = "true";
      button.dataset.transcriptMutation = "true";
      button.textContent = "Tải lại bản mới nhất";
      button.disabled = state.transcriptMutationInFlight || state.transcriptReloadInFlight;
      container.append(button);
    }
    button.dataset.generationId = generationId;
    let status = container.querySelector(".transcript-reload-status");
    if (!status) {
      status = document.createElement("span");
      status.className = "transcript-reload-status";
      status.setAttribute("role", "status");
      container.append(status);
    }
    return button;
  }

  function createTranscriptDraftReview(generationId, field, itemId, value, latestValue) {
    const review = document.createElement("div");
    review.className = "transcript-draft-review";
    review.dataset.generationId = generationId;
    review.dataset.draftField = field;
    review.dataset.draftItemId = itemId;
    if (latestValue !== undefined) {
      const latest = document.createElement("p");
      latest.className = "transcript-latest-value";
      const generation = generationsFor(state.meeting && state.meeting.transcription)
        .find((item) => item.id === generationId);
      latest.textContent = `Bản mới nhất đã lưu: ${draftReviewValue(field, latestValue, generation)}`;
      review.append(latest);
    }
    const draft = document.createElement("p");
    draft.className = "transcript-draft-value";
    const generation = generationsFor(state.meeting && state.meeting.transcription)
      .find((item) => item.id === generationId);
    const reviewValue = draftReviewValue(field, value, generation);
    draft.textContent = `Bản nháp chưa lưu: ${reviewValue}`;
    const copy = document.createElement("button");
    copy.className = "text-button transcript-copy-draft";
    copy.type = "button";
    copy.dataset.copyTranscriptDraft = "true";
    copy.dataset.generationId = generationId;
    copy.dataset.draftField = field;
    copy.dataset.draftItemId = itemId;
    copy.textContent = field === "speakerAssignment" ? "Xem transcript này" : "Sao chép bản nháp";
    if (field === "speakerAssignment") copy.dataset.openTranscriptDraft = "true";
    const status = document.createElement("span");
    status.className = "transcript-draft-copy-status";
    status.setAttribute("role", "status");
    review.append(draft, copy, status);
    return review;
  }

  function renderTranscriptDraftRecovery(transcription, selectedGenerationId) {
    const panel = $("#transcript-draft-recovery");
    const generations = generationsFor(transcription);
    const entries = [];
    for (const [generationId, bucket] of state.transcriptDrafts) {
      const generation = generations.find((item) => item.id === generationId);
      if (!generation) continue;
      if (generationId === selectedGenerationId) {
        for (const draft of bucket.speakerAddName.values()) {
          entries.push({
            generationId,
            generationNumber: generation.generation_number,
            field: "speakerAddName",
            value: draft.value,
            conflictCode: draft.conflictCode || "",
          });
        }
        continue;
      }
      for (const [segmentId, draft] of bucket.segmentText) {
        const segment = generation.segments.find((item) => item.id === segmentId);
        if (segment) entries.push({
          generationId,
          generationNumber: generation.generation_number,
          field: "segmentText",
          itemId: segmentId,
          value: draft.value,
          conflictCode: draft.conflictCode || "",
          latestValue: segment.text,
          startSeconds: segment.start_seconds,
        });
      }
      for (const draft of bucket.speakerAddName.values()) {
        entries.push({
          generationId,
          generationNumber: generation.generation_number,
          field: "speakerAddName",
          value: draft.value,
          conflictCode: draft.conflictCode || "",
        });
      }
      for (const [speakerId, draft] of bucket.speakerName) {
        const speaker = generation.speakers.find((item) => item.speaker_id === speakerId);
        if (speaker) entries.push({
          generationId,
          generationNumber: generation.generation_number,
          field: "speakerName",
          itemId: speakerId,
          value: draft.value,
          conflictCode: draft.conflictCode || "",
          latestValue: speaker.display_name,
        });
      }
      for (const [segmentId, draft] of bucket.speakerAssignment) {
        const segment = generation.segments.find((item) => item.id === segmentId);
        if (segment) entries.push({
          generationId,
          generationNumber: generation.generation_number,
          field: "speakerAssignment",
          itemId: segmentId,
          value: draft.value,
          conflictCode: draft.conflictCode || "",
          latestValue: segment.speaker_id || "",
          startSeconds: segment.start_seconds,
        });
      }
    }
    const renderKey = JSON.stringify(entries);
    panel.hidden = entries.length === 0;
    if (panel.dataset.renderKey === renderKey) return;
    panel.dataset.renderKey = renderKey;
    panel.replaceChildren();
    const sections = new Map();
    for (const entry of entries) {
      let section = sections.get(entry.generationId);
      if (!section) {
        section = document.createElement("section");
        section.className = "transcript-draft-generation";
        const heading = document.createElement("h5");
        heading.textContent = `Bản nháp chưa lưu · Transcript #${entry.generationNumber}`;
        section.append(heading);
        sections.set(entry.generationId, section);
        panel.append(section);
      }
      if (entry.field === "segmentText") {
        const context = document.createElement("p");
        context.className = "transcript-draft-context";
        context.textContent = `Đoạn bắt đầu tại ${formatTimestamp(entry.startSeconds)}`;
        section.append(
          context,
          createTranscriptDraftReview(
            entry.generationId,
            "segmentText",
            entry.itemId,
            entry.value,
            entry.latestValue,
          ),
        );
      } else if (entry.field === "speakerName") {
        const context = document.createElement("p");
        context.className = "transcript-draft-context";
        context.textContent = `Tên người nói · ${entry.itemId}`;
        section.append(
          context,
          createTranscriptDraftReview(
            entry.generationId,
            "speakerName",
            entry.itemId,
            entry.value,
            entry.latestValue,
          ),
        );
      } else if (entry.field === "speakerAssignment") {
        const context = document.createElement("p");
        context.className = "transcript-draft-context";
        context.textContent = `Người nói · đoạn bắt đầu tại ${formatTimestamp(entry.startSeconds)}`;
        section.append(
          context,
          createTranscriptDraftReview(
            entry.generationId,
            "speakerAssignment",
            entry.itemId,
            entry.value,
            entry.latestValue,
          ),
        );
      } else {
        const context = document.createElement("p");
        context.className = "transcript-draft-context";
        context.textContent = "Tên người nói chưa được thêm";
        const review = document.createElement("div");
        review.className = "transcript-draft-review transcript-speaker-add-draft-review";
        review.dataset.generationId = entry.generationId;
        review.dataset.draftField = "speakerAddName";
        const value = document.createElement("p");
        value.className = "transcript-draft-value";
        value.textContent = `Tên cần thêm: ${entry.value || "(để trống; máy chủ sẽ đặt tên mặc định)"}`;
        const apply = document.createElement("button");
        apply.type = "button";
        apply.className = "secondary-button transcript-reapply-speaker-add";
        apply.dataset.reapplySpeakerAddDraft = "true";
        apply.dataset.generationId = entry.generationId;
        apply.dataset.transcriptMutation = "true";
        const current = transcription && transcription.generation;
        const draft = transcriptDraft(entry.generationId, "speakerAddName", "speaker-add-name");
        apply.disabled = !speakerAddRecoveryReady(current, draft);
        apply.textContent = "Thêm vào transcript hiện tại";
        const status = document.createElement("span");
        status.className = "transcript-speaker-add-draft-status";
        status.setAttribute("role", "status");
        review.append(value, apply, status);
        section.append(context, review);
      }
    }
  }

  async function copyTranscriptDraft(button) {
    const draft = transcriptDraft(
      button.dataset.generationId,
      button.dataset.draftField,
      button.dataset.draftItemId,
    );
    if (!draft) return;
    const status = button.parentElement.querySelector(".transcript-draft-copy-status");
    try {
      if (!navigator.clipboard || !navigator.clipboard.writeText) throw new Error("Clipboard unavailable");
      await navigator.clipboard.writeText(draft.value);
      status.textContent = "Đã sao chép bản nháp.";
    } catch {
      const input = document.createElement("textarea");
      input.value = draft.value;
      input.setAttribute("readonly", "");
      input.style.position = "fixed";
      input.style.opacity = "0";
      document.body.append(input);
      input.focus();
      input.select();
      let copied = false;
      try {
        copied = document.execCommand("copy");
      } catch {
        // Keep the visible draft selectable when the clipboard command is unavailable.
      }
      input.remove();
      if (copied) {
        status.textContent = "Đã sao chép bản nháp.";
      } else {
        const selection = window.getSelection();
        const draftText = button.parentElement.querySelector(".transcript-draft-value");
        const range = document.createRange();
        range.selectNodeContents(draftText);
        selection.removeAllRanges();
        selection.addRange(range);
        status.textContent = "Bản nháp đã được chọn. Nhấn Ctrl+C hoặc ⌘C để sao chép.";
      }
    }
  }

  async function reloadLatestTranscript(button) {
    const previousMeeting = state.meeting;
    const meetingId = previousMeeting && previousMeeting.id;
    if (!meetingId || state.transcriptReloadInFlight || state.transcriptMutationInFlight) return;
    state.transcriptReloadInFlight = true;
    syncTranscriptMutationControls();
    try {
      const payload = await requestJson(`/api/meetings/${encodeURIComponent(meetingId)}`);
      if (state.meeting !== previousMeeting) return;
      const latest = payload && payload.meeting && typeof payload.meeting === "object"
        ? payload.meeting
        : payload;
      if (!latest || latest.id !== meetingId || !latest.transcription) {
        throw new Error("Không tải được trạng thái transcript mới nhất.");
      }
      installServerMeeting(latest);
      clearReloadLatestActions();
      state.transcriptMutationError = null;
      delete $("#transcript-generation").dataset.renderKey;
      renderTranscription(latest.transcription);
      renderSidebar();
    } catch (error) {
      if (button.isConnected) {
        const status = button.parentElement.querySelector(".transcript-reload-status");
        if (status) status.textContent = error && error.message
          ? error.message
          : "Không thể tải transcript mới nhất.";
      }
    } finally {
      state.transcriptReloadInFlight = false;
      syncTranscriptMutationControls();
    }
  }

  function clearSpeakerAddName() {
    const input = $("#speaker-add-name");
    if (input) input.value = "";
  }

  function renderGenerationNavigation(transcription) {
    const current = transcription && transcription.generation;
    const generations = generationsFor(transcription);
    const wrapper = $("#generation-navigation");
    const selector = $("#generation-selector");
    const previousSelectedGenerationId = state.selectedGenerationId;
    if (!generations.length) {
      wrapper.hidden = true;
      state.selectedGenerationId = null;
      state.currentGenerationId = null;
      if (previousSelectedGenerationId) clearSpeakerAddName();
      return null;
    }
    if (current && current.id !== state.currentGenerationId) {
      const previousCurrentId = state.currentGenerationId;
      state.currentGenerationId = current.id;
      if (!state.selectedGenerationId || state.selectedGenerationId === previousCurrentId) {
        state.selectedGenerationId = current.id;
      }
    }
    if (!generations.some((generation) => generation.id === state.selectedGenerationId)) {
      state.selectedGenerationId = current ? current.id : generations.at(-1).id;
    }
    if (
      previousSelectedGenerationId
      && previousSelectedGenerationId !== state.selectedGenerationId
    ) clearSpeakerAddName();
    const optionsKey = generations.map((generation) => generation.id).join(":");
    if (selector.dataset.optionsKey !== optionsKey) {
      selector.replaceChildren();
      for (const generation of generations) {
        const option = document.createElement("option");
        option.value = generation.id;
        option.textContent = `Transcript #${generation.generation_number}`
          + (current && current.id === generation.id ? " · hiện tại" : " · lịch sử");
        selector.append(option);
      }
      selector.dataset.optionsKey = optionsKey;
    }
    wrapper.hidden = generations.length < 2;
    selector.value = state.selectedGenerationId;
    return {
      generation: generations.find((generation) => generation.id === state.selectedGenerationId),
      editable: Boolean(
        current
        && current.id === state.selectedGenerationId
        && current.status === "complete",
      ),
    };
  }

  function renderSpeakerCatalog(generation, editable) {
    const list = $("#speaker-catalog-list");
    const speakers = Array.isArray(generation.speakers) ? generation.speakers : [];
    list.replaceChildren();
    $("#speaker-add-form").hidden = !editable;
    $("#speaker-add-status").textContent = "";
    $("#speaker-add-status").classList.remove("is-error");
    for (const speaker of speakers) list.append(buildSpeakerItem(generation, speaker, editable));
  }

  function speakerChipMark(text) {
    const mark = document.createElement("span");
    mark.className = "speaker-chip-mark";
    mark.textContent = text;
    return mark;
  }

  function buildSpeakerChip(generation, speaker, draft) {
    const chip = document.createElement("button");
    chip.className = "speaker-chip";
    chip.type = "button";
    chip.title = "Đổi tên người nói";
    chip.dataset.speakerChip = "true";
    chip.dataset.speakerId = speaker.speaker_id;
    chip.dataset.generationId = generation.id;
    chip.dataset.transcriptMutation = "true";
    const name = document.createElement("span");
    name.className = "speaker-chip-name";
    name.textContent = speaker.display_name || speaker.speaker_id;
    chip.append(name);
    if (DEFAULT_SPEAKER_NAME.test(speaker.display_name || "")) chip.append(speakerChipMark("đặt tên"));
    if (draft) chip.append(speakerChipMark("bản nháp"));
    return chip;
  }

  function buildSpeakerRenameForm(generation, speaker, draft) {
    const form = document.createElement("form");
    form.className = "speaker-name-form";
    form.dataset.speakerName = "true";
    form.dataset.speakerId = speaker.speaker_id;
    form.dataset.generationId = generation.id;
    const label = document.createElement("label");
    label.textContent = `Tên người nói · ${speaker.speaker_id}`;
    const input = document.createElement("input");
    input.type = "text";
    input.maxLength = 80;
    input.autocomplete = "off";
    input.value = draft ? draft.value : speaker.display_name || "";
    input.setAttribute("aria-label", `Tên hiển thị cho ${speaker.speaker_id}`);
    input.dataset.transcriptMutation = "true";
    label.append(input);
    const save = document.createElement("button");
    save.className = "secondary-button";
    save.type = "submit";
    save.dataset.transcriptMutation = "true";
    save.textContent = "Lưu tên";
    const cancel = document.createElement("button");
    cancel.className = "secondary-button";
    cancel.type = "button";
    cancel.dataset.editCancel = "true";
    cancel.dataset.speakerCancel = "true";
    cancel.setAttribute("aria-keyshortcuts", "Escape");
    cancel.textContent = "Hủy";
    const clear = document.createElement("button");
    clear.className = "text-button speaker-clear-name";
    clear.type = "button";
    clear.dataset.clearSpeakerName = "true";
    clear.dataset.speakerId = speaker.speaker_id;
    clear.dataset.generationId = generation.id;
    clear.dataset.transcriptMutation = "true";
    clear.textContent = "Khôi phục tên mặc định";
    const status = document.createElement("p");
    status.className = "speaker-form-status";
    status.dataset.speakerStatus = speaker.speaker_id;
    status.setAttribute("role", "status");
    form.append(label, save, cancel, clear, status);
    // Reopened after a conflict, the form offers the reload where the conflict first showed it.
    if (awaitsLatestReload(draft, speaker.display_name)) appendReloadLatestButton(form, generation.id);
    if (draft && draft.conflictCode) {
      form.append(
        createTranscriptDraftReview(
          generation.id,
          "speakerName",
          speaker.speaker_id,
          draft.value,
          speaker.display_name || speaker.speaker_id,
        ),
      );
    }
    return form;
  }

  // A chip in the current transcript opens an inline rename; one in a past transcript only reads.
  function buildSpeakerItem(generation, speaker, editable) {
    const item = document.createElement("li");
    item.className = "speaker-chip-item";
    item.dataset.speakerId = speaker.speaker_id;
    const draft = transcriptDraft(generation.id, "speakerName", speaker.speaker_id);
    if (!editable) {
      const name = document.createElement("span");
      name.className = "speaker-chip speaker-name-readonly";
      name.textContent = speaker.display_name || speaker.speaker_id;
      item.append(name);
      if (draft) {
        item.append(
          createTranscriptDraftReview(generation.id, "speakerName", speaker.speaker_id, draft.value),
        );
      }
    } else if (isRenamingSpeaker(generation.id, speaker.speaker_id)) {
      item.classList.add("is-renaming");
      item.append(buildSpeakerRenameForm(generation, speaker, draft));
    } else {
      item.append(buildSpeakerChip(generation, speaker, draft));
    }
    return item;
  }

  function speakerItem(speakerId) {
    return [...$("#speaker-catalog-list").children].find((item) => item.dataset.speakerId === speakerId) || null;
  }

  // Swap one speaker between chip and rename form; the other speakers stay untouched.
  function replaceSpeakerItem(generationId, speakerId) {
    const { generation, editable } = displayedGeneration();
    if (!generation || generation.id !== generationId) return null;
    const speaker = generation.speakers.find((item) => item.speaker_id === speakerId);
    const current = speakerItem(speakerId);
    if (!speaker || !current) return null;
    const item = buildSpeakerItem(generation, speaker, editable);
    current.replaceWith(item);
    if (editable) {
      const renaming = isRenamingSpeaker(generationId, speakerId);
      placeLatestReload(generationId, "speakerName", speakerId, speaker.display_name, renaming);
    }
    syncTranscriptMutationControls();
    return item;
  }

  function openSpeakerRename(speakerId) {
    const { generation, editable } = displayedGeneration();
    if (!editable || sourceMutationUnavailable() || state.transcriptMutationInFlight) return;
    const previous = state.renamingSpeaker;
    state.renamingSpeaker = { generationId: generation.id, speakerId };
    // One rename at a time: the one it leaves keeps its unsaved name as a draft.
    if (previous && previous.speakerId !== speakerId) {
      replaceSpeakerItem(previous.generationId, previous.speakerId);
    }
    const input = replaceSpeakerItem(generation.id, speakerId)?.querySelector("input");
    if (input) {
      input.focus();
      input.select();
    }
  }

  // Leave the rename and hand back the speaker's chip. `discard` is the Hủy path: it drops the typed
  // name, unless that name is a conflict-marked draft; the chip then stays marked for review.
  function closeSpeakerRename(generationId, speakerId, { discard = false } = {}) {
    if (isRenamingSpeaker(generationId, speakerId)) state.renamingSpeaker = null;
    if (discard && !isConflictedDraft(generationId, "speakerName", speakerId)) {
      rememberTranscriptDraft(
        generationId,
        "speakerName",
        speakerId,
        transcriptFieldValue(generationId, "speakerName", speakerId),
      );
    }
    return replaceSpeakerItem(generationId, speakerId)?.querySelector(".speaker-chip") || null;
  }

  function cancelSpeakerRename(speakerId) {
    const renaming = state.renamingSpeaker;
    if (!renaming || renaming.speakerId !== speakerId || state.transcriptMutationInFlight) return;
    const chip = closeSpeakerRename(renaming.generationId, speakerId, { discard: true });
    if (chip && !chip.disabled) chip.focus();
  }

  function renderTranscriptGeneration(generation, editable) {
    const panel = $("#transcript-generation");
    const list = $("#transcript-segments");
    panel.hidden = !generation;
    if (!generation) {
      list.replaceChildren();
      $("#speaker-catalog-list").replaceChildren();
      delete panel.dataset.renderKey;
      return;
    }
    // Lock changes affect controls and the mode label, not transcript content.
    // Keep the content key consistent with incremental save reconciliation.
    const renderKey = `${generation.id}:${generation.source_version}:${editable}`;
    const mode = $("#generation-mode");
    mode.textContent = editable && !state.notesSourceLockKnown
      ? "Bản hiện tại · Đang kiểm tra khóa nguồn trước khi cho phép chỉnh sửa."
      : editable && state.notesSourceLocked
        ? "Bản hiện tại · Tác vụ notes đang dùng nguồn; chỉnh sửa tạm thời bị khóa."
        : editable
          ? "Bản hiện tại · Bạn có thể chỉnh sửa transcript và người nói."
          : "Bản lịch sử · Chỉ đọc.";
    mode.classList.toggle("is-readonly", !editable || sourceMutationUnavailable());
    if (panel.dataset.renderKey === renderKey) {
      updateActiveTranscriptIntervals();
      return;
    }
    list.replaceChildren();
    panel.dataset.renderKey = renderKey;

    $("#generation-title").textContent = `Transcript #${generation.generation_number}`;
    const meta = [
      `Gợi ý: ${LANGUAGES[generation.language_hint] || generation.language_hint}`,
      generation.model_name,
      `${generation.segment_count} đoạn`,
    ].filter(Boolean);
    if (typeof generation.language_probability === "number") {
      meta.push(`language_probability ${generation.language_probability.toFixed(3)}`);
    }
    if (generation.diarization_model_name) meta.push(`Diarization · ${generation.diarization_model_name}`);
    $("#generation-meta").textContent = meta.join(" · ");
    renderSpeakerCatalog(generation, editable);

    const segments = Array.isArray(generation.segments) ? generation.segments : [];
    $("#transcript-empty").hidden = segments.length > 0;
    for (const segment of segments) list.append(buildSegmentRow(generation, segment, editable));
    if (state.transcriptMutationInFlight) setTranscriptMutationInFlight(true);
    updateActiveTranscriptIntervals();
  }

  function buildOriginalSpeaker(segment, speakerNames) {
    const originalSpeaker = document.createElement("span");
    originalSpeaker.className = "segment-original-speaker";
    originalSpeaker.dataset.originalSpeakerId = segment.original_speaker_id || "";
    originalSpeaker.textContent = `Gán ban đầu: ${segment.original_speaker_id
      ? speakerNames.get(segment.original_speaker_id) || segment.original_speaker_id
      : "Chưa xác định"}`;
    return originalSpeaker;
  }

  // A segment that shows the review cue is one the Transcript tab counts as "cần kiểm tra".
  function needsReview(segment) {
    return Boolean(segment.uncertain) || (Array.isArray(segment.review_reasons) && segment.review_reasons.length > 0);
  }

  function buildReviewCue(segment) {
    if (!needsReview(segment)) return null;
    const reasons = Array.isArray(segment.review_reasons) ? segment.review_reasons : [];
    const reviewCue = document.createElement("span");
    reviewCue.className = "segment-review-cue";
    reviewCue.textContent = reasons.length
      ? `Cần kiểm tra · ${reasons.map((reason) => REVIEW_REASON_LABELS[reason] || reason).join(" · ")}`
      : "Nên nghe lại";
    return reviewCue;
  }

  function buildModelMeasures(segment) {
    const measures = [];
    if (typeof segment.avg_logprob === "number") measures.push(`avg_logprob ${segment.avg_logprob.toFixed(3)}`);
    if (typeof segment.no_speech_prob === "number") measures.push(`no_speech_prob ${segment.no_speech_prob.toFixed(3)}`);
    if (typeof segment.compression_ratio === "number") measures.push(`compression_ratio ${segment.compression_ratio.toFixed(3)}`);
    if (!measures.length) return null;
    const modelMeasures = document.createElement("span");
    modelMeasures.className = "segment-model-measures";
    modelMeasures.textContent = `Chỉ số model, không phải độ chính xác đã hiệu chuẩn: ${measures.join(" · ")}`;
    return modelMeasures;
  }

  // The origin and the model's own measures sit behind "Chi tiết": in the open editor, or, with no
  // editor to hold them, in a past transcript's rows.
  function buildSegmentDetails(segment, speakerNames) {
    const details = document.createElement("details");
    details.className = "segment-details";
    const summary = document.createElement("summary");
    summary.textContent = "Chi tiết";
    details.append(summary, buildOriginalSpeaker(segment, speakerNames));
    const modelMeasures = buildModelMeasures(segment);
    if (modelMeasures) details.append(modelMeasures);
    return details;
  }

  function buildEditButton(segment, hasDraft) {
    const button = document.createElement("button");
    button.className = "secondary-button segment-edit-button";
    button.type = "button";
    button.dataset.editSegment = "true";
    button.dataset.transcriptMutation = "true";
    button.textContent = "Sửa";
    button.setAttribute(
      "aria-label",
      `Sửa đoạn bắt đầu tại ${formatTimestamp(segment.start_seconds)}${hasDraft ? " (có bản nháp chưa lưu)" : ""}`,
    );
    return button;
  }

  function buildSpeakerControl(generation, segment, assignmentDraft) {
    const speakers = Array.isArray(generation.speakers) ? generation.speakers : [];
    const speakerControl = document.createElement("div");
    speakerControl.className = "segment-speaker-control";
    const speakerLabel = document.createElement("span");
    speakerLabel.textContent = "Người nói";
    const speakerSelect = document.createElement("select");
    speakerSelect.className = "segment-speaker-select";
    speakerSelect.dataset.speakerAssignment = "true";
    speakerSelect.dataset.segmentId = segment.id;
    speakerSelect.dataset.currentSpeaker = segment.speaker_id || "";
    speakerSelect.dataset.generationId = generation.id;
    speakerSelect.dataset.assignmentVersion = String(segment.assignment_version || 1);
    speakerSelect.dataset.transcriptMutation = "true";
    speakerSelect.setAttribute(
      "aria-label",
      `Người nói cho đoạn bắt đầu tại ${formatTimestamp(segment.start_seconds)}`,
    );
    const unidentified = document.createElement("option");
    unidentified.value = "";
    unidentified.textContent = "Chưa xác định";
    speakerSelect.append(unidentified);
    for (const speaker of speakers) {
      const option = document.createElement("option");
      option.value = speaker.speaker_id;
      option.textContent = speaker.display_name || speaker.speaker_id;
      speakerSelect.append(option);
    }
    speakerSelect.value = assignmentDraft ? assignmentDraft.value : segment.speaker_id || "";
    speakerControl.append(speakerLabel, speakerSelect);
    return speakerControl;
  }

  function buildSegmentEditForm(generation, segment, draft) {
    const form = document.createElement("form");
    form.className = "segment-edit-form";
    form.dataset.segmentText = "true";
    form.dataset.segmentId = segment.id;
    form.dataset.generationId = generation.id;
    const editor = document.createElement("textarea");
    editor.className = "segment-text-editor";
    editor.maxLength = 10000;
    editor.rows = 3;
    editor.value = draft ? draft.value : segment.text;
    editor.setAttribute(
      "aria-label",
      `Nội dung transcript cho đoạn bắt đầu tại ${formatTimestamp(segment.start_seconds)}`,
    );
    editor.dataset.transcriptMutation = "true";
    const actions = document.createElement("div");
    actions.className = "segment-edit-actions";
    const save = document.createElement("button");
    save.className = "secondary-button";
    save.type = "submit";
    save.dataset.transcriptMutation = "true";
    save.setAttribute("aria-keyshortcuts", "Control+Enter Meta+Enter");
    save.title = "Ctrl/⌘+Enter";
    save.textContent = "Lưu đoạn";
    const cancel = document.createElement("button");
    cancel.className = "secondary-button";
    cancel.type = "button";
    cancel.dataset.editCancel = "true";
    cancel.dataset.segmentCancel = "true";
    cancel.setAttribute("aria-keyshortcuts", "Escape");
    cancel.title = "Esc";
    cancel.textContent = "Hủy";
    // Plain text, no role: every save is announced once, by the shared #transcript-mutation-status.
    const status = document.createElement("p");
    status.className = "segment-edit-status";
    actions.append(save, cancel, status);
    // Reopened after a conflict, the editor offers the reload where the conflict first showed it.
    if (awaitsLatestReload(draft, segment.text)) appendReloadLatestButton(actions, generation.id);
    form.append(editor, actions);
    return form;
  }

  // Read mode shows what a reader needs; the editor and speaker select exist only while a segment
  // is being edited. A past transcript has no editor: its rows stay read-only.
  function buildSegmentRow(generation, segment, editable) {
    const speakerNames = new Map(
      (Array.isArray(generation.speakers) ? generation.speakers : [])
        .map((speaker) => [speaker.speaker_id, speaker.display_name]),
    );
    const editing = editable && isEditingSegment(generation.id, segment.id);
    const textDraft = transcriptDraft(generation.id, "segmentText", segment.id);
    const assignmentDraft = transcriptDraft(generation.id, "speakerAssignment", segment.id);
    const hasDraft = hasSegmentDraft(generation.id, segment.id);

    const item = document.createElement("li");
    item.className = editing ? "transcript-segment is-editing" : "transcript-segment";
    item.dataset.segmentId = segment.id;
    item.dataset.startSeconds = String(segment.start_seconds);
    item.dataset.endSeconds = String(segment.end_seconds);

    const timestamp = document.createElement("button");
    timestamp.className = "segment-timestamp";
    timestamp.type = "button";
    timestamp.dataset.seekSeconds = String(segment.start_seconds);
    timestamp.textContent = formatTimestamp(segment.start_seconds);
    timestamp.setAttribute(
      "aria-label",
      `Phát bản ghi từ ${formatTimestamp(segment.start_seconds)}`,
    );

    const head = document.createElement("div");
    head.className = "segment-head";
    if (editing) {
      head.append(buildSpeakerControl(generation, segment, assignmentDraft));
    } else {
      const speakerName = document.createElement("span");
      speakerName.className = "segment-speaker";
      speakerName.dataset.speakerId = segment.speaker_id || "";
      speakerName.textContent = segment.speaker_id
        ? speakerNames.get(segment.speaker_id) || segment.speaker_id
        : "Chưa xác định";
      head.append(speakerName);
      if (editable) head.append(buildEditButton(segment, hasDraft));
    }
    item.append(timestamp, head);
    if (assignmentDraft && (editing || !editable)) {
      item.append(createAssignmentDraftReview(generation, segment, assignmentDraft, editable));
    }

    if (editing) {
      item.append(buildSegmentEditForm(generation, segment, textDraft));
      if (textDraft && textDraft.conflictCode) {
        item.append(
          createTranscriptDraftReview(
            generation.id,
            "segmentText",
            segment.id,
            textDraft.value,
            segment.text,
          ),
        );
      }
    } else {
      const text = document.createElement("p");
      text.className = "segment-text";
      text.textContent = segment.text;
      item.append(text);
      if (!editable && textDraft) {
        item.append(
          createTranscriptDraftReview(generation.id, "segmentText", segment.id, textDraft.value),
        );
      }
    }

    const reviewCue = buildReviewCue(segment);
    if (reviewCue) item.append(reviewCue);
    if (editing || !editable) {
      item.append(buildSegmentDetails(segment, speakerNames));
    } else if (hasDraft) {
      const draftMark = document.createElement("span");
      draftMark.className = "segment-draft-mark";
      draftMark.textContent = "Bản nháp chưa lưu";
      item.append(draftMark);
    }
    return item;
  }

  function segmentRow(segmentId) {
    return [...$("#transcript-segments").children].find((item) => item.dataset.segmentId === segmentId) || null;
  }

  // Swap one row between read mode and editor; every other row stays as it is.
  function replaceSegmentRow(generationId, segmentId) {
    const { generation, editable } = displayedGeneration();
    if (!generation || generation.id !== generationId) return null;
    const segment = generation.segments.find((item) => item.id === segmentId);
    const current = segmentRow(segmentId);
    if (!segment || !current) return null;
    const row = buildSegmentRow(generation, segment, editable);
    current.replaceWith(row);
    if (editable) {
      const editing = isEditingSegment(generationId, segmentId);
      placeLatestReload(generationId, "segmentText", segmentId, segment.text, editing);
    }
    syncTranscriptMutationControls();
    updateActiveTranscriptIntervals();
    return row;
  }

  function openSegmentEditor(segmentId) {
    const { generation, editable } = displayedGeneration();
    if (!editable || sourceMutationUnavailable() || state.transcriptMutationInFlight) return;
    const previous = state.editingSegment;
    state.editingSegment = { generationId: generation.id, segmentId };
    // One editor at a time: the row it leaves keeps its unsaved text in the draft store.
    if (previous && previous.segmentId !== segmentId) {
      replaceSegmentRow(previous.generationId, previous.segmentId);
    }
    const editor = replaceSegmentRow(generation.id, segmentId)?.querySelector(".segment-text-editor");
    if (editor) {
      editor.focus();
      editor.setSelectionRange(editor.value.length, editor.value.length);
    }
  }

  // Leave the editor and hand back the row's Sửa button. `discard` is the Hủy path: it drops the typed
  // text, unless that text is a conflict-marked draft; the row then stays marked for review.
  function closeSegmentEditor(generationId, segmentId, { discard = false } = {}) {
    if (isEditingSegment(generationId, segmentId)) state.editingSegment = null;
    if (discard && !isConflictedDraft(generationId, "segmentText", segmentId)) {
      rememberTranscriptDraft(
        generationId,
        "segmentText",
        segmentId,
        transcriptFieldValue(generationId, "segmentText", segmentId),
      );
    }
    return replaceSegmentRow(generationId, segmentId)?.querySelector(".segment-edit-button") || null;
  }

  function cancelSegmentEditor(segmentId) {
    const editing = state.editingSegment;
    if (!editing || editing.segmentId !== segmentId || state.transcriptMutationInFlight) return;
    const button = closeSegmentEditor(editing.generationId, segmentId, { discard: true });
    // A locked source disables Sửa; keep the keyboard on the row instead of dropping it to the page.
    const target = button && !button.disabled
      ? button
      : button?.closest(".transcript-segment").querySelector(".segment-timestamp");
    if (target) target.focus();
  }

  function createAssignmentDraftReview(generation, segment, draft, editable) {
    const review = document.createElement("div");
    review.className = "transcript-draft-review transcript-assignment-draft-review";
    review.dataset.generationId = generation.id;
    review.dataset.draftField = "speakerAssignment";
    review.dataset.draftItemId = segment.id;
    const latest = document.createElement("p");
    latest.className = "transcript-latest-value";
    latest.textContent = `Người nói đã lưu: ${transcriptSpeakerLabel(generation, segment.speaker_id || "")}`;
    const value = document.createElement("p");
    value.className = "transcript-draft-value";
    value.textContent = `Lựa chọn cần xem lại: ${transcriptSpeakerLabel(generation, draft.value)}`;
    review.append(latest, value);
    if (editable) {
      const apply = document.createElement("button");
      apply.type = "button";
      apply.className = "secondary-button transcript-reapply-assignment";
      apply.dataset.reapplyAssignmentDraft = "true";
      apply.dataset.generationId = generation.id;
      apply.dataset.segmentId = segment.id;
      apply.dataset.transcriptMutation = "true";
      apply.disabled = Boolean(draft.conflictCode) || state.transcriptMutationInFlight;
      apply.textContent = "Áp dụng lại lựa chọn";
      const status = document.createElement("span");
      status.className = "transcript-assignment-draft-status";
      status.setAttribute("role", "status");
      review.append(apply, status);
    }
    return review;
  }

  function updateAssignmentDraftReviewLabels(generation) {
    for (const review of document.querySelectorAll(".transcript-assignment-draft-review")) {
      if (review.dataset.generationId !== generation.id) continue;
      const segmentId = review.dataset.draftItemId;
      const segment = generation.segments.find((item) => item.id === segmentId);
      const draft = transcriptDraft(generation.id, "speakerAssignment", segmentId);
      if (!segment || !draft) continue;
      review.querySelector(".transcript-latest-value").textContent =
        `Người nói đã lưu: ${transcriptSpeakerLabel(generation, segment.speaker_id || "")}`;
      review.querySelector(".transcript-draft-value").textContent =
        `Lựa chọn cần xem lại: ${transcriptSpeakerLabel(generation, draft.value)}`;
    }
  }

  function updateTranscriptRenderKey(generation) {
    if (!generation || $("#generation-title").textContent !== `Transcript #${generation.generation_number}`) return;
    $("#transcript-generation").dataset.renderKey = `${generation.id}:${generation.source_version}:true`;
  }

  // The active segment follows playback while the transcript list is on screen, unless the user took
  // over the scroll in the last two seconds. A wheel, a touch move, a scroll key or any scroll the
  // app did not start counts as theirs.
  const MANUAL_SCROLL_QUIET_MS = 2000;
  const OWN_SCROLL_GAP_MS = 200; // a scroll event this soon after our scroll, or its last event, is ours
  const SCROLL_KEYS = new Set([" ", "ArrowUp", "ArrowDown", "PageUp", "PageDown", "Home", "End"]);
  let lastManualScroll = -Infinity;
  let ownScrollUntil = 0;
  let activeSegmentId = null;

  function followsPlayback(audio) {
    if (audio.paused || audio.ended) return false;
    if (performance.now() - lastManualScroll < MANUAL_SCROLL_QUIET_MS) return false;
    // Reading the notes while audio plays must not pull the page to the transcript: follow only
    // while some of the list shows below the player bar.
    const bar = $(".player-bar").getBoundingClientRect();
    const list = $("#transcript-segments").getBoundingClientRect();
    if (list.bottom <= bar.bottom || list.top >= window.innerHeight) return false;
    const focused = document.activeElement;
    return !(
      focused
      && focused.closest("#transcription-panel")
      && (focused.matches("textarea, input, select") || focused.isContentEditable)
    );
  }

  function updateActiveTranscriptIntervals() {
    const audio = $("#meeting-audio");
    const seconds = audio.currentTime;
    const items = [...$("#transcript-segments").querySelectorAll(".transcript-segment")];
    let current = null;
    for (const [index, item] of items.entries()) {
      const start = Number(item.dataset.startSeconds);
      const end = Number(item.dataset.endSeconds);
      const withinEnd = seconds < end || (index === items.length - 1 && seconds <= end);
      const active = Number.isFinite(seconds) && seconds >= start && withinEnd;
      item.classList.toggle("is-playback-active", active);
      if (active) item.setAttribute("aria-current", "true");
      else item.removeAttribute("aria-current");
      if (active && !current) current = item;
    }
    // Compare ids, not elements: a re-render of the same transcript is not a new active segment.
    const currentId = current ? current.dataset.segmentId : null;
    const changed = currentId !== null && currentId !== activeSegmentId;
    activeSegmentId = currentId;
    if (!changed || !followsPlayback(audio)) return;
    ownScrollUntil = performance.now() + OWN_SCROLL_GAP_MS;
    current.scrollIntoView({
      block: "nearest",
      behavior: window.matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth",
    });
  }

  function transcriptMutationMessage(error, fallback) {
    const code = error && error.payload && error.payload.detail && error.payload.detail.code;
    if (code === "source_version_changed") {
      return "Transcript đã thay đổi. Bản nháp vẫn được giữ; hãy xem lại trước khi lưu lần nữa.";
    }
    if (code === "current_generation_changed") {
      return "Phiên bản này không còn là bản hiện tại. Bản nháp vẫn được giữ để xem lại và thêm vào transcript hiện tại.";
    }
    return error && error.message ? error.message : fallback;
  }

  function markTranscriptDraftConflict(generationId, field, itemId, code, status) {
    const draft = transcriptDraft(generationId, field, itemId);
    if (draft) draft.conflictCode = code;
    if (status && status.isConnected) {
      appendReloadLatestButton(status.parentElement, generationId);
      return;
    }
    showTranscriptConflictNotice(generationId, code);
  }

  function showTranscriptConflictNotice(generationId, code) {
    const message = code === "source_version_changed"
      ? "Transcript đã thay đổi. Bản nháp vẫn được giữ để xem lại."
      : "Phiên bản transcript đã đổi. Bản nháp vẫn được giữ để sao chép.";
    const meetingId = state.meeting && state.meeting.id;
    if (meetingId) setTranscriptMutationError(meetingId, generationId, message, true);
  }

  function clearReloadLatestActions() {
    for (const container of [
      $("#transcript-generation"),
      $("#transcription-error"),
      $("#transcript-mutation-error"),
    ]) {
      for (const action of container.querySelectorAll("[data-reload-latest], .transcript-reload-status")) {
        action.remove();
      }
    }
  }

  function clearReloadLatestAction(container) {
    for (const action of container.querySelectorAll("[data-reload-latest], .transcript-reload-status")) {
      action.remove();
    }
  }

  function setTranscriptMutationInFlight(inFlight, statusSource = null) {
    if (inFlight && !state.transcriptMutationInFlight) {
      const active = document.activeElement;
      state.transcriptMutationFocus = active
        && active.matches("[data-transcript-mutation]")
        ? active
        : null;
      state.transcriptMutationFocusDescriptor = state.transcriptMutationFocus
        ? describeTranscriptMutationFocus(state.transcriptMutationFocus)
        : null;
      state.transcriptMutationStatusDescriptor = describeTranscriptMutationFocus(
        statusSource || active,
      );
    }
    state.transcriptMutationInFlight = inFlight;
    syncTranscriptMutationControls();
    if (!inFlight) {
      const previousFocus = state.transcriptMutationFocus;
      const descriptor = state.transcriptMutationFocusDescriptor;
      const sameMeeting = !descriptor
        || (state.meeting && descriptor.meetingId === state.meeting.id);
      let focusTarget = sameMeeting ? state.transcriptMutationFocusAfter || previousFocus : null;
      if ((!focusTarget || !focusTarget.isConnected) && state.transcriptMutationFocusDescriptor) {
        focusTarget = resolveTranscriptMutationFocus(descriptor);
      }
      state.transcriptMutationFocus = null;
      state.transcriptMutationFocusAfter = null;
      state.transcriptMutationFocusDescriptor = null;
      state.transcriptMutationStatusDescriptor = null;
      if (
        focusTarget
        && focusTarget.isConnected
        && (
          document.activeElement === document.body
          || document.activeElement === previousFocus
          || document.activeElement === focusTarget
        )
      ) focusTarget.focus({ preventScroll: true });
    }
  }

  function describeTranscriptMutationFocus(element) {
    const meetingId = state.meeting && state.meeting.id;
    if (element.id === "speaker-add-name") {
      return { kind: "speaker-add", control: "input", meetingId };
    }
    if (element.closest("[data-reapply-speaker-add-draft]")) {
      return { kind: "speaker-add", control: "submit", meetingId };
    }
    const assignmentReview = element.closest("[data-reapply-assignment-draft]");
    if (assignmentReview) {
      return {
        kind: "speaker-assignment",
        meetingId,
        generationId: assignmentReview.dataset.generationId,
        segmentId: assignmentReview.dataset.segmentId,
      };
    }
    const assignment = element.closest(".segment-speaker-select");
    if (assignment) {
      return {
        kind: "speaker-assignment",
        meetingId,
        generationId: assignment.dataset.generationId,
        segmentId: assignment.dataset.segmentId,
      };
    }
    const textForm = element.closest("form[data-segment-text]");
    if (textForm) {
      return {
        kind: "segment-text",
        meetingId,
        generationId: textForm.dataset.generationId,
        segmentId: textForm.dataset.segmentId,
        control: element.matches(".segment-text-editor") ? "editor" : "submit",
      };
    }
    const speakerForm = element.closest("form[data-speaker-name]");
    if (speakerForm) {
      return {
        kind: "speaker-name",
        meetingId,
        generationId: speakerForm.dataset.generationId,
        speakerId: speakerForm.dataset.speakerId,
        control: element.matches(".speaker-clear-name")
          ? "clear"
          : element.matches("input") ? "input" : "submit",
      };
    }
    const addForm = element.closest("#speaker-add-form");
    if (addForm) return { kind: "speaker-add", control: "submit", meetingId };
    return null;
  }

  function resolveTranscriptMutationFocus(descriptor) {
    if (!state.meeting || descriptor.meetingId !== state.meeting.id) return null;
    if (descriptor.kind === "speaker-add") {
      return descriptor.control === "input"
        ? $("#speaker-add-name")
        : $("#speaker-add-form button[type='submit']");
    }
    if (descriptor.kind === "speaker-assignment") {
      return [...document.querySelectorAll(".segment-speaker-select")].find(
        (element) => element.dataset.generationId === descriptor.generationId
          && element.dataset.segmentId === descriptor.segmentId,
      ) || null;
    }
    if (descriptor.kind === "segment-text") {
      const form = [...document.querySelectorAll("form[data-segment-text]")].find(
        (element) => element.dataset.generationId === descriptor.generationId
          && element.dataset.segmentId === descriptor.segmentId,
      );
      return form && form.querySelector(
        descriptor.control === "editor" ? ".segment-text-editor" : "button[type='submit']",
      );
    }
    if (descriptor.kind === "speaker-name") {
      const form = [...document.querySelectorAll("form[data-speaker-name]")].find(
        (element) => element.dataset.generationId === descriptor.generationId
          && element.dataset.speakerId === descriptor.speakerId,
      );
      if (!form) return null;
      if (descriptor.control === "input") return form.querySelector("input");
      return form.querySelector(
        descriptor.control === "clear" ? ".speaker-clear-name" : "button[type='submit']",
      );
    }
    return null;
  }

  function resolveTranscriptMutationStatus(descriptor, fallback) {
    if (descriptor && state.meeting && descriptor.meetingId !== state.meeting.id) return null;
    if (fallback && fallback.isConnected) return fallback;
    if (!descriptor || !state.meeting) return null;
    if (descriptor.kind === "segment-text") {
      const form = [...document.querySelectorAll("form[data-segment-text]")].find(
        (element) => element.dataset.generationId === descriptor.generationId
          && element.dataset.segmentId === descriptor.segmentId,
      );
      return form && form.querySelector(".segment-edit-status");
    }
    if (descriptor.kind === "speaker-name") {
      const form = [...document.querySelectorAll("form[data-speaker-name]")].find(
        (element) => element.dataset.generationId === descriptor.generationId
          && element.dataset.speakerId === descriptor.speakerId,
      );
      return form && form.querySelector(".speaker-form-status");
    }
    if (descriptor.kind === "speaker-add") return $("#speaker-add-status");
    return null;
  }

  function reportTranscriptMutation(descriptor, fallback, message, isError = false) {
    const target = resolveTranscriptMutationStatus(descriptor, fallback);
    if (target) {
      target.classList.toggle("is-error", isError);
      target.textContent = message;
    }
    const globalStatus = $("#transcript-mutation-status");
    const sameMeeting = !descriptor || !state.meeting || descriptor.meetingId === state.meeting.id;
    globalStatus.textContent = sameMeeting ? message : "Thay đổi transcript đã hoàn tất.";
    globalStatus.hidden = false;
    return target;
  }

  function syncTranscriptMutationControls() {
    for (const control of document.querySelectorAll(
      "#transcript-generation [data-transcript-mutation], "
      + "#transcription-error [data-transcript-mutation], "
      + "#transcript-mutation-error [data-transcript-mutation], "
      + "#transcript-draft-recovery [data-transcript-mutation]",
    )) {
      const currentGeneration = state.meeting && state.meeting.transcription
        && state.meeting.transcription.generation;
      const addFormControl = control.closest("#speaker-add-form")
        && !control.matches("[data-reload-latest]");
      const addRecoveryControl = control.matches("[data-reapply-speaker-add-draft]");
      if (addFormControl || addRecoveryControl) {
        const generationId = addRecoveryControl
          ? control.dataset.generationId
          : currentGeneration && currentGeneration.id;
        const draft = generationId
          ? transcriptDraft(generationId, "speakerAddName", "speaker-add-name")
          : null;
        control.disabled = !speakerAddRecoveryReady(currentGeneration, draft);
        continue;
      }
      if (control.matches("#generation-selector, [data-reload-latest]")) {
        control.disabled = state.transcriptMutationInFlight
          || (control.matches("[data-reload-latest]") && state.transcriptReloadInFlight);
        continue;
      }
      const assignmentDraft = control.matches("[data-reapply-assignment-draft]")
        ? transcriptDraft(control.dataset.generationId, "speakerAssignment", control.dataset.segmentId)
        : null;
      control.disabled = sourceMutationUnavailable()
        || state.transcriptMutationInFlight
        || (control.matches("[data-reload-latest]") && state.transcriptReloadInFlight)
        || Boolean(assignmentDraft && assignmentDraft.conflictCode);
      if (control.matches("[data-edit-segment], [data-speaker-chip]")) {
        // A locked source says why in #generation-mode; tie that reason to the disabled control.
        if (sourceMutationUnavailable()) control.setAttribute("aria-describedby", "generation-mode");
        else control.removeAttribute("aria-describedby");
      }
    }
    // Hủy only drops local text, so a locked source leaves it usable; a save in flight does not.
    for (const cancel of document.querySelectorAll("#transcript-generation [data-edit-cancel]")) {
      cancel.disabled = state.transcriptMutationInFlight;
    }
    $("#transcript-generation").setAttribute(
      "aria-busy",
      state.transcriptMutationInFlight ? "true" : "false",
    );
    const status = $("#transcript-mutation-status");
    if (state.transcriptMutationInFlight) {
      status.hidden = false;
      status.textContent = "Đang lưu thay đổi transcript.";
    } else {
      if (status.textContent === "Đang lưu thay đổi transcript.") {
        status.textContent = "Thay đổi transcript đã hoàn tất.";
      }
      status.hidden = !status.textContent;
    }
  }

  function setTranscriptMutationError(meetingId, generationId, message, reloadLatest) {
    state.transcriptMutationError = { meetingId, generationId, message, reloadLatest };
    renderTranscriptMutationError();
  }

  function clearTranscriptMutationError(generationId) {
    if (
      !state.transcriptMutationError
      || (generationId && state.transcriptMutationError.generationId !== generationId)
    ) return;
    state.transcriptMutationError = null;
    renderTranscriptMutationError();
  }

  async function saveSegmentText(form) {
    const meeting = state.meeting;
    const generation = meeting && meeting.transcription && meeting.transcription.generation;
    const editor = form.querySelector(".segment-text-editor");
    const status = form.querySelector(".segment-edit-status");
    const text = editor.value;
    const segment = generation && generation.segments.find((item) => item.id === form.dataset.segmentId);
    if (
      !meeting
      || sourceMutationUnavailable()
      || !generation
      || generation.id !== form.dataset.generationId
      || !segment
      || state.transcriptMutationInFlight
    ) return;
    status.classList.remove("is-error");
    const draft = rememberTranscriptDraft(generation.id, "segmentText", segment.id, text);
    if (segment.text === text) {
      const edit = closeSegmentEditor(generation.id, segment.id);
      reportTranscriptMutation(null, null, "Không có thay đổi.");
      if (edit) edit.focus();
      return;
    }
    if (draft && draft.conflictCode === "source_version_changed") {
      reportTranscriptMutation(
        null,
        status,
        "Transcript đã thay đổi. Xem bản mới nhất rồi chỉnh bản nháp trước khi lưu.",
        true,
      );
      return;
    }
    setTranscriptMutationInFlight(true, form);
    try {
      const result = await requestJson(
        `/api/meetings/${encodeURIComponent(meeting.id)}/transcript-segments/${encodeURIComponent(segment.id)}/text`,
        {
          method: "PATCH",
          body: JSON.stringify({
            expected_generation_id: generation.id,
            expected_source_version: generation.source_version,
            text,
          }),
        },
      );
      const applied = applyTranscriptMutationResult(
        meeting.id,
        meeting,
        generation.id,
        "segmentText",
        segment.id,
        text,
        result.text,
        result.source_version,
      );
      const feedbackStatus = resolveTranscriptMutationStatus(
        state.transcriptMutationStatusDescriptor,
        status,
      );
      if (applied.meeting && applied.meeting.id === meeting.id && applied.generation) {
        if (feedbackStatus) clearReloadLatestAction(feedbackStatus.parentElement);
        updateTranscriptRenderKey(applied.generation);
      }
      // The saved text is back in read mode; focus follows to its Sửa button once the save settles.
      const edit = closeSegmentEditor(generation.id, segment.id);
      if (edit) state.transcriptMutationFocusAfter = edit;
      reportTranscriptMutation(
        state.transcriptMutationStatusDescriptor,
        status,
        "Đã lưu.",
      );
    } catch (error) {
      const feedbackStatus = reportTranscriptMutation(
        state.transcriptMutationStatusDescriptor,
        status,
        transcriptMutationMessage(error, "Không thể lưu đoạn transcript."),
        true,
      );
      const code = transcriptConflictCode(error);
      if (code) {
        markTranscriptDraftConflict(
          generation.id,
          "segmentText",
          segment.id,
          code,
          feedbackStatus,
        );
      }
    } finally {
      setTranscriptMutationInFlight(false);
    }
  }

  function updateSpeakerLabelsInTranscript(generation, speaker) {
    for (const option of $("#transcript-segments").querySelectorAll(".segment-speaker-select option")) {
      if (option.value === speaker.speaker_id) option.textContent = speaker.display_name;
    }
    for (const label of $("#transcript-segments").querySelectorAll(".segment-original-speaker")) {
      if (label.dataset.originalSpeakerId === speaker.speaker_id) {
        label.textContent = `Gán ban đầu: ${speaker.display_name}`;
      }
    }
    for (const name of $("#transcript-segments").querySelectorAll(".segment-speaker")) {
      if (name.dataset.speakerId === speaker.speaker_id) name.textContent = speaker.display_name;
    }
    const item = speakerItem(speaker.speaker_id);
    if (item) {
      const input = item.querySelector("input");
      if (input) input.value = speaker.display_name;
      else replaceSpeakerItem(generation.id, speaker.speaker_id);
    }
    updateAssignmentDraftReviewLabels(generation);
    updateTranscriptRenderKey(generation);
  }

  async function saveSpeakerName(form, displayName = null, { reviewed = false } = {}) {
    const meeting = state.meeting;
    const generation = meeting && meeting.transcription && meeting.transcription.generation;
    const speakerId = form.dataset.speakerId;
    const input = form.querySelector("input");
    const status = form.querySelector(".speaker-form-status");
    const requestedName = displayName === null ? input.value : displayName;
    const speaker = generation && generation.speakers.find((item) => item.speaker_id === speakerId);
    if (
      !meeting
      || sourceMutationUnavailable()
      || !generation
      || generation.id !== form.dataset.generationId
      || !speaker
      || state.transcriptMutationInFlight
    ) return;
    status.classList.remove("is-error");
    const draft = rememberTranscriptDraft(
      generation.id,
      "speakerName",
      speakerId,
      requestedName,
      { reviewed },
    );
    if (draft && draft.conflictCode === "source_version_changed") {
      status.classList.add("is-error");
      status.textContent = "Tên người nói đã thay đổi. Xem tên mới nhất rồi chỉnh bản nháp trước khi lưu.";
      return;
    }
    setTranscriptMutationInFlight(true, form);
    try {
      const result = await requestJson(
        `/api/meetings/${encodeURIComponent(meeting.id)}/transcript-generations/${encodeURIComponent(generation.id)}/speakers/${encodeURIComponent(speakerId)}`,
        {
          method: "PATCH",
          body: JSON.stringify({
            expected_source_version: generation.source_version,
            display_name: requestedName,
          }),
        },
      );
      const applied = applyTranscriptMutationResult(
        meeting.id,
        meeting,
        generation.id,
        "speakerName",
        speakerId,
        requestedName,
        result.display_name,
        result.source_version,
      );
      const feedbackStatus = resolveTranscriptMutationStatus(
        state.transcriptMutationStatusDescriptor,
        status,
      );
      if (applied.meeting && applied.meeting.id === meeting.id && applied.generation) {
        if (feedbackStatus) clearReloadLatestAction(feedbackStatus.parentElement);
        const currentSpeaker = applied.generation.speakers.find(
          (item) => item.speaker_id === speakerId,
        );
        if (currentSpeaker && state.selectedGenerationId === applied.generation.id) {
          updateSpeakerLabelsInTranscript(applied.generation, currentSpeaker);
        }
      }
      // The new name is back on its chip; focus follows to it once the save settles.
      const chip = closeSpeakerRename(generation.id, speakerId);
      if (chip) state.transcriptMutationFocusAfter = chip;
      reportTranscriptMutation(
        state.transcriptMutationStatusDescriptor,
        status,
        "Đã lưu tên người nói.",
      );
    } catch (error) {
      const feedbackStatus = reportTranscriptMutation(
        state.transcriptMutationStatusDescriptor,
        status,
        transcriptMutationMessage(error, "Không thể lưu tên người nói."),
        true,
      );
      const code = transcriptConflictCode(error);
      if (code) {
        markTranscriptDraftConflict(
          generation.id,
          "speakerName",
          speakerId,
          code,
          feedbackStatus,
        );
      }
    } finally {
      setTranscriptMutationInFlight(false);
    }
  }

  async function addSpeaker(form) {
    const meeting = state.meeting;
    const generation = meeting && meeting.transcription && meeting.transcription.generation;
    const input = form.querySelector("#speaker-add-name");
    const status = $("#speaker-add-status");
    const existingDraft = generation
      && transcriptDraft(generation.id, "speakerAddName", "speaker-add-name");
    if (!meeting || sourceMutationUnavailable() || !speakerAddRecoveryReady(generation, existingDraft)) return;
    const requestedName = input.value;
    rememberSpeakerAddDraft(generation.id, requestedName);
    status.classList.remove("is-error");
    setTranscriptMutationInFlight(true, form);
    try {
      const result = await requestJson(
        `/api/meetings/${encodeURIComponent(meeting.id)}/transcript-generations/${encodeURIComponent(generation.id)}/speakers`,
        {
          method: "POST",
          body: JSON.stringify({
            expected_source_version: generation.source_version,
            display_name: requestedName,
          }),
        },
      );
      const speaker = {
        speaker_id: result.speaker_id,
        display_name: result.display_name,
        first_seen_seconds: result.first_seen_seconds,
        last_seen_seconds: result.last_seen_seconds,
      };
      const responseGenerationId = result.generation_id || generation.id;
      const currentMeeting = state.meeting;
      const currentTranscription = currentMeeting && currentMeeting.id === meeting.id
        ? currentMeeting.transcription
        : null;
      const targetGeneration = generationsFor(currentTranscription).find(
        (item) => item.id === responseGenerationId,
      );
      const currentVersion = Number(targetGeneration && targetGeneration.source_version) || 0;
      const resultVersion = Number(result.source_version) || 0;
      let reconciled = false;
      if (targetGeneration && resultVersion > currentVersion) {
        const existing = targetGeneration.speakers.find(
          (item) => item.speaker_id === speaker.speaker_id,
        );
        if (existing) Object.assign(existing, speaker);
        else targetGeneration.speakers.push(speaker);
        targetGeneration.source_version = resultVersion;
        reconciled = true;
      }
      if (
        reconciled
        && state.view === "meeting"
        && state.selectedGenerationId === targetGeneration.id
      ) {
        const currentGeneration = currentTranscription.generation;
        const editable = Boolean(
          currentGeneration
          && currentGeneration.id === targetGeneration.id
          && targetGeneration.status === "complete",
        );
        renderTranscriptGeneration(targetGeneration, editable);
        if (editable) {
          const chip = speakerItem(speaker.speaker_id)?.querySelector(".speaker-chip");
          if (chip) state.transcriptMutationFocusAfter = chip;
        }
      }
      clearSpeakerAddDraft(generation.id);
      if (input.value === requestedName) input.value = "";
      renderTranscriptDraftRecovery(
        state.meeting && state.meeting.transcription,
        state.selectedGenerationId,
      );
      reportTranscriptMutation(
        state.transcriptMutationStatusDescriptor,
        status,
        "Đã thêm người nói.",
      );
    } catch (error) {
      const feedbackStatus = reportTranscriptMutation(
        state.transcriptMutationStatusDescriptor,
        status,
        transcriptMutationMessage(error, "Không thể thêm người nói."),
        true,
      );
      const code = transcriptConflictCode(error);
      const draft = transcriptDraft(generation.id, "speakerAddName", "speaker-add-name");
      if (draft && code) draft.conflictCode = code;
      if (code && feedbackStatus) appendReloadLatestButton(feedbackStatus.parentElement, generation.id);
      renderTranscriptDraftRecovery(
        state.meeting && state.meeting.transcription,
        state.selectedGenerationId,
      );
    } finally {
      setTranscriptMutationInFlight(false);
    }
  }

  async function reapplySpeakerAddDraft(button) {
    const meeting = state.meeting;
    const originGenerationId = button.dataset.generationId;
    const draft = transcriptDraft(originGenerationId, "speakerAddName", "speaker-add-name");
    const generation = meeting && meeting.transcription && meeting.transcription.generation;
    const status = $("#speaker-add-status");
    if (!meeting || !speakerAddRecoveryReady(generation, draft)) return;
    const requestedName = draft.value;
    draft.baseSourceVersion = Number(generation.source_version) || 0;
    draft.conflictCode = null;
    status.classList.remove("is-error");
    setTranscriptMutationInFlight(true, button);
    try {
      const result = await requestJson(
        `/api/meetings/${encodeURIComponent(meeting.id)}/transcript-generations/${encodeURIComponent(generation.id)}/speakers`,
        {
          method: "POST",
          body: JSON.stringify({
            expected_source_version: generation.source_version,
            display_name: requestedName,
          }),
        },
      );
      const speaker = {
        speaker_id: result.speaker_id,
        display_name: result.display_name,
        first_seen_seconds: result.first_seen_seconds,
        last_seen_seconds: result.last_seen_seconds,
      };
      const currentMeeting = state.meeting;
      const currentGeneration = currentMeeting && currentMeeting.id === meeting.id
        && currentMeeting.transcription && currentMeeting.transcription.generation;
      if (currentGeneration && currentGeneration.id === generation.id) {
        const currentVersion = Number(currentGeneration.source_version) || 0;
        const resultVersion = Number(result.source_version) || 0;
        if (resultVersion > currentVersion) {
          const existing = currentGeneration.speakers.find(
            (item) => item.speaker_id === speaker.speaker_id,
          );
          if (existing) Object.assign(existing, speaker);
          else currentGeneration.speakers.push(speaker);
          currentGeneration.source_version = resultVersion;
          if (state.view === "meeting" && state.selectedGenerationId === currentGeneration.id) {
            renderTranscriptGeneration(currentGeneration, true);
            const chip = speakerItem(speaker.speaker_id)?.querySelector(".speaker-chip");
            if (chip) state.transcriptMutationFocusAfter = chip;
          }
        }
      }
      clearSpeakerAddDraft(originGenerationId);
      const addNameInput = $("#speaker-add-name");
      if (addNameInput.value === requestedName) addNameInput.value = "";
      renderTranscriptDraftRecovery(
        state.meeting && state.meeting.transcription,
        state.selectedGenerationId,
      );
      reportTranscriptMutation(
        state.transcriptMutationStatusDescriptor,
        status,
        "Đã thêm người nói.",
      );
    } catch (error) {
      const feedbackStatus = reportTranscriptMutation(
        state.transcriptMutationStatusDescriptor,
        status,
        transcriptMutationMessage(error, "Không thể thêm người nói."),
        true,
      );
      const code = transcriptConflictCode(error);
      if (draft && code) draft.conflictCode = code;
      if (code && feedbackStatus) appendReloadLatestButton(feedbackStatus.parentElement, generation.id);
      renderTranscriptDraftRecovery(
        state.meeting && state.meeting.transcription,
        state.selectedGenerationId,
      );
    } finally {
      setTranscriptMutationInFlight(false);
    }
  }

  async function saveSpeakerAssignment(select, { reviewed = false } = {}) {
    const meeting = state.meeting;
    const generation = meeting && meeting.transcription && meeting.transcription.generation;
    const segmentId = select.dataset.segmentId;
    const segment = generation && generation.segments.find((item) => item.id === segmentId);
    if (
      !meeting
      || sourceMutationUnavailable()
      || !generation
      || generation.id !== select.dataset.generationId
      || !segment
      || state.transcriptMutationInFlight
    ) return;
    const requestedSpeaker = select.value;
    const draft = rememberTranscriptDraft(
      generation.id,
      "speakerAssignment",
      segmentId,
      requestedSpeaker,
      { reviewed },
    );
    if (draft && draft.conflictCode && !reviewed) {
      const review = select.closest(".transcript-segment")
        .querySelector(".transcript-assignment-draft-review");
      if (review) {
        const status = review.querySelector(".transcript-assignment-draft-status");
        if (status) status.textContent = "Tải bản mới nhất để xem lựa chọn rồi áp dụng lại.";
      }
      return;
    }
    if ((segment.speaker_id || "") === requestedSpeaker) {
      renderTranscriptDraftRecovery(meeting.transcription, state.selectedGenerationId);
      return;
    }
    setTranscriptMutationInFlight(true, select);
    try {
      const result = await requestJson(
        `/api/meetings/${encodeURIComponent(meeting.id)}/transcript-segments/${encodeURIComponent(segmentId)}/speaker`,
        {
          method: "PATCH",
          body: JSON.stringify({
            expected_generation_id: generation.id,
            expected_source_version: generation.source_version,
            expected_assignment_version: Number(select.dataset.assignmentVersion),
            speaker_id: requestedSpeaker || null,
          }),
        },
      );
      const generationId = select.dataset.generationId;
      const applied = applyTranscriptMutationResult(
        meeting.id,
        meeting,
        generationId,
        "speakerAssignment",
        segmentId,
        requestedSpeaker,
        {
          speaker_id: result.speaker_id,
          assignment_version: result.assignment_version,
        },
        result.source_version,
      );
      const segment = applied.generation
        && applied.generation.segments.find((item) => item.id === segmentId);
      if (!segment || !applied.meeting || applied.meeting.id !== meeting.id) return;
      const currentSelect = [...document.querySelectorAll(".segment-speaker-select")].find(
        (item) => item.dataset.generationId === generationId && item.dataset.segmentId === segmentId,
      );
      if (currentSelect) {
        currentSelect.value = segment.speaker_id || "";
        currentSelect.dataset.currentSpeaker = segment.speaker_id || "";
        currentSelect.dataset.assignmentVersion = String(segment.assignment_version || 1);
        const review = currentSelect.closest(".transcript-segment")
          .querySelector(".transcript-assignment-draft-review");
        if (review) review.remove();
      }
      if (state.view === "meeting" && state.selectedGenerationId === generationId) {
        updateTranscriptRenderKey(applied.generation);
        clearTranscriptMutationError(generationId);
      }
      reportTranscriptMutation(
        state.transcriptMutationStatusDescriptor,
        null,
        "Đã lưu lựa chọn người nói.",
      );
    } catch (error) {
      const message = transcriptMutationMessage(error, "Không thể lưu người nói.");
      const code = error && error.payload && error.payload.detail && error.payload.detail.code;
      const isConflict = Boolean(
        transcriptConflictCode(error)
        || code === "assignment_version_changed",
      );
      const currentGeneration = state.meeting && state.meeting.id === meeting.id
        && state.meeting.transcription && state.meeting.transcription.generation;
      const currentSegment = currentGeneration
        && currentGeneration.id === generation.id
        && currentGeneration.segments.find((item) => item.id === segmentId);
      const latestSelect = [...document.querySelectorAll(".segment-speaker-select")].find(
        (item) => item.dataset.generationId === generation.id
          && item.dataset.segmentId === segmentId,
      );
      if (isConflict) {
        const assignmentDraft = transcriptDraft(generation.id, "speakerAssignment", segmentId);
        if (assignmentDraft) assignmentDraft.conflictCode = code;
        if (latestSelect) latestSelect.value = requestedSpeaker;
      } else {
        const bucket = transcriptDraftBucket(generation.id);
        if (bucket) {
          bucket.speakerAssignment.delete(segmentId);
          if (transcriptDraftBucketIsEmpty(bucket)) state.transcriptDrafts.delete(generation.id);
        }
        if (latestSelect) {
          latestSelect.value = currentSegment && currentSegment.speaker_id || "";
          const review = latestSelect.closest(".transcript-segment")
            .querySelector(".transcript-assignment-draft-review");
          if (review) review.remove();
        }
      }
      setTranscriptMutationError(
        meeting.id,
        generation.id,
        message,
        isConflict,
      );
      reportTranscriptMutation(
        state.transcriptMutationStatusDescriptor,
        null,
        message,
        true,
      );
      if (
        isConflict
        && currentGeneration
        && currentGeneration.id === generation.id
        && state.selectedGenerationId === generation.id
      ) {
        delete $("#transcript-generation").dataset.renderKey;
        renderTranscriptGeneration(currentGeneration, true);
      }
      renderTranscriptDraftRecovery(
        state.meeting && state.meeting.transcription,
        state.selectedGenerationId,
      );
    } finally {
      setTranscriptMutationInFlight(false);
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

  function taskStageLabel(task) {
    return TASK_STAGES[task.stage] || task.stage || "Chưa bắt đầu";
  }

  // The bar is the share of the recording already transcribed; without a usable duration it is
  // indeterminate (no value attribute, no percent) rather than a guess.
  function renderTaskProgress(task) {
    $("#task-progress").hidden = !task;
    if (!task) return;
    const duration = Number(task.audio_duration_seconds);
    const known = Number.isFinite(duration) && duration > 0;
    const fraction = known
      ? Math.min(1, Math.max(0, Number(task.transcript_end_seconds) || 0) / duration)
      : 0;
    const bar = $("#task-progress-bar");
    if (known) bar.value = fraction;
    else bar.removeAttribute("value");
    // Rounding must not announce 100% before the last second is transcribed.
    const percent = fraction >= 1 ? 100 : Math.min(99, Math.round(fraction * 100));
    $("#task-progress-percent").textContent = known ? `${percent}%` : "";
    $("#task-progress-stage").textContent = taskStageLabel(task);
  }

  function renderTranscription(transcription) {
    const task = transcription && transcription.task;
    const generation = transcription && transcription.generation;
    const active = Boolean(task && ACTIVE_TASK_STATES.has(task.status));
    const workerChecking = active && task.worker_state === "checking-worker";
    const startButton = $("#start-transcription");
    const cancelButton = $("#cancel-transcription");
    const measurements = $("#task-measurements");

    renderRuntimeProfile(transcription && transcription.runtime);

    startButton.hidden = active;
    startButton.disabled = state.taskRequestInFlight || sourceMutationUnavailable();
    startButton.textContent = generation ? "Chạy lại bản ghi" : "Bắt đầu chép lời";
    // The first run is the decisive action; running again over a transcript is not.
    startButton.classList.toggle("primary-button", !generation);
    startButton.classList.toggle("secondary-button", Boolean(generation));
    cancelButton.hidden = !active;
    cancelButton.disabled = !task || task.status === "stopping";
    cancelButton.textContent = task && task.status === "stopping" ? "Đang dừng…" : "Hủy chép lời";
    renderTaskProgress(active ? task : null);
    measurements.hidden = !task;
    renderTaskError(task);

    if (!task) {
      $("#transcription-status").textContent = generation
        ? "Transcript hoàn chỉnh đã được lưu. Bạn có thể nghe lại các mốc hoặc chủ động chạy lại bản ghi."
        : "Bản ghi đã lưu. Bấm “Bắt đầu chép lời” khi bạn muốn chạy nhận dạng local.";
    } else {
      const statusText = {
        accepted: "Tác vụ đã được nhận. Worker sẽ bắt đầu xử lý.",
        running: "Đang chép lời bằng model local. Tác vụ tiếp tục nếu bạn đóng tab.",
        stopping: "Đang dừng và thu hồi runner. Slot chỉ được nhường sau khi runner đã kết thúc.",
        succeeded: "Transcript đã được lưu hoàn chỉnh. Kết quả của lần chép lời là transcript_only.",
        failed: task.error_message || "Tác vụ thất bại. Transcript hoàn chỉnh trước đó vẫn được giữ.",
        canceled: "Đã hủy sau khi runner dừng. Transcript hoàn chỉnh trước đó vẫn được giữ.",
        interrupted: "Worker đã dừng giữa tác vụ. Không tự chạy lại; hãy bấm để thử lại.",
      };
      $("#transcription-status").textContent = workerChecking
        ? task.status === "accepted"
          ? "Đang kiểm tra worker trước khi bắt đầu xử lý."
          : "Đang kiểm tra worker vì heartbeat tác vụ đã cũ."
        : statusText[task.status] || "Đang tải trạng thái tác vụ.";
      $("#task-stage").textContent = taskStageLabel(task);
      $("#task-elapsed").textContent = formatElapsedSeconds(task.elapsed_seconds);
      $("#task-segment-count").textContent = String(task.segment_count || 0);
      $("#task-transcript-end").textContent = formatTimestamp(task.transcript_end_seconds || 0);
    }
    const status = $("#transcription-status");
    status.dataset.workerState = task && task.worker_state ? task.worker_state : "";
    status.classList.toggle("is-checking-worker", workerChecking);
    renderMeetingProcessingStatus(task, generation);
    const selected = renderGenerationNavigation(transcription);
    renderTabCounts(selected && selected.generation);
    renderTranscriptGeneration(selected && selected.generation, Boolean(selected && selected.editable));
    renderTranscriptDraftRecovery(transcription, selected && selected.generation.id);
    renderTranscriptMutationError();
    notifyMeetingContext();
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
    installServerMeeting(meeting);
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

  // Reasons an automatic start was refused; the manual button stays for a deliberate retry.
  const AUTO_START_REASONS = {
    system_busy: "Máy đang bận vì một tác vụ khác đang chạy.",
    processing_unavailable: "Slot xử lý của máy chưa sẵn sàng.",
    worker_unavailable: "Worker chép lời chưa sẵn sàng.",
    model_unavailable: "Model chép lời local chưa được chuẩn bị.",
    diarization_model_unavailable: "Model nhận dạng người nói chưa được chuẩn bị.",
  };

  // The create dialog leaves a one-shot key for a meeting it saved with "Chép lời ngay" on.
  // It is removed before anything is sent, so a reload or Back never sends again.
  function takeAutoStartRequest(meetingId) {
    const key = `asr-en-vi:auto-transcribe:${meetingId}`;
    try {
      if (window.sessionStorage.getItem(key) === null) return false;
      window.sessionStorage.removeItem(key);
      return true;
    } catch {
      return false;
    }
  }

  async function startTranscription({ auto = false } = {}) {
    const meeting = state.meeting;
    if (!meeting || state.taskRequestInFlight || sourceMutationUnavailable()) return;
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
      const code = requestError && requestError.payload && requestError.payload.detail
        ? requestError.payload.detail.code
        : "";
      state.taskRequestError = auto && Object.hasOwn(AUTO_START_REASONS, code)
        ? `${AUTO_START_REASONS[code]} Cuộc họp đã được lưu nhưng chưa chép lời. Ứng dụng không tự thử lại; bấm “Bắt đầu chép lời” khi máy sẵn sàng.`
        : `${requestError && requestError.message ? requestError.message : "Không thể xác nhận yêu cầu."} ${retryGuidance}`;
      $("#transcription-status").textContent = "Chưa xác nhận được việc nhận tác vụ. Yêu cầu chưa được tự gửi lại.";
    } finally {
      state.taskRequestInFlight = false;
      if (state.meeting && state.meeting.id === meeting.id) renderTranscription(state.meeting.transcription);
      else notifyMeetingContext();
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
    if (!sameMeeting) {
      stopTaskPolling();
      state.selectedGenerationId = null;
      state.currentGenerationId = null;
      state.transcriptMutationError = null;
      state.editingSegment = null;
      state.renamingSpeaker = null;
      clearSpeakerAddName();
      resetTab();
    }
    if (!sameMeeting) closeEditor(); // drops the draft, which orphans any save still in flight
    if (sameMeeting) {
      renderMeeting(state.meeting); // show what we already know while the refresh runs
      showView("meeting");
      initMeetingTab();
    } else {
      setHeading("Cuộc họp", "Cuộc họp · ASR EN VI");
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
      installServerMeeting(meeting);
      renderMeeting(meeting);
      const audio = $("#meeting-audio");
      if (audio.dataset.meetingId !== meeting.id) {
        const audioUrl = meeting.audio_url || (meeting.recording && meeting.recording.audio_url);
        audio.src = sameOriginAudioSource(audioUrl, meeting.id);
        audio.dataset.meetingId = meeting.id;
        audio.load();
      }
      showView("meeting");
      initMeetingTab(); // before notes.js hears of the meeting, so its source view can take focus
      notifyMeetingContext();
      startTaskPolling(meeting.id, meeting.transcription && meeting.transcription.task);
      renderSidebar();
      if (!state.meetings.length) void refreshHistory();
      const transcription = meeting.transcription || {};
      if (takeAutoStartRequest(meeting.id) && !transcription.task && !transcription.generation) {
        void startTranscription({ auto: true });
      }
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
    syncMetadataLockControls();
    $("#edit-title").focus();
  }

  function setEditorBusy(busy) {
    state.editorBusy = busy;
    syncMetadataLockControls();
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
    if (meetingDate !== draft.original.meeting_date && sourceMutationUnavailable()) {
      showEditError("Ngày họp đang bị khóa để giữ nguyên nguồn của notes. Tên cuộc họp vẫn có thể được lưu sau khi trả ngày về giá trị ban đầu.");
      syncMetadataLockControls();
      return;
    }
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
        installServerMeeting(updated);
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
      installServerMeeting(current);
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

  window.ASRMeetingHistory = Object.freeze({
    // `known` is false until notes.js has read this meeting's notes; the first answer settles the default tab.
    setNotesSummary(meetingId, revisionCount, taskStatus, known = true) {
      if (!state.meeting || state.meeting.id !== meetingId) return;
      state.notesCount = Number(revisionCount) || 0;
      state.notesKnown = Boolean(known);
      state.notesTaskStatus = taskStatus || null;
      const transcription = state.meeting.transcription || {};
      renderMeetingProcessingStatus(transcription.task, transcription.generation);
      if (state.notesKnown && state.view === "meeting" && state.tab === null) initMeetingTab();
    },
    selectTab,
    defaultSpeakerNames,
    focusSpeakerCatalog,
    currentContext() {
      return {
        meeting: state.view === "meeting" ? state.meeting : null,
        view: state.view,
        transcriptionRequestInFlight: state.taskRequestInFlight,
      };
    },
    hasUnsavedTranscriptDrafts() {
      return [...state.transcriptDrafts.values()].some((bucket) => !transcriptDraftBucketIsEmpty(bucket));
    },
    setNotesSourceLock,
    seekNotesSource,
    refreshMeeting(meetingId) {
      if (!state.meeting || state.meeting.id !== meetingId) return Promise.resolve(false);
      return loadMeeting(meetingId);
    },
  });

  // ---- wiring ----
  for (const root of document.querySelectorAll("[data-calendar]")) {
    buildCalendar(root);
    root.addEventListener("click", onCalendarClick);
    root.addEventListener("input", onCalendarInput);
    root.addEventListener("change", onCalendarChange);
    root.addEventListener("focusout", onCalendarFocusout);
    root.addEventListener("keydown", onCalendarKeydown);
  }

  $(".brand").addEventListener("click", (event) => {
    const link = event.currentTarget;
    if (
      event.defaultPrevented
      || event.button !== 0
      || event.metaKey
      || event.ctrlKey
      || event.shiftKey
      || event.altKey
      || link.hasAttribute("target")
      || link.hasAttribute("download")
    ) return;
    const destination = new URL(link.href, window.location.href);
    if (
      destination.origin !== window.location.origin
      || destination.pathname !== "/"
      || destination.search
      || destination.hash
    ) return;
    event.preventDefault();
    if (window.location.pathname !== "/" || window.location.search || window.location.hash) {
      window.history.pushState({}, "", "/");
    }
    showHome();
    $("#page-title").focus();
  });

  document.addEventListener("click", (event) => {
    const link = event.target.closest("a[data-meeting-link]");
    if (!link || event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
    event.preventDefault();
    navigateToMeeting(link.dataset.meetingLink);
  });
  $("#open-calendar").addEventListener("click", openCalendar);
  $("#calendar-back").addEventListener("click", leaveCalendar);
  $("#edit-meeting").addEventListener("click", openEditor);
  $("#edit-cancel").addEventListener("click", () => {
    closeEditor();
    $("#edit-meeting").focus();
  });
  $("#edit-clear-date").addEventListener("click", () => {
    $("#edit-date").value = "";
    syncMetadataLockControls();
    $("#edit-date").focus();
  });
  $("#edit-date").addEventListener("input", syncMetadataLockControls);
  $("#edit-date").addEventListener("change", syncMetadataLockControls);
  $("#meeting-edit").addEventListener("submit", saveMeeting);
  $("#start-transcription").addEventListener("click", () => void startTranscription());
  $("#cancel-transcription").addEventListener("click", () => void cancelTranscription());
  $("#task-diagnostic-copy").addEventListener("click", () => void copyDiagnosticCommand());
  $("#generation-selector").addEventListener("change", (event) => {
    const transcription = state.meeting && state.meeting.transcription;
    const current = transcription && transcription.generation;
    const previousSelectedGenerationId = state.selectedGenerationId;
    state.selectedGenerationId = event.currentTarget.value;
    if (previousSelectedGenerationId !== state.selectedGenerationId) clearSpeakerAddName();
    const generation = generationsFor(transcription).find(
      (item) => item.id === state.selectedGenerationId,
    );
    const editable = Boolean(
      generation && current && generation.id === current.id && generation.status === "complete",
    );
    renderTabCounts(generation);
    renderTranscriptGeneration(generation, editable);
    renderTranscriptDraftRecovery(transcription, generation && generation.id);
    renderTranscriptMutationError();
  });
  $("#transcript-generation").addEventListener("submit", (event) => {
    const form = event.target;
    if (form.matches("form[data-segment-text]")) {
      event.preventDefault();
      void saveSegmentText(form);
    } else if (form.matches("#speaker-add-form")) {
      event.preventDefault();
      void addSpeaker(form);
    } else if (form.matches("form[data-speaker-name]")) {
      event.preventDefault();
      void saveSpeakerName(form);
    }
  });
  $("#transcript-generation").addEventListener("click", (event) => {
    const reapplyAssignment = event.target.closest("button[data-reapply-assignment-draft]");
    if (reapplyAssignment) {
      const select = [...document.querySelectorAll(".segment-speaker-select")].find(
        (item) => item.dataset.generationId === reapplyAssignment.dataset.generationId
          && item.dataset.segmentId === reapplyAssignment.dataset.segmentId,
      );
      if (select) void saveSpeakerAssignment(select, { reviewed: true });
      return;
    }
    const reload = event.target.closest("button[data-reload-latest]");
    if (reload) {
      void reloadLatestTranscript(reload);
      return;
    }
    const copyDraft = event.target.closest("button[data-copy-transcript-draft]");
    if (copyDraft) {
      void copyTranscriptDraft(copyDraft);
      return;
    }
    const chip = event.target.closest("button[data-speaker-chip]");
    if (chip) {
      openSpeakerRename(chip.dataset.speakerId);
      return;
    }
    const cancelRename = event.target.closest("button[data-speaker-cancel]");
    if (cancelRename) {
      cancelSpeakerRename(cancelRename.closest("form").dataset.speakerId);
      return;
    }
    const clear = event.target.closest("button[data-clear-speaker-name]");
    if (!clear) return;
    const form = clear.closest("li").querySelector("form[data-speaker-name]");
    if (form) void saveSpeakerName(form, "", { reviewed: true });
  });
  $("#transcript-draft-recovery").addEventListener("click", (event) => {
    const reapplySpeakerAdd = event.target.closest("[data-reapply-speaker-add-draft]");
    if (reapplySpeakerAdd) {
      void reapplySpeakerAddDraft(reapplySpeakerAdd);
      return;
    }
    const openDraft = event.target.closest("[data-open-transcript-draft]");
    if (!openDraft) return;
    const selector = $("#generation-selector");
    const generationId = openDraft.dataset.generationId;
    if (!selector || selector.value === generationId) return;
    selector.value = generationId;
    selector.dispatchEvent(new Event("change", { bubbles: true }));
  });
  function onReloadLatestClick(event) {
    const reload = event.target.closest("button[data-reload-latest]");
    if (reload) void reloadLatestTranscript(reload);
  }
  $("#transcription-error").addEventListener("click", onReloadLatestClick);
  $("#transcript-mutation-error").addEventListener("click", onReloadLatestClick);
  $("#transcript-generation").addEventListener("input", (event) => {
    const editor = event.target.closest(".segment-text-editor");
    if (editor) {
      rememberTranscriptDraft(
        editor.closest("form").dataset.generationId,
        "segmentText",
        editor.closest("form").dataset.segmentId,
        editor.value,
        { reviewed: true },
      );
      return;
    }
    const speakerInput = event.target.closest(".speaker-name-form input");
    if (speakerInput) {
      const form = speakerInput.closest("form");
      rememberTranscriptDraft(
        form.dataset.generationId,
        "speakerName",
        form.dataset.speakerId,
        speakerInput.value,
        { reviewed: true },
      );
    }
  });
  // Esc cancels and Ctrl/⌘+Enter saves, but never mid-composition: a Vietnamese IME uses both keys.
  // Both work from any control of the open row: textarea, speaker select, Hủy, "Chi tiết".
  $("#transcript-generation").addEventListener("keydown", (event) => {
    if (event.isComposing || event.keyCode === 229) return;
    if (event.key === "Escape") {
      const row = event.target.closest(".transcript-segment.is-editing");
      const renaming = event.target.closest(".speaker-name-form");
      if (row) cancelSegmentEditor(row.dataset.segmentId);
      else if (renaming) cancelSpeakerRename(renaming.dataset.speakerId);
      else return;
      event.preventDefault();
    } else if (event.key === "Enter" && (event.ctrlKey || event.metaKey)) {
      const form = event.target.closest(".transcript-segment.is-editing")
        ?.querySelector(".segment-edit-form");
      if (!form) return;
      event.preventDefault();
      form.requestSubmit();
    }
  });
  $("#transcript-segments").addEventListener("click", (event) => {
    const edit = event.target.closest("button[data-edit-segment]");
    if (edit) {
      openSegmentEditor(edit.closest(".transcript-segment").dataset.segmentId);
      return;
    }
    const cancelEdit = event.target.closest("button[data-segment-cancel]");
    if (cancelEdit) {
      cancelSegmentEditor(cancelEdit.closest(".transcript-segment").dataset.segmentId);
      return;
    }
    const timestamp = event.target.closest("button[data-seek-seconds]");
    if (!timestamp) return;
    const audio = $("#meeting-audio");
    const seconds = Number(timestamp.dataset.seekSeconds);
    if (!Number.isFinite(seconds) || seconds < 0) return;
    audio.currentTime = seconds;
    updateActiveTranscriptIntervals();
    const playback = audio.play();
    if (playback && typeof playback.catch === "function") playback.catch(() => {});
  });
  $("#transcript-segments").addEventListener("change", (event) => {
    const select = event.target.closest("select[data-speaker-assignment]");
    if (select) void saveSpeakerAssignment(select);
  });
  for (const eventName of ["timeupdate", "seeked", "loadedmetadata", "play"]) {
    $("#meeting-audio").addEventListener(eventName, updateActiveTranscriptIntervals);
  }
  const noteManualScroll = () => {
    lastManualScroll = performance.now();
  };
  for (const eventName of ["wheel", "touchmove"]) {
    window.addEventListener(eventName, noteManualScroll, { passive: true });
  }
  window.addEventListener("keydown", (event) => {
    if (SCROLL_KEYS.has(event.key)) noteManualScroll();
  });
  // A scrollbar drag sends no wheel or key first. Our own smooth scroll keeps sending scroll events,
  // each one holding the window open a little longer, however far it travels.
  window.addEventListener("scroll", () => {
    const now = performance.now();
    if (now <= ownScrollUntil) ownScrollUntil = now + OWN_SCROLL_GAP_MS;
    else lastManualScroll = now;
  }, { passive: true });
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
    if (id) void loadMeeting(id); // for the same meeting this also paints the tab the address names
    else showHome();
  });
  window.addEventListener("hashchange", () => {
    if (state.view === "meeting") initMeetingTab();
  });

  $("#meeting-tabs").addEventListener("click", (event) => {
    const tab = event.target.closest("[data-meeting-tab]");
    if (tab) selectTab(tab.dataset.meetingTab);
  });
  // Arrow keys, Home and End move between the tabs and choose the one they land on.
  $("#meeting-tabs").addEventListener("keydown", (event) => {
    const tab = event.target.closest("[data-meeting-tab]");
    if (!tab || event.altKey || event.ctrlKey || event.metaKey || event.shiftKey) return;
    const index = MEETING_TABS.indexOf(tab.dataset.meetingTab);
    const last = MEETING_TABS.length - 1;
    const target = {
      ArrowLeft: index === 0 ? last : index - 1,
      ArrowRight: index === last ? 0 : index + 1,
      Home: 0,
      End: last,
    }[event.key];
    if (target === undefined) return;
    event.preventDefault();
    selectTab(MEETING_TABS[target], { focus: true });
  });

  renderCalendars();
  const initialId = meetingIdFromPath();
  if (initialId) void loadMeeting(initialId);
  else showHome();
  void refreshHistory();
})();
