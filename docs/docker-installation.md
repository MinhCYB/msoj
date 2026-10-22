# Cài đặt và vận hành MSOJ bằng Docker Compose

Tài liệu này hướng dẫn chạy MSOJ trên máy cá nhân để kiểm thử, sau đó triển khai lên server khi đã sẵn sàng. Stack Docker dùng database và thư mục dữ liệu riêng; không tự nhập dữ liệu từ MSOJ đang chạy trên host.

> Lệnh dưới đây chạy từ thư mục gốc repository. Không đưa `.env.docker`, API key, tunnel token, judge key hay output môi trường vào Git/chat/log công khai.

## 1. Thành phần và yêu cầu

Stack Compose gồm Django/uWSGI, MariaDB, Redis broker, Redis cache, Celery worker/beat, event daemon, nginx và bridge cho judge. Judge chạy riêng trên host. Cloudflare Tunnel là tùy chọn, không cần cho kiểm thử local.

Yêu cầu:

- Linux hoặc WSL2 dùng filesystem Linux, Docker Engine và Docker Compose plugin **2.24 trở lên**.
- Git checkout đầy đủ; với local build cần kết nối tới registry package Python, GitHub và npm.
- Với judge: môi trường DMOJ judge host, executor và `testlib.h` cần thiết cho checker/interactor. Các phần này không chạy trong container MSOJ.
- Production: một server có dung lượng cho database, media, problem data và backup; DNS/domain và HTTPS nếu cần truy cập công khai.

Kiểm tra Docker:

```sh
docker version
docker compose version
```

Dùng đường dẫn trên filesystem Linux, ví dụ `/home/<user>/...` hoặc `/srv/msoj`; tránh đặt database trong `/mnt/c` trên WSL và không dùng chung datadir với MariaDB host.

Các image nền được pin bằng digest; nhánh Pandoc có checksum cho amd64/arm64. Quy trình build và smoke hiện đã được chạy trên Linux amd64. Không coi arm64 là đã kiểm chứng chỉ vì image nền hỗ trợ kiến trúc đó.

## 2. Chạy thử local

### 2.1 Tạo môi trường và dữ liệu riêng

Ví dụ tạo project `msoj-dev`, web ở `http://localhost:18080`, bridge ở `127.0.0.1:19999`:

```sh
python3 docker/setup.py \
  --env-file .env.docker \
  --data-root ../msoj_docker_data \
  --project msoj-dev \
  --http-port 18080 \
  --bridge-port 19999 \
  --site-url http://localhost:18080
```

Lệnh tạo `.env.docker` với quyền `0600`, sinh secret mới và tạo các thư mục bind mount rỗng bên ngoài repository. Nó từ chối ghi đè env đã có hoặc tái sử dụng thư mục chứa dữ liệu. Giữ nguyên `DJANGO_SECRET_KEY`; đổi key có thể làm mất hiệu lực session/chữ ký và ảnh hưởng dữ liệu được mã hóa.

Nếu máy đã có `.env.docker` và dữ liệu từ lần cài trước, **không chạy lại setup**. Dùng `docker compose --env-file .env.docker up -d --wait` để khởi động lại. Không chép `docker/env.example` đè lên env đã sinh; đó chỉ là danh sách biến tham khảo.

Thư mục dữ liệu mặc định gồm:

| Host | Container | Nội dung |
| --- | --- | --- |
| `../msoj_docker_data/database` | `/var/lib/mysql` | MariaDB |
| `../msoj_docker_data/redis` | `/data` | Redis broker bền vững |
| `../msoj_docker_data/media` | `/data/media` | Ảnh, statement và file media |
| `../msoj_docker_data/problems` | `/data/problems` | Test data/problem packages; judge host đọc cùng đường dẫn host |
| `../msoj_docker_data/backups` | không mount | Database backup gzip |

Có thể chọn data root khác, nhưng phải ở ngoài repository và dành riêng cho MSOJ. Không xóa các thư mục này để xử lý lỗi container; `docker compose down` không xóa bind mount.

### 2.2 Build và khởi tạo

```sh
docker compose --env-file .env.docker \
  -f compose.yaml -f compose.build.yaml build

docker compose --env-file .env.docker up -d --wait db redis cache events
docker compose --env-file .env.docker run --rm migrate
python3 docker/ops.py --env-file .env.docker bootstrap
docker compose --env-file .env.docker run --rm web python manage.py createsuperuser
python3 docker/ops.py --env-file .env.docker bootstrap
docker compose --env-file .env.docker up -d --wait
```

Bootstrap nạp ngôn ngữ/navbar nếu bảng tương ứng còn trống, cập nhật Site từ `MSOJ_SITE_URL` và bảo đảm tài khoản admin có Profile. Không nạp dữ liệu demo hoặc database host. Mở `http://localhost:18080` và đăng nhập bằng admin vừa tạo.

Staff mặc định phải bật 2FA. Với kiểm thử local, có thể đặt hai dòng sau trong `.env.docker` trước bước khởi động app; bật lại 2FA trước khi public:

```dotenv
MSOJ_REQUIRE_STAFF_2FA=false
MSOJ_CLOUDFLARE_UPLOAD_WARNING=false
```

Dòng thứ hai chỉ ẩn cảnh báo Cloudflare khi không dùng tunnel, không đổi giới hạn request của nginx.

### 2.3 Kiểm tra và thao tác cơ bản

```sh
docker compose --env-file .env.docker ps
docker compose --env-file .env.docker logs --tail=100 web
docker compose --env-file .env.docker logs --tail=100 worker

docker compose --env-file .env.docker stop
docker compose --env-file .env.docker start
docker compose --env-file .env.docker down
```

`down` chỉ dừng/xóa container và network của project; dữ liệu bind mount còn nguyên. Không dùng `down -v`, không xóa data root nếu còn cần dữ liệu. Trên máy đang chạy project dev, tránh dùng trùng port `18080`/`19999` hoặc subnet tunnel `172.30.42.0/29` với CI/Compose project khác.

## 3. Cấu hình ứng dụng

`docker/setup.py` tạo file env ban đầu. Có thể chỉnh `.env.docker` bằng editor cục bộ; không commit, gửi hoặc in nội dung file. Các biến quan trọng:

| Biến | Ý nghĩa |
| --- | --- |
| `MSOJ_SITE_URL` | Origin chuẩn của site; local ví dụ `http://localhost:18080`, production dùng URL HTTPS thật |
| `DJANGO_ALLOWED_HOSTS` | Hostname được Django chấp nhận, phân tách bằng dấu phẩy |
| `MSOJ_HTTP_PORT` | Cổng host chỉ bind trên `127.0.0.1`; mặc định local theo lệnh setup là `18080` |
| `MSOJ_BRIDGE_PORT` | Cổng bridge bind trên `127.0.0.1`; local `19999`, production mặc định `9999` |
| `MSOJ_DB_DIR`, `MSOJ_REDIS_DIR`, `MSOJ_MEDIA_DIR`, `MSOJ_PROBLEM_DIR`, `MSOJ_BACKUP_DIR` | Đường dẫn host cho dữ liệu; phải ngoài repository và không dùng chung tùy tiện |
| `APP_UID`, `APP_GID` | UID/GID mà app container chạy dưới đó; setup lấy UID/GID hiện tại |
| `DJANGO_SECRET_KEY`, `MARIADB_PASSWORD`, `MARIADB_ROOT_PASSWORD` | Secret được setup sinh tự động; giữ bí mật và ổn định |
| `DJANGO_EMAIL_BACKEND`, `EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`, `EMAIL_USE_TLS`, `DEFAULT_FROM_EMAIL` | SMTP; mặc định local gửi email vào console, cần cấu hình SMTP trước khi mở production |
| `POLYGON_SYNC_AUTHOR` | Username MSOJ có Profile, dùng làm tác giả khi import Polygon; mặc định `admin` |
| `POLYGON_API_KEY`, `POLYGON_API_SECRET` | Thông tin Polygon, chỉ lưu ở server/env; không đưa vào Git/client |
| `AI_9ROUTER_API_KEY` | API key phía server cho AI Gateway; cấu hình route/model còn cần thực hiện trong admin/DB |
| `MSOJ_REQUIRE_STAFF_2FA` | Mặc định bật yêu cầu 2FA với staff; chỉ cân nhắc tắt cho kiểm thử local |
| `CLOUDFLARE_TUNNEL_TOKEN` | Chỉ cần khi bật named Cloudflare Tunnel |
| `MSOJ_APP_IMAGE`, `MSOJ_PROXY_IMAGE`, `MSOJ_EVENTS_IMAGE` | Local mặc định là `msoj-app:local`, `msoj-proxy:local`, `msoj-events:local`; production chọn ba image cùng commit SHA hoặc digest từ GHCR |
| `MSOJ_CLOUDFLARE_UPLOAD_WARNING` | Bật/tắt cảnh báo giới hạn Cloudflare ở trang upload; không bật/tắt service tunnel |

Luật Polygon hiện được đặt trong `dmoj/settings.py`: owner `dang`, `longvu1305`, `mmirzayanov`, `geranazavr555` và tag `yb-boclot` bị chặn tự động, không phân biệt hoa thường. Đổi luật trong source cần build image app mới và recreate web/worker/beat. Thay API key hoặc các biến môi trường không đổi code thì recreate các service liên quan, không cần build lại.

Không chia sẻ `docker compose config` không có `-q`, `docker inspect` env hoặc log có reset link/credential. Các lệnh này có thể để lộ secret.

### Áp dụng thay đổi cấu hình

Container không hot-reload source hoặc env của host. `restart` chỉ khởi động lại container cũ, không nạp giá trị env mới.

- Đổi API key, SMTP hoặc cờ local: sửa `.env.docker`, rồi recreate service dùng giá trị đó. Với web/Celery:

```sh
docker compose --env-file .env.docker up -d --no-deps --force-recreate web worker beat
```

- Đổi `MSOJ_SITE_URL`/hostname: cập nhật cả `DJANGO_ALLOWED_HOSTS`, recreate web/worker/beat, rồi chạy lại `python3 docker/ops.py --env-file .env.docker bootstrap` để cập nhật bảng Site. Nếu còn dùng HTTP local, không đặt URL HTTPS vì secure cookie sẽ không được gửi qua HTTP.
- Đổi source, luật Polygon hoặc static: build lại bằng hai file Compose như mục 2.2, rồi chạy `docker compose --env-file .env.docker up -d --wait`. Lệnh này có thể recreate cả bridge; tránh chạy khi đang chấm bài.
- `APP_UID`/`APP_GID` phải có quyền ghi media/problems, judge host phải có quyền đọc. DB/Redis quản lý owner riêng; không `chmod 777`, không chown toàn data root theo UID app.
- Đổi biến mật khẩu MariaDB trong env **không** tự đổi mật khẩu user của database đã khởi tạo. Phải đổi credential trong DB có kế hoạch và cập nhật các service tương ứng; không chạy lại setup để đổi secret.

## 4. Kết nối judge host

Judge giữ trên host, không cần privileged container. Tạo judge riêng trên trang admin MSOJ với name/key riêng; không dùng danh tính của judge đang phục vụ hệ thống khác. Trong file YAML riêng có quyền `0600`, giữ cấu hình runtime của judge host và thay identity/storage tương ứng. Đoạn sau là phần cấu hình cần thêm hoặc cập nhật; thay các giá trị minh họa bằng thông tin thật trên máy của bạn:

```yaml
id: msoj-local
key: 'REPLACE_WITH_JUDGE_KEY_FROM_ADMIN'
problem_storage_globs:
  - id: local
    glob: /home/your-user/msoj_docker_data/problems/**
```

Host và port truyền qua CLI, không lấy từ hai khóa `host`/`port` trong YAML:

```sh
dmoj -c /path/to/msoj-local.yml -p 19999 127.0.0.1
```

Chạy trong môi trường judge đã cài sẵn. Dùng port được đặt trong `MSOJ_BRIDGE_PORT`. Container Django/worker thấy test data ở `/data/problems`; judge host phải dùng đường dẫn host tương ứng, không dùng đường dẫn container. Giữ nguyên runtime/executor và `testlib.h` hiện có. Không truyền judge key trong command line hoặc chia sẻ file YAML đã điền key.

Bridge chỉ bind vào loopback. Không public bridge qua Internet/Cloudflare. Khi restart bridge, judge reconnect nhưng submission đang chấm có thể kết thúc `IE`; khi deploy, lên lịch maintenance và chờ hết lượt chấm. Không scale bridge, beat hoặc events thành nhiều replica.

## 5. Polygon, AI và giới hạn upload

Sau khi đặt Polygon key và author, recreate web/worker/beat nếu cần nạp biến môi trường. Xem trước danh mục (lệnh này refresh và ghi tracking index, không phải dry-run chỉ đọc):

```sh
docker compose --env-file .env.docker exec web python manage.py sync_polygon --list
```

Sync một ID/name đã chọn:

```sh
docker compose --env-file .env.docker exec web python manage.py sync_polygon POLYGON_ID
```

`--force` không vượt luật skip. `--list` có ghi database index; sync thật ghi DB và problem storage. Không chạy đồng thời builder, CLI sync và admin sync trên cùng Polygon API key. Full package build là bước riêng, cần quyền Polygon phù hợp.

AI Gateway cần API key trong env và ProviderConnection/ModelRoute đã cấu hình trong admin/DB. Không chép prompt nội bộ, private editorial hoặc provider credential sang Git/client.

Upload ZIP thủ công và sửa testcase vẫn có. Nginx giới hạn request 100 MiB; Cloudflare Free có giới hạn toàn request khoảng 100 MB, tính cả multipart, và có thể từ chối trước nginx. Package lớn nên import bằng Polygon sync nếu có thể.

## 6. Truy cập từ xa và Cloudflare

### Chỉ truy cập riêng khi chưa có domain

Local dùng `http://localhost:18080`. Nếu stack chạy trên VPS và chỉ cần quản trị riêng, có thể dùng SSH tunnel từ máy cá nhân:

```sh
ssh -N -L 18080:127.0.0.1:18080 user@server-ip
```

Sau khi SSH kết nối, mở `http://localhost:18080` trên máy cá nhân. Không mở cổng web hoặc bridge ra Internet chỉ để kiểm thử. Quick Tunnel là một lựa chọn tạm thời nhưng chưa được cấu hình/kiểm thử trong bộ Compose này.

### Named Cloudflare Tunnel khi đã có domain

Service `cloudflared` đã có sẵn nhưng chỉ chạy khi bật profile `cloudflare`; không bắt buộc cho local. Khi deploy:

1. Tạo named tunnel trong Cloudflare và lấy token.
2. Đặt `CLOUDFLARE_TUNNEL_TOKEN` trong env server, giữ kín.
3. Đổi `MSOJ_SITE_URL` thành `https://<domain>` và thêm hostname đó vào `DJANGO_ALLOWED_HOSTS`.
4. Trong Public Hostname của tunnel, đặt service origin là `http://proxy-tunnel:8081`.
5. Recreate app để nạp URL/hostname mới, cập nhật bảng Site rồi bật tunnel:

```sh
docker compose --env-file .env.docker up -d --no-deps --force-recreate web worker beat
python3 docker/ops.py --env-file .env.docker bootstrap
docker compose --env-file .env.docker --profile cloudflare up -d cloudflared
```

Cloudflared chỉ tạo kết nối outbound; cổng 8081 không được public. Nginx chỉ tin forwarding headers từ peer tunnel trên network riêng; listener local port 80 không tin header HTTPS do client tự gửi. Realtime dùng WebSocket `wss://<domain>/event/` và long-poll `/channels/`. Không cache HTML, đăng nhập, API, `/channels/` hoặc `/event/`.

Hiện tại bạn chỉ kiểm thử local: để service Cloudflare tắt, không cần domain/token và không cần sửa origin dashboard.

## 7. Triển khai production từ image GHCR

`compose.yaml` production chỉ dùng image; `compose.build.yaml` dành cho workstation/CI. Workflow `.github/workflows/docker.yml` chạy thủ công (`workflow_dispatch`), build/kiểm thử app, proxy, events rồi mặc định publish package riêng tư lên GHCR với tag commit SHA. Kiểm tra package visibility/quyền đọc trước khi deploy. Không dùng tag `latest`.

Trên server:

1. Checkout đúng release/commit có `compose.yaml` và `docker/ops.py`; cài Docker Compose plugin >= 2.24.
2. Chọn data root riêng (ví dụ `/srv/msoj`), tạo env bằng `docker/setup.py` với URL domain cuối cùng nếu public. Dùng HTTP loopback trước khi có HTTPS/domain.
3. Cấu hình SMTP, secrets, `DJANGO_ALLOWED_HOSTS`, domain và các image tag SHA tương ứng. Thay `owner/repo` bằng namespace GHCR thực. Các app/proxy/events phải cùng release.

   Ví dụ các dòng chọn image trong env (thay `owner/repo` và `COMMIT_SHA` bằng giá trị thật; SHA phải đầy đủ 40 ký tự):

   ```dotenv
   MSOJ_APP_IMAGE=ghcr.io/owner/repo/app:COMMIT_SHA
   MSOJ_PROXY_IMAGE=ghcr.io/owner/repo/proxy:COMMIT_SHA
   MSOJ_EVENTS_IMAGE=ghcr.io/owner/repo/events:COMMIT_SHA
   ```
4. Đăng nhập GHCR bằng PAT có quyền `read:packages`, truyền token qua stdin; không đưa token vào command-line history.
5. Khởi tạo infra, migrate, bootstrap, tạo superuser, bootstrap lại, rồi bật app:

```sh
docker compose --env-file .env.docker pull
docker compose --env-file .env.docker up -d --wait db redis cache events
docker compose --env-file .env.docker run --rm migrate
python3 docker/ops.py --env-file .env.docker bootstrap
docker compose --env-file .env.docker run --rm web python manage.py createsuperuser
python3 docker/ops.py --env-file .env.docker bootstrap
docker compose --env-file .env.docker up -d --wait
```

Không build image trên production server. Listener web chỉ publish `127.0.0.1`; dùng Cloudflare Tunnel hoặc reverse proxy HTTPS đã được cấu hình đúng để public.

### Nâng cấp release

Xác nhận backup và maintenance window trước deploy. Lệnh này chủ động restart bridge; submission đang chạy có thể thành `IE`:

```sh
python3 docker/ops.py --env-file .env.docker deploy --allow-bridge-restart
```

Tool kiểm tra image có tag release/SHA hoặc digest, pull trước, dừng writers, tạo DB backup, chạy migration rồi khởi động lại. Events được cập nhật trước khi dừng writers và mất buffer RAM khi restart, nên maintenance phải bắt đầu trước lệnh deploy. Không tự rollback DB nếu migration lỗi; cần xử lý theo backup/migration compatibility. Không deploy trong contest hoặc lúc Polygon import đang ghi dữ liệu.

## 8. Backup, restore và chuyển dữ liệu

Tạo database dump gzip nhất quán:

```sh
python3 docker/ops.py --env-file .env.docker backup
```

DB dump **không** bao gồm media/problem data. Backup đầy đủ cần phối hợp maintenance: dừng app writers và judge, backup DB, media, problems, env được mã hóa và ghi lại manifest/tag image. Đưa bản sao ra thiết bị/máy khác và kiểm tra restore định kỳ.

Restore thay dữ liệu database hiện tại nên phải có backup và xác nhận chính xác:

```sh
python3 docker/ops.py --env-file .env.docker restore /path/to/db.sql.gz \
  --confirm 'REPLACE DATABASE'
```

Restore chỉ nạp SQL, không xóa bảng không có trong dump và không phục hồi media/problems. Ưu tiên restore vào DB sạch tương thích; phục hồi file media/problem riêng. Không bao giờ trỏ container vào datadir MariaDB đang dùng hoặc copy nóng file database.

Để chuyển từ hệ thống host hiện tại, dùng quy trình dump/restore có kế hoạch, sao lưu media và problem storage, xác minh quyền sở hữu và judge storage mapping. Không tự động nhập dữ liệu cũ khi chỉ chạy lệnh khởi tạo local ở mục 2.

## 9. Kiểm tra trước khi cho người dùng truy cập

- Đăng nhập admin, tạo tài khoản và xác nhận SMTP activation/password reset.
- Kiểm tra light/dark, mobile, static, media và tải ZIP trong giới hạn.
- Kiểm tra Celery worker nhận task thật; beat hoạt động; Redis broker/cache tách biệt.
- Kiểm tra WebSocket và long-poll qua nginx.
- Kết nối judge host bằng judge identity riêng; AC mẫu, checker/testlib và problem storage đọc được.
- Kiểm tra Polygon/AI chỉ khi đã cấu hình key, quyền và routing; không coi container healthy là các tích hợp đã hoạt động.
- Kiểm tra backup nằm ngoài server và phục hồi thử trên môi trường tách biệt.
- Nếu public: HTTPS, CSRF/login, hostname, IP client, WSS và cache rules qua tunnel/reverse proxy.

Đối chiếu hướng dẫn vận hành chi tiết hơn: [Docker runbook](../docker/README.md). CI Docker có thể chạy bằng `python3 -m docker.ci`; lệnh này xóa/reinitialise data root riêng `../msoj_docker_ci` và dùng port/subnet cố định. Dừng stack dev bằng `docker compose --env-file .env.docker down` trước khi chạy CI trên workstation, rồi khởi động lại bằng `up -d --wait` sau khi CI kết thúc. Không lưu dữ liệu cần giữ trong data root CI.

## 10. Xử lý lỗi thường gặp

| Hiện tượng | Kiểm tra và xử lý |
| --- | --- |
| Setup báo env đã tồn tại hoặc thư mục không rỗng | Không xóa secret/dữ liệu. Tiếp tục với env cũ, hoặc chọn env và data root mới nếu thực sự cần một cài đặt độc lập |
| Compose báo không tìm thấy image local | Chạy build với cả `compose.yaml` và `compose.build.yaml`. Chỉ `up` không tự build |
| `port is already allocated` hoặc `Pool overlaps` | Tắt stack dev trước CI; đổi port nếu bị chiếm. Subnet tunnel cố định phải được đổi đồng bộ trong `compose.yaml` và cấu hình trust nginx nếu xung đột VPN/network khác |
| Web/worker unhealthy | Xem `ps` và log riêng service, kiểm tra DB/cache/Redis đã healthy. Không công khai log chứa credential hoặc reset link |
| 400/CSRF hoặc đăng nhập không giữ session | Dùng đúng hostname, origin và scheme của `MSOJ_SITE_URL`; `DJANGO_ALLOWED_HOSTS` không có scheme/port. Đã đặt HTTPS thì cần truy cập qua HTTPS |
| Bị yêu cầu 2FA khi vào admin | Thiết lập 2FA cho staff; chỉ tắt `MSOJ_REQUIRE_STAFF_2FA` trên local rồi recreate web nếu đang kiểm thử |
| Import/upload báo permission denied | Đối chiếu `APP_UID`/`APP_GID` và ownership media/problems; không sửa ownership datadir DB bằng UID app |
| Submission nằm chờ | Kiểm tra bridge, identity judge, executor và problem storage trên host. Web healthy không có nghĩa là judge đã kết nối |
| ZIP upload trả 413 | Giảm kích thước toàn request hoặc dùng Polygon sync; không chỉ tăng timeout để bỏ qua giới hạn dung lượng |
| Thay code mà site vẫn cũ | Source được đóng trong image, không bind mount. Rebuild/pull đúng release, rồi recreate các service cần thiết |

## 11. Dependency và giới hạn kiểm chứng

- `docker/requirements.in` là danh sách đầu vào; `requirements.lock` chứa các gói PyPI và hash được kiểm bằng `--require-hashes`. Năm package VCS nằm trong `requirements-vcs.txt`, khóa commit SHA và cài `--no-deps`; Dockerfile chạy `pip check` sau đó.
- Không chỉnh riêng `.in` rồi cho rằng image đã đổi dependency: phải tái tạo lock và danh sách VCS cùng nhau, build và kiểm thử lại. Không dùng dòng command tự sinh trong header lock như một quy trình tái tạo đầy đủ vì các gói VCS đã được tách ra sau resolve.
- Pin base image digest và hash package giúp kiểm soát đầu vào, nhưng các gói apt/build toolchain vẫn có thể thay đổi. Đây không phải cam kết image build lại giống từng byte.
- Local đã được smoke trên Linux amd64; domain/tunnel thật, SMTP thật, OAuth và AI có phí cần kiểm tra riêng khi có credential. Không tuyên bố các tích hợp đó hoạt động chỉ từ kết quả CI hoặc healthcheck.
