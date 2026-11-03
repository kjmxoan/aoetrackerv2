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

APP_VERSION_NUMBER = "5.3"
APP_VERSION = f"v{APP_VERSION_NUMBER} Wood-Gold Esports"
APP_TITLE = "TOOL BẢNG QUÂN AOE BY XO"
DEFAULT_SERVER_URL = "https://aoe-tracker.onrender.com/"


def parse_version_tuple(v_str: str) -> tuple:
    """Chuyển chuỗi phiên bản (VD: 'v5.1', '5.3.1') thành tuple số nguyên (5, 1) để so sánh chính xác."""
    nums = re.findall(r"\d+", str(v_str or "0"))
    if not nums:
        return (0,)
    return tuple(int(x) for x in nums[:4])

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
    "Carthaginian": ["Hamilcar Barca", "Matho", "Hannibal", "Hasdrubal", "Hanno", "Mago", "Gisco", "Bomilcar", "Spendius", "Adherbal", "Himilco", "Maharbal", "Xanthippus"],
    "Choson": ["Hyon", "Dangun", "Gwanggaeto", "Jumong", "Kija", "Ugeo", "Wiman", "Ulji Mundok", "Koi", "Piru", "Kunchogo", "Sosurim", "Kwanggaeto", "Changsu"],
    "Egyptian": ["Amenophis", "Ramses", "Cleopatra", "Hatshepsut", "Khufu", "Nefertiti", "Ptolemy", "Seti", "Thutmose", "Tutankhamun", "Akhenaten", "Cheops", "Menes", "Necho", "Psamtik", "Sneferu", "Zoser"],
    "Greek": ["Leonidas", "Erythrus", "Pericles", "Alexander", "Hippocrates", "Themistocles", "Pyrrhus", "Lysander", "Alcibiades", "Agamemnon", "Achilles", "Odysseus", "Miltiades", "Cimon", "Epaminondas", "Pelopidas", "Xenophon"],
    "Hittite": ["Tudhalyas", "Suppiluliumas", "Hattusilis", "Labarnas", "Mursilis", "Muwatalli", "Telipinus", "Anittas", "Hantilis", "Zidantas", "Ammunas", "Arnuwandas"],
    "Macedonian": ["Alexander", "Antigonus", "Antipater", "Cassander", "Craterus", "Demetrius", "Lysimachus", "Philip", "Ptolemy", "Seleucus", "Parmenion", "Perdiccas", "Eumenes", "Polyperchon", "Pyrrhus"],
    "Minoan": ["Gortys", "Aeacus", "Erythrus", "Minos", "Asterion", "Deucalion", "Idomeneus", "Rhadamanthus", "Sarpedon", "Talos", "Phaestus", "Knossos", "Cydon", "Catres", "Tylus", "Lyctus", "Mallia", "Zakros"],
    "Palmyran": ["Zobdas", "Syphax", "Jugurtha", "Zenobia", "Odaenathus", "Vaballathus", "Hairan", "Longinus", "Maeonius", "Zabdas", "Antiochus", "Septimius", "Vorodes"],
    "Persian": ["Astyages", "Cyrus", "Mithridates", "Darius", "Xerxes", "Cambyses", "Artaxerxes", "Shapur", "Tigranes", "Ardashir", "Bardiya", "Chosroes", "Hystaspes", "Phraates", "Tissaphernes"],
    "Phoenician": ["Ahiram", "Hiram", "Abibaal", "Dido", "Ethbaal", "Ittobaal", "Pygmalion", "Zakarbaal", "Azemilcus", "Baal", "Eshmunazar", "Luli", "Rib-Addi", "Strato", "Tabnit"],
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
        hw_max = int(w * 0.46)
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
                hh = int(round(hw * (301.0 / 468.0)))
                x1, x2 = int(round(cx - hw)), int(round(cx + hw))
                y1, y2 = int(round(cy - hh)), int(round(cy + hh))
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
            for hw in range(max(70, int(w * 0.10)), int(w * 0.45), 2):
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
                for hw_r in (hw_p - 1, hw_p, hw_p + 1):
                    if hw_r < 50:
                        continue
                    hh_r = int(round(hw_r * (301.0 / 468.0)))
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

    @staticmethod
    def verify_is_diplomacy_dialog(norm_624x400: np.ndarray) -> bool:
        # 1. Check tiêu đề DIPLOMACY chữ trắng nằm ở chính giữa thanh tiêu đề trên cùng (y: 6..32, x: 230..400)
        title_crop = norm_624x400[6:32, 230:400]
        min_t = np.min(title_crop, axis=2).astype(np.float32)
        max_t = np.max(title_crop, axis=2).astype(np.float32)
        white_title_px = int(np.sum((min_t > 155) & ((max_t - min_t) < 50)))
        if white_title_px < 100 or white_title_px > 2600:
            return False

        # Hai bên trái/phải của chữ DIPLOMACY trên thanh tiêu đề phải là nền đá/gỗ trống (không phải trang web trắng hoặc thanh tiêu đề chữ dài)
        left_slab = norm_624x400[8:30, 40:190]
        right_slab = norm_624x400[8:30, 435:585]
        w_left = int(np.sum((np.min(left_slab, axis=2) > 170) & ((np.max(left_slab, axis=2).astype(np.int16) - np.min(left_slab, axis=2).astype(np.int16)) < 40)))
        w_right = int(np.sum((np.min(right_slab, axis=2) > 170) & ((np.max(right_slab, axis=2).astype(np.int16) - np.min(right_slab, axis=2).astype(np.int16)) < 40)))
        if w_left > 120 or w_right > 120:
            return False

        # 2. Check bộ 3 nút đặc trưng riêng của bảng DIPLOMACY ở đáy hộp thoại (y: 368..396):
        #    - Nút trái (x: 75..145): Chữ 'OK' màu vàng (nhiều hơn hẳn vùng x: 170..235 của bảng Game Settings)
        #    - Nút giữa (x: 230..395): Chữ 'CLEAR TRIBUTES' màu trắng
        #    - Nút phải (x: 470..560): Chữ 'CANCEL' màu trắng
        ok_crop = norm_624x400[368:396, 75:145]
        b_ok, g_ok, r_ok = cv2.split(ok_crop)
        yellow_ok_px = int(np.sum((r_ok > 140) & (g_ok > 130) & (b_ok < 115) & ((r_ok.astype(np.int16) - b_ok.astype(np.int16)) > 55)))
        if yellow_ok_px < 12:
            return False

        clear_crop = norm_624x400[368:396, 230:395]
        min_cl = np.min(clear_crop, axis=2).astype(np.float32)
        max_cl = np.max(clear_crop, axis=2).astype(np.float32)
        white_clear_px = int(np.sum((min_cl > 150) & ((max_cl - min_cl) < 55)))
        if white_clear_px < 140:
            return False

        cancel_crop = norm_624x400[368:396, 470:560]
        min_ca = np.min(cancel_crop, axis=2).astype(np.float32)
        max_ca = np.max(cancel_crop, axis=2).astype(np.float32)
        white_cancel_px = int(np.sum((min_ca > 150) & ((max_ca - min_ca) < 55)))
        if white_cancel_px < 60:
            return False

        # 3. Check hàng tiêu đề cột 'Name' / 'Civilization' (y: 52..74, x: 10..240) và 'Ally' / 'Neutral' / 'Enemy' (x: 235..430)
        hdr_crop = norm_624x400[52:74, 10:240]
        min_h = np.min(hdr_crop, axis=2).astype(np.float32)
        max_h = np.max(hdr_crop, axis=2).astype(np.float32)
        white_hdr_px = int(np.sum((min_h > 150) & ((max_h - min_h) < 55)))
        if white_hdr_px < 35:
            return False

        stance_hdr_crop = norm_624x400[52:74, 235:430]
        min_sh = np.min(stance_hdr_crop, axis=2).astype(np.float32)
        max_sh = np.max(stance_hdr_crop, axis=2).astype(np.float32)
        white_stance_hdr_px = int(np.sum((min_sh > 150) & ((max_sh - min_sh) < 55)))
        if white_stance_hdr_px < 30:
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
    def clean_and_match_player_name(
        norm_624x400: np.ndarray,
        ocr_name_candidates,
        row_idx: int,
        full_civ: str,
        streamer_name: str,
        known_players=None,
    ):
        yc = int(round(95.0 + row_idx * 29.8))
        name_crop = norm_624x400[yc - 9:yc + 7, 14:134]
        min_n = np.min(name_crop, axis=2).astype(np.float32)
        max_n = np.max(name_crop, axis=2).astype(np.float32)
        wh_n = min_n - 0.55 * (max_n - min_n)
        bg_n = float(np.percentile(wh_n, 55))
        mask_n = wh_n > max(bg_n + 18.0, 138.0)
        if int(np.sum(mask_n)) < 10:
            return None

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
            res_s = (
                res_s.replace("rn", "m")
                .replace("gott", "gort")
                .replace("gotm", "gort")
                .replace("gonw", "gort")
                .replace("allalh", "allath")
                .replace("allh", "allth")
            )
            return res_s

        best_raw = ""
        best_quality = -1e9
        for exp_idx, raw in enumerate(ocr_name_candidates):
            if not raw:
                continue
            cleaned = "".join(ch for ch in raw if ch.isascii() and (ch.isalnum() or ch in " _-")).strip(" _-")
            if len(cleaned) < 2:
                continue
            if re.match(r"^(player|red|blue)\s*\d*$", cleaned, flags=re.IGNORECASE):
                continue
            alpha_cnt = sum(1 for ch in cleaned if ch.isalpha())
            if alpha_cnt < 2:
                continue
            weird_count = sum(1 for ch in raw if not (ch.isascii() and (ch.isalnum() or ch in " _-")))
            exp_bonus = 2.0 if exp_idx == 0 else (1.0 if exp_idx == 1 else 0.0)
            quality = alpha_cnt * 1.0 - weird_count * 2.5 + exp_bonus
            if quality > best_quality:
                best_quality = quality
                best_raw = cleaned

        civ_specific_ai = CIV_AI_NAMES.get(full_civ, [])
        pool = list(civ_specific_ai)
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

        # Đo chiều rộng thực tế (nw) và trích xuất đặc trưng 2D của chữ tên người chơi trên dòng hiện tại (từ x=9 để không cắt mất chữ cái đầu ở x=11)
        crop = norm_624x400[yc - 7:yc + 4, 9:120]
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
                if empty_run >= 5 and (xmax - xmin) >= 12:
                    break
        nw_obs = max(1, int(round((xmax - xmin + 1) * 1.0))) if xmax > xmin + 6 else 0

        # Tính trước độ tương quan mẫu chữ 2D chuẩn hóa theo chiều rộng (width-normalized 2D correlation)
        tmpl_corr_map = {}
        if AI_NAME_TEMPLATES and xmax > xmin + 6:
            patch = val[:, xmin:xmax + 1]
            for ai_name in pool:
                if ai_name not in AI_NAME_TEMPLATES:
                    continue
                tmpl, tw = AI_NAME_TEMPLATES[ai_name]
                t_patch = tmpl[:, :tw]
                p_res = cv2.resize(patch, (tw, 12), interpolation=cv2.INTER_LINEAR)
                num = float(np.sum((p_res - p_res.mean()) * (t_patch - t_patch.mean())))
                den = float(np.sqrt(np.sum((p_res - p_res.mean()) ** 2) * np.sum((t_patch - t_patch.mean()) ** 2))) + 1e-6
                tmpl_corr_map[ai_name] = max(0.0, num / den)

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
                if "ll" in cand_alpha and "ll" in target_alpha:
                    sim += 0.18
                # Điểm thưởng lớn nếu tên AI thuộc đúng loại quân (full_civ) của dòng này
                if target in civ_specific_ai:
                    sim += 0.22
                # Điểm thưởng độ khớp chiều rộng pixel chữ tên & tương quan hình ảnh 2D (giúp phân biệt chính xác Gortys, Aeacus, Vaballathus ở mọi độ phân giải)
                if nw_obs > 0 and target in AI_NAME_TEMPLATES:
                    _, tw = AI_NAME_TEMPLATES[target]
                    w_sc = max(0.0, 1.0 - abs(nw_obs - tw) / 20.0)
                    mc = tmpl_corr_map.get(target, 0.0)
                    sim = sim * 0.55 + mc * 0.45 + w_sc * 0.25
                if sim > best_sim:
                    best_sim = sim
                    best_match_name = target

        # Nếu phân vân giữa Kammu và Jimmu (cùng quân Yamato), kiểm tra độ rộng của cụm chữ đầu 'Ka' (rộng) so với 'Ji' (hẹp)
        if best_match_name in ("Kammu", "Jimmu") and full_civ == "Yamato":
            fc_crop = norm_624x400[yc - 7:yc + 3, 14:65]
            wh_fc = np.min(fc_crop, axis=2).astype(np.float32) - 0.55 * (
                np.max(fc_crop, axis=2).astype(np.float32) - np.min(fc_crop, axis=2).astype(np.float32)
            )
            cols_fc = np.where(np.sum(wh_fc > 155.0, axis=0) >= 1)[0]
            span_w = int(cols_fc[-1] - cols_fc[0] + 1) if len(cols_fc) >= 2 else 0
            best_match_name = "Kammu" if span_w >= 34 else "Jimmu"

        if best_match_name and best_sim >= 0.58:
            return best_match_name

        # Fallback thông minh cho dòng cờ màu (Vàng, Đỏ, Nâu, Xám trắng) hoặc độ phân giải 1600x900 / 1920x1080 khi đấu với AI:
        # So khớp chiều rộng & mẫu chữ 2D với danh sách AI chuẩn của đúng loại quân (full_civ)
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

        return best_raw if best_raw else None

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
        if not force and self.last_dialog_signature == sig and (time.time() - self.last_scan_time < 4.5):
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
            name_crop_check = norm[yc - 9:yc + 7, 8:134]
            min_nc = np.min(name_crop_check, axis=2).astype(np.float32)
            max_nc = np.max(name_crop_check, axis=2).astype(np.float32)
            wh_nc = min_nc - 0.55 * (max_nc - min_nc)
            bg_nc = float(np.percentile(wh_nc, 55))
            mask_nc = wh_nc > max(bg_nc + 18.0, 138.0)

            civ_crop = norm[yc - 9:yc + 9, 140:235]
            min_c = np.min(civ_crop, axis=2).astype(np.float32)
            max_c = np.max(civ_crop, axis=2).astype(np.float32)
            wh_c = min_c - 0.55 * (max_c - min_c)
            bg_c = float(np.percentile(wh_c, 55))
            mask_c = wh_c > max(bg_c + 20.0, 140.0)
            if np.sum(mask_c) < 12 or np.sum(mask_nc) < 10:
                continue

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

            # Dòng của chính người chơi mở F2 sẽ không có 3 ô radio Ally/Neutral/Enemy (max_radio < 120)
            if r == 0 or max_radio < 120.0:
                stance = "ALLY"
            elif s_ally > s_neut and s_ally > s_enem and s_ally > 90.0:
                stance = "ALLY"
            else:
                stance = "ENEMY"

            hsv_feat = self.extract_ribbon_hsv(norm, r)
            active_rows.append({
                "row_idx": r,
                "stance": stance,
                "max_radio": max_radio,
                "hsv_feat": hsv_feat,
                "w_obs": w_obs,
            })

            for x_start, x_end, base_x in [(8, 136, 20), (140, 238, 320)]:
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

        # Phải có ít nhất 2 người chơi, số người chơi phải chẵn (1v1, 2v2, 3v3, 4v4) và dòng 0 (người mở F2) bắt buộc phải có mặt
        if len(active_rows) < 2 or len(active_rows) % 2 != 0 or active_rows[0]["row_idx"] != 0:
            return None

        # Đảm bảo dòng người chơi đầu tiên luôn thuộc phe ALLY (Team Đỏ)
        active_rows[0]["stance"] = "ALLY"

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
                    if rel_x < 300:
                        name_cands[exp_idx].append((rel_x, str(w.get("text", ""))))
                    else:
                        civ_cands[exp_idx].append((rel_x, str(w.get("text", ""))))

            name_strs = [" ".join(t for _, t in sorted(cand)) for cand in name_cands if cand]
            civ_strs = [" ".join(t for _, t in sorted(cand)) for cand in civ_cands if cand]

            full_civ, short_civ = self.match_civ_for_row(norm, r, civ_strs, item["w_obs"])
            if not full_civ or not short_civ:
                return None

            player_name = self.clean_and_match_player_name(
                norm, name_strs, r, full_civ, streamer_name, known_players
            )
            if not player_name:
                return None

            item["name"] = player_name
            item["civ_full"] = full_civ
            item["civ_short"] = short_civ
            item["has_ocr_civ"] = bool(civ_strs)

        # Nếu OCR không đọc được chữ tiêu đề hộp thoại và cũng không đọc được chữ tên Quân nào -> loại bỏ cảnh giả
        if not has_hdr_keyword and sum(1 for it in active_rows if it.get("has_ocr_civ")) < max(1, len(active_rows) // 2):
            return None

        red_rows = [item for item in active_rows if item["stance"] == "ALLY"]
        blue_rows = [item for item in active_rows if item["stance"] != "ALLY"]

        if (len(red_rows) == 1 and len(blue_rows) >= 3 and len(active_rows) % 2 == 0) or not red_rows or not blue_rows:
            half = max(1, len(active_rows) // 2)
            red_rows = active_rows[:half]
            blue_rows = active_rows[half:]

        # Bắt buộc 2 đội phải cân bằng số lượng người chơi (1v1, 2v2, 3v3, 4v4) và có đủ tên + quân
        if not red_rows or not blue_rows or len(red_rows) != len(blue_rows):
            return None

        # Chỉ lưu chữ ký sau khi đã nhận diện thành công đầy đủ cả 2 đội
        self.last_dialog_signature = sig
        self.last_scan_time = time.time()

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
    "DIAMOND": ("💎 Hạng Kim Cương", "#eca133", "#241b10"),
    "GOLD": ("🥇 Hạng Vàng", "#eca133", "#241b10"),
    "SILVER": ("🥈 Hạng Bạc", "#e7ebf0", "#11151b"),
    "BRONZE": ("🥉 Hạng Đồng", "#d98f26", "#1f160e"),
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
        self.root.configure(bg="#080c16")
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
            fieldbackground="#11151b",
            background="#181e28",
            foreground="#e7ebf0",
            arrowcolor="#8e99a7",
            bordercolor="#2b3541",
            lightcolor="#2b3541",
            darkcolor="#080c16",
        )
        style.map(
            "Premium.TCombobox",
            fieldbackground=[("readonly", "#11151b")],
            selectbackground=[("readonly", "#11151b")],
            selectforeground=[("readonly", "#e7ebf0")],
        )
        style.configure(
            "Treeview",
            background="#11151b",
            foreground="#e7ebf0",
            fieldbackground="#11151b",
            bordercolor="#2b3541",
            rowheight=26,
            font=("Segoe UI", 9),
        )
        style.configure(
            "Treeview.Heading",
            background="#181e28",
            foreground="#e7ebf0",
            bordercolor="#2b3541",
            font=("Segoe UI", 9, "bold"),
        )
        style.map(
            "Treeview",
            background=[("selected", "#eca133")],
            foreground=[("selected", "#11151b")],
        )
        style.map(
            "Treeview.Heading",
            background=[("active", "#222b38")],
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

        # Khởi tạo toàn bộ biến điều khiển dùng chung giữa Màn hình Đăng nhập, Bảng Điều Khiển và Tab Cài đặt VIP
        self.server_url_var = tk.StringVar(value=self.settings.get("server_url", DEFAULT_SERVER_URL))
        self.player_name_var = tk.StringVar(value=self.settings.get("player_name", "XO"))
        self.player_pass_var = tk.StringVar(value=self.settings.get("player_password", "111"))
        self.auto_scan_var = tk.BooleanVar(value=bool(self.settings.get("auto_scan", True)))
        self.target_score_var = tk.StringVar(value=str(self.settings.get("target_score", 100)))
        self.show_date_var = tk.BooleanVar(value=bool(self.settings.get("show_date_corner", True)))
        self.c_mode_var = tk.BooleanVar(value=bool(self.settings.get("c_mode_enabled", False)))
        saved_mode_code = self.settings.get("marquee_mode", "ALL")
        self.marquee_label_var = tk.StringVar(
            value=MARQUEE_MODE_TO_LABEL.get(saved_mode_code, MARQUEE_MODE_LABELS[0][1])
        )
        self.custom_marquee_var = tk.StringVar(value=self.settings.get("custom_marquee_text", ""))
        self.obs_url_preview_var = tk.StringVar()
        self.obs_chat_url_preview_var = tk.StringVar()
        self.player_name_var.trace_add("write", lambda *_: self._update_obs_preview_entry())
        self._update_obs_preview_entry()

        self.active_tab = "BATTLE"
        self.log_drawer_open = False

        # ======================================================================
        # 1. MÀN HÌNH ĐĂNG NHẬP RIÊNG KHI BẮT ĐẦU CHẠY TOOL (LOGIN SCREEN)
        # ======================================================================
        self.login_screen_frame = tk.Frame(self.root, bg="#080c16")

        login_card = tk.Frame(
            self.login_screen_frame,
            bg="#181e28",
            highlightthickness=1,
            highlightbackground="#2b3541",
            padx=36,
            pady=30,
        )
        login_card.place(relx=0.5, rely=0.48, anchor="center", width=480)

        emblem_top = tk.Frame(
            login_card,
            bg="#11151b",
            highlightthickness=1,
            highlightbackground="#2b3541",
            padx=16,
            pady=8,
        )
        emblem_top.pack(pady=(0, 12))
        tk.Label(
            emblem_top,
            text="⚔️🛡️",
            font=("Segoe UI Emoji", 22, "bold"),
            fg="#eca133",
            bg="#11151b",
        ).pack()

        tk.Label(
            login_card,
            text=APP_TITLE,
            font=("Segoe UI", 15, "bold"),
            fg="#e7ebf0",
            bg="#181e28",
        ).pack()

        tk.Label(
            login_card,
            text=f"AOE Command Center ({APP_VERSION}) • Đăng nhập hệ thống",
            font=("Segoe UI", 9, "bold"),
            fg="#8e99a7",
            bg="#181e28",
        ).pack(pady=(2, 6))

        self.login_ver_badge_btn = tk.Button(
            login_card,
            text=f"🏷️ Phiên bản hiện tại: v{APP_VERSION_NUMBER} (Bản mới nhất)",
            command=self.open_download_tool_url,
            font=("Segoe UI", 8, "bold"),
            bg="#11151b",
            fg="#34d399",
            relief="flat",
            highlightthickness=1,
            highlightbackground="#2b3541",
            padx=12,
            pady=3,
            cursor="hand2",
        )
        self.login_ver_badge_btn.pack(pady=(0, 14))

        # Ô nhập Tên Player / Streamer
        tk.Label(
            login_card,
            text="Tên tài khoản Player / Streamer",
            font=("Segoe UI", 9, "bold"),
            fg="#e7ebf0",
            bg="#181e28",
        ).pack(anchor="w")
        login_user_entry = tk.Entry(
            login_card,
            textvariable=self.player_name_var,
            font=("Segoe UI", 11, "bold"),
            bg="#11151b",
            fg="#e7ebf0",
            insertbackground="#eca133",
            relief="flat",
            highlightthickness=1,
            highlightbackground="#2b3541",
            highlightcolor="#eca133",
        )
        login_user_entry.pack(fill="x", ipady=6, pady=(4, 12))
        login_user_entry.bind("<Return>", lambda _e: self.login_and_start())

        # Ô nhập Mật khẩu
        tk.Label(
            login_card,
            text="Mật khẩu",
            font=("Segoe UI", 9, "bold"),
            fg="#e7ebf0",
            bg="#181e28",
        ).pack(anchor="w")
        login_pass_entry = tk.Entry(
            login_card,
            textvariable=self.player_pass_var,
            show="*",
            font=("Consolas", 11, "bold"),
            bg="#11151b",
            fg="#e7ebf0",
            insertbackground="#eca133",
            relief="flat",
            highlightthickness=1,
            highlightbackground="#2b3541",
            highlightcolor="#eca133",
        )
        login_pass_entry.pack(fill="x", ipady=6, pady=(4, 10))
        login_pass_entry.bind("<Return>", lambda _e: self.login_and_start())

        # Tùy chọn nâng cao: Ẩn/Hiện Server URL để không làm rối màn hình đăng nhập
        srv_toggle_row = tk.Frame(login_card, bg="#181e28")
        srv_toggle_row.pack(fill="x", pady=(0, 6))

        srv_drawer = tk.Frame(login_card, bg="#181e28")
        self._srv_drawer_visible = False

        def _toggle_srv_drawer():
            self._srv_drawer_visible = not self._srv_drawer_visible
            if self._srv_drawer_visible:
                srv_drawer.pack(fill="x", pady=(0, 10), before=self.login_btn)
                btn_toggle_srv.config(text="▲ Ẩn cài đặt máy chủ (Server URL)")
            else:
                srv_drawer.pack_forget()
                btn_toggle_srv.config(text="⚙ Đổi địa chỉ máy chủ (Server URL)")

        btn_toggle_srv = tk.Button(
            srv_toggle_row,
            text="⚙ Đổi địa chỉ máy chủ (Server URL)",
            command=_toggle_srv_drawer,
            font=("Segoe UI", 8, "bold"),
            bg="#181e28",
            fg="#8e99a7",
            activebackground="#181e28",
            activeforeground="#eca133",
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
            bg="#181e28",
        ).pack(anchor="w")
        tk.Entry(
            srv_drawer,
            textvariable=self.server_url_var,
            font=("Consolas", 9),
            bg="#11151b",
            fg="#e7ebf0",
            insertbackground="#eca133",
            relief="flat",
            highlightthickness=1,
            highlightbackground="#2b3541",
            highlightcolor="#eca133",
        ).pack(fill="x", ipady=4, pady=(3, 0))

        self.login_btn = tk.Button(
            login_card,
            text="⚡ Đăng Nhập Vào Bảng Điều Khiển",
            command=self.login_and_start,
            font=("Segoe UI", 11, "bold"),
            bg="#eca133",
            fg="#11151b",
            activebackground="#d98f26",
            activeforeground="#11151b",
            relief="flat",
            pady=8,
            cursor="hand2",
        )
        self.login_btn.pack(fill="x", pady=(8, 8))
        self._bind_hover(self.login_btn, "#eca133", "#d98f26", "#11151b", "#11151b")

        self.login_status_lbl = tk.Label(
            login_card,
            text="Nhập tài khoản Player (hoặc Admin XO) để bắt đầu sử dụng Tool.",
            font=("Segoe UI", 9, "bold"),
            fg="#8e99a7",
            bg="#181e28",
            wraplength=400,
            justify="center",
        )
        self.login_status_lbl.pack(pady=(2, 0))

        # ======================================================================
        # 2. MÀN HÌNH CHÍNH SAU KHI ĐĂNG NHẬP (MAIN DASHBOARD VỚI TAB GÓC PHẢI)
        # ======================================================================
        self.main_app_frame = tk.Frame(self.root, bg="#080c16")

        # --- HEADER GỌN GÀNG + THANH TAB Ở GÓC PHẢI ---
        hdr_outer = tk.Frame(
            self.main_app_frame,
            bg="#181e28",
            highlightthickness=1,
            highlightbackground="#2b3541",
            padx=16,
            pady=10,
        )
        hdr_outer.pack(fill="x", padx=14, pady=(10, 5))

        left_hdr = tk.Frame(hdr_outer, bg="#181e28")
        left_hdr.pack(side="left", anchor="w")

        emblem_box = tk.Frame(
            left_hdr,
            bg="#11151b",
            highlightthickness=1,
            highlightbackground="#2b3541",
            padx=10,
            pady=5,
        )
        emblem_box.pack(side="left", padx=(0, 12))
        tk.Label(
            emblem_box,
            text="⚔️🛡️",
            font=("Segoe UI Emoji", 14, "bold"),
            fg="#eca133",
            bg="#11151b",
        ).pack()

        title_stack = tk.Frame(left_hdr, bg="#181e28")
        title_stack.pack(side="left")

        hud_tag_row = tk.Frame(title_stack, bg="#181e28")
        hud_tag_row.pack(anchor="w")

        self.pulse_dot = tk.Label(
            hud_tag_row,
            text="● Đã kết nối",
            font=("Segoe UI", 8, "bold"),
            fg="#34d399",
            bg="#11151b",
            padx=7,
            pady=1,
        )
        self.pulse_dot.pack(side="left", padx=(0, 6))

        self.status_lbl = tk.Label(
            hud_tag_row,
            text="Chưa kết nối",
            font=("Segoe UI", 9, "bold"),
            fg="#8e99a7",
            bg="#181e28",
        )
        self.status_lbl.pack(side="left")

        tk.Label(
            title_stack,
            text=f"{APP_TITLE}",
            font=("Segoe UI", 13, "bold"),
            fg="#e7ebf0",
            bg="#181e28",
        ).pack(anchor="w", pady=(1, 0))

        # --- GÓC PHẢI HEADER: NGÀY GIỜ, HẠNG VIP & CÁC TAB ĐIỀU HƯỚNG ---
        right_hdr = tk.Frame(hdr_outer, bg="#181e28")
        right_hdr.pack(side="right", anchor="e")

        top_meta_row = tk.Frame(right_hdr, bg="#181e28")
        top_meta_row.pack(anchor="e", pady=(0, 6))

        self.header_ver_badge_btn = tk.Button(
            top_meta_row,
            text=f"🏷️ Ver {APP_VERSION_NUMBER}",
            command=self.open_download_tool_url,
            font=("Segoe UI", 8, "bold"),
            fg="#34d399",
            bg="#11151b",
            relief="flat",
            padx=8,
            pady=2,
            highlightthickness=1,
            highlightbackground="#2b3541",
            cursor="hand2",
        )
        self.header_ver_badge_btn.pack(side="left", padx=(0, 8))

        self.tier_badge_lbl = tk.Label(
            top_meta_row,
            text="🥉 Hạng Đồng",
            font=("Segoe UI", 9, "bold"),
            fg="#eca133",
            bg="#11151b",
            padx=9,
            pady=2,
            highlightthickness=1,
            highlightbackground="#2b3541",
            cursor="hand2",
        )
        self.tier_badge_lbl.pack(side="left", padx=(0, 8))
        self.tier_badge_lbl.bind("<Button-1>", lambda _e: self.open_my_profile_window())

        self.date_corner_lbl = tk.Label(
            top_meta_row,
            text="📅 --/--/---- • --:--:--",
            font=("Consolas", 9, "bold"),
            fg="#8e99a7",
            bg="#11151b",
            padx=9,
            pady=2,
            highlightthickness=1,
            highlightbackground="#2b3541",
        )
        self.date_corner_lbl.pack(side="left")

        # Thanh Tab điều hướng ở góc phải
        nav_tabs_row = tk.Frame(right_hdr, bg="#181e28")
        nav_tabs_row.pack(anchor="e")

        self.tab_battle_btn = tk.Button(
            nav_tabs_row,
            text="⚔️ Bảng Điều Khiển",
            command=lambda: self.switch_main_tab("BATTLE"),
            font=("Segoe UI", 9, "bold"),
            bg="#eca133",
            fg="#11151b",
            relief="flat",
            padx=12,
            pady=4,
            cursor="hand2",
        )
        self.tab_battle_btn.pack(side="left", padx=(0, 6))

        self.tab_settings_btn = tk.Button(
            nav_tabs_row,
            text="⚙️ Tùy Chỉnh Cài Đặt VIP",
            command=lambda: self.switch_main_tab("SETTINGS"),
            font=("Segoe UI", 9, "bold"),
            bg="#11151b",
            fg="#e7ebf0",
            relief="flat",
            highlightthickness=1,
            highlightbackground="#2b3541",
            padx=12,
            pady=4,
            cursor="hand2",
        )
        self.tab_settings_btn.pack(side="left", padx=(0, 6))

        self.my_profile_btn = tk.Button(
            nav_tabs_row,
            text="👤 Tài Khoản",
            command=self.open_my_profile_window,
            font=("Segoe UI", 9, "bold"),
            bg="#11151b",
            fg="#e7ebf0",
            relief="flat",
            highlightthickness=1,
            highlightbackground="#2b3541",
            padx=10,
            pady=4,
            cursor="hand2",
        )
        self.my_profile_btn.pack(side="left", padx=(0, 6))
        self._bind_hover(self.my_profile_btn, "#11151b", "#222b38", "#e7ebf0", "#ffffff")

        self.admin_mgr_btn = tk.Button(
            nav_tabs_row,
            text="🛡️ Quản Trị Admin",
            command=self.open_admin_manager_window,
            font=("Segoe UI", 9, "bold"),
            bg="#11151b",
            fg="#eca133",
            relief="flat",
            highlightthickness=1,
            highlightbackground="#2b3541",
            padx=10,
            pady=4,
            cursor="hand2",
        )
        self.admin_mgr_btn.pack(side="left", padx=(0, 6))
        self._bind_hover(self.admin_mgr_btn, "#11151b", "#222b38", "#eca133", "#ffffff")

        self.logout_btn = tk.Button(
            nav_tabs_row,
            text="🚪 Đăng xuất",
            command=self.logout_to_login_screen,
            font=("Segoe UI", 9, "bold"),
            bg="#11151b",
            fg="#f0657b",
            relief="flat",
            highlightthickness=1,
            highlightbackground="#c94a61",
            padx=10,
            pady=4,
            cursor="hand2",
        )
        self.logout_btn.pack(side="left")
        self._bind_hover(self.logout_btn, "#11151b", "#2b161d", "#f0657b", "#fda4af")

        # ======================================================================
        # VÙNG CHỨA CÁC TAB CHÍNH (TAB 1: BẢNG ĐIỀU KHIỂN | TAB 2: CÀI ĐẶT VIP)
        # ======================================================================
        self.tab_container = tk.Frame(self.main_app_frame, bg="#080c16")
        self.tab_container.pack(fill="both", expand=True)

        self.battle_tab_frame = tk.Frame(self.tab_container, bg="#080c16")
        self.settings_tab_frame = tk.Frame(self.tab_container, bg="#080c16")

        # ----------------------------------------------------------------------
        # TAB 1: BẢNG ĐIỀU KHIỂN CHÍNH (QUÉT DIPLOMACY + COPY LINK OBS + TỈ SỐ + CHAT LIVE)
        # ----------------------------------------------------------------------
        # Thanh công cụ nhanh + Copy Link OBS & Hướng dẫn OBS nằm ngay trên Bảng Điều Khiển
        quick_bar = tk.Frame(
            self.battle_tab_frame,
            bg="#181e28",
            highlightthickness=1,
            highlightbackground="#2b3541",
            padx=14,
            pady=8,
        )
        quick_bar.pack(fill="x", padx=14, pady=(2, 5))

        tk.Checkbutton(
            quick_bar,
            text="Tự động quét Diplomacy (F2)",
            variable=self.auto_scan_var,
            command=self.save_current_config,
            font=("Segoe UI", 9, "bold"),
            fg="#e7ebf0",
            bg="#181e28",
            selectcolor="#11151b",
            activebackground="#181e28",
            activeforeground="#eca133",
            cursor="hand2",
        ).pack(side="left", padx=(0, 10))

        self.btn_scan_now = tk.Button(
            quick_bar,
            text="🔍 Quét F2 ngay",
            command=self.manual_scan_screen,
            font=("Segoe UI", 9, "bold"),
            bg="#eca133",
            fg="#11151b",
            relief="flat",
            padx=11,
            pady=4,
            cursor="hand2",
        )
        self.btn_scan_now.pack(side="left", padx=(0, 6))
        self._bind_hover(self.btn_scan_now, "#eca133", "#d98f26", "#11151b", "#11151b")

        self.btn_test_img = tk.Button(
            quick_bar,
            text="🖼️ Test ảnh...",
            command=self.test_from_image_file,
            font=("Segoe UI", 9, "bold"),
            bg="#11151b",
            fg="#e7ebf0",
            relief="flat",
            highlightthickness=1,
            highlightbackground="#2b3541",
            padx=10,
            pady=4,
            cursor="hand2",
        )
        self.btn_test_img.pack(side="left", padx=(0, 6))
        self._bind_hover(self.btn_test_img, "#11151b", "#222b38", "#e7ebf0", "#ffffff")

        # Cụm nút Copy Link OBS & Hướng dẫn OBS đặt ngay trên Bảng Điều Khiển (bên phải)
        self.open_web_btn = tk.Button(
            quick_bar,
            text="🌐 Mở Web",
            command=self.open_web_dashboard,
            font=("Segoe UI", 9, "bold"),
            bg="#11151b",
            fg="#e7ebf0",
            relief="flat",
            highlightthickness=1,
            highlightbackground="#2b3541",
            padx=10,
            pady=4,
            cursor="hand2",
        )
        self.open_web_btn.pack(side="right")
        self._bind_hover(self.open_web_btn, "#11151b", "#222b38", "#e7ebf0", "#ffffff")

        btn_obs_guide = tk.Button(
            quick_bar,
            text="📖 Hướng dẫn OBS",
            command=self.show_obs_guide_window,
            font=("Segoe UI", 9, "bold"),
            bg="#11151b",
            fg="#e7ebf0",
            relief="flat",
            highlightthickness=1,
            highlightbackground="#2b3541",
            padx=10,
            pady=4,
            cursor="hand2",
        )
        btn_obs_guide.pack(side="right", padx=(0, 6))
        self._bind_hover(btn_obs_guide, "#11151b", "#222b38", "#e7ebf0", "#ffffff")

        btn_fb_live = tk.Button(
            quick_bar,
            text="🔵 Kết nối FB Group Live",
            command=self.show_fb_group_live_bridge_window,
            font=("Segoe UI", 9, "bold"),
            bg="#152238",
            fg="#60a5fa",
            relief="flat",
            highlightthickness=1,
            highlightbackground="#2563eb",
            padx=10,
            pady=4,
            cursor="hand2",
        )
        btn_fb_live.pack(side="right", padx=(0, 6))
        self._bind_hover(btn_fb_live, "#152238", "#1d4ed8", "#60a5fa", "#ffffff")

        btn_copy_chat_obs = tk.Button(
            quick_bar,
            text="💬 Copy Link OBS Chat",
            command=self.copy_obs_chat_link,
            font=("Segoe UI", 9, "bold"),
            bg="#11151b",
            fg="#eca133",
            relief="flat",
            highlightthickness=1,
            highlightbackground="#2b3541",
            padx=10,
            pady=4,
            cursor="hand2",
        )
        btn_copy_chat_obs.pack(side="right", padx=(0, 6))
        self._bind_hover(btn_copy_chat_obs, "#11151b", "#222b38", "#eca133", "#ffffff")

        btn_copy_obs = tk.Button(
            quick_bar,
            text="📋 Copy Link OBS Bảng Quân",
            command=self.copy_obs_link,
            font=("Segoe UI", 9, "bold"),
            bg="#eca133",
            fg="#11151b",
            relief="flat",
            padx=11,
            pady=4,
            cursor="hand2",
        )
        btn_copy_obs.pack(side="right", padx=(0, 6))
        self._bind_hover(btn_copy_obs, "#eca133", "#d98f26", "#11151b", "#11151b")

        # --- KHU VỰC TRUNG TÂM: ĐIỀU KHIỂN TRẬN ĐẤU (TEAM ĐỎ VS TEAM XANH) ---
        battle_card = tk.Frame(
            self.battle_tab_frame,
            bg="#181e28",
            highlightthickness=1,
            highlightbackground="#2b3541",
            padx=16,
            pady=12,
        )
        battle_card.pack(fill="x", padx=14, pady=5)

        arena_grid = tk.Frame(battle_card, bg="#181e28")
        arena_grid.pack(fill="x")
        arena_grid.columnconfigure(0, weight=4)
        arena_grid.columnconfigure(1, weight=3)
        arena_grid.columnconfigure(2, weight=4)

        # --- CARD TRÁI: TEAM ĐỎ ---
        self.red_card = tk.Frame(
            arena_grid,
            bg="#1e171b",
            highlightthickness=1,
            highlightbackground="#5c242c",
            padx=12,
            pady=10,
        )
        self.red_card.grid(row=0, column=0, sticky="nsew", padx=(0, 8))

        red_hdr = tk.Frame(self.red_card, bg="#1e171b")
        red_hdr.pack(fill="x")
        tk.Label(
            red_hdr,
            text="🔴 Team Đỏ (Chủ nhà)",
            font=("Segoe UI", 11, "bold"),
            fg="#f87171",
            bg="#1e171b",
        ).pack(side="left")
        self.red_count_lbl = tk.Label(
            red_hdr,
            text="0 người chơi",
            font=("Segoe UI", 9, "bold"),
            fg="#fca5a5",
            bg="#11151b",
            padx=8,
            pady=1,
        )
        self.red_count_lbl.pack(side="right")

        self.red_roster_lbl = tk.Label(
            self.red_card,
            text="Chưa có đội hình Team Đỏ\n(Bấm F2 Diplomacy trong game để quét)",
            font=("Segoe UI", 10, "bold"),
            fg="#e7ebf0",
            bg="#11151b",
            justify="left",
            anchor="w",
            padx=10,
            pady=10,
            height=5,
        )
        self.red_roster_lbl.pack(fill="x", pady=8)

        self.btn_red_win = tk.Button(
            self.red_card,
            text="🔴 Team Đỏ thắng trận này (+1)",
            command=lambda: self.set_current_winner("RED"),
            font=("Segoe UI", 10, "bold"),
            bg="#c83745",
            fg="#ffffff",
            activebackground="#a82835",
            relief="flat",
            pady=7,
            cursor="hand2",
        )
        self.btn_red_win.pack(fill="x")
        self._bind_hover(self.btn_red_win, "#c83745", "#a82835", "#ffffff", "#ffffff")

        # --- CARD GIỮA: TỶ SỐ TRẬN ĐẤU TRUNG TÂM ---
        center_hud = tk.Frame(
            arena_grid,
            bg="#11151b",
            highlightthickness=1,
            highlightbackground="#2b3541",
            padx=12,
            pady=10,
        )
        center_hud.grid(row=0, column=1, sticky="nsew", padx=4)

        self.match_mode_lbl = tk.Label(
            center_hud,
            text="Chạm 100 • Chờ kèo đấu",
            font=("Segoe UI", 10, "bold"),
            fg="#eca133",
            bg="#181e28",
            padx=10,
            pady=3,
        )
        self.match_mode_lbl.pack(pady=(0, 4))

        self.score_lbl = tk.Label(
            center_hud,
            text="0  -  0",
            font=("Segoe UI", 30, "bold"),
            fg="#e7ebf0",
            bg="#11151b",
        )
        self.score_lbl.pack(pady=2)

        self.c_mode_summary_lbl = tk.Label(
            center_hud,
            text="Chế độ chuẩn • Tổng 0 trận",
            font=("Segoe UI", 9, "bold"),
            fg="#8e99a7",
            bg="#11151b",
            wraplength=240,
            justify="center",
        )
        self.c_mode_summary_lbl.pack(pady=(2, 2))

        self.stars_counter_lbl = tk.Label(
            center_hud,
            text="⭐ 0 sao được tặng trên Live",
            font=("Segoe UI", 9, "bold"),
            fg="#eca133",
            bg="#11151b",
        )
        self.stars_counter_lbl.pack(pady=(0, 6))

        self.btn_end_match = tk.Button(
            center_hud,
            text="🗑 Kết thúc kèo đấu",
            command=self.finish_current_match,
            font=("Segoe UI", 10, "bold"),
            bg="#181e28",
            fg="#f0657b",
            activebackground="#2b161d",
            activeforeground="#fda4af",
            relief="flat",
            highlightthickness=1,
            highlightbackground="#c94a61",
            pady=6,
            cursor="hand2",
        )
        self.btn_end_match.pack(side="bottom", fill="x")
        self._bind_hover(self.btn_end_match, "#181e28", "#2b161d", "#f0657b", "#fda4af")

        # --- CARD PHẢI: TEAM XANH ---
        self.blue_card = tk.Frame(
            arena_grid,
            bg="#151d29",
            highlightthickness=1,
            highlightbackground="#284268",
            padx=12,
            pady=10,
        )
        self.blue_card.grid(row=0, column=2, sticky="nsew", padx=(8, 0))

        blue_hdr = tk.Frame(self.blue_card, bg="#151d29")
        blue_hdr.pack(fill="x")
        tk.Label(
            blue_hdr,
            text="🔵 Team Xanh (Đội khách)",
            font=("Segoe UI", 11, "bold"),
            fg="#60a5fa",
            bg="#151d29",
        ).pack(side="left")
        self.blue_count_lbl = tk.Label(
            blue_hdr,
            text="0 người chơi",
            font=("Segoe UI", 9, "bold"),
            fg="#93c5fd",
            bg="#11151b",
            padx=8,
            pady=1,
        )
        self.blue_count_lbl.pack(side="right")

        self.blue_roster_lbl = tk.Label(
            self.blue_card,
            text="Chưa có đội hình Team Xanh\n(Bấm F2 Diplomacy trong game để quét)",
            font=("Segoe UI", 10, "bold"),
            fg="#e7ebf0",
            bg="#11151b",
            justify="left",
            anchor="w",
            padx=10,
            pady=10,
            height=5,
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
            pady=7,
            cursor="hand2",
        )
        self.btn_blue_win.pack(fill="x")
        self._bind_hover(self.btn_blue_win, "#2563eb", "#1d4ed8", "#ffffff", "#ffffff")

        # --- KHU VỰC DƯỚI CỦA BẢNG ĐIỀU KHIỂN: BẠN BÈ ĐANG LIVE & SẢNH CHAT TẶNG SAO ---
        social_card = tk.Frame(
            self.battle_tab_frame,
            bg="#181e28",
            highlightthickness=1,
            highlightbackground="#2b3541",
            padx=16,
            pady=10,
        )
        social_card.pack(fill="both", expand=True, padx=14, pady=5)

        friends_hdr = tk.Frame(social_card, bg="#181e28")
        friends_hdr.pack(fill="x")

        tk.Label(
            friends_hdr,
            text="👥 Bạn bè đang Live & Sảnh Chat Giao Lưu",
            font=("Segoe UI", 11, "bold"),
            fg="#e7ebf0",
            bg="#181e28",
        ).pack(side="left")

        friend_add_box = tk.Frame(friends_hdr, bg="#181e28")
        friend_add_box.pack(side="right")

        self.friend_target_var = tk.StringVar()
        tk.Entry(
            friend_add_box,
            textvariable=self.friend_target_var,
            font=("Segoe UI", 9),
            bg="#11151b",
            fg="#e7ebf0",
            insertbackground="#eca133",
            width=18,
            relief="flat",
            highlightthickness=1,
            highlightbackground="#2b3541",
        ).pack(side="left", padx=(0, 6), ipady=2)

        btn_add_friend = tk.Button(
            friend_add_box,
            text="+ Kết bạn / Hủy",
            command=self.toggle_friend_action,
            font=("Segoe UI", 8, "bold"),
            bg="#11151b",
            fg="#e7ebf0",
            relief="flat",
            highlightthickness=1,
            highlightbackground="#2b3541",
            padx=8,
            pady=2,
            cursor="hand2",
        )
        btn_add_friend.pack(side="left")
        self._bind_hover(btn_add_friend, "#11151b", "#222b38", "#e7ebf0", "#ffffff")

        self.friends_status_lbl = tk.Label(
            social_card,
            text="Kết nối tài khoản để xem bạn bè nào đang 🔴 LIVE hoặc 🟢 Online.",
            font=("Segoe UI", 9, "bold"),
            fg="#8e99a7",
            bg="#11151b",
            justify="left",
            anchor="w",
            padx=10,
            pady=5,
            wraplength=980,
        )
        self.friends_status_lbl.pack(fill="x", pady=(6, 4))

        self.friends_live_btn_frame = tk.Frame(social_card, bg="#181e28")
        self.friends_live_btn_frame.pack(fill="x", pady=(0, 6))

        chat_hdr = tk.Frame(social_card, bg="#181e28")
        chat_hdr.pack(fill="x", pady=(0, 4))

        self.lobby_badge_lbl = tk.Label(
            chat_hdr,
            text="Sảnh Chat Live · Máy XO",
            font=("Segoe UI", 10, "bold"),
            fg="#e7ebf0",
            bg="#181e28",
        )
        self.lobby_badge_lbl.pack(side="left")

        star_btns = tk.Frame(chat_hdr, bg="#181e28")
        star_btns.pack(side="right")

        btn_my_lobby = tk.Button(
            star_btns,
            text="🏠 Sảnh của tôi",
            command=lambda: self.enter_friend_live_lobby(""),
            font=("Segoe UI", 8, "bold"),
            bg="#11151b",
            fg="#e7ebf0",
            relief="flat",
            highlightthickness=1,
            highlightbackground="#2b3541",
            padx=8,
            pady=2,
            cursor="hand2",
        )
        btn_my_lobby.pack(side="left", padx=(0, 6))
        self._bind_hover(btn_my_lobby, "#11151b", "#222b38", "#e7ebf0", "#ffffff")

        btn_fb_chat_hdr = tk.Button(
            star_btns,
            text="🔵 Kết nối FB Live",
            command=self.show_fb_group_live_bridge_window,
            font=("Segoe UI", 8, "bold"),
            bg="#152238",
            fg="#60a5fa",
            relief="flat",
            highlightthickness=1,
            highlightbackground="#2563eb",
            padx=8,
            pady=2,
            cursor="hand2",
        )
        btn_fb_chat_hdr.pack(side="left", padx=(0, 6))
        self._bind_hover(btn_fb_chat_hdr, "#152238", "#1d4ed8", "#60a5fa", "#ffffff")

        for amt, lbl_txt in [(1, "🌟 Tặng +1 Sao"), (10, "🌟 +10 Sao"), (50, "💎 +50 Sao")]:
            b = tk.Button(
                star_btns,
                text=lbl_txt,
                command=lambda a=amt: self.send_star_gift_action(a),
                font=("Segoe UI", 8, "bold"),
                bg="#11151b",
                fg="#eca133",
                relief="flat",
                highlightthickness=1,
                highlightbackground="#2b3541",
                padx=8,
                pady=2,
                cursor="hand2",
            )
            b.pack(side="left", padx=(4, 0))
            self._bind_hover(b, "#11151b", "#222b38", "#eca133", "#ffffff")

        self.chat_box = tk.Text(
            social_card,
            bg="#11151b",
            fg="#e7ebf0",
            font=("Segoe UI", 9),
            relief="flat",
            height=6,
            padx=10,
            pady=6,
            state="disabled",
            highlightthickness=1,
            highlightbackground="#2b3541",
        )
        self.chat_box.pack(fill="both", expand=True, pady=(2, 6))
        self.chat_box.tag_config("SENDER", foreground="#eca133", font=("Segoe UI", 9, "bold"))
        self.chat_box.tag_config("FB_SENDER", foreground="#60a5fa", font=("Segoe UI", 9, "bold"))
        self.chat_box.tag_config("STAR", foreground="#eca133", font=("Segoe UI", 9, "bold"))
        self.chat_box.tag_config("MSG", foreground="#e7ebf0")

        chat_input_row = tk.Frame(social_card, bg="#181e28")
        chat_input_row.pack(fill="x")

        self.chat_msg_var = tk.StringVar()
        chat_entry = tk.Entry(
            chat_input_row,
            textvariable=self.chat_msg_var,
            font=("Segoe UI", 9),
            bg="#11151b",
            fg="#e7ebf0",
            insertbackground="#eca133",
            relief="flat",
            highlightthickness=1,
            highlightbackground="#2b3541",
        )
        chat_entry.pack(side="left", fill="x", expand=True, padx=(0, 6), ipady=4)
        chat_entry.bind("<Return>", lambda _e: self.send_chat_message_action())

        btn_send_chat = tk.Button(
            chat_input_row,
            text="Gửi bình luận",
            command=self.send_chat_message_action,
            font=("Segoe UI", 9, "bold"),
            bg="#eca133",
            fg="#11151b",
            relief="flat",
            padx=14,
            pady=3,
            cursor="hand2",
        )
        btn_send_chat.pack(side="right")
        self._bind_hover(btn_send_chat, "#eca133", "#d98f26", "#11151b", "#11151b")

        # ----------------------------------------------------------------------
        # TAB 2: TÙY CHỈNH CÀI ĐẶT VIP & KẾT NỐI MÁY CHỦ (SETTINGS TAB)
        # ----------------------------------------------------------------------
        vip_card = tk.Frame(
            self.settings_tab_frame,
            bg="#181e28",
            highlightthickness=1,
            highlightbackground="#2b3541",
            padx=22,
            pady=18,
        )
        vip_card.pack(fill="x", padx=14, pady=(6, 10))

        vip_hdr = tk.Frame(vip_card, bg="#181e28")
        vip_hdr.pack(fill="x", pady=(0, 12))

        tk.Label(
            vip_hdr,
            text="⚙️ Tùy chỉnh Cài đặt VIP Overlay & Hệ thống",
            font=("Segoe UI", 12, "bold"),
            fg="#e7ebf0",
            bg="#181e28",
        ).pack(side="left")

        tk.Button(
            vip_hdr,
            text="← Quay lại Bảng Điều Khiển",
            command=lambda: self.switch_main_tab("BATTLE"),
            font=("Segoe UI", 9, "bold"),
            bg="#11151b",
            fg="#eca133",
            relief="flat",
            highlightthickness=1,
            highlightbackground="#2b3541",
            padx=12,
            pady=4,
            cursor="hand2",
        ).pack(side="right")

        tk.Label(
            vip_card,
            text="Phân quyền Hạng VIP: 🥈 Hạng Bạc (Chạm X, Hiện ngày góc phải)  •  🥇 Hạng Vàng (Tùy chỉnh dòng chữ chạy)  •  💎 Hạng Kim Cương (Đánh theo C - Séc 1, 2, 3)",
            font=("Segoe UI", 9, "bold"),
            fg="#8e99a7",
            bg="#181e28",
        ).pack(anchor="w", pady=(0, 14))

        # Mục 1: Kèo chạm & Tùy chọn hiển thị
        vip_row1 = tk.Frame(vip_card, bg="#181e28")
        vip_row1.pack(fill="x", pady=6)

        tk.Label(
            vip_row1,
            text="Kèo đấu chạm bao nhiêu (🥈 Bạc+):",
            font=("Segoe UI", 10, "bold"),
            fg="#e7ebf0",
            bg="#181e28",
        ).pack(side="left")

        tk.Entry(
            vip_row1,
            textvariable=self.target_score_var,
            font=("Consolas", 11, "bold"),
            bg="#11151b",
            fg="#eca133",
            insertbackground="#eca133",
            width=8,
            justify="center",
            relief="flat",
            highlightthickness=1,
            highlightbackground="#2b3541",
        ).pack(side="left", padx=(8, 22), ipady=4)

        tk.Checkbutton(
            vip_row1,
            text="Hiển thị ngày ở góc phải Overlay (🥈 Bạc+)",
            variable=self.show_date_var,
            font=("Segoe UI", 10, "bold"),
            fg="#e7ebf0",
            bg="#181e28",
            selectcolor="#11151b",
            activebackground="#181e28",
            activeforeground="#e7ebf0",
            cursor="hand2",
        ).pack(side="left", padx=(0, 22))

        tk.Checkbutton(
            vip_row1,
            text="🏆 Đánh theo 'C' — Hiện bảng phụ Séc 1, 2, 3 bên phải (💎 Kim Cương)",
            variable=self.c_mode_var,
            font=("Segoe UI", 10, "bold"),
            fg="#e7ebf0",
            bg="#181e28",
            selectcolor="#11151b",
            activebackground="#181e28",
            activeforeground="#eca133",
            cursor="hand2",
        ).pack(side="left")

        # Mục 2: Chế độ dòng chữ chạy
        vip_row2 = tk.Frame(vip_card, bg="#181e28")
        vip_row2.pack(fill="x", pady=10)

        tk.Label(
            vip_row2,
            text="Chế độ dòng chữ chạy (🥇 Vàng+):",
            font=("Segoe UI", 10, "bold"),
            fg="#e7ebf0",
            bg="#181e28",
        ).pack(side="left")

        self.marquee_combo = self.ttk.Combobox(
            vip_row2,
            textvariable=self.marquee_label_var,
            values=[lbl for _, lbl in MARQUEE_MODE_LABELS],
            state="readonly",
            width=38,
            style="Premium.TCombobox",
            font=("Segoe UI", 10),
        )
        self.marquee_combo.pack(side="left", padx=(10, 18))

        tk.Label(
            vip_row2,
            text="Nội dung chữ tùy chỉnh:",
            font=("Segoe UI", 10, "bold"),
            fg="#e7ebf0",
            bg="#181e28",
        ).pack(side="left")

        tk.Entry(
            vip_row2,
            textvariable=self.custom_marquee_var,
            font=("Segoe UI", 10),
            bg="#11151b",
            fg="#e7ebf0",
            insertbackground="#eca133",
            relief="flat",
            highlightthickness=1,
            highlightbackground="#2b3541",
        ).pack(side="left", fill="x", expand=True, padx=(8, 0), ipady=5)

        # Mục 3: Cấu hình Server URL nâng cao trong Tab Cài đặt
        vip_row3 = tk.Frame(vip_card, bg="#181e28")
        vip_row3.pack(fill="x", pady=(10, 6))

        tk.Label(
            vip_row3,
            text="Địa chỉ máy chủ (Server URL):",
            font=("Segoe UI", 9, "bold"),
            fg="#8e99a7",
            bg="#181e28",
        ).pack(side="left")

        tk.Entry(
            vip_row3,
            textvariable=self.server_url_var,
            font=("Consolas", 9),
            bg="#11151b",
            fg="#8e99a7",
            insertbackground="#eca133",
            width=42,
            relief="flat",
            highlightthickness=1,
            highlightbackground="#2b3541",
        ).pack(side="left", padx=(8, 16), ipady=4)

        self.apply_vip_btn = tk.Button(
            vip_row3,
            text="⚡ Lưu & Áp dụng cấu hình lên OBS",
            command=self.apply_vip_overlay_settings,
            font=("Segoe UI", 10, "bold"),
            bg="#eca133",
            fg="#11151b",
            activebackground="#d98f26",
            relief="flat",
            padx=20,
            pady=6,
            cursor="hand2",
        )
        self.apply_vip_btn.pack(side="right")
        self._bind_hover(self.apply_vip_btn, "#eca133", "#d98f26", "#11151b", "#11151b")

        # ======================================================================
        # 3. THANH TRẠNG THÁI NHẬT KÝ 1 DÒNG Ở ĐÁY + NÚT MỞ XEM CHI TIẾT LOG
        # ======================================================================
        self.log_drawer_frame = tk.Frame(
            self.main_app_frame,
            bg="#181e28",
            highlightthickness=1,
            highlightbackground="#2b3541",
            padx=12,
            pady=8,
        )

        self.log_box = tk.Text(
            self.log_drawer_frame,
            bg="#11151b",
            fg="#e7ebf0",
            font=("Consolas", 9),
            relief="flat",
            height=6,
            padx=10,
            pady=6,
            insertbackground="#eca133",
            highlightthickness=1,
            highlightbackground="#2b3541",
        )
        self.log_box.pack(fill="both", expand=True)
        self.log_box.tag_config("TIME", foreground="#6f7986")
        self.log_box.tag_config("DEFAULT", foreground="#e7ebf0")
        self.log_box.tag_config("SUCCESS", foreground="#34d399")
        self.log_box.tag_config("WARN", foreground="#eca133")
        self.log_box.tag_config("ERROR", foreground="#f0657b")
        self.log_box.tag_config("TEAM", foreground="#eca133")

        self.status_log_bar = tk.Frame(
            self.main_app_frame,
            bg="#181e28",
            highlightthickness=1,
            highlightbackground="#2b3541",
            padx=12,
            pady=5,
        )
        self.status_log_bar.pack(fill="x", side="bottom", padx=14, pady=(2, 10))

        self.latest_log_lbl = tk.Label(
            self.status_log_bar,
            text="📜 Sẵn sàng — Khi đóng Tool, kèo đấu đang LIVE sẽ tự động kết thúc.",
            font=("Consolas", 9),
            fg="#8e99a7",
            bg="#181e28",
            anchor="w",
        )
        self.latest_log_lbl.pack(side="left", fill="x", expand=True)

        self.btn_toggle_log = tk.Button(
            self.status_log_bar,
            text="📜 Xem chi tiết Nhật ký ▲",
            command=self.toggle_log_drawer,
            font=("Segoe UI", 8, "bold"),
            bg="#11151b",
            fg="#e7ebf0",
            relief="flat",
            highlightthickness=1,
            highlightbackground="#2b3541",
            padx=10,
            pady=2,
            cursor="hand2",
        )
        self.btn_toggle_log.pack(side="right")
        self._bind_hover(self.btn_toggle_log, "#11151b", "#222b38", "#e7ebf0", "#ffffff")

        # Mặc định hiển thị Tab Bảng Điều Khiển bên trong Main Frame, nhưng mở Tool sẽ vào Màn hình Đăng nhập trước
        self.battle_tab_frame.pack(fill="both", expand=True)
        self.login_screen_frame.pack(fill="both", expand=True)

        self.log(f"Khởi động {APP_TITLE} ({APP_VERSION}) thành công.", "DEFAULT")
        self.log("Hãy đăng nhập tài khoản Player và ấn F2 (Diplomacy) trong game để tự động lên bảng quân.", "TEAM")

    def switch_main_tab(self, tab_name: str):
        self.active_tab = tab_name
        if tab_name == "SETTINGS":
            self.battle_tab_frame.pack_forget()
            self.settings_tab_frame.pack(fill="both", expand=True)
            self.tab_settings_btn.configure(bg="#eca133", fg="#11151b", highlightthickness=0)
            self.tab_battle_btn.configure(bg="#11151b", fg="#e7ebf0", highlightthickness=1, highlightbackground="#2b3541")
        else:
            self.settings_tab_frame.pack_forget()
            self.battle_tab_frame.pack(fill="both", expand=True)
            self.tab_battle_btn.configure(bg="#eca133", fg="#11151b", highlightthickness=0)
            self.tab_settings_btn.configure(bg="#11151b", fg="#e7ebf0", highlightthickness=1, highlightbackground="#2b3541")

    def toggle_log_drawer(self):
        self.log_drawer_open = not self.log_drawer_open
        if self.log_drawer_open:
            self.log_drawer_frame.pack(fill="x", side="bottom", padx=14, pady=(2, 2), before=self.status_log_bar)
            self.btn_toggle_log.configure(text="📜 Ẩn Nhật ký ▼", fg="#eca133")
        else:
            self.log_drawer_frame.pack_forget()
            self.btn_toggle_log.configure(text="📜 Xem chi tiết Nhật ký ▲", fg="#e7ebf0")

    def show_main_dashboard_screen(self):
        self.login_screen_frame.pack_forget()
        self.main_app_frame.pack(fill="both", expand=True)
        self.switch_main_tab("BATTLE")

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
            fg="#eca133",
        )

    def _start_clock_loop(self):
        def _tick():
            if not self.running:
                return
            try:
                now_str = time.strftime("📅 %d/%m/%Y • %H:%M:%S")
                self.date_corner_lbl.configure(text=now_str)
                if self.is_logged_in:
                    self.pulse_dot.configure(fg="#34d399", text="● Đã kết nối")
                else:
                    self.pulse_dot.configure(fg="#eca133", text="● Chờ đăng nhập")
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
            "WARN": "#eca133",
            "TEAM": "#eca133",
            "DEFAULT": "#e7ebf0",
        }

        def _append():
            try:
                self.log_box.insert("end", f"[{ts}] ", "TIME")
                self.log_box.insert("end", f"{message}\n", tag)
                self.log_box.see("end")
                if hasattr(self, "latest_log_lbl"):
                    one_line = message.replace("\n", " ")
                    if len(one_line) > 105:
                        one_line = one_line[:102] + "..."
                    self.latest_log_lbl.configure(
                        text=f"📜 [{ts}] {one_line}",
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
        win.configure(bg="#080c16")
        win.resizable(False, False)

        card = tk.Frame(win, bg="#181e28", highlightthickness=1, highlightbackground="#2b3541", padx=18, pady=16)
        card.pack(fill="both", expand=True, padx=14, pady=14)

        tk.Label(
            card,
            text="📺 Hướng dẫn gán Overlay Bảng Quân & Khung Chat vào OBS Studio",
            font=("Segoe UI", 12, "bold"),
            fg="#e7ebf0",
            bg="#181e28",
        ).pack(anchor="w", pady=(0, 10))

        # Link 1: Bảng quân
        step1 = tk.LabelFrame(
            card,
            text=" 1. Link OBS Bảng Quân + Hiệu ứng Tặng Sao (Width: 980 x Height: 600) ",
            font=("Segoe UI", 9, "bold"),
            fg="#e7ebf0",
            bg="#181e28",
            padx=12,
            pady=8,
        )
        step1.pack(fill="x", pady=6)

        url_entry = tk.Entry(
            step1,
            font=("Consolas", 9, "bold"),
            bg="#11151b",
            fg="#34d399",
            relief="flat",
            readonlybackground="#11151b",
        )
        url_entry.insert(0, obs_url)
        url_entry.configure(state="readonly")
        url_entry.pack(side="left", fill="x", expand=True, ipady=4, padx=(0, 8))

        tk.Button(
            step1,
            text="📋 Copy Link Bảng Quân",
            command=self.copy_obs_link,
            font=("Segoe UI", 9, "bold"),
            bg="#eca133",
            fg="#11151b",
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
            fg="#e7ebf0",
            bg="#181e28",
            padx=12,
            pady=8,
        )
        step_chat.pack(fill="x", pady=6)

        chat_url_entry = tk.Entry(
            step_chat,
            font=("Consolas", 9, "bold"),
            bg="#11151b",
            fg="#eca133",
            relief="flat",
            readonlybackground="#11151b",
        )
        chat_url_entry.insert(0, obs_chat_url)
        chat_url_entry.configure(state="readonly")
        chat_url_entry.pack(side="left", fill="x", expand=True, ipady=4, padx=(0, 8))

        tk.Button(
            step_chat,
            text="💬 Copy Link Khung Chat",
            command=self.copy_obs_chat_link,
            font=("Segoe UI", 9, "bold"),
            bg="#11151b",
            fg="#e7ebf0",
            relief="flat",
            highlightthickness=1,
            highlightbackground="#2b3541",
            padx=12,
            pady=3,
            cursor="hand2",
        ).pack(side="right")

        step2 = tk.LabelFrame(
            card,
            text=" 3. Các bước thêm nguồn Browser trong OBS Studio ",
            font=("Segoe UI", 9, "bold"),
            fg="#e7ebf0",
            bg="#181e28",
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
            fg="#8e99a7",
            bg="#181e28",
        ).pack(anchor="w")

        tk.Button(
            card,
            text="Đã hiểu & Đóng hướng dẫn",
            command=win.destroy,
            font=("Segoe UI", 10, "bold"),
            bg="#eca133",
            fg="#11151b",
            relief="flat",
            padx=20,
            pady=6,
            cursor="hand2",
        ).pack(pady=(12, 0))

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
                            bg="#eca133",
                            fg="#11151b",
                            highlightthickness=0,
                        )
                    if hasattr(self, "header_ver_badge_btn"):
                        self.header_ver_badge_btn.configure(
                            text=f"🚀 Cập nhật v{srv_ver} (Đang dùng v{APP_VERSION_NUMBER})",
                            bg="#eca133",
                            fg="#11151b",
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
                            bg="#11151b",
                            fg="#34d399",
                            highlightthickness=1,
                            highlightbackground="#2b3541",
                        )
                    if hasattr(self, "header_ver_badge_btn"):
                        self.header_ver_badge_btn.configure(
                            text=f"🏷️ Ver {APP_VERSION_NUMBER}",
                            bg="#11151b",
                            fg="#34d399",
                            highlightthickness=1,
                            highlightbackground="#2b3541",
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
                self.login_status_lbl.configure(text="⚠️ Vui lòng nhập đầy đủ Tên Player và Mật khẩu!", fg="#eca133")
            self.messagebox.showwarning("Thiếu thông tin", "Vui lòng nhập Tên Player và Mật khẩu!")
            return

        if hasattr(self, "login_status_lbl"):
            self.login_status_lbl.configure(text="⏳ Đang xác thực tài khoản với máy chủ...", fg="#eca133")

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
        win.configure(bg="#080c16")

        hdr_card = tk.Frame(win, bg="#181e28", highlightthickness=1, highlightbackground="#2b3541", padx=18, pady=12)
        hdr_card.pack(fill="x", padx=14, pady=(12, 6))

        title_lbl = tk.Label(
            hdr_card,
            text=f"👤 Hồ sơ tài khoản: {self.player_name_var.get().strip()}",
            font=("Segoe UI", 13, "bold"),
            fg="#e7ebf0",
            bg="#181e28",
        )
        title_lbl.pack(anchor="w")

        sub_lbl = tk.Label(
            hdr_card,
            text="Đang tải thông tin chi tiết từ máy chủ...",
            font=("Segoe UI", 9, "bold"),
            fg="#8e99a7",
            bg="#181e28",
        )
        sub_lbl.pack(anchor="w", pady=(2, 0))

        # Lưới 4 thẻ thông tin chính
        stats_grid = tk.Frame(win, bg="#080c16")
        stats_grid.pack(fill="x", padx=14, pady=4)
        for c_i in range(4):
            stats_grid.columnconfigure(c_i, weight=1)

        def _make_stat_card(col_idx, title_txt, default_val, color_hex):
            box = tk.Frame(stats_grid, bg="#181e28", highlightthickness=1, highlightbackground="#2b3541", padx=12, pady=10)
            box.grid(row=0, column=col_idx, sticky="nsew", padx=(0 if col_idx == 0 else 5, 0 if col_idx == 3 else 5))
            tk.Label(box, text=title_txt, font=("Segoe UI", 8, "bold"), fg="#8e99a7", bg="#181e28").pack(anchor="w")
            val_l = tk.Label(box, text=default_val, font=("Segoe UI", 11, "bold"), fg=color_hex, bg="#181e28")
            val_l.pack(anchor="w", pady=(3, 0))
            return val_l

        lbl_tier_val = _make_stat_card(0, "HẠNG VIP & TRẠNG THÁI", "---", "#eca133")
        lbl_created_val = _make_stat_card(1, "NGÀY TẠO / KÍCH HOẠT", "---", "#e7ebf0")
        lbl_expires_val = _make_stat_card(2, "NGÀY HẾT HẠN SỬ DỤNG", "---", "#34d399")
        lbl_stars_val = _make_stat_card(3, "SỐ DƯ SAO & SAO LIVE", "---", "#eca133")

        # Thanh đổi mật khẩu cá nhân
        pwd_card = tk.Frame(win, bg="#181e28", highlightthickness=1, highlightbackground="#2b3541", padx=16, pady=10)
        pwd_card.pack(fill="x", padx=14, pady=5)

        note_info_lbl = tk.Label(
            pwd_card,
            text="Ghi chú tài khoản: ---",
            font=("Segoe UI", 9, "bold"),
            fg="#e7ebf0",
            bg="#181e28",
        )
        note_info_lbl.pack(side="left")

        pwd_right = tk.Frame(pwd_card, bg="#181e28")
        pwd_right.pack(side="right")
        tk.Label(pwd_right, text="Đổi mật khẩu mới:", font=("Segoe UI", 9, "bold"), fg="#8e99a7", bg="#181e28").pack(side="left", padx=(0, 6))
        new_pw_var = tk.StringVar()
        tk.Entry(
            pwd_right,
            textvariable=new_pw_var,
            show="*",
            font=("Consolas", 9, "bold"),
            bg="#11151b",
            fg="#e7ebf0",
            width=16,
            relief="flat",
            highlightthickness=1,
            highlightbackground="#2b3541",
        ).pack(side="left", padx=(0, 8), ipady=3)

        def _change_my_pw():
            npw = new_pw_var.get().strip()
            if len(npw) < 2:
                self.messagebox.showwarning("Mật khẩu ngắn", "Vui lòng nhập mật khẩu mới có ít nhất 2 ký tự!", parent=win)
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
                        },
                        timeout=10,
                    )
                    d = res.json()
                    if d.get("status") == "success":
                        self.root.after(0, lambda: self.player_pass_var.set(npw))
                        self.root.after(0, self.save_current_config)
                        win.after(0, lambda: new_pw_var.set(""))
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
            bg="#eca133",
            fg="#11151b",
            relief="flat",
            padx=12,
            pady=3,
            cursor="hand2",
        ).pack(side="left")

        # 2 Khung lịch sử: Lịch sử Nạp Sao & Lịch sử Gia Hạn VIP
        hist_split = tk.Frame(win, bg="#080c16")
        hist_split.pack(fill="both", expand=True, padx=14, pady=(4, 12))
        hist_split.columnconfigure(0, weight=1)
        hist_split.columnconfigure(1, weight=1)
        hist_split.rowconfigure(0, weight=1)

        star_card = tk.Frame(hist_split, bg="#181e28", highlightthickness=1, highlightbackground="#2b3541", padx=12, pady=10)
        star_card.grid(row=0, column=0, sticky="nsew", padx=(0, 6))
        tk.Label(
            star_card,
            text="🌟 Lịch sử Nạp Sao & Tặng/Nhận Sao",
            font=("Segoe UI", 9, "bold"),
            fg="#eca133",
            bg="#181e28",
        ).pack(anchor="w", pady=(0, 6))
        star_txt = tk.Text(star_card, bg="#11151b", fg="#e7ebf0", font=("Consolas", 9), relief="flat", padx=8, pady=6, state="disabled", highlightthickness=1, highlightbackground="#2b3541")
        star_txt.pack(fill="both", expand=True)

        vip_card_h = tk.Frame(hist_split, bg="#181e28", highlightthickness=1, highlightbackground="#2b3541", padx=12, pady=10)
        vip_card_h.grid(row=0, column=1, sticky="nsew", padx=(6, 0))
        tk.Label(
            vip_card_h,
            text="👑 Lịch sử Gia hạn VIP & Biến động tài khoản",
            font=("Segoe UI", 9, "bold"),
            fg="#e7ebf0",
            bg="#181e28",
        ).pack(anchor="w", pady=(0, 6))
        vip_txt = tk.Text(vip_card_h, bg="#11151b", fg="#e7ebf0", font=("Consolas", 9), relief="flat", padx=8, pady=6, state="disabled", highlightthickness=1, highlightbackground="#2b3541")
        vip_txt.pack(fill="both", expand=True)

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
                    win.after(0, lambda: sub_lbl.config(text=f"❌ Lỗi tải thông tin: {e}", fg="#f0657b"))

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
        win.configure(bg="#080c16")

        selected_orig_name = {"val": ""}

        # ======================================================================
        # 0. QUẢN LÝ PHIÊN BẢN TOOL PC & LINK TẢI CÀI ĐẶT (BÁO CẬP NHẬT CHO USER)
        # ======================================================================
        rel_card = tk.Frame(win, bg="#181e28", highlightthickness=1, highlightbackground="#2b3541", padx=14, pady=8)
        rel_card.pack(fill="x", padx=14, pady=(10, 4))

        tk.Label(
            rel_card,
            text="🚀 Phiên bản mới:",
            font=("Segoe UI", 9, "bold"),
            fg="#eca133",
            bg="#181e28",
        ).pack(side="left")
        rel_ver_var = tk.StringVar(value=str(self.server_release_info.get("latestVersion") or APP_VERSION_NUMBER))
        tk.Entry(
            rel_card,
            textvariable=rel_ver_var,
            font=("Consolas", 9, "bold"),
            bg="#11151b",
            fg="#eca133",
            width=7,
            justify="center",
            relief="flat",
            highlightthickness=1,
            highlightbackground="#2b3541",
        ).pack(side="left", padx=(4, 10), ipady=3)

        tk.Label(
            rel_card,
            text="Link tải (.exe/.zip):",
            font=("Segoe UI", 9, "bold"),
            fg="#8e99a7",
            bg="#181e28",
        ).pack(side="left")
        rel_url_var = tk.StringVar(value=str(self.server_release_info.get("downloadUrl") or "/download-tool"))
        tk.Entry(
            rel_card,
            textvariable=rel_url_var,
            font=("Consolas", 9),
            bg="#11151b",
            fg="#e7ebf0",
            width=30,
            relief="flat",
            highlightthickness=1,
            highlightbackground="#2b3541",
        ).pack(side="left", padx=(4, 10), ipady=3)

        tk.Label(
            rel_card,
            text="Thông báo Update:",
            font=("Segoe UI", 9, "bold"),
            fg="#8e99a7",
            bg="#181e28",
        ).pack(side="left")
        rel_notes_var = tk.StringVar(value=str(self.server_release_info.get("releaseNotes") or ""))
        tk.Entry(
            rel_card,
            textvariable=rel_notes_var,
            font=("Segoe UI", 9),
            bg="#11151b",
            fg="#e7ebf0",
            relief="flat",
            highlightthickness=1,
            highlightbackground="#2b3541",
        ).pack(side="left", padx=(4, 10), ipady=3, fill="x", expand=True)

        rel_force_var = tk.BooleanVar(value=bool(self.server_release_info.get("forceUpdate", False)))
        tk.Checkbutton(
            rel_card,
            text="Bắt buộc Update",
            variable=rel_force_var,
            font=("Segoe UI", 8, "bold"),
            fg="#e7ebf0",
            bg="#181e28",
            selectcolor="#11151b",
            activebackground="#181e28",
            activeforeground="#eca133",
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
                        win.after(0, lambda: status_bar_lbl.config(text=f"⚠️ {d.get('message', 'Lỗi lưu phiên bản')}", fg="#eca133"))
                except Exception as e:
                    win.after(0, lambda: status_bar_lbl.config(text=f"❌ Lỗi: {e}", fg="#f0657b"))

            threading.Thread(target=_t, daemon=True).start()

        tk.Button(
            rel_card,
            text="💾 Lưu Phiên Bản",
            command=_save_release_cfg,
            font=("Segoe UI", 9, "bold"),
            bg="#eca133",
            fg="#11151b",
            relief="flat",
            padx=12,
            pady=3,
            cursor="hand2",
        ).pack(side="right")

        # ======================================================================
        # 0B. DỌN DẸP & XÓA LỊCH SỬ KÈO ĐẤU (1 TUẦN, 1 THÁNG, TÙY CHỈNH, TẤT CẢ)
        # ======================================================================
        hist_clean_card = tk.Frame(win, bg="#181e28", highlightthickness=1, highlightbackground="#2b3541", padx=14, pady=8)
        hist_clean_card.pack(fill="x", padx=14, pady=(2, 4))

        tk.Label(
            hist_clean_card,
            text="🗑️ Xóa lịch sử đấu:",
            font=("Segoe UI", 9, "bold"),
            fg="#f0657b",
            bg="#181e28",
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
            bg="#181e28",
        ).pack(side="left")
        cleanup_param_var = tk.StringVar(value="14")
        tk.Entry(
            hist_clean_card,
            textvariable=cleanup_param_var,
            font=("Consolas", 9, "bold"),
            bg="#11151b",
            fg="#eca133",
            width=12,
            justify="center",
            relief="flat",
            highlightthickness=1,
            highlightbackground="#2b3541",
        ).pack(side="left", padx=(4, 10), ipady=3)

        keep_live_var = tk.BooleanVar(value=True)
        tk.Checkbutton(
            hist_clean_card,
            text="Giữ lại kèo đang LIVE",
            variable=keep_live_var,
            font=("Segoe UI", 8, "bold"),
            fg="#e7ebf0",
            bg="#181e28",
            selectcolor="#11151b",
            activebackground="#181e28",
            activeforeground="#eca133",
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
                        win.after(0, lambda: status_bar_lbl.config(text=f"⚠️ {d.get('message', 'Lỗi xóa lịch sử')}", fg="#eca133"))
                except Exception as e:
                    win.after(0, lambda: status_bar_lbl.config(text=f"❌ Lỗi xóa lịch sử: {e}", fg="#f0657b"))

            threading.Thread(target=_t, daemon=True).start()

        tk.Button(
            hist_clean_card,
            text="🗑️ Xóa Lịch Sử Đấu",
            command=_exec_cleanup_history,
            font=("Segoe UI", 9, "bold"),
            bg="#11151b",
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
        top_card = tk.Frame(win, bg="#181e28", highlightthickness=1, highlightbackground="#2b3541", padx=14, pady=10)
        top_card.pack(fill="x", padx=14, pady=(2, 4))

        hdr_row = tk.Frame(top_card, bg="#181e28")
        hdr_row.pack(fill="x", pady=(0, 6))
        form_mode_lbl = tk.Label(
            hdr_row,
            text="⚙ Quản trị User & Gia hạn VIP (Chọn 1 User dưới bảng để sửa hoặc tạo mới)",
            font=("Segoe UI", 10, "bold"),
            fg="#e7ebf0",
            bg="#181e28",
        )
        form_mode_lbl.pack(side="left")

        # Hàng 1 của Form: Tên Player, Mật khẩu, Hạng VIP, Số dư Sao, Ghi chú
        form_row1 = tk.Frame(top_card, bg="#181e28")
        form_row1.pack(fill="x", pady=2)

        tk.Label(form_row1, text="Tên Player:", font=("Segoe UI", 9, "bold"), fg="#8e99a7", bg="#181e28").pack(side="left")
        u_name_var = tk.StringVar()
        tk.Entry(form_row1, textvariable=u_name_var, font=("Segoe UI", 9, "bold"), bg="#11151b", fg="#e7ebf0", width=13, relief="flat", highlightthickness=1, highlightbackground="#2b3541").pack(side="left", padx=(4, 10), ipady=3)

        tk.Label(form_row1, text="Mật khẩu:", font=("Segoe UI", 9, "bold"), fg="#8e99a7", bg="#181e28").pack(side="left")
        u_pass_var = tk.StringVar(value="123")
        tk.Entry(form_row1, textvariable=u_pass_var, show="*", font=("Consolas", 9, "bold"), bg="#11151b", fg="#e7ebf0", width=10, relief="flat", highlightthickness=1, highlightbackground="#2b3541").pack(side="left", padx=(4, 10), ipady=3)

        tk.Label(form_row1, text="Hạng VIP:", font=("Segoe UI", 9, "bold"), fg="#8e99a7", bg="#181e28").pack(side="left")
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

        tk.Label(form_row1, text="Số dư Sao:", font=("Segoe UI", 9, "bold"), fg="#8e99a7", bg="#181e28").pack(side="left")
        u_stars_var = tk.StringVar(value="0")
        tk.Entry(form_row1, textvariable=u_stars_var, font=("Consolas", 9, "bold"), bg="#11151b", fg="#eca133", width=8, justify="center", relief="flat", highlightthickness=1, highlightbackground="#2b3541").pack(side="left", padx=(4, 10), ipady=3)

        tk.Label(form_row1, text="Ghi chú:", font=("Segoe UI", 9, "bold"), fg="#8e99a7", bg="#181e28").pack(side="left")
        u_note_var = tk.StringVar()
        tk.Entry(form_row1, textvariable=u_note_var, font=("Segoe UI", 9), bg="#11151b", fg="#e7ebf0", width=18, relief="flat", highlightthickness=1, highlightbackground="#2b3541").pack(side="left", padx=(4, 0), ipady=3, fill="x", expand=True)

        # Hàng 2 của Form: Ngày tạo TK, Ngày hết hạn (DD/MM/YYYY), Hoặc +Số ngày hạn SD, Nút Lưu & Nút Làm mới form
        form_row2 = tk.Frame(top_card, bg="#181e28")
        form_row2.pack(fill="x", pady=(6, 2))

        tk.Label(form_row2, text="Ngày tạo TK (DD/MM/YYYY):", font=("Segoe UI", 9, "bold"), fg="#8e99a7", bg="#181e28").pack(side="left")
        u_created_var = tk.StringVar(value=time.strftime("%d/%m/%Y"))
        tk.Entry(form_row2, textvariable=u_created_var, font=("Consolas", 9, "bold"), bg="#11151b", fg="#e7ebf0", width=12, justify="center", relief="flat", highlightthickness=1, highlightbackground="#2b3541").pack(side="left", padx=(4, 12), ipady=3)

        tk.Label(form_row2, text="Ngày hết hạn (DD/MM/YYYY hoặc Vĩnh viễn):", font=("Segoe UI", 9, "bold"), fg="#8e99a7", bg="#181e28").pack(side="left")
        u_expires_var = tk.StringVar(value="")
        tk.Entry(form_row2, textvariable=u_expires_var, font=("Consolas", 9, "bold"), bg="#11151b", fg="#34d399", width=13, justify="center", relief="flat", highlightthickness=1, highlightbackground="#2b3541").pack(side="left", padx=(4, 12), ipady=3)

        tk.Label(form_row2, text="Hoặc đặt số ngày (0=Vĩnh viễn):", font=("Segoe UI", 9, "bold"), fg="#8e99a7", bg="#181e28").pack(side="left")
        u_days_var = tk.StringVar(value="30")
        tk.Entry(form_row2, textvariable=u_days_var, font=("Consolas", 9, "bold"), bg="#11151b", fg="#eca133", width=6, justify="center", relief="flat", highlightthickness=1, highlightbackground="#2b3541").pack(side="left", padx=(4, 10), ipady=3)

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
            form_row2,
            text="🧹 Tạo Mới (Xóa form)",
            command=_clear_form,
            font=("Segoe UI", 9, "bold"),
            bg="#11151b",
            fg="#e7ebf0",
            relief="flat",
            highlightthickness=1,
            highlightbackground="#2b3541",
            padx=10,
            pady=3,
            cursor="hand2",
        ).pack(side="right", padx=(6, 0))

        # ======================================================================
        # 2. THANH SEARCH TÌM KIẾM NHANH USER & BỘ LỌC HẠNG VIP
        # ======================================================================
        search_card = tk.Frame(win, bg="#181e28", highlightthickness=1, highlightbackground="#2b3541", padx=14, pady=8)
        search_card.pack(fill="x", padx=14, pady=4)

        tk.Label(search_card, text="🔍 Tìm kiếm nhanh User:", font=("Segoe UI", 9, "bold"), fg="#e7ebf0", bg="#181e28").pack(side="left")
        search_var = tk.StringVar()
        search_entry = tk.Entry(
            search_card,
            textvariable=search_var,
            font=("Segoe UI", 9),
            bg="#11151b",
            fg="#e7ebf0",
            insertbackground="#eca133",
            width=32,
            relief="flat",
            highlightthickness=1,
            highlightbackground="#2b3541",
        )
        search_entry.pack(side="left", padx=(6, 12), ipady=3)

        tk.Label(search_card, text="Lọc Hạng VIP:", font=("Segoe UI", 9, "bold"), fg="#8e99a7", bg="#181e28").pack(side="left")
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
            fg="#eca133",
            bg="#181e28",
        )
        count_badge_lbl.pack(side="right")

        # ======================================================================
        # 3. BẢNG DANH SÁCH USER (TREEVIEW)
        # ======================================================================
        list_card = tk.Frame(win, bg="#181e28", highlightthickness=1, highlightbackground="#2b3541", padx=14, pady=8)
        list_card.pack(fill="both", expand=True, padx=14, pady=4)

        cols = ("name", "password", "tier", "status", "created", "expires", "stars", "note")
        tree = ttk.Treeview(list_card, columns=cols, show="headings", height=9)
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
        tree.pack(fill="both", expand=True)

        # ======================================================================
        # 4. KHUNG XEM LỊCH SỬ NẠP SAO & LỊCH SỬ GIA HẠN VIP CỦA USER ĐANG CHỌN
        # ======================================================================
        hist_frame = tk.Frame(win, bg="#080c16")
        hist_frame.pack(fill="x", padx=14, pady=4)
        hist_frame.columnconfigure(0, weight=1)
        hist_frame.columnconfigure(1, weight=1)

        star_hist_card = tk.Frame(hist_frame, bg="#181e28", highlightthickness=1, highlightbackground="#2b3541", padx=10, pady=6)
        star_hist_card.grid(row=0, column=0, sticky="nsew", padx=(0, 5))
        star_hist_title = tk.Label(star_hist_card, text="🌟 Lịch sử Nạp Sao & Giao dịch Sao (Chọn User để xem)", font=("Segoe UI", 9, "bold"), fg="#eca133", bg="#181e28")
        star_hist_title.pack(anchor="w", pady=(0, 4))
        star_hist_box = tk.Text(star_hist_card, bg="#11151b", fg="#e7ebf0", font=("Consolas", 8), height=5, relief="flat", padx=6, pady=4, state="disabled", highlightthickness=1, highlightbackground="#2b3541")
        star_hist_box.pack(fill="x")

        vip_hist_card = tk.Frame(hist_frame, bg="#181e28", highlightthickness=1, highlightbackground="#2b3541", padx=10, pady=6)
        vip_hist_card.grid(row=0, column=1, sticky="nsew", padx=(5, 0))
        vip_hist_title = tk.Label(vip_hist_card, text="👑 Lịch sử Gia hạn VIP & Thay đổi gói (Chọn User để xem)", font=("Segoe UI", 9, "bold"), fg="#e7ebf0", bg="#181e28")
        vip_hist_title.pack(anchor="w", pady=(0, 4))
        vip_hist_box = tk.Text(vip_hist_card, bg="#11151b", fg="#e7ebf0", font=("Consolas", 8), height=5, relief="flat", padx=6, pady=4, state="disabled", highlightthickness=1, highlightbackground="#2b3541")
        vip_hist_box.pack(fill="x")

        status_bar_lbl = tk.Label(win, text="Đang tải danh sách tài khoản...", font=("Segoe UI", 9, "bold"), fg="#eca133", bg="#080c16")
        status_bar_lbl.pack(anchor="w", padx=16, pady=(2, 2))

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
                tree.insert(
                    "",
                    "end",
                    iid=pname,
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
                    fg="#eca133",
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
                    win.after(0, lambda: status_bar_lbl.config(text=f"❌ Lỗi tải danh sách: {e}", fg="#f0657b"))
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
                        win.after(0, lambda: status_bar_lbl.config(text=f"⚠️ {d.get('message', 'Lỗi lưu User')}", fg="#eca133"))
                except Exception as e:
                    win.after(0, lambda: status_bar_lbl.config(text=f"❌ Lỗi: {e}", fg="#f0657b"))
            threading.Thread(target=_t, daemon=True).start()

        tk.Button(
            form_row2,
            text="💾 Lưu / Cập Nhật User",
            command=_save_user,
            font=("Segoe UI", 9, "bold"),
            bg="#eca133",
            fg="#11151b",
            relief="flat",
            padx=14,
            pady=3,
            cursor="hand2",
        ).pack(side="right")

        # ======================================================================
        # 5. THANH NÚT THAO TÁC NHANH CHO USER ĐANG CHỌN (NẠP SAO, RESET MK, GIA HẠN, KHÓA, XÓA)
        # ======================================================================
        action_bar = tk.Frame(win, bg="#080c16")
        action_bar.pack(fill="x", padx=14, pady=(2, 10))

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
                        win.after(0, lambda: status_bar_lbl.config(text=f"⚠️ {d.get('message', 'Thất bại')}", fg="#eca133"))
                except Exception as e:
                    win.after(0, lambda: status_bar_lbl.config(text=f"❌ Lỗi: {e}", fg="#f0657b"))
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

        tk.Button(action_bar, text="💰 Nạp Sao (+⭐)", command=_topup_stars_dialog, font=("Segoe UI", 9, "bold"), bg="#eca133", fg="#11151b", relief="flat", padx=10, pady=4, cursor="hand2").pack(side="left", padx=(0, 6))
        tk.Button(action_bar, text="🔑 Reset Mật Khẩu", command=_reset_password_dialog, font=("Segoe UI", 9, "bold"), bg="#11151b", fg="#e7ebf0", relief="flat", highlightthickness=1, highlightbackground="#2b3541", padx=10, pady=4, cursor="hand2").pack(side="left", padx=(0, 6))
        tk.Button(action_bar, text="⏳ Gia hạn +30 Ngày", command=lambda: _quick_action("adminExtendPlayer", {"addDays": 30}), font=("Segoe UI", 9, "bold"), bg="#11151b", fg="#e7ebf0", relief="flat", highlightthickness=1, highlightbackground="#2b3541", padx=10, pady=4, cursor="hand2").pack(side="left", padx=(0, 6))
        tk.Button(action_bar, text="⏳ Gia hạn +1 Năm", command=lambda: _quick_action("adminExtendPlayer", {"addDays": 365}), font=("Segoe UI", 9, "bold"), bg="#11151b", fg="#e7ebf0", relief="flat", highlightthickness=1, highlightbackground="#2b3541", padx=10, pady=4, cursor="hand2").pack(side="left", padx=(0, 6))
        tk.Button(action_bar, text="📅 Chỉnh Hạn (+N Ngày)", command=_custom_extend_days_dialog, font=("Segoe UI", 9, "bold"), bg="#11151b", fg="#e7ebf0", relief="flat", highlightthickness=1, highlightbackground="#2b3541", padx=10, pady=4, cursor="hand2").pack(side="left", padx=(0, 6))
        tk.Button(action_bar, text="♾️ Cấp Vĩnh Viễn", command=lambda: _quick_action("adminExtendPlayer", {"addDays": 0, "lifetime": True}), font=("Segoe UI", 9, "bold"), bg="#11151b", fg="#34d399", relief="flat", highlightthickness=1, highlightbackground="#2b3541", padx=10, pady=4, cursor="hand2").pack(side="left", padx=(0, 6))
        tk.Button(action_bar, text="🔒 Khóa / 🔓 Mở", command=lambda: _quick_action("adminToggleActive", {}), font=("Segoe UI", 9, "bold"), bg="#11151b", fg="#eca133", relief="flat", highlightthickness=1, highlightbackground="#2b3541", padx=10, pady=4, cursor="hand2").pack(side="left", padx=(0, 6))
        tk.Button(action_bar, text="🗑 Xóa User", command=lambda: _quick_action("adminDeletePlayer", {}), font=("Segoe UI", 9, "bold"), bg="#11151b", fg="#f0657b", relief="flat", highlightthickness=1, highlightbackground="#c94a61", padx=10, pady=4, cursor="hand2").pack(side="left", padx=(0, 6))
        tk.Button(action_bar, text="↻ Làm mới", command=_refresh_users, font=("Segoe UI", 9, "bold"), bg="#11151b", fg="#e7ebf0", relief="flat", highlightthickness=1, highlightbackground="#2b3541", padx=10, pady=4, cursor="hand2").pack(side="right")

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

            if my_live_match:
                self.current_match = my_live_match
                self._update_battle_arena_ui(my_live_match)
            elif time.time() - getattr(self, "_last_diplomacy_push_ts", 0.0) > 10.0:
                self.current_match = None
                self._reset_battle_arena_ui()
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
                    text=f"Sảnh Chat Live · Máy {lobby_target}",
                    fg="#eca133" if lobby_target.lower() != my_name.lower() else "#e7ebf0",
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
                        fg="#8e99a7",
                        bg="#181e28",
                    ).pack(side="left", padx=(0, 6))
                    for lf in live_friends_list[:5]:
                        f_streamer = lf.get("name", "")
                        f_mode = lf.get("liveMatchMode") or "LIVE"
                        is_current = f_streamer.lower() == lobby_target.lower()
                        btn = self.tk.Button(
                            self.friends_live_btn_frame,
                            text=f"🔴 {f_streamer} ({f_mode})",
                            command=lambda s=f_streamer: self.enter_friend_live_lobby(s),
                            font=("Segoe UI", 8, "bold"),
                            bg="#eca133" if is_current else "#11151b",
                            fg="#11151b" if is_current else "#e7ebf0",
                            relief="flat",
                            highlightthickness=0 if is_current else 1,
                            highlightbackground="#2b3541",
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
                        elif c.get("source") == "FACEBOOK" or c.get("senderTier") == "FACEBOOK":
                            self.chat_box.insert("end", f"🔵 [FB] {sender}: ", "FB_SENDER")
                            self.chat_box.insert("end", f"{msg}\n", "MSG")
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

    def _reset_battle_arena_ui(self, summary_text: str = "Ấn F2 (Diplomacy) trong game để bắt đầu"):
        def _render():
            try:
                t_score = self.target_score_var.get() or 100
                self.match_mode_lbl.config(text=f"Chạm {t_score} • Chờ kèo Live")
                self.score_lbl.config(text="0  -  0")
                self.c_mode_summary_lbl.config(text=summary_text)
                self.red_roster_lbl.config(text="Chưa có đội hình Team Đỏ\n(Bấm F2 Diplomacy trong game để quét)")
                self.blue_roster_lbl.config(text="Chưa có đội hình Team Xanh\n(Bấm F2 Diplomacy trong game để quét)")
                self.red_count_lbl.config(text="0 người chơi")
                self.blue_count_lbl.config(text="0 người chơi")
            except Exception:
                pass

        self.root.after(0, _render)

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
        win.configure(bg="#080c16")

        hdr = tk.Frame(win, bg="#181e28", highlightthickness=1, highlightbackground="#2b3541", padx=18, pady=12)
        hdr.pack(fill="x", padx=14, pady=(12, 6))

        tk.Label(
            hdr,
            text=f"🔵 Cầu Nối Đẩy Comment Luồng Live Trong Group Facebook Lên OBS (Máy {streamer})",
            font=("Segoe UI", 12, "bold"),
            fg="#60a5fa",
            bg="#181e28",
        ).pack(anchor="w")

        tk.Label(
            hdr,
            text="Giải pháp chuyên dụng cho Streamer phát Live trong Group Facebook (kể cả Nhóm Kín & Nhóm Công Khai) — Không cần duyệt App Meta, không sợ khóa nick!",
            font=("Segoe UI", 9, "bold"),
            fg="#e7ebf0",
            bg="#181e28",
            wraplength=700,
            justify="left",
        ).pack(anchor="w", pady=(4, 0))

        steps_card = tk.Frame(win, bg="#181e28", highlightthickness=1, highlightbackground="#2b3541", padx=18, pady=12)
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
            bg="#181e28",
            justify="left",
            anchor="w",
        ).pack(fill="x")

        btn_row = tk.Frame(win, bg="#080c16")
        btn_row.pack(fill="x", padx=14, pady=6)

        status_feedback_lbl = tk.Label(
            win,
            text="💡 Mẹo: Bạn có thể bấm '🧪 Gửi thử 1 Comment FB lên OBS' ngay bây giờ để kiểm tra chữ hiện trên OBS!",
            font=("Segoe UI", 9, "bold"),
            fg="#eca133",
            bg="#080c16",
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
            bg="#eca133",
            fg="#11151b",
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
            bg="#181e28",
            fg="#e7ebf0",
            relief="flat",
            highlightthickness=1,
            highlightbackground="#2b3541",
            padx=12,
            pady=7,
            cursor="hand2",
        )
        btn_copy_obs_c.pack(side="right")

        status_feedback_lbl.pack(fill="x", padx=14, pady=(2, 4))

        code_card = tk.Frame(win, bg="#181e28", highlightthickness=1, highlightbackground="#2b3541", padx=12, pady=8)
        code_card.pack(fill="both", expand=True, padx=14, pady=(2, 12))
        tk.Label(
            code_card,
            text="🔒 Mã cầu nối tự động (Mật khẩu đã được ẨN & MÃ HÓA BẢO MẬT hoàn toàn — Không lộ mật khẩu khi Live):",
            font=("Segoe UI", 8, "bold"),
            fg="#34d399",
            bg="#181e28",
        ).pack(anchor="w", pady=(0, 4))

        code_txt = tk.Text(
            code_card,
            bg="#11151b",
            fg="#60a5fa",
            font=("Consolas", 8),
            relief="flat",
            padx=8,
            pady=6,
            highlightthickness=1,
            highlightbackground="#2b3541",
        )
        code_txt.pack(fill="both", expand=True)
        code_txt.insert("1.0", self._generate_fb_group_bridge_js(for_display=True))
        code_txt.configure(state="disabled")

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

    def manual_scan_screen(self):
        def _task():
            try:
                frames = self._grab_all_monitors_bgr()
                for img_bgr in frames:
                    res = self.scanner.parse_diplomacy_from_image(
                        img_bgr,
                        streamer_name=self.player_name_var.get().strip(),
                        known_players=self.known_players,
                        force=True,
                    )
                    if res and res.get("status") == "ok":
                        self._send_parsed_diplomacy_to_server(res, allow_same_civ=False)
                        return
                self.log("⚠️ Không tìm thấy bảng DIPLOMACY (F2) trên màn hình hiện tại!", "WARN")
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
                self._send_parsed_diplomacy_to_server(res, allow_same_civ=False)
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
                    self.scanner.last_dialog_signature = None
                    self._reset_battle_arena_ui("Kèo đấu đã kết thúc • Ấn F2 trong game để bắt đầu kèo mới")
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
            pw = self._get_effective_player_password() or self.settings.get("player_password", "").strip()
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
                    "isAdmin": self.is_admin,
                    "adminPassword": self.admin_password,
                },
                timeout=3.5,
            )
        except Exception:
            pass

    def on_closing(self):
        """Sự kiện đóng cửa sổ Tool: lưu cấu hình và thoát (giữ nguyên kèo LIVE trên Web/OBS cho đến khi bấm Kết thúc kèo)."""
        self.running = False
        try:
            self.save_current_config()
        except Exception:
            pass
        try:
            self.root.destroy()
        except Exception:
            sys.exit(0)

    def _monitor_diplomacy_events(self):
        """
        Bắt sự kiện khi người chơi thực sự click vào nút Diplomacy trên thanh HUD phía trên trong game
        hoặc bấm phím tắt F2 / Alt+D. Chỉ khi có sự kiện này mới kích hoạt cửa sổ quét bảng quân.
        """
        if os.name != "nt":
            return
        try:
            import ctypes
            from ctypes import wintypes

            user32 = ctypes.windll.user32
            VK_LBUTTON = 0x01
            VK_F2 = 0x71
            VK_MENU = 0x12
            VK_D = 0x44

            prev_lbtn = False
            prev_f2 = False
            prev_alt_d = False

            while self.running:
                try:
                    if not self.is_logged_in or not self.auto_scan_var.get():
                        time.sleep(0.1)
                        continue

                    f2_down = (user32.GetAsyncKeyState(VK_F2) & 0x8000) != 0
                    alt_down = (user32.GetAsyncKeyState(VK_MENU) & 0x8000) != 0
                    d_down = (user32.GetAsyncKeyState(VK_D) & 0x8000) != 0
                    alt_d_down = alt_down and d_down
                    lbtn_down = (user32.GetAsyncKeyState(VK_LBUTTON) & 0x8000) != 0

                    triggered = False
                    reason = ""

                    if f2_down and not prev_f2:
                        triggered = True
                        reason = "F2"
                    elif alt_d_down and not prev_alt_d:
                        triggered = True
                        reason = "Alt+D"
                    elif lbtn_down and not prev_lbtn:
                        pt = wintypes.POINT()
                        if user32.GetCursorPos(ctypes.byref(pt)):
                            hwnd = user32.GetForegroundWindow()
                            rect = wintypes.RECT()
                            if hwnd and user32.GetWindowRect(hwnd, ctypes.byref(rect)):
                                w = max(1, rect.right - rect.left)
                                h = max(1, rect.bottom - rect.top)
                                rel_x = (pt.x - rect.left) / float(w)
                                rel_y = (pt.y - rect.top) / float(h)
                                # Thanh nút Diplomacy trong AOE nằm ở góc trên bên phải (rel_y <= 0.18, rel_x >= 0.42)
                                if 0.0 <= rel_y <= 0.18 and 0.42 <= rel_x <= 0.99:
                                    triggered = True
                                    reason = "Click Diplomacy"
                            else:
                                scr_w = max(1, user32.GetSystemMetrics(0))
                                scr_h = max(1, user32.GetSystemMetrics(1))
                                if 0.0 <= (pt.y / float(scr_h)) <= 0.18 and (pt.x / float(scr_w)) >= 0.42:
                                    triggered = True
                                    reason = "Click Diplomacy"

                    prev_f2 = f2_down
                    prev_alt_d = alt_d_down
                    prev_lbtn = lbtn_down

                    if triggered:
                        self._diplomacy_trigger_reason = reason
                        # Đợi 0.18s để hộp thoại Diplomacy kịp hiển thị sắc nét rồi mở cửa sổ quét 2.4 giây
                        time.sleep(0.18)
                        self._diplomacy_scan_window_until = time.time() + 2.4
                except Exception:
                    pass
                time.sleep(0.025)
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
                    force_scan = self.current_match is None
                    for img_bgr in frames:
                        res = self.scanner.parse_diplomacy_from_image(
                            img_bgr,
                            streamer_name=self.player_name_var.get().strip(),
                            known_players=self.known_players,
                            force=force_scan,
                        )
                        if res and res.get("status") == "ok":
                            self._diplomacy_scan_window_until = 0.0
                            self._send_parsed_diplomacy_to_server(res, allow_same_civ=False)
                            break
                        elif res and res.get("status") == "unchanged":
                            self._diplomacy_scan_window_until = 0.0
                            break

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
            time.sleep(0.35)


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
