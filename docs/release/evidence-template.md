# Release evidence template

Copy this template for each release.
Replace each placeholder before publication.
Use one artifact row for each platform.
Add one check row for each required check or measurement decision.
Keep the record with the GitHub Release or its linked evidence report.

## Candidate

| Field | Value |
| --- | --- |
| Version and tag | `VERSION_AND_TAG` |
| Source commit | `FULL_SHA` |
| Previous release | `TAG_AND_SHA` |
| Changed areas | `AREAS_FROM_PROCESS_TABLE` |
| Decision date | `UTC_DATE` |
| CI | `RUN_URL_AND_RESULT` |
| Release decision | `READY_OR_BLOCKED_WITH_REASON` |

## Artifacts

| Platform | Registry digest | Configuration digest | Inventory | Source archive and SHA-256 | Publication checks |
| --- | --- | --- | --- | --- | --- |
| `PLATFORM` | `DIGEST` | `DIGEST` | `LINK` | `LINKS` | `RUN_URL_AND_RESULT` |

Combined manifest digest: `DIGEST`

## Checks and measurements

The evidence field describes how this release uses a report.
The result field preserves what the report observed.

| Check | Evidence | Original result | Report or run | Scope or omission reason |
| --- | --- | --- | --- | --- |
| `CHECK` | `NEW_OR_REUSED_OR_NOT_RUN` | `PASS_FAIL_PARTIAL_OR_UNKNOWN` | `LINK_OR_NONE` | `REASON` |

`NEW` means a measurement or check ran for this candidate.
`REUSED` means an earlier report supports only the stated scope.
`NOT_RUN` means no applicable result exists for this candidate.
Use `UNKNOWN` when no result exists.
Keep `FAIL` and `PARTIAL` visible when an earlier report contains them.

## Benchmark configuration

Use one block for each new or reused benchmark report.
Use `unknown` for missing historical fields.
Use `not applicable` for fields outside the measured path.
Missing fields can prevent reuse under the [release process](process.md).

| Field | Value |
| --- | --- |
| Report and measured commit | `LINK_AND_FULL_SHA` |
| Measurement date | `UTC_DATE` |
| Dataset | `STABLE_ID_OR_HASH_AND_DURATION` |
| Task and timing boundaries | `START_END_AND_EXCLUDED_STAGES` |
| Model | `NAME_REVISION_AND_PRECISION` |
| Notes configuration | `PROVIDER_MODEL_PROMPT_VERSION_LANGUAGE_AND_EFFORT` |
| Runtime | `IMAGE_DIGEST_OR_LOCKFILE_HASH_AND_NATIVE_VERSIONS` |
| Hardware | `CPU_RAM_GPU_AND_DRIVER` |
| Repetitions | `COUNT_AND_VARIATION` |
| Candidate differences | `RELEVANT_CODE_AND_CONFIGURATION_DIFF` |
| Reuse reason | `WHY_DIFFERENCES_DO_NOT_AFFECT_THE_STATED_SCOPE_OR_NOT_APPLICABLE` |

## Limitations and blockers

- `State each limitation, affected scope, issue link, and release decision.`
- `State each unresolved requirement that blocks release.`

Synthetic provider checks: `RESULT_AND_SCOPE`
Real provider authentication and inference: `RESULT_OR_NOT_RUN_WITH_REASON`
Fresh source installation: `RESULT_AND_LINK`
Fresh image installation: `RESULT_AND_LINK`
