""""
- def: rename milestone

- def: generate milestone changelog
    - iterate all milestone PR which are merged
    - devide PRs by categories via labels
        - follow config where categories have assigned labels
        - assign labels to host icons
    - get description and create markdown colapsed text
    - create title with host icons and sort them by host order
    - essamble full change log markdown and output as text
    - merge changelog text at beginning of CHANGELOG.md
    - add changelog text to milestone description
    - return change log text for other actions
"""

import os
import requests
from dotenv import load_dotenv
import click
from pprint import pprint

load_dotenv()

GITHUB_TOKEN = None
GITHUB_REPOSITORY_OWNER=None
GITHUB_REPOSITORY_NAME=None


@click.group()
def main():
    pass


def _get_request_header():
    github_token = GITHUB_TOKEN or os.getenv("GITHUB_TOKEN")

    return {"Authorization": f"Bearer {github_token}"}


def _run_github_query(query, query_variables):
    """Running query at Github

    Args:
        query (str): query text
        query_variables (dict): variables used inside of query

    Raises:
        Exception: _description_

    Returns:
        str: json text
    """


    try:
        # A simple function to use requests.post to make
        # the API call. Note the json= section.
        request = requests.post(
            'https://api.github.com/graphql',
            json={'query': query, "variables": query_variables},
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


@main.command(
    name="set-milestone-to-issue",
    help=(
        "Assign milestone to issue by ids. "
        "Returns JSON string with the edited issue"
    )
)
@click.option(
    "--milestone-id", required=True,
    help="Milestone ID number > `10`",
    type=click.INT
)
@click.option(
    "--issue-id", required=True,
    help="Issue ID number > `10`",
    type=click.INT
)
def assign_milestone_to_issue(milestone_id, issue_id):
    """Assign milestone to issue by ids

    Args:
        milestone_id (int): milestone number id
        issue_id (int): issue milestone id
    """
    owner =  GITHUB_REPOSITORY_OWNER or os.getenv("GITHUB_REPOSITORY_OWNER")
    repo_name = GITHUB_REPOSITORY_NAME or os.getenv("GITHUB_REPOSITORY_NAME")

    try:
        request = requests.patch(
            url=f"https://api.github.com/repos/{owner}/{repo_name}/issues/{issue_id}",
            data=f"{{\"milestone\": {milestone_id}}}",
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

    print(request.json())


class PullRequestDescription:
    title: str
    body: str
    url: str

    def __init__(
        self, title:str, body:str, url:str,
        *args, **kwargs
    ) -> None:
        self.title = title
        self.body = body
        self.url = url

    def get_content(self) -> str:
        return self.body

@main.command(
    name="get-milestone-changelog",
    help=(
        "Generate changelong form input milestone. "
        "Returns markdown text with changelog"
    )
)
@click.option(
    "--milestone", required=True,
    help="Name of milestone > `1.0.1`"
)
def generate_milestone_changelog(milestone):
    """Generate changelog from input milestone

    Args:
        milestone (str): milestone name
    """
    variables = {
        "owner": GITHUB_REPOSITORY_OWNER or os.getenv("GITHUB_REPOSITORY_OWNER"),
        "repo_name": GITHUB_REPOSITORY_NAME or os.getenv("GITHUB_REPOSITORY_NAME"),
        "milestone": milestone,
        "num_prs": 1
    }

    query = """
        query (
            $owner: String!, $repo_name: String!, $milestone: String!, $num_prs: Int!
        ){
            repository(owner: $owner, name: $repo_name) {
                milestones(query: $milestone, first: 1) {
                    nodes{
                        title
                        url
                        number
                        pullRequests(states:[OPEN, MERGED], first: $num_prs){
                            nodes{
                                title
                                body
                                state
                                url
                            }
                        }
                    }
                }
            }
        }
    """

    # Execute the query
    result = _run_github_query(query, variables)
    # Drill down the dictionary
    milestone = result["data"]['repository']['milestones']['nodes'].pop()
    _pr = milestone.pop("pullRequests")

    print("_" * 100)
    pprint(milestone)

    for pr_ in _pr["nodes"]:
        pull = PullRequestDescription(**pr_)
        print("_" * 100)
        print(pull.get_content())


if __name__ == '__main__':
    main()
