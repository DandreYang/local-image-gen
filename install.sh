#!/usr/bin/env bash
# Install local-image-gen as a CLI and as an agent skill.
# Safe to re-run. Never overwrites a non-symlink skill directory.
set -euo pipefail

NAME="local-image-gen"
REPO_SLUG="${LOCAL_IMAGE_GEN_REPO:-DandreYang/local-image-gen}"
REPO_URL="${LOCAL_IMAGE_GEN_REPO_URL:-https://github.com/${REPO_SLUG}.git}"
DEFAULT_HOME="${HOME}/.local/share/${NAME}"
BIN_DIR="${LOCAL_IMAGE_GEN_BIN:-${HOME}/.local/bin}"
DRY_RUN=0

usage() {
  cat <<EOF
Usage: install.sh [--dry-run]

One-liner (no prior clone):
  curl -fsSL https://raw.githubusercontent.com/${REPO_SLUG}/main/install.sh | bash

From a checkout:
  ./install.sh

Clones or updates ${DEFAULT_HOME}, puts ${NAME} on PATH, and
symlinks the skill into detected agent directories.
EOF
}

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  usage
  exit 0
fi
if [[ "${1:-}" == "--dry-run" ]]; then
  DRY_RUN=1
fi

run() {
  if [[ "$DRY_RUN" -eq 1 ]]; then
    printf 'would  '
    printf '%q ' "$@"
    printf '\n'
    return 0
  fi
  "$@"
}

canon() {
  python3 -c 'import os, sys; print(os.path.realpath(sys.argv[1]))' "$1"
}

script_dir=""
if [[ -n "${BASH_SOURCE[0]:-}" && -f "${BASH_SOURCE[0]}" ]]; then
  script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
fi

if [[ -n "$script_dir" && -f "$script_dir/SKILL.md" && -f "$script_dir/scripts/local_image_gen.py" ]]; then
  ROOT="$script_dir"
  SOURCE="checkout"
else
  ROOT="${LOCAL_IMAGE_GEN_HOME:-$DEFAULT_HOME}"
  SOURCE="fetch"
fi

if ! command -v git >/dev/null 2>&1; then
  echo "git is required." >&2
  exit 1
fi
if ! command -v python3 >/dev/null 2>&1; then
  echo "python3 is required (3.9+)." >&2
  exit 1
fi

if [[ "$SOURCE" == "fetch" ]]; then
  if [[ -d "$ROOT/.git" ]]; then
    echo "update  ${ROOT}"
    if [[ "$DRY_RUN" -eq 0 ]]; then
      git -C "$ROOT" pull --ff-only
    fi
  elif [[ -e "$ROOT" ]]; then
    echo "skip    ${ROOT} exists and is not a git checkout" >&2
    exit 1
  else
    echo "clone   ${REPO_URL} -> ${ROOT}"
    run mkdir -p "$(dirname "$ROOT")"
    run git clone --depth 1 "$REPO_URL" "$ROOT"
  fi
else
  echo "using   ${ROOT}"
fi

CLI_SRC="${ROOT}/scripts/local_image_gen.py"
if [[ ! -f "$CLI_SRC" ]]; then
  echo "missing ${CLI_SRC}" >&2
  exit 1
fi

run mkdir -p "$BIN_DIR"
WRAPPER="${BIN_DIR}/${NAME}"
if [[ "$DRY_RUN" -eq 1 ]]; then
  echo "would   write ${WRAPPER}"
else
  cat >"$WRAPPER" <<EOF
#!/usr/bin/env bash
exec python3 "$(printf '%q' "$CLI_SRC")" "\$@"
EOF
  chmod +x "$WRAPPER"
  echo "cli     ${WRAPPER}"
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
    if [[ "$(canon "$dest")" == "$(canon "$ROOT")" ]]; then
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
echo "install_root=${ROOT}"
echo "cli=${WRAPPER}"
echo "skills_linked_or_ok=${linked} skipped=${skipped} agents_not_present=${missing}"

if [[ ":${PATH}:" != *":${BIN_DIR}:"* ]]; then
  echo
  echo "Add this to your shell profile so '${NAME}' is on PATH:"
  echo "  export PATH=\"${BIN_DIR}:\$PATH\""
fi

if command -v dyro >/dev/null 2>&1; then
  echo
  echo "Dyro is optional. Image gen does not require it."
  echo "Inside a Dyro workspace, images default to <workspace>/outputs/images."
fi

echo
echo "Next:"
if command -v "$NAME" >/dev/null 2>&1 || [[ ":${PATH}:" == *":${BIN_DIR}:"* ]]; then
  echo "  ${NAME} --list-providers"
  echo "  ${NAME} --doctor"
else
  echo "  \"${WRAPPER}\" --list-providers"
  echo "  \"${WRAPPER}\" --doctor"
fi
