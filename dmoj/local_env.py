import os


def load_local_ai_key(path):
    """Load one local-only secret without overriding the process environment."""
    try:
        with open(path, encoding='utf-8') as env_file:
            for line in env_file:
                line = line.strip()
                if not line or line.startswith('#') or '=' not in line:
                    continue
                key, value = line.split('=', 1)
                value = value.strip()
                if key.strip() == 'AI_9ROUTER_API_KEY' and value and value != '<PLACEHOLDER>':
                    os.environ.setdefault('AI_9ROUTER_API_KEY', value)
    except FileNotFoundError:
        pass
