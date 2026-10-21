import os

# Secrets that may be loaded from the local, git-ignored .env file. Production supplies them
# through the process environment instead.
LOCAL_ENV_KEYS = frozenset({'AI_9ROUTER_API_KEY', 'POLYGON_API_KEY', 'POLYGON_API_SECRET'})


def load_local_env(path):
    """Load allowlisted local-only secrets without overriding the process environment."""
    try:
        with open(path, encoding='utf-8') as env_file:
            for line in env_file:
                line = line.strip()
                if not line or line.startswith('#') or '=' not in line:
                    continue
                key, value = line.split('=', 1)
                key, value = key.strip(), value.strip()
                if key in LOCAL_ENV_KEYS and value and value != '<PLACEHOLDER>':
                    os.environ.setdefault(key, value)
    except FileNotFoundError:
        pass
