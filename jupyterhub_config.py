"""JupyterHub on Railway: one container, settings from environment variables.

- The hub starts configurable-http-proxy, which listens on $PORT.
- Each user's JupyterLab runs as a local UNIX account (LocalProcessSpawner).
- Accounts, passwords and notebooks live on the Railway volume at /data:
  /data/hub (SQLite database, cookie secret) and /data/home/<user>.
- NativeAuthenticator: the admin is created at boot from JUPYTERHUB_ADMIN_USER /
  JUPYTERHUB_ADMIN_PASSWORD; anyone else can sign up at /hub/signup but can only
  log in after the admin approves them under /hub/authorize.
"""
import os
import uuid

import bcrypt
from jupyterhub.auth import LocalAuthenticator
from jupyterhub.spawner import LocalProcessSpawner
from nativeauthenticator import NativeAuthenticator
from nativeauthenticator.orm import UserInfo

c = get_config()  # noqa: F821

DATA = os.environ.get("JUPYTERHUB_DATA", "/data")
HOME_ROOT = os.path.join(DATA, "home")
HUB_DIR = os.path.join(DATA, "hub")
ADMIN_USER = (os.environ.get("JUPYTERHUB_ADMIN_USER") or "admin").strip().lower()
ADMIN_PASSWORD = os.environ.get("JUPYTERHUB_ADMIN_PASSWORD", "")


def _cgroup_cpus():
    try:
        quota, period = open("/sys/fs/cgroup/cpu.max").read().split()
        if quota != "max":
            return max(1, int(int(quota) / int(period)))
    except (OSError, ValueError):
        pass
    return max(1, min(os.cpu_count() or 1, 2))


def _cgroup_mem_mb():
    try:
        v = open("/sys/fs/cgroup/memory.max").read().strip()
        if v != "max":
            return int(v) // (1024 * 1024)
    except (OSError, ValueError):
        pass
    return 0


CPUS = _cgroup_cpus()
MEM_MB = _cgroup_mem_mb()

# ---------------------------------------------------------------- network
c.JupyterHub.bind_url = "http://:{}".format(os.environ.get("PORT", "8000"))
domain = os.environ.get("RAILWAY_PUBLIC_DOMAIN", "").strip()
if domain:
    # Railway ends TLS at its edge; tell the hub its real public URL so cookies
    # are marked Secure and redirects use https.
    c.JupyterHub.public_url = "https://{}/".format(domain)
c.JupyterHub.hub_ip = "127.0.0.1"
c.ConfigurableHTTPProxy.pid_file = "/tmp/jupyterhub-proxy.pid"

# ---------------------------------------------------------------- state
c.JupyterHub.db_url = "sqlite:///" + os.path.join(HUB_DIR, "jupyterhub.sqlite")
c.JupyterHub.cookie_secret_file = os.path.join(HUB_DIR, "jupyterhub_cookie_secret")
c.JupyterHub.upgrade_db = True
c.JupyterHub.cleanup_servers = True
c.JupyterHub.admin_access = False
c.JupyterHub.authenticate_prometheus = True


# ---------------------------------------------------------------- auth
class RailwayAuthenticator(LocalAuthenticator, NativeAuthenticator):
    """NativeAuthenticator accounts backed by local UNIX users."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._bootstrap_admin()

    def _bootstrap_admin(self):
        if not ADMIN_PASSWORD:
            raise SystemExit("JUPYTERHUB_ADMIN_PASSWORD is not set")
        db = self.db
        info = UserInfo.find(db, ADMIN_USER)
        if info is None:
            info = UserInfo(
                username=ADMIN_USER,
                password=bcrypt.hashpw(ADMIN_PASSWORD.encode(), bcrypt.gensalt()),
                is_authorized=True,
            )
            db.add(info)
            self.log.info("Created admin account %r", ADMIN_USER)
        else:
            # The variable is the source of truth: changing it on Railway resets
            # the admin password on the next deploy.
            if not bcrypt.checkpw(ADMIN_PASSWORD.encode(), info.password):
                info.password = bcrypt.hashpw(ADMIN_PASSWORD.encode(), bcrypt.gensalt())
                self.log.info("Admin password for %r updated from JUPYTERHUB_ADMIN_PASSWORD", ADMIN_USER)
            info.is_authorized = True
        db.commit()


c.JupyterHub.authenticator_class = RailwayAuthenticator
c.Authenticator.admin_users = {ADMIN_USER}
c.Authenticator.allow_all = True  # NativeAuthenticator already requires admin approval
c.LocalAuthenticator.create_system_users = True
c.LocalAuthenticator.add_user_cmd = ["/usr/local/bin/jh-adduser"]
c.NativeAuthenticator.enable_signup = True
c.NativeAuthenticator.open_signup = False
c.NativeAuthenticator.minimum_password_length = 10
c.NativeAuthenticator.check_common_password = True
c.NativeAuthenticator.allowed_failed_logins = 5
c.NativeAuthenticator.seconds_before_next_try = 600
# Usernames become UNIX account names.
c.Authenticator.username_pattern = r"^[a-z][a-z0-9_-]{0,31}$"
c.JupyterHub.template_paths = [os.path.dirname(__import__("nativeauthenticator").__file__) + "/templates/"]

# ---------------------------------------------------------------- spawner
BOOT = uuid.uuid4().hex


class RailwaySpawner(LocalProcessSpawner):
    """LocalProcessSpawner that forgets process ids from an earlier container.

    After a restart or redeploy every user server is gone, but the database
    still holds their old pids, which a new process may now be using.
    """

    def get_state(self):
        state = super().get_state()
        if self.pid:
            state["boot"] = BOOT
        return state

    def load_state(self, state):
        if state.get("boot") != BOOT:
            state = {k: v for k, v in state.items() if k not in ("pid", "boot")}
        super().load_state(state)


c.JupyterHub.spawner_class = RailwaySpawner
c.Spawner.cmd = ["/usr/local/bin/jh-singleuser"]
c.Spawner.default_url = "/lab"
c.Spawner.notebook_dir = "~"
c.Spawner.start_timeout = 180
c.Spawner.http_timeout = 120
c.LocalProcessSpawner.shell_cmd = []
threads = str(CPUS)
c.Spawner.environment = {
    "PATH": "/srv/venv/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin",
    "LANG": "C.UTF-8",
    "SHELL": "/bin/bash",
    # Railway shows the host's CPUs inside a 1-2 vCPU service; keep numeric
    # libraries to the CPUs this service really has.
    "OMP_NUM_THREADS": threads,
    "OPENBLAS_NUM_THREADS": threads,
    "MKL_NUM_THREADS": threads,
    "NUMEXPR_MAX_THREADS": threads,
    "MALLOC_ARENA_MAX": "2",
    "PIP_NO_CACHE_DIR": "1",
}
# Idle servers and kernels stop on their own, so memory is freed without a
# separate culler process.
idle = os.environ.get("JUPYTERHUB_IDLE_TIMEOUT", "3600")
c.Spawner.args = [
    "--ServerApp.shutdown_no_activity_timeout=" + idle,
    "--MappingKernelManager.cull_idle_timeout=" + idle,
    "--MappingKernelManager.cull_interval=300",
    "--MappingKernelManager.cull_connected=False",
    "--TerminalManager.cull_inactive_timeout=" + idle,
    "--TerminalManager.cull_interval=300",
    "--LabApp.news_url=",
    "--LabApp.check_for_updates_class=jupyterlab.NeverCheckForUpdate",
    "--ServerApp.terminals_enabled=True",
]

# How many user servers may run at once: about 300 MB each after ~200 MB for
# the hub and proxy. 0.5 GB allows one, 1 GB three, 8 GB 26.
if MEM_MB:
    c.JupyterHub.active_server_limit = max(1, (MEM_MB - 200) // 300)
c.JupyterHub.concurrent_spawn_limit = max(2, CPUS * 2)
