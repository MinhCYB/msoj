# VNOJ: VNOI Online Judge [![Build Status](https://github.com/VNOI-Admin/OJ/workflows/build/badge.svg)](https://github.com/VNOI-Admin/OJ/actions/) [![AGPL License](https://img.shields.io/badge/license-AGPLv3.0-blue.svg)](http://www.gnu.org/licenses/agpl-3.0) [![Discord link](https://img.shields.io/discord/660930260405190688?color=%237289DA&label=Discord&logo=Discord)](https://discord.com/invite/TDyYVyd)

As a fork of [DMOJ](https://github.com/DMOJ/online-judge), VNOJ serves as [VNOI](https://team.vnoi.info/)'s official online judge and hosts its programming contests.

See it live at [oj.vnoi.info](https://oj.vnoi.info/)!

## Features

Check out its features [here](https://github.com/DMOJ/online-judge#features).

## Installation

Refer to the install documentation [here](https://vnoi-admin.github.io/vnoj-docs/#/site/installation). Almost all installation steps remain the same as the docs, but there are several minor differences, including cloning this repo instead of DMOJ's repo.

### Docker Compose (MSOJ)

Installation and configuration: [Docker installation guide (Vietnamese)](docs/docker-installation.md).
Operational reference: [Docker runbook](docker/README.md).
The stack keeps the judge on the host, bind-mounts database/media/problem data
outside the repository, supports realtime events and optional Cloudflare Tunnel,
and deploys prebuilt GHCR images without building on the production server.
Use the isolated local setup in the runbook before connecting a production judge.

### Additional installation steps

- You **have to** define `DMOJ_PROBLEM_DATA_ROOT` in `local_settings.py`, which should be the path to the directory that contains your problems' tests.

- Regarding disabling full-text search, please read [this issue](https://github.com/VNOI-Admin/OJ/issues/4) for more information.

- To sync the judge server and the site's cache, change the cache framework (`CACHES`) to `memcached` or `redis` instead of the default (local-memory caching).

- If you use `python3 manage.py loaddata demo`, the home button in the admin dashboard (/admin) links you to `localhost:8081`, there are 2 ways to change that:

  1. You can change that in [demo.json](/judge/fixtures/demo.json)
  2. You can go to the admin page, scroll down to find the `Sites` setting and change `localhost:8081` to your domain.

- Custom Polygon checkers/interactors require [testlib.h](https://github.com/MikeMirzayanov/testlib/blob/master/testlib.h) on the **judge host**, not only on the Django host. Install the header in a GCC include directory, or configure a dedicated directory as below. `PATH` locates executables; it does not locate C++ headers.

### Codeforces Polygon imports

Detailed Vietnamese operations guide: [Polygon build and sync](docs/polygon-operations.md).

Automatic synchronisation (`manage.py sync_polygon` and the Polygon admin sync
actions) skips problems matching `POLYGON_SKIP_TAGS` or `POLYGON_SKIP_OWNERS`,
case-insensitively. Defaults exclude tag `yb-boclot` and owners `dang`,
`longvu1305`, `mmirzayanov` and `geranazavr555`. Force sync does not override these rules. Excluded problems remain
in the Polygon tracking table with a skip reason and cannot win duplicate-code
selection. Previously imported MSOJ problems are not deleted or hidden by a new
exclusion rule. Manual ZIP imports are separate from automatic synchronisation.
Restart Celery workers after changing sync settings; the next refresh/sync
reclassifies the stored Polygon index.

Build missing full packages before importing (uses the same environment API
credentials as sync; requires WRITE/OWNER access on Polygon):

```sh
# Preview the eligible problems without starting builds.
venv/bin/python manage.py build_polygon_packages --dry-run
# Build sequentially, verify solutions, and wait for each linux/READY package.
venv/bin/python manage.py build_polygon_packages
# Optional: process selected Polygon names/IDs, or include ALL excluded problems.
venv/bin/python manage.py build_polygon_packages 450077 hhy-cluster
venv/bin/python manage.py build_polygon_packages --include-excluded
# Import separately once packages are ready.
venv/bin/python manage.py sync_polygon
```

`build_polygon_packages` reads live tags, respects sync owner/tag exclusions by
default, skips current-revision linux/READY packages, and waits for an existing
PENDING/RUNNING build rather than starting another. `--include-excluded` overrides
only the builder's exclusions, not the sync policy. Polling defaults to 15 seconds
and a 1,800-second wait limit per problem (`--poll-interval`, `--timeout`).
It does not import, delete, update local database records, or commit Polygon
working copies. Commit/review uncommitted changes in Polygon first. Failures are
reported per problem, remaining problems are processed, and the command exits
nonzero if any failed. A timeout/lost response can leave a remote build running;
inspect Polygon before rerunning. Build-start requests are not automatically
retried. Do not run this command alongside other Polygon sync/build processes
using the same API key. Full/verified builds can take substantial remote compute.
API contract: https://codeforces.github.io/polygon-misc/API#problembuildpackage

Polygon imports require the **Pandoc CLI >= 3.0.0** to convert LaTeX statements
and tutorials to Markdown. This is a system dependency: `pip install -r
requirements.txt` does not install it, and the Python package named `pandoc` is
not a substitute. Install it in the same host/container that runs Django, not
only on the judge host.

On Debian/Ubuntu with a sufficiently recent package:

```sh
sudo apt-get update
sudo apt-get install pandoc
pandoc --version
```

If the distribution provides Pandoc 2.x or root access is unavailable, use an
[official standalone release](https://pandoc.org/installing.html#linux).
For example, a rootless Linux x86-64 installation:

```sh
curl -fL -o /tmp/pandoc-3.1.11.1-linux-amd64.tar.gz \
  https://github.com/jgm/pandoc/releases/download/3.1.11.1/pandoc-3.1.11.1-linux-amd64.tar.gz
mkdir -p "$HOME/.local"
tar -xzf /tmp/pandoc-3.1.11.1-linux-amd64.tar.gz --strip-components=1 -C "$HOME/.local"
export PATH="$HOME/.local/bin:$PATH"
pandoc --version
```

The Django service account must be able to execute `pandoc` from its own `PATH`.
Configure that PATH in the service/container environment; changing an interactive
shell alone does not change an existing service environment. Restart the web
service if its PATH configuration changes. No TeX/PDF engine is needed for this
LaTeX-to-Markdown conversion.

### Testlib on the judge host

For a rootless installation, place `testlib.h` in a dedicated Linux directory
such as `/home/judge/.local/include/testlib/`. Configure the judge YAML using
the actual absolute path (do not use `~`):

```yaml
runtime:
  # Merge with existing compiler/runtime entries; do not replace them.
  gcc_compile:
    PATH: /usr/bin:/bin
    CPLUS_INCLUDE_PATH: /home/judge/.local/include/testlib
extra_fs:
  CPP03: &testlib_access
    - recursive_dir: /home/judge/.local/include/testlib
  CPP11: *testlib_access
  CPP14: *testlib_access
  CPP17: *testlib_access
  CPP20: *testlib_access
  CPP23: *testlib_access
  CPPTHEMIS: *testlib_access
  CPPICPC: *testlib_access
  OBJC: *testlib_access
```

Merge existing `gcc_compile` environment variables and `extra_fs` rules rather
than discarding them. Adjust the compiler PATH if your toolchain is elsewhere.
The sandbox needs read access to the dedicated include directory, including
probes for headers that do not exist there; allowing only `testlib.h` is not
sufficient. Do not grant access to an entire home directory or Windows drive.
Restart the judge, verify C/C++ executor self-tests, then rejudge affected
submissions. A checker compilation failure is an internal error (IE), not a
compilation error in the contestant's solution.

## Contributing ![PR's Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg?style=flat)

Take a look at [our contribution guideline](contributing.md).

If you find any bug, please feel free to contact us via Discord [![Discord Chat](https://img.shields.io/discord/660930260405190688?color=%237289DA&label=Discord&logo=Discord)](https://discord.gg/TDyYVyd) or open an issue.

Pull requests are welcome as well. Before you submit your PR, please check your code with [flake8](https://flake8.pycqa.org/en/latest/) and format it if needed. There's also `prettier` if you need to format JS code (in `websocket/`).

Translation contributions are also welcome.
