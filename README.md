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

### Foundations curriculum (local development)

Foundations presents **seven programming topics** (I/O and arithmetic, conditions,
loops, functions, arrays, strings, matrices) followed by **three problem-solving
skills** (reasoning/correctness, complexity, implementation/testing/debugging).
These are display sections, not additional GROUP nodes. `queries` now belongs
to `range-queries`; correctness and finite-domain precomputation remain lessons
of algorithmic thinking and brute force respectively. The current catalog has
217 nodes: 27 groups and 190 topics.

For an existing original dev catalog, use the one-way transfer rather than
re-seeding or deleting learner data:

```sh
venv/bin/python manage.py restructure_foundations  # read-only plan
venv/bin/python manage.py restructure_foundations --apply --development --user admin
venv/bin/python manage.py seed_roadmap_theory       # verify canonical notes
```

Writes require local database, `DEBUG=True`, explicit development opt-in and an
authorized active staff author. The transfer retains renamed node IDs and
original lesson IDs/bodies/content revisions, so reading offsets and Q&A stay
attached to the same content. It redistributes practice links without replacing
problems, tests or submissions; parent progress counts unique problems. Old
lesson URLs whose topic changed must be reopened from the current topic; there
is no legacy-node alias. Practice guides keep their draft/publication status.
Fresh catalog/theory seeds use the new structure directly. Generic Polygon
`basic` maps to implementation; concrete skill tags map to their own topics.
This cutover command is restricted to dev, not a production deployment path.

Focused verification (Jinja response-context instrumentation needs debug mode):

```sh
venv/bin/python manage.py test mentor.tests_foundations_restructure \
  mentor.tests_roadmap_curriculum mentor.tests_polygon_tag_mapping \
  mentor.tests_roadmap_theory mentor.tests_roadmap_explorer \
  mentor.tests_roadmap_pages mentor.tests_roadmap_learning \
  mentor.tests_roadmap_api mentor.tests_lecture --keepdb --noinput --debug-mode
```

### Quản lý lộ trình học trong admin

Vào **Học tập & nội dung → Lộ trình học → Quản lý lộ trình**
(`/admin/mentor/roadmap/<id>/workspace/`). Chọn một nhóm/chuyên đề trong cây
để sửa thông tin, bài giảng, bài luyện, quan hệ **Nên học trước** và trạng thái
hiển thị. Cây có tìm kiếm; chọn nhóm cha để di chuyển, dùng **Lên / Xuống**
để sắp xếp. Thêm chuyên đề mặc định tạo bộ nội dung riêng ở trạng thái Bản nháp;
chỉ chọn dùng lại nội dung khi thực sự cần chia sẻ giữa nhiều vị trí.
Đổi thứ tự bài giảng chỉ đổi vị trí; không tăng revision nội dung, không làm
mất vị trí đọc hay hội thoại của học viên. Thao tác này dùng nút Lên / Xuống
trong chuyên đề thay vì sửa trường thứ tự ở form nâng cao.

Soạn mỗi bài giảng ở trang riêng. **Xem trước** cho staff đọc được bản nháp,
không xuất bản, ghi tiến độ đọc hay gọi AI. **Trang học viên** giữ nguyên điều
kiện truy cập thực tế. Các quyền xem/sửa/xóa và `mentor.publish_roadmap` vẫn
được kiểm tra tại endpoint; ẩn menu không thay thế phân quyền. Nội dung dùng
chung yêu cầu xác nhận ảnh hưởng. Gỡ bài luyện chỉ xóa liên kết chuyên đề,
không xóa đề bài, bài nộp hoặc AC. Dữ liệu tiến độ/hỏi đáp bài giảng chỉ được xem
trong nhóm **Theo dõi vận hành**.

#### Trang học chuyên đề

**Vào học chuyên đề** mở trực tiếp tài liệu gồm các bài giảng đã xuất bản,
theo thứ tự trong admin, với mục lục bên trái và bài tập ở cuối. Trên mobile,
mục lục thu gọn; nội dung dùng cuộn trang tự nhiên. Không còn tab Slide hay
trang trung gian chọn bài giảng. Tóm tắt mở theo từng chương; mô phỏng nằm
ngay trong nội dung. **Hỏi AI** là bot chat nổi ở góc trang, thu gọn/mở lại
được trong khi đọc. Lần mở đầu chọn chương đang đọc; sau đó ngữ cảnh chỉ đổi
khi chọn **Đang hỏi về** hoặc **Hỏi về chương đang đọc**, không tự đổi khi cuộn.
Bản nháp được giữ riêng từng chương khi chuyển hội thoại hoặc thu gọn trong
cùng trang. Có thể tiếp tục đọc khi chờ; câu trả lời quay về đúng hội thoại
đã gửi. Mobile mở chat dạng hộp thoại, hỗ trợ Escape và trả focus về nút mở.

Liên kết HTML bài giảng cũ chuyển đến `/learn/#rm-lesson-<id>` sau khi kiểm tra
quyền; API JSON bài giảng không đổi. Vị trí đọc và lịch sử hỏi đáp vẫn riêng
theo tài khoản, bài giảng và revision. **Đọc tiếp** chỉ cuộn khi được bấm;
đổi nội dung không khôi phục vị trí/hội thoại của revision cũ. Đọc lý thuyết
không tăng AC hoặc đánh dấu thành thạo. Khi JavaScript tắt, vẫn đọc được tài
liệu, tóm tắt, mục lục và liên kết bài tập; mô phỏng, hỏi AI và lưu vị trí đọc
cần JavaScript.

Bảy bài mở đầu (nhập/xuất, điều kiện, vòng lặp, hàm, mảng, xâu, bảng hai chiều)
trong `mentor/theory_notes.json` dùng cấu trúc: mục đích → ví dụ C++ hoàn chỉnh
→ input/output → lỗi thường gặp → thử thay dữ liệu. Nội dung MSOJ viết độc lập,
liên kết [W3Schools C++](https://www.w3schools.com/cpp/default.asp) làm tham khảo,
không nhập nguyên trang hay đưa các phần mở rộng vào ví dụ đầu tiên. Bài vòng
lặp nhúng mô phỏng ngay sau ví dụ. Chỉnh nội dung đang dùng phải qua admin hoặc
`save_content`, giữ ID và tăng revision; seeder hiện tại không ghi đè bài đã có.


#### Bài giảng tương tác

Trình biên soạn dùng tài liệu JSON `version: 2` trong fence `msoj-visual`.
**Xem trước nội dung chưa lưu** và trang học dùng chung bộ kiểm tra, compiler
và runtime. Có thể ghép bảng, biểu đồ, đồ thị, mảng, hàng đợi/ngăn xếp, ma trận,
biến/phạm vi, mã nguồn, công thức và sơ đồ trong lưới khai báo. Các điều khiển
và phép dẫn xuất dùng danh sách phép toán đóng; không thực thi JavaScript hoặc
mã nguồn do nội dung cung cấp. Mã C++/Python chỉ để đọc.

Compiler tin cậy tạo timeline cho vòng `for`, BFS, DFS đệ quy, DP chuỗi ma trận
và DP bitmask ghép đôi. `POST /roadmap/visual-compile/` nhận `{document, input}`,
trả `{document, frames}`, giữ CSRF và không ghi database. Giới hạn: 128 KiB/khối,
512 KiB cấu hình/bài, 12 khối/bài; 500 snapshot và 2 MiB snapshot/tài liệu.
Brainstorm chỉ công bố văn bản và tài liệu đã qua reviewer; payload đã duyệt
được lưu cùng câu trả lời. Không cho sửa đầu vào generator trong Brainstorm.

Runtime `MSOJVisuals.mountDocument(root, compiled, options)` trả controller
`next/previous/seek/play/pause/reset/getState/subscribe/destroy`. Thư viện biểu đồ,
đồ thị và validator được tự host; không dùng iframe/Vamonos hay runtime v1.
Khi JavaScript tắt, dữ liệu và mô tả tĩnh vẫn đọc được. Mô phỏng không tự đánh
dấu học viên đã hiểu bài và không gọi AI từ thao tác phát timeline.

Workspace trực quan ưu tiên hình/mã nguồn cạnh nhau, trạng thái ở các hàng dưới;
timeline nằm trên grid, JSON đầu vào mặc định thu gọn. Bật **Sắp xếp** để kéo
module sang ô khác hoặc chọn ô bằng danh sách (hỗ trợ bàn phím/mobile).
Ô đã có module sẽ đổi chỗ; ô trống nhận module. Bố cục giữ nguyên khi đổi bước,
phát/reset timeline hoặc tạo lại đầu vào, không thay đổi dữ liệu hay vùng chọn.
**Bố cục mặc định** phục hồi cách sắp xếp học tập; **Bố cục bài soạn** dùng
`layout.areas` gốc. Thay đổi chỉ tồn tại trong phiên mount, không tự lưu bài hay
payload Brainstorm. Trên màn hình hẹp, các ô chuyển thành một cột theo thứ tự grid.

Kiểm chứng grid: 32 focused tests; compile 6 mẫu và 5 generator; browser chạy
kéo thả, chuyển bằng bàn phím, đổi chỗ/ô trống, giữ state/canvas, recompile sau
khi chuyển ô, desktop/mobile light/dark và destroy controller.

```sh
npm ci --ignore-scripts
npm run build:visuals
venv/bin/python manage.py seed_interactive_lessons
venv/bin/python manage.py seed_interactive_lessons --apply --development --user <staff>
```

Seed tạo nội dung DRAFT và không ghi đè bài đã sửa. Nội dung v1 phải chuyển đổi
tường minh; runtime không tự nhận cấu hình cũ. Với từng lesson ID đã kiểm tra:

```sh
venv/bin/python manage.py migrate_visual_documents --lesson <id> --backup /private/path/visual-backup.json
venv/bin/python manage.py migrate_visual_documents --lesson <id> --backup /private/path/visual-backup.json --apply --development --user <staff>
```

Apply chỉ nhận database local, `DEBUG=True`, opt-in development và staff đủ quyền;
snapshot phải khớp nội dung/revision/trạng thái hiện tại. Chuyển đổi giữ prose,
ID và trạng thái xuất bản. Hướng dẫn biên soạn: [mô phỏng](docs/lesson-simulations.md).

Kiểm chứng cutover: 80 focused Django tests, 687 tình huống đối chiếu thuật toán,
build vendor assets và kiểm tra hash dependency lock đã qua. Browser đã chạy
author/preview, learner recompile/timeline, liên kết prefix/scene/chart, lifecycle,
và Brainstorm gateway → reviewer → lịch sử ở light/mobile dark. Chưa build image
Docker đầy đủ; test migration tạo database riêng cần quyền CREATE DATABASE.
Migration storage mới: `mentor.0014_brainstormmessage_approved_visuals`.



Database là nguồn runtime duy nhất cho `RoadmapNode.summary`,
`RoadmapNode.display_section` và `RoadmapPrerequisite.reason`/quan hệ học trước,
kể cả lộ trình Competitive Programming. Migration `mentor.0011` chứa snapshot
metadata/prerequisite hiện có; giữ nguyên ID, nội dung bài giảng và trạng thái
học. Manifest chỉ phục vụ khởi tạo/provenance. Seed gán metadata và quan hệ cho
node mới, không ghi đè chỉnh sửa database của node đã tồn tại. Prerequisite là
gợi ý thứ tự học, không khóa chuyên đề; không cho phép vòng phụ thuộc.

Lệnh seed có thể từ chối khi cấu trúc quản trị đã khác catalog; đó là bảo vệ
nội dung, không phải yêu cầu sửa database trở lại theo manifest. Không chạy
lại lệnh chuyển cấu trúc một lần để quản lý nội dung thường ngày.

```sh
venv/bin/python manage.py migrate mentor
venv/bin/python manage.py test mentor.tests_roadmap_workspace \
    mentor.tests_roadmap_staff_preview mentor.tests_roadmap_admin \
    mentor.tests_roadmap_explorer mentor.tests_roadmap_curriculum \
    mentor.tests_roadmap_pages mentor.tests_roadmap_api --keepdb --noinput --debug-mode
```


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
case-insensitively. Defaults exclude only owners `dang` and `longvu1305`; no tags
exclude problems. Tags such as `yb-boclot` and `cyb-boclot`, and other owners,
remain eligible. Excluded owners are rejected before tag or package requests.
The download API rechecks live owner/tag metadata before opening a payload stream
or temporary ZIP. Missing source metadata
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
