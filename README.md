# ⚔️🛡️ TOOL BẢNG QUÂN AOE BY XO (`v5.3`) — HỆ THỐNG AUTO DIPLOMACY, SẢNH LIVE, OBS OVERLAY & CẦU NỐI FACEBOOK GROUP LIVE

Hệ thống tự động trích xuất **Bảng Quân, Màu Quân & Phe Đồng Minh / Đối Thủ** trực tiếp khi người chơi ấn **Diplomacy (`F2`)** trong game **Age of Empires (AOE 1 / Rise of Rome)**, đồng bộ thời gian thực lên **Web Quản Lý Kèo**, **OBS Bảng Quân Overlay**, **OBS Khung Chat Trong Suốt** và tích hợp **Cầu Nối Tự Động Đẩy Comment Luồng Live Trong Group Facebook Lên OBS**.

---

## 📂 1. Kiến Trúc & Cấu Trúc Thư Mục Hệ Thống

```text
aoe-tracker/
├── client/
│   ├── bangquanaoe.py               # Mã nguồn chính của Tool PC (Tkinter GUI + OpenCV Diplomacy Scanner)
│   ├── bangquanaoe.spec             # Cấu hình đóng gói PyInstaller tạo file thực thi .exe
│   ├── dist/
│   │   ├── bangquanaoe.exe          # File chạy chính thức trên Windows
│   │   └── TOOL_BANG_QUAN_AOE_BY_XO.exe # Bản sao file chạy phục vụ đường dẫn tải trực tiếp (/download-tool)
│   └── fb_group_live_extension/     # Tiện ích Chrome / Edge / Cốc Cốc tự động bắt Comment Facebook Group Live
│       ├── manifest.json            # Khai báo Chrome Extension Manifest V3
│       └── content.js               # Script quét DOM bình luận luồng Live Facebook đẩy về Server
├── public/
│   ├── index.html                   # Trang chủ Web: Danh sách kèo, Sảnh Chat & Tặng Sao, Thống kê, Quản trị Admin
│   ├── overlay.html                 # Link OBS 1: Bảng Quân, Màu Cờ, Tỉ Số, Chữ Chạy & Bảng Phụ Đánh Theo C
│   └── chat-overlay.html            # Link OBS 2: Khung Chat & Hiệu ứng Sao bay nền trong suốt 100% (chỉ hiện chữ)
├── server/
│   ├── index.js                     # Backend API Server (Express + SSE Realtime Stream + Quản lý User/VIP/Version)
│   └── db.js                        # Tầng lưu trữ dữ liệu (Tự động dùng MongoDB hoặc fallback về data/db.json)
└── README.md                        # Tài liệu hướng dẫn tính năng, cách sử dụng & quy trình cập nhật hệ thống
```

---

## 🚀 2. Tổng Hợp Toàn Bộ Tính Năng Hệ Thống (`v5.3`)

### 2.1. Giao Diện Tool PC Tối Ưu Hóa (`Dark Wood / Charcoal Theme`)
1. **Màn hình Đăng Nhập Khởi Động (`Login Gate`)**:
   - Khi mở phần mềm, người chơi vào màn hình **Đăng Nhập Tài Khoản Player** trước tiên (có tự động điền thông tin đã lưu và tự động đăng nhập nếu tài khoản hợp lệ).
2. **Thanh Điều Hướng Góc Phải (`Top-Right Navigation Bar`)**:
   - **`⚔️ Bảng Điều Khiển`**: Khu vực điều khiển trận đấu chính (Team Đỏ vs Team Xanh, Tỉ số trung tâm, Sảnh Chat Live & Bạn bè đang Live).
   - **`⚙️ Tùy Chỉnh Cài Đặt VIP`**: Chỉnh kèo chạm bao nhiêu, chế độ chữ chạy (`Marquee`), bật/tắt ngày tháng góc phải, bật/tắt chế độ Đánh theo C (`Séc 1, 2, 3`), đổi địa chỉ máy chủ.
   - **`👤 Tài Khoản`**: Mở hồ sơ cá nhân của người chơi.
   - **`🛡️ Quản Trị Admin`**: Mở khóa quyền Admin và mở Bảng Điều Khiển Quản Trị User, VIP, Phiên Bản & Lịch Sử Đấu.
   - **`🚪 Đăng xuất`**: Đăng xuất về màn hình đăng nhập.
3. **Khu Vực Tỉ Số Trung Tâm & Nút Kết Thúc Kèo**:
   - Nút **`🗑 Kết thúc kèo đấu`** được đặt ngay ngắn ở đáy ô **Tỉ Số Trung Tâm**, nằm thẳng hàng ngang ở giữa 2 nút **`🔴 Team Đỏ thắng trận này (+1)`** và **`🔵 Team Xanh thắng trận này (+1)`**.
   - Kèo đấu đang `LIVE` sẽ được giữ nguyên trên Web và OBS cho đến khi người chơi chủ động bấm **`Kết thúc kèo`** (hoặc tự động đóng sau 4 giờ không hoạt động), giúp việc chấm tỉ số trên Web luôn đồng bộ tức thì với OBS Overlay.
4. **Nguyên Tắc Bắt Sự Kiện Click Nút `Diplomacy` (`F2`) & Xác Thực Đầy Đủ Đội Hình/Quân**:
   - **Chỉ quét khi có sự kiện mở Diplomacy**: Tool lắng nghe sự kiện khi người chơi thực sự **click chuột trái vào nút `Diplomacy` trên thanh HUD phía trên trong game** hoặc nhấn phím tắt **`F2` / `Alt+D`** (hoặc bấm nút quét thủ công trên Tool), tuyệt đối không quét ngầm vô điều kiện gây bắt nhầm màn hình kết thúc trận đấu.
   - **Bắt buộc đầy đủ thông tin Người chơi & Quân của cả 2 đội**: Chỉ trích xuất và gửi lên Server khi hộp thoại `DIPLOMACY` có đầy đủ nút `OK` + `Cancel`, tiêu đề cột `Name` / `Civilization` / `Ally` / `Neutral` / `Enemy`, số người chơi 2 đội cân bằng (`1v1`, `2v2`, `3v3`, `4v4`), tất cả các dòng đều đọc được tên người chơi hợp lệ (loại bỏ hoàn toàn tên giả `Player 1..8`, `Red 1`, `Blue 1`) và tên Quân hợp lệ (không đoán mò quân theo độ rộng pixel).
   - **Nguyên tắc tính trận đấu mới (`TRẬN X`)**: Khi bảng quân hợp lệ có **sự thay đổi quân (`đổi quân`)** hoặc trận trước đã có kết quả thắng/thua thì hệ thống mới tính sang **ván đấu mới (`+1 TRẬN`)**. Nếu đổi thể thức (ví dụ từ `2v2` sang `1v1` hoặc `3v3`), hệ thống tự động kết thúc kèo cũ và tạo kèo mới bắt đầu từ `TRẬN 1`.
5. **Thanh Nhật Ký 1 Dòng Gọn Gàng (`Collapsible Battle Log`)**:
   - Thu gọn thành 1 dòng trạng thái ở đáy cửa sổ; bấm **`📜 Chi tiết ▴`** khi cần mở rộng xem lịch sử hệ thống.

---

### 2.2. Hệ Thống Phân Hạng Tài Khoản VIP (`Kim Cương - Vàng - Bạc - Đồng`)
- **🥉 Hạng Đồng (`BRONZE`)**: Quét Diplomacy (`F2`) tự động, hiển thị bảng quân, màu cờ & tỉ số tiêu chuẩn.
- **🥈 Hạng Bạc (`SILVER`)**:
  - Tùy chỉnh con số hiển thị **Kèo đấu chạm bao nhiêu (`Chạm X`)**.
  - Bật / Tắt **Hiển thị Ngày tháng ở góc phải** trên OBS Overlay.
- **🥇 Hạng Vàng (`GOLD`)**: Mở khóa toàn bộ tính năng Hạng Bạc + **Tùy chỉnh dòng chữ chạy (`Marquee`)**:
  - Chọn hiển thị **Tổng Cung - Chém + Từng người**, chỉ **Tổng Cung - Chém**, chỉ **Cung - Chém từng người**, hoặc **Tắt chữ chạy**.
  - Chạy **dòng chữ tùy chỉnh bất kỳ** (thông báo kèo đấu, thông tin donate, quảng cáo...).
- **💎 Hạng Kim Cương (`DIAMOND`)**: Mở khóa toàn bộ tính năng Hạng Vàng + **Chế độ Đánh theo `C` (Séc đấu)**:
  - Hiển thị thêm **Bảng phụ kết quả từng C (`Séc 1, Séc 2, Séc 3...`)** nằm bên phải bảng quân chính trên OBS.
  - Tự động tính điểm Séc khi một đội chạm mốc thắng (mặc định chạm 3 mỗi C) và tự động nhảy sang Séc mới.

---

### 2.3. Hệ Thống Bạn Bè Đang Live, Sảnh Chat Giao Lưu & Tặng Sao Cổ Vũ (`🌟`)
- **Kết bạn & Theo dõi trạng thái trực tuyến**:
  - Người chơi có thể kết bạn với các Streamer/Player khác để biết ai đang **`🔴 LIVE`** hoặc **`🟢 Online`**.
  - Bấm 1 chạm **`🏟️ Vào Sảnh Live`** của bạn bè ngay trên Tool hoặc trên Web để trò chuyện và tặng Sao.
- **Bình luận & Tặng Sao Cổ Vũ (`+1 ⭐`, `+10 🌟`, `+50 ✨`, `+100 🔥`)**:
  - Bắt buộc đăng nhập tài khoản Player để bình luận hoặc tặng Sao.
  - Khi tặng Sao, số Sao sẽ trừ từ **Số dư Sao (`starsBalance`)** của người tặng, cộng vào tổng Sao nhận được của Streamer và kích hoạt **Hiệu ứng mưa Sao bay + Vinh danh nổi** ngay trên màn hình OBS của Streamer.

---

### 2.4. Cầu Nối Tự Động Đẩy Comment Luồng Live Trong Group Facebook Lên OBS (`🔵 [FB]`)
- Thiết kế chuyên biệt cho Streamer phát sóng **Live trong Group Facebook** (kể cả **Nhóm Kín / Private Group** và **Nhóm Công Khai**):
  - Không dùng Graph API bên thứ 3 nên **không cần duyệt App Meta**, **không cần lấy Cookie/Token nhạy cảm**, an toàn 100% cho tài khoản Facebook.
  - Tự động bắt mọi bình luận mới của khán giả đang comment dưới video luồng Live trên Facebook và đẩy thẳng lên **OBS Khung Chat ([`public/chat-overlay.html`](file:///C:/Users/APC/.gemini/antigravity/scratch/aoe-tracker/public/chat-overlay.html))**, **Sảnh Live trên Web ([`public/index.html`](file:///C:/Users/APC/.gemini/antigravity/scratch/aoe-tracker/public/index.html))** và **Khung Chat trên Tool ([`client/bangquanaoe.py`](file:///C:/Users/APC/.gemini/antigravity/scratch/aoe-tracker/client/bangquanaoe.py))** với nhãn **`🔵 [FB]`** màu xanh nổi bật.
  - Có cơ chế chống trùng lặp 2 lớp (trên trình duyệt và trên Server `global.__fbDedupMap`) để không bao giờ lặp lại bình luận cũ.

---

### 2.5. Hồ Sơ Tài Khoản Cá Nhân (Xem trên cả App PC & Web)
Người chơi bấm nút **`👤 Tài Khoản`** (trên Tool PC) hoặc **`Thông Tin TK`** (trên Web) để xem:
- **Hạng VIP hiện tại** (`Đồng / Bạc / Vàng / Kim Cương`) và trạng thái tài khoản (`Active / Tạm khóa`).
- **Ngày tạo tài khoản** và **Ngày kích hoạt VIP**.
- **Ngày hết hạn sử dụng** kèm bộ đếm ngược số ngày còn lại (`Còn X ngày` hoặc `♾️ Vĩnh viễn`).
- **Số dư Sao hiện có (`starsBalance`)** và **Tổng Sao đã được tặng trên Live (`starsReceived`)**.
- **Lịch sử Nạp Sao / Tặng Sao / Nhận Sao** và **Lịch sử Gia hạn VIP / Biến động tài khoản** chi tiết theo thời gian.
- Tự **Đổi mật khẩu cá nhân** trực tiếp.

---

### 2.6. Bảng Điều Khiển Quản Trị Admin Toàn Diện (Trên cả App PC & Web)
Admin sau khi đăng nhập mật khẩu quản trị có toàn quyền:
1. **Tìm kiếm (`Search`) & Lọc User thông minh**:
   - Tìm tức thì theo Tên máy / Ghi chú.
   - Lọc theo Hạng VIP, trạng thái Khóa/Mở, tài khoản Sắp hết hạn ($\le 7$ ngày), Đã hết hạn, hoặc Đang Live.
2. **Chỉnh sửa toàn diện thông tin User**:
   - Chỉnh sửa Tên máy, đổi Mật khẩu hoặc bấm **🔑 Reset mật khẩu nhanh** (mặc định về `123`).
   - Đổi Hạng VIP (`BRONZE`, `SILVER`, `GOLD`, `DIAMOND`), chỉnh **Ngày tạo tài khoản (`createdAt`)**, chỉnh **Ngày hết hạn (`expiresAt`)**.
   - Gia hạn nhanh bằng 1 nút bấm: **`+7 ngày`**, **`+30 ngày`**, **`+90 ngày`**, **`+1 năm`**, **`+N ngày tùy chỉnh`**, hoặc **`♾️ Cấp Vĩnh Viễn`**.
   - **💰 Nạp Sao (`+⭐`)** vào ví cho User kèm ghi chú lịch sử.
   - **🔒 Khóa / 🔓 Mở khóa** tài khoản hoặc **🗑 Xóa User**.
   - Xem trực tiếp bảng **Lịch sử nạp/tặng Sao** và **Lịch sử gia hạn VIP** của từng User.
3. **Quản lý Phiên bản Tool (`App Release`) & Link Tải**:
   - Cập nhật số phiên bản mới nhất (ví dụ `5.3`), đường dẫn tải file cài đặt (mặc định `/download-tool` hoặc link Google Drive / GitHub Release / Mega), nội dung thông báo cập nhật và tùy chọn **Bắt buộc cập nhật (`forceUpdate`)**.
   - Khi người chơi mở bản Tool cũ (ví dụ `v5.1` trong khi hệ thống đang là `v5.3`), Tool sẽ tự động hiện hộp thoại hỏi người chơi có muốn tải bản mới về ngay hay không.
   - **Tương thích ngược 100%**: Nếu chưa tích bắt buộc cập nhật, người dùng ở bản cũ vẫn quét bảng quân F2, lên tỉ số và dùng OBS bình thường mà không bị lỗi.
4. **Dọn Dẹp & Xóa Lịch Sử Đấu (`adminCleanupMatchHistory`)**:
   - **`🗓️ Xóa > 1 Tuần trước`**: Xóa các kèo đấu cũ hơn 7 ngày.
   - **`📅 Xóa > 1 Tháng trước`**: Xóa các kèo đấu cũ hơn 30 ngày.
   - **`⚙️ Tùy chỉnh: Xóa > N ngày`**: Nhập số ngày bất kỳ cần dọn.
   - **`👤 Xóa theo tên Streamer`**: Xóa toàn bộ lịch sử kèo của 1 Streamer cụ thể.
   - **`🧹 Xóa kèo rỗng (0 trận)`**: Dọn các kèo nháp không có trận đấu nào.
   - **`🏁 Xóa kèo đã kết thúc`**: Giữ nguyên các kèo đang `LIVE`, chỉ xóa các kèo đã kết thúc.
   - **`🔥 Xóa TẤT CẢ lịch sử đấu`**: Làm sạch 100% danh sách kèo đấu trên hệ thống.

---

## 📺 3. Hướng Dẫn Sử Dụng Chi Tiết Cho Streamer

### 3.1. Gán 2 Link OBS Hiển Thị Lên Livestream
Trong phần mềm **OBS Studio**, tại mục **Sources (Nguồn)** bấm dấu **`+`** $\rightarrow$ chọn **`Browser` (Trình duyệt)**:

| Loại Nguồn OBS | Cách lấy Link trên Tool / Web | Kích thước chuẩn (Width x Height) | Công dụng |
| :--- | :--- | :--- | :--- |
| **1. OBS Bảng Quân & Tỉ Số** | Bấm nút **`📋 Copy Link OBS Bảng Quân`** (`/overlay.html?streamer=TEN_MAY`) | **`980` x `600`** | Hiển thị Bảng Quân 2 Team, Màu Cờ, Tỉ Số, Chữ Chạy & Bảng phụ Đánh theo C. |
| **2. OBS Khung Chat & Sao** | Bấm nút **`💬 Copy Link OBS Chat`** (`/chat-overlay.html?streamer=TEN_MAY`) | **`380` x `520`** | Nền **trong suốt 100%**, chỉ hiện chữ viền đen sắc nét + Hiệu ứng Sao bay + Comment từ Facebook Group Live (`🔵 [FB]`). |

---

### 3.2. Hướng Dẫn Đẩy Comment Từ Luồng Live Trong Group Facebook Lên OBS
Khi bạn phát Live trong **Group Facebook**, hãy chọn 1 trong 2 cách sau:

#### Cách 1: Dùng nút 1-Click trên Tool (Nhanh nhất — 10 giây, Bảo mật 100% mật khẩu khi Live)
1. Trên Tool PC, bấm nút **`🔵 Kết nối FB Group Live`** $\rightarrow$ bấm **`📋 Copy Mã Tự Động Bắt Comment FB Group (1-Click)`** (hoặc bấm nút **`🔵 Kết nối FB Live`** ngay trên Web).
   - *Bảo mật chống lộ mật khẩu trên sóng Live*: Khung xem trước mã trên cửa sổ Tool hoàn toàn ẩn mật khẩu (`const AUTH_TOKEN = "•••••••••••••••• (Đã mã hóa bảo mật - Không lộ mật khẩu khi Live)"`), và đoạn mã copy vào Clipboard sử dụng mã khóa băm `SHA-256 bridgeToken` kết hợp mã hóa hex ẩn, tuyệt đối không để lộ mật khẩu dạng văn bản (`plaintext`) trên màn hình hay trong cửa sổ F12 Console.
2. Mở bài phát Live của bạn trong Group Facebook trên trình duyệt (Chrome / Cốc Cốc / Edge).
   - *Lưu ý*: Chuyển bộ lọc bình luận dưới video Facebook sang chế độ **"Mới nhất" (Newest)** hoặc **"Tất cả bình luận" (All comments)** và giữ nguyên tab đó chạy ngầm khi chơi game.
3. Ấn phím **`F12`** $\rightarrow$ chọn tab **`Console`** $\rightarrow$ ấn **`Ctrl + V`** rồi **`Enter`**.
4. Góc trái dưới màn hình Facebook sẽ hiện hộp tín hiệu **`🔵 AOE BY XO • Đang bắt Comment FB Group Live -> OBS`**. Mọi comment mới của người xem trên luồng Live Facebook sẽ tự động hiện lên OBS sau ~1 giây!

#### Cách 2: Cài Tiện Ích Trình Duyệt Chạy Ngầm (Cài 1 lần dùng mãi mãi)
1. Mở trình duyệt Chrome / Edge / Cốc Cốc, truy cập `chrome://extensions` (hoặc `edge://extensions`).
2. Bật công tắc **Chế độ dành cho nhà phát triển (Developer mode)** ở góc trên bên phải.
3. Bấm **Tải tiện ích đã giải nén (Load unpacked)** $\rightarrow$ chọn thư mục [`client/fb_group_live_extension`](file:///C:/Users/APC/.gemini/antigravity/scratch/aoe-tracker/client/fb_group_live_extension).
4. Khi mở bài Live trên Facebook, góc dưới bên trái sẽ có sẵn thanh **`🔵 AOE FB Live`**: nhập tên máy + mật khẩu của bạn rồi bấm **`BẬT`** là tự động hút toàn bộ comment đẩy lên OBS.

---

## 🛠️ 4. Hướng Dẫn Chỉnh Sửa, Đóng Gói `.exe` & Cập Nhật Hệ Thống (`Developer Guide`)

Mỗi khi chỉnh sửa tính năng hoặc ra mắt phiên bản mới (ví dụ nâng từ `5.3` lên `5.4`), hãy thực hiện theo đúng 4 bước chuẩn dưới đây:

### Bước 1: Cập nhật mã phiên bản (`Version Bump`)
1. **Trong [`client/bangquanaoe.py`](file:///C:/Users/APC/.gemini/antigravity/scratch/aoe-tracker/client/bangquanaoe.py)** (khoảng dòng 30):
   ```python
   APP_VERSION = "5.4"
   ```
2. **Trong [`server/index.js`](file:///C:/Users/APC/.gemini/antigravity/scratch/aoe-tracker/server/index.js)** (tại hằng số `DEFAULT_APP_RELEASE` khoảng dòng 34):
   ```javascript
   const DEFAULT_APP_RELEASE = {
     latestVersion: '5.4',
     downloadUrl: '/download-tool',
     releaseNotes: 'Mô tả các tính năng mới của bản cập nhật...',
     forceUpdate: false,
     updatedAt: Date.now()
   };
   ```
   *(Hoặc sau khi deploy xong, Admin có thể vào thẳng **Bảng Quản Trị Admin** trên Web/App để đổi số `Phiên bản mới nhất` và `Link tải` mà không cần sửa code).*

### Bước 2: Kiểm tra cú pháp (`Syntax Check`)
Chạy lệnh kiểm tra nhanh để đảm bảo không có lỗi cú pháp ở cả Server Node.js và Client Python:
```powershell
node -c "C:\Users\APC\.gemini\antigravity\scratch\aoe-tracker\server\index.js"
C:\Users\APC\.gemini\antigravity\scratch\aoe-tracker\client\.venv\Scripts\python.exe -m py_compile "C:\Users\APC\.gemini\antigravity\scratch\aoe-tracker\client\bangquanaoe.py"
```

### Bước 3: Đóng gói lại file chạy `.exe` bằng PyInstaller
Chạy lệnh đóng gói trong thư mục `client` và cập nhật cả 2 file `.exe` (`bangquanaoe.exe` và `TOOL_BANG_QUAN_AOE_BY_XO.exe`):
```powershell
Set-Location "C:\Users\APC\.gemini\antigravity\scratch\aoe-tracker\client"
.\.venv\Scripts\pyinstaller.exe --noconfirm bangquanaoe.spec
Copy-Item "dist\bangquanaoe.exe" "dist\TOOL_BANG_QUAN_AOE_BY_XO.exe" -Force
```

### Bước 4: Đồng bộ sang `aoetrackerv2` & Đẩy lên Git / Cloud Server
Nếu bạn đang sử dụng song song 2 thư mục `aoe-tracker` và `aoetrackerv2`, hãy đồng bộ các file đã sửa rồi commit + push lên Git để Railway / Render tự động deploy:
```powershell
$src = "C:\Users\APC\.gemini\antigravity\scratch\aoe-tracker"
$dst = "C:\Users\APC\.gemini\antigravity\scratch\aoetrackerv2"

Copy-Item "$src\README.md" "$dst\README.md" -Force
Copy-Item "$src\server\index.js" "$dst\server\index.js" -Force
Copy-Item "$src\public\index.html" "$dst\public\index.html" -Force
Copy-Item "$src\public\overlay.html" "$dst\public\overlay.html" -Force
Copy-Item "$src\public\chat-overlay.html" "$dst\public\chat-overlay.html" -Force
Copy-Item "$src\client\bangquanaoe.py" "$dst\client\bangquanaoe.py" -Force
Copy-Item "$src\client\fb_group_live_extension\*" "$dst\client\fb_group_live_extension\" -Force
Copy-Item "$src\client\dist\bangquanaoe.exe" "$dst\client\dist\bangquanaoe.exe" -Force
Copy-Item "$src\client\dist\TOOL_BANG_QUAN_AOE_BY_XO.exe" "$dst\client\dist\TOOL_BANG_QUAN_AOE_BY_XO.exe" -Force
```

---

## 📋 5. Nhật Ký Cập Nhật Phiên Bản (`Changelog`)

- **`v5.3` (Hiện tại)**:
  - Tích hợp **Cầu nối tự động bắt Comment từ luồng Live trong Group Facebook (`🔵 [FB]`)** đẩy thẳng lên OBS Khung Chat, Sảnh Live Web & Tool PC kèm bộ Chrome/Edge Extension [`client/fb_group_live_extension`](file:///C:/Users/APC/.gemini/antigravity/scratch/aoe-tracker/client/fb_group_live_extension) — **tích hợp cơ chế ẩn & mã hóa bảo mật mật khẩu (`SHA-256 bridgeToken` + khóa mã hóa hex)** chống lộ mật khẩu của Streamer trên sóng Live và trong cửa sổ F12 Console.
  - Bổ sung công cụ **Dọn dẹp & Xóa Lịch Sử Đấu (`adminCleanupMatchHistory`)** trong bảng Admin (xóa $>1$ tuần, $>1$ tháng, $>N$ ngày, theo Streamer, kèo rỗng, kèo đã kết thúc hoặc xóa tất cả).
  - Bổ sung nút **⬇️ Tải Tool PC** trên Web (`/download-tool`), tính năng **Đánh dấu phiên bản (`v5.3`) & Tự động nhắc cập nhật** khi người dùng mở bản cũ, cùng mục quản lý Version dành cho Admin.
  - Tinh chỉnh giao diện **Màu Gỗ Tối (`Dark Wood / Charcoal`)**, màn hình **Đăng nhập khi khởi động**, thanh **Menu Tab ở góc phải**, ẩn nút quét/test thủ công và đưa nút **🗑 Kết thúc kèo đấu** xuống đáy ô tỉ số trung tâm.
  - **Nhận diện chuẩn xác bảng Diplomacy (`F2`) đa màn hình & mọi độ phân giải (`800x600` $\rightarrow$ `2K 2560x1440` / `4K`) + Làm sạch bảng quân khi mới Đăng nhập**:
    - Tự động chuẩn hóa khung viền trên màn hình độ phân giải cao (`1080p` / `2K` / `4K` cả chế độ kéo giãn Fullscreen lẫn kích thước gốc `468x301` hoặc chế độ Cửa sổ lệch tâm).
    - Hỗ trợ quét đồng thời trên hệ thống nhiều màn hình (`Multi-Monitor`) ngay cả khi đang đặt cửa sổ Tool ở màn hình phụ; khôi phục 2 nút **🔍 Quét F2 ngay** và **🖼️ Test ảnh...** trên thanh công cụ nhanh.
    - Kiểm tra cấu trúc hộp thoại `DIPLOMACY` (tiêu đề trắng chính giữa, hai biên tiêu đề trống, nút `OK` vàng, tiêu đề cột `Name`/`Civilization`) và tự động làm sạch 2 bảng đội hình (`Team Đỏ` & `Team Xanh`) khi mới đăng nhập hoặc kết thúc kèo.
  - **Tối ưu hóa toàn diện Giao diện Điện thoại (`Mobile-First Livescore`) & Bảng màu Tối giản Thể thao điện tử (`Minimalist Esports`)** trên [`public/index.html`](file:///C:/Users/APC/.gemini/antigravity/scratch/aoe-tracker/public/index.html):
    - Chuyển sang bảng màu **Xám Đen (`#0b0f17` / `#131b26`) + Trắng Sáng + Xanh Dương dịu (`#38bdf8`)**, loại bỏ các mảng màu vàng/cam chói mắt và bỏ màu cầu vồng 8 màu AOE trên tên người chơi để chữ hiển thị trắng sáng đồng nhất, dễ đọc.
    - Bổ sung **Thanh Tab nhanh & Thanh điều hướng cố định dưới đáy (`Bottom Navigation Bar`)** trên điện thoại (`⚔️ Kèo Đấu` / `💬 Chat & Sao` / `👥 Bạn Bè` / `📊 Thống Kê`), ẩn các nút chỉ dành cho PC/OBS vào menu thu gọn `☰`.
    - Thiết kế lại **Thẻ Kèo Đấu & Bảng Tỉ Số nằm ngang (`Team Đỏ - Tỉ Số - Team Xanh` trên cùng 1 hàng)** giống ứng dụng Livescore, cùng danh sách quân từng trận xếp song song 2 cột gọn gàng trên màn hình điện thoại.
  - Nâng cấp toàn diện **Quản lý User & VIP** (tìm kiếm, lọc, chỉnh ngày tạo, ngày hết hạn, reset mật khẩu, nạp Sao, lịch sử Sao & VIP) và mục **Hồ sơ Tài khoản cá nhân** cho người chơi.
  - **Sửa triệt để lỗi nhảy bảng quân sang trận đã kết thúc, sai số trận (`TRẬN X`) & đồng bộ tức thì tỉ số từ Web lên OBS Overlay**:
    - **Cơ chế bắt sự kiện Click `Diplomacy` / `F2` (`_monitor_diplomacy_events`)**: Chỉ mở cửa sổ quét màn hình khi người chơi thực sự click vào nút `Diplomacy` trên thanh công cụ trong game hoặc bấm phím `F2` / `Alt+D`.
    - **Kiểm duyệt nghiêm ngặt bảng quân & người chơi**: Bắt buộc hộp thoại có đủ cả nút `OK` và `Cancel` màu vàng, tiêu đề `DIPLOMACY` & `Civilization / Ally / Neutral / Enemy`, có mặt người chơi dòng 1 (`row 0`), đầy đủ tên người chơi thật và tên Quân hợp lệ cho toàn bộ thành viên 2 đội cân bằng (`1v1`, `2v2`, `3v3`, `4v4`); loại bỏ hoàn toàn việc tự sinh tên `Player 2..8`, `Red 1`, `Blue 1` hoặc quân `Random`.
    - **Chuẩn hóa bộ đếm số trận (`TRẬN X`) & chống nhảy về kèo đã kết thúc**: Chỉ cộng ván đấu mới khi đổi quân (hoặc ván trước đã có đội thắng); tự động tách kèo mới về `TRẬN 1` nếu đổi thể thức (`1v1` $\leftrightarrow$ `2v2` $\leftrightarrow$ `3v3` $\leftrightarrow$ `4v4`); `overlay.html` chỉ hiển thị kèo đang `LIVE` (không bao giờ fallback về kèo `FINISHED` đã kết thúc).
    - **Đồng bộ tức thì tỉ số từ Web lên OBS Overlay (`setWinner`)**: Bổ sung nút chấm nhanh `🔴 +1 Đỏ` / `🔵 +1 Xanh` trên bảng tỉ số trung tâm Web, lưu phiên đăng nhập bền vững (`localStorage` + tự động thực thi lệnh chấm điểm ngay sau khi đăng nhập), kích hoạt trạng thái `LIVE` cho kèo vừa chấm điểm và phát trực tiếp dữ liệu `match` qua luồng SSE (`winner_updated`) kèm chống cache (`Cache-Control: no-store`) giúp OBS Overlay nhảy tỉ số ngay lập tức.
    - **Quét trực tiếp (Live Scan) bảng Diplomacy chuẩn xác trên cả 3 chế độ `Screen Size` (`1366 x 768`, `1600 x 900`, `1920 x 1080`)**:
      - Kích hoạt `SetProcessDpiAwareness(2)` ngay khi mở Tool để `ImageGrab` chụp đúng 100% độ phân giải vật lý của màn hình mà không bị Windows DPI Scaling (125%/150%) cắt góc.
      - Gỡ bỏ rào cản Windows UIPI khi game `EMPIRESX.EXE` chạy quyền Administrator (không bị chặn khi chờ `GetAsyncKeyState`), đồng thời hỗ trợ tự động cắt khung cửa sổ game hoặc khung con `(0, 0)` khi chỉnh `Screen Size` nhỏ hơn màn hình chính.
      - Nâng cấp bộ lọc `verify_is_diplomacy_dialog` kiểm tra đủ bộ 3 nút đáy đặc trưng của bảng `DIPLOMACY` (`OK` vàng bên trái, `CLEAR TRIBUTES` trắng ở giữa, `CANCEL` trắng bên phải), loại bỏ tuyệt đối bảng `GAME SETTINGS` hoặc `MENU`.
      - Chuẩn hóa baseline cố định `11px` cho bộ mẫu chữ 2D (`CIV_TEMPLATES` & `AI_NAME_TEMPLATES`), mở rộng vùng cắt tên từ `x=8` (không cắt mất chữ cái đầu), khử vân gỗ trên/dưới dòng chữ và bổ sung đầy đủ danh sách tên AI chuẩn của 16 loại quân AOE 1 ROR (`Gortys`, `Aeacus`, `Vaballathus`, ...).
