#!/usr/bin/env bash
# Publish the validated xams-sim manual at https://www.nikhef.nl/~xamsdata/xams-sim/.
# Install this script as /user/xamsdata/bin/update-xams-sim-docs.
#
# The same design as the XAMS handbook updater (xams-handbook,
# tools/update-nikhef-from-github.sh): CI moves the docs-deploy-ready tag after
# a strict build, then runs this through a key whose forced command is this
# script and nothing else. It clones that exact tag with a read-only GitHub
# deploy key, builds strictly, checks that anonymous access is refused, and
# synchronises the site into public_html/xams-sim/, which inherits the
# handbook's SSO .htaccess. The handbook sync protects that subdirectory.
set -euo pipefail

account_home=/user/xamsdata
state_root=$account_home/.local/share/xams-sim-docs-deploy
parent=$account_home/public_html
target=$parent/xams-sim
deploy_key=$account_home/.ssh/xams-sim-deploy
repository=git@github.com:XAMS-nikhef/xams-sim.git
tag=docs-deploy-ready
public_url=https://www.nikhef.nl/~xamsdata/xams-sim/
lock_file=$state_root/update.lock
deployed_file=$state_root/deployed-sha
venv_root=$state_root/venv

if [ "$(id -un)" != xamsdata ]; then
  echo "This updater must run as xamsdata." >&2
  exit 2
fi

mkdir -p "$state_root"
exec 9>"$lock_file"
flock -n 9 || exit 0

# The parent is the handbook's protected root; the manual relies on its policy.
test -f "$deploy_key"
test -d "$parent"
test -f "$parent/.xams-handbook-root"
test -f "$parent/.htaccess"
grep -Eq '^[[:space:]]*AuthType[[:space:]]+shibboleth([[:space:]]|$)' "$parent/.htaccess"
grep -Eq '^[[:space:]]*ShibRequestSetting[[:space:]]+requireSession[[:space:]]+1([[:space:]]|$)' "$parent/.htaccess"
grep -Eq '^[[:space:]]*Require[[:space:]]+shib-' "$parent/.htaccess"
# The target must have been dedicated on purpose, and must not be a link.
test -d "$target"
test ! -L "$target"
test -f "$target/.xams-sim-docs-root"
# A .htaccess of its own could loosen the inherited policy.
test ! -e "$target/.htaccess"

ssh_command="ssh -i $deploy_key -o IdentitiesOnly=yes -o BatchMode=yes -o StrictHostKeyChecking=yes"
candidate_sha=$(GIT_SSH_COMMAND="$ssh_command" git ls-remote --refs \
  "$repository" "refs/tags/$tag" | awk 'NR == 1 {print $1}')
if ! [[ "$candidate_sha" =~ ^[0-9a-f]{40}$ ]]; then
  echo "No valid $tag tag was returned." >&2
  exit 4
fi

if [ -f "$deployed_file" ] && [ "$(<"$deployed_file")" = "$candidate_sha" ]; then
  exit 0
fi

check_protected() {
  local code
  code=$(/usr/bin/curl --silent --show-error --output /dev/null \
    --write-out '%{http_code}' --max-time 20 "$public_url")
  case "$code" in
    301|302|303|307|308|401|403) return 0 ;;
    *) echo "$1: anonymous protection check returned HTTP $code." >&2; return 1 ;;
  esac
}
check_protected "Refusing deployment" || exit 5

build_root=$(mktemp -d "$state_root/build.XXXXXX")
cleanup() {
  find "$build_root" -mindepth 1 -delete
  rmdir "$build_root"
}
trap cleanup EXIT

GIT_SSH_COMMAND="$ssh_command" git clone --quiet --depth 1 \
  --branch "$tag" "$repository" "$build_root/source"
actual_sha=$(git -C "$build_root/source" rev-parse HEAD)
if [ "$actual_sha" != "$candidate_sha" ]; then
  echo "Refusing deployment: cloned commit does not match $tag." >&2
  exit 6
fi

if [ ! -x "$venv_root/bin/python" ]; then
  /usr/bin/python3 -m venv "$venv_root"
fi
"$venv_root/bin/python" -m pip install --quiet --disable-pip-version-check \
  -r "$build_root/source/requirements-docs.txt"
"$venv_root/bin/mkdocs" build --strict \
  --config-file "$build_root/source/mkdocs.yml" \
  --site-dir "$build_root/site"
find "$build_root/site" -name .DS_Store -delete

/usr/bin/rsync -a --delete --delete-excluded --exclude=.DS_Store \
  --filter='P .xams-sim-docs-root' \
  "$build_root/site/" "$target/"

check_protected "Deployment completed, but" || exit 7

printf '%s\n' "$candidate_sha" >"$deployed_file.new"
mv "$deployed_file.new" "$deployed_file"
printf 'Deployed xams-sim manual commit %s at %s\n' \
  "$candidate_sha" "$(date --iso-8601=seconds)"
