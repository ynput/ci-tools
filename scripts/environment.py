import re
import io
import subprocess
import platform
from optparse import OptionParser


def file_regex_find(filename, regex):
    with open(filename, 'r') as f:
        for line in f.readlines():
            found = re.findall(regex, line)
            if not found:
                continue
            return found.pop()


def check_pyproject_python_version():
    # bump pyproject.toml
    filename = "pyproject.toml"
    regex = "^python = \"(.*)\""
    return file_regex_find(filename, regex)

def set_pyenv_python_version():
    pyenv_executable = "pyenv"
    pyproj_pyversion = check_pyproject_python_version()

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

    return exist_version


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
    test_version = test_version.replace("*", "[\\d]+")
    regex = f"({test_version})"
    match_versions = []
    for v_ in versions:
        found = re.findall(regex, v_)
        if not found:
            continue
        match_versions.append(found.pop())

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


def main():
    usage = "usage: %prog [options] arg"
    parser = OptionParser(usage)
    parser.add_option("-P", "--set-python-version",
                      dest="set_pyenv_local_version", action="store_true", default=False,
                      help="return pyproject python version")

    (options, args) = parser.parse_args()

    if options.set_pyenv_local_version:
        version = set_pyenv_python_version()
        print(version)


if __name__ == "__main__":
    main()
