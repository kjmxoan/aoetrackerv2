# Quy Tắc Phát Triển & Cập Nhật Dự Án TOOL BẢNG QUÂN AOE BY XO

Mỗi khi thêm tính năng mới, sửa lỗi hoặc chỉnh sửa hệ thống, Agent BẮT BUỘC thực hiện đầy đủ các quy tắc sau trước khi hoàn tất:

1. **Luôn cập nhật tài liệu `README.md`**:
   - Cập nhật đầy đủ vào `README.md` mô tả chi tiết tính năng mới, cách sử dụng cho Streamer/User/Admin, cấu trúc file liên quan, hướng dẫn chỉnh sửa/đóng gói khi có update mới và ghi vào mục `Changelog`.

2. **Đóng gói lại bản chạy `.exe` khi có thay đổi ở `client/bangquanaoe.py`**:
   - Kiểm tra cú pháp: `python -m py_compile client/bangquanaoe.py` và `node -c server/index.js`.
   - Build lại bằng PyInstaller: `C:\Users\APC\.gemini\antigravity\scratch\aoe-tracker\client\.venv\Scripts\pyinstaller.exe --noconfirm bangquanaoe.spec`.
   - Copy `client/dist/bangquanaoe.exe` sang `client/dist/TOOL_BANG_QUAN_AOE_BY_XO.exe` để đường dẫn `/download-tool` trên Web luôn trả về bản `.exe` mới nhất.

3. **Đồng bộ 2 kho mã nguồn (`aoe-tracker` & `aoetrackerv2`)**:
   - Mọi thay đổi ở `C:\Users\APC\.gemini\antigravity\scratch\aoe-tracker` (bao gồm `server/`, `public/`, `client/`, `README.md`, `GEMINI.md`) phải được đồng bộ sang `C:\Users\APC\.gemini\antigravity\scratch\aoetrackerv2` và commit vào Git ở cả 2 thư mục.

