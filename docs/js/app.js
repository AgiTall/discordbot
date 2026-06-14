/**
 * js/app.js — Membot Dashboard
 * Общая логика: навигация, localStorage, dashboard, поиск команд
 */

// =============================================
// КОНФИГУРАЦИЯ
// =============================================
const CONFIG = {
  botVersion: 'v0.5.3',
  inviteUrl:  'https://discord.com/oauth2/authorize?client_id=YOUR_CLIENT_ID&permissions=8&scope=bot%20applications.commands',
  supportUrl: 'https://discord.gg/YOUR_INVITE_CODE',
  storageKey: 'membot_settings',
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
// ЛОКАЛЬНОЕ ХРАНИЛИЩЕ
// =============================================
function loadSettings() {
  try {
    const raw = localStorage.getItem(CONFIG.storageKey);
    return raw ? JSON.parse(raw) : {};
  } catch {
    return {};
  }
}

function saveSettings(data) {
  try {
    const existing = loadSettings();
    const merged = { ...existing, ...data };
    localStorage.setItem(CONFIG.storageKey, JSON.stringify(merged));
    return true;
  } catch {
    return false;
  }
}

// =============================================
// DASHBOARD
// =============================================
function initDashboard() {
  const navLinks   = document.querySelectorAll('.sidebar-nav__item a[data-section]');
  const sections   = document.querySelectorAll('.dash-section');
  const saveBtn    = document.getElementById('saveSettingsBtn');
  const toast      = document.getElementById('toast');

  if (!navLinks.length) return;

  // Восстановить сохранённые значения
  const settings = loadSettings();
  applySettingsToForm(settings);

  // Навигация по секциям
  function activateSection(target) {
    sections.forEach(s => s.classList.toggle('active', s.id === target));
    navLinks.forEach(a => a.classList.toggle('active', a.dataset.section === target));
  }

  navLinks.forEach(link => {
    link.addEventListener('click', e => {
      e.preventDefault();
      activateSection(link.dataset.section);
    });
  });

  // По умолчанию — первая секция
  const firstSection = navLinks[0]?.dataset.section;
  if (firstSection) activateSection(firstSection);

  // Кнопка сохранения
  if (saveBtn) {
    saveBtn.addEventListener('click', () => {
      const data = collectFormData();
      if (saveSettings(data)) {
        showToast(toast);
      }
    });
  }

  // Динамические строки ролей за уровни
  initRankRoleEditor();
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
function initRankRoleEditor() {
  const list    = document.getElementById('rankRolesList');
  const addBtn  = document.getElementById('addRankRoleBtn');
  if (!list || !addBtn) return;

  // Восстановить сохранённые роли
  const saved = loadSettings().rankRoles || [];
  saved.forEach(entry => addRankRoleRow(list, entry.level, entry.role));
  if (!saved.length) addRankRoleRow(list);

  addBtn.addEventListener('click', () => addRankRoleRow(list));
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
