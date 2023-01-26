import os
import requests
from dotenv import load_dotenv
from pprint import pprint

load_dotenv()

GITHUB_TOKEN = None


def run_query(query, query_variables):
    github_token = GITHUB_TOKEN or os.getenv("GITHUB_TOKEN")

    headers = {"Authorization": f"Bearer {github_token}"}
    # A simple function to use requests.post to make
    # the API call. Note the json= section.
    request = requests.post(
        'https://api.github.com/graphql',
        json={'query': query, "variables": query_variables},
        headers=headers
    )
    if request.status_code == 200:
      return request.json()
    else:
        raise Exception(
            "Query failed to run by returning "
            f"code of {request.status_code}. {query}"
        )



variables = {
    "owner": "ynput",
    "repo_name": "ci-testing",
    "milestone": "3.3.0"
}

query = """
query ($owner: String!, $repo_name: String!, $milestone: String!)
{
  repository(owner: $owner, name: $repo_name) {
    milestones(query: $milestone, first: 1) {
      nodes{
        title
        url
        pullRequests(states:[OPEN, MERGED], first: 50){
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
result = run_query(query, variables)
# Drill down the dictionary
milestone = result["data"]['repository']['milestones']['nodes'].pop()
_pr = milestone.pop("pullRequests")
print("_" * 100)
pprint(milestone)
pull_requests = _pr["nodes"]
pprint(pull_requests)

# rename this milestone to future `patch` release number
# create new milestone for `next-patch` and get number of the milestone
# devide PRs to `MERGED` status - those will be included in change log
# iteratte PRs with status `OPEN` and assign them to newly created milestone
request = requests.patch(
    "https://api.github.com/repos/pypeclub/ci-testing/issues/29",
    '{"milestone": 10}',
    headers=headers
)

if request.status_code == 200:
    pprint(request.json())
