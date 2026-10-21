---
name: ASR EN VI
description: An editorial-engineering workbench for local, source-verifiable meeting transcription.
colors:
  light-background: "#faf9f7"
  light-surface: "#ffffff"
  light-surface-subtle: "#f6f4f0"
  light-ink: "#1c1c21"
  light-ink-secondary: "#52525b"
  light-ink-muted: "#70707c"
  light-accent: "#8e2433"
  light-accent-hover: "#741b29"
  light-accent-soft: "#f3e4e6"
  light-hairline: "#e5e2dc"
  dark-background: "#131318"
  dark-surface: "#1b1b22"
  dark-surface-subtle: "#17171d"
  dark-ink: "#e9e7e3"
  dark-ink-secondary: "#a6a6b0"
  dark-ink-muted: "#83838e"
  dark-accent: "#e08b96"
  dark-accent-hover: "#eea2ab"
  dark-accent-soft: "#35222a"
  dark-hairline: "#2a2a33"
  success-light: "#226442"
  success-dark: "#86c9a4"
  warning-light: "#81540f"
  warning-dark: "#efbd69"
  danger-light: "#a63838"
  danger-dark: "#f0958e"
typography:
  access-display:
    fontFamily: "Newsreader Variable, Georgia, Times New Roman, serif"
    fontSize: "clamp(2.65rem, 6vw, 4.5rem)"
    fontWeight: 500
    lineHeight: 1.02
    letterSpacing: "-0.045em"
  access-display-mobile:
    fontFamily: "Newsreader Variable, Georgia, Times New Roman, serif"
    fontSize: "2.7rem"
    fontWeight: 500
    lineHeight: 1.02
    letterSpacing: "-0.045em"
  headline:
    fontFamily: "Newsreader Variable, Georgia, Times New Roman, serif"
    fontSize: "clamp(24px, 3vw, 34px)"
    fontWeight: 500
    lineHeight: 1.2
    letterSpacing: "-0.035em"
  meeting-headline:
    fontFamily: "Newsreader Variable, Georgia, Times New Roman, serif"
    fontSize: "clamp(26px, 3vw, 36px)"
    fontWeight: 500
    lineHeight: 1.2
    letterSpacing: "-0.035em"
  title:
    fontFamily: "Newsreader Variable, Georgia, Times New Roman, serif"
    fontSize: "27px"
    fontWeight: 500
    lineHeight: 1.2
    letterSpacing: "-0.035em"
  calendar-title:
    fontFamily: "Newsreader Variable, Georgia, Times New Roman, serif"
    fontSize: "26px"
    fontWeight: 500
    lineHeight: 1.2
  dialog-title:
    fontFamily: "Newsreader Variable, Georgia, Times New Roman, serif"
    fontSize: "24px"
    fontWeight: 500
    lineHeight: 1.2
  dialog-title-mobile:
    fontFamily: "Newsreader Variable, Georgia, Times New Roman, serif"
    fontSize: "23px"
    fontWeight: 500
    lineHeight: 1.2
  mobile-title:
    fontFamily: "Newsreader Variable, Georgia, Times New Roman, serif"
    fontSize: "22px"
    fontWeight: 500
    lineHeight: 1.2
  section-title:
    fontFamily: "Newsreader Variable, Georgia, Times New Roman, serif"
    fontSize: "17px"
    fontWeight: 560
    lineHeight: 1.3
  interface-heading:
    fontFamily: "Newsreader Variable, Georgia, Times New Roman, serif"
    fontSize: "1rem"
    fontWeight: 500
    lineHeight: 1.3
  intro:
    fontFamily: "Inter Variable, system-ui, sans-serif"
    fontSize: "0.9375rem"
    fontWeight: 400
    lineHeight: 1.7
  panel-title:
    fontFamily: "Newsreader Variable, Georgia, Times New Roman, serif"
    fontSize: "15px"
    fontWeight: 650
    lineHeight: 1.3
  subheading:
    fontFamily: "Newsreader Variable, Georgia, Times New Roman, serif"
    fontSize: "14px"
    fontWeight: 650
    lineHeight: 1.3
  body:
    fontFamily: "Inter Variable, system-ui, sans-serif"
    fontSize: "13px"
    fontWeight: 400
    lineHeight: 1.65
  body-rem:
    fontFamily: "Inter Variable, system-ui, sans-serif"
    fontSize: "0.8125rem"
    fontWeight: 400
    lineHeight: 1.65
  control:
    fontFamily: "Inter Variable, system-ui, sans-serif"
    fontSize: "12px"
    fontWeight: 600
    lineHeight: 1.55
  control-rem:
    fontFamily: "Inter Variable, system-ui, sans-serif"
    fontSize: "0.75rem"
    fontWeight: 600
    lineHeight: 1.55
  body-small:
    fontFamily: "Inter Variable, system-ui, sans-serif"
    fontSize: "11px"
    fontWeight: 400
    lineHeight: 1.6
  body-small-rem:
    fontFamily: "Inter Variable, system-ui, sans-serif"
    fontSize: "0.6875rem"
    fontWeight: 400
    lineHeight: 1.6
  metadata:
    fontFamily: "JetBrains Mono, ui-monospace, monospace"
    fontSize: "10px"
    fontWeight: 400
    lineHeight: 1.5
  label:
    fontFamily: "JetBrains Mono, ui-monospace, monospace"
    fontSize: "9px"
    fontWeight: 650
    lineHeight: 1.5
    letterSpacing: "0.15em"
rounded:
  sm: "4px"
  md: "8px"
  lg: "12px"
spacing:
  xs: "4px"
  sm: "8px"
  md: "12px"
  lg: "16px"
  xl: "24px"
  xxl: "32px"
components:
  button-primary-light:
    backgroundColor: "{colors.light-accent}"
    textColor: "#fffafa"
    typography: "{typography.body}"
    rounded: "{rounded.sm}"
    padding: "0 15px"
    height: "40px"
  button-primary-dark:
    backgroundColor: "{colors.dark-accent}"
    textColor: "#2a1117"
    typography: "{typography.body}"
    rounded: "{rounded.sm}"
    padding: "0 15px"
    height: "40px"
  field-light:
    backgroundColor: "{colors.light-surface}"
    textColor: "{colors.light-ink}"
    typography: "{typography.body}"
    rounded: "{rounded.sm}"
    padding: "0 12px"
    height: "40px"
  field-dark:
    backgroundColor: "{colors.dark-surface}"
    textColor: "{colors.dark-ink}"
    typography: "{typography.body}"
    rounded: "{rounded.sm}"
    padding: "0 12px"
    height: "40px"
  panel-light:
    backgroundColor: "{colors.light-surface}"
    textColor: "{colors.light-ink}"
    rounded: "{rounded.md}"
    padding: "20px"
  panel-dark:
    backgroundColor: "{colors.dark-surface}"
    textColor: "{colors.dark-ink}"
    rounded: "{rounded.md}"
    padding: "20px"
---

# Design System: ASR EN VI

## Overview

**Creative North Star: "The Editorial Engineering Ledger"**

ASR EN VI feels like a precise working ledger: calm enough for long review sessions, editorial enough to belong to the bibo product family, and technical enough to expose provenance, runtime state, and recoverable errors without ceremony. Warm paper and charcoal fields carry the visual world; burgundy signal lines, fine rules, and disciplined typography establish hierarchy.

The brand foundation is portable: palette roles, the Newsreader–Inter–JetBrains Mono relationship, hairlines, compact radii, accessible focus, and restrained motion. The sidebar, calendars, transcript generations, runtime panels, speaker tools, and one-step create-meeting dialog are ASR-specific operational components. Future products may reuse the foundation without copying this application's information architecture.

**Key Characteristics:**

- Editorial headlines paired with dense, legible controls.
- Flat, quiet surfaces divided by hairlines rather than decorative cards.
- Burgundy used as a sparse signal for action and selection.
- Technical metadata visually distinct in mono type.
- Light, dark, and system-following themes with the same semantic hierarchy.

## Colors

The palette pairs warm paper neutrals with charcoal dark surfaces and a reserved oxblood-to-dusty-rose accent.

### Primary

- **Oxblood Signal:** The light-theme action, link, focus, and selected-state color.
- **Dusty Rose Signal:** The corresponding dark-theme accent, raised in lightness to preserve contrast.

### Neutral

- **Warm Paper:** The light canvas; use restrained white and off-white surfaces to establish hierarchy.
- **Charcoal Field:** The dark canvas; use close charcoal steps instead of blue-tinted dashboard layers.
- **Ledger Ink:** Primary copy and titles; secondary and muted ink are reserved for explanation and metadata.
- **Hairline Rule:** One-pixel borders and dividers; it organizes information without becoming a frame.

### Named Rules

**The Sparse Signal Rule.** Burgundy identifies primary action, selection, focus, or source linkage; it never becomes a full-screen wash.

**The Semantic Independence Rule.** Success, warning, and danger keep their own green, amber, and red roles in both themes and always appear with text, an icon, or another non-color cue.

## Typography

- **Display Font:** Newsreader Variable (with Georgia and Times New Roman fallbacks)
- **Body Font:** Inter Variable (with system UI fallbacks)
- **Label/Mono Font:** JetBrains Mono (with platform monospace fallbacks)

**Character:** Newsreader gives saved work and section titles an editorial voice. Inter keeps Vietnamese and English controls compact and readable; JetBrains Mono turns runtime state, timestamps, versions, IDs, and small uppercase labels into a distinct technical layer.

### Hierarchy

- **Headline:** Medium-weight Newsreader with tight tracking for access, empty-state, and meeting titles.
- **Title:** Medium-weight Newsreader for workspace and calendar headings.
- **Body:** Inter at compact dashboard sizes with generous line height for explanations and transcript prose.
- **Label:** JetBrains Mono, usually uppercase with tracking, for operational metadata rather than long content.

### Named Rules

**The Three-Voice Rule.** Serif names the subject, sans-serif supports the task, and mono reports the machine; do not interchange those roles for decoration.

## Layout

Desktop uses a narrow navigation ledger beside a flexible workspace capped at a readable maximum width. The ledger is fixed to the viewport height: it stays in place while the workspace scrolls and scrolls internally, with a thin scrollbar and never sideways, when its content is taller. The primary task and status stay above the fold; transcript, calendar, and dialog content remain dense but separated by consistent rhythm. Space follows the 4/8/12/16/24/32 progression, with larger gaps reserved for changes in meaning rather than card decoration.

At 980px and below, the provider status buttons drop to their own row under the page title, and a status too long for its button wraps under the provider name instead of being cut. At 680px and below, the sidebar becomes a compact top bar that scrolls with the page, the calendar opener moves into the workspace header, secondary navigation moves into the workspace, and multi-column content stacks. At 520px and below, the create action becomes an accessible icon control and dialogs use nearly the full viewport. The document must never create horizontal overflow at the supported 320px minimum.

In a meeting the player is the one sticky element in the content area, at every width: a single bar, at most 72px tall, pinned to the top edge of that area while the notes and the transcript scroll under it. On desktop the navigation ledger stays pinned beside it; at 680px and below, where the navigation bar scrolls away with the page, the player is the only pinned piece. The recording heading and its hint stay in normal flow and scroll away. Anything the page scrolls to stops below the bar: the document scroller reserves the bar's height and each scroll target adds a 12px gap, so a segment or the notes source heading never lands under it. The browser scrolls a keyboard-focused control clear of the bar too, but a text field may only reveal its caret line, so part of the field can stay beneath the bar. While audio plays and some of the transcript list shows below the bar, the active segment follows with a nearest-edge scroll, instant under reduced motion; the page holds still while audio is paused, for two seconds after a manual scroll, while a transcript field has focus, and while the whole list is off screen, so reading the notes is never interrupted.

## Elevation & Depth

The system is flat by default. Surface contrast and one-pixel hairlines carry most structure; the only ambient elevation belongs to modal dialogs and the small recording signal tile when it must separate from the canvas.

### Shadow Vocabulary

- **Ambient Tile:** A low-opacity, broad shadow used only beneath the recording signal tile.
- **Modal Lift:** A large soft shadow beneath dialogs, paired with a theme-aware overlay.

### Named Rules

**The Flat-by-Default Rule.** A panel earns elevation only when it floats above the current task; ordinary dashboard regions stay on the ledger plane. The pinned player floats over scrolling content but stays flat: an opaque surface and a hairline separate it, never a shadow.

## Shapes

Corners are compact and engineered: controls use the small radius, content panels use the medium radius, and modal dialogs use the large radius. Circular geometry is reserved for status dots, waveform orbit details, and count badges. Borders remain one pixel; avoid thick accent bars and nested rounded containers.

## Components

### Buttons

- **Shape:** Compact rectangular control with the small radius and a 40px default height.
- **Primary:** Solid accent fill with theme-specific contrast text; reserve it for the next decisive action.
- **Hover / Focus:** A one-pixel upward movement is allowed on hover; keyboard focus uses a two-pixel accent outline. Reduced-motion preferences collapse transitions to effectively instant.
- **Secondary / Text:** Secondary buttons use a neutral surface and strong hairline. Text actions remain transparent and underlined.
- **Disabled:** Neutral surface and muted ink, plus the native disabled state; never communicate disabled only through opacity.

### Player

- **Shape:** One bar with the small radius, a one-pixel hairline and the surface background, holding only the native audio control and no heading, hint or shadow.
- **Behavior:** Sticky to the top edge of the content area, opaque so scrolling content never shows through, in light and dark.
- **Focus:** The two-pixel accent outline is drawn inside the bar, so the bar edge and the top of the viewport never clip it.

### Transcript Segments

- **Read mode (default):** One bordered row per segment, on the subtle surface with the medium radius. It holds the timestamp button (mono, 12px, accent; seeks and plays), the speaker name (12px, semibold ink), the text (Inter body, 13px) and, when the segment needs review, the amber "Cần kiểm tra" cue with its reasons (11px, bordered, never color alone). No field, select or save button is rendered. The playing segment keeps its accent border and soft fill.
- **Sửa:** A secondary button, always visible and never hover-only, at the end of the speaker line. A read row has two tab stops: the timestamp and "Sửa". Its accessible name carries the start time and, with an unsaved draft, "(có bản nháp chưa lưu)".
- **Editor:** "Sửa" swaps only that row for the editor: speaker select, text area (13px), "Lưu đoạn" and "Hủy", and a closed "Chi tiết" disclosure (11px) holding "Gán ban đầu" and the model measures. One editor is open at a time; opening another returns the first row to read mode and keeps its unsaved text. The select saves on change; Esc or "Hủy" closes, Ctrl/⌘+Enter saves from any control in the editor, and focus returns to that row's "Sửa" afterwards. Esc and "Hủy" drop ordinary typed text but keep a conflict-marked draft: the row stays marked, and "Sửa" reopens it with the draft and its review panel.
- **Draft mark:** A row with an unsaved draft shows "Bản nháp chưa lưu" in warning ink on a dashed warning border, so the mark never relies on color alone. After a version conflict, "Tải lại bản mới nhất" sits in the open editor or rename form, and in the conflict panel above the transcript while that row or chip is closed.
- **Locked / past:** A locked source disables "Sửa" with the reason from the generation status line attached by `aria-describedby`; in an open editor the fields and "Lưu đoạn" are disabled and "Hủy" stays usable. A past transcript is read-only: no "Sửa", and each row keeps only the closed "Chi tiết".
- **Feedback:** A row has no live region of its own for save messages. Every "Đã lưu" and error goes to the one shared polite status above the transcript; the in-editor status line is plain text.

### Speaker Chips

- **Shape:** One compact button per speaker (30px minimum height, large radius, strong hairline, surface fill, 12px semibold name) in a wrapping row; hover shifts to the accent border and soft fill.
- **Marks:** A speaker still carrying the system default name ("Speaker N") shows an outlined "đặt tên" mark in accent. A name typed and left unsaved shows "bản nháp". Marks are words, not color alone.
- **Rename:** A chip click swaps only that chip for an inline form on its own line (name field, "Lưu tên", "Hủy", "Khôi phục tên mặc định"; the label is 12px). Enter saves, Esc cancels, one rename is open at a time, and focus returns to the chip. "Thêm người nói" stays below the chips.
- **Disabled / read-only:** A locked source disables chips with muted ink and a plain hairline, tied to the lock reason like "Sửa". In a past transcript chips are plain text.

### Cards / Containers

- **Corner Style:** Medium radius for panels and compact radius for list rows.
- **Background:** One semantic surface step above the canvas.
- **Shadow Strategy:** Flat at rest; see the elevation rules.
- **Border:** One-pixel semantic hairline.
- **Internal Padding:** Usually 16–24px on desktop and 14–18px on mobile.

### Inputs / Fields

- **Style:** Neutral surface, one-pixel border, compact radius, and Inter for ordinary values; tokens, commands, and technical values may use JetBrains Mono.
- **Focus:** Accent outline and/or border shift with sufficient contrast in both themes.
- **Error / Disabled:** Danger copy accompanies invalid state; disabled fields retain readable value text.

### Navigation

Navigation is a quiet ledger rail: mono wordmark, uppercase technical section labels, compact rows, and an accent-soft current state. A compact sun/moon toggle sits beside the wordmark and exposes a dynamic accessible name for the opposite theme. On mobile the rail becomes a top bar containing the brand, theme toggle, and icon-only create action.

### Operational Status

Provider connection appears as two header buttons, OpenAI and Google; each pairs a status dot with explicit status text and its own accessible name. Runtime profile, task measurements, generations, timestamps, and diagnostic IDs use mono metadata inside flat bordered groups. Loading, saved, warning, and error states pair semantic color with explicit language. Transcript and history layouts belong to this product; preserve their scan order when restyling.

## Do's and Don'ts

### Do:

- **Do** use semantic tokens from `design-system.css`; add a role there before adding a page-specific color.
- **Do** load fonts and visual assets from the packaged application only.
- **Do** preserve visible keyboard focus, semantic labels, and reduced-motion behavior.
- **Do** keep operational state compact, textual, and easy to scan in both themes.
- **Do** verify new surfaces at desktop and narrow mobile widths in light and dark modes.

### Don't:

- **Don't** return to the teal, blue-black SaaS dashboard palette.
- **Don't** copy portfolio hero, timeline, or marketing-page composition into the workspace.
- **Don't** use burgundy for success, warning, or danger.
- **Don't** introduce gradients, glass effects, heavy shadows, pill-shaped primary controls, or decorative card grids.
- **Don't** stack uppercase mono overlabels directly above headings; put essential state in operational metadata.
- **Don't** load fonts, icons, CSS, scripts, telemetry, or visual assets from third-party origins at runtime.
