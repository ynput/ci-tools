import os
import re
import json
import platform
from pprint import pprint
from dotenv import load_dotenv
import requests
import asyncio
import aiohttp
from datetime import datetime

load_dotenv()

repo_owner = "ynput"
repo_name = "OpenPype"
headers = {
    "Content-Type": "application/json",
    "Authorization": f"Bearer {os.getenv('GITHUB_TOKEN')}"
}

json_file_path = "temp_file.json"

def get_pulls_from_repository(from_pr_number, to_pr_number):
    """Get a list of pull requests from the repository."""
    def return_range(prs):
        return [pr for pr in prs if from_pr_number <= pr["number"] <= to_pr_number]

    global repo_owner, repo_name, json_file_path

    if os.path.exists(json_file_path):
        with open(json_file_path, 'r') as file:
            prs_ = json.load(file)
            return return_range(prs_)

    # Define the GraphQL query
    query = """
        query (
            $owner: String!, $repo_name: String!,
            $max_count: Int!, $after_cursor: String, $states: [PullRequestState!]) {
                repository(owner: $owner, name: $repo_name) {
                pullRequests(states: $states, first: $max_count, after: $after_cursor) {
                    edges {
                    node {
                        number
                        title
                        mergedAt
                        mergedBy {
                        login
                        }
                        baseRefName
                        headRefName
                    }
                    cursor
                    }
                    pageInfo {
                    endCursor
                    hasNextPage
                }
                }
            }
        }
    """

    # Set the necessary parameters
    access_token = os.getenv("GITHUB_TOKEN")
    max_count = 100  # The maximum number of pull requests to retrieve at once

    # Set up the variables for the GraphQL query
    variables = {
        "states": "MERGED",
        "max_count": max_count,
        "repo_name": repo_name,
        "owner": repo_owner
    }

    _pull_requests = []

    # Loop through the pages of pull requests until we hit the end or the last pull request we want
    has_next_page = True
    end_cursor = None
    while has_next_page:
        # Update the cursor variable for the next page of pull requests
        if end_cursor:
            variables["after_cursor"] = end_cursor

        # Send the GraphQL query to the GitHub API
        headers = {'Authorization': f'Bearer {access_token}'}
        response = requests.post(
            'https://api.github.com/graphql',
            json={'query': query, "variables": variables},
            headers=headers
        )

        # Parse the response into JSON
        data = json.loads(response.text)

        # Retrieve the pull requests from the response data
        pull_requests_page = [edge['node'] for edge in data['data']['repository']['pullRequests']['edges']]

        # Add the pull requests to the list of pull requests we're collecting
        _pull_requests += pull_requests_page

        # Check if there are more pages of pull requests to retrieve
        page_info = data['data']['repository']['pullRequests']['pageInfo']
        has_next_page = page_info['hasNextPage']
        end_cursor = page_info['endCursor']
        print(f"Collected PRs {len(_pull_requests)}")

    # Save text to temporary file
    with open(json_file_path, 'w') as file:
        json.dump(_pull_requests, file)

    # Return the list of pull requests which match the given range
    return return_range(_pull_requests)

async def get_request_to_session(session, url):
    global headers
    async with session.get(url, headers=headers ) as resp:
        return await resp.json()

async def put_clickup_request(session, url, payload, query):
    headers_ = {
        "Content-Type": "application/json",
        "Authorization": os.getenv("CLICKUP_API_KEY")
    }
    async with session.post(url, json=payload, headers=headers_, params=query ) as resp:
            return await resp.json()

async def set_release_names_to_clickup(session, pull, release_version, skipping_prs):

    pr_number = pull["number"]
    pr_title = pull["title"]
    pr_head_ref = pull["headRefName"]
    field_id = os.getenv("CLICKUP_RELEASE_FIELD_ID")

    query = {
        "custom_task_ids": "true",
        "team_id": os.getenv("CLICKUP_TEAM_ID")
    }

    # Return the latest release tag name
    clickup_custom_id = None
    found = re.findall(r"OP-\d{4}", pr_head_ref)
    if found:
        clickup_custom_id = found.pop()
        print(f"Found Clickup ID {clickup_custom_id}")

    if not clickup_custom_id:
        skipping_prs.append(str(pr_number))
        return

    payload = {
        "value": release_version
    }

    url = (
        f"https://api.clickup.com/api/v2/task/{clickup_custom_id}"
        f"/field/{field_id}"
    )
    print(url)
    response = await put_clickup_request(session, url, payload, query)

    if "error" in response:
        print(f"Error: {response['error']}")
        return

    return f"Processing PR: '{pr_number}' / '{pr_title}' / '{pr_head_ref}' CU Task: '{clickup_custom_id}'"

async def get_release(pull, session):
    global repo_owner, repo_name

    pr_number = pull["number"]

    # Get pull request details
    pr_url = f"https://api.github.com/repos/{repo_owner}/{repo_name}/pulls/{pr_number}"
    pr_response = await get_request_to_session(session, pr_url)

    # Get all the merged commits related to the pull request
    if "merge_commit_sha" not in pr_response:
        print("No merge commit for PR", pr_number)
        return None

    merge_commit_url = pr_response["merge_commit_sha"]

    # Get the details of the merge commit
    commit_url = f"https://api.github.com/repos/{repo_owner}/{repo_name}/commits/{merge_commit_url}"
    commit_response = await get_request_to_session(session, commit_url)


    # Get the timestamp of the merge commit as a datetime object
    merge_commit_timestamp = datetime.strptime(commit_response["commit"]["committer"]["date"], '%Y-%m-%dT%H:%M:%SZ')

    # Get all the tags associated with the repository
    release_url = f"https://api.github.com/repos/{repo_owner}/{repo_name}/releases"
    release_response = await get_request_to_session(session, release_url)

    # Filter out pre-releases and tags before the merge commit timestamp
    release_names = [
        release["name"] for release in release_response
        if not release["prerelease"]
        if datetime.strptime(release["published_at"],'%Y-%m-%dT%H:%M:%SZ') >= merge_commit_timestamp
    ]

    return release_names[-1]

async def get_release_from_prs(from_pr_number, to_pr_number):

    async with aiohttp.ClientSession() as session:
        pulls = get_pulls_from_repository(from_pr_number, to_pr_number)
        tasks = []
        skipping_prs = []
        print("Total PRs: ", len(pulls))

        for pull in pulls:
            release_version = await get_release(pull, session)

            # add task to list for later async execution
            tasks.append(
                asyncio.ensure_future(
                    set_release_names_to_clickup(session, pull, release_version, skipping_prs)
                )
            )

        # execute all tasks and get answers
        responses = await asyncio.gather(*tasks)
        for response in responses:
            print(response)

        print(f"Skipped PRs: {' '.join(skipping_prs)}")
        print("Total skipped PRs: ", len(skipping_prs))

# to avoid: `RuntimeError: Event loop is closed` on Windows
if platform.platform().startswith("Windows"):
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

asyncio.run(get_release_from_prs(from_pr_number=2000, to_pr_number=3200))
print("Done")