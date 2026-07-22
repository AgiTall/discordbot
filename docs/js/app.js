/**
 * js/app.js — Пчев 𝑊𝑖𝑙𝑑𝑊𝑒𝑠𝑡 𝑅𝑃𝐺 Dashboard
 * Общая логика: навигация, localStorage, dashboard, поиск команд
 */

// =============================================
// КОНФИГУРАЦИЯ
// =============================================
const CONFIG = {
  botVersion: '',
  inviteUrl:  '/auth/discord',
  supportUrl: '',
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
  { name: 'work',         emoji: '<img src="https://cdn.discordapp.com/emojis/1515766697913745438.png" style="width:1em;height:1em;vertical-align:-0.15em;">', category: 'econ', tag: 'econ', desc: 'Поработать и получить деньги (перезарядка 1 час).' },
  { name: 'balance',      emoji: '👤', category: 'econ', tag: 'econ', desc: 'Открыть баланс, оружие, текущий курс и обмен золота.' },

  // ── Профессии ─────────────────────────────
  { name: 'roles',           emoji: '🎭', category: 'role', tag: 'role', desc: 'Просмотреть и купить доступные профессиональные роли за золото.' },
  { name: 'dealer',          emoji: '<img src="https://cdn.discordapp.com/emojis/1515766702837731429.png" style="width:1em;height:1em;vertical-align:-0.15em;">', category: 'role', tag: 'role', desc: 'Торговец: заполнить повозку товарами (10–35% в час).' },
  { name: 'dealer-delivery', emoji: '📦', category: 'role', tag: 'role', desc: 'Торговец: доставить полную повозку и получить 500–625 $.' },
  { name: 'moonshine',       emoji: '<img src="https://cdn.discordapp.com/emojis/1515766699402465362.png" style="width:1em;height:1em;vertical-align:-0.15em;">', category: 'role', tag: 'role', desc: 'Самогонщик: открыть меню предприятия (бражка, ингредиенты, улучшения).' },
  { name: 'bounty',          emoji: '<img src="https://cdn.discordapp.com/emojis/1515766696223445053.png" style="width:1em;height:1em;vertical-align:-0.15em;">', category: 'role', tag: 'role', desc: 'Охотник за головами: открыть меню контрактов (лёгкий/средний/сложный).' },
  { name: 'naturalist',      emoji: '<img src="https://cdn.discordapp.com/emojis/1515766700904284370.png" style="width:1em;height:1em;vertical-align:-0.15em;">', category: 'role', tag: 'role', desc: 'Натуралист: образцы, справочник животных и магазин транквилизаторов.' },
  { name: 'excavation',      emoji: '<img src="https://cdn.discordapp.com/emojis/1515766697913745438.png" style="width:1em;height:1em;vertical-align:-0.15em;">', category: 'role', tag: 'role', desc: 'Использовать карту сокровищ для раскопок — найдите клад!' },
  { name: 'mine',            emoji: '<img src="https://cdn.discordapp.com/emojis/1521863885689192518.png" style="width:1em;height:1em;vertical-align:-0.15em;">', category: 'role', tag: 'role', desc: 'Шахтёр: добыча руды, плавка слитков, улучшения и продажа ресурсов.' },
  { name: 'collector',       emoji: '<img src="https://cdn.discordapp.com/emojis/1515766697913745438.png" style="width:1em;height:1em;vertical-align:-0.15em;">', category: 'role', tag: 'role', desc: 'Коллекционер: поиск редкостей по картам, наборы, инструменты и продажа находок.' },
  { name: 'catalog',         emoji: '📖', category: 'role', tag: 'role', desc: 'Открыть каталог Wheeler, Rawson & Co. и приобрести товары.' },
  { name: 'investments',     emoji: '🏢', category: 'econ', tag: 'econ', desc: 'Открыть компании, прогресс снабжения и управление инвестициями.' },

  // ── Игры ──────────────────────────────────
  { name: 'dice',       emoji: '🎲', category: 'game', tag: 'game', desc: 'Сыграть в кости с ботом.', args: '[ставка]' },
  { name: 'poker',      emoji: '🃏', category: 'game', tag: 'game', desc: 'Сыграть в покер с ботом. Попробуйте обыграть дилера!', args: '[ставка]' },
  { name: 'blackjack',  emoji: '🎲', category: 'game', tag: 'game', desc: 'Сыграть в блэкджек с дилером. Наберите 21, не перебрав!', args: '[ставка]' },
  { name: 'rob',        emoji: '🗡️', category: 'game', tag: 'game', desc: 'Попытаться ограбить другого игрока с риском получить штраф.', args: '<участник>' },

  // ── Банды и сейф ──────────────────────────
  { name: 'gang',          emoji: '🔫', category: 'gang', tag: 'gang', desc: 'Открыть панель своей банды.' },
  { name: 'gang-create',   emoji: '⭐', category: 'gang', tag: 'gang', desc: 'Создать собственную банду за 50 золота.' },
  { name: 'gang-join',     emoji: '🤝', category: 'gang', tag: 'gang', desc: 'Принять приглашение и вступить в банду.' },
  { name: 'gang-leave',    emoji: '🚪', category: 'gang', tag: 'gang', desc: 'Покинуть текущую банду.' },
  { name: 'gang-info',     emoji: '📜', category: 'gang', tag: 'gang', desc: 'Посмотреть статистику банды.' },
  { name: 'gang-deposit',  emoji: '📥', category: 'gang', tag: 'gang', desc: 'Внести деньги или золото в общак банды.' },
  { name: 'gang-withdraw', emoji: '📤', category: 'gang', tag: 'gang', desc: 'Снять средства из общака — доступно лидеру.' },
  { name: 'gang-rob',      emoji: '💣', category: 'gang', tag: 'gang', desc: 'Ограбить общак чужой банды с риском штрафа.' },
  { name: 'safe-money',    emoji: '🔐', category: 'econ', tag: 'econ', desc: 'Положить деньги или золото в личный сейф.' },
  { name: 'safe-take-money', emoji: '🔓', category: 'econ', tag: 'econ', desc: 'Забрать деньги или золото из личного сейфа.' },

  // ── Справка ───────────────────────────────
  { name: 'help',       emoji: '❓', category: 'util', tag: 'util', desc: 'Открыть интерактивную справку по возможностям бота.' },
  { name: 'version',    emoji: '🏷️', category: 'util', tag: 'util', desc: 'Показать установленную версию бота.' },
  { name: 'status',     emoji: '🟢', category: 'util', tag: 'util', desc: 'Показать версию, число серверов и задержку.' },

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
  { name: 'set-rate',    emoji: '📊', category: 'admin', tag: 'admin', desc: 'Установить курс золота вручную.', args: '<курс>' },
  { name: 'reset-all',   emoji: '⚠️', category: 'admin', tag: 'admin', desc: 'Полный сброс экономики сервера с подтверждением.' },
  { name: 'news',        emoji: '📰', category: 'admin', tag: 'admin', desc: 'Опубликовать оформленную новость в настроенный канал.' },
  { name: 'treasure-channel', emoji: '🗺️', category: 'admin', tag: 'admin', desc: 'Настроить канал ежедневных карт сокровищ.' },
  { name: 'treasure-event', emoji: '✨', category: 'admin', tag: 'admin', desc: 'Выдать игрокам карты и объявить событие.' },
  { name: 'threads-on',  emoji: '🧵', category: 'admin', tag: 'admin', desc: 'Включить автоматические ветки в канале.' },
  { name: 'threads-off', emoji: '✂️', category: 'admin', tag: 'admin', desc: 'Выключить автоматические ветки в канале.' },
  { name: 'gang-admin',  emoji: '🛡️', category: 'admin', tag: 'admin', desc: 'Открыть панель управления бандами сервера.' },
  { name: 'set-discount-shop', emoji: '🏷️', category: 'admin', tag: 'admin', desc: 'Установить скидку на товар каталога.' },
  { name: 'send', emoji: '✉️', category: 'admin', tag: 'admin', desc: 'Отправить участнику личное сообщение от имени бота.' },
  { name: 'delete-role', emoji: '🗑️', category: 'admin', tag: 'admin', desc: 'Удалить игровую роль у участника.' },
  { name: 'restart-roles', emoji: '🔄', category: 'admin', tag: 'admin', desc: 'Повторно проверить и выдать игровые роли.' },
  { name: 'auto-thread', emoji: '🧵', category: 'admin', tag: 'admin', desc: 'Переключить авто-ветки в текущем канале.' },
  { name: 'set-icon-roles', emoji: '🎭', category: 'admin', tag: 'admin', desc: 'Настроить эмодзи игровых ролей.' },
  { name: 'set-discounts-roles', emoji: '🏷️', category: 'admin', tag: 'admin', desc: 'Установить временную скидку на игровую роль.' },
  { name: 'clear-discounts-roles', emoji: '✖️', category: 'admin', tag: 'admin', desc: 'Убрать скидку с игровой роли.' },
  { name: 'fill-dealer', emoji: '📦', category: 'admin', tag: 'admin', desc: 'Изменить заполнение торговой повозки.' },
  { name: 'give-moonshine-ingredient', emoji: '🍎', category: 'admin', tag: 'admin', desc: 'Выдать ингредиент самогонщика.' },
  { name: 'remove-moonshine-ingredient', emoji: '🧺', category: 'admin', tag: 'admin', desc: 'Забрать ингредиент самогонщика.' },
  { name: 'set-moonshine-upgrade', emoji: '⚗️', category: 'admin', tag: 'admin', desc: 'Установить уровень оборудования самогонщика.' },
  { name: 'set-moonshine-skill', emoji: '⭐', category: 'admin', tag: 'admin', desc: 'Включить или выключить навык самогонщика.' },
  { name: 'finish-moonshine', emoji: '✅', category: 'admin', tag: 'admin', desc: 'Мгновенно завершить текущую партию.' },
  { name: 'reset-moonshine', emoji: '♻️', category: 'admin', tag: 'admin', desc: 'Сбросить состояние предприятия самогонщика.' },
  { name: 'set-emoji', emoji: '😀', category: 'admin', tag: 'admin', desc: 'Настроить эмодзи валют, кнопок и ролей.' },
  { name: 'set-message', emoji: '📝', category: 'admin', tag: 'admin', desc: 'Изменить системные сообщения бота.' },
  { name: 'reset-work', emoji: '⏱️', category: 'admin', tag: 'admin', desc: 'Сбросить перезарядку команды /work.' },
  { name: 'reset-dealer', emoji: '🚚', category: 'admin', tag: 'admin', desc: 'Сбросить перезарядку торговой доставки.' },
  { name: 'admin inspect', emoji: '🩺', category: 'admin', tag: 'admin', desc: 'Показать полное состояние игрока во всех механиках.', args: '<участник>' },
  { name: 'admin cooldown', emoji: '⏱️', category: 'admin', tag: 'admin', desc: 'Сбросить выбранный кулдаун или сразу все активности игрока.', args: '<участник> <активность>' },
  { name: 'admin progress', emoji: '📈', category: 'admin', tag: 'admin', desc: 'Установить общий ранг либо уровень и XP профессии.', args: '<участник> <профессия> <уровень> [XP]' },
  { name: 'admin item', emoji: '🎒', category: 'admin', tag: 'admin', desc: 'Выдать, изъять или установить предметы каталога и профессий.', args: '<участник> <действие> <хранилище> <предмет> <количество>' },
  { name: 'admin role', emoji: '🎭', category: 'admin', tag: 'admin', desc: 'Выдать, забрать или синхронизировать игровую профессию.', args: '<участник> <роль> <действие>' },
  { name: 'admin investment', emoji: '🏦', category: 'admin', tag: 'admin', desc: 'Исправить личный вклад инвестора и общий прогресс компании.', args: '<участник> <действие> <сумма>' },
  { name: 'admin reset', emoji: '⚠️', category: 'admin', tag: 'admin', desc: 'Полностью сбросить выбранную профессию с явным подтверждением.', args: '<участник> <профессия> <подтверждение>' },
  { name: 'admin mine', emoji: '⛏️', category: 'admin', tag: 'admin', desc: 'Изменить попытки, глубину, прочность кирки и припасы шахтёра.', args: '<участник> <параметр> <действие> <значение>' },
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

function escapeHtml(value) {
  return String(value ?? '').replace(/[&<>"']/g, character => ({
    '&': '&amp;',
    '<': '&lt;',
    '>': '&gt;',
    '"': '&quot;',
    "'": '&#039;',
  })[character]);
}

/** Преобразовать Discord-разметку <:name:id> / <a:name:id> в CDN-изображение. */
function discordEmojiHtml(value, fallback = '') {
  const raw = String(value || fallback || '').trim();
  const match = raw.match(/^<(a?):([A-Za-z0-9_]+):(\d+)>$/);
  if (!match) return escapeHtml(raw);
  const [, animated, name, id] = match;
  const extension = animated ? 'gif' : 'png';
  return `<img class="discord-emoji" src="https://cdn.discordapp.com/emojis/${id}.${extension}?size=32&quality=lossless" alt=":${escapeHtml(name)}:" loading="lazy">`;
}

function economyEmojiHtml(emojis, key, fallback = '') {
  return discordEmojiHtml(emojis?.[key], fallback);
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

/** На главной странице авторизованному пользователю показываем быстрый вход в панель. */
async function initHomeAuthCta() {
  const cta = document.getElementById('heroSecondaryCta');
  if (!cta) return;

  try {
    const me = await fetchMe();
    if (me?.authenticated) {
      cta.href = 'dashboard.html';
      cta.textContent = 'ПЕРЕЙТИ К НАСТРОЙКАМ БОТА';
    }
  } catch (error) {
    console.debug('Не удалось проверить авторизацию для главной кнопки:', error);
  }
}

async function loadPublicConfig() {
  try {
    const response = await fetch('/api/config');
    if (!response.ok) return;
    const config = await response.json();
    if (config.inviteUrl) CONFIG.inviteUrl = config.inviteUrl;
    if (config.supportUrl) CONFIG.supportUrl = config.supportUrl;
    if (config.version) {
      CONFIG.botVersion = config.version.startsWith('v') ? config.version : `v${config.version}`;
      document.querySelectorAll('.navbar__badge, .footer__version').forEach(element => {
        element.textContent = CONFIG.botVersion;
      });
    }
  } catch (error) {
    console.warn('Public config unavailable', error);
  }
}

function apiErrorMessage(payload, fallback) {
  const detail = payload?.detail ?? payload?.error;
  if (typeof detail === 'string' && detail.trim()) return detail;
  if (detail && typeof detail === 'object') {
    return detail.error || detail.message || fallback;
  }
  return fallback;
}

async function loadGuildSettings(guildId) {
  const res = await fetch(`/api/guilds/${guildId}/settings`, { credentials: 'same-origin' });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(apiErrorMessage(err, 'Не удалось загрузить настройки'));
  }
  return res.json();
}

async function saveGuildSettings(guildId, data) {
  const res = await fetch(`/api/guilds/${guildId}/settings`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'same-origin',
    body: JSON.stringify({ data }),  // backend expects {data: {...}}
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(apiErrorMessage(err, 'Не удалось сохранить настройки'));
  }
  return res.json();
}

async function loadRankRoles(guildId) {
  const res = await fetch(`/api/guilds/${guildId}/rank-roles`, { credentials: 'same-origin' });
  if (!res.ok) return [];
  const data = await res.json().catch(() => []);
  // Конвертируем формат API -> формат фронта
  return data.map(e => ({ level: String(e.level), role: String(e.role_id), removeRole: e.remove_role_id ? String(e.remove_role_id) : '' }));
}

async function saveRankRoles(guildId, cards) {
  const entries = cards
    .filter(c => c.level && c.role)
    .map(c => ({
      level: parseInt(c.level),
      role_id: String(c.role),
      remove_role_id: c.removeRole || null,
    }));
  const res = await fetch(`/api/guilds/${guildId}/rank-roles`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'same-origin',
    body: JSON.stringify(entries),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(apiErrorMessage(err, 'Не удалось сохранить ранговые роли'));
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
    <span class="user-badge__name">${escapeHtml(authState.user.global_name || authState.user.username)}</span>
  `;
}

function renderGuildPicker() {
  const grid = document.getElementById('guildGrid');
  const empty = document.getElementById('guildPickerEmpty');
  if (!grid) return;

  renderUserBadge(document.getElementById('userBadge'));

  const manageable = authState.guilds.filter(g => g.canManage);
  const available = manageable.filter(g => g.botPresent);
  const unavailable = manageable.filter(g => !g.botPresent);

  grid.innerHTML = '';

  available.forEach(guild => {
    const card = document.createElement('button');
    card.type = 'button';
    card.className = 'guild-card';
    card.setAttribute('role', 'listitem');
    const icon = guild.icon
      ? `<img src="${guild.icon}" alt="" class="guild-card__icon">`
      : '<div class="guild-card__icon guild-card__icon--placeholder"></div>';
    card.innerHTML = `${icon}<span class="guild-card__name">${escapeHtml(guild.name)}</span>`;
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
    card.innerHTML = `${icon}<span class="guild-card__name">${escapeHtml(guild.name)}</span><span class="guild-card__badge">Добавить бота</span>`;
    grid.appendChild(card);
  });

  if (empty) {
    empty.hidden = manageable.length > 0;
  }

  // ── Кнопка «Обновить список» ──────────────────────────
  let refreshBtn = document.getElementById('refreshGuildListBtn');
  const picker = document.getElementById('guildPicker');
  if (!refreshBtn && picker) {
    refreshBtn = document.createElement('button');
    refreshBtn.id = 'refreshGuildListBtn';
    refreshBtn.type = 'button';
    refreshBtn.className = 'btn btn--sm btn--ghost';
    refreshBtn.style.cssText = 'margin: 12px auto 0; display: flex; align-items: center; gap: 6px;';
    refreshBtn.innerHTML = `
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="width:14px;height:14px">
        <polyline points="23 4 23 10 17 10"/>
        <path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"/>
      </svg>
      Обновить список серверов`;
    picker.appendChild(refreshBtn);
  }
  refreshBtn?.addEventListener('click', refreshGuildList);
}

// =============================================
// ОБНОВЛЕНИЕ СПИСКА СЕРВЕРОВ
// =============================================

let _guildRefreshInProgress = false;

async function refreshGuildList() {
  if (_guildRefreshInProgress) return;
  _guildRefreshInProgress = true;

  const btn = document.getElementById('refreshGuildListBtn');
  if (btn) {
    btn.disabled = true;
    btn.textContent = 'Обновляем...';
  }

  try {
    const res = await fetch('/api/me/refresh', {
      method: 'POST',
      credentials: 'same-origin',
    });
    if (res.ok) {
      const data = await res.json();
      if (data.guilds) {
        authState.guilds = data.guilds;
        renderGuildPicker();
      }
    } else {
      // Если refresh недоступен — просто перечитываем /api/me
      const me = await fetchMe();
      if (me?.authenticated) {
        authState.guilds = me.guilds || [];
        renderGuildPicker();
      }
    }
  } catch (e) {
    console.warn('Refresh failed, falling back to /api/me', e);
    try {
      const me = await fetchMe();
      if (me?.authenticated) {
        authState.guilds = me.guilds || [];
        renderGuildPicker();
      }
    } catch (_) {}
  } finally {
    _guildRefreshInProgress = false;
    const b = document.getElementById('refreshGuildListBtn');
    if (b) {
      b.disabled = false;
      b.innerHTML = `
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="width:14px;height:14px">
          <polyline points="23 4 23 10 17 10"/>
          <path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"/>
        </svg>
        Обновить список серверов`;
    }
  }
}

// Автообновление когда пользователь возвращается на вкладку после приглашения бота
document.addEventListener('visibilitychange', () => {
  if (document.visibilityState === 'visible') {
    const picker = document.getElementById('guildPicker');
    if (picker && !picker.hasAttribute('hidden')) {
      refreshGuildList();
    }
  }
});

function renderCurrentGuildBadge() {
  const badge = document.getElementById('currentGuildBadge');
  const guild = authState.guilds.find(g => String(g.id) === String(authState.selectedGuildId));
  if (!badge || !guild) return;
  const icon = guild.icon
    ? `<img src="${guild.icon}" alt="" class="guild-card__icon">`
    : '<div class="guild-card__icon guild-card__icon--placeholder"></div>';
  badge.innerHTML = `${icon}<span>${escapeHtml(guild.name)}</span>`;
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
    if (el.dataset.changeTrackingBound) return;
    el.dataset.changeTrackingBound = 'true';
    el.addEventListener('change', () => setUnsaved(true));
    el.addEventListener('input', () => setUnsaved(true));
  });
}

// =============================================
// DASHBOARD UI
// =============================================

let economyStatsGuildId = null;
let wealthChartInstance = null;
let gangsChartInstance = null;
let leaderboardRows = [];
let leaderboardEmojis = {};
let leaderboardGoldRate = 1;
let leaderboardSort = { key: "wealth", direction: "desc" };

function renderLeaderboard() {
  const tbody = document.getElementById("leaderboardTbody");
  if (!tbody) return;

  if (!leaderboardRows.length) {
    tbody.innerHTML = "<tr><td colspan=\"7\" class=\"table-empty\">В экономике этого сервера пока нет игроков.</td></tr>";
    return;
  }

  const numericValue = (user, key) => {
    if (key === "safe") return Number(user.safe_cash || 0) + Number(user.safe_gold || 0) * leaderboardGoldRate;
    if (key === "gold") return Number(user.total_gold || 0);
    return Number(user[key] || 0);
  };
  const direction = leaderboardSort.direction === "asc" ? 1 : -1;
  const sortedRows = [...leaderboardRows].sort((a, b) => {
    const result = leaderboardSort.key === "name"
      ? String(a.name || "").localeCompare(String(b.name || ""), "ru", { sensitivity: "base" })
      : numericValue(a, leaderboardSort.key) - numericValue(b, leaderboardSort.key);
    return result * direction || String(a.name || "").localeCompare(String(b.name || ""), "ru");
  });

  const cashEmoji = economyEmojiHtml(leaderboardEmojis, 'cash', '$');
  const goldEmoji = economyEmojiHtml(leaderboardEmojis, 'gold', '🪙');
  const wealthEmoji = economyEmojiHtml(leaderboardEmojis, 'wealth', '💰');
  const safeEmoji = economyEmojiHtml(leaderboardEmojis, 'safe', '🔒');
  tbody.innerHTML = sortedRows.map((u, i) => `
    <tr style="border-bottom:1px solid var(--border)">
      <td style="padding:10px;color:var(--text-muted);">${i + 1}</td>
      <td style="padding:10px;font-weight:bold;color:var(--gold);">${escapeHtml(u.name)}</td>
      <td style="padding:10px;">${Number(u.level || 0).toLocaleString("ru-RU")}</td>
      <td style="padding:10px;">${Number(u.cash || 0).toLocaleString("ru-RU")} ${cashEmoji}</td>
      <td style="padding:10px;">${safeEmoji} ${Number(u.safe_cash || 0).toLocaleString("ru-RU")} ${cashEmoji} · ${Number(u.safe_gold || 0).toLocaleString("ru-RU")} ${goldEmoji}</td>
      <td style="padding:10px;">${Number(u.total_gold || 0).toLocaleString("ru-RU")} ${goldEmoji}</td>
      <td style="padding:10px;font-weight:bold;">${Math.round(Number(u.wealth || 0)).toLocaleString("ru-RU")} ${wealthEmoji}</td>
    </tr>
  `).join("");
}

function initLeaderboardSorting() {
  document.querySelectorAll("[data-leaderboard-sort]").forEach(button => {
    button.addEventListener("click", () => {
      const key = button.dataset.leaderboardSort;
      leaderboardSort = {
        key,
        direction: leaderboardSort.key === key && leaderboardSort.direction === "desc" ? "asc" : "desc"
      };
      document.querySelectorAll("[data-leaderboard-sort]").forEach(sortButton => {
        const active = sortButton.dataset.leaderboardSort === key;
        const th = sortButton.closest("th");
        sortButton.classList.toggle("is-active", active);
        sortButton.querySelector(".table-sort__arrow").textContent = active
          ? (leaderboardSort.direction === "asc" ? "▲" : "▼")
          : "";
        th?.setAttribute("aria-sort", active
          ? (leaderboardSort.direction === "asc" ? "ascending" : "descending")
          : "none");
      });
      renderLeaderboard();
    });
  });
}

async function loadEconomyStats(guildId) {
  const tbody = document.getElementById("leaderboardTbody");
  if (!tbody) return;
  tbody.innerHTML = "<tr><td colspan=\"7\" class=\"table-empty\">Загрузка актуальных данных...</td></tr>";
  
  try {
    const res = await fetch(`/api/guilds/${guildId}/stats`);
    if (!res.ok) throw new Error("Failed to fetch stats");
    const data = await res.json();
    const emojis = data.emojis || {};
    const cashEmoji = economyEmojiHtml(emojis, 'cash', '$');
    const goldEmoji = economyEmojiHtml(emojis, 'gold', '🪙');
    const wealthEmoji = economyEmojiHtml(emojis, 'wealth', '💰');
    const statsEmoji = economyEmojiHtml(emojis, 'stats', '🏆');
    const safeEmoji = economyEmojiHtml(emojis, 'safe', '🔒');
    const statsHeadingEmoji = document.getElementById('leaderboardStatsEmoji');
    if (statsHeadingEmoji) statsHeadingEmoji.innerHTML = statsEmoji;
    
    // Populate Leaderboard
    leaderboardRows = Array.isArray(data.leaderboard) ? data.leaderboard : [];
    leaderboardEmojis = emojis;
    leaderboardGoldRate = Number(data.globals?.gold_rate || 1);
    renderLeaderboard();

    renderCompanyStats(data.company, cashEmoji);

    // Chart.js Default Config for Dark Theme
    if (typeof Chart !== "undefined") {
      Chart.defaults.color = "#99aab5";
      Chart.defaults.font.family = "Inter, sans-serif";
    }

    // Wealth Pie Chart
    const wCtx = document.getElementById("wealthChart");
    if (wCtx && data.leaderboard && typeof Chart !== "undefined") {
      const topNames = data.leaderboard.slice(0, 5).map(u => u.name);
      const topWealth = data.leaderboard.slice(0, 5).map(u => u.wealth);
      
      const sumTop5 = topWealth.reduce((a, b) => a + b, 0);
      const totalServerWealth = (data.globals.players_total_cash || 0) + ((data.globals.players_total_gold || 0) * (data.globals.gold_rate || 1));
      const othersWealth = Math.max(0, totalServerWealth - sumTop5);
      
      if (topNames.length > 0) {
        topNames.push("Остальные");
        topWealth.push(othersWealth);
      }

      if (wealthChartInstance) wealthChartInstance.destroy();
      wealthChartInstance = new Chart(wCtx, {
        type: "doughnut",
        data: {
          labels: topNames,
          datasets: [{
            data: topWealth,
            backgroundColor: ["#c19b38", "#d93838", "#4287f5", "#38c172", "#9b59b6", "#2f3136"],
            borderColor: "#202225",
            borderWidth: 2
          }]
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: {
            legend: { position: "right" },
            title: { display: true, text: "Распределение богатства" }
          }
        }
      });
    }

    // Gangs Bar Chart
    const gCtx = document.getElementById("gangsChart");
    if (gCtx && data.gangs && typeof Chart !== "undefined") {
      const gNames = data.gangs.map(g => g.name);
      const gWealth = data.gangs.map(g => g.wealth);
      
      if (gangsChartInstance) gangsChartInstance.destroy();
      gangsChartInstance = new Chart(gCtx, {
        type: "bar",
        data: {
          labels: gNames,
          datasets: [{
            label: "Состояние общака",
            data: gWealth,
            backgroundColor: "#d93838",
            borderColor: "#f04747",
            borderWidth: 1,
            borderRadius: 4
          }]
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          scales: {
            y: { beginAtZero: true, grid: { color: "#2f3136" } },
            x: { grid: { display: false } }
          },
          plugins: {
            legend: { display: false },
            title: { display: true, text: "Самые богатые банды" }
          }
        }
      });
    }

    economyStatsGuildId = guildId;
  } catch (err) {
    console.error("Failed to load economy stats:", err);
    tbody.innerHTML = "<tr><td colspan=\"7\" class=\"table-empty table-empty--error\">Не удалось загрузить экономику сервера.</td></tr>";
  }
}

function renderCompanyStats(company, cashEmoji = '$') {
  if (!company) return;
  const roman = ["0", "I", "II", "III", "IV"];
  const level = Number(company.level || 1);
  const maxLevel = Number(company.max_level || 4);
  const target = company.next_threshold;
  const percent = target ? Math.min(100, (Number(company.invested || 0) / Number(target)) * 100) : 100;

  const levelNode = document.getElementById("companyLevel");
  const investedNode = document.getElementById("companyInvested");
  const viewerInvestedNode = document.getElementById("companyViewerInvested");
  const viewerDiscountNode = document.getElementById("companyViewerDiscount");
  const progressNode = document.getElementById("companyProgress");
  const progressFill = document.getElementById("companyProgressFill");
  const progressLabel = document.getElementById("companyProgressLabel");
  const remainingNode = document.getElementById("companyRemaining");

  if (levelNode) levelNode.textContent = `${roman[level] || level} / ${roman[maxLevel] || maxLevel}`;
  if (investedNode) investedNode.innerHTML = `${Number(company.invested || 0).toLocaleString("ru-RU")} ${cashEmoji}`;
  if (viewerInvestedNode) viewerInvestedNode.innerHTML = `${Number(company.viewer_invested || 0).toLocaleString("ru-RU")} ${cashEmoji}`;
  if (viewerDiscountNode) viewerDiscountNode.textContent = `${Number(company.viewer_discount || 0)}%`;
  if (progressNode) progressNode.setAttribute("aria-valuenow", String(Math.round(percent)));
  if (progressFill) progressFill.style.width = `${percent}%`;
  if (progressLabel) {
    progressLabel.innerHTML = target
      ? `${Number(company.invested || 0).toLocaleString("ru-RU")} / ${Number(target).toLocaleString("ru-RU")} ${cashEmoji}`
      : "Максимальный уровень снабжения";
  }
  if (remainingNode) {
    remainingNode.innerHTML = target
      ? `Осталось ${Number(company.remaining || 0).toLocaleString("ru-RU")} ${cashEmoji}`
      : "Все товары открыты";
  }

  document.querySelectorAll("[data-company-tier]").forEach(node => {
    node.classList.toggle("is-unlocked", Number(node.dataset.companyTier) <= level);
  });

  const investorsBody = document.getElementById("companyInvestorsTbody");
  if (!investorsBody) return;
  if (!company.investors || company.investors.length === 0) {
    investorsBody.innerHTML = '<tr><td colspan="3" class="table-empty">Инвесторов пока нет.</td></tr>';
    return;
  }
  investorsBody.innerHTML = company.investors.map((investor, index) => `
    <tr>
      <td>${index + 1}</td>
      <td><strong>${escapeHtml(investor.name)}</strong></td>
      <td class="money-cell">${Number(investor.amount).toLocaleString("ru-RU")} ${cashEmoji}</td>
    </tr>
  `).join("");
}

let dashboardUiReady = false;

function setupDashboardUi(settings) {
  const navLinks   = document.querySelectorAll('.sidebar-nav__item a[data-section]');
  const sections   = document.querySelectorAll('.dash-section');
  const saveBtn    = document.getElementById('saveSettingsBtn');
  const toast      = document.getElementById('toast');

  if (!navLinks.length) return;

  hideSkeletonLoader();
  applySettingsToForm(settings);
  // Инициализируем редактор даже при ответе старого API без autoReactions.
  initAutoReactionEditor(settings?.autoReactions || []);
  renderSetupHealth(settings);
  
  // Предзагрузка каналов и ролей сервера для UI
  if (authState.selectedGuildId) {
    guildRolesCache = [];
    guildChannelsCache = [];
    guildEmojisCache = [];
    guildRolesPromise = null;
    guildChannelsPromise = null;
    guildEmojisPromise = null;
    Promise.all([
      fetchGuildRoles(authState.selectedGuildId),
      fetchGuildChannels(authState.selectedGuildId),
      fetchGuildEmojis(authState.selectedGuildId)
    ]).then(([roles, channels, emojis]) => {
      populateChannelSelects(channels);
      populateRoleSelects(roles);
      populateEmojiSelects(emojis);
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
    if (target === "economy") {
      loadEconomyStats(authState.selectedGuildId);
    }
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
            renderSetupHealth(data);
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
  economyStatsGuildId = null;
  setSelectedGuildId(guildId);
  showDashboard();
  showSkeletonLoader();
  try {
    const [settings, rankRoles] = await Promise.all([
      loadGuildSettings(guildId),
      loadRankRoles(guildId),
    ]);
    // Подмешиваем ранговые роли из правильной таблицы (rank_roles в PostgreSQL)
    settings.rankRoles = rankRoles;
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
    if (savedGuild && authState.guilds.some(g => String(g.id) === String(savedGuild) && g.botPresent && g.canManage)) {
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
  const rankRolesData = data.rankRoles || [];
  const settingsData = { ...data };
  delete settingsData.rankRoles;

  // Успех показывается только после сохранения обеих частей конфигурации.
  const [result] = await Promise.all([
    saveGuildSettings(authState.selectedGuildId, settingsData),
    saveRankRoles(authState.selectedGuildId, rankRolesData),
  ]);
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
  data.autoReactions = Array.from(document.querySelectorAll('.auto-reaction-card')).map(card => ({
    trigger: card.querySelector('[data-auto-reaction-trigger]')?.value?.trim() || '',
    emoji: card.querySelector('[data-auto-reaction-emoji]')?.value?.trim() || '',
  })).filter(rule => rule.trigger && rule.emoji);

  return data;
}

/** Применить сохранённые настройки к форме */
function applySettingsToForm(settings) {
  Object.entries(settings).forEach(([key, val]) => {
    if (key === 'rankRoles') return; // обрабатывается отдельно
    if (key === 'autoReactions') return; // отдельный динамический редактор
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
      } else if (el.tagName === 'SELECT' && el.classList.contains('emoji-select') && val) {
        if (!Array.from(el.options).some(opt => opt.value === String(val))) {
          const opt = document.createElement('option');
          opt.value = val;
          opt.text = val;
          el.appendChild(opt);
        }
      }
      el.value = val ?? '';
      if (el.classList.contains('emoji-select')) {
        updateEmojiPreview(el);
      }
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
        <span style="font-family:'Helvetica Neue', sans-serif; font-size:0.85rem">${escapeHtml(roleName)}</span>
      </div>
      <label style="margin-top: 8px;">Изымается роль</label>
      <div style="padding: 4px 12px; background: rgba(0,0,0,0.1); border: 1px solid var(--border); border-radius: 4px; font-family:'Helvetica Neue', sans-serif; font-size:0.75rem; color:var(--text-muted)">
        ${escapeHtml(removeRoleName)}
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
  const channelOptions = channels
    .filter(c => [0, 5].includes(Number(c.type)))
    .map(c => `<option value="${c.id}"># ${escapeHtml(c.name)}</option>`)
    .join('');

  document.querySelectorAll('select.channel-select').forEach(select => {
    const currentValues = select.multiple
      ? Array.from(select.selectedOptions).map(option => option.value)
      : [select.value];
    select.innerHTML = select.multiple
      ? channelOptions
      : `<option value="">Не выбран</option>${channelOptions}`;
    currentValues.filter(Boolean).forEach(currentVal => {
      if (!channels.some(c => String(c.id) === String(currentVal))) {
        select.innerHTML += `<option value="${currentVal}">Недоступный канал: ${currentVal}</option>`;
      }
    });
    if (select.multiple) {
      Array.from(select.options).forEach(option => {
        option.selected = currentValues.includes(option.value);
      });
    } else {
      select.value = currentValues[0] || '';
    }
  });

  const datalist = document.getElementById('channelDatalist');
  if (datalist) {
    datalist.innerHTML = channels.map(c => `<option value="${c.id}"># ${escapeHtml(c.name)}</option>`).join('');
  }
}

function initAutoReactionEditor(rules = []) {
  const list = document.getElementById('autoReactionsList');
  const addBtn = document.getElementById('addAutoReactionBtn');
  if (!list || !addBtn) return;

  const normalized = Array.isArray(rules)
    ? rules.slice(0, 20).filter(rule => rule && typeof rule === 'object' && rule.emoji)
    : [];

  if (!normalized.length) {
    list.innerHTML = `
      <div class="auto-reactions-empty">
        <strong>Правил пока нет</strong>
        <span>Добавьте слово и выберите реакцию, которую поставит бот.</span>
      </div>`;
  } else {
    list.innerHTML = normalized.map((rule, index) => `
      <div class="auto-reaction-card" data-auto-reaction-index="${index}">
        <div class="form-group auto-reaction-card__trigger">
          <label for="autoReactionTrigger${index}">Слово или фраза</label>
          <input class="form-control" id="autoReactionTrigger${index}" data-auto-reaction-trigger
            maxlength="100" value="${escapeHtml(rule.trigger)}" placeholder="Например: победа">
        </div>
        <div class="form-group auto-reaction-card__emoji">
          <label for="autoReactionEmoji${index}">Реакция</label>
          <div class="emoji-field">
            <select class="form-control emoji-select" id="autoReactionEmoji${index}" data-auto-reaction-emoji>
              <option value="">Выберите эмодзи...</option>
              <option value="${escapeHtml(rule.emoji)}" selected>${escapeHtml(rule.emoji)}</option>
            </select>
            <span class="emoji-preview" id="preview_autoReactionEmoji${index}"></span>
          </div>
        </div>
        <button type="button" class="auto-reaction-card__remove" data-remove-auto-reaction="${index}"
          aria-label="Удалить автореакцию" title="Удалить">×</button>
      </div>`).join('');
  }

  populateEmojiSelects(guildEmojisCache);
  list.querySelectorAll('input, select').forEach(element => {
    element.addEventListener('input', () => setUnsaved(true));
    element.addEventListener('change', () => setUnsaved(true));
  });
  list.querySelectorAll('[data-remove-auto-reaction]').forEach(button => {
    button.addEventListener('click', () => {
      const current = collectAutoReactionRules();
      current.splice(Number(button.dataset.removeAutoReaction), 1);
      initAutoReactionEditor(current);
      setUnsaved(true);
    });
  });

  if (!addBtn.dataset.bound) {
    addBtn.dataset.bound = 'true';
    addBtn.addEventListener('click', () => {
      const current = collectAutoReactionRules();
      if (current.length >= 20) {
        showToast(document.getElementById('toast'), 'Можно добавить не больше 20 правил.', true);
        return;
      }
      current.push({ trigger: '', emoji: '👍' });
      initAutoReactionEditor(current);
      setUnsaved(true);
    });
  }
}

function collectAutoReactionRules() {
  return Array.from(document.querySelectorAll('.auto-reaction-card')).map(card => ({
    trigger: card.querySelector('[data-auto-reaction-trigger]')?.value?.trim() || '',
    emoji: card.querySelector('[data-auto-reaction-emoji]')?.value?.trim() || '',
  }));
}

function renderSetupHealth(settings) {
  const checklist = document.getElementById('setupChecklist');
  if (!checklist || !settings) return;

  const hasIds = value => Array.isArray(value)
    ? value.length > 0
    : String(value || '').split(',').some(item => item.trim());
  const logEventsEnabled = ['logJoin', 'logLeave', 'logBan', 'logDelete', 'logEdit', 'logVoice', 'logCommands']
    .some(key => Boolean(settings[key]));
  const checks = [
    {
      ok: Boolean(settings.allowAllChannels) || hasIds(settings.commandChannelIds),
      title: 'Команды доступны игрокам',
      detail: settings.allowAllChannels ? 'Разрешены во всех каналах' : 'Выбраны командные каналы',
      missing: 'Выберите каналы или разрешите команды везде',
      section: 'channels',
    },
    {
      ok: Boolean(settings.treasureChannelId),
      title: 'Ежедневные карты сокровищ',
      detail: 'Канал раздачи выбран',
      missing: 'Канал раздачи ещё не выбран',
      section: 'channels',
    },
    {
      ok: Boolean(settings.levelupChannelId) || Boolean(settings.levelupDM),
      title: 'Уведомления об уровнях',
      detail: settings.levelupDM ? 'Отправляются в личные сообщения' : 'Канал уведомлений выбран',
      missing: 'Выберите канал или включите личные сообщения',
      section: 'levels',
    },
    {
      ok: Array.isArray(settings.rankRoles) && settings.rankRoles.length > 0,
      title: 'Награды за уровни',
      detail: `Настроено ролей: ${settings.rankRoles?.length || 0}`,
      missing: 'Добавьте хотя бы одну роль за уровень',
      section: 'rankroles',
    },
    {
      ok: !settings.welcomeEnabled || Boolean(settings.welcomeChannelId),
      title: 'Приветствие новичков',
      detail: settings.welcomeEnabled ? 'Приветствие настроено' : 'Функция пока выключена',
      missing: 'Приветствие включено, но канал не выбран',
      section: 'welcome',
    },
    {
      ok: !logEventsEnabled || Boolean(settings.logsChannelId),
      title: 'Журнал событий',
      detail: logEventsEnabled ? 'Канал логов выбран' : 'События логов выключены',
      missing: 'Логи включены, но канал не выбран',
      section: 'logs',
    },
  ];

  const completed = checks.filter(check => check.ok).length;
  const percent = Math.round((completed / checks.length) * 100);
  document.getElementById('setupPercent').textContent = `${percent}%`;
  document.getElementById('setupProgressBar').style.width = `${percent}%`;
  document.getElementById('setupSummaryText').textContent = percent === 100
    ? 'Основные функции готовы к запуску'
    : `Готово ${completed} из ${checks.length} основных пунктов`;

  checklist.innerHTML = checks.map(check => `
    <div class="setup-check ${check.ok ? '' : 'setup-check--missing'}">
      <span class="setup-check__state" aria-hidden="true">${check.ok ? '✓' : '!'}</span>
      <span>
        <strong>${check.title}</strong>
        <small>${check.ok ? check.detail : check.missing}</small>
      </span>
      <a href="#" class="setup-check__link" data-section-link="${check.section}">${check.ok ? 'Проверить' : 'Настроить'} →</a>
    </div>
  `).join('');
  checklist.querySelectorAll('[data-section-link]').forEach(link => {
    link.addEventListener('click', event => {
      event.preventDefault();
      document.querySelector(`[data-section="${link.dataset.sectionLink}"]`)?.click();
    });
  });
}

function populateRoleSelects(roles) {
  document.querySelectorAll('select.role-select').forEach(select => {
    const currentVal = select.value;
    select.innerHTML = '<option value="">Не выбрана</option>' + roles
      .map(role => `<option value="${role.id}">${escapeHtml(role.name)}</option>`)
      .join('');
    if (currentVal && !roles.some(role => String(role.id) === String(currentVal))) {
      select.innerHTML += `<option value="${currentVal}">Недоступная роль: ${currentVal}</option>`;
    }
    select.value = currentVal;
  });
}

let guildEmojisCache = [];
let guildEmojisPromise = null;

function fetchGuildEmojis(guildId) {
  if (guildEmojisCache.length) return guildEmojisCache;
  if (guildEmojisPromise) return guildEmojisPromise;
  
  guildEmojisPromise = fetch(`/api/guilds/${guildId}/emojis`, { credentials: 'same-origin' })
    .then(r => {
      if (!r.ok) throw new Error('Network error');
      return r.json();
    })
    .then(data => {
      guildEmojisCache = data;
      return data;
    })
    .catch(() => [])
    .finally(() => guildEmojisPromise = null);
    
  return guildEmojisPromise;
}

function updateEmojiPreview(selectEl) {
  const previewEl = document.getElementById('preview_' + selectEl.id);
  if (!previewEl) return;
  const val = selectEl.value;
  // If it's a custom emoji like <:name:id> or <a:name:id>
  const match = val.match(/<(a?):([^:]+):(\d+)>/);
  if (match) {
    const animated = match[1] === 'a';
    const id = match[3];
    const ext = animated ? 'gif' : 'png';
    previewEl.innerHTML = `<img src="https://cdn.discordapp.com/emojis/${id}.${ext}" alt="${val}" style="width:24px;height:24px;vertical-align:middle;">`;
  } else {
    // Unicode emoji
    previewEl.innerHTML = val;
  }
}

function populateEmojiSelects(emojis) {
  const customOptions = emojis.map(e => `<option value="${escapeHtml(e.format)}">${escapeHtml(e.name)}</option>`).join('');
  document.querySelectorAll('select.emoji-select').forEach(select => {
    const defaultOpt = select.options[0].outerHTML;
    const currentVal = select.value;
    
    let html = defaultOpt;
    if (emojis.length > 0) {
      html += `<optgroup label="Эмодзи сервера">${customOptions}</optgroup>`;
    }
    html += `<optgroup label="Другое"><option value="__custom__">➕ Ввести кастомный эмодзи...</option></optgroup>`;
    select.innerHTML = html;
    
    select.value = currentVal;
    if (!select.value && currentVal && currentVal !== '__custom__') {
      select.innerHTML += `<option value="${currentVal}">${currentVal}</option>`;
      select.value = currentVal;
    }
    
    // Initialize prevVal
    if (!select.dataset.prevVal) select.dataset.prevVal = select.value;
    
    updateEmojiPreview(select);
    
    if (!select.dataset.customListenerAdded) {
      select.dataset.customListenerAdded = 'true';
      select.addEventListener('change', (e) => {
        const el = e.target;
        if (el.value === '__custom__') {
          const prevVal = el.dataset.prevVal || el.options[0].value;
          const val = prompt('Вставьте код кастомного эмодзи или стикера бота (например: <:emoji_name:123456789> или 🍎):');
          if (val && val.trim() !== '') {
            const opt = document.createElement('option');
            opt.value = val.trim();
            opt.text = 'Свой эмодзи: ' + val.trim();
            el.appendChild(opt);
            el.value = val.trim();
            el.dataset.prevVal = el.value;
            // Trigger unsaved indicator manually since this might bypass the other listener
            const indicator = document.getElementById('unsavedIndicator');
            if (indicator) indicator.classList.add('visible');
          } else {
            el.value = prevVal;
          }
        } else {
          el.dataset.prevVal = el.value;
        }
        updateEmojiPreview(el);
      });
    }
  });
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
    roleSelect.innerHTML += `<option value="${r.id}" style="color:${r.color}">${escapeHtml(r.name)}</option>`;
    removeRoleSelect.innerHTML += `<option value="${r.id}" style="color:${r.color}">${escapeHtml(r.name)}</option>`;
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

    const numericLevel = Number(level);
    if (!Number.isInteger(numericLevel) || numericLevel < 1 || numericLevel > 100) {
      alert('Уровень должен быть целым числом от 1 до 100.');
      return;
    }

    const duplicate = Array.from(document.querySelectorAll('.rank-role-card'))
      .some(card => card !== editingRankRoleCard && Number(card.dataset.level) === numericLevel);
    if (duplicate) {
      alert(`Для уровня ${numericLevel} роль уже настроена.`);
      return;
    }
    
    const list = document.getElementById('rankRolesList');
    
    if (editingRankRoleCard) {
      editingRankRoleCard.remove();
      addRankRoleCard(list, String(numericLevel), roleId, removeRoleId);
    } else {
      addRankRoleCard(list, String(numericLevel), roleId, removeRoleId);
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
      const tagLabel = { level: 'Уровни', admin: 'Админ', econ: 'Экономика', role: 'Профессия', game: 'Игры', gang: 'Банды', util: 'Утилита' }[cmd.tag] || cmd.tag;

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
    if (!CONFIG.supportUrl) {
      btn.hidden = true;
      return;
    }
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
          ${escapeHtml(gang.name)}
          <div style="font-size:0.75rem;color:var(--text-muted);font-weight:400;margin-top:2px;">Улучшения: ${Object.keys(gang.camp_upgrades || {}).length}</div>
        </div>
        <div style="font-size:0.9rem;color:var(--text);font-variant-numeric: tabular-nums;">
          <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" style="vertical-align:middle;margin-right:4px;color:var(--text-muted)"><path d="M17 21v-2a4 4 0 00-4-4H5a4 4 0 00-4 4v2"></path><circle cx="9" cy="7" r="4"></circle><path d="M23 21v-2a4 4 0 00-3-3.87"></path><path d="M16 3.13a4 4 0 010 7.75"></path></svg>
          ${gang.member_count}
        </div>
        <div style="font-size:0.9rem;color:var(--gold);font-family:'ChineseRocks','Oswald',sans-serif;letter-spacing:0.05em">
          $${gang.balance.toLocaleString('ru-RU')}
        </div>
        <div style="display:flex;gap:6px;justify-content:flex-end;">
          <button class="btn btn--secondary btn--sm gang-delete-btn" style="padding:6px;color:var(--red);border-color:rgba(211,47,47,0.3);background:transparent;" title="Удалить банду">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true" width="16" height="16">
              <polyline points="3 6 5 6 21 6"></polyline>
              <path d="M19 6v14a2 2 0 01-2 2H7a2 2 0 01-2-2V6m3 0V4a2 2 0 012-2h4a2 2 0 012 2v2"></path>
              <line x1="10" y1="11" x2="10" y2="17"></line>
              <line x1="14" y1="11" x2="14" y2="17"></line>
            </svg>
          </button>
        </div>
      `;
      card.querySelector('.gang-delete-btn')?.addEventListener('click', () => deleteGang(gang.id, gang.name));
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
document.addEventListener('DOMContentLoaded', async () => {
  await loadPublicConfig();
  await initHomeAuthCta();
  markActiveNav();
  initHamburger();
  initHeroButtons();
  initCommandsPage();
  initLeaderboardSorting();
  initDashboard();
  initLevelsPage();
  initCookieBanner();

  requestAnimationFrame(() => initScrollAnimations());
});
