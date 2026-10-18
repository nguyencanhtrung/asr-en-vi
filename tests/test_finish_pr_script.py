from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[1]
FINISH_SCRIPT = ROOT / "scripts" / "finish-pr.sh"
pytestmark = pytest.mark.timeout(30)


def git(repository: Path, *arguments: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *arguments],
        cwd=repository,
        text=True,
        capture_output=True,
        check=check,
    )


def create_pull_request_repository(
    tmp_path: Path,
    *,
    push_merge: bool = True,
    delete_remote_source: bool = True,
    advance_remote_base: bool = False,
    squash_merge: bool = False,
) -> tuple[Path, dict[str, object]]:
    remote = tmp_path / "origin.git"
    subprocess.run(
        ["git", "init", "--bare", "--initial-branch=main", str(remote)],
        check=True,
        capture_output=True,
        text=True,
    )
    repository = tmp_path / "repository"
    repository.mkdir()
    git(repository, "init", "--initial-branch=main")
    git(repository, "config", "user.name", "Delivery Test")
    git(repository, "config", "user.email", "delivery@example.test")
    (repository / "tracked.txt").write_text("base\n", encoding="utf-8")
    git(repository, "add", "tracked.txt")
    git(repository, "commit", "-m", "base")
    git(repository, "remote", "add", "origin", str(remote))
    git(repository, "push", "-u", "origin", "main")

    git(repository, "switch", "-c", "chore/guardrails")
    (repository / "change.txt").write_text("merged\n", encoding="utf-8")
    git(repository, "add", "change.txt")
    git(repository, "commit", "-m", "delivery changes")
    source_oid = git(repository, "rev-parse", "HEAD").stdout.strip()
    git(repository, "push", "-u", "origin", "chore/guardrails")

    git(repository, "switch", "main")
    if squash_merge:
        git(repository, "merge", "--squash", "chore/guardrails")
        git(repository, "commit", "-m", "Squash pull request #17")
    else:
        git(repository, "merge", "--no-ff", "chore/guardrails", "-m", "Merge pull request #17")
    merge_oid = git(repository, "rev-parse", "HEAD").stdout.strip()
    if push_merge:
        git(repository, "push", "origin", "main")
    if advance_remote_base:
        (repository / "followup.txt").write_text("remote update\n", encoding="utf-8")
        git(repository, "add", "followup.txt")
        git(repository, "commit", "-m", "advance remote base")
        git(repository, "push", "origin", "main")
        git(repository, "reset", "--hard", merge_oid)
    if delete_remote_source:
        git(repository, "push", "origin", "--delete", "chore/guardrails")
    git(repository, "switch", "chore/guardrails")

    return repository, {
        "state": "MERGED",
        "mergedAt": "2026-10-18T12:00:00Z",
        "baseRefName": "main",
        "headRefName": "chore/guardrails",
        "headRefOid": source_oid,
        "mergeCommit": {"oid": merge_oid},
        "isCrossRepository": False,
    }


def stub_gh(tmp_path: Path, pull_request: dict[str, object], *, auto_delete: bool = True) -> Path:
    stub_directory = tmp_path / "stub-bin"
    stub_directory.mkdir(exist_ok=True)
    pull_request_path = tmp_path / "pull-request.json"
    pull_request_path.write_text(json.dumps(pull_request), encoding="utf-8")
    auto_delete_json = json.dumps({"delete_branch_on_merge": auto_delete})
    gh_script = f"""#!/bin/sh
case "$1" in
  repo)
    if [ "$2" != view ] || [ "$4" != --json ] || [ "$5" != nameWithOwner ]; then exit 90; fi
    printf '%s\\n' '{{"nameWithOwner":"example/project"}}' ;;
  api)
    if [ "$2" != repos/example/project ] || [ $# -ne 2 ]; then exit 90; fi
    printf '%s\\n' '{auto_delete_json}' ;;
  pr)
    if [ "$2" != view ] || [ "$3" != 17 ] || [ "$4" != --repo ] || \
       [ "$5" != example/project ] || [ "$6" != --json ]; then exit 90; fi
    cat "$GH_PULL_REQUEST_JSON" ;;
  *) echo "unexpected gh command: $*" >&2; exit 90 ;;
esac
"""
    (stub_directory / "gh").write_text(gh_script, encoding="utf-8")
    (stub_directory / "gh").chmod(0o755)
    return stub_directory


def run_finish(
    repository: Path,
    stub_directory: Path,
    pull_request_path: Path,
) -> subprocess.CompletedProcess[str]:
    environment = os.environ.copy()
    environment["PATH"] = f"{stub_directory}:{environment['PATH']}"
    environment["GH_PULL_REQUEST_JSON"] = str(pull_request_path)
    return subprocess.run(
        [str(FINISH_SCRIPT), "17"],
        cwd=repository,
        env=environment,
        text=True,
        capture_output=True,
        check=False,
    )


def setup_script_stub(
    tmp_path: Path,
    pull_request: dict[str, object],
    *,
    auto_delete: bool = True,
) -> tuple[Path, Path]:
    stub_directory = stub_gh(tmp_path, pull_request, auto_delete=auto_delete)
    return stub_directory, tmp_path / "pull-request.json"


def test_finish_pr_switches_to_updated_base_and_preserves_untracked_files(tmp_path):
    repository, pull_request = create_pull_request_repository(tmp_path, advance_remote_base=True)
    untracked = repository / "operator-notes.txt"
    untracked.write_text("keep this file\n", encoding="utf-8")
    stub_directory, pull_request_path = setup_script_stub(tmp_path, pull_request)

    first_run = run_finish(repository, stub_directory, pull_request_path)

    assert first_run.returncode == 0, first_run.stdout + first_run.stderr
    assert git(repository, "branch", "--show-current").stdout.strip() == "main"
    local_base = git(repository, "rev-parse", "main").stdout
    remote_base = git(repository, "rev-parse", "origin/main").stdout
    assert local_base == remote_base
    assert (repository / "followup.txt").read_text(encoding="utf-8") == "remote update\n"
    source_branch_ref = "refs/heads/chore/guardrails"
    assert git(repository, "show-ref", "--verify", source_branch_ref, check=False).returncode != 0
    assert untracked.read_text(encoding="utf-8") == "keep this file\n"
    merge_oid = str(pull_request["mergeCommit"]["oid"])
    assert (
        git(
            repository,
            "merge-base",
            "--is-ancestor",
            merge_oid,
            "origin/main",
            check=False,
        ).returncode
        == 0
    )
    assert git(repository, "ls-remote", "--heads", "origin", source_branch_ref).stdout == ""

    second_run = run_finish(repository, stub_directory, pull_request_path)

    assert second_run.returncode == 0, second_run.stdout + second_run.stderr
    assert git(repository, "branch", "--show-current").stdout.strip() == "main"
    assert untracked.read_text(encoding="utf-8") == "keep this file\n"


@pytest.mark.parametrize(
    "failure",
    [
        "not-merged",
        "auto-delete-disabled",
        "local-head-moved",
        "base-missing-merge",
        "remote-head-present",
        "tracked-dirty",
        "fork-pr",
        "local-base-diverged",
    ],
)
def test_finish_pr_stops_before_switching_when_cleanup_preconditions_fail(tmp_path, failure):
    repository, pull_request = create_pull_request_repository(
        tmp_path,
        push_merge=failure != "base-missing-merge",
        delete_remote_source=failure != "remote-head-present",
    )
    auto_delete = failure != "auto-delete-disabled"
    if failure == "not-merged":
        pull_request.update(state="OPEN", mergedAt=None, mergeCommit=None)
    elif failure == "local-head-moved":
        git(repository, "commit", "--allow-empty", "-m", "local change after merge")
    elif failure == "tracked-dirty":
        (repository / "tracked.txt").write_text("local edit\n", encoding="utf-8")
    elif failure == "fork-pr":
        pull_request["isCrossRepository"] = True
    elif failure == "local-base-diverged":
        git(repository, "switch", "main")
        git(repository, "commit", "--allow-empty", "-m", "local base commit")
        git(repository, "switch", "chore/guardrails")

    stub_directory, pull_request_path = setup_script_stub(
        tmp_path, pull_request, auto_delete=auto_delete
    )

    result = run_finish(repository, stub_directory, pull_request_path)

    assert result.returncode != 0
    expected_error = {
        "not-merged": "pr #17 is not merged",
        "auto-delete-disabled": "delete_branch_on_merge is disabled",
        "local-head-moved": "does not match pr head",
        "base-missing-merge": "origin/main does not contain merge commit",
        "remote-head-present": "remote source branch chore/guardrails still exists",
        "tracked-dirty": "tracked changes must be clean",
        "fork-pr": "comes from a fork",
        "local-base-diverged": "local base branch main has commits not present",
    }[failure]
    assert expected_error in result.stderr.casefold()
    assert git(repository, "branch", "--show-current").stdout.strip() == "chore/guardrails"
    assert (
        git(
            repository, "show-ref", "--verify", "refs/heads/chore/guardrails", check=False
        ).returncode
        == 0
    )
    if failure == "tracked-dirty":
        assert (repository / "tracked.txt").read_text(encoding="utf-8") == "local edit\n"


def test_finish_pr_keeps_local_source_after_squash_merge_when_git_does_not_consider_it_merged(
    tmp_path,
):
    repository, pull_request = create_pull_request_repository(tmp_path, squash_merge=True)
    stub_directory, pull_request_path = setup_script_stub(tmp_path, pull_request)

    result = run_finish(repository, stub_directory, pull_request_path)

    assert result.returncode != 0
    assert "has 1 commit(s) not present in origin/main" in result.stderr
    assert git(repository, "branch", "--show-current").stdout.strip() == "chore/guardrails"
    assert (
        git(
            repository,
            "show-ref",
            "--verify",
            "refs/heads/chore/guardrails",
            check=False,
        ).returncode
        == 0
    )
