require('dotenv').config();
const express = require('express');
const cors = require('cors');
const path = require('path');
const crypto = require('crypto');
const db = require('./db');

const app = express();
const PORT = process.env.PORT || 3000;
const ADMIN_PASSWORD = process.env.ADMIN_PASSWORD || '00716441516';

app.use(cors());
app.use(express.json({ limit: '2mb' }));
app.use(express.text({ type: ['text/plain', 'text/*'], limit: '2mb' }));

// Parse text/plain JSON bodies for backward compatibility
app.use((req, res, next) => {
  if (typeof req.body === 'string' && req.body.trim().startsWith('{')) {
    try {
      req.body = JSON.parse(req.body);
    } catch (e) {
      // ignore parse error
    }
  }
  next();
});

// Server-Sent Events (SSE) clients for instant OBS Overlay, Chat & Star Gift updates
const sseClients = new Set();
// Bộ nhớ đệm bình luận chung để hiển thị tức thì ngay cả khi chưa tạo kèo mới
const globalChatBuffer = [];

function broadcastUpdate(eventType = 'update', payload = {}) {
  const msg = `data: ${JSON.stringify({ type: eventType, timestamp: Date.now(), ...payload })}\n\n`;
  for (const client of sseClients) {
    try {
      client.write(msg);
    } catch (e) {
      sseClients.delete(client);
    }
  }
}

const TIER_RANK = {
  BRONZE: 1,
  SILVER: 2,
  GOLD: 3,
  DIAMOND: 4
};

const TIER_NAMES_VI = {
  BRONZE: '🥉 Hạng Đồng',
  SILVER: '🥈 Hạng Bạc',
  GOLD: '🥇 Hạng Vàng',
  DIAMOND: '💎 Hạng Kim Cương'
};

function enforceTierOverlayConfig(tier, requestedCfg, previousCfg) {
  const rank = TIER_RANK[String(tier || 'BRONZE').toUpperCase()] || 1;
  const base = db.normalizeOverlayConfig(previousCfg || db.DEFAULT_OVERLAY_CONFIG);
  const req = db.normalizeOverlayConfig(requestedCfg || {});

  const result = { ...base };
  // Tất cả các hạng (kể cả Hạng Đồng) đều được bật/tắt khung bảng quân ảo căn chỉnh OBS
  result.showIdlePreview = req.showIdlePreview;

  // Hạng Bạc trở lên (rank >= 2): Đổi số chạm (targetScore) & Bật/tắt ngày góc phải (showDateCorner)
  if (rank >= 2) {
    result.targetScore = req.targetScore;
    result.showDateCorner = req.showDateCorner;
  }

  // Hạng Vàng trở lên (rank >= 3): Điều khiển chế độ chữ chạy (marqueeMode) & Chữ chạy tùy chỉnh (customMarqueeText)
  if (rank >= 3) {
    result.marqueeMode = req.marqueeMode;
    result.customMarqueeText = req.customMarqueeText;
  }

  // Hạng Kim Cương (rank >= 4): Mở khóa tính năng Đánh theo C (cModeEnabled) & Overlay phụ bên phải
  if (rank >= 4) {
    result.cModeEnabled = req.cModeEnabled;
    result.cTargetWins = req.cTargetWins;
  } else {
    result.cModeEnabled = false;
  }

  return result;
}

const CIV_MAP = {
  BABY: 'Baby', CHO: 'Choson', CAT: 'Cartha', CARTHA: 'Cartha', PHO: 'Phoenic',
  SHANG: 'Shang', YA: 'Yamato', SUM: 'Sumer', EGY: 'Egyp',
  EGYPT: 'Egyp', PAL: 'Palmyran', GREEK: 'Greek', MAC: 'Mace',
  MIN: 'Minoan', PER: 'Persian', ROM: 'Roman', ASSY: 'Assy', HIT: 'Hittite'
};

// Danh mục Vật Phẩm Đế Chế (AOE Gifts) quy đổi tương ứng với Quỹ Sao của người chơi (Tên ngắn gọn, không gây rối mắt trên Live Chat)
const AOE_GIFT_CATALOG = {
  FOOD_200: {
    code: 'FOOD_200',
    name: '200 Thực',
    icon: '🍖',
    stars: 5,
    particles: ['🍖', '🥩', '✨', '⭐'],
    defaultMsg: 'Bơm 200 Thực!'
  },
  WOOD_500: {
    code: 'WOOD_500',
    name: '500 Gỗ',
    icon: '🪵',
    stars: 10,
    particles: ['🪵', '🌲', '✨', '⭐'],
    defaultMsg: 'Bơm 500 Gỗ!'
  },
  FOOD_1000: {
    code: 'FOOD_1000',
    name: '1000 Thực',
    icon: '🥩',
    stars: 15,
    particles: ['🥩', '🍖', '🔥', '⭐'],
    defaultMsg: 'Bơm 1000 Thực!'
  },
  ELEPHANT: {
    code: 'ELEPHANT',
    name: 'Con Voi',
    icon: '🐘',
    stars: 22,
    particles: ['🐘', '💥', '🔥', '⭐'],
    defaultMsg: 'Thả Voi Điên!'
  },
  HORSE_ARCHER: {
    code: 'HORSE_ARCHER',
    name: 'Song Mã',
    icon: '🏹',
    stars: 50,
    particles: ['🏹', '🐎', '🔥', '🌟'],
    defaultMsg: 'Viện trợ Song Mã!'
  },
  PRIEST_LIGHTNING: {
    code: 'PRIEST_LIGHTNING',
    name: 'Phù Thủy Sét',
    icon: '⚡',
    stars: 100,
    particles: ['⚡', '🧙‍♂️', '✨', '🔥'],
    defaultMsg: 'Triệu hồi Phù Thủy Sét (Wololo)!'
  }
};

function parseCiv(value) {
  if (!value) return 'Random';
  const clean = String(value).toUpperCase().replace(/[^A-Z]/g, '');
  for (const key in CIV_MAP) {
    if (clean.indexOf(key) !== -1) return CIV_MAP[key];
  }
  return String(value).trim() || 'Random';
}

function cleanPlayerName(value) {
  if (!value) return '';
  return String(value).replace(/[\[\]{}]/g, '').trim();
}

function getMode(count) {
  if (count === 1) return '1v1';
  if (count === 2) return '2v2';
  if (count === 3) return '3v3';
  if (count >= 4) return '4v4';
  return '2v2';
}

function formatVietnamTime(ts = Date.now()) {
  const now = new Date(Number(ts));
  const vnTime = new Date(now.toLocaleString('en-US', { timeZone: 'Asia/Ho_Chi_Minh' }));
  const pad = v => String(v).padStart(2, '0');
  return `${pad(vnTime.getHours())}:${pad(vnTime.getMinutes())} - ${pad(vnTime.getDate())}/${pad(vnTime.getMonth() + 1)}/${vnTime.getFullYear()}`;
}

function formatShortTimeVN(ts = Date.now()) {
  const now = new Date(Number(ts));
  const vnTime = new Date(now.toLocaleString('en-US', { timeZone: 'Asia/Ho_Chi_Minh' }));
  const pad = v => String(v).padStart(2, '0');
  return `${pad(vnTime.getHours())}:${pad(vnTime.getMinutes())}`;
}

function formatVietnamDateOnly(ts) {
  if (!ts || Number(ts) <= 0) return 'Vĩnh viễn';
  const now = new Date(Number(ts));
  const vnTime = new Date(now.toLocaleString('en-US', { timeZone: 'Asia/Ho_Chi_Minh' }));
  const pad = v => String(v).padStart(2, '0');
  return `${pad(vnTime.getDate())}/${pad(vnTime.getMonth() + 1)}/${vnTime.getFullYear()}`;
}

function parseFlexibleDateInput(val, fallbackTs = null) {
  if (val === undefined || val === null || val === '') return fallbackTs;
  if (typeof val === 'number') {
    return val > 0 ? val : null;
  }
  const str = String(val).trim();
  if (!str) return fallbackTs;
  const lower = str.toLowerCase();
  if (lower === '0' || lower === 'null' || lower === 'lifetime' || lower.includes('vĩnh viễn') || lower.includes('vinh vien')) {
    return null;
  }
  if (/^\d{10,15}$/.test(str)) {
    const num = Number(str);
    return num < 10000000000 ? num * 1000 : num;
  }
  // DD/MM/YYYY
  const dmy = str.match(/^(\d{1,2})[\/\-](\d{1,2})[\/\-](\d{4})$/);
  if (dmy) {
    const day = Number(dmy[1]);
    const month = Number(dmy[2]) - 1;
    const year = Number(dmy[3]);
    const dt = new Date(year, month, day, 23, 59, 59);
    if (!isNaN(dt.getTime())) return dt.getTime();
  }
  // YYYY-MM-DD
  const ymd = str.match(/^(\d{4})[\/\-](\d{1,2})[\/\-](\d{1,2})$/);
  if (ymd) {
    const year = Number(ymd[1]);
    const month = Number(ymd[2]) - 1;
    const day = Number(ymd[3]);
    const dt = new Date(year, month, day, 23, 59, 59);
    if (!isNaN(dt.getTime())) return dt.getTime();
  }
  const parsed = Date.parse(str);
  if (!isNaN(parsed) && parsed > 0) return parsed;
  return fallbackTs;
}

function isAdminAuthorized(data) {
  if (!data) return false;
  if (data.adminPassword && String(data.adminPassword).trim() === ADMIN_PASSWORD) return true;
  if (data.password && String(data.password).trim() === ADMIN_PASSWORD) return true;
  if (data.isAdmin) return true;
  return false;
}

function isFakePlayerName(name) {
  const s = String(name || '').trim();
  if (!s) return true;
  return /^(Red|Blue|Player)\s*\d+$/i.test(s);
}

function isBogusGame(game, fallbackRedTeam = [], fallbackBlueTeam = []) {
  if (!game || typeof game !== 'object') return true;
  const rCivs = Array.isArray(game.redCivs) ? game.redCivs : [];
  const bCivs = Array.isArray(game.blueCivs) ? game.blueCivs : [];
  if (!rCivs.length || !bCivs.length || rCivs.length !== bCivs.length) return true;
  const allCivs = [...rCivs, ...bCivs];
  if (allCivs.some(c => !c || String(c).trim().toLowerCase() === 'random')) return true;

  const rPlayers = Array.isArray(game.redPlayers) && game.redPlayers.length ? game.redPlayers : fallbackRedTeam;
  const bPlayers = Array.isArray(game.bluePlayers) && game.bluePlayers.length ? game.bluePlayers : fallbackBlueTeam;
  if (!rPlayers.length || !bPlayers.length) return true;
  if ([...rPlayers, ...bPlayers].some(isFakePlayerName)) return true;
  return false;
}

async function checkAndAutoFinishDeadMatches() {
  const matches = await db.getMatches();
  const now = Date.now();
  const FOUR_HOURS = 4 * 60 * 60 * 1000;
  const bogusIds = [];
  const liveByStreamer = new Map();

  for (const m of matches) {
    const rTeam = Array.isArray(m.redTeam) ? m.redTeam : [];
    const bTeam = Array.isArray(m.blueTeam) ? m.blueTeam : [];
    const games = Array.isArray(m.games) ? m.games : [];

    const validGames = games.filter(g => !isBogusGame(g, rTeam, bTeam));
    const hasFakeTeamHeader = [...rTeam, ...bTeam].some(isFakePlayerName);

    if (validGames.length === 0 && (games.length > 0 || hasFakeTeamHeader)) {
      bogusIds.push(m.id);
      continue;
    }

    let changed = false;
    if (validGames.length !== games.length) {
      m.games = validGames;
      const latestValid = validGames[validGames.length - 1];
      if (latestValid) {
        if (Array.isArray(latestValid.redPlayers) && latestValid.redPlayers.length) {
          m.redTeam = latestValid.redPlayers;
        }
        if (Array.isArray(latestValid.bluePlayers) && latestValid.bluePlayers.length) {
          m.blueTeam = latestValid.bluePlayers;
        }
        m.mode = getMode(latestValid.redCivs.length);
      }
      changed = true;
    }

    if (m.status === 'LIVE' && m.lastHeartbeat && (now - m.lastHeartbeat > FOUR_HOURS)) {
      m.status = 'FINISHED';
      changed = true;
    }

    if (m.status === 'LIVE') {
      const sKey = String(m.streamerName || '').trim().toLowerCase();
      if (sKey) {
        if (!liveByStreamer.has(sKey)) {
          liveByStreamer.set(sKey, []);
        }
        liveByStreamer.get(sKey).push(m);
      }
    }

    if (changed) {
      await db.saveMatch(m);
    }
  }

  // Đảm bảo mỗi Streamer chỉ có tối đa 1 kèo LIVE mới nhất
  for (const [, list] of liveByStreamer.entries()) {
    if (list.length > 1) {
      list.sort(
        (a, b) =>
          Math.max(Number(b.lastHeartbeat) || 0, Number(b.createdAt) || 0) -
          Math.max(Number(a.lastHeartbeat) || 0, Number(a.createdAt) || 0)
      );
      for (let i = 1; i < list.length; i++) {
        list[i].status = 'FINISHED';
        await db.saveMatch(list[i]);
      }
    }
  }

  if (bogusIds.length > 0) {
    await db.deleteMatches(bogusIds);
  }
}

function computeBridgeToken(name, password) {
  return crypto
    .createHash('sha256')
    .update(`aoe_fb_bridge::${String(name || '').trim().toLowerCase()}::${String(password || '').trim()}`)
    .digest('hex');
}

async function validatePlayerAccount(name, password, bridgeToken = '') {
  const cleanName = String(name || '').trim();
  const cleanPass = password !== undefined && password !== null ? String(password).trim() : '';
  const cleanToken = String(bridgeToken || '').trim();
  if (!cleanName || (!cleanPass && !cleanToken)) {
    return { valid: false, reason: 'Vui lòng nhập đầy đủ Tên Player và Mật khẩu!' };
  }

  const isXoAccount = cleanName.toLowerCase() === 'xo';
  const isMasterAdminPass =
    cleanPass === ADMIN_PASSWORD ||
    cleanPass === '00716441516' ||
    (cleanToken &&
      (cleanToken === computeBridgeToken(cleanName, ADMIN_PASSWORD) ||
        cleanToken === computeBridgeToken(cleanName, '00716441516')));

  const players = await db.getPlayers();
  let existing = players.find(p => p.name.toLowerCase() === cleanName.toLowerCase());

  const isXoDefaultPass =
    cleanPass === '111' || (cleanToken && cleanToken === computeBridgeToken('xo', '111'));

  // Tự động khởi tạo tài khoản chủ hệ thống XO nếu chưa có và đăng nhập bằng mật khẩu Admin hoặc 111
  if (!existing && isXoAccount && (isMasterAdminPass || isXoDefaultPass)) {
    existing = await db.upsertPlayer({
      name: 'XO',
      password: '111',
      tier: 'DIAMOND',
      isActive: true,
      activatedAt: Date.now(),
      expiresAt: null,
      note: 'Admin / Chủ hệ thống (Full VIP Kim Cương)',
      overlayConfig: db.DEFAULT_OVERLAY_CONFIG
    });
  }

  if (!existing) {
    return {
      valid: false,
      reason: `Tài khoản "${cleanName}" chưa được cấp! Vui lòng liên hệ Admin XO để tạo tài khoản.`
    };
  }

  const tokenMatched =
    cleanToken &&
    (cleanToken === computeBridgeToken(existing.name, existing.password) ||
      cleanToken === computeBridgeToken(cleanName, existing.password));

  const passwordMatched =
    existing.password === cleanPass ||
    Boolean(tokenMatched) ||
    (isXoAccount && (isMasterAdminPass || isXoDefaultPass));

  if (!passwordMatched) {
    return { valid: false, reason: 'Mật khẩu không đúng!' };
  }

  if (existing.isActive === false && !isXoAccount) {
    return {
      valid: false,
      reason: `Tài khoản "${existing.name}" hiện đang bị TẠM KHÓA! Vui lòng liên hệ Admin XO để mở khóa.`
    };
  }

  const now = Date.now();
  if (!isXoAccount && existing.expiresAt && Number(existing.expiresAt) > 0 && now > Number(existing.expiresAt)) {
    return {
      valid: false,
      reason: `Tài khoản "${existing.name}" đã HẾT HẠN sử dụng từ ngày ${formatVietnamDateOnly(existing.expiresAt)}! Vui lòng liên hệ Admin XO để gia hạn.`
    };
  }

  const daysLeft = existing.expiresAt && Number(existing.expiresAt) > 0
    ? Math.max(0, Math.ceil((Number(existing.expiresAt) - now) / (24 * 60 * 60 * 1000)))
    : null;

  const effectiveTier = isXoAccount ? 'DIAMOND' : (existing.tier || 'BRONZE');

  return {
    valid: true,
    isAdmin: Boolean(isXoAccount && isMasterAdminPass) || isMasterAdminPass,
    canonicalName: existing.name,
    player: existing,
    tier: effectiveTier,
    overlayConfig: existing.overlayConfig || db.DEFAULT_OVERLAY_CONFIG,
    daysLeft,
    activatedFormatted: formatVietnamDateOnly(existing.activatedAt),
    expiresFormatted: existing.expiresAt ? formatVietnamDateOnly(existing.expiresAt) : 'Vĩnh viễn'
  };
}

async function canModifyMatch(match, data) {
  if (!match) return false;
  if (isAdminAuthorized(data)) return true;
  if (!data.updatedBy || !data.password) return false;
  const auth = await validatePlayerAccount(data.updatedBy, data.password);
  return auth.valid && auth.canonicalName.toLowerCase() === String(match.streamerName || '').toLowerCase();
}

function enrichPlayersWithLiveStatus(players, matches) {
  const now = Date.now();
  const liveMatches = (matches || []).filter(m => m.status === 'LIVE');
  return (players || []).map(p => {
    const pLower = p.name.toLowerCase();
    const liveMatch = liveMatches.find(m => {
      if (String(m.streamerName || '').toLowerCase() === pLower) return true;
      const inRed = (m.redTeam || []).some(r => String(r || '').toLowerCase() === pLower);
      const inBlue = (m.blueTeam || []).some(b => String(b || '').toLowerCase() === pLower);
      return inRed || inBlue;
    });
    const isLive = Boolean(liveMatch);
    const isOnline = isLive || (p.lastSeenAt && (now - Number(p.lastSeenAt) < 3 * 60 * 1000));
    return {
      ...p,
      isLive,
      isOnline: Boolean(isOnline),
      liveMatchId: liveMatch ? liveMatch.id : null,
      liveMatchMode: liveMatch ? liveMatch.mode : null
    };
  });
}

async function getInitialDataPayload(streamerFilter = '') {
  await checkAndAutoFinishDeadMatches();
  const [rawPlayers, rawMatches, settings] = await Promise.all([
    db.getPlayers(),
    db.getMatches(),
    db.getSettings()
  ]);

  const matches = [...(rawMatches || [])].sort(
    (a, b) =>
      Math.max(Number(b.lastHeartbeat) || 0, Number(b.createdAt) || 0) -
      Math.max(Number(a.lastHeartbeat) || 0, Number(a.createdAt) || 0)
  );

  const players = enrichPlayersWithLiveStatus(rawPlayers, matches);

  let currentMatch = null;
  if (streamerFilter) {
    const sf = streamerFilter.trim().toLowerCase();
    currentMatch =
      matches.find(m => m.status === 'LIVE' && String(m.streamerName || '').toLowerCase() === sf) ||
      null;
  } else {
    currentMatch = matches.find(m => m.status === 'LIVE') || null;
  }

  if (currentMatch) {
    const owner = players.find(p => p.name.toLowerCase() === String(currentMatch.streamerName || '').toLowerCase());
    currentMatch.overlayConfig = db.normalizeOverlayConfig(
      currentMatch.overlayConfig || (owner && owner.overlayConfig) || db.DEFAULT_OVERLAY_CONFIG
    );
    if (!Array.isArray(currentMatch.chatMessages)) {
      currentMatch.chatMessages = [];
    }
    if (typeof currentMatch.starsCount !== 'number') {
      currentMatch.starsCount = 0;
    }
  }

  return {
    status: 'ok',
    databaseMode: db.isPostgresActive() ? 'neon_postgres' : 'local_json',
    players,
    matches,
    currentMatch,
    recentChat: globalChatBuffer.slice(-50),
    settings,
    appRelease: settings.appRelease || db.DEFAULT_APP_RELEASE
  };
}

async function handleAutoAddGame(data, authResult) {
  const canonicalStreamerName = authResult.canonicalName;
  const playerRecord = authResult.player;
  playerRecord.lastSeenAt = Date.now();
  await db.upsertPlayer(playerRecord);

  const rawRedCivs = Array.isArray(data.redCivs) ? data.redCivs : [];
  const rawBlueCivs = Array.isArray(data.blueCivs) ? data.blueCivs : [];
  const rawRedPlayers = Array.isArray(data.redPlayers) ? data.redPlayers : [];
  const rawBluePlayers = Array.isArray(data.bluePlayers) ? data.bluePlayers : [];

  const redPlayers = rawRedPlayers
    .map(cleanPlayerName)
    .filter(name => name && !isFakePlayerName(name));
  const bluePlayers = rawBluePlayers
    .map(cleanPlayerName)
    .filter(name => name && !isFakePlayerName(name));

  const redCivs = rawRedCivs.map(parseCiv).filter(civ => civ && civ !== 'Random');
  const blueCivs = rawBlueCivs.map(parseCiv).filter(civ => civ && civ !== 'Random');

  if (
    !redPlayers.length ||
    !bluePlayers.length ||
    redPlayers.length !== rawRedPlayers.length ||
    bluePlayers.length !== rawBluePlayers.length ||
    redCivs.length !== rawRedCivs.length ||
    blueCivs.length !== rawBlueCivs.length ||
    redPlayers.length !== bluePlayers.length ||
    redCivs.length !== redPlayers.length ||
    blueCivs.length !== bluePlayers.length
  ) {
    return {
      added: false,
      message: 'Bỏ qua: Bảng quân cần đầy đủ tên người chơi và quân hợp lệ của cả 2 đội (cân bằng 1v1, 2v2, 3v3, 4v4)!'
    };
  }

  const mode = getMode(redPlayers.length);

  const redColors = Array.isArray(data.redColors) ? data.redColors.slice(0, redPlayers.length) : [];
  const blueColors = Array.isArray(data.blueColors) ? data.blueColors.slice(0, bluePlayers.length) : [];
  const streamerName = canonicalStreamerName || data.streamerName || 'Auto Bot';

  const effectiveOverlayCfg = data.overlayConfig
    ? enforceTierOverlayConfig(playerRecord.tier, data.overlayConfig, playerRecord.overlayConfig)
    : db.normalizeOverlayConfig(playerRecord.overlayConfig);

  const matches = await db.getMatches();
  const sLower = streamerName.toLowerCase();
  const liveCandidates = matches
    .filter(item => item.status === 'LIVE' && String(item.streamerName || '').toLowerCase() === sLower)
    .sort(
      (a, b) =>
        Math.max(Number(b.lastHeartbeat) || 0, Number(b.createdAt) || 0) -
        Math.max(Number(a.lastHeartbeat) || 0, Number(a.createdAt) || 0)
    );

  let liveMatch = liveCandidates[0] || null;
  for (let i = 1; i < liveCandidates.length; i++) {
    liveCandidates[i].status = 'FINISHED';
    await db.saveMatch(liveCandidates[i]);
  }

  // Nếu đổi thể thức (ví dụ 2v2 sang 1v1 hoặc 3v3) thì kết thúc kèo cũ và tạo kèo mới từ Trận 1
  if (liveMatch && liveMatch.mode && liveMatch.mode !== mode) {
    liveMatch.status = 'FINISHED';
    await db.saveMatch(liveMatch);
    liveMatch = null;
  }

  if (liveMatch && liveMatch.games && liveMatch.games.length) {
    const previous = liveMatch.games[liveMatch.games.length - 1];
    const prevWinner = String(previous.winner || 'PENDING').toUpperCase();
    const isSameCivLineup =
      JSON.stringify(previous.redCivs) === JSON.stringify(redCivs) &&
      JSON.stringify(previous.blueCivs) === JSON.stringify(blueCivs);

    if (!data.allowSameCiv && prevWinner === 'PENDING' && isSameCivLineup) {
      liveMatch.redTeam = redPlayers;
      liveMatch.blueTeam = bluePlayers;
      liveMatch.redColors = redColors;
      liveMatch.blueColors = blueColors;
      liveMatch.overlayConfig = effectiveOverlayCfg;
      previous.redPlayers = redPlayers;
      previous.bluePlayers = bluePlayers;
      previous.redColors = redColors;
      previous.blueColors = blueColors;
      liveMatch.lastHeartbeat = Date.now();
      await db.saveMatch(liveMatch);
      broadcastUpdate('match_updated', {
        matchId: liveMatch.id,
        streamerName: liveMatch.streamerName,
        match: liveMatch
      });
      return {
        added: false,
        match: liveMatch,
        message: `Đang ở Trận ${liveMatch.games.length} (Đã đồng bộ tên/màu)`
      };
    }
  }

  if (!liveMatch) {
    liveMatch = {
      id: 'MATCH_' + Date.now(),
      createdAt: Date.now(),
      lastHeartbeat: Date.now(),
      streamerName,
      mode,
      redTeam: redPlayers,
      blueTeam: bluePlayers,
      redColors,
      blueColors,
      overlayConfig: effectiveOverlayCfg,
      updatedBy: streamerName,
      formattedTime: formatVietnamTime(),
      status: 'LIVE',
      starsCount: 0,
      chatMessages: [],
      games: []
    };
  } else {
    liveMatch.mode = mode;
    liveMatch.redTeam = redPlayers;
    liveMatch.blueTeam = bluePlayers;
    liveMatch.redColors = redColors;
    liveMatch.blueColors = blueColors;
    liveMatch.overlayConfig = effectiveOverlayCfg;
    liveMatch.lastHeartbeat = Date.now();
    if (!Array.isArray(liveMatch.chatMessages)) liveMatch.chatMessages = [];
    if (typeof liveMatch.starsCount !== 'number') liveMatch.starsCount = 0;
  }

  liveMatch.games.push({
    redPlayers,
    bluePlayers,
    redCivs,
    blueCivs,
    redColors,
    blueColors,
    winner: 'PENDING',
    capturedAt: Date.now()
  });

  await db.saveMatch(liveMatch);
  broadcastUpdate('game_added', {
    matchId: liveMatch.id,
    streamerName: liveMatch.streamerName,
    gameNumber: liveMatch.games.length,
    match: liveMatch
  });
  return {
    added: true,
    match: liveMatch,
    message: `Đã cập nhật Trận ${liveMatch.games.length} (${mode})`
  };
}

// SSE Endpoint for instant live updates
app.get('/api/stream', (req, res) => {
  res.setHeader('Content-Type', 'text/event-stream');
  res.setHeader('Cache-Control', 'no-cache');
  res.setHeader('Connection', 'keep-alive');
  res.flushHeaders?.();

  res.write(`data: ${JSON.stringify({ type: 'connected', timestamp: Date.now() })}\n\n`);
  sseClients.add(res);

  const keepAlive = setInterval(() => {
    try {
      res.write(': keep-alive\n\n');
    } catch (e) {
      clearInterval(keepAlive);
      sseClients.delete(res);
    }
  }, 25000);

  req.on('close', () => {
    clearInterval(keepAlive);
    sseClients.delete(res);
  });
});

// GET /api
app.get('/api', async (req, res) => {
  try {
    res.setHeader('Cache-Control', 'no-store, no-cache, must-revalidate, proxy-revalidate');
    res.setHeader('Pragma', 'no-cache');
    res.setHeader('Expires', '0');
    const action = req.query.action || 'getInitialData';
    const streamer = req.query.streamer || req.query.player || '';
    if (action === 'getInitialData') {
      const payload = await getInitialDataPayload(streamer);
      return res.json(payload);
    }
    return res.json({ status: 'ok', databaseMode: db.isPostgresActive() ? 'neon_postgres' : 'local_json' });
  } catch (err) {
    console.error('[API GET Error]:', err);
    return res.status(500).json({ status: 'error', message: String(err.message || err) });
  }
});

// POST /api
app.post('/api', async (req, res) => {
  try {
    const data = req.body || {};
    const action = data.action;

    if (action === 'verifyPlayerLogin') {
      const [auth, settings] = await Promise.all([
        validatePlayerAccount(data.playerName, data.password),
        db.getSettings()
      ]);
      if (auth.valid && auth.player) {
        auth.player.lastSeenAt = Date.now();
        await db.upsertPlayer(auth.player);
        broadcastUpdate('presence_updated', { playerName: auth.canonicalName });
      }
      const pObj = auth.player || {};
      return res.json({
        status: auth.valid ? 'success' : 'error',
        isAdmin: Boolean(auth.isAdmin),
        playerName: auth.canonicalName || data.playerName,
        tier: auth.tier || 'BRONZE',
        tierNameVi: TIER_NAMES_VI[auth.tier || 'BRONZE'] || '🥉 Hạng Đồng',
        overlayConfig: auth.overlayConfig || db.DEFAULT_OVERLAY_CONFIG,
        appRelease: settings.appRelease || db.DEFAULT_APP_RELEASE,
        friends: pObj.friends || [],
        starsReceived: pObj.starsReceived || 0,
        starsBalance: pObj.starsBalance || 0,
        starHistory: pObj.starHistory || [],
        vipHistory: pObj.vipHistory || [],
        note: pObj.note || '',
        isActive: pObj.isActive !== undefined ? pObj.isActive : false,
        createdAt: pObj.createdAt || null,
        createdFormatted: pObj.createdAt ? formatVietnamDateOnly(pObj.createdAt) : '',
        activatedAt: pObj.activatedAt || null,
        expiresAt: pObj.expiresAt || null,
        daysLeft: auth.daysLeft !== undefined ? auth.daysLeft : null,
        activatedFormatted: auth.activatedFormatted || '',
        expiresFormatted: auth.expiresFormatted || '',
        player: auth.valid ? {
          ...pObj,
          password: '******',
          tierNameVi: TIER_NAMES_VI[auth.tier || 'BRONZE'] || '🥉 Hạng Đồng',
          createdFormatted: pObj.createdAt ? formatVietnamDateOnly(pObj.createdAt) : '',
          activatedFormatted: auth.activatedFormatted || '',
          expiresFormatted: auth.expiresFormatted || '',
          daysLeft: auth.daysLeft !== undefined ? auth.daysLeft : null
        } : null,
        message: auth.valid
          ? (auth.isAdmin
            ? `Đăng nhập thành công với quyền QUẢN TRỊ ADMIN XO [${TIER_NAMES_VI[auth.tier] || auth.tier}]!`
            : `Đăng nhập thành công [${TIER_NAMES_VI[auth.tier] || auth.tier}]! (Hạn SD: ${auth.expiresFormatted})`)
          : (auth.reason || 'Đăng nhập thất bại!')
      });
    }

    if (action === 'getPlayerProfile') {
      const targetName = String(data.targetName || data.playerName || '').trim();
      const adminOk = isAdminAuthorized(data);
      let auth = { valid: false };
      if (!adminOk) {
        auth = await validatePlayerAccount(data.playerName || targetName, data.password);
        if (!auth.valid) {
          return res.json({ status: 'error', message: auth.reason || 'Vui lòng đăng nhập để xem thông tin tài khoản!' });
        }
      }
      const lookupName = adminOk ? (targetName || data.playerName || 'XO') : auth.canonicalName;
      const [rawPlayers, matches] = await Promise.all([db.getPlayers(), db.getMatches()]);
      const enriched = enrichPlayersWithLiveStatus(rawPlayers, matches);
      const found = enriched.find(p => p.name.toLowerCase() === String(lookupName).toLowerCase());
      if (!found) {
        return res.json({ status: 'error', message: `Không tìm thấy thông tin tài khoản "${lookupName}"!` });
      }
      const now = Date.now();
      const daysLeft = found.expiresAt && Number(found.expiresAt) > 0
        ? Math.max(0, Math.ceil((Number(found.expiresAt) - now) / (24 * 60 * 60 * 1000)))
        : null;
      return res.json({
        status: 'success',
        profile: {
          ...found,
          password: adminOk ? found.password : '******',
          tierNameVi: TIER_NAMES_VI[found.tier || 'BRONZE'] || '🥉 Hạng Đồng',
          createdFormatted: found.createdAt ? formatVietnamDateOnly(found.createdAt) : '---',
          activatedFormatted: found.activatedAt ? formatVietnamDateOnly(found.activatedAt) : '---',
          expiresFormatted: found.expiresAt ? formatVietnamDateOnly(found.expiresAt) : '♾️ Vĩnh viễn',
          daysLeft
        }
      });
    }

    if (action === 'userChangePassword') {
      const auth = await validatePlayerAccount(data.playerName, data.oldPassword || data.password);
      if (!auth.valid || !auth.player) {
        return res.json({ status: 'error', message: auth.reason || 'Mật khẩu hiện tại không đúng!' });
      }
      const newPass = String(data.newPassword || '').trim();
      const confirmPass = data.confirmPassword !== undefined ? String(data.confirmPassword || '').trim() : newPass;
      if (!newPass || newPass.length < 8) {
        return res.json({ status: 'error', message: 'Mật khẩu mới bắt buộc phải có tối thiểu 8 ký tự!' });
      }
      if (newPass !== confirmPass) {
        return res.json({ status: 'error', message: 'Mật khẩu xác nhận nhập lại không trùng khớp!' });
      }
      const now = Date.now();
      auth.player.password = newPass;
      auth.player.vipHistory = Array.isArray(auth.player.vipHistory) ? auth.player.vipHistory : [];
      auth.player.vipHistory.push({
        id: 'PASS_' + now,
        action: 'USER_CHANGE_PASS',
        tier: auth.player.tier,
        note: 'Người dùng tự đổi mật khẩu cá nhân (đã xác thực 2 lớp)',
        by: auth.player.name,
        createdAt: now,
        formattedTime: formatVietnamTime(now)
      });
      await db.upsertPlayer(auth.player);
      return res.json({
        status: 'success',
        message: 'Đã đổi mật khẩu tài khoản thành công!'
      });
    }

    if (action === 'verifyAdminLogin') {
      const ok = String(data.password || '').trim() === ADMIN_PASSWORD;
      return res.json({
        status: ok ? 'success' : 'error',
        message: ok ? 'Đăng nhập Admin thành công!' : 'Mật khẩu Admin sai!'
      });
    }

    if (action === 'autoAddGame') {
      const auth = await validatePlayerAccount(data.streamerName, data.password);
      if (!auth.valid) {
        return res.json({ status: 'error', message: auth.reason || 'Tài khoản không hợp lệ!' });
      }
      const result = await handleAutoAddGame(data, auth);
      return res.json({
        status: 'success',
        added: result.added,
        match: result.match,
        message: result.message
      });
    }

    if (action === 'updateOverlayConfig') {
      const lookupName = data.streamerName || data.playerName;
      const auth = await validatePlayerAccount(lookupName, data.password);
      if (!auth.valid && !isAdminAuthorized(data)) {
        return res.json({ status: 'error', message: auth.reason || 'Xác thực thất bại!' });
      }
      const players = await db.getPlayers();
      const targetName = auth.valid ? auth.canonicalName : String(lookupName || 'XO').trim();
      const playerObj = players.find(p => p.name.toLowerCase() === targetName.toLowerCase());
      const effectiveTier = isAdminAuthorized(data) ? 'DIAMOND' : (playerObj ? playerObj.tier : 'BRONZE');

      const sanitizedCfg = enforceTierOverlayConfig(
        effectiveTier,
        data.overlayConfig,
        playerObj ? playerObj.overlayConfig : db.DEFAULT_OVERLAY_CONFIG
      );

      if (playerObj) {
        playerObj.overlayConfig = sanitizedCfg;
        playerObj.lastSeenAt = Date.now();
        await db.upsertPlayer(playerObj);
      }

      const matches = await db.getMatches();
      const liveMatch = matches.find(
        m => m.status === 'LIVE' && String(m.streamerName || '').toLowerCase() === targetName.toLowerCase()
      ) || matches.find(
        m => String(m.streamerName || '').toLowerCase() === targetName.toLowerCase()
      );

      if (liveMatch) {
        liveMatch.overlayConfig = sanitizedCfg;
        liveMatch.lastHeartbeat = Date.now();
        await db.saveMatch(liveMatch);
      }

      broadcastUpdate('overlay_config_updated', { streamerName: targetName, overlayConfig: sanitizedCfg });
      return res.json({
        status: 'success',
        overlayConfig: sanitizedCfg,
        match: liveMatch || null,
        message: 'Đã đồng bộ Cấu Hình VIP Overlay lên Livestream!'
      });
    }

    // ==================== KẾT BẠN & THEO DÕI TRẠNG THÁI LIVE CỦA BẠN BÈ ====================
    if (action === 'toggleFriend') {
      const auth = await validatePlayerAccount(data.playerName, data.password);
      if (!auth.valid) {
        return res.json({ status: 'error', message: auth.reason || 'Vui lòng đăng nhập tài khoản Player để kết bạn!' });
      }
      const targetFriend = String(data.friendName || '').trim();
      if (!targetFriend) {
        return res.json({ status: 'error', message: 'Vui lòng chọn hoặc nhập tên người chơi cần kết bạn!' });
      }
      const rawPlayers = await db.getPlayers();
      const me = rawPlayers.find(p => p.name.toLowerCase() === auth.canonicalName.toLowerCase());
      const friendObj = rawPlayers.find(p => p.name.toLowerCase() === targetFriend.toLowerCase());

      if (!me) {
        return res.json({ status: 'error', message: 'Không tìm thấy tài khoản của bạn!' });
      }
      if (!friendObj) {
        return res.json({ status: 'error', message: `Không tìm thấy người chơi "${targetFriend}" trong hệ thống!` });
      }
      if (me.name.toLowerCase() === friendObj.name.toLowerCase()) {
        return res.json({ status: 'error', message: 'Không thể tự kết bạn với chính mình!' });
      }

      me.friends = Array.isArray(me.friends) ? me.friends : [];
      friendObj.friends = Array.isArray(friendObj.friends) ? friendObj.friends : [];

      const existsIdx = me.friends.findIndex(f => f.toLowerCase() === friendObj.name.toLowerCase());
      let added = false;
      if (existsIdx >= 0) {
        me.friends.splice(existsIdx, 1);
      } else {
        me.friends.push(friendObj.name);
        if (!friendObj.friends.some(f => f.toLowerCase() === me.name.toLowerCase())) {
          friendObj.friends.push(me.name);
        }
        added = true;
      }

      me.lastSeenAt = Date.now();
      await db.upsertPlayer(me);
      if (added) {
        await db.upsertPlayer(friendObj);
      }

      const [updatedRawPlayers, matches] = await Promise.all([db.getPlayers(), db.getMatches()]);
      const enriched = enrichPlayersWithLiveStatus(updatedRawPlayers, matches);
      broadcastUpdate('friends_updated', { playerName: me.name });

      return res.json({
        status: 'success',
        added,
        friends: me.friends,
        players: enriched,
        message: added
          ? `Đã kết bạn với "${friendObj.name}"! Bạn có thể theo dõi khi ${friendObj.name} lên sóng LIVE.`
          : `Đã hủy kết bạn với "${friendObj.name}".`
      });
    }

    // ==================== KHUNG CHAT BÌNH LUẬN TRẬN ĐẤU & OVERLAY CHAT OBS (BẮT BUỘC ĐĂNG NHẬP) ====================
    if (action === 'sendChatMessage') {
      const loginName = String(data.senderName || data.playerName || '').trim();
      const auth = await validatePlayerAccount(loginName, data.password);
      if (!auth.valid && !isAdminAuthorized(data)) {
        return res.json({
          status: 'error',
          message: auth.reason || 'Bạn bắt buộc phải đăng nhập tài khoản Player để bình luận trong sảnh Live!'
        });
      }

      const text = String(data.text || data.message || '').trim().slice(0, 260);
      if (!text) {
        return res.json({ status: 'error', message: 'Nội dung bình luận trống!' });
      }
      const senderPlayer = auth.player || null;
      const senderName = auth.canonicalName || loginName || 'XO';
      const senderTier = senderPlayer ? senderPlayer.tier : (isAdminAuthorized(data) ? 'DIAMOND' : 'BRONZE');

      if (senderPlayer) {
        senderPlayer.lastSeenAt = Date.now();
        await db.upsertPlayer(senderPlayer);
      }

      const matches = await db.getMatches();
      let targetMatch = null;
      if (data.matchId) {
        targetMatch = matches.find(m => m.id === data.matchId);
      }
      if (!targetMatch && data.streamerName) {
        const sLower = String(data.streamerName).toLowerCase();
        targetMatch =
          matches.find(m => m.status === 'LIVE' && String(m.streamerName || '').toLowerCase() === sLower) ||
          matches.find(m => String(m.streamerName || '').toLowerCase() === sLower);
      }
      if (!targetMatch) {
        targetMatch = matches.find(m => m.status === 'LIVE') || matches[0] || null;
      }

      const streamerName = (targetMatch && targetMatch.streamerName) || data.streamerName || senderName || 'XO';
      const isAdminSender = Boolean(auth.isAdmin || isAdminAuthorized(data) || senderName.toLowerCase() === 'xo');
      const isStreamerSender = Boolean(senderName.toLowerCase() === String(streamerName).toLowerCase());
      const now = Date.now();
      const msgObj = {
        id: 'MSG_' + now + '_' + Math.floor(Math.random() * 1000),
        matchId: targetMatch ? targetMatch.id : null,
        streamerName,
        senderName,
        senderTier,
        isAdmin: isAdminSender,
        isStreamer: isStreamerSender,
        text,
        message: text,
        type: 'CHAT',
        createdAt: now,
        timeText: formatShortTimeVN(now)
      };

      globalChatBuffer.push(msgObj);
      if (globalChatBuffer.length > 100) globalChatBuffer.shift();

      if (targetMatch) {
        if (!Array.isArray(targetMatch.chatMessages)) targetMatch.chatMessages = [];
        targetMatch.chatMessages.push(msgObj);
        if (targetMatch.chatMessages.length > 60) {
          targetMatch.chatMessages = targetMatch.chatMessages.slice(-60);
        }
        await db.saveMatch(targetMatch);
      }

      broadcastUpdate('chat_message', {
        matchId: targetMatch ? targetMatch.id : null,
        streamerName,
        chat: msgObj
      });

      return res.json({
        status: 'success',
        chat: msgObj,
        match: targetMatch || null
      });
    }

    // ==================== GHIM / BỎ GHIM BÌNH LUẬN QUAN TRỌNG TRONG SẢNH LIVE ====================
    if (action === 'pinChatMessage') {
      const loginName = String(data.senderName || data.playerName || data.updatedBy || '').trim();
      const auth = await validatePlayerAccount(loginName, data.password);
      const adminOk = isAdminAuthorized(data) || Boolean(auth.valid && auth.isAdmin);
      if (!auth.valid && !adminOk) {
        return res.json({ status: 'error', message: 'Vui lòng đăng nhập để ghim bình luận!' });
      }
      const matches = await db.getMatches();
      let targetMatch = null;
      if (data.matchId) {
        targetMatch = matches.find(m => m.id === data.matchId);
      }
      if (!targetMatch && data.streamerName) {
        const sLower = String(data.streamerName).toLowerCase();
        targetMatch =
          matches.find(m => m.status === 'LIVE' && String(m.streamerName || '').toLowerCase() === sLower) ||
          matches.find(m => String(m.streamerName || '').toLowerCase() === sLower);
      }
      if (!targetMatch) {
        targetMatch = matches.find(m => m.status === 'LIVE') || matches[0] || null;
      }

      const streamerName = (targetMatch && targetMatch.streamerName) || data.streamerName || auth.canonicalName || 'XO';
      const isRoomOwner = auth.valid && auth.canonicalName.toLowerCase() === String(streamerName).toLowerCase();
      if (!adminOk && !isRoomOwner) {
        return res.json({ status: 'error', message: 'Chỉ chủ sảnh Streamer hoặc Admin XO mới có quyền ghim bình luận!' });
      }

      let pinnedObj = null;
      if (data.unpin) {
        pinnedObj = null;
      } else if (data.chat && typeof data.chat === 'object') {
        pinnedObj = {
          id: data.chat.id || ('PIN_' + Date.now()),
          senderName: String(data.chat.senderName || auth.canonicalName || 'XO').slice(0, 60),
          text: String(data.chat.text || data.chat.message || '').trim().slice(0, 260),
          pinnedBy: auth.canonicalName || 'XO',
          pinnedAt: Date.now(),
          timeText: formatShortTimeVN(Date.now())
        };
      } else if (data.text) {
        pinnedObj = {
          id: 'PIN_' + Date.now(),
          senderName: String(data.authorName || auth.canonicalName || 'XO').slice(0, 60),
          text: String(data.text || '').trim().slice(0, 260),
          pinnedBy: auth.canonicalName || 'XO',
          pinnedAt: Date.now(),
          timeText: formatShortTimeVN(Date.now())
        };
      }

      if (targetMatch) {
        targetMatch.pinnedChat = pinnedObj;
        await db.saveMatch(targetMatch);
      }

      broadcastUpdate('chat_pinned', {
        matchId: targetMatch ? targetMatch.id : null,
        streamerName,
        pinnedChat: pinnedObj
      });

      return res.json({
        status: 'success',
        pinnedChat: pinnedObj,
        match: targetMatch || null,
        message: pinnedObj ? `📌 Đã ghim bình luận của ${pinnedObj.senderName}!` : 'Đã bỏ ghim bình luận!'
      });
    }

    // ==================== ĐẨY COMMENT TỪ LUỒNG LIVE FACEBOOK GROUP / FANPAGE VỀ OBS & TOOL ====================
    if (action === 'pushFacebookComment') {
      const streamerLogin = String(data.streamerName || data.playerName || 'XO').trim();
      const auth = await validatePlayerAccount(streamerLogin, data.password, data.bridgeToken);
      if (!auth.valid && !isAdminAuthorized(data)) {
        return res.json({
          status: 'error',
          message: auth.reason || 'Xác thực tài khoản Streamer không hợp lệ khi đẩy comment Facebook!'
        });
      }

      const canonicalStreamer = auth.valid ? auth.canonicalName : streamerLogin;
      const rawItems = Array.isArray(data.comments)
        ? data.comments
        : [{ authorName: data.authorName || data.senderName, text: data.text || data.message, commentId: data.commentId }];

      const matches = await db.getMatches();
      const sLower = canonicalStreamer.toLowerCase();
      const targetMatch =
        matches.find(m => m.status === 'LIVE' && String(m.streamerName || '').toLowerCase() === sLower) ||
        matches.find(m => String(m.streamerName || '').toLowerCase() === sLower) ||
        matches.find(m => m.status === 'LIVE') ||
        matches[0] ||
        null;

      if (!global.__fbDedupMap) global.__fbDedupMap = new Map();
      const dedupMap = global.__fbDedupMap;
      const now = Date.now();
      for (const [k, ts] of dedupMap.entries()) {
        if (now - ts > 90000) dedupMap.delete(k);
      }

      const addedChats = [];
      for (const item of rawItems.slice(0, 15)) {
        const author = String(item.authorName || item.senderName || 'Khán giả FB').trim().slice(0, 60);
        const text = String(item.text || item.message || '').trim().slice(0, 260);
        if (!text) continue;

        const sig = `${canonicalStreamer.toLowerCase()}::${author.toLowerCase()}::${text.toLowerCase()}`;
        if (dedupMap.has(sig)) continue;
        dedupMap.set(sig, now);

        const msgObj = {
          id: 'FB_' + now + '_' + Math.floor(Math.random() * 10000),
          matchId: targetMatch ? targetMatch.id : null,
          streamerName: canonicalStreamer,
          senderName: author,
          senderTier: 'FACEBOOK',
          source: 'FACEBOOK',
          text,
          message: text,
          type: 'CHAT',
          createdAt: now,
          timeText: formatShortTimeVN(now)
        };

        globalChatBuffer.push(msgObj);
        if (globalChatBuffer.length > 100) globalChatBuffer.shift();

        if (targetMatch) {
          if (!Array.isArray(targetMatch.chatMessages)) targetMatch.chatMessages = [];
          targetMatch.chatMessages.push(msgObj);
          if (targetMatch.chatMessages.length > 60) {
            targetMatch.chatMessages = targetMatch.chatMessages.slice(-60);
          }
        }

        addedChats.push(msgObj);
        broadcastUpdate('chat_message', {
          matchId: targetMatch ? targetMatch.id : null,
          streamerName: canonicalStreamer,
          chat: msgObj
        });
      }

      if (targetMatch && addedChats.length > 0) {
        await db.saveMatch(targetMatch);
      }

      return res.json({
        status: 'success',
        addedCount: addedChats.length,
        chats: addedChats,
        message: addedChats.length > 0 ? `Đã đẩy ${addedChats.length} bình luận Facebook Live lên OBS!` : 'Bỏ qua bình luận trùng lặp'
      });
    }

    // ==================== HIỆU ỨNG TẶNG SAO & VẬT PHẨM ĐẾ CHẾ (TRỪ TRỰC TIẾP TỪ QUỸ SAO CỦA NGƯỜI CHƠI) ====================
    if (action === 'sendStarGift') {
      const loginName = String(data.senderName || data.playerName || '').trim();
      const auth = await validatePlayerAccount(loginName, data.password);
      if (!auth.valid && !isAdminAuthorized(data)) {
        return res.json({
          status: 'error',
          message: auth.reason || 'Bạn bắt buộc phải đăng nhập tài khoản Player để tặng Sao / Vật phẩm trong sảnh Live!'
        });
      }

      const senderName = auth.canonicalName || loginName || 'XO';
      const rawGiftCode = String(data.giftCode || '').toUpperCase().trim();
      const giftDef = AOE_GIFT_CATALOG[rawGiftCode] || null;

      const starCount = giftDef
        ? giftDef.stars
        : Math.max(1, Math.min(9999, Number(data.starCount || data.stars) || 1));
      const giftCode = giftDef ? giftDef.code : (rawGiftCode || 'STAR');
      const giftName = giftDef ? giftDef.name : String(data.giftName || `${starCount} Sao`).trim();
      const giftIcon = giftDef ? giftDef.icon : String(data.giftIcon || '⭐').trim();
      const giftParticles = giftDef ? giftDef.particles : ['⭐', '🌟', '✨', '💫', '🔥'];
      const cheerText = String(data.message || (giftDef ? giftDef.defaultMsg : 'Đánh hay quá! Tặng sao cổ vũ!')).trim().slice(0, 160);

      const matches = await db.getMatches();
      let targetMatch = null;
      if (data.matchId) {
        targetMatch = matches.find(m => m.id === data.matchId);
      }
      if (!targetMatch && data.streamerName) {
        const sLower = String(data.streamerName).toLowerCase();
        targetMatch =
          matches.find(m => m.status === 'LIVE' && String(m.streamerName || '').toLowerCase() === sLower) ||
          matches.find(m => String(m.streamerName || '').toLowerCase() === sLower);
      }
      if (!targetMatch) {
        targetMatch = matches.find(m => m.status === 'LIVE') || matches[0] || null;
      }

      const streamerName = String((targetMatch && targetMatch.streamerName) || data.streamerName || 'XO').trim();
      const rawPlayers = await db.getPlayers();
      const streamerObj = rawPlayers.find(p => p.name.toLowerCase() === streamerName.toLowerCase());
      const senderObj = rawPlayers.find(p => p.name.toLowerCase() === senderName.toLowerCase());

      if (!senderObj) {
        return res.json({
          status: 'error',
          message: `Không tìm thấy tài khoản "${senderName}" để trừ Quỹ Sao!`
        });
      }

      const currentSenderBalance = Number(senderObj.starsBalance) || 0;
      if (currentSenderBalance < starCount) {
        return res.json({
          status: 'error',
          starsBalance: currentSenderBalance,
          message: `Quỹ Sao của bạn không đủ để tặng ${giftIcon} ${giftName} (Cần ${starCount} ⭐, quỹ hiện có ${currentSenderBalance} ⭐). Vui lòng liên hệ Admin XO để nạp thêm Sao!`
        });
      }

      const now = Date.now();
      const isSelfGift = Boolean(streamerObj && streamerObj.name.toLowerCase() === senderObj.name.toLowerCase());

      // 1. Trừ trực tiếp số Sao từ Quỹ Sao (starsBalance) của người tặng
      senderObj.starsBalance = Math.max(0, currentSenderBalance - starCount);
      senderObj.lastSeenAt = now;
      senderObj.starHistory = Array.isArray(senderObj.starHistory) ? senderObj.starHistory : [];
      senderObj.starHistory.push({
        id: 'STAR_SENT_' + now + '_' + Math.floor(Math.random() * 1000),
        type: 'GIFT_SENT',
        amount: -starCount,
        balanceAfter: senderObj.starsBalance,
        note: `Tặng ${giftIcon} ${giftName} (-${starCount} ⭐) cho sảnh Live của ${streamerName}: "${cheerText}"`,
        by: senderName,
        createdAt: now,
        formattedTime: formatVietnamTime(now)
      });

      // 2. Cộng vào tổng Sao nhận trên Live (starsReceived) của Streamer
      let totalStreamerStars = starCount;
      const receiverTarget = isSelfGift ? senderObj : streamerObj;
      if (receiverTarget) {
        receiverTarget.starsReceived = (Number(receiverTarget.starsReceived) || 0) + starCount;
        totalStreamerStars = receiverTarget.starsReceived;
        receiverTarget.starHistory = Array.isArray(receiverTarget.starHistory) ? receiverTarget.starHistory : [];
        receiverTarget.starHistory.push({
          id: 'STAR_RCV_' + now + '_' + Math.floor(Math.random() * 1000),
          type: 'GIFT_RECEIVED',
          amount: starCount,
          balanceAfter: receiverTarget.starsBalance || 0,
          totalReceivedAfter: totalStreamerStars,
          note: `Nhận ${giftIcon} ${giftName} (+${starCount} ⭐) từ ${senderName}: "${cheerText}"`,
          by: senderName,
          createdAt: now,
          formattedTime: formatVietnamTime(now)
        });
      }

      // Lưu vào DB (Nếu tự tặng tại sảnh của mình thì chỉ upsert 1 lần trên cùng object đã cập nhật cả 2 trường)
      await db.upsertPlayer(senderObj);
      if (streamerObj && !isSelfGift) {
        await db.upsertPlayer(streamerObj);
      }

      const itemTitle = giftDef ? `${giftIcon} ${giftName} (+${starCount}⭐)` : `+${starCount} ⭐`;
      const displayLine = `tặng ${itemTitle} ➔ ${streamerName}`;
      const starChatObj = {
        id: 'STAR_' + now + '_' + Math.floor(Math.random() * 1000),
        matchId: targetMatch ? targetMatch.id : null,
        streamerName,
        receiverName: streamerName,
        senderName,
        senderTier: 'STAR',
        starCount,
        giftCode,
        giftName,
        giftIcon,
        itemTitle,
        text: displayLine,
        message: displayLine,
        type: 'STAR',
        createdAt: now,
        timeText: formatShortTimeVN(now)
      };

      globalChatBuffer.push(starChatObj);
      if (globalChatBuffer.length > 100) globalChatBuffer.shift();

      let totalMatchStars = starCount;
      if (targetMatch) {
        targetMatch.starsCount = (Number(targetMatch.starsCount) || 0) + starCount;
        totalMatchStars = targetMatch.starsCount;
        if (!Array.isArray(targetMatch.chatMessages)) targetMatch.chatMessages = [];
        targetMatch.chatMessages.push(starChatObj);
        if (targetMatch.chatMessages.length > 60) {
          targetMatch.chatMessages = targetMatch.chatMessages.slice(-60);
        }
        await db.saveMatch(targetMatch);
      }

      const giftPayload = {
        id: starChatObj.id,
        matchId: targetMatch ? targetMatch.id : null,
        streamerName,
        senderName,
        starCount,
        giftCode,
        giftName,
        giftIcon,
        giftParticles,
        message: cheerText,
        totalMatchStars,
        totalStreamerStars,
        senderStarsBalance: senderObj.starsBalance,
        createdAt: now
      };

      broadcastUpdate('star_gifted', {
        matchId: targetMatch ? targetMatch.id : null,
        streamerName,
        gift: giftPayload,
        chat: starChatObj
      });

      return res.json({
        status: 'success',
        gift: giftPayload,
        chat: starChatObj,
        match: targetMatch || null,
        senderStarsBalance: senderObj.starsBalance,
        message: `${giftIcon} Đã tặng ${giftName} (-${starCount} ⭐) tới sảnh Live của ${streamerName}! (Quỹ Sao còn lại: ${senderObj.starsBalance} ⭐)`
      });
    }

    if (action === 'triggerHypeShout') {
      const auth = await validatePlayerAccount(data.streamerName || data.senderName, data.password);
      const adminOk = isAdminAuthorized(data);
      if (!auth.valid && !adminOk) {
        return res.json({ status: 'error', message: auth.reason || 'Vui lòng đăng nhập tài khoản Player để bắn hiệu ứng F8!' });
      }
      const streamerName = auth.valid ? auth.canonicalName : String(data.streamerName || 'XO').trim();
      const shoutText = String(data.text || 'Tay đâu, tayyyy đâuuuuu').trim();
      const subText = String(data.subText || '🔥 CHIẾN THẮNG NGHẸT THỞ • QUẨY LÊN ANH EM ƠI! 🙌').trim();
      const durationMs = Math.min(12000, Math.max(3500, Number(data.durationMs) || 6500));
      const now = Date.now();

      const matches = await db.getMatches();
      const sLower = streamerName.toLowerCase();
      const sortedForStreamer = matches
        .filter(m => String(m.streamerName || '').toLowerCase() === sLower)
        .sort(
          (a, b) =>
            Math.max(Number(b.lastHeartbeat) || 0, Number(b.createdAt) || 0) -
            Math.max(Number(a.lastHeartbeat) || 0, Number(a.createdAt) || 0)
        );
      const targetMatch =
        sortedForStreamer.find(m => m.status === 'LIVE') ||
        sortedForStreamer[0] ||
        null;

      const hypePayload = {
        id: 'HYPE_' + now + '_' + Math.floor(Math.random() * 1000),
        matchId: targetMatch ? targetMatch.id : null,
        streamerName,
        text: shoutText,
        subText,
        durationMs,
        particles: ['🙌', '🔥', '👏', '⚡', '🏆', '💥'],
        createdAt: now
      };

      // Lưu lastHypeShout trên cả Match và overlayConfig của Streamer để khung 'Link OBS' (overlay.html) luôn bắt được hiệu ứng F8
      if (targetMatch) {
        targetMatch.lastHypeShout = hypePayload;
        targetMatch.lastHeartbeat = now;
        await db.saveMatch(targetMatch);
      }
      if (auth.player) {
        auth.player.overlayConfig = {
          ...(auth.player.overlayConfig || {}),
          lastHypeShout: hypePayload
        };
        auth.player.lastSeenAt = now;
        await db.upsertPlayer(auth.player);
      }

      broadcastUpdate('hype_shout', {
        matchId: targetMatch ? targetMatch.id : null,
        streamerName,
        hype: hypePayload
      });

      return res.json({
        status: 'success',
        hype: hypePayload,
        match: targetMatch || null,
        message: `🙌🔥 Đã bắn hiệu ứng "${shoutText}" lên khung Link OBS Bảng Quân!`
      });
    }

    if (action === 'heartbeat') {
      const auth = await validatePlayerAccount(data.streamerName, data.password);
      if (!auth.valid) {
        return res.json({ status: 'error', message: auth.reason || 'Xác thực thất bại!' });
      }
      if (auth.player) {
        auth.player.lastSeenAt = Date.now();
        await db.upsertPlayer(auth.player);
      }
      const matches = await db.getMatches();
      const match = matches.find(
        item => item.status === 'LIVE' && String(item.streamerName || '').toLowerCase() === auth.canonicalName.toLowerCase()
      );
      if (match) {
        match.lastHeartbeat = Date.now();
        await db.saveMatch(match);
      }
      return res.json({
        status: 'success',
        tier: auth.tier,
        overlayConfig: auth.overlayConfig,
        match: match || null,
        message: 'Heartbeat OK'
      });
    }

    if (action === 'setWinner') {
      const matches = await db.getMatches();
      let match = null;
      if (data.matchId) {
        match = matches.find(item => item.id === data.matchId);
      } else if (data.streamerName) {
        const sLower = String(data.streamerName).toLowerCase();
        const sortedForStreamer = matches
          .filter(item => String(item.streamerName || '').toLowerCase() === sLower)
          .sort(
            (a, b) =>
              Math.max(Number(b.lastHeartbeat) || 0, Number(b.createdAt) || 0) -
              Math.max(Number(a.lastHeartbeat) || 0, Number(a.createdAt) || 0)
          );
        match =
          sortedForStreamer.find(item => item.status === 'LIVE') ||
          sortedForStreamer[0] ||
          null;
      }
      if (!match || !(await canModifyMatch(match, data))) {
        return res.json({ status: 'error', message: 'Không có quyền hoặc không tìm thấy kèo!' });
      }
      if (!Array.isArray(match.games) || match.games.length === 0) {
        return res.json({ status: 'error', message: 'Chưa có bảng quân của trận đấu! Hãy ấn F2 (Diplomacy) trong game để hiển thị quân trước khi bấm F5/F6.' });
      }

      const rawWinner = String(data.winner || 'PENDING').toUpperCase().trim();
      const winnerVal = ['RED', 'BLUE', 'PENDING'].includes(rawWinner) ? rawWinner : 'PENDING';

      let gameIdx = -1;
      if (data.gameIndex !== undefined && data.gameIndex !== null && data.gameIndex !== '') {
        gameIdx = Number(data.gameIndex);
      } else {
        // Quy tắc nghiêm ngặt: Phím F5 / F6 (hoặc nút +1) chỉ được chấp thuận khi quân của trận đấu đó đã hiển thị
        // và mỗi trận đấu chỉ có duy nhất 1 đội chiến thắng (chỉ chấm cho ván đang PENDING, không tự sinh thêm ván).
        const pendingIdx = match.games.findIndex(
          g => !g.winner || String(g.winner).toUpperCase() === 'PENDING'
        );
        if (pendingIdx === -1) {
          const lastW = match.games[match.games.length - 1].winner === 'RED' ? 'Team Đỏ' : 'Team Xanh';
          return res.json({
            status: 'error',
            message: `Trận #${match.games.length} đã ghi nhận ${lastW} chiến thắng! Mỗi trận đấu chỉ có 1 đội thắng duy nhất — hãy ấn F2 (Diplomacy) trong game để hiển thị quân trận mới trước khi bấm F5/F6.`
          });
        }
        gameIdx = pendingIdx;
      }

      const targetGame = match.games[gameIdx];
      if (!targetGame) {
        return res.json({ status: 'error', message: 'Không tìm thấy trận đấu!' });
      }

      // Kiểm tra bắt buộc quân của cả 2 đội trong trận đấu đó đã được hiển thị hợp lệ
      const hasValidRedCivs = Array.isArray(targetGame.redCivs) && targetGame.redCivs.length > 0 && targetGame.redCivs.every(c => c && c !== '---' && c !== 'Random');
      const hasValidBlueCivs = Array.isArray(targetGame.blueCivs) && targetGame.blueCivs.length > 0 && targetGame.blueCivs.every(c => c && c !== '---' && c !== 'Random');
      if (!hasValidRedCivs || !hasValidBlueCivs) {
        return res.json({
          status: 'error',
          message: 'Quân của trận đấu chưa hiển thị đầy đủ! Hãy ấn F2 (Diplomacy) trong game để hiện bảng quân trước khi bấm F5/F6.'
        });
      }

      targetGame.winner = winnerVal;
      match.lastHeartbeat = Date.now();
      match.status = 'LIVE';

      // Đảm bảo các kèo khác của cùng Streamer được chuyển sang FINISHED để Overlay hiển thị đúng kèo vừa chấm tỉ số
      const sLower = String(match.streamerName || '').toLowerCase();
      for (const other of matches) {
        if (
          other.id !== match.id &&
          other.status === 'LIVE' &&
          String(other.streamerName || '').toLowerCase() === sLower
        ) {
          other.status = 'FINISHED';
          await db.saveMatch(other);
        }
      }

      const rawPlayers = await db.getPlayers();
      const owner = rawPlayers.find(p => p.name.toLowerCase() === sLower);
      match.overlayConfig = db.normalizeOverlayConfig(
        match.overlayConfig || (owner && owner.overlayConfig) || db.DEFAULT_OVERLAY_CONFIG
      );

      const rWinsNow = (match.games || []).filter(g => g && g.winner === 'RED').length;
      const bWinsNow = (match.games || []).filter(g => g && g.winner === 'BLUE').length;
      if (winnerVal === 'RED' || winnerVal === 'BLUE') {
        const sysNow = Date.now();
        const winLabel = winnerVal === 'RED' ? '🔴 TEAM ĐỎ' : '🔵 TEAM XANH';
        const sysEvent = {
          id: 'SYS_' + sysNow + '_' + Math.floor(Math.random() * 1000),
          matchId: match.id,
          streamerName: match.streamerName,
          senderName: 'HỆ THỐNG',
          senderTier: 'SYSTEM',
          type: 'SYSTEM',
          text: `Ván #${gameIdx + 1}: ${winLabel} chiến thắng! Tỷ số hiện tại: ${rWinsNow} - ${bWinsNow}`,
          message: `Ván #${gameIdx + 1}: ${winLabel} chiến thắng! Tỷ số hiện tại: ${rWinsNow} - ${bWinsNow}`,
          createdAt: sysNow,
          timeText: formatShortTimeVN(sysNow)
        };
        if (!Array.isArray(match.chatMessages)) match.chatMessages = [];
        match.chatMessages.push(sysEvent);
        if (match.chatMessages.length > 60) match.chatMessages = match.chatMessages.slice(-60);
      }

      await db.saveMatch(match);
      broadcastUpdate('winner_updated', {
        matchId: match.id,
        streamerName: match.streamerName,
        gameIndex: gameIdx,
        winner: winnerVal,
        match
      });
      return res.json({ status: 'success', gameIndex: gameIdx, winner: winnerVal, match });
    }

    if (action === 'undoLastWinner') {
      const matches = await db.getMatches();
      let match = null;
      if (data.matchId) {
        match = matches.find(item => item.id === data.matchId);
      } else if (data.streamerName) {
        const sLower = String(data.streamerName).toLowerCase();
        const sortedForStreamer = matches
          .filter(item => String(item.streamerName || '').toLowerCase() === sLower)
          .sort(
            (a, b) =>
              Math.max(Number(b.lastHeartbeat) || 0, Number(b.createdAt) || 0) -
              Math.max(Number(a.lastHeartbeat) || 0, Number(a.createdAt) || 0)
          );
        match =
          sortedForStreamer.find(item => item.status === 'LIVE') ||
          sortedForStreamer[0] ||
          null;
      }
      if (!match || !(await canModifyMatch(match, data))) {
        return res.json({ status: 'error', message: 'Không có quyền hoặc không tìm thấy kèo!' });
      }
      if (!Array.isArray(match.games) || match.games.length === 0) {
        return res.json({ status: 'error', message: 'Kèo đấu chưa có trận nào để hoàn tác!' });
      }

      let targetIdx = -1;
      for (let i = match.games.length - 1; i >= 0; i--) {
        const w = String((match.games[i] && match.games[i].winner) || '').toUpperCase();
        if (w === 'RED' || w === 'BLUE') {
          targetIdx = i;
          break;
        }
      }
      if (targetIdx === -1) {
        return res.json({ status: 'error', message: 'Chưa có ván thắng nào được chấm để hoàn tác!' });
      }

      const prevWinner = match.games[targetIdx].winner;
      if (match.games[targetIdx].autoAppendedByHotkey && match.games.length > 1) {
        match.games.splice(targetIdx, 1);
      } else {
        match.games[targetIdx].winner = 'PENDING';
      }
      match.lastHeartbeat = Date.now();
      match.status = 'LIVE';

      const rWinsNow = (match.games || []).filter(g => g && g.winner === 'RED').length;
      const bWinsNow = (match.games || []).filter(g => g && g.winner === 'BLUE').length;
      const sysNow = Date.now();
      const sysEvent = {
        id: 'SYS_' + sysNow + '_' + Math.floor(Math.random() * 1000),
        matchId: match.id,
        streamerName: match.streamerName,
        senderName: 'HỆ THỐNG',
        senderTier: 'SYSTEM',
        type: 'SYSTEM',
        text: `↩️ Đã hoàn tác kết quả Ván #${targetIdx + 1}. Tỷ số hiện tại: ${rWinsNow} - ${bWinsNow}`,
        message: `↩️ Đã hoàn tác kết quả Ván #${targetIdx + 1}. Tỷ số hiện tại: ${rWinsNow} - ${bWinsNow}`,
        createdAt: sysNow,
        timeText: formatShortTimeVN(sysNow)
      };
      if (!Array.isArray(match.chatMessages)) match.chatMessages = [];
      match.chatMessages.push(sysEvent);
      if (match.chatMessages.length > 60) match.chatMessages = match.chatMessages.slice(-60);

      await db.saveMatch(match);
      broadcastUpdate('winner_updated', {
        matchId: match.id,
        streamerName: match.streamerName,
        gameIndex: targetIdx,
        winner: 'PENDING',
        match
      });
      return res.json({
        status: 'success',
        gameIndex: targetIdx,
        previousWinner: prevWinner,
        winner: 'PENDING',
        match,
        message: `↩️ Đã hoàn tác kết quả Ván #${targetIdx + 1} (${prevWinner === 'RED' ? 'Team Đỏ' : 'Team Xanh'})!`
      });
    }

    if (action === 'finishMatch') {
      const matches = await db.getMatches();
      let match = null;
      if (data.matchId) {
        match = matches.find(item => item.id === data.matchId);
      } else if (data.streamerName) {
        match = matches.find(
          item => item.status === 'LIVE' && String(item.streamerName || '').toLowerCase() === String(data.streamerName).toLowerCase()
        );
      }
      if (!match || !(await canModifyMatch(match, data))) {
        return res.json({ status: 'error', message: 'Không có quyền hoặc không tìm thấy kèo!' });
      }
      match.status = 'FINISHED';
      await db.saveMatch(match);
      broadcastUpdate('match_finished', {
        matchId: match.id,
        streamerName: match.streamerName
      });
      return res.json({ status: 'success', match });
    }

    if (action === 'saveMatch') {
      if (!data.match || !data.match.id) {
        return res.json({ status: 'error', message: 'Dữ liệu kèo không hợp lệ!' });
      }
      const matches = await db.getMatches();
      const existing = matches.find(item => item.id === data.match.id);
      if (!existing || !(await canModifyMatch(existing, data))) {
        return res.json({ status: 'error', message: 'Không có quyền chỉnh sửa kèo này!' });
      }
      data.match.lastHeartbeat = Date.now();
      await db.saveMatch(data.match);
      broadcastUpdate('match_saved', {
        matchId: data.match.id,
        streamerName: data.match.streamerName,
        match: data.match
      });
      return res.json({ status: 'success', match: data.match });
    }

    if (action === 'deleteMatches') {
      if (!isAdminAuthorized(data)) {
        return res.json({ status: 'error', message: 'Chỉ Admin mới có quyền xóa!' });
      }
      await db.deleteMatches(data.matchIds || []);
      broadcastUpdate('matches_deleted', { matchIds: data.matchIds || [] });
      return res.json({ status: 'success' });
    }

    if (action === 'adminCleanupMatchHistory') {
      if (!isAdminAuthorized(data)) {
        return res.json({ status: 'error', message: 'Chỉ Admin mới có quyền xóa lịch sử đấu!' });
      }
      const mode = String(data.mode || 'OLDER_THAN_DAYS').toUpperCase().trim();
      const keepLive = data.keepLive !== undefined ? Boolean(data.keepLive) : true;
      const days = Math.max(1, Number(data.days || 7));
      const targetStreamer = String(data.streamerName || '').trim().toLowerCase();
      const now = Date.now();
      const cutoffTs = now - days * 24 * 60 * 60 * 1000;

      const allMatches = await db.getMatches();
      const toDeleteIds = [];
      let modeDesc = '';

      for (const m of allMatches) {
        if (!m || !m.id) continue;
        if (keepLive && m.status === 'LIVE' && mode !== 'ALL_FORCE') {
          continue;
        }
        const mCreated = Number(m.createdAt || m.lastHeartbeat || 0);
        if (mode === 'ALL' || mode === 'ALL_FORCE') {
          toDeleteIds.push(m.id);
          modeDesc = keepLive && mode !== 'ALL_FORCE' ? 'tất cả kèo đã kết thúc' : 'toàn bộ lịch sử kèo đấu';
        } else if (mode === 'FINISHED_ONLY') {
          if (m.status !== 'LIVE') {
            toDeleteIds.push(m.id);
          }
          modeDesc = 'tất cả các kèo đã kết thúc';
        } else if (mode === 'OLDER_THAN_DAYS') {
          if (!mCreated || mCreated < cutoffTs) {
            toDeleteIds.push(m.id);
          }
          modeDesc = `các kèo cũ hơn ${days} ngày trước`;
        } else if (mode === 'BY_STREAMER') {
          if (targetStreamer && String(m.streamerName || '').toLowerCase() === targetStreamer) {
            toDeleteIds.push(m.id);
          }
          modeDesc = `lịch sử đấu của Streamer "${data.streamerName}"`;
        } else if (mode === 'EMPTY_MATCHES') {
          const games = Array.isArray(m.games) ? m.games : [];
          const hasScoredGame = games.some(g => g && (g.winner === 'RED' || g.winner === 'BLUE'));
          if (games.length === 0 || (!hasScoredGame && m.status !== 'LIVE')) {
            toDeleteIds.push(m.id);
          }
          modeDesc = 'các kèo trống / chưa có tỉ số';
        }
      }

      if (toDeleteIds.length > 0) {
        await db.deleteMatches(toDeleteIds);
      }
      if ((mode === 'ALL' && !keepLive) || mode === 'ALL_FORCE') {
        globalChatBuffer.length = 0;
      }

      const remainingMatches = await db.getMatches();
      broadcastUpdate('matches_deleted', { matchIds: toDeleteIds, mode });
      return res.json({
        status: 'success',
        deletedCount: toDeleteIds.length,
        remainingCount: remainingMatches.length,
        matches: remainingMatches,
        message: toDeleteIds.length > 0
          ? `🗑️ Đã xóa ${toDeleteIds.length} kèo đấu (${modeDesc}). Còn lại ${remainingMatches.length} kèo trên hệ thống!`
          : `ℹ️ Không có kèo đấu nào thỏa điều kiện xóa (${modeDesc}).`
      });
    }

    // ==================== ADMIN USER, VIP TIER & SUBSCRIPTION MANAGEMENT ====================
    if (action === 'adminSavePlayer') {
      if (!isAdminAuthorized(data)) {
        return res.json({ status: 'error', message: 'Chỉ Admin mới có quyền quản lý tài khoản!' });
      }
      const pData = data.player || {};
      const name = String(pData.name || '').trim();
      if (!name) {
        return res.json({ status: 'error', message: 'Vui lòng nhập Tên Player!' });
      }
      const now = Date.now();
      const existingPlayers = await db.getPlayers();
      const originalName = String(pData.originalName || name).trim();
      const existing =
        existingPlayers.find(p => p.name.toLowerCase() === originalName.toLowerCase()) ||
        existingPlayers.find(p => p.name.toLowerCase() === name.toLowerCase()) ||
        null;

      // Nếu đổi sang tên mới thì xóa bản ghi tên cũ
      if (existing && existing.name.toLowerCase() !== name.toLowerCase()) {
        await db.deletePlayerByName(existing.name);
      }

      // Xử lý mật khẩu: nếu truyền '******' hoặc rỗng khi sửa User đã có thì giữ nguyên mật khẩu cũ
      const rawPassInput = pData.password !== undefined && pData.password !== null ? String(pData.password).trim() : '';
      const isMaskedPass = /^\*+$/.test(rawPassInput);
      const finalPassword = (!rawPassInput || isMaskedPass)
        ? (existing ? existing.password : '123')
        : rawPassInput;

      // Xử lý ngày tạo (createdAt) và ngày kích hoạt (activatedAt)
      const createdAt = parseFlexibleDateInput(
        pData.createdDate !== undefined ? pData.createdDate : pData.createdAt,
        existing ? existing.createdAt : now
      ) || now;

      const activatedAt = parseFlexibleDateInput(
        pData.activatedDate !== undefined ? pData.activatedDate : pData.activatedAt,
        existing ? existing.activatedAt : createdAt
      ) || now;

      // Xử lý hạn sử dụng (expiresAt)
      let expiresAt = existing ? existing.expiresAt : null;
      if (pData.lifetime === true || String(pData.expiresDate || '').toLowerCase() === 'lifetime') {
        expiresAt = null;
      } else if (pData.durationDays !== undefined && pData.durationDays !== null && pData.durationDays !== '') {
        const days = Number(pData.durationDays);
        expiresAt = days > 0 ? now + days * 24 * 60 * 60 * 1000 : null;
      } else if (pData.expiresDate !== undefined) {
        expiresAt = parseFlexibleDateInput(pData.expiresDate, null);
      } else if (pData.expiresAt !== undefined) {
        expiresAt = parseFlexibleDateInput(pData.expiresAt, null);
      }

      const finalTier = String(pData.tier || (existing ? existing.tier : 'BRONZE')).toUpperCase();
      const finalActive = pData.isActive !== undefined ? Boolean(pData.isActive) : (existing ? existing.isActive : true);
      const finalNote = pData.note !== undefined ? String(pData.note || '').trim() : (existing ? existing.note : '');
      const finalStarsBalance = pData.starsBalance !== undefined && pData.starsBalance !== ''
        ? Number(pData.starsBalance)
        : (existing ? (existing.starsBalance || 0) : 0);
      const finalStarsReceived = pData.starsReceived !== undefined && pData.starsReceived !== ''
        ? Number(pData.starsReceived)
        : (existing ? (existing.starsReceived || 0) : 0);

      const vipHistory = existing && Array.isArray(existing.vipHistory) ? [...existing.vipHistory] : [];
      const starHistory = existing && Array.isArray(existing.starHistory) ? [...existing.starHistory] : [];

      if (!existing) {
        vipHistory.push({
          id: 'VIP_CREATE_' + now,
          action: 'CREATE_USER',
          tier: finalTier,
          previousExpiresAt: null,
          newExpiresAt: expiresAt,
          note: `Tạo tài khoản mới [${TIER_NAMES_VI[finalTier] || finalTier}] — Hạn: ${formatVietnamDateOnly(expiresAt)}`,
          by: 'Admin XO',
          createdAt: now,
          formattedTime: formatVietnamTime(now)
        });
        if (finalStarsBalance > 0) {
          starHistory.push({
            id: 'STAR_INIT_' + now,
            type: 'TOPUP',
            amount: finalStarsBalance,
            balanceAfter: finalStarsBalance,
            note: `Khởi tạo số dư +${finalStarsBalance} ⭐ khi mở tài khoản`,
            by: 'Admin XO',
            createdAt: now,
            formattedTime: formatVietnamTime(now)
          });
        }
      } else {
        const changes = [];
        if (existing.tier !== finalTier) {
          changes.push(`Đổi hạng VIP: ${TIER_NAMES_VI[existing.tier] || existing.tier} → ${TIER_NAMES_VI[finalTier] || finalTier}`);
        }
        if (formatVietnamDateOnly(existing.expiresAt) !== formatVietnamDateOnly(expiresAt)) {
          changes.push(`Hạn SD: ${formatVietnamDateOnly(existing.expiresAt)} → ${formatVietnamDateOnly(expiresAt)}`);
        }
        if (formatVietnamDateOnly(existing.createdAt) !== formatVietnamDateOnly(createdAt)) {
          changes.push(`Ngày tạo: ${formatVietnamDateOnly(existing.createdAt)} → ${formatVietnamDateOnly(createdAt)}`);
        }
        if (existing.password !== finalPassword) {
          changes.push('Đặt lại mật khẩu');
        }
        if (existing.isActive !== finalActive) {
          changes.push(finalActive ? 'Mở khóa tài khoản' : 'Tạm khóa tài khoản');
        }
        if (changes.length > 0) {
          vipHistory.push({
            id: 'VIP_EDIT_' + now + '_' + Math.floor(Math.random() * 1000),
            action: 'ADMIN_EDIT',
            tier: finalTier,
            previousExpiresAt: existing.expiresAt,
            newExpiresAt: expiresAt,
            note: changes.join(' | '),
            by: 'Admin XO',
            createdAt: now,
            formattedTime: formatVietnamTime(now)
          });
        }
        const prevBalance = Number(existing.starsBalance || 0);
        if (finalStarsBalance !== prevBalance) {
          const diff = finalStarsBalance - prevBalance;
          starHistory.push({
            id: 'STAR_ADJ_' + now + '_' + Math.floor(Math.random() * 1000),
            type: diff > 0 ? 'TOPUP' : 'ADMIN_ADJUST',
            amount: diff,
            balanceAfter: finalStarsBalance,
            note: diff > 0 ? `Admin XO nạp thêm +${diff} ⭐` : `Admin XO điều chỉnh ${diff} ⭐`,
            by: 'Admin XO',
            createdAt: now,
            formattedTime: formatVietnamTime(now)
          });
        }
      }

      const saved = await db.upsertPlayer({
        name,
        password: finalPassword,
        tier: finalTier,
        isActive: finalActive,
        activatedAt,
        expiresAt,
        note: finalNote,
        overlayConfig: pData.overlayConfig || (existing ? existing.overlayConfig : db.DEFAULT_OVERLAY_CONFIG),
        friends: pData.friends || (existing ? existing.friends : []),
        starsReceived: finalStarsReceived,
        starsBalance: finalStarsBalance,
        starHistory,
        vipHistory,
        lastSeenAt: existing ? existing.lastSeenAt : now,
        createdAt
      });
      const [rawPlayers, matches] = await Promise.all([db.getPlayers(), db.getMatches()]);
      const players = enrichPlayersWithLiveStatus(rawPlayers, matches);
      broadcastUpdate('players_updated');
      return res.json({
        status: 'success',
        player: saved,
        players,
        message: `Đã lưu thông tin tài khoản "${saved.name}" [${TIER_NAMES_VI[saved.tier]}] (Hạn: ${formatVietnamDateOnly(saved.expiresAt)})!`
      });
    }

    if (action === 'adminResetPassword') {
      if (!isAdminAuthorized(data)) {
        return res.json({ status: 'error', message: 'Chỉ Admin mới có quyền reset mật khẩu!' });
      }
      const targetName = String(data.name || '').trim();
      const newPassword = String(data.newPassword || '123').trim() || '123';
      const players = await db.getPlayers();
      const existing = players.find(p => p.name.toLowerCase() === targetName.toLowerCase());
      if (!existing) {
        return res.json({ status: 'error', message: 'Không tìm thấy tài khoản cần reset mật khẩu!' });
      }
      const now = Date.now();
      existing.password = newPassword;
      existing.vipHistory = Array.isArray(existing.vipHistory) ? existing.vipHistory : [];
      existing.vipHistory.push({
        id: 'VIP_RESET_PW_' + now,
        action: 'RESET_PASS',
        tier: existing.tier,
        previousExpiresAt: existing.expiresAt,
        newExpiresAt: existing.expiresAt,
        note: 'Admin XO đã reset mật khẩu tài khoản',
        by: 'Admin XO',
        createdAt: now,
        formattedTime: formatVietnamTime(now)
      });
      await db.upsertPlayer(existing);
      const [updatedRaw, matches] = await Promise.all([db.getPlayers(), db.getMatches()]);
      const updatedPlayers = enrichPlayersWithLiveStatus(updatedRaw, matches);
      broadcastUpdate('players_updated');
      return res.json({
        status: 'success',
        player: existing,
        players: updatedPlayers,
        message: `🔑 Đã reset mật khẩu cho tài khoản "${existing.name}" thành công!`
      });
    }

    if (action === 'adminTopupStars') {
      if (!isAdminAuthorized(data)) {
        return res.json({ status: 'error', message: 'Chỉ Admin mới có quyền nạp Sao cho User!' });
      }
      const targetName = String(data.name || '').trim();
      const addStars = Number(data.amount || data.stars || 0);
      if (!targetName || isNaN(addStars) || addStars === 0) {
        return res.json({ status: 'error', message: 'Vui lòng nhập số Sao hợp lệ để nạp!' });
      }
      const players = await db.getPlayers();
      const existing = players.find(p => p.name.toLowerCase() === targetName.toLowerCase());
      if (!existing) {
        return res.json({ status: 'error', message: 'Không tìm thấy tài khoản cần nạp Sao!' });
      }
      const now = Date.now();
      existing.starsBalance = Math.max(0, (Number(existing.starsBalance) || 0) + addStars);
      existing.starHistory = Array.isArray(existing.starHistory) ? existing.starHistory : [];
      existing.starHistory.push({
        id: 'TOPUP_' + now + '_' + Math.floor(Math.random() * 1000),
        type: 'TOPUP',
        amount: addStars,
        balanceAfter: existing.starsBalance,
        note: String(data.note || (addStars > 0 ? `Admin XO nạp +${addStars} ⭐` : `Admin XO trừ ${addStars} ⭐`)).trim(),
        by: 'Admin XO',
        createdAt: now,
        formattedTime: formatVietnamTime(now)
      });
      await db.upsertPlayer(existing);
      const [updatedRaw, matches] = await Promise.all([db.getPlayers(), db.getMatches()]);
      const updatedPlayers = enrichPlayersWithLiveStatus(updatedRaw, matches);
      broadcastUpdate('players_updated');
      return res.json({
        status: 'success',
        player: existing,
        players: updatedPlayers,
        message: `🌟 Đã nạp ${addStars > 0 ? '+' + addStars : addStars} Sao cho "${existing.name}" (Số dư mới: ${existing.starsBalance} ⭐)!`
      });
    }

    if (action === 'adminExtendPlayer') {
      if (!isAdminAuthorized(data)) {
        return res.json({ status: 'error', message: 'Chỉ Admin mới có quyền gia hạn!' });
      }
      const targetName = String(data.name || '').trim();
      const players = await db.getPlayers();
      const existing = players.find(p => p.name.toLowerCase() === targetName.toLowerCase());
      if (!existing) {
        return res.json({ status: 'error', message: 'Không tìm thấy tài khoản cần gia hạn!' });
      }

      const now = Date.now();
      const prevExpires = existing.expiresAt;
      if (data.tier && TIER_RANK[String(data.tier).toUpperCase()]) {
        existing.tier = String(data.tier).toUpperCase();
      }
      if (data.lifetime || Number(data.addDays) === 0) {
        existing.expiresAt = null;
      } else if (data.exactExpiresDate !== undefined && data.exactExpiresDate !== '') {
        existing.expiresAt = parseFlexibleDateInput(data.exactExpiresDate, existing.expiresAt);
      } else {
        const addDaysNum = Number(data.addDays || 30);
        const addMs = addDaysNum * 24 * 60 * 60 * 1000;
        const baseTime = (existing.expiresAt && Number(existing.expiresAt) > now) ? Number(existing.expiresAt) : now;
        existing.expiresAt = baseTime + addMs;
      }
      existing.isActive = true;
      if (!existing.activatedAt) existing.activatedAt = now;

      existing.vipHistory = Array.isArray(existing.vipHistory) ? existing.vipHistory : [];
      existing.vipHistory.push({
        id: 'VIP_EXT_' + now + '_' + Math.floor(Math.random() * 1000),
        action: 'EXTEND_VIP',
        tier: existing.tier,
        addDays: (data.lifetime || Number(data.addDays) === 0) ? 0 : Number(data.addDays || 30),
        previousExpiresAt: prevExpires,
        newExpiresAt: existing.expiresAt,
        note: String(
          data.note ||
          ((data.lifetime || Number(data.addDays) === 0)
            ? `Cấp hạn Vĩnh viễn [${TIER_NAMES_VI[existing.tier] || existing.tier}]`
            : `Gia hạn +${data.addDays || 30} ngày [${TIER_NAMES_VI[existing.tier] || existing.tier}] (Hạn mới: ${formatVietnamDateOnly(existing.expiresAt)})`)
        ).trim(),
        by: 'Admin XO',
        createdAt: now,
        formattedTime: formatVietnamTime(now)
      });

      await db.upsertPlayer(existing);
      const [updatedRaw, matches] = await Promise.all([db.getPlayers(), db.getMatches()]);
      const updatedPlayers = enrichPlayersWithLiveStatus(updatedRaw, matches);
      broadcastUpdate('players_updated');
      return res.json({
        status: 'success',
        player: existing,
        players: updatedPlayers,
        message: `Đã gia hạn tài khoản "${existing.name}" (Hạn mới: ${formatVietnamDateOnly(existing.expiresAt)})`
      });
    }

    if (action === 'adminToggleActive') {
      if (!isAdminAuthorized(data)) {
        return res.json({ status: 'error', message: 'Chỉ Admin mới có quyền khóa/mở khóa!' });
      }
      const targetName = String(data.name || '').trim();
      const players = await db.getPlayers();
      const existing = players.find(p => p.name.toLowerCase() === targetName.toLowerCase());
      if (!existing) {
        return res.json({ status: 'error', message: 'Không tìm thấy tài khoản!' });
      }
      existing.isActive = data.isActive !== undefined ? Boolean(data.isActive) : !existing.isActive;
      if (existing.isActive && !existing.activatedAt) {
        existing.activatedAt = Date.now();
      }
      await db.upsertPlayer(existing);
      const [updatedRaw, matches] = await Promise.all([db.getPlayers(), db.getMatches()]);
      const updatedPlayers = enrichPlayersWithLiveStatus(updatedRaw, matches);
      broadcastUpdate('players_updated');
      return res.json({
        status: 'success',
        players: updatedPlayers,
        message: existing.isActive
          ? `Đã KÍCH HOẠT (Active) tài khoản "${existing.name}"!`
          : `Đã TẠM KHÓA tài khoản "${existing.name}"!`
      });
    }

    if (action === 'adminDeletePlayer') {
      if (!isAdminAuthorized(data)) {
        return res.json({ status: 'error', message: 'Chỉ Admin mới có quyền xóa tài khoản!' });
      }
      await db.deletePlayerByName(data.name);
      const [updatedRaw, matches] = await Promise.all([db.getPlayers(), db.getMatches()]);
      const updatedPlayers = enrichPlayersWithLiveStatus(updatedRaw, matches);
      broadcastUpdate('players_updated');
      return res.json({
        status: 'success',
        players: updatedPlayers,
        message: `Đã xóa tài khoản "${data.name}"!`
      });
    }

    if (action === 'savePlayers') {
      if (!isAdminAuthorized(data)) {
        return res.json({ status: 'error', message: 'Chỉ Admin mới có quyền!' });
      }
      const updatedRaw = await db.savePlayers(data.players || []);
      const matches = await db.getMatches();
      const updatedPlayers = enrichPlayersWithLiveStatus(updatedRaw, matches);
      broadcastUpdate('players_updated');
      return res.json({ status: 'success', players: updatedPlayers });
    }

    if (action === 'saveSettings') {
      await db.saveSetting('showCivStats', Boolean(data.showCivStats));
      broadcastUpdate('settings_updated', { showCivStats: Boolean(data.showCivStats) });
      return res.json({ status: 'success' });
    }

    if (action === 'adminUpdateReleaseConfig') {
      if (!isAdminAuthorized(data)) {
        return res.json({ status: 'error', message: 'Chỉ Admin mới có quyền cập nhật phiên bản & link tải Tool!' });
      }
      const currentSettings = await db.getSettings();
      const prevRel = currentSettings.appRelease || db.DEFAULT_APP_RELEASE;
      const newRel = db.normalizeAppRelease({
        latestVersion: data.latestVersion !== undefined ? data.latestVersion : prevRel.latestVersion,
        downloadUrl: data.downloadUrl !== undefined ? data.downloadUrl : prevRel.downloadUrl,
        releaseNotes: data.releaseNotes !== undefined ? data.releaseNotes : prevRel.releaseNotes,
        forceUpdate: data.forceUpdate !== undefined ? Boolean(data.forceUpdate) : prevRel.forceUpdate,
        updatedAt: Date.now()
      });
      await db.saveSetting('appRelease', newRel);
      broadcastUpdate('release_updated', { appRelease: newRel });
      return res.json({
        status: 'success',
        appRelease: newRel,
        message: `🚀 Đã cập nhật phiên bản hệ thống lên v${newRel.latestVersion} và lưu Link Tải Tool!`
      });
    }

    return res.json({ status: 'error', message: 'Invalid action: ' + action });
  } catch (err) {
    console.error('[API POST Error]:', err);
    return res.status(500).json({ status: 'error', message: String(err.message || err) });
  }
});

app.get('/health', (req, res) => {
  res.json({ status: 'ok', db: db.isPostgresActive() ? 'neon_postgres' : 'local_json' });
});

app.get('/download-tool', async (req, res) => {
  try {
    const fs = require('fs');
    const settings = await db.getSettings();
    const rel = settings.appRelease || db.DEFAULT_APP_RELEASE;
    const url = String(rel.downloadUrl || '').trim();
    if (url && /^https?:\/\//i.test(url)) {
      return res.redirect(url);
    }
    const rootExe = path.join(__dirname, '..', 'TOOL_BANG_QUAN_AOE_BY_XO.exe');
    const distExe = path.join(__dirname, '..', 'client', 'dist', 'bangquanaoe.exe');
    if (fs.existsSync(rootExe)) {
      return res.download(rootExe, 'TOOL_BANG_QUAN_AOE_BY_XO.exe');
    }
    if (fs.existsSync(distExe)) {
      return res.download(distExe, 'TOOL_BANG_QUAN_AOE_BY_XO.exe');
    }
    return res.redirect('https://github.com/buiviet2306-arch/aoetrackerv2/releases');
  } catch (e) {
    return res.status(500).send('Không thể tải file cài đặt lúc này.');
  }
});

// Serve static files from public/
const PUBLIC_DIR = path.join(__dirname, '..', 'public');
app.use(express.static(PUBLIC_DIR));

app.get('/overlay', (req, res) => {
  res.sendFile(path.join(PUBLIC_DIR, 'overlay.html'));
});

app.get('/chat-overlay', (req, res) => {
  res.sendFile(path.join(PUBLIC_DIR, 'chat-overlay.html'));
});

app.get('*', (req, res) => {
  res.sendFile(path.join(PUBLIC_DIR, 'index.html'));
});

db.initDb().then(() => {
  app.listen(PORT, () => {
    console.log(`[*] AOE COMMAND CENTER Server đang chạy tại: http://localhost:${PORT}`);
    console.log(`[*] Trang quản lý kèo  : http://localhost:${PORT}`);
    console.log(`[*] Link OBS Bảng Quân : http://localhost:${PORT}/overlay.html?streamer=XO`);
    console.log(`[*] Link OBS Khung Chat: http://localhost:${PORT}/chat-overlay.html?streamer=XO`);
  });
});
