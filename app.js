(function () {
  'use strict';

  /* ------------------------------------------------------------ constants */
  const STATUSES = [['wishlist', 'Wishlist'], ['applied', 'Applied'], ['oa', 'Online test'],
                    ['interview', 'Interviewing'], ['offer', 'Offer'], ['rejected', 'Rejected']];
  const STATUS_LABEL = Object.fromEntries(STATUSES);
  const PROB_STATUS = [['todo', 'Not yet'], ['solved', 'Solved'], ['revisit', 'Needs another look']];
  const CONF_LABEL = { 1: 'Blank', 2: 'Barely', 3: 'Slowly', 4: 'Fine', 5: 'Instantly' };
  const TOPICS = ['Arrays', 'Strings', 'Linked List', 'Stacks', 'Queues', 'Trees', 'Graphs', 'Recursion',
                  'Dynamic Programming', 'Sorting & Searching', 'Hashing', 'Greedy', 'SQL', 'OOP', 'DBMS', 'OS', 'Networks'];
  const SOURCES = ['Campus', 'Referral', 'LinkedIn', 'Careers page', 'Naukri', 'Off-campus drive', 'Other'];
  const PLATFORMS = ['LeetCode', 'GeeksforGeeks', 'HackerRank', 'CodeChef', 'Codeforces', 'InterviewBit', 'Other'];
  const MOCK_KINDS = [['aptitude', 'Aptitude'], ['dsa', 'Coding / DSA'], ['technical', 'Technical'],
                      ['hr', 'HR'], ['interview', 'Mock interview'], ['other', 'Other']];

  const S = {
    token: null, name: '', email: '', registering: false,
    apps: [], probs: [], mocks: [],
    f: { appStatus: 'all', appQ: '', pStatus: '', pTopic: '', pDiff: '', pQ: '' },
  };

  /* ------------------------------------------------------------- helpers */
  const $ = (s, r) => (r || document).querySelector(s);
  const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  const safeUrl = (u) => (/^https?:\/\//i.test(u || '') ? u : '');
  const pad = (n) => String(n).padStart(2, '0');
  const iso = (d) => `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
  const parse = (s) => new Date(s + 'T00:00:00');
  const todayISO = () => iso(new Date());
  const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
  const fmt = (s) => { if (!s) return ''; const d = parse(s); return `${d.getDate()} ${MONTHS[d.getMonth()]}`; };
  const diffDays = (s) => Math.round((parse(s) - parse(todayISO())) / 86400000);
  function rel(s) {
    if (!s) return '';
    const n = diffDays(s);
    if (n === 0) return 'today'; if (n === 1) return 'tomorrow'; if (n === -1) return 'yesterday';
    return n > 0 ? `in ${n} days` : `${-n} days ago`;
  }
  const num = (v, d = 1) => (v == null ? '' : Number(v).toFixed(d).replace(/\.?0+$/, ''));

  let toastTimer;
  function toast(msg, isErr) {
    const t = $('#toast'); t.textContent = msg; t.className = 'toast' + (isErr ? ' err' : '');
    clearTimeout(toastTimer); toastTimer = setTimeout(() => t.classList.add('hidden'), 2800);
  }

  async function api(path, opts) {
    opts = opts || {};
    const headers = { 'Content-Type': 'application/json' };
    if (S.token) headers.Authorization = 'Bearer ' + S.token;
    const res = await fetch(path, { method: opts.method || 'GET', headers, body: opts.body ? JSON.stringify(opts.body) : undefined });
    if (res.status === 401 && S.token && !path.startsWith('/api/login')) { logout(); throw new Error('Please sign in again'); }
    if (res.status === 204) return null;
    let data = null; try { data = await res.json(); } catch (e) { /* not json */ }
    if (!res.ok) {
      let msg = res.statusText;
      if (data && typeof data.detail === 'string') msg = data.detail;
      else if (data && Array.isArray(data.detail)) msg = data.detail.map((d) => (d.msg || '').replace(/^Value error, /, '')).join('; ');
      throw new Error(msg);
    }
    return data;
  }
  const store = {
    get: (k) => { try { return localStorage.getItem(k); } catch (e) { return null; } },
    set: (k, v) => { try { localStorage.setItem(k, v); } catch (e) { /* ignore */ } },
    del: (k) => { try { localStorage.removeItem(k); } catch (e) { /* ignore */ } },
  };

  /* ---------------------------------------------------------------- auth */
  function showLogin() {
    $('#shell').classList.add('hidden'); $('#login').classList.remove('hidden');
    $('#loginForm').password && ($('#loginForm').password.value = '');
  }
  function enter() {
    $('#login').classList.add('hidden'); $('#shell').classList.remove('hidden');
    $('#who').textContent = S.name ? `${S.name} · ${S.email}` : S.email;
    route();
  }
  function logout() { S.token = null; store.del('pl_token'); store.del('pl_name'); store.del('pl_email'); location.hash = ''; showLogin(); }

  function setMode(registering) {
    S.registering = registering;
    $('.name-field').classList.toggle('hidden', !registering);
    $('#loginSubmit').textContent = registering ? 'Create account' : 'Sign in';
    $('#loginToggle').textContent = registering ? 'I already have an account' : 'Create an account';
    $('#loginError').textContent = '';
  }

  $('#loginToggle').addEventListener('click', () => setMode(!S.registering));
  $('#loginForm').addEventListener('submit', async (e) => {
    e.preventDefault();
    const f = e.target; $('#loginError').textContent = '';
    try {
      const r = await api(S.registering ? '/api/register' : '/api/login',
        { method: 'POST', body: { email: f.email.value, password: f.password.value, name: f.name.value } });
      S.token = r.token; S.name = r.name; S.email = r.email;
      store.set('pl_token', r.token); store.set('pl_name', r.name || ''); store.set('pl_email', r.email);
      enter();
    } catch (err) { $('#loginError').textContent = err.message; }
  });

  /* ------------------------------------------------------------- drawer */
  function field(f, v) {
    const val = v == null ? '' : v;
    const cls = 'field' + (f.full ? ' full' : '');
    let input;
    if (f.t === 'select') {
      input = `<select name="${f.n}">${f.opts.map(([k, l]) => `<option value="${esc(k)}" ${String(k) === String(val) ? 'selected' : ''}>${esc(l)}</option>`).join('')}</select>`;
    } else if (f.t === 'textarea') {
      input = `<textarea name="${f.n}" maxlength="4000">${esc(val)}</textarea>`;
    } else {
      input = `<input name="${f.n}" type="${f.t || 'text'}" value="${esc(val)}" ${f.req ? 'required' : ''} ${f.step ? `step="${f.step}"` : ''}
               ${f.min != null ? `min="${f.min}"` : ''} ${f.list ? `list="dl-${f.n}"` : ''} ${f.ph ? `placeholder="${esc(f.ph)}"` : ''} maxlength="200">`;
    }
    const dl = f.list ? `<datalist id="dl-${f.n}">${f.list.map((o) => `<option value="${esc(o)}">`).join('')}</datalist>` : '';
    return `<label class="${cls}">${esc(f.l)}${input}${dl}</label>`;
  }

  function openDrawer(title, html) {
    const d = $('#drawer'); d.innerHTML = `<h2>${esc(title)}</h2>${html}`;
    d.classList.remove('hidden'); $('#drawerMask').classList.remove('hidden'); d.setAttribute('aria-hidden', 'false');
    const first = d.querySelector('input, select, textarea, button'); if (first) first.focus();
    return d;
  }
  function closeDrawer() {
    $('#drawer').classList.add('hidden'); $('#drawerMask').classList.add('hidden'); $('#drawer').setAttribute('aria-hidden', 'true');
  }
  document.addEventListener('keydown', (e) => { if (e.key === 'Escape') closeDrawer(); });

  function formDrawer(title, fields, values, onSave, onDelete) {
    const html = `<form>${fields.map((f) => field(f, values[f.n])).join('')}
      <div class="foot"><button class="btn primary" type="submit">Save</button>
      <button class="btn" type="button" data-act="close-drawer">Cancel</button></div></form>`;
    const d = openDrawer(title, html);
    d.querySelector('form').addEventListener('submit', async (e) => {
      e.preventDefault();
      const out = {};
      fields.forEach((f) => {
        let v = e.target.elements[f.n].value;
        if (f.t === 'number') v = v === '' ? null : Number(v);
        else if (f.t === 'date' || f.nullable) v = v === '' ? null : v;
        if (f.int && v != null) v = parseInt(v, 10);
        out[f.n] = v;
      });
      try { await onSave(out); closeDrawer(); } catch (err) { toast(err.message, true); }
    });
  }

  /* --------------------------------------------------------------- pages */
  const view = () => $('#view');

  function head(title, right) {
    const d = new Date();
    const line = d.toLocaleDateString('en-GB', { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' });
    return `<div class="page-head"><h1>${title}</h1><div class="tools">${right || ''}<span class="dateline">${line}</span></div></div>`;
  }

  /* ---- overview */
  async function pageDashboard() {
    const d = await api('/api/dashboard');
    S.name = d.user.name || S.name; $('#who').textContent = S.name ? `${S.name} · ${S.email}` : S.email;
    const t = d.totals;
    const nothing = t.applications === 0 && t.problems === 0 && d.mocks.length === 0;
    const hour = new Date().getHours();
    const greet = hour < 12 ? 'Morning' : hour < 17 ? 'Afternoon' : 'Evening';
    let html = head(S.name ? `${greet}, ${esc(S.name.split(' ')[0])}` : 'Overview');

    if (nothing) {
      return view().innerHTML = html + `<p class="empty">Nothing recorded yet. Start with the companies you plan to apply to, or log the last problem you solved.</p>
        <p><button class="btn primary" data-act="add-app">Add an application</button>
        <button class="btn" data-act="add-prob" style="margin-left:8px">Log a problem</button>
        <button class="linkbtn" data-act="demo" style="margin-left:16px">Fill with sample data</button></p>`;
    }

    html += `<div class="figures">
      <div class="figure"><div class="n">${t.active}</div><div class="l">in progress, of ${t.applications} tracked</div></div>
      <div class="figure"><div class="n">${t.offers}</div><div class="l">offer${t.offers === 1 ? '' : 's'}</div></div>
      <div class="figure"><div class="n">${t.solved}</div><div class="l">problems solved, ${t.problems - t.solved} waiting</div></div>
      <div class="figure ${t.due ? 'alert' : ''}"><div class="n">${t.due}</div><div class="l">due for review</div></div>
      <div class="figure"><div class="n">${t.streak}</div><div class="l">day streak</div></div></div>`;

    const total = Object.values(d.pipeline).reduce((a, b) => a + b, 0) || 1;
    html += `<div class="block"><h2>Pipeline</h2>
      <div class="pipe">${STATUSES.map(([k]) => d.pipeline[k] ? `<i class="s-${k}" style="width:${d.pipeline[k] / total * 100}%" title="${STATUS_LABEL[k]}: ${d.pipeline[k]}"></i>` : '').join('')}</div>
      <div class="pipe-legend">${STATUSES.map(([k, l]) => `<span class="s-${k}"><b class="sq"></b>${l} <span class="mono">${d.pipeline[k]}</span></span>`).join('')}</div></div>`;

    html += `<div class="cols"><div class="block"><h2>Coming up</h2>${d.upcoming.length ? d.upcoming.map((a) => `
        <div class="list-row"><div class="main"><b>${esc(a.company)}</b> <span class="sub">${esc(a.role)}</span><div class="sub">${esc(a.next_step || STATUS_LABEL[a.status])}</div></div>
        <div class="mono sub" style="text-align:right;white-space:nowrap">${fmt(a.next_date)}<br>${rel(a.next_date)}</div></div>`).join('') : '<p class="empty">No dates ahead. Add one to an application.</p>'}</div>

      <div class="block"><h2>Review queue</h2>${d.due.length ? d.due.map((p) => `
        <div class="list-row"><div class="main"><b>${esc(p.title)}</b><div class="sub">${esc(p.topic || 'No topic')} · due ${rel(p.next_review)}</div></div>
        <button class="btn small" data-act="review" data-id="${p.id}">Review</button></div>`).join('') : '<p class="empty">Nothing is due. Good.</p>'}</div></div>`;

    const maxT = Math.max(1, ...d.topics.map((x) => x.count));
    html += `<div class="cols"><div class="block"><h2>Solved by topic</h2>${d.topics.length ? d.topics.map((x) => `
        <div class="bar-row"><span>${esc(x.name)}</span><span class="track"><i style="width:${x.count / maxT * 100}%"></i></span><span class="v">${x.count}</span></div>`).join('') : '<p class="empty">Solve something and it shows up here.</p>'}
        <div class="heat-note mono">easy ${d.difficulty.easy} · medium ${d.difficulty.medium} · hard ${d.difficulty.hard}</div></div>
      <div class="block"><h2>Last 12 weeks</h2>${heatmap(d)}
        <div class="heat-note">Each square is a day. Darker means more problems, reviews or tests logged.</div></div></div>`;

    if (d.mocks.length) {
      html += `<div class="block"><h2>Recent mock scores</h2>${d.mocks.slice(-5).reverse().map((m) => `
        <div class="list-row"><div class="main"><b>${esc(m.title)}</b> <span class="sub">${esc(kindLabel(m.kind))}</span></div>
        <div class="mono">${m.pct}%<span class="sub"> · ${fmt(m.taken_on)}</span></div></div>`).join('')}</div>`;
    }
    view().innerHTML = html;
  }

  const kindLabel = (k) => (MOCK_KINDS.find((x) => x[0] === k) || [0, k])[1];

  function heatmap(d) {
    const end = parse(d.today); const start = new Date(end); start.setDate(end.getDate() - 83);
    const lead = (start.getDay() + 6) % 7; let cells = '';
    for (let i = 0; i < lead; i++) cells += '<i class="pad"></i>';
    for (let i = 0; i < 84; i++) {
      const day = new Date(start); day.setDate(start.getDate() + i);
      const key = iso(day); const c = d.heatmap[key] || 0;
      cells += `<i class="${c >= 3 ? 'l3' : c === 2 ? 'l2' : c === 1 ? 'l1' : ''}" title="${fmt(key)}: ${c}"></i>`;
    }
    return `<div class="heat">${cells}</div>`;
  }

  /* ---- applications */
  const APP_FIELDS = () => [
    { n: 'company', l: 'Company', req: true, full: true },
    { n: 'role', l: 'Role' },
    { n: 'status', l: 'Stage', t: 'select', opts: STATUSES },
    { n: 'ctc_lpa', l: 'CTC (LPA)', t: 'number', step: '0.1', min: 0 },
    { n: 'location', l: 'Location' },
    { n: 'source', l: 'How you found it', list: SOURCES },
    { n: 'applied_on', l: 'Applied on', t: 'date' },
    { n: 'next_date', l: 'Next date', t: 'date' },
    { n: 'next_step', l: 'What happens then', full: true, ph: 'e.g. Online assessment, HR round' },
    { n: 'link', l: 'Link', full: true, ph: 'https://' },
    { n: 'notes', l: 'Notes', t: 'textarea', full: true },
  ];

  async function pageApplications() {
    S.apps = await api('/api/applications');
    renderApplications();
  }
  function renderApplications() {
    const f = S.f; const q = f.appQ.trim().toLowerCase();
    const counts = Object.fromEntries(STATUSES.map(([k]) => [k, S.apps.filter((a) => a.status === k).length]));
    const list = S.apps.filter((a) => (f.appStatus === 'all' || a.status === f.appStatus) &&
      (!q || `${a.company} ${a.role} ${a.location}`.toLowerCase().includes(q)));
    let html = head('Applications', '<button class="btn primary" data-act="add-app">Add application</button>');
    html += `<div class="filters"><div class="tabs"><button data-tab="all" class="${f.appStatus === 'all' ? 'on' : ''}">All<span class="c">${S.apps.length}</span></button>
      ${STATUSES.map(([k, l]) => `<button data-tab="${k}" class="${f.appStatus === k ? 'on' : ''}">${l}<span class="c">${counts[k]}</span></button>`).join('')}</div>
      <input class="grow" id="appQ" type="search" placeholder="Search company, role, city" value="${esc(f.appQ)}"></div>`;
    if (!list.length) {
      html += `<p class="empty">${S.apps.length ? 'Nothing matches that filter.' : 'No applications yet.'}</p>`;
    } else {
      html += `<div class="tbl-wrap"><table><thead><tr><th>Company</th><th>Stage</th><th class="r">CTC</th><th>Next</th><th></th></tr></thead><tbody>
        ${list.map((a) => {
          const link = safeUrl(a.link);
          return `<tr><td><b>${link ? `<a href="${esc(link)}" target="_blank" rel="noopener noreferrer">${esc(a.company)}</a>` : esc(a.company)}</b>
            <div class="sub">${esc([a.role, a.location].filter(Boolean).join(' · '))}</div></td>
            <td><select class="stat-sel s-${a.status}" data-status-id="${a.id}" aria-label="Stage">${STATUSES.map(([k, l]) => `<option value="${k}" ${k === a.status ? 'selected' : ''}>${l}</option>`).join('')}</select></td>
            <td class="r mono">${a.ctc_lpa != null ? num(a.ctc_lpa, 2) + ' L' : '<span class="muted">-</span>'}</td>
            <td>${a.next_date ? `<span class="mono">${fmt(a.next_date)}</span> <span class="sub">${rel(a.next_date)}</span><div class="sub">${esc(a.next_step)}</div>` : '<span class="muted">-</span>'}</td>
            <td class="acts"><button class="linkbtn" data-act="edit-app" data-id="${a.id}">Edit</button><button class="linkbtn" data-act="del-app" data-id="${a.id}">Delete</button></td></tr>`;
        }).join('')}</tbody></table></div>`;
    }
    view().innerHTML = html;
  }

  function appForm(a) {
    const isNew = !a;
    formDrawer(isNew ? 'New application' : 'Edit application', APP_FIELDS(), a || { status: 'wishlist' }, async (v) => {
      v.link = v.link || '';
      await api(isNew ? '/api/applications' : `/api/applications/${a.id}`, { method: isNew ? 'POST' : 'PUT', body: v });
      toast(isNew ? 'Application added' : 'Saved'); await refresh();
    });
  }

  /* ---- practice */
  const PROB_FIELDS = () => [
    { n: 'title', l: 'Problem', req: true, full: true },
    { n: 'topic', l: 'Topic', list: TOPICS },
    { n: 'difficulty', l: 'Difficulty', t: 'select', opts: [['easy', 'Easy'], ['medium', 'Medium'], ['hard', 'Hard']] },
    { n: 'platform', l: 'Platform', list: PLATFORMS },
    { n: 'time_min', l: 'Minutes taken', t: 'number', min: 0, int: true },
    { n: 'url', l: 'Link', full: true, ph: 'https://' },
    { n: 'status', l: 'Status', t: 'select', opts: PROB_STATUS },
    { n: 'confidence', l: 'How well do you know it', t: 'select', nullable: true, int: true, opts: [['', 'Not rated'], ...Object.entries(CONF_LABEL).map(([k, l]) => [k, `${k} - ${l}`])] },
    { n: 'notes', l: 'Notes, the trick that made it click', t: 'textarea', full: true },
  ];

  async function pagePractice() {
    S.probs = await api('/api/problems');
    renderPractice();
  }
  const isDue = (p) => p.status !== 'todo' && p.next_review && p.next_review <= todayISO();
  const dots = (c) => (c ? `<span class="dots" title="${CONF_LABEL[c]}">${'●'.repeat(c)}<span class="off">${'●'.repeat(5 - c)}</span></span>` : '<span class="muted">-</span>');

  function renderPractice() {
    const f = S.f; const q = f.pQ.trim().toLowerCase();
    const solved = S.probs.filter((p) => p.status !== 'todo').length; const due = S.probs.filter(isDue);
    const topics = [...new Set(S.probs.map((p) => p.topic).filter(Boolean))].sort();
    const list = S.probs.filter((p) => (!f.pStatus || p.status === f.pStatus) && (!f.pTopic || p.topic === f.pTopic) &&
      (!f.pDiff || p.difficulty === f.pDiff) && (!q || `${p.title} ${p.topic} ${p.platform}`.toLowerCase().includes(q)));
    let html = head('Practice log', '<button class="btn primary" data-act="add-prob">Log a problem</button>');
    html += `<p class="muted" style="margin:0 0 18px"><span class="mono">${solved}</span> solved of <span class="mono">${S.probs.length}</span> logged · <span class="mono ${due.length ? 'due' : ''}">${due.length}</span> due for review</p>`;
    if (due.length) {
      html += `<div class="block"><h2>Due for review</h2>${due.slice(0, 6).map((p) => `<div class="list-row"><div class="main"><b>${esc(p.title)}</b>
        <div class="sub">${esc(p.topic)} · was due ${rel(p.next_review)}</div></div><button class="btn small" data-act="review" data-id="${p.id}">Review</button></div>`).join('')}</div>`;
    }
    html += `<div class="filters">
      <select id="pStatus"><option value="">Any status</option>${PROB_STATUS.map(([k, l]) => `<option value="${k}" ${f.pStatus === k ? 'selected' : ''}>${l}</option>`).join('')}</select>
      <select id="pTopic"><option value="">Any topic</option>${topics.map((t) => `<option ${f.pTopic === t ? 'selected' : ''}>${esc(t)}</option>`).join('')}</select>
      <select id="pDiff"><option value="">Any difficulty</option>${['easy', 'medium', 'hard'].map((d) => `<option value="${d}" ${f.pDiff === d ? 'selected' : ''}>${d[0].toUpperCase() + d.slice(1)}</option>`).join('')}</select>
      <input class="grow" id="pQ" type="search" placeholder="Search problems" value="${esc(f.pQ)}"></div>`;
    if (!list.length) html += `<p class="empty">${S.probs.length ? 'Nothing matches that filter.' : 'No problems logged yet.'}</p>`;
    else {
      html += `<div class="tbl-wrap"><table><thead><tr><th>Problem</th><th>Topic</th><th></th><th>Status</th><th>Recall</th><th>Next review</th><th></th></tr></thead><tbody>
      ${list.map((p) => {
        const url = safeUrl(p.url);
        return `<tr><td><b>${url ? `<a href="${esc(url)}" target="_blank" rel="noopener noreferrer">${esc(p.title)}</a>` : esc(p.title)}</b>${p.platform ? `<div class="sub">${esc(p.platform)}</div>` : ''}</td>
        <td>${esc(p.topic) || '<span class="muted">-</span>'}</td><td><span class="diff ${p.difficulty}">${p.difficulty}</span></td>
        <td>${esc((PROB_STATUS.find((x) => x[0] === p.status) || [0, p.status])[1])}</td><td>${dots(p.confidence)}</td>
        <td class="mono ${isDue(p) ? 'due' : ''}">${p.next_review ? fmt(p.next_review) : '<span class="muted">-</span>'}</td>
        <td class="acts">${p.status !== 'todo' ? `<button class="linkbtn" data-act="review" data-id="${p.id}">Review</button>` : ''}<button class="linkbtn" data-act="edit-prob" data-id="${p.id}">Edit</button><button class="linkbtn" data-act="del-prob" data-id="${p.id}">Delete</button></td></tr>`;
      }).join('')}</tbody></table></div>`;
    }
    view().innerHTML = html;
  }

  function probForm(p) {
    const isNew = !p;
    formDrawer(isNew ? 'Log a problem' : 'Edit problem', PROB_FIELDS(), p || { difficulty: 'medium', status: 'solved', confidence: 3 }, async (v) => {
      await api(isNew ? '/api/problems' : `/api/problems/${p.id}`, { method: isNew ? 'POST' : 'PUT', body: v });
      toast(isNew ? 'Logged' : 'Saved'); await refresh();
    });
  }

  function reviewDrawer(id) {
    const p = S.probs.find((x) => x.id === id) || {};
    const d = openDrawer('Review', `<p style="margin:0 0 4px"><b>${esc(p.title || 'This problem')}</b></p>
      <p class="muted" style="margin:0 0 6px">Without looking at your notes: how well could you solve it again?</p>
      <div class="scale">${[1, 2, 3, 4, 5].map((n) => `<button data-conf="${n}">${n}</button>`).join('')}</div>
      <p class="muted" style="font-size:12.5px;display:flex;justify-content:space-between;margin:0 0 18px"><span>1 · blank</span><span>5 · instantly</span></p>
      <button class="btn" data-act="close-drawer">Cancel</button>`);
    d.querySelectorAll('[data-conf]').forEach((b) => b.addEventListener('click', async () => {
      try {
        const r = await api(`/api/problems/${id}/review`, { method: 'POST', body: { confidence: +b.dataset.conf } });
        closeDrawer(); toast(`Next review ${rel(r.next_review)}`); await refresh();
      } catch (err) { toast(err.message, true); }
    }));
  }

  /* ---- mocks */
  async function pageMocks() {
    S.mocks = await api('/api/mocks');
    let html = head('Mock tests', '<button class="btn primary" data-act="add-mock">Add a score</button>');
    if (!S.mocks.length) return view().innerHTML = html + '<p class="empty">No scores yet. Log an aptitude test, a coding round or a mock interview after you take it.</p>';
    html += `<div class="block"><h2>Trend</h2>${chart(S.mocks.slice().reverse())}</div>`;
    html += `<div class="tbl-wrap"><table><thead><tr><th>Date</th><th>Test</th><th>Type</th><th class="r">Score</th><th class="r">%</th><th></th></tr></thead><tbody>
      ${S.mocks.map((m) => `<tr><td class="mono">${fmt(m.taken_on)}</td><td><b>${esc(m.title)}</b>${m.notes ? `<div class="sub">${esc(m.notes)}</div>` : ''}</td>
      <td>${esc(kindLabel(m.kind))}</td><td class="r mono">${num(m.score)} / ${num(m.max_score)}</td><td class="r mono">${num(m.score / m.max_score * 100)}</td>
      <td class="acts"><button class="linkbtn" data-act="del-mock" data-id="${m.id}">Delete</button></td></tr>`).join('')}</tbody></table></div>`;
    view().innerHTML = html;
  }

  function chart(items) {
    const W = 760, H = 190, L = 34, R = 28, T = 12, B = 26;
    const x = (i) => (items.length === 1 ? (L + W - R) / 2 : L + i * (W - L - R) / (items.length - 1));
    const y = (p) => T + (1 - p / 100) * (H - T - B);
    const pts = items.map((m, i) => [x(i), y(m.score / m.max_score * 100), m]);
    const grid = [0, 25, 50, 75, 100].map((g) => `<line x1="${L}" x2="${W - R}" y1="${y(g)}" y2="${y(g)}" stroke="var(--rule)" stroke-width="1"/><text x="${L - 6}" y="${y(g) + 3}" text-anchor="end">${g}</text>`).join('');
    const line = pts.length > 1 ? `<polyline fill="none" stroke="var(--ink)" stroke-width="1.5" points="${pts.map((p) => p[0] + ',' + p[1]).join(' ')}"/>` : '';
    const dotsSvg = pts.map(([px, py, m], i) => `<circle cx="${px}" cy="${py}" r="3.5" fill="var(--accent)"><title>${esc(m.title)}: ${num(m.score / m.max_score * 100)}%</title></circle>
      ${items.length <= 12 || i % 2 === 0 ? `<text x="${px}" y="${H - 8}" text-anchor="middle">${fmt(m.taken_on)}</text>` : ''}`).join('');
    return `<svg class="chart" viewBox="0 0 ${W} ${H}" role="img" aria-label="Mock test scores over time, percent">${grid}${line}${dotsSvg}</svg>`;
  }

  function mockForm() {
    formDrawer('Add a score', [
      { n: 'title', l: 'Test', req: true, full: true, ph: 'e.g. Quant sectional 3' },
      { n: 'kind', l: 'Type', t: 'select', opts: MOCK_KINDS },
      { n: 'taken_on', l: 'Taken on', t: 'date', req: true },
      { n: 'score', l: 'Score', t: 'number', step: 'any', min: 0, req: true },
      { n: 'max_score', l: 'Out of', t: 'number', step: 'any', min: 0, req: true },
      { n: 'notes', l: 'What went wrong, or right', t: 'textarea', full: true },
    ], { kind: 'aptitude', taken_on: todayISO() }, async (v) => {
      await api('/api/mocks', { method: 'POST', body: v }); toast('Added'); await refresh();
    });
  }

  /* -------------------------------------------------------------- export */
  async function download(name) {
    const res = await fetch(`/api/export/${name}.csv`, { headers: { Authorization: 'Bearer ' + S.token } });
    if (!res.ok) return toast('Export failed', true);
    const url = URL.createObjectURL(await res.blob());
    const a = document.createElement('a'); a.href = url; a.download = `prepledger-${name}.csv`; a.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }

  /* -------------------------------------------------------------- router */
  const PAGES = { dashboard: pageDashboard, applications: pageApplications, practice: pagePractice, mocks: pageMocks };
  const current = () => (location.hash.replace('#/', '') || 'dashboard');

  async function route() {
    if (!S.token) return;
    const page = PAGES[current()] ? current() : 'dashboard';
    document.querySelectorAll('#nav a').forEach((a) => a.classList.toggle('on', a.dataset.page === page));
    try { await PAGES[page](); } catch (err) { if (S.token) view().innerHTML = `<p class="error">${esc(err.message)}</p>`; }
  }
  const refresh = () => route();
  window.addEventListener('hashchange', () => { closeDrawer(); route(); window.scrollTo(0, 0); });

  /* --------------------------------------------------------- interactions */
  document.addEventListener('click', async (e) => {
    const tab = e.target.closest('[data-tab]');
    if (tab) { S.f.appStatus = tab.dataset.tab; return renderApplications(); }
    const el = e.target.closest('[data-act]'); if (!el) return;
    const id = +el.dataset.id;
    try {
      switch (el.dataset.act) {
        case 'logout': return logout();
        case 'close-drawer': return closeDrawer();
        case 'add-app': return appForm();
        case 'edit-app': return appForm(S.apps.find((a) => a.id === id));
        case 'del-app':
          if (confirm('Delete this application?')) { await api(`/api/applications/${id}`, { method: 'DELETE' }); toast('Deleted'); refresh(); } return;
        case 'add-prob': return probForm();
        case 'edit-prob': return probForm(S.probs.find((p) => p.id === id));
        case 'del-prob':
          if (confirm('Delete this problem?')) { await api(`/api/problems/${id}`, { method: 'DELETE' }); toast('Deleted'); refresh(); } return;
        case 'review':
          if (!S.probs.find((p) => p.id === id)) S.probs = await api('/api/problems');
          return reviewDrawer(id);
        case 'add-mock': return mockForm();
        case 'del-mock':
          if (confirm('Delete this score?')) { await api(`/api/mocks/${id}`, { method: 'DELETE' }); toast('Deleted'); refresh(); } return;
        case 'demo': await api('/api/demo', { method: 'POST' }); toast('Sample data added'); return refresh();
        case 'export-menu': {
          const d = openDrawer('Export', `<p class="muted" style="margin:0 0 14px">Download your records as CSV files that open in Excel or Sheets.</p>
            <p><button class="btn" data-act="export" data-name="applications">Applications</button></p>
            <p><button class="btn" data-act="export" data-name="problems">Practice log</button></p>
            <p><button class="btn" data-act="export" data-name="mocks">Mock tests</button></p>
            <hr style="border:0;border-top:1px solid var(--rule);margin:22px 0">
            <p class="muted" style="font-size:13px">Done with the sample data, or want a clean slate?</p>
            <p><button class="btn danger" data-act="wipe">Delete everything in my account</button></p>`);
          return d;
        }
        case 'export': return download(el.dataset.name);
        case 'wipe':
          if (confirm('This deletes all your applications, problems and scores. Continue?')) {
            await api('/api/data', { method: 'DELETE' }); closeDrawer(); toast('Account cleared'); refresh();
          } return;
      }
    } catch (err) { toast(err.message, true); }
  });

  document.addEventListener('change', async (e) => {
    const t = e.target;
    if (t.dataset.statusId) {
      try { await api(`/api/applications/${t.dataset.statusId}/status`, { method: 'PATCH', body: { status: t.value } });
        const a = S.apps.find((x) => x.id === +t.dataset.statusId); if (a) a.status = t.value; renderApplications(); toast('Stage updated'); }
      catch (err) { toast(err.message, true); }
    } else if (t.id === 'pStatus') { S.f.pStatus = t.value; renderPractice(); }
    else if (t.id === 'pTopic') { S.f.pTopic = t.value; renderPractice(); }
    else if (t.id === 'pDiff') { S.f.pDiff = t.value; renderPractice(); }
  });

  document.addEventListener('input', (e) => {
    const t = e.target; const pos = t.selectionStart;
    if (t.id === 'appQ') { S.f.appQ = t.value; renderApplications(); }
    else if (t.id === 'pQ') { S.f.pQ = t.value; renderPractice(); }
    else return;
    const again = document.getElementById(t.id); if (again) { again.focus(); again.setSelectionRange(pos, pos); }
  });

  /* ---------------------------------------------------------------- boot */
  S.token = store.get('pl_token');
  if (S.token) { S.name = store.get('pl_name') || ''; S.email = store.get('pl_email') || ''; enter(); } else showLogin();
})();
