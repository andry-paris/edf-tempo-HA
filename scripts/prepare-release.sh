#!/usr/bin/env bash

set -euo pipefail

usage() {
  echo "Usage: $0 <version>" >&2
  echo "Example: $0 1.2.11" >&2
}

if [[ $# -ne 1 ]]; then
  usage
  exit 2
fi

version="$1"
if [[ ! "$version" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
  echo "Error: version must use the X.Y.Z format." >&2
  exit 2
fi

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd "$script_dir/.." && pwd)"
cd "$repo_root"

for command_name in git python3 node; do
  if ! command -v "$command_name" >/dev/null 2>&1; then
    echo "Error: required command '$command_name' was not found." >&2
    exit 1
  fi
done

current_branch="$(git branch --show-current)"
if [[ "$current_branch" != "main" ]]; then
  echo "Error: run this script from main (current branch: $current_branch)." >&2
  exit 1
fi

if [[ -n "$(git status --porcelain --untracked-files=normal)" ]]; then
  echo "Error: the working tree must be clean before preparing a release." >&2
  exit 1
fi

release_branch="release/$version"
if git show-ref --verify --quiet "refs/heads/$release_branch"; then
  echo "Error: local branch '$release_branch' already exists." >&2
  exit 1
fi

current_version="$(python3 -c 'import json; print(json.load(open("custom_components/edf_tempo/manifest.json", encoding="utf-8"))["version"])')"
if [[ "$current_version" == "$version" ]]; then
  echo "Error: version $version is already present in the manifest." >&2
  exit 1
fi

git switch -c "$release_branch"

python3 - "$current_version" "$version" <<'PY'
from __future__ import annotations

import sys
from pathlib import Path

old_version, new_version = sys.argv[1:]


def replace_exact(path: str, old: str, new: str, expected: int = 1) -> None:
    file_path = Path(path)
    text = file_path.read_text(encoding="utf-8")
    count = text.count(old)
    if count != expected:
        raise SystemExit(
            f"Error: expected {expected} occurrence(s) of {old!r} in {path}, found {count}."
        )
    file_path.write_text(text.replace(old, new), encoding="utf-8")


replace_exact(
    "custom_components/edf_tempo/manifest.json",
    f'"version": "{old_version}"',
    f'"version": "{new_version}"',
)
replace_exact(
    "custom_components/edf_tempo/const.py",
    f'INTEGRATION_VERSION = "{old_version}"',
    f'INTEGRATION_VERSION = "{new_version}"',
)
replace_exact(
    "README.md",
    f"/edf_tempo/card.js?v={old_version}",
    f"/edf_tempo/card.js?v={new_version}",
)

private_readme = Path("README.private.md")
if private_readme.is_file():
    replace_exact(
        "README.private.md",
        f"Current development version: `{old_version}`.",
        f"Current development version: `{new_version}`.",
    )
    replace_exact(
        "README.private.md",
        f"/edf_tempo/card.js?v={old_version}",
        f"/edf_tempo/card.js?v={new_version}",
        expected=2,
    )
PY

python3 -m unittest discover -s tests -v
node --test tests_js/*.test.js
git diff --check

git add README.md custom_components/edf_tempo/const.py custom_components/edf_tempo/manifest.json
git commit -m "Prepare version $version"

echo
echo "Release $version prepared on branch $release_branch."
echo "Next step: ./scripts/open-release-pr.sh $version"
