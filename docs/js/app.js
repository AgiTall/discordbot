/**
 * js/app.js — Пчев 𝑊𝑖𝑙𝑑𝑊𝑒𝑠𝑡 𝑅𝑃𝐺 Dashboard
 * Общая логика: навигация, localStorage, dashboard, поиск команд
 */

// =============================================
// КОНФИГУРАЦИЯ
// =============================================
const CONFIG = {
  botVersion: 'v0.5.3',
  inviteUrl:  'https://discord.com/oauth2/authorize?client_id=1513810717495525377&scope=bot%20applications.commands&permissions=8',
  supportUrl: 'https://discord.gg/YOUR_INVITE_CODE',
  storageKey: 'membot_settings',
  selectedGuildKey: 'membot_selected_guild',
};

let authState = {
  user: null,
  guilds: [],
  selectedGuildId: null,
  inviteUrl: CONFIG.inviteUrl,
};

// =============================================
// ВСЕ КОМАНДЫ БОТА
// =============================================
const COMMANDS = [
  // ── Профиль и уровни ──────────────────────
  { name: 'rank',             emoji: '🏅', category: 'level', tag: 'level',  desc: 'Показать ваш текущий уровень и количество опыта.', args: '[участник]' },
  { name: 'leaderboard',      emoji: '🏆', category: 'level', tag: 'level',  desc: 'Топ-10 игроков сервера по уровням.' },
  { name: 'set-rank-role',    emoji: '🎖️', category: 'level', tag: 'admin',  desc: 'Привязать роль Discord к определённому уровню.', args: '<уровень> <роль>' },
  { name: 'remove-rank-role', emoji: '❌', category: 'level', tag: 'admin',  desc: 'Удалить привязку роли к уровню.', args: '<уровень>' },
  { name: 'rank-roles',       emoji: '📋', category: 'level', tag: 'admin',  desc: 'Показать все привязки уровней к ролям.' },
  { name: 'set-levelup-channel', emoji: '📢', category: 'level', tag: 'admin', desc: 'Установить канал для уведомлений о повышении уровня.', args: '<канал>' },
  { name: 'set-xp-rate',      emoji: '⚡', category: 'level', tag: 'admin',  desc: 'Настройка множителей опыта для сообщений, голоса, профессий и ивентов.', args: '<источник> <множитель>' },
  { name: 'restart-rank',     emoji: '🔄', category: 'level', tag: 'admin',  desc: 'Перепроверить и выдать ранговую роль пользователю или всем.', args: '[участник] [all]' },
  { name: 'command-chat',     emoji: '💬', category: 'level', tag: 'admin',  desc: 'Указать каналы, где разрешены команды.', args: '[канал] [remove]' },

  // ── Экономика ─────────────────────────────
  { name: 'gold-rate',    emoji: '📈', category: 'econ', tag: 'econ', desc: 'Показать текущий курс золота к деньгам.' },
  { name: 'buy-gold',     emoji: '🪙', category: 'econ', tag: 'econ', desc: 'Купить золото за деньги по текущему курсу.', args: '<количество>' },
  { name: 'sell-gold',    emoji: '💰', category: 'econ', tag: 'econ', desc: 'Продать золото за деньги по текущему курсу.', args: '<количество>' },
  { name: 'deposit',      emoji: '🏦', category: 'econ', tag: 'econ', desc: 'Положить деньги на вклад (3% в сутки).', args: '<сумма>' },
  { name: 'withdraw',     emoji: '💸', category: 'econ', tag: 'econ', desc: 'Снять деньги с вклада. 0 — снять всё.', args: '[сумма]' },
  { name: 'work',         emoji: '⛏️', category: 'econ', tag: 'econ', desc: 'Поработать и получить деньги (перезарядка 1 час).' },
  { name: 'balance',      emoji: '👤', category: 'econ', tag: 'econ', desc: 'Показать баланс вашего аккаунта.' },

  // ── Профессии ─────────────────────────────
  { name: 'roles',           emoji: '🎭', category: 'role', tag: 'role', desc: 'Просмотреть и купить доступные профессиональные роли за золото.' },
  { name: 'dealer',          emoji: '🛒', category: 'role', tag: 'role', desc: 'Торговец: заполнить повозку товарами (10–35% в час).' },
  { name: 'dealer-delivery', emoji: '📦', category: 'role', tag: 'role', desc: 'Торговец: доставить полную повозку и получить 500–625 $.' },
  { name: 'moonshine',       emoji: '🥃', category: 'role', tag: 'role', desc: 'Самогонщик: открыть меню предприятия (бражка, ингредиенты, улучшения).' },
  { name: 'bounty',          emoji: '🎯', category: 'role', tag: 'role', desc: 'Охотник за головами: открыть меню контрактов (лёгкий/средний/сложный).' },
  { name: 'bounty-leaderboard', emoji: '🏆', category: 'role', tag: 'role', desc: 'Топ охотников за головами по уровню и количеству поимок.' },
  { name: 'naturalist',      emoji: '🌿', category: 'role', tag: 'role', desc: 'Натуралист: образцы, справочник животных и магазин транквилизаторов.' },
  { name: 'excavation',      emoji: '⛏️', category: 'role', tag: 'role', desc: 'Использовать карту сокровищ для раскопок — найдите клад!' },

  // ── Игры ──────────────────────────────────
  { name: 'poker',      emoji: '🃏', category: 'game', tag: 'game', desc: 'Сыграть в покер с ботом. Попробуйте обыграть дилера!', args: '[ставка]' },
  { name: 'blackjack',  emoji: '🎲', category: 'game', tag: 'game', desc: 'Сыграть в блэкджек с дилером. Наберите 21, не перебрав!', args: '[ставка]' },

  // ── Администрирование ─────────────────────
  { name: 'check',       emoji: '🔍', category: 'admin', tag: 'admin', desc: 'Показать баланс участника.', args: '<участник>' },
  { name: 'give-money',  emoji: '💵', category: 'admin', tag: 'admin', desc: 'Выдать деньги участнику или всем.', args: '<участник|all> <сумма>' },
  { name: 'remove-money',emoji: '🔻', category: 'admin', tag: 'admin', desc: 'Отнять деньги у участника или всех.', args: '<участник|all> <сумма>' },
  { name: 'set-money',   emoji: '🔧', category: 'admin', tag: 'admin', desc: 'Установить баланс денег участника.', args: '<участник> <сумма>' },
  { name: 'give-gold',   emoji: '🪙', category: 'admin', tag: 'admin', desc: 'Выдать золото участнику или всем.', args: '<участник|all> <сумма>' },
  { name: 'remove-gold', emoji: '🔻', category: 'admin', tag: 'admin', desc: 'Отнять золото у участника или всех.', args: '<участник|all> <сумма>' },
  { name: 'set-gold',    emoji: '🔧', category: 'admin', tag: 'admin', desc: 'Установить баланс золота участника.', args: '<участник> <сумма>' },
  { name: 'give-map',    emoji: '🗺️', category: 'admin', tag: 'admin', desc: 'Выдать карты сокровищ участнику или всем.', args: '<участник|all> [количество]' },
  { name: 'remove-map',  emoji: '🗺️', category: 'admin', tag: 'admin', desc: 'Забрать карты сокровищ у участника или всех.', args: '<участник|all> [количество]' },
  { name: 'set-deposit', emoji: '🏦', category: 'admin', tag: 'admin', desc: 'Установить вклад участника.', args: '<участник> <сумма>' },
  { name: 'set-rate',    emoji: '📊', category: 'admin', tag: 'admin', desc: 'Установить курс золота вручную.', args: '<курс>' },
  { name: 'reset',       emoji: '⚠️', category: 'admin', tag: 'admin', desc: 'Полный сброс экономики сервера (требует подтверждения).' },
  { name: 'set-channel', emoji: '📡', category: 'admin', tag: 'admin', desc: 'Указать каналы новостей для публикации анонсов.' },
];

// =============================================
// ТАБЛИЦА УРОВНЕЙ (первые 30)
// =============================================
function buildLevelsTable() {
  const rows = [];
  let totalXp = 0;
  for (let lvl = 1; lvl <= 30; lvl++) {
    const xpNeeded = lvl <= 1 ? 0 : Math.round(100 * Math.pow(lvl, 1.5));
    totalXp += xpNeeded;
    const prev = lvl <= 1 ? 0 : Math.round(100 * Math.pow(lvl - 1, 1.5));
    rows.push({ level: lvl, xpNeeded, totalXp });
  }
  return rows;
}

// =============================================
// ХЕЛПЕРЫ
// =============================================

/** Форматировать число с пробелом-разделителем */
function fmtNum(n) {
  return n.toLocaleString('ru-RU');
}

/** Активная страница из URL */
function currentPage() {
  const path = window.location.pathname.split('/').pop() || 'index.html';
  return path.replace('.html', '') || 'index';
}

/** Установить активный класс на nav-ссылки */
function markActiveNav() {
  const page = currentPage();
  document.querySelectorAll('.navbar__links a, .mobile-nav a').forEach(a => {
    const href = a.getAttribute('href') || '';
    const linkPage = href.replace('.html', '').replace('./', '') || 'index';
    a.classList.toggle('active', linkPage === page);
  });
}

// =============================================
// HAMBURGER MENU
// =============================================
function initHamburger() {
  const btn = document.getElementById('hamburgerBtn');
  const mobileNav = document.getElementById('mobileNav');
  if (!btn || !mobileNav) return;

  btn.addEventListener('click', () => {
    const open = btn.classList.toggle('open');
    mobileNav.classList.toggle('open', open);
  });

  // Закрыть при клике вне
  document.addEventListener('click', e => {
    if (!btn.contains(e.target) && !mobileNav.contains(e.target)) {
      btn.classList.remove('open');
      mobileNav.classList.remove('open');
    }
  });
}

// =============================================
// AUTH & GUILD API
// =============================================

const AUTH_ERRORS = {
  oauth_denied: 'Авторизация отменена.',
  oauth_state: 'Ошибка безопасности OAuth. Попробуйте снова.',
  oauth_code: 'Не получен код авторизации.',
  oauth_not_configured: 'OAuth не настроен. Добавьте DISCORD_CLIENT_SECRET в .env.',
  oauth_token: 'Не удалось получить токен Discord.',
  oauth_user: 'Не удалось загрузить профиль Discord.',
};

async function fetchMe() {
  const res = await fetch('/api/me', { credentials: 'same-origin' });
  if (res.status === 401) return null;
  if (!res.ok) throw new Error('API error');
  return res.json();
}

async function loadGuildSettings(guildId) {
  const res = await fetch(`/api/guilds/${guildId}/settings`, { credentials: 'same-origin' });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.error || 'Failed to load settings');
  }
  return res.json();
}

async function saveGuildSettings(guildId, data) {
  const res = await fetch(`/api/guilds/${guildId}/settings`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'same-origin',
    body: JSON.stringify(data),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.error || 'Failed to save settings');
  }
  return res.json();
}

async function logout() {
  await fetch('/auth/logout', { method: 'POST', credentials: 'same-origin' });
  authState = { user: null, guilds: [], selectedGuildId: null, inviteUrl: CONFIG.inviteUrl };
  localStorage.removeItem(CONFIG.selectedGuildKey);
  showAuthGate();
}

function getSelectedGuildId() {
  const params = new URLSearchParams(window.location.search);
  return params.get('guild') || localStorage.getItem(CONFIG.selectedGuildKey);
}

function setSelectedGuildId(guildId) {
  authState.selectedGuildId = guildId;
  if (guildId) {
    localStorage.setItem(CONFIG.selectedGuildKey, guildId);
    const url = new URL(window.location.href);
    url.searchParams.set('guild', guildId);
    window.history.replaceState({}, '', url);
  } else {
    localStorage.removeItem(CONFIG.selectedGuildKey);
    const url = new URL(window.location.href);
    url.searchParams.delete('guild');
    window.history.replaceState({}, '', url);
  }
}

function showAuthGate() {
  document.getElementById('authGate')?.removeAttribute('hidden');
  document.getElementById('guildPicker')?.setAttribute('hidden', '');
  document.getElementById('dashboardMain')?.setAttribute('hidden', '');
}

function showGuildPicker() {
  document.getElementById('authGate')?.setAttribute('hidden', '');
  document.getElementById('guildPicker')?.removeAttribute('hidden');
  document.getElementById('dashboardMain')?.setAttribute('hidden', '');
  renderGuildPicker();
}

function showDashboard() {
  document.getElementById('authGate')?.setAttribute('hidden', '');
  document.getElementById('guildPicker')?.setAttribute('hidden', '');
  document.getElementById('dashboardMain')?.removeAttribute('hidden');
  renderCurrentGuildBadge();
}

function renderUserBadge(container) {
  if (!container || !authState.user) return;
  const avatar = authState.user.avatar_url
    ? `<img src="${authState.user.avatar_url}" alt="" class="user-badge__avatar">`
    : '<span class="user-badge__avatar user-badge__avatar--placeholder"></span>';
  container.innerHTML = `
    ${avatar}
    <span class="user-badge__name">${authState.user.global_name || authState.user.username}</span>
  `;
}

function renderGuildPicker() {
  const grid = document.getElementById('guildGrid');
  const empty = document.getElementById('guildPickerEmpty');
  if (!grid) return;

  renderUserBadge(document.getElementById('userBadge'));

  const available = authState.guilds.filter(g => g.botPresent);
  const unavailable = authState.guilds.filter(g => !g.botPresent);

  grid.innerHTML = '';

  available.forEach(guild => {
    const card = document.createElement('button');
    card.type = 'button';
    card.className = 'guild-card';
    card.setAttribute('role', 'listitem');
    const icon = guild.icon
      ? `<img src="${guild.icon}" alt="" class="guild-card__icon">`
      : '<div class="guild-card__icon guild-card__icon--placeholder"></div>';
    card.innerHTML = `${icon}<span class="guild-card__name">${guild.name}</span>`;
    card.addEventListener('click', () => selectGuild(guild.id));
    grid.appendChild(card);
  });

  unavailable.forEach(guild => {
    const card = document.createElement('a');
    card.className = 'guild-card guild-card--invite';
    card.href = authState.inviteUrl;
    card.target = '_blank';
    card.rel = 'noopener';
    card.setAttribute('role', 'listitem');
    const icon = guild.icon
      ? `<img src="${guild.icon}" alt="" class="guild-card__icon">`
      : '<div class="guild-card__icon guild-card__icon--placeholder"></div>';
    card.innerHTML = `${icon}<span class="guild-card__name">${guild.name}</span><span class="guild-card__badge">Добавить бота</span>`;
    grid.appendChild(card);
  });

  if (empty) {
    empty.hidden = authState.guilds.length > 0;
  }
}

function renderCurrentGuildBadge() {
  const badge = document.getElementById('currentGuildBadge');
  const guild = authState.guilds.find(g => String(g.id) === String(authState.selectedGuildId));
  if (!badge || !guild) return;
  const icon = guild.icon
    ? `<img src="${guild.icon}" alt="" class="guild-card__icon">`
    : '<div class="guild-card__icon guild-card__icon--placeholder"></div>';
  badge.innerHTML = `${icon}<span>${guild.name}</span>`;
}

let dashboardUiReady = false;

function setupDashboardUi(settings) {
  const navLinks   = document.querySelectorAll('.sidebar-nav__item a[data-section]');
  const sections   = document.querySelectorAll('.dash-section');
  const saveBtn    = document.getElementById('saveSettingsBtn');
  const toast      = document.getElementById('toast');

  if (!navLinks.length) return;

  applySettingsToForm(settings);

  function activateSection(target) {
    sections.forEach(s => s.classList.toggle('active', s.id === target));
    navLinks.forEach(a => a.classList.toggle('active', a.dataset.section === target));
  }

  if (!dashboardUiReady) {
    navLinks.forEach(link => {
      link.addEventListener('click', e => {
        e.preventDefault();
        activateSection(link.dataset.section);
      });
    });

    const firstSection = navLinks[0]?.dataset.section;
    if (firstSection) activateSection(firstSection);

    if (saveBtn) {
      saveBtn.addEventListener('click', async () => {
        if (!authState.selectedGuildId) {
          alert('Сначала выберите сервер.');
          return;
        }
        saveBtn.disabled = true;
        const data = collectFormData();
        try {
          if (await saveSettings(data)) {
            showToast(toast);
          }
        } catch (err) {
          alert('Ошибка сохранения: ' + err.message);
        }
        saveBtn.disabled = false;
      });
    }
    dashboardUiReady = true;
  }

  initRankRoleEditor(settings);
}

async function selectGuild(guildId) {
  setSelectedGuildId(guildId);
  showDashboard();
  try {
    const settings = await loadGuildSettings(guildId);
    setupDashboardUi(settings);
  } catch (err) {
    console.error(err);
    alert('Не удалось загрузить настройки сервера: ' + err.message);
    setSelectedGuildId(null);
    showGuildPicker();
  }
}

async function initDashboardAuth() {
  const params = new URLSearchParams(window.location.search);
  const error = params.get('error');
  const authError = document.getElementById('authError');
  if (error && authError) {
    authError.textContent = AUTH_ERRORS[error] || 'Ошибка авторизации.';
    authError.hidden = false;
    const url = new URL(window.location.href);
    url.searchParams.delete('error');
    window.history.replaceState({}, '', url);
  }

  document.getElementById('logoutBtn')?.addEventListener('click', logout);
  document.getElementById('changeGuildBtn')?.addEventListener('click', () => {
    setSelectedGuildId(null);
    showGuildPicker();
  });

  try {
    const me = await fetchMe();
    if (!me?.authenticated) {
      showAuthGate();
      return;
    }
    authState.user = me.user;
    authState.guilds = me.guilds || [];
    authState.inviteUrl = me.inviteUrl || CONFIG.inviteUrl;

    const navbarAuth = document.getElementById('navbarAuth');
    if (navbarAuth) {
      navbarAuth.innerHTML = `
        <span class="navbar__user">${me.user.global_name || me.user.username}</span>
        <button class="btn btn--sm btn--ghost" id="navbarLogoutBtn">Выйти</button>
      `;
      document.getElementById('navbarLogoutBtn')?.addEventListener('click', logout);
    }

    const savedGuild = getSelectedGuildId();
    if (savedGuild && authState.guilds.some(g => String(g.id) === String(savedGuild) && g.botPresent)) {
      await selectGuild(savedGuild);
    } else {
      showGuildPicker();
    }
  } catch (err) {
    console.warn('Auth check failed', err);
    showAuthGate();
  }
}

// =============================================
// ЛОКАЛЬНОЕ ХРАНИЛИЩЕ (legacy fallback)
// =============================================
async function loadSettings() {
  if (authState.selectedGuildId) {
    return loadGuildSettings(authState.selectedGuildId);
  }
  try {
    const raw = localStorage.getItem(CONFIG.storageKey);
    return raw ? JSON.parse(raw) : {};
  } catch {
    return {};
  }
}

async function saveSettings(data) {
  if (!authState.selectedGuildId) {
    throw new Error('Сервер не выбран');
  }
  const result = await saveGuildSettings(authState.selectedGuildId, data);
  return result.status === 'ok';
}

// =============================================
// DASHBOARD
// =============================================
async function initDashboard() {
  if (!document.querySelector('.sidebar-nav__item a[data-section]')) return;

  await initDashboardAuth();
  if (!authState.selectedGuildId) return;

  const settings = await loadSettings();
  setupDashboardUi(settings);
}

/** Собрать все данные форм */
function collectFormData() {
  const data = {};
  document.querySelectorAll('[data-setting]').forEach(el => {
    const key = el.dataset.setting;
    if (el.type === 'checkbox') {
      data[key] = el.checked;
    } else {
      data[key] = el.value;
    }
  });

  // Ранговые роли
  const roles = [];
  document.querySelectorAll('.rank-role-entry').forEach(row => {
    const lvl  = row.querySelector('[data-field="level"]')?.value;
    const role = row.querySelector('[data-field="role"]')?.value;
    if (lvl && role) roles.push({ level: lvl, role });
  });
  data.rankRoles = roles;

  return data;
}

/** Применить сохранённые настройки к форме */
function applySettingsToForm(settings) {
  Object.entries(settings).forEach(([key, val]) => {
    const el = document.querySelector(`[data-setting="${key}"]`);
    if (!el) return;
    if (el.type === 'checkbox') {
      el.checked = Boolean(val);
    } else {
      el.value = val;
    }
  });
}

/** Показать toast-уведомление */
function showToast(toast) {
  if (!toast) return;
  toast.classList.add('show');
  setTimeout(() => toast.classList.remove('show'), 3000);
}

/** Редактор ранговых ролей */
function initRankRoleEditor(settings) {
  const list    = document.getElementById('rankRolesList');
  const addBtn  = document.getElementById('addRankRoleBtn');
  if (!list || !addBtn) return;

  list.innerHTML = '';
  const saved = settings?.rankRoles || [];
  saved.forEach(entry => addRankRoleRow(list, entry.level, entry.role));
  if (!saved.length) addRankRoleRow(list);

  const newAddBtn = addBtn.cloneNode(true);
  addBtn.parentNode.replaceChild(newAddBtn, addBtn);
  newAddBtn.addEventListener('click', () => addRankRoleRow(list));
}

function addRankRoleRow(list, level = '', role = '') {
  const row = document.createElement('div');
  row.className = 'rank-role-entry rank-role-row';
  row.innerHTML = `
    <input class="form-control" type="number" min="1" max="999" placeholder="Уровень" data-field="level" value="${level}" style="max-width:100px">
    <input class="form-control" placeholder="ID или @Название роли" data-field="role" value="${role}">
    <button class="btn btn--ghost btn--sm remove-rank-role-btn" title="Удалить">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="3 6 5 6 21 6"/><path d="M19 6l-1 14H6L5 6"/><path d="M10 11v6M14 11v6"/></svg>
    </button>
  `;
  row.querySelector('.remove-rank-role-btn').addEventListener('click', () => row.remove());
  list.appendChild(row);
}

// =============================================
// КОМАНДЫ — поиск и фильтры
// =============================================
function initCommandsPage() {
  const listEl     = document.getElementById('commandsList');
  const noResults  = document.getElementById('noResults');
  const searchEl   = document.getElementById('cmdSearch');
  const filterBtns = document.querySelectorAll('.filter-tab');

  if (!listEl) return;

  let activeFilter = 'all';
  let query = '';

  function render() {
    const q = query.toLowerCase().trim();
    let visible = 0;

    listEl.innerHTML = '';
    COMMANDS.forEach(cmd => {
      const matchCat = activeFilter === 'all' || cmd.category === activeFilter;
      const matchQ   = !q || cmd.name.includes(q) || cmd.desc.toLowerCase().includes(q);
      if (!matchCat || !matchQ) return;

      visible++;
      const tagClass = `cmd-card__tag--${cmd.tag}`;
      const tagLabel = { level: 'Уровни', admin: 'Админ', econ: 'Экономика', role: 'Профессия', game: 'Игры', util: 'Утилита' }[cmd.tag] || cmd.tag;

      const card = document.createElement('div');
      card.className = 'cmd-card';
      card.setAttribute('role', 'listitem');
      card.innerHTML = `
        <div class="cmd-card__icon">${cmd.emoji}</div>
        <div class="cmd-card__info">
          <div class="cmd-card__name">
            <span class="cmd-card__slug">/${cmd.name}</span>
            <span class="cmd-card__tag ${tagClass}">${tagLabel}</span>
          </div>
          <div class="cmd-card__desc">${cmd.desc}</div>
          ${cmd.args ? `<div class="cmd-card__args">Аргументы: <code>${cmd.args}</code></div>` : ''}
        </div>
      `;
      listEl.appendChild(card);
    });

    if (noResults) {
      noResults.style.display = visible === 0 ? 'block' : 'none';
    }
  }

  // Поиск
  if (searchEl) {
    searchEl.addEventListener('input', () => { query = searchEl.value; render(); });
  }

  // Фильтры
  filterBtns.forEach(btn => {
    btn.addEventListener('click', () => {
      activeFilter = btn.dataset.filter;
      filterBtns.forEach(b => b.classList.toggle('active', b === btn));
      render();
    });
  });

  render();
}

// =============================================
// ТАБЛИЦА УРОВНЕЙ
// =============================================
function initLevelsPage() {
  const tbody = document.getElementById('levelsTableBody');
  if (!tbody) return;

  const rows = buildLevelsTable();
  const maxXp = rows[rows.length - 1].totalXp;

  rows.forEach(({ level, xpNeeded, totalXp }) => {
    const pct = Math.round((totalXp / maxXp) * 100);
    const special = [5, 10, 15, 20, 25, 30].includes(level);
    const tr = document.createElement('tr');
    tr.innerHTML = `
      <td><span class="level-badge ${special ? 'level-badge--special' : ''}">${level}</span></td>
      <td>${level <= 1 ? '—' : fmtNum(xpNeeded) + ' XP'}</td>
      <td>
        <div class="progress-bar-wrap">
          <div class="progress-bar">
            <div class="progress-bar__fill" style="width:${pct}%"></div>
          </div>
          <span class="progress-text">${fmtNum(totalXp)} XP</span>
        </div>
      </td>
      <td>${special ? '🏆 Награда' : '—'}</td>
    `;
    tbody.appendChild(tr);
  });
}

// =============================================
// INVITE / SUPPORT КНОПКИ
// =============================================
function initHeroButtons() {
  document.querySelectorAll('[data-action="invite"]').forEach(btn => {
    btn.addEventListener('click', () => window.open(CONFIG.inviteUrl, '_blank'));
  });
  document.querySelectorAll('[data-action="support"]').forEach(btn => {
    btn.addEventListener('click', () => window.open(CONFIG.supportUrl, '_blank'));
  });
}

// =============================================
// ANIMATE ON SCROLL (простой IntersectionObserver)
// =============================================
function initScrollAnimations() {
  const style = document.createElement('style');
  style.textContent = `
    .anim-fade { opacity: 0; transform: translateY(24px); transition: opacity 0.5s ease, transform 0.5s ease; }
    .anim-fade.visible { opacity: 1; transform: none; }
  `;
  document.head.appendChild(style);

  const els = document.querySelectorAll('.card, .feature-card, .cmd-card, .reward-card, .stat-item');
  const obs = new IntersectionObserver((entries) => {
    entries.forEach(e => {
      if (e.isIntersecting) { e.target.classList.add('visible'); obs.unobserve(e.target); }
    });
  }, { threshold: 0.08 });

  els.forEach((el, i) => {
    el.classList.add('anim-fade');
    el.style.transitionDelay = `${(i % 6) * 60}ms`;
    obs.observe(el);
  });
}

// =============================================
// ИНИЦИАЛИЗАЦИЯ
// =============================================
document.addEventListener('DOMContentLoaded', () => {
  markActiveNav();
  initHamburger();
  initHeroButtons();
  initCommandsPage();
  initDashboard();
  initLevelsPage();

  // Небольшая задержка чтобы контент успел отрендериться
  requestAnimationFrame(() => initScrollAnimations());
});
