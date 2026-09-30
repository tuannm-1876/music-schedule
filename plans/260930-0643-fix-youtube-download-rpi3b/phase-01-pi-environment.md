# Phase 1 — Môi trường Pi: OS / Python / JS runtime

**Ưu tiên:** P0 · **Trạng thái:** todo

## Kiểm tra trên Pi
```bash
uname -m                 # aarch64 hay armv7l
cat /etc/os-release      # bookworm/trixie hay bullseye
venv/bin/python -V
venv/bin/yt-dlp --version
venv/bin/yt-dlp -v -F "https://www.youtube.com/watch?v=dQw4w9WgXcQ" 2>&1 | grep -i "js\|runtime\|challenge\|warning"
```

## Nhánh quyết định
| Hiện trạng | Việc cần làm |
|---|---|
| Python < 3.10 (Bullseye) | Cài mới Pi OS Bookworm **64-bit** Lite (khuyến nghị), rồi chép `instance/music.db` + `music/` sang |
| aarch64 | Cài Deno ≥2.3: `curl -fsSL https://deno.land/install.sh \| sh` (runtime mặc định của yt-dlp, không cần cấu hình) |
| armv7l, không muốn cài lại OS | Node 22 LTS armv7l (NodeSource hoặc tarball chính thức), đặt `js_runtimes={'node': {}}`; phương án cuối là QuickJS-NG ≥0.12 (bản cũ hơn chậm tới vài phút mỗi lần giải) |

- Pi 3B+ chỉ có 1GB RAM, Deno/Node tốn khoảng 60–120MB mỗi lần giải: bật zram (`sudo apt install zram-tools`) và không tải song song.
- Dựng lại venv: `pip install -U "yt-dlp[default]"` (kéo theo `yt-dlp-ejs`).
- `requirements.txt`: đổi `yt-dlp` thành `yt-dlp[default]`.

## Biến môi trường mới (file dotenv của project)
```
YTDLP_JS_RUNTIME=deno        # deno | node | quickjs
YTDLP_JS_RUNTIME_PATH=       # tùy chọn, đường dẫn tuyệt đối tới binary
YTDLP_COOKIES_FILE=          # tùy chọn, dùng khi bị "Sign in to confirm you're not a bot"
```
Service systemd phải có `PATH` chứa `~/.deno/bin` (hoặc khai `YTDLP_JS_RUNTIME_PATH`), vì systemd không đọc `.bashrc`.

## Done khi
- Lệnh `yt-dlp -F` ở trên liệt kê được format audio (140/251) và không còn cảnh báo "No supported JavaScript runtime".

## Rủi ro
- Cài lại OS có thể mất dữ liệu: backup `instance/`, `music/`, file dotenv trước.
- IP nhà bị YouTube chặn tạm: dùng cookies file (xuất từ trình duyệt đăng nhập tài khoản phụ, không dùng tài khoản chính).
