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

// Server-Sent Events (SSE) clients for instant OBS Overlay & Web updates
const sseClients = new Set();

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

function formatVietnamDateOnly(ts) {
  if (!ts || Number(ts) <= 0) return 'Vĩnh viễn';
  const now = new Date(Number(ts));
  const vnTime = new Date(now.toLocaleString('en-US', { timeZone: 'Asia/Ho_Chi_Minh' }));
  const pad = v => String(v).padStart(2, '0');
  return `${pad(vnTime.getDate())}/${pad(vnTime.getMonth() + 1)}/${vnTime.getFullYear()}`;
}

function isAdminAuthorized(data) {
  if (!data || !data.isAdmin) return false;
  if (data.adminPassword && String(data.adminPassword).trim() === ADMIN_PASSWORD) return true;
  return Boolean(data.isAdmin && !data.adminPassword);
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

  const players = await db.getPlayers();
  const existing = players.find(p => p.name.toLowerCase() === cleanName.toLowerCase());

  if (!existing) {
    return {
      valid: false,
      reason: `Tài khoản "${cleanName}" chưa được cấp! Vui lòng liên hệ Admin XO để tạo tài khoản.`
    };
  }

  if (existing.password !== cleanPass) {
    return { valid: false, reason: 'Mật khẩu không đúng!' };
  }

  if (existing.isActive === false) {
    return {
      valid: false,
      reason: `Tài khoản "${existing.name}" hiện đang bị TẠM KHÓA! Vui lòng liên hệ Admin XO để mở khóa.`
    };
  }

  const now = Date.now();
  if (existing.expiresAt && Number(existing.expiresAt) > 0 && now > Number(existing.expiresAt)) {
    return {
      valid: false,
      reason: `Tài khoản "${existing.name}" đã HẾT HẠN sử dụng từ ngày ${formatVietnamDateOnly(existing.expiresAt)}! Vui lòng liên hệ Admin XO để gia hạn.`
    };
  }

  const daysLeft = existing.expiresAt && Number(existing.expiresAt) > 0
    ? Math.max(0, Math.ceil((Number(existing.expiresAt) - now) / (24 * 60 * 60 * 1000)))
    : null;

  return {
    valid: true,
    canonicalName: existing.name,
    player: existing,
    tier: existing.tier || 'BRONZE',
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

async function getInitialDataPayload(streamerFilter = '') {
  await checkAndAutoFinishDeadMatches();
  const [players, matches, settings] = await Promise.all([
    db.getPlayers(),
    db.getMatches(),
    db.getSettings()
  ]);

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

  // Gắn kèm overlayConfig của Streamer nếu match chưa có
  if (currentMatch) {
    const owner = players.find(p => p.name.toLowerCase() === String(currentMatch.streamerName || '').toLowerCase());
    currentMatch.overlayConfig = db.normalizeOverlayConfig(
      currentMatch.overlayConfig || (owner && owner.overlayConfig) || db.DEFAULT_OVERLAY_CONFIG
    );
  }

  return {
    status: 'ok',
    databaseMode: db.isPostgresActive() ? 'neon_postgres' : 'local_json',
    players,
    matches,
    currentMatch,
    settings
  };
}

async function handleAutoAddGame(data, authResult) {
  const canonicalStreamerName = authResult.canonicalName;
  const playerRecord = authResult.player;
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
      return res.json({
        status: auth.valid ? 'success' : 'error',
        playerName: auth.canonicalName || data.playerName,
        tier: auth.tier || 'BRONZE',
        tierNameVi: TIER_NAMES_VI[auth.tier || 'BRONZE'] || '🥉 Hạng Đồng',
        overlayConfig: auth.overlayConfig || db.DEFAULT_OVERLAY_CONFIG,
        isActive: auth.player ? auth.player.isActive : false,
        activatedAt: auth.player ? auth.player.activatedAt : null,
        expiresAt: auth.player ? auth.player.expiresAt : null,
        daysLeft: auth.daysLeft !== undefined ? auth.daysLeft : null,
        activatedFormatted: auth.activatedFormatted || '',
        expiresFormatted: auth.expiresFormatted || '',
        message: auth.valid
          ? `Đăng nhập thành công [${TIER_NAMES_VI[auth.tier] || auth.tier}]! (Hạn SD: ${auth.expiresFormatted})`
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
      const auth = await validatePlayerAccount(data.streamerName, data.password);
      if (!auth.valid && !isAdminAuthorized(data)) {
        return res.json({ status: 'error', message: auth.reason || 'Xác thực thất bại!' });
      }
      const players = await db.getPlayers();
      const targetName = auth.valid ? auth.canonicalName : String(data.streamerName || 'XO').trim();
      const playerObj = players.find(p => p.name.toLowerCase() === targetName.toLowerCase());
      const effectiveTier = isAdminAuthorized(data) ? 'DIAMOND' : (playerObj ? playerObj.tier : 'BRONZE');

      const sanitizedCfg = enforceTierOverlayConfig(
        effectiveTier,
        data.overlayConfig,
        playerObj ? playerObj.overlayConfig : db.DEFAULT_OVERLAY_CONFIG
      );

      if (playerObj) {
        playerObj.overlayConfig = sanitizedCfg;
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

    if (action === 'heartbeat') {
      const auth = await validatePlayerAccount(data.streamerName, data.password);
      if (!auth.valid) {
        return res.json({ status: 'error', message: auth.reason || 'Xác thực thất bại!' });
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
        createdAt: pData.createdAt ? Number(pData.createdAt) : now
      });
      const players = await db.getPlayers();
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
      const updatedPlayers = await db.getPlayers();
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
      const updatedPlayers = await db.getPlayers();
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
      const updatedPlayers = await db.getPlayers();
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
      const updatedPlayers = await db.savePlayers(data.players || []);
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

app.get('*', (req, res) => {
  res.sendFile(path.join(PUBLIC_DIR, 'index.html'));
});

db.initDb().then(() => {
  app.listen(PORT, () => {
    console.log(`[*] AOE COMMAND CENTER Server đang chạy tại: http://localhost:${PORT}`);
    console.log(`[*] Trang quản lý kèo: http://localhost:${PORT}`);
    console.log(`[*] Link OBS Overlay : http://localhost:${PORT}/overlay.html?streamer=XO`);
  });
});
