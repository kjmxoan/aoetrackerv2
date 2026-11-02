import os
import sys
import time
import json
import difflib
import itertools
import threading
import subprocess
import tempfile
from pathlib import Path

import cv2
import numpy as np
import requests
from PIL import Image, ImageGrab, ImageDraw, ImageFont

APP_VERSION = "v4.0.0"

# ==============================================================================
# 1. DANH SÁCH 16 QUÂN AOE 1 & BẢNG MÀU CHUẨN TRONG BẢNG DIPLOMACY
# ==============================================================================
CIV_LIST = [
    ("Assyrian", "Assy", 53),
    ("Babylonian", "Baby", 68),
    ("Carthaginian", "Cartha", 76),
    ("Choson", "Choson", 48),
    ("Egyptian", "Egyp", 53),
    ("Greek", "Greek", 38),
    ("Hittite", "Hittite", 40),
    ("Macedonian", "Mace", 72),
    ("Minoan", "Minoan", 46),
    ("Palmyran", "Palmyran", 56),
    ("Persian", "Persian", 48),
    ("Phoenician", "Phoenic", 67),
    ("Roman", "Roman", 44),
    ("Shang", "Shang", 39),
    ("Sumerian", "Sumer", 58),
    ("Yamato", "Yamato", 47),
]

# 8 màu chuẩn của AOE (0..7 tương ứng mảng COLORS trên overlay.html)
# 0: Blue (Xanh lam), 1: Orange (Cam), 2: Red (Đỏ), 3: Yellow (Vàng),
# 4: Green (Xanh lá), 5: Gray/White (Xám trắng), 6: Brown (Nâu), 7: Cyan (Xanh cung)
AOE_RIBBON_HSV = {
    0: (115.0, 155.0, 105.0),  # P1 - Blue (Xanh lam)
    1: (13.0,  200.0, 120.0),  # P2 - Orange (Cam)
    2: (2.0,   172.0, 110.0),  # P3 - Red (Đỏ)
    3: (21.0,  142.0, 105.0),  # P4 - Yellow (Vàng)
    4: (50.0,   72.0,  75.0),  # P5 - Green (Xanh lá)
    5: (0.0,     5.0,  78.0),  # P6 - Gray/White (Xám trắng)
    6: (14.5,   88.0,  82.0),  # P7 - Brown (Nâu)
    7: (88.0,  108.0,  84.0),  # P8 - Cyan (Xanh cung)
}

COLOR_NAMES_VI = {
    0: "Xanh lam",
    1: "Cam",
    2: "Đỏ",
    3: "Vàng",
    4: "Xanh lá",
    5: "Xám trắng",
    6: "Nâu",
    7: "Xanh cung",
}

COLOR_HEX = {
    0: "#60a5fa",
    1: "#fb923c",
    2: "#ef4444",
    3: "#facc15",
    4: "#4ade80",
    5: "#d1d5db",
    6: "#b45309",
    7: "#22d3ee",
}

# Danh sách tên máy (AI) chuẩn trong AOE 1 để tự động sửa lỗi chính tả OCR nếu đấu với máy
KNOWN_AI_NAMES = [
    "Nabonidus", "Hyon", "Zobdas", "Keiko", "Syphax", "Amenophis",
    "Hamilcar Barca", "Erythrus", "Hippocrates", "Enmerkar", "Tudhalyas",
    "Gilgamesh", "Mithridates", "Astyages", "Marcus Aurelius", "Himiko",
    "Cleopatra", "Pericles", "Hammurabi", "Ashurbanipal", "Minos",
    "Suppiluliumas", "Hiram", "Sargon", "Cyrus", "Tang", "Jimmu",
    "Dangun", "Caesar", "Hannibal", "Zenobia", "Alexander"
]


def normalize_ocr_for_civ(s: str) -> str:
    s = s.lower()
    s = s.replace("1", "l").replace("!", "i").replace("|", "l").replace(")", "b").replace("(", "c")
    s = s.replace("0", "o").replace("rn", "m").replace("tn", "m").replace("tl", "m").replace("ll", "l")
    s = s.replace("q", "g").replace("v", "y").replace("j", "y")
    return "".join(ch for ch in s if ch.isalpha())


NORM_CIV_TARGETS = [
    (full, short, exp_w, normalize_ocr_for_civ(full), full.lower())
    for full, short, exp_w in CIV_LIST
]


def build_civ_templates():
    templates = {}
    font = None
    for font_path in ["C:/Windows/Fonts/arialbd.ttf", "C:/Windows/Fonts/arial.ttf"]:
        if os.path.exists(font_path):
            try:
                font = ImageFont.truetype(font_path, 12)
                break
            except Exception:
                pass
    if font is None:
        return templates

    for full_name, _, _ in CIV_LIST:
        img = Image.new("L", (110, 24), 0)
        draw = ImageDraw.Draw(img)
        draw.text((0, 2), full_name, fill=255, font=font)
        arr = np.array(img)
        ys, xs = np.where(arr > 80)
        if len(xs) == 0:
            continue
        patch = arr[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
        new_w = max(1, int(round(patch.shape[1] * (12.0 / patch.shape[0]))))
        resized = cv2.resize(patch, (new_w, 12), interpolation=cv2.INTER_AREA)
        canvas = np.zeros((12, 90), dtype=np.float32)
        w_clip = min(90, new_w)
        canvas[:, :w_clip] = resized[:, :w_clip] / 255.0
        templates[full_name] = (canvas, new_w)
    return templates


CIV_TEMPLATES = build_civ_templates()


# ==============================================================================
# 2. BỘ NHẬN DIỆN TRỰC TIẾP BẢNG DIPLOMACY TRÊN MÀN HÌNH GAME
# ==============================================================================
class DiplomacyScanner:
    def __init__(self):
        self.last_dialog_signature = None
        self.last_scan_time = 0.0

    @staticmethod
    def find_diplomacy_box(img_bgr: np.ndarray):
        """
        Dò tìm khung cửa sổ DIPLOMACY ở chính giữa màn hình với tỉ lệ chuẩn 468:301 (~1.555).
        Hoạt động trên mọi độ phân giải (1024x768, 1366x768, 1600x900, 1920x1080, 2K, 4K)
        và mọi giao diện (Classic Tan / Dark Stone).
        """
        if img_bgr is None or img_bgr.size == 0:
            return None, 0.0

        h, w = img_bgr.shape[:2]
        if w < 600 or h < 400:
            return None, 0.0

        gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
        sobelx = np.abs(cv2.Sobel(gray, cv2.CV_32F, 1, 0, ksize=3))
        sobely = np.abs(cv2.Sobel(gray, cv2.CV_32F, 0, 1, ksize=3))

        cx, cy = w / 2.0, h / 2.0
        best_score = -1.0
        best_box = None

        # Khung Diplomacy luôn nằm tâm màn hình với bán rộng từ 14%..42% chiều ngang màn hình
        for hw in range(int(w * 0.14), int(w * 0.42), max(1, int(w / 1000))):
            hh = int(round(hw * (301.0 / 468.0)))
            x1, x2 = int(round(cx - hw)), int(round(cx + hw))
            y1, y2 = int(round(cy - hh)), int(round(cy + hh))
            if y1 < 2 or y2 >= h - 2 or x1 < 2 or x2 >= w - 2:
                continue

            left_line = float(np.mean(sobelx[y1:y2, x1 - 1:x1 + 2]))
            right_line = float(np.mean(sobelx[y1:y2, x2 - 1:x2 + 2]))
            top_line = float(np.mean(sobely[y1 - 1:y1 + 2, x1:x2]))
            bot_line = float(np.mean(sobely[y2 - 1:y2 + 2, x1:x2]))

            score = (
                min(left_line, right_line) * 2.0
                + min(top_line, bot_line) * 2.0
                + (left_line + right_line + top_line + bot_line) * 0.5
            )
            if score > best_score:
                best_score = score
                best_box = (x1, y1, x2, y2)

        if best_box is None or best_score < 480.0:
            return None, best_score

        # Tinh chỉnh ±2px quanh best_box
        bx1, by1, bx2, by2 = best_box
        hw_base = (bx2 - bx1) // 2
        for hw in range(max(50, hw_base - 3), hw_base + 4):
            hh = int(round(hw * (301.0 / 468.0)))
            x1, x2 = int(round(cx - hw)), int(round(cx + hw))
            y1, y2 = int(round(cy - hh)), int(round(cy + hh))
            if y1 < 2 or y2 >= h - 2 or x1 < 2 or x2 >= w - 2:
                continue
            left_line = float(np.mean(sobelx[y1:y2, x1 - 1:x1 + 2]))
            right_line = float(np.mean(sobelx[y1:y2, x2 - 1:x2 + 2]))
            top_line = float(np.mean(sobely[y1 - 1:y1 + 2, x1:x2]))
            bot_line = float(np.mean(sobely[y2 - 1:y2 + 2, x1:x2]))
            score = (
                min(left_line, right_line) * 2.0
                + min(top_line, bot_line) * 2.0
                + (left_line + right_line + top_line + bot_line) * 0.5
            )
            if score > best_score:
                best_score = score
                best_box = (x1, y1, x2, y2)

        return best_box, best_score

    @staticmethod
    def verify_is_diplomacy_dialog(norm_624x400: np.ndarray) -> bool:
        """
        Kiểm tra chắc chắn 100% đây là cửa sổ DIPLOMACY:
        1. Tiêu đề 'DIPLOMACY' chữ trắng ở (x: 230..400, y: 6..32)
        2. Nút 'OK' chữ vàng ở góc dưới trái (x: 85..130, y: 370..394)
        3. Tiêu đề cột 'Name' & 'Civilization' ở y: 54..72
        """
        # 1. Check tiêu đề DIPLOMACY chữ trắng
        title_crop = norm_624x400[6:32, 230:400]
        min_t = np.min(title_crop, axis=2).astype(np.float32)
        max_t = np.max(title_crop, axis=2).astype(np.float32)
        white_title_px = np.sum((min_t > 165) & ((max_t - min_t) < 45))
        if white_title_px < 120:
            return False

        # 2. Check chữ 'OK' màu vàng ở nút dưới bên trái (y: 370..395, x: 82..135)
        ok_crop = norm_624x400[370:395, 82:135]
        b_ok, g_ok, r_ok = cv2.split(ok_crop)
        yellow_ok_px = np.sum((r_ok > 150) & (g_ok > 140) & (b_ok < 100) & ((r_ok.astype(np.int16) - b_ok.astype(np.int16)) > 70))
        if yellow_ok_px < 15:
            return False

        # 3. Check hàng tiêu đề cột 'Name' / 'Civilization' (y: 54..72, x: 10..230)
        hdr_crop = norm_624x400[54:72, 10:230]
        min_h = np.min(hdr_crop, axis=2).astype(np.float32)
        max_h = np.max(hdr_crop, axis=2).astype(np.float32)
        white_hdr_px = np.sum((min_h > 160) & ((max_h - min_h) < 50))
        if white_hdr_px < 40:
            return False

        return True

    @staticmethod
    def compute_dialog_signature(norm_624x400: np.ndarray) -> bytes:
        roi = norm_624x400[80:320, 135:410]
        small = cv2.resize(roi, (32, 24), interpolation=cv2.INTER_AREA)
        gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
        return (gray > np.median(gray)).tobytes()

    @staticmethod
    def extract_ribbon_hsv(norm_624x400: np.ndarray, row_idx: int):
        yc = int(round(95.0 + row_idx * 29.8))
        banner_crop = norm_624x400[yc - 10:yc + 10, 15:120]
        hsv_b = cv2.cvtColor(banner_crop, cv2.COLOR_BGR2HSV)
        # Loại bỏ chữ trắng (S < 45 & V > 185) và bóng đen (V < 50)
        mask = (hsv_b[:, :, 2] >= 50) & ~((hsv_b[:, :, 1] < 45) & (hsv_b[:, :, 2] > 185))
        if not np.any(mask):
            return (0.0, 0.0, 75.0)
        pts = hsv_b[mask]
        hist = cv2.calcHist([hsv_b], [0], mask.astype(np.uint8), [180], [0, 180])
        dom_h = float(np.argmax(hist))
        med_s = float(np.median(pts[:, 1]))
        med_v = float(np.median(pts[:, 2]))
        return (dom_h, med_s, med_v)

    @staticmethod
    def ribbon_hsv_distance(feat, color_idx: int) -> float:
        h_val, s_val, v_val = feat
        th, ts, tv = AOE_RIBBON_HSV[color_idx]
        # Màu 5 (Xám trắng) có độ bão hòa S rất thấp (< 25)
        if color_idx == 5:
            if s_val < 30:
                return abs(s_val - ts) * 0.5 + abs(v_val - tv) * 0.3
            return 250.0 + s_val * 2.0
        # Nếu thực tế ảnh có S rất thấp (< 22) thì phạt nặng các màu có sắc độ
        if s_val < 22:
            return 250.0
        dh = min(abs(h_val - th), 180.0 - abs(h_val - th))
        ds = abs(s_val - ts)
        dv = abs(v_val - tv)
        return dh * 2.8 + ds * 0.85 + dv * 0.5

    @classmethod
    def assign_player_colors(cls, hsv_features):
        n = len(hsv_features)
        if n == 0:
            return []
        best_perm = None
        best_cost = float("inf")
        for perm in itertools.permutations(range(8), min(n, 8)):
            cost = sum(cls.ribbon_hsv_distance(hsv_features[i], perm[i]) for i in range(len(perm)))
            if cost < best_cost:
                best_cost = cost
                best_perm = list(perm)
        return best_perm or list(range(n))

    @staticmethod
    def run_windows_ocr_batch(multi_canvas_bgr: np.ndarray):
        """
        Sử dụng trực tiếp Windows.Media.Ocr có sẵn trên mọi máy Windows 10/11
        (Không cần cài đặt Tesseract-OCR hay thư viện ngoài).
        """
        tmp_fd, tmp_path = tempfile.mkstemp(suffix=".png", prefix="aoe_diplomacy_")
        os.close(tmp_fd)
        try:
            cv2.imwrite(tmp_path, multi_canvas_bgr)
            ps_script = f"""
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
Add-Type -AssemblyName System.Runtime.WindowsRuntime
$null = [Windows.Media.Ocr.OcrEngine, Windows.Foundation, ContentType = WindowsRuntime]
$null = [Windows.Graphics.Imaging.BitmapDecoder, Windows.Foundation, ContentType = WindowsRuntime]

function Await($WinRtTask, $ResultType) {{
    $asTaskGeneric = ([System.WindowsRuntimeSystemExtensions].GetMethods() | Where-Object {{ $_.Name -eq 'AsTask' -and $_.GetParameters().Count -eq 1 -and $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperation`1' }})[0]
    $asTask = $asTaskGeneric.MakeGenericMethod($ResultType)
    $netTask = $asTask.Invoke($null, @($WinRtTask))
    $netTask.Wait(-1) | Out-Null
    return $netTask.Result
}}

$lang = New-Object Windows.Globalization.Language("en-US")
$engine = [Windows.Media.Ocr.OcrEngine]::TryCreateFromLanguage($lang)
if ($null -eq $engine) {{
    $engine = [Windows.Media.Ocr.OcrEngine]::TryCreateFromUserProfileLanguages()
}}
$fs = [System.IO.File]::OpenRead("{tmp_path.replace('\\', '\\\\')}")
$stream = [System.IO.WindowsRuntimeStreamExtensions]::AsRandomAccessStream($fs)
$decoder = Await ([Windows.Graphics.Imaging.BitmapDecoder]::CreateAsync($stream)) ([Windows.Graphics.Imaging.BitmapDecoder])
$bitmap = Await ($decoder.GetSoftwareBitmapAsync()) ([Windows.Graphics.Imaging.SoftwareBitmap])
$result = Await ($engine.RecognizeAsync($bitmap)) ([Windows.Media.Ocr.OcrResult])
$words = @()
foreach ($line in $result.Lines) {{
    foreach ($w in $line.Words) {{
        $words += @{{
            text = $w.Text
            x = [int]$w.BoundingRect.X
            y = [int]$w.BoundingRect.Y
            w = [int]$w.BoundingRect.Width
        }}
    }}
}}
$stream.Dispose()
$fs.Dispose()
ConvertTo-Json -InputObject @($words) -Depth 3 -Compress
"""
            startupinfo = None
            if os.name == "nt":
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW

            res = subprocess.run(
                ["powershell", "-NoProfile", "-Command", ps_script],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=10,
                startupinfo=startupinfo,
            )
            stdout = (res.stdout or "").strip()
            if not stdout:
                return []
            data = json.loads(stdout)
            if isinstance(data, dict):
                return [data]
            return data if isinstance(data, list) else []
        except Exception as e:
            print("[OCR Warning]:", e)
            return []
        finally:
            try:
                os.remove(tmp_path)
            except OSError:
                pass

    @staticmethod
    def match_civ_for_row(norm_624x400: np.ndarray, row_idx: int, ocr_civ_candidates, w_obs: int):
        scores = {full: 0.0 for full, _, _ in CIV_LIST}

        # 1. Điểm tương đồng chuỗi từ 3 mức phơi sáng OCR + điểm thưởng prefix 2 ký tự đầu duy nhất
        for full, short, exp_w, norm_target, raw_target in NORM_CIV_TARGETS:
            if w_obs > 0:
                w_diff = abs(w_obs - exp_w)
                scores[full] += max(0.0, 1.0 - w_diff / 22.0) * 0.45

            best_str_sim = 0.0
            prefix_bonus = 0.0
            for txt in ocr_civ_candidates:
                if not txt:
                    continue
                clean_raw = "".join(ch for ch in txt.lower() if ch.isalpha())
                clean_norm = normalize_ocr_for_civ(txt)
                if not clean_raw:
                    continue

                sim1 = difflib.SequenceMatcher(None, clean_raw, raw_target).ratio()
                sim2 = difflib.SequenceMatcher(None, clean_norm, norm_target).ratio()
                sim3 = 0.0
                if len(clean_norm) >= 3 and (clean_norm in norm_target or norm_target in clean_norm):
                    sim3 = 0.65 + 0.35 * (min(len(clean_norm), len(norm_target)) / max(len(clean_norm), len(norm_target)))

                # Kiểm tra 2 chữ cái đầu (Mỗi quân trong 16 quân AOE có 2 chữ cái đầu hoàn toàn khác nhau!)
                if len(clean_raw) >= 2 and clean_raw[:2] == raw_target[:2]:
                    prefix_bonus = max(prefix_bonus, 0.45)
                elif len(clean_norm) >= 2 and clean_norm[:2] == norm_target[:2]:
                    prefix_bonus = max(prefix_bonus, 0.35)

                best_str_sim = max(best_str_sim, sim1, sim2, sim3)

            scores[full] += best_str_sim * 1.6 + prefix_bonus

        # 2. Điểm tương quan mẫu ảnh (Template Matching 2D Arial Bold)
        if CIV_TEMPLATES:
            yc = int(round(95.0 + row_idx * 29.8))
            crop = norm_624x400[yc - 9:yc + 9, 139:235]
            min_rgb = np.min(crop, axis=2).astype(np.float32)
            max_rgb = np.max(crop, axis=2).astype(np.float32)
            val = np.clip((min_rgb - (max_rgb - min_rgb) * 0.6 - 110.0) / 110.0, 0.0, 1.0)
            mask = val > 0.35
            col_counts = np.sum(mask, axis=0)
            valid_xs = np.where(col_counts >= 1)[0]
            if len(valid_xs) >= 8:
                x_min, x_max = valid_xs[0], valid_xs[-1]
                row_counts = np.sum(mask[:, x_min:x_max + 1], axis=1)
                valid_ys = np.where(row_counts >= 2)[0]
                if len(valid_ys) >= 4:
                    y_min, y_max = valid_ys[0], valid_ys[-1]
                    patch = val[y_min:y_max + 1, x_min:x_max + 1]
                    new_w = max(1, int(round(patch.shape[1] * (12.0 / max(patch.shape[0], 9.0)))))
                    resized = cv2.resize(patch, (new_w, 12), interpolation=cv2.INTER_LINEAR)
                    feat = np.zeros((12, 90), dtype=np.float32)
                    w_clip = min(90, new_w)
                    feat[:, :w_clip] = resized[:, :w_clip]

                    for full, _, _ in CIV_LIST:
                        if full not in CIV_TEMPLATES:
                            continue
                        tmpl, _ = CIV_TEMPLATES[full]
                        max_corr = -1.0
                        for dx in range(-2, 3):
                            if dx >= 0:
                                a = feat[:, dx:]
                                b_t = tmpl[:, :a.shape[1]]
                            else:
                                b_t = tmpl[:, -dx:]
                                a = feat[:, :b_t.shape[1]]
                            num = float(np.sum((a - a.mean()) * (b_t - b_t.mean())))
                            den = float(np.sqrt(np.sum((a - a.mean()) ** 2) * np.sum((b_t - b_t.mean()) ** 2))) + 1e-6
                            corr = num / den
                            if corr > max_corr:
                                max_corr = corr
                        scores[full] += max(0.0, max_corr) * 0.75

        best_full = max(scores, key=lambda k: scores[k])
        short_map = {full: short for full, short, _ in CIV_LIST}
        return best_full, short_map[best_full]

    @staticmethod
    def clean_and_match_player_name(ocr_name_candidates, row_idx: int, streamer_name: str, known_players=None):
        # Hàng đầu tiên (Row 0) trong bảng Diplomacy luôn là người chơi mở bảng (Streamer)
        if row_idx == 0 and streamer_name and streamer_name.strip():
            return streamer_name.strip()

        def normalize_name_token(s: str) -> str:
            rep = {"2": "z", "0": "o", "1": "i", "4": "a", "6": "e", "5": "s", "$": "s", "@": "a"}
            out = []
            for ch in s.lower():
                ch = rep.get(ch, ch)
                if ch.isascii() and ch.isalpha():
                    out.append(ch)
            return "".join(out)

        # Chấm điểm độ sạch của từng ứng viên OCR (ưu tiên chữ cái ASCII chuẩn, phạt ký tự lạ)
        best_raw = ""
        best_quality = -1e9
        for exp_idx, raw in enumerate(ocr_name_candidates):
            if not raw:
                continue
            cleaned = "".join(ch for ch in raw if ch.isascii() and (ch.isalnum() or ch in " _-")).strip(" _-")
            if len(cleaned) < 2:
                continue
            weird_count = sum(1 for ch in raw if not (ch.isascii() and (ch.isalnum() or ch in " _-")))
            exp_bonus = 2.0 if exp_idx == 0 else (1.0 if exp_idx == 1 else 0.0)
            quality = sum(1.0 for ch in cleaned if ch.isalpha()) - weird_count * 2.5 + exp_bonus
            if quality > best_quality:
                best_quality = quality
                best_raw = cleaned

        # So khớp mờ (fuzzy match) với danh sách Player đã biết + tên AI chuẩn của AOE
        pool = list(KNOWN_AI_NAMES)
        if known_players:
            for p in known_players:
                pname = p.get("name") if isinstance(p, dict) else str(p)
                if pname and pname not in pool:
                    pool.append(pname)
        if streamer_name and streamer_name not in pool:
            pool.append(streamer_name)

        all_candidates = [c for c in ocr_name_candidates if c]
        if best_raw:
            all_candidates.insert(0, best_raw)

        best_match_name = None
        best_sim = 0.0
        for cand in all_candidates:
            cand_alpha = normalize_name_token(cand)
            if len(cand_alpha) < 2:
                continue
            for target in pool:
                target_alpha = normalize_name_token(target)
                sim = difflib.SequenceMatcher(None, cand_alpha, target_alpha).ratio()
                if len(cand_alpha) >= 4 and (target_alpha.endswith(cand_alpha) or target_alpha.startswith(cand_alpha)):
                    sim = max(sim, 0.85)
                if sim > best_sim:
                    best_sim = sim
                    best_match_name = target

        if best_match_name and best_sim >= 0.60:
            return best_match_name

        return best_raw if best_raw else f"Player {row_idx + 1}"

    def parse_diplomacy_from_image(self, img_bgr: np.ndarray, streamer_name: str = "XO", known_players=None, force: bool = False):
        """
        Trích xuất toàn bộ thông tin từ ảnh chụp màn hình có mở bảng DIPLOMACY.
        Trả về dict kết quả hoặc None nếu không phải màn hình DIPLOMACY.
        """
        box, box_score = self.find_diplomacy_box(img_bgr)
        if box is None:
            return None

        x1, y1, x2, y2 = box
        crop = img_bgr[y1:y2, x1:x2]
        norm = cv2.resize(crop, (624, 400), interpolation=cv2.INTER_CUBIC)

        if not self.verify_is_diplomacy_dialog(norm):
            return None

        sig = self.compute_dialog_signature(norm)
        if not force and self.last_dialog_signature == sig and (time.time() - self.last_scan_time < 15.0):
            return {"status": "unchanged"}

        self.last_dialog_signature = sig
        self.last_scan_time = time.time()

        # Tính gradient để nhận diện dấu 'X' trong 3 cột Ally / Neutral / Enemy
        gray = cv2.cvtColor(norm, cv2.COLOR_BGR2GRAY)
        edges = np.abs(cv2.Sobel(gray, cv2.CV_32F, 1, 0, ksize=3)) + np.abs(cv2.Sobel(gray, cv2.CV_32F, 0, 1, ksize=3))

        active_rows = []
        multi_canvas = np.full((8 * 70, 2300, 3), 255, dtype=np.uint8)

        # Đặt thêm vùng bảng điểm F4 góc dưới phải màn hình (nếu có) vào x=1820..2280 để hỗ trợ đọc tên người chơi nền đen
        h_full, w_full = img_bgr.shape[:2]
        f4_crop = img_bgr[int(h_full * 0.58):int(h_full * 0.85), int(w_full * 0.82):w_full]
        if f4_crop.size > 0:
            f4_up = cv2.resize(f4_crop, (440, 520), interpolation=cv2.INTER_CUBIC)
            max_f4 = np.max(f4_up, axis=2).astype(np.float32)
            a_f4 = np.clip((max_f4 - 48.0) / 110.0, 0.0, 1.0)
            ink_f4 = cv2.cvtColor((255.0 * (1.0 - a_f4)).astype(np.uint8), cv2.COLOR_GRAY2BGR)
            multi_canvas[10:530, 1830:2270] = ink_f4

        for r in range(8):
            yc = int(round(95.0 + r * 29.8))
            civ_crop = norm[yc - 9:yc + 9, 140:235]
            min_c = np.min(civ_crop, axis=2).astype(np.float32)
            max_c = np.max(civ_crop, axis=2).astype(np.float32)
            wh_c = min_c - 0.55 * (max_c - min_c)
            bg_c = float(np.percentile(wh_c, 55))
            mask_c = wh_c > max(bg_c + 20.0, 140.0)
            if np.sum(mask_c) < 12:
                continue

            col_counts = np.sum(mask_c, axis=0)
            valid_xs = np.where(col_counts >= 1)[0]
            w_obs = int(valid_xs[-1] - valid_xs[0] + 1) if len(valid_xs) > 0 else 0

            # Xác định phe (ALLY vs ENEMY)
            if r == 0:
                stance = "ALLY"
            else:
                s_ally = float(np.mean(edges[yc - 6:yc + 6, 248:262]))
                s_neut = float(np.mean(edges[yc - 6:yc + 6, 317:331]))
                s_enem = float(np.mean(edges[yc - 6:yc + 6, 387:401]))
                if s_ally > s_neut and s_ally > s_enem and s_ally > 90.0:
                    stance = "ALLY"
                else:
                    stance = "ENEMY"

            hsv_feat = self.extract_ribbon_hsv(norm, r)
            active_rows.append({
                "row_idx": r,
                "stance": stance,
                "hsv_feat": hsv_feat,
                "w_obs": w_obs,
            })

            # Vẽ 3 mức phơi sáng cho Name & Civilization lên multi_canvas để OCR 1 lần duy nhất
            for x_start, x_end, base_x in [(12, 136, 20), (140, 238, 320)]:
                cell = norm[yc - 11:yc + 11, x_start:x_end]
                up1 = cv2.resize(cell, (0, 0), fx=2.5, fy=2.5, interpolation=cv2.INTER_LANCZOS4)
                min1 = np.min(up1, axis=2).astype(np.float32)
                max1 = np.max(up1, axis=2).astype(np.float32)
                wh1 = min1 - 0.55 * (max1 - min1)
                bg1 = float(np.percentile(wh1, 60))

                # Phơi sáng 1: Mềm (giữ nét mảnh)
                a1 = np.clip((wh1 - (bg1 + 14.0)) / 42.0, 0.0, 1.0)
                ink1 = cv2.cvtColor((255.0 * (1.0 - a1)).astype(np.uint8), cv2.COLOR_GRAY2BGR)

                # Phơi sáng 2: Đậm + nối nét ngang
                a2 = np.clip((wh1 - (bg1 + 22.0)) / 45.0, 0.0, 1.0)
                kernel = np.array([[0.2, 1.0, 0.2]], dtype=np.float32)
                a2_dil = np.clip(cv2.filter2D(a2, -1, kernel), 0.0, 1.0)
                ink2 = cv2.cvtColor((255.0 * (1.0 - a2_dil)).astype(np.uint8), cv2.COLOR_GRAY2BGR)

                # Phơi sáng 3: Khử bóng đổ (Shadow subtraction)
                b_ch, g_ch, r_ch = cv2.split(up1)
                lum = (0.2 * r_ch + 0.4 * g_ch + 0.4 * b_ch).astype(np.float32)
                shadow = np.roll(np.roll(lum, 2, axis=0), 2, axis=1)
                contrast = lum - 0.5 * shadow
                bg3 = float(np.percentile(contrast, 65))
                a3 = np.clip((contrast - (bg3 + 15.0)) / 45.0, 0.0, 1.0)
                ink3 = cv2.cvtColor((255.0 * (1.0 - a3)).astype(np.uint8), cv2.COLOR_GRAY2BGR)

                hp, wp = ink1.shape[:2]
                multi_canvas[r * 70 + 8:r * 70 + 8 + hp, base_x:base_x + wp] = ink1
                multi_canvas[r * 70 + 8:r * 70 + 8 + hp, base_x + 600:base_x + 600 + wp] = ink2
                multi_canvas[r * 70 + 8:r * 70 + 8 + hp, base_x + 1200:base_x + 1200 + wp] = ink3

        if not active_rows:
            return None

        # Gán màu chuẩn không trùng lặp cho tất cả người chơi trong trận
        assigned_colors = self.assign_player_colors([item["hsv_feat"] for item in active_rows])
        for item, color_id in zip(active_rows, assigned_colors):
            item["color_id"] = color_id

        # Chạy Windows OCR trên toàn bộ các dòng
        ocr_words = self.run_windows_ocr_batch(multi_canvas)

        for item in active_rows:
            r = item["row_idx"]
            row_y_min, row_y_max = r * 70, (r + 1) * 70
            name_cands = [[], [], []]
            civ_cands = [[], [], []]
            for w in ocr_words:
                wy = w.get("y", -1)
                if row_y_min <= wy <= row_y_max:
                    wx = w.get("x", 0)
                    exp_idx = wx // 600
                    if exp_idx > 2:
                        continue
                    rel_x = wx % 600
                    if rel_x < 300:
                        name_cands[exp_idx].append((rel_x, str(w.get("text", ""))))
                    else:
                        civ_cands[exp_idx].append((rel_x, str(w.get("text", ""))))

            name_strs = [" ".join(t for _, t in sorted(cand)) for cand in name_cands if cand]
            civ_strs = [" ".join(t for _, t in sorted(cand)) for cand in civ_cands if cand]

            full_civ, short_civ = self.match_civ_for_row(norm, r, civ_strs, item["w_obs"])
            player_name = self.clean_and_match_player_name(name_strs, r, streamer_name, known_players)

            item["name"] = player_name
            item["civ_full"] = full_civ
            item["civ_short"] = short_civ

        # Chia thành Team Đỏ (Bản thân + Đồng minh ALLY) và Team Xanh (Đối thủ ENEMY)
        red_rows = [item for item in active_rows if item["stance"] == "ALLY"]
        blue_rows = [item for item in active_rows if item["stance"] != "ALLY"]

        # Trường hợp đầu trận chưa kịp tích Ally (tất cả đều là ENEMY trừ Row 0) và có >= 4 người chơi:
        if len(red_rows) == 1 and len(blue_rows) >= 3 and len(active_rows) % 2 == 0:
            half = len(active_rows) // 2
            red_rows = active_rows[:half]
            blue_rows = active_rows[half:]

        return {
            "status": "ok",
            "redPlayers": [r["name"] for r in red_rows],
            "redCivs": [r["civ_short"] for r in red_rows],
            "redColors": [r["color_id"] for r in red_rows],
            "bluePlayers": [r["name"] for r in blue_rows],
            "blueCivs": [r["civ_short"] for r in blue_rows],
            "blueColors": [r["color_id"] for r in blue_rows],
            "allRows": active_rows,
        }


# ==============================================================================
# 3. GIAO DIỆN DESKTOP APP (TKINTER DARK THEME) CHO NGƯỜI CHƠI
# ==============================================================================
def get_settings_path() -> Path:
    appdata = os.environ.get("APPDATA") or os.path.expanduser("~")
    folder = Path(appdata) / "bangquanaoe"
    folder.mkdir(parents=True, exist_ok=True)
    return folder / "settings.json"


def load_user_settings() -> dict:
    path = get_settings_path()
    default_cfg = {
        "server_url": "http://localhost:3000",
        "player_name": "XO",
        "player_password": "111",
        "auto_scan": True,
    }
    if path.exists():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            default_cfg.update(data)
        except Exception:
            pass
    return default_cfg


def save_user_settings(cfg: dict):
    try:
        get_settings_path().write_text(json.dumps(cfg, indent=2, ensure_ascii=False), encoding="utf-8")
    except Exception as e:
        print("Không thể lưu settings:", e)


class AOETrackerApp:
    def __init__(self, root):
        import tkinter as tk
        from tkinter import ttk, filedialog, messagebox

        self.tk = tk
        self.ttk = ttk
        self.filedialog = filedialog
        self.messagebox = messagebox
        self.root = root
        self.root.title(f"Tool Bảng Quân AOE (bangquanaoe) {APP_VERSION} - Tự Động Quét Diplomacy")
        self.root.geometry("680x640")
        self.root.configure(bg="#090d16")
        self.root.resizable(True, True)

        self.settings = load_user_settings()
        self.scanner = DiplomacyScanner()
        self.is_logged_in = False
        self.known_players = []
        self.current_match = None
        self.running = True

        self._build_ui()
        self.threading_loop = threading.Thread(target=self._background_worker, daemon=True)
        self.threading_loop.start()

        # Tự động kết nối nếu đã lưu thông tin từ lần trước
        if self.settings.get("player_name") and self.settings.get("player_password"):
            self.root.after(400, self.login_and_start)

    def _build_ui(self):
        tk = self.tk

        # Header
        hdr = tk.Frame(self.root, bg="#111827", pady=10, padx=14, highlightthickness=1, highlightbackground="#f59e0b")
        hdr.pack(fill="x", padx=12, pady=(12, 8))

        title_lbl = tk.Label(
            hdr,
            text="⚔️ TOOL BẢNG QUÂN AOE (BANGQUANAOE) - AUTO DIPLOMACY",
            font=("Segoe UI", 12, "bold"),
            fg="#fbbf24",
            bg="#111827",
        )
        title_lbl.pack(anchor="w")

        sub_lbl = tk.Label(
            hdr,
            text="Tự động nhận diện Bảng Quân & Màu khi mở Diplomacy (F2) trong game • Không cần cài đặt Tesseract hay sửa file config",
            font=("Segoe UI", 8),
            fg="#94a3b8",
            bg="#111827",
        )
        sub_lbl.pack(anchor="w", pady=(2, 0))

        # Khung Cấu hình & Đăng nhập
        login_frame = tk.LabelFrame(
            self.root,
            text=" 1. Kết Nối Server & Tài Khoản Player ",
            font=("Segoe UI", 9, "bold"),
            fg="#38bdf8",
            bg="#0f172a",
            padx=12,
            pady=10,
        )
        login_frame.pack(fill="x", padx=12, pady=6)

        tk.Label(login_frame, text="Server URL (Render/Web):", font=("Segoe UI", 9), fg="#cbd5e1", bg="#0f172a").grid(
            row=0, column=0, sticky="w", pady=4
        )
        self.server_url_var = tk.StringVar(value=self.settings.get("server_url", "http://localhost:3000"))
        tk.Entry(
            login_frame,
            textvariable=self.server_url_var,
            font=("Consolas", 9),
            bg="#1e293b",
            fg="#f8fafc",
            insertbackground="#f8fafc",
            width=48,
            relief="flat",
        ).grid(row=0, column=1, columnspan=3, sticky="we", padx=(8, 0), pady=4, ipady=3)

        tk.Label(login_frame, text="Tên Player (Streamer):", font=("Segoe UI", 9), fg="#cbd5e1", bg="#0f172a").grid(
            row=1, column=0, sticky="w", pady=4
        )
        self.player_name_var = tk.StringVar(value=self.settings.get("player_name", "XO"))
        tk.Entry(
            login_frame,
            textvariable=self.player_name_var,
            font=("Segoe UI", 9, "bold"),
            bg="#1e293b",
            fg="#fbbf24",
            insertbackground="#fbbf24",
            width=18,
            relief="flat",
        ).grid(row=1, column=1, sticky="w", padx=(8, 12), pady=4, ipady=3)

        tk.Label(login_frame, text="Mật khẩu:", font=("Segoe UI", 9), fg="#cbd5e1", bg="#0f172a").grid(
            row=1, column=2, sticky="e", pady=4
        )
        self.player_pass_var = tk.StringVar(value=self.settings.get("player_password", "111"))
        tk.Entry(
            login_frame,
            textvariable=self.player_pass_var,
            show="*",
            font=("Segoe UI", 9),
            bg="#1e293b",
            fg="#f8fafc",
            insertbackground="#f8fafc",
            width=14,
            relief="flat",
        ).grid(row=1, column=3, sticky="we", padx=(8, 0), pady=4, ipady=3)

        btn_row = tk.Frame(login_frame, bg="#0f172a")
        btn_row.grid(row=2, column=0, columnspan=4, sticky="we", pady=(8, 2))

        self.login_btn = tk.Button(
            btn_row,
            text="🔑 Lưu & Kết Nối Ngay",
            command=self.login_and_start,
            font=("Segoe UI", 9, "bold"),
            bg="#f59e0b",
            fg="#090d16",
            activebackground="#d97706",
            relief="flat",
            padx=12,
            pady=4,
            cursor="hand2",
        )
        self.login_btn.pack(side="left")

        self.copy_obs_btn = tk.Button(
            btn_row,
            text="📺 Copy Link OBS Overlay",
            command=self.copy_obs_link,
            font=("Segoe UI", 9, "bold"),
            bg="#312e81",
            fg="#e0e7ff",
            activebackground="#4338ca",
            relief="flat",
            padx=10,
            pady=4,
            cursor="hand2",
        )
        self.copy_obs_btn.pack(side="left", padx=8)

        self.open_web_btn = tk.Button(
            btn_row,
            text="🌐 Mở Trang Web Quản Lý",
            command=self.open_web_dashboard,
            font=("Segoe UI", 9),
            bg="#1e293b",
            fg="#cbd5e1",
            relief="flat",
            padx=10,
            pady=4,
            cursor="hand2",
        )
        self.open_web_btn.pack(side="left")

        self.auto_scan_var = tk.BooleanVar(value=bool(self.settings.get("auto_scan", True)))
        tk.Checkbutton(
            btn_row,
            text="Tự động quét Diplomacy",
            variable=self.auto_scan_var,
            font=("Segoe UI", 9, "bold"),
            fg="#4ade80",
            bg="#0f172a",
            selectcolor="#1e293b",
            activebackground="#0f172a",
            activeforeground="#4ade80",
        ).pack(side="right")

        # Khung Điều Khiển Trận Đấu & Quét Bảng Quân
        match_frame = tk.LabelFrame(
            self.root,
            text=" 2. Trạng Thái Quét & Điều Khiển Nhanh Kèo Đấu ",
            font=("Segoe UI", 9, "bold"),
            fg="#4ade80",
            bg="#0f172a",
            padx=12,
            pady=10,
        )
        match_frame.pack(fill="x", padx=12, pady=6)

        self.status_lbl = tk.Label(
            match_frame,
            text="⏳ Đang chờ kết nối tới Server...",
            font=("Segoe UI", 9, "bold"),
            fg="#fbbf24",
            bg="#0f172a",
        )
        self.status_lbl.pack(anchor="w")

        self.score_lbl = tk.Label(
            match_frame,
            text="Tỉ số hiện tại: Chưa có kèo LIVE",
            font=("Segoe UI", 10, "bold"),
            fg="#f8fafc",
            bg="#0f172a",
            pady=4,
        )
        self.score_lbl.pack(anchor="w")

        ctrl_row = tk.Frame(match_frame, bg="#0f172a")
        ctrl_row.pack(fill="x", pady=(4, 2))

        tk.Button(
            ctrl_row,
            text="🔴 Team Đỏ Thắng",
            command=lambda: self.set_current_winner("RED"),
            font=("Segoe UI", 9, "bold"),
            bg="#dc2626",
            fg="#ffffff",
            relief="flat",
            padx=10,
            pady=4,
            cursor="hand2",
        ).pack(side="left")

        tk.Button(
            ctrl_row,
            text="🔵 Team Xanh Thắng",
            command=lambda: self.set_current_winner("BLUE"),
            font=("Segoe UI", 9, "bold"),
            bg="#2563eb",
            fg="#ffffff",
            relief="flat",
            padx=10,
            pady=4,
            cursor="hand2",
        ).pack(side="left", padx=6)

        tk.Button(
            ctrl_row,
            text="🏁 Kết Thúc Kèo",
            command=self.finish_current_match,
            font=("Segoe UI", 9, "bold"),
            bg="#475569",
            fg="#ffffff",
            relief="flat",
            padx=10,
            pady=4,
            cursor="hand2",
        ).pack(side="left")

        tk.Button(
            ctrl_row,
            text="🖼️ Test Từ Ảnh Chụp...",
            command=self.test_from_image_file,
            font=("Segoe UI", 8, "bold"),
            bg="#334155",
            fg="#38bdf8",
            relief="flat",
            padx=8,
            pady=4,
            cursor="hand2",
        ).pack(side="right")

        tk.Button(
            ctrl_row,
            text="🔍 Quét Màn Hình Ngay",
            command=self.manual_scan_screen,
            font=("Segoe UI", 8, "bold"),
            bg="#065f46",
            fg="#a7f3d0",
            relief="flat",
            padx=8,
            pady=4,
            cursor="hand2",
        ).pack(side="right", padx=6)

        # Khung Hiển Thị Bảng Quân Vừa Quét & Nhật Ký Hoạt Động
        preview_frame = tk.LabelFrame(
            self.root,
            text=" 3. Bảng Quân Nhận Diện Gần Nhất & Nhật Ký (Log) ",
            font=("Segoe UI", 9, "bold"),
            fg="#fbbf24",
            bg="#0f172a",
            padx=12,
            pady=8,
        )
        preview_frame.pack(fill="both", expand=True, padx=12, pady=(6, 12))

        self.log_box = tk.Text(
            preview_frame,
            bg="#020617",
            fg="#e2e8f0",
            font=("Consolas", 9),
            relief="flat",
            height=14,
            padx=8,
            pady=8,
        )
        self.log_box.pack(fill="both", expand=True)
        self.log("✨ Chào mừng bạn đến với Tool Bảng Quân AOE (bangquanaoe) v4.0.0!")
        self.log("👉 Nhập Server URL, Tên Player & Mật khẩu rồi bấm 'Lưu & Kết Nối Ngay'.")
        self.log("👉 Trong khi chơi AOE, chỉ cần bấm Diplomacy (F2) là bảng quân và OBS Overlay sẽ tự động cập nhật!")

    def log(self, message: str):
        ts = time.strftime("%H:%M:%S")
        line = f"[{ts}] {message}\n"

        def _append():
            self.log_box.insert("end", line)
            self.log_box.see("end")

        self.root.after(0, _append)

    def get_api_endpoint(self) -> str:
        base = self.server_url_var.get().strip().rstrip("/")
        if not base.startswith("http"):
            base = "https://" + base
        if base.endswith("/api"):
            return base
        return base + "/api"

    def save_current_config(self):
        self.settings = {
            "server_url": self.server_url_var.get().strip().rstrip("/"),
            "player_name": self.player_name_var.get().strip(),
            "player_password": self.player_pass_var.get().strip(),
            "auto_scan": bool(self.auto_scan_var.get()),
        }
        save_user_settings(self.settings)

    def login_and_start(self):
        self.save_current_config()
        api_url = self.get_api_endpoint()
        name = self.settings["player_name"]
        pw = self.settings["player_password"]
        if not name or not pw:
            self.messagebox.showwarning("Thiếu thông tin", "Vui lòng nhập Tên Player và Mật khẩu!")
            return

        def _task():
            try:
                res = requests.post(
                    api_url,
                    json={
                        "action": "verifyPlayerLogin",
                        "playerName": name,
                        "password": pw,
                        "autoRegister": True,
                    },
                    timeout=12,
                )
                data = res.json()
                if data.get("status") == "success":
                    self.is_logged_in = True
                    canonical = data.get("playerName", name)
                    self.root.after(0, lambda: self.player_name_var.set(canonical))
                    self.root.after(
                        0,
                        lambda: self.status_lbl.config(
                            text=f"🟢 Đã kết nối ({canonical}) - Đang tự động theo dõi màn hình Diplomacy (F2)",
                            fg="#4ade80",
                        ),
                    )
                    self.log(f"✅ {data.get('message', 'Đăng nhập thành công!')} (Server: {api_url})")
                    self.refresh_initial_state()
                else:
                    self.is_logged_in = False
                    msg = data.get("message", "Đăng nhập thất bại!")
                    self.root.after(0, lambda: self.status_lbl.config(text=f"🔴 {msg}", fg="#f87171"))
                    self.log(f"❌ {msg}")
            except Exception as e:
                self.is_logged_in = False
                self.root.after(
                    0, lambda: self.status_lbl.config(text="🔴 Không kết nối được Server!", fg="#f87171")
                )
                self.log(f"❌ Lỗi kết nối Server ({api_url}): {e}")

        threading.Thread(target=_task, daemon=True).start()

    def refresh_initial_state(self):
        try:
            api_url = self.get_api_endpoint()
            name = self.player_name_var.get().strip()
            res = requests.get(f"{api_url}?action=getInitialData&streamer={name}", timeout=10)
            data = res.json()
            self.known_players = data.get("players", [])
            match = data.get("currentMatch")
            if match and str(match.get("streamerName", "")).lower() == name.lower() and match.get("status") == "LIVE":
                self.current_match = match
                self._update_score_label(match)
            else:
                self.current_match = None
                self.root.after(0, lambda: self.score_lbl.config(text="Tỉ số hiện tại: Chưa có kèo LIVE (Hãy bấm F2 Diplomacy trong game)"))
        except Exception:
            pass

    def _update_score_label(self, match: dict):
        if not match:
            return
        games = match.get("games", [])
        red_w = sum(1 for g in games if g.get("winner") == "RED")
        blue_w = sum(1 for g in games if g.get("winner") == "BLUE")
        mode = match.get("mode", "2v2")
        txt = f"🔥 Kèo {mode} Đang LIVE | Team Đỏ  {red_w} - {blue_w}  Team Xanh | Tổng số trận: {len(games)}"
        self.root.after(0, lambda: self.score_lbl.config(text=txt))

    def copy_obs_link(self):
        base = self.server_url_var.get().strip().rstrip("/")
        name = self.player_name_var.get().strip() or "XO"
        obs_url = f"{base}/overlay.html?streamer={name}"
        self.root.clipboard_clear()
        self.root.clipboard_append(obs_url)
        self.log(f"📋 Đã copy Link OBS Overlay vào Clipboard: {obs_url}")

    def open_web_dashboard(self):
        import webbrowser
        base = self.server_url_var.get().strip().rstrip("/")
        webbrowser.open(base)

    def _send_parsed_diplomacy_to_server(self, parsed: dict, allow_same_civ: bool = False):
        red_str = ", ".join(
            f"{p} [{c} - {COLOR_NAMES_VI.get(col, col)}]"
            for p, c, col in zip(parsed["redPlayers"], parsed["redCivs"], parsed["redColors"])
        )
        blue_str = ", ".join(
            f"{p} [{c} - {COLOR_NAMES_VI.get(col, col)}]"
            for p, c, col in zip(parsed["bluePlayers"], parsed["blueCivs"], parsed["blueColors"])
        )
        self.log(f"🎯 Đã quét bảng Diplomacy:")
        self.log(f"   🔴 Team Đỏ  : {red_str}")
        self.log(f"   🔵 Team Xanh: {blue_str}")

        api_url = self.get_api_endpoint()
        payload = {
            "action": "autoAddGame",
            "streamerName": self.player_name_var.get().strip(),
            "password": self.player_pass_var.get().strip(),
            "redPlayers": parsed["redPlayers"],
            "redCivs": parsed["redCivs"],
            "redColors": parsed["redColors"],
            "bluePlayers": parsed["bluePlayers"],
            "blueCivs": parsed["blueCivs"],
            "blueColors": parsed["blueColors"],
            "allowSameCiv": allow_same_civ,
        }
        try:
            res = requests.post(api_url, json=payload, timeout=15)
            data = res.json()
            self.log(f"   ☁️ Server phản hồi: {data.get('message', '')}")
            if data.get("match"):
                self.current_match = data["match"]
                self._update_score_label(data["match"])
        except Exception as e:
            self.log(f"   ❌ Lỗi gửi dữ liệu lên Server: {e}")

    def manual_scan_screen(self):
        def _task():
            try:
                pil_img = ImageGrab.grab()
                img_bgr = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)
                res = self.scanner.parse_diplomacy_from_image(
                    img_bgr,
                    streamer_name=self.player_name_var.get().strip(),
                    known_players=self.known_players,
                    force=True,
                )
                if not res or res.get("status") != "ok":
                    self.log("⚠️ Không tìm thấy bảng DIPLOMACY trên màn hình hiện tại!")
                    return
                self._send_parsed_diplomacy_to_server(res, allow_same_civ=False)
            except Exception as e:
                self.log(f"❌ Lỗi quét màn hình: {e}")

        threading.Thread(target=_task, daemon=True).start()

    def test_from_image_file(self):
        file_path = self.filedialog.askopenfilename(
            title="Chọn ảnh chụp màn hình game AOE có mở bảng Diplomacy",
            filetypes=[("Image files", "*.png *.jpg *.jpeg *.bmp")],
        )
        if not file_path:
            return

        def _task():
            try:
                # Đọc file hỗ trợ đường dẫn tiếng Việt Unicode trên Windows
                raw_bytes = np.fromfile(file_path, dtype=np.uint8)
                img_bgr = cv2.imdecode(raw_bytes, cv2.IMREAD_COLOR)
                res = self.scanner.parse_diplomacy_from_image(
                    img_bgr,
                    streamer_name=self.player_name_var.get().strip(),
                    known_players=self.known_players,
                    force=True,
                )
                if not res or res.get("status") != "ok":
                    self.log(f"⚠️ Ảnh '{os.path.basename(file_path)}' không chứa bảng DIPLOMACY hợp lệ!")
                    return
                self._send_parsed_diplomacy_to_server(res, allow_same_civ=True)
            except Exception as e:
                self.log(f"❌ Lỗi đọc ảnh: {e}")

        threading.Thread(target=_task, daemon=True).start()

    def set_current_winner(self, winner: str):
        def _task():
            try:
                api_url = self.get_api_endpoint()
                res = requests.post(
                    api_url,
                    json={
                        "action": "setWinner",
                        "streamerName": self.player_name_var.get().strip(),
                        "updatedBy": self.player_name_var.get().strip(),
                        "password": self.player_pass_var.get().strip(),
                        "winner": winner,
                    },
                    timeout=10,
                )
                data = res.json()
                if data.get("status") == "success":
                    team_vi = "🔴 Team Đỏ Thắng" if winner == "RED" else "🔵 Team Xanh Thắng"
                    self.log(f"✅ Đã cập nhật kết quả trận mới nhất: {team_vi}")
                    if data.get("match"):
                        self.current_match = data["match"]
                        self._update_score_label(data["match"])
                else:
                    self.log(f"⚠️ {data.get('message', 'Không thể cập nhật tỉ số')}")
            except Exception as e:
                self.log(f"❌ Lỗi cập nhật tỉ số: {e}")

        threading.Thread(target=_task, daemon=True).start()

    def finish_current_match(self):
        if not self.messagebox.askyesno("Xác nhận", "Bạn muốn KẾT THÚC kèo đấu đang LIVE hiện tại?"):
            return

        def _task():
            try:
                api_url = self.get_api_endpoint()
                res = requests.post(
                    api_url,
                    json={
                        "action": "finishMatch",
                        "streamerName": self.player_name_var.get().strip(),
                        "updatedBy": self.player_name_var.get().strip(),
                        "password": self.player_pass_var.get().strip(),
                    },
                    timeout=10,
                )
                data = res.json()
                if data.get("status") == "success":
                    self.log("🏁 Đã kết thúc kèo đấu thành công!")
                    self.current_match = None
                    self.root.after(0, lambda: self.score_lbl.config(text="Tỉ số hiện tại: Kèo đã kết thúc"))
                else:
                    self.log(f"⚠️ {data.get('message', 'Không thể kết thúc kèo')}")
            except Exception as e:
                self.log(f"❌ Lỗi kết thúc kèo: {e}")

        threading.Thread(target=_task, daemon=True).start()

    def _background_worker(self):
        last_heartbeat = time.time()
        while self.running:
            try:
                if self.is_logged_in and self.auto_scan_var.get():
                    pil_img = ImageGrab.grab()
                    img_bgr = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)
                    res = self.scanner.parse_diplomacy_from_image(
                        img_bgr,
                        streamer_name=self.player_name_var.get().strip(),
                        known_players=self.known_players,
                        force=False,
                    )
                    if res and res.get("status") == "ok":
                        self._send_parsed_diplomacy_to_server(res, allow_same_civ=False)

                # Định kỳ gửi heartbeat mỗi 60s để giữ kèo LIVE
                if self.is_logged_in and (time.time() - last_heartbeat > 60.0):
                    last_heartbeat = time.time()
                    try:
                        requests.post(
                            self.get_api_endpoint(),
                            json={
                                "action": "heartbeat",
                                "streamerName": self.player_name_var.get().strip(),
                                "password": self.player_pass_var.get().strip(),
                            },
                            timeout=8,
                        )
                    except Exception:
                        pass
            except Exception:
                pass
            time.sleep(0.8)


def run_cli_self_test(image_paths, streamer_name="XO"):
    scanner = DiplomacyScanner()
    for p in image_paths:
        raw_bytes = np.fromfile(p, dtype=np.uint8)
        img = cv2.imdecode(raw_bytes, cv2.IMREAD_COLOR)
        res = scanner.parse_diplomacy_from_image(img, streamer_name=streamer_name, force=True)
        print(f"=== TEST {os.path.basename(p)} ===")
        print(json.dumps(res, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--test":
        run_cli_self_test(sys.argv[2:])
    else:
        import tkinter as tk
        root = tk.Tk()
        app = AOETrackerApp(root)
        root.mainloop()
