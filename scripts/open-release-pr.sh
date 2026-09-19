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

for command_name in git gh python3; do
  if ! command -v "$command_name" >/dev/null 2>&1; then
    echo "Error: required command '$command_name' was not found." >&2
    exit 1
  fi
done

release_branch="release/$version"
current_branch="$(git branch --show-current)"
if [[ "$current_branch" != "$release_branch" ]]; then
  echo "Error: expected branch '$release_branch' (current branch: $current_branch)." >&2
  exit 1
fi

if [[ -n "$(git status --porcelain --untracked-files=normal)" ]]; then
  echo "Error: the working tree must be clean before opening the pull request." >&2
  exit 1
fi

manifest_version="$(python3 -c 'import json; print(json.load(open("custom_components/edf_tempo/manifest.json", encoding="utf-8"))["version"])')"
if [[ "$manifest_version" != "$version" ]]; then
  echo "Error: manifest version is $manifest_version, expected $version." >&2
  exit 1
fi

git push -u origin "$release_branch"

existing_pr="$(gh pr list --head "$release_branch" --state open --json url --jq '.[0].url // empty')"
if [[ -n "$existing_pr" ]]; then
  echo "An open pull request already exists: $existing_pr"
  exit 0
fi

pr_url="$(gh pr create \
  --base main \
  --head "$release_branch" \
  --title "Prepare EDF Tempo $version" \
  --body "$(cat <<EOF
## Résumé

Prépare la release EDF Tempo $version.

## Modifications

- met à jour la version du manifeste vers $version ;
- synchronise la constante interne de version ;
- actualise l’URL versionnée de la carte Lovelace dans le README.

## Validation

- tests unitaires Python réussis localement ;
- tests JavaScript réussis localement ;
- validations HACS, Hassfest et Home Assistant exécutées par GitHub Actions.
EOF
)" \
)"

echo "Pull request created: $pr_url"
echo "Wait for all GitHub checks before merging it."
echo "Creating a tag or GitHub release remains a separate, explicit action."
