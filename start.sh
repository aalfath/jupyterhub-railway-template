#!/bin/sh
# Start JupyterHub on Railway. Runs under tini (PID 1), so when the hub stops
# for any reason other than a deploy's SIGTERM, the container exits non-zero
# and Railway's ON_FAILURE policy restarts it.
set -eu
DATA=${JUPYTERHUB_DATA:-/data}
export JUPYTERHUB_DATA="$DATA"
export JUPYTERHUB_HOME_ROOT="$DATA/home"
if [ -z "${JUPYTERHUB_ADMIN_PASSWORD:-}" ] || [ "${#JUPYTERHUB_ADMIN_PASSWORD}" -lt 10 ]; then
  echo "FATAL: set JUPYTERHUB_ADMIN_PASSWORD (10 characters or more) on the service." >&2
  exit 1
fi
mkdir -p "$DATA/hub" "$DATA/home"
chmod 0700 "$DATA/hub"
chmod 0755 "$DATA" "$DATA/home"
cd /srv/jupyterhub
jupyterhub -f /srv/jupyterhub/jupyterhub_config.py "$@" || rc=$?
rc=${rc:-0}
# A clean exit that wasn't asked for (no SIGTERM) still has to restart the service.
[ "$rc" -eq 0 ] && rc=1
echo "jupyterhub exited (code $rc)" >&2
exit "$rc"
