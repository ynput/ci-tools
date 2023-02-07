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

class ChangeLogConfig:
    sections = [
        {
            "title": "### **🆕 New features**",
            "label": "feature",
            "items": []
        },
        {
            "title": "### **🚀 Enhancements**",
            "label": "enhancement",
            "items": []
        },
        {
            "title": "### **🐛 Bug fixes**",
            "label": "bug",
            "items": []
        },
        {
            "title": "### **🔀 Refactored code**",
            "label": "refactor",
            "items": []
        },
        {
            "title": "### **📃 Documentation**",
            "label": "documentation",
            "items": []
        },
        {
            "title": "### **Merged pull requests**",
            "label": "*",
            "items": []
        }
    ]
    domains = [
        {"domain": "3d", "hosts": ["maya", "houdini", "unreal"]},
        {"domain": "2d", "hosts": ["nuke", "fusion"]},
        {"domain": "editorial", "hosts": ["hiero", "flame", "resolve"]},
        {"domain": "other", "hosts": ["*"]},
    ]

    def __init__(self, changelog_data) -> None:
        self._populate_sections(changelog_data)
        self._sort_by_hosts()

    def _populate_sections(self, changelog_data):
        for pr_ in changelog_data["changelog"]:
            types = pr_["types"]
            for section in self.sections:
                # TODO: need to do regex check
                if section["label"] in types:
                    section["items"].append(pr_)
                    break

    def _sort_by_hosts(self):
        for section in self.sections:
            new_order = []
            items = section["items"]
            for domain_ in self.domains:
                for host in domain_["hosts"]:
                    for item in items:
                        # TODO: regex check `*`
                        if host in item["hosts"]:
                            # add domane to item
                            item["domain"] = domain_["domain"]
                            # add to reorder
                            new_order.append(item)
                            # dont duplicate and remove item
                            items = [
                                i_ for i_ in items
                                if i_["title"] != item["title"]
                            ]

    def _get_changelog_item_from_template(self, **kwards):
        pretitle = ""
        hosts_str = ""
        modules_str = ""

        # get pr kwargs
        domain = kwards.get("domain")
        title = kwards.get("title")
        url = kwards.get("url")
        body = kwards.get("body")
        hosts = kwards.get("hosts")
        modules = kwards.get("modules")

        if domain:
            pretitle += f"[{domain}]"
        if hosts:
            hosts_str = ",".join(hosts)
        if modules:
            modules_str = ",".join(modules)

        if hosts_str:
            pretitle += f"[{hosts_str}] "
        if modules_str:
            pretitle += f"[{modules_str}] "

        return f"""
<details>
<summary>{pretitle}{title} - {url}</summary>
\r\n
___
\r\n
{body}
\r\n
___
\r\n
</details>\r\n
"""

    def generate(self):
        out_text = ""
        for section in self.sections:
            if not section["items"]:
                continue
            out_text += section["title"] + "\r\n\r\n"
            for item in section["items"]:
                out_text += self._get_changelog_item_from_template(**item)

        return out_text




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
    _types: list = []
    _hosts: list = []
    _modules: list = []
    title: str
    body: str
    url: str


    def __init__(
        self, title:str, body:str, url:str, number:int,
        labels:dict, *args, **kwargs
    ) -> None:
        self.title = title
        self.body = body
        self.url = url
        self.number = number

        # set pr type
        self._define_pr_types(labels)

        # set hosts
        self._define_pr_hosts(labels)

        # set hosts
        self._define_pr_modules(labels)

    def _define_pr_types(self, labels) -> None:
        self._types = []
        for label in labels["nodes"]:
            if "type:" not in label["name"]:
                continue

            # adding available types from labels
            self._types.append(
                label["name"]
                .replace("type: ", "")
                .lower()
            )

    def _define_pr_modules(self, labels) -> None:
        self._modules = []
        for label in labels["nodes"]:
            if "module:" not in label["name"]:
                continue

            # adding available types from labels
            self._modules.append(
                label["name"]
                .replace("module: ", "")
                .lower()
            )

    def _define_pr_hosts(self, labels) -> None:
        self._hosts = []
        for label in labels["nodes"]:
            if "host:" not in label["name"]:
                continue

            # adding available hosts from labels
            self._hosts.append(
                label["name"]
                .replace("host: ", "")
                .lower()
            )

    @property
    def hosts(self):
        return self._hosts

    @property
    def modules(self):
        return self._modules

    @property
    def types(self):
        return self._types

    def get_url(self) -> str:
        return f"<a href=\"{self.url}\">#{self.number}</a>"

    def get_title(self) -> str:
        return self.title

    def get_body(self) -> dict:
        processing_headers = {}
        headers = [
            "Brief description",
            "Description"
        ]
        markdown = mistune.create_markdown(renderer="ast")
        markdown_obj = markdown(self.body)
        pprint(markdown_obj)

        test_available_headers = [
            el_ for el_ in markdown_obj
            if el_["type"] == "heading" and el_["children"][0]["text"] in headers
        ]
        if not test_available_headers:
            return self.body

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
                el_["type"] in ["paragraph", "list", "block_code"]
            ):
                processing_headers[actual_header].append(el_)

        parsed_body = {
            header: flatten_markdown_paragraph(paragraph)
            for header, paragraph in processing_headers.items()
        }

        text = ""
        for header, paragraph in parsed_body.items():
            text += f"## {header}\r\n"
            if isinstance(paragraph, list):
                for s_ in paragraph:
                    text += "".join(s_)
                text += """\r\n\r\n"""
                text = text.lstrip("\r\n")

        return text

def flatten_markdown_paragraph(input, type_=None):
    if isinstance(input, dict):
        type_ = type_ or input.get("type")

    return_list = []
    if isinstance(input, list):
        nested_list = list(itertools.chain(*[flatten_markdown_paragraph(item, type_) for item in input]))
        return_list.extend(nested_list)

    if "children" in input:
        if input.get("type") in ["strong", "emphasis", "list_item", "list"]:
            # some reformats are applied to list of inputs
            nested_list = list(itertools.chain(*[flatten_markdown_paragraph(item, input.get("type")) for item in input["children"]]))
        else:
            # other reformats are applied directly
            nested_list = list(itertools.chain(*[flatten_markdown_paragraph(item, item.get("type")) for item in input["children"]]))

        if input.get('type') == "paragraph":
            return_list.append(nested_list)
        elif input.get("type") == "block_text":
            return_list.extend(("\r\n- ", nested_list))
        else:
            return_list.extend(nested_list)

    if "text" in input:
        text = input["text"]
        # add text style
        if type_ == "codespan":
            text = "`" + text + "`"
        elif type_ == "emphasis":
            text = "_" + text + "_"
        elif type_ == "strong":
            text = "**" + text + "**"
        elif type_ == "block_code":
            info = input.get("info")
            if info:
                text = f"\r\n\r\n```{info}\r\n" + text.replace("\n", "\r\n") + "```"
            else:
                text = f"```\r\n" + text.replace("\n", "\r\n") + "```"
        # condition for text with line endings
        if "\n" in text and type_ != "block_code":
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
        "num_prs": 10
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
                                number
                                labels(first: 5){
                                    nodes{
                                        name
                                        color
                                    }
                                }
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

    changelog_data = {
        "milestone": milestone,
        "changelog": []
    }
    for pr_ in _pr["nodes"]:
        pprint(pr_)
        pull = PullRequestDescription(**pr_)
        changelog_data["changelog"].append({
            "title": pull.get_title(),
            "body": pull.get_body(),
            "url": pull.get_url(),
            "types": pull.types,
            "hosts": pull.hosts,
            "modules": pull.modules
        })

    # sort and devide PRs by labels
    changelog = ChangeLogConfig(changelog_data)
    print(changelog.generate())

    tfile = tempfile.NamedTemporaryFile(mode="w+")
    json.dump(changelog_data, tfile)
    tfile.flush()

    print(tfile.name)




if __name__ == '__main__':
    main()
