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
  magnet: '<path d="M5.5 4.5h4v7a2.5 2.5 0 0 0 5 0v-7h4v7a6.5 6.5 0 0 1-13 0z"/><path d="M5.5 8h4m5 0h4"/>',
  pause: '<path d="M9 6.5v11M15 6.5v11"/>',
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
  save: { label: 'Salvataggio nella cartella', from: 88, to: 88 },
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
  progress: { entries: [], continue: {} },
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
  $('.status-label', chip).textContent = status?.connected ? status.domain : status?.domain ? 'Non connesso' : 'Configura';
  chip.title = status?.connected ? `Connesso a ${status.site}` : status?.error || 'Configura il sito';
  chip.setAttribute('aria-label', chip.title);

  document.body.classList.toggle('remote-client', Boolean(status?.remote_client));
}

function openSettings({ welcome = false, panel = 'site' } = {}) {
  const { status } = state;
  const error = $('#settings-error');

  $('#settings-title').textContent = welcome ? 'Benvenuto in SC Downloader' : 'Connessione al sito';
  $('#settings-text').textContent = welcome
    ? "Per iniziare inserisci l'indirizzo attuale del sito."
    : "Il sito cambia spesso indirizzo: se smette di funzionare, inserisci quello nuovo. Puoi cambiare anche il nome, non solo l'estensione.";
  $('#domain-input').value = status?.domain || '';
  error.textContent = status?.connected ? '' : status?.error || '';
  error.hidden = !error.textContent;

  $('#settings-form .notice')?.remove();
  if (status?.ffmpeg === false) {
    $('#settings-submit').before(h('div', { class: 'notice' }, icon('alert'), 'FFmpeg non è installato: puoi cercare, ma i download non funzioneranno.'));
  }

  showSettingsPanel(panel);
  openLayer($('#settings'));
  setTimeout(() => ({ videos: $('#videos-path'), nas: $('#nas-host'), torrent: $('#tc-jackett-url') }[panel] || $('#domain-input')).focus(), 80);
}

function showSettingsPanel(name) {
  $$('.settings-tabs .tab').forEach((tab) => tab.setAttribute('aria-selected', String(tab.dataset.panel === name)));
  $('#settings-form').hidden = name !== 'site';
  $('#videos-form').hidden = name !== 'videos';
  $('#nas-form').hidden = name !== 'nas';
  $('#torrent-config-form').hidden = name !== 'torrent';
  $('#remote-panel').hidden = name !== 'remote';

  if (name === 'videos') loadVideos();
  if (name === 'nas') loadNas();
  if (name === 'torrent') loadTorrentConfig();
  if (name === 'remote') loadRemote();
}

/* ---------- Folder of the downloads ---------- */

function renderVideos(config) {
  $('#videos-path').value = config.path;
  $('#videos-path').placeholder = `Vuoto: ${config.default}`;
  $('#videos-note').replaceChildren(
    'Ora i video vanno in ', h('code', {}, config.folder), '. ',
    config.docker
      ? 'In Docker vale un percorso del container: per usare una cartella del PC collegala in docker-compose.yml. '
      : '',
    'Se il NAS è attivo, qui il file resta solo fino al caricamento.');
}

async function loadVideos() {
  $('#videos-result').replaceChildren();

  try {
    renderVideos(await api('/api/videos'));
  } catch (error) {
    $('#videos-result').replaceChildren(h('div', { class: 'result bad' }, h('strong', {}, error.message)));
  }
}

async function saveVideos(event) {
  event.preventDefault();

  const button = $('#videos-save');
  button.classList.add('loading');
  button.disabled = true;
  $('#videos-result').replaceChildren();

  try {
    renderVideos(await api('/api/videos', { method: 'POST', body: { path: $('#videos-path').value.trim() } }));
    toast('Cartella dei download salvata', 'success');
  } catch (error) {
    $('#videos-result').replaceChildren(h('div', { class: 'result bad' }, h('strong', {}, error.message)));
  } finally {
    button.classList.remove('loading');
    button.disabled = false;
  }
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
  $('#remote-box').hidden = !(info.running && info.addresses?.length);
  $('#remote-result').replaceChildren();

  if (!info.running) {
    $('#remote-result').replaceChildren(h('div', { class: 'result bad' }, h('strong', {}, 'Accesso dalla rete non attivo: riavvia il programma')));
  } else if (!info.addresses?.length) {
    $('#remote-result').replaceChildren(h('div', { class: 'result bad' }, h('strong', {}, 'Il PC non sembra collegato a una rete di casa')));
  }

  // The svg is made by the program on this pc
  $('#remote-qr').innerHTML = info.qr || '';
  $('#remote-address').textContent = info.addresses?.[0] || '';
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
    loadStatus();

    if (state.nas.password_error) {
      showNasResult(false, state.nas.password_error);
    } else if (state.nas.enabled && !state.nas.password_saved) {
      showNasResult(false, 'Impostazioni salvate, ma manca la password: senza i file restano sul PC');
    } else {
      $('#nas-result').replaceChildren();
      toast(state.nas.enabled ? 'Caricamento sul NAS attivo' : 'Impostazioni del NAS salvate', 'success');
    }
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
  // Accept also a pasted address like https://site.academy/it, only the extension is still fine
  const domain = input.value.trim()
    .replace(/^https?:\/\//i, '')
    .replace(/^www\./i, '')
    .replace(/[/?#].*$/, '')
    .replace(/^\.+|\.+$/g, '');

  if (!domain) {
    error.textContent = "Inserisci l'indirizzo, per esempio streamingcommunityz.shiksha";
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
      state.status?.error || "Inserisci l'indirizzo attuale del sito per vedere i titoli del momento e cercare film e serie TV.",
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

  delete $('#rows').dataset.ready;
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
  delete $('#rows').dataset.ready;
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
  $('#rows').dataset.ready = state.category;
  loadRecommendations();
  renderContinueRow();

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
  const track = h('div', { class: 'row-track' }, slider.nodes || slider.titles.map((title, index) => card(title, { index, rank: ranked ? index + 1 : null })));
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

/* ---------- Continue watching ---------- */

function titleOf(entry) {
  return {
    id: entry.id,
    slug: entry.slug,
    name: entry.name,
    source: entry.source || 'sc',
    type: entry.type,
    year: entry.year,
    poster: entry.poster,
    backdrop: entry.backdrop,
    dub: entry.dub,
  };
}

/** Where the video is: minutes left, or the next episode */
function continueLabel(entry) {
  const code = entry.episode_id == null ? null : entry.source === 'anime' ? `Ep. ${entry.episode_number}` : `S${entry.season || 1} E${entry.episode_number}`;

  if (!code) {
    const left = minutesLeft(entry);
    return left[0].toUpperCase() + left.slice(1);
  }

  return entry.up_next ? `Prossimo: ${code}` : `${code} · ${minutesLeft(entry)}`;
}

function continueCard(entry, index) {
  const title = titleOf(entry);
  const label = continueLabel(entry);
  const poster = posterNode(title);

  poster.append(...[
    h('span', { class: 'poster-hover', 'aria-hidden': 'true' }, h('span', { class: 'poster-action' }, icon('play'))),
    entry.up_next ? null : watchBar(entry),
  ].filter(Boolean));

  return h('div', { class: 'card-wrap', style: `--i:${index}` },
    h('button', {
      class: 'card',
      type: 'button',
      style: `--i:${index}`,
      title: title.name,
      'aria-label': `Riprendi ${title.name}, ${label}`,
      onclick: () => resumeEntry(entry),
    },
      poster,
      h('span', { class: 'card-body' },
        h('span', { class: 'card-title' }, title.name),
        h('span', { class: 'card-reason' }, label))),
    h('button', {
      class: 'card-dismiss',
      type: 'button',
      title: 'Togli da Continua a guardare',
      'aria-label': `Togli ${title.name} da Continua a guardare`,
      onclick: () => sendProgress('/api/progress/dismiss', { source: title.source, id: title.id }),
    }, icon('close')));
}

/** The first row of the home: the films and the episodes stopped in the middle, and the next episodes */
function renderContinueRow() {
  const rows = $('#rows');
  const old = $('#continue');
  const entries = state.progress.continue?.[state.category] || [];

  // While a video plays the row waits: it changes every few seconds and nobody sees it
  if (layers.includes($('#player'))) return;

  // Only above the rows of the home, not on its messages
  if (!entries.length || rows.dataset.ready !== state.category) {
    old?.remove();
    return;
  }

  const row = renderRow({ name: 'continue', label: 'Continua a guardare', titles: [], nodes: entries.map(continueCard) });
  row.id = 'continue';

  if (old) old.replaceWith(row);
  else rows.prepend(row);
}

/** Start again a video of the row, with the episodes after it so the player goes on by itself */
async function resumeEntry(entry) {
  const title = titleOf(entry);
  if (entry.episode_id == null) {
    openPlayer(title);
    return;
  }

  const episode = { id: entry.episode_id, number: entry.episode_number, name: entry.episode_name || `Episodio ${entry.episode_number}` };
  let queue = null;

  try {
    if (isAnime(title)) {
      const start = Math.floor(((parseInt(entry.episode_number, 10) || 1) - 1) / 100) * 100 + 1;
      const key = `${keyOf(title)}:resume:${start}`;
      queue = seasonCache.get(key) || (await api(`/api/anime/episodes?id=${title.id}&start=${start}&end=${start + 99}`)).episodes;
      seasonCache.set(key, queue);
    } else {
      const key = `${keyOf(title)}:${entry.season || 1}`;
      queue = seasonCache.get(key) || (await api(`/api/season?id=${title.id}&slug=${encodeURIComponent(title.slug)}&number=${entry.season || 1}`)).episodes;
      seasonCache.set(key, queue);
    }
  } catch {
    // Without the list only this episode is played
    queue = null;
  }

  openPlayer(title, queue?.find((item) => item.id === episode.id) || episode, 0, { queue, season: entry.season ?? null });
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
  $('#torrent-view').hidden = name !== 'torrent';
  $('#torrent-button').setAttribute('aria-pressed', String(name === 'torrent'));

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
  $('#topbar').classList.toggle('scrolled', window.scrollY > 30 || $('#home-view').hidden);
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
  // The season of the last episode watched, so going on is one click
  if (detail.type === 'tv' && groups.length) selectSeason(lastGroup(detail, groups) || groups[0].key);
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

  // A film stopped in the middle starts again from there
  const watchMovie = detail.type === 'tv' ? null : watchButton(() => openPlayer(detail), '', 'movie-watch-button');
  const watchNote = detail.type === 'tv' ? null : h('div', { class: 'movie-watch', id: 'movie-watch' });
  if (watchMovie) fillMovieWatch(watchMovie, watchNote, detail);

  return h('div', { class: 'detail-body', id: 'detail-body' },
    h('div', { class: 'detail-grid' },
      h('div', {},
        plot,
        more,
        detail.type === 'tv' ? null : h('div', { class: 'detail-actions' }, movieButton(detail), watchMovie),
        watchNote),
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

/* ---------- Player ---------- */

const AUDIO_NAMES = { ita: 'italiano', jpn: 'giapponese', eng: 'inglese' };
let playerRequest = 0;
let hlsPlayer = null;
let hlsLibrary = null;

function watchButton(onclick, size = '', id = null) {
  return h('button', { class: `button ghost${size ? ` ${size}` : ''}`, type: 'button', id, onclick }, icon('play'), h('span', {}, 'Guarda'));
}

/** Watch or go on with a film, with where it was stopped under the buttons */
function fillMovieWatch(button, note, detail) {
  const entry = progressFor(detail);
  const resume = canResume(entry);

  $('span', button).textContent = resume ? 'Riprendi' : 'Guarda';
  if (resume) {
    note.replaceChildren(watchBar(entry), h('p', {}, `Interrotto a ${clock(entry.position)} di ${clock(entry.duration)} · ${minutesLeft(entry)}`));
  } else if (entry?.finished) {
    note.replaceChildren(h('p', { class: 'seen' }, 'Già visto'));
  } else {
    note.replaceChildren();
  }
}

function clock(seconds) {
  const hours = Math.floor(seconds / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  const rest = String(Math.floor(seconds % 60)).padStart(2, '0');
  return hours ? `${hours}:${String(minutes).padStart(2, '0')}:${rest}` : `${minutes}:${rest}`;
}

/* ---------- Where the videos have been stopped ---------- */

const MIN_RESUME = 10;          // Seconds: before this the video starts again from the beginning
const SAVE_INTERVAL = 5000;     // A computer turned off loses a few seconds at most
let watching = null;

function canResume(entry) {
  return Boolean(entry) && !entry.finished && (entry.position || 0) >= MIN_RESUME;
}

function sameTitle(entry, title) {
  return (entry.source || 'sc') === (title.source || 'sc') && entry.id === title.id;
}

function progressFor(title, episodeId = null) {
  return state.progress.entries.find((entry) => sameTitle(entry, title) && (entry.episode_id ?? null) === episodeId) || null;
}

function lastWatched(title) {
  return state.progress.entries.filter((entry) => sameTitle(entry, title)).sort((a, b) => b.updated_at - a.updated_at)[0] || null;
}

function watchFraction(entry) {
  return entry?.duration ? Math.min(1, entry.position / entry.duration) : 0;
}

function minutesLeft(entry) {
  return `mancano ${Math.max(1, Math.round(((entry.duration || 0) - (entry.position || 0)) / 60))} min`;
}

function watchBar(entry) {
  return h('span', { class: 'watch-bar', 'aria-hidden': 'true' }, h('span', { style: `width:${(watchFraction(entry) * 100).toFixed(1)}%` }));
}

function setProgress(view) {
  state.progress = { entries: view.entries || [], continue: view.continue || {} };
  renderContinueRow();
  refreshDetailStates();
  if ($('#watch-episode')) updateSelection();
}

async function loadProgress() {
  try {
    setProgress(await api('/api/progress'));
  } catch {
    // The app works also without the positions
  }
}

async function sendProgress(path, body) {
  // Keepalive: the position arrives also when the window is closing
  try {
    const response = await fetch(path, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body), keepalive: true });
    if (response.ok) setProgress(await response.json());
  } catch {
    // The next save tries again
  }
}

function watchItem(title, episode, season) {
  return {
    source: title.source || 'sc',
    id: title.id,
    slug: title.slug,
    name: title.name,
    type: title.type,
    year: title.year,
    poster: title.poster,
    backdrop: title.backdrop,
    dub: title.dub,
    season: isAnime(title) ? null : season ?? null,
    episode_id: episode?.id ?? null,
    episode_number: episode?.number ?? null,
    episode_name: episode?.name ?? null,
  };
}

/** Remember where the video is, at the end the episode is seen and the next one goes in the home */
function saveWatching({ ended = false } = {}) {
  const current = watching;
  const video = current?.video;
  if (!video || !Number.isFinite(video.duration) || video.duration <= 0) return;

  // Just started: the position saved before stays, an accidental open does not lose it
  const position = ended ? video.duration : video.currentTime;
  if (position < 5) return;

  current.savedAt = Date.now();
  const { next } = current;
  sendProgress('/api/progress', {
    item: watchItem(current.title, current.episode, current.season),
    position,
    duration: video.duration,
    next: next ? { episode_id: next.id, episode_number: next.number, episode_name: next.name } : null,
  });
}

/** The video went on from where it was stopped: a few seconds to start it again from the beginning */
function resumeNote(video, position) {
  const note = h('div', { class: 'player-resume', role: 'status' },
    h('span', {}, `Ripreso da ${clock(position)}`),
    h('button', {
      class: 'button glass small',
      type: 'button',
      onclick: () => {
        video.currentTime = 0;
        note.remove();
      },
    }, icon('retry'), 'Ricomincia'));

  setTimeout(() => note.classList.add('leaving'), 8000);
  setTimeout(() => note.remove(), 8600);
  return note;
}

/** The episode to go on with in the season open: the one stopped in the middle, or the one after the last seen */
function continueEpisode() {
  const episodes = Array.isArray(state.episodes) ? state.episodes : [];
  if (!state.detail || !episodes.length) return null;

  const ids = episodes.map((item) => item.id);
  const last = state.progress.entries
    .filter((entry) => sameTitle(entry, state.detail) && ids.includes(entry.episode_id))
    .sort((a, b) => b.updated_at - a.updated_at)[0];
  if (!last) return null;

  const index = ids.indexOf(last.episode_id);
  if (last.up_next || canResume(last)) return episodes[index];
  return last.finished ? episodes[index + 1] || null : null;
}

/** The season, or the block of episodes, of the last episode watched */
function lastGroup(detail, groups) {
  const last = lastWatched(detail);
  if (!last) return null;

  if (isAnime(detail)) {
    const number = parseInt(last.episode_number, 10);
    return groups.find((group) => number >= group.start && number <= group.end)?.key || null;
  }

  return groups.find((group) => group.number === last.season)?.key || null;
}

function episodeToWatch() {
  const episodes = Array.isArray(state.episodes) ? state.episodes : [];

  // The first selected episode, the one to go on with, or the first of the list
  return episodes.find((item) => state.selected.has(item.id)) || continueEpisode() || episodes[0];
}

function watchEpisode() {
  const episode = episodeToWatch();
  if (episode && state.detail) openPlayer(state.detail, episode);
}

function nextEpisode(title, episode, queue = null) {
  const list = queue || (state.detail === title && Array.isArray(state.episodes) ? state.episodes : null);
  if (!episode || !list) return null;

  const index = list.findIndex((item) => item.id === episode.id);
  return index >= 0 ? list[index + 1] || null : null;
}

function loadHls() {
  // The library is big, it is loaded the first time a video is watched
  hlsLibrary ||= new Promise((resolve, reject) => {
    const script = document.createElement('script');
    script.src = '/vendor/hls.min.js';
    script.onload = () => resolve(window.Hls);
    script.onerror = () => {
      hlsLibrary = null;
      script.remove();
      reject(new Error('Il lettore video non si è caricato, riprova'));
    };
    document.head.append(script);
  });

  return hlsLibrary;
}

/**
 * The film or the episode in streaming. Without a time it starts where it was stopped the last time.
 * The queue is the list of the episodes after it, when the player is not opened from the page of the title.
 */
async function openPlayer(title, episode = null, startAt = 0, { queue = null, season = undefined } = {}) {
  const requestId = ++playerRequest;
  const layer = $('#player');
  const stage = $('#player-stage');
  const next = nextEpisode(title, episode, queue);
  const nextButton = $('#player-next');
  const seasonNumber = season !== undefined ? season : state.detail === title && state.season ? Number(state.season) : null;
  const again = { queue, season: seasonNumber };

  // The video watched until now keeps its position
  stopVideo();

  const saved = startAt ? null : progressFor(title, episode?.id ?? null);
  const resumeAt = canResume(saved) ? saved.position : 0;
  const start = startAt || resumeAt;

  $('#player-title').textContent = episode ? `${title.name} · Episodio ${episode.number}` : title.name;
  $('#player-meta').textContent = 'Nella stessa qualità del download';
  nextButton.hidden = !next;
  nextButton.onclick = next ? () => openPlayer(title, next, 0, again) : null;
  stage.replaceChildren(h('div', { class: 'player-wait', role: 'status' },
    h('span', { class: 'spinner', 'aria-hidden': 'true' }),
    h('strong', {}, 'Preparo il video…'),
    h('span', {}, 'Qualche secondo')));
  openLayer(layer);

  const params = new URLSearchParams({ source: title.source || 'sc', id: title.id, type: title.type });
  if (episode) params.set('episode_id', episode.id);

  const showError = (error, video = null) => {
    if (requestId !== playerRequest || !layers.includes(layer)) return;

    // Trying again starts from where the video stopped
    const position = video?.currentTime || start;
    stopVideo();
    stage.replaceChildren(errorState(error, () => openPlayer(title, episode, position, again)));
  };

  try {
    const [result, Hls] = await Promise.all([api(`/api/stream?${params}`), loadHls()]);
    if (requestId !== playerRequest || !layers.includes(layer)) return;

    // Anime have the audio inside the video: dubbed copies are in italian, the others in japanese with subtitles
    const code = result.language || (isAnime(title) ? (title.dub ? 'ita' : 'jpn') : null);
    const language = AUDIO_NAMES[code] || code;
    const shownSubtitle = result.subtitles.find((track) => track.default);
    $('#player-meta').textContent = [
      result.quality,
      language ? `Audio ${language}` : null,
      isAnime(title) && code !== 'ita' ? 'sottotitoli in italiano' : null,
      shownSubtitle ? `Sottotitoli ${shownSubtitle.label.toLowerCase()}` : null,
      result.duration ? clock(result.duration) : null,
    ].filter(Boolean).join(' · ');

    // The player of the browser shows the default track by itself, the others are in its menu
    const video = h('video', { controls: true, autoplay: true, playsinline: true }, result.subtitles.map((track) => h('track', {
      kind: 'subtitles',
      src: track.url,
      srclang: track.language,
      label: track.label,
      default: track.default,
    })));
    const current = { title, episode, next, season: seasonNumber, video, savedAt: Date.now() };
    watching = current;

    // The position is saved often while it plays, and every time it stops
    video.addEventListener('timeupdate', () => {
      if (watching === current && !video.paused && Date.now() - current.savedAt > SAVE_INTERVAL) saveWatching();
    });
    video.addEventListener('pause', () => {
      if (watching === current && !video.ended) saveWatching();
    });
    video.addEventListener('ended', () => {
      if (watching === current) saveWatching({ ended: true });
      if (next) openPlayer(title, next, 0, again);
    });

    stage.replaceChildren(video);

    // Shown when the video really starts: before, the player would move it back to the saved time
    if (resumeAt) video.addEventListener('playing', () => stage.append(resumeNote(video, resumeAt)), { once: true });

    if (Hls?.isSupported()) {
      hlsPlayer = new Hls({ startPosition: start || -1, maxBufferLength: 60 });
      let recovered = false;

      hlsPlayer.on(Hls.Events.ERROR, (event, data) => {
        if (!data.fatal) return;

        // A broken piece of video is skipped once, after that the error is shown
        if (data.type === Hls.ErrorTypes.MEDIA_ERROR && !recovered) {
          recovered = true;
          hlsPlayer.recoverMediaError();
          return;
        }

        showError(new Error('Lo streaming si è interrotto: il sito non manda più il video'), video);
      });

      hlsPlayer.loadSource(result.url);
      hlsPlayer.attachMedia(video);
    } else if (video.canPlayType('application/vnd.apple.mpegurl')) {
      // Safari of old iPhones plays the playlist by itself
      video.addEventListener('loadedmetadata', () => { if (start) video.currentTime = start; }, { once: true });
      video.addEventListener('error', () => showError(new Error('Lo streaming si è interrotto: il sito non manda più il video'), video));
      video.src = result.url;
    } else {
      throw new Error('Questo browser non riesce a riprodurre lo streaming');
    }

    video.focus({ preventScroll: true });
  } catch (error) {
    showError(error);
  }
}

function stopVideo() {
  // Closed, or another video: the position stays for the next time
  saveWatching();
  watching = null;

  hlsPlayer?.destroy();
  hlsPlayer = null;

  // Without its source the video stops asking the segments, also when it is no longer on the page
  const video = $('#player-stage video');
  if (video) {
    video.pause();
    video.removeAttribute('src');
    video.load();
  }
}

function stopPlayer() {
  playerRequest += 1;
  stopVideo();
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
    watchButton(watchEpisode, 'small', 'watch-episode'),
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
      episode.duration ? h('span', { class: 'episode-duration' }, `${episode.duration} min`) : null,
      h('span', { class: 'episode-progress' })),
    h('span', { class: 'episode-info' },
      h('span', { class: 'episode-title' },
        compact ? null : h('span', { class: 'episode-number' }, episode.number),
        h('span', { class: 'episode-name' }, episode.name),
        h('span', { class: 'episode-state' })),
      h('span', { class: 'episode-watch' }),
      episode.plot ? h('span', { class: 'episode-plot' }, episode.plot) : null),
    h('span', { class: 'check', 'aria-hidden': 'true' }, icon('check')),
    compact ? h('span', { class: 'episode-progress' }) : null);
}

/** Seen to the end, or stopped in the middle with the time left */
function updateEpisodeWatch(row, entry) {
  const text = $('.episode-watch', row);
  const resume = canResume(entry);
  const compact = row.closest('.episodes.compact');

  text.className = `episode-watch${entry?.finished ? ' seen' : ''}`;
  text.textContent = entry?.finished ? 'Visto' : resume ? (compact ? `Interrotto a ${clock(entry.position)}` : `Interrotto a ${clock(entry.position)} · ${minutesLeft(entry)}`) : '';
  $('.episode-progress', row).replaceChildren(...(resume ? [watchBar(entry)] : []));
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

  // Which episode starts: the first selected, the one to go on with, or the first of the list
  const watch = $('#watch-episode');
  const episode = episodeToWatch();
  const going = !count && episode && episode === continueEpisode();
  if (watch && episode) $('span', watch).textContent = `${going ? 'Riprendi' : 'Guarda'} ep. ${episode.number}`;
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

  const watchMovie = $('#movie-watch-button');
  if (watchMovie) fillMovieWatch(watchMovie, $('#movie-watch'), detail);

  $$('#season-body .episode').forEach((row) => {
    updateEpisodeWatch(row, progressFor(detail, Number(row.dataset.episodeId)));
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

    if (job.status === 'done' && job.warning) toast(`Non caricato sul NAS, il file resta sul PC: ${jobName(job)} · ${job.warning}`, 'warning', { action: 'Apri', onAction: openDownloads });
    else if (job.status === 'done' && job.remote) toast(`Caricato sul NAS: ${jobName(job)}`, 'success');
    else if (job.status === 'done') toast(`Download completato: ${jobName(job)}`, 'success', { action: 'Mostra', onAction: () => openFolder(job.id) });
    if (job.status === 'error') toast(`Download non riuscito: ${jobName(job)}${job.error ? ` · ${job.error}` : ''}`, 'error', { action: 'Dettagli', onAction: openDownloads });
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

const speedNumber = new Intl.NumberFormat('it-IT', { maximumFractionDigits: 1 });

function formatSpeed(bytes) {
  if (bytes == null) return '';
  if (bytes < 1e6) return `${Math.round(bytes / 1e3)} KB/s`;
  return `${speedNumber.format(bytes / 1e6)} MB/s`;
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
    eta = stage ? [formatSpeed(job.speed), formatEta(estimateSeconds(job, percent))].filter(Boolean).join(' · ') : '';
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
  const speed = formatSpeed(state.jobs.find((job) => job.status === 'running')?.speed);
  const parts = [
    count('running') ? `Download in corso${speed ? ` a ${speed}` : ''}` : null,
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

/* ---------- Torrents ---------- */

const TORRENT_KINDS = { movie: 'Film', tv: 'Serie TV', anime: 'Anime' };
const LANGUAGES = {
  ita: 'Italiano', eng: 'Inglese', jpn: 'Giapponese', fre: 'Francese', fra: 'Francese', ger: 'Tedesco', deu: 'Tedesco',
  spa: 'Spagnolo', por: 'Portoghese', rus: 'Russo', kor: 'Coreano', chi: 'Cinese', zho: 'Cinese', ara: 'Arabo',
  hin: 'Hindi', pol: 'Polacco', dut: 'Olandese', nld: 'Olandese', swe: 'Svedese', tur: 'Turco', ukr: 'Ucraino',
};
const INSPECT_STEPS = {
  adding: 'Invio il torrent a qBittorrent…',
  metadata: 'Ricevo l’elenco dei file…',
  pieces: 'Scarico l’inizio del video…',
  probe: 'Leggo le tracce…',
};
const MAX_TORRENT_ROWS = 300;

const torrent = {
  category: 'all',
  quality: '',
  ita: false,
  showFakes: false,
  hideSuspects: false,
  results: [],
  failed: [],
  searchId: 0,
  items: [],
  loaded: false,
  status: null,
  pollTimer: null,
  sheet: null,
};
const torrentNodes = new Map();
const sizeNumber = new Intl.NumberFormat('it-IT', { maximumFractionDigits: 1 });

function formatSize(bytes) {
  if (!bytes) return '—';

  const units = ['B', 'KB', 'MB', 'GB', 'TB'];
  let value = bytes;
  let unit = 0;

  while (value >= 1024 && unit < units.length - 1) {
    value /= 1024;
    unit += 1;
  }

  return `${unit >= 2 ? sizeNumber.format(value) : Math.round(value)} ${units[unit]}`;
}

function formatDay(date) {
  if (!date) return null;
  const day = new Date(date);
  return Number.isNaN(day.getTime()) ? null : day.toLocaleDateString('it-IT', { day: 'numeric', month: 'short', year: 'numeric' });
}

// Like replaceChildren, but the parts left out (null, false) are skipped instead of written as text
function fill(node, ...children) {
  node.replaceChildren(...children.flat(Infinity).filter((child) => child !== null && child !== undefined && child !== false && child !== ''));
}

function tagNode(tag) {
  const tone = tag.label === 'ITA' ? ' good' : tag.label === 'CAM' ? ' bad' : '';
  return h('span', { class: `tag ${tag.kind}${tone}` }, tag.label);
}

function canInspect() {
  return torrent.status?.mode === 'webui' && torrent.status?.probe !== false;
}

function inspectBlocker() {
  if (torrent.status?.mode !== 'webui') return 'Serve la Web UI di qBittorrent: attivala nelle impostazioni, scheda Torrent.';
  if (torrent.status?.probe === false) return 'Serve ffprobe: installa FFmpeg completo.';
  return '';
}

function mediaOf(result) {
  const { guess } = result;
  return { name: guess.name, year: guess.year, type: guess.type, season: guess.season };
}

function mediaLabel(media) {
  if (media.type === 'movie') return media.year ? `${media.name} (${media.year})` : media.name;
  return `${media.name} · Stagione ${media.season || 1}`;
}

function openTorrents() {
  showView('torrent');
  pollTorrents();

  if (!$('#torrent-list').childElementCount) {
    $('#torrent-list').replaceChildren(emptyState('search', 'Cerca un film, una serie o un anime',
      'I risultati arrivano da tutti gli indicizzatori di Jackett. Aprine uno per leggere la scheda tecnica prima di scaricarlo.'));
  }

  if (!torrent.results.length && window.matchMedia('(pointer: fine)').matches) {
    setTimeout(() => $('#torrent-input').focus({ preventScroll: true }), 60);
  }
}

/* Search */

async function runTorrentSearch(event) {
  event?.preventDefault();

  const input = $('#torrent-input');
  const query = input.value.trim();
  const list = $('#torrent-list');
  const button = $('#torrent-go');

  if (!query) {
    input.focus();
    return;
  }

  const searchId = ++torrent.searchId;
  button.classList.add('loading');
  button.disabled = true;
  input.blur();
  $('#torrent-toolbar').hidden = true;
  list.replaceChildren(h('div', { class: 'torrent-wait', role: 'status' },
    h('span', { class: 'spinner', 'aria-hidden': 'true' }),
    h('strong', {}, `Cerco “${query}” su tutti gli indicizzatori…`),
    h('span', {}, 'Jackett aspetta ogni sito: può volerci fino a un minuto')));

  try {
    const data = await api(`/api/torrents/search?q=${encodeURIComponent(query)}&cat=${torrent.category}`);
    if (searchId !== torrent.searchId) return;

    torrent.results = data.results;
    torrent.failed = data.failed || [];

    // Nowhere to search: jackett without sites and no plugins of qbittorrent
    if (!data.indexers && !data.plugins) {
      torrent.results = [];
      const jackett = torrent.status?.jackett_url && !state.status?.remote_client
        ? h('a', { class: 'button ghost small', href: torrent.status.jackett_url, target: '_blank', rel: 'noopener' }, 'Apri Jackett')
        : null;
      list.replaceChildren(emptyState('alert', 'Nessun sito in cui cercare', 'Jackett non ha indicizzatori e non ho trovato i plugin di ricerca di qBittorrent: aggiungi qualche sito dalla dashboard di Jackett (Add indexer), oppure installa i plugin da qBittorrent (Ricerca → Estensioni).', jackett));
      return;
    }

    renderTorrentResults();
  } catch (error) {
    if (searchId !== torrent.searchId) return;
    list.replaceChildren(errorState(error, runTorrentSearch));
  } finally {
    if (searchId === torrent.searchId) {
      button.classList.remove('loading');
      button.disabled = false;
    }
  }
}

function resultQuality(result) {
  return result.guess.tags.find((tag) => tag.kind === 'quality')?.label || '';
}

function renderTorrentResults() {
  const list = $('#torrent-list');
  const words = $('#torrent-filter').value.toLowerCase().split(/\s+/).filter(Boolean);
  const compare = {
    seeders: (a, b) => b.seeders - a.seeders || b.size - a.size,
    size: (a, b) => b.size - a.size,
    'size-asc': (a, b) => a.size - b.size,
    date: (a, b) => (b.date || '').localeCompare(a.date || ''),
  }[$('#torrent-sort').value];

  // Fakes never show up unless asked, suspects only on request are hidden
  const hidden = (result) => (result.check.level === 'fake' && !torrent.showFakes) || (result.check.level === 'suspect' && torrent.hideSuspects);
  const fakes = torrent.results.filter((result) => result.check.level === 'fake').length;

  const shown = torrent.results
    .filter((result) => !hidden(result))
    .filter((result) => !torrent.quality || resultQuality(result) === torrent.quality)
    .filter((result) => !torrent.ita || result.guess.tags.some((tag) => tag.label === 'ITA'))
    .filter((result) => words.every((word) => result.title.toLowerCase().includes(word)))
    .sort(compare);

  $('#torrent-toolbar').hidden = !torrent.results.length;
  $('#torrent-count').textContent = shown.length === torrent.results.length
    ? plural(shown.length, 'risultato', 'risultati')
    : `${shown.length} di ${torrent.results.length}`;

  const notes = [
    fakes ? h('span', {},
      `${plural(fakes, 'falso nascosto', 'falsi nascosti')} (programmi, archivi con password, pesi impossibili) · `,
      h('button', { class: 'link-button', type: 'button', onclick: () => { torrent.showFakes = !torrent.showFakes; renderTorrentResults(); } },
        torrent.showFakes ? 'Nascondili' : 'Mostrali')) : null,
    torrent.failed.length ? h('span', {}, `Non hanno risposto: ${torrent.failed.join(', ')}`) : null,
  ].filter(Boolean);
  const failed = notes.length ? h('p', { class: 'torrent-failed' }, icon('alert'), h('span', { class: 'torrent-notes' }, notes)) : null;

  if (!torrent.results.length) {
    list.replaceChildren(emptyState('search', 'Nessun risultato', 'Nessun indicizzatore ha trovato qualcosa: prova con meno parole o con il titolo originale.'), failed || '');
    return;
  }

  if (!shown.length) {
    list.replaceChildren(failed || '', emptyState('search', 'Nessun risultato con questi filtri', 'Togli qualche filtro per vedere gli altri.'));
    return;
  }

  list.replaceChildren(failed || '', ...shown.slice(0, MAX_TORRENT_ROWS).map(torrentRow));
}

function checkTag(check) {
  if (!check?.level) return null;
  return h('span', { class: `tag ${check.level === 'fake' ? 'bad' : 'warn'}` }, check.level === 'fake' ? 'Falso' : 'Sospetto');
}

function checkNotices(check) {
  return (check?.reasons || []).map((reason) => h('div', { class: `notice${reason.level === 'fake' ? ' bad' : ''}` }, icon('alert'), h('span', {}, reason.text)));
}

function torrentRow(result, index) {
  const health = result.seeders >= 10 ? 'good' : result.seeders > 0 ? 'low' : 'none';
  const { check } = result;

  return h('article', { class: `torrent-row${result.seeders ? '' : ' dead'}${check.level ? ` ${check.level}` : ''}`, style: `--i:${Math.min(index, 16)}` },
    h('button', { class: 'torrent-row-main', type: 'button', onclick: () => openTorrentSheet(result) },
      h('span', { class: 'torrent-title' }, result.title),
      result.guess.tags.length || check.level ? h('span', { class: 'torrent-tags' }, checkTag(check), result.guess.tags.map(tagNode)) : null,
      h('span', { class: 'torrent-meta' }, [result.tracker, formatSize(result.size), formatDay(result.date)].filter(Boolean).join(' · ')),
      check.level ? h('span', { class: `torrent-reasons ${check.level}` }, check.reasons.map((reason) => reason.text).join(' · ')) : null),
    h('div', { class: `torrent-health ${health}`, title: `${result.seeders} seed · ${result.peers} peer` },
      h('strong', {}, result.seeders),
      h('span', {}, 'seed')),
    h('div', { class: 'torrent-row-actions' },
      h('button', {
        class: 'button ghost small',
        type: 'button',
        title: canInspect() ? 'Risoluzione, lingue e sottotitoli prima di scaricare' : inspectBlocker(),
        disabled: !canInspect(),
        onclick: () => openTorrentSheet(result, { inspect: true }),
      }, icon('info'), h('span', { class: 'hide-small' }, 'Scheda tecnica')),
      h('button', { class: 'button primary small', type: 'button', 'aria-label': `Scarica ${result.title}`, onclick: (event) => quickDownload(result, event.currentTarget) },
        icon('download'), h('span', { class: 'hide-small' }, 'Scarica'))));
}

async function quickDownload(result, button) {
  // A fake is downloaded only after reading why it looks like one
  if (result.check.level === 'fake') {
    openTorrentSheet(result);
    return;
  }

  button.classList.add('loading');
  button.disabled = true;

  try {
    const data = await api('/api/torrents/download', { method: 'POST', body: { result: result.id, media: mediaOf(result) } });
    setTorrentItems(data.items);
    toast(`${data.message}: ${mediaLabel(mediaOf(result))}`, 'success');
    pollTorrents();
  } catch (error) {
    toast(error.message, 'error');
  } finally {
    button.classList.remove('loading');
    button.disabled = false;
  }
}

/* Sheet of a torrent: name on the nas and scheda tecnica */

function openTorrentSheet(result, { inspect = false } = {}) {
  torrent.sheet = { result, media: mediaOf(result), item: null, files: null, converted: false, timer: null };

  renderTorrentSheet();
  const layer = $('#torrent-sheet');
  $('.sheet', layer).scrollTop = 0;
  openLayer(layer);
  $('.close-button', layer).focus({ preventScroll: true });

  if (inspect) startInspect();
}

function closeTorrentSheet() {
  const sheet = torrent.sheet;
  torrent.sheet = null;
  if (!sheet) return;

  clearTimeout(sheet.timer);

  // The start of the video downloaded for the scheda tecnica is not wanted
  if (sheet.item?.id && !sheet.converted) discardTorrent(sheet.item.id);
}

function renderTorrentSheet() {
  const { result } = torrent.sheet;
  const details = result.details && !state.status?.remote_client
    ? h('a', { class: 'link-button', href: result.details, target: '_blank', rel: 'noopener noreferrer' }, 'Pagina del torrent sul sito')
    : null;

  $('#torrent-sheet-body').replaceChildren(
    h('header', { class: 'ts-head' },
      h('p', { class: 'eyebrow' }, result.tracker || 'Torrent'),
      h('h2', { class: 'ts-title', id: 'torrent-sheet-title' }, result.title),
      metaRow([formatSize(result.size), `${result.seeders} seed · ${result.peers} peer`, formatDay(result.date), result.category || null]),
      result.guess.tags.length || result.check.level ? h('div', { class: 'torrent-tags' }, checkTag(result.check), result.guess.tags.map(tagNode)) : null,
      details,
      result.check.level ? h('div', { class: 'ts-check' }, checkNotices(result.check)) : null),
    h('section', { class: 'ts-section' },
      h('h3', { class: 'ts-section-title' }, 'Salva come'),
      mediaFields(),
      h('p', { class: 'form-note' }, torrentDestination())),
    h('section', { class: 'ts-section', id: 'ts-inspect' }),
    h('footer', { class: 'ts-actions' },
      h('button', { class: 'button ghost', type: 'button', 'data-close': true }, 'Chiudi'),
      h('button', { class: 'button primary', type: 'button', id: 'ts-download', onclick: sheetDownload }, icon('download'), h('span', {}, 'Scarica'))));

  renderInspect();
}

function torrentDestination() {
  if (torrent.status?.mode === 'app' && !torrent.status.system_open) return 'Per scaricare da qui serve la Web UI di qBittorrent: attivala nelle impostazioni, scheda Torrent.';
  if (torrent.status?.mode === 'app') return 'Il torrent si apre in qBittorrent sul PC.';
  if (torrent.status?.nas) return 'Finito il download lo carico sul NAS con questo nome, nella cartella dei film, delle serie o degli anime.';
  return 'Resta nella cartella dei download di qBittorrent.';
}

function mediaFields() {
  const { media } = torrent.sheet;
  const seasonField = h('label', { class: 'field port', hidden: media.type === 'movie' },
    h('span', {}, 'Stagione'),
    h('input', { type: 'number', min: '1', max: '99', value: media.season || 1, oninput: (event) => { media.season = Number(event.target.value) || 1; } }));

  const kinds = h('div', { class: 'tabs ts-kinds', role: 'radiogroup', 'aria-label': 'Tipo' });
  const selectKind = (kind) => {
    media.type = kind;
    if (kind !== 'movie' && !media.season) media.season = 1;
    seasonField.hidden = kind === 'movie';
    $$('.tab', kinds).forEach((tab) => {
      tab.setAttribute('aria-checked', String(tab.dataset.kind === kind));
      tab.setAttribute('aria-selected', String(tab.dataset.kind === kind));
    });
  };

  kinds.append(...Object.entries(TORRENT_KINDS).map(([kind, label]) => h('button', {
    class: 'tab small',
    type: 'button',
    role: 'radio',
    dataset: { kind },
    onclick: () => selectKind(kind),
  }, label)));
  selectKind(media.type);

  return h('div', { class: 'fields' },
    h('div', { class: 'field-row' },
      h('label', { class: 'field grow' }, h('span', {}, 'Titolo'),
        h('input', { type: 'text', value: media.name, spellcheck: 'false', autocomplete: 'off', oninput: (event) => { media.name = event.target.value; } })),
      h('label', { class: 'field port' }, h('span', {}, 'Anno'),
        h('input', { type: 'text', inputmode: 'numeric', maxlength: '4', value: media.year || '', placeholder: '—', autocomplete: 'off', oninput: (event) => { media.year = event.target.value.trim(); } }))),
    h('div', { class: 'field-row ts-kind-row' },
      h('div', { class: 'field grow' }, h('span', {}, 'Tipo'), kinds),
      seasonField));
}

async function startInspect() {
  const sheet = torrent.sheet;
  if (!sheet || (sheet.item && sheet.item.inspect?.status !== 'error')) return;

  // A scheda tecnica that failed is made again from the start
  if (sheet.item?.id) discardTorrent(sheet.item.id);
  sheet.item = { inspect: { status: 'adding' } };
  sheet.files = null;
  renderInspect();

  try {
    const item = await api('/api/torrents/inspect', { method: 'POST', body: { result: sheet.result.id, media: sheet.media } });

    if (torrent.sheet !== sheet) {
      discardTorrent(item.id);
      return;
    }

    sheet.item = item;
    renderInspect();
    pollInspect(sheet);
  } catch (error) {
    if (torrent.sheet !== sheet) return;
    sheet.item = { inspect: { status: 'error', message: error.message } };
    renderInspect();
  }
}

async function pollInspect(sheet) {
  clearTimeout(sheet.timer);
  if (torrent.sheet !== sheet || !sheet.item?.id || sheet.converted) return;

  const before = sheet.item.inspect?.status;

  try {
    const item = await api(`/api/torrents/item?id=${sheet.item.id}`);
    if (torrent.sheet !== sheet || item.phase !== 'inspect') return;

    sheet.item = item;
    if (!(before === 'ready' && item.inspect.status === 'ready')) renderInspect();
  } catch (error) {
    if (torrent.sheet !== sheet) return;
    sheet.item = { id: sheet.item.id, inspect: { status: 'error', message: error.message } };
    renderInspect();
    return;
  }

  // A ready scheda is only kept alive, the others are followed closely
  const finished = ['ready', 'error'].includes(sheet.item.inspect.status);
  sheet.timer = setTimeout(() => pollInspect(sheet), finished ? 60000 : 1000);
}

// A fake can still be downloaded, but the button does not invite to
function updateSheetButton() {
  const sheet = torrent.sheet;
  const button = $('#ts-download');
  if (!sheet || !button) return;

  const fake = sheet.result.check.level === 'fake' || sheet.item?.inspect?.info?.check?.level === 'fake';
  button.className = `button ${fake ? 'ghost danger' : 'primary'}`;
  $('span', button).textContent = fake ? 'Scarica comunque' : 'Scarica';
}

function renderInspect() {
  const area = $('#ts-inspect');
  const sheet = torrent.sheet;
  if (!area || !sheet) return;

  updateSheetButton();

  const title = h('h3', { class: 'ts-section-title' }, 'Scheda tecnica');
  const inspect = sheet.item?.inspect;

  if (!inspect) {
    fill(area, title,
      h('p', { class: 'ts-text' }, 'Scarico solo l’inizio del video, pochi MB, e leggo le sue tracce: risoluzione vera, codec, lingue dell’audio e sottotitoli. Ci vogliono pochi secondi se ci sono abbastanza seed.'),
      h('button', { class: 'button ghost small', type: 'button', disabled: !canInspect(), onclick: startInspect }, icon('info'), 'Leggi la scheda tecnica'),
      canInspect() ? null : h('p', { class: 'form-note' }, inspectBlocker()));
    return;
  }

  if (inspect.status === 'error') {
    fill(area, title,
      h('div', { class: 'result bad' }, h('strong', {}, inspect.message || 'Scheda tecnica non riuscita')),
      inspect.info ? filesView(inspect.info) : null,
      h('button', { class: 'button ghost small ts-retry', type: 'button', onclick: startInspect }, icon('retry'), 'Riprova'));
    return;
  }

  if (inspect.status !== 'ready') {
    const percent = inspect.status === 'pieces' && inspect.need ? Math.floor((inspect.have / inspect.need) * 100) : null;
    const live = [
      sheet.item.seeds != null ? plural(sheet.item.seeds, 'seed collegato', 'seed collegati') : null,
      sheet.item.speed ? formatSpeed(sheet.item.speed) : null,
    ].filter(Boolean).join(' · ');

    fill(area, title,
      h('div', { class: 'ts-wait', role: 'status' },
        h('span', { class: 'spinner', 'aria-hidden': 'true' }),
        h('div', {},
          h('strong', {}, `${INSPECT_STEPS[inspect.status] || 'Preparo…'}${percent != null ? ` ${percent}%` : ''}`),
          h('span', {}, live || 'In attesa di qualcuno che lo condivida'))),
      percent != null ? h('div', { class: 'progress' }, h('span', { class: 'progress-bar', style: `width:${percent}%` })) : null);
    return;
  }

  const { info } = inspect;
  fill(area, title,
    info.check?.level ? null : h('div', { class: 'notice good' }, icon('check'), h('span', {}, 'Nessun segno di falso: i file e le tracce corrispondono al nome')),
    checkNotices(info.check),
    info.probe ? probeView(info.probe) : h('p', { class: 'ts-text' }, 'Nessun video da leggere in questo torrent.'),
    filesView(info));
}

function resolutionLabel(video) {
  const { width = 0, height = 0 } = video;
  let label = `${height}p`;

  if (width >= 3800 || height >= 2000) label = '4K';
  else if (width >= 1900 || height >= 1000) label = '1080p';
  else if (width >= 1260 || height >= 700) label = '720p';

  return width && height ? `${label} (${width}×${height})` : null;
}

function probeView(data) {
  const { video } = data;
  const row = (label, value) => h('div', {}, h('dt', {}, label), h('dd', {}, value));

  return h('dl', { class: 'specs' },
    video ? row('Video', [
      resolutionLabel(video),
      video.codec,
      video.hdr,
      video.bit_depth ? `${video.bit_depth} bit` : null,
      video.fps ? `${speedNumber.format(video.fps)} fps` : null,
    ].filter(Boolean).join(' · ')) : null,
    data.duration ? row('Durata', formatRuntime(Math.round(data.duration / 60))) : null,
    row('Audio', data.audio.length ? h('div', { class: 'tracks' }, data.audio.map(trackNode)) : 'Nessuna traccia audio'),
    row('Sottotitoli', data.subtitles.length ? h('div', { class: 'tracks' }, data.subtitles.map(trackNode)) : 'Nessuno'));
}

function trackNode(track) {
  const code = (track.language || '').toLowerCase();
  const language = LANGUAGES[code] || (code && code !== 'und' ? code.toUpperCase() : 'Lingua non indicata');
  const title = track.title && !track.title.toLowerCase().includes(language.toLowerCase()) ? track.title : null;
  const details = [track.codec, track.channels, track.forced ? 'forzati' : null, title].filter(Boolean).join(' · ');

  return h('span', { class: `track${code === 'ita' ? ' ita' : ''}` }, h('strong', {}, language), details ? h('span', {}, details) : null);
}

function filesView(info) {
  const sheet = torrent.sheet;
  const { files } = info;
  if (!files?.length) return null;

  // Videos and their subtitles by default, never samples or programs
  if (!sheet.files) {
    const wanted = files.filter((file) => (file.video && !file.sample) || /\.(srt|ass|ssa|sub|idx|vtt)$/i.test(file.name));
    sheet.files = new Set((wanted.length ? wanted : files.filter((file) => !file.dangerous)).map((file) => file.index));
  }

  if (files.length === 1) {
    return h('p', { class: 'ts-text ts-single' }, 'Un solo file: ', h('code', {}, files[0].name), ` · ${formatSize(files[0].size)}`);
  }

  const count = h('span', { class: 'toolbar-count' });
  const updateCount = () => {
    const chosen = files.filter((file) => sheet.files.has(file.index));
    count.textContent = `${chosen.length} di ${files.length} · ${formatSize(chosen.reduce((total, file) => total + file.size, 0))}`;
  };
  updateCount();

  return h('div', { class: 'ts-files' },
    h('div', { class: 'ts-files-head' }, h('h4', {}, 'File da scaricare'), count),
    h('div', { class: 'ts-file-list' }, files.map((file) => h('label', { class: `ts-file${file.dangerous ? ' dangerous' : ''}` },
      h('input', {
        type: 'checkbox',
        checked: sheet.files.has(file.index),
        // A program is never downloaded, not even by choice
        disabled: file.dangerous,
        title: file.dangerous ? 'Programma: non viene mai scaricato' : null,
        onchange: (event) => {
          if (event.target.checked) sheet.files.add(file.index);
          else sheet.files.delete(file.index);
          updateCount();
        },
      }),
      h('span', { class: 'ts-file-name', title: file.name }, file.name),
      h('span', { class: 'ts-file-size' }, formatSize(file.size))))));
}

async function sheetDownload() {
  const sheet = torrent.sheet;
  const button = $('#ts-download');
  if (!sheet) return;

  if (!sheet.media.name.trim()) {
    toast('Scrivi il titolo con cui salvarlo', 'error');
    return;
  }

  const body = { media: sheet.media };

  // The torrent already in qbittorrent for the scheda tecnica goes on from there
  if (sheet.item?.id) {
    body.item = sheet.item.id;

    if (sheet.item.inspect?.status === 'ready' && sheet.files) {
      if (!sheet.files.size) {
        toast('Scegli almeno un file da scaricare', 'error');
        return;
      }
      body.files = [...sheet.files];
    }
  } else {
    body.result = sheet.result.id;
  }

  button.classList.add('loading');
  button.disabled = true;

  try {
    const data = await api('/api/torrents/download', { method: 'POST', body });
    sheet.converted = true;
    setTorrentItems(data.items);
    closeLayer($('#torrent-sheet'));
    toast(`${data.message || 'Inviato a qBittorrent'}: ${mediaLabel(sheet.media)}`, 'success');
    pollTorrents();
  } catch (error) {
    toast(error.message, 'error');
  } finally {
    button.classList.remove('loading');
    button.disabled = false;
  }
}

async function discardTorrent(id) {
  try {
    const { items } = await api('/api/torrents/discard', { method: 'POST', body: { id } });
    setTorrentItems(items);
  } catch {
    // Left in qbittorrent, the program throws it away by itself later
  }
}

/* List of the torrents */

async function pollTorrents() {
  clearTimeout(torrent.pollTimer);

  try {
    const data = await api('/api/torrents');
    torrent.status = data.status;
    setTorrentItems(data.items);
    renderTorrentSetup();
  } catch {
    // The downloads say when the program does not answer
  }

  const visible = !$('#torrent-view').hidden;
  const active = torrent.items.some((item) => item.phase === 'download' || item.phase === 'upload');
  torrent.pollTimer = setTimeout(pollTorrents, visible ? (active ? 1500 : 5000) : (active ? 5000 : 20000));
}

function setTorrentItems(items) {
  const previous = new Map(torrent.items.map((item) => [item.id, item.phase]));
  const notes = new Map(torrent.items.map((item) => [item.id, item.note]));
  torrent.items = items;

  for (const item of torrent.loaded ? items : []) {
    if (item.note && notes.has(item.id) && !notes.get(item.id)) toast(`${mediaLabel(item.media)}: ${item.note}`, 'warning');

    const before = previous.get(item.id);
    if (!before || before === item.phase) continue;

    const name = mediaLabel(item.media);
    if (item.phase === 'upload') toast(`Torrent scaricato, lo carico sul NAS: ${name}`, 'info');
    else if (item.phase === 'done' && item.warning) toast(`Non caricato sul NAS: ${name} · ${item.warning}`, 'warning', { action: 'Vedi', onAction: openTorrents });
    else if (item.phase === 'done' && item.remote) toast(`Caricato sul NAS: ${name}`, 'success');
    else if (item.phase === 'done') toast(`Torrent completato: ${name}`, 'success', { action: 'Vedi', onAction: openTorrents });
    else if (item.phase === 'error') toast(`${name}: ${item.error}`, 'error');
  }

  torrent.loaded = true;
  renderTorrentItems();
}

function torrentPercent(item) {
  if (item.phase === 'done') return 100;
  if (item.phase === 'upload') return item.upload?.total ? (item.upload.done / item.upload.total) * 100 : 0;
  return (item.progress || 0) * 100;
}

function renderTorrentItems() {
  const list = $('#torrent-jobs');
  const ids = new Set(torrent.items.map((item) => item.id));

  for (const [id, node] of torrentNodes) {
    if (ids.has(id)) continue;
    node.remove();
    torrentNodes.delete(id);
  }

  const empty = $('.empty', list);
  if (!torrent.items.length) {
    if (!empty) list.replaceChildren(emptyState('magnet', 'Nessun torrent', 'Quelli che scarichi da qui compaiono in questa colonna, con l’avanzamento.'));
  } else if (empty) {
    empty.remove();
  }

  // Moving first, then the finished ones from the newest
  const order = { upload: 0, download: 1, error: 2, done: 2 };
  const items = [...torrent.items].sort((a, b) => order[a.phase] - order[b.phase] || b.id - a.id);

  items.forEach((item, index) => {
    let node = torrentNodes.get(item.id);

    if (!node) {
      node = createTorrentNode(item);
      torrentNodes.set(item.id, node);
    }

    updateTorrentNode(node, item);
    if (list.children[index] !== node) list.insertBefore(node, list.children[index] || null);
  });

  renderTorrentSummary();
}

function createTorrentNode(item) {
  return h('article', { class: 'job torrent-job' },
    posterNode({ id: item.id, name: item.media.name }, 'poster job-poster'),
    h('div', { class: 'job-main' },
      h('div', { class: 'job-title', title: mediaLabel(item.media) }, mediaLabel(item.media)),
      h('div', { class: 'job-sub', title: item.title }, item.title),
      h('div', { class: 'progress', role: 'progressbar', 'aria-valuemin': '0', 'aria-valuemax': '100', 'aria-label': `Avanzamento di ${item.media.name}` },
        h('span', { class: 'progress-bar' })),
      h('div', { class: 'job-status' }, h('span', { class: 'job-state' }), h('span', { class: 'job-eta' }))),
    h('div', { class: 'job-actions' }));
}

function updateTorrentNode(node, item) {
  const percent = torrentPercent(item);
  const waiting = item.phase === 'download' && (item.paused || item.stalled || !item.in_client || item.problem);
  let label = '';
  let eta = '';

  const status = { download: waiting ? 'waiting' : 'running', upload: 'running', done: 'done', error: 'error' }[item.phase];
  node.className = `job torrent-job ${status}${item.warning ? ' warning' : ''}`;
  $('.progress', node).setAttribute('aria-valuenow', String(Math.round(percent)));
  $('.progress-bar', node).style.width = `${percent}%`;

  if (item.phase === 'download') {
    const progress = `${Math.floor(percent)}%`;

    if (item.problem) label = item.problem;
    else if (!item.in_client) label = torrent.status?.client_error ? 'qBittorrent non risponde' : 'Invio a qBittorrent…';
    else if (item.paused) label = `In pausa · ${progress}`;
    else if (item.state === 'metaDL' || item.state === 'forcedMetaDL') label = 'Ricevo l’elenco dei file…';
    else if (item.stalled) label = `In attesa di fonti · ${progress}`;
    else label = `Download · ${progress}`;

    if (item.in_client && !item.paused) {
      eta = [item.speed ? formatSpeed(item.speed) : null, item.seeds != null ? `${item.seeds} seed` : null, formatEta(item.eta)].filter(Boolean).join(' · ');
    }
  } else if (item.phase === 'upload') {
    const upload = item.upload;
    label = upload ? `Caricamento sul NAS${upload.count > 1 ? ` · file ${upload.index} di ${upload.count}` : ''} · ${Math.floor(percent)}%` : 'Caricamento sul NAS…';
    eta = upload?.speed ? formatSpeed(upload.speed) : '';
  } else if (item.phase === 'done') {
    label = item.warning ? `Sul PC · ${item.warning}` : item.remote ? (item.uploaded > 1 ? `Sul NAS · ${item.uploaded} file` : 'Sul NAS') : 'Completato';
    eta = item.in_client && !item.warning && !item.remote ? 'in condivisione' : '';
  } else {
    label = item.error || 'Non riuscito';
  }

  const stateNode = $('.job-state', node);
  stateNode.textContent = label;
  stateNode.title = item.remote || label;
  $('.job-eta', node).textContent = eta;

  const actions = $('.job-actions', node);
  const key = `${item.phase}:${item.paused ? 1 : 0}:${item.in_client ? 1 : 0}:${item.warning ? 1 : 0}`;

  if (actions.dataset.key !== key) {
    actions.dataset.key = key;
    actions.replaceChildren(...torrentActions(item));
  }
}

function torrentActions(item) {
  const button = (iconName, label, onclick) => h('button', { class: 'icon-button small', type: 'button', title: label, 'aria-label': label, onclick }, icon(iconName));
  const actions = [];

  if (item.phase === 'download' && item.in_client) {
    actions.push(item.paused
      ? button('play', 'Riprendi', () => torrentCommand('/api/torrents/pause', { id: item.id, paused: false }))
      : button('pause', 'Metti in pausa', () => torrentCommand('/api/torrents/pause', { id: item.id, paused: true })));
  }
  if (item.phase === 'download') actions.push(confirmButton('Annulla e cancella i file scaricati', () => torrentCommand('/api/torrents/discard', { id: item.id })));
  if (item.phase === 'done' && item.in_client && !state.status?.remote_client) actions.push(button('folder', 'Mostra i file', () => torrentCommand('/api/torrents/open', { id: item.id })));
  if (item.phase === 'done' && item.warning && torrent.status?.nas && item.in_client) actions.push(button('upload', 'Riprova il caricamento sul NAS', () => torrentCommand('/api/torrents/upload', { id: item.id })));
  if (item.phase === 'done' || item.phase === 'error') actions.push(button('close', 'Togli dalla lista (i file restano)', () => torrentCommand('/api/torrents/discard', { id: item.id })));

  return actions;
}

async function torrentCommand(path, body) {
  try {
    const data = await api(path, { method: 'POST', body });
    if (data.items) setTorrentItems(data.items);
    pollTorrents();
  } catch (error) {
    toast(error.message, 'error');
  }
}

function renderTorrentSummary() {
  const count = (phase) => torrent.items.filter((item) => item.phase === phase).length;
  const active = count('download') + count('upload');
  const parts = [
    count('download') ? `${count('download')} in download` : null,
    count('upload') ? 'caricamento sul NAS' : null,
    count('done') ? plural(count('done'), 'completato', 'completati') : null,
    count('error') ? plural(count('error'), 'non riuscito', 'non riusciti') : null,
  ].filter(Boolean);

  $('#torrent-summary').textContent = parts.join(' · ') || 'Nessun torrent';
  $('#torrent-side').classList.toggle('active', Boolean(active));
  $('#torrent-badge').hidden = !active;
  $('#torrent-badge').textContent = String(active);
  $('#torrent-button').setAttribute('aria-label', active ? `Torrent, ${active} attivi` : 'Torrent');
}

function renderTorrentSetup() {
  const { status } = torrent;
  const container = $('#torrent-setup');
  const setup = h('button', { class: 'button ghost small', type: 'button', onclick: () => openSettings({ panel: 'torrent' }) }, 'Impostazioni');
  let notice = null;

  if (!status) {
    notice = null;
  } else if (!status.jackett_key && !status.plugins) {
    notice = h('div', { class: 'notice' }, icon('alert'), h('span', {}, 'Nessuna fonte per cercare: manca la chiave API di Jackett e non trovo i plugin di ricerca di qBittorrent.'), setup);
  } else if (status.client_error) {
    notice = h('div', { class: 'notice bad' }, icon('alert'), h('span', {}, status.client_error), setup);
  } else if (status.mode === 'app') {
    notice = h('div', { class: 'notice' }, icon('info'), h('span', {}, 'La Web UI di qBittorrent non è impostata: i torrent si aprono in qBittorrent, ma qui non vedi l’avanzamento, la scheda tecnica e il caricamento sul NAS.'), setup);
  }

  const key = notice ? notice.textContent : '';
  if (container.dataset.key === key) return;
  container.dataset.key = key;
  container.replaceChildren(notice || '');
}

/* Settings */

async function loadTorrentConfig() {
  try {
    const config = await api('/api/torrents/config');

    $('#tc-jackett-url').value = config.jackett_url || '';
    $('#tc-jackett-key').value = '';
    $('#tc-jackett-key').placeholder = config.jackett_key_saved
      ? 'Chiave salvata'
      : config.jackett_key_auto ? 'Presa dal plugin Jackett di qBittorrent' : 'Copiala dalla dashboard di Jackett';
    $('#tc-qbit-url').value = config.qbit_url || '';
    $('#tc-qbit-user').value = config.qbit_user || '';
    $('#tc-qbit-password').value = '';
    $('#tc-qbit-password').placeholder = config.password_saved ? 'Password salvata' : 'Facoltativa';
    $('#tc-save-path').value = config.save_path || '';
    $('#tc-remove').checked = config.after_upload !== 'keep';
    $('#tc-path-from').value = config.path_from || '';
    $('#tc-path-to').value = config.path_to || '';
    $('#tc-plugins').checked = config.plugins !== 'off';
    $('#tc-plugins-path').value = config.plugins_path || '';
    $('#tc-plugins-found').textContent = config.plugins_error
      || (config.plugins_found.length
        ? `Trovati in qBittorrent: ${config.plugins_found.join(', ')}. Si gestiscono da qBittorrent, in Ricerca → Estensioni.`
        : 'Non trovo i plugin di ricerca di qBittorrent su questo PC: installali da qBittorrent, in Ricerca → Estensioni.');
    $('#tc-advanced').open = Boolean(config.docker || config.path_from || config.path_to || config.plugins_path);
    $('#torrent-config-result').replaceChildren();
  } catch (error) {
    showTorrentConfigResult(false, error.message);
  }
}

function readTorrentConfig() {
  return {
    jackett_url: $('#tc-jackett-url').value.trim(),
    jackett_key: $('#tc-jackett-key').value.trim(),
    qbit_url: $('#tc-qbit-url').value.trim(),
    qbit_user: $('#tc-qbit-user').value.trim(),
    qbit_password: $('#tc-qbit-password').value,
    save_path: $('#tc-save-path').value.trim(),
    after_upload: $('#tc-remove').checked ? 'remove' : 'keep',
    path_from: $('#tc-path-from').value.trim(),
    path_to: $('#tc-path-to').value.trim(),
    plugins: $('#tc-plugins').checked ? 'on' : 'off',
    plugins_path: $('#tc-plugins-path').value.trim(),
  };
}

function showTorrentConfigResult(ok, message, details = []) {
  $('#torrent-config-result').replaceChildren(h('div', { class: `result ${ok ? 'ok' : 'bad'}` }, h('strong', {}, message), details));
}

async function testTorrentConfig() {
  const button = $('#torrent-config-test');
  button.classList.add('loading');
  button.disabled = true;
  $('#torrent-config-result').replaceChildren();

  try {
    const { jackett, qbit, plugins } = await api('/api/torrents/config/test', { method: 'POST', body: readTorrentConfig() });
    const details = [
      h('div', {}, 'Jackett: ', jackett.ok
        ? (jackett.indexers ? `collegato, ${plural(jackett.indexers, 'indicizzatore', 'indicizzatori')}` : 'collegato, ma senza indicizzatori: aggiungili dalla sua dashboard')
        : jackett.error),
      h('div', {}, 'Plugin di ricerca di qBittorrent: ', plugins ? `${plural(plugins, 'plugin funzionante', 'plugin funzionanti')}` : 'nessuno trovato o spenti'),
      h('div', {}, 'qBittorrent: ', qbit.mode === 'app'
        ? 'senza Web UI, i torrent si aprono con il programma'
        : qbit.ok ? [`collegato, versione ${qbit.version}`, qbit.save_path ? ' · scarica in ' : '', qbit.save_path ? h('code', {}, qbit.save_path) : ''] : qbit.error),
    ];
    const ok = (jackett.ok && jackett.indexers > 0 || plugins > 0) && qbit.ok;
    showTorrentConfigResult(ok, ok ? 'Collegamento riuscito' : 'Qualcosa non va', details);
  } catch (error) {
    showTorrentConfigResult(false, error.message);
  } finally {
    button.classList.remove('loading');
    button.disabled = false;
  }
}

async function saveTorrentConfig(event) {
  event.preventDefault();

  const button = $('#torrent-config-save');
  button.classList.add('loading');
  button.disabled = true;

  try {
    const config = await api('/api/torrents/config', { method: 'POST', body: readTorrentConfig() });

    if (config.password_error) {
      showTorrentConfigResult(false, config.password_error);
    } else {
      $('#torrent-config-result').replaceChildren();
      toast('Impostazioni dei torrent salvate', 'success');
    }

    loadTorrentConfig();
    pollTorrents();
  } catch (error) {
    showTorrentConfigResult(false, error.message);
  } finally {
    button.classList.remove('loading');
    button.disabled = false;
  }
}

function setChoice(group, attribute, value) {
  $$('.tab', group).forEach((tab) => {
    const selected = tab.dataset[attribute] === value;
    tab.setAttribute('aria-checked', String(selected));
    tab.setAttribute('aria-selected', String(selected));
  });
}

function bindTorrentEvents() {
  $('#torrent-form').addEventListener('submit', runTorrentSearch);
  $('#torrent-sheet').addEventListener('layerclose', closeTorrentSheet);
  $('#torrent-config-form').addEventListener('submit', saveTorrentConfig);
  $('#torrent-config-test').addEventListener('click', testTorrentConfig);

  $('#torrent-cats').addEventListener('click', (event) => {
    const tab = event.target.closest('.tab');
    if (!tab || tab.dataset.cat === torrent.category) return;

    torrent.category = tab.dataset.cat;
    setChoice($('#torrent-cats'), 'cat', torrent.category);
    if ($('#torrent-input').value.trim() && (torrent.results.length || $('.empty', $('#torrent-list')))) runTorrentSearch();
  });

  $('#torrent-quality').addEventListener('click', (event) => {
    const tab = event.target.closest('.tab');
    if (!tab) return;

    torrent.quality = tab.dataset.quality;
    setChoice($('#torrent-quality'), 'quality', torrent.quality);
    renderTorrentResults();
  });

  $('#torrent-ita').addEventListener('click', (event) => {
    torrent.ita = !torrent.ita;
    event.currentTarget.setAttribute('aria-pressed', String(torrent.ita));
    renderTorrentResults();
  });

  $('#torrent-suspects').addEventListener('click', (event) => {
    torrent.hideSuspects = !torrent.hideSuspects;
    event.currentTarget.setAttribute('aria-pressed', String(torrent.hideSuspects));
    renderTorrentResults();
  });

  $('#torrent-sort').addEventListener('change', renderTorrentResults);
  $('#torrent-filter').addEventListener('input', renderTorrentResults);
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

  bindTorrentEvents();
  $('#settings-form').addEventListener('submit', submitDomain);
  $('#videos-form').addEventListener('submit', saveVideos);
  $('#nas-form').addEventListener('submit', saveNas);
  $('#nas-test').addEventListener('click', testNas);
  $$('.settings-tabs .tab').forEach((tab) => tab.addEventListener('click', () => showSettingsPanel(tab.dataset.panel)));
  $$('#category-switch .category').forEach((button) => button.addEventListener('click', () => setCategory(button.dataset.category)));
  $('#player').addEventListener('layerclose', stopPlayer);
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
      case 'torrents':
        openTorrents();
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
      // The torrent page has its own search
      const input = $('#torrent-view').hidden ? searchInput : $('#torrent-input');
      event.preventDefault();
      input.focus();
      input.select();
    }
  });

  // Closing the window stops the program, unless a download is running
  window.addEventListener('pagehide', () => {
    // A video watched until the window closes keeps its position
    saveWatching();

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
  pollTorrents();

  loadProgress();
  const status = await loadStatus();
  loadHome();

  if (!status.connected && state.category === 'sc') openSettings({ welcome: !status.domain });

  if (status.ffmpeg === false) toast('FFmpeg non trovato: i download non funzioneranno finché non lo installi', 'error');
}

init();
