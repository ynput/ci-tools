# example commands
- get commit sha found in milestone description
`python .\tools\cli.py milestones get-milestone-commit --milestone=next-patch`

- get latest commit on input branch name
`python .\tools\cli.py repo get-latest-commit --branch=develop`

- get new version number (part will define how to version up)
`python .\tools\cli.py versioning bump-version --type=release --part=patch`

- bump versions in workspace files
`python .\tools\cli.py versioning bump-file-version --version=4.1.2 --version-path=./openpype/version.py --pyproject-path=./pyproject.toml`