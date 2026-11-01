# v0.2.0 — ASR Studio

## Changes

- Introduce the ASR Studio name, waveform-and-fader logo, favicon and updated interface labels.
- Rename the Python package to `asr_studio` and the distribution and container image to `asr-studio`.
- Migrate browser preferences and pending request keys automatically. Keep the existing Compose deployment identity so a renamed checkout uses the same data, auth and provider volumes.
- Include the recent accessibility, upload recovery, task progress, provider feedback and notes refresh fixes from main.

## Upgrade

- Check out tag `v0.2.0` and use its Compose files and scripts. Use `ASR_IMAGE=ghcr.io/nguyencanhtrung/asr-studio:v0.2.0` with `./scripts/start.sh --pull`, or `ASR_IMAGE=asr-studio:local` with `./scripts/start.sh --source`.
- Use `python -m asr_studio.cli` for diagnostic and access commands. The old Python module name is no longer available in this release.
- Keep your existing `COMPOSE_PROJECT_NAME`, model directory, browser origin and data volumes. Do not delete volumes to upgrade. The default Compose project name intentionally remains `asr-en-vi` for compatibility.
- Run `uv sync --all-groups --locked` after updating a source checkout. Recreate or refresh the virtual environment when moving an existing checkout.
- Releases through v0.1.3 retain their original image and module names. Use the instructions from their tags when running them.

See the [user guide](../user-guide.md#install-a-release).

## Known limitations

- This release makes no new ASR quality, diarization accuracy or latency claim. Historical reports apply only to their recorded artifacts and configuration.
- Synthetic provider checks do not establish real provider authentication or inference. Exact checks and omissions are recorded in the release evidence asset.

## Measurements

New measurements: automated tests, browser scenarios and exact-artifact checks recorded in the release evidence.
Reused benchmark evidence: none.
Omitted measurements: model quality and timing benchmarks; the rebrand changes names and packaging and makes no new numerical or performance claim.
