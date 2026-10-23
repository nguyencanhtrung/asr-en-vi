#!/usr/bin/env python3
"""Fail a pull request check while its linked issues have unresolved acceptance criteria.

A linked issue passes when every checkbox in its "Acceptance criteria" section is
ticked, or is left unticked with a "Not done: <reason>" note on the same line.
"""

from __future__ import annotations

import json
import os
import re
import subprocess

WORKFLOW = "acceptance-criteria.yml"
HEADING = re.compile(r"^#{1,6}\s+acceptance criteria\s*$", re.IGNORECASE)
UNTICKED = re.compile(r"^\s*[-*+]\s+\[ \]\s+(.*)$")


def unresolved_criteria(body: str) -> list[str]:
    """Return unticked criteria that carry no "Not done:" reason."""
    unresolved: list[str] = []
    in_section = False
    for line in body.splitlines():
        if line.startswith("#"):
            in_section = bool(HEADING.match(line.strip()))
            continue
        match = UNTICKED.match(line) if in_section else None
        if match and "not done:" not in match.group(1).lower():
            unresolved.append(match.group(1).strip())
    return unresolved


def graphql(query: str, **variables: object) -> dict:
    command = ["gh", "api", "graphql", "-f", f"query={query}"]
    for name, value in variables.items():
        command += ["-F", f"{name}={value}"]
    output = subprocess.run(command, check=True, capture_output=True, text=True).stdout
    return json.loads(output)["data"]["repository"]


def pull_requests_for_issue(owner: str, name: str, issue: int) -> list[int]:
    data = graphql(
        """query($owner: String!, $name: String!, $number: Int!) {
          repository(owner: $owner, name: $name) {
            issue(number: $number) {
              closedByPullRequestsReferences(first: 50, includeClosedPrs: false) {
                nodes { number }
              }
            }
          }
        }""",
        owner=owner,
        name=name,
        number=issue,
    )
    return [node["number"] for node in data["issue"]["closedByPullRequestsReferences"]["nodes"]]


def check_pull_request(repository: str, number: int) -> bool:
    owner, name = repository.split("/")
    data = graphql(
        """query($owner: String!, $name: String!, $number: Int!) {
          repository(owner: $owner, name: $name) {
            pullRequest(number: $number) {
              closingIssuesReferences(first: 50) { nodes { number body } }
            }
          }
        }""",
        owner=owner,
        name=name,
        number=number,
    )["pullRequest"]
    passed = True
    for issue in data["closingIssuesReferences"]["nodes"]:
        for criterion in unresolved_criteria(issue["body"]):
            print(
                f"::error::Issue #{issue['number']}: tick or add 'Not done: <reason>': {criterion}"
            )
            passed = False
    return passed


def rerun_pull_request_check(repository: str, number: int) -> None:
    """Re-run the PR's latest check so the required check reflects the edited issue."""
    branch = subprocess.run(
        ["gh", "pr", "view", str(number), "--repo", repository, "--json", "headRefName"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    runs = subprocess.run(
        [
            "gh",
            "run",
            "list",
            "--repo",
            repository,
            "--workflow",
            WORKFLOW,
            "--event",
            "pull_request",
            "--branch",
            json.loads(branch)["headRefName"],
            "--limit",
            "1",
            "--json",
            "databaseId",
        ],
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    for run in json.loads(runs):
        subprocess.run(
            ["gh", "run", "rerun", str(run["databaseId"]), "--repo", repository], check=True
        )
        print(f"PR #{number}: re-ran check run {run['databaseId']}")


def main() -> int:
    repository = os.environ["GITHUB_REPOSITORY"]
    if os.environ.get("ISSUE_NUMBER"):
        owner, name = repository.split("/")
        for number in pull_requests_for_issue(owner, name, int(os.environ["ISSUE_NUMBER"])):
            rerun_pull_request_check(repository, number)
        return 0
    return 0 if check_pull_request(repository, int(os.environ["PR_NUMBER"])) else 1


if __name__ == "__main__":
    raise SystemExit(main())
