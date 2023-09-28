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
import pytz
import datetime
import json
import os
from dotenv import load_dotenv
import pandas as pd
import requests

load_dotenv()

JSON_FILE_USERS = os.path.join(os.path.dirname(__file__), "data_users.json")
JSON_FILE_REPOS = os.path.join(os.path.dirname(__file__), "data_repos.json")
CSV_FILE = os.path.join(os.path.dirname(__file__), "activity.csv")
LOCAL_TIMEZONE = pytz.timezone('Europe/Berlin')
HEADERS = {
    "Authorization": f"Bearer {os.getenv('GITHUB_TOKEN')}"
}

# Get the organization name from the user
ORG_NAME = "ynput"
TEAM_NAME = "coreteam"


def get_timerange():
    # Get the current date and time
    now = datetime.datetime.now()

    # Get the past 24 hours
    past_24_hours = (now - datetime.timedelta(hours=24)).strftime("%Y-%m-%dT%H:%M:%S")
    print(past_24_hours)

    return past_24_hours


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
        # Parse the response
        data = response_pulls.json()["data"]["organization"]["repositories"]["edges"]
        for repo in data:
            repo_name = repo["node"]["name"]
            if not repo_name in data_repos:
                data_repos[repo_name] = {}
            print(repo_name)

        # Check if there are more pages
        page_info = response_pulls.json()["data"]["organization"]["repositories"]["pageInfo"]
        if page_info["hasNextPage"]:
            variables["cursor"] = page_info["endCursor"]
        else:
            break

    # iterate all repos in data_repos and get all pulls via graphql query `query_pulls`
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

    # save all captured data to json file for further analysis
    with open(JSON_FILE_REPOS, 'w') as outfile:
        json.dump(data_repos, outfile, indent=4)

def get_all_members(cached=False):

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
            events_response = requests.get(f'https://api.github.com/users/{login}/events/public', headers=HEADERS)
            events = events_response.json()
            events_activity[login] = {
                "events": events
            }

        # save all captured data to json file for further analysis
        with open(JSON_FILE_USERS, 'w') as outfile:
            json.dump(events_activity, outfile, indent=4)

    activity = {}
    for member in events_activity:
        events = events_activity[member]["events"]
        for event in events:
            # TODO: assignee
            # TODO: reviewers
            # TODO: aggregate all prs separately to own table
            # TODO: CU task availability - but do it before with all aggregated PRs
            event_data = get_event_data(member, event)

            activity[event["id"]] = event_data

    output_records = write_activity_to_csv(activity)
    print("activity --------------")
    json_output_records = json.dumps(output_records, indent=4)
    print(json_output_records)


def get_event_data(member, event):
    utc_dt = datetime.datetime.strptime(
                event["created_at"], "%Y-%m-%dT%H:%M:%SZ"
            )
    utc_local = utc_to_local(utc_dt)

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
    event_data = {
                "repository": event["repo"]["name"],
                "type": event["type"],
                "created_at": str(utc_local),
                "user": member,
                "github_number": github_number,
                "github_url": github_url,
                "is_pr": is_pr,
                "subject_owner": subject_owner == member,
                "activity_url": activity_url
            }

    return event_data


def write_activity_to_csv(activity):
    # convert activity to pandas dataframe
    df = pd.DataFrame.from_dict(activity, orient='index')

    # sort by index
    df.sort_index(inplace=True)

    if os.path.exists(CSV_FILE):
        # read already created CSV FILE
        df_old = pd.read_csv(CSV_FILE, sep=';', encoding='utf-8', index_col=0)

        # set index to string so it is comparable
        df_old.index = df_old.index.astype(str)

        # find different raws between df and df_old
        diff_df = df[~df.index.isin(df_old.index)]
        diff_df.sort_index(inplace=True)

        # only append difference to already existing CSV_FILE
        diff_df.to_csv(
            CSV_FILE,
            sep=';',
            encoding='utf-8',
            mode='a',
            header=False
        )
        return diff_df.to_dict("index")

    # write to csv
    df.to_csv(CSV_FILE, sep=';', encoding='utf-8', index=True)
    return df.to_dict("index")


def main():
    get_timerange()
    get_all_pulls(True)
    get_all_members(True)


if __name__ == "__main__":
    main()
