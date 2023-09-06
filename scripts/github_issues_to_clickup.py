
from asyncio import tasks
import os
import pprint
import re
import json
import platform
from dotenv import load_dotenv
import requests
import asyncio
import aiohttp

load_dotenv()

JSON_ISSUES_FILE_PATH = "temp_file_issues.json"
JSON_TASKS_FILE_PATH = "temp_file_cu_tasks.json"


class CTX:
    repo_owner = "ynput"
    repo_name = "OpenPype"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {os.getenv('GITHUB_TOKEN')}"
    }
    list_id = os.getenv("CLICKUP_LIST_ID")
    team_id = os.getenv("CLICKUP_TEAM_ID")




def get_issues_from_repository(from_issue_number, to_issue_number):
    """Get a list of Issues requests from the repository."""

    def return_range(issues):
        return [
            iss for iss in issues
            if from_issue_number <= iss["number"] <= to_issue_number
        ]

    if os.path.exists(JSON_ISSUES_FILE_PATH):
        with open(JSON_ISSUES_FILE_PATH, 'r') as file:
            prs_ = json.load(file)
            return return_range(prs_)

    # Define the GraphQL query
    query = """
        query (
            $owner: String!, $repo_name: String!,
            $max_count: Int!, $after_cursor: String, $states: [IssueState!]) {
                repository(owner: $owner, name: $repo_name) {
                issues(states: $states, first: $max_count, after: $after_cursor) {
                    edges {
                        node {
                            number
                            title
                            body
                            url
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
    """  # noqa: E501

    # Set the necessary parameters
    access_token = os.getenv("GITHUB_TOKEN")
    max_count = 100  # The maximum number of pull requests to retrieve at once

    # Set up the variables for the GraphQL query
    variables = {
        "states": "OPEN",
        "max_count": max_count,
        "repo_name": CTX.repo_name,
        "owner": CTX.repo_owner
    }

    _issues = []

    # Loop through the pages of pull requests until we hit the end or the last
    # pull request we want
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
        returned_data = json.loads(response.text)

        # Retrieve the pull requests from the response data
        pull_requests_page = [
            edge['node']
            for edge in returned_data['data']['repository']['issues']['edges']
        ]

        # Add the pull requests to the list of pull requests we're collecting
        _issues += pull_requests_page

        # Check if there are more pages of pull requests to retrieve
        page_info = returned_data['data']['repository']['issues']['pageInfo']
        has_next_page = page_info['hasNextPage']
        end_cursor = page_info['endCursor']
        print(f"Collected Issues {len(_issues)}")

    # Dump json data into file
    with open(JSON_ISSUES_FILE_PATH, 'w') as file:
        json.dump(_issues, file, indent=4)

    # Return the list of pull requests which match the given range
    return return_range(_issues)


async def get_request_to_session(session, url):

    async with session.get(url, headers=CTX.headers) as resp:
        return await resp.json()


async def put_clickup_request(session, url, payload, query):
    headers_ = {
        "Content-Type": "application/json",
        "Authorization": os.getenv("CLICKUP_API_KEY")
    }
    async with session.post(
        url,
        json=payload,
        headers=headers_,
        params=query
    ) as resp:
        return await resp.json()


async def get_clickup_request(session, url, query):
    headers_ = {
        "Content-Type": "application/json",
        "Authorization": os.getenv("CLICKUP_API_KEY")
    }
    async with session.get(
        url,
        headers=headers_,
        params=query
    ) as resp:
        return await resp.json()


async def get_clickup_task(
        session, cu_id_hash):

    query = {
        "custom_task_ids": "true",
        "team_id": CTX.team_id
    }
    print(query)

    url = (
        f"https://api.clickup.com/api/v2/task/{cu_id_hash}")

    print(url)

    response = await get_clickup_request(session, url, query)

    if "error" in response:
        print(f"Error: {response['error']}")
        return
    elif (
        "err" in response
        and "Task not found, deleted" in response["err"]
    ):
        response["status"] = {"status": "Deleted"}
        return response

    elif "err" in response:
        print(f"Err: {response['err']}")
        return

    return response


async def get_all_clickup_tasks(
        session):

    if os.path.exists(JSON_TASKS_FILE_PATH):
        with open(JSON_TASKS_FILE_PATH, 'r') as file:
            return json.load(file)

    tasks_all = {}
    query = {
        "archived": "false",
        "subtasks": "true",
        "include_closed": "true",
        "page": "0",
    }

    url = (
        f"https://api.clickup.com/api/v2/list/{CTX.list_id}/task")

    response = await get_clickup_request(session, url, query)

    if "error" in response:
        print(f"Error: {response['error']}")
        return
    elif "err" in response:
        print(f"Error: {response['err']}")
        return

    while response["tasks"]:
        print(f"Page: {query['page']}")
        # Process the current page results
        tasks_page = {task["name"]: task for task in response["tasks"]}
        print(f"Collected Tasks {len(tasks_page)}")
        tasks_all.update(tasks_page)

        # Increment the page number for the next request
        query["page"] = str(int(query["page"]) + 1)

        response = await get_clickup_request(session, url, query)

        if "error" in response:
            print(f"Error: {response['error']}")
            break
        elif "err" in response:
            print(f"Error: {response['err']}")
            break

    # Save text to temporary file
    with open(JSON_TASKS_FILE_PATH, 'w') as file:
        json.dump(tasks_all, file, indent=4)

    return tasks_all


def get_cu_id_tag(body_text):
    """Get the latest release tag name from the body."""
    found = re.findall(r"\[cuID:.*\]", body_text)
    return found.pop() if found else None


def get_cu_id_url(cu_id_tag):
    """Get url from cuID tag."""
    found = re.findall(r"(https://app\.clickup\.com/t/.*)\)\]", cu_id_tag)
    return found.pop() if found else None


def get_cu_id_op(cu_id_tag):
    """Get OP- patter from cuID tag."""
    found = re.findall(r"OP-\d{4}", cu_id_tag)
    return found.pop() if found else None


def get_cu_id_hash(cu_id_tag):
    found = re.findall(r"cuID:(.*)\]", cu_id_tag)
    return found.pop() if found else None


async def make_clickup_task(
        session, issue):

    issue_number = issue["number"]
    issue_title = issue["title"]
    issue_body = issue["body"]
    issue_url = issue["url"]

    query = {
        "custom_task_ids": "true",
        "team_id": CTX.team_id
    }
    print(query)

    payload = {
        "name": issue_title,
        "description": issue_body,
        "custom_fields": [
            {
                "id": "4f79c492-b1f2-4737-b7fa-6e60c9a67f57",
                "value": issue_number
            },
            {
                "id": "849ed6ee-4b5d-476d-b559-702490b0ef73",
                "value": issue_url
            }
        ]
    }

    url = (
        f"https://api.clickup.com/api/v2/list/{CTX.list_id}/task")

    print(url)

    response = await put_clickup_request(session, url, payload, query)

    if "error" in response:
        print(f"Error: {response['error']}")
        return
    elif "err" in response:
        print(f"Error: {response['err']}")
        return

    return response


async def create_task_in_clickup(session, issue, cu_tasks, cu_id_tag=None):
    """Create a task in Clickup."""

    issue_number = issue["number"]
    issue_title = issue["title"]

    if issue_title in cu_tasks:
        print(f"Task '{issue_number}:{issue_title}' already exists in Clickup")
        task_id_hash = cu_tasks[issue_title]["id"]
        custom_task_id = cu_tasks[issue_title]["custom_id"]
        cu_task_data = cu_tasks[issue_title]
    else:
        print(f"Creating task '{issue_number}:{issue_title}' in Clickup")
        cu_task_data = await make_clickup_task(
            session, issue)

        task_id_hash = cu_task_data["id"]
        custom_task_id = cu_task_data["custom_id"]

    if not custom_task_id:
        # check if custom_id key in created_task_data if not wait for 5 seconds
        # and try again
        while True:
            await asyncio.sleep(5)
            cu_task_data = await get_clickup_task(
                session, task_id_hash)
            custom_task_id = cu_task_data["custom_id"]

            if custom_task_id:
                break

    await update_cuid_url_to_issue(session, issue, cu_task_data, cu_id_tag)


async def update_cuid_url_to_issue(session, issue, task_data, cu_id_tag=None):
    # update issue body with cuID
    task_cu_id_url_markdown = \
        f"[cuID:[{task_data['custom_id']}]({task_data['url']})]"

    if cu_id_tag:
        print(f"Updating Issue: {issue['number']} with '{task_cu_id_url_markdown}'")
        issue_body = issue["body"].replace(
            cu_id_tag, task_cu_id_url_markdown)
    else:
        print(f"Adding CU url: {issue['number']} with '{task_cu_id_url_markdown}'")
        issue_body = (
            issue["body"]
            + f"\n\n{task_cu_id_url_markdown}"
        )

    # update github issue with new body
    url = (
        f"https://api.github.com/repos/{CTX.repo_owner}/{CTX.repo_name}"
        f"/issues/{issue['number']}"
    )

    payload = {
        "body": issue_body
    }

    await session.patch(url, json=payload, headers=CTX.headers)


async def close_github_issue(session, issue):
    """Close issue in Github."""
    print(f"Closing Issue: {issue['number']}")
    url = (
        f"https://api.github.com/repos/{CTX.repo_owner}/{CTX.repo_name}"
        f"/issues/{issue['number']}"
    )

    payload = {
        "state": "closed"
    }

    await session.patch(url, json=payload, headers=CTX.headers)


async def get_clickup_task_data(
        session, issue, cu_tasks, cu_id_custom=None, cu_id=None
):
    task_data = get_clickup_task_data_by_cu_id(
        issue, cu_tasks, cu_id_custom, cu_id)
    if not task_data:
        # task was moved to another list
        # get the task data from clickup
        print(f"Task was moved to another list: {cu_id}")
        task_data = await get_clickup_task(
            session, cu_id)

    return task_data


async def sync_issues_to_clickup(
        from_issue_number, to_issue_number, remove_temp_files=True):
    """Sync issues from Github to Clickup."""
    # remove temp files if exists
    if remove_temp_files and os.path.exists(JSON_ISSUES_FILE_PATH):
        os.remove(JSON_ISSUES_FILE_PATH)

    if remove_temp_files and os.path.exists(JSON_TASKS_FILE_PATH):
        os.remove(JSON_TASKS_FILE_PATH)

    async with aiohttp.ClientSession() as session:
        # check if the issue title is not already created in clickup tasks
        cu_tasks = await get_all_clickup_tasks(session)
        print(f"ClickUp tasks amount: {len(cu_tasks)}")

        async_tasks = []
        # get all issues from github
        issues = get_issues_from_repository(from_issue_number, to_issue_number)
        # iterate through all issues
        for issue in issues:
            # get cuID from issue body
            cu_id_tag = get_cu_id_tag(issue["body"])
            print(f"Processing Issue: {issue['number']} with {cu_id_tag}")

            if cu_id_tag:
                # check if url https://app.clickup.com exists
                url_in_tag = get_cu_id_url(cu_id_tag)

                if url_in_tag:
                    # skip this issue since it is done
                    cu_id_custom = get_cu_id_op(cu_id_tag)
                    cu_id = url_in_tag.split("/")[-1]

                    task_data = await get_clickup_task_data(
                        session, issue, cu_tasks, cu_id_custom, cu_id)

                    if (
                        task_data
                        and task_data['status']['status'] in [
                            'Closed',
                            'Deleted',
                        ]
                    ):
                        async_tasks.append(
                            asyncio.ensure_future(
                                close_github_issue(session, issue)
                            )
                        )
                    continue

                # check if cuID is in regex pattern `/OP-.+/g`
                cu_id_custom = get_cu_id_op(cu_id_tag)
                print(f"cuID Custom: {cu_id_custom}")

                cu_id = get_cu_id_hash(cu_id_tag)
                print(f"cuID: {cu_id}")

                # in case tag existing but it is not filled anyway
                if not any([cu_id_custom, cu_id]):
                    print(f"Creating task in Clickup: {cu_id_tag}")
                    # create the task in clickup
                    # add task to list for later async execution
                    async_tasks.append(
                        asyncio.ensure_future(
                            create_task_in_clickup(
                                session, issue, cu_tasks, cu_id_tag)
                        )
                    )
                    continue

                print(f"Updating task in Clickup: {cu_id_tag}")

                task_data = await get_clickup_task_data(
                        session, issue, cu_tasks, cu_id_custom, cu_id)

                if (
                    task_data
                    and task_data['status']['status'] in [
                        'Closed',
                        'Deleted',
                    ]
                ):
                    async_tasks.append(
                            asyncio.ensure_future(
                                close_github_issue(session, issue)
                            )
                        )
                elif task_data:
                    async_tasks.append(
                        asyncio.ensure_future(
                            update_cuid_url_to_issue(
                                session, issue, task_data, cu_id_tag)
                        )
                    )

            else:
                # create the task in clickup
                # add task to list for later async execution
                async_tasks.append(
                    asyncio.ensure_future(
                        create_task_in_clickup(
                            session, issue, cu_tasks)
                    )
                )

        # execute all tasks and get answers
        responses = await asyncio.gather(*async_tasks)

        for response in responses:
            print(response)


def get_clickup_task_data_by_cu_id(issue, cu_tasks, cu_id_custom=None, cu_id=None):
    task_data = None
    # for cu_task_name, cu_task_data in cu_tasks.items():
    #     if cu_task_name == issue["title"]:
    #         print(f">> Check duplicity: {cu_task_name}: {cu_task_data['id']}")

    for cu_task_name, cu_task_data in cu_tasks.items():
        if cu_task_data["id"] == cu_id:
            # print(f"Found 'cuID' task in clickup: {cu_task_data['name']}")
            task_data = cu_task_data
            break
        if cu_task_data["custom_id"] == cu_id_custom:
            # print(f"Found 'custom_id' task in clickup: {cu_task_data['name']}")
            task_data = cu_task_data
            break

    return task_data


# to avoid: `RuntimeError: Event loop is closed` on Windows
if platform.platform().startswith("Windows"):
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

asyncio.run(
    sync_issues_to_clickup(
        from_issue_number=2000, to_issue_number=4000, remove_temp_files=False
    )
)

print("Done")
