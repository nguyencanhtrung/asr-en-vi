# Project instructions

## GitHub issue tracker

This repository uses GitHub Issues for specifications and implementation tickets.

Before a skill publishes or triages an issue, read both of these project files:

- `docs/agents/issue-tracker.md`
- `docs/agents/triage-labels.md`

Treat `needs-triage`, `needs-info`, `ready-for-agent`, `ready-for-human`, and `wontfix` as canonical triage roles. Resolve each role through the project mapping before applying a GitHub label.

These tracker and triage conventions apply only to this repository and override broader defaults for the same workflow.

## Pull request cleanup

After merging a pull request, verify the base branch contains the merge, switch the local worktree to that base branch, fast-forward it, and delete the local source branch with `git branch -d`. Verify that GitHub deleted the remote source branch through the repository's automatic head-branch cleanup setting. If the local branch is not fully merged, stop and report the remaining commits instead of force-deleting it.
