"""This module provides functionality to transfer issues from a GitHub
repository to a ClickUp task list.

The module uses the GitHub API to retrieve issues from a specified repository
and the ClickUp API to create tasks in a specified task list.

The module requires the following environment variables to be set:
- GITHUB_TOKEN: a personal access token for the GitHub API
- CLICKUP_LIST_ID: the ID of the ClickUp task list to create tasks in
- CLICKUP_TEAM_ID: the ID of the ClickUp team to create tasks in

The module defines the following functions:
- _get_issues_from_repository: retrieves a list of issues from a GitHub
repository
- create_clickup_tasks: creates ClickUp tasks from a list of issues
"""

"""
TODO:
- [ ] add support for resolving of PYPE-XXXX issues
- [ ] only extract relevant text from markdown issue body into clickup task
- [ ] resync all issues body to clickup tasks as markdown
- [ ] sync all issue domaine labels to clickup task's custom attributes
- [ ] function for addressing single issue by number
- [ ] cli interface
"""

import os
from pprint import pprint
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
    folder_id = os.getenv("CLICKUP_FOLDER_ID")
    cu_custom_attributes = {
        "type": {
            "id": os.getenv("CLICKUP_ISSUETYPE_FIELD_ID"),
            "options": None
        },
        "host": {
            "id": os.getenv("CLICKUP_DOMAIN_FIELD_ID"),
            "options": None
        }
    }
    request_sleep_time = 60


def _get_issues_from_repository(from_issue_number, to_issue_number):
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
                            labels(first: 100) {
                                edges {
                                    node {
                                        name
                                    }
                                }
                            }
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


async def _post_clickup_request(session, url, payload, query):
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
        print(f"CU Post Status: {resp.status}")
        if resp.status == 429:
            print(
                "Rate limit reached, waiting "
                f"for {CTX.request_sleep_time} seconds"
            )
            await asyncio.sleep(CTX.request_sleep_time)
            return await _get_clickup_request(session, url, query)

        return await resp.json()


async def _put_clickup_request(session, url, payload, query):
    headers_ = {
        "Content-Type": "application/json",
        "Authorization": os.getenv("CLICKUP_API_KEY")
    }
    async with session.put(
        url,
        json=payload,
        headers=headers_,
        params=query
    ) as resp:
        print(f"CU Put Status: {resp.status}")
        if resp.status == 429:
            print(
                "Rate limit reached, waiting "
                f"for {CTX.request_sleep_time} seconds"
            )
            await asyncio.sleep(CTX.request_sleep_time)
            return await _get_clickup_request(session, url, query)

        return await resp.json()


async def _get_clickup_request(session, url, query):
    headers_ = {
        "Content-Type": "application/json",
        "Authorization": os.getenv("CLICKUP_API_KEY")
    }

    async with session.get(
        url,
        headers=headers_,
        params=query
    ) as resp:
        print(f"CU Get Status: {resp.status}")
        if resp.status == 429:
            print(
                "Rate limit reached, waiting "
                f"for {CTX.request_sleep_time} seconds"
            )
            await asyncio.sleep(CTX.request_sleep_time)
            return await _get_clickup_request(session, url, query)

        return await resp.json()


async def _get_clickup_task(
        session, cu_id_hash):

    query = {
        "custom_task_ids": "true",
        "team_id": CTX.team_id
    }
    print(query)

    url = (
        f"https://api.clickup.com/api/v2/task/{cu_id_hash}")

    print(url)

    response = await _get_clickup_request(session, url, query)

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


async def _get_all_clickup_tasks(
        session):

    if os.path.exists(JSON_TASKS_FILE_PATH):
        with open(JSON_TASKS_FILE_PATH, 'r') as file:
            return json.load(file)

    # get all lists ids from folder id
    lists_ids = await _get_clickup_folder_list_ids(session, CTX.folder_id)
    print(f"ClickUp lists: {lists_ids}")

    tasks_all = {}
    for list_id, list_name in lists_ids.items():
        print(f"Processing List: {list_name}")

        query = {
            "archived": "false",
            "subtasks": "true",
            "include_closed": "true",
            "page": "0",
        }

        url = (
            f"https://api.clickup.com/api/v2/list/{list_id}/task")

        response = await _get_clickup_request(session, url, query)

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

            response = await _get_clickup_request(session, url, query)

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


def _get_clickup_cuid_tag(body_text):
    """Get the latest release tag name from the body."""
    found = re.findall(r"\[cuID:.*\]", body_text)
    return found.pop() if found else None


def _get_clickup_url_id(cu_id_tag):
    """Get url from cuID tag."""
    found = re.findall(r"(https://app\.clickup\.com/t/.*)\)\]", cu_id_tag)
    return found.pop() if found else None


def _get_clickup_custom_id(cu_id_tag):
    """Get OP- patter from cuID tag."""
    found = re.findall(r"OP-\d{4}", cu_id_tag)
    return found.pop() if found else None


def _get_clickup_id_hash(cu_id_tag):
    found = re.findall(r"cuID:(.*)\]", cu_id_tag)
    return found.pop() if found else None


async def _make_clickup_task(
        session, issue):

    issue_number = issue["number"]
    issue_title = issue["title"]
    issue_body = issue["body"]
    issue_url = issue["url"]

    query = {
        "custom_task_ids": "true",
        "team_id": CTX.team_id
    }
    custom_fields_from_labels = _get_custom_fields_from_labels(issue)
    custom_fields = [
        {
            "id": "4f79c492-b1f2-4737-b7fa-6e60c9a67f57",
            "value": issue_number
        },
        {
            "id": "849ed6ee-4b5d-476d-b559-702490b0ef73",
            "value": issue_url
        }
    ]
    if custom_fields_from_labels:
        custom_fields.extend(custom_fields_from_labels)

    markdown = _trantktuate_issue_body(issue)

    payload = {
        "name": issue_title,
        "markdown_description": markdown or issue_body,
        "custom_fields": custom_fields
    }

    url = (
        f"https://api.clickup.com/api/v2/list/{CTX.list_id}/task")

    response = await _post_clickup_request(session, url, payload, query)

    if "error" in response:
        print(f"Error: {response['error']}")
        return
    elif "err" in response:
        print(f"Error: {response['err']}")
        return

    return response


async def _update_clickup_task(
        session, cu_task_id, payload):

    query = {
        "custom_task_ids": "true",
        "team_id": CTX.team_id
    }

    url = (
        f"https://api.clickup.com/api/v2/task/{cu_task_id}")

    response = await _put_clickup_request(session, url, payload, query)

    if "error" in response:
        print(f"Error: {response['error']}")
        return
    elif "err" in response:
        print(f"Error: {response['err']}")
        return

    return response


async def _create_task_in_clickup(session, issue, cu_tasks, cu_id_tag=None):
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
        cu_task_data = await _make_clickup_task(
            session, issue)

        task_id_hash = cu_task_data["id"]
        custom_task_id = cu_task_data["custom_id"]

    if not custom_task_id:
        # check if custom_id key in created_task_data if not wait for 5 seconds
        # and try again
        while True:
            await asyncio.sleep(5)
            cu_task_data = await _get_clickup_task(
                session, task_id_hash)
            custom_task_id = cu_task_data["custom_id"]

            if custom_task_id:
                break

    await _update_cuid_url_to_issue(session, issue, cu_task_data, cu_id_tag)


async def _update_cuid_url_to_issue(session, issue, task_data, cu_id_tag=None):
    # update issue body with cuID
    task_cu_id_url_markdown = \
        f"[cuID:[{task_data['custom_id']}]({task_data['url']})]"

    if cu_id_tag:
        print(
            f"Updating Issue: {issue['number']} "
            f"with '{task_cu_id_url_markdown}'"
        )
        issue_body = issue["body"].replace(
            cu_id_tag, task_cu_id_url_markdown)
    else:
        print(
            f"Adding CU url: {issue['number']} "
            f"with '{task_cu_id_url_markdown}'"
        )
        issue_body = (
            issue["body"]
            + f"\n\n{task_cu_id_url_markdown}"
        )

    # update issue in issues data with new body
    issue["body"] = issue_body

    # update github issue with new body
    url = (
        f"https://api.github.com/repos/{CTX.repo_owner}/{CTX.repo_name}"
        f"/issues/{issue['number']}"
    )

    payload = {
        "body": issue_body
    }

    await session.patch(url, json=payload, headers=CTX.headers)


async def _close_github_issue(session, issue):
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


async def _get_clickup_task_data(
        session, cu_tasks, cu_id_custom=None, cu_id=None
):
    task_data = _get_clickup_task_data_by_cu_id(
        cu_tasks, cu_id_custom, cu_id)
    if not task_data:
        # task was moved to another list
        # get the task data from clickup
        print(f"Task was moved to another list: {cu_id}")
        task_data = await _get_clickup_task(
            session, cu_id)

    return task_data


def _get_clickup_task_data_by_cu_id(cu_tasks, cu_id_custom=None, cu_id=None):
    """This function searches through a dictionary of ClickUp tasks

    Returns the task data for a specific task that matches either
    a custom ID or a ClickUp ID.

    Args:
        cu_tasks (dict): A dictionary of ClickUp tasks.
        cu_id_custom (str, optional): The custom ID of the task to search for.
            Defaults to None.
        cu_id (str, optional): The ClickUp ID of the task to search for.
            Defaults to None.

    Returns:
        dict: The task data for the matching task,
            or None if no match is found.
    """
    task_data = None
    for _, cu_task_data in cu_tasks.items():
        if cu_task_data["id"] == cu_id:
            task_data = cu_task_data
            break
        if cu_task_data["custom_id"] == cu_id_custom:
            task_data = cu_task_data
            break

    return task_data


async def _get_clickup_folder_list_ids(session, folder_id):
    """Get all lists ids from clickup folder."""
    url = (
        f"https://api.clickup.com/api/v2/folder/{folder_id}/list")

    response = await _get_clickup_request(session, url, {"archived": "false"})

    if "error" in response:
        print(f"Error: {response['error']}")
        return
    elif "err" in response:
        print(f"Error: {response['err']}")
        return
    return {list_["id"]: list_["name"] for list_ in response["lists"]}


def _get_custom_fields_from_labels(issue):
    """Set labels to clickup task."""
    issue_labels = [label["node"]["name"] for label in issue["labels"]["edges"]]
    print(f"Issue labels: {issue_labels}")
    custom_fields_to_set = []
    # only one host is allowed
    host_field = None
    for label in issue_labels:
        print(f"Processing label: {label}")
        for field, field_data in CTX.cu_custom_attributes.items():
            if field not in label.lower():
                continue

            if not field_data["options"]:
                print(f"Options for {field} not found")
                continue

            if host_field and field == "host":
                print(f"Host field already set: {host_field}")
                continue

            label_trimmed = label.replace(f"{field}:", "").strip()
            option = None
            for option_name, option_order in field_data["options"].items():
                if label_trimmed.lower() in option_name.lower():
                    option = option_order

            if option is None:
                print(f"Option for {field} not found")
                continue

            if "host" in field and host_field is None:
                host_field = option

            custom_fields_to_set.append(
                {
                    "id": field_data["id"],
                    "value": option
                }
            )

        if len(custom_fields_to_set) == 2:
            break

    return custom_fields_to_set


def _aggregate_custom_attributes(all_cu_tasks):
    for field in CTX.cu_custom_attributes.values():
        for task_data in all_cu_tasks:
            if not task_data.get("custom_fields"):
                continue
            for custom_field in task_data["custom_fields"]:
                if custom_field["id"] == field["id"]:
                    field["options"] = \
                        {
                            op["name"]: op["orderindex"]
                            for op in custom_field["type_config"]["options"]
                        }
                    break


def _trantktuate_issue_body(issue):
    def _cut_markdown_by_headers(markdown, headers):
        matches = [
            (match.start(), match.end(), match.group())
            for header in headers for match in re.finditer(re.escape(header), markdown)
        ]
        matches.sort()

        chunks = {}
        for i in range(len(matches)-1):
            header = matches[i][2]
            start_index = matches[i][1]
            end_index = matches[i+1][0]
            content = markdown[start_index:end_index].strip()
            if not content:
                continue
            if "_No response_" in content:
                continue

            if "\n###" in content:
                content = content.split("\n###")[0].strip()

            if "\n[cuID" in content:
                content = content.split("\n[cuID")[0].strip()

            chunks[header] = content


        # for last header, end index will be end of string
        if len(matches) > 0:
            header = matches[-1][2]
            start_index = matches[-1][1]
            content = markdown[start_index:].strip()

            if not content:
                return chunks

            if "\n###" in content:
                content = content.split("\n###")[0].strip()

            if "\n[cuID" in content:
                content = content.split("\n[cuID")[0].strip()

            if "_No response_" in content:
                return chunks

            chunks[header] = content

        return chunks

    description_headers = [
        "### Current Behavior:",
        "### Expected Behavior:",
        "### Version",
        "### Steps To Reproduce:",
        "### Relevant log output:",
        "### Additional context:",
        "### Please describe the feature you have in mind and explain what the current shortcomings are?",
        "### How would you imagine the implementation of the feature?",
        "### Describe alternatives you've considered:",
        "### Additional context:"
    ]
    markdown_dict = _cut_markdown_by_headers(
        issue["body"], description_headers)

    if not markdown_dict:
        print(f"Markdown dict is empty: {issue['number']}")
        return

    # create long markdown string from dict
    markdown = ""
    for key, value in markdown_dict.items():
        markdown += f"{key}\n\n{value}\n\n"

    return markdown


async def _fix_clickup_task_description(session, issue, cu_task_data):
    """Fix description of task."""

    markdown = _trantktuate_issue_body(issue)
    # compare if cu task description is different from issue body
    if markdown and markdown == cu_task_data.get("description", ""):
        print(f"Description is the same: {issue['number']}")
        return

    if not markdown:
        markdown = issue["body"]

    print(
        f"Fixing description of task: {issue['number']}:{cu_task_data['id']}}}"
    )

    return await _update_clickup_task(session, cu_task_data["id"], {
        "markdown_description": markdown
    })


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
        cu_tasks = await _get_all_clickup_tasks(session)
        print(f"ClickUp tasks amount: {len(cu_tasks)}")

        _aggregate_custom_attributes(cu_tasks.values())
        pprint(CTX.cu_custom_attributes)

        async_tasks = []
        # get all issues from github
        issues = _get_issues_from_repository(
            from_issue_number, to_issue_number)
        # iterate through all issues
        for issue in issues:
            # get cuID from issue body
            cu_id_tag = _get_clickup_cuid_tag(issue["body"])
            print(f"Processing Issue: {issue['number']} with {cu_id_tag}")

            if cu_id_tag:
                # check if url https://app.clickup.com exists
                url_in_tag = _get_clickup_url_id(cu_id_tag)

                if url_in_tag:
                    # skip this issue since it is done
                    continue

                # check if cuID is in regex pattern `/OP-.+/g`
                cu_id_custom = _get_clickup_custom_id(cu_id_tag)
                print(f"cuID Custom: {cu_id_custom}")

                cu_id = _get_clickup_id_hash(cu_id_tag)
                print(f"cuID: {cu_id}")

                # in case tag existing but it is not filled anyway
                if not any([cu_id_custom, cu_id]):
                    print(f"Creating task in Clickup: {cu_id_tag}")
                    # create the task in clickup
                    # add task to list for later async execution
                    async_tasks.append(
                        asyncio.ensure_future(
                            _create_task_in_clickup(
                                session, issue, cu_tasks, cu_id_tag)
                        )
                    )
                    continue

                print(f"Updating task in Clickup: {cu_id_tag}")

                task_data = await _get_clickup_task_data(
                        session, cu_tasks, cu_id_custom, cu_id)

                if (
                    task_data
                    and task_data['status']['status'] in [
                        'Closed',
                        'Deleted',
                    ]
                ):
                    async_tasks.append(
                            asyncio.ensure_future(
                                _close_github_issue(session, issue)
                            )
                        )
                elif task_data:
                    async_tasks.append(
                        asyncio.ensure_future(
                            _update_cuid_url_to_issue(
                                session, issue, task_data, cu_id_tag)
                        )
                    )

            else:
                # create the task in clickup
                # add task to list for later async execution
                async_tasks.append(
                    asyncio.ensure_future(
                        _create_task_in_clickup(
                            session, issue, cu_tasks)
                    )
                )

        for issue in issues:
            # get cuID from issue body
            cu_id_tag = _get_clickup_cuid_tag(issue["body"])
            print(f"Syncing Issue status: {issue['number']} with {cu_id_tag}")

            if cu_id_tag:
                # check if url https://app.clickup.com exists
                url_in_tag = _get_clickup_url_id(cu_id_tag)

                if url_in_tag:
                    # skip this issue since it is done
                    cu_id_custom = _get_clickup_custom_id(cu_id_tag)
                    cu_id = url_in_tag.split("/")[-1]

                    task_data = await _get_clickup_task_data(
                        session, cu_tasks, cu_id_custom, cu_id)

                    # make status sync
                    if (
                        task_data
                        and task_data['status']['status'] in [
                            'Closed',
                            'Deleted',
                        ]
                    ):
                        async_tasks.append(
                            asyncio.ensure_future(
                                _close_github_issue(session, issue)
                            )
                        )
                    elif task_data:
                        # fix description of task
                        async_tasks.append(
                            asyncio.ensure_future(
                                _fix_clickup_task_description(
                                    session, issue, task_data)
                            )
                        )
                    continue

        # execute all tasks and get answers
        await asyncio.gather(*async_tasks)


# to avoid: `RuntimeError: Event loop is closed` on Windows
if platform.platform().startswith("Windows"):
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

asyncio.run(
    sync_issues_to_clickup(
        from_issue_number=0, to_issue_number=6000, remove_temp_files=True
    )
)

print("Done")
