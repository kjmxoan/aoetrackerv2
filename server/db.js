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

const DEFAULT_STATE = {
  players: [
    {
      name: 'XO',
      password: '111',
      isActive: true,
      activatedAt: Date.now(),
      expiresAt: null,
      note: 'Admin / Chủ hệ thống',
      createdAt: Date.now()
    }
  ],
  matches: [],
  settings: {
    showCivStats: true
  }
};

function normalizePlayerRecord(raw) {
  const now = Date.now();
  return {
    name: String(raw.name || '').trim(),
    password: String(raw.password !== undefined && raw.password !== null ? raw.password : '123').trim(),
    isActive: raw.isActive !== undefined ? Boolean(raw.isActive) : (raw.is_active !== undefined ? Boolean(raw.is_active) : true),
    activatedAt: Number(raw.activatedAt || raw.activated_at || raw.createdAt || raw.created_at || now),
    expiresAt: (raw.expiresAt !== undefined && raw.expiresAt !== null && raw.expiresAt !== '' && Number(raw.expiresAt) > 0)
      ? Number(raw.expiresAt)
      : ((raw.expires_at !== undefined && raw.expires_at !== null && raw.expires_at !== '' && Number(raw.expires_at) > 0)
        ? Number(raw.expires_at)
        : null),
    note: String(raw.note || '').trim(),
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
        is_active BOOLEAN DEFAULT TRUE,
        activated_at BIGINT DEFAULT (EXTRACT(EPOCH FROM NOW()) * 1000)::BIGINT,
        expires_at BIGINT NULL,
        note TEXT DEFAULT '',
        created_at BIGINT DEFAULT (EXTRACT(EPOCH FROM NOW()) * 1000)::BIGINT
      );

      ALTER TABLE players ADD COLUMN IF NOT EXISTS is_active BOOLEAN DEFAULT TRUE;
      ALTER TABLE players ADD COLUMN IF NOT EXISTS activated_at BIGINT DEFAULT (EXTRACT(EPOCH FROM NOW()) * 1000)::BIGINT;
      ALTER TABLE players ADD COLUMN IF NOT EXISTS expires_at BIGINT NULL;
      ALTER TABLE players ADD COLUMN IF NOT EXISTS note TEXT DEFAULT '';
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

    // Seed default player XO if players table is empty
    const { rows: playerCount } = await pool.query('SELECT COUNT(*)::INT AS cnt FROM players');
    if (playerCount[0].cnt === 0) {
      const now = Date.now();
      await pool.query(
        `INSERT INTO players (name, password, is_active, activated_at, expires_at, note, created_at)
         VALUES ($1, $2, TRUE, $3, NULL, $4, $3)
         ON CONFLICT (name) DO NOTHING`,
        ['XO', '111', now, 'Admin / Chủ hệ thống']
      );
    }

    // Seed default showCivStats setting
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
    `SELECT name, password, is_active, activated_at, expires_at, note, created_at
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
      await client.query(
        `INSERT INTO players (name, password, is_active, activated_at, expires_at, note, created_at)
         VALUES ($1, $2, $3, $4, $5, $6, $7)
         ON CONFLICT (name) DO UPDATE SET
           password = EXCLUDED.password,
           is_active = EXCLUDED.is_active,
           activated_at = EXCLUDED.activated_at,
           expires_at = EXCLUDED.expires_at,
           note = EXCLUDED.note`,
        [p.name, p.password, p.isActive, p.activatedAt, p.expiresAt, p.note, p.createdAt]
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
      p.createdAt = state.players[idx].createdAt || p.createdAt;
      state.players[idx] = p;
    } else {
      state.players.push(p);
    }
    writeLocalState(state);
    return p;
  }

  await pool.query(
    `INSERT INTO players (name, password, is_active, activated_at, expires_at, note, created_at)
     VALUES ($1, $2, $3, $4, $5, $6, $7)
     ON CONFLICT (name) DO UPDATE SET
       password = EXCLUDED.password,
       is_active = EXCLUDED.is_active,
       activated_at = EXCLUDED.activated_at,
       expires_at = EXCLUDED.expires_at,
       note = EXCLUDED.note`,
    [p.name, p.password, p.isActive, p.activatedAt, p.expiresAt, p.note, p.createdAt]
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
    return readLocalState().settings || { showCivStats: true };
  }
  const { rows } = await pool.query('SELECT key, value FROM settings');
  const settings = { showCivStats: true };
  for (const r of rows) {
    settings[r.key] = r.value;
  }
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
  isPostgresActive: () => usePostgres
};
