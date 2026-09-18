'use strict';

/* ---------- Helpers ---------- */

const $ = (selector, root = document) => root.querySelector(selector);
const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];

const ICONS = {
  alert: '<circle cx="12" cy="12" r="9"/><path d="M12 7.5v5.5m0 3.5v.01"/>',
  check: '<path d="m5 12.5 4.5 4.5L19 7.5"/>',
  chevronLeft: '<path d="m14.5 5.5-6.5 6.5 6.5 6.5"/>',
  chevronRight: '<path d="m9.5 5.5 6.5 6.5-6.5 6.5"/>',
  close: '<path d="M6.5 6.5l11 11M17.5 6.5l-11 11"/>',
  download: '<path d="M12 4.5v10m0 0-4-4m4 4 4-4M5.5 19h13"/>',
  film: '<rect x="3.5" y="4.5" width="17" height="15" rx="2.5"/><path d="M8 4.5v15m8-15v15M3.5 9.5H8m8 0h4.5M3.5 14.5H8m8 0h4.5"/>',
  folder: '<path d="M3.5 7.5a2 2 0 0 1 2-2h4l2 2h7a2 2 0 0 1 2 2v7.5a2 2 0 0 1-2 2h-13a2 2 0 0 1-2-2z"/>',
  globe: '<circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3c2.4 2.5 3.7 5.5 3.7 9s-1.3 6.5-3.7 9c-2.4-2.5-3.7-5.5-3.7-9S9.6 5.5 12 3z"/>',
  info: '<circle cx="12" cy="12" r="9"/><path d="M12 11v5.5m0-9v.01"/>',
  play: '<path d="M8 5.8v12.4L18 12z"/>',
  retry: '<path d="M4.5 12a7.5 7.5 0 0 1 12.8-5.3L19.5 9m0-4.5V9H15m4.5 3a7.5 7.5 0 0 1-12.8 5.3L4.5 15m0 4.5V15H9"/>',
  search: '<circle cx="11" cy="11" r="7"/><path d="m20 20-3.5-3.5"/>',
  upload: '<path d="M12 19.5v-11m0 0-4 4m4-4 4 4M5.5 4.5h13"/>',
  star: '<path d="m12 3.2 2.7 5.6 6.1.8-4.5 4.2 1.1 6.1L12 17l-5.4 2.9 1.1-6.1-4.5-4.2 6.1-.8z"/>',
};

function icon(name, className = 'icon') {
  const template = document.createElement('template');
  template.innerHTML = `<svg class="${className}" viewBox="0 0 24 24" aria-hidden="true">${ICONS[name]}</svg>`;
  return template.content.firstElementChild;
}

function h(tag, props = {}, ...children) {
  const node = document.createElement(tag);

  for (const [key, value] of Object.entries(props || {})) {
    if (value === null || value === undefined || value === false) continue;
    if (key === 'class') node.className = value;
    else if (key === 'dataset') Object.assign(node.dataset, value);
    else if (key.startsWith('on') && typeof value === 'function') node.addEventListener(key.slice(2), value);
    else node.setAttribute(key, value === true ? '' : String(value));
  }

  for (const child of children.flat(Infinity)) {
    if (child === null || child === undefined || child === false || child === '') continue;
    node.append(child instanceof Node ? child : String(child));
  }

  return node;
}

function plural(count, one, many) {
  return `${count} ${count === 1 ? one : many}`;
}

function initials(name = '') {
  return name.split(/\s+/).filter(Boolean).slice(0, 2).map((word) => word[0]).join('').toUpperCase();
}

function hue(id) {
  return (Number(id) * 47) % 360;
}

function formatRuntime(minutes) {
  if (!minutes) return null;
  const hours = Math.floor(minutes / 60);
  const rest = minutes % 60;
  if (!hours) return `${rest} min`;
  return rest ? `${hours} h ${rest} min` : `${hours} h`;
}

function isAnime(title) {
  return title?.source === 'anime';
}

// Ids of the two sites can be the same number
function keyOf(title) {
  return `${title.source || 'sc'}:${title.id}`;
}

function apiPath(source, path) {
  return source === 'anime' ? `/api/anime${path}` : `/api${path}`;
}

function titleKind(title) {
  if (isAnime(title)) return !title.label || title.label === 'Anime' ? 'Anime' : `Anime · ${title.label}`;
  return title.type === 'tv' ? 'Serie TV' : 'Film';
}

function titleLength(title) {
  if (isAnime(title) && title.type === 'tv') return title.episodes_count ? plural(title.episodes_count, 'episodio', 'episodi') : null;
  if (title.type === 'tv') return title.seasons_count ? plural(title.seasons_count, 'stagione', 'stagioni') : null;
  return formatRuntime(title.runtime);
}

function episodeCode(job) {
  if (job.source === 'anime') return `E${String(job.episode_number).padStart(2, '0')}`;
  return `S${String(job.season).padStart(2, '0')}E${String(job.episode_number).padStart(2, '0')}`;
}

function jobName(job) {
  return job.type === 'tv' ? `${job.name} ${episodeCode(job)}` : job.name;
}

function jobSubtitle(job) {
  if (job.source === 'anime') return job.type === 'tv' ? `Anime · Episodio ${job.episode_number}` : 'Film anime';
  return job.type === 'tv' ? [episodeCode(job), job.episode_name].filter(Boolean).join(' · ') : 'Film';
}

function scoreNode(score) {
  return score ? h('span', { class: 'score' }, icon('star', 'icon-fill'), score) : null;
}

function pill(text) {
  return text ? h('span', { class: 'pill' }, text) : null;
}

function metaRow(parts) {
  const row = h('div', { class: 'meta' });

  parts.filter(Boolean).forEach((part, index) => {
    if (index) row.append(h('span', { class: 'sep', 'aria-hidden': 'true' }));
    row.append(part);
  });

  return row;
}

function image(src, className = '', { lazy = true } = {}) {
  const node = h('img', { class: className, src, alt: '', loading: lazy ? 'lazy' : null, decoding: 'async' });
  node.addEventListener('load', () => node.classList.add('loaded'), { once: true });
  node.addEventListener('error', () => node.remove(), { once: true });
  return node;
}

function posterNode(title, className = 'poster') {
  return h('span', { class: className, style: `--hue:${hue(title.id)}` },
    h('span', { class: 'poster-fallback', 'aria-hidden': 'true' }, initials(title.name)),
    title.poster ? image(title.poster) : null);
}

function emptyState(iconName, title, text, action = null) {
  return h('div', { class: 'empty' },
    h('span', { class: 'empty-icon' }, icon(iconName)),
    h('h3', {}, title),
    h('p', {}, text),
    action);
}

function errorState(error, retry) {
  return emptyState('alert', 'Qualcosa è andato storto', error.message,
    retry ? h('button', { class: 'button ghost small', type: 'button', onclick: retry }, icon('retry'), 'Riprova') : null);
}

async function api(path, { method = 'GET', body } = {}) {
  let response;

  try {
    response = await fetch(path, {
      method,
      headers: body ? { 'Content-Type': 'application/json' } : undefined,
      body: body ? JSON.stringify(body) : undefined,
    });
  } catch {
    throw new Error('Il programma non risponde: controlla che sia ancora aperto');
  }

  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(data.error || `Errore ${response.status}`);
  return data;
}

/* ---------- State ---------- */

const HERO_INTERVAL = 9000;

// Weight of each download stage on the total progress
const STAGES = {
  video: { label: 'Video', from: 0, to: 72 },
  join_video: { label: 'Unione video', from: 72, to: 75 },
  audio: { label: 'Audio', from: 75, to: 85 },
  join_audio: { label: 'Unione audio', from: 85, to: 86 },
  merge: { label: 'Finalizzazione', from: 86, to: 88 },
  upload: { label: 'Caricamento sul NAS', from: 88, to: 100 },
};

const CATEGORIES = {
  sc: { label: 'Film e Serie', search: 'Cerca film e serie TV', hero: (index) => `N° ${index + 1} in tendenza` },
  anime: { label: 'Anime', search: 'Cerca anime', hero: () => 'In evidenza' },
};

function savedCategory() {
  try {
    return localStorage.getItem('category') === 'anime' ? 'anime' : 'sc';
  } catch {
    return 'sc';
  }
}

const state = {
  status: null,
  category: savedCategory(),
  homes: {},
  hero: { items: [], index: 0, timer: null, contentTimer: null },
  searchId: 0,
  detail: null,
  detailId: 0,
  season: null,
  episodes: null,
  selected: new Set(),
  jobs: [],
  pollTimer: null,
  eta: new Map(),
  nas: null,
};

const detailCache = new Map();
const detailRequests = new Map();
const seasonCache = new Map();
const jobNodes = new Map();
const layers = [];
const rowUpdaters = new Set();
const searchInput = $('#search-input');
let searchTimer = null;

/* ---------- Layers ---------- */

function openLayer(layer) {
  clearTimeout(layer.closeTimer);

  if (!layers.includes(layer)) {
    layer.returnFocus = document.activeElement;
    layers.push(layer);
  }

  layer.hidden = false;
  layer.getBoundingClientRect();
  layer.classList.add('open');
  document.body.classList.add('no-scroll');
  syncHero();
}

function closeLayer(layer) {
  const index = layers.indexOf(layer);
  if (index < 0) return;

  layers.splice(index, 1);
  layer.classList.remove('open');
  layer.closeTimer = setTimeout(() => { layer.hidden = true; }, 500);

  if (!layers.length) document.body.classList.remove('no-scroll');
  if (layer.returnFocus && document.contains(layer.returnFocus)) layer.returnFocus.focus({ preventScroll: true });

  layer.dispatchEvent(new CustomEvent('layerclose'));
  syncHero();
}

/* ---------- Status and settings ---------- */

async function loadStatus() {
  try {
    state.status = await api('/api/status');
  } catch (error) {
    state.status = { connected: false, domain: '', error: error.message };
  }

  renderStatus();
  return state.status;
}

function renderStatus() {
  const { status } = state;
  const chip = $('#status-chip');

  chip.classList.toggle('online', Boolean(status?.connected));
  chip.classList.toggle('offline', Boolean(status) && !status.connected);
  $('.status-label', chip).textContent = status?.connected ? `.${status.domain}` : status?.domain ? 'Non connesso' : 'Configura';
  chip.title = status?.connected ? `Connesso a ${status.site}` : status?.error || 'Configura il sito';
  chip.setAttribute('aria-label', chip.title);

  if (status?.site_name) $('#domain-prefix').textContent = `${status.site_name}.`;
  document.body.classList.toggle('remote-client', Boolean(status?.remote_client));
}

function openSettings({ welcome = false, panel = 'site' } = {}) {
  const { status } = state;
  const error = $('#settings-error');

  $('#settings-title').textContent = welcome ? 'Benvenuto in SC Downloader' : 'Connessione al sito';
  $('#settings-text').textContent = welcome
    ? "Per iniziare inserisci l'estensione attuale del sito."
    : "Il sito cambia spesso estensione: se smette di funzionare, inserisci quella nuova.";
  $('#domain-input').value = status?.domain || '';
  error.textContent = status?.connected ? '' : status?.error || '';
  error.hidden = !error.textContent;

  $('#settings-form .notice')?.remove();
  if (status?.ffmpeg === false) {
    $('#settings-submit').before(h('div', { class: 'notice' }, icon('alert'), 'FFmpeg non è installato: puoi cercare, ma i download non funzioneranno.'));
  }

  showSettingsPanel(panel);
  openLayer($('#settings'));
  setTimeout(() => (panel === 'nas' ? $('#nas-host') : $('#domain-input')).focus(), 80);
}

function showSettingsPanel(name) {
  $$('.settings-tabs .tab').forEach((tab) => tab.setAttribute('aria-selected', String(tab.dataset.panel === name)));
  $('#settings-form').hidden = name !== 'site';
  $('#nas-form').hidden = name !== 'nas';
  $('#remote-panel').hidden = name !== 'remote';

  if (name === 'nas') loadNas();
  if (name === 'remote') loadRemote();
}

/* ---------- Access from the phone ---------- */

async function loadRemote() {
  try {
    renderRemote(await api('/api/remote'));
  } catch (error) {
    $('#remote-result').replaceChildren(h('div', { class: 'result bad' }, h('strong', {}, error.message)));
  }
}

function renderRemote(info) {
  $('#remote-enabled').checked = Boolean(info.enabled);
  $('#remote-box').hidden = !(info.enabled && info.running);
  $('#remote-result').replaceChildren();

  if (info.enabled && !info.url) {
    $('#remote-result').replaceChildren(h('div', { class: 'result bad' }, h('strong', {}, 'Il PC non sembra collegato a una rete di casa')));
    return;
  }

  // The svg is made by the program on this pc
  $('#remote-qr').innerHTML = info.qr || '';
  $('#remote-address').textContent = info.addresses?.[0] || '';
}

async function setRemote(enabled) {
  const toggle = $('#remote-enabled');
  toggle.disabled = true;

  try {
    renderRemote(await api('/api/remote', { method: 'POST', body: { enabled } }));
    toast(enabled ? 'Accesso dal telefono attivo' : 'Accesso dal telefono disattivato', 'success');
  } catch (error) {
    toggle.checked = !enabled;
    $('#remote-result').replaceChildren(h('div', { class: 'result bad' }, h('strong', {}, error.message)));
  } finally {
    toggle.disabled = false;
  }
}

async function newRemoteKey() {
  try {
    renderRemote(await api('/api/remote/key', { method: 'POST', body: {} }));
    toast('Telefoni scollegati: inquadra il nuovo codice per ricollegarli', 'success');
  } catch (error) {
    toast(error.message, 'error');
  }
}

/* ---------- NAS ---------- */

async function loadNas() {
  try {
    const config = await api('/api/nas');
    state.nas = config;

    $('#nas-enabled').checked = Boolean(config.enabled);
    $('#nas-host').value = config.host || '';
    $('#nas-port').value = config.port || 22;
    $('#nas-user').value = config.user || '';
    $('#nas-film').value = config.film_path || '';
    $('#nas-tv').value = config.tv_path || '';
    $('#nas-anime').value = config.anime_path || '';
    $('#nas-password').value = '';
    $('#nas-password').placeholder = config.password_saved ? 'Password salvata' : 'Inserisci la password';
  } catch (error) {
    showNasResult(false, error.message);
  }
}

function readNas() {
  return {
    enabled: $('#nas-enabled').checked,
    host: $('#nas-host').value.trim(),
    port: Number($('#nas-port').value) || 22,
    user: $('#nas-user').value.trim(),
    film_path: $('#nas-film').value.trim(),
    tv_path: $('#nas-tv').value.trim(),
    anime_path: $('#nas-anime').value.trim(),
    password: $('#nas-password').value,
  };
}

function showNasResult(ok, message, details = []) {
  $('#nas-result').replaceChildren(h('div', { class: `result ${ok ? 'ok' : 'bad'}` }, h('strong', {}, message), details));
}

async function testNas() {
  const button = $('#nas-test');
  const config = readNas();

  if (!config.host || !config.user) {
    showNasResult(false, 'Inserisci indirizzo e utente del NAS');
    return;
  }

  button.classList.add('loading');
  button.disabled = true;
  $('#nas-result').replaceChildren();

  try {
    const result = await api('/api/nas/test', { method: 'POST', body: config });

    if (!result.ok) {
      showNasResult(false, result.error);
      return;
    }

    const labels = { film_path: 'Film', tv_path: 'Serie TV', anime_path: 'Anime' };
    const details = [];

    for (const [key, folder] of Object.entries(result.folders)) {
      if (!folder.path) continue;

      details.push(h('div', {}, `${labels[key]}: `, h('code', {}, folder.path), folder.exists ? ' — cartella trovata' : ' — non esiste ancora, la creo al primo caricamento'));

      if (!folder.exists && folder.near.length) {
        details.push(h('div', {}, 'Lì accanto ci sono: ', h('code', {}, folder.near.slice(0, 8).join(', '))));
      }
    }

    showNasResult(true, 'Collegamento riuscito', details);
  } catch (error) {
    showNasResult(false, error.message);
  } finally {
    button.classList.remove('loading');
    button.disabled = false;
  }
}

async function saveNas(event) {
  event.preventDefault();

  const button = $('#nas-save');
  const config = readNas();

  if (config.enabled && (!config.host || !config.user || !config.film_path)) {
    showNasResult(false, 'Per attivare il caricamento servono indirizzo, utente e cartella film');
    return;
  }

  button.classList.add('loading');
  button.disabled = true;

  try {
    state.nas = await api('/api/nas', { method: 'POST', body: config });
    $('#nas-password').value = '';
    $('#nas-password').placeholder = state.nas.password_saved ? 'Password salvata' : 'Inserisci la password';
    toast(state.nas.enabled ? 'Caricamento sul NAS attivo' : 'Impostazioni del NAS salvate', 'success');
    loadStatus();
  } catch (error) {
    showNasResult(false, error.message);
  } finally {
    button.classList.remove('loading');
    button.disabled = false;
  }
}

async function submitDomain(event) {
  event.preventDefault();

  const input = $('#domain-input');
  const error = $('#settings-error');
  const button = $('#settings-submit');
  const siteName = state.status?.site_name || 'streamingcommunityz';

  // Accept also a pasted address like https://site.academy/it
  const domain = input.value.trim()
    .replace(/^https?:\/\//i, '')
    .replace(new RegExp(`^(www\\.)?${siteName}\\.`, 'i'), '')
    .replace(/\/.*$/, '')
    .replace(/^\.+|\.+$/g, '');

  if (!domain) {
    error.textContent = "Inserisci l'estensione, per esempio academy";
    error.hidden = false;
    input.focus();
    return;
  }

  const previous = state.status?.connected ? state.status.domain : null;
  button.classList.add('loading');
  button.disabled = true;
  error.hidden = true;

  try {
    state.status = await api('/api/domain', { method: 'POST', body: { domain } });
    renderStatus();
    closeLayer($('#settings'));
    toast(`Connesso a ${state.status.site}`, 'success');

    if (previous !== state.status.domain || !state.homes.sc) {
      detailCache.clear();
      seasonCache.clear();
      delete state.homes.sc;
      if (state.category === 'sc') loadHome();
    }
  } catch (requestError) {
    error.textContent = requestError.message;
    error.hidden = false;
  } finally {
    button.classList.remove('loading');
    button.disabled = false;
  }
}

/* ---------- Home ---------- */

async function loadHome() {
  const category = state.category;
  $('#home-view').dataset.category = category;

  // Films and series need their site connected, anime come from another site
  if (category === 'sc' && !state.status?.connected) {
    renderHomeMessage('Collega il sito per iniziare',
      state.status?.error || "Inserisci l'estensione attuale del sito per vedere i titoli del momento e cercare film e serie TV.",
      h('button', { class: 'button primary', type: 'button', onclick: () => openSettings() }, icon('globe'), 'Imposta il sito'));
    return;
  }

  renderHomeLoading();

  try {
    const home = await api(apiPath(category, '/home'));
    state.homes[category] = home;
    if (category === state.category) renderHome();
  } catch (error) {
    if (category !== state.category) return;
    renderHomeMessage('Home non disponibile', error.message,
      h('button', { class: 'button glass', type: 'button', onclick: loadHome }, icon('retry'), 'Riprova'));
  }
}

function renderHomeLoading() {
  $('#hero').classList.toggle('compact', state.category === 'anime');
  const content = $('#hero-content');

  content.replaceChildren(h('div', { class: 'hero-skeleton', 'aria-hidden': 'true' },
    h('div', { class: 'skeleton sk-logo' }),
    h('div', { class: 'skeleton sk-block', style: 'width: 72%' }),
    h('div', { class: 'skeleton sk-block', style: 'width: 56%' })));
  content.classList.add('visible');

  $('#rows').replaceChildren(skeletonRow(), skeletonRow());
}

function skeletonRow() {
  return h('section', { class: 'row', 'aria-hidden': 'true' },
    h('div', { class: 'row-head' }, h('div', { class: 'skeleton sk-title' })),
    h('div', { class: 'row-track' }, Array.from({ length: 12 }, skeletonCard)));
}

function skeletonCard(_, index = 0) {
  return h('div', { class: 'card', style: `--i:${index}`, 'aria-hidden': 'true' },
    h('div', { class: 'skeleton sk-poster' }),
    h('div', { class: 'skeleton sk-line' }),
    h('div', { class: 'skeleton sk-line short' }));
}

function renderHomeMessage(title, text, action) {
  clearTimeout(state.hero.timer);
  state.hero.items = [];

  $('#hero-media').replaceChildren();
  $('#hero-dots').replaceChildren();
  $('#rows').replaceChildren();

  const content = $('#hero-content');
  content.replaceChildren(
    h('p', { class: 'eyebrow' }, h('span', { class: 'eyebrow-dot' }), 'SC Downloader'),
    h('h1', { class: 'hero-title' }, title),
    h('p', { class: 'hero-plot' }, text),
    h('div', { class: 'hero-actions' }, action));
  content.classList.add('visible');
}

function renderHome() {
  const home = state.homes[state.category];
  const sliders = (home.sliders || []).filter((slider) => slider.titles.length);
  const order = ['top10', 'trending', 'latest'];
  const position = (slider) => (order.includes(slider.name) ? order.indexOf(slider.name) : order.length);

  $('#home-view').dataset.category = state.category;
  $('#hero').classList.toggle('compact', state.category === 'anime');

  rowUpdaters.clear();
  $('#rows').replaceChildren(...[...sliders].sort((a, b) => position(a) - position(b)).map((slider) => renderRow(slider)));
  loadRecommendations();

  // Anime have their own featured titles, films and series use the trending ones
  const trending = sliders.find((slider) => slider.name === 'trending') || sliders[0];
  state.hero.items = (home.hero || trending?.titles || []).filter((title) => title.backdrop).slice(0, 8);
  state.hero.index = 0;

  if (state.hero.items.length) {
    showHero(0);
  } else {
    renderHomeMessage('Cosa scarichiamo oggi?', 'Cerca un film o una serie TV con la barra in alto.', null);
  }
}

/* ---------- Hero ---------- */

function showHero(index) {
  const { items } = state.hero;
  if (!items.length) return;

  state.hero.index = (index + items.length) % items.length;
  const title = items[state.hero.index];

  // Cross fade between backdrops
  const media = $('#hero-media');
  const backdrop = h('img', { class: 'hero-backdrop', src: title.backdrop, alt: '' });
  backdrop.addEventListener('load', () => {
    backdrop.classList.add('visible');
    $$('.hero-backdrop', media).filter((node) => node !== backdrop).forEach((node) => setTimeout(() => node.remove(), 1300));
  }, { once: true });
  media.append(backdrop);

  const content = $('#hero-content');
  const delay = content.classList.contains('visible') && content.childElementCount ? 300 : 0;
  content.classList.remove('visible');
  clearTimeout(state.hero.contentTimer);

  state.hero.contentTimer = setTimeout(() => {
    content.replaceChildren(...heroContent(title));
    requestAnimationFrame(() => content.classList.add('visible'));
    fillHeroDetail(title);
  }, delay);

  syncHero();
  preloadHero(state.hero.index + 1);
}

function heroContent(title) {
  const detail = detailCache.get(keyOf(title));
  const heading = title.logo
    ? h('h1', { class: 'hero-heading' }, h('img', {
      class: 'hero-logo',
      src: title.logo,
      alt: title.name,
      onerror: (event) => event.target.parentElement.replaceWith(h('h1', { class: 'hero-title' }, title.name)),
    }))
    : h('h1', { class: 'hero-title' }, title.name);

  const primary = title.type === 'tv'
    ? h('button', { class: 'button primary', type: 'button', onclick: () => openDetail(title) }, icon('download'), 'Scegli episodi')
    : h('button', { class: 'button primary', type: 'button', onclick: () => queueMovie(title) }, icon('download'), 'Scarica film');

  const text = [
    h('p', { class: 'eyebrow' }, h('span', { class: 'eyebrow-dot' }), CATEGORIES[state.category].hero(state.hero.index)),
    heading,
    heroMeta(title, detail),
    h('p', { class: 'hero-plot' }, detail?.plot || title.plot || ''),
    h('div', { class: 'hero-actions' },
      primary,
      h('button', { class: 'button glass', type: 'button', onclick: () => openDetail(title) }, icon('info'), 'Dettagli')),
  ];

  // Banners of anime are low, the poster next to the title fills the space
  if (!isAnime(title) || !title.poster) return text;
  return [h('div', { class: 'hero-with-poster' }, posterNode(title, 'poster hero-poster'), h('div', { class: 'hero-text' }, text))];
}

function heroMeta(title, detail) {
  return metaRow([
    scoreNode(title.score),
    title.year,
    titleKind(title),
    titleLength(detail || title),
    title.age ? pill(`${title.age}+`) : null,
  ]);
}

async function fillHeroDetail(title) {
  try {
    const detail = await getDetail(title);
    if (state.hero.items[state.hero.index]?.id !== title.id) return;

    const content = $('#hero-content');
    const plot = $('.hero-plot', content);
    if (plot && !plot.textContent) plot.textContent = detail.plot || '';
    $('.meta', content)?.replaceWith(heroMeta(title, detail));
  } catch {
    // The hero works also without plot
  }
}

function preloadHero(index) {
  const title = state.hero.items[index % state.hero.items.length];
  if (!title || title.preloaded) return;

  title.preloaded = true;
  new Image().src = title.backdrop;
  if (title.logo) new Image().src = title.logo;
  getDetail(title).catch(() => {});
}

function renderHeroDots() {
  const { items, index } = state.hero;
  const dots = $('#hero-dots');

  dots.style.setProperty('--hero-interval', `${HERO_INTERVAL}ms`);
  dots.replaceChildren(...(items.length < 2 ? [] : items.map((title, position) => h('button', {
    class: `hero-dot${position === index ? ' active' : ''}`,
    type: 'button',
    'aria-label': `Mostra ${title.name}`,
    'aria-current': position === index ? 'true' : null,
    onclick: () => position !== state.hero.index && showHero(position),
  }))));
}

function syncHero() {
  clearTimeout(state.hero.timer);

  const active = state.hero.items.length > 1 && !$('#home-view').hidden && !layers.length && !document.hidden;
  $('#hero').classList.toggle('paused', !active);

  // Render dots again to restart the progress of the active one
  renderHeroDots();

  if (active) state.hero.timer = setTimeout(() => showHero(state.hero.index + 1), HERO_INTERVAL);
}

/* ---------- Rows and cards ---------- */

function renderRow(slider) {
  const ranked = slider.name === 'top10';
  const track = h('div', { class: 'row-track' }, slider.titles.map((title, index) => card(title, { index, rank: ranked ? index + 1 : null })));
  const prev = h('button', { class: 'row-arrow prev', type: 'button', tabindex: '-1', 'aria-label': 'Scorri indietro', onclick: () => scrollRow(track, -1) }, icon('chevronLeft'));
  const next = h('button', { class: 'row-arrow next', type: 'button', tabindex: '-1', 'aria-label': 'Scorri avanti', onclick: () => scrollRow(track, 1) }, icon('chevronRight'));

  const update = () => {
    prev.disabled = track.scrollLeft <= 4;
    next.disabled = track.scrollLeft + track.clientWidth >= track.scrollWidth - 4;
  };

  track.addEventListener('scroll', update, { passive: true });
  rowUpdaters.add(update);
  requestAnimationFrame(update);

  return h('section', { class: `row${ranked ? ' row-top' : ''}`, 'aria-label': slider.label },
    h('div', { class: 'row-head' },
      h('div', {},
        h('h2', { class: 'row-title' }, slider.label),
        slider.subtitle ? h('p', { class: 'row-sub' }, slider.subtitle) : null)),
    h('div', { class: 'row-viewport' }, prev, track, next));
}

function scrollRow(track, direction) {
  track.scrollBy({ left: direction * track.clientWidth * 0.8, behavior: 'smooth' });
}

function card(title, { index = 0, rank = null } = {}) {
  const poster = posterNode(title);

  poster.append(...[
    h('span', { class: 'poster-type' }, title.label || (title.type === 'tv' ? 'Serie' : 'Film')),
    title.score ? h('span', { class: 'poster-score' }, icon('star', 'icon-fill'), title.score) : null,
    h('span', { class: 'poster-hover', 'aria-hidden': 'true' }, h('span', { class: 'poster-action' }, icon('info'))),
  ].filter(Boolean));

  return h('button', {
    class: `card${rank ? ' ranked' : ''}${rank >= 10 ? ' double' : ''}`,
    type: 'button',
    style: `--i:${index}`,
    title: title.name,
    'aria-label': `${title.name}, ${titleKind(title)}${title.year ? `, ${title.year}` : ''}`,
    onclick: () => openDetail(title),
  },
    rank ? h('span', { class: 'rank', 'aria-hidden': 'true' }, rank) : null,
    poster,
    h('span', { class: 'card-body', 'aria-hidden': 'true' },
      h('span', { class: 'card-title' }, title.name),
      h('span', { class: 'card-meta' }, cardMeta(title)),
      title.reason ? h('span', { class: 'card-reason', title: title.reason }, title.reason) : null));
}

/* ---------- Recommendations ---------- */

let recommendationsRequest = 0;
let recommendationsTimer = null;

async function loadRecommendations() {
  const requestId = ++recommendationsRequest;
  const category = state.category;
  let row = $('#recommended');

  // First load shows a placeholder, a refresh keeps the old row until the new one is ready
  if (!row) {
    row = skeletonRow();
    row.id = 'recommended';
    $('#rows').prepend(row);
  }

  try {
    const { titles, based_on: basedOn } = await api(apiPath(category, '/recommendations'));
    if (requestId !== recommendationsRequest || category !== state.category || !document.contains(row)) return;

    if (!titles.length) {
      row.remove();
      return;
    }

    const fresh = renderRow({
      name: 'recommended',
      label: 'Consigliati per te',
      subtitle: `In base a ${plural(basedOn, 'titolo che hai scaricato', 'titoli che hai scaricato')}`,
      titles,
    });
    fresh.id = 'recommended';
    row.replaceWith(fresh);
  } catch {
    // Recommendations are extra, the home works without them
    if (requestId === recommendationsRequest) row.remove();
  }
}

function refreshRecommendations() {
  clearTimeout(recommendationsTimer);
  if (state.homes[state.category] && !$('#home-view').hidden) recommendationsTimer = setTimeout(loadRecommendations, 1500);
}

function cardMeta(title) {
  let length;

  if (isAnime(title)) {
    length = title.type === 'tv' && title.episodes_count ? plural(title.episodes_count, 'episodio', 'episodi') : title.label;

    // The dubbed copy has the same name and poster of the original one
    if (title.dub) return [title.year, length, 'ITA'].filter(Boolean).join(' · ');
  } else {
    length = title.type === 'tv'
      ? (title.seasons_count ? plural(title.seasons_count, 'stagione', 'stagioni') : 'Serie TV')
      : 'Film';
  }

  return [title.year, length].filter(Boolean).join(' · ');
}

/* ---------- Search ---------- */

function onSearchInput() {
  const query = searchInput.value.trim();
  $('#search-clear').hidden = !searchInput.value;
  clearTimeout(searchTimer);

  if (!query) {
    goHome();
    return;
  }

  if (query.length >= 2) searchTimer = setTimeout(() => runSearch(query), 450);
}

async function runSearch(query) {
  clearTimeout(searchTimer);
  const category = state.category;

  if (category === 'sc' && !state.status?.connected) {
    openSettings();
    return;
  }

  const searchId = ++state.searchId;
  showView('search');
  $('#search-view .eyebrow').textContent = `Risultati della ricerca · ${CATEGORIES[category].label}`;
  $('#search-title').textContent = `“${query}”`;
  $('#search-count').textContent = 'Ricerca in corso…';
  $('#results').replaceChildren(...Array.from({ length: 14 }, skeletonCard));

  try {
    const { results } = await api(apiPath(category, `/search?q=${encodeURIComponent(query)}`));
    if (searchId !== state.searchId) return;

    $('#search-count').textContent = results.length ? plural(results.length, 'titolo trovato', 'titoli trovati') : '';
    $('#results').replaceChildren(...(results.length
      ? results.map((title, index) => card(title, { index }))
      : [emptyState('search', 'Nessun risultato', `Nessun titolo corrisponde a “${query}”. Controlla come è scritto o prova con meno parole.`)]));
  } catch (error) {
    if (searchId !== state.searchId) return;
    $('#search-count').textContent = '';
    $('#results').replaceChildren(errorState(error, () => runSearch(query)));
  }
}

function showView(name) {
  const wasHome = !$('#home-view').hidden;

  $('#home-view').hidden = name !== 'home';
  $('#search-view').hidden = name !== 'search';

  if (wasHome !== (name === 'home')) window.scrollTo({ top: 0 });
  updateTopbar();
  syncHero();
}

function goHome() {
  state.searchId += 1;
  clearTimeout(searchTimer);
  searchInput.value = '';
  $('#search-clear').hidden = true;
  showView('home');

  // The home on screen can be of the other category
  if ($('#home-view').dataset.category !== state.category) {
    if (state.homes[state.category]) renderHome();
    else loadHome();
  }
}

/* ---------- Categories ---------- */

function setCategory(category) {
  if (category === state.category) {
    goHome();
    return;
  }

  state.category = category;

  try {
    localStorage.setItem('category', category);
  } catch {
    // Only the choice of the next start is lost
  }

  renderCategory();

  // A search on screen is done again in the new category
  const query = searchInput.value.trim();
  if (query && !$('#search-view').hidden) runSearch(query);
  else goHome();
}

function renderCategory() {
  const { search } = CATEGORIES[state.category];

  $$('#category-switch .category').forEach((button) => {
    button.setAttribute('aria-selected', String(button.dataset.category === state.category));
  });
  $('#category-switch').dataset.active = state.category;

  searchInput.placeholder = search;
  searchInput.setAttribute('aria-label', search);
}

function updateTopbar() {
  $('#topbar').classList.toggle('scrolled', window.scrollY > 30 || !$('#search-view').hidden);
}

/* ---------- Detail ---------- */

function getDetail(title) {
  const key = keyOf(title);
  if (detailCache.has(key)) return Promise.resolve(detailCache.get(key));

  if (!detailRequests.has(key)) {
    const request = api(apiPath(title.source, `/title?id=${title.id}&slug=${encodeURIComponent(title.slug || '')}`))
      .then((detail) => {
        detailCache.set(key, detail);
        return detail;
      })
      .finally(() => detailRequests.delete(key));

    detailRequests.set(key, request);
  }

  return detailRequests.get(key);
}

// Seasons for series, blocks of episodes for anime that can have more than a thousand
function episodeGroups(detail) {
  if (isAnime(detail)) {
    return (detail.groups || []).map((group) => ({ key: `${group.start}-${group.end}`, label: `${group.start}–${group.end}`, ...group }));
  }

  return (detail.seasons || []).map((number) => ({ key: String(number), label: `Stagione ${number}`, number }));
}

async function openDetail(title) {
  const detailId = ++state.detailId;
  const cached = detailCache.get(keyOf(title));
  const layer = $('#detail');

  state.detail = cached || title;
  state.season = null;
  state.episodes = null;
  state.selected = new Set();

  renderDetail(state.detail, !cached);
  $('.sheet', layer).scrollTop = 0;
  openLayer(layer);
  $('.close-button', layer).focus({ preventScroll: true });

  let detail = cached;

  if (!detail) {
    try {
      detail = await getDetail(title);
    } catch (error) {
      if (detailId === state.detailId) {
        $('#detail-body').replaceWith(h('div', { class: 'detail-body', id: 'detail-body' }, errorState(error, () => openDetail(title))));
      }
      return;
    }

    if (detailId !== state.detailId) return;
    state.detail = detail;
    renderDetail(detail, false);
  }

  const groups = episodeGroups(detail);
  if (detail.type === 'tv' && groups.length) selectSeason(groups[0].key);
}

function renderDetail(detail, loading) {
  const container = $('#detail-content');
  const fresh = container.dataset.titleId !== keyOf(detail);

  if (fresh) {
    container.dataset.titleId = keyOf(detail);
    container.replaceChildren(
      h('div', { class: 'detail-hero' },
        detail.backdrop ? image(detail.backdrop, 'detail-backdrop', { lazy: false }) : null,
        h('div', { class: 'detail-head' },
          posterNode(detail, 'poster detail-poster'),
          h('div', { id: 'detail-info' }))),
      h('div', { id: 'detail-body' }));
  }

  $('#detail-info').replaceWith(detailInfo(detail, fresh));
  $('#detail-body').replaceWith(loading ? detailLoading() : detailBody(detail));

  if (!loading && detail.type === 'tv') renderSeasonTabs();
}

function detailInfo(detail, animate) {
  const heading = detail.logo
    ? h('h2', { class: 'detail-heading' }, h('img', {
      class: 'detail-logo',
      src: detail.logo,
      alt: detail.name,
      onerror: (event) => event.target.parentElement.replaceWith(h('h2', { class: 'detail-title' }, detail.name)),
    }))
    : h('h2', { class: 'detail-title' }, detail.name);

  return h('div', { class: 'detail-info', id: 'detail-info', style: animate ? null : 'animation: none' },
    h('p', { class: 'eyebrow' }, titleKind(detail)),
    heading,
    detail.original_name && detail.original_name !== detail.name ? h('p', { class: 'detail-original' }, detail.original_name) : null,
    metaRow([
      scoreNode(detail.score),
      detail.year,
      titleLength(detail),
      pill(detail.quality),
      detail.age ? pill(`${detail.age}+`) : null,
      detail.sub_ita ? pill('Sub ITA') : null,
      detail.dub ? pill('Doppiato') : null,
    ]),
    detail.genres?.length ? h('div', { class: 'genres' }, detail.genres.map((genre) => h('span', { class: 'genre' }, genre))) : null);
}

function detailLoading() {
  return h('div', { class: 'detail-body', id: 'detail-body', 'aria-busy': 'true' },
    h('div', { class: 'detail-loading' },
      h('div', { class: 'skeleton sk-block', style: 'width: 94%' }),
      h('div', { class: 'skeleton sk-block', style: 'width: 88%' }),
      h('div', { class: 'skeleton sk-block', style: 'width: 62%' })));
}

function detailBody(detail) {
  // Anime give studio and state, films and series give direction and cast
  const credits = detail.credits
    ? detail.credits.map((credit) => h('div', {}, h('dt', {}, credit.label), h('dd', {}, credit.value)))
    : [
      detail.directors?.length ? h('div', {}, h('dt', {}, 'Regia'), h('dd', {}, detail.directors.join(', '))) : null,
      detail.actors?.length ? h('div', {}, h('dt', {}, 'Cast'), h('dd', {}, detail.actors.join(', '))) : null,
    ].filter(Boolean);

  // Long plots are collapsed so episodes stay close
  const plot = h('p', { class: 'plot clamped' }, detail.plot || 'Trama non disponibile.');
  const more = h('button', {
    class: 'link-button',
    type: 'button',
    hidden: true,
    onclick: () => {
      more.textContent = plot.classList.toggle('clamped') ? 'Leggi tutto' : 'Mostra meno';
    },
  }, 'Leggi tutto');
  requestAnimationFrame(() => { more.hidden = plot.scrollHeight <= plot.clientHeight + 2; });

  return h('div', { class: 'detail-body', id: 'detail-body' },
    h('div', { class: 'detail-grid' },
      h('div', {},
        plot,
        more,
        detail.type === 'tv' ? null : h('div', { class: 'detail-actions' }, movieButton(detail), previewButton(() => openPreview(detail)))),
      credits.length ? h('dl', { class: 'credits' }, credits) : null),
    detail.type === 'tv' ? h('section', { class: 'seasons', id: 'seasons', 'aria-label': 'Episodi' }) : null,
    detail.related?.length ? h('section', { class: 'related', 'aria-label': 'Correlati' },
      h('h3', { class: 'section-title' }, 'Correlati'),
      h('div', { class: 'related-grid' }, detail.related.map((title, index) => card(title, { index })))) : null);
}

function movieButton(detail) {
  const button = h('button', { class: 'button primary', type: 'button', id: 'movie-button' }, icon('download'), h('span', {}, 'Scarica film'));
  updateMovieButton(button, detail);
  return button;
}

function updateMovieButton(button, detail) {
  const job = findJob(detail);
  const percent = Math.floor(jobPercent(job));
  const [style, iconName, label, disabled] = {
    queued: ['glass', 'download', 'In coda', true],
    waiting: ['glass', 'retry', 'Problema temporaneo · riprovo da solo', true],
    running: ['glass', 'download', job?.cancel ? 'Annullamento…' : job?.waiting === 'offline' ? `In pausa, senza connessione · ${percent}%` : job?.stage ? `Download in corso · ${percent}%` : 'Avvio del download…', true],
    done: job?.remote && !job?.warning
      ? ['success', 'check', 'Caricato sul NAS', true]
      : ['success', 'check', 'Scaricato · Mostra file', false],
    error: ['primary', 'retry', 'Riprova il download', false],
  }[job?.status] || ['primary', 'download', 'Scarica film', false];

  button.className = `button ${style}`;
  button.disabled = disabled;
  $('span', button).textContent = label;
  button.onclick = job?.status === 'done' ? () => openFolder(job.id) : () => queueMovie(detail);

  if (button.dataset.icon !== iconName) {
    button.dataset.icon = iconName;
    $('svg', button).replaceWith(icon(iconName));
  }
}

/* ---------- Preview ---------- */

const AUDIO_NAMES = { ita: 'italiano', jpn: 'giapponese', eng: 'inglese' };
let previewRequest = 0;

function previewButton(onclick, size = '') {
  return h('button', { class: `button ghost${size ? ` ${size}` : ''}`, type: 'button', onclick }, icon('play'), 'Anteprima');
}

function clock(seconds) {
  const hours = Math.floor(seconds / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  const rest = String(Math.floor(seconds % 60)).padStart(2, '0');
  return hours ? `${hours}:${String(minutes).padStart(2, '0')}:${rest}` : `${minutes}:${rest}`;
}

function previewEpisode() {
  const episodes = Array.isArray(state.episodes) ? state.episodes : [];

  // The first selected episode, or the first of the list
  const episode = episodes.find((item) => state.selected.has(item.id)) || episodes[0];
  if (episode && state.detail) openPreview(state.detail, episode);
}

async function openPreview(title, episode = null) {
  const requestId = ++previewRequest;
  const layer = $('#preview');
  const stage = $('#preview-stage');

  $('#preview-title').textContent = episode ? `${title.name} · Episodio ${episode.number}` : title.name;
  $('#preview-meta').textContent = 'Qualche minuto da metà video, nella stessa qualità del download';
  stage.replaceChildren(h('div', { class: 'preview-wait', role: 'status' },
    h('span', { class: 'preview-spinner', 'aria-hidden': 'true' }),
    h('strong', {}, 'Preparo l’anteprima…'),
    h('span', {}, 'Ci vogliono circa 20 secondi')));
  openLayer(layer);

  const params = new URLSearchParams({ source: title.source || 'sc', id: title.id, type: title.type });
  if (episode) params.set('episode_id', episode.id);

  try {
    const result = await api(`/api/preview?${params}`);
    if (requestId !== previewRequest || !layers.includes(layer)) return;

    // Anime have the audio inside the video: dubbed copies are in italian, the others in japanese with subtitles
    const code = result.language || (isAnime(title) ? (title.dub ? 'ita' : 'jpn') : null);
    const language = AUDIO_NAMES[code] || code;
    $('#preview-meta').textContent = [
      result.quality,
      language ? `Audio ${language}` : null,
      isAnime(title) && code !== 'ita' ? 'sottotitoli in italiano' : null,
      `da ${clock(result.start)} a ${clock(result.start + result.length)} di ${clock(result.total)}`,
    ].filter(Boolean).join(' · ');

    const video = h('video', { src: result.url, controls: true, autoplay: true, playsinline: true, preload: 'auto' });
    stage.replaceChildren(video);
    video.focus({ preventScroll: true });
  } catch (error) {
    if (requestId !== previewRequest || !layers.includes(layer)) return;
    stage.replaceChildren(errorState(error, () => openPreview(title, episode)));
  }
}

function stopPreview() {
  previewRequest += 1;

  // Without its source the video stops asking the file
  const video = $('#preview-stage video');
  if (video) {
    video.pause();
    video.removeAttribute('src');
    video.load();
  }
}

/* ---------- Seasons and episodes ---------- */

function renderSeasonTabs() {
  const container = $('#seasons');
  const detail = state.detail;
  const groups = episodeGroups(detail);
  if (!container) return;

  if (!groups.length) {
    container.replaceChildren(emptyState('film', 'Nessun episodio disponibile', 'Questa serie non ha ancora episodi da scaricare.'));
    return;
  }

  // An anime with less than a hundred episodes has a single block, no tabs are needed
  const tabs = groups.length > 1 || !isAnime(detail)
    ? h('div', { class: 'tabs', role: 'tablist', 'aria-label': isAnime(detail) ? 'Episodi' : 'Stagioni' }, groups.map((group) => h('button', {
      class: 'tab',
      type: 'button',
      role: 'tab',
      dataset: { season: group.key },
      'aria-selected': String(group.key === state.season),
      onclick: () => group.key !== state.season && selectSeason(group.key),
    }, group.label)))
    : null;

  container.replaceChildren(
    h('div', { class: 'seasons-head' }, h('h3', { class: 'section-title' }, 'Episodi'), tabs),
    h('div', { id: 'season-body' }));

  renderSeasonBody();
}

async function selectSeason(key) {
  const detail = state.detail;
  const group = episodeGroups(detail).find((item) => item.key === key);
  const cacheKey = `${keyOf(detail)}:${key}`;

  state.season = key;
  state.selected = new Set();
  state.episodes = seasonCache.get(cacheKey) || null;

  const tabs = $('#seasons .tabs');
  $$('.tab', tabs || document.createElement('div')).forEach((tab) => {
    const selected = tab.dataset.season === key;
    tab.setAttribute('aria-selected', String(selected));

    // Center the selected tab inside the strip
    if (selected) {
      const offset = tab.getBoundingClientRect().left - tabs.getBoundingClientRect().left;
      tabs.scrollBy({ left: offset - (tabs.clientWidth - tab.offsetWidth) / 2, behavior: 'smooth' });
    }
  });

  renderSeasonBody();
  if (state.episodes) return;

  const path = isAnime(detail)
    ? `/api/anime/episodes?id=${detail.id}&start=${group.start}&end=${group.end}`
    : `/api/season?id=${detail.id}&slug=${encodeURIComponent(detail.slug)}&number=${group.number}`;

  try {
    const { episodes } = await api(path);
    seasonCache.set(cacheKey, episodes);
    if (state.detail !== detail || state.season !== key) return;
    state.episodes = episodes;
  } catch (error) {
    if (state.detail !== detail || state.season !== key) return;
    state.episodes = error;
  }

  renderSeasonBody();
}

function renderSeasonBody() {
  const body = $('#season-body');
  if (!body) return;

  if (state.episodes === null) {
    body.replaceChildren(h('div', { class: 'episodes', 'aria-busy': 'true' }, Array.from({ length: 4 }, () => h('div', { class: 'skeleton sk-episode' }))));
  } else if (state.episodes instanceof Error) {
    body.replaceChildren(errorState(state.episodes, () => selectSeason(state.season)));
  } else if (!state.episodes.length) {
    body.replaceChildren(emptyState('film', 'Nessun episodio', 'Questa stagione non ha ancora episodi disponibili.'));
  } else {
    body.replaceChildren(episodesToolbar(), h('div', { class: `episodes${isAnime(state.detail) ? ' compact' : ''}` }, state.episodes.map(episodeRow)));
    updateSelection();
    refreshDetailStates();
  }
}

function episodesToolbar() {
  return h('div', { class: 'toolbar' },
    h('button', { class: 'button ghost small', type: 'button', id: 'select-all', onclick: toggleAllEpisodes }, 'Seleziona tutti'),
    h('button', { class: 'button primary small', type: 'button', id: 'download-selected', onclick: queueSelectedEpisodes }, icon('download'), h('span', {}, 'Scarica')),
    previewButton(previewEpisode, 'small'),
    h('span', { class: 'toolbar-count', id: 'selection-count', 'aria-live': 'polite' }));
}

function episodeRow(episode, index) {
  const input = h('input', { type: 'checkbox', 'aria-label': `Episodio ${episode.number}: ${episode.name}` });

  input.addEventListener('change', () => {
    if (input.checked) state.selected.add(episode.id);
    else state.selected.delete(episode.id);
    updateSelection();
  });

  // Episodes of anime have no image and no plot, they are small boxes in a grid
  const compact = isAnime(state.detail);

  return h('label', { class: 'episode', style: `--i:${index}`, dataset: { episodeId: episode.id } },
    input,
    compact ? null : h('span', { class: 'episode-thumb', style: `--hue:${hue(episode.id)}` },
      episode.cover ? image(episode.cover) : null,
      episode.duration ? h('span', { class: 'episode-duration' }, `${episode.duration} min`) : null),
    h('span', { class: 'episode-info' },
      h('span', { class: 'episode-title' },
        compact ? null : h('span', { class: 'episode-number' }, episode.number),
        h('span', { class: 'episode-name' }, episode.name),
        h('span', { class: 'episode-state' })),
      episode.plot ? h('span', { class: 'episode-plot' }, episode.plot) : null),
    h('span', { class: 'check', 'aria-hidden': 'true' }, icon('check')));
}

function updateSelection() {
  const episodes = Array.isArray(state.episodes) ? state.episodes : [];
  const count = state.selected.size;

  $$('#season-body .episode').forEach((row) => {
    const selected = state.selected.has(Number(row.dataset.episodeId));
    row.classList.toggle('selected', selected);
    $('input', row).checked = selected;
  });

  const selectAll = $('#select-all');
  if (selectAll) selectAll.textContent = count && count === episodes.length ? 'Deseleziona tutti' : 'Seleziona tutti';

  const counter = $('#selection-count');
  if (counter) counter.textContent = count ? `${count} di ${episodes.length} selezionati` : plural(episodes.length, 'episodio', 'episodi');

  const button = $('#download-selected');
  if (button) {
    button.disabled = !count;
    $('span', button).textContent = count ? `Scarica ${plural(count, 'episodio', 'episodi')}` : 'Scarica';
  }
}

function toggleAllEpisodes() {
  const episodes = Array.isArray(state.episodes) ? state.episodes : [];
  state.selected = state.selected.size === episodes.length ? new Set() : new Set(episodes.map((episode) => episode.id));
  updateSelection();
}

function queueSelectedEpisodes() {
  const detail = state.detail;
  const items = state.episodes
    .filter((episode) => state.selected.has(episode.id))
    .map((episode) => ({
      id: detail.id,
      slug: detail.slug,
      name: detail.name,
      source: detail.source || 'sc',
      year: detail.year,
      type: 'tv',
      poster: detail.poster,
      season: isAnime(detail) ? null : Number(state.season),
      episode_id: episode.id,
      episode_number: episode.number,
      episode_name: episode.name,
    }));

  if (!items.length) return;

  state.selected = new Set();
  updateSelection();
  queueDownloads(items);
}

function refreshDetailStates() {
  const detail = state.detail;
  if (!detail || !layers.includes($('#detail'))) return;

  const button = $('#movie-button');
  if (button) updateMovieButton(button, detail);

  $$('#season-body .episode').forEach((row) => {
    const job = findJob(detail, Number(row.dataset.episodeId));
    const chip = $('.episode-state', row);
    const status = job?.status || '';

    chip.className = `episode-state ${status}`;
    chip.textContent = {
      queued: 'In coda',
      waiting: 'Riprovo…',
      running: job?.cancel ? 'Annullamento…' : job?.waiting === 'offline' ? 'In pausa' : job?.stage ? `${Math.floor(jobPercent(job))}%` : 'Avvio…',
      done: job?.warning ? 'Sul PC' : job?.remote ? 'Sul NAS' : 'Scaricato',
      error: 'Errore',
    }[status] || '';
  });
}

/* ---------- Downloads ---------- */

async function queueMovie(title) {
  let movie = title;

  // Anime from lists of related titles come without slug, the page of the anime has it
  if (!title.slug) {
    try {
      movie = await getDetail(title);
    } catch (error) {
      toast(error.message, 'error');
      return;
    }
  }

  queueDownloads([{ id: movie.id, slug: movie.slug, name: movie.name, source: movie.source || 'sc', year: movie.year, type: 'movie', poster: movie.poster }]);
}

async function queueDownloads(items) {
  try {
    const { added, jobs } = await api('/api/downloads', { method: 'POST', body: { items } });
    setJobs(jobs);

    if (!added.length) {
      toast(items.length === 1 ? 'È già nella coda dei download' : 'Questi episodi sono già in coda', 'info', { action: 'Apri', onAction: openDownloads });
    } else {
      toast(added.length === 1 ? `${jobName(added[0])} aggiunto alla coda` : `${added.length} episodi aggiunti alla coda`, 'success', { action: 'Apri', onAction: openDownloads });
    }

    pollDownloads();
  } catch (error) {
    toast(error.message, 'error');
  }
}

function openDownloads() {
  openLayer($('#downloads'));
  $('#downloads .drawer-head .icon-button').focus({ preventScroll: true });
}

async function pollDownloads() {
  clearTimeout(state.pollTimer);

  try {
    const { jobs } = await api('/api/downloads');
    setServerReachable(true);
    setJobs(jobs);
  } catch {
    // Server not reachable: the page stays, it tries again by itself
    setServerReachable(false);
  }

  const active = state.jobs.some((job) => job.status === 'queued' || job.status === 'running' || job.status === 'waiting');
  state.pollTimer = setTimeout(pollDownloads, state.serverDown ? 3000 : active ? 800 : 3000);
}

/* ---------- Connection ---------- */

function setServerReachable(reachable) {
  if (state.serverDown === !reachable) return;
  state.serverDown = !reachable;

  if (reachable && state.serverWasDown) toast('Il programma risponde di nuovo', 'success');
  if (!reachable) state.serverWasDown = true;
  renderConnectionBanner();
}

function renderConnectionBanner() {
  const banner = $('#connection-banner');
  let text = '';

  if (state.serverDown) {
    text = 'Il programma non risponde. Se l’hai chiuso riaprilo da SC Downloader: i download ripartono da dove erano. Riprovo da solo…';
  } else if (!navigator.onLine) {
    text = 'Connessione a internet assente: i download sono in pausa e riprendono da soli quando torna.';
  }

  banner.hidden = !text;
  $('.connection-text', banner).textContent = text;
}

function setJobs(jobs) {
  const previous = new Map(state.jobs.map((job) => [job.id, job.status]));
  state.jobs = jobs;

  for (const job of jobs) {
    const before = previous.get(job.id);
    if (!before || before === job.status) continue;

    // A new download changes what is recommended
    if (job.status === 'done') refreshRecommendations();

    if (job.status === 'done' && job.warning) toast(`${jobName(job)}: NAS non raggiungibile, il file resta sul PC`, 'warning', { action: 'Apri', onAction: openDownloads });
    else if (job.status === 'done' && job.remote) toast(`Caricato sul NAS: ${jobName(job)}`, 'success');
    else if (job.status === 'done') toast(`Download completato: ${jobName(job)}`, 'success', { action: 'Mostra', onAction: () => openFolder(job.id) });
    if (job.status === 'error') toast(`Download non riuscito: ${jobName(job)}`, 'error', { action: 'Dettagli', onAction: openDownloads });
    if (job.status === 'waiting') toast(`${jobName(job)}: problema temporaneo, riprovo da solo tra poco`, 'warning', { action: 'Dettagli', onAction: openDownloads });
    if (job.status === 'cancelled') toast(`Download annullato: ${jobName(job)}`, 'info');
  }

  renderJobs();
}

function findJob(title, episodeId = null) {
  const priority = { running: 0, queued: 1, waiting: 1, done: 2, error: 3, cancelled: 4 };
  const source = title.source || 'sc';

  return state.jobs
    .filter((job) => (job.source || 'sc') === source && job.title_id === title.id && (job.episode_id ?? null) === episodeId)
    .sort((a, b) => priority[a.status] - priority[b.status] || b.id - a.id)[0] || null;
}

function jobPercent(job) {
  if (!job) return 0;
  if (job.status === 'done') return 100;

  const stage = STAGES[job.stage];
  if (!stage) return 0;

  const ratio = job.total ? Math.min(job.done / job.total, 1) : 0;
  return stage.from + (stage.to - stage.from) * ratio;
}

function estimateSeconds(job, percent) {
  const now = Date.now();
  const sample = state.eta.get(job.id);

  if (!sample || percent < sample.percent) {
    state.eta.set(job.id, { time: now, percent, rate: 0 });
    return null;
  }

  const elapsed = (now - sample.time) / 1000;
  if (elapsed >= 2 && percent > sample.percent) {
    const rate = (percent - sample.percent) / elapsed;
    sample.rate = sample.rate ? sample.rate * 0.6 + rate * 0.4 : rate;
    sample.time = now;
    sample.percent = percent;
  }

  return sample.rate ? (100 - percent) / sample.rate : null;
}

function formatDelay(seconds) {
  if (seconds < 60) return `${seconds} s`;
  return `${Math.ceil(seconds / 60)} min`;
}

function formatEta(seconds) {
  if (!seconds || !Number.isFinite(seconds)) return '';
  if (seconds < 60) return 'meno di 1 min';

  const minutes = Math.round(seconds / 60);
  if (minutes < 60) return `~${minutes} min`;
  return `~${Math.floor(minutes / 60)} h ${minutes % 60} min`;
}

function renderJobs() {
  const list = $('#jobs');
  const ids = new Set(state.jobs.map((job) => job.id));

  for (const [id, node] of jobNodes) {
    if (ids.has(id)) continue;
    node.remove();
    jobNodes.delete(id);
    state.eta.delete(id);
  }

  const empty = $('.empty', list);
  if (!state.jobs.length) {
    if (!empty) list.replaceChildren(emptyState('download', 'Nessun download', 'Scegli un film o degli episodi: li vedrai qui mentre vengono scaricati.'));
  } else if (empty) {
    empty.remove();
  }

  // Running first, then queue in order, then finished from the newest
  const order = { running: 0, queued: 1, waiting: 1, error: 2, done: 2, cancelled: 2 };
  const jobs = [...state.jobs].sort((a, b) => order[a.status] - order[b.status] || (a.status === 'queued' ? a.id - b.id : b.id - a.id));

  jobs.forEach((job, index) => {
    let node = jobNodes.get(job.id);

    if (!node) {
      node = createJobNode(job);
      jobNodes.set(job.id, node);
    }

    updateJobNode(node, job);
    if (list.children[index] !== node) list.insertBefore(node, list.children[index] || null);
  });

  renderDownloadsSummary();
  renderDownloadsButton();
  refreshDetailStates();
}

function createJobNode(job) {
  return h('article', { class: 'job' },
    posterNode({ id: job.title_id, name: job.name, poster: job.poster }, 'poster job-poster'),
    h('div', { class: 'job-main' },
      h('div', { class: 'job-title', title: job.name }, job.name),
      h('div', { class: 'job-sub' }, jobSubtitle(job)),
      h('div', { class: 'progress', role: 'progressbar', 'aria-valuemin': '0', 'aria-valuemax': '100', 'aria-label': `Avanzamento di ${jobName(job)}` },
        h('span', { class: 'progress-bar' })),
      h('div', { class: 'job-status' }, h('span', { class: 'job-state' }), h('span', { class: 'job-eta' }))),
    h('div', { class: 'job-actions' }));
}

function updateJobNode(node, job) {
  const percent = jobPercent(job);
  const stage = STAGES[job.stage];
  let label = '';
  let eta = '';

  const offline = job.status === 'running' && job.waiting === 'offline';
  node.className = `job ${job.status}${job.warning ? ' warning' : ''}${offline ? ' offline' : ''}${job.status === 'running' && stage && !job.total ? ' indeterminate' : ''}`;
  $('.progress', node).setAttribute('aria-valuenow', String(Math.round(percent)));
  $('.progress-bar', node).style.width = `${job.status === 'queued' || job.status === 'waiting' ? 0 : percent}%`;

  if (job.status === 'queued') {
    label = job.attempt ? `In coda · tentativo ${job.attempt + 1}` : 'In coda';
  } else if (job.status === 'waiting') {
    label = `Riprovo ${job.retry_in ? `tra ${formatDelay(job.retry_in)}` : 'appena torna la connessione'}${job.error ? ` · ${job.error}` : ''}`;
  } else if (job.status === 'running' && job.cancel) {
    label = 'Annullamento…';
  } else if (offline) {
    label = `Connessione assente · in pausa al ${Math.floor(percent)}%`;
  } else if (job.status === 'running') {
    label = stage ? `${stage.label} · ${Math.floor(percent)}%` : 'Preparazione…';
    eta = stage ? formatEta(estimateSeconds(job, percent)) : '';
  } else if (job.status === 'cancelled') {
    label = 'Annullato';
  } else if (job.status === 'done') {
    label = job.warning ? 'Salvato sul PC' : job.remote ? 'Sul NAS' : 'Completato';
  } else if (job.status === 'error') {
    label = job.error || 'Download non riuscito';
  }

  const stateNode = $('.job-state', node);
  stateNode.textContent = label;
  stateNode.title = job.status === 'waiting' ? `${job.error || ''}\n${label}` : job.warning || job.remote || label;
  $('.job-eta', node).textContent = eta;

  const actions = $('.job-actions', node);
  const key = `${job.status}:${job.can_upload ? 1 : 0}:${job.output ? 1 : 0}:${job.cancel ? 1 : 0}`;

  if (actions.dataset.key !== key) {
    actions.dataset.key = key;
    actions.replaceChildren(...jobActions(job));
  }
}

function jobActions(job) {
  const button = (iconName, label, onclick) => h('button', { class: 'icon-button small', type: 'button', title: label, 'aria-label': label, onclick }, icon(iconName));
  const actions = [];

  if (job.status === 'done' && job.output) actions.push(button('folder', 'Mostra file', () => openFolder(job.id)));
  if (job.can_upload) actions.push(button('upload', 'Riprova il caricamento sul NAS', () => retryUpload(job.id)));
  if (job.status === 'error' && !job.can_upload) actions.push(button('retry', 'Riprova il download', () => retryJob(job)));
  if (job.status === 'running' && !job.cancel) actions.push(confirmButton('Annulla il download', () => cancelJob(job.id)));
  if (job.status !== 'running') actions.push(button('close', job.status === 'queued' || job.status === 'waiting' ? 'Annulla' : 'Rimuovi dalla lista', () => removeJob(job.id)));

  return actions;
}

// Stopping a long download by mistake is costly: the first click only asks for confirmation
function confirmButton(label, onconfirm) {
  const node = h('button', { class: 'icon-button small confirmable', type: 'button', title: label, 'aria-label': label },
    icon('close'),
    h('span', { class: 'confirm-text' }, 'Annullare?'));
  let timer = null;

  node.addEventListener('click', () => {
    if (node.classList.contains('confirm')) {
      clearTimeout(timer);
      node.disabled = true;
      onconfirm();
      return;
    }

    node.classList.add('confirm');
    node.setAttribute('aria-label', 'Clicca di nuovo per annullare il download');
    timer = setTimeout(() => {
      node.classList.remove('confirm');
      node.setAttribute('aria-label', label);
    }, 3500);
  });

  return node;
}

async function cancelJob(id) {
  try {
    const { jobs } = await api('/api/downloads/cancel', { method: 'POST', body: { id } });
    setJobs(jobs);
  } catch (error) {
    toast(error.message, 'error');
  }
}

function renderDownloadsSummary() {
  const count = (status) => state.jobs.filter((job) => job.status === status).length;
  const parts = [
    count('running') ? 'Download in corso' : null,
    count('queued') ? `${count('queued')} in coda` : null,
    count('waiting') ? `${count('waiting')} in attesa di riprovare` : null,
    count('done') ? plural(count('done'), 'completato', 'completati') : null,
    count('error') ? plural(count('error'), 'non riuscito', 'non riusciti') : null,
    count('cancelled') ? plural(count('cancelled'), 'annullato', 'annullati') : null,
  ].filter(Boolean);

  $('#downloads-summary').textContent = parts.join(' · ') || 'Nessun download';
  $('[data-action="clear-downloads"]').disabled = !(count('done') + count('error') + count('cancelled'));
}

function renderDownloadsButton() {
  const running = state.jobs.find((job) => job.status === 'running');
  const active = state.jobs.filter((job) => job.status === 'queued' || job.status === 'running' || job.status === 'waiting').length;
  const percent = running ? jobPercent(running) : 0;
  const button = $('#downloads-button');
  const badge = $('#downloads-badge');

  button.classList.toggle('active', Boolean(running));
  button.setAttribute('aria-label', active ? `Download, ${active} attivi` : 'Download');
  $('#ring-value').style.strokeDashoffset = String(113.1 * (1 - percent / 100));

  badge.hidden = !active;
  badge.textContent = String(active);

  document.title = running ? `${Math.floor(percent)}% · SC Downloader` : 'SC Downloader';
}

async function removeJob(id) {
  try {
    const { jobs } = await api('/api/downloads/remove', { method: 'POST', body: { id } });
    setJobs(jobs);
  } catch (error) {
    toast(error.message, 'error');
  }
}

async function retryUpload(id) {
  try {
    const { jobs } = await api('/api/downloads/upload', { method: 'POST', body: { id } });
    setJobs(jobs);
  } catch (error) {
    toast(error.message, 'error');
  }
}

async function retryJob(job) {
  await removeJob(job.id);
  queueDownloads([{
    id: job.title_id,
    slug: job.slug,
    name: job.name,
    source: job.source,
    year: job.year,
    type: job.type,
    poster: job.poster,
    season: job.season,
    episode_id: job.episode_id,
    episode_number: job.episode_number,
    episode_name: job.episode_name,
  }]);
}

async function clearDownloads() {
  try {
    const { jobs } = await api('/api/downloads/clear', { method: 'POST', body: {} });
    setJobs(jobs);
  } catch (error) {
    toast(error.message, 'error');
  }
}

async function openFolder(id) {
  // On the phone the files are on the pc or on the nas
  if (state.status?.remote_client) {
    toast('Il file è sul PC: aprilo da lì o dal NAS', 'info');
    return;
  }

  try {
    await api('/api/open', { method: 'POST', body: id ? { id } : {} });
  } catch (error) {
    toast(error.message, 'error');
  }
}

/* ---------- Toasts ---------- */

function toast(message, type = 'info', { action, onAction } = {}) {
  const container = $('#toasts');
  const node = h('div', { class: `toast ${type}`, role: type === 'error' ? 'alert' : 'status' },
    h('span', { class: 'toast-icon' }, icon({ success: 'check', error: 'alert', warning: 'alert' }[type] || 'info')),
    h('span', { class: 'toast-text' }, message));

  const dismiss = () => {
    node.classList.remove('show');
    setTimeout(() => node.remove(), 400);
  };

  if (action) {
    node.append(h('button', { class: 'toast-action', type: 'button', onclick: () => { onAction(); dismiss(); } }, action));
  }

  container.append(node);
  while (container.children.length > 4) container.firstElementChild.remove();

  requestAnimationFrame(() => requestAnimationFrame(() => node.classList.add('show')));
  setTimeout(dismiss, type === 'error' ? 7000 : 4500);
}

/* ---------- Start ---------- */

function isTyping(target) {
  return target instanceof HTMLInputElement || target instanceof HTMLTextAreaElement || target.isContentEditable;
}

function bindEvents() {
  window.addEventListener('online', renderConnectionBanner);
  window.addEventListener('offline', renderConnectionBanner);

  $('#search-form').addEventListener('submit', (event) => {
    event.preventDefault();
    const query = searchInput.value.trim();
    if (query) runSearch(query);
  });

  searchInput.addEventListener('input', onSearchInput);
  $('#search-clear').addEventListener('click', () => {
    goHome();
    searchInput.focus();
  });

  $('#settings-form').addEventListener('submit', submitDomain);
  $('#nas-form').addEventListener('submit', saveNas);
  $('#nas-test').addEventListener('click', testNas);
  $('#remote-enabled').addEventListener('change', (event) => setRemote(event.target.checked));
  $('#remote-key').addEventListener('click', newRemoteKey);
  $$('.settings-tabs .tab').forEach((tab) => tab.addEventListener('click', () => showSettingsPanel(tab.dataset.panel)));
  $$('#category-switch .category').forEach((button) => button.addEventListener('click', () => setCategory(button.dataset.category)));
  $('#preview').addEventListener('layerclose', stopPreview);
  $('#detail').addEventListener('layerclose', () => {
    state.detailId += 1;
    state.detail = null;
  });

  document.addEventListener('click', (event) => {
    const closer = event.target.closest('[data-close]');
    if (closer) {
      closeLayer(closer.closest('.layer'));
      return;
    }

    const action = event.target.closest('[data-action]');
    if (!action) return;
    event.preventDefault();

    switch (action.dataset.action) {
      case 'home':
        goHome();
        window.scrollTo({ top: 0, behavior: 'smooth' });
        break;
      case 'settings':
        openSettings();
        break;
      case 'downloads':
        openDownloads();
        break;
      case 'open-folder':
        openFolder();
        break;
      case 'clear-downloads':
        clearDownloads();
        break;
      default:
        break;
    }
  });

  document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape' && layers.length) {
      event.preventDefault();
      closeLayer(layers[layers.length - 1]);
    } else if (event.key === 'Escape' && document.activeElement === searchInput) {
      goHome();
      searchInput.blur();
    } else if (event.key === '/' && !layers.length && !isTyping(event.target)) {
      event.preventDefault();
      searchInput.focus();
      searchInput.select();
    }
  });

  // Closing the window stops the program, unless a download is running
  window.addEventListener('pagehide', () => {
    // The phone closing its page does not close the program on the pc
    if (state.status?.remote_client) return;

    try {
      fetch('/api/close', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: '{}', keepalive: true });
    } catch {
      // Nothing to do, the program stays open
    }
  });

  window.addEventListener('scroll', updateTopbar, { passive: true });
  window.addEventListener('resize', () => rowUpdaters.forEach((update) => update()));
  document.addEventListener('visibilitychange', syncHero);
}

async function init() {
  bindEvents();
  renderCategory();
  renderJobs();
  pollDownloads();

  const status = await loadStatus();
  loadHome();

  if (!status.connected && state.category === 'sc' && !status.remote_client) openSettings({ welcome: !status.domain });

  if (status.ffmpeg === false) toast('FFmpeg non trovato: i download non funzioneranno finché non lo installi', 'error');
}

init();
