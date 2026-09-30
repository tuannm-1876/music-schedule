# Phase 0 — Chốt code đang dở

**Ưu tiên:** P0 · **Trạng thái:** todo

## Bối cảnh
Working tree có 11 file đã sửa, cùng `frontend/src/components/holiday/`, `playlist-manager/`, `migrate_play_all.py`, `migrate_playlist_holiday.py` chưa commit (tính năng holiday/playlist/play_all). Nếu sửa YouTube chồng lên thì khó review và khó rollback.

## Các bước
1. `cd frontend && npm run build` — xác nhận build qua.
2. `venv/bin/python -c "import app"` — xác nhận import không lỗi.
3. Commit riêng: `feat: add holiday and playlist management with play_all schedules`.
4. Tạo nhánh `fix/youtube-download-rpi`.

## Done khi
- `git status` sạch, đang ở nhánh fix.
