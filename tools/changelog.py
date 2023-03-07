""""
- def: rename milestone

- def: generate milestone changelog
    - iterate all milestone PR which are merged
    - divide PRs by categories via labels
        - follow config where categories have assigned labels
        - assign labels to host icons
    - get description and create markdown collapsed text
    - create title with host icons and sort them by host order
    - assemble full change log markdown and output as text
    - merge changelog text at beginning of CHANGELOG.md
    - add changelog text to milestone description
    - return change log text for other actions
"""

from copy import deepcopy
import re
import requests
import click
import tempfile
import mistune
import itertools
from pprint import pformat
from repository import GithubConnect
from utils import Printer

printer = Printer()


class PullRequestDescription:
    _types: list = []
    _domain: str = ""
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

    def __repr__(self) -> str:
        return f"<PullRequestDescription('{self.url}')>"

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
    def domain(self):
        return self._domain

    @domain.setter
    def domain(self, value):
        self._domain = value

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
            "Description",
            "Changelog Description"
        ]
        markdown = mistune.create_markdown(renderer="ast")
        markdown_obj = markdown(self.body)

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
            header: self._flatten_markdown_paragraph(paragraph)
            for header, paragraph in processing_headers.items()
        }

        text = ""
        for header, paragraph in parsed_body.items():
            strong = False
            if header == "Brief description":
                # make paragraph in markdown strong text
                strong = True

            # make strong text if activated
            if strong:
                text += "<strong>"

            # print paragraph
            if isinstance(paragraph, list):
                for s_ in paragraph:
                    text += "".join(s_)
                text += """\n\n"""
                text = text.lstrip("\n")

            # close strong text if activated
            if strong:
                text += "</strong>"

        return text


    def _flatten_markdown_paragraph(self, input, type_=None):
        if isinstance(input, dict):
            type_ = type_ or input.get("type")

        return_list = []
        if isinstance(input, list):
            nested_list = list(
                itertools.chain(*[
                    self._flatten_markdown_paragraph(item, type_)
                    for item in input
                ])
            )
            return_list.extend(nested_list)

        if "children" in input:
            if input.get("type") in ["strong", "emphasis", "list_item", "list"]:
                # some reformats are applied to list of inputs
                nested_list = list(
                    itertools.chain(*[
                        self._flatten_markdown_paragraph(item, input.get("type"))
                        for item in input["children"]
                    ])
                )
            else:
                # other reformats are applied directly
                nested_list = list(
                    itertools.chain(*[
                        self._flatten_markdown_paragraph(item, item.get("type"))
                        for item in input["children"]
                    ])
                )

            if input.get('type') == "paragraph":
                return_list.append(nested_list)
            elif input.get("type") == "block_text":
                return_list.extend(("\n- ", nested_list))
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
                    text = f"\n```{info}\n" + text + "```"
                else:
                    text = f"\n```\n" + text + "```"
            # condition for text with line endings
            if "\n" in text and type_ != "block_code":
                return_list.extend(text.split("\n"))
            else:
                return_list.append(text)

        return return_list


class SectionItems:
    title: str
    label: str
    _pulls: list[PullRequestDescription] = []

    def __init__(self, title, label):
        self.title = title
        self.label = label
        self._pulls = []

    def __repr__(self) -> str:
        return f"<SectionItems('{self.label}')>"

    @property
    def pulls(self):
        return self._pulls

    @pulls.setter
    def pulls(self, input_pulls: list[PullRequestDescription]):
        self._pulls = input_pulls

    def pull_append(self, pull: PullRequestDescription):
        self._pulls.append(pull)


class DomaineItems:
    name: str = ""
    hosts: list[str]

    def __init__(self, name, hosts):
        self.name = name
        self.hosts = hosts

    def __repr__(self) -> str:
        return f"<DomaineItems('{self.name}')>"


class ChangeLogMilestoneProcessor:
    repo_connect = GithubConnect()

    domain_color = "#367F6C"
    domain_bold = False
    domain_cursive = True

    hosts_color = "#365E7F"
    hosts_bold = False
    hosts_cursive = True

    modules_color = "#1E1B7B"
    modules_bold = False
    modules_cursive = True

    sections: list[SectionItems] = [
        SectionItems("### **🆕 New features**", "feature"),
        SectionItems("### **🚀 Enhancements**", "enhancement"),
        SectionItems("### **🐛 Bug fixes**", "bug"),
        SectionItems("### **🔀 Refactored code**", "refactor"),
        SectionItems("### **📃 Documentation**", "documentation"),
        SectionItems("### **📃 Testing**", "unittest"),
        SectionItems("### **Merged pull requests**", "*")
    ]
    domains: list[DomaineItems] = [
        DomaineItems("3d", ["maya", "houdini", "ue", "3dsmax", "blender"]),
        DomaineItems("2d", [
            "nuke", "fusion", "tv paint",
            "after effects", "harmony", "photoshop"
        ]),
        DomaineItems("editorial", ["hiero", "flame", "resolve"]),
        DomaineItems("other", ["*"])
    ]

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

        printer.echo(f"Collected PRs {pformat(self._pullrequests)}")

        self._populate_sections()
        self._sort_by_hosts()

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

    def _populate_sections(self):
        all_labels = [sec.label for sec in self.sections if "*" not in sec.label]
        for pull in self._pullrequests:
            for section in self.sections:
                if section.label != "*" and any(re.match(section.label, type_) for type_ in pull.types):
                    section.pull_append(pull)
                    break
                elif section.label == "*" and not any(True for type_ in pull.types if type_ in all_labels):
                    section.pull_append(pull)
                    break

    def _sort_by_hosts(self):
        for section in self.sections:
            new_order: list[PullRequestDescription] = []
            pulls = deepcopy(section.pulls)

            for domain in self.domains:
                for host in domain.hosts:
                    for pr_ in pulls:
                        if host in pr_.hosts:
                            # add domaine to item
                            pr_.domain = domain.name
                            # add to reorder
                            if pr_ not in new_order:
                                new_order.append(pr_)
                                # dont duplicate and remove item
                                pulls.remove(pr_)
                    if host == "*" and pulls:
                        for pr_ in pulls:
                            # add domaine to item
                            pr_.domain = domain.name
                            # add to reorder
                            if pr_ not in new_order:
                                new_order.append(pr_)
                                # dont duplicate and remove item
                                pulls.remove(pr_)

            section.pulls = new_order

    def _get_changelog_item_from_template(self, pull: PullRequestDescription):
        tags = ""
        modules_str = ""

        # get pr kwargs
        domain = pull.domain
        title = pull.get_title()
        url = pull.get_url()
        body = pull.get_body()
        hosts = pull.hosts
        modules = pull.modules

        # add domain to tags
        if domain:
            domain_text = (
                f"<font color='{self.domain_color}';>"
                f"{domain}</font> "
            )
            if self.domain_bold:
                domain_text = f"<b>{domain_text}</b>"
            if self.domain_cursive:
                domain_text = f"<i>{domain_text}</i>"

            tags += domain_text + " "

        # add hosts to tags
        hosts_str = ",".join(hosts) if hosts else ""
        if hosts_str:
            hosts_text = (
                f"<font style='color:{self.hosts_color}';>"
                f"/ {hosts_str}</font>"
            )
            if self.hosts_bold:
                hosts_text = f"<b>{hosts_text}</b>"
            if self.hosts_cursive:
                hosts_text = f"<i>{hosts_text}</i>"

            tags += hosts_text+ " "

        # add modules to tags
        modules_str = ",".join(modules) if modules else ""
        if modules_str:
            modules_text = (
                f"<font style='color:{self.modules_color}';>"
                f"/ {modules_str}</font>"
            )
            if self.modules_bold:
                modules_text = f"<b>{modules_text}</b>"
            if self.modules_cursive:
                modules_text = f"<i>{modules_text}</i>"

            tags += modules_text + " "

        # format template and return
        return f"""
<details>
<summary>{title} {url}</summary>

{body}
___

</details>\n
"""

    def generate(self):
        out_text = ""
        for section in self.sections:
            if not section.pulls:
                continue

            out_text += section.title + "\n\n"
            for pull in section.pulls:
                out_text += self._get_changelog_item_from_template(pull)

        return out_text


def _get_request_header():
    repo_connect = GithubConnect()

    return {"Authorization": f"Bearer {repo_connect.token}"}


def assign_milestone_to_issue(milestone_id, issue_id):
    """Assign milestone to issue by ids

    Args:
        milestone_id (int): milestone number id
        issue_id (int): issue milestone id
    """
    repo_connect = GithubConnect()

    try:
        request = requests.patch(
            url=f"https://api.github.com/repos/{repo_connect.repo_path}/issues/{issue_id}",
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


@click.command(
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
def assign_milestone_to_issue_cli(milestone_id, issue_id):
    """Wrapping cli function

    Assign milestone to issue by ids

    Args:
        milestone_id (int): milestone number id
        issue_id (int): issue milestone id
    """
    printer.echo("Assigning milestone to issue by ids...")
    assign_milestone_to_issue(milestone_id, issue_id)


def generate_milestone_changelog(milestone, new_tag, old_tag):
    """Generate changelog from input milestone

    Args:
        milestone (str): milestone name
        new_tag (str):  New version tag
        old_tag (str):  Current version tag
    """
    repo_connect = GithubConnect()

    release_head = f"""
[Full Changelog](https://github.com/{repo_connect.repo_path}/compare/{old_tag}...{new_tag})

"""

    changelog = ChangeLogMilestoneProcessor(milestone)

    # join head with changelog
    changelog_str = release_head + changelog.generate()

    return changelog_str


@click.command(
    name="generate-milestone-changelog",
    help=(
        "Generate changelong form input milestone. "
        "Returns markdown text with changelog"
    )
)
@click.option(
    "--milestone", required=True,
    help="Name of milestone > `1.0.1`"
)
@click.option(
    "--old-tag", required=True,
    help="Current tag version"
)
@click.option(
    "--new-tag", required=True,
    help="New tag version"
)
def generate_milestone_changelog_cli(milestone, new_tag, old_tag):
    """Wrapping cli function

    Generate changelog from input milestone

    Args:
        milestone (str): milestone name
        new_tag (str):  New version tag
        old_tag (str):  Current version tag
    """
    printer.echo("Generating changelog from milestone...")

    changelong_str = generate_milestone_changelog(milestone, new_tag, old_tag)

    tfile = tempfile.NamedTemporaryFile(mode="w+", encoding="UTF-8")
    tfile.close()

    with open(tfile.name, mode="w+", encoding="UTF-8") as file:
        file.write(changelong_str)
        file.close()

    print(tfile.name)


def add_to_changelog(new_changelog_path, old_changelog_path):
    """Add new changelog to current changelog file

    Args:
        new_changelog_path (str): Path to new temp changelog file
        old_changelog_path (str): Path to current changelog
                                  file usually `./CHANGELOG.md`
    """
    printer.echo("Adding changelog to changelog file...")
    # read new changelog
    with open(new_changelog_path, "r", encoding="UTF-8") as nf_:
        new_changelog = nf_.read()
        nf_.close()

    # write new changelog at beginning of current changelog file
    with open(old_changelog_path, "r+", encoding="UTF-8") as of_:
        old_new_changelog = of_.read()
        if new_changelog in old_new_changelog:
            return False

        # move cursor back to top
        of_.seek(0)
        lines = of_.readlines()
        start = "".join(lines[0]) + "\n"
        end = "".join(lines[1:])
        of_.seek(0)
        of_.write(start + new_changelog + '\n' + end)
        of_.close()

    return True


@click.command(
    name="add-to-changelog-file",
    help=(
        "Add changelog to input file"
    )
)
@click.option(
    "--new-changelog-path", required=True,
    help="Path to new temp changelog file",
    type=click.Path()
)
@click.option(
    "--old-changelog-path", required=True,
    help="Path to current changelog file usually `./CHANGELOG.md`",
    type=click.Path()
)
def add_to_changelog_cli(new_changelog_path, old_changelog_path):
    """Add new changelog to current changelog file

    Args:
        new_changelog_path (str): Path to new temp changelog file
        old_changelog_path (str): Path to current changelog
                                  file usually `./CHANGELOG.md`
    """
    print(
        add_to_changelog(new_changelog_path, old_changelog_path)
    )
