#!/bin/sh
set -eu
case "\${1:-}" in
  *Username*|*username*) printf '%s\n' 'x-access-token' ;;
  *Password*|*password*) printf '%s\n' "\${GITHUB_TOKEN:?GitHub read token is not configured}" ;;
  *) exit 1 ;;
esac
