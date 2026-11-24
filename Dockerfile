# JupyterHub for Railway: hub + configurable-http-proxy + JupyterLab user servers
# in one container. Upstream image: https://hub.docker.com/r/jupyterhub/jupyterhub
# (same digest as quay.io/jupyterhub/jupyterhub:6.2.0).
FROM jupyterhub/jupyterhub:6.2.0@sha256:57905557c2e52e5ecb13d4fbaacea19bc4d4afbb9fed4405c6bc1b582e32e110

ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8000 \
    JUPYTERHUB_DATA=/data

# tini reaps the proxy and every user server the hub forks; git, nano and less
# make the JupyterLab terminal usable.
RUN apt-get update -qq \
 && apt-get install -yqq --no-install-recommends tini git nano less \
 && rm -rf /var/lib/apt/lists/* /var/log/apt /var/log/dpkg.log

COPY requirements.txt constraints.txt /tmp/
RUN pip install --no-compile -r /tmp/requirements.txt -c /tmp/constraints.txt \
 && rm /tmp/requirements.txt /tmp/constraints.txt \
 && jupyter lab --version && python -c "import nativeauthenticator, numpy, pandas, matplotlib"

# Home-folder template for new users (the stock Ubuntu one plus a welcome notebook).
COPY skel/ /etc/skel/
COPY jupyterhub_config.py /srv/jupyterhub/jupyterhub_config.py
COPY --chmod=0755 jh-adduser /usr/local/bin/jh-adduser
COPY --chmod=0755 start.sh /usr/local/bin/jupyterhub-railway-start

# The image's default "ubuntu" user (uid 1000) is not a hub user.
RUN userdel -r ubuntu 2>/dev/null || true; \
    sed -i 's/^HOME_MODE.*/HOME_MODE\t0750/' /etc/login.defs; \
    python -c "import ast; ast.parse(open('/srv/jupyterhub/jupyterhub_config.py').read())"

EXPOSE 8000
ENTRYPOINT ["/usr/bin/tini", "-g", "--"]
CMD ["/usr/local/bin/jupyterhub-railway-start"]
