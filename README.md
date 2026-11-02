# ⚔️🛡️ AOE COMMAND CENTER — TOOL BẢNG QUÂN AOE BY XO (`v5.0 Cyber HUD`)

Hệ thống tự động trích xuất **Bảng Quân, Màu Quân & Phe Đồng Minh/Đối Thủ** trực tiếp khi người chơi mở bảng **Diplomacy (F2)** trong game **Age of Empires (AOE 1 / Rise of Rome)**, đồng bộ thời gian thực lên **Web Quản Lý Kèo** và **OBS Cyber HUD Overlay**.

---

## 🚀 Thiết Kế & Tính Năng Mới (v5.0 Futuristic Cyber Gaming / Blue Neon HUD)

1. **Giao diện `AOE COMMAND CENTER` (Cyber Gaming / Blue Neon HUD)**:
   - Tông màu **Deep Navy (`#040814`)**, **Neon Blue (`#3b82f6`)**, **Cyan phát sáng (`#00f2fe`)** và điểm nhấn **Vàng Gold (`#fbbf24`)** đặc trưng của Age of Empires.
   - Header **AOE COMMAND CENTER** với biểu tượng Kiếm & Khiên (`⚔️🛡️`), đèn tín hiệu **Pulse Indicator**, thanh quét **Scanning Laser Neon**, huy hiệu **Hạng Tài Khoản VIP**, và **Đồng hồ + Ngày tháng thời gian thực ở góc phải**.
   - **Battle Control Arena**: Thiết kế **Team Đỏ (`RED LEGION`)** và **Team Xanh (`BLUE VANGUARD`)** thành 2 Card đối đầu trực quan, hiển thị đội hình, loại quân, màu cờ và nút bấm chiến thắng riêng biệt.
   - **Battle Log Terminal**: Giao diện Terminal hiện đại (`Consolas` monospace), phân loại màu sắc tự động theo từng sự kiện (`[SYSTEM]`, `[SUCCESS]`, `[BATTLE]`, `[VIP]`, `[WARN]`, `[ERROR]`).
   - **Tự động kết thúc kèo đấu khi tắt Tool**: Khi người chơi đóng phần mềm, hệ thống tự động gửi tín hiệu kết thúc kèo đang `LIVE` lên Server.

2. **Hệ Thống Phân Hạng Tài Khoản VIP (`Kim Cương - Vàng - Bạc - Đồng`)**:
   - **🥉 Hạng Đồng (`BRONZE`)**: Quét Diplomacy tự động, hiển thị bảng quân & tỉ số tiêu chuẩn.
   - **🥈 Hạng Bạc (`SILVER`)**:
     - Tùy chỉnh con số hiển thị **Kèo đấu chạm bao nhiêu (`CHẠM X`)** ngay trên bảng điều khiển.
     - Bật/Tắt **Hiển thị Ngày ở góc phải** trên OBS Overlay.
   - **🥇 Hạng Vàng (`GOLD`)**: Mở khóa toàn bộ tính năng Hạng Bạc + **Tùy chỉnh dòng chữ chạy (`Marquee`)**:
     - Bật/Tắt dòng chữ chạy.
     - Chọn chỉ hiển thị **Tổng Cung - Chém**, hoặc chỉ hiển thị **Số Cung - Chém của từng người**, hoặc hiển thị **Cả hai**.
     - Chạy **1 dòng chữ bất kỳ** do người chơi tự nhập (ví dụ: thông báo kèo đấu, thông tin donate...).
   - **💎 Hạng Kim Cương (`DIAMOND`)**: Mở khóa toàn bộ tính năng Hạng Vàng + **Chế độ Đánh theo 'C' (Séc đấu)**:
     - Hiển thị thêm **1 Overlay phụ nằm ở bên phải** bảng quân chính trên OBS.
     - Tự động tính kết quả từng **Séc (C1, C2, C3...)** theo quy tắc: đội nào thắng trước **3 trận** sẽ thắng Séc 1 (ví dụ `3 - 1`), các trận tiếp theo tự động sang Séc 2 (`2 - 3`), Séc 3 (`3 - 0`) và tổng tỉ số `C`.

---

## 📺 Hướng Dẫn Gán Link OBS Hiển Thị Lên Livestream

1. Bấm nút **📋 COPY LINK OBS** ngay trên thanh hướng dẫn của `TOOL BẢNG QUÂN AOE BY XO` (hoặc trên Web):
   ```text
   https://aoe-tracker.onrender.com/overlay.html?streamer=XO
   ```
   *(Thay `XO` bằng đúng tên tài khoản Player của bạn).*
2. Mở phần mềm **OBS Studio** trên máy tính.
3. Tại cột **Sources (Nguồn)** bên dưới, bấm dấu **`+`** → Chọn **`Browser` (Trình duyệt)** → Đặt tên `Bang Quan AOE` → Bấm **OK**.
4. Trong cửa sổ **Properties** hiện ra, thiết lập như sau:
   - **Local file**: ⬜ Bỏ tích (Không chọn)
   - **URL**: Dán link vừa copy (`https://aoe-tracker.onrender.com/overlay.html?streamer=XO`)
   - **Width (Chiều rộng)**: `980` *(để hiển thị trọn vẹn cả bảng phụ Đánh theo 'C' nằm bên phải)*
   - **Height (Chiều cao)**: `600`
5. Bấm **OK**!
