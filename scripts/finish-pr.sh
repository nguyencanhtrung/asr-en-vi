#!/bin/sh
set -eu

if [ "$#" -ne 1 ]; then
    echo "Usage: scripts/finish-pr.sh PR_NUMBER" >&2
    exit 2
fi
pull_request_number=$1
case "$pull_request_number" in
    ""|*[!0-9]*)
        echo "PR_NUMBER must be a positive integer." >&2
        exit 2
        ;;
    0)
        echo "PR_NUMBER must be a positive integer." >&2
        exit 2
        ;;
esac

if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    echo "Run this script from a Git working tree." >&2
    exit 1
fi
if ! command -v gh >/dev/null 2>&1; then
    echo "GitHub CLI (gh) is required to verify pull request status." >&2
    exit 1
fi

json_field() {
    printf '%s\n' "$1" | python3 -c '
import json
import sys

value = json.load(sys.stdin)
for part in sys.argv[1].split("."):
    value = value.get(part) if isinstance(value, dict) else None
if value is None:
    print("")
elif isinstance(value, (dict, list)):
    print(json.dumps(value))
else:
    print(value)
' "$2"
}

if ! origin_url=$(git remote get-url origin 2>/dev/null); then
    echo "An origin remote is required to verify the merged base and deleted source." >&2
    exit 1
fi
repository_json=$(gh repo view "$origin_url" --json nameWithOwner)
repository_name=$(json_field "$repository_json" nameWithOwner)
case "$repository_name" in
    */*) ;;
    *)
        echo "Could not determine the GitHub repository for this working tree." >&2
        exit 1
        ;;
esac
repository_settings=$(gh api "repos/$repository_name")
auto_delete=$(json_field "$repository_settings" delete_branch_on_merge)
if [ "$auto_delete" != "True" ] && [ "$auto_delete" != "true" ]; then
    echo "GitHub delete_branch_on_merge is disabled for $repository_name." >&2
    exit 1
fi

pull_request_json=$(gh pr view "$pull_request_number" --repo "$repository_name" \
    --json state,mergedAt,baseRefName,headRefName,headRefOid,mergeCommit,isCrossRepository)
pull_request_state=$(json_field "$pull_request_json" state)
merged_at=$(json_field "$pull_request_json" mergedAt)
base_branch=$(json_field "$pull_request_json" baseRefName)
source_branch=$(json_field "$pull_request_json" headRefName)
source_oid=$(json_field "$pull_request_json" headRefOid)
merge_oid=$(json_field "$pull_request_json" mergeCommit.oid)
is_cross_repository=$(json_field "$pull_request_json" isCrossRepository)
if [ "$pull_request_state" != "MERGED" ] || [ -z "$merged_at" ]; then
    echo "PR #$pull_request_number is not merged." >&2
    exit 1
fi
if [ -z "$base_branch" ] || [ -z "$source_branch" ] || [ -z "$source_oid" ] || [ -z "$merge_oid" ]; then
    echo "PR #$pull_request_number is missing branch or merge commit metadata." >&2
    exit 1
fi
if [ "$is_cross_repository" = "True" ] || [ "$is_cross_repository" = "true" ]; then
    echo "PR #$pull_request_number comes from a fork; verify and delete that remote branch separately." >&2
    exit 1
fi
if [ "$base_branch" = "$source_branch" ] || \
    ! git check-ref-format --branch "$base_branch" >/dev/null 2>&1 || \
    ! git check-ref-format --branch "$source_branch" >/dev/null 2>&1; then
    echo "PR #$pull_request_number has invalid or identical base and source branches." >&2
    exit 1
fi

if ! git diff --quiet || ! git diff --cached --quiet; then
    echo "Tracked changes must be clean before finishing a pull request." >&2
    exit 1
fi

source_branch_exists=false
if git show-ref --verify --quiet "refs/heads/$source_branch"; then
    source_branch_exists=true
    local_source_oid=$(git rev-parse "refs/heads/$source_branch")
    if [ "$local_source_oid" != "$source_oid" ]; then
        echo "Local branch $source_branch does not match PR head $source_oid." >&2
        exit 1
    fi
fi

if ! current_branch=$(git symbolic-ref --quiet --short HEAD); then
    echo "Switch to the PR source or base branch before finishing it." >&2
    exit 1
fi
case "$current_branch" in
    "$source_branch"|"$base_branch") ;;
    *)
        echo "Current branch $current_branch is neither PR source $source_branch nor base $base_branch." >&2
        exit 1
        ;;
esac
if [ "$source_branch_exists" = false ] && [ "$current_branch" != "$base_branch" ]; then
    echo "Local source branch $source_branch is missing while not on base $base_branch." >&2
    exit 1
fi
if ! git fetch --quiet origin "+refs/heads/$base_branch:refs/remotes/origin/$base_branch"; then
    echo "Could not fetch origin/$base_branch." >&2
    exit 1
fi
if ! git merge-base --is-ancestor "$merge_oid" "refs/remotes/origin/$base_branch"; then
    echo "origin/$base_branch does not contain merge commit $merge_oid." >&2
    exit 1
fi
if git show-ref --verify --quiet "refs/heads/$base_branch" && \
    ! git merge-base --is-ancestor "refs/heads/$base_branch" "refs/remotes/origin/$base_branch"; then
    echo "Local base branch $base_branch has commits not present in origin/$base_branch." >&2
    exit 1
fi

set +e
remote_source=$(git ls-remote --exit-code --heads origin "refs/heads/$source_branch" 2>&1)
remote_status=$?
set -e
if [ "$remote_status" -eq 0 ]; then
    echo "Remote source branch $source_branch still exists on origin." >&2
    exit 1
fi
if [ "$remote_status" -ne 2 ]; then
    echo "Could not verify that remote source branch $source_branch is absent." >&2
    if [ -n "$remote_source" ]; then
        echo "$remote_source" >&2
    fi
    exit 1
fi

if [ "$source_branch_exists" = true ] && \
    ! git merge-base --is-ancestor "$source_oid" "refs/remotes/origin/$base_branch"; then
    remaining_count=$(git rev-list --count "refs/remotes/origin/$base_branch..refs/heads/$source_branch")
    echo "Local source branch $source_branch has $remaining_count commit(s) not present in origin/$base_branch." >&2
    git log --oneline "refs/remotes/origin/$base_branch..refs/heads/$source_branch" >&2
    exit 1
fi

if [ "$current_branch" != "$base_branch" ]; then
    if git show-ref --verify --quiet "refs/heads/$base_branch"; then
        git switch "$base_branch"
    else
        git switch --track -c "$base_branch" "origin/$base_branch"
    fi
fi
git merge --ff-only "refs/remotes/origin/$base_branch"

# A merged PR does not make the base green; report failures so "done" is not claimed over a red base.
failed_runs=$(gh run list --repo "$repository_name" --branch "$base_branch" --limit 10 \
    --json conclusion,workflowName,headSha,url \
    --jq '.[] | select(.conclusion == "failure") | "\(.workflowName) \(.headSha[0:7]) \(.url)"' 2>/dev/null || true)
if [ -n "$failed_runs" ]; then
    echo "WARNING: recent failed workflow runs on $base_branch:" >&2
    printf '%s\n' "$failed_runs" >&2
fi

if [ "$source_branch_exists" = true ]; then
    if ! git branch -d "$source_branch"; then
        echo "Git refused to delete local source branch $source_branch; it remains in place." >&2
        exit 1
    fi
    echo "Switched to $base_branch and deleted local branch $source_branch."
else
    echo "PR #$pull_request_number is already finished on $base_branch."
fi
