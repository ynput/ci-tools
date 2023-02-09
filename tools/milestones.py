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

import os
from pprint import pprint
import requests
from dotenv import load_dotenv


load_dotenv()

GITHUB_TOKEN = None
GITHUB_REPOSITORY_OWNER=None
GITHUB_REPOSITORY_NAME=None



QUERY = """
    query (
        $owner: String!, $repo_name: String!, $milestone: String!, $num_prs: Int!
    ){
        repository(owner: $owner, name: $repo_name) {
            milestones(query: $milestone, first: 1) {
                nodes{
                    title
                    url
                    number
                    pullRequests(states:[MERGED], first: $num_prs){
                        totalCount
                    }
                }
            }
        }
    }
"""

def _get_request_header():
    github_token = GITHUB_TOKEN or os.getenv("GITHUB_TOKEN")

    return {"Authorization": f"Bearer {github_token}"}


def _run_github_query(milestone):
    """Running query at Github

    Args:
        milestone (str): milestone name

    Raises:
        Exception: _description_

    Returns:
        str: json text
    """
    variables = {
        "owner": GITHUB_REPOSITORY_OWNER or os.getenv("GITHUB_REPOSITORY_OWNER"),
        "repo_name": GITHUB_REPOSITORY_NAME or os.getenv("GITHUB_REPOSITORY_NAME"),
        "milestone": milestone,
        "num_prs": 10
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

pprint(_run_github_query("next-patch"))