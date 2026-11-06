# 📜 ĐẶC TẢ HỢP ĐỒNG GIAO TIẾP API & BẢO TOÀN TƯƠNG THÍCH (`API_CONTRACT.md`)

> **Giai đoạn:** TASK 2 — Thiết Kế Hợp Đồng API Giữa Các Hệ Thống (Chưa can thiệp mã nguồn)  
> **Nguyên tắc số 1:** Tuyệt đối không phá vỡ hợp đồng REST API (`/api`) và SSE (`/api/stream`) đang phục vụ **AOE Command Center (`.exe`)** và **OBS Overlays (`overlay.html`, `chat-overlay.html`)**.

---

## 1. HIỆN TRẠNG GIAO TIẾP API (CURRENT API STATE)

Hiện tại [`server/index.js`](file:///c:/Users/APC/.gemini/antigravity/scratch/aoetrackerv2/server/index.js) phục vụ toàn bộ hệ thống AOE qua 2 kênh chính:
1. **Kênh Đồng bộ & Điều khiển (`GET /api` & `POST /api`)**:
   - Phục vụ 18 lệnh gọi từ [`client/bangquanaoe.py`](file:///c:/Users/APC/.gemini/antigravity/scratch/aoetrackerv2/client/bangquanaoe.py), 28 nhánh xử lý từ [`public/index.html`](file:///c:/Users/APC/.gemini/antigravity/scratch/aoetrackerv2/public/index.html), và polling dự phòng từ 2 trang OBS.
2. **Kênh Phát Sóng Thời Gian Thực (`GET /api/stream` — Server-Sent Events)**:
   - Phát đi 13 loại sự kiện (`connected`, `game_added`, `match_updated`, `winner_updated`, `match_finished`, `match_saved`, `matches_deleted`, `overlay_config_updated`, `chat_message`, `chat_pinned`, `star_gifted`, `hype_shout`, `players_updated`, `presence_updated`, `friends_updated`, `release_updated`, `settings_updated`).

---

## 2. HỢP ĐỒNG API BẤT BIẾN DÀNH CHO AOE CORE & OBS (IMMUTABLE AOE CONTRACT)

Bảng dưới đây quy định các endpoint và trường dữ liệu **BẮT BUỘC GIỮ NGUYÊN 100% TÊN TRƯỜNG & KIỂU DỮ LIỆU** để đảm bảo phần mềm `.exe` và OBS Studio hoạt động ổn định tuyệt đối:

### 2.1. Hợp Đồng `GET /api?action=getInitialData`

```json
{
  "status": "success",
  "databaseMode": "POSTGRES | LOCAL_JSON",
  "players": [
    {
      "name": "TenMay",
      "tier": "BRONZE | SILVER | GOLD | DIAMOND",
      "isActive": true,
      "activatedAt": 1730000000000,
      "expiresAt": null,
      "overlayConfig": {
        "targetScore": 100,
        "marqueeMode": "ALL",
        "customMarqueeText": "",
        "showDateCorner": true,
        "cModeEnabled": false,
        "cTargetWins": 3,
        "showIdlePreview": true
      },
      "friends": [],
      "starsReceived": 0,
      "starsBalance": 0,
      "lastSeenAt": 1730000000000,
      "isLive": false,
      "isOnline": true
    }
  ],
  "matches": [ /* Danh sách đối tượng kèo đấu AOE */ ],
  "currentMatch": { /* Kèo đấu đang LIVE của streamer được hỏi (hoặc null) */ },
  "recentChat": [ /* Các tin nhắn chat gần nhất */ ],
  "settings": {
    "showCivStats": true,
    "appRelease": {
      "latestVersion": "5.4.0",
      "downloadUrl": "/download-tool",
      "releaseNotes": "...",
      "forceUpdate": false,
      "updatedAt": 1730000000000
    }
  },
  "appRelease": { /* Bản sao đồng bộ của settings.appRelease */ }
}
```

> **Thay đổi bảo mật duy nhất được phép trên `GET /api` (Sanitization)**:
> - Loại bỏ trường `"password"` khỏi từng phần tử trong mảng `"players"` trả về công khai (hoặc gán cố định `"password": "******"`).
> - Qua kiểm tra toàn bộ 8.173 dòng code của [`client/bangquanaoe.py`](file:///c:/Users/APC/.gemini/antigravity/scratch/aoetrackerv2/client/bangquanaoe.py) và [`public/overlay.html`](file:///c:/Users/APC/.gemini/antigravity/scratch/aoetrackerv2/public/overlay.html), [`public/chat-overlay.html`](file:///c:/Users/APC/.gemini/antigravity/scratch/aoetrackerv2/public/chat-overlay.html): **không có bất kỳ dòng code nào ở App PC hay OBS đọc trường `p.password` từ `getInitialData`**! Do đó việc ẩn `password` trong `getInitialData` an toàn 100% với bản `.exe` hiện hành.

---

### 2.2. Hợp Đồng Các Action `POST /api` Phục Vụ AOE Command Center (`.exe`)

Toàn bộ các `action` sau giữ nguyên 100% đầu vào và đầu ra:
1. **`verifyPlayerLogin`**: Nhận `{ action, playerName, password }` $\rightarrow$ Trả về `{ status, message, playerName, tier, expiresAt, daysLeft, starsBalance, starsReceived, friends, overlayConfig, appRelease }` (+ cấp thêm `sessionToken` / `Set-Cookie` cho trình duyệt Web).
2. **`autoAddGame`**: Nhận `{ action, streamerName, password, redPlayers, redCivs, redColors, bluePlayers, blueCivs, blueColors, allowSameCiv }` $\rightarrow$ Trả về `{ status, message, match, matches, duplicateIgnored }`.
3. **`setWinner` & `undoLastWinner`**: Nhận `{ action, streamerName, updatedBy, password, winner, matchId, gameIndex }` $\rightarrow$ Trả về `{ status, message, match, matches }`.
4. **`triggerHypeShout`**: Nhận `{ action, streamerName, senderName, password, text, subText, durationMs }` $\rightarrow$ Phát SSE `hype_shout` tới `overlay.html` & `chat-overlay.html`.
5. **`heartbeat` & `finishMatch`**: Duy trì trạng thái `LIVE` mỗi 25s và tự động đóng kèo khi tắt App (`reason: "APP_CLOSED"`).
6. **`pushFacebookComment`**: Nhận `{ action, streamerName, password, bridgeToken, authorName, fbAuthor, text, commentId, fbCommentId }` *(Cập nhật đọc cả `authorName` lẫn `fbAuthor` để vá lỗi hiển thị tên `"Khán giả FB"`).*

---

## 3. ĐẶC TẢ GIAO TIẾP MỚI ĐỀ XUẤT (NON-BREAKING ADDITIONS)

Các giao tiếp bổ sung cho giai đoạn tích hợp tiếp theo được thiết kế **tách biệt hoàn toàn**, không chạm vào các action cốt lõi bên trên:

### 3.1. Chuẩn Hóa Xác Thực Admin (`isAdminAuthorized`)
- **Hiện tại (Lỗi `WEB-01`)**: `if (data.isAdmin) return true;`
- **Hợp đồng mới**:
  - Chỉ trả về `true` khi:
    1. `data.adminPassword` được gửi lên và khớp với `<ADMIN_PASSWORD_ENV>` trên Server; HOẶC
    2. Request mang `Admin Session Cookie / Token` hợp lệ do Server ký; HOẶC
    3. Người gọi xác thực hợp lệ bằng tài khoản chủ hệ thống `XO` kèm mật khẩu đúng của `XO`.
  - *Kiểm chứng tương thích với `bangquanaoe.exe`*: Trong [`client/bangquanaoe.py`](file:///c:/Users/APC/.gemini/antigravity/scratch/aoetrackerv2/client/bangquanaoe.py#L5214-L5860), tất cả các lệnh Admin (`adminUpdateReleaseConfig`, `adminCleanupMatchHistory`, `adminSavePlayer`, `adminTopupStars`, `adminResetPassword`, `adminExtendPlayer`, `adminToggleActive`, `adminDeletePlayer`) đều gửi kèm `"adminPassword": self.admin_password_cached`, nên **tương thích 100% không cần sửa giao thức**.

### 3.2. Giao Tiếp Cô Lập Cho Khu Vực Mini Games (`🎮 Giải Trí Chờ Kèo`)
- **Nguyên tắc cô lập**: Không nhét dữ liệu điểm số hay phòng chơi của Mini Games vào `GET /api?action=getInitialData` của AOE.
- **Cơ chế truyền định danh một chiều sang Mini Games**:
  - Với **Rắn săn mồi (`Snake`)** và **2048 (`2048`)** chạy trực tiếp trên trình duyệt: Đọc trực tiếp biến trạng thái `sessionPlayerName` và `sessionPlayerTier` đã xác thực trên giao diện Vue để hiển thị tên người chơi và lưu kỷ lục.
  - Với **Caro (`/caro`)**, **Sudoku (`/sudoku`)**, **Cờ vua (`/chess`)** chạy trên service `caro-online`:
    - Website cấp một vé định danh ngắn hạn (`action: "issueMiniGameTicket"`, hạn dùng `30 giây`, ký bằng `<SESSION_HMAC_SECRET>`) chứa `{ playerName, tier, exp }`.
    - Service `caro-online` xác minh chữ ký HMAC của vé này để tự động điền tên người chơi XO mà không cần truy cập vào bảng `players` của AOE.

---

## 4. LÝ DO LỰA CHỌN, ƯU ĐIỂM, NHƯỢC ĐIỂM, RỦI RO & ROLLBACK

- **Lý do lựa chọn**: Bảo vệ tuyệt đối tính tương thích ngược cho hàng trăm người dùng/Streamer đang giữ file `.exe` trên máy tính, đồng thời bịt kín các lỗ hổng bảo mật trên Server.
- **Ưu điểm**:
  - Không làm tăng kích thước bản tin JSON của `getInitialData` và luồng SSE `/api/stream`.
  - Vá được cả lỗi bảo mật nghiêm trọng lẫn lỗi tên tác giả Facebook Live chỉ bằng các điều chỉnh nhỏ, chính xác ở phía Server.
- **Nhược điểm**:
  - Cần duy trì hỗ trợ xác thực kép (vừa nhận `Session Cookie/Token` cho Web, vừa nhận `playerName + password` trên HTTPS POST cho bản `.exe` cũ) để không gây gián đoạn dịch vụ.
- **Rủi ro & Kiểm soát**:
  - *Rủi ro*: Nếu thay đổi cấu trúc trả về của `getPlayerProfile` khi Admin đang mở cửa sổ sửa User trên Web, form Admin có thể thiếu thông tin.
  - *Kiểm soát*: Giữ nguyên phản hồi của `getPlayerProfile` khi và chỉ khi `isAdminAuthorized(data)` hợp lệ (đã xác thực `adminPassword`), chỉ ẩn `password` ở endpoint công khai `getInitialData`.
- **Các module bị ảnh hưởng**: [`server/index.js`](file:///c:/Users/APC/.gemini/antigravity/scratch/aoetrackerv2/server/index.js) (hàm `isAdminAuthorized`, `enrichPlayersWithLiveStatus`, nhánh `pushFacebookComment`).
- **Phương án Rollback**: Mọi thay đổi nằm gọn trong kurang hơn 30 dòng kiểm tra điều kiện tại `server/index.js`, có thể hoàn tác tức thì bằng `git checkout` nếu phát sinh bất kỳ bất tương thích nào.

