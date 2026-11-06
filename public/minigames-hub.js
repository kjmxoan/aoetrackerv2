/**
 * XO MINIGAMES HUB v5.4.0 — 5 Trò Chơi Trí Tuệ & Giải Trí Chờ Kèo (Obsidian - Gold Edition)
 * Danh mục chuẩn hóa: 1. Cờ Caro (caro) | 2. Sudoku (sudoku) | 3. Cờ vua (chess) | 4. Rắn săn mồi (snake) | 5. 2048 (2048)
 * Tích hợp trực tiếp vào XO Website Hub (public/index.html) & đồng bộ Bảng Xếp Hạng qua /api
 */
(function () {
  const GAMES_META = [
    { key: 'caro', name: 'Cờ Caro', icon: '⭕', badge: '5 Quân Thắng', desc: 'Bàn cờ 20×20 chuẩn Esports. Đấu Máy AI 5 cấp độ, 2 Người hoặc Chướng ngại vật.' },
    { key: 'sudoku', name: 'Sudoku', icon: '▦', badge: 'Giải Đố 9×9', desc: '4 độ khó & Thử thách hằng ngày. Có ghi chú nháp (Pencil Marks), gợi ý & đua tốc độ.' },
    { key: 'chess', name: 'Cờ Vua', icon: '♟️', badge: 'Chiến Thuật 8×8', desc: 'Luật chuẩn quốc tế (Nhập thành, Bắt tốt qua đường, Phong cấp). Đấu AI Minimax hoặc 2P.' },
    { key: 'snake', name: 'Rắn Săn Mồi', icon: '🐍', badge: 'Arcade 60FPS', desc: 'Săn táo vàng Đế Chế, 4 giao diện chủ đề, hỗ trợ phím mũi tên/WASD & nút bấm điện thoại.' },
    { key: '2048', name: '2048', icon: '🔢', badge: 'Ghép Số 4×4', desc: 'Gộp các ô số lũy thừa 2 để đạt mốc 2048 Hoàng Kim. Hỗ trợ hoàn tác (Undo) 5 bước.' }
  ];

  const state = {
    activeGame: 'caro',
    leaderboards: { caro: [], sudoku: [], chess: [], snake: [], '2048': [] },
    getPlayerInfo: () => ({ name: 'Khách', tier: 'BRONZE' }),
    onNotify: () => {}
  };

  function esc(s) {
    return String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  }

  function tierBadgeHtml(tier) {
    const t = String(tier || 'BRONZE').toUpperCase();
    if (t === 'DIAMOND') return '<span class="px-1.5 py-0.5 rounded text-[10px] font-bold bg-sky-500/20 text-sky-300 border border-sky-400/40">💎 Kim Cương</span>';
    if (t === 'GOLD') return '<span class="px-1.5 py-0.5 rounded text-[10px] font-bold bg-amber-500/20 text-amber-300 border border-amber-400/40">🥇 Vàng</span>';
    if (t === 'SILVER') return '<span class="px-1.5 py-0.5 rounded text-[10px] font-bold bg-slate-400/20 text-slate-200 border border-slate-400/40">🥈 Bạc</span>';
    return '<span class="px-1.5 py-0.5 rounded text-[10px] font-bold bg-amber-900/30 text-amber-400 border border-amber-700/40">🥉 Đồng</span>';
  }

  async function fetchLeaderboard(gameKey) {
    try {
      const res = await fetch('/api', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action: 'getMinigameLeaderboard', game: gameKey })
      });
      const d = await res.json();
      if (d.status === 'success') {
        if (gameKey && Array.isArray(d.leaderboard)) {
          state.leaderboards[gameKey] = d.leaderboard;
        } else if (d.leaderboards) {
          state.leaderboards = { ...state.leaderboards, ...d.leaderboards };
        }
        renderLeaderboardPanel();
      }
    } catch (e) {}
  }

  async function submitScore(gameKey, score, extraLabel = '') {
    const info = state.getPlayerInfo();
    const playerName = (info && info.name) ? info.name : (localStorage.getItem('aoe_playerName') || localStorage.getItem('aoe_guestChatName') || 'Khách');
    const tier = (info && info.tier) ? info.tier : (localStorage.getItem('aoe_playerTier') || 'BRONZE');
    try {
      const res = await fetch('/api', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          action: 'saveMinigameScore',
          game: gameKey,
          playerName,
          tier,
          score: Number(score) || 0,
          extra: extraLabel
        })
      });
      const d = await res.json();
      if (d.status === 'success' && Array.isArray(d.leaderboard)) {
        state.leaderboards[gameKey] = d.leaderboard;
        renderLeaderboardPanel();
      }
    } catch (e) {}
  }

  function renderLeaderboardPanel() {
    const box = document.getElementById('xo-mg-leaderboard-list');
    const titleEl = document.getElementById('xo-mg-leaderboard-title');
    if (!box) return;
    const gMeta = GAMES_META.find(g => g.key === state.activeGame) || GAMES_META[0];
    if (titleEl) titleEl.innerHTML = `🏆 BXH ${esc(gMeta.name)}`;
    const list = state.leaderboards[state.activeGame] || [];
    if (!list.length) {
      box.innerHTML = `<div class="text-xs text-slate-400 text-center py-6 bg-slate-950/60 rounded-xl border border-slate-800">Chưa có kỷ lục nào cho <b>${esc(gMeta.name)}</b>.<br>Hãy là người đầu tiên ghi danh!</div>`;
      return;
    }
    box.innerHTML = list.slice(0, 10).map((row, idx) => {
      const rankIcon = idx === 0 ? '🥇' : (idx === 1 ? '🥈' : (idx === 2 ? '🥉' : `#${idx + 1}`));
      return `<div class="flex items-center justify-between gap-2 bg-slate-950/85 border border-slate-800/90 px-3 py-2 rounded-xl text-xs">
        <div class="flex items-center gap-2 min-w-0">
          <span class="font-extrabold text-amber-300 w-5">${rankIcon}</span>
          <span class="font-bold text-white truncate">${esc(row.playerName)}</span>
          ${tierBadgeHtml(row.tier)}
        </div>
        <div class="text-right shrink-0">
          <span class="font-mono font-extrabold text-emerald-400">${esc(row.score)} đ</span>
          ${row.extra ? `<span class="text-[10px] text-slate-400 block">${esc(row.extra)}</span>` : ''}
        </div>
      </div>`;
    }).join('');
  }

  // ============================================================================
  // 1. CỜ CARO ENGINE (20x20, Online PvP Lobby 2 Tài Khoản XO, AI 5 Levels, 2P, Obstacles)
  // ============================================================================
  const caro = {
    N: 20,
    board: [],
    moves: [],
    rocks: [],
    mode: 'online', // 'online' | 'ai' | '2p'
    aiLevel: 3, // 1..5
    obstacles: false,
    humanRole: 'X',
    winner: null,
    winLine: null,
    thinking: false,
    // Online PvP state
    roomsList: [],
    onlineRoom: null,
    onlineRole: 'V',
    pollTimer: null,
    init() {
      this.newGame();
      this.startPolling();
    },
    startPolling() {
      clearInterval(this.pollTimer);
      this.pollTimer = setInterval(() => {
        if (state.activeGame !== 'caro' || this.mode !== 'online') return;
        const mount = document.getElementById('xo-minigames-mount');
        if (!mount || mount.offsetParent === null) return;
        if (this.onlineRoom && this.onlineRoom.code) {
          this.refreshOnlineRoom();
        } else {
          this.fetchRoomsList();
        }
      }, 1400);
    },
    async fetchRoomsList() {
      try {
        const res = await fetch('/api', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ action: 'caroListRooms' })
        });
        const d = await res.json();
        if (d.status === 'success' && Array.isArray(d.rooms)) {
          this.roomsList = d.rooms;
          this.renderOnlineLobbyBox();
        }
      } catch (e) {}
    },
    async createOnlineRoom() {
      const info = state.getPlayerInfo();
      const playerName = (info && info.name) ? info.name : '';
      const tier = (info && info.tier) ? info.tier : 'BRONZE';
      if (!playerName || playerName.toLowerCase() === 'khách') {
        state.onNotify('🔒 Vui lòng Đăng nhập tài khoản XO (góc trên bên phải) để tạo bàn đấu Caro Online!', 'error');
        return;
      }
      try {
        const res = await fetch('/api', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            action: 'caroCreateRoom',
            playerName,
            tier,
            obstacles: this.obstacles
          })
        });
        const d = await res.json();
        if (d.status === 'success' && d.room) {
          this.onlineRole = d.role || 'X';
          this.applyOnlineRoomData(d.room);
          renderActiveGameStage();
          state.onNotify(`🏟️ Đã mở bàn Caro Online #${d.room.code}! Hãy gửi mã bàn hoặc chờ người chơi khác vào bàn.`);
        } else {
          state.onNotify(d.message || 'Không thể tạo bàn cờ!', 'error');
        }
      } catch (e) {
        state.onNotify('Lỗi kết nối khi tạo bàn cờ!', 'error');
      }
    },
    async joinOnlineRoom(codeInput) {
      const code = String(codeInput || '').trim().toUpperCase().replace(/^#/, '');
      if (!code) {
        state.onNotify('Vui lòng nhập mã bàn cờ (VD: XO88)!', 'error');
        return;
      }
      const info = state.getPlayerInfo();
      const playerName = (info && info.name) ? info.name : '';
      const tier = (info && info.tier) ? info.tier : 'BRONZE';
      if (!playerName || playerName.toLowerCase() === 'khách') {
        state.onNotify('🔒 Vui lòng Đăng nhập tài khoản XO để vào bàn đấu Caro Online!', 'error');
        return;
      }
      try {
        const res = await fetch('/api', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ action: 'caroJoinRoom', code, playerName, tier })
        });
        const d = await res.json();
        if (d.status === 'success' && d.room) {
          this.onlineRole = d.role || 'V';
          this.applyOnlineRoomData(d.room);
          renderActiveGameStage();
          state.onNotify(`⚔️ Đã vào bàn #${d.room.code} với tư cách ${this.onlineRole === 'V' ? 'Khán giả' : 'Kỳ thủ Quân ' + this.onlineRole}!`);
        } else {
          state.onNotify(d.message || 'Không tìm thấy bàn cờ này!', 'error');
        }
      } catch (e) {
        state.onNotify('Lỗi kết nối khi vào bàn!', 'error');
      }
    },
    async refreshOnlineRoom() {
      if (!this.onlineRoom || !this.onlineRoom.code) return;
      const info = state.getPlayerInfo();
      const playerName = (info && info.name) ? info.name : '';
      try {
        const res = await fetch('/api', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ action: 'caroGetRoom', code: this.onlineRoom.code, playerName })
        });
        const d = await res.json();
        if (d.status === 'success' && d.room) {
          this.onlineRole = d.role || this.onlineRole;
          this.applyOnlineRoomData(d.room);
          this.draw();
          this.updateStatus();
          this.renderOnlineRoomHeaderAndChat();
        } else {
          this.onlineRoom = null;
          renderActiveGameStage();
        }
      } catch (e) {}
    },
    applyOnlineRoomData(room) {
      this.onlineRoom = room;
      this.N = room.N || 20;
      this.board = Array.from({ length: this.N }, () => Array(this.N).fill(''));
      this.rocks = room.rocks || [];
      for (const [rx, ry] of this.rocks) {
        if (ry >= 0 && ry < this.N && rx >= 0 && rx < this.N) this.board[ry][rx] = '#';
      }
      this.moves = room.moves || [];
      for (const m of this.moves) {
        if (m.y >= 0 && m.y < this.N && m.x >= 0 && m.x < this.N) this.board[m.y][m.x] = m.role;
      }
      this.winner = room.winner || null;
      this.winLine = room.winLine || null;
    },
    async sendOnlineMove(x, y) {
      if (!this.onlineRoom) return;
      const info = state.getPlayerInfo();
      const playerName = (info && info.name) ? info.name : '';
      const tier = (info && info.tier) ? info.tier : 'BRONZE';
      try {
        const res = await fetch('/api', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            action: 'caroMove',
            code: this.onlineRoom.code,
            playerName,
            tier,
            x,
            y
          })
        });
        const d = await res.json();
        if (d.status === 'success' && d.room) {
          this.onlineRole = d.role || this.onlineRole;
          this.applyOnlineRoomData(d.room);
          this.draw();
          this.updateStatus();
          this.renderOnlineRoomHeaderAndChat();
          if (d.room.winner) fetchLeaderboard('caro');
        } else if (d.message) {
          state.onNotify(d.message, 'error');
        }
      } catch (e) {}
    },
    async resetOnlineGame() {
      if (!this.onlineRoom) return;
      const info = state.getPlayerInfo();
      const playerName = (info && info.name) ? info.name : '';
      try {
        const res = await fetch('/api', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ action: 'caroResetGame', code: this.onlineRoom.code, playerName })
        });
        const d = await res.json();
        if (d.status === 'success' && d.room) {
          this.onlineRole = d.role || this.onlineRole;
          this.applyOnlineRoomData(d.room);
          this.draw();
          this.updateStatus();
          this.renderOnlineRoomHeaderAndChat();
        } else if (d.message) {
          state.onNotify(d.message, 'error');
        }
      } catch (e) {}
    },
    async resignOnlineGame() {
      if (!this.onlineRoom) return;
      const info = state.getPlayerInfo();
      const playerName = (info && info.name) ? info.name : '';
      try {
        const res = await fetch('/api', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ action: 'caroResign', code: this.onlineRoom.code, playerName })
        });
        const d = await res.json();
        if (d.status === 'success' && d.room) {
          this.applyOnlineRoomData(d.room);
          this.draw();
          this.updateStatus();
          this.renderOnlineRoomHeaderAndChat();
        }
      } catch (e) {}
    },
    async leaveOnlineRoom() {
      if (!this.onlineRoom) return;
      const info = state.getPlayerInfo();
      const playerName = (info && info.name) ? info.name : '';
      try {
        await fetch('/api', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ action: 'caroLeaveRoom', code: this.onlineRoom.code, playerName })
        });
      } catch (e) {}
      this.onlineRoom = null;
      this.onlineRole = 'V';
      renderActiveGameStage();
      this.fetchRoomsList();
    },
    async sendOnlineChat(textInput) {
      if (!this.onlineRoom) return;
      const inp = document.getElementById('xo-caro-chat-inp');
      const text = (textInput || (inp ? inp.value : '')).trim();
      if (!text) return;
      if (inp && !textInput) inp.value = '';
      const info = state.getPlayerInfo();
      const playerName = (info && info.name) ? info.name : 'Kỳ thủ';
      const tier = (info && info.tier) ? info.tier : 'BRONZE';
      try {
        const res = await fetch('/api', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            action: 'caroRoomChat',
            code: this.onlineRoom.code,
            playerName,
            tier,
            text
          })
        });
        const d = await res.json();
        if (d.status === 'success' && d.room) {
          this.onlineRoom = d.room;
          this.renderOnlineRoomHeaderAndChat();
        }
      } catch (e) {}
    },
    renderOnlineLobbyBox() {
      const box = document.getElementById('xo-caro-rooms-grid');
      if (!box) return;
      if (!this.roomsList.length) {
        box.innerHTML = `
          <div class="col-span-full bg-slate-950/80 border border-slate-800 rounded-xl p-6 text-center space-y-2">
            <div class="text-2xl">⭕⚔️❌</div>
            <div class="text-sm font-bold text-white">Hiện chưa có bàn cờ Caro Online nào đang mở</div>
            <div class="text-xs text-slate-400">Hãy bấm nút <b class="text-amber-300">"➕ Tạo Bàn Mới"</b> ở trên để mở bàn và mời bạn bè (trên Web hoặc App Windows) vào so tài!</div>
          </div>
        `;
        return;
      }
      box.innerHTML = this.roomsList.map(r => {
        const waiting = r.status === 'WAITING';
        const px = r.playerX ? `${esc(r.playerX.name)} ${tierBadgeHtml(r.playerX.tier)}` : '<span class="text-slate-400 italic">Trống</span>';
        const po = r.playerO ? `${esc(r.playerO.name)} ${tierBadgeHtml(r.playerO.tier)}` : '<span class="text-amber-300 font-bold animate-pulse">⏳ Đang chờ đối thủ...</span>';
        return `
          <div class="bg-slate-950/90 border ${waiting ? 'border-amber-500/50' : 'border-slate-800'} rounded-xl p-3.5 flex flex-col justify-between gap-2.5 hover:border-amber-400 transition">
            <div class="flex items-center justify-between gap-2">
              <div class="flex items-center gap-2">
                <span class="font-mono font-black text-xs px-2 py-0.5 rounded bg-amber-500/20 text-amber-300 border border-amber-400/40">#${esc(r.code)}</span>
                <span class="font-bold text-xs text-white truncate">${esc(r.title)}</span>
              </div>
              <span class="text-[10px] font-extrabold px-2 py-0.5 rounded-full ${waiting ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/40' : 'bg-sky-500/20 text-sky-300 border border-sky-500/40'}">
                ${waiting ? '🟢 Chờ người (1/2)' : `⚔️ Nước #${r.movesCount}`}
              </span>
            </div>
            <div class="bg-slate-900/90 border border-slate-800 rounded-lg p-2 text-xs space-y-1">
              <div class="flex items-center justify-between">
                <span class="text-amber-400 font-extrabold">❌ Quân X:</span>
                <span class="font-semibold text-white flex items-center gap-1">${px}</span>
              </div>
              <div class="flex items-center justify-between">
                <span class="text-sky-400 font-extrabold">⭕ Quân O:</span>
                <span class="font-semibold text-white flex items-center gap-1">${po}</span>
              </div>
            </div>
            <div class="flex items-center justify-between gap-2 pt-0.5">
              <span class="text-[11px] text-slate-400 font-semibold">
                Tỉ số: <b class="text-amber-300">${(r.scores && r.scores.X) || 0} - ${(r.scores && r.scores.O) || 0}</b>
                ${r.obstacles ? ' &bull; 🪨 Có đá cản' : ''}
              </span>
              <button data-join-code="${esc(r.code)}" class="xo-caro-join-btn ${waiting ? 'bg-amber-500 hover:bg-amber-400 text-slate-950' : 'bg-sky-500/20 hover:bg-sky-500 text-sky-300 hover:text-slate-950 border border-sky-500/40'} font-extrabold px-3 py-1.5 rounded-xl text-xs transition">
                ${waiting ? '⚔️ Vào Đấu Ngay' : '👁️ Vào Bàn'}
              </button>
            </div>
          </div>
        `;
      }).join('');
      box.querySelectorAll('.xo-caro-join-btn').forEach(btn => {
        btn.onclick = () => this.joinOnlineRoom(btn.dataset.joinCode);
      });
    },
    renderOnlineRoomHeaderAndChat() {
      const hdr = document.getElementById('xo-caro-online-match-bar');
      if (hdr && this.onlineRoom) {
        const r = this.onlineRoom;
        const pxName = r.players.X ? esc(r.players.X.name) : 'Đang chờ X...';
        const poName = r.players.O ? esc(r.players.O.name) : '⏳ Đang chờ đối thủ vào bàn...';
        const pxTier = r.players.X ? tierBadgeHtml(r.players.X.tier) : '';
        const poTier = r.players.O ? tierBadgeHtml(r.players.O.tier) : '';
        hdr.innerHTML = `
          <div class="grid grid-cols-11 gap-2 items-center bg-slate-950/90 border border-amber-500/40 rounded-xl p-2.5 text-xs">
            <div class="col-span-4 text-left truncate">
              <div class="text-[10px] font-extrabold text-amber-400 uppercase">❌ Quân X ${this.onlineRole === 'X' ? '(Bạn)' : ''}</div>
              <div class="font-bold text-white flex items-center gap-1 mt-0.5 truncate">${pxName} ${pxTier}</div>
            </div>
            <div class="col-span-3 text-center">
              <div class="font-display font-black text-base sm:text-xl text-amber-300">${(r.scores && r.scores.X) || 0} - ${(r.scores && r.scores.O) || 0}</div>
              <div class="text-[10px] text-slate-400 font-mono">Bàn #${esc(r.code)}</div>
            </div>
            <div class="col-span-4 text-right truncate">
              <div class="text-[10px] font-extrabold text-sky-400 uppercase">⭕ Quân O ${this.onlineRole === 'O' ? '(Bạn)' : ''}</div>
              <div class="font-bold text-white flex items-center justify-end gap-1 mt-0.5 truncate">${poName} ${poTier}</div>
            </div>
          </div>
        `;
      }
      const chatFeed = document.getElementById('xo-caro-chat-feed');
      if (chatFeed && this.onlineRoom) {
        const list = this.onlineRoom.chat || [];
        chatFeed.innerHTML = list.map(m => m.sys
          ? `<div class="text-[11px] text-amber-300/90 italic bg-slate-900/70 px-2.5 py-1 rounded-lg">${esc(m.text)}</div>`
          : `<div class="text-xs bg-slate-900/90 border border-slate-800 px-2.5 py-1.5 rounded-lg flex items-center justify-between gap-2">
               <div><b class="text-sky-300">${esc(m.sender)}:</b> <span class="text-slate-100">${esc(m.text)}</span></div>
               <span class="text-[10px] text-slate-500 font-mono shrink-0">${esc(m.timeText || '')}</span>
             </div>`
        ).join('');
        chatFeed.scrollTop = chatFeed.scrollHeight;
      }
    },
    newGame() {
      this.board = Array.from({ length: this.N }, () => Array(this.N).fill(''));
      this.moves = [];
      this.rocks = [];
      this.winner = null;
      this.winLine = null;
      this.thinking = false;
      if (this.obstacles) {
        let count = 0;
        while (count < 12) {
          const rx = 2 + Math.floor(Math.random() * (this.N - 4));
          const ry = 2 + Math.floor(Math.random() * (this.N - 4));
          if ((rx === 10 && ry === 10) || this.board[ry][rx]) continue;
          this.board[ry][rx] = '#';
          this.rocks.push([rx, ry]);
          count++;
        }
      }
      if (this.mode === 'ai' && this.humanRole === 'O') {
        this.playMove(10, 10, 'X');
      }
      this.draw();
      this.updateStatus();
    },
    turn() {
      return this.moves.length % 2 === 0 ? 'X' : 'O';
    },
    undo() {
      if (this.thinking || !this.moves.length || this.winner) return;
      if (this.mode === 'ai' && this.moves.length >= 2) {
        const m1 = this.moves.pop();
        const m2 = this.moves.pop();
        this.board[m1.y][m1.x] = '';
        this.board[m2.y][m2.x] = '';
      } else {
        const m = this.moves.pop();
        this.board[m.y][m.x] = '';
      }
      this.draw();
      this.updateStatus();
    },
    checkWin(x, y, role) {
      const dirs = [[1, 0], [0, 1], [1, 1], [1, -1]];
      const opp = role === 'X' ? 'O' : 'X';
      for (const [dx, dy] of dirs) {
        let count = 1;
        let ax = x, ay = y, ex = x, ey = y;
        let i = x + dx, j = y + dy;
        while (i >= 0 && i < this.N && j >= 0 && j < this.N && this.board[j][i] === role) {
          count++; ex = i; ey = j; i += dx; j += dy;
        }
        const block1 = !(i >= 0 && i < this.N && j >= 0 && j < this.N) || this.board[j][i] === opp || this.board[j][i] === '#';
        i = x - dx; j = y - dy;
        while (i >= 0 && i < this.N && j >= 0 && j < this.N && this.board[j][i] === role) {
          count++; ax = i; ay = j; i -= dx; j -= dy;
        }
        const block2 = !(i >= 0 && i < this.N && j >= 0 && j < this.N) || this.board[j][i] === opp || this.board[j][i] === '#';
        if (count >= 6 || (count === 5 && !(block1 && block2))) {
          return [[ax, ay], [ex, ey]];
        }
      }
      return null;
    },
    playMove(x, y, role) {
      if (this.winner || this.board[y][x] !== '') return false;
      this.board[y][x] = role;
      this.moves.push({ x, y, role });
      const wl = this.checkWin(x, y, role);
      if (wl) {
        this.winner = role;
        this.winLine = wl;
        if (this.mode === 'ai' && role === this.humanRole) {
          const pts = this.aiLevel * 150 + Math.max(20, 200 - this.moves.length * 2);
          submitScore('caro', pts, `Thắng AI Cấp ${this.aiLevel} (${this.moves.length} nước)`);
          state.onNotify(`🏆 Chúc mừng! Bạn đã thắng AI Cờ Caro Cấp ${this.aiLevel} (+${pts} điểm)!`);
        }
      } else if (this.moves.length >= this.N * this.N - this.rocks.length) {
        this.winner = 'DRAW';
      }
      this.draw();
      this.updateStatus();
      return true;
    },
    scoreLine(x, y, dx, dy, role) {
      const opp = role === 'X' ? 'O' : 'X';
      let count = 1, openEnds = 0;
      let i = x + dx, j = y + dy;
      while (i >= 0 && i < this.N && j >= 0 && j < this.N && this.board[j][i] === role) { count++; i += dx; j += dy; }
      if (i >= 0 && i < this.N && j >= 0 && j < this.N && this.board[j][i] === '') openEnds++;
      i = x - dx; j = y - dy;
      while (i >= 0 && i < this.N && j >= 0 && j < this.N && this.board[j][i] === role) { count++; i -= dx; j -= dy; }
      if (i >= 0 && i < this.N && j >= 0 && j < this.N && this.board[j][i] === '') openEnds++;
      if (count >= 5 && openEnds >= 1) return 100000;
      if (count === 4 && openEnds === 2) return 15000;
      if (count === 4 && openEnds === 1) return 3500;
      if (count === 3 && openEnds === 2) return 1800;
      if (count === 3 && openEnds === 1) return 300;
      if (count === 2 && openEnds === 2) return 180;
      return count * 15 * openEnds;
    },
    aiMove() {
      if (this.winner) return;
      const aiRole = this.humanRole === 'X' ? 'O' : 'X';
      const human = this.humanRole;
      const dirs = [[1, 0], [0, 1], [1, 1], [1, -1]];
      let bestScore = -1;
      let candidates = [];
      const defenseWeight = [0.7, 0.9, 1.05, 1.2, 1.35][this.aiLevel - 1] || 1.1;

      for (let y = 0; y < this.N; y++) {
        for (let x = 0; x < this.N; x++) {
          if (this.board[y][x] !== '') continue;
          // Check neighbor within distance 2
          let hasNeighbor = false;
          for (let dy = -2; dy <= 2 && !hasNeighbor; dy++) {
            for (let dx = -2; dx <= 2; dx++) {
              const nx = x + dx, ny = y + dy;
              if (nx >= 0 && nx < this.N && ny >= 0 && ny < this.N && (this.board[ny][nx] === 'X' || this.board[ny][nx] === 'O')) {
                hasNeighbor = true; break;
              }
            }
          }
          if (!hasNeighbor && this.moves.length > 0) continue;

          let atk = 0, def = 0;
          this.board[y][x] = aiRole;
          if (this.checkWin(x, y, aiRole)) atk += 500000;
          for (const [dx, dy] of dirs) atk += this.scoreLine(x, y, dx, dy, aiRole);
          this.board[y][x] = human;
          if (this.checkWin(x, y, human)) def += 400000;
          for (const [dx, dy] of dirs) def += this.scoreLine(x, y, dx, dy, human);
          this.board[y][x] = '';

          const centerBias = 15 - (Math.abs(x - 10) + Math.abs(y - 10)) * 0.5;
          const noise = this.aiLevel <= 2 ? Math.random() * 140 : (this.aiLevel === 3 ? Math.random() * 35 : Math.random() * 5);
          const total = atk + def * defenseWeight + centerBias + noise;
          if (total > bestScore) {
            bestScore = total;
            candidates = [[x, y]];
          } else if (Math.abs(total - bestScore) < 5) {
            candidates.push([x, y]);
          }
        }
      }
      const pick = candidates.length ? candidates[Math.floor(Math.random() * candidates.length)] : [10, 10];
      this.playMove(pick[0], pick[1], aiRole);
    },
    handleClick(ev) {
      if (this.winner || this.thinking) return;
      const canvas = document.getElementById('xo-caro-canvas');
      if (!canvas) return;
      const rect = canvas.getBoundingClientRect();
      const x = Math.floor(((ev.clientX - rect.left) / rect.width) * this.N);
      const y = Math.floor(((ev.clientY - rect.top) / rect.height) * this.N);
      if (x < 0 || x >= this.N || y < 0 || y >= this.N) return;
      if (this.mode === 'online') {
        this.sendOnlineMove(x, y);
        return;
      }
      const curTurn = this.turn();
      if (this.mode === 'ai' && curTurn !== this.humanRole) return;
      if (this.playMove(x, y, curTurn)) {
        if (!this.winner && this.mode === 'ai') {
          this.thinking = true;
          this.updateStatus();
          setTimeout(() => {
            this.thinking = false;
            this.aiMove();
          }, 180);
        }
      }
    },
    updateStatus() {
      const el = document.getElementById('xo-caro-status');
      if (!el) return;
      if (this.mode === 'online' && this.onlineRoom) {
        const r = this.onlineRoom;
        if (!r.players.X || !r.players.O) {
          el.innerHTML = `<span class="text-amber-300 font-bold">⏳ Đang chờ kỳ thủ thứ 2 vào bàn #${esc(r.code)}... Hãy gửi mã bàn #${esc(r.code)} cho bạn bè!</span>`;
          return;
        }
        if (this.winner === 'DRAW') {
          el.innerHTML = `<span class="text-amber-300 font-bold">🤝 Ván đấu Hòa! Bấm "🔄 Ván Mới" để tái đấu.</span>`;
          return;
        }
        if (this.winner) {
          const wName = (r.players[this.winner] && r.players[this.winner].name) || this.winner;
          el.innerHTML = `<span class="text-emerald-400 font-extrabold">🏆 ${esc(wName)} (${this.winner}) CHIẾN THẮNG! (${esc(r.winReason || '')})</span>`;
          return;
        }
        const t = this.turn();
        const tPlayer = (r.players[t] && r.players[t].name) || t;
        const isMyTurn = this.onlineRole === t;
        el.innerHTML = isMyTurn
          ? `<span class="text-amber-300 font-extrabold">⚡ TỚI LƯỢT BẠN ĐÁNH (Quân ${t}) — Nước #${this.moves.length + 1}</span>`
          : `<span class="text-sky-300 font-semibold">⏳ Đang chờ <b>${esc(tPlayer)}</b> (${t}) đi nước #${this.moves.length + 1}...</span>`;
        return;
      }
      if (this.winner === 'DRAW') {
        el.innerHTML = `<span class="text-amber-300 font-bold">🤝 Ván đấu Hòa!</span>`;
      } else if (this.winner) {
        const winText = this.mode === 'ai'
          ? (this.winner === this.humanRole ? '🏆 BẠN CHIẾN THẮNG!' : '🤖 MÁY AI CHIẾN THẮNG!')
          : `🏆 NGƯỜI CHƠI ${this.winner} CHIẾN THẮNG!`;
        el.innerHTML = `<span class="text-emerald-400 font-extrabold">${winText}</span>`;
      } else if (this.thinking) {
        el.innerHTML = `<span class="text-sky-300 font-semibold">🤖 Máy AI (Cấp ${this.aiLevel}) đang tính nước đi...</span>`;
      } else {
        const t = this.turn();
        const colorCls = t === 'X' ? 'text-amber-400' : 'text-sky-400';
        el.innerHTML = `Lượt đi: <b class="${colorCls} font-extrabold">${t}</b> &bull; Nước #${this.moves.length + 1}`;
      }
    },
    draw() {
      const canvas = document.getElementById('xo-caro-canvas');
      if (!canvas) return;
      const ctx = canvas.getContext('2d');
      const W = canvas.width, H = canvas.height;
      const cell = W / this.N;
      ctx.fillStyle = '#0B0F17';
      ctx.fillRect(0, 0, W, H);

      // Grid lines
      ctx.strokeStyle = '#1E293B';
      ctx.lineWidth = 1;
      for (let i = 0; i <= this.N; i++) {
        const pos = Math.floor(i * cell) + 0.5;
        ctx.beginPath(); ctx.moveTo(pos, 0); ctx.lineTo(pos, H); ctx.stroke();
        ctx.beginPath(); ctx.moveTo(0, pos); ctx.lineTo(W, pos); ctx.stroke();
      }

      // Star points
      ctx.fillStyle = '#334155';
      for (const [sx, sy] of [[4, 4], [10, 10], [15, 4], [4, 15], [15, 15]]) {
        ctx.beginPath();
        ctx.arc((sx + 0.5) * cell, (sy + 0.5) * cell, 3, 0, Math.PI * 2);
        ctx.fill();
      }

      // Last move highlight
      if (this.moves.length) {
        const last = this.moves[this.moves.length - 1];
        ctx.fillStyle = 'rgba(245, 158, 11, 0.18)';
        ctx.fillRect(last.x * cell + 1, last.y * cell + 1, cell - 2, cell - 2);
      }

      // Pieces & rocks
      for (let y = 0; y < this.N; y++) {
        for (let x = 0; x < this.N; x++) {
          const v = this.board[y][x];
          const cx = (x + 0.5) * cell, cy = (y + 0.5) * cell;
          if (v === '#') {
            ctx.fillStyle = '#334155';
            ctx.fillRect(x * cell + 3, y * cell + 3, cell - 6, cell - 6);
            ctx.fillStyle = '#94A3B8';
            ctx.font = `${Math.floor(cell * 0.55)}px sans-serif`;
            ctx.textAlign = 'center';
            ctx.textBaseline = 'middle';
            ctx.fillText('🪨', cx, cy);
          } else if (v === 'X') {
            ctx.strokeStyle = '#F59E0B';
            ctx.lineWidth = 2.8;
            ctx.lineCap = 'round';
            const r = cell * 0.3;
            ctx.beginPath();
            ctx.moveTo(cx - r, cy - r); ctx.lineTo(cx + r, cy + r);
            ctx.moveTo(cx + r, cy - r); ctx.lineTo(cx - r, cy + r);
            ctx.stroke();
          } else if (v === 'O') {
            ctx.strokeStyle = '#38BDF8';
            ctx.lineWidth = 2.8;
            ctx.beginPath();
            ctx.arc(cx, cy, cell * 0.3, 0, Math.PI * 2);
            ctx.stroke();
          }
        }
      }

      // Winning line
      if (this.winLine) {
        const [[x1, y1], [x2, y2]] = this.winLine;
        ctx.strokeStyle = '#10B981';
        ctx.lineWidth = 4;
        ctx.beginPath();
        ctx.moveTo((x1 + 0.5) * cell, (y1 + 0.5) * cell);
        ctx.lineTo((x2 + 0.5) * cell, (y2 + 0.5) * cell);
        ctx.stroke();
      }
    }
  };

  // ============================================================================
  // 2. SUDOKU ENGINE (9x9, 4 Difficulties + Daily, Notes Mode, Hints, Timer)
  // ============================================================================
  const sudoku = {
    difficulty: 'easy',
    solution: [],
    givens: [],
    board: [],
    notes: [],
    selected: -1,
    notesMode: false,
    mistakes: 0,
    hintsUsed: 0,
    seconds: 0,
    complete: false,
    timer: null,
    seededRandom(seedStr) {
      let h = 2166136261 >>> 0;
      for (let i = 0; i < seedStr.length; i++) {
        h ^= seedStr.charCodeAt(i);
        h = Math.imul(h, 16777619);
      }
      return function () {
        h += h << 13; h ^= h >>> 7; h += h << 3; h ^= h >>> 17; h += h << 5;
        return (h >>> 0) / 4294967296;
      };
    },
    generatePuzzle(diff) {
      const seed = diff === 'daily' ? ('xo-daily-' + new Date().toISOString().slice(0, 10)) : ('xo-' + Date.now() + '-' + Math.random());
      const rng = this.seededRandom(seed);
      const base = [1, 2, 3, 4, 5, 6, 7, 8, 9];
      const shuffle = arr => {
        const a = [...arr];
        for (let i = a.length - 1; i > 0; i--) {
          const j = Math.floor(rng() * (i + 1));
          [a[i], a[j]] = [a[j], a[i]];
        }
        return a;
      };
      const nums = shuffle(base);
      const rowBands = shuffle([0, 1, 2]).flatMap(b => shuffle([0, 1, 2]).map(r => b * 3 + r));
      const colBands = shuffle([0, 1, 2]).flatMap(b => shuffle([0, 1, 2]).map(c => b * 3 + c));
      const sol = [];
      for (let r = 0; r < 9; r++) {
        for (let c = 0; c < 9; c++) {
          const rr = rowBands[r], cc = colBands[c];
          sol.push(nums[(rr * 3 + Math.floor(rr / 3) + cc) % 9]);
        }
      }
      const holesMap = { easy: 34, medium: 43, hard: 50, evil: 56, daily: 42 };
      const holes = holesMap[diff] || 36;
      const idxs = shuffle(Array.from({ length: 81 }, (_, i) => i));
      const brd = [...sol];
      for (let k = 0; k < holes; k++) brd[idxs[k]] = 0;
      return { solution: sol, board: brd, givens: brd.map(v => v !== 0) };
    },
    newGame(diff) {
      if (diff) this.difficulty = diff;
      const p = this.generatePuzzle(this.difficulty);
      this.solution = p.solution;
      this.board = p.board;
      this.givens = p.givens;
      this.notes = Array.from({ length: 81 }, () => new Set());
      this.selected = -1;
      this.mistakes = 0;
      this.hintsUsed = 0;
      this.seconds = 0;
      this.complete = false;
      clearInterval(this.timer);
      this.timer = setInterval(() => {
        if (!this.complete && state.activeGame === 'sudoku') {
          this.seconds++;
          const tEl = document.getElementById('xo-sudoku-timer');
          if (tEl) tEl.textContent = this.formatTime(this.seconds);
        }
      }, 1000);
      this.render();
    },
    formatTime(s) {
      const m = Math.floor(s / 60), sec = s % 60;
      return `${String(m).padStart(2, '0')}:${String(sec).padStart(2, '0')}`;
    },
    input(num) {
      if (this.complete || this.selected < 0 || this.givens[this.selected]) return;
      const idx = this.selected;
      if (num === 0) {
        this.board[idx] = 0;
        this.notes[idx].clear();
        this.render();
        return;
      }
      if (this.notesMode) {
        if (this.notes[idx].has(num)) this.notes[idx].delete(num);
        else this.notes[idx].add(num);
        this.render();
        return;
      }
      this.board[idx] = num;
      this.notes[idx].clear();
      if (num !== this.solution[idx]) {
        this.mistakes++;
      } else {
        // Clear peer notes
        const r = Math.floor(idx / 9), c = idx % 9, br = Math.floor(r / 3) * 3, bc = Math.floor(c / 3) * 3;
        for (let i = 0; i < 9; i++) {
          this.notes[r * 9 + i].delete(num);
          this.notes[i * 9 + c].delete(num);
        }
        for (let dr = 0; dr < 3; dr++) for (let dc = 0; dc < 3; dc++) {
          this.notes[(br + dr) * 9 + (bc + dc)].delete(num);
        }
        if (this.board.every((v, i) => v === this.solution[i])) {
          this.complete = true;
          clearInterval(this.timer);
          const mult = { easy: 1, medium: 1.4, hard: 1.8, evil: 2.4, daily: 1.6 }[this.difficulty] || 1;
          const score = Math.max(100, Math.round((1200 - this.seconds - this.mistakes * 30 - this.hintsUsed * 60) * mult));
          submitScore('sudoku', score, `${this.difficulty.toUpperCase()} • ${this.formatTime(this.seconds)}`);
          state.onNotify(`🎉 Hoàn thành Sudoku (${this.formatTime(this.seconds)})! Đã lưu ${score} điểm lên BXH!`);
        }
      }
      this.render();
    },
    hint() {
      if (this.complete) return;
      const empties = [];
      for (let i = 0; i < 81; i++) {
        if (this.board[i] !== this.solution[i]) empties.push(i);
      }
      if (!empties.length) return;
      const pick = (this.selected >= 0 && this.board[this.selected] !== this.solution[this.selected])
        ? this.selected
        : empties[Math.floor(Math.random() * empties.length)];
      this.selected = pick;
      this.hintsUsed++;
      this.notesMode = false;
      this.input(this.solution[pick]);
    },
    render() {
      const grid = document.getElementById('xo-sudoku-grid');
      if (!grid) return;
      const sel = this.selected;
      const sr = sel >= 0 ? Math.floor(sel / 9) : -1;
      const sc = sel >= 0 ? sel % 9 : -1;
      const selVal = sel >= 0 ? this.board[sel] : 0;

      grid.innerHTML = this.board.map((v, i) => {
        const r = Math.floor(i / 9), c = i % 9;
        const isGiven = this.givens[i];
        const isSel = i === sel;
        const isPeer = sel >= 0 && (r === sr || c === sc || (Math.floor(r / 3) === Math.floor(sr / 3) && Math.floor(c / 3) === Math.floor(sc / 3)));
        const isSame = selVal > 0 && v === selVal;
        const isWrong = v > 0 && !isGiven && v !== this.solution[i];

        const borderR = (c === 2 || c === 5) ? 'border-r-2 border-r-amber-500/70' : 'border-r border-r-slate-800';
        const borderB = (r === 2 || r === 5) ? 'border-b-2 border-b-amber-500/70' : 'border-b border-b-slate-800';
        let bg = 'bg-slate-950/90';
        if (isSel) bg = 'bg-amber-500/30 ring-2 ring-amber-400 z-10';
        else if (isWrong) bg = 'bg-rose-950/80';
        else if (isSame) bg = 'bg-sky-500/25';
        else if (isPeer) bg = 'bg-slate-900/95';

        let textCls = isGiven ? 'text-slate-100 font-black' : (isWrong ? 'text-rose-400 font-extrabold' : 'text-sky-300 font-bold');
        let inner = '';
        if (v > 0) {
          inner = `<span class="text-base sm:text-lg ${textCls}">${v}</span>`;
        } else if (this.notes[i].size > 0) {
          inner = `<div class="grid grid-cols-3 w-full h-full text-[9px] leading-none text-amber-300/90 items-center justify-items-center p-0.5">` +
            [1, 2, 3, 4, 5, 6, 7, 8, 9].map(n => `<span>${this.notes[i].has(n) ? n : ''}</span>`).join('') +
            `</div>`;
        }
        return `<button data-idx="${i}" class="xo-sudoku-cell aspect-square flex items-center justify-center ${bg} ${borderR} ${borderB} transition select-none">${inner}</button>`;
      }).join('');

      grid.querySelectorAll('.xo-sudoku-cell').forEach(btn => {
        btn.onclick = () => {
          this.selected = Number(btn.dataset.idx);
          this.render();
        };
      });

      const metaEl = document.getElementById('xo-sudoku-meta');
      if (metaEl) {
        const filled = this.board.filter((v, i) => v === this.solution[i]).length;
        metaEl.innerHTML = `Tiến độ: <b class="text-emerald-400">${filled}/81</b> &bull; Lỗi: <b class="text-rose-400">${this.mistakes}</b> &bull; Gợi ý: <b class="text-amber-300">${this.hintsUsed}</b>`;
      }
      const noteBtn = document.getElementById('xo-sudoku-note-btn');
      if (noteBtn) {
        noteBtn.className = this.notesMode
          ? 'bg-amber-400 text-slate-950 font-extrabold px-3 py-1.5 rounded-xl text-xs shadow transition'
          : 'bg-slate-900 hover:bg-slate-800 text-slate-200 border border-slate-700 px-3 py-1.5 rounded-xl text-xs font-semibold transition';
        noteBtn.textContent = `✏️ Nháp: ${this.notesMode ? 'BẬT' : 'TẮT'}`;
      }
    }
  };

  // ============================================================================
  // 3. CỜ VUA ENGINE (8x8 Full Legal Moves, Castling, En Passant, Promotion, Minimax AI)
  // ============================================================================
  const chess = {
    UNICODE: {
      wK: '♔', wQ: '♕', wR: '♖', wB: '♗', wN: '♘', wP: '♙',
      bK: '♚', bQ: '♛', bR: '♜', bB: '♝', bN: '♞', bP: '♟'
    },
    VALS: { P: 100, N: 320, B: 330, R: 500, Q: 900, K: 20000 },
    board: [],
    turn: 'w',
    mode: 'ai', // 'ai' | '2p'
    aiLevel: 2, // 1..3
    flipped: false,
    selected: null,
    legalMoves: [],
    history: [],
    castling: { wK: true, wQ: true, bK: true, bQ: true },
    epTarget: null,
    winner: null,
    statusText: '',
    newGame() {
      const back = ['R', 'N', 'B', 'Q', 'K', 'B', 'N', 'R'];
      this.board = Array.from({ length: 8 }, (_, r) =>
        Array.from({ length: 8 }, (__, c) => {
          if (r === 0) return 'b' + back[c];
          if (r === 1) return 'bP';
          if (r === 6) return 'wP';
          if (r === 7) return 'w' + back[c];
          return '';
        })
      );
      this.turn = 'w';
      this.selected = null;
      this.legalMoves = [];
      this.history = [];
      this.castling = { wK: true, wQ: true, bK: true, bQ: true };
      this.epTarget = null;
      this.winner = null;
      this.statusText = 'Trắng đi trước';
      this.render();
    },
    cloneState() {
      return {
        board: this.board.map(r => [...r]),
        turn: this.turn,
        castling: { ...this.castling },
        epTarget: this.epTarget ? [...this.epTarget] : null
      };
    },
    inBounds(r, c) { return r >= 0 && r < 8 && c >= 0 && c < 8; },
    findKing(brd, side) {
      const target = side + 'K';
      for (let r = 0; r < 8; r++) for (let c = 0; c < 8; c++) if (brd[r][c] === target) return [r, c];
      return null;
    },
    isSquareAttacked(brd, tr, tc, bySide) {
      // Pawn attacks
      const pDir = bySide === 'w' ? 1 : -1;
      for (const dc of [-1, 1]) {
        const pr = tr + pDir, pc = tc + dc;
        if (this.inBounds(pr, pc) && brd[pr][pc] === bySide + 'P') return true;
      }
      // Knights
      for (const [dr, dc] of [[-2, -1], [-2, 1], [-1, -2], [-1, 2], [1, -2], [1, 2], [2, -1], [2, 1]]) {
        const nr = tr + dr, nc = tc + dc;
        if (this.inBounds(nr, nc) && brd[nr][nc] === bySide + 'N') return true;
      }
      // King
      for (let dr = -1; dr <= 1; dr++) for (let dc = -1; dc <= 1; dc++) {
        if (!dr && !dc) continue;
        const kr = tr + dr, kc = tc + dc;
        if (this.inBounds(kr, kc) && brd[kr][kc] === bySide + 'K') return true;
      }
      // Rook/Queen
      for (const [dr, dc] of [[-1, 0], [1, 0], [0, -1], [0, 1]]) {
        let r = tr + dr, c = tc + dc;
        while (this.inBounds(r, c)) {
          const p = brd[r][c];
          if (p) {
            if (p === bySide + 'R' || p === bySide + 'Q') return true;
            break;
          }
          r += dr; c += dc;
        }
      }
      // Bishop/Queen
      for (const [dr, dc] of [[-1, -1], [-1, 1], [1, -1], [1, 1]]) {
        let r = tr + dr, c = tc + dc;
        while (this.inBounds(r, c)) {
          const p = brd[r][c];
          if (p) {
            if (p === bySide + 'B' || p === bySide + 'Q') return true;
            break;
          }
          r += dr; c += dc;
        }
      }
      return false;
    },
    inCheck(brd, side) {
      const k = this.findKing(brd, side);
      if (!k) return true;
      return this.isSquareAttacked(brd, k[0], k[1], side === 'w' ? 'b' : 'w');
    },
    applyMoveOnBoard(brd, castling, m) {
      const nb = brd.map(r => [...r]);
      const nc = { ...castling };
      const piece = nb[m.fr][m.fc];
      const side = piece[0], type = piece[1];
      nb[m.fr][m.fc] = '';
      if (m.epCapture) {
        nb[m.fr][m.tc] = '';
      }
      if (m.castle === 'K') {
        nb[m.fr][5] = side + 'R';
        nb[m.fr][7] = '';
      } else if (m.castle === 'Q') {
        nb[m.fr][3] = side + 'R';
        nb[m.fr][0] = '';
      }
      nb[m.tr][m.tc] = m.promote ? (side + m.promote) : piece;
      if (piece === 'wK') { nc.wK = false; nc.wQ = false; }
      if (piece === 'bK') { nc.bK = false; nc.bQ = false; }
      if (m.fr === 7 && m.fc === 0) nc.wQ = false;
      if (m.fr === 7 && m.fc === 7) nc.wK = false;
      if (m.fr === 0 && m.fc === 0) nc.bQ = false;
      if (m.fr === 0 && m.fc === 7) nc.bK = false;
      const ep = (type === 'P' && Math.abs(m.tr - m.fr) === 2) ? [(m.fr + m.tr) / 2, m.fc] : null;
      return { board: nb, castling: nc, epTarget: ep };
    },
    generateLegalMoves(brd, side, castling, epTarget) {
      const opp = side === 'w' ? 'b' : 'w';
      const pseudo = [];
      for (let r = 0; r < 8; r++) {
        for (let c = 0; c < 8; c++) {
          const p = brd[r][c];
          if (!p || p[0] !== side) continue;
          const type = p[1];
          if (type === 'P') {
            const dir = side === 'w' ? -1 : 1;
            const startRow = side === 'w' ? 6 : 1;
            const promRow = side === 'w' ? 0 : 7;
            const nr = r + dir;
            if (this.inBounds(nr, c) && !brd[nr][c]) {
              if (nr === promRow) pseudo.push({ fr: r, fc: c, tr: nr, tc: c, promote: 'Q' });
              else pseudo.push({ fr: r, fc: c, tr: nr, tc: c });
              const nr2 = r + dir * 2;
              if (r === startRow && !brd[nr2][c]) pseudo.push({ fr: r, fc: c, tr: nr2, tc: c });
            }
            for (const dc of [-1, 1]) {
              const nc = c + dc;
              if (!this.inBounds(nr, nc)) continue;
              const target = brd[nr][nc];
              if (target && target[0] === opp) {
                if (nr === promRow) pseudo.push({ fr: r, fc: c, tr: nr, tc: nc, promote: 'Q' });
                else pseudo.push({ fr: r, fc: c, tr: nr, tc: nc });
              } else if (epTarget && epTarget[0] === nr && epTarget[1] === nc) {
                pseudo.push({ fr: r, fc: c, tr: nr, tc: nc, epCapture: true });
              }
            }
          } else if (type === 'N') {
            for (const [dr, dc] of [[-2, -1], [-2, 1], [-1, -2], [-1, 2], [1, -2], [1, 2], [2, -1], [2, 1]]) {
              const nr = r + dr, nc = c + dc;
              if (this.inBounds(nr, nc) && (!brd[nr][nc] || brd[nr][nc][0] === opp)) {
                pseudo.push({ fr: r, fc: c, tr: nr, tc: nc });
              }
            }
          } else if (type === 'K') {
            for (let dr = -1; dr <= 1; dr++) for (let dc = -1; dc <= 1; dc++) {
              if (!dr && !dc) continue;
              const nr = r + dr, nc = c + dc;
              if (this.inBounds(nr, nc) && (!brd[nr][nc] || brd[nr][nc][0] === opp)) {
                pseudo.push({ fr: r, fc: c, tr: nr, tc: nc });
              }
            }
            // Castling
            const row = side === 'w' ? 7 : 0;
            if (r === row && c === 4 && !this.inCheck(brd, side)) {
              if (castling[side + 'K'] && !brd[row][5] && !brd[row][6] && brd[row][7] === side + 'R') {
                if (!this.isSquareAttacked(brd, row, 5, opp) && !this.isSquareAttacked(brd, row, 6, opp)) {
                  pseudo.push({ fr: row, fc: 4, tr: row, tc: 6, castle: 'K' });
                }
              }
              if (castling[side + 'Q'] && !brd[row][3] && !brd[row][2] && !brd[row][1] && brd[row][0] === side + 'R') {
                if (!this.isSquareAttacked(brd, row, 3, opp) && !this.isSquareAttacked(brd, row, 2, opp)) {
                  pseudo.push({ fr: row, fc: 4, tr: row, tc: 2, castle: 'Q' });
                }
              }
            }
          } else {
            const dirs = type === 'R' ? [[-1, 0], [1, 0], [0, -1], [0, 1]]
              : (type === 'B' ? [[-1, -1], [-1, 1], [1, -1], [1, 1]]
                : [[-1, 0], [1, 0], [0, -1], [0, 1], [-1, -1], [-1, 1], [1, -1], [1, 1]]);
            for (const [dr, dc] of dirs) {
              let nr = r + dr, nc = c + dc;
              while (this.inBounds(nr, nc)) {
                const t = brd[nr][nc];
                if (!t) {
                  pseudo.push({ fr: r, fc: c, tr: nr, tc: nc });
                } else {
                  if (t[0] === opp) pseudo.push({ fr: r, fc: c, tr: nr, tc: nc });
                  break;
                }
                nr += dr; nc += dc;
              }
            }
          }
        }
      }
      return pseudo.filter(m => {
        const next = this.applyMoveOnBoard(brd, castling, m);
        return !this.inCheck(next.board, side);
      });
    },
    evaluate(brd) {
      let score = 0;
      for (let r = 0; r < 8; r++) {
        for (let c = 0; c < 8; c++) {
          const p = brd[r][c];
          if (!p) continue;
          const v = this.VALS[p[1]] || 0;
          const centerBonus = (3.5 - Math.abs(3.5 - r)) * 4 + (3.5 - Math.abs(3.5 - c)) * 4;
          score += (p[0] === 'b' ? 1 : -1) * (v + centerBonus);
        }
      }
      return score;
    },
    aiMove() {
      if (this.winner || this.turn !== 'b') return;
      const moves = this.generateLegalMoves(this.board, 'b', this.castling, this.epTarget);
      if (!moves.length) return;
      let bestMove = moves[0], bestVal = -999999;
      const depth = this.aiLevel === 1 ? 1 : 2;

      for (const m of moves) {
        const next = this.applyMoveOnBoard(this.board, this.castling, m);
        let val = this.evaluate(next.board) + (Math.random() * 8);
        if (depth >= 2) {
          const oppMoves = this.generateLegalMoves(next.board, 'w', next.castling, next.epTarget);
          if (!oppMoves.length) {
            val = this.inCheck(next.board, 'w') ? 500000 : 0;
          } else {
            let worstForAi = 999999;
            for (const om of oppMoves) {
              const n2 = this.applyMoveOnBoard(next.board, next.castling, om);
              const ev = this.evaluate(n2.board);
              if (ev < worstForAi) worstForAi = ev;
            }
            val = worstForAi + (this.aiLevel === 3 ? 0 : Math.random() * 12);
          }
        }
        if (val > bestVal) {
          bestVal = val;
          bestMove = m;
        }
      }
      this.executeMove(bestMove);
    },
    coordLabel(r, c) {
      return 'abcdefgh'[c] + (8 - r);
    },
    executeMove(m) {
      const prev = this.cloneState();
      const piece = this.board[m.fr][m.fc];
      const captured = this.board[m.tr][m.tc] || (m.epCapture ? (this.turn === 'w' ? 'bP' : 'wP') : '');
      const next = this.applyMoveOnBoard(this.board, this.castling, m);
      this.board = next.board;
      this.castling = next.castling;
      this.epTarget = next.epTarget;
      const note = `${this.UNICODE[piece]} ${this.coordLabel(m.fr, m.fc)}${captured ? '×' : '→'}${this.coordLabel(m.tr, m.tc)}${m.promote ? '=♕' : ''}`;
      this.history.push({ prev, note });
      this.selected = null;
      this.legalMoves = [];
      this.turn = this.turn === 'w' ? 'b' : 'w';

      const nextMoves = this.generateLegalMoves(this.board, this.turn, this.castling, this.epTarget);
      const checked = this.inCheck(this.board, this.turn);
      if (!nextMoves.length) {
        if (checked) {
          this.winner = this.turn === 'w' ? 'b' : 'w';
          this.statusText = `🏆 Chiếu hết! ${this.winner === 'w' ? 'Trắng' : 'Đen'} thắng!`;
          if (this.mode === 'ai' && this.winner === 'w') {
            const pts = this.aiLevel * 250;
            submitScore('chess', pts, `Chiếu hết AI Cấp ${this.aiLevel}`);
            state.onNotify(`🏆 Chiếu hết! Bạn đã đánh bại AI Cờ Vua Cấp ${this.aiLevel} (+${pts} điểm)!`);
          }
        } else {
          this.winner = 'DRAW';
          this.statusText = '🤝 Hòa cờ (Stalemate)!';
        }
      } else {
        this.statusText = `${this.turn === 'w' ? '⚪ Lượt Trắng' : '⚫ Lượt Đen'}${checked ? ' — ⚠️ ĐANG BỊ CHIẾU!' : ''}`;
      }
      this.render();
      if (!this.winner && this.mode === 'ai' && this.turn === 'b') {
        setTimeout(() => this.aiMove(), 240);
      }
    },
    undo() {
      if (!this.history.length) return;
      const popOne = () => {
        const h = this.history.pop();
        if (!h) return;
        this.board = h.prev.board;
        this.turn = h.prev.turn;
        this.castling = h.prev.castling;
        this.epTarget = h.prev.epTarget;
      };
      popOne();
      if (this.mode === 'ai' && this.turn === 'b' && this.history.length) popOne();
      this.winner = null;
      this.selected = null;
      this.legalMoves = [];
      this.statusText = `${this.turn === 'w' ? '⚪ Lượt Trắng' : '⚫ Lượt Đen'}`;
      this.render();
    },
    clickSquare(r, c) {
      if (this.winner) return;
      if (this.mode === 'ai' && this.turn === 'b') return;
      const move = this.legalMoves.find(m => m.tr === r && m.tc === c);
      if (move) {
        this.executeMove(move);
        return;
      }
      const p = this.board[r][c];
      if (p && p[0] === this.turn) {
        this.selected = [r, c];
        const all = this.generateLegalMoves(this.board, this.turn, this.castling, this.epTarget);
        this.legalMoves = all.filter(m => m.fr === r && m.fc === c);
      } else {
        this.selected = null;
        this.legalMoves = [];
      }
      this.render();
    },
    render() {
      const grid = document.getElementById('xo-chess-grid');
      if (!grid) return;
      const rows = this.flipped ? [7, 6, 5, 4, 3, 2, 1, 0] : [0, 1, 2, 3, 4, 5, 6, 7];
      const cols = this.flipped ? [7, 6, 5, 4, 3, 2, 1, 0] : [0, 1, 2, 3, 4, 5, 6, 7];
      let html = '';
      for (const r of rows) {
        for (const c of cols) {
          const isLight = (r + c) % 2 === 0;
          const isSel = this.selected && this.selected[0] === r && this.selected[1] === c;
          const isLegal = this.legalMoves.some(m => m.tr === r && m.tc === c);
          const p = this.board[r][c];
          const bg = isSel ? 'bg-amber-500/50 ring-2 ring-amber-300' : (isLight ? 'bg-slate-700/90' : 'bg-slate-900/95');
          const pieceColor = p ? (p[0] === 'w' ? 'text-amber-100 drop-shadow-[0_2px_2px_rgba(0,0,0,0.9)]' : 'text-sky-400 drop-shadow-[0_2px_2px_rgba(0,0,0,0.9)]') : '';
          html += `<button data-r="${r}" data-c="${c}" class="xo-chess-sq aspect-square relative flex items-center justify-center ${bg} hover:brightness-110 transition select-none">
            ${p ? `<span class="text-2xl sm:text-3xl leading-none ${pieceColor}">${this.UNICODE[p]}</span>` : ''}
            ${isLegal ? `<span class="w-3 h-3 rounded-full ${p ? 'ring-2 ring-rose-400 bg-rose-500/60' : 'bg-amber-400/80'} absolute"></span>` : ''}
          </button>`;
        }
      }
      grid.innerHTML = html;
      grid.querySelectorAll('.xo-chess-sq').forEach(b => {
        b.onclick = () => this.clickSquare(Number(b.dataset.r), Number(b.dataset.c));
      });
      const stEl = document.getElementById('xo-chess-status');
      if (stEl) stEl.textContent = this.statusText;
      const histEl = document.getElementById('xo-chess-history');
      if (histEl) {
        histEl.innerHTML = this.history.length
          ? this.history.map((h, i) => `<span class="px-2 py-0.5 rounded bg-slate-900 border border-slate-800 text-[11px] font-mono text-slate-200">${i + 1}. ${esc(h.note)}</span>`).join(' ')
          : '<span class="text-xs text-slate-500">Chưa có nước đi nào. Bấm vào quân cờ Trắng để bắt đầu.</span>';
      }
    }
  };

  // ============================================================================
  // 4. RẮN SĂN MỒI ENGINE (20x20 Canvas, 4 Themes, Golden Bonus Apple, Mobile D-Pad)
  // ============================================================================
  const snake = {
    N: 20,
    body: [],
    dir: [1, 0],
    nextDir: [1, 0],
    food: [14, 10],
    bonus: null,
    score: 0,
    best: Number(localStorage.getItem('xo_snake_best') || 0),
    running: false,
    gameOver: false,
    theme: 'gold',
    timer: null,
    THEMES: {
      gold: { bg: '#0B0F17', grid: '#161F30', head: '#F59E0B', body: '#D97706', food: '#EF4444' },
      cyber: { bg: '#090D16', grid: '#1E1B4B', head: '#38BDF8', body: '#0284C7', food: '#F43F5E' },
      emerald: { bg: '#06120E', grid: '#064E3B', head: '#10B981', body: '#059669', food: '#FBBF24' }
    },
    start() {
      this.body = [[8, 10], [7, 10], [6, 10]];
      this.dir = [1, 0];
      this.nextDir = [1, 0];
      this.score = 0;
      this.running = true;
      this.gameOver = false;
      this.bonus = null;
      this.spawnFood();
      clearInterval(this.timer);
      this.timer = setInterval(() => this.tick(), 115);
      this.draw();
      this.updateMeta();
    },
    stop() {
      clearInterval(this.timer);
      this.running = false;
    },
    spawnFood() {
      const occ = new Set(this.body.map(([x, y]) => `${x},${y}`));
      const free = [];
      for (let y = 0; y < this.N; y++) for (let x = 0; x < this.N; x++) {
        if (!occ.has(`${x},${y}`)) free.push([x, y]);
      }
      if (free.length) this.food = free[Math.floor(Math.random() * free.length)];
    },
    setDir(dx, dy) {
      if (dx === -this.dir[0] && dy === -this.dir[1]) return;
      this.nextDir = [dx, dy];
      if (!this.running && !this.gameOver) this.start();
    },
    tick() {
      if (!this.running || state.activeGame !== 'snake') return;
      this.dir = this.nextDir;
      const [hx, hy] = this.body[0];
      const nx = hx + this.dir[0], ny = hy + this.dir[1];
      if (nx < 0 || nx >= this.N || ny < 0 || ny >= this.N || this.body.some(([bx, by]) => bx === nx && by === ny)) {
        this.running = false;
        this.gameOver = true;
        clearInterval(this.timer);
        if (this.score > this.best) {
          this.best = this.score;
          localStorage.setItem('xo_snake_best', String(this.best));
        }
        if (this.score >= 30) {
          submitScore('snake', this.score, `Dài ${this.body.length} đốt`);
        }
        this.draw();
        this.updateMeta();
        return;
      }
      this.body.unshift([nx, ny]);
      if (nx === this.food[0] && ny === this.food[1]) {
        this.score += 10;
        this.spawnFood();
        if (!this.bonus && Math.random() < 0.28) {
          this.bonus = { x: Math.floor(Math.random() * this.N), y: Math.floor(Math.random() * this.N), ttl: 35 };
        }
      } else if (this.bonus && nx === this.bonus.x && ny === this.bonus.y) {
        this.score += 40;
        this.bonus = null;
      } else {
        this.body.pop();
      }
      if (this.bonus) {
        this.bonus.ttl--;
        if (this.bonus.ttl <= 0) this.bonus = null;
      }
      if (this.score > this.best) {
        this.best = this.score;
        localStorage.setItem('xo_snake_best', String(this.best));
      }
      this.draw();
      this.updateMeta();
    },
    updateMeta() {
      const sEl = document.getElementById('xo-snake-score');
      if (sEl) sEl.innerHTML = `Điểm: <b class="text-amber-400">${this.score}</b> &bull; Kỷ lục: <b class="text-emerald-400">${this.best}</b>`;
    },
    draw() {
      const canvas = document.getElementById('xo-snake-canvas');
      if (!canvas) return;
      const ctx = canvas.getContext('2d');
      const W = canvas.width, H = canvas.height, cell = W / this.N;
      const pal = this.THEMES[this.theme] || this.THEMES.gold;
      ctx.fillStyle = pal.bg;
      ctx.fillRect(0, 0, W, H);
      ctx.strokeStyle = pal.grid;
      ctx.lineWidth = 1;
      for (let i = 0; i <= this.N; i++) {
        const p = Math.floor(i * cell) + 0.5;
        ctx.beginPath(); ctx.moveTo(p, 0); ctx.lineTo(p, H); ctx.stroke();
        ctx.beginPath(); ctx.moveTo(0, p); ctx.lineTo(W, p); ctx.stroke();
      }
      // Food
      ctx.fillStyle = pal.food;
      ctx.beginPath();
      ctx.arc((this.food[0] + 0.5) * cell, (this.food[1] + 0.5) * cell, cell * 0.38, 0, Math.PI * 2);
      ctx.fill();
      // Bonus
      if (this.bonus) {
        ctx.fillStyle = '#FACC15';
        ctx.beginPath();
        ctx.arc((this.bonus.x + 0.5) * cell, (this.bonus.y + 0.5) * cell, cell * 0.42, 0, Math.PI * 2);
        ctx.fill();
      }
      // Snake
      this.body.forEach(([x, y], idx) => {
        ctx.fillStyle = idx === 0 ? pal.head : pal.body;
        ctx.fillRect(x * cell + 2, y * cell + 2, cell - 4, cell - 4);
      });
      if (this.gameOver) {
        ctx.fillStyle = 'rgba(11, 15, 23, 0.82)';
        ctx.fillRect(0, 0, W, H);
        ctx.fillStyle = '#F59E0B';
        ctx.font = 'bold 22px Montserrat, sans-serif';
        ctx.textAlign = 'center';
        ctx.fillText('💀 KẾT THÚC — ' + this.score + ' ĐIỂM', W / 2, H / 2 - 8);
        ctx.fillStyle = '#E2E8F0';
        ctx.font = '13px Be Vietnam Pro, sans-serif';
        ctx.fillText('Bấm "Chơi Lại" hoặc phím Space để bắt đầu ván mới', W / 2, H / 2 + 20);
      }
    }
  };

  // ============================================================================
  // 5. 2048 ENGINE (4x4 Grid, Keyboard & Swipe, 5-step Undo, Best Score Sync)
  // ============================================================================
  const g2048 = {
    grid: [],
    score: 0,
    best: Number(localStorage.getItem('xo_2048_best') || 0),
    history: [],
    gameOver: false,
    newGame() {
      this.grid = Array(16).fill(0);
      this.score = 0;
      this.history = [];
      this.gameOver = false;
      this.addRandomTile();
      this.addRandomTile();
      this.render();
    },
    addRandomTile() {
      const empties = [];
      this.grid.forEach((v, i) => { if (!v) empties.push(i); });
      if (!empties.length) return;
      const idx = empties[Math.floor(Math.random() * empties.length)];
      this.grid[idx] = Math.random() < 0.9 ? 2 : 4;
    },
    undo() {
      if (!this.history.length) return;
      const prev = this.history.pop();
      this.grid = prev.grid;
      this.score = prev.score;
      this.gameOver = false;
      this.render();
    },
    slideLine(line) {
      const arr = line.filter(Boolean);
      const out = [];
      let gained = 0;
      for (let i = 0; i < arr.length; i++) {
        if (i + 1 < arr.length && arr[i] === arr[i + 1]) {
          const merged = arr[i] * 2;
          out.push(merged);
          gained += merged;
          i++;
        } else {
          out.push(arr[i]);
        }
      }
      while (out.length < 4) out.push(0);
      return { out, gained };
    },
    move(dir) {
      if (this.gameOver) return;
      const prevGrid = [...this.grid];
      const prevScore = this.score;
      let totalGain = 0;

      const getIdx = (r, c) => r * 4 + c;
      for (let i = 0; i < 4; i++) {
        let indices = [];
        if (dir === 'LEFT') indices = [getIdx(i, 0), getIdx(i, 1), getIdx(i, 2), getIdx(i, 3)];
        if (dir === 'RIGHT') indices = [getIdx(i, 3), getIdx(i, 2), getIdx(i, 1), getIdx(i, 0)];
        if (dir === 'UP') indices = [getIdx(0, i), getIdx(1, i), getIdx(2, i), getIdx(3, i)];
        if (dir === 'DOWN') indices = [getIdx(3, i), getIdx(2, i), getIdx(1, i), getIdx(0, i)];
        const line = indices.map(idx => this.grid[idx]);
        const { out, gained } = this.slideLine(line);
        totalGain += gained;
        indices.forEach((idx, k) => { this.grid[idx] = out[k]; });
      }

      const changed = this.grid.some((v, idx) => v !== prevGrid[idx]);
      if (!changed) return;

      this.history.push({ grid: prevGrid, score: prevScore });
      if (this.history.length > 5) this.history.shift();
      this.score += totalGain;
      if (this.score > this.best) {
        this.best = this.score;
        localStorage.setItem('xo_2048_best', String(this.best));
      }
      this.addRandomTile();
      if (!this.canMove()) {
        this.gameOver = true;
        const maxTile = Math.max(...this.grid);
        if (this.score >= 500) {
          submitScore('2048', this.score, `Ô lớn nhất: ${maxTile}`);
        }
      }
      this.render();
    },
    canMove() {
      if (this.grid.some(v => v === 0)) return true;
      for (let r = 0; r < 4; r++) {
        for (let c = 0; c < 4; c++) {
          const v = this.grid[r * 4 + c];
          if (c < 3 && this.grid[r * 4 + c + 1] === v) return true;
          if (r < 3 && this.grid[(r + 1) * 4 + c] === v) return true;
        }
      }
      return false;
    },
    tileClass(v) {
      const map = {
        0: 'bg-slate-900/80 text-transparent border-slate-800',
        2: 'bg-slate-800 text-slate-100 border-slate-700',
        4: 'bg-slate-700 text-amber-100 border-slate-600',
        8: 'bg-amber-700/80 text-white border-amber-500/60',
        16: 'bg-amber-600 text-white border-amber-400',
        32: 'bg-orange-600 text-white border-orange-400',
        64: 'bg-rose-600 text-white border-rose-400',
        128: 'bg-amber-500 text-slate-950 border-amber-300 shadow-md',
        256: 'bg-amber-400 text-slate-950 border-amber-200 shadow-md',
        512: 'bg-yellow-400 text-slate-950 border-white shadow-lg',
        1024: 'bg-sky-400 text-slate-950 border-white shadow-lg',
        2048: 'bg-emerald-400 text-slate-950 border-white shadow-xl'
      };
      return map[v] || 'bg-purple-500 text-white border-amber-300';
    },
    render() {
      const boardEl = document.getElementById('xo-2048-grid');
      if (!boardEl) return;
      boardEl.innerHTML = this.grid.map(v => `
        <div class="aspect-square rounded-2xl border flex items-center justify-center font-display font-black ${v >= 1024 ? 'text-xl sm:text-2xl' : 'text-2xl sm:text-3xl'} transition-all select-none ${this.tileClass(v)}">
          ${v || ''}
        </div>
      `).join('');
      const metaEl = document.getElementById('xo-2048-meta');
      if (metaEl) {
        const maxTile = Math.max(...this.grid);
        metaEl.innerHTML = `Điểm: <b class="text-amber-400">${this.score}</b> &bull; Kỷ lục: <b class="text-emerald-400">${this.best}</b> &bull; Ô cao nhất: <b class="text-sky-300">${maxTile}</b>`;
      }
    }
  };

  // ============================================================================
  // RENDER ACTIVE GAME WORKSPACE
  // ============================================================================
  function renderActiveGameStage() {
    const stage = document.getElementById('xo-mg-stage');
    if (!stage) return;

    // Update selector buttons
    document.querySelectorAll('.xo-mg-tab-btn').forEach(b => {
      const active = b.dataset.game === state.activeGame;
      b.className = `xo-mg-tab-btn px-3.5 py-2 rounded-xl text-xs font-extrabold transition flex items-center gap-2 shrink-0 ${
        active
          ? 'bg-amber-500 text-slate-950 shadow-lg border border-amber-300'
          : 'bg-slate-900 hover:bg-slate-800 text-slate-200 border border-slate-700'
      }`;
    });

    if (state.activeGame === 'caro') {
      const pInfo = state.getPlayerInfo() || { name: 'Khách', tier: 'BRONZE' };
      const isLogged = pInfo.name && pInfo.name.toLowerCase() !== 'khách';

      // Mode switch bar (3 modes: Online Lobby 2 Tài Khoản XO | Đấu Máy AI | 2 Người Cùng Máy)
      const modeSwitchHtml = `
        <div class="grid grid-cols-3 gap-2 bg-slate-950 p-1.5 rounded-xl border border-slate-800">
          <button data-cmode="online" class="xo-caro-mode-tab py-2 px-2 rounded-lg text-xs font-extrabold transition flex items-center justify-center gap-1.5 ${caro.mode === 'online' ? 'bg-amber-500 text-slate-950 shadow' : 'text-slate-300 hover:text-white'}">
            <span>🌐 Sảnh Đấu Online (2 Tài Khoản)</span>
          </button>
          <button data-cmode="ai" class="xo-caro-mode-tab py-2 px-2 rounded-lg text-xs font-extrabold transition flex items-center justify-center gap-1.5 ${caro.mode === 'ai' ? 'bg-amber-500 text-slate-950 shadow' : 'text-slate-300 hover:text-white'}">
            <span>🤖 Đấu Máy AI (5 Cấp)</span>
          </button>
          <button data-cmode="2p" class="xo-caro-mode-tab py-2 px-2 rounded-lg text-xs font-extrabold transition flex items-center justify-center gap-1.5 ${caro.mode === '2p' ? 'bg-amber-500 text-slate-950 shadow' : 'text-slate-300 hover:text-white'}">
            <span>👥 2 Người Cùng Máy</span>
          </button>
        </div>
      `;

      if (caro.mode === 'online' && !caro.onlineRoom) {
        stage.innerHTML = `
          <div class="space-y-3">
            ${modeSwitchHtml}
            <div class="bg-slate-950/90 border border-amber-500/40 rounded-2xl p-4 space-y-3">
              <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-2.5 border-b border-slate-800 pb-3">
                <div>
                  <h3 class="font-display text-sm sm:text-base font-black text-amber-300 uppercase">
                    🏟️ SẢNH BÀN CỜ CARO ONLINE (ĐẤU GIỮA 2 TÀI KHOẢN XO)
                  </h3>
                  <p class="text-xs text-slate-300 mt-0.5">
                    Tạo bàn hoặc chọn bàn đang chờ để thi đấu trực tiếp giữa 2 người chơi trên Website &amp; App Windows
                  </p>
                </div>
                <div class="text-xs shrink-0">
                  ${isLogged
                    ? `<span class="bg-slate-900 border border-slate-700 px-3 py-1.5 rounded-xl font-bold text-white inline-flex items-center gap-1.5">👤 Kỳ thủ: <b class="text-amber-300">${esc(pInfo.name)}</b> ${tierBadgeHtml(pInfo.tier)}</span>`
                    : `<span class="bg-rose-950/80 border border-rose-500/50 text-rose-200 px-3 py-1.5 rounded-xl font-bold inline-block">🔒 Hãy bấm "Đăng Nhập" ở góc trên để tạo/vào bàn</span>`}
                </div>
              </div>

              <!-- Thanh công cụ Tạo bàn & Vào bàn bằng Mã -->
              <div class="flex flex-wrap items-center justify-between gap-2">
                <div class="flex flex-wrap items-center gap-2">
                  <button id="xo-caro-create-room" class="bg-amber-500 hover:bg-amber-400 text-slate-950 font-extrabold px-4 py-2 rounded-xl text-xs shadow transition flex items-center gap-1.5">
                    <span>➕ Tạo Bàn Mới</span>
                  </button>
                  <label class="flex items-center gap-1.5 text-xs text-slate-200 cursor-pointer bg-slate-900 border border-slate-700 px-3 py-2 rounded-xl">
                    <input type="checkbox" id="xo-caro-online-obs" class="accent-amber-500" ${caro.obstacles ? 'checked' : ''}>
                    <span>🪨 Bàn có Đá cản</span>
                  </label>
                </div>
                <div class="flex items-center gap-1.5">
                  <input id="xo-caro-join-code-inp" type="text" maxlength="8" placeholder="Nhập mã bàn (VD: XO88)..."
                         class="bg-slate-900 border border-slate-700 focus:border-amber-400 rounded-xl px-3 py-1.5 text-xs text-white font-mono uppercase outline-none w-44">
                  <button id="xo-caro-join-code-btn" class="bg-sky-500 hover:bg-sky-400 text-slate-950 font-extrabold px-3.5 py-1.5 rounded-xl text-xs transition">
                    ⚔️ Vào Bàn
                  </button>
                  <button id="xo-caro-refresh-rooms" class="bg-slate-900 hover:bg-slate-800 text-slate-200 border border-slate-700 px-2.5 py-1.5 rounded-xl text-xs">
                    🔄
                  </button>
                </div>
              </div>

              <!-- Danh sách các bàn cờ đang mở -->
              <div id="xo-caro-rooms-grid" class="grid grid-cols-1 md:grid-cols-2 gap-3 pt-1"></div>
            </div>
          </div>
        `;
        stage.querySelectorAll('.xo-caro-mode-tab').forEach(b => {
          b.onclick = () => {
            caro.mode = b.dataset.cmode;
            if (caro.mode !== 'online') caro.newGame();
            renderActiveGameStage();
          };
        });
        document.getElementById('xo-caro-online-obs').onchange = e => { caro.obstacles = e.target.checked; };
        document.getElementById('xo-caro-create-room').onclick = () => caro.createOnlineRoom();
        document.getElementById('xo-caro-join-code-btn').onclick = () => {
          const v = document.getElementById('xo-caro-join-code-inp').value;
          caro.joinOnlineRoom(v);
        };
        document.getElementById('xo-caro-join-code-inp').onkeydown = e => {
          if (e.key === 'Enter') caro.joinOnlineRoom(e.target.value);
        };
        document.getElementById('xo-caro-refresh-rooms').onclick = () => caro.fetchRoomsList();
        caro.startPolling();
        caro.fetchRoomsList();
      } else if (caro.mode === 'online' && caro.onlineRoom) {
        const r = caro.onlineRoom;
        stage.innerHTML = `
          <div class="space-y-3">
            <div class="flex flex-wrap items-center justify-between gap-2 bg-slate-950/90 border border-slate-800 p-2.5 rounded-xl">
              <div class="flex items-center gap-2">
                <span class="bg-amber-500 text-slate-950 font-mono font-black text-xs px-2.5 py-1 rounded-lg">BÀN #${esc(r.code)}</span>
                <button id="xo-caro-copy-code" class="bg-slate-900 hover:bg-slate-800 text-sky-300 border border-slate-700 px-2.5 py-1 rounded-lg text-xs font-bold">
                  📋 Copy Mã Bàn
                </button>
              </div>
              <div class="flex items-center gap-1.5">
                <button id="xo-caro-online-new" class="bg-amber-500 hover:bg-amber-400 text-slate-950 px-3 py-1 rounded-lg text-xs font-extrabold">🔄 Ván Mới / Đổi Bên</button>
                <button id="xo-caro-online-resign" class="bg-slate-900 hover:bg-rose-600 text-rose-300 hover:text-white border border-rose-500/40 px-2.5 py-1 rounded-lg text-xs font-bold">🏳️ Xin Thua</button>
                <button id="xo-caro-online-leave" class="bg-slate-800 hover:bg-slate-700 text-slate-200 px-3 py-1 rounded-lg text-xs font-bold">🚪 Rời Bàn</button>
              </div>
            </div>
            <div id="xo-caro-online-match-bar"></div>
            <div id="xo-caro-status" class="text-xs sm:text-sm text-center bg-slate-900/90 border border-slate-800 py-2 rounded-xl"></div>
            <div class="flex justify-center">
              <canvas id="xo-caro-canvas" width="520" height="520" class="w-full max-w-[520px] aspect-square rounded-2xl border-2 border-amber-500/40 shadow-2xl cursor-pointer"></canvas>
            </div>
            <!-- Khung Chat Nhanh Trong Bàn Cờ Caro Online -->
            <div class="bg-slate-950/90 border border-slate-800 rounded-xl p-3 space-y-2">
              <div class="flex items-center justify-between text-xs">
                <span class="font-bold text-amber-300">💬 Chat Trong Bàn Cờ (#${esc(r.code)})</span>
                <div class="flex gap-1 overflow-x-auto no-scrollbar">
                  ${['🔥 Nước đi cao đấy!', '😎 Chạy đi đâu!', '⚡ Nhanh tay bạn ơi!', '🤝 Ván hay quá!'].map(q =>
                    `<button data-qchat="${esc(q)}" class="xo-caro-qchat text-[11px] bg-slate-900 hover:bg-amber-500/20 text-slate-300 hover:text-amber-300 border border-slate-800 px-2 py-0.5 rounded-lg">${esc(q)}</button>`
                  ).join('')}
                </div>
              </div>
              <div id="xo-caro-chat-feed" class="max-h-28 overflow-y-auto space-y-1 pr-1"></div>
              <div class="flex gap-2">
                <input id="xo-caro-chat-inp" type="text" maxlength="140" placeholder="Nhắn tin cho đối thủ trong bàn..."
                       class="flex-1 bg-slate-900 border border-slate-700 focus:border-amber-400 rounded-xl px-3 py-1.5 text-xs text-white outline-none">
                <button id="xo-caro-chat-send" class="bg-sky-500 hover:bg-sky-400 text-slate-950 font-extrabold px-3.5 py-1.5 rounded-xl text-xs">Gửi</button>
              </div>
            </div>
          </div>
        `;
        document.getElementById('xo-caro-copy-code').onclick = () => {
          navigator.clipboard.writeText(r.code).then(() => state.onNotify(`📋 Đã copy mã bàn #${r.code}! Gửi cho bạn bè để vào bàn ngay.`));
        };
        document.getElementById('xo-caro-online-new').onclick = () => caro.resetOnlineGame();
        document.getElementById('xo-caro-online-resign').onclick = () => caro.resignOnlineGame();
        document.getElementById('xo-caro-online-leave').onclick = () => caro.leaveOnlineRoom();
        document.getElementById('xo-caro-canvas').onclick = ev => caro.handleClick(ev);
        document.getElementById('xo-caro-chat-send').onclick = () => caro.sendOnlineChat();
        document.getElementById('xo-caro-chat-inp').onkeydown = e => { if (e.key === 'Enter') caro.sendOnlineChat(); };
        stage.querySelectorAll('.xo-caro-qchat').forEach(b => {
          b.onclick = () => caro.sendOnlineChat(b.dataset.qchat);
        });
        caro.startPolling();
        caro.renderOnlineRoomHeaderAndChat();
        caro.draw();
        caro.updateStatus();
      } else {
        stage.innerHTML = `
          <div class="space-y-3">
            ${modeSwitchHtml}
            <div class="flex flex-wrap items-center justify-between gap-2 bg-slate-950/80 border border-slate-800 p-3 rounded-xl">
              <div class="flex flex-wrap items-center gap-2 text-xs">
                <select id="xo-caro-level" class="bg-slate-900 border border-slate-700 rounded-lg px-2.5 py-1.5 text-amber-300 font-bold" ${caro.mode === '2p' ? 'disabled' : ''}>
                  <option value="1" ${caro.aiLevel === 1 ? 'selected' : ''}>🤖 AI Cấp 1: Tập Sự</option>
                  <option value="2" ${caro.aiLevel === 2 ? 'selected' : ''}>🤖 AI Cấp 2: Phong Trào</option>
                  <option value="3" ${caro.aiLevel === 3 ? 'selected' : ''}>🤖 AI Cấp 3: Kỳ Thủ</option>
                  <option value="4" ${caro.aiLevel === 4 ? 'selected' : ''}>🤖 AI Cấp 4: Cao Thủ</option>
                  <option value="5" ${caro.aiLevel === 5 ? 'selected' : ''}>🤖 AI Cấp 5: Đại Kiện Tướng</option>
                </select>
                <label class="flex items-center gap-1.5 text-slate-200 cursor-pointer bg-slate-900 border border-slate-700 px-2.5 py-1.5 rounded-lg">
                  <input type="checkbox" id="xo-caro-obs" class="accent-amber-500" ${caro.obstacles ? 'checked' : ''}>
                  <span>🪨 Chướng ngại vật</span>
                </label>
              </div>
              <div class="flex items-center gap-2">
                <button id="xo-caro-undo" class="bg-slate-900 hover:bg-slate-800 text-slate-200 border border-slate-700 px-3 py-1.5 rounded-xl text-xs font-bold">↩️ Đi lại</button>
                <button id="xo-caro-new" class="bg-amber-500 hover:bg-amber-400 text-slate-950 px-3.5 py-1.5 rounded-xl text-xs font-extrabold shadow">🔄 Ván Mới</button>
              </div>
            </div>
            <div id="xo-caro-status" class="text-xs sm:text-sm text-center bg-slate-900/90 border border-slate-800 py-2 rounded-xl"></div>
            <div class="flex justify-center">
              <canvas id="xo-caro-canvas" width="520" height="520" class="w-full max-w-[520px] aspect-square rounded-2xl border-2 border-amber-500/40 shadow-2xl cursor-pointer"></canvas>
            </div>
          </div>
        `;
        stage.querySelectorAll('.xo-caro-mode-tab').forEach(b => {
          b.onclick = () => {
            caro.mode = b.dataset.cmode;
            if (caro.mode !== 'online') caro.newGame();
            renderActiveGameStage();
          };
        });
        document.getElementById('xo-caro-level').onchange = e => { caro.aiLevel = Number(e.target.value); caro.newGame(); };
        document.getElementById('xo-caro-obs').onchange = e => { caro.obstacles = e.target.checked; caro.newGame(); };
        document.getElementById('xo-caro-undo').onclick = () => caro.undo();
        document.getElementById('xo-caro-new').onclick = () => caro.newGame();
        document.getElementById('xo-caro-canvas').onclick = ev => caro.handleClick(ev);
        if (!caro.board.length) caro.init();
        else { caro.draw(); caro.updateStatus(); }
      }
    } else if (state.activeGame === 'sudoku') {
      stage.innerHTML = `
        <div class="space-y-3">
          <div class="flex flex-wrap items-center justify-between gap-2 bg-slate-950/80 border border-slate-800 p-3 rounded-xl">
            <div class="flex items-center gap-2 flex-wrap">
              <select id="xo-sudoku-diff" class="bg-slate-900 border border-slate-700 rounded-lg px-2.5 py-1.5 text-xs text-amber-300 font-bold">
                <option value="easy" ${sudoku.difficulty === 'easy' ? 'selected' : ''}>🌱 Dễ (Easy)</option>
                <option value="medium" ${sudoku.difficulty === 'medium' ? 'selected' : ''}>🌿 Trung bình (Medium)</option>
                <option value="hard" ${sudoku.difficulty === 'hard' ? 'selected' : ''}>🔥 Khó (Hard)</option>
                <option value="evil" ${sudoku.difficulty === 'evil' ? 'selected' : ''}>👹 Ác mộng (Evil)</option>
                <option value="daily" ${sudoku.difficulty === 'daily' ? 'selected' : ''}>🌟 Thử thách Hằng ngày</option>
              </select>
              <span id="xo-sudoku-timer" class="font-mono text-xs sm:text-sm font-extrabold text-sky-300 bg-slate-900 border border-slate-700 px-3 py-1 rounded-lg">${sudoku.formatTime(sudoku.seconds)}</span>
            </div>
            <div class="flex items-center gap-2 flex-wrap">
              <button id="xo-sudoku-note-btn"></button>
              <button id="xo-sudoku-hint" class="bg-sky-500/20 hover:bg-sky-500 hover:text-slate-950 text-sky-300 border border-sky-500/40 px-3 py-1.5 rounded-xl text-xs font-bold transition">💡 Gợi ý</button>
              <button id="xo-sudoku-erase" class="bg-slate-900 hover:bg-slate-800 text-slate-200 border border-slate-700 px-3 py-1.5 rounded-xl text-xs font-bold">⌫ Xóa ô</button>
              <button id="xo-sudoku-new" class="bg-amber-500 hover:bg-amber-400 text-slate-950 px-3.5 py-1.5 rounded-xl text-xs font-extrabold shadow">🔄 Đề Mới</button>
            </div>
          </div>
          <div id="xo-sudoku-meta" class="text-xs text-center text-slate-300 bg-slate-900/90 border border-slate-800 py-1.5 rounded-xl"></div>
          <div id="xo-sudoku-grid" class="grid grid-cols-9 max-w-[430px] mx-auto border-2 border-amber-500/70 rounded-xl overflow-hidden shadow-2xl"></div>
          <div class="grid grid-cols-9 gap-1.5 max-w-[430px] mx-auto pt-1">
            ${[1, 2, 3, 4, 5, 6, 7, 8, 9].map(n => `<button data-num="${n}" class="xo-sudoku-num bg-slate-900 hover:bg-amber-500 hover:text-slate-950 text-amber-300 border border-slate-700 font-display font-black py-2.5 rounded-xl text-base transition">${n}</button>`).join('')}
          </div>
        </div>
      `;
      document.getElementById('xo-sudoku-diff').onchange = e => sudoku.newGame(e.target.value);
      document.getElementById('xo-sudoku-note-btn').onclick = () => { sudoku.notesMode = !sudoku.notesMode; sudoku.render(); };
      document.getElementById('xo-sudoku-hint').onclick = () => sudoku.hint();
      document.getElementById('xo-sudoku-erase').onclick = () => sudoku.input(0);
      document.getElementById('xo-sudoku-new').onclick = () => sudoku.newGame();
      stage.querySelectorAll('.xo-sudoku-num').forEach(b => {
        b.onclick = () => sudoku.input(Number(b.dataset.num));
      });
      if (!sudoku.board.length) sudoku.newGame('easy');
      else sudoku.render();
    } else if (state.activeGame === 'chess') {
      stage.innerHTML = `
        <div class="space-y-3">
          <div class="flex flex-wrap items-center justify-between gap-2 bg-slate-950/80 border border-slate-800 p-3 rounded-xl">
            <div class="flex items-center gap-2 flex-wrap text-xs">
              <select id="xo-chess-mode" class="bg-slate-900 border border-slate-700 rounded-lg px-2.5 py-1.5 text-white font-bold">
                <option value="ai" ${chess.mode === 'ai' ? 'selected' : ''}>🤖 Đấu Máy AI</option>
                <option value="2p" ${chess.mode === '2p' ? 'selected' : ''}>👥 2 Người Chơi</option>
              </select>
              <select id="xo-chess-level" class="bg-slate-900 border border-slate-700 rounded-lg px-2.5 py-1.5 text-amber-300 font-bold" ${chess.mode === '2p' ? 'disabled' : ''}>
                <option value="1" ${chess.aiLevel === 1 ? 'selected' : ''}>AI Cấp 1: Tập Sự</option>
                <option value="2" ${chess.aiLevel === 2 ? 'selected' : ''}>AI Cấp 2: Kỳ Thủ</option>
                <option value="3" ${chess.aiLevel === 3 ? 'selected' : ''}>AI Cấp 3: Kiện Tướng</option>
              </select>
            </div>
            <div class="flex items-center gap-2">
              <button id="xo-chess-flip" class="bg-slate-900 hover:bg-slate-800 text-slate-200 border border-slate-700 px-3 py-1.5 rounded-xl text-xs font-bold">🔃 Xoay bàn</button>
              <button id="xo-chess-undo" class="bg-slate-900 hover:bg-slate-800 text-slate-200 border border-slate-700 px-3 py-1.5 rounded-xl text-xs font-bold">↩️ Đi lại</button>
              <button id="xo-chess-new" class="bg-amber-500 hover:bg-amber-400 text-slate-950 px-3.5 py-1.5 rounded-xl text-xs font-extrabold shadow">🔄 Ván Mới</button>
            </div>
          </div>
          <div id="xo-chess-status" class="text-xs sm:text-sm font-bold text-center text-amber-300 bg-slate-900/90 border border-slate-800 py-2 rounded-xl"></div>
          <div id="xo-chess-grid" class="grid grid-cols-8 max-w-[440px] mx-auto border-2 border-amber-500/60 rounded-xl overflow-hidden shadow-2xl"></div>
          <div id="xo-chess-history" class="bg-slate-950/80 border border-slate-800 rounded-xl p-2.5 max-h-20 overflow-y-auto flex flex-wrap gap-1"></div>
        </div>
      `;
      document.getElementById('xo-chess-mode').onchange = e => { chess.mode = e.target.value; renderActiveGameStage(); chess.newGame(); };
      document.getElementById('xo-chess-level').onchange = e => { chess.aiLevel = Number(e.target.value); chess.newGame(); };
      document.getElementById('xo-chess-flip').onclick = () => { chess.flipped = !chess.flipped; chess.render(); };
      document.getElementById('xo-chess-undo').onclick = () => chess.undo();
      document.getElementById('xo-chess-new').onclick = () => chess.newGame();
      if (!chess.board.length) chess.newGame();
      else chess.render();
    } else if (state.activeGame === 'snake') {
      stage.innerHTML = `
        <div class="space-y-3">
          <div class="flex flex-wrap items-center justify-between gap-2 bg-slate-950/80 border border-slate-800 p-3 rounded-xl">
            <div class="flex items-center gap-2">
              <select id="xo-snake-theme" class="bg-slate-900 border border-slate-700 rounded-lg px-2.5 py-1.5 text-xs text-amber-300 font-bold">
                <option value="gold" ${snake.theme === 'gold' ? 'selected' : ''}>👑 Chủ đề: XO Hoàng Kim</option>
                <option value="cyber" ${snake.theme === 'cyber' ? 'selected' : ''}>⚡ Chủ đề: Neon Cyber</option>
                <option value="emerald" ${snake.theme === 'emerald' ? 'selected' : ''}>🌲 Chủ đề: Rừng Đế Chế</option>
              </select>
              <span id="xo-snake-score" class="text-xs sm:text-sm"></span>
            </div>
            <button id="xo-snake-start" class="bg-amber-500 hover:bg-amber-400 text-slate-950 px-4 py-1.5 rounded-xl text-xs font-extrabold shadow">▶️ Chơi Ngay / Chơi Lại</button>
          </div>
          <div class="flex justify-center">
            <canvas id="xo-snake-canvas" width="420" height="420" class="w-full max-w-[420px] aspect-square rounded-2xl border-2 border-amber-500/40 shadow-2xl"></canvas>
          </div>
          <div class="grid grid-cols-3 gap-2 max-w-[220px] mx-auto pt-1">
            <div></div>
            <button data-dir="0,-1" class="xo-snake-pad bg-slate-900 hover:bg-slate-800 text-white border border-slate-700 py-2 rounded-xl font-bold">▲</button>
            <div></div>
            <button data-dir="-1,0" class="xo-snake-pad bg-slate-900 hover:bg-slate-800 text-white border border-slate-700 py-2 rounded-xl font-bold">◀</button>
            <button data-dir="0,1" class="xo-snake-pad bg-slate-900 hover:bg-slate-800 text-white border border-slate-700 py-2 rounded-xl font-bold">▼</button>
            <button data-dir="1,0" class="xo-snake-pad bg-slate-900 hover:bg-slate-800 text-white border border-slate-700 py-2 rounded-xl font-bold">▶</button>
          </div>
        </div>
      `;
      document.getElementById('xo-snake-theme').onchange = e => { snake.theme = e.target.value; snake.draw(); };
      document.getElementById('xo-snake-start').onclick = () => snake.start();
      stage.querySelectorAll('.xo-snake-pad').forEach(b => {
        b.onclick = () => {
          const [dx, dy] = b.dataset.dir.split(',').map(Number);
          snake.setDir(dx, dy);
        };
      });
      if (!snake.body.length) snake.start();
      else { snake.draw(); snake.updateMeta(); }
    } else if (state.activeGame === '2048') {
      stage.innerHTML = `
        <div class="space-y-3">
          <div class="flex flex-wrap items-center justify-between gap-2 bg-slate-950/80 border border-slate-800 p-3 rounded-xl">
            <div id="xo-2048-meta" class="text-xs sm:text-sm"></div>
            <div class="flex items-center gap-2">
              <button id="xo-2048-undo" class="bg-slate-900 hover:bg-slate-800 text-slate-200 border border-slate-700 px-3 py-1.5 rounded-xl text-xs font-bold">↩️ Hoàn tác</button>
              <button id="xo-2048-new" class="bg-amber-500 hover:bg-amber-400 text-slate-950 px-3.5 py-1.5 rounded-xl text-xs font-extrabold shadow">🔄 Ván Mới</button>
            </div>
          </div>
          <div id="xo-2048-grid" class="grid grid-cols-4 gap-2.5 max-w-[380px] mx-auto bg-slate-950 p-3 rounded-2xl border-2 border-amber-500/40 shadow-2xl"></div>
          <div class="grid grid-cols-3 gap-2 max-w-[220px] mx-auto pt-1">
            <div></div>
            <button data-m="UP" class="xo-2048-btn bg-slate-900 hover:bg-slate-800 text-white border border-slate-700 py-2 rounded-xl font-bold">▲</button>
            <div></div>
            <button data-m="LEFT" class="xo-2048-btn bg-slate-900 hover:bg-slate-800 text-white border border-slate-700 py-2 rounded-xl font-bold">◀</button>
            <button data-m="DOWN" class="xo-2048-btn bg-slate-900 hover:bg-slate-800 text-white border border-slate-700 py-2 rounded-xl font-bold">▼</button>
            <button data-m="RIGHT" class="xo-2048-btn bg-slate-900 hover:bg-slate-800 text-white border border-slate-700 py-2 rounded-xl font-bold">▶</button>
          </div>
        </div>
      `;
      document.getElementById('xo-2048-undo').onclick = () => g2048.undo();
      document.getElementById('xo-2048-new').onclick = () => g2048.newGame();
      stage.querySelectorAll('.xo-2048-btn').forEach(b => {
        b.onclick = () => g2048.move(b.dataset.m);
      });
      if (!g2048.grid.length) g2048.newGame();
      else g2048.render();
    }
    renderLeaderboardPanel();
  }

  // Global keyboard handler when Mini Games tab is visible
  window.addEventListener('keydown', ev => {
    const mount = document.getElementById('xo-minigames-mount');
    if (!mount || mount.offsetParent === null) return;
    if (['INPUT', 'TEXTAREA', 'SELECT'].includes((ev.target && ev.target.tagName) || '')) return;

    if (state.activeGame === 'sudoku') {
      if (ev.key >= '1' && ev.key <= '9') { ev.preventDefault(); sudoku.input(Number(ev.key)); }
      else if (ev.key === 'Backspace' || ev.key === 'Delete' || ev.key === '0') { ev.preventDefault(); sudoku.input(0); }
      else if (ev.key === 'n' || ev.key === 'N') { ev.preventDefault(); sudoku.notesMode = !sudoku.notesMode; sudoku.render(); }
    } else if (state.activeGame === 'snake') {
      const k = ev.key.toLowerCase();
      if (k === 'arrowup' || k === 'w') { ev.preventDefault(); snake.setDir(0, -1); }
      else if (k === 'arrowdown' || k === 's') { ev.preventDefault(); snake.setDir(0, 1); }
      else if (k === 'arrowleft' || k === 'a') { ev.preventDefault(); snake.setDir(-1, 0); }
      else if (k === 'arrowright' || k === 'd') { ev.preventDefault(); snake.setDir(1, 0); }
      else if (k === ' ' && snake.gameOver) { ev.preventDefault(); snake.start(); }
    } else if (state.activeGame === '2048') {
      const k = ev.key.toLowerCase();
      if (k === 'arrowup' || k === 'w') { ev.preventDefault(); g2048.move('UP'); }
      else if (k === 'arrowdown' || k === 's') { ev.preventDefault(); g2048.move('DOWN'); }
      else if (k === 'arrowleft' || k === 'a') { ev.preventDefault(); g2048.move('LEFT'); }
      else if (k === 'arrowright' || k === 'd') { ev.preventDefault(); g2048.move('RIGHT'); }
      else if ((ev.ctrlKey || ev.metaKey) && k === 'z') { ev.preventDefault(); g2048.undo(); }
    }
  });

  window.XOMinigamesHub = {
    mount(containerId, options = {}) {
      if (options.getPlayerInfo) state.getPlayerInfo = options.getPlayerInfo;
      if (options.onNotify) state.onNotify = options.onNotify;
      const root = document.getElementById(containerId);
      if (!root) return;

      root.innerHTML = `
        <div class="space-y-4">
          <!-- Game Selector Bar (5 Approved Games) -->
          <div class="premium-card p-4 rounded-2xl border-l-4 border-l-amber-400">
            <div class="flex flex-col md:flex-row md:items-center justify-between gap-3 pb-3 mb-3 border-b border-slate-800">
              <div>
                <h2 class="font-display text-sm sm:text-base font-black text-amber-300 uppercase tracking-wide flex items-center gap-2">
                  <span>🎮 SẢNH GIẢI TRÍ CHỜ KÈO XO (5 TRÒ CHƠI TRÍ TUỆ)</span>
                </h2>
                <p class="text-xs text-slate-300 mt-0.5">
                  Thư giãn trong lúc chờ kèo AOE lên sóng &bull; Dùng chung tài khoản XO &amp; vinh danh Bảng Xếp Hạng toàn hệ thống
                </p>
              </div>
              <div class="flex items-center gap-2 overflow-x-auto no-scrollbar">
                ${GAMES_META.map(g => `
                  <button data-game="${g.key}" class="xo-mg-tab-btn">
                    <span>${g.icon}</span>
                    <span>${esc(g.name)}</span>
                  </button>
                `).join('')}
              </div>
            </div>

            <div class="grid grid-cols-1 lg:grid-cols-12 gap-4 items-start">
              <div id="xo-mg-stage" class="lg:col-span-8 bg-slate-950/60 border border-slate-800/90 rounded-2xl p-3.5 sm:p-4"></div>
              <div class="lg:col-span-4 bg-slate-950/60 border border-slate-800/90 rounded-2xl p-3.5 sm:p-4 space-y-3">
                <div class="flex items-center justify-between border-b border-slate-800 pb-2">
                  <h3 id="xo-mg-leaderboard-title" class="font-display text-xs sm:text-sm font-black text-amber-300 uppercase">🏆 Bảng Xếp Hạng</h3>
                  <button id="xo-mg-refresh-lb" class="text-[11px] text-sky-300 hover:text-amber-300 font-bold">🔄 Làm mới</button>
                </div>
                <div id="xo-mg-leaderboard-list" class="space-y-2 max-h-[380px] overflow-y-auto pr-1"></div>
                <div class="bg-slate-900/90 border border-slate-800 rounded-xl p-3 text-[11px] text-slate-300 space-y-1">
                  <div class="font-bold text-amber-300">💡 Mẹo nhỏ:</div>
                  <div>&bull; Điểm số và kỷ lục tự động lưu theo <b>Tài khoản XO</b> bạn đang đăng nhập.</div>
                  <div>&bull; Cả 5 trò chơi này cũng có mặt trực tiếp trên <b>App Windows (Tool Bảng Quân AOE PC)</b> ở tab <b>🎮 Giải Trí Chờ Kèo</b>!</div>
                </div>
              </div>
            </div>
          </div>
        </div>
      `;

      root.querySelectorAll('.xo-mg-tab-btn').forEach(btn => {
        btn.onclick = () => {
          if (state.activeGame === 'snake') snake.stop();
          state.activeGame = btn.dataset.game;
          renderActiveGameStage();
          fetchLeaderboard(state.activeGame);
        };
      });
      const refreshBtn = document.getElementById('xo-mg-refresh-lb');
      if (refreshBtn) refreshBtn.onclick = () => fetchLeaderboard(state.activeGame);

      renderActiveGameStage();
      fetchLeaderboard();
    },
    selectGame(gameKey) {
      if (GAMES_META.some(g => g.key === gameKey)) {
        state.activeGame = gameKey;
        renderActiveGameStage();
        fetchLeaderboard(gameKey);
      }
    }
  };
})();

