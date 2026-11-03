const { Pool } = require('pg');
const fs = require('fs');
const path = require('path');

const DATABASE_URL = process.env.DATABASE_URL || '';
const LOCAL_DB_PATH = path.join(__dirname, '..', 'local_db.json');

let pool = null;
let usePostgres = false;

if (DATABASE_URL && DATABASE_URL.startsWith('postgres')) {
  pool = new Pool({
    connectionString: DATABASE_URL,
    ssl: { rejectUnauthorized: false },
    max: 10,
    idleTimeoutMillis: 30000
  });
  usePostgres = true;
}

const VALID_TIERS = ['BRONZE', 'SILVER', 'GOLD', 'DIAMOND'];

const DEFAULT_OVERLAY_CONFIG = {
  targetScore: 100,
  marqueeMode: 'ALL', // 'ALL' | 'TOTAL_ONLY' | 'PER_PLAYER' | 'CUSTOM' | 'OFF'
  customMarqueeText: '',
  showDateCorner: true,
  cModeEnabled: false,
  cTargetWins: 3,
  showIdlePreview: true
};

const DEFAULT_APP_RELEASE = {
  latestVersion: '5.3',
  downloadUrl: '/download-tool',
  releaseNotes: 'Cập nhật giao diện Wood-Gold mới, Màn hình Đăng nhập riêng, Tab Cài đặt VIP góc phải và tối ưu Bảng Điều Khiển.',
  forceUpdate: false,
  updatedAt: Date.now()
};

function normalizeAppRelease(rawRel) {
  const rel = rawRel && typeof rawRel === 'object' ? rawRel : {};
  return {
    latestVersion: String(rel.latestVersion || DEFAULT_APP_RELEASE.latestVersion).trim(),
    downloadUrl: String(rel.downloadUrl || DEFAULT_APP_RELEASE.downloadUrl).trim() || '/download-tool',
    releaseNotes: String(rel.releaseNotes !== undefined ? rel.releaseNotes : DEFAULT_APP_RELEASE.releaseNotes).trim(),
    forceUpdate: Boolean(rel.forceUpdate),
    updatedAt: Number(rel.updatedAt || Date.now())
  };
}

const DEFAULT_STATE = {
  players: [
    {
      name: 'XO',
      password: '111',
      tier: 'DIAMOND',
      isActive: true,
      activatedAt: Date.now(),
      expiresAt: null,
      note: 'Admin / Chủ hệ thống (Full VIP Kim Cương)',
      overlayConfig: { ...DEFAULT_OVERLAY_CONFIG },
      friends: [],
      starsReceived: 0,
      starsBalance: 9999,
      starHistory: [],
      vipHistory: [],
      lastSeenAt: Date.now(),
      createdAt: Date.now()
    }
  ],
  matches: [],
  settings: {
    showCivStats: true,
    appRelease: { ...DEFAULT_APP_RELEASE }
  }
};

function normalizeOverlayConfig(rawCfg) {
  const cfg = rawCfg && typeof rawCfg === 'object' ? rawCfg : {};
  return {
    targetScore: cfg.targetScore !== undefined && cfg.targetScore !== '' ? Number(cfg.targetScore) : 100,
    marqueeMode: ['ALL', 'TOTAL_ONLY', 'PER_PLAYER', 'CUSTOM', 'OFF'].includes(cfg.marqueeMode) ? cfg.marqueeMode : 'ALL',
    customMarqueeText: String(cfg.customMarqueeText || '').trim(),
    showDateCorner: cfg.showDateCorner !== undefined ? Boolean(cfg.showDateCorner) : true,
    cModeEnabled: cfg.cModeEnabled !== undefined ? Boolean(cfg.cModeEnabled) : false,
    cTargetWins: cfg.cTargetWins && Number(cfg.cTargetWins) > 0 ? Number(cfg.cTargetWins) : 3,
    showIdlePreview: cfg.showIdlePreview !== undefined ? Boolean(cfg.showIdlePreview) : true
  };
}

function normalizePlayerRecord(raw) {
  const now = Date.now();
  const name = String(raw.name || '').trim();
  const defaultTier = name.toLowerCase() === 'xo' ? 'DIAMOND' : 'BRONZE';
  const rawTier = String(raw.tier || defaultTier).toUpperCase().trim();
  const tier = VALID_TIERS.includes(rawTier) ? rawTier : defaultTier;

  let rawOverlay = raw.overlayConfig || raw.overlay_config || {};
  if (typeof rawOverlay === 'string') {
    try {
      rawOverlay = JSON.parse(rawOverlay);
    } catch (e) {
      rawOverlay = {};
    }
  }

  let rawSocial = raw.socialData || raw.social_data || {};
  if (typeof rawSocial === 'string') {
    try {
      rawSocial = JSON.parse(rawSocial);
    } catch (e) {
      rawSocial = {};
    }
  }

  const friendsRaw = Array.isArray(raw.friends)
    ? raw.friends
    : (Array.isArray(rawSocial.friends) ? rawSocial.friends : []);
  const friends = Array.from(new Set(friendsRaw.map(f => String(f || '').trim()).filter(Boolean)));
  const starsReceived = Number(raw.starsReceived ?? rawSocial.starsReceived ?? 0) || 0;
  const starsBalance = Number(raw.starsBalance ?? rawSocial.starsBalance ?? 0) || 0;
  const starHistoryRaw = Array.isArray(raw.starHistory)
    ? raw.starHistory
    : (Array.isArray(rawSocial.starHistory) ? rawSocial.starHistory : []);
  const vipHistoryRaw = Array.isArray(raw.vipHistory)
    ? raw.vipHistory
    : (Array.isArray(rawSocial.vipHistory) ? rawSocial.vipHistory : []);
  const lastSeenAt = Number(raw.lastSeenAt ?? rawSocial.lastSeenAt ?? raw.createdAt ?? raw.created_at ?? 0) || 0;

  return {
    name,
    password: String(raw.password !== undefined && raw.password !== null ? raw.password : '123').trim(),
    tier,
    isActive: raw.isActive !== undefined ? Boolean(raw.isActive) : (raw.is_active !== undefined ? Boolean(raw.is_active) : true),
    activatedAt: Number(raw.activatedAt || raw.activated_at || raw.createdAt || raw.created_at || now),
    expiresAt: (raw.expiresAt !== undefined && raw.expiresAt !== null && raw.expiresAt !== '' && Number(raw.expiresAt) > 0)
      ? Number(raw.expiresAt)
      : ((raw.expires_at !== undefined && raw.expires_at !== null && raw.expires_at !== '' && Number(raw.expires_at) > 0)
        ? Number(raw.expires_at)
        : null),
    note: String(raw.note || '').trim(),
    overlayConfig: normalizeOverlayConfig(rawOverlay),
    friends,
    starsReceived,
    starsBalance,
    starHistory: starHistoryRaw.slice(-100),
    vipHistory: vipHistoryRaw.slice(-100),
    lastSeenAt,
    createdAt: Number(raw.createdAt || raw.created_at || now)
  };
}

function readLocalState() {
  try {
    if (!fs.existsSync(LOCAL_DB_PATH)) {
      fs.writeFileSync(LOCAL_DB_PATH, JSON.stringify(DEFAULT_STATE, null, 2), 'utf-8');
      return JSON.parse(JSON.stringify(DEFAULT_STATE));
    }
    const state = JSON.parse(fs.readFileSync(LOCAL_DB_PATH, 'utf-8'));
    state.players = (state.players || []).map(normalizePlayerRecord);
    return state;
  } catch (err) {
    console.error('[DB] Error reading local_db.json:', err.message);
    return JSON.parse(JSON.stringify(DEFAULT_STATE));
  }
}

function writeLocalState(state) {
  try {
    fs.writeFileSync(LOCAL_DB_PATH, JSON.stringify(state, null, 2), 'utf-8');
  } catch (err) {
    console.error('[DB] Error writing local_db.json:', err.message);
  }
}

async function initDb() {
  if (!usePostgres) {
    console.log('[DB] DATABASE_URL chưa được cấu hình -> Sử dụng local_db.json (chế độ chạy thử cục bộ).');
    readLocalState();
    return;
  }

  try {
    await pool.query(`
      CREATE TABLE IF NOT EXISTS players (
        name TEXT PRIMARY KEY,
        password TEXT NOT NULL,
        tier TEXT DEFAULT 'BRONZE',
        is_active BOOLEAN DEFAULT TRUE,
        activated_at BIGINT DEFAULT (EXTRACT(EPOCH FROM NOW()) * 1000)::BIGINT,
        expires_at BIGINT NULL,
        note TEXT DEFAULT '',
        overlay_config JSONB DEFAULT '{}'::jsonb,
        social_data JSONB DEFAULT '{}'::jsonb,
        created_at BIGINT DEFAULT (EXTRACT(EPOCH FROM NOW()) * 1000)::BIGINT
      );

      ALTER TABLE players ADD COLUMN IF NOT EXISTS tier TEXT DEFAULT 'BRONZE';
      ALTER TABLE players ADD COLUMN IF NOT EXISTS is_active BOOLEAN DEFAULT TRUE;
      ALTER TABLE players ADD COLUMN IF NOT EXISTS activated_at BIGINT DEFAULT (EXTRACT(EPOCH FROM NOW()) * 1000)::BIGINT;
      ALTER TABLE players ADD COLUMN IF NOT EXISTS expires_at BIGINT NULL;
      ALTER TABLE players ADD COLUMN IF NOT EXISTS note TEXT DEFAULT '';
      ALTER TABLE players ADD COLUMN IF NOT EXISTS overlay_config JSONB DEFAULT '{}'::jsonb;
      ALTER TABLE players ADD COLUMN IF NOT EXISTS social_data JSONB DEFAULT '{}'::jsonb;
      ALTER TABLE players ADD COLUMN IF NOT EXISTS created_at BIGINT DEFAULT (EXTRACT(EPOCH FROM NOW()) * 1000)::BIGINT;

      CREATE TABLE IF NOT EXISTS matches (
        id TEXT PRIMARY KEY,
        streamer_name TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'LIVE',
        created_at BIGINT NOT NULL,
        last_heartbeat BIGINT NOT NULL,
        data JSONB NOT NULL,
        updated_at TIMESTAMPTZ DEFAULT NOW()
      );

      CREATE INDEX IF NOT EXISTS idx_matches_created_at ON matches (created_at DESC);
      CREATE INDEX IF NOT EXISTS idx_matches_status_streamer ON matches (status, streamer_name);

      CREATE TABLE IF NOT EXISTS settings (
        key TEXT PRIMARY KEY,
        value JSONB NOT NULL
      );
    `);

    const { rows: playerCount } = await pool.query('SELECT COUNT(*)::INT AS cnt FROM players');
    if (playerCount[0].cnt === 0) {
      const now = Date.now();
      await pool.query(
        `INSERT INTO players (name, password, tier, is_active, activated_at, expires_at, note, overlay_config, social_data, created_at)
         VALUES ($1, $2, 'DIAMOND', TRUE, $3, NULL, $4, $5::jsonb, $6::jsonb, $3)
         ON CONFLICT (name) DO NOTHING`,
        ['XO', '111', now, 'Admin / Chủ hệ thống (VIP Kim Cương)', JSON.stringify(DEFAULT_OVERLAY_CONFIG), JSON.stringify({ friends: [], starsReceived: 0, lastSeenAt: now })]
      );
    } else {
      await pool.query(`UPDATE players SET tier = 'DIAMOND' WHERE LOWER(name) = 'xo' AND (tier IS NULL OR tier = 'BRONZE')`);
    }

    await pool.query(
      `INSERT INTO settings (key, value) VALUES ('showCivStats', 'true'::jsonb) ON CONFLICT (key) DO NOTHING`
    );

    console.log('[DB] Đã kết nối & khởi tạo bảng trên Neon PostgreSQL thành công!');
  } catch (err) {
    console.error('[DB] Lỗi kết nối Neon PostgreSQL, chuyển sang chế độ dự phòng local_db.json:', err.message);
    usePostgres = false;
    readLocalState();
  }
}

async function getPlayers() {
  if (!usePostgres) {
    return (readLocalState().players || []).map(normalizePlayerRecord);
  }
  const { rows } = await pool.query(
    `SELECT name, password, tier, is_active, activated_at, expires_at, note, overlay_config, social_data, created_at
     FROM players
     ORDER BY created_at ASC, name ASC`
  );
  return rows.map(normalizePlayerRecord);
}

async function savePlayers(players) {
  const cleanPlayers = (Array.isArray(players) ? players : [])
    .map(normalizePlayerRecord)
    .filter(p => p.name.length > 0);

  if (!usePostgres) {
    const state = readLocalState();
    state.players = cleanPlayers;
    writeLocalState(state);
    return cleanPlayers;
  }

  const client = await pool.connect();
  try {
    await client.query('BEGIN');
    await client.query('DELETE FROM players');
    for (const p of cleanPlayers) {
      const socialJson = JSON.stringify({
        friends: p.friends || [],
        starsReceived: p.starsReceived || 0,
        starsBalance: p.starsBalance || 0,
        starHistory: p.starHistory || [],
        vipHistory: p.vipHistory || [],
        lastSeenAt: p.lastSeenAt || 0
      });
      await client.query(
        `INSERT INTO players (name, password, tier, is_active, activated_at, expires_at, note, overlay_config, social_data, created_at)
         VALUES ($1, $2, $3, $4, $5, $6, $7, $8::jsonb, $9::jsonb, $10)
         ON CONFLICT (name) DO UPDATE SET
           password = EXCLUDED.password,
           tier = EXCLUDED.tier,
           is_active = EXCLUDED.is_active,
           activated_at = EXCLUDED.activated_at,
           expires_at = EXCLUDED.expires_at,
           note = EXCLUDED.note,
           overlay_config = EXCLUDED.overlay_config,
           social_data = EXCLUDED.social_data,
           created_at = EXCLUDED.created_at`,
        [p.name, p.password, p.tier, p.isActive, p.activatedAt, p.expiresAt, p.note, JSON.stringify(p.overlayConfig), socialJson, p.createdAt]
      );
    }
    await client.query('COMMIT');
  } catch (err) {
    await client.query('ROLLBACK');
    throw err;
  } finally {
    client.release();
  }
  return cleanPlayers;
}

async function upsertPlayer(playerObj) {
  const p = normalizePlayerRecord(playerObj);
  if (!p.name) throw new Error('Tên Player không hợp lệ');

  if (!usePostgres) {
    const state = readLocalState();
    const idx = state.players.findIndex(item => item.name.toLowerCase() === p.name.toLowerCase());
    if (idx >= 0) {
      p.name = state.players[idx].name;
      if (!playerObj.createdAt && !playerObj.created_at) {
        p.createdAt = state.players[idx].createdAt || p.createdAt;
      }
      state.players[idx] = p;
    } else {
      state.players.push(p);
    }
    writeLocalState(state);
    return p;
  }

  const socialJson = JSON.stringify({
    friends: p.friends || [],
    starsReceived: p.starsReceived || 0,
    starsBalance: p.starsBalance || 0,
    starHistory: p.starHistory || [],
    vipHistory: p.vipHistory || [],
    lastSeenAt: p.lastSeenAt || 0
  });

  await pool.query(
    `INSERT INTO players (name, password, tier, is_active, activated_at, expires_at, note, overlay_config, social_data, created_at)
     VALUES ($1, $2, $3, $4, $5, $6, $7, $8::jsonb, $9::jsonb, $10)
     ON CONFLICT (name) DO UPDATE SET
       password = EXCLUDED.password,
       tier = EXCLUDED.tier,
       is_active = EXCLUDED.is_active,
       activated_at = EXCLUDED.activated_at,
       expires_at = EXCLUDED.expires_at,
       note = EXCLUDED.note,
       overlay_config = EXCLUDED.overlay_config,
       social_data = EXCLUDED.social_data,
       created_at = EXCLUDED.created_at`,
    [p.name, p.password, p.tier, p.isActive, p.activatedAt, p.expiresAt, p.note, JSON.stringify(p.overlayConfig), socialJson, p.createdAt]
  );
  return p;
}

async function deletePlayerByName(name) {
  const cleanName = String(name || '').trim();
  if (!cleanName) return;
  if (!usePostgres) {
    const state = readLocalState();
    state.players = (state.players || []).filter(p => p.name.toLowerCase() !== cleanName.toLowerCase());
    writeLocalState(state);
    return;
  }
  await pool.query('DELETE FROM players WHERE LOWER(name) = LOWER($1)', [cleanName]);
}

async function getMatches() {
  if (!usePostgres) {
    const matches = readLocalState().matches || [];
    return matches.sort((a, b) => (b.createdAt || 0) - (a.createdAt || 0));
  }
  const { rows } = await pool.query('SELECT data FROM matches ORDER BY created_at DESC');
  return rows.map(r => r.data);
}

async function saveMatch(match) {
  if (!match || !match.id) return;
  if (!usePostgres) {
    const state = readLocalState();
    const idx = state.matches.findIndex(m => m.id === match.id);
    if (idx >= 0) {
      state.matches[idx] = match;
    } else {
      state.matches.unshift(match);
    }
    writeLocalState(state);
    return;
  }

  await pool.query(
    `INSERT INTO matches (id, streamer_name, status, created_at, last_heartbeat, data, updated_at)
     VALUES ($1, $2, $3, $4, $5, $6, NOW())
     ON CONFLICT (id) DO UPDATE SET
       streamer_name = EXCLUDED.streamer_name,
       status = EXCLUDED.status,
       last_heartbeat = EXCLUDED.last_heartbeat,
       data = EXCLUDED.data,
       updated_at = NOW()`,
    [
      match.id,
      match.streamerName || 'Auto Bot',
      match.status || 'LIVE',
      match.createdAt || Date.now(),
      match.lastHeartbeat || Date.now(),
      JSON.stringify(match)
    ]
  );
}

async function deleteMatches(matchIds) {
  if (!Array.isArray(matchIds) || matchIds.length === 0) return;
  if (!usePostgres) {
    const state = readLocalState();
    state.matches = state.matches.filter(m => !matchIds.includes(m.id));
    writeLocalState(state);
    return;
  }
  await pool.query('DELETE FROM matches WHERE id = ANY($1::text[])', [matchIds]);
}

async function getSettings() {
  if (!usePostgres) {
    const rawSettings = readLocalState().settings || { showCivStats: true };
    rawSettings.appRelease = normalizeAppRelease(rawSettings.appRelease);
    return rawSettings;
  }
  const { rows } = await pool.query('SELECT key, value FROM settings');
  const settings = { showCivStats: true, appRelease: { ...DEFAULT_APP_RELEASE } };
  for (const r of rows) {
    settings[r.key] = r.value;
  }
  settings.appRelease = normalizeAppRelease(settings.appRelease);
  return settings;
}

async function saveSetting(key, value) {
  if (!usePostgres) {
    const state = readLocalState();
    state.settings = state.settings || {};
    state.settings[key] = value;
    writeLocalState(state);
    return;
  }
  await pool.query(
    `INSERT INTO settings (key, value) VALUES ($1, $2::jsonb)
     ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value`,
    [key, JSON.stringify(value)]
  );
}

module.exports = {
  initDb,
  getPlayers,
  savePlayers,
  upsertPlayer,
  deletePlayerByName,
  getMatches,
  saveMatch,
  deleteMatches,
  getSettings,
  saveSetting,
  normalizeOverlayConfig,
  normalizeAppRelease,
  DEFAULT_OVERLAY_CONFIG,
  DEFAULT_APP_RELEASE,
  isPostgresActive: () => usePostgres
};
