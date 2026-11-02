# ⚔️ TOOL BẢNG QUÂN AOE BY XO (`bangquanaoe` - `aoetrackerv2`)

Hệ thống tự động trích xuất **Bảng Quân, Màu Quân & Phe Đồng Minh/Đối Thủ** trực tiếp khi người chơi mở bảng **Diplomacy (F2)** trong game **Age of Empires (AOE 1 / Rise of Rome)**, đồng bộ thời gian thực lên **Web Quản Lý Kèo** và **OBS Overlay**.

---

## ✨ Tính Năng Nổi Bật (v4.1)

1. **Quét trực tiếp cửa sổ `DIPLOMACY` trên màn hình game**:
   - Không cần công cụ trung gian xuất file `civi.png`.
   - Không cần cài đặt `Tesseract-OCR` thủ công (sử dụng trực tiếp **Windows Native OCR** tích hợp sẵn trên mọi máy Windows 10/11 kết hợp thuật toán so khớp mẫu 16 quân & AI AOE).
   - Nhận diện chuẩn xác 100% **8 màu cờ chuẩn của AOE** bằng thuật toán tách dải vải cờ thuần túy (loại bỏ hoàn toàn nền đá xám và bóng chữ).
2. **Giao diện Desktop App (`TOOL BẢNG QUÂN AOE BY XO`)**:
   - Mặc định kết nối sẵn tới Server: `https://aoe-tracker.onrender.com/`
   - Hiển thị trực tiếp **Trạng thái tài khoản (`ACTIVE`)** và **Hạn sử dụng (`Ngày hết hạn / Số ngày còn lại`)**.
   - Tích hợp sẵn nút **📖 Hướng Dẫn Gán OBS** và **📺 Copy Link OBS** ngay trên phần mềm.
3. **Hệ thống Quản Trị User & Gia Hạn Thu Phí (Admin XO)**:
   - Chỉ Admin mới có quyền cấp tài khoản mới cho người chơi.
   - Quản lý danh sách toàn bộ User: **Tên Player, Mật khẩu, Ghi chú (SĐT/Zalo/Gói cước), Trạng thái (`Active` / `Tạm khóa`), Ngày kích hoạt (`activatedAt`), Ngày hết hạn (`expiresAt`)**.
   - Các nút **Gia hạn nhanh 1-Click**: `+7 Ngày`, `+30 Ngày`, `+1 Năm`, `Vĩnh viễn` hoặc chọn ngày hết hạn tùy ý trên lịch.
   - Tự động chặn đăng nhập và chặn đẩy trận đấu nếu tài khoản bị khóa hoặc hết hạn sử dụng.

---

## 📺 Hướng Dẫn Gán Link OBS Hiển Thị Lên Livestream

1. Bấm nút **📺 Copy Link OBS** trên phần mềm `TOOL BẢNG QUÂN AOE BY XO` (hoặc trên Web) để lấy đường dẫn của bạn:
   ```text
   https://aoe-tracker.onrender.com/overlay.html?streamer=XO
   ```
   *(Thay `XO` bằng đúng tên tài khoản Player của bạn).*
2. Mở phần mềm **OBS Studio** trên máy tính.
3. Tại cột **Sources (Nguồn)** bên dưới, bấm dấu **`+`** → Chọn **`Browser` (Trình duyệt)** → Đặt tên (ví dụ: `Bang Quan AOE`) → Bấm **OK**.
4. Trong cửa sổ **Properties** hiện ra, thiết lập như sau:
   - **Local file**: ⬜ Bỏ tích (Không chọn)
   - **URL**: Dán link vừa copy (`https://aoe-tracker.onrender.com/overlay.html?streamer=XO`)
   - **Width (Chiều rộng)**: `800`
   - **Height (Chiều cao)**: `600`
5. Bấm **OK**! Bảng quân nền trong suốt sẽ hiển thị ngay trên màn hình OBS để bạn kéo thả tới vị trí mong muốn trên Livestream.
