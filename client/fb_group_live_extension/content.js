/* AOE BY XO - Tiện ích tự động bắt Comment Facebook Group Live đẩy lên OBS */
(() => {
  const DEFAULT_SERVER = 'https://aoe-tracker.onrender.com';
  let cfg = {
    enabled: false,
    server: localStorage.getItem('aoe_fb_server') || DEFAULT_SERVER,
    streamer: localStorage.getItem('aoe_fb_streamer') || 'XO',
    password: localStorage.getItem('aoe_fb_password') || ''
  };

  const seen = new Set();
  let initialized = false;
  let pushedCount = 0;

  const panel = document.createElement('div');
  panel.id = '__aoe_fb_ext_panel';
  panel.style.cssText = 'position:fixed;bottom:14px;left:14px;z-index:999999;background:#11151b;color:#e7ebf0;border:1.5px solid #2563eb;padding:8px 12px;border-radius:12px;font-family:Segoe UI,sans-serif;font-size:12px;box-shadow:0 8px 24px rgba(0,0,0,0.7);display:flex;align-items:center;gap:8px;';
  panel.innerHTML = `
    <span style="color:#60a5fa;font-weight:bold;">🔵 AOE FB Live</span>
    <input id="__aoe_fb_streamer" value="${cfg.streamer}" placeholder="Tên máy" style="width:70px;background:#181e28;color:#fff;border:1px solid #2b3541;border-radius:6px;padding:2px 6px;font-size:11px;" />
    <input id="__aoe_fb_pass" type="password" value="${cfg.password}" placeholder="Mật khẩu" style="width:65px;background:#181e28;color:#fff;border:1px solid #2b3541;border-radius:6px;padding:2px 6px;font-size:11px;" />
    <button id="__aoe_fb_toggle" style="background:#2563eb;color:#fff;border:none;border-radius:6px;padding:3px 9px;font-weight:bold;cursor:pointer;font-size:11px;">BẬT</button>
    <span id="__aoe_fb_stat" style="color:#94a3b8;font-size:11px;">Đang tắt</span>
  `;
  document.body.appendChild(panel);

  const btn = panel.querySelector('#__aoe_fb_toggle');
  const stat = panel.querySelector('#__aoe_fb_stat');
  const inpStreamer = panel.querySelector('#__aoe_fb_streamer');
  const inpPass = panel.querySelector('#__aoe_fb_pass');

  btn.addEventListener('click', () => {
    cfg.streamer = inpStreamer.value.trim() || 'XO';
    cfg.password = inpPass.value.trim();
    localStorage.setItem('aoe_fb_streamer', cfg.streamer);
    localStorage.setItem('aoe_fb_password', cfg.password);
    cfg.enabled = !cfg.enabled;
    initialized = false;
    if (cfg.enabled) {
      btn.textContent = 'ĐANG BẬT';
      btn.style.background = '#10b981';
      stat.textContent = `Đang quét -> ${cfg.streamer} (${pushedCount})`;
      scanComments();
    } else {
      btn.textContent = 'BẬT';
      btn.style.background = '#2563eb';
      stat.textContent = 'Đang tắt';
    }
  });

  const ignoreWords = new Set(['Thích', 'Phản hồi', 'Chia sẻ', 'Theo dõi', 'Viết bình luận...', 'Bình luận', 'Tất cả bình luận', 'Phù hợp nhất', 'Mới nhất']);

  function scanComments() {
    if (!cfg.enabled) return;
    const articles = document.querySelectorAll('div[role="article"]');
    articles.forEach(art => {
      const authorEl = art.querySelector('a[role="link"] span[dir="auto"], span.xt0psk2 span[dir="auto"], h3 span, h4 span');
      const author = (authorEl ? authorEl.innerText : '').trim();
      if (!author || ignoreWords.has(author)) return;

      const textDivs = art.querySelectorAll('div[dir="auto"]');
      let bodyText = '';
      textDivs.forEach(td => {
        const val = (td.innerText || '').trim();
        if (val && val !== author && !ignoreWords.has(val) && !val.startsWith('Phản hồi ')) {
          bodyText = val;
        }
      });
      if (!bodyText || bodyText.length > 350) return;

      const key = author + '::' + bodyText;
      if (seen.has(key)) return;
      seen.add(key);
      if (!initialized) return;

      pushedCount++;
      stat.textContent = `Đã đẩy: ${pushedCount}`;

      fetch(cfg.server + '/api', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          action: 'pushFacebookComment',
          streamerName: cfg.streamer,
          password: cfg.password,
          authorName: author,
          fbAuthor: author,
          text: bodyText,
          commentId: key,
          fbCommentId: key
        })
      }).catch(() => {});
    });
    initialized = true;
  }

  setInterval(scanComments, 1500);
})();

