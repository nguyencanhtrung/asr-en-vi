#!/usr/bin/env python3
"""Set the acceptance-criteria commit status on pull requests from their linked issues.

A linked issue passes when every checkbox in its "Acceptance criteria" section is
ticked, or is left unticked with a "Not done: <reason>" note on the same line.
"""

from __future__ import annotations

import json
import os
import re
import subprocess

CONTEXT = "acceptance-criteria"
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
              headRefOid
              closingIssuesReferences(first: 50) { nodes { number body } }
            }
          }
        }""",
        owner=owner,
        name=name,
        number=number,
    )["pullRequest"]
    failing = []
    for issue in data["closingIssuesReferences"]["nodes"]:
        for criterion in unresolved_criteria(issue["body"]):
            print(f"PR #{number}: issue #{issue['number']} unresolved: {criterion}")
            failing.append(issue["number"])
    if failing:
        issues = ", ".join(f"#{n}" for n in sorted(set(failing)))
        state, description = "failure", f"Tick or explain (Not done: ...) criteria in {issues}"
    else:
        state, description = "success", "All linked acceptance criteria resolved"
    subprocess.run(
        [
            "gh",
            "api",
            "--method",
            "POST",
            f"repos/{repository}/statuses/{data['headRefOid']}",
            "-f",
            f"state={state}",
            "-f",
            f"context={CONTEXT}",
            "-f",
            f"description={description[:140]}",
        ],
        check=True,
        capture_output=True,
    )
    print(f"PR #{number}: {state}")
    return state == "success"


def main() -> None:
    repository = os.environ["GITHUB_REPOSITORY"]
    if os.environ.get("ISSUE_NUMBER"):
        owner, name = repository.split("/")
        numbers = pull_requests_for_issue(owner, name, int(os.environ["ISSUE_NUMBER"]))
    else:
        numbers = [int(os.environ["PR_NUMBER"])]
    for number in numbers:
        check_pull_request(repository, number)


if __name__ == "__main__":
    main()
