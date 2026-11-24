[![Deploy on Railway](https://railway.com/button.svg)](https://railway.com/new/template/jupyterhub-1?utm_medium=integration&utm_source=button&utm_campaign=jupyterhub)

# JupyterHub on Railway

One-click [JupyterHub](https://jupyter.org/hub) **6.2.0** for Railway: a multi-user Jupyter server where each person signs in and gets their own JupyterLab, home folder and Python kernels.

## What the template deploys

One service, **JupyterHub**, built from this repo's `Dockerfile`:

- `FROM jupyterhub/jupyterhub:6.2.0@sha256:57905557c2e52e5ecb13d4fbaacea19bc4d4afbb9fed4405c6bc1b582e32e110` (the official image; the same digest as `quay.io/jupyterhub/jupyterhub:6.2.0`).
- The hub, its `configurable-http-proxy` (listening on `PORT` 8000) and every user's JupyterLab server run in this one container. Users are local UNIX accounts started by JupyterHub's default `LocalProcessSpawner`, so there is no Docker-in-Docker and no Kubernetes.
- JupyterLab 4.6.6 with NumPy, pandas and Matplotlib, plus git, nano and less for the terminal. All Python packages are pinned (`requirements.txt`, `constraints.txt`).
- Logins use [NativeAuthenticator](https://native-authenticator.readthedocs.io/) 1.4.0: an admin account is created on first boot, and anyone else can sign up at `/hub/signup` but can only log in after the admin approves them at `/hub/authorize`.
- One Railway volume at `/data` holds everything: `/data/hub` (the hub's SQLite database with accounts and password hashes, and its cookie secret) and `/data/home/<user>` (each user's files and `pip install --user` packages).
- Health check: `/hub/health`. Restart policy: on failure. If the hub stops for any reason, the container exits non-zero, so Railway restarts it.

## Variables

| Variable | Default | Notes |
|---|---|---|
| `JUPYTERHUB_ADMIN_USER` | `admin` | Admin username (lower case letters, digits, `-`, `_`). |
| `JUPYTERHUB_ADMIN_PASSWORD` | generated (24 characters) | The admin's password. Read it on the service's **Variables** tab. Changing it and redeploying resets the admin password. |
| `PORT` | `8000` | Port the proxy listens on. |

Optional, not set by the template: `JUPYTERHUB_IDLE_TIMEOUT` (seconds, default `3600`) stops idle kernels, terminals and user servers.

## After deploying

1. Open the service's public URL and sign in as `admin` with the password from the **Variables** tab.
2. Your JupyterLab starts in about 10 seconds with a `Welcome.ipynb`; run it to check NumPy, pandas and Matplotlib.
3. Send people the `/hub/signup` link, then approve them at `/hub/authorize`. The **Admin** page (`/hub/admin`) lists users and running servers.

## Memory and plan sizes

Measured on Railway with a 0.5 GB limit: the hub uses about 150 MB, the proxy 75 MB and one idle JupyterLab server 165 MB, so **0.5 GB (Free plan) runs the hub plus one user server** with small notebooks. The template limits how many user servers run at once from the service's memory: one at 0.5 GB, three at 1 GB, about 26 at 8 GB. If a notebook uses more memory than the service has, Linux stops that notebook's kernel (JupyterLab shows "Kernel restarting") and the hub keeps running. For a class or team, give the service 2 GB or more under **Settings → Resources**.

Railway services have no GPU; this is a CPU-only Jupyter.

## Updates

This template builds from `aalfath/jupyterhub-railway-template`. When we merge a new JupyterHub or JupyterLab version into `main`, Railway shows "update available" on your service and you choose when to apply it. Read `CHANGELOG.md` first. The hub upgrades its own database on start (`upgrade_db`), and your volume is kept.

## Local test

```sh
docker build -t jupyterhub-railway .
docker run -p 8000:8000 -e JUPYTERHUB_ADMIN_PASSWORD=change-me-please -v jhdata:/data jupyterhub-railway
```

Licence: JupyterHub and NativeAuthenticator are BSD-3-Clause (Project Jupyter). This wrapper is offered under the same terms.
