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
import json
from pprint import pprint
import tempfile
import mistune
import itertools

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
        processing_headers = {}
        headers = [
            "Brief description",
            "Description"
        ]
        markdown = mistune.create_markdown(renderer="ast")
        markdown_obj = markdown(self.body)

        # first get all defined headers and its paragraphs
        actual_header = None
        for el_ in markdown_obj:
            if (
                el_["type"] == "heading"
                and el_["children"][0]["text"] in headers
            ):
                actual_header = el_["children"][0]["text"]
                processing_headers[actual_header] = []
            if (
                el_["type"] == "heading"
                and el_["children"][0]["text"] not in headers
            ):
                break
            elif (
                el_["type"] == "paragraph"
            ):
                processing_headers[actual_header].append(el_)

        parsed_body = {
            header: flatten_markdown_paragraph(paragraph)
            for header, paragraph in processing_headers.items()
        }

        return parsed_body

def flatten_markdown_paragraph(input, type=None):
    return_list = []
    if isinstance(input, list):
        print(f"__ type: {type}")
        nested_list = list(itertools.chain(*[flatten_markdown_paragraph(item, type) for item in input]))
        return_list.extend(nested_list)

    if "children" in input:
        nested_list = list(itertools.chain(*[flatten_markdown_paragraph(item, input.get("type")) for item in input["children"]]))
        if input.get('type') == "paragraph":
            return_list.append(nested_list)
        else:
            return_list.extend(nested_list)

    if "text" in input:
        text = input["text"]

        # add text style
        if type == "strong":
            text = "**" + text + "**"

        # condition for text with line endings
        if "\n" in text:
            return_list.extend(text.split("\n"))
        else:
            return_list.append(text)

    return return_list

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

    out_dict = {
        "milestone": milestone,
        "changelog": []
    }
    for pr_ in _pr["nodes"]:
        pull = PullRequestDescription(**pr_)
        # print("_" * 100)
        out_dict["changelog"].append(pull.get_content())

    pprint(out_dict)

    tfile = tempfile.NamedTemporaryFile(mode="w+")
    json.dump(out_dict, tfile)
    tfile.flush()

    print(tfile.name)

if __name__ == '__main__':
    main()
