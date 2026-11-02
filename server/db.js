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
    { name: 'XO', password: '111' }
  ],
  matches: [],
  settings: {
    showCivStats: true
  }
};

function readLocalState() {
  try {
    if (!fs.existsSync(LOCAL_DB_PATH)) {
      fs.writeFileSync(LOCAL_DB_PATH, JSON.stringify(DEFAULT_STATE, null, 2), 'utf-8');
      return JSON.parse(JSON.stringify(DEFAULT_STATE));
    }
    return JSON.parse(fs.readFileSync(LOCAL_DB_PATH, 'utf-8'));
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
        created_at BIGINT DEFAULT (EXTRACT(EPOCH FROM NOW()) * 1000)::BIGINT
      );

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
      await pool.query(
        'INSERT INTO players (name, password) VALUES ($1, $2) ON CONFLICT (name) DO NOTHING',
        ['XO', '111']
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
    return readLocalState().players || [];
  }
  const { rows } = await pool.query('SELECT name, password FROM players ORDER BY created_at ASC, name ASC');
  return rows;
}

async function savePlayers(players) {
  const cleanPlayers = (Array.isArray(players) ? players : [])
    .map(p => ({
      name: String(p.name || '').trim(),
      password: String(p.password !== undefined ? p.password : '123').trim()
    }))
    .filter(p => p.name.length > 0);

  if (!usePostgres) {
    const state = readLocalState();
    state.players = cleanPlayers;
    writeLocalState(state);
    return;
  }

  const client = await pool.connect();
  try {
    await client.query('BEGIN');
    await client.query('DELETE FROM players');
    for (const p of cleanPlayers) {
      await client.query(
        'INSERT INTO players (name, password) VALUES ($1, $2) ON CONFLICT (name) DO UPDATE SET password = EXCLUDED.password',
        [p.name, p.password]
      );
    }
    await client.query('COMMIT');
  } catch (err) {
    await client.query('ROLLBACK');
    throw err;
  } finally {
    client.release();
  }
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
  getMatches,
  saveMatch,
  deleteMatches,
  getSettings,
  saveSetting,
  isPostgresActive: () => usePostgres
};

