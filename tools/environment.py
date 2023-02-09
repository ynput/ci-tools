import re
import io
import click
import subprocess
import platform
from utils import Printer

printer = Printer()

def file_regex_find(filename, regex):
    with open(filename, 'r') as f:
        for line in f:
            found = re.findall(regex, line)
            if not found:
                continue
            return found.pop()


def check_pyproject_python_version(pyproject_path=None):
    # bump pyproject.toml
    pyproject_path = pyproject_path or "pyproject.toml"
    regex = "^python = \"(.*)\""
    return file_regex_find(pyproject_path, regex)


def _install_pyenv_version(pyenv_executable, pyproj_pyversion):
    args_versions_available = [pyenv_executable, "install", "-l"]
    available_versions = _get_stdout_from_command(args_versions_available)
    version_to_install = _filter_versions(available_versions, pyproj_pyversion)

    if not version_to_install:
        raise KeyError((
            "Version doesnt exists in pyenv repository. "
            f"Available versions: {available_versions}. "
            f"Pyproject.toml version: {pyproj_pyversion}."
        ))

    # pyenv install version
    _subprocess_args(
        [pyenv_executable, "install", version_to_install]
    ).communicate()

    return version_to_install


def _filter_versions(versions, test_version):
    # in case of ">=3.9.1,<3.10"
    if "," in test_version:
        test_version = test_version.split(",")[-1]

    # remove all symbols and keep only semver
    test_version = re.sub("[\^<>=]", "", test_version)

    # lets add .* at the and if there is not
    # so in next step we replace it with number search
    if "*" not in test_version:
        test_version += ".*"

    printer.echo(f"Testing version: {test_version}")

    test_version = test_version.replace("*", "[\\d]+")
    regex = f"({test_version})"
    match_versions = []
    for v_ in versions:
        found = re.findall(regex, v_)
        if not found:
            continue
        match_versions.append(found.pop())

    printer.echo(match_versions)
    # reverse sort so pop can take higher version
    if match_versions:
        match_versions = sorted(
            list(set(match_versions))
        )
        return match_versions.pop()


def _subprocess_args(args):
    return subprocess.Popen(args, shell=True, stdout=subprocess.PIPE)


def _get_stdout_from_command(args):
    proc = _subprocess_args(args)
    return_list = []
    return_list.extend(
        line.rstrip().strip()
        for line in io.TextIOWrapper(proc.stdout, encoding="utf-8")
    )
    return return_list


@click.command(
    name="set-python-version",
    help=(
        "Return pyproject compatible python version."
    )
)
@click.option(
    "--pyproject-path", required=False,
    help="Relative path to project root"
)
def set_pyenv_python_version(pyproject_path=None):

    printer.echo("Setting up python environment...")

    pyenv_executable = "pyenv"
    pyproj_pyversion = check_pyproject_python_version(pyproject_path)

    if platform.system().lower() == "windows":
        pyenv_executable += ".bat"

    args_versions_installed = [pyenv_executable, "versions"]
    installed_versions = _get_stdout_from_command(args_versions_installed)

    # check if available versions corresponing to pyproj vers
    exist_version = _filter_versions(installed_versions, pyproj_pyversion)

    if not exist_version:
        exist_version = _install_pyenv_version(
            pyenv_executable, pyproj_pyversion
        )

    # pyenv local version to current dir
    _subprocess_args(
        [pyenv_executable, "local", exist_version]
    ).communicate()

    print(exist_version)
