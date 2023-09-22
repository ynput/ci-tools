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
import csv
import datetime
import json
import os

from pprint import pprint
import requests


JSON_FILE_USERS = os.path.join(os.path.dirname(__file__), "data_users.json")
JSON_FILE_REPOS = os.path.join(os.path.dirname(__file__), "data_repos.json")
CSV_FILE = os.path.join(os.path.dirname(__file__), "activity.csv")

# Set the personal access token and headers
token = "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"
HEADERS = {
    "Authorization": f"Bearer {token}"
}

# Get the organization name from the user
ORG_NAME = "ynput"
TEAM_NAME = "coreteam"
LOCAL_TIMEZONE = pytz.timezone('Europe/Berlin')


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
                pullRequests(first: 100, after: $cursor, states: [OPEN], orderBy: {field: CREATED_AT, direction: DESC}) {
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
        variables = {"orgName": ORG_NAME, "repoName": repo, "cursor": None}
        while True:
            # Send the GraphQL request
            response_pulls = requests.post(
                "https://api.github.com/graphql",
                json={"query": query_pulls, "variables": variables},
                headers=HEADERS
            )
            # Parse the response
            data = response_pulls.json()["data"]["organization"]["repository"]["pullRequests"]["edges"]
            for pull in data:
                pull_number = pull["node"]["number"]

                data_repos[repo][pull_number] = pull["node"]
                print(pull_number)

            # Check if there are more pages
            page_info = response_pulls.json()["data"]["organization"]["repository"]["pullRequests"]["pageInfo"]
            if page_info["hasNextPage"]:
                variables["cursor"] = page_info["endCursor"]
            else:
                break

    # save all captured data to json file for further analysis
    with open(JSON_FILE_REPOS, 'w') as outfile:
        json.dump(data_repos, outfile, indent=4)

def get_all_members():
    if os.path.exists(JSON_FILE_USERS):
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
        login = member
        events = events_activity[member]["events"]
        activity[login] = []
        for event in events:
            # TODO: own or other PR?
            # TODO: PR number
            # TODO: what repository?
            # TODO: url to the activity
            # TODO: assignee
            # TODO: reviewers
            # TODO: aggregate all prs separately to own table
            # TODO: CU task availability - but do it before with all aggregated PRs
            utc_dt = datetime.datetime.strptime(
                event["created_at"], "%Y-%m-%dT%H:%M:%SZ"
            )
            utc_local = utc_to_local(utc_dt)
            activity[login].append({
                "type": event["type"],
                "timestamp": utc_local

            })

    write_activity_to_csv(activity)


def write_activity_to_csv(activity):
    with open(CSV_FILE, "w", newline="") as csvfile:
        fieldnames = ["user", "event_type", "timestamp"]
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)

        writer.writeheader()
        for user, events in activity.items():
            for event in events:
                writer.writerow({"user": user, "event_type": event["type"], "timestamp": event["timestamp"]})


def main():
    get_timerange()
    get_all_pulls(True)
    get_all_members()


if __name__ == "__main__":
    main()