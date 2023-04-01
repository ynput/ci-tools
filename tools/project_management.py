import re
import platform
import click
import requests
import asyncio
import aiohttp
from pprint import pformat
from repository import GithubConnect
from utils import Printer
printer = Printer()

def _get_request_header():
    repo_connect = GithubConnect()

    return {"Authorization": f"Bearer {repo_connect.token}"}

class PullRequestDescription:
    title: str
    url: str
    head_ref: str


    def __init__(
        self, title:str, url:str, number:int,
        headRefName=str, *args, **kwargs
    ) -> None:
        self.title = title
        self.url = url
        self.number = number
        self.head_ref = headRefName

    def __repr__(self) -> str:
        return f"<PullRequestDescription('{self.url}')>"

    def get_url(self) -> str:
        return f"<a href=\"{self.url}\">#{self.number}</a>"

    def get_title(self) -> str:
        return self.title



class MilestonePRProcessor:
    repo_connect = GithubConnect()

    query = """
            query (
                $owner: String!, $repo_name: String!, $milestone: String!
            ){
                repository(owner: $owner, name: $repo_name) {
                    milestones(query: $milestone, first: 1) {
                        nodes{
                            title
                            url
                            number
                            pullRequests(states:[OPEN, MERGED], first: 1000){
                                nodes{
                                    title
                                    url
                                    number
                                    headRefName
                                }
                            }
                        }
                    }
                }
            }
        """

    _pullrequests: list[PullRequestDescription] = []

    def __init__(self, milestone) -> None:
        # Execute the query
        result = self._run_github_query(milestone)

        # Drill down the dictionary
        milestone_data = result["data"]['repository']['milestones']['nodes'].pop()
        pullrequest_data = milestone_data.pop("pullRequests")
        assert pullrequest_data, "Missing PullRequest in Milestone"

        for pr_ in pullrequest_data["nodes"]:
            pull = PullRequestDescription(**pr_)
            self._pullrequests.append(pull)

        printer.echo(f"Amount or Collected PRs {len(self._pullrequests)}")
        printer.echo(f"Collected PRs {pformat(self._pullrequests)}")

    @property
    def pulls(self):
        return self._pullrequests

    def _run_github_query(self, milestone):
        """Running query at Github

        Args:
            milestone (str): milestone name

        Raises:
            Exception: _description_

        Returns:
            str: json text
        """
        variables = {
            "owner": self.repo_connect.owner,
            "repo_name": self.repo_connect.name,
            "milestone": milestone
        }

        try:
            # A simple function to use requests.post to make
            # the API call. Note the json= section.
            request = requests.post(
                'https://api.github.com/graphql',
                json={'query': self.query, "variables": variables},
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

async def put_clickup_request(session, url, headers, payload, query):
    async with session.post(url, json=payload, headers=headers, params=query ) as resp:
            response = await resp.json()
            printer.echo(pformat(response))

async def milestone_prs_to_clickup(context, milestone):

    skipping_prs = []
    milestone_prs_proc = MilestonePRProcessor(milestone)

    # define all variables from context
    field_id = context.obj["CLICKUP_RELEASE_FIELD_ID"]

    headers = {
        "Content-Type": "application/json",
        "Authorization": context.obj["CLICKUP_API_KEY"]
    }

    query = {
        "custom_task_ids": "true",
        "team_id": context.obj["CLICKUP_TEAM_ID"]
    }

    printer.echo(f"{headers}")
    printer.echo(f"{query}")

    async with aiohttp.ClientSession() as session:
        tasks = []
        for pr_ in milestone_prs_proc.pulls:
            printer.echo("__________________")
            clickup_custom_id = None
            found = re.findall(r"OP-\d{4}", pr_.head_ref)
            if found:
                clickup_custom_id = found.pop()
                printer.echo(f"Found Clickup ID {clickup_custom_id}")

            if not clickup_custom_id:
                skipping_prs.append(str(pr_.number))
                printer.echo(f"Skipping PR: '{pr_.number}' / '{pr_.get_title()}' / '{pr_.head_ref}'")
                continue

            payload = {
                "value": milestone
            }

            url = (
                f"https://api.clickup.com/api/v2/task/{clickup_custom_id}"
                f"/field/{field_id}"
            )
            printer.echo(f"Processing PR: '{pr_.number}' / '{pr_.get_title()}' / '{pr_.head_ref}'")
            printer.echo(f"Requesting {url}")

            # add task to list for later async execution
            tasks.append(
                asyncio.ensure_future(
                    put_clickup_request(session, url, headers, payload, query)
                )
            )

            # execute all tasks and get answers
            put_answers = await asyncio.gather(*tasks)
            for answers in put_answers:
                printer.echo(answers)

        printer.echo(f"Skipped PRs: {' '.join(skipping_prs)}")

@click.command(
    name="prs-to-clickup",
    help=(
        "Add pr milestone name to clickup task as tag"
    )
)
@click.option(
    "--milestone", required=True,
    help="Name of milestone > `1.0.1`"
)
@click.pass_context
def milestone_prs_to_clickup_cli(ctx, milestone):
    """Wrapping cli function

    Args:
        milestone (str): milestone name
    """

    printer.echo("Generating changelog from milestone...")

    # to avoid: `RuntimeError: Event loop is closed` on Windows
    if platform.platform().startswith("Windows"):
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    asyncio.run(milestone_prs_to_clickup(ctx, milestone))
    print("Done")
