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

### MSOJ beginner problem pack

The original Vietnamese pack in `judge/fixtures/beginner/` contains 45 exercises:
five each for arithmetic/I/O, conditions, loops, digits, arrays, frequency tables,
strings, matrices and elementary number theory. Function practice reuses four
exercises; it does not duplicate statements or claim output grading enforces functions.
Each authored exercise is worth 100 points, with partial scoring disabled.
The catalog also selects 11 existing exercises without changing their statements,
test data or publication status. No skipped Polygon sources are included.

```sh
# Read-only inventory; export creates a private authoring directory, not DB rows.
venv/bin/python manage.py seed_beginner_problems --export /private/beginner-pack
# Upload only this authored pack, with algorithm/skill tags, to Polygon.
venv/bin/python manage.py seed_beginner_problems --upload --user admin \
  --report /private/beginner-pack/polygon-report.json
# Confirm every selected ID has a current-revision linux/READY full package.
venv/bin/python manage.py build_polygon_packages POLYGON_IDS
# Import ready packages, retain skill-tag mappings, and attach roadmap practice.
venv/bin/python manage.py seed_beginner_problems --apply --user admin
```

The upload needs the existing Polygon API environment credentials and Pandoc.
It creates only `msb-*` problems; resuming requires the pack's Polygon note marker
and matching test inputs. Source/test collisions stop rather than overwrite other
work. Mutating requests are not retried automatically. Keep the report: after an
interrupted request, inspect the marked problem before resuming. Large manual
tests use a 120-second connection/write timeout; a timeout still stops the upload
without replaying the mutation. All imported exercises/editorials remain private;
the ten practice guides are drafts. Staff
must review and publish explicitly. `--apply` also requires the existing CP roadmap
and its learning topics. On a server, use this command rather than plain
`sync_polygon` when fine-grained skill tags and roadmap placements are needed.
Import refuses uncommitted sources and packages older than the current Polygon
revision. A newer revision may replace a previously imported pack exercise only
when its local statement and editorial still match the authored catalog; edited
local content stops the import for review. Whitespace-sensitive test lines use a
small Polygon generator, so blank lines and leading/trailing spaces are retained.
Re-running `--apply` after a catalog expansion appends missing exercise links to
existing draft practice guides without replacing authored text. Published guides
requiring new links stop for explicit editorial review instead.

Reference C++17 solutions, independent Python answer oracles, strict testlib
validators, deterministic input cases, Markdown statements and editorials are
kept together. Export includes sources, test archives and checksum metadata.
These fixtures do not call Polygon or modify runtime data merely by importing.

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
case-insensitively. Defaults exclude tags `yb-boclot` and `cyb-boclot` and owners `dang`,
`longvu1305`, `mmirzayanov` and `geranazavr555`. Excluded owners are rejected before tag or package
requests. Excluded tags are rejected before package downloads, and the download API rechecks
live owner/tag metadata before opening a payload stream or temporary ZIP. Missing source metadata
fails closed. Force sync cannot bypass these rules. Excluded sources remain only in the tracking
index with a skip reason and cannot win duplicate-code selection. Previously imported problems
require an explicit, backed-up hard-delete cleanup of their database rows and test directories;
changing the policy alone does not delete them. Manual ZIP uploads remain a separate local-file flow.
Restart Celery workers after changing sync settings; the next refresh/sync reclassifies the index.

Build missing full packages before importing (uses the same environment API
credentials as sync; requires WRITE/OWNER access on Polygon):

```sh
# Preview the eligible problems without starting builds.
venv/bin/python manage.py build_polygon_packages --dry-run
# Build sequentially, verify solutions, and wait for each linux/READY package.
venv/bin/python manage.py build_polygon_packages
# Optional: process selected eligible Polygon names/IDs.
venv/bin/python manage.py build_polygon_packages 450077 hhy-cluster
# Import separately once packages are ready.
venv/bin/python manage.py sync_polygon
```

`build_polygon_packages` reads live tags and always enforces sync owner/tag exclusions;
there is no excluded-source override. It skips current-revision linux/READY packages and
waits for an existing PENDING/RUNNING build rather than starting another. Polling defaults
to 15 seconds and a 1,800-second wait limit per problem (`--poll-interval`, `--timeout`).
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
