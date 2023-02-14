"""
set_milestone_name:
    is milestone any pullrequestes?
        true:
            - go to next step
        else:
            - return False
    is milestone `next-patch` or `next-minor`
        true:
            - get latest semver from tags (path/minor)
            - rename milestone (if not pre-release)
            - return new milestone name
        false:
            - return milestone name
"""

import click
from pprint import pprint
import requests
import re
from utils import Printer
from repository import (
    GithubConnect
)

printer = Printer()

MILESTONE_COMMIT_DESCRIPTION = "closing-commit-hash:"

QUERY = """
    query (
        $repo_owner: String!, $repo_name: String!, $milestone: String!
    ){
        repository(owner: $repo_owner, name: $repo_name) {
            milestones(query: $milestone, first: 1) {
                nodes{
                    title
                    url
                    number
                    description
                }
            }
        }
    }
"""

def _get_request_header():
    repo_connect = GithubConnect()

    return {"Authorization": f"Bearer {repo_connect.token}"}


def _run_github_query(milestone):
    """Running query at Github

    Args:
        milestone (str): milestone name

    Raises:
        Exception: _description_

    Returns:
        str: json text
    """
    repo_connect = GithubConnect()

    variables = {
        "repo_owner": repo_connect.owner,
        "repo_name": repo_connect.name,
        "milestone": milestone
    }

    try:
        # A simple function to use requests.post to make
        # the API call. Note the json= section.
        request = requests.post(
            'https://api.github.com/graphql',
            json={'query': QUERY, "variables": variables},
            headers=_get_request_header(),
            timeout=3
        )
        request.raise_for_status()
    except requests.exceptions.RequestException as err:
        raise requests.exceptions.RequestException(f"Request error: {err}")
    except requests.exceptions.HTTPError as errh:
        raise requests.exceptions.HTTPError(f"Http Error: {errh}")
    except requests.exceptions.ConnectionError as errc:
        raise requests.exceptions.ConnectionError(f"Error Connecting: {errc}")
    except requests.exceptions.Timeout as errt:
        raise requests.exceptions.Timeout(f"Timeout Error: {errt}")

    return request.json()


def get_commit_from_milestone_description(milestone):
    """Returns a closing commit sha if

    it is found in descriptions

    Args:
        milestone (str): milestone title

    Returns:
        str: commit sha
    """
    pattern = re.compile(f"(?:({MILESTONE_COMMIT_DESCRIPTION}\s))([a-z0-9]+)")
    query_back = _run_github_query(milestone)
    returned_nodes = query_back["data"]["repository"]["milestones"]["nodes"]
    milestone_data = next(
        iter(m for m in returned_nodes if milestone == m["title"]),
        None
    )

    if milestone_data:
        matching_groups = pattern.findall(milestone_data["description"])
        if not matching_groups:
            return
        match = matching_groups.pop()
        return match[-1]


@click.command(
    name="get-milestone-commit",
    help=(
        "Get commit from milestone description"
    )
)
@click.option(
    "--milestone", required=True,
    help="Name of milestone > `1.0.1`"
)
def get_commit_from_milestone_description_cli(milestone):
    """Wrapping cli function

    Returns a closing commit sha if
    it is found in descriptions

    Args:
        milestone (str): milestone title

    Returns:
        str: commit sha
    """
    commit_sha = get_commit_from_milestone_description(milestone)
    if commit_sha:
        print(commit_sha)


@click.command(
    name="set-milestone-commit",
    help=(
        "Set commit to milestone description"
    )
)
@click.option(
    "--milestone", required=True,
    help="Name of milestone > `1.0.1`"
)
def set_commit_to_milestone_description(milestone, commit_sha):
    milestone_obj = _run_github_query(milestone)
    print(milestone_obj["description"])
