# ⚔️🛡️ TOOL BẢNG QUÂN AOE BY XO (`v5.3`) — HỆ THỐNG AUTO DIPLOMACY, SẢNH LIVE, OBS OVERLAY & CẦU NỐI FACEBOOK GROUP LIVE

Hệ thống tự động trích xuất **Bảng Quân, Màu Quân & Phe Đồng Minh / Đối Thủ** trực tiếp khi người chơi ấn **Diplomacy (`F2`)** trong game **Age of Empires (AOE 1 / Rise of Rome)**, đồng bộ thời gian thực lên **Web Quản Lý Kèo**, **OBS Bảng Quân Overlay**, **OBS Khung Chat Trong Suốt** và tích hợp **Cầu Nối Tự Động Đẩy Comment Luồng Live Trong Group Facebook Lên OBS**.

---

## 📂 1. Kiến Trúc & Cấu Trúc Thư Mục Hệ Thống

```text
aoe-tracker/
├── .agents/
│   └── skills/                      # Bộ 7 kỹ năng thiết kế AI (ui-ux-pro-max, design-system, ui-styling, design, brand, banner-design, slides)
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
│   ├── logo.svg                     # Logo Vector chính thức của thương hiệu AOE BY XO (Khiên Obsidian, Song Kiếm Vàng, Vương Miện "XO")
│   ├── brand-tokens.css             # Hệ thống Design Tokens 3 tầng (Primitive -> Semantic -> Component) & Animation Vinh Danh
│   ├── index.html                   # Trang chủ Web: Sảnh Các Trận Đấu Đang Live, Hộp Chat & Vật Phẩm AOE, Thống kê, Admin
│   ├── overlay.html                 # Link OBS 1: Bảng Quân, Màu Cờ, Tỉ Số, Chữ Chạy, Bảng Phụ C & Bảng Vinh Danh Hoàng Gia
│   └── chat-overlay.html            # Link OBS 2: Khung Chat & Bảng Vinh Danh Vật Phẩm AOE nền trong suốt
├── docs/
│   └── brand-guidelines.md          # Tài liệu Bộ Nhận Diện Thương Hiệu & Chuẩn UI/UX Pro Max của AOE BY XO
├── design-system/
│   └── aoe-by-xo/
│       └── MASTER.md                # Thiết kế tổng thể sinh tự động từ bộ kỹ năng ui-ux-pro-max
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
5. **Bảng Nhật Ký Điều Tra Mở Rộng (`Expanded Diagnostic Log Panel`)**:
   - Hiển thị sẵn bảng Nhật ký rộng rãi (`10 dòng` kèm thanh cuộn dọc) ngay khi mở Tool; tích hợp nút **`🔎 Phóng to Log (18 dòng)`** để mở rộng tối đa vùng điều tra, nút **`📋 Copy Log`** để sao chép nhanh toàn bộ lịch sử log và ghi rõ chi tiết tọa độ khung hộp thoại, độ phân giải chụp được cũng như nguyên nhân từ chối (nếu có) ở từng bước quét `F2`.

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

### 2.3. Hệ Thống Sảnh Các Trận Đấu Đang Live (`🏟️`), Bạn Bè, Hộp Chat Đứng & Tặng Vật Phẩm Đế Chế (`🐘 ⚡ 🥩`)
- **🏟️ Sảnh Các Trận Đấu Đang Live (`Live Matches Lobby`)**:
  - Hiển thị danh sách trực quan toàn bộ các trận đấu đang `LIVE` trên hệ thống kèm tên Streamer, thể thức (`1v1`, `2v2`, `3v3`, `4v4`), đội hình 2 phe và tỉ số hiện tại.
  - Người chơi bấm **`👁️ Vào Sảnh & Chat`** để theo dõi trực tiếp đội hình/tỉ số trận đấu đó ngay trên bảng điều khiển (khi máy mình chưa có trận) và tham gia bình luận, tặng vật phẩm tương tác.
- **Bố cục Bảng Điều Khiển 2 Cột & Hộp Chat Đứng (`Vertical Chat Box`)**:
  - **Cột Trái (`56%`)**: Góc trên là khung **Team Đỏ vs Team Xanh** thu gọn gọn gàng; ở giữa là **🏟️ Sảnh Các Trận Đấu Đang Live & Bạn Bè**; ở dưới là **📜 Bảng Nhật Ký Điều Tra**.
  - **Cột Phải (`44%`)**: **Hộp Chat Đứng (`Vertical Chat Box`)** thiết kế giống hệt `chat-overlay.html` trên OBS, giúp đọc được nhiều bình luận, không bao giờ bị che khuất ô nhập chat hay các nút bấm ngay cả trên màn hình 4K DPI cao.
- **Quy Đổi Sao Từ Quỹ Sao Cá Nhân (`starsBalance`) & Bộ Vật Phẩm Đặc Trưng Đế Chế (`AOE Gift Catalog`)**:
  - Mỗi khi tặng Sao hoặc Vật Phẩm, hệ thống **trừ trực tiếp từ chính Quỹ Sao (`starsBalance`) của người tặng** và cộng vào Sao nhận được của Streamer (kèm lưu lịch sử giao dịch Sao 2 chiều).
  - Bổ sung bộ **6 Vật Phẩm Đặc Trưng Game Đế Chế (AOE 1)** quy đổi theo Quỹ Sao, hiển thị biểu tượng và hiệu ứng mưa icon bay lên trên OBS (`overlay.html` & `chat-overlay.html`):
    - **`🍖 Bơm 200 Thực`** (`5 ⭐`): Cứu chủ lực đầu đời!
    - **`🪵 Bơm 500 Gỗ`** (`10 ⭐`): Đóng nhà BA / bánh xe!
    - **`🥩 Bơm 1000 Thực`** (`15 ⭐`): Kích Đời 4 thần tốc!
    - **`🐘 Thả Con Voi Điên`** (`22 ⭐`): Húc bay nhà địch!
    - **`🏹 Viện Trợ Song Mã`** (`50 ⭐`): Đạo Song Mã thần cứu nhà!
    - **`⚡ Triệu Hồi Phù Thủy Sét`** (`100 ⭐`): Hú hú Wololo biến đổi quân địch!
- **Bảo mật Đổi Mật Khẩu 2 Lớp (`>= 8 ký tự`)**:
  - Khi người chơi đổi mật khẩu cá nhân (trên cả Tool PC và Web), hệ thống yêu cầu **tối thiểu 8 ký tự** và bắt buộc **nhập 2 lần mật khẩu (`Mật khẩu mới` & `Nhập lại mật khẩu`)** để kiểm tra trùng khớp trước khi lưu.

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

### 3.1. Gán 2 Link OBS Hiển Thị Lên Livestream & Căn Chỉnh Bằng Khung Bảng Quân Ảo
Trong phần mềm **OBS Studio**, tại mục **Sources (Nguồn)** bấm dấu **`+`** $\rightarrow$ chọn **`Browser` (Trình duyệt)**:

| Loại Nguồn OBS | Cách lấy Link trên Tool / Web | Kích thước chuẩn (Width x Height) | Công dụng |
| :--- | :--- | :--- | :--- |
| **1. OBS Bảng Quân & Tỉ Số** | Bấm nút **`📋 Copy Link OBS Bảng Quân`** (`/overlay.html?streamer=TEN_MAY`) | **`550` x `210`** *(hoặc **`750` x `210`** nếu bật Đánh theo C)* | Hiển thị Bảng Quân 2 Team, Màu Cờ, Tỉ Số, Chữ Chạy & Bảng phụ Đánh theo C. Khung vừa khít bảng quân, không bị thừa khoảng trống dưới đáy khi đặt sát mép dưới OBS. |
| **2. OBS Khung Chat & Sao** | Bấm nút **`💬 Copy Link OBS Chat`** (`/chat-overlay.html?streamer=TEN_MAY`) | **`380` x `520`** | Nền **trong suốt 100%**, chỉ hiện chữ viền đen sắc nét + Hiệu ứng Sao bay + Comment từ Facebook Group Live (`🔵 [FB]`). |

> [!TIP]
> **Tính năng Khung Bảng Quân Ảo Căn Chỉnh OBS (`showIdlePreview`)**:
> - Khi bạn chưa vào trận đấu (`match === null`), link `/overlay.html?streamer=TEN_MAY` sẽ tự động hiển thị một **Khung Bảng Quân Ảo (viền nét đứt vàng + nhãn `📐 KHUNG ẢO CĂN OBS`)** có kích thước, bố cục, màu cờ và cài đặt VIP y hệt bảng quân thật.
> - Bạn có thể kéo và căn vị trí khung trên OBS cực kỳ trực quan ngay trước khi vào game.
> - Ngay khi vào trận và bấm **`F2 (Diplomacy)`**, khung ảo sẽ tự động biến mất và chuyển sang **Bảng Quân & Tỉ Số thực tế** theo thời gian thực! (Có thể bật/tắt khung ảo bất kỳ lúc nào trong tab **⚙️ Tùy Chỉnh Cài Đặt VIP**).

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
      - Chuẩn hóa baseline cố định `11px` cho bộ mẫu chữ 2D (`CIV_TEMPLATES` & `AI_NAME_TEMPLATES`), mở rộng vùng cắt tên từ `x=8` (không cắt mất chữ cái đầu), khử vân gỗ trên/dưới dòng chữ và bổ sung đầy đủ danh sách tên AI chuẩn của 16 loại quân AOE 1 ROR (`Gortys`, `Aeacus`, `Vaballathus`, `Philo`, `Dido`, `Hatshepsut`, ...).
    - **Hỗ trợ đồng thời cả 2 giao diện hộp thoại AOE 1 (`Light Grey Marble` của quân Greek/Roman/Minoan & `Tan Wood` của quân Yamato/Shang) + Nới rộng Bảng Log Điều Tra**:
      - Khắc phục triệt để lỗi bảng `DIPLOMACY` nền **Đá Cẩm Thạch Xám Sáng (`Light Grey Marble`, `R=G=B=150..205`)** khi cầm quân `Greek`, `Roman`, `Minoan`, `Phoenician`... bị từ chối ở bước kiểm tra nền thanh tiêu đề (`w_left`/`w_right` và `white_title_px`) hoặc bị vân đá xám ở các dòng trống (`r=4..7`) làm lệch số dòng người chơi.
      - Áp dụng bộ lọc tương phản bóng đổ chữ trắng (`Drop-Shadow Contrast: min_rgb - shadow_rgb > 40`) giúp tách biệt tuyệt đối chữ trắng thật trên dòng người chơi với vân đá cẩm thạch xám sáng trên dòng trống.
      - Bổ sung ngưỡng khớp ký tự tối thiểu (`raw_sim >= 0.48`) trong `clean_and_match_player_name` trước khi cộng điểm thưởng AI theo quân, giữ nguyên chính xác tên người chơi thật hoặc tên AI ngắn (`Philo`, `Dido`) mà không bị ghi đè nhầm.
      - Nới rộng khung Nhật ký (`10 dòng` mặc định + thanh cuộn dọc + nút **`🔎 Phóng to Log (18 dòng)`** + nút **`📋 Copy Log`**) và hiển thị log chẩn đoán chi tiết tọa độ khung/độ phân giải/lý do từ chối khi bấm `F2` hoặc `Quét F2 ngay`.
    - **Khung Bảng Quân Ảo Căn Chỉnh OBS (`Virtual Preview Frame`) & Chuẩn hóa kích thước OBS Browser Source (`550 x 210` / `750 x 210`)**:
      - Khi chưa có trận đấu `LIVE`, [`public/overlay.html`](file:///C:/Users/APC/.gemini/antigravity/scratch/aoe-tracker/public/overlay.html) tự động hiển thị **Khung Bảng Quân Ảo (`📐 KHUNG ẢO CĂN OBS`)** với đúng kích thước thật (`525px` hoặc `733px` khi bật Đánh theo C), viền nét đứt vàng dễ nhận biết và áp dụng đầy đủ cấu hình VIP của Streamer (`Chạm X`, `Dòng chữ chạy`, `Hiện ngày góc phải`, `Bảng phụ Séc 1-2-3`) để người chơi dễ dàng kéo đặt vị trí trong OBS trước khi vào trận.
      - Ngay khi người chơi vào game ấn `F2 (Diplomacy)` tạo trận đấu mới, OBS Overlay tự động chuyển mượt mà từ Khung Ảo sang Bảng Quân thật qua luồng SSE thời gian thực.
      - Cập nhật kích thước chuẩn khuyên dùng cho nguồn Browser Bảng Quân trên OBS thành **`Width = 550, Height = 210`** (hoặc **`750 x 210`** nếu bật Đánh theo C) thay vì `980 x 600`, giúp khung viền đỏ của OBS ôm vừa khít bảng quân, không còn khoảng trống thừa bên dưới bị tràn ra ngoài mép đáy màn hình OBS.
      - Bổ sung tùy chọn bật/tắt **`📐 Hiện Khung Bảng Quân Ảo trên OBS khi chưa có trận`** (`showIdlePreview`, miễn phí cho mọi hạng từ Đồng trở lên) trên cả Tool PC và Web.
    - **Thiết kế lại Khung Đăng Nhập & Bố cục Bảng Điều Khiển 2 Cột (Tương thích 4K DPI) + Sảnh Trận Đấu Live + Vật Phẩm Đế Chế (`🐘 ⚡ 🥩`)**:
      - **Khung Đăng Nhập (`login_card`) co giãn tự động theo DPI**: Loại bỏ kích thước pixel cố định gây cắt chữ trên màn hình 4K (`3840x2160`), vẽ lại viền đôi (`#eca133` / `#2b3541`) ôm sát khung nhập liệu bên trong.
      - **Đổi mật khẩu an toàn (≥ 8 ký tự & Xác nhận 2 lần)**: Yêu cầu mật khẩu mới tối thiểu 8 ký tự và nhập lại lần 2 trùng khớp trên cả Tool PC (`open_my_profile_window`), Web (`index.html`) và API (`userChangePassword`).
      - **Bố cục Bảng Điều Khiển 2 Cột (`2-Column Workspace`)**: Thu gọn khung **Team Đỏ vs Team Xanh** sang góc trên bên trái, đặt **🏟️ Sảnh Các Trận Đấu Đang Live & Bạn Bè** ở giữa bên trái, **Bảng Nhật Ký Điều Tra** ở góc dưới bên trái; dành trọn **Cột Phải (`44%`)** làm **Hộp Chat Đứng (`Vertical Chat Box`)** giống `chat-overlay.html` giúp các nút và ô nhập bình luận luôn hiển thị đầy đủ, không bao giờ bị co cụm hay mất chữ.
      - **Sảnh Các Trận Đấu Đang Live (`Live Matches Lobby`)**: Liệt kê trực tiếp các trận đang `LIVE` kèm đội hình 2 bên và tỉ số, cho phép bấm **`👁️ Vào Sảnh & Chat`** để theo dõi trận đấu và tương tác ngay.
      - **Trừ Sao trực tiếp từ Quỹ Sao cá nhân (`starsBalance`) & 6 Biểu tượng Vật Phẩm Đế Chế (`AOE_GIFT_CATALOG`)**: Tặng **`🍖 200 Thực (5⭐)`**, **`🪵 500 Gỗ (10⭐)`**, **`🥩 1000 Thực (15⭐)`**, **`🐘 Con Voi (22⭐)`**, **`🏹 Song Mã (50⭐)`**, **`⚡ Phù Thủy Sét (100⭐)`** quy đổi trực tiếp từ Quỹ Sao của người chơi và bắn hiệu ứng icon bay lên trên OBS.
      - **Chống bắt nhầm cửa sổ nền tối (`med_bg_v`) trên màn 4K**: Bổ sung kiểm tra độ sáng trung vị nền hộp thoại (`58.0 <= med_bg_v <= 220.0`) trong `verify_is_diplomacy_dialog` để loại bỏ ngay cửa sổ nền tối của chính Tool.
    - **Tích hợp bộ 7 Kỹ năng Thiết kế UI/UX (`ui-ux-pro-max-skill` v2.0) vào `.agents/skills/`**:
      - Cài đặt đầy đủ 7 kỹ năng (`ui-ux-pro-max`, `design-system`, `ui-styling`, `design`, `brand`, `banner-design`, `slides`) vào `.agents/skills/` ở cả 2 kho mã nguồn (`aoe-tracker` & `aoetrackerv2`), hỗ trợ tra cứu 79 phong cách UI, 192 bảng màu ngành nghề, 74 cặp font chữ và 119 quy tắc UX trực tiếp qua công cụ `scripts/search.py`.
    - **Thiết kế Bộ Nhận Diện Thương Hiệu `AOE BY XO` & Tái Thiết Kế Toàn Diện bằng `ui-ux-pro-max` (Web • OBS Overlay • App PC)**:
      - **Logo Vector & Bộ Nhận Diện Thương Hiệu (`public/logo.svg`, `public/brand-tokens.css`, `docs/brand-guidelines.md`)**: Thiết kế biểu tượng chính thức **AOE BY XO** gồm Khiên Chiến Thuật Obsidian (`#0F172A`), Song Kiếm Chéo Vàng Hoàng Gia (`#FEF08A` $\rightarrow$ `#D97706`), Vương Miện 3 Đỉnh và Monogram `"XO"`; đồng bộ trên Web/OBS qua `/logo.svg` và vẽ trực tiếp bằng Vector Canvas (`_create_brand_crest_canvas`) trên Màn hình Đăng nhập + Header của App PC (`client/bangquanaoe.py`).
      - **Tái thiết kế khu vực `🏟️ Sảnh Các Trận Đấu Đang Live` (`Live Arena Showcase`)**: Bổ sung khu vực tiêu điểm Đấu Trường Trực Tiếp ngay đầu trang Web (`public/index.html`) và nâng cấp danh sách Sảnh Live trên App PC (`self.live_matches_list_frame`), hiển thị rõ Streamer, thể thức, bảng tỉ số ngang Đỏ vs Xanh bằng font điện tử `Chakra Petch`, tổng Sao, bình luận và cụm nút hành động 1 chạm (**`👁️ Vào Sảnh & Chat`**, **`🐘 Thả Voi 22⭐`**, **`⚡ Phù Thủy 100⭐`**).
      - **Làm mới Hiệu ứng Vinh Danh Hoàng Gia (`Royal Honor Plate` — `.aoe-honor-plate`)**: Khi người chơi tặng Sao hoặc Vật Phẩm Đế Chế (`🐘 Con Voi`, `⚡🧙‍♂️ Phù Thủy Sét`, `🥩 1000 Thực`, `🏹 Song Mã`), cả 3 nền tảng (**Web Dashboard**, **OBS Overlay `overlay.html` / `chat-overlay.html`**, và **Đỉnh Hộp Chat Đứng trên App PC `self.chat_honor_banner_frame`**) đồng loạt hiển thị Bảng Vinh Danh Hoàng Gia viền vàng ánh kim chuyển động kèm mưa biểu tượng vật phẩm bay lên.
      - **Kiểm tra & Chuẩn hóa Độ Tương Phản (WCAG AA/AAA), Khoảng Cách Nút Bấm (`>= 8px`) & Tỷ Lệ Chữ**: Nâng độ tương phản chữ phụ từ `#8e99a7` / `text-slate-500` lên `#cbd5e1` / `text-slate-200` (`>= 11.2:1`), chuẩn hóa khoảng cách nút `gap-2` (`8px`) và `padx=3..6` trên toàn bộ Dashboard.
    - **v5.4.0 — Tái Thiết Kế Giao Diện `Modern Esports Dashboard – Dark Premium – Gold Accent` (Chia 4 Khu Vực Chuẩn Pro)**:
      - **Khu vực A – Header và Thanh Điều Hướng**:
        - **Thanh Header Chính**: Gom gọn Logo Vector + `AOE COMMAND CENTER` (`TOOL QUẢN LÝ AOE BY XO - v5.4.0 Wood-Gold Esports`) bên trái; trạng thái kết nối pill (`🟢 Đã kết nối •`) và đồng hồ thực (`🕒 HH:MM:SS - DD/MM/YYYY`) ở giữa; `👑 Quỹ Sao`, `💎 Hạng VIP`, **Menu gộp `🛡️ Quản trị ▾`** (gồm Quản lý Tài khoản & Quỹ Sao, Phát hành Phiên bản, Dọn lịch sử kèo đấu) và `🚪 Đăng xuất` bên phải.
        - **Thanh Điều Hướng & Công Cụ Phụ**: Bên trái là 3 Tab chính có gạch chân vàng (`⊞ Bảng điều khiển`, `⚙️ Cài đặt VIP`, `👤 Tài khoản`); bên phải là các nút công cụ phụ kích thước nhỏ gọn (`🖥️ Link OBS`, `💬 OBS Chat`, `🔵 FB Group Live`, `📖 Hướng dẫn`, `🌐 Mở Web`).
        - **Thanh Thao Tác Nhanh (`Quick Action Sub-bar`)**: Phân cấp rõ độ nổi bật với nút chính màu vàng kim **`🔍 Quét F2 ngay`**, hộp kiểm `[✓] Tự động quét F2`, nút phụ `🖼️ Test ảnh` và liên kết `🔗 Link OBS Bảng Quân` bên phải.
      - **Khu vực B – Trung Tâm Quản Lý Trận Đấu (`Esports Scoreboard`)**:
        - Thiết kế dạng **Scoreboard Esports chuyên nghiệp**: Khiên Biểu Tượng Đội Đỏ (`#dc2626`) và Đội Xanh (`#2563eb`) vẽ bằng Canvas đối xứng 2 bên, hiển thị nổi bật tên tuyển thủ chính, loại quân + màu (`[Hittite] (Xám trắng)`).
        - **Tỉ số khổng lồ (`34pt`, `1 : 0`)** đặt chính giữa kèm thể thức (`Kèo 1v1 - Chạm 7`), trạng thái trận (`Trận #1 đang diễn ra`), **Dải lịch sử kết quả từng ván (`Lịch sử: V1: 🔴 Đỏ • V2: 🔵 Xanh`)** và hiệu ứng vinh danh khi kết thúc kèo.
        - **2 Nút xác nhận chiến thắng kích thước bằng nhau (`50% / 50%`)**: `🏆 Team Đỏ thắng (+1)` và `🏆 Team Xanh thắng (+1)`, kèm **nút `↩️ Hoàn tác (-1)` (`undoLastWinner`)** ngay trên thanh tiêu đề Scoreboard để tránh thao tác nhầm.
      - **Khu vực C – Danh Sách Trận Đấu (Dạng Card Nhỏ) và Bạn Bè**:
        - Bổ sung **ô tìm kiếm trận đấu (`🔍`)** và **bộ lọc nhanh (`Tất cả` | `Đang LIVE` | `Đã kết thúc`)**.
        - Hiển thị danh sách trận đấu dạng **Card nhỏ gọn** (`LIVE` / `XONG`, `Máy XO [1v1] • XO (1 - 0) Irm • ⭐ 0`, nút thả nhanh `🐘 22`, nút `📌 Đang xem` / `👁️ Xem trận`). Nhấn vào bất kỳ trận đấu nào sẽ chuyển ngay Scoreboard Khu vực B và Sảnh Chat Khu vực D sang trận đấu đó.
        - Thanh trạng thái bạn bè dưới đáy hiển thị số lượng bạn bè đang online (`👥 Bạn bè: X online • 🟢 ... • ⚫ bond (Offline)`).
      - **Khu vực D – Live Chat và Quà Tặng (Nâng Cấp 7 Tính Năng Livestream)**:
        1. **Tin nhắn quà tặng nổi bật**: Nền nâu vàng ánh kim (`#231b10`), viền vàng và biểu tượng vật phẩm riêng (`🐘`, `⚡`, `🥩`, `🏹`).
        2. **Phân biệt tin nhắn Admin & Chủ sảnh**: Gắn huy hiệu `🛡️ ADMIN` (nền đỏ) và `🎥 HOST` (nền xanh lam).
        3. **Ghim bình luận quan trọng (`pinChatMessage`)**: Thanh banner `📌 GHIM` cố định đầu khung chat kèm nút `📌 Ghim mới nhất` / `✕` bỏ ghim.
        4. **Tìm kiếm tên người dùng / nội dung chat (`🔍`)** ngay trên thanh công cụ chat.
        5. **Tùy chọn `Lọc Spam` (`[✓] Lọc Spam`)**: Tự động thu gọn các chuỗi từ lặp lại kiểu `"hay hay hay hay..."` thành `"hay (x16)"` và ẩn tin nhắn trùng lặp liên tiếp.
        6. **Hiển thị Tổng Sao nhận được trong phiên Live (`🎁 Phiên Live: X ⭐`)** cạnh Quỹ Sao cá nhân.
        7. **Tách sự kiện hệ thống (`⚙️ [HỆ THỐNG]`)** khỏi tin nhắn thông thường với 4 tab lọc nhanh (`Tất cả` | `💬 Chat` | `🎁 Quà` | `⚙️ Hệ thống`).
        - Khu vực **Vật Phẩm Đế Chế 3x2** có hình minh họa riêng (`200 Thực 5⭐`, `500 Gỗ 10⭐`, `1000 Thực 15⭐`, `Con Voi 22⭐`, `Song Mã 50⭐`, `Phù Thủy Sét 100⭐`), 4 nút tặng Sao nhanh (`+1`, `+10`, `+50`, `+100`) và nút `😊` chèn nhanh biểu tượng cảm xúc cổ vũ.
      - **Thanh Phím Tắt & Nhật Ký Thu Gọn Dưới Đáy (`Bottom Status & Hotkey Bar`)**: Hiển thị `Phiên bản 5.4.0`, `🟢 Cập nhật mới`, cụm phím tắt nhanh (`F2 Quét | F3 Test ảnh | F5 Thắng Đỏ | F6 Thắng Xanh | F7 Kết thúc kèo`) và ngăn kéo Nhật ký thu gọn mặc định (`📜 Xem chi tiết Nhật ký`).
      - **Tối Ưu Hóa Kích Thước Cửa Sổ Chuẩn `1366 x 768`, Nút Gộp `🎁 Tặng Sao ▾` & Phím Tắt Toàn Cục `F5 / F6` Ngay Trong Màn Hình Game**:
        - **Khung cửa sổ gọn gàng chuẩn `1366 x 768` (`tk scaling 1.26`)**: Cố định kích thước mở mặc định `1366 x 768` cân đối, các nút chức năng ở hàng thứ 2 (`⊞ Bảng điều khiển`, `⚙️ Cài đặt VIP`, `👤 Tài khoản` | `🖥️ Link OBS`, `💬 OBS Chat`, `🔵 FB Group Live`, `📖 Hướng dẫn`, `🌐 Mở Web`) xếp liền kề nhau đúng theo bản thiết kế gốc; thu gọn chiều cao Khu vực B (`TRẬN ĐẤU ĐANG DIỄN RA`) với khung viền nổi bật ở ô tỉ số trung tâm để nhường thêm không gian cho danh sách trận đấu Khu vực C.
        - **Gộp khu vực Vật Phẩm & Tặng Sao vào một nút duy nhất (`🎁 Tặng Sao ▾` / `🎁 Tặng Sao / Vật Phẩm ▾`)**: Mặc định ẩn bảng chọn vật phẩm để khung bình luận Live Chat có chiều cao tối đa; khi bấm vào nút **`🎁 Tặng Sao ▾`** sẽ xổ ra bảng 6 Vật Phẩm Đế Chế (`200 Thực`, `500 Gỗ`, `1000 Thực`, `Con Voi`, `Song Mã`, `Phù Thủy Sét`) + 4 mức tặng Sao nhanh (`+1`, `+10`, `+50`, `+100 Sao`) và tự động thu gọn lại sau khi tặng (đồng bộ cả trên App PC và Web Dashboard).
        - **Phím tắt `F5` (Team Đỏ thắng +1) & `F6` (Team Xanh thắng +1) hoạt động trực tiếp khi đang ở trong màn hình Game AOE (`Global In-Game Hotkeys`)**: Kết hợp đăng ký `user32.RegisterHotKey` (`WM_HOTKEY`) và `GetAsyncKeyState` trong luồng chạy ngầm kèm âm báo xác nhận (`Beep`), đồng thời tự động cộng nối tiếp ván thắng mới (`+1`) trên Server ngay cả khi người chơi bấm `F5`/`F6` liên tiếp trong game.
        - **Phím tắt `F8` (`🙌 Tay đâu, tayyyy đâuuuuu 🔥`) — Hiệu Ứng Ăn Mừng Chiến Thắng Nghẹt Thở Làm Mờ Bảng Quân OBS**:
          - Khi người chơi vừa có một chiến thắng nghẹt thở và nhấn **`F8`** trực tiếp trong màn hình Game AOE (hoặc bấm nút **`🙌 Tay đâu! [F8]`** trên thanh thao tác nhanh của App PC), hệ thống phát âm báo 2 nốt hứng khởi và kích hoạt API `triggerHypeShout` (`hype_shout` SSE).
          - Trên **OBS Bảng Quân Overlay ([`public/overlay.html`](file:///C:/Users/APC/.gemini/antigravity/scratch/aoe-tracker/public/overlay.html))**, toàn bộ bảng quân tự động mờ đi (`opacity: 0.14; filter: blur(4px)`) và được thay thế ngay chính giữa bằng bảng hiệu ứng vàng lửa bắn dòng chữ **`🙌 "Tay đâu, tayyyy đâuuuuu" 🙌`** rung lắc nhẹ kiểu hứng khởi (`@keyframes hypeGentleShake`) kèm mưa biểu tượng vỗ tay & lửa (`🙌`, `🔥`, `👏`, `⚡`, `🏆`) trong `6.5 giây` trước khi tự động trả lại bảng quân sắc nét.
          - Đồng thời đẩy thông điệp ăn mừng vào **OBS Chat Overlay ([`public/chat-overlay.html`](file:///C:/Users/APC/.gemini/antigravity/scratch/aoe-tracker/public/chat-overlay.html))**, **Sảnh Live Web ([`public/index.html`](file:///C:/Users/APC/.gemini/antigravity/scratch/aoe-tracker/public/index.html))** và **Bảng Tỉ Số / Khung Chat trên App PC**.
        - **Tối Giản Dòng Tặng Sao 1 Hàng (4 Màu Phân Biệt) & Tự Động Làm Mờ `chat-overlay.html` 80% Sau 5 Giây Không Có Chat Mới**:
          - **Rút gọn câu thông báo Tặng Sao / Vật Phẩm thành 1 dòng duy nhất**: Loại bỏ câu slogan mặc định lặp lại dài dòng (`— "Triệu hồi Phù Thủy Sét..."`), thu gọn theo cấu trúc **`🎁 [Người tặng] tặng [Icon + Vật phẩm (+X⭐)] ➔ [Người nhận]`** (ví dụ: `⚡ bond tặng ⚡ Phù Thủy Sét (+100⭐) ➔ XO`).
          - **Phân tách 4 màu sắc độc lập (Chống lẫn với màu vàng của Sao)**: **Người tặng** màu **Trắng Sáng (`#ffffff`)**, từ nối **`tặng / ➔`** màu **Xám Bạc (`#cbd5e1`)**, **Vật phẩm & Số Sao** màu **Vàng Kim (`#fbbf24`)**, và **Người nhận (`XO`)** đổi sang màu **Xanh Ngọc Lục Bảo Sáng (`#34d399`)** giúp người xem đọc lướt cực nhanh trên OBS, Web và App PC.
          - **Tự động giảm `80%` độ đậm (`opacity: 0.20`) trên [`public/chat-overlay.html`](file:///C:/Users/APC/.gemini/antigravity/scratch/aoe-tracker/public/chat-overlay.html) sau `5 giây` tĩnh**: Nếu sau `5 giây` không có bình luận hay quà tặng mới, toàn bộ khung Chat OBS tự động mờ mượt xuống `opacity: 0.20` để không che tầm nhìn bản đồ trong game, và lập tức sáng rõ `100%` (`opacity: 1.0`) ngay khi có tin nhắn hoặc quà tặng mới.
        - **Quy Tắc Chấm Tỉ Số Nghiêm Ngặt Cho `F5 / F6` (1 Trận 1 Đội Thắng Duy Nhất & Phải Hiện Quân), Nâng Cửa Sổ App PC Lên `1600 x 900` & Tách Biệt Hiệu Ứng `F8` Chỉ Hiện Trên `Link OBS`**:
          - **Quy tắc `F5 / F6` chuẩn giải đấu (`_validate_can_score_current_game` + `setWinner` API)**: Phím `F5` (Team Đỏ thắng +1) và `F6` (Team Xanh thắng +1) chỉ được chấp thuận khi quân của cả 2 đội trong trận đấu đó (`redCivs` & `blueCivs`) đã được quét và hiển thị hợp lệ; đồng thời mỗi trận đấu chỉ có duy nhất một đội chiến thắng (`winner === 'PENDING'`). Khi trận hiện tại đã có đội thắng, bấm tiếp `F5`/`F6` sẽ bị từ chối và nhắc người chơi ấn `F2 (Diplomacy)` trong game để hiển thị quân trận mới.
          - **Tăng kích thước cửa sổ App PC lên `1600 x 900` (`tk scaling 1.38`)**: Mở rộng không gian hiển thị mặc định của `client/bangquanaoe.py` lên `1600 x 900` rộng rãi, sắc nét.
          - **Hiệu ứng `F8` (`"Tay đâu, tayyyy đâuuuuu"`) chỉ hiển thị ở khung `'Link OBS'` ([`public/overlay.html`](file:///C:/Users/APC/.gemini/antigravity/scratch/aoe-tracker/public/overlay.html)), không hiển thị ở `'OBS Chat'` ([`public/chat-overlay.html`](file:///C:/Users/APC/.gemini/antigravity/scratch/aoe-tracker/public/chat-overlay.html))**: Mỗi khi ấn `F8`, khung `'OBS Chat'` và bảng quân `'Link OBS'` tự động làm mờ (`blur` + giảm `opacity`), đồng thời chỉ khung `'Link OBS'` hiển thị bảng hiệu ứng rung lắc `"Tay đâu, tayyyy đâuuuuu"` (hỗ trợ cả khi đang ở chế độ Khung Ảo căn OBS và khởi động lại hiệu ứng mượt mà mỗi lần ấn `F8`).
          - **Chống sinh trùng trận đấu khi mở lại `Diplomacy` (`F2`) trong cùng ván (`areSameCivLineups` + `deduplicateConsecutiveSameCivGames`)**: Khi người chơi ấn mở `Diplomacy` (`F2`) mà bộ quân 2 đội vẫn giống hệt trận hiện tại (`Trận #N`), cả App PC lẫn Server đều xác định trận đấu vẫn chưa kết thúc / chưa sang ván mới và giữ nguyên ở `Trận #N` (kể cả khi trước đó người chơi đã ấn `F5`/`F6` chấm kết quả của `Trận #N`), đồng thời tự động gộp khử các bản ghi trận liên tiếp trùng bộ quân.
          - **Cơ chế Bắt Phím Xuyên Game 3 Tầng (`3-Layer In-Game Hotkey Engine`) & Tự Động Nâng Quyền Administrator (`uac_admin=True`) Cho `F2 / F5 / F6 / F8`**:
            - **Khắc phục triệt để rào cản Windows UIPI (`User Interface Privilege Isolation`)**: Trên Windows 10/11, game Đế Chế (`EMPIRESX.EXE`) luôn chạy ở mức `High Integrity Level` (`Administrator`) do DirectPlay compatibility shim. Bản đóng gói [`client/bangquanaoe.spec`](file:///C:/Users/APC/.gemini/antigravity/scratch/aoe-tracker/client/bangquanaoe.spec) nay tích hợp sẵn `uac_admin=True` kèm hàm tự động nâng quyền `ensure_windows_admin_for_ingame_hotkeys()` (`ShellExecuteW("runas")`) trong [`client/bangquanaoe.py`](file:///C:/Users/APC/.gemini/antigravity/scratch/aoe-tracker/client/bangquanaoe.py) để Tool luôn chạy ngang quyền với Game.
            - **Kết hợp 3 tầng bắt phím độc lập (`_monitor_diplomacy_events`)**:
              1. **Tầng 1 — `SetWindowsHookExW(WH_KEYBOARD_LL = 13)`**: Hook bàn phím tầng thấp trực tiếp từ hàng đợi Kernel Input trước khi DirectInput của AOE xử lý phím.
              2. **Tầng 2 — `GetAsyncKeyState` tốc độ cao (`20ms`, không bị nghẽn bởi `sleep`)**: Kiểm tra đồng thời bit đang giữ (`0x8000`) và bit vừa gõ nhanh (`0x0001`).
              3. **Tầng 3 — `RegisterHotKey` (`WM_HOTKEY`)**: Bơm toàn bộ hàng đợi thông điệp Windows (`PeekMessageW(..., 0, 0, 1)` + `TranslateMessage` + `DispatchMessageW`) kèm bộ chống dội phím (`debounce 0.45s`), đảm bảo ấn `F5`, `F6`, `F8`, `F2` ngay trong màn hình Game AOE luôn nhạy 100%.
          - **Sửa triệt để lỗi tự nhảy về tab `Kèo Đấu` trên trình duyệt điện thoại khi đang ở `Chat Live` (`checkUrlForMatch` + `hasCheckedInitialUrlMatch`)**: Khắc phục lỗi khi người dùng chọn một kèo đấu (URL có `?matchId=...`) rồi chuyển sang tab `Chat Live` để bình luận hoặc tặng Sao thì vòng lặp đồng bộ `fetchInitialData()` (8s/lần hoặc khi có SSE) gọi lại `checkUrlForMatch()` và ép `mobileSection = 'matches'`. Nay `checkUrlForMatch()` chỉ kiểm tra 1 lần duy nhất lúc tải trang đầu tiên (`hasCheckedInitialUrlMatch`) và tuyệt đối không ghi đè tab `mobileSection` hiện tại của người dùng trên điện thoại.
