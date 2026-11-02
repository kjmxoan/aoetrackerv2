# ⚔️ Tool Bảng Quân AOE (`bangquanaoe` - `aoetrackerv2`)

Hệ thống tự động trích xuất **Bảng Quân, Màu Quân & Phe Đồng Minh/Đối Thủ** trực tiếp khi người chơi mở bảng **Diplomacy (F2)** trong game **Age of Empires (AOE 1 / Rise of Rome)**, đồng bộ thời gian thực lên **Web Quản Lý Kèo** và **OBS Overlay**.

---

## ✨ Điểm Mới Nổi Bật (v4.0)

1. **Quét trực tiếp cửa sổ `DIPLOMACY` trên màn hình game**:
   - Không cần công cụ trung gian xuất file `civi.png`.
   - Không cần cài đặt `Tesseract-OCR` thủ công (sử dụng trực tiếp **Windows Native OCR** tích hợp sẵn trên mọi máy Windows 10/11 kết hợp thuật toán so khớp mẫu 16 quân AOE).
   - Tự động nhận diện **Team Đỏ (Bản thân + Đồng minh tích `X` ở cột Ally)** và **Team Xanh (Đối thủ tích `X` ở cột Enemy)** cùng **8 màu cờ chuẩn của AOE**.
   - Tương thích mọi độ phân giải màn hình (`1024x768`, `1366x768`, `1600x900`, `1920x1080`, `2K`) và mọi giao diện (`Classic Tan` / `Dark Stone`).
2. **Giao diện App Desktop (GUI) thân thiện cho người chơi**:
   - Không cần mở hay chỉnh sửa file `config.json`.
   - Chỉ cần nhập **Tên Player** và **Mật khẩu** ngay trên cửa sổ phần mềm (tự động tạo tài khoản mới trong lần đăng nhập đầu tiên và tự động ghi nhớ cho các lần mở sau).
   - Có sẵn nút bấm nhanh ngay trên App: **🔴 Team Đỏ Thắng**, **🔵 Team Xanh Thắng**, **🏁 Kết Thúc Kèo**, **📺 Copy Link OBS Overlay**.
3. **Database PostgreSQL trên Neon.tech + Deploy miễn phí trên Render.com**:
   - Thay thế hoàn toàn Google Sheet / Apps Script chậm trễ bằng **Node.js + Express + Server-Sent Events (SSE)** và **Neon PostgreSQL**, giúp OBS Overlay cập nhật tức thì (`< 0.1 giây`).
   - Tự động khởi tạo bảng (`CREATE TABLE IF NOT EXISTS`) ngay khi Server khởi động — không cần chạy lệnh SQL thủ công.

---

## 📂 Cấu Trúc Thư Mục

```text
aoetrackerv2/
├── package.json              # Cấu hình Node.js Backend
├── render.yaml               # Cấu hình tự động deploy trên Render.com
├── .env.example              # Mẫu biến môi trường (DATABASE_URL, ADMIN_PASSWORD)
├── server/
│   ├── index.js              # Express API + Realtime SSE + Phục vụ Web/Overlay
│   └── db.js                 # Kết nối Neon PostgreSQL + Tự động tạo bảng
├── public/
│   ├── index.html            # Giao diện Web quản lý kèo đấu & Thống kê Meta
│   └── overlay.html          # Giao diện OBS Browser Source (?streamer=XO)
└── client/
    ├── bangquanaoe.py        # App Desktop GUI tự động quét màn hình Diplomacy
    ├── aoe_client.py         # Bản dự phòng tương thích
    ├── requirements.txt      # Thư viện Python cho App Desktop
    └── build_exe.bat         # Script đóng gói thành 1 file bangquanaoe.exe duy nhất
```

---

## 🚀 Hướng Dẫn Triển Khai Miễn Phí (Neon.tech + GitHub + Render.com)

### Bước 1: Tạo Database PostgreSQL miễn phí trên Neon.tech
1. Truy cập [https://neon.tech](https://neon.tech) và đăng nhập (bằng GitHub hoặc Google).
2. Bấm **New Project** → Đặt tên (ví dụ: `aoe-tracker-db`), chọn Region gần Việt Nam (ví dụ: **Singapore `ap-southeast-1`**) → Bấm **Create Project**.
3. Tại màn hình Dashboard của Neon, bấm **Copy Snippet** để lấy chuỗi kết nối **Connection String** (có dạng):
   ```text
   postgresql://neondb_owner:npg_xxxxx@ep-xxxx-pooler.ap-southeast-1.aws.neon.tech/neondb?sslmode=require
   ```
   *(Lưu ý: Hệ thống sẽ tự động tạo các bảng `players`, `matches`, `settings` trong lần chạy đầu tiên).*

### Bước 2: Đẩy Code lên GitHub (`aoetrackerv2`)
Mở Terminal tại thư mục dự án và chạy:
```bash
git init
git add .
git commit -m "Initial commit bangquanaoe - aoetrackerv2"
git branch -M main
git remote add origin https://github.com/AnhntOEV/aoetrackerv2.git
git push -u origin main
```

### Bước 3: Deploy miễn phí trên Render.com
1. Truy cập [https://render.com](https://render.com) và đăng nhập bằng tài khoản GitHub.
2. Bấm **New +** → Chọn **Web Service** → Kết nối tới repository GitHub bạn vừa đẩy lên.
3. Cấu hình dịch vụ:
   - **Runtime**: `Node`
   - **Build Command**: `npm install`
   - **Start Command**: `npm start`
   - **Instance Type**: `Free`
4. Kéo xuống mục **Environment Variables**, bấm **Add Environment Variable**:
   - `DATABASE_URL` = *(Dán chuỗi kết nối PostgreSQL từ Neon.tech ở Bước 1)*
   - `ADMIN_PASSWORD` = `00716441516` *(hoặc mật khẩu Admin tùy chọn của bạn)*
5. Bấm **Deploy Web Service**. Sau khoảng 1 phút, bạn sẽ nhận được đường dẫn Web chính thức (ví dụ: `https://aoe-match-tracker.onrender.com`).

---

## 🎮 Hướng Dẫn Sử Dụng Cho Người Chơi / Streamer

### 1. Chạy App Desktop (`bangquanaoe.py` hoặc `bangquanaoe.exe`)
- **Cách 1 (Chạy trực tiếp bằng Python)**:
  ```bash
  cd client
  pip install -r requirements.txt
  python bangquanaoe.py
  ```
- **Cách 2 (Đóng gói thành file `.exe` gửi cho người chơi khác)**:
  Chạy file `client\build_exe.bat` → Gửi file `client\dist\bangquanaoe.exe` cho người chơi.

### 2. Kết nối & Sử dụng trong Game
1. Mở phần mềm **AOE Match Tracker Client**:
   - Nhập **Server URL**: Ví dụ `https://aoe-match-tracker.onrender.com`
   - Nhập **Tên Player**: Ví dụ `XO`
   - Nhập **Mật khẩu**: Ví dụ `111`
   - Bấm **🔑 Lưu & Kết Nối Ngay** (Lần sau mở app sẽ tự động đăng nhập!).
2. Vào game **Age of Empires**, mỗi khi bắt đầu trận mới, chỉ cần bấm nút **Diplomacy (phím tắt F2)** để soi quân:
   - Phần mềm sẽ tự động phát hiện bảng `DIPLOMACY`, đọc tên người chơi, loại quân, màu cờ và phe Đồng minh (`Ally`) / Đối thủ (`Enemy`), sau đó cập nhật thẳng lên Web và OBS Overlay!
3. **Gán vào OBS Studio**:
   - Bấm nút **📺 Copy Link OBS Overlay** trên phần mềm (hoặc trên Web).
   - Trong OBS Studio → Thêm **Browser Source** → Dán link:
     `https://<TEN_APP_CUA_BAN>.onrender.com/overlay.html?streamer=XO`
   - Chiều rộng (Width): `520`, Chiều cao (Height): `160`.

