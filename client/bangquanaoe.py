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

APP_VERSION = "v5.2 Premium Esports"
APP_TITLE = "TOOL BẢNG QUÂN AOE BY XO"
DEFAULT_SERVER_URL = "https://aoe-tracker.onrender.com/"

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
# Đo trực tiếp trên dải vải cờ thuần túy (loại bỏ 100% nền đá xám và chữ trắng)
# 0: Blue (Xanh lam), 1: Orange (Cam), 2: Red (Đỏ), 3: Yellow (Vàng),
# 4: Green (Xanh lá), 5: Gray/White (Xám trắng), 6: Brown (Nâu), 7: Cyan (Xanh cung)
AOE_RIBBON_HSV = {
    0: (113.0, 195.0, 118.0),  # P1 - Blue (Xanh lam)
    1: (13.0,  232.0, 142.0),  # P2 - Orange (Cam)
    2: (2.0,   232.0, 122.0),  # P3 - Red (Đỏ)
    3: (22.5,  168.0, 124.0),  # P4 - Yellow (Vàng)
    4: (50.0,  128.0,  72.0),  # P5 - Green (Xanh lá)
    5: (0.0,     4.0,  78.0),  # P6 - Gray/White (Xám trắng)
    6: (14.5,  128.0,  82.0),  # P7 - Brown (Nâu)
    7: (88.5,  215.0,  80.0),  # P8 - Cyan (Xanh cung)
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

# Danh sách tên máy (AI) chuẩn theo từng loại quân trong AOE 1 Rise of Rome
CIV_AI_NAMES = {
    "Assyrian": ["Ashurbanipal", "Sargon", "Sennacherib", "Shalmaneser", "Tiglath-Pileser", "Tukulti-Ninurta", "Adad-nirari", "Esarhaddon"],
    "Babylonian": ["Nabonidus", "Hammurabi", "Nebuchadnezzar", "Tiglath-Pileser", "Sumu-abum", "Samsu-iluna", "Burna-Buriash"],
    "Carthaginian": ["Hamilcar Barca", "Matho", "Hannibal", "Hasdrubal", "Hanno", "Mago", "Gisco", "Bomilcar"],
    "Choson": ["Hyon", "Dangun", "Gwanggaeto", "Jumong", "Kija", "Ugeo", "Wiman", "Ulji Mundok"],
    "Egyptian": ["Amenophis", "Ramses", "Cleopatra", "Hatshepsut", "Khufu", "Nefertiti", "Ptolemy", "Seti", "Thutmose", "Tutankhamun"],
    "Greek": ["Leonidas", "Erythrus", "Pericles", "Alexander", "Hippocrates", "Themistocles", "Pyrrhus", "Lysander", "Alcibiades"],
    "Hittite": ["Tudhalyas", "Suppiluliumas", "Hattusilis", "Labarnas", "Mursilis", "Muwatalli", "Telipinus"],
    "Macedonian": ["Alexander", "Antigonus", "Antipater", "Cassander", "Craterus", "Demetrius", "Lysimachus", "Philip", "Ptolemy", "Seleucus"],
    "Minoan": ["Erythrus", "Minos", "Asterion", "Deucalion", "Idomeneus", "Rhadamanthus", "Sarpedon", "Talos"],
    "Palmyran": ["Zobdas", "Syphax", "Jugurtha", "Zenobia", "Odaenathus", "Vaballathus", "Hairan", "Longinus"],
    "Persian": ["Astyages", "Cyrus", "Mithridates", "Darius", "Xerxes", "Cambyses", "Artaxerxes", "Shapur", "Tigranes"],
    "Phoenician": ["Ahiram", "Hiram", "Abibaal", "Dido", "Ethbaal", "Ittobaal", "Pygmalion", "Zakarbaal"],
    "Roman": ["Marcus Aurelius", "Caesar", "Augustus", "Pompey", "Scipio", "Sulla", "Trajan", "Crassus", "Marius"],
    "Shang": ["Zhou Xin", "Tang", "Wu Ding", "Pan Geng", "Tai Jia", "Zu Yi", "Di Yi", "Tai Wu"],
    "Sumerian": ["Enmerkar", "Gilgamesh", "Sargon", "Ur-Nammu", "Shulgi", "Eannatum", "Gudea", "Lugal-zage-si"],
    "Yamato": ["Keiko", "Kammu", "Jimmu", "Himiko", "Nintoku", "Ojin", "Suinin", "Sujin", "Shotoku"],
}

KNOWN_AI_NAMES = []
for _civ_names in CIV_AI_NAMES.values():
    for _n in _civ_names:
        if _n not in KNOWN_AI_NAMES:
            KNOWN_AI_NAMES.append(_n)


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


def _get_arial_bold_font():
    for font_path in ["C:/Windows/Fonts/arialbd.ttf", "C:/Windows/Fonts/arial.ttf"]:
        if os.path.exists(font_path):
            try:
                return ImageFont.truetype(font_path, 12)
            except Exception:
                pass
    return None


def build_text_templates(word_list, max_w=110):
    templates = {}
    font = _get_arial_bold_font()
    if font is None:
        return templates

    for word in word_list:
        img = Image.new("L", (140, 24), 0)
        draw = ImageDraw.Draw(img)
        draw.text((0, 2), word, fill=255, font=font)
        arr = np.array(img)
        ys, xs = np.where(arr > 80)
        if len(xs) == 0:
            continue
        patch = arr[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
        new_w = max(1, int(round(patch.shape[1] * (12.0 / patch.shape[0]))))
        resized = cv2.resize(patch, (new_w, 12), interpolation=cv2.INTER_AREA)
        canvas = np.zeros((12, max_w), dtype=np.float32)
        w_clip = min(max_w, new_w)
        canvas[:, :w_clip] = resized[:, :w_clip] / 255.0
        templates[word] = (canvas, new_w)
    return templates


CIV_TEMPLATES = build_text_templates([full for full, _, _ in CIV_LIST], max_w=90)
AI_NAME_TEMPLATES = build_text_templates(KNOWN_AI_NAMES, max_w=110)


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
        """
        Trích xuất màu HSV chuẩn xác 100% từ dải vải cờ thuần túy nằm ngay dưới chữ tên Player
        (y: yc+3..yc+8, x: 20..98) và loại bỏ hoàn toàn nền đá xám (S < 45) khỏi histogram Hue.
        """
        yc = int(round(95.0 + row_idx * 29.8))
        cloth_strip = norm_624x400[yc + 3:yc + 8, 20:98]
        hsv_strip = cv2.cvtColor(cloth_strip, cv2.COLOR_BGR2HSV)

        valid_strip = hsv_strip[:, :, 2] >= 35
        if not np.any(valid_strip):
            return (0.0, 0.0, 75.0)

        # Kiểm tra cờ Xám trắng (Color 5): hầu hết pixel trên dải vải cờ có độ bão hòa S < 38
        s_85 = float(np.percentile(hsv_strip[:, :, 1][valid_strip], 85))
        if s_85 < 38.0:
            med_s = float(np.median(hsv_strip[:, :, 1][valid_strip]))
            med_v = float(np.median(hsv_strip[:, :, 2][valid_strip]))
            return (0.0, med_s, med_v)

        # Đối với 7 màu có sắc độ: chỉ lấy các pixel thực sự có màu (S >= 45, V >= 35)
        # để nền đá xám (H=0, S=0) không bao giờ làm lệch góc màu Hue!
        banner_crop = norm_624x400[yc - 8:yc + 9, 18:102]
        hsv_b = cv2.cvtColor(banner_crop, cv2.COLOR_BGR2HSV)
        chrom_mask = (hsv_b[:, :, 1] >= 45) & (hsv_b[:, :, 2] >= 35) & ~((hsv_b[:, :, 1] < 60) & (hsv_b[:, :, 2] > 180))

        if np.sum(chrom_mask) < 20:
            med_s = float(np.median(hsv_strip[:, :, 1][valid_strip]))
            med_v = float(np.median(hsv_strip[:, :, 2][valid_strip]))
            return (0.0, med_s, med_v)

        pts = hsv_b[chrom_mask]
        hist = cv2.calcHist([hsv_b], [0], chrom_mask.astype(np.uint8), [180], [0, 180]).flatten()
        smooth_hist = np.zeros(180, dtype=np.float32)
        for h_i in range(180):
            smooth_hist[h_i] = 0.25 * hist[(h_i - 1) % 180] + 0.5 * hist[h_i] + 0.25 * hist[(h_i + 1) % 180]
        dom_h = float(np.argmax(smooth_hist))

        strip_chrom = (hsv_strip[:, :, 1] >= 45) & (hsv_strip[:, :, 2] >= 35)
        if np.sum(strip_chrom) >= 10:
            med_s = float(np.median(hsv_strip[:, :, 1][strip_chrom]))
            med_v = float(np.median(hsv_strip[:, :, 2][strip_chrom]))
        else:
            med_s = float(np.median(pts[:, 1]))
            med_v = float(np.median(pts[:, 2]))

        return (dom_h, med_s, med_v)

    @staticmethod
    def ribbon_hsv_distance(feat, color_idx: int) -> float:
        h_val, s_val, v_val = feat
        th, ts, tv = AOE_RIBBON_HSV[color_idx]

        # Màu 5 (Xám trắng) có độ bão hòa S rất thấp (< 38)
        if color_idx == 5:
            if s_val < 38.0:
                return abs(s_val - ts) * 0.5 + abs(v_val - tv) * 0.3
            return 500.0 + s_val * 3.0

        # Nếu thực tế cờ có S < 38 thì phạt nặng các màu có sắc độ
        if s_val < 38.0:
            return 500.0

        dh = min(abs(h_val - th), 180.0 - abs(h_val - th))
        ds = abs(s_val - ts)
        dv = abs(v_val - tv)
        return dh * 6.0 + ds * 0.9 + dv * 1.1

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
        Sử dụng trực tiếp Windows.Media.Ocr có sẵn trên mọi máy Windows 10/11.
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

                if len(clean_raw) >= 2 and clean_raw[:2] == raw_target[:2]:
                    prefix_bonus = max(prefix_bonus, 0.45)
                elif len(clean_norm) >= 2 and clean_norm[:2] == norm_target[:2]:
                    prefix_bonus = max(prefix_bonus, 0.35)

                best_str_sim = max(best_str_sim, sim1, sim2, sim3)

            scores[full] += best_str_sim * 1.6 + prefix_bonus

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
    def clean_and_match_player_name(
        norm_624x400: np.ndarray,
        ocr_name_candidates,
        row_idx: int,
        full_civ: str,
        streamer_name: str,
        known_players=None,
    ):
        if row_idx == 0 and streamer_name and streamer_name.strip():
            return streamer_name.strip()

        def normalize_name_token(s: str) -> str:
            rep = {"2": "z", "0": "o", "1": "i", "4": "a", "6": "e", "5": "s", "$": "s", "@": "a"}
            out = []
            for ch in s.lower():
                ch = rep.get(ch, ch)
                if ch.isascii() and ch.isalpha():
                    out.append(ch)
            res_s = "".join(out)
            res_s = res_s.replace("rn", "m").replace("nt", "m").replace("lt", "m").replace("ll", "l")
            return res_s

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

        civ_specific_ai = CIV_AI_NAMES.get(full_civ, [])
        pool = list(civ_specific_ai) + [n for n in KNOWN_AI_NAMES if n not in civ_specific_ai]
        human_pool = []
        if known_players:
            for p in known_players:
                pname = p.get("name") if isinstance(p, dict) else str(p)
                if pname and pname not in human_pool:
                    human_pool.append(pname)
                    if pname not in pool:
                        pool.insert(0, pname)
        if streamer_name and streamer_name not in pool:
            pool.insert(0, streamer_name)

        all_candidates = [c for c in ocr_name_candidates if c]
        if best_raw:
            all_candidates.insert(0, best_raw)

        best_match_name = None
        best_sim = 0.0
        for cand in all_candidates:
            cand_alpha = normalize_name_token(cand)
            if len(cand_alpha) < 2:
                continue
            cand_i = cand_alpha.replace("l", "i")
            for target in pool:
                target_alpha = normalize_name_token(target)
                target_i = target_alpha.replace("l", "i")
                sim = max(
                    difflib.SequenceMatcher(None, cand_alpha, target_alpha).ratio(),
                    difflib.SequenceMatcher(None, cand_i, target_i).ratio(),
                )
                if len(cand_i) >= 3 and (target_i.endswith(cand_i) or target_i.startswith(cand_i)):
                    len_ratio = min(len(cand_i), len(target_i)) / max(len(cand_i), len(target_i))
                    sim = max(sim, 0.74 + 0.18 * len_ratio)
                # Điểm thưởng lớn nếu tên AI thuộc đúng loại quân (full_civ) của dòng này
                if target in civ_specific_ai:
                    sim += 0.22
                if sim > best_sim:
                    best_sim = sim
                    best_match_name = target

        # Nếu phân vân giữa Kammu và Jimmu (cùng quân Yamato), kiểm tra độ rộng của cụm chữ đầu 'Ka' (rộng) so với 'Ji' (hẹp)
        if best_match_name in ("Kammu", "Jimmu") and full_civ == "Yamato":
            yc = int(round(95.0 + row_idx * 29.8))
            fc_crop = norm_624x400[yc - 7:yc + 3, 14:65]
            wh_fc = np.min(fc_crop, axis=2).astype(np.float32) - 0.55 * (
                np.max(fc_crop, axis=2).astype(np.float32) - np.min(fc_crop, axis=2).astype(np.float32)
            )
            cols_fc = np.where(np.sum(wh_fc > 155.0, axis=0) >= 1)[0]
            span_w = int(cols_fc[-1] - cols_fc[0] + 1) if len(cols_fc) >= 2 else 0
            best_match_name = "Kammu" if span_w >= 34 else "Jimmu"

        if best_match_name and best_sim >= 0.60:
            return best_match_name

        # Fallback thông minh cho dòng cờ Xám trắng (hoặc ảnh độ phân giải thấp) khi đấu với AI:
        # So khớp chiều rộng & mẫu chữ 2D với danh sách AI chuẩn của đúng loại quân (full_civ)
        if civ_specific_ai and AI_NAME_TEMPLATES:
            yc = int(round(95.0 + row_idx * 29.8))
            crop = norm_624x400[yc - 7:yc + 3, 14:120]
            min_rgb = np.min(crop, axis=2).astype(np.float32)
            max_rgb = np.max(crop, axis=2).astype(np.float32)
            wh = min_rgb - 0.55 * (max_rgb - min_rgb)
            thr = max(float(np.percentile(wh, 84)) + 14.0, 168.0)
            val = np.clip((wh - thr) / 55.0, 0.0, 1.0)
            mask = val > 0.25
            col_sum = np.sum(mask, axis=0)
            xmin = 0
            while xmin < len(col_sum) and col_sum[xmin] < 2:
                xmin += 1
            xmax = xmin
            empty_run = 0
            for x in range(xmin, len(col_sum)):
                if col_sum[x] >= 2:
                    xmax = x
                    empty_run = 0
                else:
                    empty_run += 1
                    if empty_run >= 5 and (xmax - xmin) >= 12:
                        break
            if xmax > xmin + 8:
                patch = val[:, xmin:xmax + 1]
                nw = max(1, int(round(patch.shape[1] * (12.0 / 10.0))))
                resized = cv2.resize(patch, (nw, 12), interpolation=cv2.INTER_LINEAR)
                feat = np.zeros((12, 110), dtype=np.float32)
                wc = min(110, nw)
                feat[:, :wc] = resized[:, :wc]
                best_ai_t = None
                best_ai_sc = -1.0
                for ai_name in civ_specific_ai:
                    if ai_name not in AI_NAME_TEMPLATES:
                        continue
                    tmpl, tw = AI_NAME_TEMPLATES[ai_name]
                    w_score = max(0.0, 1.0 - abs(nw - tw) / 20.0) * 0.55
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
                    total_sc = max(0.0, max_corr) * 0.45 + w_score
                    if total_sc > best_ai_sc:
                        best_ai_sc = total_sc
                        best_ai_t = ai_name
                if best_ai_t in ("Kammu", "Jimmu") and full_civ == "Yamato":
                    first_char = norm_624x400[yc - 7:yc + 2, 14:22]
                    wh_fc = np.min(first_char, axis=2).astype(np.float32)
                    top_left_ink = float(np.mean(wh_fc[:4, :3] > 165))
                    best_ai_t = "Kammu" if top_left_ink >= 0.25 else "Jimmu"
                if best_ai_t and best_ai_sc >= 0.48:
                    return best_ai_t

        return best_raw if best_raw else f"Player {row_idx + 1}"

    def parse_diplomacy_from_image(self, img_bgr: np.ndarray, streamer_name: str = "XO", known_players=None, force: bool = False):
        """
        Trích xuất toàn bộ thông tin từ ảnh chụp màn hình có mở bảng DIPLOMACY.
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

        gray = cv2.cvtColor(norm, cv2.COLOR_BGR2GRAY)
        edges = np.abs(cv2.Sobel(gray, cv2.CV_32F, 1, 0, ksize=3)) + np.abs(cv2.Sobel(gray, cv2.CV_32F, 0, 1, ksize=3))

        active_rows = []
        multi_canvas = np.full((8 * 70, 2900, 3), 255, dtype=np.uint8)

        h_full, w_full = img_bgr.shape[:2]
        f4_crop = img_bgr[int(h_full * 0.58):int(h_full * 0.85), int(w_full * 0.82):w_full]
        if f4_crop.size > 0:
            f4_up = cv2.resize(f4_crop, (440, 520), interpolation=cv2.INTER_CUBIC)
            max_f4 = np.max(f4_up, axis=2).astype(np.float32)
            a_f4 = np.clip((max_f4 - 48.0) / 110.0, 0.0, 1.0)
            ink_f4 = cv2.cvtColor((255.0 * (1.0 - a_f4)).astype(np.uint8), cv2.COLOR_GRAY2BGR)
            multi_canvas[10:530, 2430:2870] = ink_f4

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

                # Phơi sáng 4: Thích ứng ngưỡng cao trên nền cờ màu (cắt sát dòng yc-10..yc+10)
                cell4 = norm[yc - 10:yc + 10, x_start:x_end]
                up4 = cv2.resize(cell4, (0, 0), fx=2.5, fy=2.5, interpolation=cv2.INTER_LANCZOS4)
                min4 = np.min(up4, axis=2).astype(np.float32)
                max4 = np.max(up4, axis=2).astype(np.float32)
                wh4 = min4 - 0.55 * (max4 - min4)
                bg_high = max(float(np.percentile(wh4, 65)) + 16.0, float(np.percentile(wh4, 88)) + 6.0)
                a4 = np.clip((wh4 - bg_high) / 38.0, 0.0, 1.0)
                ink4 = cv2.cvtColor((255.0 * (1.0 - a4)).astype(np.uint8), cv2.COLOR_GRAY2BGR)
                hp4, wp4 = ink4.shape[:2]

                hp, wp = ink1.shape[:2]
                multi_canvas[r * 70 + 8:r * 70 + 8 + hp, base_x:base_x + wp] = ink1
                multi_canvas[r * 70 + 8:r * 70 + 8 + hp, base_x + 600:base_x + 600 + wp] = ink2
                multi_canvas[r * 70 + 8:r * 70 + 8 + hp, base_x + 1200:base_x + 1200 + wp] = ink3
                multi_canvas[r * 70 + 8:r * 70 + 8 + hp4, base_x + 1800:base_x + 1800 + wp4] = ink4

        if not active_rows:
            return None

        assigned_colors = self.assign_player_colors([item["hsv_feat"] for item in active_rows])
        for item, color_id in zip(active_rows, assigned_colors):
            item["color_id"] = color_id

        ocr_words = self.run_windows_ocr_batch(multi_canvas)

        for item in active_rows:
            r = item["row_idx"]
            row_y_min, row_y_max = r * 70, (r + 1) * 70
            name_cands = [[], [], [], []]
            civ_cands = [[], [], [], []]
            for w in ocr_words:
                wy = w.get("y", -1)
                if row_y_min <= wy <= row_y_max:
                    wx = w.get("x", 0)
                    exp_idx = wx // 600
                    if exp_idx > 3:
                        continue
                    rel_x = wx % 600
                    if rel_x < 300:
                        name_cands[exp_idx].append((rel_x, str(w.get("text", ""))))
                    else:
                        civ_cands[exp_idx].append((rel_x, str(w.get("text", ""))))

            name_strs = [" ".join(t for _, t in sorted(cand)) for cand in name_cands if cand]
            civ_strs = [" ".join(t for _, t in sorted(cand)) for cand in civ_cands if cand]

            full_civ, short_civ = self.match_civ_for_row(norm, r, civ_strs, item["w_obs"])
            player_name = self.clean_and_match_player_name(
                norm, name_strs, r, full_civ, streamer_name, known_players
            )

            item["name"] = player_name
            item["civ_full"] = full_civ
            item["civ_short"] = short_civ

        red_rows = [item for item in active_rows if item["stance"] == "ALLY"]
        blue_rows = [item for item in active_rows if item["stance"] != "ALLY"]

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
        "server_url": DEFAULT_SERVER_URL,
        "player_name": "XO",
        "player_password": "111",
        "auto_scan": True,
    }
    if path.exists():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            # Tự động nâng cấp URL cũ localhost sang server Render mặc định mới
            saved_url = str(data.get("server_url", "")).strip()
            if not saved_url or "localhost:3000" in saved_url:
                data["server_url"] = DEFAULT_SERVER_URL
            default_cfg.update(data)
        except Exception:
            pass
    return default_cfg


def save_user_settings(cfg: dict):
    try:
        get_settings_path().write_text(json.dumps(cfg, indent=2, ensure_ascii=False), encoding="utf-8")
    except Exception as e:
        print("Không thể lưu settings:", e)


# Bảng mã màu Hex hiển thị cho 8 màu quân AOE
AOE_COLOR_HEX = {
    0: "#3b82f6",  # P1 - Xanh lam
    1: "#fb923c",  # P2 - Cam
    2: "#ef4444",  # P3 - Đỏ
    3: "#facc15",  # P4 - Vàng
    4: "#4ade80",  # P5 - Xanh lá
    5: "#e2e8f0",  # P6 - Xám trắng
    6: "#d97706",  # P7 - Nâu
    7: "#38bdf8",  # P8 - Xanh cung (Cyan)
}

MARQUEE_MODE_LABELS = [
    ("ALL", "Tổng Cung-Chém + Số Cung-Chém từng người"),
    ("TOTAL_ONLY", "Chỉ hiện tổng Cung - Chém"),
    ("PER_PLAYER", "Chỉ hiện số Cung - Chém từng người"),
    ("CUSTOM", "Chạy dòng chữ tùy chỉnh do bạn nhập"),
    ("OFF", "Tắt dòng chữ chạy"),
]
LABEL_TO_MARQUEE_MODE = {lbl: code for code, lbl in MARQUEE_MODE_LABELS}
MARQUEE_MODE_TO_LABEL = {code: lbl for code, lbl in MARQUEE_MODE_LABELS}

TIER_RANKS = {"BRONZE": 0, "SILVER": 1, "GOLD": 2, "DIAMOND": 3}
TIER_BADGES = {
    "DIAMOND": ("💎 Hạng Kim Cương", "#38bdf8", "#0f2942"),
    "GOLD": ("🥇 Hạng Vàng", "#fbbf24", "#2e2105"),
    "SILVER": ("🥈 Hạng Bạc", "#e2e8f0", "#1e293b"),
    "BRONZE": ("🥉 Hạng Đồng", "#fb923c", "#2a1205"),
}


class AOETrackerApp:
    def __init__(self, root):
        import atexit
        import tkinter as tk
        from tkinter import ttk, filedialog, messagebox

        self.tk = tk
        self.ttk = ttk
        self.filedialog = filedialog
        self.messagebox = messagebox
        self.root = root
        self.root.title(f"AOE COMMAND CENTER — {APP_TITLE} ({APP_VERSION})")
        self.root.geometry("1120x880")
        self.root.minsize(1020, 800)
        self.root.configure(bg="#090e1a")
        self.root.resizable(True, True)

        self.settings = load_user_settings()
        self.scanner = DiplomacyScanner()
        self.is_logged_in = False
        self.is_admin = False
        self.admin_password = ""
        self.player_tier = "BRONZE"
        self.known_players = []
        self.my_friends = []
        self.active_lobby_streamer = ""
        self.current_match = None
        self.last_parsed_teams = None
        self.running = True
        self._did_finish_on_exit = False
        self._last_chat_id = None

        self._configure_ttk_styles()
        self._build_ui()

        # Tự động kết thúc kèo đấu nếu người chơi tắt Tool
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        atexit.register(self._auto_finish_match_sync)

        self._start_clock_loop()
        self.threading_loop = threading.Thread(target=self._background_worker, daemon=True)
        self.threading_loop.start()

        if self.settings.get("player_name") and self.settings.get("player_password"):
            self.root.after(400, self.login_and_start)

    def _configure_ttk_styles(self):
        style = self.ttk.Style()
        try:
            style.theme_use("clam")
        except Exception:
            pass
        style.configure(
            "Premium.TCombobox",
            fieldbackground="#0b1221",
            background="#1e293b",
            foreground="#f8fafc",
            arrowcolor="#94a3b8",
            bordercolor="#283756",
            lightcolor="#283756",
            darkcolor="#090e1a",
        )
        style.map(
            "Premium.TCombobox",
            fieldbackground=[("readonly", "#0b1221")],
            selectbackground=[("readonly", "#0b1221")],
            selectforeground=[("readonly", "#f8fafc")],
        )

    def _bind_hover(self, widget, normal_bg, hover_bg, normal_fg=None, hover_fg=None):
        def _on_enter(_e):
            try:
                widget.configure(bg=hover_bg)
                if hover_fg:
                    widget.configure(fg=hover_fg)
            except Exception:
                pass

        def _on_leave(_e):
            try:
                widget.configure(bg=normal_bg)
                if normal_fg:
                    widget.configure(fg=normal_fg)
            except Exception:
                pass

        widget.bind("<Enter>", _on_enter)
        widget.bind("<Leave>", _on_leave)

    def _build_ui(self):
        tk = self.tk

        # ======================================================================
        # HEADER: PREMIUM GAMING DASHBOARD — MODERN AOE INTERFACE
        # ======================================================================
        hdr_outer = tk.Frame(
            self.root,
            bg="#121b2f",
            highlightthickness=1,
            highlightbackground="#23314d",
            padx=18,
            pady=12,
        )
        hdr_outer.pack(fill="x", padx=14, pady=(12, 6))

        left_hdr = tk.Frame(hdr_outer, bg="#121b2f")
        left_hdr.pack(side="left", anchor="w")

        emblem_box = tk.Frame(
            left_hdr,
            bg="#18243d",
            highlightthickness=1,
            highlightbackground="#334155",
            padx=12,
            pady=6,
        )
        emblem_box.pack(side="left", padx=(0, 14))
        tk.Label(
            emblem_box,
            text="⚔️🛡️",
            font=("Segoe UI Emoji", 16, "bold"),
            fg="#fbbf24",
            bg="#18243d",
        ).pack()

        title_stack = tk.Frame(left_hdr, bg="#121b2f")
        title_stack.pack(side="left")

        hud_tag_row = tk.Frame(title_stack, bg="#121b2f")
        hud_tag_row.pack(anchor="w")

        self.pulse_dot = tk.Label(
            hud_tag_row,
            text="● Hệ thống sẵn sàng",
            font=("Segoe UI", 9, "bold"),
            fg="#38bdf8",
            bg="#0b1221",
            padx=8,
            pady=1,
        )
        self.pulse_dot.pack(side="left", padx=(0, 8))

        tk.Label(
            hud_tag_row,
            text="AOE COMMAND CENTER • Esports Tournament Manager",
            font=("Segoe UI", 9, "bold"),
            fg="#94a3b8",
            bg="#121b2f",
        ).pack(side="left")

        tk.Label(
            title_stack,
            text=f"{APP_TITLE} ({APP_VERSION})",
            font=("Segoe UI", 14, "bold"),
            fg="#f8fafc",
            bg="#121b2f",
        ).pack(anchor="w", pady=(2, 0))

        # Góc phải Header: Ngày giờ & Hạng tài khoản VIP
        right_hdr = tk.Frame(hdr_outer, bg="#121b2f")
        right_hdr.pack(side="right", anchor="e")

        self.date_corner_lbl = tk.Label(
            right_hdr,
            text="📅 --/--/---- • --:--:--",
            font=("Consolas", 10, "bold"),
            fg="#f8fafc",
            bg="#0b1221",
            padx=10,
            pady=4,
            highlightthickness=1,
            highlightbackground="#283756",
        )
        self.date_corner_lbl.pack(anchor="e", pady=(0, 5))

        self.tier_badge_lbl = tk.Label(
            right_hdr,
            text="🥉 Hạng Đồng (Chưa kết nối)",
            font=("Segoe UI", 9, "bold"),
            fg="#fb923c",
            bg="#2a1205",
            padx=10,
            pady=2,
            highlightthickness=1,
            highlightbackground="#7c2d12",
        )
        self.tier_badge_lbl.pack(anchor="e")

        # ======================================================================
        # PANEL 1: KẾT NỐI HỆ THỐNG (SERVER & TÀI KHOẢN PLAYER)
        # ======================================================================
        conn_card = tk.Frame(
            self.root,
            bg="#121b2f",
            highlightthickness=1,
            highlightbackground="#23314d",
            padx=16,
            pady=10,
        )
        conn_card.pack(fill="x", padx=14, pady=5)

        conn_hdr = tk.Frame(conn_card, bg="#121b2f")
        conn_hdr.pack(fill="x", pady=(0, 8))

        tk.Label(
            conn_hdr,
            text="⚡ KẾT NỐI HỆ THỐNG & TÀI KHOẢN STREAMER",
            font=("Segoe UI", 10, "bold"),
            fg="#38bdf8",
            bg="#121b2f",
        ).pack(side="left")

        self.status_lbl = tk.Label(
            conn_hdr,
            text="⏳ Chưa kết nối — Vui lòng đăng nhập tài khoản Player",
            font=("Segoe UI", 10, "bold"),
            fg="#fbbf24",
            bg="#121b2f",
        )
        self.status_lbl.pack(side="right")

        inputs_grid = tk.Frame(conn_card, bg="#121b2f")
        inputs_grid.pack(fill="x")
        inputs_grid.columnconfigure(0, weight=5)
        inputs_grid.columnconfigure(1, weight=3)
        inputs_grid.columnconfigure(2, weight=2)

        # Cột 1: Server Endpoint
        col_srv = tk.Frame(inputs_grid, bg="#121b2f")
        col_srv.grid(row=0, column=0, sticky="we", padx=(0, 10))
        tk.Label(
            col_srv,
            text="Địa chỉ máy chủ (Server URL)",
            font=("Segoe UI", 9, "bold"),
            fg="#94a3b8",
            bg="#121b2f",
        ).pack(anchor="w")
        self.server_url_var = tk.StringVar(value=self.settings.get("server_url", DEFAULT_SERVER_URL))
        tk.Entry(
            col_srv,
            textvariable=self.server_url_var,
            font=("Consolas", 10),
            bg="#0b1221",
            fg="#f8fafc",
            insertbackground="#38bdf8",
            relief="flat",
            highlightthickness=1,
            highlightbackground="#283756",
            highlightcolor="#38bdf8",
        ).pack(fill="x", ipady=5, pady=(3, 0))

        # Cột 2: Tên Player (Streamer)
        col_usr = tk.Frame(inputs_grid, bg="#121b2f")
        col_usr.grid(row=0, column=1, sticky="we", padx=10)
        tk.Label(
            col_usr,
            text="Tên Player / Streamer",
            font=("Segoe UI", 9, "bold"),
            fg="#94a3b8",
            bg="#121b2f",
        ).pack(anchor="w")
        self.player_name_var = tk.StringVar(value=self.settings.get("player_name", "XO"))
        self.player_name_var.trace_add("write", lambda *_: self._update_obs_preview_entry())
        tk.Entry(
            col_usr,
            textvariable=self.player_name_var,
            font=("Segoe UI", 10, "bold"),
            bg="#0b1221",
            fg="#f8fafc",
            insertbackground="#38bdf8",
            relief="flat",
            highlightthickness=1,
            highlightbackground="#283756",
            highlightcolor="#38bdf8",
        ).pack(fill="x", ipady=4, pady=(3, 0))

        # Cột 3: Mật khẩu
        col_pwd = tk.Frame(inputs_grid, bg="#121b2f")
        col_pwd.grid(row=0, column=2, sticky="we", padx=(10, 0))
        tk.Label(
            col_pwd,
            text="Mật khẩu",
            font=("Segoe UI", 9, "bold"),
            fg="#94a3b8",
            bg="#121b2f",
        ).pack(anchor="w")
        self.player_pass_var = tk.StringVar(value=self.settings.get("player_password", "111"))
        tk.Entry(
            col_pwd,
            textvariable=self.player_pass_var,
            show="*",
            font=("Consolas", 10, "bold"),
            bg="#0b1221",
            fg="#f8fafc",
            insertbackground="#38bdf8",
            relief="flat",
            highlightthickness=1,
            highlightbackground="#283756",
            highlightcolor="#38bdf8",
        ).pack(fill="x", ipady=4, pady=(3, 0))

        # Hàng nút Connect nổi bật ở trung tâm
        conn_btn_bar = tk.Frame(conn_card, bg="#121b2f")
        conn_btn_bar.pack(fill="x", pady=(10, 2))

        self.auto_scan_var = tk.BooleanVar(value=bool(self.settings.get("auto_scan", True)))
        tk.Checkbutton(
            conn_btn_bar,
            text="🟢 Tự động quét bảng Diplomacy (F2)",
            variable=self.auto_scan_var,
            font=("Segoe UI", 9, "bold"),
            fg="#e2e8f0",
            bg="#121b2f",
            selectcolor="#0b1221",
            activebackground="#121b2f",
            activeforeground="#34d399",
            cursor="hand2",
        ).pack(side="left")

        self.open_web_btn = tk.Button(
            conn_btn_bar,
            text="🌐 Mở trang Web Quản Lý",
            command=self.open_web_dashboard,
            font=("Segoe UI", 9, "bold"),
            bg="#1e293b",
            fg="#f8fafc",
            activebackground="#334155",
            activeforeground="#ffffff",
            relief="flat",
            padx=12,
            pady=5,
            cursor="hand2",
        )
        self.open_web_btn.pack(side="right")
        self._bind_hover(self.open_web_btn, "#1e293b", "#334155", "#f8fafc", "#ffffff")

        self.admin_mgr_btn = tk.Button(
            conn_btn_bar,
            text="🛡️ Quản Trị Admin XO",
            command=self.open_admin_manager_window,
            font=("Segoe UI", 9, "bold"),
            bg="#451a03",
            fg="#fbbf24",
            activebackground="#78350f",
            activeforeground="#ffffff",
            relief="flat",
            padx=12,
            pady=5,
            cursor="hand2",
        )
        self.admin_mgr_btn.pack(side="right", padx=(0, 8))
        self._bind_hover(self.admin_mgr_btn, "#451a03", "#78350f", "#fbbf24", "#ffffff")

        self.login_btn = tk.Button(
            conn_btn_bar,
            text="⚡ Kết nối & Lưu cấu hình",
            command=self.login_and_start,
            font=("Segoe UI", 10, "bold"),
            bg="#0284c7",
            fg="#ffffff",
            activebackground="#0369a1",
            activeforeground="#ffffff",
            relief="flat",
            padx=26,
            pady=5,
            cursor="hand2",
        )
        self.login_btn.pack(anchor="center")
        self._bind_hover(self.login_btn, "#0284c7", "#0369a1", "#ffffff", "#ffffff")

        # ======================================================================
        # PANEL 2: ĐIỀU KHIỂN TRẬN ĐẤU — TEAM ĐỎ VS TEAM XANH (TỶ SỐ TRUNG TÂM)
        # ======================================================================
        battle_card = tk.Frame(
            self.root,
            bg="#121b2f",
            highlightthickness=1,
            highlightbackground="#23314d",
            padx=16,
            pady=12,
        )
        battle_card.pack(fill="x", padx=14, pady=5)

        battle_hdr = tk.Frame(battle_card, bg="#121b2f")
        battle_hdr.pack(fill="x", pady=(0, 8))

        tk.Label(
            battle_hdr,
            text="⚔️ ĐIỀU KHIỂN TRẬN ĐẤU (BATTLE CONTROL)",
            font=("Segoe UI", 10, "bold"),
            fg="#38bdf8",
            bg="#121b2f",
        ).pack(side="left")

        scan_actions = tk.Frame(battle_hdr, bg="#121b2f")
        scan_actions.pack(side="right")

        btn_scan_now = tk.Button(
            scan_actions,
            text="🔍 Quét màn hình ngay",
            command=self.manual_scan_screen,
            font=("Segoe UI", 9, "bold"),
            bg="#059669",
            fg="#ffffff",
            relief="flat",
            padx=12,
            pady=4,
            cursor="hand2",
        )
        btn_scan_now.pack(side="left", padx=(0, 8))
        self._bind_hover(btn_scan_now, "#059669", "#047857", "#ffffff", "#ffffff")

        btn_test_img = tk.Button(
            scan_actions,
            text="🖼️ Test từ file ảnh...",
            command=self.test_from_image_file,
            font=("Segoe UI", 9, "bold"),
            bg="#1e293b",
            fg="#e2e8f0",
            relief="flat",
            padx=12,
            pady=4,
            cursor="hand2",
        )
        btn_test_img.pack(side="left", padx=(0, 8))
        self._bind_hover(btn_test_img, "#1e293b", "#334155", "#e2e8f0", "#ffffff")

        btn_end_match = tk.Button(
            scan_actions,
            text="🏁 Kết thúc kèo đấu",
            command=self.finish_current_match,
            font=("Segoe UI", 9, "bold"),
            bg="#3f2712",
            fg="#fcd34d",
            relief="flat",
            padx=12,
            pady=4,
            cursor="hand2",
        )
        btn_end_match.pack(side="left")
        self._bind_hover(btn_end_match, "#3f2712", "#78350f", "#fcd34d", "#ffffff")

        # Lưới 3 cột: Card Team Đỏ (Trái) — Bảng Tỉ Số Trung Tâm (Giữa) — Card Team Xanh (Phải)
        arena_grid = tk.Frame(battle_card, bg="#121b2f")
        arena_grid.pack(fill="x")
        arena_grid.columnconfigure(0, weight=4)
        arena_grid.columnconfigure(1, weight=3)
        arena_grid.columnconfigure(2, weight=4)

        # --- CARD TRÁI: TEAM ĐỎ ---
        self.red_card = tk.Frame(
            arena_grid,
            bg="#221219",
            highlightthickness=1,
            highlightbackground="#7f1d1d",
            padx=12,
            pady=10,
        )
        self.red_card.grid(row=0, column=0, sticky="nsew", padx=(0, 8))

        red_hdr = tk.Frame(self.red_card, bg="#221219")
        red_hdr.pack(fill="x")
        tk.Label(
            red_hdr,
            text="🔴 Team Đỏ (Chủ nhà)",
            font=("Segoe UI", 11, "bold"),
            fg="#f87171",
            bg="#221219",
        ).pack(side="left")
        self.red_count_lbl = tk.Label(
            red_hdr,
            text="0 người chơi",
            font=("Segoe UI", 9, "bold"),
            fg="#fca5a5",
            bg="#3b1520",
            padx=8,
            pady=1,
        )
        self.red_count_lbl.pack(side="right")

        self.red_roster_lbl = tk.Label(
            self.red_card,
            text="Chưa có đội hình Team Đỏ\n(Bấm F2 Diplomacy trong game để quét)",
            font=("Segoe UI", 10, "bold"),
            fg="#f8fafc",
            bg="#160b10",
            justify="left",
            anchor="w",
            padx=10,
            pady=8,
            height=4,
        )
        self.red_roster_lbl.pack(fill="x", pady=8)

        self.btn_red_win = tk.Button(
            self.red_card,
            text="🔴 Team Đỏ thắng trận này (+1)",
            command=lambda: self.set_current_winner("RED"),
            font=("Segoe UI", 10, "bold"),
            bg="#dc2626",
            fg="#ffffff",
            activebackground="#b91c1c",
            relief="flat",
            pady=6,
            cursor="hand2",
        )
        self.btn_red_win.pack(fill="x")
        self._bind_hover(self.btn_red_win, "#dc2626", "#b91c1c", "#ffffff", "#ffffff")

        # --- CARD GIỮA: TỶ SỐ TRẬN ĐẤU TRUNG TÂM ---
        center_hud = tk.Frame(
            arena_grid,
            bg="#0b1221",
            highlightthickness=1,
            highlightbackground="#334155",
            padx=14,
            pady=10,
        )
        center_hud.grid(row=0, column=1, sticky="nsew", padx=4)

        self.match_mode_lbl = tk.Label(
            center_hud,
            text="Chạm 100 • Chờ kèo đấu",
            font=("Segoe UI", 10, "bold"),
            fg="#fbbf24",
            bg="#1e293b",
            padx=10,
            pady=3,
        )
        self.match_mode_lbl.pack(pady=(0, 6))

        self.score_lbl = tk.Label(
            center_hud,
            text="0  -  0",
            font=("Segoe UI", 28, "bold"),
            fg="#f8fafc",
            bg="#0b1221",
        )
        self.score_lbl.pack(pady=4)

        self.c_mode_summary_lbl = tk.Label(
            center_hud,
            text="Chế độ chuẩn • Tổng 0 trận",
            font=("Segoe UI", 9, "bold"),
            fg="#94a3b8",
            bg="#0b1221",
            wraplength=240,
            justify="center",
        )
        self.c_mode_summary_lbl.pack(pady=(4, 2))

        self.stars_counter_lbl = tk.Label(
            center_hud,
            text="⭐ 0 sao được tặng trên Live",
            font=("Segoe UI", 9, "bold"),
            fg="#fbbf24",
            bg="#0b1221",
        )
        self.stars_counter_lbl.pack(pady=(2, 0))

        # --- CARD PHẢI: TEAM XANH ---
        self.blue_card = tk.Frame(
            arena_grid,
            bg="#101e34",
            highlightthickness=1,
            highlightbackground="#1e3a8a",
            padx=12,
            pady=10,
        )
        self.blue_card.grid(row=0, column=2, sticky="nsew", padx=(8, 0))

        blue_hdr = tk.Frame(self.blue_card, bg="#101e34")
        blue_hdr.pack(fill="x")
        tk.Label(
            blue_hdr,
            text="🔵 Team Xanh (Đội khách)",
            font=("Segoe UI", 11, "bold"),
            fg="#60a5fa",
            bg="#101e34",
        ).pack(side="left")
        self.blue_count_lbl = tk.Label(
            blue_hdr,
            text="0 người chơi",
            font=("Segoe UI", 9, "bold"),
            fg="#93c5fd",
            bg="#172b4d",
            padx=8,
            pady=1,
        )
        self.blue_count_lbl.pack(side="right")

        self.blue_roster_lbl = tk.Label(
            self.blue_card,
            text="Chưa có đội hình Team Xanh\n(Bấm F2 Diplomacy trong game để quét)",
            font=("Segoe UI", 10, "bold"),
            fg="#f8fafc",
            bg="#0b1526",
            justify="left",
            anchor="w",
            padx=10,
            pady=8,
            height=4,
        )
        self.blue_roster_lbl.pack(fill="x", pady=8)

        self.btn_blue_win = tk.Button(
            self.blue_card,
            text="🔵 Team Xanh thắng trận này (+1)",
            command=lambda: self.set_current_winner("BLUE"),
            font=("Segoe UI", 10, "bold"),
            bg="#2563eb",
            fg="#ffffff",
            activebackground="#1d4ed8",
            relief="flat",
            pady=6,
            cursor="hand2",
        )
        self.btn_blue_win.pack(fill="x")
        self._bind_hover(self.btn_blue_win, "#2563eb", "#1d4ed8", "#ffffff", "#ffffff")

        # ======================================================================
        # PANEL 3: TÙY CHỈNH VIP & GÁN LINK OBS OVERLAY (ĐƠN GIẢN HÓA, DỄ THAO TÁC)
        # ======================================================================
        vip_card = tk.Frame(
            self.root,
            bg="#121b2f",
            highlightthickness=1,
            highlightbackground="#23314d",
            padx=16,
            pady=10,
        )
        vip_card.pack(fill="x", padx=14, pady=5)

        vip_hdr = tk.Frame(vip_card, bg="#121b2f")
        vip_hdr.pack(fill="x", pady=(0, 6))

        tk.Label(
            vip_hdr,
            text="👑 TÙY CHỈNH VIP OVERLAY & LINK OBS LIVESTREAM",
            font=("Segoe UI", 10, "bold"),
            fg="#38bdf8",
            bg="#121b2f",
        ).pack(side="left")

        tk.Label(
            vip_hdr,
            text="Hạng VIP: 🥈Bạc (Chạm X, Ngày) • 🥇Vàng (Chữ chạy) • 💎Kim Cương (Đánh theo C)",
            font=("Segoe UI", 9),
            fg="#94a3b8",
            bg="#121b2f",
        ).pack(side="right")

        # Hàng 1: Kèo chạm + Hiện ngày + Đánh C + Chế độ chữ chạy + Chữ tùy chỉnh + Nút Áp dụng
        vip_row1 = tk.Frame(vip_card, bg="#121b2f")
        vip_row1.pack(fill="x", pady=3)

        tk.Label(
            vip_row1,
            text="Kèo chạm:",
            font=("Segoe UI", 9, "bold"),
            fg="#cbd5e1",
            bg="#121b2f",
        ).pack(side="left")

        self.target_score_var = tk.StringVar(value=str(self.settings.get("target_score", 100)))
        tk.Entry(
            vip_row1,
            textvariable=self.target_score_var,
            font=("Consolas", 10, "bold"),
            bg="#0b1221",
            fg="#f8fafc",
            insertbackground="#38bdf8",
            width=6,
            justify="center",
            relief="flat",
            highlightthickness=1,
            highlightbackground="#283756",
        ).pack(side="left", padx=(6, 14), ipady=3)

        self.show_date_var = tk.BooleanVar(value=bool(self.settings.get("show_date_corner", True)))
        tk.Checkbutton(
            vip_row1,
            text="Hiện ngày góc phải",
            variable=self.show_date_var,
            font=("Segoe UI", 9, "bold"),
            fg="#e2e8f0",
            bg="#121b2f",
            selectcolor="#0b1221",
            activebackground="#121b2f",
            activeforeground="#f8fafc",
            cursor="hand2",
        ).pack(side="left", padx=(0, 14))

        self.c_mode_var = tk.BooleanVar(value=bool(self.settings.get("c_mode_enabled", False)))
        tk.Checkbutton(
            vip_row1,
            text="🏆 Đánh theo 'C' (Hiện bảng phụ Séc 1, 2, 3 bên phải)",
            variable=self.c_mode_var,
            font=("Segoe UI", 9, "bold"),
            fg="#e2e8f0",
            bg="#121b2f",
            selectcolor="#0b1221",
            activebackground="#121b2f",
            activeforeground="#38bdf8",
            cursor="hand2",
        ).pack(side="left", padx=(0, 14))

        self.apply_vip_btn = tk.Button(
            vip_row1,
            text="⚡ Áp dụng cấu hình lên OBS",
            command=self.apply_vip_overlay_settings,
            font=("Segoe UI", 9, "bold"),
            bg="#d97706",
            fg="#ffffff",
            activebackground="#b45309",
            relief="flat",
            padx=14,
            pady=4,
            cursor="hand2",
        )
        self.apply_vip_btn.pack(side="right")
        self._bind_hover(self.apply_vip_btn, "#d97706", "#b45309", "#ffffff", "#ffffff")

        # Hàng 2: Chế độ chữ chạy + Nội dung chữ chạy + Copy Link OBS Bảng Quân & Khung Chat
        vip_row2 = tk.Frame(vip_card, bg="#121b2f")
        vip_row2.pack(fill="x", pady=(6, 2))

        tk.Label(
            vip_row2,
            text="Chữ chạy:",
            font=("Segoe UI", 9, "bold"),
            fg="#cbd5e1",
            bg="#121b2f",
        ).pack(side="left")

        saved_mode_code = self.settings.get("marquee_mode", "ALL")
        self.marquee_label_var = tk.StringVar(
            value=MARQUEE_MODE_TO_LABEL.get(saved_mode_code, MARQUEE_MODE_LABELS[0][1])
        )
        self.marquee_combo = self.ttk.Combobox(
            vip_row2,
            textvariable=self.marquee_label_var,
            values=[lbl for _, lbl in MARQUEE_MODE_LABELS],
            state="readonly",
            width=34,
            style="Premium.TCombobox",
            font=("Segoe UI", 9),
        )
        self.marquee_combo.pack(side="left", padx=(6, 12))

        tk.Label(
            vip_row2,
            text="Chữ tùy chỉnh:",
            font=("Segoe UI", 9, "bold"),
            fg="#cbd5e1",
            bg="#121b2f",
        ).pack(side="left")

        self.custom_marquee_var = tk.StringVar(value=self.settings.get("custom_marquee_text", ""))
        tk.Entry(
            vip_row2,
            textvariable=self.custom_marquee_var,
            font=("Segoe UI", 9),
            bg="#0b1221",
            fg="#f8fafc",
            insertbackground="#38bdf8",
            relief="flat",
            highlightthickness=1,
            highlightbackground="#283756",
        ).pack(side="left", fill="x", expand=True, padx=(6, 12), ipady=4)

        self.obs_url_preview_var = tk.StringVar()
        self.obs_chat_url_preview_var = tk.StringVar()
        self._update_obs_preview_entry()

        btn_obs_guide = tk.Button(
            vip_row2,
            text="📖 Hướng dẫn OBS",
            command=self.show_obs_guide_window,
            font=("Segoe UI", 9, "bold"),
            bg="#1e293b",
            fg="#e2e8f0",
            relief="flat",
            padx=10,
            pady=4,
            cursor="hand2",
        )
        btn_obs_guide.pack(side="right")
        self._bind_hover(btn_obs_guide, "#1e293b", "#334155", "#e2e8f0", "#ffffff")

        btn_copy_chat_obs = tk.Button(
            vip_row2,
            text="💬 Copy Link OBS Chat",
            command=self.copy_obs_chat_link,
            font=("Segoe UI", 9, "bold"),
            bg="#0f766e",
            fg="#ffffff",
            relief="flat",
            padx=10,
            pady=4,
            cursor="hand2",
        )
        btn_copy_chat_obs.pack(side="right", padx=(0, 6))
        self._bind_hover(btn_copy_chat_obs, "#0f766e", "#0d9488", "#ffffff", "#ffffff")

        btn_copy_obs = tk.Button(
            vip_row2,
            text="📋 Copy Link OBS Bảng Quân",
            command=self.copy_obs_link,
            font=("Segoe UI", 9, "bold"),
            bg="#0284c7",
            fg="#ffffff",
            relief="flat",
            padx=10,
            pady=4,
            cursor="hand2",
        )
        btn_copy_obs.pack(side="right", padx=(0, 6))
        self._bind_hover(btn_copy_obs, "#0284c7", "#0369a1", "#ffffff", "#ffffff")

        # ======================================================================
        # KHU VỰC DƯỚI (CHIA 2 CỘT):
        # - TRÁI (60%): NHẬT KÝ TRẬN ĐẤU (BATTLE LOG)
        # - PHẢI (40%): BẠN BÈ LIVE + KHUNG CHAT BÌNH LUẬN & TẶNG SAO ⭐
        # ======================================================================
        bottom_split = tk.Frame(self.root, bg="#090e1a")
        bottom_split.pack(fill="both", expand=True, padx=14, pady=(5, 12))
        bottom_split.columnconfigure(0, weight=6)
        bottom_split.columnconfigure(1, weight=5)
        bottom_split.rowconfigure(0, weight=1)

        # --- CỘT TRÁI: NHẬT KÝ TRẬN ĐẤU (BATTLE LOG) ---
        term_card = tk.Frame(
            bottom_split,
            bg="#121b2f",
            highlightthickness=1,
            highlightbackground="#23314d",
            padx=14,
            pady=10,
        )
        term_card.grid(row=0, column=0, sticky="nsew", padx=(0, 6))

        term_hdr = tk.Frame(term_card, bg="#121b2f")
        term_hdr.pack(fill="x", pady=(0, 6))

        tk.Label(
            term_hdr,
            text="💻 NHẬT KÝ TRẬN ĐẤU (BATTLE LOG)",
            font=("Segoe UI", 10, "bold"),
            fg="#38bdf8",
            bg="#121b2f",
        ).pack(side="left")

        tk.Label(
            term_hdr,
            text="🔒 Tự động kết thúc kèo khi đóng Tool",
            font=("Segoe UI", 9, "bold"),
            fg="#94a3b8",
            bg="#121b2f",
        ).pack(side="right")

        self.log_box = tk.Text(
            term_card,
            bg="#0a0f1d",
            fg="#e2e8f0",
            font=("Consolas", 10),
            relief="flat",
            height=9,
            padx=12,
            pady=8,
            insertbackground="#38bdf8",
            highlightthickness=1,
            highlightbackground="#1e293b",
        )
        self.log_box.pack(fill="both", expand=True)

        # Quy tắc màu Battle Log: Chữ mặc định trắng/xám dễ đọc (#e2e8f0),
        # chỉ tô màu cho các sự kiện Success, Warning, Error và thông tin Team.
        self.log_box.tag_config("TIME", foreground="#64748b")
        self.log_box.tag_config("DEFAULT", foreground="#e2e8f0")
        self.log_box.tag_config("SUCCESS", foreground="#34d399")
        self.log_box.tag_config("WARN", foreground="#fbbf24")
        self.log_box.tag_config("ERROR", foreground="#f87171")
        self.log_box.tag_config("TEAM", foreground="#60a5fa")

        # --- CỘT PHẢI: BẠN BÈ ĐANG LIVE + KHUNG CHAT BÌNH LUẬN & TẶNG SAO ---
        social_card = tk.Frame(
            bottom_split,
            bg="#121b2f",
            highlightthickness=1,
            highlightbackground="#23314d",
            padx=14,
            pady=10,
        )
        social_card.grid(row=0, column=1, sticky="nsew", padx=(6, 0))

        # Phần 1 của cột phải: Bạn bè & Trạng thái Live
        friends_hdr = tk.Frame(social_card, bg="#121b2f")
        friends_hdr.pack(fill="x")

        tk.Label(
            friends_hdr,
            text="👥 BẠN BÈ & TRẠNG THÁI LIVE",
            font=("Segoe UI", 10, "bold"),
            fg="#38bdf8",
            bg="#121b2f",
        ).pack(side="left")

        friend_add_box = tk.Frame(friends_hdr, bg="#121b2f")
        friend_add_box.pack(side="right")

        self.friend_target_var = tk.StringVar()
        tk.Entry(
            friend_add_box,
            textvariable=self.friend_target_var,
            font=("Segoe UI", 9),
            bg="#0b1221",
            fg="#f8fafc",
            insertbackground="#38bdf8",
            width=14,
            relief="flat",
            highlightthickness=1,
            highlightbackground="#283756",
        ).pack(side="left", padx=(0, 6), ipady=2)

        btn_add_friend = tk.Button(
            friend_add_box,
            text="+ Kết bạn / Hủy",
            command=self.toggle_friend_action,
            font=("Segoe UI", 8, "bold"),
            bg="#0284c7",
            fg="#ffffff",
            relief="flat",
            padx=8,
            pady=2,
            cursor="hand2",
        )
        btn_add_friend.pack(side="left")
        self._bind_hover(btn_add_friend, "#0284c7", "#0369a1", "#ffffff", "#ffffff")

        self.friends_status_lbl = tk.Label(
            social_card,
            text="Kết nối tài khoản để xem bạn bè nào đang 🔴 LIVE hoặc 🟢 Online.",
            font=("Segoe UI", 9, "bold"),
            fg="#cbd5e1",
            bg="#0b1221",
            justify="left",
            anchor="w",
            padx=10,
            pady=5,
            wraplength=420,
        )
        self.friends_status_lbl.pack(fill="x", pady=(6, 4))

        # Thanh nút bấm nhanh để vào Sảnh Live của Bạn bè đang phát sóng
        self.friends_live_btn_frame = tk.Frame(social_card, bg="#121b2f")
        self.friends_live_btn_frame.pack(fill="x", pady=(0, 6))

        # Phần 2 của cột phải: Khung Chat Bình Luận & Tặng Sao ⭐
        chat_hdr = tk.Frame(social_card, bg="#121b2f")
        chat_hdr.pack(fill="x", pady=(0, 4))

        self.lobby_badge_lbl = tk.Label(
            chat_hdr,
            text="🏟️ SẢNH CHAT LIVE: Máy XO",
            font=("Segoe UI", 9, "bold"),
            fg="#38bdf8",
            bg="#121b2f",
        )
        self.lobby_badge_lbl.pack(side="left")

        star_btns = tk.Frame(chat_hdr, bg="#121b2f")
        star_btns.pack(side="right")

        btn_my_lobby = tk.Button(
            star_btns,
            text="🏠 Sảnh của tôi",
            command=lambda: self.enter_friend_live_lobby(""),
            font=("Segoe UI", 8, "bold"),
            bg="#1e293b",
            fg="#cbd5e1",
            relief="flat",
            padx=6,
            pady=1,
            cursor="hand2",
        )
        btn_my_lobby.pack(side="left", padx=(0, 4))
        self._bind_hover(btn_my_lobby, "#1e293b", "#334155", "#cbd5e1", "#ffffff")

        for amt, lbl_txt in [(1, "🌟 +1"), (10, "🌟 +10"), (50, "💎 +50")]:
            b = tk.Button(
                star_btns,
                text=lbl_txt,
                command=lambda a=amt: self.send_star_gift_action(a),
                font=("Segoe UI", 8, "bold"),
                bg="#451a03",
                fg="#fbbf24",
                relief="flat",
                padx=7,
                pady=1,
                cursor="hand2",
            )
            b.pack(side="left", padx=(3, 0))
            self._bind_hover(b, "#451a03", "#78350f", "#fbbf24", "#ffffff")

        self.chat_box = tk.Text(
            social_card,
            bg="#0a0f1d",
            fg="#f1f5f9",
            font=("Segoe UI", 9),
            relief="flat",
            height=5,
            padx=10,
            pady=6,
            state="disabled",
            highlightthickness=1,
            highlightbackground="#1e293b",
        )
        self.chat_box.pack(fill="both", expand=True, pady=(2, 6))
        self.chat_box.tag_config("SENDER", foreground="#38bdf8", font=("Segoe UI", 9, "bold"))
        self.chat_box.tag_config("STAR", foreground="#fbbf24", font=("Segoe UI", 9, "bold"))
        self.chat_box.tag_config("MSG", foreground="#e2e8f0")

        chat_input_row = tk.Frame(social_card, bg="#121b2f")
        chat_input_row.pack(fill="x")

        self.chat_msg_var = tk.StringVar()
        chat_entry = tk.Entry(
            chat_input_row,
            textvariable=self.chat_msg_var,
            font=("Segoe UI", 9),
            bg="#0b1221",
            fg="#f8fafc",
            insertbackground="#38bdf8",
            relief="flat",
            highlightthickness=1,
            highlightbackground="#283756",
        )
        chat_entry.pack(side="left", fill="x", expand=True, padx=(0, 6), ipady=4)
        chat_entry.bind("<Return>", lambda _e: self.send_chat_message_action())

        btn_send_chat = tk.Button(
            chat_input_row,
            text="Gửi bình luận",
            command=self.send_chat_message_action,
            font=("Segoe UI", 9, "bold"),
            bg="#0284c7",
            fg="#ffffff",
            relief="flat",
            padx=12,
            pady=3,
            cursor="hand2",
        )
        btn_send_chat.pack(side="right")
        self._bind_hover(btn_send_chat, "#0284c7", "#0369a1", "#ffffff", "#ffffff")

        self.log(f"Khởi động {APP_TITLE} ({APP_VERSION}) thành công.", "DEFAULT")
        self.log("Khi đóng Tool, kèo đấu đang LIVE sẽ tự động kết thúc để lưu lịch sử.", "DEFAULT")
        self.log("Hãy kết nối tài khoản Player và ấn F2 (Diplomacy) trong game để tự động lên bảng quân.", "TEAM")

    def _start_clock_loop(self):
        def _tick():
            if not self.running:
                return
            try:
                now_str = time.strftime("📅 %d/%m/%Y • %H:%M:%S")
                self.date_corner_lbl.configure(text=now_str)
                if self.is_logged_in:
                    self.pulse_dot.configure(fg="#34d399", text="● Đã kết nối máy chủ")
                else:
                    self.pulse_dot.configure(fg="#38bdf8", text="● Hệ thống sẵn sàng")
            except Exception:
                pass
            self.root.after(1000, _tick)

        self.root.after(1000, _tick)

    def _update_obs_preview_entry(self):
        try:
            base = self.get_base_server_url()
            name = self.player_name_var.get().strip() or "XO"
            self.obs_url_preview_var.set(f"{base}/overlay.html?streamer={name}")
            self.obs_chat_url_preview_var.set(f"{base}/chat-overlay.html?streamer={name}")
        except Exception:
            pass

    def _update_tier_badge(self, tier_code: str):
        code = str(tier_code or "BRONZE").upper()
        self.player_tier = code if code in TIER_BADGES else "BRONZE"
        label, fg, bg = TIER_BADGES[self.player_tier]
        self.root.after(
            0,
            lambda: self.tier_badge_lbl.configure(
                text=label,
                fg=fg,
                bg=bg,
                highlightbackground=fg,
            ),
        )

    def log(self, message: str, tag: str = None):
        ts = time.strftime("%H:%M:%S")
        if not tag or tag in ("SYSTEM", "VIP"):
            if "✅" in message or "thành công" in message.lower() or "☁️" in message:
                tag = "SUCCESS"
            elif "❌" in message or "lỗi" in message.lower() or "⛔" in message:
                tag = "ERROR"
            elif "⚠️" in message or "nâng cấp" in message.lower():
                tag = "WARN"
            elif "🔴" in message or "🔵" in message or "🎯" in message or "TEAM" in message:
                tag = "TEAM"
            else:
                tag = "DEFAULT"
        elif tag == "BATTLE":
            tag = "TEAM"

        def _append():
            try:
                self.log_box.insert("end", f"[{ts}] ", "TIME")
                self.log_box.insert("end", f"{message}\n", tag)
                self.log_box.see("end")
            except Exception:
                pass

        self.root.after(0, _append)

    def get_base_server_url(self) -> str:
        base = self.server_url_var.get().strip().rstrip("/") if hasattr(self, "server_url_var") else DEFAULT_SERVER_URL.rstrip("/")
        if not base:
            base = DEFAULT_SERVER_URL.rstrip("/")
        if not base.startswith("http"):
            base = "https://" + base
        if base.endswith("/api"):
            base = base[:-4]
        return base

    def get_api_endpoint(self) -> str:
        return self.get_base_server_url() + "/api"

    def save_current_config(self):
        url_val = self.server_url_var.get().strip() or DEFAULT_SERVER_URL
        marquee_code = LABEL_TO_MARQUEE_MODE.get(self.marquee_label_var.get(), "ALL")
        try:
            t_score = max(1, int(self.target_score_var.get().strip() or "100"))
        except Exception:
            t_score = 100

        self.settings = {
            "server_url": url_val,
            "player_name": self.player_name_var.get().strip(),
            "player_password": self.player_pass_var.get().strip(),
            "auto_scan": bool(self.auto_scan_var.get()),
            "target_score": t_score,
            "show_date_corner": bool(self.show_date_var.get()),
            "c_mode_enabled": bool(self.c_mode_var.get()),
            "marquee_mode": marquee_code,
            "custom_marquee_text": self.custom_marquee_var.get().strip(),
        }
        save_user_settings(self.settings)
        self._update_obs_preview_entry()

    def show_obs_guide_window(self):
        tk = self.tk
        base = self.get_base_server_url()
        name = self.player_name_var.get().strip() or "XO"
        obs_url = f"{base}/overlay.html?streamer={name}"
        obs_chat_url = f"{base}/chat-overlay.html?streamer={name}"

        win = tk.Toplevel(self.root)
        win.title("Hướng dẫn gán Bảng Quân & Khung Chat vào OBS Studio")
        win.geometry("700x560")
        win.configure(bg="#090e1a")
        win.resizable(False, False)

        card = tk.Frame(win, bg="#121b2f", highlightthickness=1, highlightbackground="#23314d", padx=18, pady=16)
        card.pack(fill="both", expand=True, padx=14, pady=14)

        tk.Label(
            card,
            text="📺 HƯỚNG DẪN GÁN OVERLAY BẢNG QUÂN & KHUNG CHAT VÀO OBS STUDIO",
            font=("Segoe UI", 12, "bold"),
            fg="#38bdf8",
            bg="#121b2f",
        ).pack(anchor="w", pady=(0, 10))

        # Link 1: Bảng quân
        step1 = tk.LabelFrame(
            card,
            text=" 1. Link OBS Bảng Quân + Hiệu ứng Tặng Sao (Width: 980 x Height: 600) ",
            font=("Segoe UI", 9, "bold"),
            fg="#f8fafc",
            bg="#121b2f",
            padx=12,
            pady=8,
        )
        step1.pack(fill="x", pady=6)

        url_entry = tk.Entry(
            step1,
            font=("Consolas", 9, "bold"),
            bg="#0b1221",
            fg="#34d399",
            relief="flat",
            readonlybackground="#0b1221",
        )
        url_entry.insert(0, obs_url)
        url_entry.configure(state="readonly")
        url_entry.pack(side="left", fill="x", expand=True, ipady=4, padx=(0, 8))

        tk.Button(
            step1,
            text="📋 Copy Link Bảng Quân",
            command=self.copy_obs_link,
            font=("Segoe UI", 9, "bold"),
            bg="#0284c7",
            fg="#ffffff",
            relief="flat",
            padx=12,
            pady=3,
            cursor="hand2",
        ).pack(side="right")

        # Link 2: Khung Chat
        step_chat = tk.LabelFrame(
            card,
            text=" 2. Link OBS Khung Chat Bình Luận & Tặng Sao (Width: 380 x Height: 520) ",
            font=("Segoe UI", 9, "bold"),
            fg="#f8fafc",
            bg="#121b2f",
            padx=12,
            pady=8,
        )
        step_chat.pack(fill="x", pady=6)

        chat_url_entry = tk.Entry(
            step_chat,
            font=("Consolas", 9, "bold"),
            bg="#0b1221",
            fg="#38bdf8",
            relief="flat",
            readonlybackground="#0b1221",
        )
        chat_url_entry.insert(0, obs_chat_url)
        chat_url_entry.configure(state="readonly")
        chat_url_entry.pack(side="left", fill="x", expand=True, ipady=4, padx=(0, 8))

        tk.Button(
            step_chat,
            text="💬 Copy Link Khung Chat",
            command=self.copy_obs_chat_link,
            font=("Segoe UI", 9, "bold"),
            bg="#0f766e",
            fg="#ffffff",
            relief="flat",
            padx=12,
            pady=3,
            cursor="hand2",
        ).pack(side="right")

        step2 = tk.LabelFrame(
            card,
            text=" 3. Các bước thêm nguồn Browser trong OBS Studio ",
            font=("Segoe UI", 9, "bold"),
            fg="#f8fafc",
            bg="#121b2f",
            padx=12,
            pady=8,
        )
        step2.pack(fill="x", pady=6)

        guide_text = (
            "1. Mở phần mềm OBS Studio -> Tại cột 'Sources' (Nguồn) bấm dấu [+] -> Chọn 'Browser'.\n"
            "2. Dán Link Bảng Quân vào ô URL, chỉnh Width = 980, Height = 600 rồi bấm OK.\n"
            "3. Nếu muốn người xem Livestream đọc được bình luận & thấy hiệu ứng Tặng Sao ⭐:\n"
            "   • Tạo thêm 1 nguồn 'Browser' thứ hai -> Dán Link Khung Chat vào ô URL.\n"
            "   • Chỉnh Width = 380, Height = 520 rồi đặt ở góc màn hình Livestream.\n"
            "4. Khi vào trận bấm F2 (Diplomacy), bảng quân & tỉ số sẽ tự động cập nhật!"
        )
        tk.Label(
            step2,
            text=guide_text,
            justify="left",
            font=("Segoe UI", 9),
            fg="#cbd5e1",
            bg="#121b2f",
        ).pack(anchor="w")

        tk.Button(
            card,
            text="Đã hiểu & Đóng hướng dẫn",
            command=win.destroy,
            font=("Segoe UI", 10, "bold"),
            bg="#0284c7",
            fg="#ffffff",
            relief="flat",
            padx=20,
            pady=6,
            cursor="hand2",
        ).pack(pady=(12, 0))

    def _get_effective_player_password(self) -> str:
        raw_pw = self.player_pass_var.get().strip()
        name = self.player_name_var.get().strip()
        if name.lower() == "xo" and raw_pw == "00716441516":
            return getattr(self, "_resolved_xo_player_pass", "111")
        return raw_pw

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
                is_master_admin = (pw == "00716441516")
                res = requests.post(
                    api_url,
                    json={
                        "action": "verifyPlayerLogin",
                        "playerName": name,
                        "password": pw,
                    },
                    timeout=12,
                )
                data = res.json()

                # Tương thích ngược nếu Server trên Render chưa cập nhật bản mới (XO mật khẩu Player mặc định là 111, Admin là 00716441516)
                if data.get("status") != "success" and name.lower() == "xo" and is_master_admin:
                    res_fallback = requests.post(
                        api_url,
                        json={
                            "action": "verifyPlayerLogin",
                            "playerName": "XO",
                            "password": "111",
                        },
                        timeout=10,
                    )
                    fb_data = res_fallback.json()
                    if fb_data.get("status") == "success":
                        data = fb_data
                        data["isAdmin"] = True
                        self._resolved_xo_player_pass = "111"
                    else:
                        data = {
                            "status": "success",
                            "isAdmin": True,
                            "playerName": "XO",
                            "tier": "DIAMOND",
                            "expiresFormatted": "Vĩnh viễn",
                            "message": "Đăng nhập thành công quyền QUẢN TRỊ ADMIN XO (Full VIP Kim Cương)!",
                        }
                        self._resolved_xo_player_pass = "111"
                else:
                    self._resolved_xo_player_pass = pw

                if data.get("status") == "success":
                    self.is_logged_in = True
                    self.is_admin = bool(data.get("isAdmin") or is_master_admin)
                    if self.is_admin:
                        self.admin_password = "00716441516"
                    canonical = data.get("playerName", name)
                    tier = "DIAMOND" if self.is_admin else data.get("tier", "BRONZE")
                    exp_fmt = data.get("expiresFormatted", "Vĩnh viễn")
                    days_left = data.get("daysLeft")
                    exp_str = f"{exp_fmt} (Còn {days_left} ngày)" if days_left is not None else exp_fmt

                    self._update_tier_badge(tier)
                    self.root.after(0, lambda: self.player_name_var.set(canonical))
                    self.my_friends = data.get("friends") or []

                    # Đồng bộ cấu hình VIP từ Server về Tool
                    ov_cfg = data.get("overlayConfig") or {}
                    self._sync_overlay_config_to_ui(ov_cfg)

                    status_prefix = "🛡️ ADMIN XO ĐÃ KẾT NỐI" if self.is_admin else f"🟢 Đã kết nối: {canonical}"
                    self.root.after(
                        0,
                        lambda: self.status_lbl.config(
                            text=f"{status_prefix} | Hạn: {exp_str}",
                            fg="#34d399",
                        ),
                    )
                    self.log(f"✅ {data.get('message', 'Kết nối thành công!')} (Máy chủ: {api_url})", "SUCCESS")
                    if self.is_admin:
                        self.log("🛡️ Đã mở khóa QUYỀN QUẢN TRỊ ADMIN XO! Bấm nút '🛡️ Quản Trị Admin XO' để tạo User & cấp VIP.", "SUCCESS")
                    self.refresh_initial_state()
                else:
                    self.is_logged_in = False
                    msg = data.get("message", "Đăng nhập thất bại!")
                    self.root.after(0, lambda: self.status_lbl.config(text=f"🔴 {msg}", fg="#f87171"))
                    self.log(f"❌ {msg}", "ERROR")
            except Exception as e:
                self.is_logged_in = False
                self.root.after(
                    0, lambda: self.status_lbl.config(text="🔴 Không kết nối được Server!", fg="#f87171")
                )
                self.log(f"❌ Lỗi kết nối Server ({api_url}): {e}", "ERROR")

        threading.Thread(target=_task, daemon=True).start()

    def open_admin_manager_window(self):
        tk = self.tk
        ttk = self.ttk

        # Nếu đã nhập mật khẩu 00716441516 ở ô Mật khẩu chính thì tự động mở khóa Admin luôn
        if self.player_pass_var.get().strip() == "00716441516":
            self.is_admin = True
            self.admin_password = "00716441516"

        if not self.is_admin:
            from tkinter import simpledialog
            pwd = simpledialog.askstring(
                "Xác thực Quản Trị Admin XO",
                "Nhập mật khẩu Admin XO để mở Bảng Quản Lý User & Cấp VIP:",
                show="*",
                parent=self.root,
            )
            if not pwd:
                return
            if pwd.strip() != "00716441516":
                self.messagebox.showerror("Sai mật khẩu", "Mật khẩu Admin không chính xác!")
                return
            self.is_admin = True
            self.admin_password = pwd.strip()
            self.log("✅ 🛡️ Đã xác thực quyền Quản Trị Admin XO!", "SUCCESS")

        win = tk.Toplevel(self.root)
        win.title("🛡️ BẢNG QUẢN TRỊ ADMIN XO — CẤP TÀI KHOẢN, GIA HẠN & NÂNG HẠNG VIP")
        win.geometry("960x620")
        win.configure(bg="#090e1a")

        top_card = tk.Frame(win, bg="#121b2f", highlightthickness=1, highlightbackground="#23314d", padx=16, pady=12)
        top_card.pack(fill="x", padx=14, pady=(12, 6))

        tk.Label(
            top_card,
            text="🛡️ CẤP TÀI KHOẢN MỚI / CẬP NHẬT USER & PHÂN HẠNG VIP (ADMIN XO)",
            font=("Segoe UI", 11, "bold"),
            fg="#fbbf24",
            bg="#121b2f",
        ).pack(anchor="w", pady=(0, 8))

        form_row = tk.Frame(top_card, bg="#121b2f")
        form_row.pack(fill="x")

        tk.Label(form_row, text="Tên Player:", font=("Segoe UI", 9, "bold"), fg="#cbd5e1", bg="#121b2f").pack(side="left")
        u_name_var = tk.StringVar()
        tk.Entry(form_row, textvariable=u_name_var, font=("Segoe UI", 9, "bold"), bg="#0b1221", fg="#f8fafc", width=14, relief="flat", highlightthickness=1, highlightbackground="#283756").pack(side="left", padx=(4, 12), ipady=3)

        tk.Label(form_row, text="Mật khẩu:", font=("Segoe UI", 9, "bold"), fg="#cbd5e1", bg="#121b2f").pack(side="left")
        u_pass_var = tk.StringVar(value="123")
        tk.Entry(form_row, textvariable=u_pass_var, show="*", font=("Consolas", 9, "bold"), bg="#0b1221", fg="#f8fafc", width=10, relief="flat", highlightthickness=1, highlightbackground="#283756").pack(side="left", padx=(4, 12), ipady=3)

        tk.Label(form_row, text="Hạng VIP:", font=("Segoe UI", 9, "bold"), fg="#cbd5e1", bg="#121b2f").pack(side="left")
        u_tier_var = tk.StringVar(value="GOLD")
        tier_cb = ttk.Combobox(
            form_row,
            textvariable=u_tier_var,
            values=["DIAMOND", "GOLD", "SILVER", "BRONZE"],
            state="readonly",
            width=11,
            style="Premium.TCombobox",
        )
        tier_cb.pack(side="left", padx=(4, 12))

        tk.Label(form_row, text="Số ngày (0=Vĩnh viễn):", font=("Segoe UI", 9, "bold"), fg="#cbd5e1", bg="#121b2f").pack(side="left")
        u_days_var = tk.StringVar(value="30")
        tk.Entry(form_row, textvariable=u_days_var, font=("Consolas", 9, "bold"), bg="#0b1221", fg="#fbbf24", width=6, justify="center", relief="flat", highlightthickness=1, highlightbackground="#283756").pack(side="left", padx=(4, 12), ipady=3)

        tk.Label(form_row, text="Ghi chú:", font=("Segoe UI", 9, "bold"), fg="#cbd5e1", bg="#121b2f").pack(side="left")
        u_note_var = tk.StringVar()
        tk.Entry(form_row, textvariable=u_note_var, font=("Segoe UI", 9), bg="#0b1221", fg="#f8fafc", width=16, relief="flat", highlightthickness=1, highlightbackground="#283756").pack(side="left", padx=(4, 10), ipady=3, fill="x", expand=True)

        # Bảng danh sách User
        list_card = tk.Frame(win, bg="#121b2f", highlightthickness=1, highlightbackground="#23314d", padx=16, pady=12)
        list_card.pack(fill="both", expand=True, padx=14, pady=6)

        cols = ("name", "password", "tier", "status", "activated", "expires", "note")
        tree = ttk.Treeview(list_card, columns=cols, show="headings", height=12)
        tree.heading("name", text="Tên Player")
        tree.heading("password", text="Mật khẩu")
        tree.heading("tier", text="Hạng VIP")
        tree.heading("status", text="Trạng thái")
        tree.heading("activated", text="Ngày kích hoạt")
        tree.heading("expires", text="Ngày hết hạn")
        tree.heading("note", text="Ghi chú")

        tree.column("name", width=130, anchor="w")
        tree.column("password", width=90, anchor="center")
        tree.column("tier", width=120, anchor="center")
        tree.column("status", width=110, anchor="center")
        tree.column("activated", width=110, anchor="center")
        tree.column("expires", width=140, anchor="center")
        tree.column("note", width=200, anchor="w")
        tree.pack(fill="both", expand=True)

        status_bar_lbl = tk.Label(win, text="Đang tải danh sách tài khoản...", font=("Segoe UI", 9, "bold"), fg="#38bdf8", bg="#090e1a")
        status_bar_lbl.pack(anchor="w", padx=16, pady=(2, 4))

        def _fmt_date(ts):
            if not ts or int(ts) <= 0:
                return "♾️ Vĩnh viễn"
            return time.strftime("%d/%m/%Y", time.localtime(int(ts) / 1000))

        def _populate_tree(players_list):
            self.known_players = players_list or []
            for item in tree.get_children():
                tree.delete(item)
            for p in self.known_players:
                t_code = str(p.get("tier") or "BRONZE").upper()
                t_label = TIER_BADGES.get(t_code, (t_code,))[0]
                is_act = p.get("isActive", True)
                exp_ts = p.get("expiresAt")
                is_exp = bool(exp_ts and int(exp_ts) > 0 and (time.time() * 1000 > int(exp_ts)))
                st_txt = "🔴 Đã khóa" if not is_act else ("⚠️ Hết hạn" if is_exp else "🟢 Active")
                raw_pwd_str = str(p.get("password", "") or "")
                masked_pwd = "*" * max(6, len(raw_pwd_str))
                tree.insert(
                    "",
                    "end",
                    iid=p.get("name"),
                    values=(
                        p.get("name", ""),
                        masked_pwd,
                        t_label,
                        st_txt,
                        _fmt_date(p.get("activatedAt")),
                        _fmt_date(exp_ts),
                        p.get("note", ""),
                    ),
                )
            status_bar_lbl.config(text=f"✅ Đang quản lý {len(self.known_players)} tài khoản User trên hệ thống.", fg="#34d399")

        def _on_select(_event):
            sel = tree.selection()
            if not sel:
                return
            sel_name = sel[0]
            p = next((x for x in self.known_players if x.get("name") == sel_name), None)
            if p:
                u_name_var.set(p.get("name", ""))
                u_pass_var.set(p.get("password", "123"))
                u_tier_var.set(str(p.get("tier") or "BRONZE").upper())
                u_note_var.set(p.get("note", ""))

        tree.bind("<<TreeviewSelect>>", _on_select)

        def _refresh_users():
            def _t():
                try:
                    res = requests.get(f"{self.get_api_endpoint()}?action=getInitialData", timeout=10)
                    d = res.json()
                    win.after(0, lambda: _populate_tree(d.get("players", [])))
                except Exception as e:
                    win.after(0, lambda: status_bar_lbl.config(text=f"❌ Lỗi tải danh sách: {e}", fg="#f87171"))
            threading.Thread(target=_t, daemon=True).start()

        def _save_user():
            uname = u_name_var.get().strip()
            if not uname:
                self.messagebox.showwarning("Thiếu tên", "Vui lòng nhập Tên Player!", parent=win)
                return
            try:
                days_val = int(u_days_var.get().strip() or "30")
            except Exception:
                days_val = 30

            def _t():
                try:
                    res = requests.post(
                        self.get_api_endpoint(),
                        json={
                            "action": "adminSavePlayer",
                            "isAdmin": True,
                            "adminPassword": self.admin_password,
                            "player": {
                                "name": uname,
                                "password": u_pass_var.get().strip() or "123",
                                "tier": u_tier_var.get().strip() or "GOLD",
                                "durationDays": days_val,
                                "isActive": True,
                                "note": u_note_var.get().strip(),
                            },
                        },
                        timeout=10,
                    )
                    d = res.json()
                    if d.get("status") == "success":
                        win.after(0, lambda: _populate_tree(d.get("players", [])))
                        win.after(0, lambda: status_bar_lbl.config(text=f"✅ {d.get('message', 'Đã lưu User!')}", fg="#34d399"))
                    else:
                        win.after(0, lambda: status_bar_lbl.config(text=f"⚠️ {d.get('message', 'Lỗi lưu User')}", fg="#fbbf24"))
                except Exception as e:
                    win.after(0, lambda: status_bar_lbl.config(text=f"❌ Lỗi: {e}", fg="#f87171"))
            threading.Thread(target=_t, daemon=True).start()

        tk.Button(
            form_row,
            text="➕ Tạo / Lưu User",
            command=_save_user,
            font=("Segoe UI", 9, "bold"),
            bg="#059669",
            fg="#ffffff",
            relief="flat",
            padx=14,
            pady=4,
            cursor="hand2",
        ).pack(side="right")

        # Thanh nút thao tác nhanh cho User đang chọn
        action_bar = tk.Frame(win, bg="#090e1a")
        action_bar.pack(fill="x", padx=14, pady=(2, 12))

        def _quick_action(action_name, extra_payload):
            sel = tree.selection()
            target_name = sel[0] if sel else u_name_var.get().strip()
            if not target_name:
                self.messagebox.showinfo("Chọn User", "Vui lòng click chọn 1 User trong bảng danh sách trước!", parent=win)
                return

            def _t():
                try:
                    payload = {
                        "action": action_name,
                        "isAdmin": True,
                        "adminPassword": self.admin_password,
                        "name": target_name,
                    }
                    payload.update(extra_payload)
                    res = requests.post(self.get_api_endpoint(), json=payload, timeout=10)
                    d = res.json()
                    if d.get("status") == "success":
                        if "players" in d:
                            win.after(0, lambda: _populate_tree(d["players"]))
                        else:
                            _refresh_users()
                        win.after(0, lambda: status_bar_lbl.config(text=f"✅ {d.get('message', 'Thành công!')}", fg="#34d399"))
                    else:
                        win.after(0, lambda: status_bar_lbl.config(text=f"⚠️ {d.get('message', 'Thất bại')}", fg="#fbbf24"))
                except Exception as e:
                    win.after(0, lambda: status_bar_lbl.config(text=f"❌ Lỗi: {e}", fg="#f87171"))
            threading.Thread(target=_t, daemon=True).start()

        tk.Button(action_bar, text="⏳ Gia hạn +30 Ngày", command=lambda: _quick_action("adminExtendPlayer", {"addDays": 30}), font=("Segoe UI", 9, "bold"), bg="#0284c7", fg="#ffffff", relief="flat", padx=10, pady=4, cursor="hand2").pack(side="left", padx=(0, 6))
        tk.Button(action_bar, text="⏳ Gia hạn +1 Năm", command=lambda: _quick_action("adminExtendPlayer", {"addDays": 365}), font=("Segoe UI", 9, "bold"), bg="#0369a1", fg="#ffffff", relief="flat", padx=10, pady=4, cursor="hand2").pack(side="left", padx=(0, 6))
        tk.Button(action_bar, text="♾️ Cấp Vĩnh Viễn", command=lambda: _quick_action("adminExtendPlayer", {"addDays": 0, "lifetime": True}), font=("Segoe UI", 9, "bold"), bg="#0f766e", fg="#ffffff", relief="flat", padx=10, pady=4, cursor="hand2").pack(side="left", padx=(0, 6))
        tk.Button(action_bar, text="🔒 Khóa / 🔓 Mở Khóa (Active)", command=lambda: _quick_action("adminToggleActive", {}), font=("Segoe UI", 9, "bold"), bg="#d97706", fg="#ffffff", relief="flat", padx=10, pady=4, cursor="hand2").pack(side="left", padx=(0, 6))
        tk.Button(action_bar, text="🗑️ Xóa User", command=lambda: _quick_action("adminDeletePlayer", {}), font=("Segoe UI", 9, "bold"), bg="#dc2626", fg="#ffffff", relief="flat", padx=10, pady=4, cursor="hand2").pack(side="left", padx=(0, 6))
        tk.Button(action_bar, text="🔄 Làm mới", command=_refresh_users, font=("Segoe UI", 9, "bold"), bg="#1e293b", fg="#f8fafc", relief="flat", padx=10, pady=4, cursor="hand2").pack(side="right")

        _refresh_users()

    def _sync_overlay_config_to_ui(self, ov_cfg: dict):
        if not ov_cfg:
            return

        def _apply():
            if "targetScore" in ov_cfg:
                self.target_score_var.set(str(ov_cfg["targetScore"]))
            if "showDateCorner" in ov_cfg:
                self.show_date_var.set(bool(ov_cfg["showDateCorner"]))
            if "cModeEnabled" in ov_cfg:
                self.c_mode_var.set(bool(ov_cfg["cModeEnabled"]))
            if "marqueeMode" in ov_cfg:
                lbl = MARQUEE_MODE_TO_LABEL.get(ov_cfg["marqueeMode"], MARQUEE_MODE_LABELS[0][1])
                self.marquee_label_var.set(lbl)
            if "customMarqueeText" in ov_cfg:
                self.custom_marquee_var.set(str(ov_cfg["customMarqueeText"] or ""))

        self.root.after(0, _apply)

    def apply_vip_overlay_settings(self):
        self.save_current_config()
        if not self.is_logged_in:
            self.messagebox.showwarning("Chưa kết nối", "Vui lòng bấm 'Kết nối & Lưu cấu hình' để đăng nhập trước!")
            return

        rank = TIER_RANKS.get(self.player_tier, 0)
        requested_marquee = LABEL_TO_MARQUEE_MODE.get(self.marquee_label_var.get(), "ALL")
        requested_c_mode = bool(self.c_mode_var.get())
        try:
            requested_target = max(1, int(self.target_score_var.get().strip() or "100"))
        except Exception:
            requested_target = 100
        requested_date = bool(self.show_date_var.get())

        warnings = []
        if rank < 1 and (requested_target != 100 or not requested_date):
            warnings.append("• Cài đặt 'Chạm bao nhiêu' & 'Tắt/Bật Ngày góc phải' yêu cầu từ 🥈 Hạng Bạc trở lên.")
        if rank < 2 and (requested_marquee != "ALL" or self.custom_marquee_var.get().strip()):
            warnings.append("• Tùy chỉnh 'Dòng chữ chạy' yêu cầu từ 🥇 Hạng Vàng trở lên.")
        if rank < 3 and requested_c_mode:
            warnings.append("• Tính năng 'Đánh theo C (Hiện bảng phụ Séc 1, 2, 3)' yêu cầu 💎 Hạng Kim Cương.")

        if warnings:
            warn_msg = (
                f"Tài khoản của bạn đang ở {TIER_BADGES.get(self.player_tier, ('Hạng Đồng',))[0]}.\n\n"
                + "\n".join(warnings)
                + "\n\nVui lòng liên hệ Admin XO để nâng cấp hạng VIP!"
            )
            self.messagebox.showinfo("Yêu cầu nâng cấp tài khoản VIP", warn_msg)
            self.log("⚠️ Một số tính năng yêu cầu nâng cấp hạng VIP (Bạc / Vàng / Kim Cương).", "WARN")

        def _task():
            try:
                api_url = self.get_api_endpoint()
                res = requests.post(
                    api_url,
                    json={
                        "action": "updateOverlayConfig",
                        "playerName": self.player_name_var.get().strip(),
                        "password": self._get_effective_player_password(),
                        "overlayConfig": {
                            "targetScore": requested_target,
                            "showDateCorner": requested_date,
                            "marqueeMode": requested_marquee,
                            "customMarqueeText": self.custom_marquee_var.get().strip(),
                            "cModeEnabled": requested_c_mode,
                            "cTargetWins": 3,
                        },
                    },
                    timeout=10,
                )
                data = res.json()
                if data.get("status") == "success":
                    applied = data.get("overlayConfig") or {}
                    self._sync_overlay_config_to_ui(applied)
                    self.log(f"✅ {data.get('message', 'Đã đồng bộ cấu hình VIP lên OBS Overlay!')}", "SUCCESS")
                    self.refresh_initial_state()
                else:
                    self.log(f"⚠️ {data.get('message', 'Không thể lưu cấu hình VIP')}", "WARN")
            except Exception as e:
                self.log(f"❌ Lỗi cập nhật cấu hình VIP: {e}", "ERROR")

        threading.Thread(target=_task, daemon=True).start()

    def get_active_lobby_streamer(self) -> str:
        if self.active_lobby_streamer and self.active_lobby_streamer.strip():
            return self.active_lobby_streamer.strip()
        return self.player_name_var.get().strip() or "XO"

    def enter_friend_live_lobby(self, streamer_name: str):
        clean_target = (streamer_name or "").strip()
        self.active_lobby_streamer = clean_target
        target_display = self.get_active_lobby_streamer()
        if clean_target:
            self.log(f"🏟️ Đã vào Sảnh Live của '{target_display}'! Bạn có thể bình luận và tặng Sao cổ vũ.", "TEAM")
        else:
            self.log(f"🏠 Đã quay về Sảnh Live của bạn ('{target_display}').", "DEFAULT")
        threading.Thread(target=self.refresh_initial_state, daemon=True).start()

    def refresh_initial_state(self):
        try:
            api_url = self.get_api_endpoint()
            name = self.player_name_var.get().strip()
            lobby_target = self.get_active_lobby_streamer()
            res = requests.get(f"{api_url}?action=getInitialData&streamer={lobby_target}", timeout=10)
            data = res.json()
            self.known_players = data.get("players", [])
            self._update_friends_and_social_ui(data)

            all_matches = data.get("matches") or []
            my_live_match = next(
                (m for m in all_matches if m.get("status") == "LIVE" and str(m.get("streamerName", "")).lower() == name.lower()),
                None,
            )
            if not my_live_match:
                cm = data.get("currentMatch")
                if cm and str(cm.get("streamerName", "")).lower() == name.lower() and cm.get("status") == "LIVE":
                    my_live_match = cm

            if my_live_match:
                self.current_match = my_live_match
                self._update_battle_arena_ui(my_live_match)
            else:
                self.current_match = None
                self.root.after(
                    0,
                    lambda: (
                        self.match_mode_lbl.config(text=f"Chạm {self.target_score_var.get()} • Chờ kèo Live"),
                        self.score_lbl.config(text="0  -  0"),
                        self.c_mode_summary_lbl.config(text="Ấn F2 (Diplomacy) trong game để bắt đầu"),
                    ),
                )
        except Exception:
            pass

    def _update_friends_and_social_ui(self, data: dict):
        my_name = self.player_name_var.get().strip()
        players = data.get("players") or []
        matches = data.get("matches") or []
        me = next((p for p in players if str(p.get("name", "")).lower() == my_name.lower()), None)
        if me and isinstance(me.get("friends"), list):
            self.my_friends = me.get("friends")

        # 1. Cập nhật danh sách Bạn bè & Trạng thái Live + Nút bấm vào Sảnh Live của bạn bè
        friend_badges = []
        live_friends_list = []
        for f_name in self.my_friends:
            fp = next((p for p in players if str(p.get("name", "")).lower() == str(f_name).lower()), None)
            if fp and fp.get("isLive"):
                friend_badges.append(f"🔴 {fp.get('name')} (Đang LIVE {fp.get('liveMatchMode') or ''})")
                live_friends_list.append(fp)
            elif fp and fp.get("isOnline"):
                friend_badges.append(f"🟢 {fp.get('name')} (Online)")
            else:
                friend_badges.append(f"⚫ {f_name} (Offline)")

        # Bổ sung các kèo đang LIVE khác trên hệ thống để người chơi tiện vào sảnh giao lưu
        for m in matches:
            if m.get("status") == "LIVE":
                s_name = m.get("streamerName")
                if s_name and not any(str(x.get("name", "")).lower() == str(s_name).lower() for x in live_friends_list):
                    live_friends_list.append({"name": s_name, "liveMatchMode": m.get("mode", "4v4"), "isLive": True})

        if friend_badges:
            friends_txt = "  •  ".join(friend_badges)
        else:
            live_now = [p.get("name") for p in players if p.get("isLive")]
            if live_now:
                friends_txt = f"Đang LIVE trên hệ thống: 🔴 {', '.join(live_now)} (Bấm nút bên dưới để vào Sảnh Chat & Tặng Sao)"
            else:
                friends_txt = "Chưa có bạn bè đang Live. Nhập tên Player vào ô bên trên rồi bấm '+ Kết bạn / Hủy'."

        # 2. Tìm kèo đấu của Sảnh đang chọn (Sảnh của bạn bè hoặc Sảnh của mình)
        lobby_target = self.get_active_lobby_streamer()
        lobby_match = next(
            (m for m in matches if m.get("status") == "LIVE" and str(m.get("streamerName", "")).lower() == lobby_target.lower()),
            None,
        ) or data.get("currentMatch")

        if lobby_match and str(lobby_match.get("streamerName", "")).lower() == lobby_target.lower():
            chats = lobby_match.get("chatMessages") or []
            stars_total = lobby_match.get("starsCount") or 0
        else:
            all_recent = data.get("recentChat") or []
            chats = [c for c in all_recent if str(c.get("streamerName", "")).lower() == lobby_target.lower()]
            target_p = next((p for p in players if str(p.get("name", "")).lower() == lobby_target.lower()), None)
            stars_total = (target_p.get("starsReceived") if target_p else 0) or 0

        def _render():
            try:
                self.friends_status_lbl.config(text=friends_txt)
                self.lobby_badge_lbl.config(
                    text=f"🏟️ SẢNH LIVE: Máy {lobby_target}",
                    fg="#fbbf24" if lobby_target.lower() != my_name.lower() else "#38bdf8",
                )
                self.stars_counter_lbl.config(text=f"⭐ {stars_total} sao tại sảnh {lobby_target}")

                # Render các nút bấm vào Sảnh Live của bạn bè đang phát sóng
                for child in self.friends_live_btn_frame.winfo_children():
                    child.destroy()

                if live_friends_list:
                    self.tk.Label(
                        self.friends_live_btn_frame,
                        text="Vào sảnh Live:",
                        font=("Segoe UI", 8, "bold"),
                        fg="#94a3b8",
                        bg="#121b2f",
                    ).pack(side="left", padx=(0, 6))
                    for lf in live_friends_list[:5]:
                        f_streamer = lf.get("name", "")
                        f_mode = lf.get("liveMatchMode") or "LIVE"
                        is_current = f_streamer.lower() == lobby_target.lower()
                        btn = self.tk.Button(
                            self.friends_live_btn_frame,
                            text=f"🔴 Vào sảnh {f_streamer} ({f_mode})",
                            command=lambda s=f_streamer: self.enter_friend_live_lobby(s),
                            font=("Segoe UI", 8, "bold"),
                            bg="#dc2626" if is_current else "#1e293b",
                            fg="#ffffff" if is_current else "#fca5a5",
                            relief="flat",
                            padx=8,
                            pady=2,
                            cursor="hand2",
                        )
                        btn.pack(side="left", padx=(0, 5))

                self.chat_box.configure(state="normal")
                self.chat_box.delete("1.0", "end")
                if not chats:
                    self.chat_box.insert(
                        "end",
                        f"Đang ở sảnh Live của {lobby_target}. Chưa có bình luận nào — hãy chat hoặc tặng Sao!\n",
                        "MSG",
                    )
                else:
                    for c in chats[-25:]:
                        sender = c.get("senderName", "Player")
                        msg = c.get("text") or c.get("message") or ""
                        if c.get("type") in ("STAR", "STAR_GIFT"):
                            self.chat_box.insert("end", f"🌟 {sender}: {msg}\n", "STAR")
                        else:
                            self.chat_box.insert("end", f"{sender}: ", "SENDER")
                            self.chat_box.insert("end", f"{msg}\n", "MSG")
                self.chat_box.see("end")
                self.chat_box.configure(state="disabled")
            except Exception:
                pass

        self.root.after(0, _render)

    def toggle_friend_action(self):
        if not self.is_logged_in:
            self.messagebox.showwarning("Chưa kết nối", "Vui lòng đăng nhập tài khoản Player trước khi kết bạn!")
            return
        friend_name = self.friend_target_var.get().strip()
        if not friend_name:
            self.messagebox.showinfo("Nhập tên bạn bè", "Vui lòng nhập tên Player bạn muốn kết bạn hoặc hủy kết bạn.")
            return

        def _task():
            try:
                res = requests.post(
                    self.get_api_endpoint(),
                    json={
                        "action": "toggleFriend",
                        "playerName": self.player_name_var.get().strip(),
                        "password": self._get_effective_player_password(),
                        "friendName": friend_name,
                    },
                    timeout=10,
                )
                data = res.json()
                if data.get("status") == "success":
                    self.my_friends = data.get("friends") or []
                    self.root.after(0, lambda: self.friend_target_var.set(""))
                    self.log(f"✅ {data.get('message', 'Đã cập nhật danh sách bạn bè!')}", "SUCCESS")
                    self.refresh_initial_state()
                else:
                    self.log(f"⚠️ {data.get('message', 'Không thể kết bạn')}", "WARN")
            except Exception as e:
                self.log(f"❌ Lỗi kết bạn: {e}", "ERROR")

        threading.Thread(target=_task, daemon=True).start()

    def send_chat_message_action(self):
        if not self.is_logged_in:
            self.messagebox.showwarning(
                "Yêu cầu đăng nhập",
                "Bạn bắt buộc phải đăng nhập tài khoản Player trước khi bình luận trong sảnh Live!",
            )
            return
        msg = self.chat_msg_var.get().strip()
        if not msg:
            return
        sender = self.player_name_var.get().strip()
        target_streamer = self.get_active_lobby_streamer()
        self.chat_msg_var.set("")

        def _task():
            try:
                res = requests.post(
                    self.get_api_endpoint(),
                    json={
                        "action": "sendChatMessage",
                        "streamerName": target_streamer,
                        "senderName": sender,
                        "password": self._get_effective_player_password(),
                        "isAdmin": self.is_admin,
                        "adminPassword": self.admin_password,
                        "text": msg,
                        "message": msg,
                    },
                    timeout=10,
                )
                data = res.json()
                if data.get("status") == "success":
                    self.refresh_initial_state()
                else:
                    self.log(f"⚠️ {data.get('message', 'Không gửi được bình luận')}", "WARN")
            except Exception as e:
                self.log(f"❌ Lỗi gửi bình luận: {e}", "ERROR")

        threading.Thread(target=_task, daemon=True).start()

    def send_star_gift_action(self, stars: int = 1):
        if not self.is_logged_in:
            self.messagebox.showwarning(
                "Yêu cầu đăng nhập",
                "Bạn bắt buộc phải đăng nhập tài khoản Player trước khi tặng Sao trong sảnh Live!",
            )
            return
        sender = self.player_name_var.get().strip()
        target_streamer = self.get_active_lobby_streamer()

        def _task():
            try:
                res = requests.post(
                    self.get_api_endpoint(),
                    json={
                        "action": "sendStarGift",
                        "streamerName": target_streamer,
                        "senderName": sender,
                        "password": self._get_effective_player_password(),
                        "isAdmin": self.is_admin,
                        "adminPassword": self.admin_password,
                        "starCount": stars,
                        "stars": stars,
                        "message": f"Tặng {stars} sao cổ vũ {target_streamer}!",
                    },
                    timeout=10,
                )
                data = res.json()
                if data.get("status") == "success":
                    self.log(f"✅ 🌟 Đã tặng +{stars} Sao vào sảnh Live của {target_streamer}!", "SUCCESS")
                    self.refresh_initial_state()
                else:
                    self.log(f"⚠️ {data.get('message', 'Không thể tặng sao')}", "WARN")
            except Exception as e:
                self.log(f"❌ Lỗi tặng sao: {e}", "ERROR")

        threading.Thread(target=_task, daemon=True).start()

    def _compute_c_mode_summary(self, games: list, target_wins: int = 3) -> str:
        sets = []
        cur_r, cur_b, c_r, c_b, idx = 0, 0, 0, 0, 1
        for g in games:
            w = g.get("winner")
            if w == "RED":
                cur_r += 1
            elif w == "BLUE":
                cur_b += 1
            if cur_r >= target_wins or cur_b >= target_wins:
                if cur_r >= target_wins:
                    c_r += 1
                else:
                    c_b += 1
                sets.append(f"Séc {idx}: {cur_r}-{cur_b}")
                idx += 1
                cur_r, cur_b = 0, 0
        if cur_r > 0 or cur_b > 0 or not sets:
            sets.append(f"Séc {idx}: {cur_r}-{cur_b}")
        return f"🏆 Tỉ số C: {c_r} - {c_b}  |  " + " • ".join(sets)

    def _update_battle_arena_ui(self, match: dict):
        if not match:
            return
        games = match.get("games", [])
        red_w = sum(1 for g in games if g.get("winner") == "RED")
        blue_w = sum(1 for g in games if g.get("winner") == "BLUE")
        mode = match.get("mode", "4v4")
        ov_cfg = match.get("overlayConfig") or {}
        target_score = ov_cfg.get("targetScore") or self.target_score_var.get() or 100
        c_enabled = bool(ov_cfg.get("cModeEnabled", self.c_mode_var.get()))

        last_game = games[-1] if games else {}
        red_players = match.get("redTeam") or []
        blue_players = match.get("blueTeam") or []
        red_civs = last_game.get("redCivs") or []
        blue_civs = last_game.get("blueCivs") or []
        red_colors = last_game.get("redColors") or match.get("redColors") or []
        blue_colors = last_game.get("blueColors") or match.get("blueColors") or []

        red_lines = []
        for i, p in enumerate(red_players):
            civ = red_civs[i] if i < len(red_civs) else "---"
            col_idx = red_colors[i] if i < len(red_colors) else i
            col_name = COLOR_NAMES_VI.get(col_idx, f"Màu {col_idx + 1}")
            red_lines.append(f"• {p:<12}  [{civ:<8}]  ({col_name})")

        blue_lines = []
        for i, p in enumerate(blue_players):
            civ = blue_civs[i] if i < len(blue_civs) else "---"
            col_idx = blue_colors[i] if i < len(blue_colors) else i + 4
            col_name = COLOR_NAMES_VI.get(col_idx, f"Màu {col_idx + 1}")
            blue_lines.append(f"• {p:<12}  [{civ:<8}]  ({col_name})")

        red_text = "\n".join(red_lines) if red_lines else "Chưa có dữ liệu Team Đỏ"
        blue_text = "\n".join(blue_lines) if blue_lines else "Chưa có dữ liệu Team Xanh"

        if c_enabled:
            summary_txt = self._compute_c_mode_summary(games, int(ov_cfg.get("cTargetWins") or 3))
            hdr_txt = f"Kèo {mode} • Đánh theo C (Chạm 3)"
        else:
            summary_txt = f"Trận #{len(games)} đang diễn ra • Tổng {len(games)} trận"
            hdr_txt = f"Kèo {mode} • Chạm {target_score}"

        def _render():
            self.match_mode_lbl.config(text=hdr_txt)
            self.score_lbl.config(text=f"{red_w}  -  {blue_w}")
            self.c_mode_summary_lbl.config(text=summary_txt)
            self.red_roster_lbl.config(text=red_text)
            self.blue_roster_lbl.config(text=blue_text)
            self.red_count_lbl.config(text=f"{len(red_players)} người chơi")
            self.blue_count_lbl.config(text=f"{len(blue_players)} người chơi")

        self.root.after(0, _render)

    def copy_obs_link(self):
        base = self.get_base_server_url()
        name = self.player_name_var.get().strip() or "XO"
        obs_url = f"{base}/overlay.html?streamer={name}"
        self.root.clipboard_clear()
        self.root.clipboard_append(obs_url)
        self.log(f"✅ 📋 Đã copy Link OBS Bảng Quân: {obs_url}", "SUCCESS")

    def copy_obs_chat_link(self):
        base = self.get_base_server_url()
        name = self.player_name_var.get().strip() or "XO"
        chat_url = f"{base}/chat-overlay.html?streamer={name}"
        self.root.clipboard_clear()
        self.root.clipboard_append(chat_url)
        self.log(f"✅ 💬 Đã copy Link OBS Khung Chat (380x520): {chat_url}", "SUCCESS")

    def open_web_dashboard(self):
        import webbrowser
        webbrowser.open(self.get_base_server_url())

    def _send_parsed_diplomacy_to_server(self, parsed: dict, allow_same_civ: bool = False):
        red_str = ", ".join(
            f"{p} [{c} - {COLOR_NAMES_VI.get(col, col)}]"
            for p, c, col in zip(parsed["redPlayers"], parsed["redCivs"], parsed["redColors"])
        )
        blue_str = ", ".join(
            f"{p} [{c} - {COLOR_NAMES_VI.get(col, col)}]"
            for p, c, col in zip(parsed["bluePlayers"], parsed["blueCivs"], parsed["blueColors"])
        )
        self.log("🎯 Đã quét bảng quân Diplomacy:", "TEAM")
        self.log(f"   🔴 Team Đỏ  : {red_str}", "TEAM")
        self.log(f"   🔵 Team Xanh: {blue_str}", "TEAM")

        preview_match = {
            "mode": f"{len(parsed['redPlayers'])}v{len(parsed['bluePlayers'])}",
            "redTeam": parsed["redPlayers"],
            "blueTeam": parsed["bluePlayers"],
            "redColors": parsed["redColors"],
            "blueColors": parsed["blueColors"],
            "games": (self.current_match.get("games", []) if self.current_match else [])
            + [
                {
                    "redCivs": parsed["redCivs"],
                    "blueCivs": parsed["blueCivs"],
                    "redColors": parsed["redColors"],
                    "blueColors": parsed["blueColors"],
                    "winner": "PENDING",
                }
            ],
        }
        self._update_battle_arena_ui(preview_match)

        api_url = self.get_api_endpoint()
        payload = {
            "action": "autoAddGame",
            "streamerName": self.player_name_var.get().strip(),
            "password": self._get_effective_player_password(),
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
            if data.get("status") == "error":
                self.log(f"⛔ Từ chối: {data.get('message', '')}", "ERROR")
                self.root.after(0, lambda: self.status_lbl.config(text=f"🔴 {data.get('message', '')}", fg="#f87171"))
                return
            self.log(f"✅ ☁️ Đồng bộ Server: {data.get('message', '')}", "SUCCESS")
            if data.get("match"):
                self.current_match = data["match"]
                self._update_battle_arena_ui(data["match"])
        except Exception as e:
            self.log(f"❌ Lỗi gửi dữ liệu lên Server: {e}", "ERROR")

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
                    self.log("⚠️ Không tìm thấy bảng DIPLOMACY trên màn hình hiện tại!", "WARN")
                    return
                self._send_parsed_diplomacy_to_server(res, allow_same_civ=False)
            except Exception as e:
                self.log(f"❌ Lỗi quét màn hình: {e}", "ERROR")

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
                raw_bytes = np.fromfile(file_path, dtype=np.uint8)
                img_bgr = cv2.imdecode(raw_bytes, cv2.IMREAD_COLOR)
                res = self.scanner.parse_diplomacy_from_image(
                    img_bgr,
                    streamer_name=self.player_name_var.get().strip(),
                    known_players=self.known_players,
                    force=True,
                )
                if not res or res.get("status") != "ok":
                    self.log(f"⚠️ Ảnh '{os.path.basename(file_path)}' không chứa bảng DIPLOMACY hợp lệ!", "WARN")
                    return
                self._send_parsed_diplomacy_to_server(res, allow_same_civ=True)
            except Exception as e:
                self.log(f"❌ Lỗi đọc ảnh: {e}", "ERROR")

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
                        "password": self._get_effective_player_password(),
                        "winner": winner,
                    },
                    timeout=10,
                )
                data = res.json()
                if data.get("status") == "success":
                    team_vi = "🔴 Team Đỏ thắng (+1)" if winner == "RED" else "🔵 Team Xanh thắng (+1)"
                    self.log(f"✅ Đã cập nhật kết quả trận đấu: {team_vi}", "SUCCESS")
                    if data.get("match"):
                        self.current_match = data["match"]
                        self._update_battle_arena_ui(data["match"])
                else:
                    self.log(f"⚠️ {data.get('message', 'Không thể cập nhật tỉ số')}", "WARN")
            except Exception as e:
                self.log(f"❌ Lỗi cập nhật tỉ số: {e}", "ERROR")

        threading.Thread(target=_task, daemon=True).start()

    def finish_current_match(self):
        if not self.messagebox.askyesno("Xác nhận kết thúc", "Bạn muốn KẾT THÚC kèo đấu đang LIVE hiện tại?"):
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
                        "password": self._get_effective_player_password(),
                    },
                    timeout=10,
                )
                data = res.json()
                if data.get("status") == "success":
                    self.log("✅ 🏁 Đã kết thúc kèo đấu thành công!", "SUCCESS")
                    self.current_match = None
                    self.root.after(
                        0,
                        lambda: (
                            self.score_lbl.config(text="0  -  0"),
                            self.c_mode_summary_lbl.config(text="Kèo đấu đã kết thúc"),
                        ),
                    )
                else:
                    self.log(f"⚠️ {data.get('message', 'Không thể kết thúc kèo')}", "WARN")
            except Exception as e:
                self.log(f"❌ Lỗi kết thúc kèo: {e}", "ERROR")

        threading.Thread(target=_task, daemon=True).start()

    def _auto_finish_match_sync(self):
        """Tự động gửi lệnh kết thúc kèo đấu đang LIVE khi người chơi tắt Tool."""
        if self._did_finish_on_exit:
            return
        self._did_finish_on_exit = True
        try:
            streamer = self.settings.get("player_name", "").strip()
            pw = self.settings.get("player_password", "").strip()
            if not streamer or not pw:
                return
            api_url = self.get_api_endpoint()
            requests.post(
                api_url,
                json={
                    "action": "finishMatch",
                    "streamerName": streamer,
                    "updatedBy": streamer,
                    "password": pw,
                },
                timeout=3.5,
            )
        except Exception:
            pass

    def on_closing(self):
        """Sự kiện đóng cửa sổ Tool: lưu cấu hình, tự động kết thúc kèo LIVE và thoát."""
        self.running = False
        try:
            self.save_current_config()
        except Exception:
            pass
        self._auto_finish_match_sync()
        try:
            self.root.destroy()
        except Exception:
            sys.exit(0)

    def _background_worker(self):
        last_heartbeat = time.time()
        last_social_sync = time.time()
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

                # Định kỳ đồng bộ trạng thái Bạn bè Live, Khung Chat & Sao mỗi 8 giây
                if self.is_logged_in and (time.time() - last_social_sync > 8.0):
                    last_social_sync = time.time()
                    self.refresh_initial_state()

                if self.is_logged_in and (time.time() - last_heartbeat > 50.0):
                    last_heartbeat = time.time()
                    try:
                        requests.post(
                            self.get_api_endpoint(),
                            json={
                                "action": "heartbeat",
                                "streamerName": self.player_name_var.get().strip(),
                                "password": self._get_effective_player_password(),
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
