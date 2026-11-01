# Issue tracker: GitHub

Specifications and implementation tickets for `nguyencanhtrung/asr-studio` live in GitHub Issues.

## Publishing

- When a skill says to publish to the issue tracker, create a GitHub issue in this repository.
- When a skill publishes multiple tickets, create one issue per ticket in dependency order.
- Use GitHub's native blocking or sub-issue relationships when the available integration supports them. Otherwise, record dependencies in each issue's `Blocked by` section.
- Do not fall back to local Markdown tickets unless the user explicitly requests local files.

## Triage labels

Before adding a triage label, resolve the skill's canonical role through [`triage-labels.md`](triage-labels.md). Use the mapped label exactly and do not substitute a similar GitHub default label.

If a required mapped label is absent from the repository, report the exact missing label. Create missing repository labels only when the user has authorized label setup or administration.
