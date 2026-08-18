#!/usr/bin/env bash
# Link this checkout into local coding-agent skill directories.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
NAME="local-image-gen"
DRY_RUN=0

usage() {
  cat <<EOF
Usage: ./install.sh [--dry-run]

Creates a symlink named ${NAME} in each detected agent skill root.
Existing non-matching entries are left untouched.
EOF
}

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  usage
  exit 0
fi
if [[ "${1:-}" == "--dry-run" ]]; then
  DRY_RUN=1
fi

SKILL_ROOTS=(
  "${HOME}/.codex/skills"
  "${HOME}/.claude/skills"
  "${HOME}/.agents/skills"
  "${HOME}/.gemini/skills"
  "${HOME}/.cursor/skills"
  "${HOME}/.trae-cn/skills"
  "${HOME}/.hermes/skills"
  "${HOME}/.grok/skills"
  "${HOME}/.opencode/skills"
  "${HOME}/.config/opencode/skills"
)

linked=0
skipped=0
missing=0

for root in "${SKILL_ROOTS[@]}"; do
  parent="$(dirname "$root")"
  dest="${root}/${NAME}"
  if [[ ! -d "$root" && ! -d "$parent" ]]; then
    missing=$((missing + 1))
    continue
  fi
  if [[ -L "$dest" ]]; then
    current="$(readlink "$dest")"
    if [[ "$current" == "$ROOT" ]]; then
      echo "ok      ${dest}"
      linked=$((linked + 1))
      continue
    fi
    echo "skip    ${dest} (symlink to ${current})"
    skipped=$((skipped + 1))
    continue
  fi
  if [[ -e "$dest" ]]; then
    echo "skip    ${dest} (exists and is not a symlink)"
    skipped=$((skipped + 1))
    continue
  fi
  if [[ "$DRY_RUN" -eq 1 ]]; then
    echo "would   ${dest} -> ${ROOT}"
    linked=$((linked + 1))
    continue
  fi
  mkdir -p "$root"
  ln -s "$ROOT" "$dest"
  echo "linked  ${dest} -> ${ROOT}"
  linked=$((linked + 1))
done

echo
echo "linked_or_ok=${linked} skipped=${skipped} agents_not_present=${missing}"
if [[ "$linked" -eq 0 ]]; then
  echo "No agent skill root was found. Install the CLI by running:"
  echo "  python3 \"${ROOT}/scripts/local_image_gen.py\" --list-providers"
  exit 1
fi
