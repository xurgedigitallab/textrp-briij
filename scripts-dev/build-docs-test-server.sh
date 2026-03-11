#!/usr/bin/env bash
# Build the docs for serving at test-server.textrp.io/docs
# Requires mdbook 0.5.2+ (older releases generate incompatible theme assets).
# Output is in book/ with site-url set to /docs/ so nginx can serve it at /docs/
#
# Usage (from repo root):
#   ./scripts-dev/build-docs-test-server.sh
# Then copy book/ to your server's doc root, e.g.:
#   sudo mkdir -p /var/www/test-server-docs/docs
#   sudo rsync -av --delete book/ /var/www/test-server-docs/docs/

set -e
cd "$(dirname "$0")/.."

if ! command -v mdbook &>/dev/null; then
  echo "mdbook not found. Install with: cargo install mdbook --version 0.5.2 --locked"
  exit 1
fi

required_mdbook_version="0.5.2"
raw_mdbook_version="$(mdbook --version | awk '{print $2}')"
mdbook_version="$(echo "$raw_mdbook_version" | sed -E 's/^v([0-9]+\.[0-9]+\.[0-9]+).*/\1/')"

version_gte() {
  local IFS=.
  local left=($1)
  local right=($2)
  local i

  for ((i=${#left[@]}; i<${#right[@]}; i++)); do
    left[i]=0
  done
  for ((i=${#right[@]}; i<${#left[@]}; i++)); do
    right[i]=0
  done

  for ((i=0; i<${#left[@]}; i++)); do
    if ((10#${left[i]} > 10#${right[i]})); then
      return 0
    fi
    if ((10#${left[i]} < 10#${right[i]})); then
      return 1
    fi
  done

  return 0
}

if [[ ! "$mdbook_version" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]] || ! version_gte "$mdbook_version" "$required_mdbook_version"; then
  echo "mdbook $raw_mdbook_version is too old for docs theming."
  echo "Install mdbook >= $required_mdbook_version, for example:"
  echo "  cargo install mdbook --version $required_mdbook_version --locked"
  exit 1
fi

# Build with base path /docs/ so links work when served at test-server.textrp.io/docs
export MDBOOK_OUTPUT__HTML__SITE_URL="/docs/"

# Avoid deploying stale output when a prior build used an incompatible mdBook.
rm -rf book
mdbook build

# mdbook does not emit index.html at root by default; use welcome as the landing page
if [[ -f book/welcome_and_overview.html ]]; then
  cp book/welcome_and_overview.html book/index.html
fi

has_match() {
  local pattern
  for pattern in "$@"; do
    if compgen -G "$pattern" > /dev/null; then
      return 0
    fi
  done
  return 1
}

# Validate the generated asset layout expected by our custom theme.
missing_assets=0

if [[ ! -f "book/index.html" ]]; then
  echo "Missing required docs asset: book/index.html"
  missing_assets=1
fi

if ! has_match "book/css/variables.css" "book/css/variables-*.css"; then
  echo "Missing required docs asset: book/css/variables*.css"
  missing_assets=1
fi

if ! has_match "book/css/general.css" "book/css/general-*.css"; then
  echo "Missing required docs asset: book/css/general*.css"
  missing_assets=1
fi

if ! has_match "book/css/chrome.css" "book/css/chrome-*.css"; then
  echo "Missing required docs asset: book/css/chrome*.css"
  missing_assets=1
fi

if ! has_match "book/fonts/fonts.css" "book/fonts/fonts-*.css"; then
  echo "Missing required docs asset: book/fonts/fonts*.css"
  missing_assets=1
fi

if ! has_match "book/toc.js" "book/toc-*.js"; then
  echo "Missing required docs asset: book/toc*.js"
  missing_assets=1
fi

if ! has_match "book/docs/website_files/version-picker.js" "book/docs/website_files/version-picker-*.js"; then
  echo "Missing required docs asset: book/docs/website_files/version-picker*.js"
  missing_assets=1
fi

if ! has_match "book/docs/website_files/version.js" "book/docs/website_files/version-*.js"; then
  echo "Missing required docs asset: book/docs/website_files/version*.js"
  missing_assets=1
fi

if [[ "$missing_assets" -ne 0 ]]; then
  echo "Build output is incomplete and should not be deployed."
  exit 1
fi

echo "Docs built in book/. To serve at test-server.textrp.io/docs:"
echo "  sudo mkdir -p /var/www/test-server-docs/docs"
echo "  sudo rsync -av --delete book/ /var/www/test-server-docs/docs/"
echo "Then reload nginx (see nginx/test-server.textrp.io.conf)."
