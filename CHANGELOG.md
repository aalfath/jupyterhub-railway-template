# Changelog

## 6.2.0-1 (2026-11-24)

First release.

- JupyterHub 6.2.0 (`jupyterhub/jupyterhub:6.2.0@sha256:57905557c2e52e5ecb13d4fbaacea19bc4d4afbb9fed4405c6bc1b582e32e110`), JupyterLab 4.6.6, NativeAuthenticator 1.4.0, NumPy 2.5.5, pandas 3.1.1, Matplotlib 3.11.2.
- One service with a volume at `/data` for the hub database, cookie secret and user homes.
- Admin account created on first boot from `JUPYTERHUB_ADMIN_USER` / `JUPYTERHUB_ADMIN_PASSWORD` (generated). Sign-ups need the admin's approval.
