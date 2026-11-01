# Historical notes evidence

These records describe earlier notes pipelines.
The [original report](archive/v0.1.0/notes-v0.1.0.md) retains full quality tables and implementation details.
They do not establish quality or latency for the current release.

## Output recovery: #72 and PR #94

Revision `3c96052` retried oversized output with a smaller length target.
A 75-minute sample completed after 798.5 seconds with 16 calls and one recovery.
The earlier run at `151f3e4` failed after 571.3 seconds with 13 calls.
A failure duration and a completion duration do not measure the same endpoint.

The later composite run at `4a88ec8` still failed after recovery attempts ended.
A requested length does not enforce the actual output length.
The original report records repair and diagnostic limitations under #95, #96, and #102.

## Single-pass planning: #104 and PR #109

Revision `b78711d` used prompt `notes-hierarchical-v7`.
The planner used model-specific context budgets for two configured provider/model pairs.
Large inputs still used chunking and reduction.
Citation units grouped adjacent segments when a source exceeded 999 segments.
Restoration returned the original segment identifiers.

The measured ChatGPT runs completed with one call each.
Missing findings and misplaced decisions prevented a complete quality claim.
The [performance summary](performance-v0.1.0.md) records timings and strict findings.

## Prompt wording: #100 and PR #111

Prompt `notes-hierarchical-v8` used short statements and one idea per item.
The experiment used ChatGPT `gpt-5.6-sol`, medium effort, and English notes.
It included one run per meeting and one AI scorer per run.

| Sample | Strict findings, v7 → c2 | Repeated ideas, v7 → c2 | c2 latency |
| --- | --- | --- | --- |
| A | 41 → 44 | 27 → 12 | 112.4 s |
| C | 31 → 33 | 38 → 19 | 91.3 s |
| B | 28 → 26 | 15 → 15 | 81.4 s |

Sample B lost strict findings relative to its baseline.
Repeated ideas remained in all three samples.
The original report records unmet criteria and follow-up #110.
Real chunk/reduce runs did not validate the changed prompt in this experiment.
Historical issue references do not state current issue status.
