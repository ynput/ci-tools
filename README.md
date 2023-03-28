# example commands
- get commit sha found in milestone description
`python .\tools\cli.py milestones get-milestone-commit --milestone=next-patch`

- get commit sha found in milestone description
`python .\tools\cli.py milestones get-milestone-tag --milestone=next-patch`

- get latest commit on input branch name
`python .\tools\cli.py repo get-latest-commit --branch=develop`

- get new version number (part will define how to version up)
`python .\tools\cli.py versioning bump-version --type=release --part=patch`

- get current version from tags
`python .\tools\cli.py versioning current-version --type=release`

- bump versions in workspace files
`python .\tools\cli.py versioning bump-file-version --version=4.1.2 --version-path=./openpype/version.py --pyproject-path=./pyproject.toml`

- set commit hash to milestone
`python .\tools\cli.py milestones set-milestone-commit --milestone=next-minor --commit-sha=9a4a138b05097e9f8c71053ce74c013171c2125c`

- set tag to milestone
`python .\tools\cli.py milestones set-milestone-tag --milestone=next-minor --tag-name=3.2.1`


- Set changelog to milestone
`python .\tools\cli.py milestones set-milestone-changelog --milestone=next-minor --changelog-path=/tmp/oanneq7asdfe`

- Generate changelog to temp file
`python .\tools\cli.py changelog generate-milestone-changelog --milestone=3.15.2 --old-tag=3.15.1 --new-tag=3.15.2`

- Add changelong to current changelog file
`python .\tools\cli.py changelog add-to-changelog-file --old-changelog-path=./CHANGELOG.md  --new-changelog-path=/Temp/tmpzye6axex --tag=3.1.2`
