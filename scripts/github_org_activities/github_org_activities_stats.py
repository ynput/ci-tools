"""
Python script to get the activity of users in a github organization.
Python scrip is also having CLI interface to get the input from a particular user id.

This script should:

- Output aggregated data in a table and save it as a CSV file.
- Divide all active pull requests into two groups based on the label 'community contribution'.
- Aggregate all users per Ynput organization teams, focusing on the 'core team'.
- Iterate over all users and retrieve their activity from the past 24 hours.
- Group all users' activity by authored pull requests and other activities.

The script should be run daily to obtain the following metrics:

- Number of active reviews assigned per user.
- Number of active assignments for review per user.
- Daily activity of pulling PR-related branches (excluding own author PRs) per user.
- Daily activity of commenting on PRs per user.
- Daily activity of any PR-related activity (except creating and merging own author PRs) per user.

"""
from hashlib import sha1
import pytz
import datetime
import json
import os
from pprint import pprint
from dotenv import load_dotenv
import pandas as pd
import requests

load_dotenv()

JSON_FILE_USERS = os.path.join(os.path.dirname(__file__), "data_users.json")
JSON_FILE_REPOS = os.path.join(os.path.dirname(__file__), "data_repos.json")
USER_CSV_FILE = os.path.join(os.path.dirname(__file__), "user_activities.csv")
PR_CSV_FILE = os.path.join(os.path.dirname(__file__), "pr_activities.csv")

LOCAL_TIMEZONE = pytz.timezone('Europe/Berlin')
HEADERS = {
    "Authorization": f"Bearer {os.getenv('GITHUB_TOKEN')}"
}

# Get the organization name from the user
ORG_NAME = os.getenv('GITHUB_ORGANIZATION')
TEAM_NAME = os.getenv('GITHUB_TEAM')


def get_current_time():
    # Get the current date and time with the timezone
    now = datetime.datetime.now(tz=pytz.utc).astimezone(LOCAL_TIMEZONE)
    return LOCAL_TIMEZONE.normalize(now)


def utc_to_local(utc_dt):
    local_dt = utc_dt.replace(tzinfo=pytz.utc).astimezone(LOCAL_TIMEZONE)
    return LOCAL_TIMEZONE.normalize(local_dt)


def get_all_pulls(cached=False):
    if os.path.exists(JSON_FILE_REPOS) and cached:
        print("cached pulls data --------------")
        with open(JSON_FILE_REPOS) as json_file:
            return json.load(json_file)

    query_repos = """
    query($orgName: String!, $cursor: String) {
        organization(login: $orgName) {
            repositories(first: 100, after: $cursor) {
                pageInfo {
                    hasNextPage
                    endCursor
                }
                edges {
                    node {
                        name
                        isArchived
                        isFork
                        isLocked
                        isTemplate
                        pullRequests(first: 1) {
                            totalCount
                        }
                    }
                }
            }
        }
    }
    """

    query_pulls = """
    query($orgName: String!, $repoName: String!, $cursor: String) {
        organization(login: $orgName) {
            repository(name: $repoName) {
                pullRequests(first: 20, after: $cursor, states: [OPEN], orderBy: {field: CREATED_AT, direction: DESC}) {
                    pageInfo {
                        hasNextPage
                        endCursor
                    }
                    edges {
                        node {
                            state
                            mergeable
                            number
                            title
                            createdAt
                            lastEditedAt
                            url
                            headRefName
                            isDraft
                            author {
                                login
                            }
                            labels(first: 100) {
                                edges {
                                    node {
                                        name
                                    }
                                }
                            }
                            assignees(first: 100) {
                                edges {
                                    node {
                                        login
                                    }
                                }
                            }
                            reviews(first: 100) {
                                edges {
                                    node {
                                        author {
                                            login
                                        }
                                        state
                                    }
                                }
                            }
                            reviewDecision
                            participants (first: 100) {
                                edges {
                                    node {
                                        login
                                    }
                                }
                            }
                            reviewRequests (first: 100) {
                                edges {
                                    node {
                                        requestedReviewer {
                                            ... on User {
                                                login
                                            }
                                        }
                                    }
                                }
                            }
                            authorAssociation
                            changedFiles
                            isCrossRepository
                            maintainerCanModify
                            reviewDecision
                            totalCommentsCount
                            updatedAt
                        }
                    }
                }
            }
        }
    }
    """

    # Define the variables for the GraphQL query
    variables = {"orgName": ORG_NAME, "cursor": None}

    data_repos = {}
    empty_repos = []
    while True:
        # Send the GraphQL request
        response_pulls = requests.post(
            "https://api.github.com/graphql",
            json={"query": query_repos, "variables": variables},
            headers=HEADERS
        )
        if (
                response_pulls.json()["data"] is None
                and "errors" in response_pulls.json()
        ):
            print(response_pulls.json())
            break

        response_json = response_pulls.json()
        repos_data = response_json["data"]["organization"]["repositories"]

        # Parse the response
        _data_page = repos_data["edges"]

        for repo in _data_page:
            repo_name = repo["node"]["name"]
            pr_count = repo["node"]["pullRequests"]["totalCount"]
            # skip if repo is archived, locked or template or it has no PRs
            if (
                repo["node"]["isArchived"]
                or repo["node"]["isLocked"]
                or repo["node"]["isTemplate"]
                or pr_count == 0
            ):
                empty_repos.append(repo_name)
                continue

            if repo_name not in data_repos:
                data_repos[repo_name] = {}
                print(
                    f"Adding repo '{repo_name}' for rather processing. "
                    f"'{pr_count}' pullrequests in total."
                )

        # Check if there are more pages
        page_info = repos_data["pageInfo"]

        if page_info["hasNextPage"]:
            variables["cursor"] = page_info["endCursor"]
        else:
            break

    # iterate all repos in data_repos and get all pulls via
    # graphql query `query_pulls`
    for repo in data_repos:
        page_index = 0
        variables = {"orgName": ORG_NAME, "repoName": repo, "cursor": None}
        while True:
            print("-" * 20 + "> " + f"{repo} > page: {page_index}")
            # Send the GraphQL request
            response_pulls = requests.post(
                "https://api.github.com/graphql",
                json={"query": query_pulls, "variables": variables},
                headers=HEADERS
            )

            if (
                response_pulls.json()["data"] is None
                and "errors" in response_pulls.json()
            ):
                print(response_pulls.json())
                break

            # Parse the response
            data = response_pulls.json()["data"]["organization"]["repository"]["pullRequests"]["edges"]
            for pull in data:
                pull_number = pull["node"]["number"]

                data_repos[repo][pull_number] = pull["node"]
                print(f"{repo}: {pull_number}")

            # Check if there are more pages
            page_info = response_pulls.json()["data"]["organization"]["repository"]["pullRequests"]["pageInfo"]
            if page_info["hasNextPage"]:
                variables["cursor"] = page_info["endCursor"]
                page_index += 1
            else:
                break

    # add empty repos keys into repos data
    for repo in empty_repos:
        data_repos[repo] = {}

    # save all captured data to json file for further analysis
    with open(JSON_FILE_REPOS, 'w') as outfile:
        json.dump(data_repos, outfile, indent=4)

    return data_repos


def get_all_members_activity_data(cached=False):

    if os.path.exists(JSON_FILE_USERS) and cached:
        print("cached members data --------------")
        with open(JSON_FILE_USERS) as json_file:
            events_activity = json.load(json_file)
    else:
        # Define the GraphQL query
        query_users = """
        query($orgName: String!, $teamName: String!) {
        organization(login: $orgName) {
            team(slug: $teamName) {
            members {
                nodes {
                login
                }
            }
            }
        }
        }
        """

        # Define the variables for the GraphQL query
        variables = {
            "orgName": ORG_NAME,
            "teamName": TEAM_NAME
        }

        # Send the GraphQL request
        response_users = requests.post(
            "https://api.github.com/graphql",
            json={"query": query_users, "variables": variables},
            headers=HEADERS
        )
        print(response_users.json())
        # Get the response data
        members = (
            response_users.json()
            ["data"]
            ["organization"]
            ["team"]
            ["members"]
            ["nodes"]
        )
        print(members)

        events_activity = {}
        # Iterate over all the teams in the organization
        for member in members:
            login = member["login"]
            # exclude bot user
            if login == "ynbot":
                continue
            events_response = requests.get(f'https://api.github.com/users/{login}/events/public', headers=HEADERS)
            events = events_response.json()
            events_activity[login] = {
                "events": events
            }

        # save all captured data to json file for further analysis
        with open(JSON_FILE_USERS, 'w') as outfile:
            json.dump(events_activity, outfile, indent=4)

    return events_activity


def process_user_activity_data(events_activity, repos_activity_data):
    activity = {}
    for member in events_activity:
        events = events_activity[member]["events"]
        for event in events:
            event_data = get_event_data(member, event, repos_activity_data)
            if event_data:
                activity[event["id"]] = event_data

    output_records = write_activity_to_csv(activity, USER_CSV_FILE)
    json_output_records = json.dumps(output_records, indent=4)

    # output for n8n
    # print(json_output_records)


def get_event_data(member, event, repos_activity_data):
    # excluded activities
    excluded_activities = [
        "WatchEvent", "PushEvent", "CreateEvent", "DeleteEvent", "ForkEvent",
        "GollumEvent", "MemberEvent", "ReleaseEvent"
    ]

    org_activity = True
    activity_type = event["type"]

    if activity_type in excluded_activities:
        return None

    utc_dt = datetime.datetime.strptime(
        event["created_at"], "%Y-%m-%dT%H:%M:%SZ"
    )
    utc_local = utc_to_local(utc_dt)
    repo_full_name = event["repo"]["name"]

    # get user from payload if available
    subject_owner = (
        event["payload"].get("issue", {}).get("user", {}).get("login", None) or
        event["payload"].get("pull_request", {}).get("user", {}).get("login", None)
    )

    # get url to the activity found in payload
    activity_url = (
        event["payload"].get("review", {}).get("html_url", None) or
        event["payload"].get("comment", {}).get("html_url", None)
    )

    github_number = (
        event["payload"].get("issue", {}).get("number", None) or
        event["payload"].get("pull_request", {}).get("number", None)
    )
    github_url = (
        event["payload"].get("issue", {}).get("html_url", None) or
        event["payload"].get("pull_request", {}).get("html_url", None)
    )
    is_pr = bool(
        event["payload"].get("issue", {}).get("pull_request", None) or
        event["payload"].get("pull_request", {}).get("html_url", None)
    )

    repo_name = repo_full_name.split("/")[-1]
    matching_repo = False
    matching_pr = None
    for _id, pr_data in repos_activity_data.items():
        if pr_data["repository"] != repo_name:
            continue

        matching_repo = True

        if str(pr_data["number"]) == str(github_number):
            matching_pr = pr_data
            break

    # TODO: add data collection for case where it is pr but it is
    # not in the list of prs - we need to query it from github api as merged
    # and we need to add it to the list of prs
    if matching_pr:
        complexity_index = matching_pr["complexity_index"]
    else:
        _id = None
        complexity_index = None

    event_data = {
        "user": member,
        "subject_owner": subject_owner == member,
        "type": event["type"],
        "created_at": str(utc_local),
        "repository": repo_full_name,
        "github_number": github_number,
        "github_url": github_url,
        "activity_url": activity_url,
        "org_activity": matching_repo,
        "is_pr": is_pr,
        "pr_activity_id": _id,
        "pr_complexity_index": complexity_index,
    }

    return event_data


def get_pr_activities(org_pulls_data):
    """Get all organisation pr activies as pandas dataframe
    """
    current_time = get_current_time()
    org_activity = {}
    for repo_name, pulls in org_pulls_data.items():
        for pull_number, pull_data in pulls.items():
            # convert pull_data to sha1 hash with 12 chars
            _id = sha1(json.dumps(pull_data, sort_keys=True).encode('utf-8')).hexdigest()

            # get all assignees number
            assignees_number = len(pull_data["assignees"]["edges"])
            reviews_number = len(pull_data["reviews"]["edges"])
            participants_number = len(pull_data["participants"]["edges"])
            review_requests_number = len(pull_data["reviewRequests"]["edges"])
            labels_number = len(pull_data["labels"]["edges"])

            # calculate complexity index from above quantities
            complexity_index = int(
                assignees_number + reviews_number + participants_number +
                review_requests_number + labels_number
            )

            org_activity[_id] = {
                "activity_capture_time": str(current_time),
                "repository": repo_name,
                "author": pull_data["author"]["login"],
                "number": pull_number,
                "url": pull_data["url"],
                "pr_assignees_number": assignees_number,
                "pr_reviewers_number": reviews_number,
                "pr_participants_number": participants_number,
                "pr_review_requests_number": review_requests_number,
                "head_ref_name": pull_data["headRefName"],
                "author_association": pull_data["authorAssociation"],
                "labels_number": labels_number,
                "changed_files": pull_data["changedFiles"],
                "total_comments_count": pull_data["totalCommentsCount"],
                "updated_at": pull_data["updatedAt"],
                "complexity_index": complexity_index,
                "review_decision": pull_data["reviewDecision"]
            }

    return org_activity


def process_pr_activity_data(pr_activity_data):
    output_records = write_activity_to_csv(pr_activity_data, PR_CSV_FILE)
    print(output_records)
    json_output_records = json.dumps(output_records, indent=4)

    # output for n8n
    # print(json_output_records)


def write_activity_to_csv(activity, filepath):
    # convert activity to pandas dataframe
    df = pd.DataFrame.from_dict(activity, orient='index')

    # sort by index
    df.sort_index(inplace=True)

    if os.path.exists(filepath):
        # read already created CSV FILE
        df_old = pd.read_csv(filepath, sep=';', encoding='utf-8', index_col=0)

        # set index to string so it is comparable
        df_old.index = df_old.index.astype(str)

        # find different raws between df and df_old
        diff_df = df[~df.index.isin(df_old.index)]
        diff_df.sort_index(inplace=True)

        # only append difference to already existing USER_CSV_FILE
        diff_df.to_csv(
            filepath,
            sep=';',
            encoding='utf-8',
            mode='a',
            header=False
        )
        return diff_df.to_dict("index")

    # write to csv
    df.to_csv(filepath, sep=';', encoding='utf-8', index=True)
    return df.to_dict("index")


def main(cached=False):
    org_pulls_data = get_all_pulls(cached)
    repos_activity_data = get_pr_activities(org_pulls_data)

    process_pr_activity_data(repos_activity_data)
    members_activity_data = get_all_members_activity_data(cached)
    process_user_activity_data(
        members_activity_data, repos_activity_data)


if __name__ == "__main__":
    main(True)
