# Vận hành MSOJ bằng Docker

Hướng dẫn cài mới, config local, xử lý lỗi và deploy: [Cài đặt MSOJ bằng Docker](../docs/docker-installation.md).
Local không cần domain hoặc Cloudflare; chỉ bật tunnel khi đã sẵn sàng public.

## Ranh giới và dữ liệu

Stack gồm Django/uWSGI, bridge, Celery worker + beat, event daemon Node, MariaDB,
Redis broker bền vững, Redis cache riêng, nginx và Cloudflare Tunnel tùy chọn.
Judge giữ trên host; không cần privileged container. Bridge và event daemon chỉ
chạy một instance. Không bật RabbitMQ, không đổi luật lọc Polygon.

`compose.yaml` chỉ dùng image, **không build trên production**. `compose.build.yaml`
chỉ phục vụ build trên workstation/CI. Docker Compose >= 2.24 và Linux containers.

Dữ liệu bind mount ngoài repo, mặc định `../msoj_docker_data/`:

| Thư mục | Container | Ghi chú |
| --- | --- | --- |
| database | `/var/lib/mysql` | MariaDB tự quản owner; không sửa/copy nóng file DB |
| redis | `/data` | Broker AOF; không dùng chung eviction với cache |
| media | `/data/media` | App ghi, nginx chỉ đọc |
| problems | `/data/problems` | App/worker ghi, judge host đọc thư mục host tương ứng |
| backups | không mount | Host nhận dump gzip, quyền 0600 |

Có thể đặt từng `MSOJ_*_DIR` ở thư mục ngoài riêng như `../msoj_db`,
`../msoj_media`, `../msoj_problem_data`. Không trỏ Docker DB vào data directory
của MariaDB host đang chạy. Không chạy hai MariaDB trên cùng thư mục. Muốn chuyển
DB cũ: dump/restore, không tái sử dụng datadir trực tiếp. Trong WSL dùng filesystem
Linux (`/home/...`), không dùng `/mnt/c` cho DB. Không `chmod 777`.

`docker compose down` không xóa các bind directory. Không xóa thư mục dữ liệu để
sửa lỗi container. Compose chạy app theo `APP_UID`/`APP_GID` do setup lấy từ host;
đảm bảo UID/GID đó có quyền ghi media/problems và judge host có quyền đọc problem
data. Image mặc định build với UID/GID 1000; local build nhận giá trị từ setup.
DB/Redis quản lý ownership datadir riêng; không chown toàn data root theo UID app.

## 1. Khởi tạo local, không đụng hệ thống hiện tại

```sh
python3 docker/setup.py --env-file .env.docker \
  --data-root ../msoj_docker_data --project msoj-dev \
  --http-port 18080 --bridge-port 19999 --site-url http://localhost:18080

docker compose --env-file .env.docker -f compose.yaml -f compose.build.yaml build
docker compose --env-file .env.docker up -d --wait db redis cache events
docker compose --env-file .env.docker run --rm migrate
python3 docker/ops.py --env-file .env.docker bootstrap
docker compose --env-file .env.docker run --rm web python manage.py createsuperuser
python3 docker/ops.py --env-file .env.docker bootstrap
docker compose --env-file .env.docker up -d --wait
```

Setup chỉ tạo file env mới (0600), random secret và thư mục rỗng, từ chối ghi đè.
Không in secret. Giữ `DJANGO_SECRET_KEY` ổn định và backup riêng có mã hóa; thay key
làm mất hiệu lực session, chữ ký và có thể ảnh hưởng trường mã hóa.

Bootstrap chỉ nạp `language_all`/`navbar` nếu bảng tương ứng rỗng, cập nhật Site từ
`MSOJ_SITE_URL`, bảo đảm superuser có Profile. Không nạp demo hay dữ liệu host.
Mặc định staff phải 2FA; có thể đặt `MSOJ_REQUIRE_STAFF_2FA=false` **chỉ cho kiểm
chứng local**, không vô hiệu hóa production. Locale mặc định tiếng Việt.

Truy cập `http://localhost:18080`. `docker compose --env-file .env.docker ps` và
`logs --tail=100 SERVICE` dùng để quan sát. Không chia sẻ output `compose config`
(không có `--quiet`), `inspect` env hoặc `.env.docker`: chúng chứa credential.
Email mặc định ra console để dev; production cấu hình SMTP trước khi cho đăng ký/
reset mật khẩu. Tránh chia sẻ log chứa liên kết reset.

## 2. Judge cùng host

Tạo một Judge bằng admin (tên và khóa riêng). Giữ khóa ngoài source/log. Cấu hình
judge host dùng `problem_storage_globs` trỏ vào **đường dẫn host** trong
`MSOJ_PROBLEM_DIR`, không phải `/data/problems` của container:

```yaml
judge_version: 2
problem_storage_globs:
  - id: local
    glob: /srv/msoj/problems/**
```

`judge_version: 2` là bắt buộc cho dạng storage có `{id, glob}` của judge MSOJ;
không bỏ khóa này rồi dùng cấu hình protocol 1 mặc định.

Giữ runtime/testlib.h/executor hiện có. Chạy judge với bridge `127.0.0.1` và port
`MSOJ_BRIDGE_PORT` (local thử là 19999, prod mặc định 9999). Không chạy judge thử
bằng cùng name/key với judge đang phục vụ hệ thống khác. Không in key command line
vào tài liệu hay log chia sẻ. Quản lý judge bằng service host với config riêng có
quyền hạn chế.

Bridge publish duy nhất `127.0.0.1:PORT`; Django gọi `bridge:9998` nội bộ. Không mở
9998/9999 qua Cloudflare. Khi mở rộng nhiều máy, mở bridge trên VPN và bổ sung cơ
chế phân phối test data; bridge không tự chuyển toàn bộ test data tới judge.

**Restart bridge chuyển submission đang chấm sang IE và judge kết nối lại.**
Lên lịch maintenance, dừng nhận bài và chờ hết bài đang chấm trước deploy. Không
scale bridge/beat/events thành nhiều replica.

## 3. Polygon và AI

Thêm riêng `POLYGON_API_KEY`/`POLYGON_API_SECRET` vào env server, không chép đè
toàn bộ `.env` local. Recreate worker/web/beat (không build lại image), chờ web
healthy rồi restart proxy để nginx resolve lại IP web; tránh 502 do upstream cũ.
`POLYGON_SYNC_AUTHOR` phải là user có Profile.

```sh
docker compose --env-file .env.docker exec web python manage.py sync_polygon --list
# Sau khi xem danh mục, sync bài đã chọn theo ID/tên Polygon:
docker compose --env-file .env.docker exec web python manage.py sync_polygon POLYGON_ID
```

Worker/app có Pandoc >= 3. Builder full package là bước riêng, cần quyền Polygon
WRITE/OWNER; command sync không tự tạo build. Không chạy builder/CLI sync/admin
sync đồng thời trên cùng API key. `--list` có refresh và ghi tracking index, không
phải dry-run thuần đọc DB. Blacklist owner/tag giữ nguyên cấu hình hiện hành;
force không vượt blacklist. Không xóa bài đã import chỉ vì thay blacklist.

ZIP import thủ công và testcase ZIP vẫn được giữ; cảnh báo giới hạn Cloudflare
Free 100 MB cho **toàn request**, kể cả multipart. Nginx cũng giới hạn 100 MiB và
trả 413; Cloudflare có thể từ chối trước nginx. Để dư khoảng trống hoặc ưu tiên
Polygon sync (server tải package, không qua đường upload trình duyệt).

AI Gateway/prompt cấu hình nằm trong DB, không đóng DB/dump vào image. Cấu hình
ProviderConnection/ModelRoute bằng admin và `AI_9ROUTER_API_KEY` trong env; không
copy prompt/private editorial/provider credential từ DB host sang Git hay client.
Khám phá catalog bằng `ai_gateway_smoke --connection SLUG`; phát sinh completion
có phí là lựa chọn riêng, cần xác nhận rõ trước khi chạy. DB sạch chưa có route
thì AI không được coi là đã cấu hình.

## 4. Cloudflare Tunnel (production)

Tạo named tunnel trong Cloudflare dashboard, public hostname của bạn trỏ vào:

```text
HTTP service: http://proxy-tunnel:8081
```

Trong env đặt `MSOJ_SITE_URL=https://oj.example.com`, `DJANGO_ALLOWED_HOSTS` có
`oj.example.com`, và `CLOUDFLARE_TUNNEL_TOKEN`. Không gửi token qua chat/Git.

```sh
docker compose --env-file .env.docker --profile cloudflare up -d cloudflared
```

Cloudflared chỉ outbound; không cần mở 80/443 inbound. Web listener mặc định
`127.0.0.1:MSOJ_HTTP_PORT`; có thể đặt `MSOJ_HTTP_BIND` thành IP Tailscale cụ thể
để truy cập trong tailnet, đồng thời đổi site URL và allowed hosts theo hướng dẫn.
Không dùng `0.0.0.0` để mở bản thử riêng ra tất cả card mạng.
Nginx listener 8081 chỉ tin peer tunnel `172.30.42.2` trên network riêng
`172.30.42.0/29`; listener 80 bỏ qua header HTTPS do client tự giả. Nếu subnet
xung đột host/VPN, đổi cả Compose network và nginx trust rồi build proxy lại.
Không public 8081. Không bật Cloudflare Access toàn site nếu muốn người học truy
cập công khai. Không cache HTML/auth/API/`/channels/`/`/event/`. Static dùng cache
ngắn, purge khi phát hành nếu bật thêm Cache Rule ở Cloudflare.

Realtime đi `wss://DOMAIN/event/`; `/channels/` là long-poll. Publisher 9997 chỉ
nội bộ và không có auth command; tuyệt đối không publish port này. Events giữ
buffer trong RAM, restart có thể mất thông báo trung gian; kết quả bài lưu DB.

### Thử domain trên máy dev trước khi chuyển server

Không trỏ tunnel thẳng vào Django `runserver` với `DEBUG=True`. Nếu kho bài nằm
trong DB host còn Docker đang dùng DB thử riêng, dùng origin WSGI tách biệt với
`DEBUG=False`, secret ổn định, allowed hosts/CSRF/cookie HTTPS đúng domain và
proxy phục vụ static/media; không đổi DB chỉ để bật tunnel. Trên Docker Desktop,
`network_mode: host` không đồng nghĩa loopback của WSL: kiểm tra đường proxy tới
IP WSL và cập nhật lại khi IP thay đổi. Cổng origin, DB và bridge không public.

Token connector chỉ dùng kết nối tunnel; hostname/DNS phải được tạo trong
Cloudflare dashboard hoặc bằng quyền API quản lý riêng. Giữ token trong env
git-ignored, quyền `0600`, không đặt token trên command line hay trong tài liệu.

Sau khi lưu hostname, kiểm tra DNS/TLS thực qua domain, HTTP chuyển sang HTTPS,
form đăng nhập qua CSRF, cookie Secure, static và WebSocket/long-poll. Connector
đã kết nối không đồng nghĩa hostname/DNS hay toàn bộ ứng dụng đã hoạt động.


## 5. CI/GHCR và deploy không build server

Workflow `.github/workflows/docker.yml` kích hoạt thủ công, không tự deploy.
Image package mới mặc định private; kiểm tra package visibility/access trước dùng,
không chuyển public nếu source image chưa được duyệt. Repo public không làm lộ
prompt trong DB, nhưng code/chỉ dẫn cố định trong source vẫn nằm trong image.
GitHub Actions dùng GITHUB_TOKEN; server chỉ cần PAT classic `read:packages`.
Đăng nhập qua `docker login ghcr.io --password-stdin`, không ghi token vào command.
GHCR hiện miễn phí storage/bandwidth theo GitHub; chính sách có thể thay đổi.

Build app/proxy/events từ cùng commit. CI kiểm tra trước publish; chọn đúng kiến
trúc server (workflow ban đầu Linux amd64). Server nhận compose và docker tooling
của đúng release, sửa env chọn ba image `ghcr.io/OWNER/REPO/{app,proxy,events}`
ở cùng SHA tag; khuyến nghị pin `@sha256:...`. Không dùng `latest`.

Lần đầu server: setup như mục 1 nhưng dùng `/srv/msoj` và domain thực; đặt image
release trong env, `compose pull`, chạy infra/migrate/bootstrap trước khi up app.
Không chạy `compose.build.yaml` trên production.

Cập nhật:

```sh
python3 docker/ops.py --env-file .env.docker deploy --allow-bridge-restart
```

Tool từ chối image local/latest, pull trước downtime, chờ infrastructure khỏe,
dừng app writers, backup DB, chạy migrate rõ ràng rồi khởi động app. Không tự hồi
phục bằng image cũ khi migrate lỗi. Không xem đổi image là rollback database:
phải kiểm tra migration tương thích, hoặc phục hồi bản backup phù hợp. Không
chạy deploy giữa contest hoặc trong khi Polygon import đang ghi dữ liệu.

## 6. Backup và restore

```sh
python3 docker/ops.py --env-file .env.docker backup
# Trong maintenance, restore chỉ khi chủ động đồng ý thay dữ liệu:
python3 docker/ops.py --env-file .env.docker restore /path/db.sql.gz --confirm 'REPLACE DATABASE'
```

DB backup là gzip dump transaction nhất quán, không phải copy nóng datadir.
Backup command không chụp media/problems. Muốn bản khôi phục đầy đủ: maintenance,
dừng app writers và judge đang dùng dữ liệu, dump DB, backup media/problems và env
đã mã hóa cùng release manifest. Đưa bản sao ra máy/đĩa khác, có retention và thử
restore định kỳ. `restore` import vào DB hiện tại, không xóa table không có trong
dump; ưu tiên target DB sạch tương thích. Không chạy restore trên DB production
chưa có backup. Đọc output tool để biết service nào đang dừng và chủ động up lại.

Không nâng MariaDB major bằng đổi tag rồi thử; làm dump/restore staging trước.

## 7. Kiểm chứng trước public

- DB migration/bootstrap; login/admin; light/dark/mobile, static/media.
- Worker ping và task thực; beat lịch; cache chung giữa process.
- Browser nhận event WebSocket và long-poll qua nginx; restart events reconnect.
- Judge host kết nối bridge, submission mẫu nhận AC; test data bind mount.
- Polygon package import bằng Pandoc và bài mới judge đọc được.
- Backup gzip có thể restore và dữ liệu vẫn còn sau recreate container.
- Domain/Tunnel thật: HTTPS, CSRF/login, IP thật, wss, cache rules.
- SMTP/OAuth/AI cần credential và cấu hình thật; không đánh dấu PASS khi chỉ có
  container healthy. Không có token/domain thì chỉ kiểm chứng local, không giả
  lập rồi tuyên bố Cloudflare đã hoạt động.
