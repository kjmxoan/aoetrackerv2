require('dotenv').config();
const express = require('express');
const cors = require('cors');
const path = require('path');
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

function isAdminAuthorized(data) {
  if (!data) return false;
  if (data.adminPassword && String(data.adminPassword).trim() === ADMIN_PASSWORD) return true;
  if (data.password && String(data.password).trim() === ADMIN_PASSWORD) return true;
  if (data.isAdmin) return true;
  return false;
}

async function checkAndAutoFinishDeadMatches() {
  const matches = await db.getMatches();
  const now = Date.now();
  const FOUR_HOURS = 4 * 60 * 60 * 1000;
  for (const m of matches) {
    if (m.status === 'LIVE' && m.lastHeartbeat && (now - m.lastHeartbeat > FOUR_HOURS)) {
      m.status = 'FINISHED';
      await db.saveMatch(m);
    }
  }
}

async function validatePlayerAccount(name, password) {
  if (!name || password === undefined || password === null) {
    return { valid: false, reason: 'Vui lòng nhập đầy đủ Tên Player và Mật khẩu!' };
  }
  const cleanName = String(name).trim();
  const cleanPass = String(password).trim();
  if (!cleanName || !cleanPass) {
    return { valid: false, reason: 'Vui lòng nhập đầy đủ Tên Player và Mật khẩu!' };
  }

  const isXoAccount = cleanName.toLowerCase() === 'xo';
  const isMasterAdminPass = cleanPass === ADMIN_PASSWORD || cleanPass === '00716441516';

  const players = await db.getPlayers();
  let existing = players.find(p => p.name.toLowerCase() === cleanName.toLowerCase());

  // Tự động khởi tạo tài khoản chủ hệ thống XO nếu chưa có và đăng nhập bằng mật khẩu Admin hoặc 111
  if (!existing && isXoAccount && (isMasterAdminPass || cleanPass === '111')) {
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

  const passwordMatched =
    existing.password === cleanPass ||
    (isXoAccount && (isMasterAdminPass || cleanPass === '111'));

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
  const [rawPlayers, matches, settings] = await Promise.all([
    db.getPlayers(),
    db.getMatches(),
    db.getSettings()
  ]);

  const players = enrichPlayersWithLiveStatus(rawPlayers, matches);

  let currentMatch = null;
  if (streamerFilter) {
    const sf = streamerFilter.trim().toLowerCase();
    currentMatch =
      matches.find(m => m.status === 'LIVE' && String(m.streamerName || '').toLowerCase() === sf) ||
      matches.find(m => String(m.streamerName || '').toLowerCase() === sf) ||
      null;
  }
  if (!currentMatch) {
    currentMatch = matches.find(m => m.status === 'LIVE') || matches[0] || null;
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
    settings
  };
}

async function handleAutoAddGame(data, authResult) {
  const canonicalStreamerName = authResult.canonicalName;
  const playerRecord = authResult.player;
  playerRecord.lastSeenAt = Date.now();
  await db.upsertPlayer(playerRecord);

  const rawRedCivs = Array.isArray(data.redCivs) ? data.redCivs : [];
  const rawBlueCivs = Array.isArray(data.blueCivs) ? data.blueCivs : [];
  const redPlayers = (Array.isArray(data.redPlayers) ? data.redPlayers : [])
    .map(cleanPlayerName)
    .filter(Boolean);
  const bluePlayers = (Array.isArray(data.bluePlayers) ? data.bluePlayers : [])
    .map(cleanPlayerName)
    .filter(Boolean);

  const redCivs = rawRedCivs.map(parseCiv).filter(civ => civ !== 'Random');
  const blueCivs = rawBlueCivs.map(parseCiv).filter(civ => civ !== 'Random');

  if (!redCivs.length && !blueCivs.length) {
    return { added: false, message: 'Bỏ qua: Không nhận diện được quân!' };
  }

  const maxCount = Math.max(redCivs.length, blueCivs.length, redPlayers.length, bluePlayers.length, 1);
  const mode = getMode(maxCount);
  while (redPlayers.length < maxCount) redPlayers.push('Red ' + (redPlayers.length + 1));
  while (bluePlayers.length < maxCount) bluePlayers.push('Blue ' + (bluePlayers.length + 1));
  while (redCivs.length < maxCount) redCivs.push('Random');
  while (blueCivs.length < maxCount) blueCivs.push('Random');

  const redColors = Array.isArray(data.redColors) ? data.redColors : [];
  const blueColors = Array.isArray(data.blueColors) ? data.blueColors : [];
  const streamerName = canonicalStreamerName || data.streamerName || 'Auto Bot';

  const effectiveOverlayCfg = data.overlayConfig
    ? enforceTierOverlayConfig(playerRecord.tier, data.overlayConfig, playerRecord.overlayConfig)
    : db.normalizeOverlayConfig(playerRecord.overlayConfig);

  const matches = await db.getMatches();
  let liveMatch = matches.find(
    item => item.status === 'LIVE' && String(item.streamerName || '').toLowerCase() === streamerName.toLowerCase()
  );

  if (liveMatch && liveMatch.games && liveMatch.games.length) {
    const previous = liveMatch.games[liveMatch.games.length - 1];
    if (
      !data.allowSameCiv &&
      JSON.stringify(previous.redCivs) === JSON.stringify(redCivs) &&
      JSON.stringify(previous.blueCivs) === JSON.stringify(blueCivs)
    ) {
      liveMatch.redTeam = redPlayers;
      liveMatch.blueTeam = bluePlayers;
      liveMatch.redColors = redColors;
      liveMatch.blueColors = blueColors;
      liveMatch.overlayConfig = effectiveOverlayCfg;
      previous.redColors = redColors;
      previous.blueColors = blueColors;
      liveMatch.lastHeartbeat = Date.now();
      await db.saveMatch(liveMatch);
      broadcastUpdate('match_updated', { matchId: liveMatch.id });
      return { added: false, match: liveMatch, message: `Đang ở Trận ${liveMatch.games.length} (Đã đồng bộ tên/màu)` };
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
    redCivs,
    blueCivs,
    redColors,
    blueColors,
    winner: 'PENDING',
    capturedAt: Date.now()
  });

  await db.saveMatch(liveMatch);
  broadcastUpdate('game_added', { matchId: liveMatch.id, gameNumber: liveMatch.games.length });
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
      const auth = await validatePlayerAccount(data.playerName, data.password);
      if (auth.valid && auth.player) {
        auth.player.lastSeenAt = Date.now();
        await db.upsertPlayer(auth.player);
        broadcastUpdate('presence_updated', { playerName: auth.canonicalName });
      }
      return res.json({
        status: auth.valid ? 'success' : 'error',
        isAdmin: Boolean(auth.isAdmin),
        playerName: auth.canonicalName || data.playerName,
        tier: auth.tier || 'BRONZE',
        tierNameVi: TIER_NAMES_VI[auth.tier || 'BRONZE'] || '🥉 Hạng Đồng',
        overlayConfig: auth.overlayConfig || db.DEFAULT_OVERLAY_CONFIG,
        friends: auth.player ? (auth.player.friends || []) : [],
        starsReceived: auth.player ? (auth.player.starsReceived || 0) : 0,
        isActive: auth.player ? auth.player.isActive : false,
        activatedAt: auth.player ? auth.player.activatedAt : null,
        expiresAt: auth.player ? auth.player.expiresAt : null,
        daysLeft: auth.daysLeft !== undefined ? auth.daysLeft : null,
        activatedFormatted: auth.activatedFormatted || '',
        expiresFormatted: auth.expiresFormatted || '',
        message: auth.valid
          ? (auth.isAdmin
            ? `Đăng nhập thành công với quyền QUẢN TRỊ ADMIN XO [${TIER_NAMES_VI[auth.tier] || auth.tier}]!`
            : `Đăng nhập thành công [${TIER_NAMES_VI[auth.tier] || auth.tier}]! (Hạn SD: ${auth.expiresFormatted})`)
          : (auth.reason || 'Đăng nhập thất bại!')
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

    // ==================== KHUNG CHAT BÌNH LUẬN TRẬN ĐẤU & OVERLAY CHAT OBS ====================
    if (action === 'sendChatMessage') {
      const text = String(data.text || '').trim().slice(0, 260);
      if (!text) {
        return res.json({ status: 'error', message: 'Nội dung bình luận trống!' });
      }
      const senderName = String(data.senderName || 'Khán giả').trim().slice(0, 32) || 'Khán giả';
      const rawPlayers = await db.getPlayers();
      const senderPlayer = rawPlayers.find(p => p.name.toLowerCase() === senderName.toLowerCase());
      const senderTier = senderPlayer ? senderPlayer.tier : (data.senderTier || 'VIEWER');

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

      const streamerName = (targetMatch && targetMatch.streamerName) || data.streamerName || 'XO';
      const now = Date.now();
      const msgObj = {
        id: 'MSG_' + now + '_' + Math.floor(Math.random() * 1000),
        matchId: targetMatch ? targetMatch.id : null,
        streamerName,
        senderName: senderPlayer ? senderPlayer.name : senderName,
        senderTier,
        text,
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

    // ==================== HIỆU ỨNG TẶNG SAO (STAR GIFT EFFECT TRÊN LIVESTREAM) ====================
    if (action === 'sendStarGift') {
      const senderName = String(data.senderName || 'Fan AOE').trim().slice(0, 32) || 'Fan AOE';
      const starCount = Math.max(1, Math.min(9999, Number(data.starCount) || 1));
      const cheerText = String(data.message || 'Đánh hay quá! Tặng sao cổ vũ!').trim().slice(0, 160);

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

      let totalStreamerStars = starCount;
      if (streamerObj) {
        streamerObj.starsReceived = (Number(streamerObj.starsReceived) || 0) + starCount;
        totalStreamerStars = streamerObj.starsReceived;
        await db.upsertPlayer(streamerObj);
      }

      const now = Date.now();
      const starChatObj = {
        id: 'STAR_' + now + '_' + Math.floor(Math.random() * 1000),
        matchId: targetMatch ? targetMatch.id : null,
        streamerName,
        senderName,
        senderTier: 'STAR',
        starCount,
        text: `đã tặng ${starCount} ⭐ cho ${streamerName} — "${cheerText}"`,
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
        message: cheerText,
        totalMatchStars,
        totalStreamerStars,
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
        message: `🌟 Đã gửi tặng ${starCount} Sao tới Livestream của ${streamerName}!`
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
        match = matches.find(
          item => item.status === 'LIVE' && String(item.streamerName || '').toLowerCase() === String(data.streamerName).toLowerCase()
        );
      }
      if (!match || !(await canModifyMatch(match, data))) {
        return res.json({ status: 'error', message: 'Không có quyền hoặc không tìm thấy kèo!' });
      }
      const gameIdx =
        data.gameIndex !== undefined && data.gameIndex !== null
          ? Number(data.gameIndex)
          : (match.games ? match.games.length - 1 : -1);

      if (!match.games || !match.games[gameIdx]) {
        return res.json({ status: 'error', message: 'Không tìm thấy trận đấu!' });
      }
      match.games[gameIdx].winner = data.winner;
      match.lastHeartbeat = Date.now();
      await db.saveMatch(match);
      broadcastUpdate('winner_updated', { matchId: match.id, gameIndex: gameIdx, winner: data.winner });
      return res.json({ status: 'success', match });
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
      broadcastUpdate('match_finished', { matchId: match.id });
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
      await db.saveMatch(data.match);
      broadcastUpdate('match_saved', { matchId: data.match.id });
      return res.json({ status: 'success' });
    }

    if (action === 'deleteMatches') {
      if (!isAdminAuthorized(data)) {
        return res.json({ status: 'error', message: 'Chỉ Admin mới có quyền xóa!' });
      }
      await db.deleteMatches(data.matchIds || []);
      broadcastUpdate('matches_deleted', { matchIds: data.matchIds || [] });
      return res.json({ status: 'success' });
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
      let expiresAt = pData.expiresAt !== undefined && pData.expiresAt !== null && pData.expiresAt !== ''
        ? Number(pData.expiresAt)
        : null;

      if (pData.durationDays !== undefined && pData.durationDays !== null && pData.durationDays !== '') {
        const days = Number(pData.durationDays);
        expiresAt = days > 0 ? now + days * 24 * 60 * 60 * 1000 : null;
      }

      const saved = await db.upsertPlayer({
        name,
        password: String(pData.password || '123').trim(),
        tier: String(pData.tier || 'BRONZE').toUpperCase(),
        isActive: pData.isActive !== undefined ? Boolean(pData.isActive) : true,
        activatedAt: pData.activatedAt ? Number(pData.activatedAt) : now,
        expiresAt,
        note: String(pData.note || '').trim(),
        overlayConfig: pData.overlayConfig || db.DEFAULT_OVERLAY_CONFIG,
        friends: pData.friends || [],
        starsReceived: pData.starsReceived || 0,
        lastSeenAt: pData.lastSeenAt || 0,
        createdAt: pData.createdAt ? Number(pData.createdAt) : now
      });
      const [rawPlayers, matches] = await Promise.all([db.getPlayers(), db.getMatches()]);
      const players = enrichPlayersWithLiveStatus(rawPlayers, matches);
      broadcastUpdate('players_updated');
      return res.json({ status: 'success', player: saved, players, message: `Đã lưu tài khoản "${saved.name}" [${TIER_NAMES_VI[saved.tier]}]!` });
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
      if (data.lifetime || Number(data.addDays) === 0) {
        existing.expiresAt = null;
      } else {
        const addMs = Number(data.addDays || 30) * 24 * 60 * 60 * 1000;
        const baseTime = (existing.expiresAt && Number(existing.expiresAt) > now) ? Number(existing.expiresAt) : now;
        existing.expiresAt = baseTime + addMs;
      }
      existing.isActive = true;
      if (!existing.activatedAt) existing.activatedAt = now;

      await db.upsertPlayer(existing);
      const [updatedRaw, matches] = await Promise.all([db.getPlayers(), db.getMatches()]);
      const updatedPlayers = enrichPlayersWithLiveStatus(updatedRaw, matches);
      broadcastUpdate('players_updated');
      return res.json({
        status: 'success',
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

    return res.json({ status: 'error', message: 'Invalid action: ' + action });
  } catch (err) {
    console.error('[API POST Error]:', err);
    return res.status(500).json({ status: 'error', message: String(err.message || err) });
  }
});

app.get('/health', (req, res) => {
  res.json({ status: 'ok', db: db.isPostgresActive() ? 'neon_postgres' : 'local_json' });
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
