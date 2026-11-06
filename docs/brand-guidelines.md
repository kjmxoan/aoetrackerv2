# ⚔️🛡️ BỘ NHẬN DIỆN THƯƠNG HIỆU & DESIGN SYSTEM — AOE BY XO (UI/UX PRO MAX v5.4)

Tài liệu này quy định chuẩn **Brand Identity (Bộ nhận diện thương hiệu)**, **Logo & Icon System**, **Kiến trúc 3 tầng Design Tokens**, và **Tiêu chuẩn UI/UX Pro Max** được đồng bộ xuyên suốt 3 nền tảng của hệ sinh thái **AOE BY XO**:
1. **Web Command Center & Live Arena (`public/index.html`)**
2. **OBS Broadcast Overlays (`public/overlay.html` & `public/chat-overlay.html`)**
3. **App PC Streamer (`client/bangquanaoe.py` & `.exe`)**

---

## 1. Triết Lý Thương Hiệu & Khẩu Hiệu (Brand Essence)
- **Tên thương hiệu**: **AOE BY XO** (`TOOL BẢNG QUÂN AOE BY XO`)
- **Phong cách chủ đạo (Aesthetic Persona)**: **Imperial Tactical Wood-Gold Esports** — Sự giao thoa giữa hào khí Đế Chế Cổ Đại (Khiên Vàng Hoàng Gia, Song Kiếm, Vương Miện) và Bảng Điều Khiển Esports Hiện Đại (Nền Đá Đen Obsidian, Viền Cyan Chiến Thuật, Số Tỷ Số Điện Tử Sắc Nét).
- **3 Giá trị cốt lõi**:
  1. **Tức thì & Chính xác (Zero-Latency Tactical Precision)**: Nhìn rõ quân, tỷ số và sảnh Live trong 0.5 giây.
  2. **Tôn vinh Cộng đồng (Royal Honor & Community)**: Mỗi lượt tặng Sao hay vật phẩm Đế Chế (`🐘 Con Voi`, `⚡ Phù Thủy Sét`, `🥩 1000 Thực`, `🏹 Song Mã`) đều được vinh danh trang trọng như trên sóng giải đấu chuyên nghiệp.
  3. **Đồng nhất Đa nền tảng (Cross-Platform Cohesion)**: Người dùng mở App PC, xem trên OBS hay vào Web đều nhận ra ngay dấu ấn **AOE BY XO**.

---

## 2. Thiết Kế Logo & Hệ Thống Biểu Tượng (`public/logo.svg`)
### 2.1. Biểu Tượng Chính (Primary Crest Emblem)
- **File chuẩn Vector**: [`public/logo.svg`](../public/logo.svg)
- **Cấu trúc hình học**:
  - **Khiên Chiến Thuật Obsidian (`#0F172A` -> `#060913`)**: Bảo vệ trung tâm, bo viền Vàng Hoàng Gia (`#FEF08A` -> `#D97706`) và đường chỉ khâu chiến thuật Esports Cyan (`#38BDF8`).
  - **Song Kiếm Chéo (Crossed Broadswords)**: Đặt phía sau khiên, tượng trưng cho các kèo đấu Solo / Team nảy lửa.
  - **Vương Miện 3 Đỉnh & Monogram `"XO"`**: Đặt tại tâm khiên, khẳng định bản quyền thương hiệu **AOE BY XO**.
- **Trên App PC (`client/bangquanaoe.py`)**:
  - Được vẽ trực tiếp bằng **Vector Canvas (`_create_brand_crest_canvas`)** trên cả Màn hình Đăng nhập và Thanh Header chính, tái tạo chính xác Khiên Obsidian, Song Kiếm Vàng và chữ `"XO"` không phụ thuộc vào font emoji của Windows.

### 2.2. Hệ Thống Vật Phẩm Vinh Danh Đế Chế (AOE Signature Gift Icons)
| Mã Vật Phẩm | Biểu Tượng | Tên Hiển Thị | Chi Phí Sao | Ý Nghĩa Trong Game AOE |
| :--- | :---: | :--- | :---: | :--- |
| `STAR` | 🌟 | **Tặng Sao** | `1 / 10 / 50 ⭐` | Cổ vũ tinh thần trực tiếp cho Streamer |
| `FOOD_200` | 🍖 | **Bơm 200 Thực** | `5 ⭐` | Cứu nguy xin dân thời kỳ Đời 1 - Đời 2 |
| `WOOD_500` | 🪵 | **Bơm 500 Gỗ** | `10 ⭐` | Đóng thêm nhà BA / BL / BM thần tốc |
| `ELEPHANT` | 🐘 | **Tặng Con Voi** | `22 ⭐` | Dắt voi húc về nhà chính — con số `22` huyền thoại |
| `FOOD_1000` | 🥩 | **Bơm 1000 Thực** | `15 ⭐` | Bơm thực kích Đời 3 / Đời 4 thần tốc |
| `HORSE_ARCHER` | 🏹 | **Đạo Quân Song Mã** | `50 ⭐` | Càn quét bản đồ với đại quân C Tên / Đạp Đôi |
| `PRIEST_LIGHTNING` | ⚡🧙‍♂️ | **Phù Thủy Sét** | `100 ⭐` | *Hú Wololo!* — Cấp bậc vinh danh Hoàng Gia cao nhất |

---

## 3. Kiến Trúc 3 Tầng Design Tokens (`public/brand-tokens.css`)

### Tầng 1 — Primitive Tokens (Bảng Màu Gốc)
- **Obsidian & Slate Dark Surfaces**:
  - `--aoe-obsidian-950`: `#060913` (Nền Canvas chính)
  - `--aoe-slate-900`: `#111622` (Nền Card / Panel)
  - `--aoe-slate-850`: `#161d2b` (Nền Elevated / Sảnh Live)
  - `--aoe-slate-800`: `#1e293b` (Nền Nút / Ô nhập liệu)
- **Imperial Gold (Thương hiệu & Vinh danh)**:
  - `--aoe-gold-200`: `#fef08a` | `--aoe-gold-500`: `#eca133` | `--aoe-gold-600`: `#d97706`
- **Tactical Team & Status Colors**:
  - **Team Đỏ (Crimson)**: `#f43f5e` (`--team-red`)
  - **Team Xanh (Royal Blue)**: `#3b82f6` (`--team-blue`)
  - **Esports Cyan (Tương tác / Sảnh đang xem)**: `#38bdf8` (`--brand-accent`)
  - **Emerald Live (Đang phát sóng)**: `#34d399` (`--status-live`)

### Tầng 2 — Semantic & Contrast Standards (Chuẩn Tương Phản WCAG AA/AAA)
- **Văn bản chính (`--text-primary`)**: `#f8fafc` (Độ tương phản `17.4 : 1` trên nền `#0b0f19` — Đạt chuẩn AAA).
- **Văn bản phụ (`--text-secondary`)**: `#e2e8f0` (Độ tương phản `14.1 : 1` — Đạt chuẩn AAA).
- **Nhãn thông tin (`--text-muted`)**: `#cbd5e1` (Độ tương phản `11.2 : 1` — Loại bỏ hoàn toàn lỗi chữ xám mờ khó đọc).
- **Metadata phụ (`--text-subtle`)**: `#94a3b8` (Độ tương phản `6.4 : 1` — Vượt chuẩn AA `4.5 : 1`).

### Tầng 3 — Typography & Spacing Scale
- **Font tiêu đề & Tỷ số (`--font-display`)**: `Chakra Petch` / `Roboto Condensed` (`font-weight: 700-800`, `tabular-nums`) tạo cảm giác bảng điện tử giải đấu.
- **Font giao diện & Chat (`--font-sans`)**: `Inter` / `Segoe UI` giúp đọc bình luận và danh sách người chơi rõ ràng ở mọi kích thước.
- **Font nhật ký & Thời gian (`--font-mono`)**: `JetBrains Mono` / `Consolas`.
- **Khoảng cách nút bấm (`Button Spacing Rule`)**:
  - Khoảng cách tối thiểu giữa 2 nút bấm liền kề là **`8px` (`gap-2` trên Web, `padx=4..6` mỗi bên trên App PC)** để tránh bấm nhầm khi đang thao tác nhanh trong trận.
