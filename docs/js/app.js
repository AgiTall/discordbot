/**
 * js/app.js — Пчев 𝑊𝑖𝑙𝑑𝑊𝑒𝑠𝑡 𝑅𝑃𝐺 Dashboard
 * Общая логика: навигация, localStorage, dashboard, поиск команд
 */

// =============================================
// КОНФИГУРАЦИЯ
// =============================================
const CONFIG = {
  botVersion: 'v0.5.9.3',
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
// XP УТИЛИТЫ
// =============================================
function xpForLevel(level) {
  if (level <= 1) return 0;
  return Math.round(100 * Math.pow(level, 1.5));
}

function totalXpForLevel(level) {
  let total = 0;
  for (let i = 2; i <= level; i++) total += xpForLevel(i);
  return total;
}

function fmtXp(n) {
  return n.toLocaleString('ru-RU');
}

// =============================================
// ТАБЛИЦА УРОВНЕЙ (первые 30)
// =============================================
function buildLevelsTable() {
  const rows = [];
  let totalXp = 0;
  for (let lvl = 1; lvl <= 30; lvl++) {
    const xpNeeded = lvl <= 1 ? 0 : Math.round(100 * Math.pow(lvl, 1.5));
    totalXp += xpNeeded;
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
  hideSkeletonLoader();
}

function showGuildPicker() {
  document.getElementById('authGate')?.setAttribute('hidden', '');
  document.getElementById('guildPicker')?.removeAttribute('hidden');
  document.getElementById('dashboardMain')?.setAttribute('hidden', '');
  hideSkeletonLoader();
  renderGuildPicker();
}

function showDashboard() {
  document.getElementById('authGate')?.setAttribute('hidden', '');
  document.getElementById('guildPicker')?.setAttribute('hidden', '');
  document.getElementById('dashboardMain')?.removeAttribute('hidden');
  renderCurrentGuildBadge();
}

// ── Skeleton loader ──
function showSkeletonLoader() {
  const sk = document.getElementById('skeletonLoader');
  if (sk) sk.classList.add('active');
  // Скрываем секции пока грузим
  document.querySelectorAll('.dash-section').forEach(s => s.style.visibility = 'hidden');
}

function hideSkeletonLoader() {
  const sk = document.getElementById('skeletonLoader');
  if (sk) sk.classList.remove('active');
  document.querySelectorAll('.dash-section').forEach(s => s.style.visibility = '');
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

// =============================================
// ТРЕКИНГ НЕСОХРАНЁННЫХ ИЗМЕНЕНИЙ
// =============================================
let _hasUnsavedChanges = false;

function setUnsaved(val) {
  _hasUnsavedChanges = val;
  const indicator = document.getElementById('unsavedIndicator');
  if (indicator) indicator.classList.toggle('visible', val);
}

function trackChanges() {
  // Слушаем все поля формы
  document.querySelectorAll('[data-setting]').forEach(el => {
    el.addEventListener('change', () => setUnsaved(true));
    el.addEventListener('input', () => setUnsaved(true));
  });
}

// =============================================
// DASHBOARD UI
// =============================================
let dashboardUiReady = false;

function setupDashboardUi(settings) {
  const navLinks   = document.querySelectorAll('.sidebar-nav__item a[data-section]');
  const sections   = document.querySelectorAll('.dash-section');
  const saveBtn    = document.getElementById('saveSettingsBtn');
  const toast      = document.getElementById('toast');

  if (!navLinks.length) return;

  hideSkeletonLoader();
  applySettingsToForm(settings);
  
  // Предзагрузка каналов и ролей сервера для UI
  if (authState.selectedGuildId) {
    guildRolesCache = [];
    guildChannelsCache = [];
    Promise.all([
      fetchGuildRoles(authState.selectedGuildId),
      fetchGuildChannels(authState.selectedGuildId)
    ]).then(([roles, channels]) => {
      populateChannelSelects(channels);
      applySettingsToForm(settings); // Применяем настройки после загрузки каналов
      initRankRoleEditor(settings);
    });
  } else {
    applySettingsToForm(settings);
    initRankRoleEditor(settings);
  }

  function activateSection(target) {
    sections.forEach(s => s.classList.toggle('active', s.id === target));
    navLinks.forEach(a => a.classList.toggle('active', a.dataset.section === target));
    // На мобильных закрываем сайдбар после выбора
    if (window.innerWidth <= 900) {
      document.getElementById('sidebarNav')?.classList.remove('mobile-open');
      document.getElementById('sidebarSaveWrap')?.classList.remove('mobile-open');
      document.getElementById('sidebarToggleBtn')?.classList.remove('open');
    }
  }

  if (!dashboardUiReady) {
    navLinks.forEach(link => {
      link.addEventListener('click', e => {
        e.preventDefault();
        activateSection(link.dataset.section);
      });
    });

    // Ссылки внутри контента (например, "Настройки XP" в секции Экономика)
    document.querySelectorAll('[data-section-link]').forEach(a => {
      a.addEventListener('click', e => {
        e.preventDefault();
        activateSection(a.dataset.sectionLink);
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
        saveBtn.textContent = 'Сохраняем...';
        const data = collectFormData();
        try {
          const result = await saveSettings(data);
          if (result) {
            setUnsaved(false);
            showToast(toast, 'Настройки сохранены! ✓');
            // Обновляем экономику после сохранения
            updateEconomySection(data);
          }
        } catch (err) {
          showToast(toast, 'Ошибка: ' + err.message, true);
        }
        saveBtn.disabled = false;
        saveBtn.innerHTML = `
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M19 21H5a2 2 0 01-2-2V5a2 2 0 012-2h11l5 5v11a2 2 0 01-2 2z"/>
            <polyline points="17 21 17 13 7 13 7 21"/>
            <polyline points="7 3 7 8 15 8"/>
          </svg>
          Сохранить`;
      });
    }

    // Мобильный toggle сайдбара
    initSidebarMobileToggle();

    // XP калькулятор
    initXpCalculator();

    dashboardUiReady = true;
  }

  // Трекинг изменений запускаем после применения настроек
  setTimeout(trackChanges, 100);

  updateEconomySection(settings);
  if (authState.selectedGuildId) {
    fetchAndRenderGangs();
  }
}

function initSidebarMobileToggle() {
  const toggleBtn  = document.getElementById('sidebarToggleBtn');
  const sidebarNav = document.getElementById('sidebarNav');
  const saveWrap   = document.getElementById('sidebarSaveWrap');
  if (!toggleBtn || !sidebarNav) return;

  toggleBtn.addEventListener('click', () => {
    const open = toggleBtn.classList.toggle('open');
    toggleBtn.setAttribute('aria-expanded', open);
    sidebarNav.classList.toggle('mobile-open', open);
    if (saveWrap) saveWrap.classList.toggle('mobile-open', open);
  });
}

function initXpCalculator() {
  const input   = document.getElementById('xpCalcLevel');
  const lvlOut  = document.getElementById('xpCalcLvlOut');
  const xpOut   = document.getElementById('xpCalcXpOut');
  if (!input || !lvlOut || !xpOut) return;

  function update() {
    const lvl = Math.max(1, Math.min(100, parseInt(input.value) || 1));
    const xp  = xpForLevel(lvl);
    lvlOut.textContent = lvl;
    xpOut.textContent  = fmtXp(xp);
  }
  input.addEventListener('input', update);
  update();
}

async function selectGuild(guildId) {
  setSelectedGuildId(guildId);
  showDashboard();
  showSkeletonLoader();
  try {
    const settings = await loadGuildSettings(guildId);
    setupDashboardUi(settings);
  } catch (err) {
    console.error(err);
    hideSkeletonLoader();
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
    setUnsaved(false);
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
// ЗАГРУЗКА / СОХРАНЕНИЕ НАСТРОЕК
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
// DASHBOARD — main init
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
    } else if (el.type === 'select-multiple') {
      const selected = Array.from(el.options).filter(opt => opt.selected).map(opt => opt.value);
      data[key] = selected.join(', ');
    } else {
      data[key] = el.value;
    }
  });

  // Ранговые роли — собираем из карточек
  const roles = [];
  document.querySelectorAll('.rank-role-card').forEach(card => {
    const lvl  = card.dataset.level || card.querySelector('[data-field="level"]')?.value?.trim();
    const role = card.dataset.role;
    const removeRole = card.dataset.removeRole || '';
    if (lvl && role) roles.push({ level: lvl, role, removeRole });
  });
  data.rankRoles = roles;

  return data;
}

/** Применить сохранённые настройки к форме */
function applySettingsToForm(settings) {
  Object.entries(settings).forEach(([key, val]) => {
    if (key === 'rankRoles') return; // обрабатывается отдельно
    const el = document.querySelector(`[data-setting="${key}"]`);
    if (!el) return;
    if (el.type === 'checkbox') {
      el.checked = Boolean(val);
    } else if (el.type === 'select-multiple') {
      const values = (val || '').split(',').map(s => s.trim());
      Array.from(el.options).forEach(opt => {
        opt.selected = values.includes(opt.value);
      });
    } else {
      if (el.tagName === 'SELECT' && el.classList.contains('channel-select') && val) {
        if (!Array.from(el.options).some(opt => opt.value === String(val))) {
          const opt = document.createElement('option');
          opt.value = val;
          opt.text = 'ID: ' + val;
          el.appendChild(opt);
        }
      }
      el.value = val ?? '';
    }
  });
}

/** Toast-уведомление */
function showToast(toast, message = 'Настройки сохранены!', isError = false) {
  if (!toast) return;
  toast.textContent = message;
  toast.style.display = 'block';
  toast.style.borderLeftColor = isError ? 'var(--red)' : '#3a7a3a';
  toast.classList.add('show');
  setTimeout(() => {
    toast.classList.remove('show');
    setTimeout(() => { toast.style.display = 'none'; }, 300);
  }, 3000);
}

// =============================================
// СЕКЦИЯ ЭКОНОМИКИ — отображение данных
// =============================================
function updateEconomySection(settings) {
  if (!settings) return;

  const goldRateEl = document.getElementById('goldRateValue');
  if (goldRateEl && settings.goldRate != null) {
    goldRateEl.textContent = parseFloat(settings.goldRate).toLocaleString('ru-RU', { maximumFractionDigits: 2 });
  }

  const xpMsg   = parseFloat(settings.xpMessages || 15) * parseFloat(settings.xpRateMessages || 1);
  const xpVoice = parseFloat(settings.xpVoice || 10)    * parseFloat(settings.xpRateVoice || 1);

  const map = {
    econ_xpJobs:   `×${parseFloat(settings.xpJobs || 1).toFixed(1)}`,
    econ_xpEvents: `×${parseFloat(settings.xpEvents || 1).toFixed(1)}`,
    econ_xpMsg:    Math.round(xpMsg) + ' XP',
    econ_xpVoice:  Math.round(xpVoice) + ' XP',
    econ_roles:    (settings.rankRoles?.length ?? 0) + ' шт.',
    econJobsRate:  `×${parseFloat(settings.xpJobs || 1).toFixed(1)}`,
    econEventsRate:`×${parseFloat(settings.xpEvents || 1).toFixed(1)}`,
    econMsgRate:   `×${parseFloat(settings.xpRateMessages || 1).toFixed(1)}`,
    econVoiceRate: `×${parseFloat(settings.xpRateVoice || 1).toFixed(1)}`,
  };
  Object.entries(map).forEach(([id, val]) => {
    const el = document.getElementById(id);
    if (el) el.textContent = val;
  });
}

// =============================================
// РЕДАКТОР РАНГОВЫХ РОЛЕЙ
// =============================================

function xpHintHtml(level) {
  const lvl = parseInt(level);
  if (!lvl || lvl < 1) return '<span style="color:var(--text-muted)">Введите уровень</span>';
  const xp = xpForLevel(lvl);
  return `<span style="color:var(--text-muted)">Нужно XP</span><strong>${fmtXp(xp)}</strong>`;
}

function updateRankRolesCount() {
  const countEl = document.getElementById('rankRolesCount');
  if (!countEl) return;
  const count = document.querySelectorAll('.rank-role-card').length;
  countEl.innerHTML = `Настроено: <strong>${count}</strong> ${pluralRoles(count)}`;
}

function pluralRoles(n) {
  if (n % 10 === 1 && n % 100 !== 11) return 'роль';
  if ([2,3,4].includes(n % 10) && ![12,13,14].includes(n % 100)) return 'роли';
  return 'ролей';
}

function validateDuplicateLevels() {
  const cards  = document.querySelectorAll('.rank-role-card');
  const levels = {};
  cards.forEach(card => {
    const lvl = card.querySelector('[data-field="level"]')?.value?.trim();
    if (!lvl) return;
    levels[lvl] = (levels[lvl] || 0) + 1;
  });
  cards.forEach(card => {
    const lvl = card.querySelector('[data-field="level"]')?.value?.trim();
    const errEl = card.querySelector('.rank-role-card__error');
    const isDup = lvl && levels[lvl] > 1;
    card.classList.toggle('has-error', isDup);
    if (errEl) errEl.textContent = isDup ? `Уровень ${lvl} уже добавлен` : '';
  });
}

function getRoleName(roleId) {
  const role = guildRolesCache.find(r => String(r.id) === String(roleId));
  return role ? role.name : roleId;
}

function getRoleColor(roleId) {
  const role = guildRolesCache.find(r => String(r.id) === String(roleId));
  return role ? role.color : '#99aab5';
}

function addRankRoleCard(list, level = '', roleId = '', removeRoleId = '') {
  const empty = list.querySelector('.rank-roles-empty');
  if (empty) empty.remove();

  const card = document.createElement('div');
  card.className = 'rank-role-card';
  card.dataset.level = level;
  card.dataset.role = roleId;
  card.dataset.removeRole = removeRoleId;
  
  const roleName = roleId ? getRoleName(roleId) : 'Выберите роль';
  const roleColor = roleId ? getRoleColor(roleId) : '#fff';
  const removeRoleName = removeRoleId ? getRoleName(removeRoleId) : 'Авто-удаление старых';

  card.innerHTML = `
    <div class="rank-role-card__level">
      <div class="rank-role-card__level-badge form-control" style="cursor:default">${level}</div>
      <div class="rank-role-card__xp-hint">${xpHintHtml(level)}</div>
    </div>
    <div class="rank-role-card__role">
      <label>Выдаётся роль</label>
      <div style="padding: 6px 12px; background: rgba(0,0,0,0.2); border: 1px solid var(--border); border-radius: 4px; display: flex; align-items: center; gap: 8px;">
        <span style="display:inline-block; width:12px; height:12px; border-radius:50%; background-color:${roleColor}"></span>
        <span style="font-family:'Helvetica Neue', sans-serif; font-size:0.85rem">${roleName}</span>
      </div>
      <label style="margin-top: 8px;">Изымается роль</label>
      <div style="padding: 4px 12px; background: rgba(0,0,0,0.1); border: 1px solid var(--border); border-radius: 4px; font-family:'Helvetica Neue', sans-serif; font-size:0.75rem; color:var(--text-muted)">
        ${removeRoleName}
      </div>
      <div class="rank-role-card__error"></div>
    </div>
    <div style="display: flex; flex-direction: column; gap: 6px;">
      <button class="rank-role-card__remove" title="Редактировать" aria-label="Редактировать строку" onclick="editRankRoleCard(this)">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"></path>
          <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"></path>
        </svg>
      </button>
      <button class="rank-role-card__remove" title="Удалить" aria-label="Удалить строку" onclick="removeRankRoleCard(this)">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <polyline points="3 6 5 6 21 6"/>
          <path d="M19 6l-1 14H6L5 6"/>
          <path d="M10 11v6M14 11v6"/>
        </svg>
      </button>
    </div>
  `;

  list.appendChild(card);
  updateRankRolesCount();
  validateDuplicateLevels();
}

window.removeRankRoleCard = function(btn) {
  const card = btn.closest('.rank-role-card');
  card.style.opacity = '0';
  card.style.transform = 'translateX(12px)';
  card.style.transition = 'opacity 0.15s, transform 0.15s';
  setTimeout(() => {
    const list = card.parentNode;
    card.remove();
    updateRankRolesCount();
    validateDuplicateLevels();
    showEmptyStateIfNeeded(list);
    setUnsaved(true);
  }, 150);
};

window.editRankRoleCard = function(btn) {
  const card = btn.closest('.rank-role-card');
  openRankRoleModal(card);
};

function showEmptyStateIfNeeded(list) {
  if (list.querySelectorAll('.rank-role-card').length === 0) {
    list.innerHTML = `
      <div class="rank-roles-empty">
        <svg viewBox="0 0 24 24" fill="none" stroke-width="1.5"><path d="M17 21v-2a4 4 0 00-4-4H5a4 4 0 00-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 00-3-3.87M16 3.13a4 4 0 010 7.75"/></svg>
        Нет настроенных ролей.<br>
        Нажмите «Добавить строку» или выберите шаблон выше.
      </div>
    `;
    updateRankRolesCount();
  }
}

function addTemplateRows(list, levels) {
  // Удаляем пустое состояние
  list.querySelector('.rank-roles-empty')?.remove();
  // Добавляем только те уровни, которых ещё нет
  const existing = new Set();
  list.querySelectorAll('[data-field="level"]').forEach(el => {
    if (el.value) existing.add(el.value.trim());
  });
  levels.forEach(lvl => {
    if (!existing.has(String(lvl))) {
      addRankRoleCard(list, lvl, '');
    }
  });
}

function initRankRoleEditor(settings) {
  const list   = document.getElementById('rankRolesList');
  const addBtn = document.getElementById('addRankRoleBtn');
  if (!list || !addBtn) return;

  list.innerHTML = '';
  const saved = settings?.rankRoles || [];
  if (saved.length) {
    saved.forEach(entry => addRankRoleCard(list, entry.level, entry.role, entry.removeRole));
  } else {
    showEmptyStateIfNeeded(list);
  }

  // Кнопка «Добавить строку»
  const newAddBtn = addBtn.cloneNode(true);
  addBtn.parentNode.replaceChild(newAddBtn, addBtn);
  newAddBtn.addEventListener('click', () => {
    openRankRoleModal();
  });

  // Шаблоны
  function bindTemplate(id, levels) {
    const btn = document.getElementById(id);
    if (!btn) return;
    const newBtn = btn.cloneNode(true);
    btn.parentNode.replaceChild(newBtn, btn);
    newBtn.addEventListener('click', () => {
      addTemplateRows(list, levels);
      setUnsaved(true);
    });
  }

  bindTemplate('tplStandard', [5, 10, 15, 20, 25, 30]);
  bindTemplate('tplEvery5',   [5, 10, 15, 20, 25, 30, 35, 40, 45, 50]);
  bindTemplate('tplEvery10',  [10, 20, 30, 40, 50]);

  const clearBtn = document.getElementById('tplClear');
  if (clearBtn) {
    const newClear = clearBtn.cloneNode(true);
    clearBtn.parentNode.replaceChild(newClear, clearBtn);
    newClear.addEventListener('click', () => {
      if (list.querySelectorAll('.rank-role-card').length === 0) return;
      if (!confirm('Очистить все строки ролей?')) return;
      list.innerHTML = '';
      showEmptyStateIfNeeded(list);
      setUnsaved(true);
    });
  }
}

// =============================================
// MODAL LOGIC FOR RANK ROLES
// =============================================
let guildRolesCache = [];
let guildRolesLoading = false;
let guildChannelsCache = [];
let guildChannelsLoading = false;

let guildChannelsPromise = null;

async function fetchGuildChannels(guildId) {
  if (guildChannelsCache.length) return guildChannelsCache;
  if (guildChannelsPromise) return guildChannelsPromise;
  
  guildChannelsPromise = fetch(`/api/guilds/${guildId}/channels`, { credentials: 'same-origin' })
    .then(res => {
      if (!res.ok) throw new Error('Network response was not ok');
      return res.json();
    })
    .then(data => {
      guildChannelsCache = data;
      return data;
    })
    .catch(e => {
      console.error('Failed to fetch guild channels:', e);
      return [];
    })
    .finally(() => {
      guildChannelsPromise = null;
    });
    
  return guildChannelsPromise;
}

function populateChannelSelects(channels) {
  const optionsHtml = '<option value="">Не выбран (или выберите из списка)</option>' + 
    channels.map(c => `<option value="${c.id}"># ${c.name}</option>`).join('');
    
  document.querySelectorAll('select.channel-select').forEach(select => {
    const currentVal = select.value;
    select.innerHTML = optionsHtml;
    if (currentVal && !channels.some(c => String(c.id) === String(currentVal))) {
        select.innerHTML += `<option value="${currentVal}">ID: ${currentVal}</option>`;
    }
    select.value = currentVal;
  });

  const datalist = document.getElementById('channelDatalist');
  if (datalist) {
    datalist.innerHTML = channels.map(c => `<option value="${c.id}"># ${c.name}</option>`).join('');
  }
}

let guildRolesPromise = null;

async function fetchGuildRoles(guildId) {
  if (guildRolesCache.length) return guildRolesCache;
  if (guildRolesPromise) return guildRolesPromise;
  
  guildRolesPromise = fetch(`/api/guilds/${guildId}/roles`, { credentials: 'same-origin' })
    .then(res => {
      if (!res.ok) throw new Error('Network response was not ok');
      return res.json();
    })
    .then(data => {
      guildRolesCache = data;
      return data;
    })
    .catch(e => {
      console.error('Failed to fetch guild roles:', e);
      return [];
    })
    .finally(() => {
      guildRolesPromise = null;
    });
    
  return guildRolesPromise;
}

let editingRankRoleCard = null;

async function openRankRoleModal(card = null) {
  const modal = document.getElementById('rankRoleModal');
  if (!modal) return;
  
  editingRankRoleCard = card;
  const modalTitle = document.getElementById('rankRoleModalTitle');
  const levelInput = document.getElementById('modalRankLevel');
  const roleSelect = document.getElementById('modalRankRoleSelect');
  const removeRoleSelect = document.getElementById('modalRemoveRoleSelect');
  
  modalTitle.textContent = card ? 'Редактировать роль' : 'Добавить ранговую роль';
  
  if (card) {
    levelInput.value = card.dataset.level || '';
  } else {
    levelInput.value = '';
  }
  
  // Show modal immediately with loading state
  roleSelect.innerHTML = '<option value="">Загрузка ролей...</option>';
  removeRoleSelect.innerHTML = '<option value="">Загрузка ролей...</option>';
  modal.removeAttribute('hidden');
  
  const roles = await fetchGuildRoles(authState.selectedGuildId);
  
  roleSelect.innerHTML = '<option value="">Выберите роль...</option>';
  removeRoleSelect.innerHTML = '<option value="">Не забирать конкретную роль</option>';
  
  roles.forEach(r => {
    roleSelect.innerHTML += `<option value="${r.id}" style="color:${r.color}">${r.name}</option>`;
    removeRoleSelect.innerHTML += `<option value="${r.id}" style="color:${r.color}">${r.name}</option>`;
  });
  
  if (card) {
    roleSelect.value = card.dataset.role || '';
    removeRoleSelect.value = card.dataset.removeRole || '';
  }
}

document.addEventListener('DOMContentLoaded', () => {
  const modal = document.getElementById('rankRoleModal');
  const closeBtn = document.getElementById('closeRankRoleModalBtn');
  const cancelBtn = document.getElementById('cancelRankRoleBtn');
  const saveBtn = document.getElementById('saveRankRoleBtn');
  
  function closeModal() {
    if (modal) modal.setAttribute('hidden', '');
  }
  
  closeBtn?.addEventListener('click', closeModal);
  cancelBtn?.addEventListener('click', closeModal);
  
  saveBtn?.addEventListener('click', () => {
    const level = document.getElementById('modalRankLevel').value.trim();
    const roleId = document.getElementById('modalRankRoleSelect').value;
    const removeRoleId = document.getElementById('modalRemoveRoleSelect').value;
    
    if (!level || !roleId) {
      alert('Укажите требуемый уровень и выберите роль!');
      return;
    }
    
    const list = document.getElementById('rankRolesList');
    
    if (editingRankRoleCard) {
      editingRankRoleCard.remove();
      addRankRoleCard(list, level, roleId, removeRoleId);
    } else {
      addRankRoleCard(list, level, roleId, removeRoleId);
    }
    
    setUnsaved(true);
    closeModal();
  });
});

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

  if (searchEl) {
    searchEl.addEventListener('input', () => { query = searchEl.value; render(); });
  }

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
// ANIMATE ON SCROLL
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
// GANGS DASHBOARD LOGIC
// =============================================
async function fetchAndRenderGangs() {
  const container = document.getElementById('gangsAdminList');
  if (!container || !authState.selectedGuildId) return;

  container.innerHTML = '<div class="rank-roles-empty">Загрузка банд...</div>';

  try {
    const res = await fetch(`/api/guilds/${authState.selectedGuildId}/gangs`, { credentials: 'same-origin' });
    if (!res.ok) throw new Error('Ошибка загрузки');
    const gangs = await res.json();

    if (!gangs || gangs.length === 0) {
      container.innerHTML = '<div class="rank-roles-empty">На сервере пока нет ни одной банды.</div>';
      return;
    }

    container.innerHTML = '';
    gangs.forEach(gang => {
      const card = document.createElement('div');
      card.style.display = 'grid';
      card.style.gridTemplateColumns = '1fr 100px 100px 80px';
      card.style.gap = '12px';
      card.style.alignItems = 'center';
      card.style.background = 'var(--bg-card)';
      card.style.border = '1px solid var(--border)';
      card.style.padding = '12px 16px';
      card.style.borderRadius = 'var(--radius)';
      card.style.marginBottom = '8px';

      card.innerHTML = `
        <div style="font-weight:600;color:var(--text);font-size:0.95rem;">
          ${gang.name}
          <div style="font-size:0.75rem;color:var(--text-muted);font-weight:400;margin-top:2px;">Улучшения: ${Object.keys(gang.camp_upgrades).length}</div>
        </div>
        <div style="font-size:0.9rem;color:var(--text);font-variant-numeric: tabular-nums;">
          <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" style="vertical-align:middle;margin-right:4px;color:var(--text-muted)"><path d="M17 21v-2a4 4 0 00-4-4H5a4 4 0 00-4 4v2"></path><circle cx="9" cy="7" r="4"></circle><path d="M23 21v-2a4 4 0 00-3-3.87"></path><path d="M16 3.13a4 4 0 010 7.75"></path></svg>
          ${gang.member_count}
        </div>
        <div style="font-size:0.9rem;color:var(--gold);font-family:'ChineseRocks','Oswald',sans-serif;letter-spacing:0.05em">
          $${gang.balance.toLocaleString('ru-RU')}
        </div>
        <div style="display:flex;gap:6px;justify-content:flex-end;">
          <button class="btn btn--secondary btn--sm" style="padding:6px;color:var(--red);border-color:rgba(211,47,47,0.3);background:transparent;" onclick="deleteGang(${gang.id}, '${gang.name.replace(/'/g, "\\'")}')" title="Удалить банду">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true" width="16" height="16">
              <polyline points="3 6 5 6 21 6"></polyline>
              <path d="M19 6v14a2 2 0 01-2 2H7a2 2 0 01-2-2V6m3 0V4a2 2 0 012-2h4a2 2 0 012 2v2"></path>
              <line x1="10" y1="11" x2="10" y2="17"></line>
              <line x1="14" y1="11" x2="14" y2="17"></line>
            </svg>
          </button>
        </div>
      `;
      container.appendChild(card);
    });

  } catch (err) {
    container.innerHTML = `<div class="rank-roles-empty" style="color:var(--red)">Ошибка: ${err.message}</div>`;
  }
}

window.fetchAndRenderGangs = fetchAndRenderGangs;

window.deleteGang = async function(gangId, gangName) {
  if (!confirm(`Вы действительно хотите удалить банду "${gangName}"?\nЭто действие нельзя отменить!`)) return;

  try {
    const res = await fetch(`/api/guilds/${authState.selectedGuildId}/gangs/${gangId}`, {
      method: 'DELETE',
      credentials: 'same-origin',
    });
    if (!res.ok) throw new Error('Ошибка при удалении');
    
    // Перезагрузить список
    fetchAndRenderGangs();
    const toast = document.getElementById('toast');
    if (toast) showToast(toast, 'Банда успешно удалена');
  } catch (err) {
    alert('Ошибка: ' + err.message);
  }
};


// =============================================
// COOKIE BANNER
// =============================================
function initCookieBanner() {
  const banner = document.getElementById('cookieBanner');
  const acceptBtn = document.getElementById('cookieAcceptBtn');
  if (!banner || !acceptBtn) return;
  
  if (!localStorage.getItem('cookies_accepted')) {
    setTimeout(() => {
      banner.removeAttribute('hidden');
      // небольшая задержка для анимации, если нужно
      requestAnimationFrame(() => banner.classList.add('visible'));
    }, 500);
  }
  
  acceptBtn.addEventListener('click', () => {
    localStorage.setItem('cookies_accepted', 'true');
    banner.classList.remove('visible');
    setTimeout(() => banner.setAttribute('hidden', ''), 400);
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
  initCookieBanner();

  requestAnimationFrame(() => initScrollAnimations());
});
