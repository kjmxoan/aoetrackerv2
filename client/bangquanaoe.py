import os
import sys
import time
import json
import base64
import hashlib
import difflib
import itertools
import threading
import subprocess
import tempfile
import random
from datetime import datetime, timezone
from pathlib import Path

import cv2
import numpy as np
import requests
from PIL import Image, ImageGrab, ImageDraw, ImageFont

import re

# Kích hoạt Per-Monitor DPI Awareness trên Windows ngay khi khởi động để ImageGrab.grab()
# luôn chụp đủ 100% độ phân giải thật (1366x768, 1600x900, 1920x1080, 2K, 4K) mà không bị cắt góc bởi Windows Scaling (125%, 150%)
if os.name == "nt":
    try:
        import ctypes
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(2)
        except Exception:
            ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass

APP_VERSION_NUMBER = "5.5.0"
APP_VERSION = f"v{APP_VERSION_NUMBER} HUD Sci-Fi Glass"
APP_TITLE = "TOOL BẢNG QUÂN AOE BY XO"
DEFAULT_SERVER_URL = "https://aoe-tracker.onrender.com/"


def parse_version_tuple(v_str: str) -> tuple:
    """Chuyển chuỗi phiên bản (VD: 'v5.1', '5.3.1') thành tuple số nguyên (5, 1) để so sánh chính xác."""
    nums = re.findall(r"\d+", str(v_str or "0"))
    if not nums:
        return (0,)
    return tuple(int(x) for x in nums[:4])


def is_windows_process_admin() -> bool:
    """Kiểm tra xem tiến trình hiện tại có đang chạy với quyền Administrator (High Integrity) để bắt phím xuyên Game AOE hay không."""
    if os.name != "nt":
        return True
    try:
        import ctypes
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def ensure_windows_admin_for_ingame_hotkeys():
    """
    Tự động nâng quyền Administrator (UAC 'runas') nếu người dùng mở Tool ở quyền thường.
    Lý do: Game Đế Chế (EMPIRESX.EXE) trên Windows 10/11 luôn chạy ở mức High Integrity (Administrator)
    do DirectPlay shim. Nếu Tool chạy ở Medium Integrity, Windows UIPI sẽ chặn toàn bộ phím F2, F5, F6, F8 khi đang trong màn hình Game.
    """
    if os.name != "nt":
        return
    if "--no-elevate" in sys.argv or "--test" in sys.argv:
        return
    if is_windows_process_admin():
        return
    try:
        import ctypes
        exe_path = sys.executable
        if getattr(sys, "frozen", False):
            args_list = [a for a in sys.argv[1:] if a != "--no-elevate"] + ["--no-elevate"]
        else:
            script_path = os.path.abspath(sys.argv[0])
            args_list = [script_path] + [a for a in sys.argv[1:] if a != "--no-elevate"] + ["--no-elevate"]
        params = subprocess.list2cmdline(args_list)
        ret = ctypes.windll.shell32.ShellExecuteW(None, "runas", exe_path, params, os.getcwd(), 1)
        if int(ret) > 32:
            sys.exit(0)
    except Exception:
        pass

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
    "Assyrian": ["Ashurbanipal", "Sargon", "Sennacherib", "Shalmaneser", "Tiglath-Pileser", "Tukulti-Ninurta", "Adad-nirari", "Esarhaddon", "Nimrod", "Semiramis", "Ashurnasirpal", "Shamshi-Adad"],
    "Babylonian": ["Nabonidus", "Hammurabi", "Nebuchadnezzar", "Tiglath-Pileser", "Sumu-abum", "Samsu-iluna", "Burna-Buriash", "Nabopolassar", "Belshazzar", "Marduk", "Neriglissar", "Rim-Sin"],
    "Carthaginian": ["Hamilcar Barca", "Matho", "Hannibal", "Hasdrubal", "Hanno", "Mago", "Gisco", "Gisgo", "Bomilcar", "Spendius", "Adherbal", "Himilco", "Maharbal", "Xanthippus", "Dido"],
    "Choson": ["Hyon", "Dangun", "Gwanggaeto", "Jumong", "Kija", "Ugeo", "Wiman", "Ulji Mundok", "Koi", "Piru", "Kunchogo", "Sosurim", "Kwanggaeto", "Changsu"],
    "Egyptian": ["Amenophis", "Ramses", "Cleopatra", "Hatshepsut", "Khufu", "Nefertiti", "Ptolemy", "Seti", "Thutmose", "Tutankhamun", "Akhenaten", "Cheops", "Menes", "Necho", "Psamtik", "Sneferu", "Zoser"],
    "Greek": ["Leonidas", "Erythrus", "Pericles", "Alexander", "Hippocrates", "Themistocles", "Pyrrhus", "Lysander", "Alcibiades", "Agamemnon", "Achilles", "Odysseus", "Miltiades", "Cimon", "Epaminondas", "Pelopidas", "Xenophon"],
    "Hittite": ["Tudhalyas", "Suppiluliumas", "Hattusilis", "Labarnas", "Mursilis", "Muwatalli", "Telipinus", "Anittas", "Hantilis", "Zidantas", "Ammunas", "Arnuwandas"],
    "Macedonian": ["Alexander", "Antigonus", "Antipater", "Cassander", "Craterus", "Demetrius", "Lysimachus", "Philip", "Ptolemy", "Seleucus", "Parmenion", "Perdiccas", "Eumenes", "Polyperchon", "Pyrrhus"],
    "Minoan": ["Gortys", "Aeacus", "Erythrus", "Minos", "Asterion", "Deucalion", "Idomeneus", "Rhadamanthus", "Sarpedon", "Talos", "Phaestus", "Knossos", "Cydon", "Catres", "Tylus", "Lyctus", "Mallia", "Zakros"],
    "Palmyran": ["Zobdas", "Syphax", "Jugurtha", "Zenobia", "Odaenathus", "Vaballathus", "Hairan", "Longinus", "Maeonius", "Zabdas", "Antiochus", "Septimius", "Vorodes"],
    "Persian": ["Astyages", "Cyrus", "Mithridates", "Darius", "Xerxes", "Cambyses", "Artaxerxes", "Shapur", "Tigranes", "Ardashir", "Bardiya", "Chosroes", "Hystaspes", "Phraates", "Tissaphernes"],
    "Phoenician": ["Ahiram", "Hiram", "Abibaal", "Dido", "Philo", "Boodes", "Gisgo", "Hanno", "Mago", "Malchus", "Ethbaal", "Ittobaal", "Pygmalion", "Zakarbaal", "Azemilcus", "Baal", "Eshmunazar", "Luli", "Rib-Addi", "Strato", "Tabnit"],
    "Roman": ["Marcus Aurelius", "Caesar", "Augustus", "Pompey", "Scipio", "Sulla", "Trajan", "Crassus", "Marius", "Cicero", "Constantine", "Fabius", "Germanicus", "Hadrian", "Mark Antony", "Nero", "Tiberius", "Vespasian"],
    "Shang": ["Zhou Xin", "Tang", "Wu Ding", "Pan Geng", "Tai Jia", "Zu Yi", "Di Yi", "Tai Wu", "Bu Bing", "Wai Ren", "Zhong Ding", "Zu Geng", "Zu Jia", "Lin Xin", "Geng Ding"],
    "Sumerian": ["Enmerkar", "Gilgamesh", "Sargon", "Ur-Nammu", "Shulgi", "Eannatum", "Gudea", "Lugal-zage-si", "Aka", "Dungi", "Enmebaragesi", "Ibbi-Sin", "Lugalbanda", "Mesilim", "Urukagina", "Utu-hegal"],
    "Yamato": ["Keiko", "Kammu", "Jimmu", "Himiko", "Nintoku", "Ojin", "Suinin", "Sujin", "Shotoku", "Annei", "Itoku", "Kaika", "Kogen", "Kosho", "Koan", "Korei", "Richu", "Seinei", "Yuryaku"],
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

    # Đo khung dọc chuẩn cố định (từ đỉnh chữ hoa đến đáy nét móc chữ g/p/y) để giữ nguyên tỷ lệ baseline
    ref_img = Image.new("L", (140, 24), 0)
    ImageDraw.Draw(ref_img).text((0, 2), "Agpy", fill=255, font=font)
    ref_ys, _ = np.where(np.array(ref_img) > 80)
    if len(ref_ys) > 0:
        y0_fixed, y1_fixed = int(ref_ys.min()), int(ref_ys.max() + 1)
    else:
        y0_fixed, y1_fixed = 4, 15
    fh_fixed = max(1, y1_fixed - y0_fixed)

    for word in word_list:
        img = Image.new("L", (140, 24), 0)
        draw = ImageDraw.Draw(img)
        draw.text((0, 2), word, fill=255, font=font)
        arr = np.array(img)
        _, xs = np.where(arr > 80)
        if len(xs) == 0:
            continue
        patch = arr[y0_fixed:y1_fixed, xs.min():xs.max() + 1]
        new_w = max(1, int(round(patch.shape[1] * (12.0 / fh_fixed))))
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

    @classmethod
    def _search_box_on_image(cls, img_bgr: np.ndarray, orig_bgr: np.ndarray, scale_x: float, scale_y: float, hw_min_ratio: float = 0.13):
        h, w = img_bgr.shape[:2]
        orig_h, orig_w = orig_bgr.shape[:2]
        gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
        sobelx = np.abs(cv2.Sobel(gray, cv2.CV_32F, 1, 0, ksize=3))
        sobely = np.abs(cv2.Sobel(gray, cv2.CV_32F, 0, 1, ksize=3))

        cx_base, cy_base = w / 2.0, h / 2.0
        hw_min = max(70, int(w * hw_min_ratio))
        hw_max = int(w * 0.36)
        step = max(1, int(w / 900))

        candidates = []
        for hw in range(hw_min, hw_max, step):
            hh = int(round(hw * (301.0 / 468.0)))
            x1, x2 = int(round(cx_base - hw)), int(round(cx_base + hw))
            y1, y2 = int(round(cy_base - hh)), int(round(cy_base + hh))
            if y1 < 2 or y2 >= h - 2 or x1 < 2 or x2 >= w - 2:
                continue

            left_line = float(np.mean(sobelx[y1:y2, x1 - 1:x1 + 2]))
            right_line = float(np.mean(sobelx[y1:y2, x2 - 1:x2 + 2]))
            top_line = float(np.mean(sobely[y1 - 1:y1 + 2, x1:x2]))
            bot_line = float(np.mean(sobely[y2 - 1:y2 + 2, x1:x2]))
            if min(left_line, right_line) < 42.0 or min(top_line, bot_line) < 42.0:
                continue

            score = (
                min(left_line, right_line) * 2.0
                + min(top_line, bot_line) * 2.0
                + (left_line + right_line + top_line + bot_line) * 0.5
            )
            if score >= 310.0:
                candidates.append((score, hw, cx_base, cy_base))

        # Sắp xếp các ứng viên có viền khung mạnh nhất để tinh chỉnh và xác thực cấu trúc bảng Diplomacy
        candidates.sort(key=lambda item: item[0], reverse=True)
        checked_hws = []
        best_overall_score = candidates[0][0] if candidates else 0.0

        for cand_score, hw_cand, cx, cy in candidates:
            if any(abs(hw_cand - prev_hw) <= 4 for prev_hw in checked_hws):
                continue
            checked_hws.append(hw_cand)
            if len(checked_hws) > 6:
                break

            best_local_sc = -1.0
            best_local_box = None
            for hw in range(max(50, hw_cand - 3), hw_cand + 4):
                hh_base = int(round(hw * (301.0 / 468.0)))
                for dh in (-1, 0, 1):
                    hh = hh_base + dh
                    for dy in (-2, -1, 0, 1, 2):
                        for dx in (-1, 0, 1):
                            x1, x2 = int(round(cx + dx - hw)), int(round(cx + dx + hw))
                            y1, y2 = int(round(cy + dy - hh)), int(round(cy + dy + hh))
                            if y1 < 2 or y2 >= h - 2 or x1 < 2 or x2 >= w - 2:
                                continue
                            left_line = float(np.mean(sobelx[y1:y2, x1 - 1:x1 + 2]))
                            right_line = float(np.mean(sobelx[y1:y2, x2 - 1:x2 + 2]))
                            top_line = float(np.mean(sobely[y1 - 1:y1 + 2, x1:x2]))
                            bot_line = float(np.mean(sobely[y2 - 1:y2 + 2, x1:x2]))
                            sc = (
                                min(left_line, right_line) * 2.0
                                + min(top_line, bot_line) * 2.0
                                + (left_line + right_line + top_line + bot_line) * 0.5
                            )
                            if sc > best_local_sc:
                                best_local_sc = sc
                                best_local_box = (x1, y1, x2, y2)

            if best_local_box is not None:
                bx1, by1, bx2, by2 = best_local_box
                ox1 = max(0, min(orig_w - 1, int(round(bx1 * scale_x))))
                oy1 = max(0, min(orig_h - 1, int(round(by1 * scale_y))))
                ox2 = max(ox1 + 10, min(orig_w, int(round(bx2 * scale_x))))
                oy2 = max(oy1 + 10, min(orig_h, int(round(by2 * scale_y))))
                crop = orig_bgr[oy1:oy2, ox1:ox2]
                if crop.size > 0:
                    norm = cv2.resize(crop, (624, 400), interpolation=cv2.INTER_CUBIC)
                    if cls.verify_is_diplomacy_dialog(norm):
                        return (ox1, oy1, ox2, oy2), best_local_sc

        # Dự phòng cho chế độ Cửa sổ (Windowed Mode) hoặc mở ảnh chụp màn hình bị lệch tâm:
        # Dùng tích phân 2D (Cumulative Sum) trên ảnh chuẩn hóa (w <= 1080) để dò tâm (cx, cy) bị lệch
        if w <= 1080:
            v_strip = cv2.blur(sobelx, (3, 1))
            h_strip = cv2.blur(sobely, (1, 3))
            cs_v = np.pad(np.cumsum(v_strip, axis=0), ((1, 0), (0, 0)))
            cs_h = np.pad(np.cumsum(h_strip, axis=1), ((0, 0), (1, 0)))

            cxs = np.arange(int(w * 0.25), int(w * 0.75), 3)
            cys = np.arange(int(h * 0.25), int(h * 0.75), 3)
            CX, CY = np.meshgrid(cxs, cys)
            off_peaks = []
            for hw in range(max(70, int(w * 0.10)), int(w * 0.49), 2):
                hh = int(round(hw * (301.0 / 468.0)))
                x1, x2 = CX - hw, CX + hw
                y1, y2 = CY - hh, CY + hh
                valid = (x1 >= 2) & (x2 < w - 2) & (y1 >= 2) & (y2 < h - 2)
                if not np.any(valid):
                    continue
                x1v, x2v, y1v, y2v = x1[valid], x2[valid], y1[valid], y2[valid]
                l_edge = (cs_v[y2v, x1v] - cs_v[y1v, x1v]) / float(2 * hh)
                r_edge = (cs_v[y2v, x2v] - cs_v[y1v, x2v]) / float(2 * hh)
                t_edge = (cs_h[y1v, x2v] - cs_h[y1v, x1v]) / float(2 * hw)
                b_edge = (cs_h[y2v, x2v] - cs_h[y2v, x1v]) / float(2 * hw)
                sc_arr = np.minimum(l_edge, r_edge) * 2.0 + np.minimum(t_edge, b_edge) * 2.0 + (l_edge + r_edge + t_edge + b_edge) * 0.5
                idx = int(np.argmax(sc_arr))
                if sc_arr[idx] >= 320.0:
                    off_peaks.append((float(sc_arr[idx]), int(CX[valid][idx]), int(CY[valid][idx]), hw))

            off_peaks.sort(key=lambda item: item[0], reverse=True)
            refined_candidates = []
            for sc_p, cx_p, cy_p, hw_p in off_peaks[:12]:
                best_ref_sc = -1.0
                best_ref_box = None
                for hw_r in (hw_p - 2, hw_p - 1, hw_p, hw_p + 1, hw_p + 2):
                    if hw_r < 50:
                        continue
                    hh_base_r = int(round(hw_r * (301.0 / 468.0)))
                    for dh_r in (-3, -2, -1, 0, 1, 2, 3):
                        hh_r = hh_base_r + dh_r
                        for dy_r in (-1, 0, 1):
                            for dx_r in (-1, 0, 1):
                                x1, x2 = cx_p + dx_r - hw_r, cx_p + dx_r + hw_r
                                y1, y2 = cy_p + dy_r - hh_r, cy_p + dy_r + hh_r
                                if y1 < 2 or y2 >= h - 2 or x1 < 2 or x2 >= w - 2:
                                    continue
                                l_r = float(np.mean(sobelx[y1:y2, x1 - 1:x1 + 2]))
                                r_r = float(np.mean(sobelx[y1:y2, x2 - 1:x2 + 2]))
                                t_r = float(np.mean(sobely[y1 - 1:y1 + 2, x1:x2]))
                                b_r = float(np.mean(sobely[y2 - 1:y2 + 2, x1:x2]))
                                sc_r = min(l_r, r_r) * 2.0 + min(t_r, b_r) * 2.0 + (l_r + r_r + t_r + b_r) * 0.5
                                if sc_r > best_ref_sc:
                                    best_ref_sc = sc_r
                                    best_ref_box = (x1, y1, x2, y2)
                if best_ref_box is not None:
                    refined_candidates.append((best_ref_sc, best_ref_box))

            refined_candidates.sort(key=lambda item: item[0], reverse=True)
            for ref_sc, (bx1, by1, bx2, by2) in refined_candidates:
                ox1 = max(0, min(orig_w - 1, int(round(bx1 * scale_x))))
                oy1 = max(0, min(orig_h - 1, int(round(by1 * scale_y))))
                ox2 = max(ox1 + 10, min(orig_w, int(round(bx2 * scale_x))))
                oy2 = max(oy1 + 10, min(orig_h, int(round(by2 * scale_y))))
                crop = orig_bgr[oy1:oy2, ox1:ox2]
                if crop.size > 0:
                    norm = cv2.resize(crop, (624, 400), interpolation=cv2.INTER_CUBIC)
                    if cls.verify_is_diplomacy_dialog(norm):
                        return (ox1, oy1, ox2, oy2), ref_sc

        return None, best_overall_score

    @classmethod
    def find_diplomacy_box(cls, img_bgr: np.ndarray):
        """
        Dò tìm khung cửa sổ DIPLOMACY ở chính giữa màn hình với tỉ lệ chuẩn 468:301 (~1.555).
        Hoạt động trên mọi độ phân giải (800x600, 1024x768, 1366x768, 1600x900, 1920x1080, 2K 2560x1440, 4K)
        và mọi giao diện (Classic Tan / Dark Stone), kể cả khi màn hình kéo giãn (stretched) hoặc giữ nguyên kích thước 468x301.
        """
        if img_bgr is None or img_bgr.size == 0:
            return None, 0.0

        h, w = img_bgr.shape[:2]
        if w < 450 or h < 300:
            return None, 0.0

        best_score = 0.0

        # Lượt 1: Chuẩn hóa chiều ngang về 1024px để làm sắc nét các đường viền khi game chạy Fullscreen kéo giãn trên màn 1080p / 2K / 4K
        if w > 1080:
            det_w = 1024
            det_h = max(300, int(round(h * (1024.0 / w))))
            det_img = cv2.resize(img_bgr, (det_w, det_h), interpolation=cv2.INTER_AREA)
            box, sc = cls._search_box_on_image(det_img, img_bgr, w / float(det_w), h / float(det_h), hw_min_ratio=0.135)
            best_score = max(best_score, sc)
            if box is not None:
                return box, sc

        # Lượt 2: Quét trực tiếp trên độ phân giải gốc (bắt chuẩn hộp thoại 468x301 / 624x400 unscaled trên màn 1920x1080 / 2560x1440)
        box, sc = cls._search_box_on_image(img_bgr, img_bgr, 1.0, 1.0, hw_min_ratio=0.075)
        best_score = max(best_score, sc)
        if box is not None:
            return box, sc

        # Lượt 3: Hỗ trợ khi người chơi chỉnh Screen Size trong Game Settings (1600x900, 1366x768, 1280x720, 1024x768)
        # nhỏ hơn độ phân giải màn hình chính (ví dụ màn 1920x1080 hoặc 2K khiến khung game nằm ở góc trên bên trái 0,0)
        for vw, vh in [(1600, 900), (1366, 768), (1280, 720), (1024, 768)]:
            if w > vw + 40 and h >= vh and vw >= 600 and vh >= 400:
                sub_bgr = img_bgr[:vh, :vw]
                det_w = min(1024, vw)
                det_h = max(300, int(round(vh * (float(det_w) / vw))))
                det_sub = cv2.resize(sub_bgr, (det_w, det_h), interpolation=cv2.INTER_AREA) if det_w < vw else sub_bgr
                box, sc = cls._search_box_on_image(
                    det_sub, sub_bgr, vw / float(det_w), vh / float(det_h), hw_min_ratio=0.135
                )
                best_score = max(best_score, sc)
                if box is not None:
                    return box, sc

        return None, best_score

    last_verify_reason = ""

    @staticmethod
    def verify_is_diplomacy_dialog(norm_624x400: np.ndarray) -> bool:
        # 0. Kiểm tra độ sáng trung vị của nền hộp thoại (loại bỏ ngay các cửa sổ nền tối #11151b / #181e28 của chính Tool hoặc nền trắng >220)
        #    Bảng Diplomacy thật của AOE có nền Gỗ Nâu (median V ~ 115..150) hoặc Đá Cẩm Thạch Xám (median V ~ 155..190)
        bg_sample = norm_624x400[80:340, 240:580]
        med_bg_v = float(np.median(np.max(bg_sample, axis=2)))
        if med_bg_v < 58.0 or med_bg_v > 220.0:
            DiplomacyScanner.last_verify_reason = f"Nền hộp thoại không phải gỗ/đá AOE (med_bg_v={med_bg_v:.1f})"
            return False

        # 1. Check tiêu đề DIPLOMACY chữ trắng nằm ở chính giữa thanh tiêu đề trên cùng (y: 6..32, x: 230..400)
        title_crop = norm_624x400[6:32, 230:400]
        min_t = np.min(title_crop, axis=2).astype(np.float32)
        max_t = np.max(title_crop, axis=2).astype(np.float32)
        wh_t = min_t - 0.55 * (max_t - min_t)
        bg_t = float(np.percentile(wh_t, 55))
        white_title_px = int(np.sum((wh_t > max(bg_t + 16.0, 150.0)) & ((max_t - min_t) < 55)))
        if white_title_px < 80 or white_title_px > 2600:
            DiplomacyScanner.last_verify_reason = f"Tiêu đề DIPLOMACY không khớp (white_title_px={white_title_px})"
            return False

        # Hai bên trái/phải của chữ DIPLOMACY trên thanh tiêu đề phải là nền đá cẩm thạch xám (<=215) hoặc gỗ nâu,
        # không phải trang web nền trắng tinh (>225)
        left_slab = norm_624x400[8:30, 40:190]
        right_slab = norm_624x400[8:30, 435:585]
        w_left = int(np.sum((np.min(left_slab, axis=2) > 225) & ((np.max(left_slab, axis=2).astype(np.int16) - np.min(left_slab, axis=2).astype(np.int16)) < 30)))
        w_right = int(np.sum((np.min(right_slab, axis=2) > 225) & ((np.max(right_slab, axis=2).astype(np.int16) - np.min(right_slab, axis=2).astype(np.int16)) < 30)))
        if w_left > 180 or w_right > 180:
            DiplomacyScanner.last_verify_reason = f"Thanh tiêu đề quá trắng như trang web (w_left={w_left}, w_right={w_right})"
            return False

        # 2. Check bộ 3 nút đặc trưng riêng của bảng DIPLOMACY ở đáy hộp thoại (y: 368..396):
        #    - Nút trái (x: 75..145): Chữ 'OK' màu vàng (nhiều hơn hẳn vùng x: 170..235 của bảng Game Settings)
        #    - Nút giữa (x: 230..395): Chữ 'CLEAR TRIBUTES' màu trắng
        #    - Nút phải (x: 470..560): Chữ 'CANCEL' màu trắng
        ok_crop = norm_624x400[368:396, 75:145]
        b_ok, g_ok, r_ok = cv2.split(ok_crop)
        yellow_ok_px = int(np.sum((r_ok > 140) & (g_ok > 130) & (b_ok < 115) & ((r_ok.astype(np.int16) - b_ok.astype(np.int16)) > 55)))
        if yellow_ok_px < 12:
            DiplomacyScanner.last_verify_reason = f"Không thấy chữ OK màu vàng ở góc dưới trái (yellow_ok_px={yellow_ok_px})"
            return False

        clear_crop = norm_624x400[368:396, 230:395]
        min_cl = np.min(clear_crop, axis=2).astype(np.float32)
        max_cl = np.max(clear_crop, axis=2).astype(np.float32)
        white_clear_px = int(np.sum((min_cl > 150) & ((max_cl - min_cl) < 55)))
        if white_clear_px < 140:
            DiplomacyScanner.last_verify_reason = f"Không thấy nút CLEAR TRIBUTES ở đáy giữa (white_clear_px={white_clear_px})"
            return False

        cancel_crop = norm_624x400[368:396, 470:560]
        min_ca = np.min(cancel_crop, axis=2).astype(np.float32)
        max_ca = np.max(cancel_crop, axis=2).astype(np.float32)
        white_cancel_px = int(np.sum((min_ca > 150) & ((max_ca - min_ca) < 55)))
        if white_cancel_px < 60:
            DiplomacyScanner.last_verify_reason = f"Không thấy nút CANCEL ở đáy phải (white_cancel_px={white_cancel_px})"
            return False

        # 3. Check hàng tiêu đề cột 'Name' / 'Civilization' (y: 52..74, x: 10..240) và 'Ally' / 'Neutral' / 'Enemy' (x: 235..430)
        hdr_crop = norm_624x400[52:74, 10:240]
        min_h = np.min(hdr_crop, axis=2).astype(np.float32)
        max_h = np.max(hdr_crop, axis=2).astype(np.float32)
        white_hdr_px = int(np.sum((min_h > 150) & ((max_h - min_h) < 55)))
        if white_hdr_px < 35:
            DiplomacyScanner.last_verify_reason = f"Không thấy tiêu đề cột Name/Civilization (white_hdr_px={white_hdr_px})"
            return False

        stance_hdr_crop = norm_624x400[52:74, 235:430]
        min_sh = np.min(stance_hdr_crop, axis=2).astype(np.float32)
        max_sh = np.max(stance_hdr_crop, axis=2).astype(np.float32)
        white_stance_hdr_px = int(np.sum((min_sh > 150) & ((max_sh - min_sh) < 55)))
        if white_stance_hdr_px < 30:
            DiplomacyScanner.last_verify_reason = f"Không thấy tiêu đề cột Ally/Neutral/Enemy (white_stance_hdr_px={white_stance_hdr_px})"
            return False

        DiplomacyScanner.last_verify_reason = "OK"
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
        overall_best_str_sim = 0.0
        overall_best_tmpl_corr = 0.0

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

            overall_best_str_sim = max(overall_best_str_sim, best_str_sim)
            scores[full] += best_str_sim * 1.6 + prefix_bonus

        if CIV_TEMPLATES:
            yc = int(round(95.0 + row_idx * 29.8))
            crop = norm_624x400[yc - 7:yc + 4, 139:235]
            min_rgb = np.min(crop, axis=2).astype(np.float32)
            max_rgb = np.max(crop, axis=2).astype(np.float32)
            sh_rgb = np.roll(np.roll(min_rgb, -1, axis=0), -1, axis=1)
            wh = min_rgb - 0.55 * (max_rgb - min_rgb) + 0.35 * np.maximum(0.0, min_rgb - sh_rgb)
            thr = max(float(np.percentile(wh, 65)) + 16.0, 125.0)
            val = np.clip((wh - thr) / 50.0, 0.0, 1.0)
            mask = val > 0.25
            col_counts = np.sum(mask, axis=0)
            valid_xs = np.where(col_counts >= 1)[0]
            if len(valid_xs) >= 8:
                x_min = int(valid_xs[0])
                x_max = x_min
                empty_run = 0
                for x_col in range(x_min, len(col_counts)):
                    if col_counts[x_col] >= 1:
                        x_max = x_col
                        empty_run = 0
                    else:
                        empty_run += 1
                        if empty_run >= 6 and (x_max - x_min) >= 14:
                            break
                patch = val[:, x_min:x_max + 1]
                new_w = max(1, int(round(patch.shape[1] * 1.0)))
                resized = cv2.resize(patch, (new_w, 12), interpolation=cv2.INTER_LINEAR)
                feat = np.zeros((12, 90), dtype=np.float32)
                w_clip = min(90, new_w)
                feat[:, :w_clip] = resized[:, :w_clip]

                for full, _, _ in CIV_LIST:
                    if full not in CIV_TEMPLATES:
                        continue
                    tmpl, tw = CIV_TEMPLATES[full]
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
                    t_patch = tmpl[:, :tw]
                    p_res = cv2.resize(patch, (tw, 12), interpolation=cv2.INTER_LINEAR)
                    num_n = float(np.sum((p_res - p_res.mean()) * (t_patch - t_patch.mean())))
                    den_n = float(np.sqrt(np.sum((p_res - p_res.mean()) ** 2) * np.sum((t_patch - t_patch.mean()) ** 2))) + 1e-6
                    mc_norm = num_n / den_n
                    comb_corr = 0.55 * max(0.0, max_corr) + 0.45 * max(0.0, mc_norm)
                    overall_best_tmpl_corr = max(overall_best_tmpl_corr, max_corr, mc_norm)
                    scores[full] += comb_corr * 0.85

        # Bắt buộc phải có độ khớp chữ OCR hoặc mẫu 2D đủ tin cậy (không đoán mò quân chỉ dựa vào độ rộng pixel)
        if overall_best_str_sim < 0.45 and overall_best_tmpl_corr < 0.34:
            return None, None

        best_full = max(scores, key=lambda k: scores[k])
        short_map = {full: short for full, short, _ in CIV_LIST}
        return best_full, short_map[best_full]

    @staticmethod
    def post_clean_aoe_player_name(raw_s: str) -> str:
        if not raw_s:
            return ""
        char_map = {
            "Ä": "A", "Á": "A", "À": "A", "Â": "A", "Ã": "A", "Å": "A",
            "ä": "a", "á": "a", "à": "a", "â": "a", "ã": "a", "å": "a",
            "Ë": "E", "É": "E", "È": "E", "Ê": "E",
            "ë": "e", "é": "e", "è": "e", "ê": "e",
            "Ï": "I", "Í": "I", "Ì": "I", "Î": "I",
            "ï": "i", "í": "i", "ì": "i", "î": "i",
            "Ö": "O", "Ó": "O", "Ò": "O", "Ô": "O", "Õ": "O", "Ø": "O",
            "ö": "o", "ó": "o", "ò": "o", "ô": "o", "õ": "o", "ø": "o",
            "Ü": "U", "Ú": "U", "Ù": "U", "Û": "U",
            "ü": "u", "ú": "u", "ù": "u", "û": "u",
            "ß": "s",
        }
        s = "".join(char_map.get(ch, ch) for ch in raw_s)
        s = re.sub(r"\[(?=[Hh][Aa][Nn])", "T", s)
        s = "".join(ch for ch in s if ch.isascii() and (ch.isalnum() or ch in " _-"))
        s = re.sub(r"\s+", " ", s).strip(" _-")
        # Loại bỏ hậu tố tên Quân nếu từng bị dính từ đuôi dải cờ sang cột Civilization
        s = re.sub(
            r"[\s_\-]+(?:[Il1tZz\.\-]*\s*)?(?:Persian|Egyptian|Eqvniian|Macedonian|lacedoni\w*|Assyrian|Hittite|Minoan|Phoenician|Palmyran|Babylonian|Choson|Carthaginian|Shang|Yamato|Sumerian|Greek|Roman)\b.*$",
            "",
            s,
            flags=re.IGNORECASE,
        ).strip(" _-")
        # Khắc phục các cặp chữ đặc trưng dễ bị Windows OCR đọc nhầm trên font pixel AOE1
        s = re.sub(r"\bM[FF]M\b", "MEM", s)
        s = re.sub(r"\bME-m(?:t)?\b", "MEM", s, flags=re.IGNORECASE)
        s = re.sub(r"\bUEU\b", "MEM", s)
        s = re.sub(r"^8G([_ ])", r"BG\1", s)
        s = re.sub(r"^BG\s+(?=Diem|Dieni)", "BG_", s, flags=re.IGNORECASE)
        s = re.sub(r"Dieni(?=[Vv]u)", "Diem", s)
        s = re.sub(r"\bluc(?:kv|icv|k|iy|iw|ky)m(?:an|en)\b", "luckyman", s, flags=re.IGNORECASE)
        s = re.sub(r"\bD[ijJ][oO0uUD](?:ko|ku|uo|im|k0|kn)N[aAd](?:m|tn|in)\b", "DjokoNam", s, flags=re.IGNORECASE)
        s = re.sub(r"\bn[gqy]u[vy]enbb\b", "nguyenbb", s, flags=re.IGNORECASE)
        s = re.sub(r"\b(?:[Il1]king|kin[gq]|kiri[Zz2]|ki\s+n\s+g|ki\s+ng|k\s+ing)\b", "king", s, flags=re.IGNORECASE)
        s = re.sub(r"\b(?:[LlI1]?Aja[wxv]|LAJax)\b", "Ajax", s, flags=re.IGNORECASE)
        s = re.sub(r"\b(?:[zapg3]pp[li1]e|ap\s+pie|lappip)\b", "apple", s, flags=re.IGNORECASE)
        s = re.sub(r"\b(?:Pig|Piq|Pill|Plg|Ptq|fhq)\s+A[trlu]{1,2}[ui]la\b", "Pig Atula", s, flags=re.IGNORECASE)
        s = re.sub(r"\b(?:MINH|MINif|rilNii|M1NH)\s+MEM(?:\s+MA[I1l]?)?\b", "MINH MEM MAI", s, flags=re.IGNORECASE)
        s = re.sub(r"^MEM\s+MAI$", "MINH MEM MAI", s, flags=re.IGNORECASE)
        s = re.sub(r"\bBG[_\s]+Die(?:m|rn|ni)Vu[ou]ng\b", "BG_DiemVuong", s, flags=re.IGNORECASE)
        s = re.sub(r"\b(?:THU\s+)?(?:THAN|IRAN|IHAN|I\s+HAN)\s+[fTH]{1,2}[lI1]?E[NnUu]\b", "THU THAN THIEN", s, flags=re.IGNORECASE)
        s = re.sub(r"\b(?:THU\s+THAN\s+)?THIEN\b", lambda m: "THU THAN THIEN" if len(s) <= 6 and s.upper() == "THIEN" else m.group(0), s)
        s = re.sub(r"\b([A-Za-z0-9_]*?)[oO]n[gq9]\b", r"\1ong", s)
        s = re.sub(r"\b([A-Za-z0-9_]*?)Vuang\b", r"\1Vuong", s)
        s = re.sub(r"\b(?:IHU|THIJ)\b", "THU", s, flags=re.IGNORECASE)
        s = re.sub(r"\b[fT]H[lI1]E[NnUu]\b", "THIEN", s)
        return s.strip(" _-")

    @staticmethod
    def clean_and_match_player_name(
        norm_624x400: np.ndarray,
        ocr_name_candidates,
        row_idx: int,
        full_civ: str,
        streamer_name: str,
        known_players=None,
        is_self_row: bool = False,
    ):
        yc = int(round(95.0 + row_idx * 29.8))
        name_crop = norm_624x400[yc - 9:yc + 8, 8:134]
        min_n = np.min(name_crop, axis=2).astype(np.float32)
        max_n = np.max(name_crop, axis=2).astype(np.float32)
        sh_n = np.minimum(np.roll(min_n, -1, axis=0), np.roll(np.roll(min_n, -1, axis=0), -1, axis=1))
        wh_n = min_n - 0.55 * (max_n - min_n)
        bg_n = float(np.percentile(wh_n, 65))
        mask_n = (wh_n > max(bg_n + 20.0, 140.0)) & ((min_n - sh_n) > 40.0)
        if int(np.sum(mask_n)) < 10:
            return None

        if is_self_row and streamer_name and streamer_name.strip():
            return streamer_name.strip()

        def normalize_name_token(s: str) -> str:
            rep = {"2": "z", "0": "o", "1": "i", "4": "a", "6": "e", "5": "s", "$": "s", "@": "a"}
            out = []
            for ch in s.lower():
                ch = rep.get(ch, ch)
                if ch.isascii() and ch.isalpha():
                    out.append(ch)
            res_s = "".join(out)
            res_s = (
                res_s.replace("rn", "m")
                .replace("gott", "gort")
                .replace("gotm", "gort")
                .replace("gonw", "gort")
                .replace("allalh", "allath")
                .replace("allh", "allth")
            )
            return res_s

        cleaned_list = []
        norm_counts = {}
        exact_counts = {}
        for exp_idx, raw in enumerate(ocr_name_candidates):
            if not raw:
                continue
            cleaned = DiplomacyScanner.post_clean_aoe_player_name(raw)
            if len(cleaned) < 2:
                continue
            if re.match(r"^(player|red|blue)\s*\d*$", cleaned, flags=re.IGNORECASE):
                continue
            alpha_cnt = sum(1 for ch in cleaned if ch.isalpha())
            if alpha_cnt < 2:
                continue
            ntok = normalize_name_token(cleaned)
            if len(ntok) < 2:
                continue
            norm_counts[ntok] = norm_counts.get(ntok, 0) + 1
            exact_counts[cleaned.lower()] = exact_counts.get(cleaned.lower(), 0) + 1
            cleaned_list.append((exp_idx, raw, cleaned, ntok, alpha_cnt))

        best_raw = ""
        best_quality = -1e9
        for exp_idx, raw, cleaned, ntok, alpha_cnt in cleaned_list:
            weird_count = sum(1 for ch in raw if not (ch.isascii() and (ch.isalnum() or ch in " _-")))
            single_char_toks = sum(1 for tok in cleaned.split() if len(tok) == 1)
            exp_bonus = 1.5 if exp_idx in (1, 2) else 1.0
            consensus_bonus = (norm_counts.get(ntok, 1) - 1) * 3.5 + (exact_counts.get(cleaned.lower(), 1) - 1) * 2.0
            quality = alpha_cnt * 1.0 - weird_count * 2.0 - single_char_toks * 2.5 + exp_bonus + consensus_bonus
            if quality > best_quality:
                best_quality = quality
                best_raw = cleaned

        civ_specific_ai = CIV_AI_NAMES.get(full_civ, [])
        human_pool = []
        if known_players:
            for p in known_players:
                raw_pname = p.get("name") if isinstance(p, dict) else str(p)
                pname = DiplomacyScanner.post_clean_aoe_player_name(raw_pname) or raw_pname
                if pname and pname not in human_pool:
                    human_pool.append(pname)
        if streamer_name and streamer_name not in human_pool:
            human_pool.insert(0, streamer_name)

        all_candidates = [c for _, _, c, _, _ in cleaned_list]
        for c in ocr_name_candidates:
            if c and c not in all_candidates:
                all_candidates.append(c)
        if best_raw and best_raw not in all_candidates:
            all_candidates.insert(0, best_raw)

        # BƯỚC 1: Ưu tiên đối chiếu với danh sách người chơi đã biết (human_pool: Tài khoản trên hệ thống + Người chơi ở ván trước)
        best_human_name = None
        best_human_sim = 0.0
        for cand in all_candidates:
            cand_clean = DiplomacyScanner.post_clean_aoe_player_name(cand) or cand
            cand_alpha = normalize_name_token(cand_clean)
            if len(cand_alpha) < 2:
                continue
            cand_i = cand_alpha.replace("l", "i")
            for target in human_pool:
                target_alpha = normalize_name_token(target)
                target_i = target_alpha.replace("l", "i")
                if not target_alpha:
                    continue
                raw_sim = max(
                    difflib.SequenceMatcher(None, cand_alpha, target_alpha).ratio(),
                    difflib.SequenceMatcher(None, cand_i, target_i).ratio(),
                )
                if len(cand_i) >= 5 and (target_i.endswith(cand_i) or target_i.startswith(cand_i) or cand_i in target_i):
                    len_ratio = min(len(cand_i), len(target_i)) / max(len(cand_i), len(target_i))
                    raw_sim = max(raw_sim, 0.78 + 0.18 * len_ratio)
                if raw_sim > best_human_sim:
                    best_human_sim = raw_sim
                    best_human_name = target

        if best_human_name and best_human_sim >= 0.72:
            return best_human_name

        # Đo chiều rộng thực tế (nw) và trích xuất đặc trưng 2D của chữ tên người chơi trên dòng hiện tại
        crop = norm_624x400[yc - 7:yc + 4, 11:120]
        min_rgb = np.min(crop, axis=2).astype(np.float32)
        max_rgb = np.max(crop, axis=2).astype(np.float32)
        sh_rgb = np.roll(np.roll(min_rgb, -1, axis=0), -1, axis=1)
        wh = min_rgb - 0.45 * (max_rgb - min_rgb) + 0.45 * np.maximum(0.0, min_rgb - sh_rgb)
        thr = max(float(np.percentile(wh, 76)) + 14.0, 122.0)
        val = np.clip((wh - thr) / 50.0, 0.0, 1.0)
        mask = val > 0.22
        col_sum = np.sum(mask, axis=0)
        xmin = 0
        while xmin < len(col_sum) and col_sum[xmin] < 1:
            xmin += 1
        xmax = xmin
        empty_run = 0
        for x in range(xmin, len(col_sum)):
            if col_sum[x] >= 1:
                xmax = x
                empty_run = 0
            else:
                empty_run += 1
                if empty_run >= 7 and (xmax - xmin) >= 12:
                    break
        nw_obs = max(1, int(round((xmax - xmin + 1) * 1.0))) if xmax > xmin + 6 else 0

        tmpl_corr_map = {}
        if AI_NAME_TEMPLATES and xmax > xmin + 6:
            for ai_name in civ_specific_ai:
                if ai_name not in AI_NAME_TEMPLATES:
                    continue
                tmpl, tw = AI_NAME_TEMPLATES[ai_name]
                t_patch = tmpl[:, :tw]
                t_zero = t_patch - t_patch.mean()
                t_norm = float(np.sqrt(np.sum(t_zero ** 2))) + 1e-6
                best_mc = 0.0
                for dx_s in (0, 1, 2):
                    x_s = min(xmin + dx_s, xmax - 4)
                    sub_p = val[:, x_s:xmax + 1]
                    if sub_p.shape[1] < 4:
                        continue
                    p_res = cv2.resize(sub_p, (tw, 12), interpolation=cv2.INTER_LINEAR)
                    for dy_s in (-1, 0, 1):
                        p_sh = np.roll(p_res, dy_s, axis=0) if dy_s != 0 else p_res
                        p_zero = p_sh - p_sh.mean()
                        num = float(np.sum(p_zero * t_zero))
                        den = float(np.sqrt(np.sum(p_zero ** 2))) * t_norm + 1e-6
                        mc_val = num / den
                        if mc_val > best_mc:
                            best_mc = mc_val
                tmpl_corr_map[ai_name] = best_mc

        # BƯỚC 2: Nếu OCR đã đọc được tên người chơi hợp lệ (best_raw), chỉ cho phép khớp sang tên AI của máy
        # khi chuỗi chữ OCR thực sự giống tên AI đó (ví dụ khi đánh với máy Gortys, Aeacus, Vaballathus, Hatshepsut).
        # Tuyệt đối KHÔNG dùng độ rộng pixel của AI để ghi đè tên người chơi thật (như luckyman, DjokoNam, nguyenbb, king...).
        if best_raw:
            best_ai_str_match = None
            best_ai_str_sim = 0.0
            for cand in all_candidates:
                cand_alpha = normalize_name_token(cand)
                if len(cand_alpha) < 3:
                    continue
                cand_i = cand_alpha.replace("l", "i")
                for ai_target in civ_specific_ai:
                    t_alpha = normalize_name_token(ai_target)
                    t_i = t_alpha.replace("l", "i")
                    r_sim = max(
                        difflib.SequenceMatcher(None, cand_alpha, t_alpha).ratio(),
                        difflib.SequenceMatcher(None, cand_i, t_i).ratio(),
                    )
                    if len(cand_i) >= 4 and (t_i.endswith(cand_i) or t_i.startswith(cand_i)):
                        len_ratio = min(len(cand_i), len(t_i)) / max(len(cand_i), len(t_i))
                        r_sim = max(r_sim, 0.74 + 0.18 * len_ratio)
                    elif len(cand_i) >= 4 and t_i.startswith(cand_i[:3]):
                        r_sim = max(r_sim, 0.62)
                    if r_sim > best_ai_str_sim:
                        best_ai_str_sim = r_sim
                        best_ai_str_match = ai_target

            mc_for_str = tmpl_corr_map.get(best_ai_str_match, 0.0) if best_ai_str_match else 0.0
            if best_ai_str_match and (best_ai_str_sim >= 0.72 or (best_ai_str_sim >= 0.56 and mc_for_str >= 0.30)):
                if best_ai_str_match in ("Kammu", "Jimmu") and full_civ == "Yamato":
                    fc_crop = norm_624x400[yc - 7:yc + 3, 14:65]
                    wh_fc = np.min(fc_crop, axis=2).astype(np.float32) - 0.55 * (
                        np.max(fc_crop, axis=2).astype(np.float32) - np.min(fc_crop, axis=2).astype(np.float32)
                    )
                    cols_fc = np.where(np.sum(wh_fc > 155.0, axis=0) >= 1)[0]
                    span_w = int(cols_fc[-1] - cols_fc[0] + 1) if len(cols_fc) >= 2 else 0
                    return "Kammu" if span_w >= 34 else "Jimmu"
                return best_ai_str_match

            if len(best_raw) <= 4 and best_raw.isupper() and tmpl_corr_map:
                top_ai_mc_name = max(tmpl_corr_map, key=tmpl_corr_map.get)
                if tmpl_corr_map[top_ai_mc_name] >= 0.48:
                    return top_ai_mc_name

            return best_raw

        # BƯỚC 3: Chỉ khi OCR hoàn toàn không đọc được chữ nào (best_raw rỗng), mới dùng mẫu 2D của AI làm dự phòng
        if civ_specific_ai and tmpl_corr_map and nw_obs > 0:
            best_ai_t = None
            best_ai_sc = -1.0
            for ai_name in civ_specific_ai:
                if ai_name not in AI_NAME_TEMPLATES:
                    continue
                _, tw = AI_NAME_TEMPLATES[ai_name]
                w_score = max(0.0, 1.0 - abs(nw_obs - tw) / 20.0) * 0.42
                mc = tmpl_corr_map.get(ai_name, 0.0)
                total_sc = mc * 0.58 + w_score
                if total_sc > best_ai_sc:
                    best_ai_sc = total_sc
                    best_ai_t = ai_name
            if best_ai_t in ("Kammu", "Jimmu") and full_civ == "Yamato":
                first_char = norm_624x400[yc - 7:yc + 2, 14:22]
                wh_fc = np.min(first_char, axis=2).astype(np.float32)
                top_left_ink = float(np.mean(wh_fc[:4, :3] > 165))
                best_ai_t = "Kammu" if top_left_ink >= 0.25 else "Jimmu"
            if best_ai_t and best_ai_sc >= 0.42:
                return best_ai_t

        return None

    def parse_diplomacy_from_image(self, img_bgr: np.ndarray, streamer_name: str = "XO", known_players=None, force: bool = False):
        """
        Trích xuất toàn bộ thông tin từ ảnh chụp màn hình có mở bảng DIPLOMACY.
        """
        self.last_reject_reason = ""
        box, box_score = self.find_diplomacy_box(img_bgr)
        if box is None:
            self.last_reject_reason = f"Không tìm thấy khung viền hộp thoại Diplomacy (best_score={box_score:.1f})"
            return None

        x1, y1, x2, y2 = box
        crop = img_bgr[y1:y2, x1:x2]
        norm = cv2.resize(crop, (624, 400), interpolation=cv2.INTER_CUBIC)

        if not self.verify_is_diplomacy_dialog(norm):
            self.last_reject_reason = f"Khung ({x1},{y1})-({x2},{y2}) không qua bước xác thực: {self.last_verify_reason}"
            return None

        sig = self.compute_dialog_signature(norm)
        if not force and self.last_dialog_signature == sig and (time.time() - self.last_scan_time < 15.0):
            return {"status": "unchanged"}

        gray = cv2.cvtColor(norm, cv2.COLOR_BGR2GRAY)
        edges = np.abs(cv2.Sobel(gray, cv2.CV_32F, 1, 0, ksize=3)) + np.abs(cv2.Sobel(gray, cv2.CV_32F, 0, 1, ksize=3))

        active_rows = []
        multi_canvas = np.full((9 * 70, 2420, 3), 255, dtype=np.uint8)

        # Đặt tiêu đề DIPLOMACY và thanh cột Civilization/Ally/Neutral/Enemy vào dòng thứ 9 (row 8) để OCR xác thực
        hdr_title = norm[6:30, 225:405]
        hdr_up = cv2.resize(hdr_title, (0, 0), fx=2.0, fy=2.0, interpolation=cv2.INTER_LANCZOS4)
        min_ht = np.min(hdr_up, axis=2).astype(np.float32)
        max_ht = np.max(hdr_up, axis=2).astype(np.float32)
        wh_ht = min_ht - 0.55 * (max_ht - min_ht)
        a_ht = np.clip((wh_ht - 145.0) / 45.0, 0.0, 1.0)
        ink_ht = cv2.cvtColor((255.0 * (1.0 - a_ht)).astype(np.uint8), cv2.COLOR_GRAY2BGR)
        multi_canvas[8 * 70 + 8:8 * 70 + 8 + ink_ht.shape[0], 20:20 + ink_ht.shape[1]] = ink_ht

        hdr_cols = norm[50:74, 130:425]
        hdr_cols_up = cv2.resize(hdr_cols, (0, 0), fx=2.0, fy=2.0, interpolation=cv2.INTER_LANCZOS4)
        min_hc = np.min(hdr_cols_up, axis=2).astype(np.float32)
        max_hc = np.max(hdr_cols_up, axis=2).astype(np.float32)
        wh_hc = min_hc - 0.55 * (max_hc - min_hc)
        a_hc = np.clip((wh_hc - 140.0) / 45.0, 0.0, 1.0)
        ink_hc = cv2.cvtColor((255.0 * (1.0 - a_hc)).astype(np.uint8), cv2.COLOR_GRAY2BGR)
        multi_canvas[8 * 70 + 8:8 * 70 + 8 + ink_hc.shape[0], 500:500 + ink_hc.shape[1]] = ink_hc

        for r in range(8):
            yc = int(round(95.0 + r * 29.8))
            name_crop_check = norm[yc - 8:yc + 5, 8:134]
            min_nc = np.min(name_crop_check, axis=2).astype(np.float32)
            max_nc = np.max(name_crop_check, axis=2).astype(np.float32)
            sh_nc = np.minimum(np.roll(min_nc, -1, axis=0), np.roll(np.roll(min_nc, -1, axis=0), -1, axis=1))
            wh_nc = min_nc - 0.55 * (max_nc - min_nc)
            bg_nc = float(np.percentile(wh_nc, 65))
            mask_nc = (wh_nc > max(bg_nc + 20.0, 140.0)) & ((min_nc - sh_nc) > 40.0)

            civ_crop_check = norm[yc - 8:yc + 5, 140:235]
            min_cc = np.min(civ_crop_check, axis=2).astype(np.float32)
            max_cc = np.max(civ_crop_check, axis=2).astype(np.float32)
            sh_cc = np.minimum(np.roll(min_cc, -1, axis=0), np.roll(np.roll(min_cc, -1, axis=0), -1, axis=1))
            wh_cc = min_cc - 0.55 * (max_cc - min_cc)
            bg_cc = float(np.percentile(wh_cc, 65))
            mask_cc = (wh_cc > max(bg_cc + 22.0, 145.0)) & ((min_cc - sh_cc) > 45.0)
            if np.sum(mask_cc) < 12 or np.sum(mask_nc) < 10:
                continue

            civ_crop = norm[yc - 9:yc + 9, 140:235]
            min_c = np.min(civ_crop, axis=2).astype(np.float32)
            max_c = np.max(civ_crop, axis=2).astype(np.float32)
            wh_c = min_c - 0.55 * (max_c - min_c)
            bg_c = float(np.percentile(wh_c, 55))
            mask_c = wh_c > max(bg_c + 20.0, 140.0)

            col_counts = np.sum(mask_c, axis=0)
            valid_xs = np.where(col_counts >= 1)[0]
            if len(valid_xs) > 0:
                x0 = int(valid_xs[0])
                x1_w = x0
                empty_r = 0
                for xc in range(x0, len(col_counts)):
                    if col_counts[xc] >= 1:
                        x1_w = xc
                        empty_r = 0
                    else:
                        empty_r += 1
                        if empty_r >= 6 and (x1_w - x0) >= 14:
                            break
                w_obs = int(x1_w - x0 + 1)
            else:
                w_obs = 0

            s_ally = float(np.mean(edges[yc - 6:yc + 6, 248:262]))
            s_neut = float(np.mean(edges[yc - 6:yc + 6, 317:331]))
            s_enem = float(np.mean(edges[yc - 6:yc + 6, 387:401]))
            max_radio = max(s_ally, s_neut, s_enem)
            min_radio = min(s_ally, s_neut, s_enem)
            radio_diff = max_radio - min_radio

            if s_ally > s_neut and s_ally > s_enem and s_ally > 80.0:
                stance = "ALLY"
            else:
                stance = "ENEMY"

            hsv_feat = self.extract_ribbon_hsv(norm, r)
            active_rows.append({
                "row_idx": r,
                "stance": stance,
                "s_ally": s_ally,
                "s_neut": s_neut,
                "s_enem": s_enem,
                "max_radio": max_radio,
                "radio_diff": radio_diff,
                "hsv_feat": hsv_feat,
                "w_obs": w_obs,
            })

            # 1) Cột Tên Người Chơi (x: 9..124, y: yc-9..yc+8 giữ trọn tên dài & tách biệt hoàn toàn với cột Quân ở base_x=340)
            name_cell = norm[yc - 9:yc + 8, 9:124]
            up_n = cv2.resize(name_cell, (0, 0), fx=2.5, fy=2.5, interpolation=cv2.INTER_LANCZOS4)
            min_n1 = np.min(up_n, axis=2).astype(np.float32)
            max_n1 = np.max(up_n, axis=2).astype(np.float32)
            wh_n1 = min_n1 - 0.65 * (max_n1 - min_n1)
            bg_n1 = float(np.percentile(wh_n1, 65))
            a_n1 = np.clip((wh_n1 - (bg_n1 + 18.0)) / 42.0, 0.0, 1.0)
            ink_n1 = cv2.cvtColor((255.0 * (1.0 - a_n1)).astype(np.uint8), cv2.COLOR_GRAY2BGR)

            sh_n1 = np.roll(np.roll(min_n1, -2, axis=0), -2, axis=1)
            wh_n_sh = wh_n1 + 0.45 * np.maximum(0.0, min_n1 - sh_n1)
            bg_n_sh = float(np.percentile(wh_n_sh, 68))
            a_n2 = np.clip((wh_n_sh - (bg_n_sh + 22.0)) / 48.0, 0.0, 1.0)
            ink_n2 = cv2.cvtColor((255.0 * (1.0 - a_n2)).astype(np.uint8), cv2.COLOR_GRAY2BGR)

            sh_n_dark = np.minimum(np.roll(min_n1, -2, axis=0), np.roll(np.roll(min_n1, -2, axis=0), -2, axis=1))
            wh_n_drop = min_n1 - 0.35 * (max_n1 - min_n1) + 0.65 * np.maximum(0.0, min_n1 - sh_n_dark)
            bg_n3 = float(np.percentile(wh_n_drop, 72))
            a_n3 = np.clip((wh_n_drop - (bg_n3 + 18.0)) / 45.0, 0.0, 1.0)
            ink_n3 = cv2.cvtColor((255.0 * (1.0 - a_n3)).astype(np.uint8), cv2.COLOR_GRAY2BGR)

            bg_n4 = float(np.percentile(wh_n_drop, 80))
            a_n4 = np.clip((wh_n_drop - (bg_n4 + 14.0)) / 36.0, 0.0, 1.0)
            ink_n4 = cv2.cvtColor((255.0 * (1.0 - a_n4)).astype(np.uint8), cv2.COLOR_GRAY2BGR)

            hpn, wpn = ink_n1.shape[:2]
            multi_canvas[r * 70 + 12:r * 70 + 12 + hpn, 20:20 + wpn] = ink_n1
            multi_canvas[r * 70 + 12:r * 70 + 12 + hpn, 620:620 + wpn] = ink_n2
            multi_canvas[r * 70 + 12:r * 70 + 12 + hpn, 1220:1220 + wpn] = ink_n3
            multi_canvas[r * 70 + 12:r * 70 + 12 + hpn, 1820:1820 + wpn] = ink_n4

            # 2) Cột Tên Quân Civilization (x: 140..238, đặt tại base_x=340 cách biệt hoàn toàn với cột Tên)
            for x_start, x_end, base_x in [(140, 238, 340)]:
                cell = norm[yc - 8:yc + 4, x_start:x_end]
                up1 = cv2.resize(cell, (0, 0), fx=2.5, fy=2.5, interpolation=cv2.INTER_LANCZOS4)
                min1 = np.min(up1, axis=2).astype(np.float32)
                max1 = np.max(up1, axis=2).astype(np.float32)
                wh1 = min1 - 0.65 * (max1 - min1)
                bg1 = float(np.percentile(wh1, 65))

                # Phơi sáng 1: Khử vân gỗ vàng (Tan Wood) & giữ nét chữ trắng thuần khiết
                a1 = np.clip((wh1 - (bg1 + 18.0)) / 42.0, 0.0, 1.0)
                ink1 = cv2.cvtColor((255.0 * (1.0 - a1)).astype(np.uint8), cv2.COLOR_GRAY2BGR)

                # Phơi sáng 2: Tăng cường bóng đổ chữ trắng (Drop-shadow enhancement) cho cả nền gỗ và nền cờ màu
                sh1 = np.roll(np.roll(min1, -2, axis=0), -2, axis=1)
                wh_sh = wh1 + 0.45 * np.maximum(0.0, min1 - sh1)
                bg_sh = float(np.percentile(wh_sh, 68))
                a2 = np.clip((wh_sh - (bg_sh + 22.0)) / 48.0, 0.0, 1.0)
                ink2 = cv2.cvtColor((255.0 * (1.0 - a2)).astype(np.uint8), cv2.COLOR_GRAY2BGR)

                # Phơi sáng 3: Ngưỡng cao sắc nét (High-percentile)
                bg3 = float(np.percentile(wh1, 78))
                a3 = np.clip((wh1 - (bg3 + 12.0)) / 36.0, 0.0, 1.0)
                ink3 = cv2.cvtColor((255.0 * (1.0 - a3)).astype(np.uint8), cv2.COLOR_GRAY2BGR)

                # Phơi sáng 4: Nối nét ngang nhẹ trên kênh bóng đổ
                kernel = np.array([[0.15, 1.0, 0.15]], dtype=np.float32)
                a4 = np.clip(cv2.filter2D(a2, -1, kernel), 0.0, 1.0)
                ink4 = cv2.cvtColor((255.0 * (1.0 - a4)).astype(np.uint8), cv2.COLOR_GRAY2BGR)
                hp4, wp4 = ink4.shape[:2]

                hp, wp = ink1.shape[:2]
                multi_canvas[r * 70 + 18:r * 70 + 18 + hp, base_x:base_x + wp] = ink1
                multi_canvas[r * 70 + 18:r * 70 + 18 + hp, base_x + 600:base_x + 600 + wp] = ink2
                multi_canvas[r * 70 + 18:r * 70 + 18 + hp, base_x + 1200:base_x + 1200 + wp] = ink3
                multi_canvas[r * 70 + 18:r * 70 + 18 + hp4, base_x + 1800:base_x + 1800 + wp4] = ink4

        # Phải có ít nhất 2 người chơi, số người chơi phải chẵn (1v1, 2v2, 3v3, 4v4) và dòng 0 bắt buộc phải có mặt
        if len(active_rows) < 2 or len(active_rows) % 2 != 0 or active_rows[0]["row_idx"] != 0:
            self.last_reject_reason = f"Số dòng người chơi không hợp lệ ({len(active_rows)} dòng: {[r['row_idx'] for r in active_rows]})"
            return None

        # Xác định dòng của chính người chơi mở Diplomacy dựa trên độ chênh lệch nút tích (radio_diff = max_radio - min_radio):
        # Dòng của bản thân không có ô tích [X] nên cả 3 vị trí đều là nền phẳng (radio_diff ~ 4..25),
        # trong khi các dòng người chơi khác có 1 ô tích [X] sáng rõ (radio_diff ~ 70..240) trên cả nền Đá Xám lẫn Gỗ Vàng!
        min_diff_row = min(active_rows, key=lambda it: it["radio_diff"])
        self_row = min_diff_row if min_diff_row["radio_diff"] < 48.0 else active_rows[0]

        for it in active_rows:
            if it is self_row:
                it["is_self"] = True
                it["stance"] = "ALLY"
            else:
                it["is_self"] = False
                if it["s_ally"] > it["s_neut"] and it["s_ally"] > it["s_enem"] and it["s_ally"] > 80.0:
                    it["stance"] = "ALLY"
                else:
                    it["stance"] = "ENEMY"

        assigned_colors = self.assign_player_colors([item["hsv_feat"] for item in active_rows])
        for item, color_id in zip(active_rows, assigned_colors):
            item["color_id"] = color_id

        ocr_words = self.run_windows_ocr_batch(multi_canvas)

        # Kiểm tra xác thực tiêu đề DIPLOMACY / Civilization / Ally / Neutral / Enemy ở dòng thứ 9 (row 8)
        hdr_texts = [str(w.get("text", "")).lower() for w in ocr_words if w.get("y", -1) >= 8 * 70]
        hdr_joined = " ".join(hdr_texts)
        has_hdr_keyword = any(
            kw in hdr_joined for kw in ("diplom", "dipiom", "civil", "civii", "ally", "neutral", "enemy")
        )

        for item in active_rows:
            r = item["row_idx"]
            row_y_min, row_y_max = r * 70, (r + 1) * 70
            name_cands = [[], [], [], []]
            civ_cands = [[], [], [], []]
            for w in ocr_words:
                wy = w.get("y", -1)
                if row_y_min <= wy < row_y_max:
                    wx = w.get("x", 0)
                    exp_idx = wx // 600
                    if exp_idx > 3:
                        continue
                    rel_x = wx % 600
                    ww = max(8, int(w.get("w", 16)))
                    if rel_x < 322:
                        name_cands[exp_idx].append((rel_x, ww, str(w.get("text", ""))))
                    else:
                        civ_cands[exp_idx].append((rel_x, str(w.get("text", ""))))

            name_strs = []
            for cand in name_cands:
                if not cand:
                    continue
                scand = sorted(cand, key=lambda it: it[0])
                kept_tokens = []
                prev_end = None
                for rx, rw, tok in scand:
                    alpha_tok = sum(1 for ch in tok if ch.isalpha())
                    # Nếu token nằm xa về bên phải (vùng đuôi dải cờ x >= 170) và cách chữ trước > 38px hoặc chỉ là ký tự rác 1 chữ
                    if prev_end is not None and rx >= 170 and (rx - prev_end > 38 or alpha_tok <= 1):
                        continue
                    kept_tokens.append(tok)
                    prev_end = rx + rw
                if kept_tokens:
                    name_strs.append(" ".join(kept_tokens))
            civ_strs = [" ".join(t for _, t in sorted(cand)) for cand in civ_cands if cand]

            full_civ, short_civ = self.match_civ_for_row(norm, r, civ_strs, item["w_obs"])
            if not full_civ or not short_civ:
                self.last_reject_reason = f"Dòng {r+1} không nhận diện được tên Quân (OCR={civ_strs}, w_obs={item['w_obs']})"
                return None

            player_name = self.clean_and_match_player_name(
                norm,
                name_strs,
                r,
                full_civ,
                streamer_name,
                known_players,
                is_self_row=bool(item.get("is_self", False)),
            )
            if not player_name:
                self.last_reject_reason = f"Dòng {r+1} ({full_civ}) không nhận diện được tên Player (OCR={name_strs})"
                return None

            item["name"] = player_name
            item["civ_full"] = full_civ
            item["civ_short"] = short_civ
            item["has_ocr_civ"] = bool(civ_strs)

        # Nếu OCR không đọc được chữ tiêu đề hộp thoại và cũng không đọc được chữ tên Quân nào -> loại bỏ cảnh giả
        if not has_hdr_keyword and sum(1 for it in active_rows if it.get("has_ocr_civ")) < max(1, len(active_rows) // 2):
            self.last_reject_reason = f"OCR không xác thực được tiêu đề hoặc tên Quân (hdr='{hdr_joined}')"
            return None

        red_rows = [item for item in active_rows if item["stance"] == "ALLY"]
        blue_rows = [item for item in active_rows if item["stance"] != "ALLY"]

        if (len(red_rows) == 1 and len(blue_rows) >= 3 and len(active_rows) % 2 == 0) or not red_rows or not blue_rows:
            half = max(1, len(active_rows) // 2)
            self_pos = next((idx for idx, it in enumerate(active_rows) if it.get("is_self")), 0)
            if self_pos >= half:
                red_rows = active_rows[half:]
                blue_rows = active_rows[:half]
            else:
                red_rows = active_rows[:half]
                blue_rows = active_rows[half:]

        # Bắt buộc 2 đội phải cân bằng số lượng người chơi (1v1, 2v2, 3v3, 4v4) và có đủ tên + quân
        if not red_rows or not blue_rows or len(red_rows) != len(blue_rows):
            self.last_reject_reason = f"Số người chơi 2 phe không cân bằng (Đỏ={len(red_rows)}, Xanh={len(blue_rows)})"
            return None

        # Đảm bảo người mở Diplomacy (is_self) đứng đầu danh sách Team Đỏ mặc định
        red_rows.sort(key=lambda r_it: 0 if r_it.get("is_self") else 1)

        # Chỉ lưu chữ ký sau khi đã nhận diện thành công đầy đủ cả 2 đội
        self.last_dialog_signature = sig
        self.last_scan_time = time.time()

        return {
            "status": "ok",
            "box": box,
            "box_score": round(float(box_score), 1),
            "img_size": (int(img_bgr.shape[1]), int(img_bgr.shape[0])),
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
    "DIAMOND": ("💎 Hạng Kim Cương", "#f59e0b", "#241b10"),
    "GOLD": ("🥇 Hạng Vàng", "#f59e0b", "#241b10"),
    "SILVER": ("🥈 Hạng Bạc", "#e7ebf0", "#1a2130"),
    "BRONZE": ("🥉 Hạng Đồng", "#d97706", "#1f160e"),
}

AOE_GIFT_ITEMS = [
    ("FOOD_200", "🍖 200 Thực", 5, "Bơm 200 Thực cứu chủ lực!"),
    ("WOOD_500", "🪵 500 Gỗ", 10, "Bơm 500 Gỗ đóng nhà BA!"),
    ("FOOD_1000", "🥩 1000 Thực", 15, "Bơm 1000 Thực kích Đời 4!"),
    ("ELEPHANT", "🐘 Con Voi", 22, "Thả Voi Điên húc bay nhà địch!"),
    ("HORSE_ARCHER", "🏹 Song Mã", 50, "Viện trợ Đạo Song Mã thần cứu nhà!"),
    ("PRIEST_LIGHTNING", "⚡ Phù Thủy Sét", 100, "Triệu hồi Phù Thủy Sét (Wololo) — Ái dà, hú hú!"),
]


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
        try:
            self.root.tk.call("tk", "scaling", 1.38)
        except Exception:
            pass
        try:
            sw = int(self.root.winfo_screenwidth())
            sh = int(self.root.winfo_screenheight())
            win_w, win_h = 1600, 900
            pos_x = max(0, (sw - win_w) // 2)
            pos_y = max(0, (sh - win_h) // 2 - 15)
            self.root.geometry(f"{win_w}x{win_h}+{pos_x}+{pos_y}")
        except Exception:
            self.root.geometry("1600x900")
        self.root.minsize(1200, 720)
        self.root.configure(bg="#0b0e14")
        self.root.resizable(True, True)

        self.settings = load_user_settings()
        self.scanner = DiplomacyScanner()
        self.is_logged_in = False
        self.is_admin = False
        self.admin_password = ""
        self.player_tier = "BRONZE"
        self.my_stars_balance = 0
        self.known_players = []
        self.my_friends = []
        self.active_lobby_streamer = ""
        self.current_match = None
        self.last_parsed_teams = None
        self.running = True
        self._did_finish_on_exit = False
        self._last_chat_id = None
        self._diplomacy_scan_window_until = 0.0
        self._diplomacy_trigger_reason = ""
        self.server_release_info = {
            "latestVersion": APP_VERSION_NUMBER,
            "downloadUrl": "/download-tool",
            "releaseNotes": "",
            "forceUpdate": False,
        }
        self._prompted_update_version = None

        self._configure_ttk_styles()
        self._build_ui()

        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        # Dự phòng: nếu tiến trình thoát theo đường khác (sys.exit, lỗi...), vẫn gửi lệnh kết thúc kèo LIVE
        atexit.register(lambda: self._auto_finish_match_sync() if self.is_logged_in else None)

        self._start_clock_loop()
        threading.Thread(target=self._startup_version_check, daemon=True).start()
        self.event_listener_thread = threading.Thread(target=self._monitor_diplomacy_events, daemon=True)
        self.event_listener_thread.start()
        self.threading_loop = threading.Thread(target=self._background_worker, daemon=True)
        self.threading_loop.start()

    def _configure_ttk_styles(self):
        style = self.ttk.Style()
        try:
            style.theme_use("clam")
        except Exception:
            pass
        style.configure(
            "Premium.TCombobox",
            fieldbackground="#141f33",
            background="#0e1524",
            foreground="#f1f5f9",
            arrowcolor="#38bdf8",
            bordercolor="#1e2d47",
            lightcolor="#1e2d47",
            darkcolor="#070b12",
        )
        style.map(
            "Premium.TCombobox",
            fieldbackground=[("readonly", "#141f33")],
            selectbackground=[("readonly", "#141f33")],
            selectforeground=[("readonly", "#f1f5f9")],
        )
        style.configure(
            "Treeview",
            background="#0f1726",
            foreground="#e2e8f0",
            fieldbackground="#0f1726",
            bordercolor="#1e2d47",
            rowheight=28,
            font=("Segoe UI", 9),
        )
        style.configure(
            "Treeview.Heading",
            background="#0a101d",
            foreground="#38bdf8",
            bordercolor="#1e2d47",
            font=("Segoe UI", 9, "bold"),
        )
        style.map(
            "Treeview",
            background=[("selected", "#0369a1")],
            foreground=[("selected", "#f8fafc")],
        )
        style.map(
            "Treeview.Heading",
            background=[("active", "#16243d")],
            foreground=[("active", "#facc15")],
        )

        # Thanh cuộn tối tùy biến (Custom Dark Scrollbar) mỏng ~8px: nền #121721, thanh trượt #334155, hover #475569
        for orient in ("Vertical", "Horizontal"):
            sb_style = f"Dark.{orient}.TScrollbar"
            try:
                style.layout(
                    sb_style,
                    [
                        (
                            f"{orient}.Scrollbar.trough",
                            {
                                "sticky": "ns" if orient == "Vertical" else "ew",
                                "children": [(f"{orient}.Scrollbar.thumb", {"expand": "1", "sticky": "nswe"})],
                            },
                        )
                    ],
                )
            except Exception:
                pass
            style.configure(
                sb_style,
                troughcolor="#121721",
                background="#334155",
                bordercolor="#121721",
                lightcolor="#334155",
                darkcolor="#334155",
                arrowcolor="#94a3b8",
                gripcount=0,
                relief="flat",
                borderwidth=0,
                width=8,
                arrowsize=8,
            )
            style.map(
                sb_style,
                background=[("pressed", "#64748b"), ("active", "#475569")],
                lightcolor=[("active", "#475569")],
                darkcolor=[("active", "#475569")],
            )

    def _make_dark_scrollbar(self, parent, orient: str = "vertical", command=None):
        """Tạo thanh cuộn tối mỏng thay thế thanh cuộn trắng mặc định của Windows."""
        style_name = "Dark.Vertical.TScrollbar" if orient == "vertical" else "Dark.Horizontal.TScrollbar"
        sb = self.ttk.Scrollbar(parent, orient=orient, style=style_name)
        if command is not None:
            sb.configure(command=command)
        return sb

    def _make_ellipsis_label(self, parent, **kw):
        """Nhãn 1 dòng tự rút gọn bằng '…' theo chiều rộng thực tế (text-overflow: ellipsis) + tooltip nội dung đầy đủ.
        Giữ nguyên cách gọi .config(text=...) / .configure(text=...) của toàn bộ code cũ."""
        tk = self.tk
        app = self

        class _EllipsisLabel(tk.Label):
            def __init__(self, master, **opts):
                self._full_text = str(opts.get("text", "") or "")
                opts.setdefault("width", 1)
                super().__init__(master, **opts)
                self.bind("<Configure>", lambda _e: self._refit(), add="+")
                app._attach_tooltip(self, lambda: self._full_text if self._is_truncated() else "")

            def _avail_px(self):
                try:
                    return int(self.winfo_width()) - 2 * int(float(str(self.cget("padx")) or 0)) - 4
                except Exception:
                    return 0

            def _is_truncated(self):
                try:
                    return str(super().cget("text")) != self._full_text
                except Exception:
                    return False

            def _refit(self):
                try:
                    avail = self._avail_px()
                    shown = app._ellipsize_text(self._full_text, self.cget("font"), avail) if avail > 20 else self._full_text
                    if str(super().cget("text")) != shown:
                        super().configure(text=shown)
                except Exception:
                    pass

            def configure(self, cnf=None, **opts):
                if isinstance(cnf, dict) and "text" in cnf:
                    cnf = dict(cnf)
                    opts["text"] = cnf.pop("text")
                if "text" in opts:
                    self._full_text = str(opts.get("text") or "")
                    avail = self._avail_px()
                    if avail > 20:
                        opts["text"] = app._ellipsize_text(self._full_text, opts.get("font") or self.cget("font"), avail)
                return super().configure(cnf, **opts)

            config = configure

        return _EllipsisLabel(parent, **kw)

    def _auto_wrap_label(self, label, pad: int = 6, min_wrap: int = 80):
        """Tự động xuống dòng nhãn theo chiều rộng thực tế được cấp phát (không bao giờ bị cắt chữ)."""

        def _on_cfg(e):
            try:
                new_w = max(min_wrap, int(e.width) - pad)
                cur_w = int(float(str(label.cget("wraplength")) or 0))
                if abs(cur_w - new_w) > 3:
                    label.configure(wraplength=new_w)
            except Exception:
                pass

        label.bind("<Configure>", _on_cfg, add="+")
        return label

    def _ellipsize_text(self, text: str, font_spec, max_px: int) -> str:
        """Rút gọn chuỗi bằng dấu '…' cho vừa chiều rộng pixel (text-overflow: ellipsis)."""
        try:
            import tkinter.font as tkfont

            f = tkfont.Font(root=self.root, font=font_spec)
            s = str(text or "")
            if max_px <= 0 or f.measure(s) <= max_px:
                return s
            lo, hi = 0, len(s)
            while lo < hi:
                mid = (lo + hi + 1) // 2
                if f.measure(s[:mid] + "…") <= max_px:
                    lo = mid
                else:
                    hi = mid - 1
            return s[:lo].rstrip() + "…"
        except Exception:
            return str(text or "")

    def _attach_tooltip(self, widget, text_or_fn):
        """Hiển thị tooltip đầy đủ nội dung khi rê chuột vào nhãn đã bị rút gọn."""
        tk = self.tk
        state = {"tip": None}

        def _show(_e):
            try:
                txt = text_or_fn() if callable(text_or_fn) else str(text_or_fn or "")
                if not txt:
                    return
                tip = tk.Toplevel(widget)
                tip.wm_overrideredirect(True)
                tip.configure(bg="#262f40")
                tk.Label(
                    tip,
                    text=txt,
                    font=("Segoe UI", 8, "bold"),
                    fg="#e2e8f0",
                    bg="#1a2130",
                    padx=8,
                    pady=4,
                    justify="left",
                    wraplength=420,
                ).pack(padx=1, pady=1)
                tip.wm_geometry(f"+{widget.winfo_rootx() + 8}+{widget.winfo_rooty() + widget.winfo_height() + 4}")
                state["tip"] = tip
            except Exception:
                pass

        def _hide(_e):
            try:
                if state["tip"] is not None:
                    state["tip"].destroy()
            except Exception:
                pass
            state["tip"] = None

        widget.bind("<Enter>", _show, add="+")
        widget.bind("<Leave>", _hide, add="+")
        widget.bind("<ButtonPress>", _hide, add="+")

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

    def _create_brand_crest_canvas(self, parent, size: int = 44, bg_color: str = "#1a2130"):
        """Vẽ biểu tượng Vector Khiên Chiến Thuật + Song Kiếm + Vương Miện 'XO' đồng bộ với public/logo.svg."""
        tk = self.tk
        cv = tk.Canvas(
            parent,
            width=size,
            height=size,
            bg=bg_color,
            highlightthickness=0,
            bd=0,
        )
        s = size / 128.0
        # Song kiếm chéo phía sau khiên
        cv.create_line(int(18 * s), int(18 * s), int(108 * s), int(108 * s), fill="#f59e0b", width=max(2, int(6 * s)))
        cv.create_line(int(110 * s), int(18 * s), int(20 * s), int(108 * s), fill="#f59e0b", width=max(2, int(6 * s)))
        # Khung Khiên Obsidian viền Vàng Hoàng Gia
        shield_pts = [
            int(64 * s), int(10 * s),
            int(108 * s), int(26 * s),
            int(108 * s), int(64 * s),
            int(88 * s), int(104 * s),
            int(64 * s), int(118 * s),
            int(40 * s), int(104 * s),
            int(20 * s), int(64 * s),
            int(20 * s), int(26 * s),
        ]
        cv.create_polygon(shield_pts, fill="#0f172a", outline="#f59e0b", width=max(2, int(4 * s)))
        # Viền chiến thuật Cyan bên trong
        inner_pts = [
            int(64 * s), int(19 * s),
            int(99 * s), int(32 * s),
            int(99 * s), int(62 * s),
            int(82 * s), int(96 * s),
            int(64 * s), int(108 * s),
            int(46 * s), int(96 * s),
            int(29 * s), int(62 * s),
            int(29 * s), int(32 * s),
        ]
        cv.create_polygon(inner_pts, fill="", outline="#38bdf8", width=1)
        # Vương miện nhỏ phía trên tâm khiên
        crown_pts = [
            int(46 * s), int(39 * s),
            int(51 * s), int(27 * s),
            int(64 * s), int(34 * s),
            int(77 * s), int(27 * s),
            int(82 * s), int(39 * s),
        ]
        cv.create_polygon(crown_pts, fill="#fde047", outline="")
        # Chữ Monogram "XO" ở tâm khiên
        font_sz = max(8, int(22 * s))
        cv.create_text(
            int(64 * s),
            int(66 * s),
            text="XO",
            fill="#fef08a",
            font=("Segoe UI", font_sz, "bold"),
        )
        return cv

    def _create_team_shield_canvas(self, parent, team: str = "RED", size: int = 58, bg_color: str = "#161218"):
        """Vẽ biểu tượng Khiên Chiến Thuật Esports cho TEAM ĐỎ (Đỏ Crimson) và TEAM XANH (Xanh Royal)."""
        tk = self.tk
        cv = tk.Canvas(
            parent,
            width=size,
            height=size,
            bg=bg_color,
            highlightthickness=0,
            bd=0,
        )
        s = size / 100.0
        is_red = str(team).upper() == "RED"
        outer_border = "#ef4444" if is_red else "#3b82f6"
        inner_border = "#fca5a5" if is_red else "#93c5fd"
        shield_fill = "#2d1219" if is_red else "#10203b"
        emblem_fg = "#f87171" if is_red else "#60a5fa"

        # Hào quang viền ngoài khiên
        outer_pts = [
            int(50 * s), int(6 * s),
            int(88 * s), int(20 * s),
            int(88 * s), int(54 * s),
            int(72 * s), int(84 * s),
            int(50 * s), int(95 * s),
            int(28 * s), int(84 * s),
            int(12 * s), int(54 * s),
            int(12 * s), int(20 * s),
        ]
        cv.create_polygon(outer_pts, fill=shield_fill, outline=outer_border, width=max(2, int(3 * s)))

        # Viền bạc/sáng bên trong khiên
        inner_pts = [
            int(50 * s), int(14 * s),
            int(79 * s), int(25 * s),
            int(79 * s), int(51 * s),
            int(66 * s), int(76 * s),
            int(50 * s), int(86 * s),
            int(34 * s), int(76 * s),
            int(21 * s), int(51 * s),
            int(21 * s), int(25 * s),
        ]
        cv.create_polygon(inner_pts, fill="", outline=inner_border, width=1)

        if is_red:
            # Họa tiết chữ thập kiếm chiến thuật Team Đỏ
            cv.create_line(int(50 * s), int(22 * s), int(50 * s), int(76 * s), fill=inner_border, width=max(2, int(3 * s)))
            cv.create_line(int(30 * s), int(44 * s), int(70 * s), int(44 * s), fill=inner_border, width=max(2, int(3 * s)))
            cv.create_oval(int(36 * s), int(30 * s), int(64 * s), int(58 * s), outline=emblem_fg, width=max(1, int(2 * s)))
        else:
            # Họa tiết khiên sao chiến thuật Team Xanh
            diamond_pts = [
                int(50 * s), int(24 * s),
                int(68 * s), int(48 * s),
                int(50 * s), int(74 * s),
                int(32 * s), int(48 * s),
            ]
            cv.create_polygon(diamond_pts, fill="#1d4ed8", outline=inner_border, width=max(1, int(2 * s)))
            cv.create_oval(int(43 * s), int(41 * s), int(57 * s), int(55 * s), fill=inner_border, outline="")
        return cv

    def _show_admin_management_menu(self):
        """Hiển thị menu gom nhóm các chức năng Quản trị & Hệ thống ở Khu vực A."""
        tk = self.tk
        menu = tk.Menu(
            self.root,
            tearoff=0,
            bg="#131822",
            fg="#e7ebf0",
            activebackground="#f59e0b",
            activeforeground="#0b0e14",
            font=("Segoe UI", 9, "bold"),
            bd=1,
            relief="solid",
        )
        menu.add_command(label="🛡️ Quản trị hệ thống & Cấp VIP (Admin XO)", command=self.open_admin_manager_window)
        menu.add_separator()
        menu.add_command(label="👤 Hồ sơ & Đổi mật khẩu cá nhân", command=self.open_my_profile_window)
        menu.add_command(label="⚙️ Tùy chỉnh Cài đặt VIP Overlay", command=lambda: self.switch_main_tab("SETTINGS"))
        menu.add_command(label="📺 Hướng dẫn gán OBS Studio", command=self.show_obs_guide_window)
        menu.add_command(label="🔵 Cầu nối Comment Facebook Group Live", command=self.show_fb_group_live_bridge_window)
        menu.add_separator()
        menu.add_command(label="🌐 Mở Web Dashboard trên trình duyệt", command=self.open_web_dashboard)
        try:
            x = self.admin_mgr_btn.winfo_rootx()
            y = self.admin_mgr_btn.winfo_rooty() + self.admin_mgr_btn.winfo_height() + 2
            menu.tk_popup(x, y)
        finally:
            menu.grab_release()

    def _show_quick_emoji_menu(self):
        """Menu chọn nhanh biểu cảm / khẩu hiệu Đế Chế AOE trong Khu vực D."""
        tk = self.tk
        menu = tk.Menu(
            self.root,
            tearoff=0,
            bg="#131822",
            fg="#e7ebf0",
            activebackground="#f59e0b",
            activeforeground="#0b0e14",
            font=("Segoe UI", 9, "bold"),
            bd=1,
            relief="solid",
        )
        cheers = [
            "🔥 Đánh hay quá idol ơi!",
            "🐘 Thả Voi điên húc bay nhà địch!",
            "⚡ Wololo! Ái dà hú hú!",
            "🏹 Điều cung R đỉnh cao quá!",
            "🥩 Bơm đồ kích 4 cân bản đồ!",
            "👑 Kèo đấu siêu kinh điển!",
        ]
        for ch in cheers:
            def _insert_txt(t=ch):
                cur = self.chat_msg_var.get().strip()
                self.chat_msg_var.set((cur + " " + t).strip() if cur else t)
            menu.add_command(label=ch, command=_insert_txt)
        try:
            x = self.btn_emoji_chat.winfo_rootx() - 140
            y = self.btn_emoji_chat.winfo_rooty() - 165
            menu.tk_popup(x, y)
        finally:
            menu.grab_release()

    def _set_match_filter_mode(self, mode: str):
        self.match_filter_mode = mode
        for m_code, btn in getattr(self, "_match_filter_btns", {}).items():
            if m_code == mode:
                btn.configure(bg="#f59e0b", fg="#0b0e14", highlightthickness=0)
            else:
                btn.configure(bg="#1a2130", fg="#94a3b8", highlightthickness=1, highlightbackground="#262f40")
        if getattr(self, "_cached_social_data", None):
            self._update_friends_and_social_ui(self._cached_social_data)

    def _set_chat_filter_tab(self, tab_code: str):
        self.chat_filter_tab = tab_code
        for t_code, btn in getattr(self, "_chat_filter_btns", {}).items():
            if t_code == tab_code:
                btn.configure(bg="#f59e0b", fg="#0b0e14", highlightthickness=0)
            else:
                btn.configure(bg="#1a2130", fg="#94a3b8", highlightthickness=1, highlightbackground="#262f40")
        if getattr(self, "_cached_social_data", None):
            self._update_friends_and_social_ui(self._cached_social_data)

    def _make_safe_string_var(self, value: str = ""):
        tk = self.tk
        root_ref = self.root

        class _SafeStringVar(tk.StringVar):
            def __init__(self, master=None, val=""):
                super().__init__(master=master, value=val)
                self._cached_val = str(val or "")
                try:
                    self.trace_add("write", self._on_write)
                except Exception:
                    pass

            def _on_write(self, *_args):
                if threading.current_thread() is threading.main_thread():
                    try:
                        self._cached_val = str(super().get())
                    except Exception:
                        pass

            def get(self):
                if threading.current_thread() is threading.main_thread():
                    try:
                        self._cached_val = str(super().get())
                    except Exception:
                        pass
                return self._cached_val

            def set(self, val):
                s_val = str(val if val is not None else "")
                self._cached_val = s_val
                if threading.current_thread() is threading.main_thread():
                    super().set(s_val)
                else:
                    try:
                        root_ref.after(0, lambda v=s_val: super(_SafeStringVar, self).set(v))
                    except Exception:
                        pass

        return _SafeStringVar(master=self.root, val=value)

    def _make_safe_bool_var(self, value: bool = False):
        tk = self.tk
        root_ref = self.root

        class _SafeBooleanVar(tk.BooleanVar):
            def __init__(self, master=None, val=False):
                super().__init__(master=master, value=bool(val))
                self._cached_val = bool(val)
                try:
                    self.trace_add("write", self._on_write)
                except Exception:
                    pass

            def _on_write(self, *_args):
                if threading.current_thread() is threading.main_thread():
                    try:
                        self._cached_val = bool(super().get())
                    except Exception:
                        pass

            def get(self):
                if threading.current_thread() is threading.main_thread():
                    try:
                        self._cached_val = bool(super().get())
                    except Exception:
                        pass
                return self._cached_val

            def set(self, val):
                b_val = bool(val)
                self._cached_val = b_val
                if threading.current_thread() is threading.main_thread():
                    super().set(b_val)
                else:
                    try:
                        root_ref.after(0, lambda v=b_val: super(_SafeBooleanVar, self).set(v))
                    except Exception:
                        pass

        return _SafeBooleanVar(master=self.root, val=value)

    def _force_repaint_widget(self, widget=None):
        """Ép Windows GDI xóa nền cũ và vẽ lại toàn bộ khung con ngay lập tức để chống lưu bóng chữ cũ."""
        target = widget or getattr(self, "main_app_frame", None) or self.root
        try:
            target.update_idletasks()
            if os.name == "nt":
                import ctypes
                hwnd = int(target.winfo_id())
                # RDW_INVALIDATE (0x0001) | RDW_ERASE (0x0004) | RDW_ALLCHILDREN (0x0080) | RDW_UPDATENOW (0x0100)
                ctypes.windll.user32.RedrawWindow(hwnd, None, None, 0x0185)
        except Exception:
            pass

    def _build_ui(self):
        tk = self.tk
        self._refresh_state_lock = threading.Lock()

        # Khởi tạo toàn bộ biến điều khiển dùng chung (Thread-Safe) giữa Màn hình Đăng nhập, Bảng Điều Khiển và Tab Cài đặt VIP
        self.server_url_var = self._make_safe_string_var(self.settings.get("server_url", DEFAULT_SERVER_URL))
        self.player_name_var = self._make_safe_string_var(self.settings.get("player_name", "XO"))
        self.player_pass_var = self._make_safe_string_var(self.settings.get("player_password", "111"))
        self.auto_scan_var = self._make_safe_bool_var(bool(self.settings.get("auto_scan", True)))
        self.target_score_var = self._make_safe_string_var(str(self.settings.get("target_score", 100)))
        self.show_date_var = self._make_safe_bool_var(bool(self.settings.get("show_date_corner", True)))
        self.c_mode_var = self._make_safe_bool_var(bool(self.settings.get("c_mode_enabled", False)))
        self.show_idle_preview_var = self._make_safe_bool_var(bool(self.settings.get("show_idle_preview", True)))
        saved_mode_code = self.settings.get("marquee_mode", "ALL")
        self.marquee_label_var = self._make_safe_string_var(
            MARQUEE_MODE_TO_LABEL.get(saved_mode_code, MARQUEE_MODE_LABELS[0][1])
        )
        self.custom_marquee_var = self._make_safe_string_var(self.settings.get("custom_marquee_text", ""))
        self.obs_url_preview_var = self._make_safe_string_var()
        self.obs_chat_url_preview_var = self._make_safe_string_var()
        self.player_name_var.trace_add("write", lambda *_: self._update_obs_preview_entry())
        self._update_obs_preview_entry()

        self.active_tab = "BATTLE"
        self.log_drawer_open = True
        self.log_expanded = False
        self._last_auto_diag_log_ts = 0.0
        self._last_auto_diag_reason = ""

        # ======================================================================
        # 1. MÀN HÌNH ĐĂNG NHẬP RIÊNG KHI BẮT ĐẦU CHẠY TOOL (LOGIN SCREEN)
        #    (Tự co giãn theo DPI màn hình 1080p/2K/4K, viền khít khung bên trong)
        # ======================================================================
        self.login_screen_frame = tk.Frame(self.root, bg="#0b0e14")

        login_outer = tk.Frame(
            self.login_screen_frame,
            bg="#0f1520",
            highlightthickness=2,
            highlightbackground="#f59e0b",
            padx=4,
            pady=4,
        )
        login_outer.place(relx=0.5, rely=0.48, anchor="center")

        login_card = tk.Frame(
            login_outer,
            bg="#121721",
            highlightthickness=1,
            highlightbackground="#262f40",
            padx=22,
            pady=18,
        )
        login_card.pack(fill="both", expand=True)

        hdr_badge_row = tk.Frame(login_card, bg="#121721")
        hdr_badge_row.pack(fill="x", pady=(0, 8))

        emblem_top = tk.Frame(
            hdr_badge_row,
            bg="#1a2130",
            highlightthickness=1,
            highlightbackground="#f59e0b",
            padx=8,
            pady=4,
        )
        emblem_top.pack()
        self._create_brand_crest_canvas(emblem_top, size=48, bg_color="#1a2130").pack()

        tk.Label(
            login_card,
            text=APP_TITLE,
            font=("Segoe UI", 14, "bold"),
            fg="#f8fafc",
            bg="#121721",
            padx=8,
        ).pack()

        tk.Label(
            login_card,
            text=f"AOE Command Center ({APP_VERSION}) • Thương hiệu AOE BY XO",
            font=("Segoe UI", 9, "bold"),
            fg="#cbd5e1",
            bg="#121721",
            padx=6,
        ).pack(pady=(2, 6))

        self.login_ver_badge_btn = tk.Button(
            login_card,
            text=f"🏷️ Phiên bản hiện tại: v{APP_VERSION_NUMBER} (Bản mới nhất)",
            command=self.open_download_tool_url,
            font=("Segoe UI", 8, "bold"),
            bg="#1a2130",
            fg="#34d399",
            relief="flat",
            highlightthickness=1,
            highlightbackground="#262f40",
            padx=12,
            pady=3,
            cursor="hand2",
        )
        self.login_ver_badge_btn.pack(pady=(0, 10))

        # Khung bên trong ôm khít các trường tài khoản & mật khẩu
        login_inner_box = tk.Frame(
            login_card,
            bg="#131821",
            highlightthickness=1,
            highlightbackground="#262f40",
            padx=16,
            pady=14,
        )
        login_inner_box.pack(fill="x")

        # Ô nhập Tên Player / Streamer
        tk.Label(
            login_inner_box,
            text="👤 Tên tài khoản Player / Streamer",
            font=("Segoe UI", 9, "bold"),
            fg="#e7ebf0",
            bg="#131821",
        ).pack(anchor="w")
        login_user_entry = tk.Entry(
            login_inner_box,
            textvariable=self.player_name_var,
            font=("Segoe UI", 11, "bold"),
            width=34,
            bg="#0b0f17",
            fg="#e7ebf0",
            insertbackground="#f59e0b",
            relief="flat",
            highlightthickness=1,
            highlightbackground="#384659",
            highlightcolor="#f59e0b",
        )
        login_user_entry.pack(fill="x", ipady=5, pady=(3, 10))
        login_user_entry.bind("<Return>", lambda _e: self.login_and_start())

        # Ô nhập Mật khẩu
        tk.Label(
            login_inner_box,
            text="🔑 Mật khẩu",
            font=("Segoe UI", 9, "bold"),
            fg="#e7ebf0",
            bg="#131821",
        ).pack(anchor="w")
        login_pass_entry = tk.Entry(
            login_inner_box,
            textvariable=self.player_pass_var,
            show="*",
            font=("Consolas", 11, "bold"),
            width=34,
            bg="#0b0f17",
            fg="#e7ebf0",
            insertbackground="#f59e0b",
            relief="flat",
            highlightthickness=1,
            highlightbackground="#384659",
            highlightcolor="#f59e0b",
        )
        login_pass_entry.pack(fill="x", ipady=5, pady=(3, 8))
        login_pass_entry.bind("<Return>", lambda _e: self.login_and_start())

        # Tùy chọn nâng cao: Ẩn/Hiện Server URL để không làm rối màn hình đăng nhập
        srv_toggle_row = tk.Frame(login_inner_box, bg="#131821")
        srv_toggle_row.pack(fill="x", pady=(0, 4))

        srv_drawer = tk.Frame(login_inner_box, bg="#131821")
        self._srv_drawer_visible = False

        def _toggle_srv_drawer():
            self._srv_drawer_visible = not self._srv_drawer_visible
            if self._srv_drawer_visible:
                srv_drawer.pack(fill="x", pady=(0, 8), before=self.login_btn)
                btn_toggle_srv.config(text="▲ Ẩn cài đặt máy chủ (Server URL)")
            else:
                srv_drawer.pack_forget()
                btn_toggle_srv.config(text="⚙ Đổi địa chỉ máy chủ (Server URL)")

        btn_toggle_srv = tk.Button(
            srv_toggle_row,
            text="⚙ Đổi địa chỉ máy chủ (Server URL)",
            command=_toggle_srv_drawer,
            font=("Segoe UI", 8, "bold"),
            bg="#131821",
            fg="#8e99a7",
            activebackground="#131821",
            activeforeground="#f59e0b",
            relief="flat",
            bd=0,
            cursor="hand2",
        )
        btn_toggle_srv.pack(side="right")

        tk.Label(
            srv_drawer,
            text="Địa chỉ máy chủ (Server URL)",
            font=("Segoe UI", 8, "bold"),
            fg="#8e99a7",
            bg="#131821",
        ).pack(anchor="w")
        tk.Entry(
            srv_drawer,
            textvariable=self.server_url_var,
            font=("Consolas", 9),
            width=34,
            bg="#0b0f17",
            fg="#e7ebf0",
            insertbackground="#f59e0b",
            relief="flat",
            highlightthickness=1,
            highlightbackground="#384659",
            highlightcolor="#f59e0b",
        ).pack(fill="x", ipady=4, pady=(3, 0))

        self.login_btn = tk.Button(
            login_inner_box,
            text="⚡ Đăng Nhập Vào Bảng Điều Khiển",
            command=self.login_and_start,
            font=("Segoe UI", 10, "bold"),
            bg="#f59e0b",
            fg="#0b0e14",
            activebackground="#d97706",
            activeforeground="#0b0e14",
            relief="flat",
            pady=7,
            cursor="hand2",
        )
        self.login_btn.pack(fill="x", pady=(6, 2))
        self._bind_hover(self.login_btn, "#f59e0b", "#d97706", "#0b0e14", "#0b0e14")

        self.register_btn = tk.Button(
            login_inner_box,
            text="✨ Tạo Tài Khoản XO Mới (Dùng thử 7 ngày + Chơi 5 Mini Games)",
            command=self.open_register_account_dialog,
            font=("Segoe UI", 8, "bold"),
            bg="#1a2130",
            fg="#fbbf24",
            activebackground="#243047",
            activeforeground="#ffffff",
            relief="flat",
            highlightthickness=1,
            highlightbackground="#384659",
            pady=5,
            cursor="hand2",
        )
        self.register_btn.pack(fill="x", pady=(4, 0))
        self._bind_hover(self.register_btn, "#1a2130", "#243047", "#fbbf24", "#ffffff")

        self.login_status_lbl = tk.Label(
            login_card,
            text="Nhập tài khoản Player (hoặc Admin XO) để bắt đầu sử dụng Tool.",
            font=("Segoe UI", 8, "bold"),
            fg="#8e99a7",
            bg="#121721",
            justify="center",
        )
        self.login_status_lbl.pack(pady=(8, 0))

        # ======================================================================
        # 2. MÀN HÌNH CHÍNH SAU KHI ĐĂNG NHẬP:
        #    MODERN ESPORTS DASHBOARD – DARK PREMIUM – GOLD ACCENT (4 KHU VỰC A / B / C / D)
        # ======================================================================
        self.log_drawer_open = False
        self.match_search_var = self._make_safe_string_var()
        self.match_filter_mode = "ALL"
        self._match_filter_btns = {}
        self.chat_search_var = self._make_safe_string_var()
        self.chat_filter_tab = "ALL"
        self._chat_filter_btns = {}
        self.chat_antispam_var = self._make_safe_bool_var(True)
        self._cached_social_data = {}

        self.match_search_var.trace_add(
            "write",
            lambda *_: self._update_friends_and_social_ui(self._cached_social_data) if self._cached_social_data else None,
        )
        self.chat_search_var.trace_add(
            "write",
            lambda *_: self._update_friends_and_social_ui(self._cached_social_data) if self._cached_social_data else None,
        )

        # Phím tắt thao tác nhanh (Hoạt động cả trên cửa sổ Tool lẫn Global Hotkey khi đang trong màn hình Game AOE)
        self._last_global_score_hotkey_ts = 0.0
        self._last_global_hype_hotkey_ts = 0.0
        self.root.bind("<F3>", lambda _e: self.test_from_image_file() if self.is_logged_in else None)
        self.root.bind("<F5>", lambda _e: self._trigger_global_winner_hotkey("RED", "F5") if self.is_logged_in else None)
        self.root.bind("<F6>", lambda _e: self._trigger_global_winner_hotkey("BLUE", "F6") if self.is_logged_in else None)
        self.root.bind("<F7>", lambda _e: self.finish_current_match() if self.is_logged_in else None)
        self.root.bind("<F8>", lambda _e: self._trigger_global_hype_hotkey("F8") if self.is_logged_in else None)

        self.main_app_frame = tk.Frame(self.root, bg="#0b0e14")

        # ======================================================================
        # DESIGN TOKENS – WOOD-GOLD ESPORTS DARK THEME (PROFESSIONAL ESPORTS COMMAND CENTER)
        # ======================================================================
        C_APP, C_PANEL, C_ELEV, C_BORDER = "#070b12", "#0e1524", "#141f33", "#1e2d47"
        C_GOLD, C_GOLD_H, C_ON_GOLD = "#f59e0b", "#d97706", "#070b12"
        C_TXT, C_MUTED = "#f1f5f9", "#94a3b8"
        C_RED_SURF, C_RED, C_RED_H = "#261016", "#dc2626", "#ef4444"
        C_BLUE_SURF, C_BLUE, C_BLUE_H = "#0e1b30", "#2563eb", "#3b82f6"
        C_OK = "#10b981"

        # Áp dụng chế độ HUD Translucent Glass (Bán trong suốt 96% trên Windows) nếu được bật
        self._hud_translucent_enabled = bool(self.settings.get("hud_translucent", True))
        try:
            self.root.attributes("-alpha", 0.96 if self._hud_translucent_enabled else 1.0)
        except Exception:
            pass

        def _mk_panel(parent, padx=12, pady=10, bg=C_PANEL, border=C_BORDER):
            return tk.Frame(parent, bg=bg, highlightthickness=1, highlightbackground=border, padx=padx, pady=pady)

        def _mk_btn(
            parent,
            text,
            command,
            fg="#cbd5e1",
            bg=C_ELEV,
            hover_bg="#243047",
            hover_fg="#ffffff",
            border=C_BORDER,
            font=("Segoe UI", 9, "bold"),
            padx=10,
            pady=3,
        ):
            btn = tk.Button(
                parent,
                text=text,
                command=command,
                font=font,
                bg=bg,
                fg=fg,
                activebackground=hover_bg,
                activeforeground=hover_fg,
                relief="flat",
                highlightthickness=1 if border else 0,
                highlightbackground=border or bg,
                padx=padx,
                pady=pady,
                cursor="hand2",
            )
            self._bind_hover(btn, bg, hover_bg, fg, hover_fg)
            return btn

        def _mk_section_title(parent, text, fg=C_TXT, bg=C_PANEL, size=9):
            return tk.Label(parent, text=text, font=("Segoe UI", size, "bold"), fg=fg, bg=bg, anchor="w")

        # ----------------------------------------------------------------------
        # KHU VỰC A – UNIFIED TOP HEADER BAR (~56px): Logo + Tab điều hướng (Trái) | Trạng thái hệ thống + Tài khoản (Phải)
        # ----------------------------------------------------------------------
        hdr_outer = tk.Frame(
            self.main_app_frame,
            bg=C_PANEL,
            highlightthickness=1,
            highlightbackground=C_BORDER,
            padx=12,
            pady=4,
        )
        hdr_outer.pack(fill="x", padx=10, pady=(8, 6))
        self.header_bar = hdr_outer

        left_hdr = tk.Frame(hdr_outer, bg=C_PANEL)
        left_hdr.pack(side="left", anchor="w")

        emblem_box = tk.Frame(
            left_hdr,
            bg="#0e121a",
            highlightthickness=1,
            highlightbackground=C_GOLD,
            padx=3,
            pady=2,
        )
        emblem_box.pack(side="left", padx=(0, 10))
        self._create_brand_crest_canvas(emblem_box, size=36, bg_color="#0e121a").pack()

        title_stack = tk.Frame(left_hdr, bg=C_PANEL)
        title_stack.pack(side="left")

        tk.Label(
            title_stack,
            text="AOE COMMAND CENTER",
            font=("Segoe UI", 12, "bold"),
            fg=C_GOLD,
            bg=C_PANEL,
        ).pack(anchor="w")

        tk.Label(
            title_stack,
            text=f"{APP_VERSION}",
            font=("Segoe UI", 8, "bold"),
            fg=C_MUTED,
            bg=C_PANEL,
        ).pack(anchor="w")

        # Vạch ngăn cách giữa Logo và cụm Tab chuyển trang
        tk.Frame(left_hdr, bg=C_BORDER, width=1, height=30).pack(side="left", padx=(16, 10), pady=4)

        nav_left_tabs = tk.Frame(left_hdr, bg=C_PANEL)
        nav_left_tabs.pack(side="left", fill="y")

        def _mk_tab(text, command, active=False):
            wrap = tk.Frame(nav_left_tabs, bg=C_PANEL)
            wrap.pack(side="left", padx=(0, 4), fill="y")
            btn = tk.Button(
                wrap,
                text=text,
                command=command,
                font=("Segoe UI", 9, "bold"),
                bg=C_PANEL,
                fg="#fbbf24" if active else C_MUTED,
                activebackground="#1a202c",
                activeforeground="#fbbf24" if active else "#ffffff",
                relief="flat",
                bd=0,
                padx=11,
                pady=9,
                cursor="hand2",
            )
            btn.pack(fill="x")
            underline = tk.Frame(wrap, bg=C_GOLD if active else C_PANEL, height=3)
            underline.pack(fill="x", side="bottom")
            return btn, underline

        # Tab 1: Bảng điều khiển | Tab 2: Cài đặt VIP | Tab 3: Giải Trí Chờ Kèo (5 Game) | Tab 4: Tài khoản
        self.tab_battle_btn, self.tab_battle_underline = _mk_tab(
            "⊞ Bảng điều khiển", lambda: self.switch_main_tab("BATTLE"), active=True
        )
        self.tab_settings_btn, self.tab_settings_underline = _mk_tab(
            "⚙️ Cài đặt VIP", lambda: self.switch_main_tab("SETTINGS")
        )
        self.tab_minigames_btn, self.tab_minigames_underline = _mk_tab(
            "🎮 Giải Trí Chờ Kèo", lambda: self.switch_main_tab("MINIGAMES")
        )
        self.my_profile_btn, _profile_underline = _mk_tab("👤 Tài khoản", self.open_my_profile_window)

        # Cụm phải Header: HUD Glass Toggle, Quỹ Sao, Hạng VIP, Menu Quản trị & Đăng xuất
        right_hdr = tk.Frame(hdr_outer, bg=C_PANEL)
        right_hdr.pack(side="right", anchor="e")

        def _toggle_hud_glass():
            self._hud_translucent_enabled = not getattr(self, "_hud_translucent_enabled", True)
            self.settings["hud_translucent"] = self._hud_translucent_enabled
            try:
                self._save_local_settings()
            except Exception:
                pass
            try:
                self.root.attributes("-alpha", 0.96 if self._hud_translucent_enabled else 1.0)
            except Exception:
                pass
            if hasattr(self, "hud_glass_btn"):
                self.hud_glass_btn.config(
                    text="✨ HUD Kính mờ: BẬT" if self._hud_translucent_enabled else "🔳 HUD Kính mờ: TẮT",
                    fg="#38bdf8" if self._hud_translucent_enabled else "#94a3b8",
                    bg="#0c1d33" if self._hud_translucent_enabled else "#141f33",
                    highlightbackground="#38bdf8" if self._hud_translucent_enabled else C_BORDER,
                )

        self.hud_glass_btn = tk.Button(
            right_hdr,
            text="✨ HUD Kính mờ: BẬT" if self._hud_translucent_enabled else "🔳 HUD Kính mờ: TẮT",
            command=_toggle_hud_glass,
            font=("Segoe UI", 8, "bold"),
            fg="#38bdf8" if self._hud_translucent_enabled else "#94a3b8",
            bg="#0c1d33" if self._hud_translucent_enabled else "#141f33",
            activebackground="#162b47",
            activeforeground="#f8fafc",
            relief="flat",
            padx=8,
            pady=3,
            highlightthickness=1,
            highlightbackground="#38bdf8" if self._hud_translucent_enabled else C_BORDER,
            cursor="hand2",
        )
        self.hud_glass_btn.pack(side="left", padx=(0, 6))

        self.my_stars_badge_lbl = tk.Label(
            right_hdr,
            text="👑 Quỹ Sao: 0 ⭐",
            font=("Segoe UI", 9, "bold"),
            fg="#fbbf24",
            bg="#231a0e",
            padx=10,
            pady=4,
            highlightthickness=1,
            highlightbackground="#d4af37",
            cursor="hand2",
        )
        self.my_stars_badge_lbl.pack(side="left", padx=(0, 6))
        self.my_stars_badge_lbl.bind("<Button-1>", lambda _e: self.open_my_profile_window())

        self.tier_badge_lbl = tk.Label(
            right_hdr,
            text="💎 Hạng Kim Cương",
            font=("Segoe UI", 9, "bold"),
            fg="#fde68a",
            bg="#1c1a12",
            padx=10,
            pady=4,
            highlightthickness=1,
            highlightbackground="#d4af37",
            cursor="hand2",
        )
        self.tier_badge_lbl.pack(side="left", padx=(0, 6))
        self.tier_badge_lbl.bind("<Button-1>", lambda _e: self.open_my_profile_window())

        self.admin_mgr_btn = _mk_btn(
            right_hdr,
            "🛡️ Quản trị ▾",
            self._show_admin_management_menu,
            fg="#fbbf24",
            bg="#241b0f",
            hover_bg="#362712",
            border="#b45309",
            pady=4,
        )
        self.admin_mgr_btn.pack(side="left", padx=(0, 6))

        self.logout_btn = _mk_btn(
            right_hdr,
            "🚪 Đăng xuất",
            self.logout_to_login_screen,
            fg="#fecaca",
            bg="#3a1418",
            hover_bg="#7f1d1d",
            hover_fg="#ffffff",
            border="#7f1d1d",
            pady=4,
        )
        self.logout_btn.pack(side="left")

        # Cụm trạng thái hệ thống (tự giãn theo nội dung, xếp 2 dòng gọn gàng để không bao giờ bị cắt chữ "XO ĐÃ KẾT NỐI")
        center_hdr = tk.Frame(hdr_outer, bg=C_PANEL)
        center_hdr.pack(side="right", fill="x", expand=True, padx=(10, 14))

        status_row1 = tk.Frame(center_hdr, bg=C_PANEL)
        status_row1.pack(anchor="e")

        self.pulse_dot = tk.Label(
            status_row1,
            text="🟢 Đã kết nối •",
            font=("Segoe UI", 8, "bold"),
            fg="#34d399",
            bg="#0e261e",
            padx=8,
            pady=1,
            highlightthickness=1,
            highlightbackground="#14532d",
        )
        self.pulse_dot.pack(side="left", padx=(0, 8))

        self.date_corner_lbl = tk.Label(
            status_row1,
            text="🕒 --:--:-- - --/--/----",
            font=("Consolas", 9, "bold"),
            fg="#cbd5e1",
            bg=C_PANEL,
        )
        self.date_corner_lbl.pack(side="left")

        self.status_lbl = self._make_ellipsis_label(
            center_hdr,
            text="",
            font=("Segoe UI", 8, "bold"),
            fg="#64748b",
            bg=C_PANEL,
            anchor="e",
        )
        self.status_lbl.pack(fill="x", anchor="e", pady=(2, 0))

        # Co giãn Header: màn hình hẹp (1366x768) tự ẩn đồng hồ để ưu tiên trạng thái kết nối & các nút tài khoản
        self._hdr_clock_hidden = False

        def _on_header_resize(e):
            try:
                narrow = int(e.width) < 1440
                if narrow and not self._hdr_clock_hidden:
                    self.date_corner_lbl.pack_forget()
                    self._hdr_clock_hidden = True
                    for t_btn in (self.tab_battle_btn, self.tab_settings_btn, self.tab_minigames_btn, self.my_profile_btn):
                        t_btn.configure(padx=6)
                elif not narrow and self._hdr_clock_hidden:
                    self.date_corner_lbl.pack(side="left")
                    self._hdr_clock_hidden = False
                    for t_btn in (self.tab_battle_btn, self.tab_settings_btn, self.tab_minigames_btn, self.my_profile_btn):
                        t_btn.configure(padx=11)
            except Exception:
                pass

        hdr_outer.bind("<Configure>", _on_header_resize, add="+")

        # ======================================================================
        # KHU VỰC E – THANH TRẠNG THÁI DƯỚI CÙNG (BOTTOM STATUS BAR ~28px)
        # ======================================================================
        self.status_log_bar = tk.Frame(
            self.main_app_frame,
            bg=C_PANEL,
            highlightthickness=1,
            highlightbackground=C_BORDER,
            padx=10,
            pady=3,
        )
        self.status_log_bar.pack(fill="x", side="bottom", padx=10, pady=(4, 8))

        tk.Label(
            self.status_log_bar,
            text=f"Phiên bản {APP_VERSION_NUMBER}",
            font=("Segoe UI", 8, "bold"),
            fg=C_MUTED,
            bg=C_PANEL,
        ).pack(side="left", padx=(0, 6))

        self.header_ver_badge_btn = tk.Button(
            self.status_log_bar,
            text=f"🏷️ Ver {APP_VERSION_NUMBER}",
            command=self.open_download_tool_url,
            font=("Segoe UI", 8, "bold"),
            fg="#34d399",
            bg=C_ELEV,
            activebackground="#243047",
            activeforeground="#34d399",
            relief="flat",
            padx=8,
            pady=0,
            highlightthickness=1,
            highlightbackground=C_BORDER,
            cursor="hand2",
        )
        self.header_ver_badge_btn.pack(side="left", padx=(0, 14))

        tk.Label(
            self.status_log_bar,
            text="Thao tác:  Ấn Diplomacy đọc quân  |  F3 Test ảnh  |  F5 Thắng Đỏ  |  F6 Thắng Xanh  |  F7 Kết thúc  |  F8 Tay đâu!",
            font=("Segoe UI", 8, "bold"),
            fg="#cbd5e1",
            bg=C_PANEL,
        ).pack(side="left", padx=(0, 14))

        self.latest_log_lbl = tk.Label(
            self.status_log_bar,
            text="",
            font=("Consolas", 8),
            fg="#64748b",
            bg=C_PANEL,
            anchor="w",
            width=1,
        )
        self.latest_log_lbl.pack(side="left", fill="x", expand=True)
        self._latest_log_full_text = ""
        self._attach_tooltip(self.latest_log_lbl, lambda: getattr(self, "_latest_log_full_text", ""))

        def _refit_latest_log(_e=None):
            try:
                full_txt = getattr(self, "_latest_log_full_text", "")
                avail_px = int(self.latest_log_lbl.winfo_width() or 0) - 8
                if full_txt and avail_px > 40:
                    self.latest_log_lbl.configure(text=self._ellipsize_text(full_txt, ("Consolas", 8), avail_px))
            except Exception:
                pass

        self.latest_log_lbl.bind("<Configure>", _refit_latest_log, add="+")

        # ======================================================================
        # VÙNG CHỨA CÁC TAB CHÍNH (TAB 1: BẢNG ĐIỀU KHIỂN | TAB 2: CÀI ĐẶT VIP)
        # ======================================================================
        self.tab_container = tk.Frame(self.main_app_frame, bg=C_APP)
        self.tab_container.pack(fill="both", expand=True)

        self.battle_tab_frame = tk.Frame(self.tab_container, bg=C_APP)
        self.settings_tab_frame = tk.Frame(self.tab_container, bg=C_APP)
        self.minigames_tab_frame = tk.Frame(self.tab_container, bg=C_APP)

        # ======================================================================
        # BỐ CỤC 3 CỘT MODULAR GRID (23% TIỆN ÍCH & SẢNH | 47% ĐIỀU KHIỂN TRẬN ĐẤU & LOG | 30% SẢNH CHAT LIVE)
        # ======================================================================
        workspace_split = tk.Frame(self.battle_tab_frame, bg=C_APP)
        workspace_split.pack(fill="both", expand=True, padx=10, pady=0)
        workspace_split.columnconfigure(0, weight=23, uniform="ws_col")
        workspace_split.columnconfigure(1, weight=47, uniform="ws_col")
        workspace_split.columnconfigure(2, weight=30, uniform="ws_col")
        workspace_split.rowconfigure(0, weight=1)
        self.workspace_split = workspace_split

        self.lobby_workspace_col = tk.Frame(workspace_split, bg=C_APP)
        self.lobby_workspace_col.grid(row=0, column=0, sticky="nsew", padx=(0, 5))

        self.center_workspace_col = tk.Frame(workspace_split, bg=C_APP)
        self.center_workspace_col.grid(row=0, column=1, sticky="nsew", padx=5)
        # Giữ tương thích tên biến cũ: vùng chứa Bảng Tỷ Số (dùng cho ép vẽ lại GDI)
        self.left_workspace_col = self.center_workspace_col

        self.right_workspace_col = tk.Frame(workspace_split, bg=C_APP)
        self.right_workspace_col.grid(row=0, column=2, sticky="nsew", padx=(5, 0))

        # ----------------------------------------------------------------------
        # CỘT TRÁI – PANEL 1: TIỆN ÍCH OBS & LIÊN KẾT NHANH (QUICK LINKS GRID 2x3)
        # ----------------------------------------------------------------------
        quick_links_card = _mk_panel(self.lobby_workspace_col, padx=10, pady=8)
        quick_links_card.pack(fill="x", side="top", pady=(0, 6))
        _mk_section_title(quick_links_card, "🧰  TIỆN ÍCH OBS & LIÊN KẾT NHANH").pack(fill="x", pady=(0, 6))

        quick_grid = tk.Frame(quick_links_card, bg=C_PANEL)
        quick_grid.pack(fill="x")
        quick_grid.columnconfigure(0, weight=1, uniform="ql_col")
        quick_grid.columnconfigure(1, weight=1, uniform="ql_col")

        for q_idx, (lbl_txt, cmd_fn) in enumerate(
            [
                ("🖥️ Link OBS", self.copy_obs_link),
                ("💬 OBS Chat", self.copy_obs_chat_link),
                ("🔗 Link OBS Bảng Quân", self.copy_obs_link),
                ("🔵 FB Group Live", self.show_fb_group_live_bridge_window),
                ("📖 Hướng dẫn", self.show_obs_guide_window),
                ("🌐 Mở Web", self.open_web_dashboard),
            ]
        ):
            is_gold = lbl_txt == "🔗 Link OBS Bảng Quân"
            b_tool = _mk_btn(
                quick_grid,
                lbl_txt,
                cmd_fn,
                fg="#fbbf24" if is_gold else "#cbd5e1",
                hover_fg="#fde047" if is_gold else "#fbbf24",
                font=("Segoe UI", 8, "bold"),
                padx=6,
                pady=4,
            )
            b_tool.grid(row=q_idx // 2, column=q_idx % 2, sticky="ew", padx=2, pady=2)
            if lbl_txt == "🌐 Mở Web":
                self.open_web_btn = b_tool

        # ----------------------------------------------------------------------
        # CỘT TRÁI – PANEL 3: QUẢN LÝ BẠN BÈ (Neo ở nửa dưới cột trái)
        # ----------------------------------------------------------------------
        friends_card = _mk_panel(self.lobby_workspace_col, padx=10, pady=8)
        friends_card.pack(fill="x", side="bottom", pady=(6, 0))
        self.friends_card = friends_card

        _mk_section_title(friends_card, "👥  QUẢN LÝ BẠN BÈ").pack(fill="x", pady=(0, 6))

        friend_add_box = tk.Frame(friends_card, bg=C_PANEL)
        friend_add_box.pack(fill="x", pady=(0, 6))

        self.friend_target_var = self._make_safe_string_var()

        btn_unfriend = _mk_btn(
            friend_add_box,
            "🔄 Hủy",
            self.toggle_friend_action,
            fg=C_MUTED,
            font=("Segoe UI", 8, "bold"),
            padx=8,
            pady=2,
        )
        btn_unfriend.pack(side="right")

        btn_add_friend = _mk_btn(
            friend_add_box,
            "+ Kết bạn",
            self.toggle_friend_action,
            fg=C_ON_GOLD,
            bg=C_GOLD,
            hover_bg=C_GOLD_H,
            hover_fg=C_ON_GOLD,
            border=None,
            font=("Segoe UI", 8, "bold"),
            padx=8,
            pady=2,
        )
        btn_add_friend.pack(side="right", padx=(0, 4))

        tk.Entry(
            friend_add_box,
            textvariable=self.friend_target_var,
            font=("Segoe UI", 9),
            bg=C_ELEV,
            fg="#e7ebf0",
            insertbackground=C_GOLD,
            width=6,
            relief="flat",
            highlightthickness=1,
            highlightbackground=C_BORDER,
            highlightcolor=C_GOLD,
        ).pack(side="left", fill="x", expand=True, padx=(0, 6), ipady=3)

        # Thanh trạng thái Online của bạn bè
        self.friends_status_lbl = tk.Label(
            friends_card,
            text="👥 Bạn bè: 0 online  •  Kết nối tài khoản để theo dõi bạn bè đang LIVE",
            font=("Segoe UI", 8, "bold"),
            fg=C_MUTED,
            bg=C_ELEV,
            justify="left",
            anchor="w",
            padx=8,
            pady=5,
            wraplength=300,
        )
        self.friends_status_lbl.pack(fill="x")
        self._auto_wrap_label(self.friends_status_lbl, pad=18)

        self.friends_live_btn_frame = tk.Frame(friends_card, bg=C_PANEL)

        # ----------------------------------------------------------------------
        # CỘT TRÁI – PANEL 2: SẢNH CÁC TRẬN ĐẤU LIVE (TÌM KIẾM + LỌC + DANH SÁCH CARD)
        # ----------------------------------------------------------------------
        live_lobby_card = _mk_panel(self.lobby_workspace_col, padx=10, pady=8)
        live_lobby_card.pack(fill="both", expand=True, side="top")
        self.live_lobby_card = live_lobby_card

        _mk_section_title(live_lobby_card, "🏆  SẢNH CÁC TRẬN ĐẤU LIVE & BẠN BÈ").pack(fill="x", pady=(0, 6))

        match_search_row = tk.Frame(live_lobby_card, bg=C_PANEL)
        match_search_row.pack(fill="x", side="top", pady=(0, 6))

        tk.Label(
            match_search_row,
            text="🔍",
            font=("Segoe UI", 8),
            fg=C_MUTED,
            bg=C_ELEV,
            padx=6,
            pady=2,
        ).pack(side="left")

        tk.Entry(
            match_search_row,
            textvariable=self.match_search_var,
            font=("Segoe UI", 9),
            bg=C_ELEV,
            fg=C_TXT,
            insertbackground=C_GOLD,
            width=6,
            relief="flat",
            highlightthickness=1,
            highlightbackground=C_BORDER,
            highlightcolor=C_GOLD,
        ).pack(side="left", fill="x", expand=True, ipady=3)

        match_filter_bar = tk.Frame(live_lobby_card, bg=C_PANEL)
        match_filter_bar.pack(fill="x", side="top", pady=(0, 6))
        for f_idx in range(3):
            match_filter_bar.columnconfigure(f_idx, weight=1, uniform="mf_col")

        for f_idx, (m_code, m_lbl) in enumerate([("ALL", "Tất cả"), ("LIVE", "Đang LIVE"), ("FINISHED", "Đã kết thúc")]):
            is_act = m_code == "ALL"
            b_mf = tk.Button(
                match_filter_bar,
                text=m_lbl,
                command=lambda c=m_code: self._set_match_filter_mode(c),
                font=("Segoe UI", 8, "bold"),
                bg=C_GOLD if is_act else C_ELEV,
                fg=C_ON_GOLD if is_act else C_MUTED,
                relief="flat",
                highlightthickness=0 if is_act else 1,
                highlightbackground=C_BORDER,
                padx=6,
                pady=2,
                cursor="hand2",
            )
            b_mf.grid(row=0, column=f_idx, sticky="ew", padx=2)
            self._match_filter_btns[m_code] = b_mf

        # Danh sách Bảng Trận Đấu HUD Sci-Fi (Cuộn dọc bằng Dark Scrollbar khi nhiều trận / màn hình thấp 1366x768)
        lobby_list_outer = tk.Frame(
            live_lobby_card,
            bg="#0b111e",
            highlightthickness=1,
            highlightbackground=C_BORDER,
        )
        lobby_list_outer.pack(fill="both", expand=True)

        # Thanh tiêu đề cột dạng Bảng (HUD Sci-Fi Table Header)
        lobby_tbl_hdr = tk.Frame(lobby_list_outer, bg="#080d18", padx=8, pady=3)
        lobby_tbl_hdr.pack(fill="x", side="top")
        tk.Label(
            lobby_tbl_hdr,
            text="TRẠNG THÁI • SẢNH MÁY & ĐỘI HÌNH",
            font=("Segoe UI", 7, "bold"),
            fg="#38bdf8",
            bg="#080d18",
            anchor="w",
        ).pack(side="left")
        tk.Label(
            lobby_tbl_hdr,
            text="TỈ SỐ • THAO TÁC",
            font=("Segoe UI", 7, "bold"),
            fg="#facc15",
            bg="#080d18",
            anchor="e",
        ).pack(side="right")
        tk.Frame(lobby_list_outer, bg="#1e2d47", height=1).pack(fill="x", side="top")

        lobby_list_scroll = self._make_dark_scrollbar(lobby_list_outer, "vertical")
        lobby_list_scroll.pack(side="right", fill="y")

        lobby_list_canvas = tk.Canvas(
            lobby_list_outer,
            bg=C_ELEV,
            highlightthickness=0,
            bd=0,
            yscrollcommand=lobby_list_scroll.set,
        )
        lobby_list_canvas.pack(side="left", fill="both", expand=True)
        lobby_list_scroll.configure(command=lobby_list_canvas.yview)

        self.live_matches_list_frame = tk.Frame(lobby_list_canvas, bg=C_ELEV, padx=6, pady=6)
        lobby_list_win = lobby_list_canvas.create_window((0, 0), window=self.live_matches_list_frame, anchor="nw")

        self.live_matches_list_frame.bind(
            "<Configure>",
            lambda _e: lobby_list_canvas.configure(scrollregion=lobby_list_canvas.bbox("all")),
        )
        lobby_list_canvas.bind(
            "<Configure>",
            lambda e: lobby_list_canvas.itemconfigure(lobby_list_win, width=e.width),
        )

        def _lobby_wheel(e):
            try:
                if lobby_list_canvas.bbox("all") and lobby_list_canvas.bbox("all")[3] > lobby_list_canvas.winfo_height():
                    lobby_list_canvas.yview_scroll(int(-e.delta / 120), "units")
            except Exception:
                pass

        lobby_list_outer.bind("<Enter>", lambda _e: lobby_list_canvas.bind_all("<MouseWheel>", _lobby_wheel))
        lobby_list_outer.bind("<Leave>", lambda _e: lobby_list_canvas.unbind_all("<MouseWheel>"))

        tk.Label(
            self.live_matches_list_frame,
            text="Đang tải danh sách các trận đấu trên hệ thống...",
            font=("Segoe UI", 8, "bold"),
            fg=C_MUTED,
            bg=C_ELEV,
        ).pack(anchor="w")

        # ----------------------------------------------------------------------
        # CỘT GIỮA – THANH ĐIỀU KHIỂN ĐỌC BẢNG QUÂN (SCANNER ACTION BAR)
        # ----------------------------------------------------------------------
        quick_bar = _mk_panel(self.center_workspace_col, padx=10, pady=6)
        quick_bar.pack(fill="x", side="top", pady=(0, 6))

        tk.Checkbutton(
            quick_bar,
            text="Tự động quét Diplomacy",
            variable=self.auto_scan_var,
            command=self.save_current_config,
            font=("Segoe UI", 9, "bold"),
            fg=C_TXT,
            bg=C_PANEL,
            selectcolor=C_APP,
            activebackground=C_PANEL,
            activeforeground=C_GOLD,
            cursor="hand2",
        ).pack(side="left", padx=(0, 10))

        self.btn_scan_now = _mk_btn(
            quick_bar,
            "🔍 Quét Diplomacy ngay",
            self.manual_scan_screen,
            fg=C_ON_GOLD,
            bg=C_GOLD,
            hover_bg=C_GOLD_H,
            hover_fg=C_ON_GOLD,
            border=None,
            padx=14,
            pady=4,
        )
        self.btn_scan_now.pack(side="left", padx=(0, 8))

        self.btn_test_img = _mk_btn(
            quick_bar,
            "🖼️ Test ảnh",
            self.test_from_image_file,
            padx=11,
            pady=4,
        )
        self.btn_test_img.pack(side="left", padx=(0, 8))

        self.btn_hype_f8 = _mk_btn(
            quick_bar,
            "🙌 Tay đâu! [F8]",
            lambda: self._trigger_global_hype_hotkey("Nút F8"),
            fg="#fbbf24",
            bg="#2b1911",
            hover_bg="#452310",
            border="#d97706",
            padx=11,
            pady=4,
        )
        self.btn_hype_f8.pack(side="left")

        # ----------------------------------------------------------------------
        # CỘT GIỮA – HERO PANEL: TRẬN ĐẤU ĐANG DIỄN RA (TÂM ĐIỂM THỊ GIÁC)
        # ----------------------------------------------------------------------
        battle_card = _mk_panel(self.center_workspace_col, padx=12, pady=8)
        battle_card.pack(fill="x", side="top", pady=(0, 6))
        self.battle_card = battle_card

        # Header Hero Panel: TRẬN ĐẤU ĐANG DIỄN RA + LIVE (Trái) | Hoàn tác (-1) + Kết thúc kèo [F7] (Phải, cách xa nút cộng điểm)
        sb_top_bar = tk.Frame(battle_card, bg=C_PANEL)
        sb_top_bar.pack(fill="x", pady=(0, 8))

        self.scoreboard_hdr_lbl = tk.Label(
            sb_top_bar,
            text="◉  TRẬN ĐẤU ĐANG DIỄN RA",
            font=("Segoe UI", 10, "bold"),
            fg=C_TXT,
            bg=C_PANEL,
        )
        self.scoreboard_hdr_lbl.pack(side="left")

        self.scoreboard_live_badge = tk.Label(
            sb_top_bar,
            text="LIVE",
            font=("Segoe UI", 8, "bold"),
            fg="#34d399",
            bg="#0d2e22",
            padx=8,
            pady=1,
            highlightthickness=1,
            highlightbackground="#166534",
        )
        self.scoreboard_live_badge.pack(side="left", padx=(10, 0))

        self.btn_end_match = _mk_btn(
            sb_top_bar,
            "🗑️ Kết thúc kèo [F7]",
            self.finish_current_match,
            fg="#fca5a5",
            bg="#2a1215",
            hover_bg="#4c1d24",
            hover_fg="#fee2e2",
            border="#7f1d1d",
            font=("Segoe UI", 8, "bold"),
            padx=10,
            pady=2,
        )
        self.btn_end_match.pack(side="right")

        self.btn_undo_win = _mk_btn(
            sb_top_bar,
            "↩️ Hoàn tác (-1)",
            self.undo_last_winner,
            fg="#fbbf24",
            hover_fg="#ffffff",
            border="#475569",
            font=("Segoe UI", 8, "bold"),
            padx=10,
            pady=2,
        )
        self.btn_undo_win.pack(side="right", padx=(0, 8))

        # Bố cục 3 cột đối xứng: TEAM ĐỎ (Trái) | TỶ SỐ & THÔNG TIN KÈO (Giữa) | TEAM XANH (Phải)
        sb_board_inner = tk.Frame(battle_card, bg=C_PANEL)
        sb_board_inner.pack(fill="x", pady=(0, 10))
        sb_board_inner.columnconfigure(0, weight=5, uniform="sb_col")
        sb_board_inner.columnconfigure(1, weight=6, uniform="sb_col")
        sb_board_inner.columnconfigure(2, weight=5, uniform="sb_col")
        sb_board_inner.rowconfigure(0, weight=1)
        self.sb_board_inner = sb_board_inner

        # --- KHỐI TEAM ĐỎ ---
        self.red_card = tk.Frame(
            sb_board_inner,
            bg=C_RED_SURF,
            highlightthickness=1,
            highlightbackground=C_RED,
            padx=8,
            pady=6,
        )
        self.red_card.grid(row=0, column=0, sticky="nsew", padx=(0, 5))

        self._create_team_shield_canvas(self.red_card, "RED", size=42, bg_color=C_RED_SURF).pack(pady=(2, 2))

        tk.Label(
            self.red_card,
            text="TEAM ĐỎ",
            font=("Segoe UI", 11, "bold"),
            fg=C_RED_H,
            bg=C_RED_SURF,
        ).pack(fill="x")

        self.red_primary_player_lbl = tk.Label(
            self.red_card,
            text="XO",
            font=("Segoe UI", 11, "bold"),
            fg="#ffffff",
            bg=C_RED_SURF,
        )
        self.red_primary_player_lbl.pack(fill="x", pady=(1, 0))

        self.red_roster_lbl = tk.Label(
            self.red_card,
            text="[Chưa chọn quân] (Chờ mở Diplomacy)",
            font=("Segoe UI", 8, "bold"),
            fg="#cbd5e1",
            bg=C_RED_SURF,
            justify="center",
            wraplength=200,
        )
        self.red_roster_lbl.pack(fill="x", pady=(2, 3))
        self._auto_wrap_label(self.red_roster_lbl, pad=8)

        self.red_count_lbl = tk.Label(
            self.red_card,
            text="Chủ nhà",
            font=("Segoe UI", 8, "bold"),
            fg="#fca5a5",
            bg="#3a161b",
            padx=8,
            pady=0,
        )
        self.red_count_lbl.pack(pady=(1, 0))

        # --- KHỐI TỶ SỐ & THÔNG TIN KÈO (GIỮA – cố định chiều cao từng dòng để chống nhòe chữ) ---
        center_hud = tk.Frame(
            sb_board_inner,
            bg=C_ELEV,
            highlightthickness=1,
            highlightbackground=C_BORDER,
            padx=10,
            pady=6,
        )
        center_hud.grid(row=0, column=1, sticky="nsew", padx=5)
        self.center_hud = center_hud

        self.match_mode_lbl = tk.Label(
            center_hud,
            text="Kèo 1v1 - Chạm 7",
            font=("Segoe UI", 9, "bold"),
            fg=C_GOLD,
            bg=C_ELEV,
            height=1,
        )
        self.match_mode_lbl.pack(side="top", fill="x")

        self.score_lbl = tk.Label(
            center_hud,
            text="0 : 0",
            font=("Consolas", 36, "bold"),
            fg="#ffffff",
            bg=C_ELEV,
            height=1,
        )
        self.score_lbl.pack(side="top", fill="x")

        self.c_mode_summary_lbl = tk.Label(
            center_hud,
            text="Ấn nút Diplomacy để bắt đầu\nTổng 0 trận",
            font=("Segoe UI", 8, "bold"),
            fg=C_MUTED,
            bg=C_ELEV,
            wraplength=260,
            height=2,
            justify="center",
        )
        self.c_mode_summary_lbl.pack(side="top", fill="x", pady=(0, 2))
        self._auto_wrap_label(self.c_mode_summary_lbl, pad=10)

        self.match_history_lbl = tk.Label(
            center_hud,
            text="Lịch sử ván: Chưa có ván đấu",
            font=("Segoe UI", 8, "bold"),
            fg="#cbd5e1",
            bg="#141a26",
            padx=6,
            pady=1,
            wraplength=260,
            height=1,
            justify="center",
        )
        self.match_history_lbl.pack(side="top", fill="x", pady=(1, 3))
        self._auto_wrap_label(self.match_history_lbl, pad=14)

        self.stars_counter_lbl = tk.Label(
            center_hud,
            text="⭐ 0 sao tại sảnh XO",
            font=("Segoe UI", 8, "bold"),
            fg="#fbbf24",
            bg=C_ELEV,
            height=1,
        )
        self.stars_counter_lbl.pack(side="top", fill="x", pady=(0, 2))

        # --- KHỐI TEAM XANH ---
        self.blue_card = tk.Frame(
            sb_board_inner,
            bg=C_BLUE_SURF,
            highlightthickness=1,
            highlightbackground=C_BLUE,
            padx=8,
            pady=6,
        )
        self.blue_card.grid(row=0, column=2, sticky="nsew", padx=(5, 0))

        self._create_team_shield_canvas(self.blue_card, "BLUE", size=42, bg_color=C_BLUE_SURF).pack(pady=(2, 2))

        tk.Label(
            self.blue_card,
            text="TEAM XANH",
            font=("Segoe UI", 11, "bold"),
            fg=C_BLUE_H,
            bg=C_BLUE_SURF,
        ).pack(fill="x")

        self.blue_primary_player_lbl = tk.Label(
            self.blue_card,
            text="Đội khách",
            font=("Segoe UI", 11, "bold"),
            fg="#ffffff",
            bg=C_BLUE_SURF,
        )
        self.blue_primary_player_lbl.pack(fill="x", pady=(1, 0))

        self.blue_roster_lbl = tk.Label(
            self.blue_card,
            text="[Chưa chọn quân] (Chờ mở Diplomacy)",
            font=("Segoe UI", 8, "bold"),
            fg="#cbd5e1",
            bg=C_BLUE_SURF,
            justify="center",
            wraplength=200,
        )
        self.blue_roster_lbl.pack(fill="x", pady=(2, 3))
        self._auto_wrap_label(self.blue_roster_lbl, pad=8)

        self.blue_count_lbl = tk.Label(
            self.blue_card,
            text="Đội khách",
            font=("Segoe UI", 8, "bold"),
            fg="#93c5fd",
            bg="#16264a",
            padx=8,
            pady=0,
        )
        self.blue_count_lbl.pack(pady=(1, 0))

        # --- CỤM NÚT GHI NHẬN KẾT QUẢ (2 NÚT LỚN 50/50, CAO ~46px) ---
        win_btns_row = tk.Frame(battle_card, bg=C_PANEL)
        win_btns_row.pack(fill="x")
        win_btns_row.columnconfigure(0, weight=1, uniform="win_btn_col")
        win_btns_row.columnconfigure(1, weight=1, uniform="win_btn_col")

        self.btn_red_win = _mk_btn(
            win_btns_row,
            "🏆  Team Đỏ thắng (+1) [F5]",
            lambda: self.set_current_winner("RED"),
            fg="#ffffff",
            bg=C_RED,
            hover_bg=C_RED_H,
            hover_fg="#ffffff",
            border=None,
            font=("Segoe UI", 10, "bold"),
            pady=9,
        )
        self.btn_red_win.grid(row=0, column=0, sticky="ew", padx=(0, 5))

        self.btn_blue_win = _mk_btn(
            win_btns_row,
            "🏆  Team Xanh thắng (+1) [F6]",
            lambda: self.set_current_winner("BLUE"),
            fg="#ffffff",
            bg=C_BLUE,
            hover_bg=C_BLUE_H,
            hover_fg="#ffffff",
            border=None,
            font=("Segoe UI", 10, "bold"),
            pady=9,
        )
        self.btn_blue_win.grid(row=0, column=1, sticky="ew", padx=(5, 0))

        # ----------------------------------------------------------------------
        # CỘT GIỮA – NGĂN KÉO NHẬT KÝ HỆ THỐNG (SYSTEM LOG PANEL – THU GỌN / MỞ RỘNG LINH HOẠT)
        # ----------------------------------------------------------------------
        self.log_drawer_open = True
        self.log_drawer_frame = _mk_panel(self.center_workspace_col, padx=10, pady=6)
        self.log_drawer_frame.pack(fill="both", expand=True, side="top")

        log_hdr = tk.Frame(self.log_drawer_frame, bg=C_PANEL)
        log_hdr.pack(fill="x", side="top")

        _mk_section_title(log_hdr, "📜  NHẬT KÝ HỆ THỐNG").pack(side="left")

        self.btn_toggle_log = _mk_btn(
            log_hdr,
            "▼ Thu gọn",
            self.toggle_log_drawer,
            fg="#fbbf24",
            bg="#241b0f",
            hover_bg="#362712",
            border="#b45309",
            font=("Segoe UI", 8, "bold"),
            padx=8,
            pady=1,
        )
        self.btn_toggle_log.pack(side="right", padx=(6, 0))

        self.btn_expand_log = _mk_btn(
            log_hdr,
            "🔎 Phóng to Log (16 dòng)",
            self.toggle_expand_log_height,
            fg="#60a5fa",
            bg="#131f33",
            hover_bg="#1e3a8a",
            border="#1d4ed8",
            font=("Segoe UI", 8, "bold"),
            padx=8,
            pady=1,
        )
        self.btn_expand_log.pack(side="right", padx=(6, 0))

        self.btn_copy_log = _mk_btn(
            log_hdr,
            "📋 Copy Log",
            self.copy_all_logs_to_clipboard,
            font=("Segoe UI", 8, "bold"),
            padx=8,
            pady=1,
        )
        self.btn_copy_log.pack(side="right", padx=(6, 0))

        self.log_body_frame = tk.Frame(self.log_drawer_frame, bg=C_PANEL)
        self.log_body_frame.pack(fill="both", expand=True, side="top", pady=(6, 0))

        self.log_scrollbar = self._make_dark_scrollbar(self.log_body_frame, "vertical")
        self.log_scrollbar.pack(side="right", fill="y")

        self.log_box = tk.Text(
            self.log_body_frame,
            bg=C_ELEV,
            fg="#e7ebf0",
            font=("Consolas", 8),
            relief="flat",
            height=8,
            padx=8,
            pady=5,
            wrap="word",
            insertbackground=C_GOLD,
            highlightthickness=1,
            highlightbackground=C_BORDER,
            yscrollcommand=self.log_scrollbar.set,
        )
        self.log_box.pack(side="left", fill="both", expand=True)
        self.log_scrollbar.config(command=self.log_box.yview)
        self.log_box.tag_config("TIME", foreground="#64748b")
        self.log_box.tag_config("DEFAULT", foreground="#e7ebf0")
        self.log_box.tag_config("SUCCESS", foreground="#34d399")
        self.log_box.tag_config("WARN", foreground=C_GOLD)
        self.log_box.tag_config("ERROR", foreground="#f87171")
        self.log_box.tag_config("TEAM", foreground=C_GOLD)

        # ----------------------------------------------------------------------
        # CỘT PHẢI – SẢNH CHAT LIVE & QUÀ TẶNG (FULL HEIGHT)
        # ----------------------------------------------------------------------
        chat_card = _mk_panel(self.right_workspace_col, padx=10, pady=8)
        chat_card.pack(fill="both", expand=True)
        self.chat_card = chat_card

        # 1. Header Sảnh Chat Live
        chat_hdr = tk.Frame(chat_card, bg=C_PANEL)
        chat_hdr.pack(fill="x", side="top", pady=(0, 6))

        chat_hdr_btns = tk.Frame(chat_hdr, bg=C_PANEL)
        chat_hdr_btns.pack(side="right", anchor="n")

        self.lobby_badge_lbl = tk.Label(
            chat_hdr,
            text="💬  SẢNH CHAT LIVE - MÁY XO",
            font=("Segoe UI", 9, "bold"),
            fg=C_TXT,
            bg=C_PANEL,
            anchor="w",
            justify="left",
            width=1,
        )
        self.lobby_badge_lbl.pack(side="left", fill="x", expand=True)
        self._auto_wrap_label(self.lobby_badge_lbl, pad=4)

        btn_my_lobby = _mk_btn(
            chat_hdr_btns,
            "🏠 Sảnh của tôi",
            lambda: self.enter_friend_live_lobby(""),
            font=("Segoe UI", 8, "bold"),
            padx=8,
            pady=2,
        )
        btn_my_lobby.pack(side="left", padx=(0, 5))

        btn_fb_chat_hdr = _mk_btn(
            chat_hdr_btns,
            "📞 ●",
            self.show_fb_group_live_bridge_window,
            fg="#34d399",
            bg="#0e2920",
            hover_bg="#14532d",
            border="#166534",
            font=("Segoe UI", 8, "bold"),
            padx=8,
            pady=2,
        )
        btn_fb_chat_hdr.pack(side="left")

        # 2. Bar 1: Quỹ Sao cá nhân & Tổng Sao nhận được trong phiên Live
        wallet_bar = tk.Frame(
            chat_card,
            bg=C_ELEV,
            highlightthickness=1,
            highlightbackground=C_BORDER,
            padx=8,
            pady=4,
        )
        wallet_bar.pack(fill="x", side="top", pady=(0, 5))

        self.chat_lobby_stars_lbl = tk.Label(
            wallet_bar,
            text="🎁 Phiên Live: 0 ⭐",
            font=("Segoe UI", 8, "bold"),
            fg="#34d399",
            bg=C_ELEV,
        )
        self.chat_lobby_stars_lbl.pack(side="right")

        self.chat_wallet_lbl = self._make_ellipsis_label(
            wallet_bar,
            text="💰 Quỹ Sao của bạn: 0 ⭐  (Trừ trực tiếp khi tặng)",
            font=("Segoe UI", 8, "bold"),
            fg="#fbbf24",
            bg=C_ELEV,
            anchor="w",
        )
        self.chat_wallet_lbl.pack(side="left", fill="x", expand=True)

        # 3. Bar 2 (Gộp gọn): Banner Vinh Danh Hoàng Gia + Thanh Ghim bình luận quan trọng
        notice_stack = tk.Frame(chat_card, bg=C_BORDER, highlightthickness=0, padx=1, pady=1)
        notice_stack.pack(fill="x", side="top", pady=(0, 5))

        self.chat_honor_banner_frame = tk.Frame(notice_stack, bg="#231a0e", padx=8, pady=4)
        self.chat_honor_banner_frame.pack(fill="x")

        self.chat_honor_lbl = tk.Label(
            self.chat_honor_banner_frame,
            text="👑 VINH DANH SẢNH XO: Thả 🐘 Con Voi (22 ⭐) hoặc ⚡ Phù Thủy (100 ⭐) để lên bảng vàng!",
            font=("Segoe UI", 8, "bold"),
            fg="#fde047",
            bg="#231a0e",
            anchor="w",
            justify="left",
            width=1,
        )
        self.chat_honor_lbl.pack(fill="x")
        self._auto_wrap_label(self.chat_honor_lbl, pad=4)

        self.pinned_chat_frame = tk.Frame(notice_stack, bg="#172030", padx=8, pady=3)
        self.pinned_chat_frame.pack(fill="x", pady=(1, 0))

        btn_unpin = tk.Button(
            self.pinned_chat_frame,
            text="✕",
            command=lambda: self.pin_chat_message_action(unpin=True),
            font=("Segoe UI", 8, "bold"),
            bg="#172030",
            fg=C_MUTED,
            activebackground="#1e293b",
            activeforeground="#ffffff",
            relief="flat",
            bd=0,
            padx=4,
            cursor="hand2",
        )
        btn_unpin.pack(side="right", anchor="n")

        btn_pin_latest = tk.Button(
            self.pinned_chat_frame,
            text="📌 Ghim",
            command=lambda: self.pin_chat_message_action(unpin=False),
            font=("Segoe UI", 7, "bold"),
            bg="#1e3a8a",
            fg="#ffffff",
            activebackground="#1d4ed8",
            activeforeground="#ffffff",
            relief="flat",
            padx=6,
            pady=1,
            cursor="hand2",
        )
        btn_pin_latest.pack(side="right", anchor="n", padx=(4, 2))

        self.pinned_chat_lbl = tk.Label(
            self.pinned_chat_frame,
            text="📌 Ghim: Chưa có bình luận ghim (Bấm '📌 Ghim' để ghim tin mới nhất)",
            font=("Segoe UI", 8, "bold"),
            fg="#93c5fd",
            bg="#172030",
            anchor="w",
            justify="left",
            width=1,
        )
        self.pinned_chat_lbl.pack(side="left", fill="x", expand=True)
        self._auto_wrap_label(self.pinned_chat_lbl, pad=4)

        # 4. Thanh lọc Chat: Ô tìm kiếm + Tab Tất cả / Chat / Quà / Hệ thống + Lọc Spam
        chat_tools_bar = tk.Frame(chat_card, bg=C_PANEL)
        chat_tools_bar.pack(fill="x", side="top", pady=(0, 5))

        tk.Checkbutton(
            chat_tools_bar,
            text="Lọc Spam",
            variable=self.chat_antispam_var,
            command=lambda: self._update_friends_and_social_ui(self._cached_social_data) if self._cached_social_data else None,
            font=("Segoe UI", 8, "bold"),
            fg=C_MUTED,
            bg=C_PANEL,
            selectcolor=C_APP,
            activebackground=C_PANEL,
            activeforeground=C_GOLD,
            cursor="hand2",
        ).pack(side="right")

        tk.Label(
            chat_tools_bar,
            text="🔍",
            font=("Segoe UI", 8),
            fg=C_MUTED,
            bg=C_ELEV,
            padx=4,
            pady=1,
        ).pack(side="left")

        tk.Entry(
            chat_tools_bar,
            textvariable=self.chat_search_var,
            font=("Segoe UI", 8),
            bg=C_ELEV,
            fg=C_TXT,
            insertbackground=C_GOLD,
            width=6,
            relief="flat",
            highlightthickness=1,
            highlightbackground=C_BORDER,
            highlightcolor=C_GOLD,
        ).pack(side="left", fill="x", expand=True, ipady=2)

        # Hàng tab lọc chat chia đều 4 cột (không bao giờ tràn / đè lên Lọc Spam ở màn 1366x768)
        chat_tabs_box = tk.Frame(chat_card, bg=C_PANEL)
        chat_tabs_box.pack(fill="x", side="top", pady=(0, 5))
        for t_idx in range(4):
            chat_tabs_box.columnconfigure(t_idx, weight=1, uniform="chat_tab_col")
        for t_idx, (t_code, t_lbl) in enumerate(
            [("ALL", "Tất cả"), ("CHAT", "💬 Chat"), ("GIFT", "🎁 Quà"), ("SYSTEM", "⚙️ Hệ thống")]
        ):
            is_act = t_code == "ALL"
            b_cf = tk.Button(
                chat_tabs_box,
                text=t_lbl,
                command=lambda c=t_code: self._set_chat_filter_tab(c),
                font=("Segoe UI", 8, "bold"),
                bg=C_GOLD if is_act else C_ELEV,
                fg=C_ON_GOLD if is_act else C_MUTED,
                relief="flat",
                highlightthickness=0 if is_act else 1,
                highlightbackground=C_BORDER,
                padx=4,
                pady=1,
                cursor="hand2",
            )
            b_cf.grid(row=0, column=t_idx, sticky="ew", padx=(0 if t_idx == 0 else 2, 0))
            self._chat_filter_btns[t_code] = b_cf

        # 5. Thanh nhập Chat ở đáy (Pack side="bottom" trước để cố định đáy): Ô nhập + Tặng Sao ▾ + Gửi + Emoji
        self.gift_drawer_open = False
        chat_input_row = tk.Frame(chat_card, bg=C_PANEL)
        chat_input_row.pack(fill="x", side="bottom", pady=(5, 0))

        self.chat_msg_var = self._make_safe_string_var()

        self.btn_emoji_chat = _mk_btn(
            chat_input_row,
            "😊",
            self._show_quick_emoji_menu,
            fg=C_TXT,
            hover_fg="#fbbf24",
            font=("Segoe UI", 10),
            padx=7,
            pady=2,
        )
        self.btn_emoji_chat.pack(side="right", padx=(4, 0))

        btn_send_chat = _mk_btn(
            chat_input_row,
            "Gửi",
            self.send_chat_message_action,
            fg=C_ON_GOLD,
            bg=C_GOLD,
            hover_bg=C_GOLD_H,
            hover_fg=C_ON_GOLD,
            border=None,
            padx=14,
            pady=4,
        )
        btn_send_chat.pack(side="right", padx=(4, 0))

        self.btn_toggle_gift_drawer = _mk_btn(
            chat_input_row,
            "🎁 Tặng Sao ▾",
            self.toggle_gift_drawer,
            fg="#fbbf24",
            bg="#261c10",
            hover_bg="#3b2a14",
            border="#b45309",
            padx=10,
            pady=4,
        )
        self.btn_toggle_gift_drawer.pack(side="right")

        chat_entry = tk.Entry(
            chat_input_row,
            textvariable=self.chat_msg_var,
            font=("Segoe UI", 9),
            bg=C_ELEV,
            fg="#f8fafc",
            insertbackground=C_GOLD,
            width=6,
            relief="flat",
            highlightthickness=1,
            highlightbackground=C_BORDER,
            highlightcolor=C_GOLD,
        )
        chat_entry.pack(side="left", fill="x", expand=True, padx=(0, 6), ipady=5)
        chat_entry.bind("<Return>", lambda _e: self.send_chat_message_action())

        # 6. Khung Vật Phẩm Đế Chế 3x2 Card & 4 Nút Tặng Sao nhanh (Gộp vào nút '🎁 Tặng Sao ▾', bấm mới xổ ra)
        self.aoe_gift_panel = tk.Frame(
            chat_card,
            bg="#151a24",
            highlightthickness=1,
            highlightbackground="#b45309",
            padx=8,
            pady=6,
        )

        gift_hdr_row = tk.Frame(self.aoe_gift_panel, bg="#151a24")
        gift_hdr_row.pack(fill="x", pady=(0, 4))

        tk.Button(
            gift_hdr_row,
            text="✕ Thu gọn",
            command=lambda: self.toggle_gift_drawer(force_close=True),
            font=("Segoe UI", 8, "bold"),
            bg="#1e2533",
            fg=C_MUTED,
            relief="flat",
            padx=6,
            pady=0,
            cursor="hand2",
        ).pack(side="right", anchor="n")

        gift_title_lbl = tk.Label(
            gift_hdr_row,
            text="⚔️ CHỌN VẬT PHẨM ĐẾ CHẾ HOẶC TẶNG SAO (Trừ từ Quỹ Sao của bạn)",
            font=("Segoe UI", 8, "bold"),
            fg="#fbbf24",
            bg="#151a24",
            anchor="w",
            justify="left",
            width=1,
        )
        gift_title_lbl.pack(side="left", fill="x", expand=True)
        self._auto_wrap_label(gift_title_lbl, pad=4)

        gift_grid = tk.Frame(self.aoe_gift_panel, bg="#151a24")
        gift_grid.pack(fill="x", pady=(0, 4))
        for c_i in range(3):
            gift_grid.columnconfigure(c_i, weight=1, uniform="gift_col")

        gift_visual_defs = [
            ("FOOD_200", "🍖", "200 Thực", 5, "Bơm 200 Thực cứu chủ lực!"),
            ("WOOD_500", "🪵", "500 Gỗ", 10, "Bơm 500 Gỗ đóng nhà BA!"),
            ("FOOD_1000", "🥩", "1000 Thực", 15, "Bơm 1000 Thực kích Đời 4!"),
            ("ELEPHANT", "🐘", "Con Voi", 22, "Thả Voi Điên húc bay nhà địch!"),
            ("HORSE_ARCHER", "🏹", "Song Mã", 50, "Viện trợ Đạo Song Mã thần cứu nhà!"),
            ("PRIEST_LIGHTNING", "⚡", "Phù Thủy Sét", 100, "Triệu hồi Phù Thủy Sét (Wololo) — Ái dà, hú hú!"),
        ]

        for idx, (g_code, g_ico, g_title, g_cost, g_desc) in enumerate(gift_visual_defs):
            r_i = idx // 3
            c_i = idx % 3
            is_special = g_code in ("ELEPHANT", "PRIEST_LIGHTNING")
            card_bg = "#211a12" if is_special else "#171c26"
            card_border = "#b45309" if is_special else "#283142"

            g_card = tk.Frame(
                gift_grid,
                bg=card_bg,
                highlightthickness=1,
                highlightbackground=card_border,
                padx=6,
                pady=4,
                cursor="hand2",
            )
            g_card.grid(row=r_i, column=c_i, sticky="ew", padx=3, pady=2)

            ico_l = tk.Label(
                g_card,
                text=g_ico,
                font=("Segoe UI Emoji", 13),
                fg="#fbbf24",
                bg=card_bg,
                cursor="hand2",
            )
            ico_l.pack(side="left", padx=(2, 6))

            txt_stack = tk.Frame(g_card, bg=card_bg, cursor="hand2")
            txt_stack.pack(side="left", fill="x", expand=True)

            name_l = tk.Label(
                txt_stack,
                text=g_title,
                font=("Segoe UI", 8, "bold"),
                fg="#f8fafc",
                bg=card_bg,
                anchor="w",
                cursor="hand2",
            )
            name_l.pack(anchor="w")

            cost_l = tk.Label(
                txt_stack,
                text=f"{g_cost} ⭐",
                font=("Segoe UI", 8, "bold"),
                fg="#fbbf24",
                bg=card_bg,
                anchor="w",
                cursor="hand2",
            )
            cost_l.pack(anchor="w")

            def _bind_gift_click(
                widgets,
                code=g_code,
                cost=g_cost,
                lbl=f"{g_ico} {g_title}",
                desc=g_desc,
                c_frame=g_card,
                c_border=card_border,
            ):
                for w in widgets:
                    w.bind(
                        "<Button-1>",
                        lambda _e: self.send_star_gift_action(cost, gift_code=code, gift_name=lbl, default_msg=desc),
                    )
                    w.bind("<Enter>", lambda _e: c_frame.configure(highlightbackground=C_GOLD))
                    w.bind("<Leave>", lambda _e: c_frame.configure(highlightbackground=c_border))

            _bind_gift_click([g_card, ico_l, txt_stack, name_l, cost_l])

        # Hàng nút Tặng Sao nhanh (+1, +10, +50, +100 Sao)
        quick_star_row = tk.Frame(self.aoe_gift_panel, bg="#151a24")
        quick_star_row.pack(fill="x")
        for c_i in range(4):
            quick_star_row.columnconfigure(c_i, weight=1, uniform="qstar_col")

        for idx, (amt, lbl_txt) in enumerate(
            [(1, "★ +1 Sao"), (10, "☀️ +10 Sao"), (50, "💎 +50 Sao"), (100, "💠 +100 Sao")]
        ):
            b = tk.Button(
                quick_star_row,
                text=lbl_txt,
                command=lambda a=amt: self.send_star_gift_action(a),
                font=("Segoe UI", 8, "bold"),
                bg="#171c26",
                fg=C_TXT,
                activebackground="#242c3d",
                activeforeground="#fbbf24",
                relief="flat",
                highlightthickness=1,
                highlightbackground="#283142",
                pady=3,
                cursor="hand2",
            )
            b.grid(row=0, column=idx, sticky="ew", padx=3, pady=(2, 0))
            self._bind_hover(b, "#171c26", "#242c3d", C_TXT, "#fbbf24")

        # 7. Khung hiển thị tin nhắn (Chat Viewport) – chiếm tối đa chiều cao còn lại, Dark Scrollbar
        self.chat_feed_wrap = tk.Frame(chat_card, bg=C_ELEV, highlightthickness=1, highlightbackground=C_BORDER)
        self.chat_feed_wrap.pack(side="top", fill="both", expand=True, pady=(0, 2))
        chat_feed_wrap = self.chat_feed_wrap

        chat_scroll = self._make_dark_scrollbar(chat_feed_wrap, "vertical")
        chat_scroll.pack(side="right", fill="y")

        self.chat_box = tk.Text(
            chat_feed_wrap,
            bg=C_ELEV,
            fg=C_TXT,
            font=("Segoe UI", 9),
            relief="flat",
            width=30,
            height=11,
            padx=10,
            pady=8,
            wrap="word",
            spacing1=2,
            spacing3=2,
            state="disabled",
            highlightthickness=0,
            yscrollcommand=chat_scroll.set,
        )
        self.chat_box.pack(side="left", fill="both", expand=True)
        chat_scroll.config(command=self.chat_box.yview)
        self.chat_box.tag_config("TIME", foreground="#64748b", font=("Consolas", 8))
        self.chat_box.tag_config("ADMIN_BADGE", foreground="#fde047", background="#3b1d1d", font=("Segoe UI", 8, "bold"))
        self.chat_box.tag_config("STREAMER_BADGE", foreground="#34d399", background="#0e2920", font=("Segoe UI", 8, "bold"))
        self.chat_box.tag_config("SENDER", foreground="#f8fafc", font=("Segoe UI", 9, "bold"))
        self.chat_box.tag_config("ADMIN_SENDER", foreground="#fbbf24", font=("Segoe UI", 9, "bold"))
        self.chat_box.tag_config("FB_SENDER", foreground="#60a5fa", font=("Segoe UI", 9, "bold"))
        self.chat_box.tag_config("STAR", foreground="#fbbf24", background="#231a0e", font=("Segoe UI", 9, "bold"))
        self.chat_box.tag_config("AOE_GIFT", foreground="#fde047", background="#281d0e", font=("Segoe UI", 9, "bold"))
        self.chat_box.tag_config("GIFT_SENDER", foreground="#ffffff", font=("Segoe UI", 9, "bold"))
        self.chat_box.tag_config("GIFT_VERB", foreground="#cbd5e1", font=("Segoe UI", 9))
        self.chat_box.tag_config("GIFT_ITEM", foreground="#fbbf24", font=("Segoe UI", 9, "bold"))
        self.chat_box.tag_config("GIFT_RECEIVER", foreground="#34d399", font=("Segoe UI", 9, "bold"))
        self.chat_box.tag_config("SYS_EVENT", foreground="#93c5fd", background="#111a2e", font=("Segoe UI", 8, "bold"))
        self.chat_box.tag_config("MSG", foreground="#cbd5e1")

        # ----------------------------------------------------------------------
        # TAB 2: CÀI ĐẶT VIP OVERLAY & KẾT NỐI MÁY CHỦ (SẮP XẾP THEO NHÓM CARD KHOA HỌC)
        # ----------------------------------------------------------------------
        vip_wrap = tk.Frame(self.settings_tab_frame, bg=C_APP)
        vip_wrap.pack(fill="both", expand=True, padx=10, pady=(0, 4))

        vip_hdr = _mk_panel(vip_wrap, padx=16, pady=10)
        vip_hdr.pack(fill="x", pady=(0, 8))

        tk.Label(
            vip_hdr,
            text="⚙️ Tùy chỉnh Cài đặt VIP Overlay & Hệ thống",
            font=("Segoe UI", 12, "bold"),
            fg="#e7ebf0",
            bg=C_PANEL,
        ).pack(side="left")

        _mk_btn(
            vip_hdr,
            "← Quay lại Bảng Điều Khiển",
            lambda: self.switch_main_tab("BATTLE"),
            fg=C_GOLD,
            hover_fg="#fde047",
            padx=12,
            pady=4,
        ).pack(side="right")

        vip_grid = tk.Frame(vip_wrap, bg=C_APP)
        vip_grid.pack(fill="x")
        vip_grid.columnconfigure(0, weight=1, uniform="vip_col")
        vip_grid.columnconfigure(1, weight=1, uniform="vip_col")

        def _vip_card(row, col, title, colspan=1):
            card = _mk_panel(vip_grid, padx=16, pady=12)
            card.grid(
                row=row,
                column=col,
                columnspan=colspan,
                sticky="nsew",
                padx=(0 if col == 0 else 5, 0 if (col + colspan) >= 2 else 5),
                pady=(0, 10),
            )
            _mk_section_title(card, title, fg=C_GOLD, size=10).pack(fill="x", pady=(0, 4))
            tk.Frame(card, bg=C_BORDER, height=1).pack(fill="x", pady=(0, 10))
            body = tk.Frame(card, bg=C_PANEL)
            body.pack(fill="both", expand=True)
            return body

        # Card 1: Phân quyền Hạng VIP
        tier_body = _vip_card(0, 0, "👑  PHÂN QUYỀN HẠNG VIP", colspan=2)
        tier_info_lbl = tk.Label(
            tier_body,
            text="Phân quyền Hạng VIP: 🥈 Hạng Bạc (Chạm X, Hiện ngày góc phải)  •  🥇 Hạng Vàng (Tùy chỉnh dòng chữ chạy)  •  💎 Hạng Kim Cương (Đánh theo C - Séc 1, 2, 3)",
            font=("Segoe UI", 9, "bold"),
            fg="#cbd5e1",
            bg=C_PANEL,
            anchor="w",
            justify="left",
            width=1,
        )
        tier_info_lbl.pack(fill="x")
        self._auto_wrap_label(tier_info_lbl, pad=6)

        # Card 2: Kèo đấu & Tùy chọn hiển thị Overlay
        match_body = _vip_card(1, 0, "🎯  KÈO ĐẤU & HIỂN THỊ OVERLAY")
        match_body.columnconfigure(1, weight=1)

        tk.Label(
            match_body,
            text="Kèo đấu chạm bao nhiêu (🥈 Bạc+):",
            font=("Segoe UI", 10, "bold"),
            fg="#e7ebf0",
            bg=C_PANEL,
            anchor="w",
        ).grid(row=0, column=0, sticky="w", pady=(0, 8))

        tk.Entry(
            match_body,
            textvariable=self.target_score_var,
            font=("Consolas", 11, "bold"),
            bg=C_ELEV,
            fg=C_GOLD,
            insertbackground=C_GOLD,
            width=8,
            justify="center",
            relief="flat",
            highlightthickness=1,
            highlightbackground=C_BORDER,
            highlightcolor=C_GOLD,
        ).grid(row=0, column=1, sticky="w", padx=(10, 0), pady=(0, 8), ipady=4)

        for r_i, (cb_txt, cb_var, cb_fg) in enumerate(
            [
                ("Hiển thị ngày ở góc phải Overlay (🥈 Bạc+)", self.show_date_var, "#e7ebf0"),
                ("🏆 Đánh theo 'C' — Hiện bảng phụ Séc 1, 2, 3 bên phải (💎 Kim Cương)", self.c_mode_var, "#e7ebf0"),
            ],
            start=1,
        ):
            tk.Checkbutton(
                match_body,
                text=cb_txt,
                variable=cb_var,
                font=("Segoe UI", 10, "bold"),
                fg=cb_fg,
                bg=C_PANEL,
                selectcolor=C_ELEV,
                activebackground=C_PANEL,
                activeforeground=C_GOLD,
                anchor="w",
                justify="left",
                wraplength=560,
                cursor="hand2",
            ).grid(row=r_i, column=0, columnspan=2, sticky="w", pady=3)

        # Card 3: Khung Bảng Quân Ảo căn chỉnh OBS khi chưa có trận
        obs_body = _vip_card(1, 1, "📐  CĂN CHỈNH KHUNG OBS")
        tk.Checkbutton(
            obs_body,
            text="📐 Hiện 'Khung Bảng Quân Ảo' trên OBS khi chưa có trận (Giúp căn vị trí khung OBS chuẩn xác trước khi vào game — Mặc định Bật)",
            variable=self.show_idle_preview_var,
            font=("Segoe UI", 10, "bold"),
            fg="#34d399",
            bg=C_PANEL,
            selectcolor=C_ELEV,
            activebackground=C_PANEL,
            activeforeground="#34d399",
            anchor="w",
            justify="left",
            wraplength=560,
            cursor="hand2",
        ).pack(anchor="w", fill="x")

        # Card 4: Chế độ dòng chữ chạy
        marquee_body = _vip_card(2, 0, "📝  DÒNG CHỮ CHẠY (🥇 VÀNG+)")
        marquee_body.columnconfigure(1, weight=1)

        tk.Label(
            marquee_body,
            text="Chế độ dòng chữ chạy (🥇 Vàng+):",
            font=("Segoe UI", 10, "bold"),
            fg="#e7ebf0",
            bg=C_PANEL,
            anchor="w",
        ).grid(row=0, column=0, sticky="w", pady=(0, 8))

        self.marquee_combo = self.ttk.Combobox(
            marquee_body,
            textvariable=self.marquee_label_var,
            values=[lbl for _, lbl in MARQUEE_MODE_LABELS],
            state="readonly",
            width=30,
            style="Premium.TCombobox",
            font=("Segoe UI", 10),
        )
        self.marquee_combo.grid(row=0, column=1, sticky="ew", padx=(10, 0), pady=(0, 8))

        tk.Label(
            marquee_body,
            text="Nội dung chữ tùy chỉnh:",
            font=("Segoe UI", 10, "bold"),
            fg="#e7ebf0",
            bg=C_PANEL,
            anchor="w",
        ).grid(row=1, column=0, sticky="w")

        tk.Entry(
            marquee_body,
            textvariable=self.custom_marquee_var,
            font=("Segoe UI", 10),
            bg=C_ELEV,
            fg="#e7ebf0",
            insertbackground=C_GOLD,
            relief="flat",
            highlightthickness=1,
            highlightbackground=C_BORDER,
            highlightcolor=C_GOLD,
        ).grid(row=1, column=1, sticky="ew", padx=(10, 0), ipady=5)

        # Card 5: Cấu hình Server URL nâng cao
        server_body = _vip_card(2, 1, "🌐  KẾT NỐI MÁY CHỦ")
        server_body.columnconfigure(1, weight=1)

        tk.Label(
            server_body,
            text="Địa chỉ máy chủ (Server URL):",
            font=("Segoe UI", 10, "bold"),
            fg="#cbd5e1",
            bg=C_PANEL,
            anchor="w",
        ).grid(row=0, column=0, sticky="w")

        tk.Entry(
            server_body,
            textvariable=self.server_url_var,
            font=("Consolas", 9),
            bg=C_ELEV,
            fg="#cbd5e1",
            insertbackground=C_GOLD,
            width=20,
            relief="flat",
            highlightthickness=1,
            highlightbackground=C_BORDER,
            highlightcolor=C_GOLD,
        ).grid(row=0, column=1, sticky="ew", padx=(10, 0), ipady=5)

        # Hàng hành động: Lưu & Áp dụng cấu hình lên OBS
        vip_action_row = tk.Frame(vip_wrap, bg=C_APP)
        vip_action_row.pack(fill="x", pady=(0, 6))

        self.apply_vip_btn = _mk_btn(
            vip_action_row,
            "⚡ Lưu & Áp dụng cấu hình lên OBS",
            self.apply_vip_overlay_settings,
            fg=C_ON_GOLD,
            bg=C_GOLD,
            hover_bg=C_GOLD_H,
            hover_fg=C_ON_GOLD,
            border=None,
            font=("Segoe UI", 10, "bold"),
            padx=22,
            pady=7,
        )
        self.apply_vip_btn.pack(side="right")

        # Khởi tạo Sảnh Giải Trí Chờ Kèo (5 Mini Games chạy trực tiếp trên App Windows)
        self.minigames_hub = TkMinigamesHub(self, self.minigames_tab_frame)

        # Mặc định hiển thị Tab Bảng Điều Khiển bên trong Main Frame, nhưng mở Tool sẽ vào Màn hình Đăng nhập trước
        self.battle_tab_frame.pack(fill="both", expand=True)
        self.login_screen_frame.pack(fill="both", expand=True)

        self.log(f"Khởi động {APP_TITLE} ({APP_VERSION}) thành công.", "DEFAULT")
        if is_windows_process_admin():
            self.log(
                "🛡️ Đã kích hoạt Quyền Administrator & Hook Bàn Phím Tầng Thấp (WH_KEYBOARD_LL): Phím tắt F5, F6, F8 hoạt động xuyên màn hình Game AOE!",
                "SUCCESS",
            )
        elif os.name == "nt":
            self.log(
                "⚠️ Tool đang chạy chưa có quyền Administrator — nếu Game AOE chặn phím F5/F6/F8 (do UIPI), hãy chuột phải chọn 'Run as administrator'.",
                "WARN",
            )
        self.log("Hãy đăng nhập tài khoản Player và ấn nút Diplomacy trong game để tự động đọc bảng quân.", "TEAM")

    def switch_main_tab(self, tab_name: str):
        self.active_tab = tab_name
        for frm in (self.battle_tab_frame, self.settings_tab_frame, self.minigames_tab_frame):
            frm.pack_forget()
        for btn, und in (
            (self.tab_battle_btn, getattr(self, "tab_battle_underline", None)),
            (self.tab_settings_btn, getattr(self, "tab_settings_underline", None)),
            (getattr(self, "tab_minigames_btn", None), getattr(self, "tab_minigames_underline", None)),
        ):
            if btn:
                btn.configure(fg="#94a3b8")
            if und:
                und.configure(bg="#121721")

        if tab_name == "SETTINGS":
            self.settings_tab_frame.pack(fill="both", expand=True)
            self.tab_settings_btn.configure(fg="#fbbf24")
            if hasattr(self, "tab_settings_underline"):
                self.tab_settings_underline.configure(bg="#f59e0b")
        elif tab_name == "MINIGAMES":
            self.minigames_tab_frame.pack(fill="both", expand=True)
            if hasattr(self, "tab_minigames_btn"):
                self.tab_minigames_btn.configure(fg="#fbbf24")
            if hasattr(self, "tab_minigames_underline"):
                self.tab_minigames_underline.configure(bg="#f59e0b")
            if hasattr(self, "minigames_hub"):
                self.minigames_hub.on_tab_shown()
        else:
            self.battle_tab_frame.pack(fill="both", expand=True)
            self.tab_battle_btn.configure(fg="#fbbf24")
            if hasattr(self, "tab_battle_underline"):
                self.tab_battle_underline.configure(bg="#f59e0b")
        self._force_repaint_widget(self.main_app_frame)

    def toggle_log_drawer(self):
        """Thu gọn / Mở rộng Ngăn kéo Nhật ký hệ thống ở cột giữa (Header luôn hiển thị)."""
        self.log_drawer_open = not self.log_drawer_open
        if self.log_drawer_open:
            self.log_drawer_frame.pack_configure(fill="both", expand=True)
            self.log_body_frame.pack(fill="both", expand=True, side="top", pady=(6, 0))
            self.btn_toggle_log.configure(text="▼ Thu gọn", fg="#fbbf24")
            self.log_box.see("end")
        else:
            self.log_body_frame.pack_forget()
            self.log_drawer_frame.pack_configure(fill="x", expand=False)
            self.btn_toggle_log.configure(text="▲ Mở Nhật ký", fg="#fbbf24")
        self._force_repaint_widget(self.main_app_frame)

    def toggle_expand_log_height(self):
        if not self.log_drawer_open:
            self.toggle_log_drawer()
        self.log_expanded = not self.log_expanded
        if self.log_expanded:
            self.log_box.configure(height=16)
            self.btn_expand_log.configure(text="🔽 Thu nhỏ Log (8 dòng)", fg="#f59e0b")
        else:
            self.log_box.configure(height=8)
            self.btn_expand_log.configure(text="🔎 Phóng to Log (16 dòng)", fg="#60a5fa")
        self.log_box.see("end")
        self._force_repaint_widget(self.main_app_frame)

    def copy_all_logs_to_clipboard(self):
        try:
            content = self.log_box.get("1.0", "end-1c")
            self.root.clipboard_clear()
            self.root.clipboard_append(content)
            self.log("✅ 📋 Đã copy toàn bộ nội dung Nhật ký vào Clipboard!", "SUCCESS")
        except Exception as e:
            self.log(f"⚠️ Không thể copy Log: {e}", "WARN")

    def show_main_dashboard_screen(self):
        self.login_screen_frame.pack_forget()
        self.main_app_frame.pack(fill="both", expand=True)
        self.switch_main_tab("BATTLE")
        self._force_repaint_widget(self.main_app_frame)

    def logout_to_login_screen(self):
        self.is_logged_in = False
        self.is_admin = False
        self.current_match = None
        self.scanner.last_dialog_signature = None
        self._reset_battle_arena_ui()
        self.main_app_frame.pack_forget()
        self.login_screen_frame.pack(fill="both", expand=True)
        self.login_status_lbl.configure(
            text="Đã đăng xuất. Vui lòng đăng nhập tài khoản để tiếp tục.",
            fg="#f59e0b",
        )

    def _start_clock_loop(self):
        def _tick():
            if not self.running:
                return
            try:
                now_str = time.strftime("🕒 %H:%M:%S - %d/%m/%Y")
                self.date_corner_lbl.configure(text=now_str)
                if self.is_logged_in:
                    self.pulse_dot.configure(fg="#34d399", bg="#0e261e", text="🟢 Đã kết nối •")
                else:
                    self.pulse_dot.configure(fg="#fbbf24", bg="#231a0e", text="🟡 Chờ đăng nhập •")
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

        color_map = {
            "SUCCESS": "#34d399",
            "ERROR": "#f0657b",
            "WARN": "#f59e0b",
            "TEAM": "#f59e0b",
            "DEFAULT": "#e7ebf0",
        }

        def _append():
            try:
                self.log_box.insert("end", f"[{ts}] ", "TIME")
                self.log_box.insert("end", f"{message}\n", tag)
                self.log_box.see("end")
                if hasattr(self, "latest_log_lbl"):
                    one_line = message.replace("\n", " ")
                    full_txt = f"📜 [{ts}] {one_line}"
                    self._latest_log_full_text = full_txt
                    avail_px = int(self.latest_log_lbl.winfo_width() or 0) - 8
                    if avail_px > 40:
                        shown_txt = self._ellipsize_text(full_txt, ("Consolas", 8), avail_px)
                    else:
                        shown_txt = full_txt if len(full_txt) <= 105 else full_txt[:102] + "…"
                    self.latest_log_lbl.configure(
                        text=shown_txt,
                        fg=color_map.get(tag, "#e7ebf0"),
                    )
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
            "show_idle_preview": bool(self.show_idle_preview_var.get()),
            "marquee_mode": marquee_code,
            "custom_marquee_text": self.custom_marquee_var.get().strip(),
        }
        save_user_settings(self.settings)
        self._update_obs_preview_entry()

    def show_obs_guide_window(self):
        """
        Cửa sổ Hướng dẫn chi tiết (cuộn được, tự xuống dòng không bị cắt chữ, kèm ảnh minh họa tải từ Server):
        ① Link OBS • ② Thêm nguồn Browser • ③ Căn Khung Ảo • ④ Phím tắt trong game • ⑤ Run as Administrator • ⑥ Xử lý sự cố
        """
        tk = self.tk
        base = self.get_base_server_url()
        name = self.player_name_var.get().strip() or "XO"
        obs_url = f"{base}/overlay.html?streamer={name}"
        obs_chat_url = f"{base}/chat-overlay.html?streamer={name}"

        BG = "#0b0e14"
        CARD = "#131b28"
        BORDER = "#243247"
        TXT = "#e2e8f0"
        SUB = "#cbd5e1"

        win = tk.Toplevel(self.root)
        win.title("📖 Hướng dẫn chi tiết: Gán Bảng Quân & Khung Chat vào OBS • Phím tắt • Run as Administrator")
        try:
            sw = self.root.winfo_screenwidth()
            sh = self.root.winfo_screenheight()
            w = min(1040, max(760, int(sw * 0.62)))
            h = min(860, max(600, int(sh * 0.86)))
            win.geometry(f"{w}x{h}+{max(0, (sw - w) // 2)}+{max(0, (sh - h) // 2 - 20)}")
        except Exception:
            win.geometry("1000x800")
        win.minsize(720, 520)
        win.configure(bg=BG)
        win.resizable(True, True)
        win._guide_imgs = []

        # --- Thanh tiêu đề cố định ---
        top = tk.Frame(win, bg=CARD, highlightthickness=1, highlightbackground=BORDER, padx=16, pady=10)
        top.pack(fill="x", padx=12, pady=(12, 6))
        tk.Label(
            top,
            text="📖 Hướng dẫn chi tiết: Gán Overlay Bảng Quân & Khung Chat vào OBS",
            font=("Segoe UI", 12, "bold"),
            fg="#fbbf24",
            bg=CARD,
            anchor="w",
            justify="left",
        ).pack(fill="x")
        sub_lbl = tk.Label(
            top,
            text="Cách ấn nút Diplomacy để đọc bảng quân, phím tắt trong game (F5 / F6 / F8) và cách chạy Tool bằng quyền Administrator. Lăn chuột để xem toàn bộ hướng dẫn.",
            font=("Segoe UI", 9),
            fg=SUB,
            bg=CARD,
            anchor="w",
            justify="left",
        )
        sub_lbl.pack(fill="x", pady=(2, 0))

        # --- Vùng nội dung cuộn ---
        body = tk.Frame(win, bg=BG)
        body.pack(fill="both", expand=True, padx=12, pady=(0, 6))
        canvas = tk.Canvas(body, bg=BG, highlightthickness=0, bd=0)
        vbar = self._make_dark_scrollbar(body, "vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=vbar.set)
        vbar.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)
        inner = tk.Frame(canvas, bg=BG)
        inner_id = canvas.create_window((0, 0), window=inner, anchor="nw")

        wrap_labels = [sub_lbl]
        image_slots = []  # (label, filename, max_ratio)

        def _on_inner_configure(_e=None):
            canvas.configure(scrollregion=canvas.bbox("all"))

        def _on_canvas_configure(e):
            canvas.itemconfigure(inner_id, width=e.width)
            wrap_w = max(320, e.width - 70)
            for lb in wrap_labels:
                try:
                    lb.configure(wraplength=wrap_w)
                except Exception:
                    pass
            try:
                sub_lbl.configure(wraplength=max(320, top.winfo_width() - 40))
            except Exception:
                pass

        inner.bind("<Configure>", _on_inner_configure)
        canvas.bind("<Configure>", _on_canvas_configure)

        def _on_wheel(e):
            try:
                canvas.yview_scroll(int(-1 * (e.delta / 120)), "units")
            except Exception:
                pass

        # Toplevel nằm trong bindtags của mọi widget con → lăn chuột ở bất kỳ đâu trong cửa sổ đều cuộn nội dung
        win.bind("<MouseWheel>", _on_wheel)

        # --- Hàm dựng nội dung ---
        def section(title, color="#fbbf24", bg=CARD, border=BORDER):
            fr = tk.Frame(inner, bg=bg, highlightthickness=1, highlightbackground=border, padx=14, pady=10)
            fr.pack(fill="x", pady=6, padx=(0, 4))
            lb = tk.Label(fr, text=title, font=("Segoe UI", 11, "bold"), fg=color, bg=bg, anchor="w", justify="left")
            lb.pack(fill="x", pady=(0, 6))
            wrap_labels.append(lb)
            return fr

        def para(parent, text, fg=SUB, bold=False, size=10, pady=(0, 4)):
            lb = tk.Label(
                parent,
                text=text,
                font=("Segoe UI", size, "bold" if bold else "normal"),
                fg=fg,
                bg=parent.cget("bg"),
                anchor="w",
                justify="left",
            )
            lb.pack(fill="x", pady=pady)
            wrap_labels.append(lb)
            return lb

        def link_row(parent, label, url, color, btn_text, btn_cmd, btn_bg, btn_fg):
            para(parent, label, fg=color, bold=True, size=10, pady=(2, 2))
            row = tk.Frame(parent, bg=parent.cget("bg"))
            row.pack(fill="x", pady=(0, 6))
            ent = tk.Entry(row, font=("Consolas", 10, "bold"), bg="#0b0f17", fg=color, relief="flat", readonlybackground="#0b0f17")
            ent.insert(0, url)
            ent.configure(state="readonly")
            ent.pack(side="left", fill="x", expand=True, ipady=5, padx=(0, 8))
            tk.Button(
                row, text=btn_text, command=btn_cmd, font=("Segoe UI", 9, "bold"),
                bg=btn_bg, fg=btn_fg, activebackground=btn_bg, relief="flat", padx=12, pady=4, cursor="hand2",
            ).pack(side="right")

        def image(parent, filename, max_ratio=1.0, caption=""):
            lb = tk.Label(
                parent,
                text=f"⏳ Đang tải ảnh minh họa ({filename})...",
                font=("Segoe UI", 9, "italic"),
                fg="#64748b",
                bg="#0b0f17",
                pady=18,
                cursor="hand2",
            )
            lb.pack(fill="x", pady=(4, 2))
            lb.bind("<Button-1>", lambda _e, f=filename: self._open_url_in_browser(f"{base}/guide/{f}"))
            image_slots.append((lb, filename, max_ratio))
            if caption:
                cap = para(parent, caption, fg="#94a3b8", size=8, pady=(0, 6))
                cap.configure(anchor="center", justify="center")

        # ① LINK OBS
        s1 = section("① Lấy 2 đường link OBS của bạn", color="#38bdf8")
        link_row(s1, "Link 1 — Bảng Quân + Hiệu ứng Tặng Sao + Hiệu ứng F8:", obs_url, "#34d399",
                 "📋 Copy Link Bảng Quân", self.copy_obs_link, "#f59e0b", "#1a2130")
        link_row(s1, "Link 2 — Khung Chat Bình Luận & Quà Tặng (nền trong suốt):", obs_chat_url, "#fbbf24",
                 "💬 Copy Link Khung Chat", self.copy_obs_chat_link, "#1e293b", "#e2e8f0")
        para(s1, "Kích thước chuẩn của nguồn Browser trong OBS:", fg=TXT, bold=True, pady=(4, 2))
        para(s1, "  •  Bảng Quân (thường):  Width = 550,  Height = 210", fg="#34d399", bold=True, pady=(0, 1))
        para(s1, "  •  Bảng Quân (bật Đánh theo C — 💎 Kim Cương):  Width = 750,  Height = 210", fg="#38bdf8", bold=True, pady=(0, 1))
        para(s1, "  •  Khung Chat:  Width = 380,  Height = 450", fg="#fbbf24", bold=True, pady=(0, 2))

        # ② THÊM NGUỒN BROWSER
        s2 = section("② Thêm nguồn Browser vào OBS Studio", color="#38bdf8")
        for line in (
            "1.  Mở OBS Studio → ở khung Sources (Nguồn) bấm dấu [+].",
            "2.  Chọn Browser (Trình duyệt) → đặt tên (VD: Bang Quan AOE) → OK.",
            "3.  Dán Link 1 (Bảng Quân) vào ô URL.",
            "4.  Đặt Width = 550, Height = 210 (Đánh theo C: 750 × 210) → bấm OK.",
            "5.  Lặp lại để tạo nguồn Browser thứ 2 cho Link 2 (Khung Chat) với Width = 380, Height = 450.",
        ):
            para(s2, line, fg=SUB, pady=(0, 2))
        image(s2, "obs-add-browser.png", caption="Ảnh minh họa — bấm vào ảnh để mở cỡ lớn trên trình duyệt")
        para(s2, "Mẹo: Nếu nền bị trắng / đen, dán vào ô Custom CSS:  body { background-color: rgba(0,0,0,0) !important; }",
             fg="#94a3b8", size=9)

        # ③ CĂN KHUNG ẢO
        s3 = section("③ Căn vị trí bằng Khung Ảo (trước khi vào trận)", color="#38bdf8")
        for line in (
            "•  Khi chưa có trận, cả 2 link tự hiện Khung Ảo viền nét đứt vàng đúng kích thước thật.",
            "•  Kéo khung đỏ của OBS tới vị trí mong muốn: Bảng Quân sát mép dưới / góc màn hình, Khung Chat bên trái hoặc phải.",
            "•  Vào game bắt buộc ấn nút Diplomacy (trên thanh menu góc trên màn hình game) → Tool mới đọc được bảng quân và tự chuyển từ khung ảo sang dữ liệu thật. Mỗi trận LIVE hiện khung chat riêng của trận đó; khung chat-overlay và chữ bên trong tự làm trong suốt (ẩn 100%) nếu sau 10 giây không có thêm bình luận hoặc người tặng sao.",
            "•  Bật / tắt tại tab ⚙️ Cài đặt VIP → 📐 Hiện Khung Ảo. Thêm &preview=1 vào link để luôn hiện khung ảo khi chưa có trận.",
        ):
            para(s3, line, fg=SUB, pady=(0, 2))
        image(s3, "obs-layout.png", caption="Bố cục gợi ý: Khung Chat bên trái • Bảng Quân phía dưới")
        image(s3, "overlay-virtual.png", max_ratio=0.62, caption="Khung Bảng Quân Ảo (550 × 210)")
        image(s3, "chat-virtual.png", max_ratio=0.34, caption="Khung Chat Ảo (380 × 450)")

        # ④ CÁCH ĐỌC BẢNG QUÂN (ẤN DIPLOMACY) & PHÍM TẮT
        s4 = section("④ Cách đọc Bảng Quân (Ấn Diplomacy) & Phím tắt trong Game", color="#fbbf24")
        image(s4, "hotkeys.png")
        for line, col in (
            ("Ấn nút Diplomacy trong game:  khi bắt đầu trận đấu, người chơi PHẢI ấn vào nút Diplomacy (ở góc trên màn hình game) để mở bảng danh sách người chơi & quân → Tool mới có thể đọc bảng quân và đưa lên OBS.", "#fde68a"),
            ("F5 / F6:  chấm Team Đỏ / Team Xanh thắng (+1). Chỉ nhận khi trận hiện tại ĐÃ ẤN DIPLOMACY ĐỂ HIỆN QUÂN và CHƯA CÓ ĐỘI THẮNG (mỗi trận chỉ 1 đội thắng).", SUB),
            ("F8:  bắn hiệu ứng \"Tay đâu, tayyyy đâuuuuu\" lên Link OBS Bảng Quân (Khung Chat tự mờ trong lúc chạy hiệu ứng).", SUB),
            ("F3 (Test ảnh) và F7 (Kết thúc kèo) dùng trên cửa sổ App. Đóng App cũng tự kết thúc kèo đấu đang LIVE.", SUB),
        ):
            para(s4, "•  " + line, fg=col, pady=(0, 2))

        # ⑤ RUN AS ADMINISTRATOR
        admin_ok = is_windows_process_admin()
        s5 = section(
            "⑤ Chạy Tool bằng quyền Administrator (bắt buộc để F5 / F6 / F8 nhận trong game)",
            color="#fca5a5", bg="#1c1117", border="#7f1d1d",
        )
        para(
            s5,
            ("✅ Tool ĐANG chạy bằng quyền Administrator — phím tắt trong game đã sẵn sàng."
             if admin_ok else
             "⚠️ Tool CHƯA chạy bằng quyền Administrator — phím F5 / F6 / F8 có thể không nhận khi đang ở trong game!"),
            fg="#34d399" if admin_ok else "#fbbf24", bold=True, pady=(0, 6),
        )
        para(s5, "Game Đế Chế (EMPIRESX.EXE) luôn chạy bằng quyền Administrator. Nếu Tool chạy quyền thường, Windows sẽ chặn phím tắt "
                 "khi bạn đang ở trong màn hình game. Bản Tool mới tự xin quyền khi mở — chỉ cần bấm Yes. Nếu vẫn không nhận phím, làm 1 trong 2 cách:",
             fg=SUB)
        image(s5, "run-admin.png")
        para(s5, "Cách 1 (mỗi lần mở):  Chuột phải vào TOOL_BANG_QUAN_AOE_BY_XO.exe → Run as administrator → bấm Yes.", fg=TXT, pady=(2, 2))
        para(s5, "Cách 2 (cài 1 lần):  Chuột phải → Properties → tab Compatibility → tích \"Run this program as an administrator\" → OK.", fg=TXT, pady=(0, 2))
        para(s5, "Kiểm tra:  Nhật ký App hiện dòng \"🛡️ Đã kích hoạt Quyền Administrator...\" là phím tắt trong game đã sẵn sàng.", fg="#34d399", pady=(0, 2))

        # ⑥ XỬ LÝ SỰ CỐ
        s6 = section("⑥ Xử lý sự cố thường gặp", color=TXT)
        for q, a in (
            ("OBS không cập nhật / hiện bản cũ:", "chuột phải nguồn Browser → Properties → Refresh cache of current page."),
            ("Bảng quân bị cắt / thừa khoảng trống:", "kiểm tra lại Width / Height theo mục ①, không kéo giãn khung bằng chuột."),
            ("Ấn F5 / F6 bị từ chối:", "trận hiện tại chưa hiện quân (hãy ấn mở nút Diplomacy trong game để đọc bảng quân) hoặc trận đã có đội thắng."),
            ("Ấn phím trong game không nhận:", "làm theo mục ⑤ (Run as administrator)."),
            ("Tắt App đột ngột:", "Server tự kết thúc kèo LIVE sau khoảng 3 phút mất tín hiệu."),
        ):
            para(s6, f"•  {q}  {a}", fg=SUB, pady=(0, 2))

        # --- Thanh nút dưới đáy ---
        bottom = tk.Frame(win, bg=BG)
        bottom.pack(fill="x", padx=12, pady=(0, 12))
        tk.Button(
            bottom, text="🌐 Mở hướng dẫn trên Web", command=lambda: self._open_url_in_browser(base),
            font=("Segoe UI", 9, "bold"), bg="#1e293b", fg="#e2e8f0", activebackground="#334155",
            relief="flat", padx=14, pady=6, cursor="hand2",
        ).pack(side="left")
        tk.Button(
            bottom, text="Đã hiểu & Đóng hướng dẫn", command=win.destroy,
            font=("Segoe UI", 10, "bold"), bg="#f59e0b", fg="#0b0e14", activebackground="#d97706",
            relief="flat", padx=20, pady=6, cursor="hand2",
        ).pack(side="right")

        # --- Tải ảnh minh họa từ Server ở luồng nền (không làm đứng giao diện) ---
        def _load_images():
            try:
                from PIL import ImageTk  # noqa: F401
            except Exception:
                return
            import io
            for lb, fname, ratio in image_slots:
                try:
                    r = requests.get(f"{base}/guide/{fname}", timeout=12)
                    if r.status_code != 200 or not r.content:
                        raise ValueError(f"HTTP {r.status_code}")
                    raw = Image.open(io.BytesIO(r.content)).convert("RGBA")
                except Exception:
                    self.root.after(0, lambda l=lb, f=fname: l.winfo_exists() and l.configure(
                        text=f"⚠️ Không tải được ảnh minh họa ({f}) — kiểm tra kết nối mạng hoặc mở hướng dẫn trên Web."))
                    continue

                def _apply(l=lb, img=raw, rt=ratio):
                    try:
                        if not l.winfo_exists():
                            return
                        from PIL import ImageTk as _ImageTk
                        avail = max(320, canvas.winfo_width() - 70)
                        target_w = int(min(avail * rt, img.width * 1.25))
                        target_w = max(160, target_w)
                        target_h = int(img.height * target_w / img.width)
                        bg_img = Image.new("RGBA", img.size, (11, 15, 23, 255))
                        bg_img.alpha_composite(img)
                        photo = _ImageTk.PhotoImage(bg_img.resize((target_w, target_h), Image.LANCZOS))
                        win._guide_imgs.append(photo)
                        l.configure(image=photo, text="", pady=0, bg="#0b0f17")
                        _on_inner_configure()
                    except Exception:
                        pass

                self.root.after(0, _apply)

        win.after(250, lambda: threading.Thread(target=_load_images, daemon=True).start())

    def _open_url_in_browser(self, url: str):
        try:
            import webbrowser
            webbrowser.open(url)
        except Exception:
            pass

    def open_download_tool_url(self):
        import webbrowser

        rel = getattr(self, "server_release_info", {}) or {}
        raw_url = str(rel.get("downloadUrl") or "/download-tool").strip()
        if raw_url.startswith("http://") or raw_url.startswith("https://"):
            target_url = raw_url
        else:
            path_part = raw_url if raw_url.startswith("/") else f"/{raw_url}"
            target_url = f"{self.get_base_server_url()}{path_part}"
        webbrowser.open(target_url)

    def _startup_version_check(self):
        """Kiểm tra phiên bản mới từ Server ngay khi mở Tool (ở màn hình Đăng nhập)."""
        try:
            res = requests.get(f"{self.get_api_endpoint()}?action=getInitialData", timeout=8)
            data = res.json()
            rel = data.get("appRelease") or (data.get("settings") or {}).get("appRelease")
            if rel and isinstance(rel, dict):
                self._check_server_version_and_prompt(rel)
        except Exception:
            pass

    def _check_server_version_and_prompt(self, rel_info: dict):
        if not rel_info or not isinstance(rel_info, dict):
            return
        self.server_release_info = {
            "latestVersion": str(rel_info.get("latestVersion") or APP_VERSION_NUMBER).strip().lstrip("vV"),
            "downloadUrl": str(rel_info.get("downloadUrl") or "/download-tool").strip(),
            "releaseNotes": str(rel_info.get("releaseNotes") or "").strip(),
            "forceUpdate": bool(rel_info.get("forceUpdate", False)),
        }
        srv_ver = self.server_release_info["latestVersion"]
        cur_tuple = parse_version_tuple(APP_VERSION_NUMBER)
        srv_tuple = parse_version_tuple(srv_ver)
        is_outdated = srv_tuple > cur_tuple

        def _update_ui_and_prompt():
            try:
                if is_outdated:
                    if hasattr(self, "login_ver_badge_btn"):
                        self.login_ver_badge_btn.configure(
                            text=f"🔔 Có bản mới v{srv_ver} (Bạn đang dùng v{APP_VERSION_NUMBER}) — Bấm để tải!",
                            bg="#f59e0b",
                            fg="#0b0e14",
                            highlightthickness=0,
                        )
                    if hasattr(self, "header_ver_badge_btn"):
                        self.header_ver_badge_btn.configure(
                            text=f"🚀 Cập nhật v{srv_ver} (Đang dùng v{APP_VERSION_NUMBER})",
                            bg="#f59e0b",
                            fg="#0b0e14",
                            highlightthickness=0,
                        )
                    if self._prompted_update_version != srv_ver:
                        self._prompted_update_version = srv_ver
                        notes = self.server_release_info["releaseNotes"]
                        notes_block = f"\n\n📝 Nội dung bản cập nhật:\n{notes}" if notes else ""
                        if self.server_release_info["forceUpdate"] and not self.is_admin:
                            self.messagebox.showwarning(
                                f"Yêu cầu cập nhật phiên bản mới v{srv_ver}",
                                f"Bạn đang sử dụng phiên bản cũ (v{APP_VERSION_NUMBER}).\n"
                                f"Hệ thống hiện yêu cầu cập nhật lên phiên bản mới nhất v{srv_ver} để tiếp tục sử dụng!{notes_block}\n\n"
                                f"Nhấn OK để mở trang tải bản cập nhật mới.",
                            )
                            self.open_download_tool_url()
                            if self.is_logged_in:
                                self.logout_to_login_screen()
                        else:
                            ans = self.messagebox.askyesno(
                                f"🔔 Phát hiện phiên bản mới v{srv_ver}",
                                f"Bạn đang sử dụng Tool phiên bản v{APP_VERSION_NUMBER}, hiện hệ thống đã có phiên bản mới v{srv_ver}!{notes_block}\n\n"
                                f"Bạn có muốn tải bản cập nhật v{srv_ver} ngay bây giờ không?\n"
                                f"(Chọn 'No' nếu bạn muốn tiếp tục sử dụng bản hiện tại)",
                            )
                            if ans:
                                self.open_download_tool_url()
                else:
                    if hasattr(self, "login_ver_badge_btn"):
                        self.login_ver_badge_btn.configure(
                            text=f"🏷️ Phiên bản hiện tại: v{APP_VERSION_NUMBER} (Bản mới nhất)",
                            bg="#1a2130",
                            fg="#34d399",
                            highlightthickness=1,
                            highlightbackground="#262f40",
                        )
                    if hasattr(self, "header_ver_badge_btn"):
                        self.header_ver_badge_btn.configure(
                            text=f"🏷️ Ver {APP_VERSION_NUMBER}",
                            bg="#1a2130",
                            fg="#34d399",
                            highlightthickness=1,
                            highlightbackground="#262f40",
                        )
            except Exception:
                pass

        self.root.after(0, _update_ui_and_prompt)

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
            if hasattr(self, "login_status_lbl"):
                self.login_status_lbl.configure(text="⚠️ Vui lòng nhập đầy đủ Tên Player và Mật khẩu!", fg="#f59e0b")
            self.messagebox.showwarning("Thiếu thông tin", "Vui lòng nhập Tên Player và Mật khẩu!")
            return

        if hasattr(self, "login_status_lbl"):
            self.login_status_lbl.configure(text="⏳ Đang xác thực tài khoản với máy chủ...", fg="#f59e0b")

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
                    if data.get("appRelease"):
                        self._check_server_version_and_prompt(data["appRelease"])

                    # Khi mới đăng nhập vào phiên làm việc mới trên Tool, tự động làm sạch bảng quân
                    # và kết thúc các kèo LIVE cũ còn treo từ phiên trước trước khi bật cờ is_logged_in cho luồng quét F2
                    self.current_match = None
                    self.scanner.last_dialog_signature = None
                    self._reset_battle_arena_ui()
                    try:
                        requests.post(
                            api_url,
                            json={
                                "action": "finishMatch",
                                "streamerName": canonical,
                                "updatedBy": canonical,
                                "password": self._get_effective_player_password(),
                                "isAdmin": self.is_admin,
                                "adminPassword": self.admin_password,
                            },
                            timeout=5,
                        )
                    except Exception:
                        pass

                    self.is_logged_in = True

                    status_prefix = "🛡️ ADMIN XO ĐÃ KẾT NỐI" if self.is_admin else f"🟢 Đã kết nối: {canonical}"
                    self.root.after(
                        0,
                        lambda: (
                            self.show_main_dashboard_screen(),
                            self.status_lbl.config(
                                text=f"{status_prefix} | Hạn: {exp_str}",
                                fg="#34d399",
                            ),
                            self.login_status_lbl.config(
                                text=f"✅ {status_prefix}",
                                fg="#34d399",
                            ),
                        ),
                    )
                    self.log(f"✅ {data.get('message', 'Kết nối thành công!')} (Máy chủ: {api_url})", "SUCCESS")
                    if self.is_admin:
                        self.log("🛡️ Đã mở khóa QUYỀN QUẢN TRỊ ADMIN XO! Bấm nút '🛡️ Quản Trị Admin' để tạo User & cấp VIP.", "SUCCESS")
                    self.refresh_initial_state()
                else:
                    self.is_logged_in = False
                    msg = data.get("message", "Đăng nhập thất bại!")
                    self.root.after(
                        0,
                        lambda: (
                            self.status_lbl.config(text=f"🔴 {msg}", fg="#f0657b"),
                            self.login_status_lbl.config(text=f"🔴 {msg}", fg="#f0657b"),
                        ),
                    )
                    self.log(f"❌ {msg}", "ERROR")
            except Exception as e:
                self.is_logged_in = False
                self.root.after(
                    0,
                    lambda: (
                        self.status_lbl.config(text="🔴 Không kết nối được Server!", fg="#f0657b"),
                        self.login_status_lbl.config(text=f"🔴 Không kết nối được Server ({api_url})", fg="#f0657b"),
                    ),
                )
                self.log(f"❌ Lỗi kết nối Server ({api_url}): {e}", "ERROR")

        threading.Thread(target=_task, daemon=True).start()

    def open_my_profile_window(self):
        tk = self.tk
        if not self.is_logged_in:
            self.messagebox.showinfo(
                "Thông tin tài khoản",
                "Vui lòng bấm '⚡ Kết nối & Lưu cấu hình' để đăng nhập tài khoản trước khi xem thông tin cá nhân!",
            )
            return

        win = tk.Toplevel(self.root)
        win.title(f"👤 THÔNG TIN TÀI KHOẢN CỦA TÔI — {self.player_name_var.get().strip()}")
        win.geometry("880x620")
        win.configure(bg="#0b0e14")

        hdr_card = tk.Frame(win, bg="#121721", highlightthickness=1, highlightbackground="#262f40", padx=18, pady=12)
        hdr_card.pack(fill="x", padx=14, pady=(12, 6))

        title_lbl = tk.Label(
            hdr_card,
            text=f"👤 Hồ sơ tài khoản: {self.player_name_var.get().strip()}",
            font=("Segoe UI", 13, "bold"),
            fg="#e7ebf0",
            bg="#121721",
        )
        title_lbl.pack(anchor="w")

        sub_lbl = tk.Label(
            hdr_card,
            text="Đang tải thông tin chi tiết từ máy chủ...",
            font=("Segoe UI", 9, "bold"),
            fg="#8e99a7",
            bg="#121721",
        )
        sub_lbl.pack(anchor="w", pady=(2, 0))

        # Lưới 4 thẻ thông tin chính
        stats_grid = tk.Frame(win, bg="#0b0e14")
        stats_grid.pack(fill="x", padx=14, pady=4)
        for c_i in range(4):
            stats_grid.columnconfigure(c_i, weight=1)

        def _make_stat_card(col_idx, title_txt, default_val, color_hex):
            box = tk.Frame(stats_grid, bg="#121721", highlightthickness=1, highlightbackground="#262f40", padx=12, pady=10)
            box.grid(row=0, column=col_idx, sticky="nsew", padx=(0 if col_idx == 0 else 5, 0 if col_idx == 3 else 5))
            tk.Label(box, text=title_txt, font=("Segoe UI", 8, "bold"), fg="#8e99a7", bg="#121721").pack(anchor="w")
            val_l = tk.Label(box, text=default_val, font=("Segoe UI", 11, "bold"), fg=color_hex, bg="#121721")
            val_l.pack(anchor="w", pady=(3, 0))
            return val_l

        lbl_tier_val = _make_stat_card(0, "HẠNG VIP & TRẠNG THÁI", "---", "#f59e0b")
        lbl_created_val = _make_stat_card(1, "NGÀY TẠO / KÍCH HOẠT", "---", "#e7ebf0")
        lbl_expires_val = _make_stat_card(2, "NGÀY HẾT HẠN SỬ DỤNG", "---", "#34d399")
        lbl_stars_val = _make_stat_card(3, "SỐ DƯ SAO & SAO LIVE", "---", "#f59e0b")

        # Thanh đổi mật khẩu cá nhân
        pwd_card = tk.Frame(win, bg="#121721", highlightthickness=1, highlightbackground="#262f40", padx=16, pady=10)
        pwd_card.pack(fill="x", padx=14, pady=5)

        note_info_lbl = tk.Label(
            pwd_card,
            text="Ghi chú tài khoản: ---",
            font=("Segoe UI", 9, "bold"),
            fg="#e7ebf0",
            bg="#121721",
        )
        note_info_lbl.pack(side="left")

        pwd_right = tk.Frame(pwd_card, bg="#121721")
        pwd_right.pack(side="right")
        tk.Label(pwd_right, text="Mật khẩu mới (≥8 ký tự):", font=("Segoe UI", 8, "bold"), fg="#8e99a7", bg="#121721").pack(side="left", padx=(0, 4))
        new_pw_var = tk.StringVar()
        tk.Entry(
            pwd_right,
            textvariable=new_pw_var,
            show="*",
            font=("Consolas", 9, "bold"),
            bg="#1a2130",
            fg="#e7ebf0",
            width=14,
            relief="flat",
            highlightthickness=1,
            highlightbackground="#262f40",
        ).pack(side="left", padx=(0, 8), ipady=3)

        tk.Label(pwd_right, text="Nhập lại:", font=("Segoe UI", 8, "bold"), fg="#8e99a7", bg="#121721").pack(side="left", padx=(0, 4))
        confirm_pw_var = tk.StringVar()
        tk.Entry(
            pwd_right,
            textvariable=confirm_pw_var,
            show="*",
            font=("Consolas", 9, "bold"),
            bg="#1a2130",
            fg="#e7ebf0",
            width=14,
            relief="flat",
            highlightthickness=1,
            highlightbackground="#262f40",
        ).pack(side="left", padx=(0, 8), ipady=3)

        def _change_my_pw():
            npw = new_pw_var.get().strip()
            cpw = confirm_pw_var.get().strip()
            if len(npw) < 8:
                self.messagebox.showwarning(
                    "Mật khẩu quá ngắn",
                    "Mật khẩu mới bắt buộc phải có tối thiểu 8 ký tự!",
                    parent=win,
                )
                return
            if npw != cpw:
                self.messagebox.showwarning(
                    "Không trùng khớp",
                    "Mật khẩu xác nhận (lần 2) không trùng khớp với mật khẩu mới! Vui lòng kiểm tra lại.",
                    parent=win,
                )
                return

            def _t():
                try:
                    res = requests.post(
                        self.get_api_endpoint(),
                        json={
                            "action": "userChangePassword",
                            "playerName": self.player_name_var.get().strip(),
                            "oldPassword": self._get_effective_player_password(),
                            "newPassword": npw,
                            "confirmPassword": cpw,
                        },
                        timeout=10,
                    )
                    d = res.json()
                    if d.get("status") == "success":
                        self.root.after(0, lambda: self.player_pass_var.set(npw))
                        self.root.after(0, self.save_current_config)
                        win.after(0, lambda: (new_pw_var.set(""), confirm_pw_var.set("")))
                        win.after(0, lambda: self.messagebox.showinfo("Thành công", d.get("message", "Đã đổi mật khẩu!"), parent=win))
                        _load_profile()
                    else:
                        win.after(0, lambda: self.messagebox.showerror("Lỗi", d.get("message", "Không thể đổi mật khẩu"), parent=win))
                except Exception as e:
                    win.after(0, lambda: self.messagebox.showerror("Lỗi kết nối", str(e), parent=win))

            threading.Thread(target=_t, daemon=True).start()

        tk.Button(
            pwd_right,
            text="🔑 Đổi mật khẩu",
            command=_change_my_pw,
            font=("Segoe UI", 9, "bold"),
            bg="#f59e0b",
            fg="#0b0e14",
            relief="flat",
            padx=12,
            pady=3,
            cursor="hand2",
        ).pack(side="left")

        # 2 Khung lịch sử: Lịch sử Nạp Sao & Lịch sử Gia Hạn VIP
        hist_split = tk.Frame(win, bg="#0b0e14")
        hist_split.pack(fill="both", expand=True, padx=14, pady=(4, 12))
        hist_split.columnconfigure(0, weight=1)
        hist_split.columnconfigure(1, weight=1)
        hist_split.rowconfigure(0, weight=1)

        star_card = tk.Frame(hist_split, bg="#121721", highlightthickness=1, highlightbackground="#262f40", padx=12, pady=10)
        star_card.grid(row=0, column=0, sticky="nsew", padx=(0, 6))
        tk.Label(
            star_card,
            text="🌟 Lịch sử Nạp Sao & Tặng/Nhận Sao",
            font=("Segoe UI", 9, "bold"),
            fg="#f59e0b",
            bg="#121721",
        ).pack(anchor="w", pady=(0, 6))
        star_txt_wrap = tk.Frame(star_card, bg="#121721")
        star_txt_wrap.pack(fill="both", expand=True)
        star_txt = tk.Text(star_txt_wrap, bg="#1a2130", fg="#e7ebf0", font=("Consolas", 9), relief="flat", padx=8, pady=6, state="disabled", highlightthickness=1, highlightbackground="#262f40")
        star_txt_sb = self._make_dark_scrollbar(star_txt_wrap, "vertical", command=star_txt.yview)
        star_txt.configure(yscrollcommand=star_txt_sb.set)
        star_txt_sb.pack(side="right", fill="y")
        star_txt.pack(side="left", fill="both", expand=True)

        vip_card_h = tk.Frame(hist_split, bg="#121721", highlightthickness=1, highlightbackground="#262f40", padx=12, pady=10)
        vip_card_h.grid(row=0, column=1, sticky="nsew", padx=(6, 0))
        tk.Label(
            vip_card_h,
            text="👑 Lịch sử Gia hạn VIP & Biến động tài khoản",
            font=("Segoe UI", 9, "bold"),
            fg="#e7ebf0",
            bg="#121721",
        ).pack(anchor="w", pady=(0, 6))
        vip_txt_wrap = tk.Frame(vip_card_h, bg="#121721")
        vip_txt_wrap.pack(fill="both", expand=True)
        vip_txt = tk.Text(vip_txt_wrap, bg="#1a2130", fg="#e7ebf0", font=("Consolas", 9), relief="flat", padx=8, pady=6, state="disabled", highlightthickness=1, highlightbackground="#262f40")
        vip_txt_sb = self._make_dark_scrollbar(vip_txt_wrap, "vertical", command=vip_txt.yview)
        vip_txt.configure(yscrollcommand=vip_txt_sb.set)
        vip_txt_sb.pack(side="right", fill="y")
        vip_txt.pack(side="left", fill="both", expand=True)

        def _load_profile():
            def _t():
                try:
                    res = requests.post(
                        self.get_api_endpoint(),
                        json={
                            "action": "getPlayerProfile",
                            "playerName": self.player_name_var.get().strip(),
                            "password": self._get_effective_player_password(),
                            "isAdmin": self.is_admin,
                            "adminPassword": self.admin_password,
                        },
                        timeout=10,
                    )
                    d = res.json()
                    if d.get("status") != "success" or not d.get("profile"):
                        win.after(0, lambda: sub_lbl.config(text=f"⚠️ {d.get('message', 'Không tải được hồ sơ')}", fg="#f0657b"))
                        return
                    prof = d["profile"]

                    def _render_prof():
                        t_vi = prof.get("tierNameVi") or prof.get("tier") or "Hạng Đồng"
                        act_str = "🟢 Active" if prof.get("isActive", True) else "🔴 Tạm khóa"
                        c_fmt = prof.get("createdFormatted") or "---"
                        a_fmt = prof.get("activatedFormatted") or "---"
                        e_fmt = prof.get("expiresFormatted") or "♾️ Vĩnh viễn"
                        d_left = prof.get("daysLeft")
                        exp_full = f"{e_fmt} (Còn {d_left} ngày)" if d_left is not None else e_fmt
                        bal_s = prof.get("starsBalance") or 0
                        rcv_s = prof.get("starsReceived") or 0
                        fr_cnt = len(prof.get("friends") or [])

                        sub_lbl.config(
                            text=f"Tài khoản: {prof.get('name')}  •  Bạn bè đã kết nối: {fr_cnt} người  •  Cập nhật lúc {time.strftime('%H:%M:%S')}",
                            fg="#34d399",
                        )
                        lbl_tier_val.config(text=f"{t_vi}\n({act_str})")
                        lbl_created_val.config(text=f"Tạo: {c_fmt}\nKích hoạt: {a_fmt}")
                        lbl_expires_val.config(text=exp_full)
                        lbl_stars_val.config(text=f"💰 Số dư: {bal_s} ⭐\n🎁 Nhận Live: {rcv_s} ⭐")
                        note_info_lbl.config(text=f"Ghi chú: {prof.get('note') or 'Tài khoản thành viên chính thức'}")

                        star_txt.configure(state="normal")
                        star_txt.delete("1.0", "end")
                        s_hist = list(reversed(prof.get("starHistory") or []))
                        if not s_hist:
                            star_txt.insert("end", "Chưa có lịch sử nạp Sao hoặc tặng/nhận Sao.\n")
                        else:
                            for item in s_hist:
                                amt = item.get("amount", 0)
                                sign = f"+{amt}" if amt > 0 else str(amt)
                                star_txt.insert(
                                    "end",
                                    f"[{item.get('formattedTime', '')}] {sign} ⭐ | {item.get('note', '')}\n",
                                )
                        star_txt.configure(state="disabled")

                        vip_txt.configure(state="normal")
                        vip_txt.delete("1.0", "end")
                        v_hist = list(reversed(prof.get("vipHistory") or []))
                        if not v_hist:
                            vip_txt.insert("end", "Chưa có lịch sử gia hạn VIP.\n")
                        else:
                            for item in v_hist:
                                vip_txt.insert(
                                    "end",
                                    f"[{item.get('formattedTime', '')}] [{item.get('tier', '')}] {item.get('note', '')}\n",
                                )
                        vip_txt.configure(state="disabled")

                    win.after(0, _render_prof)
                except Exception as e:
                    win.after(0, lambda e=e: sub_lbl.config(text=f"❌ Lỗi tải thông tin: {e}", fg="#f0657b"))

            threading.Thread(target=_t, daemon=True).start()

        _load_profile()

    def open_admin_manager_window(self):
        tk = self.tk
        ttk = self.ttk
        from tkinter import simpledialog

        # Nếu đã nhập mật khẩu 00716441516 ở ô Mật khẩu chính thì tự động mở khóa Admin luôn
        if self.player_pass_var.get().strip() == "00716441516":
            self.is_admin = True
            self.admin_password = "00716441516"

        if not self.is_admin:
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
        win.title("⚙ Bảng Quản Trị Admin XO — Quản lý Phiên bản Tool, Chỉnh sửa User, Tìm kiếm & VIP")
        win.geometry("1140x810")
        win.configure(bg="#0b0e14")

        selected_orig_name = {"val": ""}

        # ======================================================================
        # 0. QUẢN LÝ PHIÊN BẢN TOOL PC & LINK TẢI CÀI ĐẶT (BÁO CẬP NHẬT CHO USER)
        # ======================================================================
        rel_card = tk.Frame(win, bg="#121721", highlightthickness=1, highlightbackground="#262f40", padx=14, pady=8)
        rel_card.pack(fill="x", padx=14, pady=(10, 4))

        tk.Label(
            rel_card,
            text="🚀 Phiên bản mới:",
            font=("Segoe UI", 9, "bold"),
            fg="#f59e0b",
            bg="#121721",
        ).pack(side="left")
        rel_ver_var = tk.StringVar(value=str(self.server_release_info.get("latestVersion") or APP_VERSION_NUMBER))
        tk.Entry(
            rel_card,
            textvariable=rel_ver_var,
            font=("Consolas", 9, "bold"),
            bg="#1a2130",
            fg="#f59e0b",
            width=7,
            justify="center",
            relief="flat",
            highlightthickness=1,
            highlightbackground="#262f40",
        ).pack(side="left", padx=(4, 10), ipady=3)

        tk.Label(
            rel_card,
            text="Link tải (.exe/.zip):",
            font=("Segoe UI", 9, "bold"),
            fg="#8e99a7",
            bg="#121721",
        ).pack(side="left")
        rel_url_var = tk.StringVar(value=str(self.server_release_info.get("downloadUrl") or "/download-tool"))
        tk.Entry(
            rel_card,
            textvariable=rel_url_var,
            font=("Consolas", 9),
            bg="#1a2130",
            fg="#e7ebf0",
            width=30,
            relief="flat",
            highlightthickness=1,
            highlightbackground="#262f40",
        ).pack(side="left", padx=(4, 10), ipady=3)

        tk.Label(
            rel_card,
            text="Thông báo Update:",
            font=("Segoe UI", 9, "bold"),
            fg="#8e99a7",
            bg="#121721",
        ).pack(side="left")
        rel_notes_var = tk.StringVar(value=str(self.server_release_info.get("releaseNotes") or ""))
        tk.Entry(
            rel_card,
            textvariable=rel_notes_var,
            font=("Segoe UI", 9),
            bg="#1a2130",
            fg="#e7ebf0",
            relief="flat",
            highlightthickness=1,
            highlightbackground="#262f40",
        ).pack(side="left", padx=(4, 10), ipady=3, fill="x", expand=True)

        rel_force_var = tk.BooleanVar(value=bool(self.server_release_info.get("forceUpdate", False)))
        tk.Checkbutton(
            rel_card,
            text="Bắt buộc Update",
            variable=rel_force_var,
            font=("Segoe UI", 8, "bold"),
            fg="#e7ebf0",
            bg="#121721",
            selectcolor="#1a2130",
            activebackground="#121721",
            activeforeground="#f59e0b",
        ).pack(side="left", padx=(0, 8))

        def _save_release_cfg():
            def _t():
                try:
                    res = requests.post(
                        self.get_api_endpoint(),
                        json={
                            "action": "adminUpdateReleaseConfig",
                            "isAdmin": True,
                            "adminPassword": self.admin_password,
                            "latestVersion": rel_ver_var.get().strip(),
                            "downloadUrl": rel_url_var.get().strip(),
                            "releaseNotes": rel_notes_var.get().strip(),
                            "forceUpdate": bool(rel_force_var.get()),
                        },
                        timeout=10,
                    )
                    d = res.json()
                    if d.get("status") == "success":
                        if d.get("appRelease"):
                            self._check_server_version_and_prompt(d["appRelease"])
                        win.after(0, lambda: status_bar_lbl.config(text=f"✅ {d.get('message', 'Đã lưu cấu hình Phiên bản & Link tải!')}", fg="#34d399"))
                    else:
                        win.after(0, lambda: status_bar_lbl.config(text=f"⚠️ {d.get('message', 'Lỗi lưu phiên bản')}", fg="#f59e0b"))
                except Exception as e:
                    win.after(0, lambda e=e: status_bar_lbl.config(text=f"❌ Lỗi: {e}", fg="#f0657b"))

            threading.Thread(target=_t, daemon=True).start()

        tk.Button(
            rel_card,
            text="💾 Lưu Phiên Bản",
            command=_save_release_cfg,
            font=("Segoe UI", 9, "bold"),
            bg="#f59e0b",
            fg="#0b0e14",
            relief="flat",
            padx=12,
            pady=3,
            cursor="hand2",
        ).pack(side="right")

        # ======================================================================
        # 0B. DỌN DẸP & XÓA LỊCH SỬ KÈO ĐẤU (1 TUẦN, 1 THÁNG, TÙY CHỈNH, TẤT CẢ)
        # ======================================================================
        hist_clean_card = tk.Frame(win, bg="#121721", highlightthickness=1, highlightbackground="#262f40", padx=14, pady=8)
        hist_clean_card.pack(fill="x", padx=14, pady=(2, 4))

        tk.Label(
            hist_clean_card,
            text="🗑️ Xóa lịch sử đấu:",
            font=("Segoe UI", 9, "bold"),
            fg="#f0657b",
            bg="#121721",
        ).pack(side="left")

        cleanup_mode_options = [
            "Cũ hơn 1 tuần trước (> 7 ngày)",
            "Cũ hơn 1 tháng trước (> 30 ngày)",
            "Tất cả kèo đã kết thúc (Giữ kèo đang LIVE)",
            "Kèo trống / 0 trận / Chưa có tỉ số",
            "Tùy chỉnh: Cũ hơn số ngày nhập bên cạnh",
            "Tùy chỉnh: Theo tên Streamer nhập bên cạnh",
            "🔥 Xóa TẤT CẢ lịch sử kèo đấu",
        ]
        cleanup_mode_var = tk.StringVar(value=cleanup_mode_options[0])
        cleanup_cb = ttk.Combobox(
            hist_clean_card,
            textvariable=cleanup_mode_var,
            values=cleanup_mode_options,
            state="readonly",
            width=36,
            style="Premium.TCombobox",
        )
        cleanup_cb.pack(side="left", padx=(6, 10))

        tk.Label(
            hist_clean_card,
            text="Giá trị tùy chỉnh (Số ngày / Tên Streamer):",
            font=("Segoe UI", 8, "bold"),
            fg="#8e99a7",
            bg="#121721",
        ).pack(side="left")
        cleanup_param_var = tk.StringVar(value="14")
        tk.Entry(
            hist_clean_card,
            textvariable=cleanup_param_var,
            font=("Consolas", 9, "bold"),
            bg="#1a2130",
            fg="#f59e0b",
            width=12,
            justify="center",
            relief="flat",
            highlightthickness=1,
            highlightbackground="#262f40",
        ).pack(side="left", padx=(4, 10), ipady=3)

        keep_live_var = tk.BooleanVar(value=True)
        tk.Checkbutton(
            hist_clean_card,
            text="Giữ lại kèo đang LIVE",
            variable=keep_live_var,
            font=("Segoe UI", 8, "bold"),
            fg="#e7ebf0",
            bg="#121721",
            selectcolor="#1a2130",
            activebackground="#121721",
            activeforeground="#f59e0b",
        ).pack(side="left", padx=(0, 8))

        def _exec_cleanup_history(quick_mode=None, quick_days=None):
            sel_label = cleanup_mode_var.get()
            raw_param = cleanup_param_var.get().strip()
            keep_live = bool(keep_live_var.get())

            if quick_mode:
                mode = quick_mode
                days = quick_days or 7
                streamer_filter = ""
            elif "1 tuần" in sel_label:
                mode, days, streamer_filter = "OLDER_THAN_DAYS", 7, ""
            elif "1 tháng" in sel_label:
                mode, days, streamer_filter = "OLDER_THAN_DAYS", 30, ""
            elif "đã kết thúc" in sel_label:
                mode, days, streamer_filter = "FINISHED_ONLY", 0, ""
            elif "Kèo trống" in sel_label:
                mode, days, streamer_filter = "EMPTY_MATCHES", 0, ""
            elif "số ngày nhập" in sel_label:
                try:
                    days = max(1, int(raw_param or "7"))
                except Exception:
                    self.messagebox.showwarning("Số ngày không hợp lệ", "Vui lòng nhập số ngày hợp lệ (VD: 3, 14, 60)!", parent=win)
                    return
                mode, streamer_filter = "OLDER_THAN_DAYS", ""
            elif "tên Streamer" in sel_label:
                if not raw_param:
                    self.messagebox.showwarning("Thiếu tên Streamer", "Vui lòng nhập tên Streamer cần xóa lịch sử vào ô bên cạnh!", parent=win)
                    return
                mode, days, streamer_filter = "BY_STREAMER", 0, raw_param
            else:
                mode, days, streamer_filter = "ALL", 0, ""

            confirm_msg = f"Bạn có chắc chắn muốn thực hiện: [{sel_label if not quick_mode else quick_mode}] không?\n(Hành động này không thể hoàn tác)"
            if not self.messagebox.askyesno("Xác nhận xóa lịch sử đấu", confirm_msg, parent=win):
                return

            def _t():
                try:
                    res = requests.post(
                        self.get_api_endpoint(),
                        json={
                            "action": "adminCleanupMatchHistory",
                            "isAdmin": True,
                            "adminPassword": self.admin_password,
                            "mode": mode,
                            "days": days,
                            "streamerName": streamer_filter,
                            "keepLive": keep_live,
                        },
                        timeout=12,
                    )
                    d = res.json()
                    if d.get("status") == "success":
                        msg = d.get("message", "Đã xóa lịch sử kèo đấu!")
                        win.after(0, lambda: status_bar_lbl.config(text=f"✅ {msg}", fg="#34d399"))
                        self.log(f"✅ {msg}", "SUCCESS")
                        self.refresh_initial_state()
                    else:
                        win.after(0, lambda: status_bar_lbl.config(text=f"⚠️ {d.get('message', 'Lỗi xóa lịch sử')}", fg="#f59e0b"))
                except Exception as e:
                    win.after(0, lambda e=e: status_bar_lbl.config(text=f"❌ Lỗi xóa lịch sử: {e}", fg="#f0657b"))

            threading.Thread(target=_t, daemon=True).start()

        tk.Button(
            hist_clean_card,
            text="🗑️ Xóa Lịch Sử Đấu",
            command=_exec_cleanup_history,
            font=("Segoe UI", 9, "bold"),
            bg="#1a2130",
            fg="#f0657b",
            relief="flat",
            highlightthickness=1,
            highlightbackground="#c94a61",
            padx=12,
            pady=3,
            cursor="hand2",
        ).pack(side="right")

        # ======================================================================
        # 1. FORM TẠO MỚI / CHỈNH SỬA ĐẦY ĐỦ THÔNG TIN USER (NGÀY TẠO, NGÀY HẾT HẠN, MẬT KHẨU, SAO)
        # ======================================================================
        top_card = tk.Frame(win, bg="#121721", highlightthickness=1, highlightbackground="#262f40", padx=14, pady=10)
        top_card.pack(fill="x", padx=14, pady=(2, 4))

        hdr_row = tk.Frame(top_card, bg="#121721")
        hdr_row.pack(fill="x", pady=(0, 6))
        form_mode_lbl = tk.Label(
            hdr_row,
            text="⚙ Quản trị User & Gia hạn VIP (Chọn 1 User dưới bảng để sửa hoặc tạo mới)",
            font=("Segoe UI", 10, "bold"),
            fg="#e7ebf0",
            bg="#121721",
        )
        form_mode_lbl.pack(side="left")

        # Hàng 1 của Form: Tên Player, Mật khẩu, Hạng VIP, Số dư Sao, Ghi chú
        form_row1 = tk.Frame(top_card, bg="#121721")
        form_row1.pack(fill="x", pady=2)

        tk.Label(form_row1, text="Tên Player:", font=("Segoe UI", 9, "bold"), fg="#8e99a7", bg="#121721").pack(side="left")
        u_name_var = tk.StringVar()
        tk.Entry(form_row1, textvariable=u_name_var, font=("Segoe UI", 9, "bold"), bg="#1a2130", fg="#e7ebf0", width=13, relief="flat", highlightthickness=1, highlightbackground="#262f40").pack(side="left", padx=(4, 10), ipady=3)

        tk.Label(form_row1, text="Mật khẩu:", font=("Segoe UI", 9, "bold"), fg="#8e99a7", bg="#121721").pack(side="left")
        u_pass_var = tk.StringVar(value="123")
        tk.Entry(form_row1, textvariable=u_pass_var, show="*", font=("Consolas", 9, "bold"), bg="#1a2130", fg="#e7ebf0", width=10, relief="flat", highlightthickness=1, highlightbackground="#262f40").pack(side="left", padx=(4, 10), ipady=3)

        tk.Label(form_row1, text="Hạng VIP:", font=("Segoe UI", 9, "bold"), fg="#8e99a7", bg="#121721").pack(side="left")
        u_tier_var = tk.StringVar(value="GOLD")
        tier_cb = ttk.Combobox(
            form_row1,
            textvariable=u_tier_var,
            values=["DIAMOND", "GOLD", "SILVER", "BRONZE"],
            state="readonly",
            width=10,
            style="Premium.TCombobox",
        )
        tier_cb.pack(side="left", padx=(4, 10))

        tk.Label(form_row1, text="Số dư Sao:", font=("Segoe UI", 9, "bold"), fg="#8e99a7", bg="#121721").pack(side="left")
        u_stars_var = tk.StringVar(value="0")
        tk.Entry(form_row1, textvariable=u_stars_var, font=("Consolas", 9, "bold"), bg="#1a2130", fg="#f59e0b", width=8, justify="center", relief="flat", highlightthickness=1, highlightbackground="#262f40").pack(side="left", padx=(4, 10), ipady=3)

        tk.Label(form_row1, text="Ghi chú:", font=("Segoe UI", 9, "bold"), fg="#8e99a7", bg="#121721").pack(side="left")
        u_note_var = tk.StringVar()
        tk.Entry(form_row1, textvariable=u_note_var, font=("Segoe UI", 9), bg="#1a2130", fg="#e7ebf0", width=18, relief="flat", highlightthickness=1, highlightbackground="#262f40").pack(side="left", padx=(4, 0), ipady=3, fill="x", expand=True)

        # Hàng 2 của Form: Ngày tạo TK, Ngày hết hạn (DD/MM/YYYY), Hoặc +Số ngày hạn SD (dạng lưới thẳng hàng)
        form_row2 = tk.Frame(top_card, bg="#121721")
        form_row2.pack(fill="x", pady=(6, 2))
        for c_i, c_w in enumerate((0, 1, 0, 1, 0, 1)):
            form_row2.columnconfigure(c_i, weight=c_w)

        tk.Label(form_row2, text="Ngày tạo TK (DD/MM/YYYY):", font=("Segoe UI", 9, "bold"), fg="#8e99a7", bg="#121721").grid(row=0, column=0, sticky="w")
        u_created_var = tk.StringVar(value=time.strftime("%d/%m/%Y"))
        tk.Entry(form_row2, textvariable=u_created_var, font=("Consolas", 9, "bold"), bg="#1a2130", fg="#e7ebf0", width=12, justify="center", relief="flat", highlightthickness=1, highlightbackground="#262f40").grid(row=0, column=1, sticky="ew", padx=(6, 14), ipady=3)

        tk.Label(form_row2, text="Ngày hết hạn (DD/MM/YYYY hoặc Vĩnh viễn):", font=("Segoe UI", 9, "bold"), fg="#8e99a7", bg="#121721").grid(row=0, column=2, sticky="w")
        u_expires_var = tk.StringVar(value="")
        tk.Entry(form_row2, textvariable=u_expires_var, font=("Consolas", 9, "bold"), bg="#1a2130", fg="#34d399", width=13, justify="center", relief="flat", highlightthickness=1, highlightbackground="#262f40").grid(row=0, column=3, sticky="ew", padx=(6, 14), ipady=3)

        tk.Label(form_row2, text="Hoặc đặt số ngày (0=Vĩnh viễn):", font=("Segoe UI", 9, "bold"), fg="#8e99a7", bg="#121721").grid(row=0, column=4, sticky="w")
        u_days_var = tk.StringVar(value="30")
        tk.Entry(form_row2, textvariable=u_days_var, font=("Consolas", 9, "bold"), bg="#1a2130", fg="#f59e0b", width=6, justify="center", relief="flat", highlightthickness=1, highlightbackground="#262f40").grid(row=0, column=5, sticky="ew", padx=(6, 0), ipady=3)

        # Hàng nút của Form (tách riêng để nút '💾 Lưu / Cập Nhật User' luôn hiển thị trọn vẹn, không bị bóp chữ)
        form_btn_row = tk.Frame(top_card, bg="#121721")
        form_btn_row.pack(fill="x", pady=(8, 0))

        def _clear_form():
            selected_orig_name["val"] = ""
            u_name_var.set("")
            u_pass_var.set("123")
            u_tier_var.set("GOLD")
            u_stars_var.set("0")
            u_created_var.set(time.strftime("%d/%m/%Y"))
            u_expires_var.set("")
            u_days_var.set("30")
            u_note_var.set("")
            form_mode_lbl.config(text="⚙ Chế độ: Tạo tài khoản User mới", fg="#e7ebf0")
            for s in tree.selection():
                tree.selection_remove(s)

        tk.Button(
            form_btn_row,
            text="🧹 Tạo Mới (Xóa form)",
            command=_clear_form,
            font=("Segoe UI", 9, "bold"),
            bg="#1a2130",
            fg="#e7ebf0",
            activebackground="#243047",
            activeforeground="#ffffff",
            relief="flat",
            highlightthickness=1,
            highlightbackground="#262f40",
            width=20,
            padx=10,
            pady=3,
            cursor="hand2",
        ).pack(side="right", padx=(8, 0))

        # ======================================================================
        # 2. THANH SEARCH TÌM KIẾM NHANH USER & BỘ LỌC HẠNG VIP
        # ======================================================================
        search_card = tk.Frame(win, bg="#121721", highlightthickness=1, highlightbackground="#262f40", padx=14, pady=8)
        search_card.pack(fill="x", padx=14, pady=4)

        tk.Label(search_card, text="🔍 Tìm kiếm nhanh User:", font=("Segoe UI", 9, "bold"), fg="#e7ebf0", bg="#121721").pack(side="left")
        search_var = tk.StringVar()
        search_entry = tk.Entry(
            search_card,
            textvariable=search_var,
            font=("Segoe UI", 9),
            bg="#1a2130",
            fg="#e7ebf0",
            insertbackground="#f59e0b",
            width=32,
            relief="flat",
            highlightthickness=1,
            highlightbackground="#262f40",
        )
        search_entry.pack(side="left", padx=(6, 12), ipady=3)

        tk.Label(search_card, text="Lọc Hạng VIP:", font=("Segoe UI", 9, "bold"), fg="#8e99a7", bg="#121721").pack(side="left")
        filter_tier_var = tk.StringVar(value="ALL")
        filter_tier_cb = ttk.Combobox(
            search_card,
            textvariable=filter_tier_var,
            values=["ALL", "DIAMOND", "GOLD", "SILVER", "BRONZE"],
            state="readonly",
            width=10,
            style="Premium.TCombobox",
        )
        filter_tier_cb.pack(side="left", padx=(6, 12))

        count_badge_lbl = tk.Label(
            search_card,
            text="Tổng: 0 User",
            font=("Segoe UI", 9, "bold"),
            fg="#f59e0b",
            bg="#121721",
        )
        count_badge_lbl.pack(side="right")

        # ======================================================================
        # 3. BẢNG DANH SÁCH USER (TREEVIEW)
        # ======================================================================
        list_card = tk.Frame(win, bg="#121721", highlightthickness=1, highlightbackground="#262f40", padx=14, pady=8)
        list_card.pack(fill="both", expand=True, padx=14, pady=4)

        cols = ("name", "password", "tier", "status", "created", "expires", "stars", "note")
        tree = ttk.Treeview(list_card, columns=cols, show="headings", height=6)
        tree.heading("name", text="Tên Player")
        tree.heading("password", text="Mật khẩu")
        tree.heading("tier", text="Hạng VIP")
        tree.heading("status", text="Trạng thái")
        tree.heading("created", text="Ngày tạo TK")
        tree.heading("expires", text="Ngày hết hạn")
        tree.heading("stars", text="Số dư Sao / Nhận Live")
        tree.heading("note", text="Ghi chú")

        tree.column("name", width=120, anchor="w")
        tree.column("password", width=80, anchor="center")
        tree.column("tier", width=115, anchor="center")
        tree.column("status", width=95, anchor="center")
        tree.column("created", width=95, anchor="center")
        tree.column("expires", width=115, anchor="center")
        tree.column("stars", width=140, anchor="center")
        tree.column("note", width=210, anchor="w")
        tree_scroll = self._make_dark_scrollbar(list_card, "vertical", command=tree.yview)
        tree.configure(yscrollcommand=tree_scroll.set)
        tree.tag_configure("evenrow", background="#0f1726", foreground="#e2e8f0")
        tree.tag_configure("oddrow", background="#141f33", foreground="#f1f5f9")
        tree_scroll.pack(side="right", fill="y")
        tree.pack(fill="both", expand=True)

        # ======================================================================
        # 4. KHUNG XEM LỊCH SỬ NẠP SAO & LỊCH SỬ GIA HẠN VIP CỦA USER ĐANG CHỌN
        # ======================================================================
        hist_frame = tk.Frame(win, bg="#0b0e14")
        hist_frame.columnconfigure(0, weight=1)
        hist_frame.columnconfigure(1, weight=1)

        star_hist_card = tk.Frame(hist_frame, bg="#121721", highlightthickness=1, highlightbackground="#262f40", padx=10, pady=6)
        star_hist_card.grid(row=0, column=0, sticky="nsew", padx=(0, 5))
        star_hist_title = tk.Label(star_hist_card, text="🌟 Lịch sử Nạp Sao & Giao dịch Sao (Chọn User để xem)", font=("Segoe UI", 9, "bold"), fg="#f59e0b", bg="#121721")
        star_hist_title.pack(anchor="w", pady=(0, 4))
        star_hist_wrap = tk.Frame(star_hist_card, bg="#121721")
        star_hist_wrap.pack(fill="x")
        star_hist_box = tk.Text(star_hist_wrap, bg="#1a2130", fg="#e7ebf0", font=("Consolas", 8), height=5, relief="flat", padx=6, pady=4, state="disabled", highlightthickness=1, highlightbackground="#262f40")
        star_hist_sb = self._make_dark_scrollbar(star_hist_wrap, "vertical", command=star_hist_box.yview)
        star_hist_box.configure(yscrollcommand=star_hist_sb.set)
        star_hist_sb.pack(side="right", fill="y")
        star_hist_box.pack(side="left", fill="x", expand=True)

        vip_hist_card = tk.Frame(hist_frame, bg="#121721", highlightthickness=1, highlightbackground="#262f40", padx=10, pady=6)
        vip_hist_card.grid(row=0, column=1, sticky="nsew", padx=(5, 0))
        vip_hist_title = tk.Label(vip_hist_card, text="👑 Lịch sử Gia hạn VIP & Thay đổi gói (Chọn User để xem)", font=("Segoe UI", 9, "bold"), fg="#e7ebf0", bg="#121721")
        vip_hist_title.pack(anchor="w", pady=(0, 4))
        vip_hist_wrap = tk.Frame(vip_hist_card, bg="#121721")
        vip_hist_wrap.pack(fill="x")
        vip_hist_box = tk.Text(vip_hist_wrap, bg="#1a2130", fg="#e7ebf0", font=("Consolas", 8), height=5, relief="flat", padx=6, pady=4, state="disabled", highlightthickness=1, highlightbackground="#262f40")
        vip_hist_sb = self._make_dark_scrollbar(vip_hist_wrap, "vertical", command=vip_hist_box.yview)
        vip_hist_box.configure(yscrollcommand=vip_hist_sb.set)
        vip_hist_sb.pack(side="right", fill="y")
        vip_hist_box.pack(side="left", fill="x", expand=True)

        status_bar_lbl = tk.Label(win, text="Đang tải danh sách tài khoản...", font=("Segoe UI", 9, "bold"), fg="#f59e0b", bg="#0b0e14", anchor="w")

        def _fmt_date(ts):
            if not ts or int(ts) <= 0:
                return "♾️ Vĩnh viễn"
            return time.strftime("%d/%m/%Y", time.localtime(int(ts) / 1000))

        def _render_user_histories(p):
            star_hist_box.configure(state="normal")
            star_hist_box.delete("1.0", "end")
            vip_hist_box.configure(state="normal")
            vip_hist_box.delete("1.0", "end")

            if not p:
                star_hist_title.config(text="🌟 Lịch sử Nạp Sao & Giao dịch Sao (Chọn User để xem)")
                vip_hist_title.config(text="👑 Lịch sử Gia hạn VIP & Thay đổi gói (Chọn User để xem)")
                star_hist_box.insert("end", "Hãy click chọn 1 User trên bảng danh sách để xem lịch sử nạp Sao.\n")
                vip_hist_box.insert("end", "Hãy click chọn 1 User trên bảng danh sách để xem lịch sử gia hạn VIP.\n")
            else:
                uname = p.get("name", "")
                s_hist = list(reversed(p.get("starHistory") or []))
                v_hist = list(reversed(p.get("vipHistory") or []))
                star_hist_title.config(text=f"🌟 Lịch sử Nạp Sao & Giao dịch Sao của '{uname}' ({len(s_hist)} mục)")
                vip_hist_title.config(text=f"👑 Lịch sử Gia hạn VIP & Thay đổi của '{uname}' ({len(v_hist)} mục)")

                if not s_hist:
                    star_hist_box.insert("end", f"User '{uname}' chưa có lịch sử nạp Sao.\n")
                else:
                    for item in s_hist:
                        amt = item.get("amount", 0)
                        sign = f"+{amt}" if amt > 0 else str(amt)
                        star_hist_box.insert("end", f"[{item.get('formattedTime', '')}] {sign} ⭐ | {item.get('note', '')}\n")

                if not v_hist:
                    vip_hist_box.insert("end", f"User '{uname}' chưa có lịch sử gia hạn VIP.\n")
                else:
                    for item in v_hist:
                        vip_hist_box.insert("end", f"[{item.get('formattedTime', '')}] [{item.get('tier', '')}] {item.get('note', '')}\n")

            star_hist_box.configure(state="disabled")
            vip_hist_box.configure(state="disabled")

        def _filter_and_populate_tree():
            q = search_var.get().strip().lower()
            ft = filter_tier_var.get().strip().upper()
            for item in tree.get_children():
                tree.delete(item)

            shown = 0
            for p in self.known_players:
                t_code = str(p.get("tier") or "BRONZE").upper()
                if ft != "ALL" and t_code != ft:
                    continue
                pname = str(p.get("name", ""))
                pnote = str(p.get("note", ""))
                t_label = TIER_BADGES.get(t_code, (t_code,))[0]
                if q and (q not in pname.lower()) and (q not in pnote.lower()) and (q not in t_code.lower()) and (q not in t_label.lower()):
                    continue

                shown += 1
                is_act = p.get("isActive", True)
                exp_ts = p.get("expiresAt")
                is_exp = bool(exp_ts and int(exp_ts) > 0 and (time.time() * 1000 > int(exp_ts)))
                st_txt = "🔴 Đã khóa" if not is_act else ("⚠️ Hết hạn" if is_exp else "🟢 Active")
                raw_pwd_str = str(p.get("password", "") or "")
                masked_pwd = "*" * max(6, len(raw_pwd_str))
                bal_s = p.get("starsBalance") or 0
                rcv_s = p.get("starsReceived") or 0
                row_tag = "evenrow" if (shown % 2 == 0) else "oddrow"
                tree.insert(
                    "",
                    "end",
                    iid=pname,
                    tags=(row_tag,),
                    values=(
                        pname,
                        masked_pwd,
                        t_label,
                        st_txt,
                        _fmt_date(p.get("createdAt") or p.get("activatedAt")),
                        _fmt_date(exp_ts),
                        f"💰 {bal_s} ⭐ | 🎁 {rcv_s} ⭐",
                        pnote,
                    ),
                )
            count_badge_lbl.config(text=f"Hiển thị: {shown} / {len(self.known_players)} User")
            status_bar_lbl.config(text=f"✅ Đang quản lý {len(self.known_players)} tài khoản User trên hệ thống.", fg="#34d399")

            if selected_orig_name["val"]:
                cur_p = next((x for x in self.known_players if x.get("name", "").lower() == selected_orig_name["val"].lower()), None)
                if cur_p:
                    _render_user_histories(cur_p)

        def _populate_tree(players_list):
            self.known_players = players_list or []
            _filter_and_populate_tree()

        search_var.trace_add("write", lambda *_: _filter_and_populate_tree())
        filter_tier_cb.bind("<<ComboboxSelected>>", lambda _e: _filter_and_populate_tree())

        def _on_select(_event):
            sel = tree.selection()
            if not sel:
                return
            sel_name = sel[0]
            p = next((x for x in self.known_players if x.get("name") == sel_name), None)
            if p:
                selected_orig_name["val"] = p.get("name", "")
                u_name_var.set(p.get("name", ""))
                u_pass_var.set("******")
                u_tier_var.set(str(p.get("tier") or "BRONZE").upper())
                u_stars_var.set(str(p.get("starsBalance") or 0))
                u_created_var.set(_fmt_date(p.get("createdAt") or p.get("activatedAt")))
                exp_ts = p.get("expiresAt")
                u_expires_var.set("Vĩnh viễn" if (not exp_ts or int(exp_ts) <= 0) else _fmt_date(exp_ts))
                u_days_var.set("")
                u_note_var.set(p.get("note", ""))
                form_mode_lbl.config(
                    text=f"✏️ Đang chỉnh sửa User: {p.get('name')} (Sửa Ngày tạo, Ngày hết hạn, Hạng VIP, Số Sao rồi bấm Lưu)",
                    fg="#f59e0b",
                )
                _render_user_histories(p)

        tree.bind("<<TreeviewSelect>>", _on_select)

        def _refresh_users():
            def _t():
                try:
                    res = requests.get(f"{self.get_api_endpoint()}?action=getInitialData", timeout=10)
                    d = res.json()
                    win.after(0, lambda: _populate_tree(d.get("players", [])))
                except Exception as e:
                    win.after(0, lambda e=e: status_bar_lbl.config(text=f"❌ Lỗi tải danh sách: {e}", fg="#f0657b"))
            threading.Thread(target=_t, daemon=True).start()

        def _save_user():
            uname = u_name_var.get().strip()
            if not uname:
                self.messagebox.showwarning("Thiếu tên", "Vui lòng nhập Tên Player!", parent=win)
                return

            days_raw = u_days_var.get().strip()
            duration_days = None
            if days_raw != "":
                try:
                    duration_days = int(days_raw)
                except Exception:
                    duration_days = None

            try:
                stars_bal = int(u_stars_var.get().strip() or "0")
            except Exception:
                stars_bal = 0

            exp_str = u_expires_var.get().strip()
            is_lifetime = (duration_days == 0) or ("vĩnh viễn" in exp_str.lower()) or ("vinh vien" in exp_str.lower())

            player_payload = {
                "originalName": selected_orig_name["val"] or uname,
                "name": uname,
                "password": u_pass_var.get().strip(),
                "tier": u_tier_var.get().strip() or "GOLD",
                "createdDate": u_created_var.get().strip(),
                "starsBalance": stars_bal,
                "note": u_note_var.get().strip(),
            }
            if is_lifetime:
                player_payload["lifetime"] = True
                player_payload["expiresDate"] = "lifetime"
            elif duration_days is not None and duration_days > 0:
                player_payload["durationDays"] = duration_days
            elif exp_str:
                player_payload["expiresDate"] = exp_str

            def _t():
                try:
                    res = requests.post(
                        self.get_api_endpoint(),
                        json={
                            "action": "adminSavePlayer",
                            "isAdmin": True,
                            "adminPassword": self.admin_password,
                            "player": player_payload,
                        },
                        timeout=10,
                    )
                    d = res.json()
                    if d.get("status") == "success":
                        selected_orig_name["val"] = uname
                        win.after(0, lambda: _populate_tree(d.get("players", [])))
                        win.after(0, lambda: status_bar_lbl.config(text=f"✅ {d.get('message', 'Đã lưu User!')}", fg="#34d399"))
                    else:
                        win.after(0, lambda: status_bar_lbl.config(text=f"⚠️ {d.get('message', 'Lỗi lưu User')}", fg="#f59e0b"))
                except Exception as e:
                    win.after(0, lambda e=e: status_bar_lbl.config(text=f"❌ Lỗi: {e}", fg="#f0657b"))
            threading.Thread(target=_t, daemon=True).start()

        tk.Button(
            form_btn_row,
            text="💾 Lưu / Cập Nhật User",
            command=_save_user,
            font=("Segoe UI", 9, "bold"),
            bg="#f59e0b",
            fg="#0b0e14",
            activebackground="#d97706",
            activeforeground="#0b0e14",
            relief="flat",
            width=22,
            padx=14,
            pady=3,
            cursor="hand2",
        ).pack(side="right")

        # ======================================================================
        # 5. THANH NÚT THAO TÁC NHANH CHO USER ĐANG CHỌN (NẠP SAO, RESET MK, GIA HẠN, KHÓA, XÓA)
        # ======================================================================
        action_bar = tk.Frame(win, bg="#0b0e14")
        # Neo cụm đáy theo thứ tự ưu tiên (Nút thao tác → Trạng thái → 2 khung Lịch sử) trước Bảng User
        # để khi cửa sổ thấp, chỉ Bảng User co lại — các nút thao tác luôn hiển thị đầy đủ.
        action_bar.pack(side="bottom", fill="x", padx=14, pady=(2, 10), before=list_card)
        status_bar_lbl.pack(side="bottom", fill="x", padx=16, pady=(2, 2), before=list_card)
        hist_frame.pack(side="bottom", fill="x", padx=14, pady=4, before=list_card)

        def _get_target_user_name():
            sel = tree.selection()
            target_name = sel[0] if sel else (selected_orig_name["val"] or u_name_var.get().strip())
            if not target_name:
                self.messagebox.showinfo("Chọn User", "Vui lòng click chọn 1 User trong bảng danh sách trước!", parent=win)
                return None
            return target_name

        def _quick_action(action_name, extra_payload):
            target_name = _get_target_user_name()
            if not target_name:
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
                        win.after(0, lambda: status_bar_lbl.config(text=f"⚠️ {d.get('message', 'Thất bại')}", fg="#f59e0b"))
                except Exception as e:
                    win.after(0, lambda e=e: status_bar_lbl.config(text=f"❌ Lỗi: {e}", fg="#f0657b"))
            threading.Thread(target=_t, daemon=True).start()

        def _topup_stars_dialog():
            target_name = _get_target_user_name()
            if not target_name:
                return
            amt = simpledialog.askinteger(
                "Nạp Sao cho User",
                f"Nhập số lượng Sao cần nạp cho '{target_name}' (Ví dụ: 100, 500):",
                initialvalue=100,
                parent=win,
            )
            if not amt:
                return
            note = simpledialog.askstring(
                "Ghi chú nạp Sao",
                f"Nhập ghi chú nạp +{amt} Sao cho '{target_name}':",
                initialvalue=f"Admin XO nạp +{amt} Sao",
                parent=win,
            )
            _quick_action("adminTopupStars", {"amount": amt, "note": note or f"Admin XO nạp +{amt} Sao"})

        def _reset_password_dialog():
            target_name = _get_target_user_name()
            if not target_name:
                return
            new_pw = simpledialog.askstring(
                "Reset Mật Khẩu User",
                f"Nhập mật khẩu mới cho tài khoản '{target_name}' (Mặc định: 123):",
                initialvalue="123",
                parent=win,
            )
            if new_pw is None:
                return
            _quick_action("adminResetPassword", {"newPassword": new_pw.strip() or "123"})

        def _custom_extend_days_dialog():
            target_name = _get_target_user_name()
            if not target_name:
                return
            days = simpledialog.askinteger(
                "Chỉnh / Gia Hạn Số Ngày Sử Dụng",
                f"Nhập số ngày muốn cộng thêm cho '{target_name}' (Nhập 0 để cấp Vĩnh viễn):",
                initialvalue=30,
                parent=win,
            )
            if days is None:
                return
            _quick_action("adminExtendPlayer", {"addDays": days, "lifetime": (days == 0)})

        # Lưới nút co giãn đều 5 cột x 2 hàng: hiển thị trọn vẹn toàn bộ 9 nút thao tác (không bao giờ tràn mép phải cửa sổ)
        for c_i in range(5):
            action_bar.columnconfigure(c_i, weight=1, uniform="adm_act_col")

        admin_action_defs = [
            ("💰 Nạp Sao (+⭐)", _topup_stars_dialog, "#0b0e14", "#f59e0b", None),
            ("🔑 Reset Mật Khẩu", _reset_password_dialog, "#e7ebf0", "#1a2130", "#262f40"),
            ("⏳ Gia hạn +30 Ngày", lambda: _quick_action("adminExtendPlayer", {"addDays": 30}), "#e7ebf0", "#1a2130", "#262f40"),
            ("⏳ Gia hạn +1 Năm", lambda: _quick_action("adminExtendPlayer", {"addDays": 365}), "#e7ebf0", "#1a2130", "#262f40"),
            ("📅 Chỉnh Hạn (+N Ngày)", _custom_extend_days_dialog, "#e7ebf0", "#1a2130", "#262f40"),
            ("♾️ Cấp Vĩnh Viễn", lambda: _quick_action("adminExtendPlayer", {"addDays": 0, "lifetime": True}), "#34d399", "#1a2130", "#262f40"),
            ("🔒 Khóa / 🔓 Mở", lambda: _quick_action("adminToggleActive", {}), "#f59e0b", "#1a2130", "#262f40"),
            ("🗑 Xóa User", lambda: _quick_action("adminDeletePlayer", {}), "#f0657b", "#1a2130", "#c94a61"),
            ("↻ Làm mới", _refresh_users, "#e7ebf0", "#1a2130", "#262f40"),
        ]
        for a_idx, (a_txt, a_cmd, a_fg, a_bg, a_border) in enumerate(admin_action_defs):
            tk.Button(
                action_bar,
                text=a_txt,
                command=a_cmd,
                font=("Segoe UI", 9, "bold"),
                bg=a_bg,
                fg=a_fg,
                activebackground="#d97706" if a_bg == "#f59e0b" else "#243047",
                activeforeground=a_fg,
                relief="flat",
                highlightthickness=1 if a_border else 0,
                highlightbackground=a_border or a_bg,
                padx=6,
                pady=4,
                cursor="hand2",
            ).grid(row=a_idx // 5, column=a_idx % 5, sticky="ew", padx=3, pady=3)

        _render_user_histories(None)
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
            if "showIdlePreview" in ov_cfg:
                self.show_idle_preview_var.set(bool(ov_cfg["showIdlePreview"]))
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
        requested_idle_preview = bool(self.show_idle_preview_var.get())
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
                            "showIdlePreview": requested_idle_preview,
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

    def enter_friend_live_lobby(self, streamer_name: str, match_id: str = ""):
        clean_target = (streamer_name or "").strip()
        self.active_lobby_streamer = clean_target
        self.selected_match_id = (match_id or "").strip()
        target_display = self.get_active_lobby_streamer()
        if clean_target:
            self.log(f"🏟️ Đã chuyển sang theo dõi Sảnh & Scoreboard của '{target_display}'!", "TEAM")
        else:
            self.log(f"🏠 Đã quay về Sảnh Live của bạn ('{target_display}').", "DEFAULT")
        if getattr(self, "_cached_social_data", None):
            self._update_friends_and_social_ui(self._cached_social_data)
        threading.Thread(target=self.refresh_initial_state, daemon=True).start()

    def refresh_initial_state(self):
        lock = getattr(self, "_refresh_state_lock", None)
        if lock is not None and not lock.acquire(blocking=False):
            return
        try:
            api_url = self.get_api_endpoint()
            name = self.player_name_var.get().strip()
            lobby_target = self.get_active_lobby_streamer()
            res = requests.get(f"{api_url}?action=getInitialData&streamer={lobby_target}", timeout=10)
            data = res.json()
            self.known_players = data.get("players", [])
            rel = data.get("appRelease") or (data.get("settings") or {}).get("appRelease")
            if rel and isinstance(rel, dict):
                self._check_server_version_and_prompt(rel)
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

            # Bỏ qua các kèo bị lỗi dữ liệu (có tên mặc định 'Red 1' / 'Blue 1' hoặc quân 'Random')
            if my_live_match:
                r_team = my_live_match.get("redTeam") or []
                b_team = my_live_match.get("blueTeam") or []
                last_g = (my_live_match.get("games") or [{}])[-1] if my_live_match.get("games") else {}
                r_civs = last_g.get("redCivs") or []
                b_civs = last_g.get("blueCivs") or []
                has_bogus = (
                    not r_team
                    or not b_team
                    or any(str(x).strip() in ("Red 1", "Blue 1") for x in (r_team + b_team))
                    or any(str(c).strip().lower() == "random" for c in (r_civs + b_civs))
                )
                if has_bogus:
                    my_live_match = None

            sel_id = getattr(self, "selected_match_id", "")
            selected_match_obj = next((m for m in all_matches if str(m.get("id", "")) == sel_id), None) if sel_id else None

            if selected_match_obj and (
                str(selected_match_obj.get("streamerName", "")).lower() != name.lower()
                or selected_match_obj.get("status") != "LIVE"
            ):
                self._update_battle_arena_ui(
                    selected_match_obj,
                    is_spectating=(str(selected_match_obj.get("streamerName", "")).lower() != name.lower()),
                )
            elif lobby_target.lower() != name.lower():
                watched_match = next(
                    (m for m in all_matches if m.get("status") == "LIVE" and str(m.get("streamerName", "")).lower() == lobby_target.lower()),
                    None,
                ) or next(
                    (m for m in all_matches if str(m.get("streamerName", "")).lower() == lobby_target.lower()),
                    None,
                )
                if watched_match:
                    self._update_battle_arena_ui(watched_match, is_spectating=True)
                elif time.time() - getattr(self, "_last_diplomacy_push_ts", 0.0) > 10.0:
                    self._reset_battle_arena_ui(f"Đang theo dõi Sảnh {lobby_target}\n(Chưa có kèo Live)")
            elif my_live_match:
                self.current_match = my_live_match
                self._update_battle_arena_ui(my_live_match, is_spectating=False)
            elif time.time() - getattr(self, "_last_diplomacy_push_ts", 0.0) > 10.0:
                self.current_match = None
                self._reset_battle_arena_ui()
        except Exception:
            pass
        finally:
            if lock is not None:
                try:
                    lock.release()
                except Exception:
                    pass

    def _condense_spam_text(self, text: str) -> str:
        """Thu gọn tin nhắn lặp từ kiểu 'hay hay hay hay...' thành 'hay (xN)'."""
        words = (text or "").strip().split()
        if len(words) >= 4:
            first_w = words[0].lower()
            if all(w.lower() == first_w for w in words):
                return f"{words[0]} (x{len(words)})"
            if len(words) >= 6 and len(set(w.lower() for w in words)) <= 2:
                pair = " ".join(words[:2])
                return f"{pair} (x{len(words) // 2})"
        return text

    def _update_friends_and_social_ui(self, data: dict):
        self._cached_social_data = data
        my_name = self.player_name_var.get().strip()
        players = data.get("players") or []
        matches = data.get("matches") or []
        me = next((p for p in players if str(p.get("name", "")).lower() == my_name.lower()), None)
        if me:
            if isinstance(me.get("friends"), list):
                self.my_friends = me.get("friends")
            self.my_stars_balance = int(me.get("starsBalance") or 0)

        # 1. Cập nhật danh sách Bạn bè & Trạng thái Online
        friend_badges = []
        online_count = 0
        for f_name in self.my_friends:
            fp = next((p for p in players if str(p.get("name", "")).lower() == str(f_name).lower()), None)
            if fp and fp.get("isLive"):
                online_count += 1
                friend_badges.append(f"🔴 {fp.get('name')} (LIVE)")
            elif fp and fp.get("isOnline"):
                online_count += 1
                friend_badges.append(f"🟢 {fp.get('name')} (Online)")
            else:
                friend_badges.append(f"⚫ {f_name} (Offline)")

        if friend_badges:
            friends_txt = f"👥 Bạn bè: {online_count} online  •  " + "  •  ".join(friend_badges)
        else:
            live_now = [p.get("name") for p in players if p.get("isLive")]
            online_all = sum(1 for p in players if p.get("isOnline") or p.get("isLive"))
            if live_now:
                friends_txt = f"👥 Hệ thống: {online_all} online  •  Đang LIVE: 🔴 {', '.join(live_now)}"
            else:
                friends_txt = f"👥 Bạn bè: {online_all} online  •  Nhập tên Player rồi bấm '+ Kết bạn'"

        # 2. Tìm kèo đấu của Sảnh đang chọn (Mỗi kèo Live có khung chat riêng biệt của kèo đó)
        lobby_target = self.get_active_lobby_streamer()
        t_lower = lobby_target.lower()
        sel_id = getattr(self, "selected_match_id", "")

        def _belongs_to_streamer(m_obj, s_l):
            if str(m_obj.get("streamerName", "")).lower() == s_l:
                return True
            r_t = [str(x).lower() for x in (m_obj.get("redTeam") or [])]
            b_t = [str(x).lower() for x in (m_obj.get("blueTeam") or [])]
            return s_l in r_t or s_l in b_t

        sel_match_obj = next((m for m in matches if str(m.get("id", "")) == sel_id), None) if sel_id else None
        live_for_target = next(
            (m for m in matches if m.get("status") == "LIVE" and _belongs_to_streamer(m, t_lower)),
            None,
        )

        # Nếu kèo đang chọn vừa kết thúc và Streamer đó đã mở kèo LIVE mới -> tự động chuyển sang kèo LIVE mới
        if sel_match_obj and sel_match_obj.get("status") != "LIVE" and live_for_target:
            sel_match_obj = live_for_target
            self.selected_match_id = str(live_for_target.get("id", ""))

        lobby_match = sel_match_obj or live_for_target

        if lobby_match:
            self.active_lobby_match_id = str(lobby_match.get("id", ""))
            raw_chats = lobby_match.get("chatMessages") or []
            chats = [
                c for c in raw_chats
                if not c.get("matchId") or str(c.get("matchId")) == self.active_lobby_match_id
            ]
            stars_total = lobby_match.get("starsCount") or 0
            pinned_chat = lobby_match.get("pinnedChat")
        else:
            self.active_lobby_match_id = ""
            chats = []
            target_p = next((p for p in players if str(p.get("name", "")).lower() == t_lower), None)
            stars_total = (target_p.get("starsReceived") if target_p else 0) or 0
            pinned_chat = None

        # Lọc danh sách trận đấu cho Khu vực C
        f_mode = getattr(self, "match_filter_mode", "ALL")
        q_match = (self.match_search_var.get() if hasattr(self, "match_search_var") else "").strip().lower()
        filtered_matches = []
        for m in matches:
            r_team = m.get("redTeam") or []
            b_team = m.get("blueTeam") or []
            if any(str(x).strip() in ("Red 1", "Blue 1") for x in (r_team + b_team)):
                continue
            st = m.get("status", "LIVE")
            if f_mode == "LIVE" and st != "LIVE":
                continue
            if f_mode == "FINISHED" and st == "LIVE":
                continue
            if q_match:
                haystack = " ".join([str(m.get("streamerName", "")), str(m.get("mode", ""))] + [str(x) for x in r_team + b_team]).lower()
                if q_match not in haystack:
                    continue
            filtered_matches.append(m)

        def _render():
            try:
                if hasattr(self, "my_stars_badge_lbl"):
                    self.my_stars_badge_lbl.config(text=f"👑 Quỹ Sao: {self.my_stars_balance} ⭐")
                if hasattr(self, "chat_wallet_lbl"):
                    self.chat_wallet_lbl.config(text=f"💰 Quỹ Sao của bạn: {self.my_stars_balance} ⭐ (Trừ trực tiếp khi tặng)")
                if hasattr(self, "chat_lobby_stars_lbl"):
                    self.chat_lobby_stars_lbl.config(text=f"🎁 Phiên Live: {stars_total} ⭐")

                self.friends_status_lbl.config(text=friends_txt)
                if lobby_match:
                    m_mode = lobby_match.get("mode") or "SOLO"
                    m_g_cnt = len(lobby_match.get("games") or []) or 1
                    badge_title = f"💬 SẢNH CHAT LIVE - MÁY {lobby_target.upper()} [{m_mode} • Trận #{m_g_cnt}]"
                else:
                    badge_title = f"💬 SẢNH CHAT LIVE - MÁY {lobby_target.upper()} [Chưa có trận LIVE]"
                self.lobby_badge_lbl.config(
                    text=badge_title,
                    fg="#f59e0b" if lobby_target.lower() != my_name.lower() else "#f8fafc",
                )
                self.stars_counter_lbl.config(text=f"⭐ {stars_total} sao tại sảnh {lobby_target}")

                # Render danh sách Card Trận Đấu tại Khu vực C
                if hasattr(self, "live_matches_list_frame"):
                    for child in self.live_matches_list_frame.winfo_children():
                        child.destroy()

                    if not filtered_matches:
                        empty_msg = (
                            "🔍 Không tìm thấy trận đấu phù hợp với bộ lọc."
                            if (q_match or f_mode != "ALL")
                            else "🛡️ Hiện chưa có trận đấu nào trên sảnh.\nKhi ấn nút Diplomacy trong game, trận đấu sẽ xuất hiện tại đây!"
                        )
                        empty_lbl = self.tk.Label(
                            self.live_matches_list_frame,
                            text=empty_msg,
                            font=("Segoe UI", 8, "bold"),
                            fg="#94a3b8",
                            bg="#1a2130",
                            justify="left",
                            anchor="w",
                            width=1,
                        )
                        empty_lbl.pack(anchor="w", fill="x", pady=4)
                        self._auto_wrap_label(empty_lbl, pad=6)
                    else:
                        for row_idx, lm in enumerate(filtered_matches[:30]):
                            m_id = str(lm.get("id", ""))
                            s_name = lm.get("streamerName") or "XO"
                            m_mode = lm.get("mode") or "4v4"
                            m_status = lm.get("status", "LIVE")
                            m_games = lm.get("games") or []
                            m_stars = lm.get("starsCount") or 0
                            rw = sum(1 for g in m_games if g.get("winner") == "RED")
                            bw = sum(1 for g in m_games if g.get("winner") == "BLUE")
                            r_names = ", ".join((lm.get("redTeam") or [])[:2]) or "Team Đỏ"
                            b_names = ", ".join((lm.get("blueTeam") or [])[:2]) or "Team Xanh"
                            if len(lm.get("redTeam") or []) > 2:
                                r_names += "..."
                            if len(lm.get("blueTeam") or []) > 2:
                                b_names += "..."

                            is_watching = (sel_id == m_id) if sel_id else (s_name.lower() == lobby_target.lower() and m_status == "LIVE")
                            stripe_bg = "#0f1726" if (row_idx % 2 == 0) else "#131e31"
                            row_bg = "#15263f" if is_watching else stripe_bg

                            row_f = self.tk.Frame(
                                self.live_matches_list_frame,
                                bg=row_bg,
                                highlightthickness=1,
                                highlightbackground="#38bdf8" if is_watching else "#1e2d47",
                                padx=8,
                                pady=5,
                            )
                            row_f.pack(fill="x", pady=1)

                            # Dòng 1: Badge LIVE / XONG + Tên máy [Chế độ] (Trái) | Số Sao (Phải)
                            top_line = self.tk.Frame(row_f, bg=row_bg)
                            top_line.pack(fill="x")
                            # Dòng 3: Nút 🐘 22 + Xem trận căn phải (tạo trước, pack sau Dòng 2)
                            btn_line = self.tk.Frame(row_f, bg=row_bg)

                            is_live_m = m_status == "LIVE"
                            self.tk.Label(
                                top_line,
                                text="LIVE" if is_live_m else "XONG",
                                font=("Segoe UI", 7, "bold"),
                                fg="#34d399" if is_live_m else "#94a3b8",
                                bg="#0d2e22" if is_live_m else "#1e293b",
                                padx=5,
                                pady=1,
                            ).pack(side="left", padx=(0, 6))

                            self.tk.Label(
                                top_line,
                                text=f"⭐ {m_stars}",
                                font=("Segoe UI", 8, "bold"),
                                fg="#fbbf24",
                                bg=row_bg,
                            ).pack(side="right", padx=(6, 0))

                            act_btn = self.tk.Button(
                                btn_line,
                                text="📌 Đang xem" if is_watching else "👁️ Xem trận",
                                command=lambda st=s_name, mid=m_id: self.enter_friend_live_lobby(st, mid),
                                font=("Segoe UI", 8, "bold"),
                                bg="#f59e0b" if is_watching else "#1a2130",
                                fg="#0b0e14" if is_watching else "#e2e8f0",
                                activebackground="#d97706" if is_watching else "#243047",
                                activeforeground="#0b0e14" if is_watching else "#ffffff",
                                relief="flat",
                                highlightthickness=0 if is_watching else 1,
                                highlightbackground="#334155",
                                padx=7,
                                pady=0,
                                cursor="hand2",
                            )
                            act_btn.pack(side="right", padx=(4, 0))

                            voi_btn = self.tk.Button(
                                btn_line,
                                text="🐘 22",
                                command=lambda st=s_name, mid=m_id: (
                                    self.enter_friend_live_lobby(st, mid),
                                    self.send_star_gift_action(22, gift_code="ELEPHANT", gift_name="Con Voi", default_msg="Thả Con Voi 22 sao húc bay nhà địch!"),
                                ),
                                font=("Segoe UI", 8, "bold"),
                                bg="#1a2130",
                                fg="#cbd5e1",
                                activebackground="#243047",
                                activeforeground="#fbbf24",
                                relief="flat",
                                highlightthickness=1,
                                highlightbackground="#262f40",
                                padx=5,
                                pady=0,
                                cursor="hand2",
                            )
                            voi_btn.pack(side="right", padx=(4, 0))

                            title_lbl = self._make_ellipsis_label(
                                top_line,
                                text=f"Máy {s_name} [{m_mode}]",
                                font=("Segoe UI", 8, "bold"),
                                fg="#f8fafc",
                                bg=row_bg,
                                anchor="w",
                                cursor="hand2",
                            )
                            title_lbl.pack(side="left", fill="x", expand=True)
                            title_lbl.bind("<Button-1>", lambda _e, st=s_name, mid=m_id: self.enter_friend_live_lobby(st, mid))

                            # Dòng 2: Người chơi 2 đội + Tỷ số (rút gọn bằng '…' + tooltip khi tên quá dài)
                            full_r = ", ".join(str(x) for x in (lm.get("redTeam") or [])) or "Team Đỏ"
                            full_b = ", ".join(str(x) for x in (lm.get("blueTeam") or [])) or "Team Xanh"
                            info_txt = f"{r_names} ({rw} - {bw}) {b_names}"
                            full_info_txt = f"Máy {s_name} [{m_mode}]  •  🔴 {full_r}  ({rw} - {bw})  🔵 {full_b}  •  ⭐ {m_stars}"
                            try:
                                avail_px = int(self.live_matches_list_frame.winfo_width() or 0) - 36
                            except Exception:
                                avail_px = 0
                            if avail_px > 60:
                                info_txt = self._ellipsize_text(info_txt, ("Segoe UI", 8), avail_px)
                            info_lbl = self.tk.Label(
                                row_f,
                                text=info_txt,
                                font=("Segoe UI", 8),
                                fg="#cbd5e1",
                                bg=row_bg,
                                anchor="w",
                                width=1,
                                cursor="hand2",
                            )
                            info_lbl.pack(fill="x", pady=(3, 0))
                            info_lbl.bind("<Button-1>", lambda _e, st=s_name, mid=m_id: self.enter_friend_live_lobby(st, mid))
                            self._attach_tooltip(info_lbl, full_info_txt)
                            btn_line.pack(fill="x", pady=(4, 0))

                # Cập nhật Bảng Vinh Danh Hoàng Gia trên đỉnh Hộp Chat
                latest_star_chat = next(
                    (c for c in reversed(chats) if c.get("type") in ("STAR", "STAR_GIFT")),
                    None,
                )
                if hasattr(self, "chat_honor_lbl"):
                    if latest_star_chat:
                        h_sender = latest_star_chat.get("senderName", "Player")
                        h_receiver = latest_star_chat.get("receiverName") or latest_star_chat.get("streamerName") or lobby_target
                        h_icon = (latest_star_chat.get("giftIcon") or "🌟").replace("🧙‍♂️", "")
                        h_name = str(latest_star_chat.get("giftName") or "").replace("(Wololo)", "").strip()
                        h_stars = latest_star_chat.get("starCount") or latest_star_chat.get("stars") or 1
                        h_gift_txt = f"{h_icon} {h_name} (+{h_stars}⭐)" if (h_name and latest_star_chat.get("giftCode") != "STAR") else f"+{h_stars} ⭐"
                        self.chat_honor_lbl.config(
                            text=f"👑 VINH DANH: {h_sender} tặng {h_gift_txt} ➔ {h_receiver}",
                            fg="#fef08a",
                        )
                    else:
                        self.chat_honor_lbl.config(
                            text=f"👑 VINH DANH SẢNH {lobby_target.upper()}: Thả 🐘 Con Voi (22 ⭐) hoặc ⚡ Phù Thủy (100 ⭐) để lên bảng vàng!",
                            fg="#fde047",
                        )

                # Cập nhật Ghim bình luận
                if hasattr(self, "pinned_chat_lbl"):
                    if pinned_chat and isinstance(pinned_chat, dict) and (pinned_chat.get("text") or pinned_chat.get("message")):
                        p_sender = pinned_chat.get("senderName", "Admin")
                        p_txt = pinned_chat.get("text") or pinned_chat.get("message") or ""
                        self.pinned_chat_lbl.config(
                            text=f"📌 GHIM [{p_sender}]: {p_txt[:68]}",
                            fg="#fef08a",
                        )
                    else:
                        self.pinned_chat_lbl.config(
                            text="📌 Chưa có bình luận ghim (Bấm '📌 Ghim mới nhất' để ghim tin nhắn đầu sảnh)",
                            fg="#93c5fd",
                        )

                # Lọc & hiển thị Live Chat tại Khu vực D
                c_tab = getattr(self, "chat_filter_tab", "ALL")
                q_chat = (self.chat_search_var.get() if hasattr(self, "chat_search_var") else "").strip().lower()
                antispam = bool(self.chat_antispam_var.get()) if hasattr(self, "chat_antispam_var") else True

                self.chat_box.configure(state="normal")
                self.chat_box.delete("1.0", "end")

                filtered_chats = []
                prev_sig = None
                for c in chats[-50:]:
                    if c.get("giftCode") == "HYPE_F8":
                        continue
                    c_type = c.get("type", "CHAT")
                    sender = str(c.get("senderName", "Player"))
                    raw_msg = str(c.get("text") or c.get("message") or "")
                    if c_tab == "CHAT" and c_type in ("STAR", "STAR_GIFT", "SYSTEM"):
                        continue
                    if c_tab == "GIFT" and c_type not in ("STAR", "STAR_GIFT"):
                        continue
                    if c_tab == "SYSTEM" and c_type != "SYSTEM":
                        continue
                    if q_chat and (q_chat not in sender.lower() and q_chat not in raw_msg.lower()):
                        continue
                    disp_msg = self._condense_spam_text(raw_msg) if antispam and c_type == "CHAT" else raw_msg
                    if antispam and c_type == "CHAT":
                        sig = f"{sender.lower()}::{disp_msg.lower()}"
                        if sig == prev_sig:
                            continue
                        prev_sig = sig
                    filtered_chats.append((c, disp_msg))

                if not filtered_chats:
                    self.chat_box.insert(
                        "end",
                        f"Đang ở sảnh Live của {lobby_target}. Chưa có tin nhắn phù hợp — hãy chat hoặc tặng Vật Phẩm Đế Chế!\n",
                        "MSG",
                    )
                else:
                    for c, msg in filtered_chats[-35:]:
                        sender = c.get("senderName", "Player")
                        c_type = c.get("type", "CHAT")
                        ts_raw = str(c.get("timestamp") or "")
                        hhmm = ""
                        if "T" in ts_raw and len(ts_raw) >= 16:
                            try:
                                dt_utc = datetime.fromisoformat(ts_raw.replace("Z", "+00:00"))
                                hhmm = dt_utc.astimezone().strftime("%H:%M ")
                            except Exception:
                                hhmm = ts_raw[11:16] + " "

                        if hhmm:
                            self.chat_box.insert("end", hhmm, "TIME")

                        if c_type == "SYSTEM":
                            self.chat_box.insert("end", f"⚙️ [HỆ THỐNG] {msg}\n", "SYS_EVENT")
                        elif c_type in ("STAR", "STAR_GIFT"):
                            if c.get("giftCode") == "HYPE_F8":
                                self.chat_box.insert("end", f"🙌 {sender}", "GIFT_RECEIVER")
                                self.chat_box.insert("end", " hô vang: ", "GIFT_VERB")
                                self.chat_box.insert("end", "\"Tay đâu, tayyyy đâuuuuu\" 🔥\n", "GIFT_ITEM")
                            else:
                                g_icon = (c.get("giftIcon") or "🌟").replace("🧙‍♂️", "")
                                g_code = str(c.get("giftCode") or "").upper()
                                g_name = str(c.get("giftName") or "").replace("(Wololo)", "").strip()
                                star_amt = c.get("starCount") or c.get("stars") or 1
                                receiver = c.get("receiverName") or c.get("streamerName") or lobby_target
                                if g_code and g_code != "STAR" and g_name:
                                    item_short = f"{g_icon} {g_name} (+{star_amt}⭐)"
                                else:
                                    item_short = f"+{star_amt} ⭐"
                                self.chat_box.insert("end", f"{g_icon} ", "GIFT_ITEM")
                                self.chat_box.insert("end", f"{sender}", "GIFT_SENDER")
                                self.chat_box.insert("end", " tặng ", "GIFT_VERB")
                                self.chat_box.insert("end", f"{item_short}", "GIFT_ITEM")
                                self.chat_box.insert("end", " ➔ ", "GIFT_VERB")
                                self.chat_box.insert("end", f"{receiver}\n", "GIFT_RECEIVER")
                        elif c.get("source") == "FACEBOOK" or c.get("senderTier") == "FACEBOOK":
                            self.chat_box.insert("end", f"🔵 [FB] {sender}: ", "FB_SENDER")
                            self.chat_box.insert("end", f"{msg}\n", "MSG")
                        else:
                            if c.get("isAdmin") or str(sender).lower() == "xo":
                                self.chat_box.insert("end", "🛡️ ADMIN ", "ADMIN_BADGE")
                            elif c.get("isStreamer") or str(sender).lower() == lobby_target.lower():
                                self.chat_box.insert("end", "🎥 HOST ", "STREAMER_BADGE")
                            self.chat_box.insert("end", f"{sender}: ", "SENDER")
                            self.chat_box.insert("end", f"{msg}\n", "MSG")
                self.chat_box.see("end")
                self.chat_box.configure(state="disabled")
                self._force_repaint_widget(self.main_app_frame)
            except Exception:
                pass

        self.root.after(0, _render)

    def pin_chat_message_action(self, unpin: bool = False):
        if not self.is_logged_in:
            self.messagebox.showwarning("Chưa đăng nhập", "Vui lòng đăng nhập trước khi ghim bình luận!")
            return
        target_streamer = self.get_active_lobby_streamer()
        chat_id = ""
        target_match_id = getattr(self, "active_lobby_match_id", "") or getattr(self, "selected_match_id", "")
        if not unpin and getattr(self, "_cached_social_data", None):
            matches = self._cached_social_data.get("matches") or []
            lm = (
                next((m for m in matches if str(m.get("id", "")) == target_match_id), None)
                if target_match_id
                else None
            ) or next(
                (m for m in matches if m.get("status") == "LIVE" and str(m.get("streamerName", "")).lower() == target_streamer.lower()),
                None,
            )
            if lm and lm.get("chatMessages"):
                non_sys = [c for c in lm.get("chatMessages") if c.get("type") != "SYSTEM"]
                if non_sys:
                    chat_id = non_sys[-1].get("id", "")

        def _task():
            try:
                res = requests.post(
                    self.get_api_endpoint(),
                    json={
                        "action": "pinChatMessage",
                        "matchId": target_match_id or None,
                        "streamerName": target_streamer,
                        "playerName": self.player_name_var.get().strip(),
                        "password": self._get_effective_player_password(),
                        "isAdmin": self.is_admin,
                        "adminPassword": self.admin_password,
                        "chatId": chat_id,
                        "unpin": unpin,
                    },
                    timeout=10,
                )
                data = res.json()
                if data.get("status") == "success":
                    self.log(f"✅ 📌 {data.get('message', 'Đã cập nhật ghim bình luận!')}", "SUCCESS")
                    self.refresh_initial_state()
                else:
                    self.log(f"⚠️ {data.get('message', 'Không thể ghim bình luận')}", "WARN")
            except Exception as e:
                self.log(f"❌ Lỗi ghim bình luận: {e}", "ERROR")

        threading.Thread(target=_task, daemon=True).start()

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
        target_match_id = getattr(self, "active_lobby_match_id", "") or getattr(self, "selected_match_id", "")
        self.chat_msg_var.set("")

        def _task():
            try:
                res = requests.post(
                    self.get_api_endpoint(),
                    json={
                        "action": "sendChatMessage",
                        "matchId": target_match_id or None,
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

    def toggle_gift_drawer(self, force_close: bool = False):
        """Đóng/mở ngăn chọn Vật Phẩm Đế Chế & Tặng Sao khi bấm vào nút '🎁 Tặng Sao ▾'."""
        if not hasattr(self, "aoe_gift_panel"):
            return
        if force_close or getattr(self, "gift_drawer_open", False):
            self.gift_drawer_open = False
            try:
                self.aoe_gift_panel.pack_forget()
                if hasattr(self, "btn_toggle_gift_drawer"):
                    self.btn_toggle_gift_drawer.configure(text="🎁 Tặng Sao ▾", bg="#261c10", fg="#fbbf24")
            except Exception:
                pass
        else:
            self.gift_drawer_open = True
            try:
                if hasattr(self, "chat_feed_wrap"):
                    self.aoe_gift_panel.pack(before=self.chat_feed_wrap, fill="x", side="bottom", pady=(4, 2))
                else:
                    self.aoe_gift_panel.pack(fill="x", side="bottom", pady=(4, 2))
                if hasattr(self, "btn_toggle_gift_drawer"):
                    self.btn_toggle_gift_drawer.configure(text="🎁 Đóng Quà ▴", bg="#f59e0b", fg="#0b0e14")
            except Exception:
                pass

    def send_star_gift_action(self, stars: int = 1, gift_code: str = "", gift_name: str = "", default_msg: str = ""):
        if not self.is_logged_in:
            self.messagebox.showwarning(
                "Yêu cầu đăng nhập",
                "Bạn bắt buộc phải đăng nhập tài khoản Player trước khi tặng Vật Phẩm / Sao trong sảnh Live!",
            )
            return
        # Tự động thu gọn ngăn chọn quà sau khi bấm chọn
        self.toggle_gift_drawer(force_close=True)
        sender = self.player_name_var.get().strip()
        target_streamer = self.get_active_lobby_streamer()
        target_match_id = getattr(self, "active_lobby_match_id", "") or getattr(self, "selected_match_id", "")
        gift_msg = default_msg or f"Tặng {stars} sao cổ vũ {target_streamer}!"

        def _task():
            try:
                res = requests.post(
                    self.get_api_endpoint(),
                    json={
                        "action": "sendStarGift",
                        "matchId": target_match_id or None,
                        "streamerName": target_streamer,
                        "senderName": sender,
                        "password": self._get_effective_player_password(),
                        "isAdmin": self.is_admin,
                        "adminPassword": self.admin_password,
                        "starCount": stars,
                        "stars": stars,
                        "giftCode": gift_code,
                        "giftName": gift_name,
                        "message": gift_msg,
                    },
                    timeout=10,
                )
                data = res.json()
                if data.get("status") == "success":
                    if "senderStarsBalance" in data:
                        self.my_stars_balance = int(data.get("senderStarsBalance") or 0)
                    label_sent = f"[{gift_name} • {stars}⭐]" if gift_name else f"+{stars} Sao"
                    self.log(
                        f"✅ 🎁 Đã tặng {label_sent} vào sảnh Live của {target_streamer}! (Quỹ Sao còn: {self.my_stars_balance} ⭐)",
                        "SUCCESS",
                    )
                    self.refresh_initial_state()
                else:
                    err_msg = data.get("message", "Không thể tặng sao")
                    self.log(f"⚠️ {err_msg}", "WARN")
                    self.root.after(0, lambda: self.messagebox.showwarning("Không đủ Sao trong quỹ", err_msg))
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

    def _reset_battle_arena_ui(self, summary_text: str = "Ấn nút Diplomacy để bắt đầu\nTổng 0 trận"):
        def _render():
            try:
                t_score = self.target_score_var.get() or 7
                self.match_mode_lbl.config(text=f"Kèo 1v1 - Chạm {t_score}")
                self.score_lbl.config(text="0 : 0")
                self.c_mode_summary_lbl.config(text=summary_text)
                if hasattr(self, "match_history_lbl"):
                    self.match_history_lbl.config(text="Lịch sử ván: Chưa có ván đấu", fg="#64748b")
                if hasattr(self, "red_primary_player_lbl"):
                    self.red_primary_player_lbl.config(text=self.player_name_var.get().strip() or "Chủ nhà")
                if hasattr(self, "blue_primary_player_lbl"):
                    self.blue_primary_player_lbl.config(text="Đội khách")
                self.red_roster_lbl.config(text="[Chưa chọn quân] (Chờ mở Diplomacy)")
                self.blue_roster_lbl.config(text="[Chưa chọn quân] (Chờ mở Diplomacy)")
                self.red_count_lbl.config(text="Chủ nhà")
                self.blue_count_lbl.config(text="Đội khách")
                if hasattr(self, "scoreboard_live_badge"):
                    self.scoreboard_live_badge.config(text="LIVE", fg="#34d399", bg="#0d2e22")
                self._force_repaint_widget(getattr(self, "left_workspace_col", None) or self.main_app_frame)
            except Exception:
                pass

        self.root.after(0, _render)

    def _update_battle_arena_ui(self, match: dict, is_spectating: bool = False):
        if not match:
            return
        games = match.get("games", [])
        red_w = sum(1 for g in games if g.get("winner") == "RED")
        blue_w = sum(1 for g in games if g.get("winner") == "BLUE")
        mode = match.get("mode", "4v4")
        m_status = match.get("status", "LIVE")
        streamer_owner = match.get("streamerName") or "XO"
        ov_cfg = match.get("overlayConfig") or {}
        target_score = ov_cfg.get("targetScore") or self.target_score_var.get() or 7
        c_enabled = bool(ov_cfg.get("cModeEnabled", self.c_mode_var.get()))

        last_game = games[-1] if games else {}
        red_players = match.get("redTeam") or []
        blue_players = match.get("blueTeam") or []
        red_civs = last_game.get("redCivs") or []
        blue_civs = last_game.get("blueCivs") or []
        red_colors = last_game.get("redColors") or match.get("redColors") or []
        blue_colors = last_game.get("blueColors") or match.get("blueColors") or []

        if len(red_players) == 1:
            red_primary = str(red_players[0])
            civ = red_civs[0] if red_civs else "---"
            col_idx = red_colors[0] if red_colors else 0
            col_name = COLOR_NAMES_VI.get(col_idx, f"Màu {col_idx + 1}")
            red_text = f"[{civ}] ({col_name})"
            red_cnt_txt = "1 người chơi"
        else:
            red_primary = " • ".join(str(x) for x in red_players[:2]) + ("..." if len(red_players) > 2 else "")
            if not red_primary:
                red_primary = "Chủ nhà"
            red_lines = []
            for i, p in enumerate(red_players):
                civ = red_civs[i] if i < len(red_civs) else "---"
                col_idx = red_colors[i] if i < len(red_colors) else i
                col_name = COLOR_NAMES_VI.get(col_idx, f"Màu {col_idx + 1}")
                red_lines.append(f"{p} [{civ}] ({col_name})")
            red_text = "\n".join(red_lines) if red_lines else "[Chưa có dữ liệu]"
            red_cnt_txt = f"{len(red_players)} người chơi"

        if len(blue_players) == 1:
            blue_primary = str(blue_players[0])
            civ = blue_civs[0] if blue_civs else "---"
            col_idx = blue_colors[0] if blue_colors else 1
            col_name = COLOR_NAMES_VI.get(col_idx, f"Màu {col_idx + 1}")
            blue_text = f"[{civ}] ({col_name})"
            blue_cnt_txt = "1 người chơi"
        else:
            blue_primary = " • ".join(str(x) for x in blue_players[:2]) + ("..." if len(blue_players) > 2 else "")
            if not blue_primary:
                blue_primary = "Đội khách"
            blue_lines = []
            for i, p in enumerate(blue_players):
                civ = blue_civs[i] if i < len(blue_civs) else "---"
                col_idx = blue_colors[i] if i < len(blue_colors) else i + 4
                col_name = COLOR_NAMES_VI.get(col_idx, f"Màu {col_idx + 1}")
                blue_lines.append(f"{p} [{civ}] ({col_name})")
            blue_text = "\n".join(blue_lines) if blue_lines else "[Chưa có dữ liệu]"
            blue_cnt_txt = f"{len(blue_players)} người chơi"

        # Lịch sử kết quả từng ván
        hist_parts = []
        for idx, g in enumerate(games[-6:], start=max(1, len(games) - 5)):
            gw = g.get("winner")
            if gw == "RED":
                hist_parts.append(f"V{idx}: 🔴 Đỏ")
            elif gw == "BLUE":
                hist_parts.append(f"V{idx}: 🔵 Xanh")
            else:
                hist_parts.append(f"V{idx}: ⏳")
        hist_txt = ("Lịch sử: " + " • ".join(hist_parts)) if hist_parts else "Lịch sử ván: Chưa có ván đấu"
        hist_fg = "#94a3b8"

        is_finished = m_status != "LIVE" or (int(target_score) < 50 and (red_w >= int(target_score) or blue_w >= int(target_score)))
        if is_finished:
            win_team = "TEAM ĐỎ CHIẾN THẮNG 🏆" if red_w > blue_w else ("TEAM XANH CHIẾN THẮNG 🏆" if blue_w > red_w else "HÒA KÈO 🤝")
            hist_txt = f"🎉 {win_team}  |  {hist_txt}"
            hist_fg = "#fbbf24"

        if is_spectating:
            hdr_txt = f"Kèo {mode} - Chạm {target_score} (Máy {streamer_owner})"
            summary_txt = f"Trận #{len(games)} đang diễn ra\nTổng {len(games)} trận"
        elif c_enabled:
            summary_txt = self._compute_c_mode_summary(games, int(ov_cfg.get("cTargetWins") or 3))
            hdr_txt = f"Kèo {mode} - Đánh C (Chạm 3)"
        else:
            summary_txt = f"Trận #{max(1, len(games))} {'đã kết thúc' if is_finished else 'đang diễn ra'}\nTổng {len(games)} trận"
            hdr_txt = f"Kèo {mode} - Chạm {target_score}"

        def _render():
            try:
                self.match_mode_lbl.config(text=hdr_txt)
                self.score_lbl.config(text=f"{red_w} : {blue_w}")
                self.c_mode_summary_lbl.config(text=summary_txt)
                if hasattr(self, "match_history_lbl"):
                    self.match_history_lbl.config(text=hist_txt, fg=hist_fg)
                if hasattr(self, "red_primary_player_lbl"):
                    self.red_primary_player_lbl.config(text=red_primary)
                if hasattr(self, "blue_primary_player_lbl"):
                    self.blue_primary_player_lbl.config(text=blue_primary)
                self.red_roster_lbl.config(text=red_text)
                self.blue_roster_lbl.config(text=blue_text)
                self.red_count_lbl.config(text=red_cnt_txt)
                self.blue_count_lbl.config(text=blue_cnt_txt)
                if hasattr(self, "scoreboard_live_badge"):
                    if is_finished:
                        self.scoreboard_live_badge.config(text="KẾT THÚC", fg="#fbbf24", bg="#2a1f10")
                    else:
                        self.scoreboard_live_badge.config(text="LIVE", fg="#34d399", bg="#0d2e22")
                self._force_repaint_widget(getattr(self, "left_workspace_col", None) or self.main_app_frame)
            except Exception:
                pass

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

    def _generate_fb_group_bridge_js(self, for_display: bool = False) -> str:
        base_url = self.get_base_server_url()
        streamer = self.player_name_var.get().strip() or "XO"
        pw = self._get_effective_player_password()
        sha_token = hashlib.sha256(f"aoe_fb_bridge::{streamer.lower()}::{pw}".encode("utf-8")).hexdigest()
        if for_display:
            auth_decl = '  const AUTH_TOKEN = "•••••••••••••••• (Đã mã hóa bảo mật - Không lộ mật khẩu khi Live)";'
            auth_payload = "          bridgeToken: AUTH_TOKEN,"
        else:
            hex_pw = "".join(f"{b ^ 0x5A:02x}" for b in pw.encode("utf-8"))
            auth_decl = (
                f'  const AUTH_TOKEN = {json.dumps("AOE_SECURE_" + sha_token[:24])}; // Đã khóa bảo mật chống lộ mật khẩu\n'
                f'  const _k = {json.dumps(hex_pw)};\n'
                f'  const _d = (h) => new TextDecoder().decode(new Uint8Array((h.match(/.{{1,2}}/g) || []).map(x => parseInt(x, 16) ^ 90)));'
            )
            auth_payload = f"          bridgeToken: {json.dumps(sha_token)},\n          password: _d(_k),"

        return f"""/* =========================================================================
 * 🔵 AOE BY XO — CẦU NỐI TỰ ĐỘNG BẮT COMMENT FACEBOOK GROUP LIVE -> OBS
 * Streamer đích : {streamer}
 * Máy chủ       : {base_url}
 * Bảo mật       : Mật khẩu đã được ẨN & MÃ HÓA BẢO MẬT (An toàn khi phát Live)
 * Cách dùng     : Mở bài phát Live trong Group Facebook -> Ấn F12 (tab Console)
 *                 -> Dán (Ctrl+V) toàn bộ đoạn mã này -> Ấn Enter!
 * ========================================================================= */
(() => {{
  if (window.__aoeFbBridgeTimer) clearInterval(window.__aoeFbBridgeTimer);
  const SERVER = {json.dumps(base_url)};
  const STREAMER = {json.dumps(streamer)};
{auth_decl}
  const seen = new Set();
  let initialized = false;
  let pushedCount = 0;

  let badge = document.getElementById('__aoe_fb_live_badge');
  if (!badge) {{
    badge = document.createElement('div');
    badge.id = '__aoe_fb_live_badge';
    badge.style.cssText = 'position:fixed;bottom:16px;left:16px;z-index:999999;background:#0f172a;color:#38bdf8;border:2px solid #2563eb;padding:8px 14px;border-radius:12px;font-family:Segoe UI,sans-serif;font-size:12px;font-weight:bold;box-shadow:0 8px 25px rgba(0,0,0,0.65);pointer-events:none;';
    document.body.appendChild(badge);
  }}
  const updateBadge = (lastTxt) => {{
    badge.innerHTML = '🔵 AOE BY XO • Đang bắt Comment FB Group Live &rarr; OBS <b>' + STREAMER + '</b> (' + pushedCount + ' bình luận)' + (lastTxt ? '<br><span style="color:#e2e8f0;font-weight:normal;font-size:11px;">Mới nhất: ' + lastTxt + '</span>' : '');
  }};
  updateBadge('');

  const ignoreWords = new Set(['Thích', 'Phản hồi', 'Chia sẻ', 'Theo dõi', 'Viết bình luận...', 'Bình luận', 'Tất cả bình luận', 'Phù hợp nhất', 'Mới nhất']);

  const scanComments = () => {{
    const articles = document.querySelectorAll('div[role="article"]');
    articles.forEach(art => {{
      const aria = art.getAttribute('aria-label') || '';
      if (!aria && !art.innerText) return;
      const authorEl = art.querySelector('a[role="link"] span[dir="auto"], span.xt0psk2 span[dir="auto"], h3 span, h4 span');
      const author = (authorEl ? authorEl.innerText : '').trim();
      if (!author || ignoreWords.has(author)) return;

      const textDivs = art.querySelectorAll('div[dir="auto"]');
      let bodyText = '';
      textDivs.forEach(td => {{
        const val = (td.innerText || '').trim();
        if (val && val !== author && !ignoreWords.has(val) && !val.startsWith('Phản hồi ')) {{
          bodyText = val;
        }}
      }});
      if (!bodyText || bodyText.length > 350) return;

      const key = author + '::' + bodyText;
      if (seen.has(key)) return;
      seen.add(key);

      // Bỏ qua các comment cũ đã có sẵn trước khi bật script để tránh đẩy lại hàng loạt comment cũ
      if (!initialized) return;

      pushedCount++;
      updateBadge(author + ': ' + bodyText.slice(0, 38));

      fetch(SERVER + '/api', {{
        method: 'POST',
        headers: {{ 'Content-Type': 'application/json' }},
        body: JSON.stringify({{
          action: 'pushFacebookComment',
          streamerName: STREAMER,
{auth_payload}
          fbAuthor: author,
          text: bodyText,
          fbCommentId: key
        }})
      }}).catch(() => {{}});
    }});
    initialized = true;
  }};

  scanComments();
  window.__aoeFbBridgeTimer = setInterval(scanComments, 1400);
  console.log('%c🔵 [AOE BY XO] Đã kết nối tự động đẩy Comment Facebook Group Live -> OBS máy ' + STREAMER, 'color:#38bdf8;font-weight:bold;font-size:14px;');
}})();"""

    def send_test_fb_comment(self, custom_author: str = "Khán Giả FB Group", custom_text: str = "Chúc streamer đánh thắng kèo này nhé! Đẩy comment từ Group FB lên OBS thành công!"):
        streamer = self.player_name_var.get().strip() or "XO"
        pw = self._get_effective_player_password()

        def _t():
            try:
                res = requests.post(
                    self.get_api_endpoint(),
                    json={
                        "action": "pushFacebookComment",
                        "streamerName": streamer,
                        "password": pw,
                        "isAdmin": self.is_admin,
                        "adminPassword": self.admin_password,
                        "fbAuthor": custom_author,
                        "text": custom_text,
                        "fbCommentId": f"test_{int(time.time() * 1000)}",
                    },
                    timeout=10,
                )
                d = res.json()
                if d.get("status") == "success":
                    self.log(f"✅ 🔵 [FB Live] Đã đẩy thử comment của '{custom_author}' lên OBS máy {streamer}!", "SUCCESS")
                    self.refresh_initial_state()
                else:
                    self.log(f"⚠️ Không thể gửi thử Comment FB: {d.get('message', '')}", "WARN")
            except Exception as e:
                self.log(f"❌ Lỗi gửi thử Comment FB: {e}", "ERROR")

        threading.Thread(target=_t, daemon=True).start()

    def show_fb_group_live_bridge_window(self):
        tk = self.tk
        streamer = self.player_name_var.get().strip() or "XO"
        win = tk.Toplevel(self.root)
        win.title(f"🔵 KẾT NỐI COMMENT FACEBOOK GROUP LIVE LÊN OBS — MÁY {streamer}")
        win.geometry("760x620")
        win.configure(bg="#0b0e14")

        hdr = tk.Frame(win, bg="#121721", highlightthickness=1, highlightbackground="#262f40", padx=18, pady=12)
        hdr.pack(fill="x", padx=14, pady=(12, 6))

        tk.Label(
            hdr,
            text=f"🔵 Cầu Nối Đẩy Comment Luồng Live Trong Group Facebook Lên OBS (Máy {streamer})",
            font=("Segoe UI", 12, "bold"),
            fg="#60a5fa",
            bg="#121721",
        ).pack(anchor="w")

        tk.Label(
            hdr,
            text="Giải pháp chuyên dụng cho Streamer phát Live trong Group Facebook (kể cả Nhóm Kín & Nhóm Công Khai) — Không cần duyệt App Meta, không sợ khóa nick!",
            font=("Segoe UI", 9, "bold"),
            fg="#e7ebf0",
            bg="#121721",
            wraplength=700,
            justify="left",
        ).pack(anchor="w", pady=(4, 0))

        steps_card = tk.Frame(win, bg="#121721", highlightthickness=1, highlightbackground="#262f40", padx=18, pady=12)
        steps_card.pack(fill="x", padx=14, pady=6)

        guide_text = (
            "📌 CÁCH SỬ DỤNG CỰC NHANH TRONG 10 GIÂY KHI BẠN BẮT ĐẦU LIVE TRONG GROUP FACEBOOK:\n\n"
            "  • Bước 1: Bấm nút màu vàng 【📋 Copy Mã Tự Động Bắt Comment FB Group】 ở bên dưới.\n"
            "  • Bước 2: Mở bài phát sóng Live của bạn trong Group Facebook trên trình duyệt (Chrome / Cốc Cốc / Edge).\n"
            "  • Bước 3: Ấn phím 【F12】 (hoặc Chuột phải -> Kiểm tra / Inspect) -> Chuyển sang tab 【Console】.\n"
            "            (Nếu trình duyệt hỏi 'Allow pasting / Cho phép dán' ở lần đầu tiên, hãy gõ allow pasting rồi ấn Enter).\n"
            "  • Bước 4: Ấn 【Ctrl + V】 để dán mã vừa copy vào Console rồi ấn 【Enter】.\n"
            "  ✨ XONG! Ở góc trái dưới màn hình Facebook sẽ hiện hộp tín hiệu '🔵 AOE BY XO • Đang bắt Comment FB Group Live'.\n"
            "     Mọi bình luận mới của khán giả trong Group Facebook sẽ tự động bay thẳng lên OBS Khung Chat & Sảnh Live của bạn với nhãn 🔵 [FB]!"
        )
        tk.Label(
            steps_card,
            text=guide_text,
            font=("Segoe UI", 9, "bold"),
            fg="#e7ebf0",
            bg="#121721",
            justify="left",
            anchor="w",
        ).pack(fill="x")

        btn_row = tk.Frame(win, bg="#0b0e14")
        btn_row.pack(fill="x", padx=14, pady=6)

        status_feedback_lbl = tk.Label(
            win,
            text="💡 Mẹo: Bạn có thể bấm '🧪 Gửi thử 1 Comment FB lên OBS' ngay bây giờ để kiểm tra chữ hiện trên OBS!",
            font=("Segoe UI", 9, "bold"),
            fg="#f59e0b",
            bg="#0b0e14",
        )

        def _copy_script_now():
            code = self._generate_fb_group_bridge_js(for_display=False)
            self.root.clipboard_clear()
            self.root.clipboard_append(code)
            status_feedback_lbl.config(
                text=f"✅ Đã Copy mã bắt Comment FB Group (đã mã hóa bảo mật mật khẩu) cho máy '{streamer}'! Hãy mở Facebook -> Ấn F12 (Console) -> Ctrl+V -> Enter!",
                fg="#34d399",
            )
            self.log(f"✅ 🔵 Đã copy mã tự động bắt Comment Facebook Group Live (đã mã hóa bảo mật) cho máy {streamer}!", "SUCCESS")

        def _test_fb_now():
            self.send_test_fb_comment()
            status_feedback_lbl.config(
                text=f"✅ Đã bắn thử 1 Comment gắn nhãn 🔵 [FB] lên OBS Khung Chat và Sảnh Live của máy '{streamer}'!",
                fg="#60a5fa",
            )

        btn_copy_js = tk.Button(
            btn_row,
            text="📋 Copy Mã Tự Động Bắt Comment FB Group (1-Click)",
            command=_copy_script_now,
            font=("Segoe UI", 10, "bold"),
            bg="#f59e0b",
            fg="#0b0e14",
            relief="flat",
            padx=14,
            pady=7,
            cursor="hand2",
        )
        btn_copy_js.pack(side="left", padx=(0, 8))

        btn_test_fb = tk.Button(
            btn_row,
            text="🧪 Gửi thử 1 Comment FB lên OBS",
            command=_test_fb_now,
            font=("Segoe UI", 10, "bold"),
            bg="#2563eb",
            fg="#ffffff",
            relief="flat",
            padx=14,
            pady=7,
            cursor="hand2",
        )
        btn_test_fb.pack(side="left", padx=(0, 8))

        btn_copy_obs_c = tk.Button(
            btn_row,
            text="💬 Copy Link OBS Chat",
            command=self.copy_obs_chat_link,
            font=("Segoe UI", 9, "bold"),
            bg="#121721",
            fg="#e7ebf0",
            relief="flat",
            highlightthickness=1,
            highlightbackground="#262f40",
            padx=12,
            pady=7,
            cursor="hand2",
        )
        btn_copy_obs_c.pack(side="right")

        status_feedback_lbl.pack(fill="x", padx=14, pady=(2, 4))

        code_card = tk.Frame(win, bg="#121721", highlightthickness=1, highlightbackground="#262f40", padx=12, pady=8)
        code_card.pack(fill="both", expand=True, padx=14, pady=(2, 12))
        tk.Label(
            code_card,
            text="🔒 Mã cầu nối tự động (Mật khẩu đã được ẨN & MÃ HÓA BẢO MẬT hoàn toàn — Không lộ mật khẩu khi Live):",
            font=("Segoe UI", 8, "bold"),
            fg="#34d399",
            bg="#121721",
        ).pack(anchor="w", pady=(0, 4))

        code_txt = tk.Text(
            code_card,
            bg="#1a2130",
            fg="#60a5fa",
            font=("Consolas", 8),
            relief="flat",
            padx=8,
            pady=6,
            highlightthickness=1,
            highlightbackground="#262f40",
        )
        code_txt.pack(fill="both", expand=True)
        code_txt.insert("1.0", self._generate_fb_group_bridge_js(for_display=True))
        code_txt.configure(state="disabled")

    def open_web_dashboard(self):
        import webbrowser
        webbrowser.open(self.get_base_server_url())

    def _align_parsed_with_current_match(self, parsed: dict):
        """
        Căn chỉnh đội hình & thứ tự người chơi theo kèo đang LIVE (self.current_match):
        Giúp khi sang Game 2, 3... dù đổi chủ phòng (từ Slot 1-2 chuyển xuống Slot 3-4)
        thì Team Đỏ và Team Xanh vẫn giữ nguyên đúng đội và thứ tự người chơi của Game 1,
        kèm đúng loại Quân mới và Màu cờ mới của từng người.
        """
        cur_m = getattr(self, "current_match", None)
        if not isinstance(cur_m, dict):
            return
        ref_red = cur_m.get("redTeam") or []
        ref_blue = cur_m.get("blueTeam") or []
        r_p = list(parsed.get("redPlayers") or [])
        b_p = list(parsed.get("bluePlayers") or [])
        r_c = list(parsed.get("redCivs") or [])
        b_c = list(parsed.get("blueCivs") or [])
        r_col = list(parsed.get("redColors") or [])
        b_col = list(parsed.get("blueColors") or [])
        if len(ref_red) != len(r_p) or len(ref_blue) != len(b_p) or not r_p:
            return

        ref_red_set = {str(x).strip().lower() for x in ref_red}
        ref_blue_set = {str(x).strip().lower() for x in ref_blue}
        keep_sc = sum(1 for x in r_p if str(x).strip().lower() in ref_red_set) + sum(
            1 for x in b_p if str(x).strip().lower() in ref_blue_set
        )
        swap_sc = sum(1 for x in r_p if str(x).strip().lower() in ref_blue_set) + sum(
            1 for x in b_p if str(x).strip().lower() in ref_red_set
        )
        if swap_sc > keep_sc:
            r_p, b_p = b_p, r_p
            r_c, b_c = b_c, r_c
            r_col, b_col = b_col, r_col

        def _reorder(ref_list, names, civs, cols):
            entries = [
                {"name": n, "lower": str(n).strip().lower(), "civ": c, "col": cl, "used": False}
                for n, c, cl in zip(names, civs, cols)
            ]
            ordered = []
            for ref_name in ref_list:
                rl = str(ref_name).strip().lower()
                found = next((e for e in entries if not e["used"] and e["lower"] == rl), None)
                if found:
                    found["used"] = True
                    ordered.append(found)
                else:
                    ordered.append(None)
            rem = [e for e in entries if not e["used"]]
            ri = 0
            for idx in range(len(ordered)):
                if ordered[idx] is None and ri < len(rem):
                    ordered[idx] = rem[ri]
                    ri += 1
            return (
                [e["name"] for e in ordered],
                [e["civ"] for e in ordered],
                [e["col"] for e in ordered],
            )

        parsed["redPlayers"], parsed["redCivs"], parsed["redColors"] = _reorder(ref_red, r_p, r_c, r_col)
        parsed["bluePlayers"], parsed["blueCivs"], parsed["blueColors"] = _reorder(ref_blue, b_p, b_c, b_col)

    def _send_parsed_diplomacy_to_server(self, parsed: dict, allow_same_civ: bool = False):
        self._align_parsed_with_current_match(parsed)
        red_str = ", ".join(
            f"{p} [{c} - {COLOR_NAMES_VI.get(col, col)}]"
            for p, c, col in zip(parsed["redPlayers"], parsed["redCivs"], parsed["redColors"])
        )
        blue_str = ", ".join(
            f"{p} [{c} - {COLOR_NAMES_VI.get(col, col)}]"
            for p, c, col in zip(parsed["bluePlayers"], parsed["blueCivs"], parsed["blueColors"])
        )
        box_info = ""
        if parsed.get("box") and parsed.get("img_size"):
            bx = parsed["box"]
            iw, ih = parsed["img_size"]
            box_info = f" [Màn {iw}x{ih} • Khung ({bx[0]},{bx[1]})-({bx[2]},{bx[3]}) • Điểm={parsed.get('box_score', 0)}]"

        # Kiểm tra ngay tại Client: Nếu bộ quân 2 đội vẫn giống hệt như trận hiện tại thì suy ra trận đấu vẫn chưa kết thúc / chưa sang ván mới
        if not allow_same_civ and isinstance(getattr(self, "current_match", None), dict):
            cur_games = self.current_match.get("games") or []
            if cur_games:
                last_g = cur_games[-1]
                prev_r = [str(c).strip().upper() for c in (last_g.get("redCivs") or [])]
                prev_b = [str(c).strip().upper() for c in (last_g.get("blueCivs") or [])]
                new_r = [str(c).strip().upper() for c in (parsed.get("redCivs") or [])]
                new_b = [str(c).strip().upper() for c in (parsed.get("blueCivs") or [])]
                same_civ_lineup = (
                    len(prev_r) == len(new_r)
                    and len(prev_b) == len(new_b)
                    and len(prev_r) > 0
                    and ((prev_r == new_r and prev_b == new_b) or (sorted(prev_r) == sorted(new_r) and sorted(prev_b) == sorted(new_b)))
                )
                same_meta = (
                    last_g.get("redPlayers") == parsed.get("redPlayers")
                    and last_g.get("bluePlayers") == parsed.get("bluePlayers")
                    and last_g.get("redColors") == parsed.get("redColors")
                    and last_g.get("blueColors") == parsed.get("blueColors")
                )
                if same_civ_lineup and same_meta:
                    now_ts = time.time()
                    if now_ts - getattr(self, "_last_same_civ_skip_log_ts", 0.0) > 5.0:
                        self._last_same_civ_skip_log_ts = now_ts
                        self.log(
                            f"ℹ️ [Soi quân Diplomacy] Bộ quân vẫn giống hệt Trận #{len(cur_games)} — Trận đấu vẫn chưa sang ván mới (giữ nguyên Trận #{len(cur_games)}).",
                            "DEFAULT",
                        )
                    return

        self.log(f"🎯 Đã quét bảng quân Diplomacy{box_info}:", "TEAM")
        self.log(f"   🔴 Team Đỏ  : {red_str}", "TEAM")
        self.log(f"   🔵 Team Xanh: {blue_str}", "TEAM")

        self._last_diplomacy_push_ts = time.time()

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
            self._last_diplomacy_push_ts = time.time()
            self.log(f"✅ ☁️ Đồng bộ Server: {data.get('message', '')}", "SUCCESS")
            if data.get("match"):
                self.current_match = data["match"]
                self._update_battle_arena_ui(data["match"])
        except Exception as e:
            self.log(f"❌ Lỗi gửi dữ liệu lên Server: {e}", "ERROR")

    def _grab_all_monitors_bgr(self):
        """Chụp màn hình chính, cửa sổ game đang mở và các màn hình phụ để luôn bắt chuẩn bảng Diplomacy ở mọi Screen Size."""
        frames = []
        primary_bgr = None
        try:
            pil_primary = ImageGrab.grab()
            primary_bgr = cv2.cvtColor(np.array(pil_primary), cv2.COLOR_RGB2BGR)
            frames.append(primary_bgr)
        except Exception:
            pass

        if os.name == "nt":
            try:
                import ctypes
                from ctypes import wintypes
                user32 = ctypes.windll.user32

                # Kiểm tra khung cửa sổ đang active (hoặc cửa sổ Age of Empires ở chế độ 1366x768 / 1600x900 / Windowed)
                candidate_hwnds = []
                fg_hwnd = user32.GetForegroundWindow()
                if fg_hwnd:
                    candidate_hwnds.append(fg_hwnd)
                for title in ("Age of Empires Expansion", "Age of Empires"):
                    h_aoe = user32.FindWindowW(None, title)
                    if h_aoe and h_aoe not in candidate_hwnds:
                        candidate_hwnds.append(h_aoe)

                for hwnd in candidate_hwnds:
                    wrect = wintypes.RECT()
                    if user32.GetWindowRect(hwnd, ctypes.byref(wrect)):
                        wl, wt, wr, wb = int(wrect.left), int(wrect.top), int(wrect.right), int(wrect.bottom)
                        ww, wh = wr - wl, wb - wt
                        if ww >= 600 and wh >= 400:
                            if primary_bgr is not None:
                                ph, pw = primary_bgr.shape[:2]
                                if 0 <= wl and 0 <= wt and wr <= pw and wb <= ph and (ww < pw - 20 or wh < ph - 20):
                                    sub_win = primary_bgr[wt:wb, wl:wr]
                                    if sub_win.size > 0:
                                        frames.insert(0, sub_win)

                if user32.GetSystemMetrics(80) > 1:
                    MONITORENUMPROC = ctypes.WINFUNCTYPE(
                        ctypes.c_int,
                        ctypes.c_ulong,
                        ctypes.c_ulong,
                        ctypes.POINTER(wintypes.RECT),
                        ctypes.c_double,
                    )
                    rects = []

                    def _cb(hmon, hdc, lprect, lparam):
                        r = lprect.contents
                        rects.append((int(r.left), int(r.top), int(r.right), int(r.bottom)))
                        return 1

                    user32.EnumDisplayMonitors(0, 0, MONITORENUMPROC(_cb), 0)
                    for left, top, right, bottom in rects:
                        if left == 0 and top == 0 and primary_bgr is not None:
                            continue
                        if right - left >= 450 and bottom - top >= 300:
                            pil_mon = ImageGrab.grab(bbox=(left, top, right, bottom), all_screens=True)
                            frames.append(cv2.cvtColor(np.array(pil_mon), cv2.COLOR_RGB2BGR))
            except Exception:
                pass
        return frames

    def _get_effective_known_players(self):
        """Gộp danh sách tài khoản hệ thống và tên người chơi trong kèo đang LIVE để nhận diện chuẩn xác ở các ván tiếp theo."""
        merged = list(self.known_players or [])
        seen = {
            (p.get("name") if isinstance(p, dict) else str(p)).strip().lower()
            for p in merged
            if p
        }
        cur_m = getattr(self, "current_match", None)
        if isinstance(cur_m, dict):
            extra_names = list(cur_m.get("redTeam") or []) + list(cur_m.get("blueTeam") or [])
            for g in (cur_m.get("games") or []):
                if isinstance(g, dict):
                    extra_names.extend(g.get("redPlayers") or [])
                    extra_names.extend(g.get("bluePlayers") or [])
            for n in extra_names:
                ns = str(n or "").strip()
                if ns and ns.lower() not in seen:
                    seen.add(ns.lower())
                    merged.insert(0, ns)
        return merged

    def manual_scan_screen(self):
        def _task():
            try:
                frames = self._grab_all_monitors_bgr()
                sizes_str = ", ".join(f"{f.shape[1]}x{f.shape[0]}" for f in frames)
                self.log(f"🔍 [Điều tra Quét Diplomacy] Đang quét {len(frames)} khung hình ({sizes_str})...", "DEFAULT")
                reasons = []
                eff_known = self._get_effective_known_players()
                for idx, img_bgr in enumerate(frames):
                    res = self.scanner.parse_diplomacy_from_image(
                        img_bgr,
                        streamer_name=self.player_name_var.get().strip(),
                        known_players=eff_known,
                        force=True,
                    )
                    if res and res.get("status") == "ok":
                        self._send_parsed_diplomacy_to_server(res, allow_same_civ=False)
                        return
                    if self.scanner.last_reject_reason:
                        reasons.append(f"Khung #{idx+1} ({img_bgr.shape[1]}x{img_bgr.shape[0]}): {self.scanner.last_reject_reason}")
                detail = " | ".join(reasons) if reasons else "Không phát hiện hộp thoại Diplomacy"
                self.log(f"⚠️ Không tìm thấy bảng DIPLOMACY: {detail}", "WARN")
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
                if img_bgr is None:
                    self.log(f"❌ Không thể giải mã file ảnh '{os.path.basename(file_path)}'!", "ERROR")
                    return
                self.log(
                    f"🖼️ [Điều tra Ảnh] Đang phân tích '{os.path.basename(file_path)}' ({img_bgr.shape[1]}x{img_bgr.shape[0]})...",
                    "DEFAULT",
                )
                res = self.scanner.parse_diplomacy_from_image(
                    img_bgr,
                    streamer_name=self.player_name_var.get().strip(),
                    known_players=self._get_effective_known_players(),
                    force=True,
                )
                if not res or res.get("status") != "ok":
                    reason = self.scanner.last_reject_reason or "Không chứa bảng DIPLOMACY hợp lệ"
                    self.log(f"⚠️ Ảnh '{os.path.basename(file_path)}' bị từ chối: {reason}", "WARN")
                    return
                self._send_parsed_diplomacy_to_server(res, allow_same_civ=False)
            except Exception as e:
                self.log(f"❌ Lỗi đọc ảnh: {e}", "ERROR")

        threading.Thread(target=_task, daemon=True).start()

    def _trigger_global_hype_hotkey(self, key_name: str = "F8"):
        """
        Xử lý phím tắt F8 (Cả trong màn hình Game AOE lẫn trên App):
        Chỉ hiển thị hiệu ứng 'Tay đâu, tayyyy đâuuuuu' ở khung 'Link OBS' (overlay.html),
        đồng thời làm mờ khung 'Link OBS' và khung 'OBS Chat' mỗi khi ấn F8.
        """
        if not self.is_logged_in:
            return
        now = time.time()
        if now - getattr(self, "_last_global_hype_hotkey_ts", 0.0) < 1.2:
            return
        self._last_global_hype_hotkey_ts = now
        shout_text = "Tay đâu, tayyyy đâuuuuu"
        self.log(f"🔥 [Phím tắt {key_name}] Đang bắn hiệu ứng \"{shout_text}\" lên khung Link OBS Bảng Quân!", "SUCCESS")

        # Phát âm báo 2 nốt hứng khởi khi ấn F8 trong Game
        if os.name == "nt":
            def _beep_hype():
                try:
                    import winsound
                    winsound.Beep(987, 90)
                    winsound.Beep(1318, 150)
                except Exception:
                    pass
            threading.Thread(target=_beep_hype, daemon=True).start()

        # Hiệu ứng rung lắc nhẹ & nổi bật ngay trên Bảng Tỉ Số Trung Tâm của App PC (không đẩy vào khung Chat)
        def _animate_local_hype(step: int = 0):
            try:
                if step == 0:
                    self._saved_mode_txt_before_hype = self.match_mode_lbl.cget("text")
                    self.match_mode_lbl.configure(text="🔥 CHIẾN THẮNG NGHẸT THỞ [F8] 🔥", fg="#fef08a")
                    self.c_mode_summary_lbl.configure(text=f"🙌 \"{shout_text}\" 🙌", fg="#fbbf24")
                if step < 18:
                    if hasattr(self, "match_history_lbl"):
                        self.match_history_lbl.configure(
                            text=f"🙌 {shout_text} 🔥",
                            fg="#fef08a" if step % 2 == 0 else "#fbbf24",
                            bg="#2b1810",
                        )
                    self.root.after(120, lambda: _animate_local_hype(step + 1))
                else:
                    if hasattr(self, "current_match") and self.current_match:
                        self._update_battle_arena_ui(self.current_match)
                    else:
                        self.match_mode_lbl.configure(
                            text=getattr(self, "_saved_mode_txt_before_hype", "Kèo 1v1 - Chạm 7"),
                            fg="#f59e0b",
                        )
            except Exception:
                pass

        self.root.after(0, lambda: _animate_local_hype(0))

        def _task():
            try:
                res = requests.post(
                    self.get_api_endpoint(),
                    json={
                        "action": "triggerHypeShout",
                        "streamerName": self.player_name_var.get().strip(),
                        "senderName": self.player_name_var.get().strip(),
                        "password": self._get_effective_player_password(),
                        "isAdmin": self.is_admin,
                        "adminPassword": self.admin_password,
                        "text": shout_text,
                        "subText": "🔥 CHIẾN THẮNG NGHẸT THỞ • QUẨY LÊN ANH EM ƠI! 🙌",
                        "durationMs": 6500,
                    },
                    timeout=10,
                )
                data = res.json()
                if data.get("status") == "success":
                    self.refresh_initial_state()
                else:
                    self.log(f"⚠️ {data.get('message', 'Không bắn được hiệu ứng F8')}", "WARN")
            except Exception as e:
                self.log(f"❌ Lỗi bắn hiệu ứng F8: {e}", "ERROR")

        threading.Thread(target=_task, daemon=True).start()

    def _validate_can_score_current_game(self):
        """
        Kiểm tra quy tắc chấm tỉ số F5 / F6:
        1. Phải có trận đấu đang diễn ra và quân của trận đấu đó (redCivs & blueCivs) đã hiển thị hợp lệ.
        2. Mỗi trận đấu chỉ có duy nhất một đội chiến thắng (chỉ chấm khi trận hiện tại đang PENDING).
        """
        match = getattr(self, "current_match", None)
        if not match or not isinstance(match, dict):
            return (
                False,
                "Quân của trận đấu chưa hiển thị! Hãy ấn nút Diplomacy trong game để hiện bảng quân trước khi bấm F5/F6.",
            )
        games = match.get("games") or []
        if not games:
            return (
                False,
                "Chưa có bảng quân của trận đấu! Hãy ấn nút Diplomacy trong game để hiện bảng quân trước khi bấm F5/F6.",
            )
        latest_game = games[-1]
        latest_winner = str(latest_game.get("winner") or "PENDING").upper()
        if latest_winner in ("RED", "BLUE"):
            last_w = "Team Đỏ" if latest_winner == "RED" else "Team Xanh"
            return (
                False,
                f"Trận #{len(games)} đã ghi nhận {last_w} chiến thắng! Mỗi trận chỉ có 1 đội thắng duy nhất — hãy ấn nút Diplomacy trong game để đọc quân trận mới.",
            )
        red_civs = latest_game.get("redCivs") or []
        blue_civs = latest_game.get("blueCivs") or []
        has_valid_red = len(red_civs) > 0 and all(c and str(c).strip() not in ("---", "Random") for c in red_civs)
        has_valid_blue = len(blue_civs) > 0 and all(c and str(c).strip() not in ("---", "Random") for c in blue_civs)
        if not (has_valid_red and has_valid_blue):
            return (
                False,
                "Quân của trận đấu chưa hiển thị đầy đủ! Hãy ấn nút Diplomacy trong game để hiện bảng quân trước khi bấm F5/F6.",
            )
        return (True, "")

    def _trigger_global_winner_hotkey(self, winner: str, key_name: str = "F5"):
        """Xử lý phím tắt F5 (Thắng Đỏ) / F6 (Thắng Xanh) cả khi đang ở trong màn hình Game AOE lẫn trên App."""
        if not self.is_logged_in:
            return
        now = time.time()
        if now - getattr(self, "_last_global_score_hotkey_ts", 0.0) < 1.0:
            return
        self._last_global_score_hotkey_ts = now

        can_score, reason = self._validate_can_score_current_game()
        if not can_score:
            self.log(f"⛔ [Phím tắt {key_name}] Từ chối cập nhật tỉ số: {reason}", "WARN")
            try:
                self.root.after(0, lambda: self.c_mode_summary_lbl.config(text=f"⛔ {reason}", fg="#f87171"))
            except Exception:
                pass
            if os.name == "nt":
                try:
                    import winsound
                    threading.Thread(target=lambda: winsound.Beep(330, 140), daemon=True).start()
                except Exception:
                    pass
            return

        team_label = "Team Đỏ (+1)" if winner == "RED" else "Team Xanh (+1)"
        self.log(f"⌨️ [Phím tắt {key_name}] Ghi nhận {team_label} từ bàn phím — đang cập nhật tỉ số...", "TEAM")
        # Phát tiếng bíp xác nhận ngắn để người chơi đang trong màn hình Game toàn màn hình biết đã ăn phím F5/F6
        if os.name == "nt":
            try:
                import winsound
                freq = 880 if winner == "RED" else 1046
                threading.Thread(target=lambda: winsound.Beep(freq, 110), daemon=True).start()
            except Exception:
                pass
        self.set_current_winner(winner, skip_local_validation=True)

    def set_current_winner(self, winner: str, skip_local_validation: bool = False):
        if not skip_local_validation:
            can_score, reason = self._validate_can_score_current_game()
            if not can_score:
                self.log(f"⛔ Từ chối cập nhật tỉ số: {reason}", "WARN")
                try:
                    self.root.after(0, lambda: self.c_mode_summary_lbl.config(text=f"⛔ {reason}", fg="#f87171"))
                except Exception:
                    pass
                return

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
                    self.refresh_initial_state()
                else:
                    err_txt = data.get("message", "Không thể cập nhật tỉ số")
                    self.log(f"⚠️ {err_txt}", "WARN")
                    try:
                        self.root.after(0, lambda: self.c_mode_summary_lbl.config(text=f"⛔ {err_txt}", fg="#f87171"))
                    except Exception:
                        pass
            except Exception as e:
                self.log(f"❌ Lỗi cập nhật tỉ số: {e}", "ERROR")

        threading.Thread(target=_task, daemon=True).start()

    def undo_last_winner(self):
        def _task():
            try:
                api_url = self.get_api_endpoint()
                res = requests.post(
                    api_url,
                    json={
                        "action": "undoLastWinner",
                        "streamerName": self.player_name_var.get().strip(),
                        "updatedBy": self.player_name_var.get().strip(),
                        "password": self._get_effective_player_password(),
                        "isAdmin": self.is_admin,
                        "adminPassword": self.admin_password,
                    },
                    timeout=10,
                )
                data = res.json()
                if data.get("status") == "success":
                    self.log(f"✅ ↩️ {data.get('message', 'Đã hoàn tác kết quả ván vừa rồi!')}", "SUCCESS")
                    if data.get("match"):
                        self.current_match = data["match"]
                        self._update_battle_arena_ui(data["match"])
                    self.refresh_initial_state()
                else:
                    self.log(f"⚠️ {data.get('message', 'Không thể hoàn tác kết quả')}", "WARN")
            except Exception as e:
                self.log(f"❌ Lỗi hoàn tác kết quả: {e}", "ERROR")

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
                    self.scanner.last_dialog_signature = None
                    self._reset_battle_arena_ui("Kèo đấu đã kết thúc • Ấn nút Diplomacy trong game để bắt đầu kèo mới")
                else:
                    self.log(f"⚠️ {data.get('message', 'Không thể kết thúc kèo')}", "WARN")
            except Exception as e:
                self.log(f"❌ Lỗi kết thúc kèo: {e}", "ERROR")

        threading.Thread(target=_task, daemon=True).start()

    def _auto_finish_match_sync(self):
        """Tự động gửi lệnh kết thúc TOÀN BỘ kèo đấu đang LIVE khi người chơi tắt Tool (đóng cửa sổ / thoát ứng dụng)."""
        if self._did_finish_on_exit:
            return False
        self._did_finish_on_exit = True
        try:
            streamer = ""
            try:
                streamer = self.player_name_var.get().strip()
            except Exception:
                streamer = ""
            if not streamer:
                streamer = str(self.settings.get("player_name", "") or "").strip()
            pw = self._get_effective_player_password() or str(self.settings.get("player_password", "") or "").strip()
            if not streamer or not pw:
                return False
            api_url = self.get_api_endpoint()
            payload = {
                "action": "finishMatch",
                "reason": "APP_CLOSED",
                "streamerName": streamer,
                "updatedBy": streamer,
                "password": pw,
                "isAdmin": self.is_admin,
                "adminPassword": self.admin_password,
            }
            # Thử tối đa 2 lần (Server Render có thể phản hồi chậm) để đảm bảo kèo đấu chắc chắn được kết thúc
            for attempt in range(2):
                try:
                    res = requests.post(api_url, json=payload, timeout=4.0 if attempt == 0 else 3.0)
                    data = res.json()
                    if data.get("status") == "success":
                        return True
                    # Fallback cho Server cũ chưa hỗ trợ reason=APP_CLOSED
                    if attempt == 0:
                        payload.pop("reason", None)
                except Exception:
                    continue
        except Exception:
            pass
        return False

    def on_closing(self):
        """Sự kiện đóng cửa sổ Tool: lưu cấu hình, TỰ ĐỘNG KẾT THÚC kèo đấu đang LIVE trên Web/OBS rồi thoát."""
        if getattr(self, "_is_closing", False):
            return
        self._is_closing = True
        self.running = False
        try:
            self.save_current_config()
        except Exception:
            pass

        if self.is_logged_in:
            # Hiện thông báo ngắn trong lúc gửi lệnh kết thúc kèo lên Server
            try:
                self.root.title(f"{APP_TITLE} — 🏁 Đang kết thúc kèo đấu & thoát...")
                if hasattr(self, "status_lbl"):
                    self.status_lbl.config(text="🏁 Đang kết thúc kèo đấu LIVE trước khi thoát...", fg="#fbbf24")
                self.root.update_idletasks()
                self.root.update()
            except Exception:
                pass
            self._auto_finish_match_sync()

        try:
            self.root.destroy()
        except Exception:
            sys.exit(0)

    def _monitor_diplomacy_events(self):
        """
        Bắt sự kiện bàn phím & chuột toàn cục 3 tầng (3-Layer In-Game Hotkey Engine)
        ngay cả khi người chơi đang ở trong màn hình Game AOE (EMPIRESX.EXE Fullscreen / Windowed):
        - Tầng 1: Windows Low-Level Keyboard Hook (SetWindowsHookExW WH_KEYBOARD_LL = 13) bắt phím trực tiếp từ Kernel Input Queue trước DirectInput.
        - Tầng 2: GetAsyncKeyState (kiểm tra cả bit giữ 0x8000 lẫn bit gõ nhanh 0x0001 ở chu kỳ 20ms không nghẽn).
        - Tầng 3: RegisterHotKey (WM_HOTKEY) kèm vòng lặp bơm thông điệp chuẩn (PeekMessageW + TranslateMessage + DispatchMessageW).
        """
        if os.name != "nt":
            return
        try:
            import ctypes
            from ctypes import wintypes

            user32 = ctypes.windll.user32
            kernel32 = ctypes.windll.kernel32

            VK_LBUTTON = 0x01
            VK_F2 = 0x71
            VK_F5 = 0x74
            VK_F6 = 0x75
            VK_F8 = 0x77
            VK_MENU = 0x12
            VK_D = 0x44
            MOD_NOREPEAT = 0x4000
            WM_HOTKEY = 0x0312
            WM_KEYDOWN = 0x0100
            WM_SYSKEYDOWN = 0x0104
            WH_KEYBOARD_LL = 13
            HOTKEY_ID_F5 = 505
            HOTKEY_ID_F6 = 506
            HOTKEY_ID_F8 = 508

            # Bộ chống dội phím (debounce) chung cho cả 3 tầng để mỗi lần bấm chỉ kích hoạt đúng 1 lần
            last_fire_ts = {"F2": 0.0, "F5": 0.0, "F6": 0.0, "F8": 0.0}
            hook_f2_pending = [False]

            def _fire_f5():
                if not self.is_logged_in:
                    return
                now_t = time.time()
                if now_t - last_fire_ts["F5"] < 0.45:
                    return
                last_fire_ts["F5"] = now_t
                self.root.after(0, lambda: self._trigger_global_winner_hotkey("RED", "F5 (In-Game)"))

            def _fire_f6():
                if not self.is_logged_in:
                    return
                now_t = time.time()
                if now_t - last_fire_ts["F6"] < 0.45:
                    return
                last_fire_ts["F6"] = now_t
                self.root.after(0, lambda: self._trigger_global_winner_hotkey("BLUE", "F6 (In-Game)"))

            def _fire_f8():
                if not self.is_logged_in:
                    return
                now_t = time.time()
                if now_t - last_fire_ts["F8"] < 0.45:
                    return
                last_fire_ts["F8"] = now_t
                self.root.after(0, lambda: self._trigger_global_hype_hotkey("F8 (In-Game)"))

            # --- TẦNG 1: CÀI ĐẶT LOW-LEVEL KEYBOARD HOOK (WH_KEYBOARD_LL = 13) ---
            LRESULT = ctypes.c_ssize_t
            HOOKPROC = ctypes.WINFUNCTYPE(LRESULT, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM)

            class KBDLLHOOKSTRUCT(ctypes.Structure):
                _fields_ = [
                    ("vkCode", wintypes.DWORD),
                    ("scanCode", wintypes.DWORD),
                    ("flags", wintypes.DWORD),
                    ("time", wintypes.DWORD),
                    ("dwExtraInfo", ctypes.c_size_t),
                ]

            user32.SetWindowsHookExW.argtypes = [ctypes.c_int, HOOKPROC, wintypes.HINSTANCE, wintypes.DWORD]
            user32.SetWindowsHookExW.restype = ctypes.c_void_p
            user32.CallNextHookEx.argtypes = [ctypes.c_void_p, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM]
            user32.CallNextHookEx.restype = LRESULT
            user32.UnhookWindowsHookEx.argtypes = [ctypes.c_void_p]
            user32.UnhookWindowsHookEx.restype = wintypes.BOOL
            kernel32.GetModuleHandleW.argtypes = [wintypes.LPCWSTR]
            kernel32.GetModuleHandleW.restype = wintypes.HMODULE

            def _ll_keyboard_callback(nCode, wParam, lParam):
                try:
                    if nCode >= 0 and wParam in (WM_KEYDOWN, WM_SYSKEYDOWN) and lParam:
                        kb = ctypes.cast(lParam, ctypes.POINTER(KBDLLHOOKSTRUCT)).contents
                        vk = kb.vkCode
                        if vk == VK_F5:
                            _fire_f5()
                        elif vk == VK_F6:
                            _fire_f6()
                        elif vk == VK_F8:
                            _fire_f8()
                        elif vk == VK_F2:
                            now_t = time.time()
                            if now_t - last_fire_ts["F2"] >= 0.45:
                                last_fire_ts["F2"] = now_t
                                hook_f2_pending[0] = True
                except Exception:
                    pass
                return user32.CallNextHookEx(None, nCode, wParam, lParam)

            # Giữ tham chiếu cứng trên self để Garbage Collector không thu hồi callback C
            self._ll_keyboard_hook_proc = HOOKPROC(_ll_keyboard_callback)
            hook_id = None
            try:
                hmod = kernel32.GetModuleHandleW(None)
                hook_id = user32.SetWindowsHookExW(WH_KEYBOARD_LL, self._ll_keyboard_hook_proc, hmod, 0)
                if not hook_id:
                    hook_id = user32.SetWindowsHookExW(WH_KEYBOARD_LL, self._ll_keyboard_hook_proc, None, 0)
            except Exception:
                hook_id = None

            # --- TẦNG 3: ĐĂNG KÝ OS HOTKEY (WM_HOTKEY) DỰ PHÒNG ---
            try:
                user32.RegisterHotKey(None, HOTKEY_ID_F5, MOD_NOREPEAT, VK_F5)
                user32.RegisterHotKey(None, HOTKEY_ID_F6, MOD_NOREPEAT, VK_F6)
                user32.RegisterHotKey(None, HOTKEY_ID_F8, MOD_NOREPEAT, VK_F8)
            except Exception:
                pass

            prev_lbtn = False
            prev_f2 = False
            prev_f5 = False
            prev_f6 = False
            prev_f8 = False
            prev_alt_d = False
            msg = wintypes.MSG()

            while self.running:
                try:
                    # 1. Bơm toàn bộ hàng đợi thông điệp Windows (bắt buộc cho cả WH_KEYBOARD_LL và WM_HOTKEY)
                    while user32.PeekMessageW(ctypes.byref(msg), None, 0, 0, 1):
                        if self.is_logged_in and msg.message == WM_HOTKEY:
                            if msg.wParam == HOTKEY_ID_F5:
                                _fire_f5()
                            elif msg.wParam == HOTKEY_ID_F6:
                                _fire_f6()
                            elif msg.wParam == HOTKEY_ID_F8:
                                _fire_f8()
                        user32.TranslateMessage(ctypes.byref(msg))
                        user32.DispatchMessageW(ctypes.byref(msg))

                    if not self.is_logged_in:
                        time.sleep(0.04)
                        continue

                    # 2. TẦNG 2: Kiểm tra trực tiếp trạng thái phím F5 / F6 / F8 bằng GetAsyncKeyState
                    # Kết hợp cả bit 0x8000 (đang giữ phím) và bit 0x0001 (vừa gõ nhanh giữa 2 nhịp quét)
                    s_f5 = user32.GetAsyncKeyState(VK_F5)
                    s_f6 = user32.GetAsyncKeyState(VK_F6)
                    s_f8 = user32.GetAsyncKeyState(VK_F8)
                    f5_down = (s_f5 & 0x8000) != 0
                    f6_down = (s_f6 & 0x8000) != 0
                    f8_down = (s_f8 & 0x8000) != 0

                    if (f5_down and not prev_f5) or ((s_f5 & 0x0001) != 0 and not prev_f5):
                        _fire_f5()
                    if (f6_down and not prev_f6) or ((s_f6 & 0x0001) != 0 and not prev_f6):
                        _fire_f6()
                    if (f8_down and not prev_f8) or ((s_f8 & 0x0001) != 0 and not prev_f8):
                        _fire_f8()

                    prev_f5 = f5_down
                    prev_f6 = f6_down
                    prev_f8 = f8_down

                    if not self.auto_scan_var.get():
                        hook_f2_pending[0] = False
                        time.sleep(0.02)
                        continue

                    s_f2 = user32.GetAsyncKeyState(VK_F2)
                    f2_down = (s_f2 & 0x8000) != 0
                    alt_down = (user32.GetAsyncKeyState(VK_MENU) & 0x8000) != 0
                    d_down = (user32.GetAsyncKeyState(VK_D) & 0x8000) != 0
                    alt_d_down = alt_down and d_down
                    s_lbtn = user32.GetAsyncKeyState(VK_LBUTTON)
                    lbtn_down = (s_lbtn & 0x8000) != 0
                    lbtn_clicked = (lbtn_down and not prev_lbtn) or ((s_lbtn & 0x0001) != 0 and not prev_lbtn)

                    triggered = False
                    reason = ""

                    if hook_f2_pending[0] or (f2_down and not prev_f2) or ((s_f2 & 0x0001) != 0 and not prev_f2):
                        hook_f2_pending[0] = False
                        triggered = True
                        reason = "F2"
                    elif alt_d_down and not prev_alt_d:
                        triggered = True
                        reason = "Alt+D"
                    elif lbtn_clicked:
                        pt = wintypes.POINT()
                        if user32.GetCursorPos(ctypes.byref(pt)):
                            scr_w = max(1, user32.GetSystemMetrics(0))
                            scr_h = max(1, user32.GetSystemMetrics(1))
                            s_rx = pt.x / float(scr_w)
                            s_ry = pt.y / float(scr_h)
                            if 0.0 <= s_ry <= 0.085 and 0.65 <= s_rx <= 0.96:
                                triggered = True
                                reason = "Click Diplomacy"
                            else:
                                hwnd = user32.GetForegroundWindow()
                                rect = wintypes.RECT()
                                if hwnd and user32.GetWindowRect(hwnd, ctypes.byref(rect)):
                                    w = max(1, rect.right - rect.left)
                                    h = max(1, rect.bottom - rect.top)
                                    rel_x = (pt.x - rect.left) / float(w)
                                    rel_y = (pt.y - rect.top) / float(h)
                                    if 0.0 <= rel_y <= 0.085 and 0.65 <= rel_x <= 0.96:
                                        triggered = True
                                        reason = "Click Diplomacy"

                    prev_f2 = f2_down
                    prev_alt_d = alt_d_down
                    prev_lbtn = lbtn_down

                    if triggered:
                        self._diplomacy_trigger_reason = reason
                        if time.time() - getattr(self, "_last_trigger_log_ts", 0.0) > 2.5:
                            self._last_trigger_log_ts = time.time()
                            self.log(f"🔍 [Sự kiện {reason}] Phát hiện thao tác mở Diplomacy — đang quét bảng quân...", "DEFAULT")
                        # Không dùng time.sleep() ở đây để tránh làm nghẽn vòng lặp bắt phím F5/F6/F8
                        self._diplomacy_scan_window_until = time.time() + 2.6
                except Exception:
                    pass
                time.sleep(0.02)

            if hook_id:
                try:
                    user32.UnhookWindowsHookEx(hook_id)
                except Exception:
                    pass
            try:
                user32.UnregisterHotKey(None, HOTKEY_ID_F5)
                user32.UnregisterHotKey(None, HOTKEY_ID_F6)
                user32.UnregisterHotKey(None, HOTKEY_ID_F8)
            except Exception:
                pass
        except Exception:
            pass

    def _background_worker(self):
        last_heartbeat = time.time()
        last_social_sync = time.time()
        while self.running:
            try:
                # Tự động quét màn hình khi bật Auto Scan (kể cả khi game AOE chạy quyền Administrator chặn phím tắt UIPI)
                # Bộ lọc verify_is_diplomacy_dialog + OCR đảm bảo chỉ kích hoạt khi bảng DIPLOMACY thực sự đang mở trên màn hình
                if self.is_logged_in and self.auto_scan_var.get():
                    frames = self._grab_all_monitors_bgr()
                    in_hotkey_window = time.time() < self._diplomacy_scan_window_until
                    force_scan = (self.current_match is None) or in_hotkey_window
                    eff_known = self._get_effective_known_players()
                    for img_bgr in frames:
                        res = self.scanner.parse_diplomacy_from_image(
                            img_bgr,
                            streamer_name=self.player_name_var.get().strip(),
                            known_players=eff_known,
                            force=force_scan,
                        )
                        if res and res.get("status") == "ok":
                            self._diplomacy_scan_window_until = 0.0
                            self._send_parsed_diplomacy_to_server(res, allow_same_civ=False)
                            break
                        elif res and res.get("status") == "unchanged":
                            self._diplomacy_scan_window_until = 0.0
                            break
                        else:
                            rej = self.scanner.last_reject_reason
                            # Chỉ ghi log điều tra nếu có hộp thoại ứng viên bị từ chối ở bước OCR/Dòng hoặc vừa bấm mở Diplomacy
                            is_key_trig = in_hotkey_window and getattr(self, "_diplomacy_trigger_reason", "") in (
                                "F2",
                                "Alt+D",
                                "Click Diplomacy",
                            )
                            if rej and (is_key_trig or "Dòng " in rej or "Số dòng" in rej or "Số người chơi" in rej):
                                now_ts = time.time()
                                if (now_ts - self._last_auto_diag_log_ts > 4.0) or (rej != self._last_auto_diag_reason):
                                    self._last_auto_diag_log_ts = now_ts
                                    self._last_auto_diag_reason = rej
                                    self.log(
                                        f"🔎 [Điều tra Auto-Scan {img_bgr.shape[1]}x{img_bgr.shape[0]}] {rej}",
                                        "WARN",
                                    )

                # Định kỳ đồng bộ trạng thái Bạn bè Live, Khung Chat & Sao mỗi 8 giây
                if self.is_logged_in and (time.time() - last_social_sync > 8.0):
                    last_social_sync = time.time()
                    self.refresh_initial_state()

                # Gửi heartbeat mỗi 25 giây để Server biết App PC còn mở (quá 3 phút mất tín hiệu → Server tự kết thúc kèo)
                if self.is_logged_in and (time.time() - last_heartbeat > 25.0):
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
            time.sleep(0.35)

    def open_register_account_dialog(self):
        tk = self.tk
        win = tk.Toplevel(self.root)
        win.title("✨ Đăng Ký Tài Khoản XO Mới (Dùng Thử 7 Ngày + Chơi 5 Mini Games)")
        win.geometry("430x340")
        win.configure(bg="#0b0e14")
        win.resizable(False, False)
        win.transient(self.root)
        win.grab_set()

        card = tk.Frame(win, bg="#121721", highlightthickness=1, highlightbackground="#f59e0b", padx=20, pady=16)
        card.pack(fill="both", expand=True, padx=14, pady=14)

        tk.Label(
            card,
            text="✨ TẠO TÀI KHOẢN XO MỚI",
            font=("Segoe UI", 12, "bold"),
            fg="#fbbf24",
            bg="#121721",
        ).pack(anchor="w")
        tk.Label(
            card,
            text="Tài khoản dùng chung trên Tool PC, Sảnh Kèo Web & 5 Mini Games.\nTặng ngay 7 ngày dùng thử Gói Đồng (BRONZE).",
            font=("Segoe UI", 8, "bold"),
            fg="#94a3b8",
            bg="#121721",
            justify="left",
        ).pack(anchor="w", pady=(2, 10))

        name_v = tk.StringVar()
        pw_v = tk.StringVar()
        cpw_v = tk.StringVar()

        for lbl_txt, var, is_pw in (
            ("Tên Tài Khoản (2-20 ký tự):", name_v, False),
            ("Mật khẩu (tối thiểu 6 ký tự):", pw_v, True),
            ("Nhập lại mật khẩu:", cpw_v, True),
        ):
            tk.Label(card, text=lbl_txt, font=("Segoe UI", 8, "bold"), fg="#cbd5e1", bg="#121721").pack(anchor="w", pady=(4, 1))
            tk.Entry(
                card,
                textvariable=var,
                show="•" if is_pw else "",
                font=("Segoe UI", 10, "bold"),
                bg="#1a2130",
                fg="#ffffff",
                insertbackground="#f59e0b",
                relief="flat",
                highlightthickness=1,
                highlightbackground="#384659",
            ).pack(fill="x", ipady=3)

        status_l = tk.Label(card, text="", font=("Segoe UI", 8, "bold"), fg="#fbbf24", bg="#121721")
        status_l.pack(anchor="w", pady=(6, 4))

        def _do_reg():
            uname = name_v.get().strip()
            pw = pw_v.get().strip()
            cpw = cpw_v.get().strip()
            if not uname or not pw:
                status_l.configure(text="⚠️ Vui lòng nhập đầy đủ Tên tài khoản và Mật khẩu!", fg="#f87171")
                return
            if pw != cpw:
                status_l.configure(text="⚠️ Mật khẩu xác nhận không khớp!", fg="#f87171")
                return
            status_l.configure(text="⏳ Đang đăng ký tài khoản lên máy chủ...", fg="#fbbf24")

            def _worker():
                try:
                    res = requests.post(
                        self.get_api_endpoint(),
                        json={
                            "action": "registerPlayer",
                            "playerName": uname,
                            "password": pw,
                            "confirmPassword": cpw,
                        },
                        timeout=10,
                    )
                    d = res.json()
                    if d.get("status") == "success":
                        def _ok():
                            self.player_name_var.set(d.get("playerName") or uname)
                            self.player_pass_var.set(pw)
                            win.destroy()
                            self.login_and_start()
                        self.root.after(0, _ok)
                    else:
                        self.root.after(0, lambda: status_l.configure(text=f"❌ {d.get('message', 'Đăng ký thất bại')}", fg="#f87171"))
                except Exception as ex:
                    self.root.after(0, lambda: status_l.configure(text=f"❌ Lỗi kết nối: {ex}", fg="#f87171"))

            threading.Thread(target=_worker, daemon=True).start()

        tk.Button(
            card,
            text="🚀 Đăng Ký & Đăng Nhập Ngay",
            command=_do_reg,
            font=("Segoe UI", 10, "bold"),
            bg="#f59e0b",
            fg="#0b0e14",
            relief="flat",
            pady=6,
            cursor="hand2",
        ).pack(fill="x", pady=(4, 0))


class TkMinigamesHub:
    """
    Sảnh 5 Mini Games chạy trực tiếp trên App Windows (Tkinter Canvas Native):
    1. Cờ Caro (caro) | 2. Sudoku (sudoku) | 3. Cờ Vua (chess) | 4. Rắn Săn Mồi (snake) | 5. 2048 (2048)
    Hoạt động độc lập trong tab '🎮 Giải Trí Chờ Kèo', giữ nguyên 100% luồng quét F2 Diplomacy & phím tắt F5/F6/F7/F8.
    """

    GAMES = [
        ("caro", "⭕ Cờ Caro"),
        ("sudoku", "▦ Sudoku"),
        ("chess", "♟️ Cờ Vua"),
        ("snake", "🐍 Rắn Săn Mồi"),
        ("2048", "🔢 2048"),
    ]

    def __init__(self, app, parent_frame):
        self.app = app
        self.tk = app.tk
        self.parent = parent_frame
        self.active_game = "caro"
        self.leaderboards = {k: [] for k, _ in self.GAMES}
        self._snake_job = None
        self._sudoku_job = None

        # Game states
        self._init_caro_state()
        self._init_sudoku_state()
        self._init_chess_state()
        self._init_snake_state()
        self._init_2048_state()

        self._build_layout()

    def _build_layout(self):
        tk = self.tk
        C_APP, C_PANEL, C_ELEV, C_BORDER = "#0b0e14", "#121721", "#1a2130", "#262f40"
        C_GOLD = "#f59e0b"

        outer = tk.Frame(self.parent, bg=C_APP, padx=12, pady=8)
        outer.pack(fill="both", expand=True)

        # Top Selector Bar
        top_bar = tk.Frame(outer, bg=C_PANEL, highlightthickness=1, highlightbackground=C_BORDER, padx=12, pady=8)
        top_bar.pack(fill="x", pady=(0, 8))

        title_col = tk.Frame(top_bar, bg=C_PANEL)
        title_col.pack(side="left")
        tk.Label(
            title_col,
            text="🎮 SẢNH GIẢI TRÍ CHỜ KÈO XO (5 MINI GAMES TRÊN WINDOWS APP)",
            font=("Segoe UI", 10, "bold"),
            fg="#fbbf24",
            bg=C_PANEL,
        ).pack(anchor="w")
        tk.Label(
            title_col,
            text="Phím tắt F2 (Quét Diplomacy) & F5/F6/F7/F8 (Cập nhật tỉ số AOE) vẫn hoạt động ngầm 100% khi bạn đang chơi!",
            font=("Segoe UI", 8, "bold"),
            fg="#94a3b8",
            bg=C_PANEL,
        ).pack(anchor="w")

        btn_back_aoe = tk.Button(
            top_bar,
            text="🏟️ Về Bảng Điều Khiển AOE",
            command=lambda: self.app.switch_main_tab("BATTLE"),
            font=("Segoe UI", 9, "bold"),
            bg="#0284c7",
            fg="#ffffff",
            relief="flat",
            padx=12,
            pady=4,
            cursor="hand2",
        )
        btn_back_aoe.pack(side="right", padx=(8, 0))

        tabs_row = tk.Frame(top_bar, bg=C_PANEL)
        tabs_row.pack(side="right")
        self.game_tab_btns = {}
        for g_key, g_label in self.GAMES:
            b = tk.Button(
                tabs_row,
                text=g_label,
                command=lambda k=g_key: self.select_game(k),
                font=("Segoe UI", 9, "bold"),
                bg=C_GOLD if g_key == self.active_game else C_ELEV,
                fg="#0b0e14" if g_key == self.active_game else "#e2e8f0",
                relief="flat",
                padx=10,
                pady=4,
                cursor="hand2",
            )
            b.pack(side="left", padx=3)
            self.game_tab_btns[g_key] = b

        # Main Split: Game Stage (Left 72%) | Leaderboard & Info (Right 28%)
        body = tk.Frame(outer, bg=C_APP)
        body.pack(fill="both", expand=True)
        body.columnconfigure(0, weight=72)
        body.columnconfigure(1, weight=28)
        body.rowconfigure(0, weight=1)

        self.stage_panel = tk.Frame(body, bg=C_PANEL, highlightthickness=1, highlightbackground=C_BORDER, padx=12, pady=10)
        self.stage_panel.grid(row=0, column=0, sticky="nsew", padx=(0, 6))

        self.side_panel = tk.Frame(body, bg=C_PANEL, highlightthickness=1, highlightbackground=C_BORDER, padx=12, pady=10)
        self.side_panel.grid(row=0, column=1, sticky="nsew", padx=(6, 0))

        lb_hdr = tk.Frame(self.side_panel, bg=C_PANEL)
        lb_hdr.pack(fill="x", pady=(0, 6))
        self.lb_title_lbl = tk.Label(
            lb_hdr,
            text="🏆 BẢNG XẾP HẠNG CỜ CARO",
            font=("Segoe UI", 10, "bold"),
            fg="#fbbf24",
            bg=C_PANEL,
        )
        self.lb_title_lbl.pack(side="left")
        tk.Button(
            lb_hdr,
            text="🔄 Làm mới",
            command=lambda: self.fetch_leaderboard(self.active_game),
            font=("Segoe UI", 8, "bold"),
            bg=C_ELEV,
            fg="#38bdf8",
            relief="flat",
            padx=8,
            pady=2,
            cursor="hand2",
        ).pack(side="right")

        self.lb_list_frame = tk.Frame(self.side_panel, bg=C_ELEV, highlightthickness=1, highlightbackground=C_BORDER, padx=8, pady=8)
        self.lb_list_frame.pack(fill="both", expand=True)

        tip_box = tk.Frame(self.side_panel, bg="#172033", highlightthickness=1, highlightbackground="#2e3f5c", padx=10, pady=8)
        tip_box.pack(fill="x", pady=(8, 0))
        tk.Label(
            tip_box,
            text="💡 HƯỚNG DẪN NHANH:\n• Điểm kỷ lục tự động đồng bộ lên BXH chung giữa App Windows và Website XO.\n• Sudoku: Bấm chọn ô rồi gõ phím số 1..9 trên bàn phím (hoặc nút trên màn hình).\n• Rắn săn mồi & 2048: Điều khiển bằng phím W/A/S/D hoặc các nút ▲ ▼ ◀ ▶.",
            font=("Segoe UI", 8, "bold"),
            fg="#cbd5e1",
            bg="#172033",
            justify="left",
            wraplength=280,
        ).pack(anchor="w")

        # Bind keyboard events for Sudoku / Snake / 2048 when in MINIGAMES tab
        self.app.root.bind("<KeyPress>", self._on_root_keypress, add="+")

    def on_tab_shown(self):
        self.select_game(self.active_game)

    def select_game(self, game_key: str):
        if self._snake_job:
            try:
                self.app.root.after_cancel(self._snake_job)
            except Exception:
                pass
            self._snake_job = None
        if getattr(self, "_caro_poll_job", None):
            try:
                self.app.root.after_cancel(self._caro_poll_job)
            except Exception:
                pass
            self._caro_poll_job = None
        self.active_game = game_key
        for k, b in self.game_tab_btns.items():
            if k == game_key:
                b.configure(bg="#f59e0b", fg="#0b0e14")
            else:
                b.configure(bg="#1a2130", fg="#e2e8f0")

        for child in self.stage_panel.winfo_children():
            child.destroy()

        if game_key == "caro":
            self._build_caro_stage()
        elif game_key == "sudoku":
            self._build_sudoku_stage()
        elif game_key == "chess":
            self._build_chess_stage()
        elif game_key == "snake":
            self._build_snake_stage()
        elif game_key == "2048":
            self._build_2048_stage()

        self.render_leaderboard()
        self.fetch_leaderboard(game_key)

    def fetch_leaderboard(self, game_key: str):
        def _t():
            try:
                res = requests.post(
                    self.app.get_api_endpoint(),
                    json={"action": "getMinigameLeaderboard", "game": game_key},
                    timeout=8,
                )
                d = res.json()
                if d.get("status") == "success":
                    if isinstance(d.get("leaderboard"), list):
                        self.leaderboards[game_key] = d["leaderboard"]
                    elif isinstance(d.get("leaderboards"), dict):
                        self.leaderboards.update(d["leaderboards"])
                    self.app.root.after(0, self.render_leaderboard)
            except Exception:
                pass

        threading.Thread(target=_t, daemon=True).start()

    def submit_score(self, game_key: str, score: int, extra: str = ""):
        pname = self.app.player_name_var.get().strip() or "Khách"
        tier = getattr(self.app, "current_player_tier", "BRONZE") or "BRONZE"

        def _t():
            try:
                res = requests.post(
                    self.app.get_api_endpoint(),
                    json={
                        "action": "saveMinigameScore",
                        "game": game_key,
                        "playerName": pname,
                        "tier": tier,
                        "score": int(score),
                        "extra": extra,
                    },
                    timeout=8,
                )
                d = res.json()
                if d.get("status") == "success" and isinstance(d.get("leaderboard"), list):
                    self.leaderboards[game_key] = d["leaderboard"]
                    self.app.root.after(0, self.render_leaderboard)
            except Exception:
                pass

        threading.Thread(target=_t, daemon=True).start()

    def render_leaderboard(self):
        tk = self.tk
        g_dict = dict(self.GAMES)
        self.lb_title_lbl.configure(text=f"🏆 BXH {g_dict.get(self.active_game, '').upper()}")
        for child in self.lb_list_frame.winfo_children():
            child.destroy()
        rows = self.leaderboards.get(self.active_game) or []
        if not rows:
            tk.Label(
                self.lb_list_frame,
                text="Chưa có kỷ lục nào trên BXH.\nHãy chiến thắng để ghi danh đầu tiên!",
                font=("Segoe UI", 9, "bold"),
                fg="#94a3b8",
                bg="#1a2130",
                justify="center",
            ).pack(pady=24)
            return
        for idx, r in enumerate(rows[:10]):
            row_f = tk.Frame(self.lb_list_frame, bg="#121721", highlightthickness=1, highlightbackground="#262f40", padx=8, pady=5)
            row_f.pack(fill="x", pady=2)
            medal = "🥇" if idx == 0 else ("🥈" if idx == 1 else ("🥉" if idx == 2 else f"#{idx + 1}"))
            tk.Label(row_f, text=medal, font=("Segoe UI", 9, "bold"), fg="#fbbf24", bg="#121721", width=3, anchor="w").pack(side="left")
            tk.Label(row_f, text=str(r.get("playerName", "Player")), font=("Segoe UI", 9, "bold"), fg="#ffffff", bg="#121721").pack(side="left", padx=(2, 6))
            extra_txt = f" ({r.get('extra')})" if r.get("extra") else ""
            tk.Label(
                row_f,
                text=f"{r.get('score', 0)} đ{extra_txt}",
                font=("Consolas", 9, "bold"),
                fg="#34d399",
                bg="#121721",
            ).pack(side="right")

    def _on_root_keypress(self, ev):
        if getattr(self.app, "active_tab", "") != "MINIGAMES" or not getattr(self.app, "is_logged_in", False):
            return
        w_cls = ev.widget.winfo_class() if ev.widget else ""
        if w_cls in ("Entry", "Text", "TCombobox"):
            return
        ks = (ev.keysym or "").lower()
        if self.active_game == "sudoku":
            if ks in ("1", "2", "3", "4", "5", "6", "7", "8", "9"):
                self._sudoku_input(int(ks))
            elif ks in ("0", "backspace", "delete"):
                self._sudoku_input(0)
            elif ks == "n":
                self.sudoku_notes_mode = not self.sudoku_notes_mode
                self._draw_sudoku()
        elif self.active_game == "snake":
            if ks in ("w", "up"):
                self._snake_set_dir(0, -1)
            elif ks in ("s", "down"):
                self._snake_set_dir(0, 1)
            elif ks in ("a", "left"):
                self._snake_set_dir(-1, 0)
            elif ks in ("d", "right"):
                self._snake_set_dir(1, 0)
        elif self.active_game == "2048":
            if ks in ("w", "up"):
                self._2048_move("UP")
            elif ks in ("s", "down"):
                self._2048_move("DOWN")
            elif ks in ("a", "left"):
                self._2048_move("LEFT")
            elif ks in ("d", "right"):
                self._2048_move("RIGHT")

    # ==========================================================================
    # 1. CỜ CARO (20x20, Sảnh Online 2 Tài Khoản / AI 5 Levels / 2P / Obstacles)
    # ==========================================================================
    def _init_caro_state(self):
        self.caro_N = 20
        self.caro_mode = "online"
        self.caro_level = 3
        self.caro_obstacles = False
        self.caro_online_rooms = []
        self.caro_online_room = None
        self.caro_online_seat = None
        self._caro_poll_job = None
        self._reset_caro_board()

    def _reset_caro_board(self):
        self.caro_board = [["" for _ in range(self.caro_N)] for _ in range(self.caro_N)]
        self.caro_moves = []
        self.caro_winner = None
        self.caro_win_line = None
        if self.caro_obstacles:
            placed = 0
            while placed < 12:
                rx, ry = random.randint(2, self.caro_N - 3), random.randint(2, self.caro_N - 3)
                if (rx, ry) != (10, 10) and not self.caro_board[ry][rx]:
                    self.caro_board[ry][rx] = "#"
                    placed += 1

    def _build_caro_stage(self):
        tk = self.tk
        ctrl = tk.Frame(self.stage_panel, bg="#121721")
        ctrl.pack(fill="x", pady=(0, 6))

        tk.Label(ctrl, text="Chế độ:", font=("Segoe UI", 9, "bold"), fg="#cbd5e1", bg="#121721").pack(side="left")
        for m_key, m_txt in (("online", "🌐 Sảnh Online (2 TK)"), ("ai", "🤖 Đấu Máy AI"), ("2p", "👥 2 Người Cùng Máy")):
            tk.Button(
                ctrl,
                text=m_txt,
                command=lambda mk=m_key: self._set_caro_mode(mk),
                font=("Segoe UI", 8, "bold"),
                bg="#f59e0b" if self.caro_mode == m_key else "#1a2130",
                fg="#0b0e14" if self.caro_mode == m_key else "#cbd5e1",
                relief="flat",
                padx=8,
                pady=3,
                cursor="hand2",
            ).pack(side="left", padx=2)

        obs_btn = tk.Button(
            ctrl,
            text=f"🪨 Đá cản: {'BẬT' if self.caro_obstacles else 'TẮT'}",
            command=self._toggle_caro_obs,
            font=("Segoe UI", 8, "bold"),
            bg="#1a2130",
            fg="#38bdf8",
            relief="flat",
            padx=8,
            pady=3,
            cursor="hand2",
        )
        obs_btn.pack(side="left", padx=6)

        if self.caro_mode == "online":
            if not self.caro_online_room:
                self._build_caro_online_lobby()
                return
            else:
                # Online Room Controls
                tk.Button(
                    ctrl,
                    text="🚪 Rời Bàn",
                    command=self._caro_online_leave,
                    font=("Segoe UI", 8, "bold"),
                    bg="#7f1d1d",
                    fg="#fecaca",
                    relief="flat",
                    padx=8,
                    pady=3,
                    cursor="hand2",
                ).pack(side="right", padx=2)
                tk.Button(
                    ctrl,
                    text="🏳️ Xin Thua",
                    command=self._caro_online_resign,
                    font=("Segoe UI", 8, "bold"),
                    bg="#1a2130",
                    fg="#f87171",
                    relief="flat",
                    padx=8,
                    pady=3,
                    cursor="hand2",
                ).pack(side="right", padx=2)
                tk.Button(
                    ctrl,
                    text="🔄 Ván Mới / Đổi Bên",
                    command=self._caro_online_rematch,
                    font=("Segoe UI", 8, "bold"),
                    bg="#f59e0b",
                    fg="#0b0e14",
                    relief="flat",
                    padx=8,
                    pady=3,
                    cursor="hand2",
                ).pack(side="right", padx=2)
        else:
            if self.caro_mode == "ai":
                tk.Label(ctrl, text="Cấp:", font=("Segoe UI", 8, "bold"), fg="#cbd5e1", bg="#121721").pack(side="left", padx=(4, 2))
                for lv in range(1, 6):
                    tk.Button(
                        ctrl,
                        text=f"C{lv}",
                        command=lambda l=lv: self._set_caro_level(l),
                        font=("Segoe UI", 8, "bold"),
                        bg="#f59e0b" if self.caro_level == lv else "#1a2130",
                        fg="#0b0e14" if self.caro_level == lv else "#cbd5e1",
                        relief="flat",
                        padx=5,
                        pady=2,
                        cursor="hand2",
                    ).pack(side="left", padx=1)

            tk.Button(
                ctrl,
                text="🔄 Ván Mới",
                command=lambda: (self._reset_caro_board(), self._draw_caro()),
                font=("Segoe UI", 9, "bold"),
                bg="#f59e0b",
                fg="#0b0e14",
                relief="flat",
                padx=10,
                pady=3,
                cursor="hand2",
            ).pack(side="right")
            tk.Button(
                ctrl,
                text="↩️ Đi Lại",
                command=self._caro_undo,
                font=("Segoe UI", 9, "bold"),
                bg="#1a2130",
                fg="#e2e8f0",
                relief="flat",
                padx=8,
                pady=3,
                cursor="hand2",
            ).pack(side="right", padx=4)

        self.caro_status_lbl = tk.Label(
            self.stage_panel,
            text="Lượt đi: X (Bạn)",
            font=("Segoe UI", 10, "bold"),
            fg="#fbbf24",
            bg="#1a2130",
            pady=4,
        )
        self.caro_status_lbl.pack(fill="x", pady=(0, 6))

        self.caro_canvas = tk.Canvas(self.stage_panel, width=440, height=440, bg="#0b0e14", highlightthickness=1, highlightbackground="#f59e0b")
        self.caro_canvas.pack(anchor="center")
        self.caro_canvas.bind("<Button-1>", self._on_caro_click)
        self._draw_caro()
        if self.caro_mode == "online" and self.caro_online_room:
            self._schedule_caro_poll()

    def _build_caro_online_lobby(self):
        tk = self.tk
        pname = self.app.player_name_var.get().strip() or "Khách"
        tier = getattr(self.app, "current_player_tier", "BRONZE") or "BRONZE"

        hdr = tk.Frame(self.stage_panel, bg="#172033", highlightthickness=1, highlightbackground="#f59e0b", padx=12, pady=10)
        hdr.pack(fill="x", pady=(0, 8))

        tk.Label(
            hdr,
            text=f"🌐 SẢNH ĐẤU CARO ONLINE 1v1 — TÀI KHOẢN: {pname.upper()} ({tier})",
            font=("Segoe UI", 10, "bold"),
            fg="#fbbf24",
            bg="#172033",
        ).pack(anchor="w")
        tk.Label(
            hdr,
            text="Tạo bàn mới hoặc nhập Mã Bàn (#XXXX) để thách đấu trực tiếp với tài khoản XO khác trên cả Website & App Windows!",
            font=("Segoe UI", 8, "bold"),
            fg="#94a3b8",
            bg="#172033",
        ).pack(anchor="w", pady=(2, 6))

        act_bar = tk.Frame(hdr, bg="#172033")
        act_bar.pack(fill="x")

        tk.Button(
            act_bar,
            text="➕ Tạo Bàn Mới",
            command=self._caro_online_create,
            font=("Segoe UI", 9, "bold"),
            bg="#f59e0b",
            fg="#0b0e14",
            relief="flat",
            padx=12,
            pady=4,
            cursor="hand2",
        ).pack(side="left", padx=(0, 10))

        tk.Label(act_bar, text="Mã bàn:", font=("Segoe UI", 9, "bold"), fg="#cbd5e1", bg="#172033").pack(side="left")
        self.caro_code_var = tk.StringVar()
        code_ent = tk.Entry(
            act_bar,
            textvariable=self.caro_code_var,
            font=("Consolas", 10, "bold"),
            width=8,
            bg="#0b0e14",
            fg="#fbbf24",
            insertbackground="#fbbf24",
            relief="flat",
            highlightthickness=1,
            highlightbackground="#334155",
        )
        code_ent.pack(side="left", padx=6, ipady=3)

        tk.Button(
            act_bar,
            text="⚔️ Vào Bàn",
            command=lambda: self._caro_online_join(self.caro_code_var.get().strip().upper()),
            font=("Segoe UI", 9, "bold"),
            bg="#1a2130",
            fg="#38bdf8",
            relief="flat",
            padx=10,
            pady=4,
            cursor="hand2",
        ).pack(side="left")

        tk.Button(
            act_bar,
            text="🔄 Làm mới Sảnh",
            command=self._caro_fetch_lobby,
            font=("Segoe UI", 8, "bold"),
            bg="#1a2130",
            fg="#e2e8f0",
            relief="flat",
            padx=10,
            pady=4,
            cursor="hand2",
        ).pack(side="right")

        self.caro_lobby_list_frame = tk.Frame(self.stage_panel, bg="#121721")
        self.caro_lobby_list_frame.pack(fill="both", expand=True)
        self._render_caro_lobby_list()
        self._caro_fetch_lobby()
        self._schedule_caro_poll()

    def _render_caro_lobby_list(self):
        if not hasattr(self, "caro_lobby_list_frame") or not self.caro_lobby_list_frame.winfo_exists():
            return
        tk = self.tk
        for child in self.caro_lobby_list_frame.winfo_children():
            child.destroy()

        rooms = self.caro_online_rooms or []
        if not rooms:
            empty_f = tk.Frame(self.caro_lobby_list_frame, bg="#1a2130", highlightthickness=1, highlightbackground="#262f40", pady=36)
            empty_f.pack(fill="x", pady=10)
            tk.Label(
                empty_f,
                text="Hiện chưa có bàn cờ Caro Online nào đang mở.\nBấm [➕ Tạo Bàn Mới] ở trên để mở phòng và gửi mã bàn 4 ký tự cho bạn bè vào chiến ngay!",
                font=("Segoe UI", 9, "bold"),
                fg="#94a3b8",
                bg="#1a2130",
                justify="center",
            ).pack()
            return

        for r in rooms[:8]:
            card = tk.Frame(self.caro_lobby_list_frame, bg="#1a2130", highlightthickness=1, highlightbackground="#2e3f5c", padx=12, pady=8)
            card.pack(fill="x", pady=4)
            rid = r.get("code") or r.get("roomId") or ""
            players_obj = r.get("players") or {}
            px = r.get("playerX") or players_obj.get("X") or {}
            po = r.get("playerO") or players_obj.get("O") or {}
            st = r.get("status", "WAITING")
            sc = r.get("scores") or {"X": 0, "O": 0}
            obs_txt = " • 🪨 Đá cản" if r.get("obstacles") else ""
            st_txt = "🟢 Đang chờ đối thủ (1/2)" if not po else ("⚔️ Đang giao đấu (2/2)" if st == "PLAYING" else "🏁 Vừa kết thúc")
            st_col = "#34d399" if not po else "#fbbf24"

            left_f = tk.Frame(card, bg="#1a2130")
            left_f.pack(side="left", fill="x", expand=True)
            tk.Label(
                left_f,
                text=f"BÀN #{rid}{obs_txt}   |   {st_txt}   |   Tỉ số: {sc.get('X', 0)} - {sc.get('O', 0)}",
                font=("Consolas", 9, "bold"),
                fg=st_col,
                bg="#1a2130",
            ).pack(anchor="w")
            tk.Label(
                left_f,
                text=f"❌ Quân X: {px.get('name', '---')} ({px.get('tier', 'BRONZE')})     vs     ⭕ Quân O: {po.get('name', 'Đang chờ người vào...') if po else 'Đang chờ người vào...'}",
                font=("Segoe UI", 9, "bold"),
                fg="#ffffff",
                bg="#1a2130",
            ).pack(anchor="w", pady=(2, 0))

            btn_txt = "⚔️ Vào Đấu Ngay" if not po else "👁️ Vào Bàn"
            btn_bg = "#f59e0b" if not po else "#121721"
            btn_fg = "#0b0e14" if not po else "#38bdf8"
            tk.Button(
                card,
                text=btn_txt,
                command=lambda code=rid: self._caro_online_join(code),
                font=("Segoe UI", 9, "bold"),
                bg=btn_bg,
                fg=btn_fg,
                relief="flat",
                padx=12,
                pady=5,
                cursor="hand2",
            ).pack(side="right")

    def _schedule_caro_poll(self):
        if getattr(self, "_caro_poll_job", None):
            try:
                self.app.root.after_cancel(self._caro_poll_job)
            except Exception:
                pass
            self._caro_poll_job = None
        if self.active_game != "caro" or self.caro_mode != "online":
            return

        def _tick():
            if self.active_game != "caro" or self.caro_mode != "online":
                return
            if self.caro_online_room:
                self._caro_poll_room_once()
            else:
                self._caro_fetch_lobby()
            self._caro_poll_job = self.app.root.after(1500, _tick)

        self._caro_poll_job = self.app.root.after(1500, _tick)

    def _caro_fetch_lobby(self):
        def _t():
            try:
                res = requests.post(self.app.get_api_endpoint(), json={"action": "caroListRooms"}, timeout=6)
                d = res.json()
                if d.get("status") == "success" and isinstance(d.get("rooms"), list):
                    self.caro_online_rooms = d["rooms"]
                    self.app.root.after(0, self._render_caro_lobby_list)
            except Exception:
                pass

        threading.Thread(target=_t, daemon=True).start()

    def _caro_apply_online_room(self, room: dict, rebuild_if_needed: bool = False):
        was_none = self.caro_online_room is None
        self.caro_online_room = room
        pname = (self.app.player_name_var.get().strip() or "Khách").lower()
        players_obj = room.get("players") or {}
        px_obj = room.get("playerX") or players_obj.get("X") or {}
        po_obj = room.get("playerO") or players_obj.get("O") or {}
        px_name = (px_obj.get("name") or "").lower()
        po_name = (po_obj.get("name") or "").lower()
        if px_name and px_name == pname:
            self.caro_online_seat = "X"
        elif po_name and po_name == pname:
            self.caro_online_seat = "O"
        else:
            self.caro_online_seat = "V"

        raw_moves = room.get("moves") or []
        self.caro_moves = [(int(m.get("x", 0)), int(m.get("y", 0)), str(m.get("role", "X"))) for m in raw_moves]

        if isinstance(room.get("board"), list) and len(room["board"]) == self.caro_N:
            self.caro_board = [[str(c or "") for c in row] for row in room["board"]]
        else:
            self.caro_board = [["" for _ in range(self.caro_N)] for _ in range(self.caro_N)]
            for rk in room.get("rocks") or []:
                if isinstance(rk, (list, tuple)) and len(rk) >= 2:
                    rx, ry = int(rk[0]), int(rk[1])
                    if 0 <= rx < self.caro_N and 0 <= ry < self.caro_N:
                        self.caro_board[ry][rx] = "#"
            for mx, my, mrole in self.caro_moves:
                if 0 <= mx < self.caro_N and 0 <= my < self.caro_N:
                    self.caro_board[my][mx] = mrole

        self.caro_winner = room.get("winner")
        wl = room.get("winLine")
        if isinstance(wl, dict):
            self.caro_win_line = (int(wl.get("ax", 0)), int(wl.get("ay", 0)), int(wl.get("ex", 0)), int(wl.get("ey", 0)))
        elif isinstance(wl, (list, tuple)) and len(wl) == 2 and isinstance(wl[0], (list, tuple)) and isinstance(wl[1], (list, tuple)):
            self.caro_win_line = (int(wl[0][0]), int(wl[0][1]), int(wl[1][0]), int(wl[1][1]))
        else:
            self.caro_win_line = None

        if was_none or rebuild_if_needed:
            self.select_game("caro")
        else:
            self._draw_caro()

    def _caro_online_create(self):
        pname = self.app.player_name_var.get().strip() or "Khách"
        tier = getattr(self.app, "current_player_tier", "BRONZE") or "BRONZE"

        def _t():
            try:
                res = requests.post(
                    self.app.get_api_endpoint(),
                    json={
                        "action": "caroCreateRoom",
                        "playerName": pname,
                        "tier": tier,
                        "obstacles": bool(self.caro_obstacles),
                    },
                    timeout=8,
                )
                d = res.json()
                if d.get("status") == "success" and d.get("room"):
                    self.app.root.after(0, lambda: self._caro_apply_online_room(d["room"], True))
                elif d.get("message"):
                    self.app.root.after(0, lambda msg=d.get("message"): self.app.log(f"⚠️ [Caro Online] {msg}"))
            except Exception as e:
                self.app.root.after(0, lambda err=str(e): self.app.log(f"⚠️ [Caro Online] Lỗi tạo bàn: {err}"))

        threading.Thread(target=_t, daemon=True).start()

    def _caro_online_join(self, code: str):
        code = (code or "").replace("#", "").strip().upper()
        if not code:
            return
        pname = self.app.player_name_var.get().strip() or "Khách"
        tier = getattr(self.app, "current_player_tier", "BRONZE") or "BRONZE"

        def _t():
            try:
                res = requests.post(
                    self.app.get_api_endpoint(),
                    json={"action": "caroJoinRoom", "code": code, "roomId": code, "playerName": pname, "tier": tier},
                    timeout=8,
                )
                d = res.json()
                if d.get("status") == "success" and d.get("room"):
                    self.app.root.after(0, lambda: self._caro_apply_online_room(d["room"], True))
                elif d.get("message"):
                    self.app.root.after(0, lambda msg=d.get("message"): self.app.log(f"⚠️ [Caro Online] {msg}"))
            except Exception as e:
                self.app.root.after(0, lambda err=str(e): self.app.log(f"⚠️ [Caro Online] Lỗi vào bàn #{code}: {err}"))

        threading.Thread(target=_t, daemon=True).start()

    def _caro_poll_room_once(self):
        if not self.caro_online_room:
            return
        rid = self.caro_online_room.get("code") or self.caro_online_room.get("roomId") or ""
        pname = self.app.player_name_var.get().strip() or "Khách"

        def _t():
            try:
                res = requests.post(
                    self.app.get_api_endpoint(),
                    json={"action": "caroGetRoom", "code": rid, "roomId": rid, "playerName": pname},
                    timeout=6,
                )
                d = res.json()
                if d.get("status") == "success" and d.get("room"):
                    self.app.root.after(0, lambda: self._caro_apply_online_room(d["room"], False))
                elif res.status_code == 404 or d.get("status") == "error":
                    def _closed():
                        self.caro_online_room = None
                        self.caro_online_seat = None
                        self.select_game("caro")
                    self.app.root.after(0, _closed)
            except Exception:
                pass

        threading.Thread(target=_t, daemon=True).start()

    def _caro_online_rematch(self):
        if not self.caro_online_room:
            return
        rid = self.caro_online_room.get("code") or self.caro_online_room.get("roomId") or ""
        pname = self.app.player_name_var.get().strip() or "Khách"

        def _t():
            try:
                res = requests.post(
                    self.app.get_api_endpoint(),
                    json={"action": "caroResetGame", "code": rid, "roomId": rid, "playerName": pname},
                    timeout=8,
                )
                d = res.json()
                if d.get("status") == "success" and d.get("room"):
                    self.app.root.after(0, lambda: self._caro_apply_online_room(d["room"], False))
            except Exception:
                pass

        threading.Thread(target=_t, daemon=True).start()

    def _caro_online_resign(self):
        if not self.caro_online_room:
            return
        rid = self.caro_online_room.get("code") or self.caro_online_room.get("roomId") or ""
        pname = self.app.player_name_var.get().strip() or "Khách"

        def _t():
            try:
                res = requests.post(
                    self.app.get_api_endpoint(),
                    json={"action": "caroResign", "code": rid, "roomId": rid, "playerName": pname},
                    timeout=8,
                )
                d = res.json()
                if d.get("status") == "success" and d.get("room"):
                    self.app.root.after(0, lambda: self._caro_apply_online_room(d["room"], False))
            except Exception:
                pass

        threading.Thread(target=_t, daemon=True).start()

    def _caro_online_leave(self):
        if not self.caro_online_room:
            return
        rid = self.caro_online_room.get("code") or self.caro_online_room.get("roomId") or ""
        pname = self.app.player_name_var.get().strip() or "Khách"
        self.caro_online_room = None
        self.caro_online_seat = None
        self._reset_caro_board()
        self.select_game("caro")

        def _t():
            try:
                requests.post(
                    self.app.get_api_endpoint(),
                    json={"action": "caroLeaveRoom", "code": rid, "roomId": rid, "playerName": pname},
                    timeout=6,
                )
            except Exception:
                pass

        threading.Thread(target=_t, daemon=True).start()

    def _set_caro_mode(self, mode_key: str):
        if self.caro_mode == "online" and mode_key != "online" and self.caro_online_room:
            self._caro_online_leave()
        self.caro_mode = mode_key
        if mode_key != "online":
            self._reset_caro_board()
        self.select_game("caro")

    def _set_caro_level(self, lv: int):
        self.caro_level = lv
        self._reset_caro_board()
        self.select_game("caro")

    def _toggle_caro_obs(self):
        self.caro_obstacles = not self.caro_obstacles
        if self.caro_mode != "online":
            self._reset_caro_board()
        self.select_game("caro")

    def _caro_undo(self):
        if self.caro_mode == "online" or self.caro_winner or not self.caro_moves:
            return
        steps = 2 if (self.caro_mode == "ai" and len(self.caro_moves) >= 2) else 1
        for _ in range(steps):
            mx, my, _ = self.caro_moves.pop()
            self.caro_board[my][mx] = ""
        self._draw_caro()

    def _caro_check_win(self, x: int, y: int, role: str):
        opp = "O" if role == "X" else "X"
        N = self.caro_N
        for dx, dy in ((1, 0), (0, 1), (1, 1), (1, -1)):
            cnt = 1
            ax, ay, ex, ey = x, y, x, y
            i, j = x + dx, y + dy
            while 0 <= i < N and 0 <= j < N and self.caro_board[j][i] == role:
                cnt += 1
                ex, ey = i, j
                i += dx
                j += dy
            b1 = not (0 <= i < N and 0 <= j < N) or self.caro_board[j][i] in (opp, "#")
            i, j = x - dx, y - dy
            while 0 <= i < N and 0 <= j < N and self.caro_board[j][i] == role:
                cnt += 1
                ax, ay = i, j
                i -= dx
                j -= dy
            b2 = not (0 <= i < N and 0 <= j < N) or self.caro_board[j][i] in (opp, "#")
            if cnt >= 6 or (cnt == 5 and not (b1 and b2)):
                return (ax, ay, ex, ey)
        return None

    def _caro_score_dir(self, x: int, y: int, dx: int, dy: int, role: str):
        N = self.caro_N
        cnt = 1
        open_ends = 0
        i, j = x + dx, y + dy
        while 0 <= i < N and 0 <= j < N and self.caro_board[j][i] == role:
            cnt += 1
            i += dx
            j += dy
        if 0 <= i < N and 0 <= j < N and self.caro_board[j][i] == "":
            open_ends += 1
        i, j = x - dx, y - dy
        while 0 <= i < N and 0 <= j < N and self.caro_board[j][i] == role:
            cnt += 1
            i -= dx
            j -= dy
        if 0 <= i < N and 0 <= j < N and self.caro_board[j][i] == "":
            open_ends += 1
        if cnt >= 5 and open_ends >= 1:
            return 100000
        if cnt == 4 and open_ends == 2:
            return 16000
        if cnt == 4 and open_ends == 1:
            return 3600
        if cnt == 3 and open_ends == 2:
            return 1800
        if cnt == 2 and open_ends == 2:
            return 200
        return cnt * 15 * open_ends

    def _on_caro_click(self, ev):
        if self.caro_winner:
            return
        cell = 440 / self.caro_N
        x, y = int(ev.x // cell), int(ev.y // cell)
        if not (0 <= x < self.caro_N and 0 <= y < self.caro_N) or self.caro_board[y][x] != "":
            return

        if self.caro_mode == "online":
            rm = self.caro_online_room
            if not rm:
                return
            players_obj = rm.get("players") or {}
            px_obj = rm.get("playerX") or players_obj.get("X")
            po_obj = rm.get("playerO") or players_obj.get("O")
            status = rm.get("status") or ("WAITING" if (not px_obj or not po_obj) else ("FINISHED" if rm.get("winner") else "PLAYING"))
            if status != "PLAYING":
                return
            turn = rm.get("turn") or ("X" if len(self.caro_moves) % 2 == 0 else "O")
            if self.caro_online_seat not in ("X", "O") or turn != self.caro_online_seat:
                return
            rid = rm.get("code") or rm.get("roomId") or ""
            pname = self.app.player_name_var.get().strip() or "Khách"
            # Optimistic draw
            self.caro_board[y][x] = self.caro_online_seat
            self.caro_moves.append((x, y, self.caro_online_seat))
            self._draw_caro()

            def _t():
                try:
                    res = requests.post(
                        self.app.get_api_endpoint(),
                        json={"action": "caroMove", "code": rid, "roomId": rid, "playerName": pname, "x": x, "y": y},
                        timeout=8,
                    )
                    d = res.json()
                    if d.get("status") == "success" and d.get("room"):
                        self.app.root.after(0, lambda: self._caro_apply_online_room(d["room"], False))
                        if d["room"].get("winner"):
                            self.fetch_leaderboard("caro")
                except Exception:
                    pass

            threading.Thread(target=_t, daemon=True).start()
            return

        role = "X" if len(self.caro_moves) % 2 == 0 else "O"
        self.caro_board[y][x] = role
        self.caro_moves.append((x, y, role))
        wl = self._caro_check_win(x, y, role)
        if wl:
            self.caro_winner = role
            self.caro_win_line = wl
            if self.caro_mode == "ai" and role == "X":
                pts = self.caro_level * 150 + max(20, 200 - len(self.caro_moves) * 2)
                self.submit_score("caro", pts, f"Thắng AI Cấp {self.caro_level}")
            self._draw_caro()
            return
        if self.caro_mode == "ai" and not self.caro_winner:
            self._caro_ai_move()
        self._draw_caro()

    def _caro_ai_move(self):
        N = self.caro_N
        best_s = -1
        cands = []
        def_w = [0.75, 0.9, 1.05, 1.2, 1.35][self.caro_level - 1]
        for y in range(N):
            for x in range(N):
                if self.caro_board[y][x] != "":
                    continue
                near = False
                for dy in range(-2, 3):
                    for dx in range(-2, 3):
                        nx, ny = x + dx, y + dy
                        if 0 <= nx < N and 0 <= ny < N and self.caro_board[ny][nx] in ("X", "O"):
                            near = True
                            break
                    if near:
                        break
                if not near and self.caro_moves:
                    continue
                atk, df = 0, 0
                self.caro_board[y][x] = "O"
                if self._caro_check_win(x, y, "O"):
                    atk += 500000
                for dx, dy in ((1, 0), (0, 1), (1, 1), (1, -1)):
                    atk += self._caro_score_dir(x, y, dx, dy, "O")
                self.caro_board[y][x] = "X"
                if self._caro_check_win(x, y, "X"):
                    df += 400000
                for dx, dy in ((1, 0), (0, 1), (1, 1), (1, -1)):
                    df += self._caro_score_dir(x, y, dx, dy, "X")
                self.caro_board[y][x] = ""
                center_b = 14 - (abs(x - 10) + abs(y - 10)) * 0.5
                noise = random.uniform(0, 90 if self.caro_level <= 2 else 15)
                tot = atk + df * def_w + center_b + noise
                if tot > best_s:
                    best_s = tot
                    cands = [(x, y)]
                elif abs(tot - best_s) < 5:
                    cands.append((x, y))
        px, py = random.choice(cands) if cands else (10, 10)
        self.caro_board[py][px] = "O"
        self.caro_moves.append((px, py, "O"))
        wl = self._caro_check_win(px, py, "O")
        if wl:
            self.caro_winner = "O"
            self.caro_win_line = wl

    def _draw_caro(self):
        if not hasattr(self, "caro_canvas") or not self.caro_canvas.winfo_exists():
            return
        c = self.caro_canvas
        c.delete("all")
        W = 440
        cell = W / self.caro_N
        for i in range(self.caro_N + 1):
            p = i * cell
            c.create_line(p, 0, p, W, fill="#1e293b")
            c.create_line(0, p, W, p, fill="#1e293b")
        if self.caro_moves:
            lx, ly, _ = self.caro_moves[-1]
            c.create_rectangle(lx * cell + 1, ly * cell + 1, (lx + 1) * cell - 1, (ly + 1) * cell - 1, fill="#3b2a10", outline="")
        for y in range(self.caro_N):
            for x in range(self.caro_N):
                v = self.caro_board[y][x]
                cx, cy = (x + 0.5) * cell, (y + 0.5) * cell
                r = cell * 0.32
                if v == "#":
                    c.create_rectangle(x * cell + 3, y * cell + 3, (x + 1) * cell - 3, (y + 1) * cell - 3, fill="#334155", outline="#64748b")
                elif v == "X":
                    c.create_line(cx - r, cy - r, cx + r, cy + r, fill="#f59e0b", width=2.5)
                    c.create_line(cx + r, cy - r, cx - r, cy + r, fill="#f59e0b", width=2.5)
                elif v == "O":
                    c.create_oval(cx - r, cy - r, cx + r, cy + r, outline="#38bdf8", width=2.5)
        if self.caro_win_line:
            ax, ay, ex, ey = self.caro_win_line
            c.create_line((ax + 0.5) * cell, (ay + 0.5) * cell, (ex + 0.5) * cell, (ey + 0.5) * cell, fill="#10b981", width=4)

        if self.caro_mode == "online" and self.caro_online_room:
            rm = self.caro_online_room
            rid = rm.get("code") or rm.get("roomId") or ""
            players_obj = rm.get("players") or {}
            px_obj = rm.get("playerX") or players_obj.get("X") or {}
            po_obj = rm.get("playerO") or players_obj.get("O") or {}
            px = px_obj.get("name", "---") if px_obj else "---"
            po = po_obj.get("name", "Đang chờ...") if po_obj else "Đang chờ..."
            sc = rm.get("scores") or {"X": 0, "O": 0}
            status = rm.get("status") or ("WAITING" if (not px_obj or not po_obj) else ("FINISHED" if rm.get("winner") else "PLAYING"))
            if status == "WAITING":
                self.caro_status_lbl.configure(
                    text=f"Bàn #{rid}  •  ❌ {px} vs ⭕ Đang chờ đối thủ vào bàn...",
                    fg="#fbbf24",
                )
            elif self.caro_winner:
                w_name = px if self.caro_winner == "X" else (po if self.caro_winner == "O" else "HÒA")
                self.caro_status_lbl.configure(
                    text=f"🏆 Bàn #{rid}: {w_name} ({self.caro_winner}) CHIẾN THẮNG!  •  Tỉ số: {sc.get('X', 0)} - {sc.get('O', 0)}",
                    fg="#34d399",
                )
            else:
                turn = rm.get("turn") or ("X" if len(self.caro_moves) % 2 == 0 else "O")
                my_turn = turn == self.caro_online_seat
                turn_txt = f"⚡ ĐẾN LƯỢT BẠN ({self.caro_online_seat})" if my_turn else f"⏳ Đợi lượt {turn}"
                self.caro_status_lbl.configure(
                    text=f"Bàn #{rid}  |  ❌ {px} ({sc.get('X', 0)}) - ({sc.get('O', 0)}) ⭕ {po}  |  {turn_txt}",
                    fg="#34d399" if my_turn else "#fbbf24",
                )
            return

        if self.caro_winner:
            msg = f"🏆 CHIẾN THẮNG: {'BẠN (X)' if (self.caro_mode == 'ai' and self.caro_winner == 'X') else ('MÁY AI (O)' if self.caro_mode == 'ai' else self.caro_winner)}!"
            self.caro_status_lbl.configure(text=msg, fg="#34d399")
        else:
            turn = "X" if len(self.caro_moves) % 2 == 0 else "O"
            self.caro_status_lbl.configure(text=f"Lượt đi: {turn}  •  Nước #{len(self.caro_moves) + 1}", fg="#fbbf24")

    # ==========================================================================
    # 2. SUDOKU (9x9, 4 Difficulties, Pencil Notes, Hint, Timer)
    # ==========================================================================
    def _init_sudoku_state(self):
        self.sudoku_diff = "easy"
        self.sudoku_notes_mode = False
        self._new_sudoku_game("easy")

    def _new_sudoku_game(self, diff=None):
        if diff:
            self.sudoku_diff = diff
        base = [1, 2, 3, 4, 5, 6, 7, 8, 9]
        nums = base[:]
        random.shuffle(nums)
        rb = [b * 3 + r for b in random.sample([0, 1, 2], 3) for r in random.sample([0, 1, 2], 3)]
        cb = [b * 3 + c for b in random.sample([0, 1, 2], 3) for c in random.sample([0, 1, 2], 3)]
        sol = []
        for r in range(9):
            for c in range(9):
                rr, cc = rb[r], cb[c]
                sol.append(nums[(rr * 3 + rr // 3 + cc) % 9])
        holes = {"easy": 34, "medium": 43, "hard": 50, "evil": 56}.get(self.sudoku_diff, 36)
        brd = sol[:]
        for idx in random.sample(range(81), holes):
            brd[idx] = 0
        self.sudoku_sol = sol
        self.sudoku_board = brd
        self.sudoku_givens = [v != 0 for v in brd]
        self.sudoku_notes = [set() for _ in range(81)]
        self.sudoku_sel = 0
        self.sudoku_mistakes = 0
        self.sudoku_hints = 0
        self.sudoku_start_ts = time.time()
        self.sudoku_complete = False

    def _build_sudoku_stage(self):
        tk = self.tk
        ctrl = tk.Frame(self.stage_panel, bg="#121721")
        ctrl.pack(fill="x", pady=(0, 6))
        for d_code, d_lbl in (("easy", "🌱 Dễ"), ("medium", "🌿 Vừa"), ("hard", "🔥 Khó"), ("evil", "👹 Ác mộng")):
            tk.Button(
                ctrl,
                text=d_lbl,
                command=lambda c=d_code: (self._new_sudoku_game(c), self.select_game("sudoku")),
                font=("Segoe UI", 8, "bold"),
                bg="#f59e0b" if self.sudoku_diff == d_code else "#1a2130",
                fg="#0b0e14" if self.sudoku_diff == d_code else "#cbd5e1",
                relief="flat",
                padx=8,
                pady=3,
                cursor="hand2",
            ).pack(side="left", padx=2)

        tk.Button(
            ctrl,
            text="💡 Gợi ý",
            command=self._sudoku_hint,
            font=("Segoe UI", 8, "bold"),
            bg="#1a2130",
            fg="#38bdf8",
            relief="flat",
            padx=8,
            pady=3,
            cursor="hand2",
        ).pack(side="right", padx=3)
        tk.Button(
            ctrl,
            text="✏️ Nháp (Phím N)",
            command=self._toggle_sudoku_note,
            font=("Segoe UI", 8, "bold"),
            bg="#1a2130",
            fg="#fbbf24",
            relief="flat",
            padx=8,
            pady=3,
            cursor="hand2",
        ).pack(side="right", padx=3)

        self.sudoku_info_lbl = tk.Label(self.stage_panel, text="", font=("Segoe UI", 9, "bold"), fg="#cbd5e1", bg="#1a2130", pady=4)
        self.sudoku_info_lbl.pack(fill="x", pady=(0, 6))

        self.sudoku_canvas = tk.Canvas(self.stage_panel, width=396, height=396, bg="#0b0e14", highlightthickness=2, highlightbackground="#f59e0b")
        self.sudoku_canvas.pack(anchor="center")
        self.sudoku_canvas.bind("<Button-1>", self._on_sudoku_click)

        num_bar = tk.Frame(self.stage_panel, bg="#121721")
        num_bar.pack(pady=(6, 0))
        for n in range(1, 10):
            tk.Button(
                num_bar,
                text=str(n),
                command=lambda v=n: self._sudoku_input(v),
                font=("Segoe UI", 10, "bold"),
                bg="#1a2130",
                fg="#fbbf24",
                width=3,
                relief="flat",
                cursor="hand2",
            ).pack(side="left", padx=2)
        tk.Button(
            num_bar,
            text="⌫ Xóa",
            command=lambda: self._sudoku_input(0),
            font=("Segoe UI", 9, "bold"),
            bg="#1a2130",
            fg="#f87171",
            padx=8,
            relief="flat",
            cursor="hand2",
        ).pack(side="left", padx=4)
        self._draw_sudoku()

    def _toggle_sudoku_note(self):
        self.sudoku_notes_mode = not self.sudoku_notes_mode
        self._draw_sudoku()

    def _on_sudoku_click(self, ev):
        cell = 396 / 9
        c, r = int(ev.x // cell), int(ev.y // cell)
        if 0 <= r < 9 and 0 <= c < 9:
            self.sudoku_sel = r * 9 + c
            self._draw_sudoku()

    def _sudoku_hint(self):
        if self.sudoku_complete:
            return
        empties = [i for i in range(81) if self.sudoku_board[i] != self.sudoku_sol[i]]
        if not empties:
            return
        idx = self.sudoku_sel if self.sudoku_sel in empties else random.choice(empties)
        self.sudoku_sel = idx
        self.sudoku_hints += 1
        self.sudoku_notes_mode = False
        self._sudoku_input(self.sudoku_sol[idx])

    def _sudoku_input(self, val: int):
        if self.sudoku_complete or self.sudoku_sel < 0 or self.sudoku_givens[self.sudoku_sel]:
            return
        idx = self.sudoku_sel
        if val == 0:
            self.sudoku_board[idx] = 0
            self.sudoku_notes[idx].clear()
            self._draw_sudoku()
            return
        if self.sudoku_notes_mode:
            if val in self.sudoku_notes[idx]:
                self.sudoku_notes[idx].remove(val)
            else:
                self.sudoku_notes[idx].add(val)
            self._draw_sudoku()
            return
        self.sudoku_board[idx] = val
        self.sudoku_notes[idx].clear()
        if val != self.sudoku_sol[idx]:
            self.sudoku_mistakes += 1
        elif self.sudoku_board == self.sudoku_sol:
            self.sudoku_complete = True
            elapsed = max(1, int(time.time() - self.sudoku_start_ts))
            score = max(100, 1200 - elapsed - self.sudoku_mistakes * 30 - self.sudoku_hints * 60)
            self.submit_score("sudoku", score, f"{self.sudoku_diff.upper()} • {elapsed}s")
        self._draw_sudoku()

    def _draw_sudoku(self):
        if not hasattr(self, "sudoku_canvas") or not self.sudoku_canvas.winfo_exists():
            return
        cv = self.sudoku_canvas
        cv.delete("all")
        W = 396
        cell = W / 9
        sr, sc = (self.sudoku_sel // 9, self.sudoku_sel % 9) if self.sudoku_sel >= 0 else (-1, -1)
        sval = self.sudoku_board[self.sudoku_sel] if self.sudoku_sel >= 0 else 0

        for i in range(81):
            r, c = i // 9, i % 9
            v = self.sudoku_board[i]
            x0, y0, x1, y1 = c * cell, r * cell, (c + 1) * cell, (r + 1) * cell
            bg = "#0b0e14"
            if i == self.sudoku_sel:
                bg = "#422c08"
            elif v > 0 and not self.sudoku_givens[i] and v != self.sudoku_sol[i]:
                bg = "#45121b"
            elif sval > 0 and v == sval:
                bg = "#112840"
            elif r == sr or c == sc or (r // 3 == sr // 3 and c // 3 == sc // 3):
                bg = "#141b27"
            cv.create_rectangle(x0, y0, x1, y1, fill=bg, outline="#1e293b")
            if v > 0:
                color = "#f8fafc" if self.sudoku_givens[i] else ("#f87171" if v != self.sudoku_sol[i] else "#38bdf8")
                cv.create_text((x0 + x1) / 2, (y0 + y1) / 2, text=str(v), fill=color, font=("Segoe UI", 14, "bold"))
            elif self.sudoku_notes[i]:
                notes_str = "".join(str(n) if n in self.sudoku_notes[i] else "·" for n in range(1, 10))
                cv.create_text((x0 + x1) / 2, (y0 + y1) / 2, text=notes_str[:5] + "\n" + notes_str[5:], fill="#fbbf24", font=("Consolas", 8))

        for k in (3, 6):
            p = k * cell
            cv.create_line(p, 0, p, W, fill="#f59e0b", width=2)
            cv.create_line(0, p, W, p, fill="#f59e0b", width=2)

        filled = sum(1 for i in range(81) if self.sudoku_board[i] == self.sudoku_sol[i])
        status = "🏆 HOÀN THÀNH SUDOKU!" if self.sudoku_complete else f"Đã điền: {filled}/81  •  Lỗi: {self.sudoku_mistakes}  •  Nháp: {'BẬT' if self.sudoku_notes_mode else 'TẮT'}"
        self.sudoku_info_lbl.configure(text=status, fg="#34d399" if self.sudoku_complete else "#fbbf24")

    # ==========================================================================
    # 3. CỜ VUA (8x8 Chess vs AI / 2P)
    # ==========================================================================
    def _init_chess_state(self):
        self.chess_mode = "ai"
        self.chess_flipped = False
        self._reset_chess_board()

    def _reset_chess_board(self):
        back = ["R", "N", "B", "Q", "K", "B", "N", "R"]
        self.chess_board = [
            ["b" + p for p in back],
            ["bP"] * 8,
            [""] * 8,
            [""] * 8,
            [""] * 8,
            [""] * 8,
            ["wP"] * 8,
            ["w" + p for p in back],
        ]
        self.chess_turn = "w"
        self.chess_sel = None
        self.chess_winner = None
        self.chess_history = []

    def _build_chess_stage(self):
        tk = self.tk
        ctrl = tk.Frame(self.stage_panel, bg="#121721")
        ctrl.pack(fill="x", pady=(0, 6))
        tk.Button(
            ctrl,
            text="🤖 Đấu Máy AI" if self.chess_mode == "ai" else "👥 2 Người Chơi",
            command=self._toggle_chess_mode,
            font=("Segoe UI", 9, "bold"),
            bg="#1a2130",
            fg="#fbbf24",
            relief="flat",
            padx=10,
            pady=3,
            cursor="hand2",
        ).pack(side="left")
        tk.Button(
            ctrl,
            text="🔃 Xoay Bàn",
            command=lambda: (setattr(self, "chess_flipped", not self.chess_flipped), self._draw_chess()),
            font=("Segoe UI", 9, "bold"),
            bg="#1a2130",
            fg="#38bdf8",
            relief="flat",
            padx=10,
            pady=3,
            cursor="hand2",
        ).pack(side="left", padx=6)
        tk.Button(
            ctrl,
            text="🔄 Ván Mới",
            command=lambda: (self._reset_chess_board(), self._draw_chess()),
            font=("Segoe UI", 9, "bold"),
            bg="#f59e0b",
            fg="#0b0e14",
            relief="flat",
            padx=12,
            pady=3,
            cursor="hand2",
        ).pack(side="right")

        self.chess_status_lbl = tk.Label(self.stage_panel, text="⚪ Lượt Trắng đi", font=("Segoe UI", 10, "bold"), fg="#fbbf24", bg="#1a2130", pady=4)
        self.chess_status_lbl.pack(fill="x", pady=(0, 6))

        self.chess_canvas = tk.Canvas(self.stage_panel, width=416, height=416, bg="#0b0e14", highlightthickness=2, highlightbackground="#f59e0b")
        self.chess_canvas.pack(anchor="center")
        self.chess_canvas.bind("<Button-1>", self._on_chess_click)
        self._draw_chess()

    def _toggle_chess_mode(self):
        self.chess_mode = "2p" if self.chess_mode == "ai" else "ai"
        self._reset_chess_board()
        self.select_game("chess")

    def _chess_moves_for(self, brd, r: int, c: int):
        p = brd[r][c]
        if not p:
            return []
        side, kind = p[0], p[1]
        opp = "b" if side == "w" else "w"
        res = []
        if kind == "P":
            d = -1 if side == "w" else 1
            sr = 6 if side == "w" else 1
            if 0 <= r + d < 8 and not brd[r + d][c]:
                res.append((r + d, c))
                if r == sr and not brd[r + 2 * d][c]:
                    res.append((r + 2 * d, c))
            for dc in (-1, 1):
                if 0 <= r + d < 8 and 0 <= c + dc < 8 and brd[r + d][c + dc].startswith(opp):
                    res.append((r + d, c + dc))
        elif kind == "N":
            for dr, dc in ((-2, -1), (-2, 1), (-1, -2), (-1, 2), (1, -2), (1, 2), (2, -1), (2, 1)):
                nr, nc = r + dr, c + dc
                if 0 <= nr < 8 and 0 <= nc < 8 and not brd[nr][nc].startswith(side):
                    res.append((nr, nc))
        elif kind == "K":
            for dr in (-1, 0, 1):
                for dc in (-1, 0, 1):
                    if dr or dc:
                        nr, nc = r + dr, c + dc
                        if 0 <= nr < 8 and 0 <= nc < 8 and not brd[nr][nc].startswith(side):
                            res.append((nr, nc))
        else:
            dirs = []
            if kind in ("R", "Q"):
                dirs.extend([(-1, 0), (1, 0), (0, -1), (0, 1)])
            if kind in ("B", "Q"):
                dirs.extend([(-1, -1), (-1, 1), (1, -1), (1, 1)])
            for dr, dc in dirs:
                nr, nc = r + dr, c + dc
                while 0 <= nr < 8 and 0 <= nc < 8:
                    t = brd[nr][nc]
                    if not t:
                        res.append((nr, nc))
                    else:
                        if t.startswith(opp):
                            res.append((nr, nc))
                        break
                    nr += dr
                    nc += dc
        return res

    def _on_chess_click(self, ev):
        if self.chess_winner:
            return
        cell = 416 / 8
        gx, gy = int(ev.x // cell), int(ev.y // cell)
        r = (7 - gy) if self.chess_flipped else gy
        c = (7 - gx) if self.chess_flipped else gx
        if not (0 <= r < 8 and 0 <= c < 8):
            return
        if self.chess_sel:
            sr, sc = self.chess_sel
            legal = self._chess_moves_for(self.chess_board, sr, sc)
            if (r, c) in legal:
                self._exec_chess_move(sr, sc, r, c)
                return
        p = self.chess_board[r][c]
        if p and p.startswith(self.chess_turn):
            self.chess_sel = (r, c)
        else:
            self.chess_sel = None
        self._draw_chess()

    def _exec_chess_move(self, fr, fc, tr, tc):
        p = self.chess_board[fr][fc]
        target = self.chess_board[tr][tc]
        self.chess_board[fr][fc] = ""
        if p == "wP" and tr == 0:
            p = "wQ"
        elif p == "bP" and tr == 7:
            p = "bQ"
        self.chess_board[tr][tc] = p
        self.chess_sel = None
        if target.endswith("K"):
            self.chess_winner = self.chess_turn
            if self.chess_winner == "w":
                self.submit_score("chess", 500, "Chiến thắng Cờ Vua")
            self._draw_chess()
            return
        self.chess_turn = "b" if self.chess_turn == "w" else "w"
        self._draw_chess()
        if self.chess_mode == "ai" and self.chess_turn == "b" and not self.chess_winner:
            self.app.root.after(220, self._chess_ai_move)

    def _chess_ai_move(self):
        vals = {"P": 100, "N": 320, "B": 330, "R": 500, "Q": 900, "K": 20000}
        moves = []
        for r in range(8):
            for c in range(8):
                if self.chess_board[r][c].startswith("b"):
                    for tr, tc in self._chess_moves_for(self.chess_board, r, c):
                        t = self.chess_board[tr][tc]
                        gain = vals.get(t[1], 0) if t else 0
                        center = (3.5 - abs(3.5 - tr)) * 5 + (3.5 - abs(3.5 - tc)) * 5
                        moves.append((gain + center + random.uniform(0, 12), r, c, tr, tc))
        if not moves:
            self.chess_winner = "w"
            self._draw_chess()
            return
        moves.sort(reverse=True)
        _, fr, fc, tr, tc = moves[0]
        self._exec_chess_move(fr, fc, tr, tc)

    def _draw_chess(self):
        if not hasattr(self, "chess_canvas") or not self.chess_canvas.winfo_exists():
            return
        cv = self.chess_canvas
        cv.delete("all")
        cell = 416 / 8
        uni = {
            "wK": "♔", "wQ": "♕", "wR": "♖", "wB": "♗", "wN": "♘", "wP": "♙",
            "bK": "♚", "bQ": "♛", "bR": "♜", "bB": "♝", "bN": "♞", "bP": "♟",
        }
        legal = self._chess_moves_for(self.chess_board, *self.chess_sel) if self.chess_sel else []
        for r in range(8):
            for c in range(8):
                dr = (7 - r) if self.chess_flipped else r
                dc = (7 - c) if self.chess_flipped else c
                x0, y0 = dc * cell, dr * cell
                is_light = (r + c) % 2 == 0
                bg = "#334155" if is_light else "#0f172a"
                if self.chess_sel == (r, c):
                    bg = "#b45309"
                cv.create_rectangle(x0, y0, x0 + cell, y0 + cell, fill=bg, outline="#1e293b")
                p = self.chess_board[r][c]
                if p:
                    col = "#fef3c7" if p.startswith("w") else "#38bdf8"
                    cv.create_text(x0 + cell / 2, y0 + cell / 2, text=uni.get(p, ""), fill=col, font=("Segoe UI Symbol", 24, "bold"))
                if (r, c) in legal:
                    cv.create_oval(x0 + cell * 0.38, y0 + cell * 0.38, x0 + cell * 0.62, y0 + cell * 0.62, fill="#f59e0b", outline="")
        if self.chess_winner:
            self.chess_status_lbl.configure(text=f"🏆 {'TRẮNG' if self.chess_winner == 'w' else 'ĐEN'} CHIẾN THẮNG!", fg="#34d399")
        else:
            self.chess_status_lbl.configure(text="⚪ Lượt Trắng đi" if self.chess_turn == "w" else "⚫ Lượt Đen đi", fg="#fbbf24")

    # ==========================================================================
    # 4. RẮN SĂN MỒI (20x20 Arcade Canvas)
    # ==========================================================================
    def _init_snake_state(self):
        self.snake_N = 20
        self.snake_best = 0
        self._reset_snake()

    def _reset_snake(self):
        self.snake_body = [(8, 10), (7, 10), (6, 10)]
        self.snake_dir = (1, 0)
        self.snake_next_dir = (1, 0)
        self.snake_score = 0
        self.snake_over = False
        self._spawn_snake_food()

    def _spawn_snake_food(self):
        free = [(x, y) for x in range(self.snake_N) for y in range(self.snake_N) if (x, y) not in self.snake_body]
        self.snake_food = random.choice(free) if free else (10, 10)

    def _build_snake_stage(self):
        tk = self.tk
        ctrl = tk.Frame(self.stage_panel, bg="#121721")
        ctrl.pack(fill="x", pady=(0, 6))
        self.snake_score_lbl = tk.Label(ctrl, text=f"Điểm: {self.snake_score}  •  Kỷ lục: {self.snake_best}", font=("Segoe UI", 10, "bold"), fg="#fbbf24", bg="#121721")
        self.snake_score_lbl.pack(side="left")
        tk.Button(
            ctrl,
            text="▶️ Chơi Ngay / Chơi Lại",
            command=self._start_snake_loop,
            font=("Segoe UI", 9, "bold"),
            bg="#f59e0b",
            fg="#0b0e14",
            relief="flat",
            padx=12,
            pady=3,
            cursor="hand2",
        ).pack(side="right")

        self.snake_canvas = tk.Canvas(self.stage_panel, width=400, height=400, bg="#0b0e14", highlightthickness=2, highlightbackground="#f59e0b")
        self.snake_canvas.pack(anchor="center")

        dpad = tk.Frame(self.stage_panel, bg="#121721")
        dpad.pack(pady=(6, 0))
        for txt, dx, dy in (("◀ Trái (A)", -1, 0), ("▲ Lên (W)", 0, -1), ("▼ Xuống (S)", 0, 1), ("▶ Phải (D)", 1, 0)):
            tk.Button(
                dpad,
                text=txt,
                command=lambda x=dx, y=dy: self._snake_set_dir(x, y),
                font=("Segoe UI", 8, "bold"),
                bg="#1a2130",
                fg="#e2e8f0",
                relief="flat",
                padx=8,
                pady=3,
                cursor="hand2",
            ).pack(side="left", padx=3)
        self._start_snake_loop()

    def _snake_set_dir(self, dx: int, dy: int):
        if (dx, dy) != (-self.snake_dir[0], -self.snake_dir[1]):
            self.snake_next_dir = (dx, dy)

    def _start_snake_loop(self):
        if self._snake_job:
            try:
                self.app.root.after_cancel(self._snake_job)
            except Exception:
                pass
        self._reset_snake()
        self._tick_snake()

    def _tick_snake(self):
        if self.active_game != "snake" or not hasattr(self, "snake_canvas") or not self.snake_canvas.winfo_exists():
            return
        self.snake_dir = self.snake_next_dir
        hx, hy = self.snake_body[0]
        nx, ny = hx + self.snake_dir[0], hy + self.snake_dir[1]
        if not (0 <= nx < self.snake_N and 0 <= ny < self.snake_N) or (nx, ny) in self.snake_body:
            self.snake_over = True
            if self.snake_score > self.snake_best:
                self.snake_best = self.snake_score
            if self.snake_score >= 30:
                self.submit_score("snake", self.snake_score, f"Dài {len(self.snake_body)} đốt")
            self._draw_snake()
            return
        self.snake_body.insert(0, (nx, ny))
        if (nx, ny) == self.snake_food:
            self.snake_score += 10
            if self.snake_score > self.snake_best:
                self.snake_best = self.snake_score
            self._spawn_snake_food()
        else:
            self.snake_body.pop()
        self._draw_snake()
        self._snake_job = self.app.root.after(120, self._tick_snake)

    def _draw_snake(self):
        if not hasattr(self, "snake_canvas") or not self.snake_canvas.winfo_exists():
            return
        cv = self.snake_canvas
        cv.delete("all")
        cell = 400 / self.snake_N
        fx, fy = self.snake_food
        cv.create_oval(fx * cell + 3, fy * cell + 3, (fx + 1) * cell - 3, (fy + 1) * cell - 3, fill="#ef4444", outline="")
        for idx, (x, y) in enumerate(self.snake_body):
            cv.create_rectangle(x * cell + 2, y * cell + 2, (x + 1) * cell - 2, (y + 1) * cell - 2, fill="#f59e0b" if idx == 0 else "#d97706", outline="")
        if self.snake_over:
            cv.create_rectangle(40, 160, 360, 240, fill="#121721", outline="#f59e0b", width=2)
            cv.create_text(200, 200, text=f"💀 KẾT THÚC: {self.snake_score} ĐIỂM\nBấm 'Chơi Lại' để tiếp tục", fill="#fbbf24", font=("Segoe UI", 11, "bold"), justify="center")
        self.snake_score_lbl.configure(text=f"Điểm: {self.snake_score}  •  Kỷ lục: {self.snake_best}")

    # ==========================================================================
    # 5. 2048 (4x4 Grid, Undo, Score Sync)
    # ==========================================================================
    def _init_2048_state(self):
        self.g2048_best = 0
        self._reset_2048()

    def _reset_2048(self):
        self.g2048_grid = [0] * 16
        self.g2048_score = 0
        self.g2048_history = []
        self._2048_spawn()
        self._2048_spawn()

    def _2048_spawn(self):
        empties = [i for i, v in enumerate(self.g2048_grid) if v == 0]
        if empties:
            self.g2048_grid[random.choice(empties)] = 2 if random.random() < 0.9 else 4

    def _build_2048_stage(self):
        tk = self.tk
        ctrl = tk.Frame(self.stage_panel, bg="#121721")
        ctrl.pack(fill="x", pady=(0, 6))
        self.g2048_lbl = tk.Label(ctrl, text="", font=("Segoe UI", 10, "bold"), fg="#fbbf24", bg="#121721")
        self.g2048_lbl.pack(side="left")
        tk.Button(
            ctrl,
            text="🔄 Ván Mới",
            command=lambda: (self._reset_2048(), self._draw_2048()),
            font=("Segoe UI", 9, "bold"),
            bg="#f59e0b",
            fg="#0b0e14",
            relief="flat",
            padx=12,
            pady=3,
            cursor="hand2",
        ).pack(side="right")
        tk.Button(
            ctrl,
            text="↩️ Hoàn Tác",
            command=self._2048_undo,
            font=("Segoe UI", 9, "bold"),
            bg="#1a2130",
            fg="#e2e8f0",
            relief="flat",
            padx=10,
            pady=3,
            cursor="hand2",
        ).pack(side="right", padx=6)

        self.g2048_canvas = tk.Canvas(self.stage_panel, width=380, height=380, bg="#0b0e14", highlightthickness=2, highlightbackground="#f59e0b")
        self.g2048_canvas.pack(anchor="center")

        dpad = tk.Frame(self.stage_panel, bg="#121721")
        dpad.pack(pady=(6, 0))
        for txt, d in (("◀ Trái (A)", "LEFT"), ("▲ Lên (W)", "UP"), ("▼ Xuống (S)", "DOWN"), ("▶ Phải (D)", "RIGHT")):
            tk.Button(
                dpad,
                text=txt,
                command=lambda mv=d: self._2048_move(mv),
                font=("Segoe UI", 8, "bold"),
                bg="#1a2130",
                fg="#e2e8f0",
                relief="flat",
                padx=8,
                pady=3,
                cursor="hand2",
            ).pack(side="left", padx=3)
        self._draw_2048()

    def _2048_undo(self):
        if self.g2048_history:
            self.g2048_grid, self.g2048_score = self.g2048_history.pop()
            self._draw_2048()

    def _2048_move(self, direction: str):
        prev = self.g2048_grid[:]
        prev_s = self.g2048_score
        gained_total = 0

        for i in range(4):
            if direction == "LEFT":
                idxs = [i * 4 + c for c in range(4)]
            elif direction == "RIGHT":
                idxs = [i * 4 + c for c in (3, 2, 1, 0)]
            elif direction == "UP":
                idxs = [r * 4 + i for r in range(4)]
            else:
                idxs = [r * 4 + i for r in (3, 2, 1, 0)]
            vals = [self.g2048_grid[k] for k in idxs if self.g2048_grid[k] != 0]
            out = []
            k = 0
            while k < len(vals):
                if k + 1 < len(vals) and vals[k] == vals[k + 1]:
                    m = vals[k] * 2
                    out.append(m)
                    gained_total += m
                    k += 2
                else:
                    out.append(vals[k])
                    k += 1
            while len(out) < 4:
                out.append(0)
            for pos, grid_idx in enumerate(idxs):
                self.g2048_grid[grid_idx] = out[pos]

        if self.g2048_grid != prev:
            self.g2048_history.append((prev, prev_s))
            if len(self.g2048_history) > 5:
                self.g2048_history.pop(0)
            self.g2048_score += gained_total
            if self.g2048_score > self.g2048_best:
                self.g2048_best = self.g2048_score
            self._2048_spawn()
            if self.g2048_score >= 500:
                self.submit_score("2048", self.g2048_score, f"Ô {max(self.g2048_grid)}")
            self._draw_2048()

    def _draw_2048(self):
        if not hasattr(self, "g2048_canvas") or not self.g2048_canvas.winfo_exists():
            return
        cv = self.g2048_canvas
        cv.delete("all")
        cell = 380 / 4
        colors = {
            0: "#121721", 2: "#1e293b", 4: "#334155", 8: "#b45309",
            16: "#d97706", 32: "#ea580c", 64: "#dc2626", 128: "#f59e0b",
            256: "#fbbf24", 512: "#facc15", 1024: "#38bdf8", 2048: "#10b981",
        }
        for i, v in enumerate(self.g2048_grid):
            r, c = i // 4, i % 4
            x0, y0 = c * cell + 6, r * cell + 6
            x1, y1 = (c + 1) * cell - 6, (r + 1) * cell - 6
            cv.create_rectangle(x0, y0, x1, y1, fill=colors.get(v, "#7c3aed"), outline="#262f40", width=2)
            if v:
                fg = "#0b0e14" if v in (128, 256, 512, 1024, 2048) else "#ffffff"
                cv.create_text((x0 + x1) / 2, (y0 + y1) / 2, text=str(v), fill=fg, font=("Segoe UI", 18, "bold"))
        self.g2048_lbl.configure(text=f"Điểm: {self.g2048_score}  •  Kỷ lục: {self.g2048_best}  •  Ô lớn nhất: {max(self.g2048_grid)}")


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
        ensure_windows_admin_for_ingame_hotkeys()
        import tkinter as tk
        root = tk.Tk()
        app = AOETrackerApp(root)
        root.mainloop()
