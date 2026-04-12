// ══════════════════════════════════════
// CHEFS' PICKS — App Logic
// ══════════════════════════════════════

let currentSort = 'score';
let activeFilters = { city: '', price: '' };
let map, markers = {}, currentScreen = 'explore';

// ── INIT ──
document.addEventListener('DOMContentLoaded', async () => {
  // Load data
  try {
    const res = await fetch('data.json');
    window.restaurants = await res.json();
  } catch (e) {
    console.error('Data load error:', e);
    window.restaurants = [];
  }

  // Telegram Web App
  if (window.Telegram?.WebApp) {
    window.Telegram.WebApp.ready();
    window.Telegram.WebApp.expand();
    window.Telegram.WebApp.setHeaderColor('#131313');
    window.Telegram.WebApp.setBackgroundColor('#131313');
  }

  initMap();
  showScreen('explore');

  // Search listeners
  document.getElementById('map-search')?.addEventListener('input', onMapSearch);
  document.getElementById('list-search')?.addEventListener('input', () => renderList());
  document.getElementById('chef-search')?.addEventListener('input', () => renderChefs());
});

// ── DRAWER ──
function toggleDrawer() {
  const d = document.getElementById('drawer'), o = document.getElementById('drawer-overlay');
  const closed = d.classList.contains('-translate-x-full');
  d.classList.toggle('-translate-x-full', !closed);
  d.classList.toggle('translate-x-0', closed);
  o.classList.toggle('hidden', !closed);
}

// ── NAVIGATION ──
function showScreen(name) {
  // Close detail first if going to main screen
  if (name !== 'detail') {
    document.getElementById('screen-detail').classList.remove('active', 'screen-enter');
  }
  document.querySelectorAll('.screen:not(#screen-detail)').forEach(s => s.classList.remove('active'));
  const el = document.getElementById('screen-' + name);
  if (el) el.classList.add('active');
  currentScreen = name;

  // Update nav tabs
  document.querySelectorAll('.nav-tab').forEach(t => {
    const a = t.dataset.tab === name;
    t.className = `nav-tab flex flex-col items-center cursor-pointer transition-all duration-300 ${a ? 'text-[#ffc66b] font-bold scale-110' : 'text-[#9d8e7c] hover:text-[#e8a838]'}`;
    const icon = t.querySelector('.material-symbols-outlined');
    if (icon) icon.style.fontVariationSettings = a ? "'FILL' 1" : "'FILL' 0";
  });

  if (name === 'explore') setTimeout(() => map?.invalidateSize(), 100);
  if (name === 'discover') renderList();
  if (name === 'chefs') renderChefs();
}

// ── DETAIL ──
function showDetail(id) {
  const r = restaurants.find(x => x.id === id);
  if (!r) return;
  const pc = p => p === 'social' ? 'badge-social' : p === 'podcast' ? 'badge-podcast' : 'badge-presse';
  const pl = p => p === 'social' ? 'Social' : p === 'podcast' ? 'Podcast' : 'Presse';
  const mapsUrl = `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(r.address + ' ' + r.city)}`;
  const photoHtml = r.photo_url
    ? `<img src="${r.photo_url}" class="w-full h-full object-cover brightness-75" alt="${r.name}"/>`
    : `<div class="w-full h-full bg-gradient-to-br from-surface-container-high to-surface-container-lowest flex items-center justify-center"><span class="material-symbols-outlined text-[80px] text-outline/20">restaurant</span></div>`;

  document.getElementById('detail-content').innerHTML = `
    <main class="pb-28">
      <section class="relative w-full h-[400px] overflow-hidden bg-surface-container-low">
        ${photoHtml}
        <div class="absolute inset-0 bg-gradient-to-t from-background via-background/30 to-transparent"></div>
        <button onclick="goBack()" class="absolute top-6 left-6 w-10 h-10 bg-background/60 backdrop-blur-md rounded-full flex items-center justify-center z-10">
          <span class="material-symbols-outlined text-[#e8a838]">arrow_back</span>
        </button>
        <div class="absolute top-6 right-6 bg-background/80 backdrop-blur-md px-3 py-1.5 rounded-full flex items-center gap-2">
          <span class="text-primary font-bold text-sm">${r.confidence_score}</span>
          <span class="text-[10px] text-outline uppercase font-bold tracking-tighter">Score</span>
        </div>
        <div class="absolute bottom-16 left-6 flex flex-wrap gap-2">
          <span class="px-3 py-1 bg-surface-container-highest/80 backdrop-blur-sm rounded-full text-[10px] uppercase tracking-wider text-primary border border-primary/10">${r.cuisine_type}</span>
          <span class="px-3 py-1 bg-surface-container-highest/80 backdrop-blur-sm rounded-full text-[10px] uppercase tracking-wider text-on-surface border border-outline-variant/10">${r.price_range}</span>
          ${r.vibe ? `<span class="px-3 py-1 bg-surface-container-highest/80 backdrop-blur-sm rounded-full text-[10px] uppercase tracking-wider text-on-surface border border-outline-variant/10">${r.vibe}</span>` : ''}
        </div>
        <h2 class="absolute bottom-4 left-6 right-6 font-headline font-extrabold text-4xl tracking-tighter text-on-surface drop-shadow-lg">${r.name}</h2>
      </section>

      <section class="px-6 mt-6 space-y-4">
        <a href="${mapsUrl}" target="_blank" rel="noopener" class="flex items-center gap-3 text-outline hover:text-primary transition-colors group">
          <span class="material-symbols-outlined text-lg">location_on</span>
          <span class="text-sm font-light tracking-wide border-b border-outline-variant/30 group-hover:border-primary/50">${r.address}${r.address ? ', ' : ''}${r.city}</span>
        </a>
        ${r.rating ? `<div class="flex items-center gap-2"><span class="material-symbols-outlined text-primary text-sm" style="font-variation-settings:'FILL' 1">star</span><span class="text-sm text-on-surface">${r.rating}/5</span><span class="text-xs text-outline">(${r.reviews_count || 0} avis)</span></div>` : ''}
        ${r.phone ? `<a href="tel:${r.phone}" class="flex items-center gap-3 text-outline hover:text-primary"><span class="material-symbols-outlined text-lg">call</span><span class="text-sm">${r.phone}</span></a>` : ''}
        <div class="flex gap-3 overflow-x-auto no-scrollbar pt-2">
          ${(r.tags || []).map(t => `<div class="flex items-center gap-2 px-4 py-2 bg-surface-container-highest rounded-full flex-shrink-0"><div class="w-1.5 h-1.5 bg-primary rounded-full"></div><span class="text-xs font-medium uppercase tracking-[.5pt]">${t}</span></div>`).join('')}
        </div>
      </section>

      <section class="mt-12 bg-surface-container-low py-10">
        <div class="px-6 mb-6"><h3 class="font-headline font-light text-2xl uppercase tracking-tighter">Recommandé par <span class="text-primary font-bold">${r.recommendation_count} chef${r.recommendation_count > 1 ? 's' : ''}</span></h3></div>
        <div class="flex gap-5 overflow-x-auto no-scrollbar px-6">
          ${r.recommendations.map(rec => `
            <div class="min-w-[280px] bg-surface-container-high rounded-xl p-6 flex flex-col space-y-4 shadow-xl border border-outline-variant/5">
              <div onclick="showChefDetail('${rec.chef_name.replace(/'/g, "\\'")}')" class="flex items-center gap-4 cursor-pointer hover:opacity-80 transition-opacity">
                <div class="w-12 h-12 rounded-full bg-surface-container-highest ring-2 ring-primary/20 flex items-center justify-center flex-shrink-0">
                  <span class="text-primary font-bold">${rec.chef_name.charAt(0)}</span>
                </div>
                <div><p class="font-headline font-semibold text-sm">${rec.chef_name}</p><p class="text-[10px] text-outline uppercase tracking-wider">${rec.chef_restaurant || ''}</p></div>
              </div>
              ${rec.quote ? `<blockquote class="serif-quote text-on-surface text-lg leading-snug">"${rec.quote}"</blockquote>` : ''}
              <div class="pt-2 flex items-center justify-between">
                <span class="px-2 py-1 ${pc(rec.platform)} text-[10px] font-bold uppercase rounded tracking-widest">${pl(rec.platform)} — ${rec.source || ''}</span>
                <span class="text-[10px] text-outline">${rec.date || ''}</span>
              </div>
            </div>
          `).join('')}
        </div>
      </section>

      <section class="px-6 mt-12 grid grid-cols-2 gap-4">
        <a href="${mapsUrl}" target="_blank" rel="noopener" class="flex items-center justify-center gap-2 py-4 rounded-xl bg-gradient-to-tr from-primary-container to-primary text-on-primary-fixed font-bold uppercase tracking-widest text-sm active:scale-95 transition-transform shadow-lg no-underline">
          <span class="material-symbols-outlined">directions</span> Y ALLER
        </a>
        <button onclick="shareResto('${r.id}')" class="flex items-center justify-center gap-2 py-4 rounded-xl bg-surface-container-high border border-outline-variant/20 text-on-surface font-semibold uppercase tracking-widest text-sm active:scale-95 transition-transform">
          <span class="material-symbols-outlined">share</span> PARTAGER
        </button>
      </section>
    </main>`;

  document.getElementById('screen-detail').classList.add('active', 'screen-enter');
  document.getElementById('screen-detail').scrollTop = 0;
}

function goBack() {
  document.getElementById('screen-detail').classList.remove('active', 'screen-enter');
  if (window.Telegram?.WebApp) window.Telegram.WebApp.BackButton.hide();
}

function shareResto(id) {
  const r = restaurants.find(x => x.id === id);
  if (!r) return;
  const text = `🍽 ${r.name} — ${r.city}\n${r.cuisine_type} · ${r.price_range}\nRecommandé par ${r.recommendation_count} chef(s)\n\n${window.location.href}`;
  if (navigator.share) {
    navigator.share({ title: r.name + " — Chefs' Picks", text, url: window.location.href });
  } else {
    navigator.clipboard?.writeText(text);
    alert('Lien copié !');
  }
}

// ── CHEF DETAIL ──
function showChefDetail(chefName) {
  const picks = [];
  restaurants.forEach(r => {
    r.recommendations.forEach(rec => {
      if (rec.chef_name === chefName) {
        picks.push({ restaurant: r, recommendation: rec });
      }
    });
  });
  if (!picks.length) return;

  const rec0 = picks[0].recommendation;
  document.getElementById('detail-content').innerHTML = `
    <main class="pb-28">
      <header class="sticky top-0 z-10 bg-[#131313]/80 backdrop-blur-md px-6 py-4 flex items-center gap-4">
        <button onclick="goBack()" class="w-10 h-10 bg-surface-container-high rounded-full flex items-center justify-center">
          <span class="material-symbols-outlined text-[#e8a838]">arrow_back</span>
        </button>
        <div>
          <h1 class="font-headline font-bold text-lg">${chefName}</h1>
          <p class="text-xs text-outline uppercase tracking-wider">${rec0.chef_restaurant || ''}</p>
        </div>
      </header>

      <section class="px-6 mt-6">
        <div class="flex items-center gap-6 mb-8">
          <div class="w-20 h-20 rounded-full bg-surface-container-highest ring-2 ring-primary/20 flex items-center justify-center flex-shrink-0">
            <span class="text-primary font-bold text-3xl">${chefName.charAt(0)}</span>
          </div>
          <div>
            <h2 class="font-headline font-bold text-2xl">${chefName}</h2>
            <p class="text-sm text-outline mt-1">${rec0.chef_restaurant || ''}</p>
            <p class="text-primary font-bold mt-2">${picks.length} adresse${picks.length > 1 ? 's' : ''} recommandée${picks.length > 1 ? 's' : ''}</p>
          </div>
        </div>

        <h3 class="font-headline font-light text-xl uppercase tracking-tighter mb-6">Ses <span class="text-primary font-bold">picks</span></h3>

        <div class="space-y-6">
          ${picks.map(({ restaurant: r, recommendation: rec }) => `
            <div onclick="showDetail('${r.id}')" class="bg-surface-container-low rounded-2xl overflow-hidden cursor-pointer active:scale-[.98] transition-transform border border-outline-variant/5">
              <div class="h-40 bg-surface-container-high flex items-center justify-center">
                ${r.photo_url ? `<img src="${r.photo_url}" class="w-full h-full object-cover" alt="${r.name}"/>` : `<span class="material-symbols-outlined text-[48px] text-outline/15">restaurant</span>`}
              </div>
              <div class="p-5">
                <div class="flex justify-between items-start mb-2">
                  <div>
                    <h4 class="font-headline font-bold text-lg">${r.name}</h4>
                    <p class="text-xs text-outline uppercase tracking-wider">${r.city} · ${r.cuisine_type} · ${r.price_range}</p>
                  </div>
                  <div class="bg-background/80 px-2 py-1 rounded-full"><span class="text-primary font-bold text-xs">${r.confidence_score}</span></div>
                </div>
                ${rec.quote ? `<p class="serif-quote text-sm text-on-surface-variant mt-3">"${rec.quote}"</p>` : ''}
              </div>
            </div>
          `).join('')}
        </div>
      </section>
    </main>`;

  document.getElementById('screen-detail').classList.add('active', 'screen-enter');
  document.getElementById('screen-detail').scrollTop = 0;
}

// ── MAP ──
function initMap() {
  map = L.map('map', { zoomControl: false, attributionControl: false }).setView([46.5, 2.5], 6);
  L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', { maxZoom: 19 }).addTo(map);

  restaurants.forEach(r => {
    if (!r.coordinates) return;
    const n = r.recommendation_count;
    const cls = n >= 3 ? 'pin-hot' : n >= 2 ? 'pin-warm' : 'pin-cool';
    const sz = n >= 3 ? 48 : n >= 2 ? 40 : 32;
    const icon = L.divIcon({
      className: '',
      html: `<div class="pin-wrap ${cls}"><div class="pin-circle" style="width:${sz}px;height:${sz}px"><span>${n}</span></div><div class="pin-stem"></div></div>`,
      iconSize: [sz, sz + 12],
      iconAnchor: [sz / 2, sz + 12]
    });
    const m = L.marker([r.coordinates.lat, r.coordinates.lng], { icon }).addTo(map);
    m.on('click', () => showMapPreview(r));
    markers[r.id] = m;
  });

  // Stats
  const chefs = new Set();
  restaurants.forEach(r => r.recommendations.forEach(rec => chefs.add(rec.chef_name)));
  const statsEl = document.getElementById('drawer-stats');
  if (statsEl) statsEl.textContent = `${restaurants.length} adresses · ${chefs.size} chefs`;
  buildMapFilters();
}

function showMapPreview(r) {
  const el = document.getElementById('map-preview');
  el.style.display = 'block';
  const photoHtml = r.photo_url
    ? `<img src="${r.photo_url}" class="w-full h-full object-cover" alt="${r.name}"/>`
    : `<div class="w-full h-full bg-surface-container-high flex items-center justify-center"><span class="material-symbols-outlined text-[40px] text-outline/30">restaurant</span></div>`;

  el.innerHTML = `
    <div onclick="showDetail('${r.id}')" class="bg-surface-container-low/90 backdrop-blur-2xl rounded-3xl overflow-hidden shadow-[0_20px_50px_rgba(0,0,0,.5)] border border-outline-variant/10 flex cursor-pointer active:scale-[.98] transition-transform">
      <div class="w-32 h-32 flex-shrink-0 overflow-hidden">${photoHtml}</div>
      <div class="flex-1 p-5 flex flex-col justify-center">
        <div class="flex justify-between items-start">
          <div>
            <h2 class="text-lg font-headline font-bold text-on-surface tracking-tight">${r.name}</h2>
            <p class="text-sm text-outline font-label uppercase tracking-widest mt-1">${r.cuisine_type} · ${r.price_range}</p>
          </div>
          <button class="text-primary"><span class="material-symbols-outlined">bookmark</span></button>
        </div>
        <div class="mt-4 flex items-center gap-3">
          <div class="flex -space-x-2">
            ${r.recommendations.slice(0, 2).map(rec => `<div class="w-6 h-6 rounded-full bg-surface-container-highest border border-surface-container-low flex items-center justify-center"><span class="text-[9px] font-bold text-primary">${rec.chef_name.charAt(0)}</span></div>`).join('')}
            ${r.recommendation_count > 2 ? `<div class="w-6 h-6 rounded-full bg-primary-container flex items-center justify-center text-[10px] font-bold text-on-primary-fixed border border-surface-container-low">+${r.recommendation_count - 2}</div>` : ''}
          </div>
          <span class="text-xs font-label font-semibold text-primary uppercase tracking-tighter">Chosen by ${r.recommendation_count} Chef${r.recommendation_count > 1 ? 's' : ''}</span>
        </div>
      </div>
    </div>`;
  map.setView([r.coordinates.lat, r.coordinates.lng], 14, { animate: true });
}

function buildMapFilters() {
  const counts = {};
  restaurants.forEach(r => { counts[r.city] = (counts[r.city] || 0) + 1; });
  const top = Object.entries(counts).sort((a, b) => b[1] - a[1]).slice(0, 6);
  document.getElementById('map-filters').innerHTML = top.map(([c, n]) =>
    `<button onclick="filterMapCity(this,'${c}')" class="map-city-btn flex items-center gap-2 px-5 py-2 rounded-full bg-surface-container-highest text-on-surface-variant font-label text-xs uppercase tracking-wider whitespace-nowrap border border-outline-variant/10">${c} <span class="text-outline text-[10px]">${n}</span></button>`
  ).join('');
}

function filterMapCity(btn, city) {
  const isActive = btn.classList.contains('bg-primary-container');
  // Reset all buttons
  document.querySelectorAll('.map-city-btn').forEach(b => {
    b.classList.remove('bg-primary-container', 'text-on-primary-fixed', 'font-bold', 'shadow-lg');
    b.classList.add('bg-surface-container-highest', 'text-on-surface-variant', 'border', 'border-outline-variant/10');
    const cityName = b.textContent.trim().split(/\s+/)[0];
    const count = restaurants.filter(r => r.city === cityName).length;
    b.innerHTML = `${cityName} <span class="text-outline text-[10px]">${count}</span>`;
  });

  if (isActive) {
    Object.values(markers).forEach(m => m.addTo(map));
    map.setView([46.5, 2.5], 6);
  } else {
    btn.classList.remove('bg-surface-container-highest', 'text-on-surface-variant');
    btn.classList.add('bg-primary-container', 'text-on-primary-fixed', 'font-bold', 'shadow-lg');
    btn.innerHTML = `${city} <span class="material-symbols-outlined text-[16px]">close</span>`;

    const cityRestos = restaurants.filter(r => r.city === city && r.coordinates);
    Object.entries(markers).forEach(([id, m]) => {
      const r = restaurants.find(x => x.id === id);
      if (r?.city === city) m.addTo(map);
      else map.removeLayer(m);
    });
    if (cityRestos.length) {
      map.fitBounds(L.latLngBounds(cityRestos.map(r => [r.coordinates.lat, r.coordinates.lng])), { padding: [80, 80], maxZoom: 14 });
    }
  }
  document.getElementById('map-preview').style.display = 'none';
}

function onMapSearch(e) {
  const q = e.target.value.toLowerCase().trim();
  if (!q) {
    Object.values(markers).forEach(m => m.addTo(map));
    map.setView([46.5, 2.5], 6);
    return;
  }

  const matching = [];
  restaurants.forEach(r => {
    const hay = [r.name, r.city, r.country, r.cuisine_type, ...(r.tags || []),
      ...r.recommendations.map(x => x.chef_name)].join(' ').toLowerCase();
    if (hay.includes(q)) {
      if (markers[r.id]) markers[r.id].addTo(map);
      if (r.coordinates) matching.push(r);
    } else {
      if (markers[r.id]) map.removeLayer(markers[r.id]);
    }
  });

  // Zoom to results
  if (matching.length > 0) {
    const bounds = L.latLngBounds(matching.map(r => [r.coordinates.lat, r.coordinates.lng]));
    map.fitBounds(bounds, { padding: [80, 80], maxZoom: 14 });
  }
}

// ── LIST ──
function getFiltered() {
  const q = document.getElementById('list-search')?.value.toLowerCase() || '';
  let d = restaurants.filter(r => {
    if (activeFilters.city && r.city !== activeFilters.city) return false;
    if (activeFilters.price && r.price_range !== activeFilters.price) return false;
    if (q) {
      const h = [r.name, r.city, r.cuisine_type, ...(r.tags || []),
        ...r.recommendations.map(x => x.chef_name)].join(' ').toLowerCase();
      if (!h.includes(q)) return false;
    }
    return true;
  });
  if (currentSort === 'score') d.sort((a, b) => b.confidence_score - a.confidence_score);
  else if (currentSort === 'chefs') d.sort((a, b) => b.recommendation_count - a.recommendation_count);
  else d.sort((a, b) => a.name.localeCompare(b.name));
  return d;
}

function renderList() {
  const data = getFiltered();
  document.getElementById('list-count').textContent = data.length + ' tables';

  document.querySelectorAll('.sort-btn').forEach(b => {
    const a = b.dataset.sort === currentSort;
    b.className = `sort-btn px-4 py-2 rounded-full text-sm font-semibold whitespace-nowrap flex items-center gap-1 ${a ? 'bg-primary-container text-on-primary-fixed shadow-lg' : 'bg-surface-container-highest text-on-surface-variant border border-outline-variant/10'}`;
  });

  const cities = [...new Set(restaurants.map(r => r.city))].sort();
  document.getElementById('list-filters').innerHTML = `
    <select onchange="activeFilters.city=this.value;renderList()" class="bg-surface-container-high border-none rounded-full px-4 py-2 text-sm text-on-surface-variant">
      <option value="">Toutes villes</option>${cities.map(c => `<option value="${c}"${activeFilters.city === c ? ' selected' : ''}>${c}</option>`).join('')}
    </select>
    <select onchange="activeFilters.price=this.value;renderList()" class="bg-surface-container-high border-none rounded-full px-4 py-2 text-sm text-on-surface-variant">
      <option value="">Tous prix</option><option value="€">€</option><option value="€€">€€</option><option value="€€€">€€€</option><option value="€€€€">€€€€</option>
    </select>`;

  document.getElementById('list-cards').innerHTML = data.slice(0, 60).map(r => {
    const photoHtml = r.photo_url
      ? `<img src="${r.photo_url}" class="w-full h-full object-cover group-hover:scale-105 transition-transform duration-700" alt="${r.name}"/>`
      : `<div class="w-full h-full bg-gradient-to-br from-surface-container-highest to-surface-container-low flex items-center justify-center group-hover:scale-105 transition-transform duration-700"><span class="material-symbols-outlined text-[56px] text-outline/10">restaurant</span></div>`;
    return `
    <article onclick="showDetail('${r.id}')" class="group cursor-pointer">
      <div class="relative aspect-[16/10] overflow-hidden rounded-2xl mb-4 bg-surface-container-low">
        ${photoHtml}
        <div class="absolute top-4 right-4 bg-background/80 backdrop-blur-md px-3 py-1.5 rounded-full flex items-center gap-2">
          <span class="text-primary font-bold text-sm leading-none">${r.confidence_score}</span>
          <span class="text-[10px] text-outline uppercase font-bold tracking-tighter">Score</span>
        </div>
        <div class="absolute bottom-4 left-4 flex gap-2">
          ${(r.tags || []).slice(0, 2).map(t => `<span class="bg-primary/20 backdrop-blur-md text-primary px-3 py-1 rounded-full text-[10px] font-bold uppercase tracking-wider">${t}</span>`).join('')}
        </div>
      </div>
      <div class="flex justify-between items-start">
        <div>
          <h3 class="text-2xl font-light font-headline tracking-tight text-on-surface">${r.name}</h3>
          <p class="text-outline text-sm font-medium mt-0.5">${r.city} · ${r.cuisine_type} · ${r.price_range}</p>
        </div>
        <div class="flex -space-x-2">
          ${r.recommendations.slice(0, 2).map(rec => `<div class="w-8 h-8 rounded-full bg-surface-container-highest border-2 border-background flex items-center justify-center"><span class="text-[10px] font-bold text-primary">${rec.chef_name.charAt(0)}</span></div>`).join('')}
          ${r.recommendation_count > 2 ? `<div class="w-8 h-8 rounded-full bg-surface-container-high border-2 border-background flex items-center justify-center"><span class="text-[10px] font-bold">+${r.recommendation_count - 2}</span></div>` : ''}
        </div>
      </div>
    </article>`;
  }).join('');
}

function setSort(s) { currentSort = s; renderList(); }

// ── CHEFS ──
function renderChefs() {
  const cm = {};
  restaurants.forEach(r => r.recommendations.forEach(rec => {
    const k = rec.chef_name;
    if (!cm[k]) cm[k] = { name: k, restaurant: rec.chef_restaurant, picks: [] };
    cm[k].picks.push({ id: r.id, name: r.name, city: r.city });
  }));
  let chefs = Object.values(cm).sort((a, b) => b.picks.length - a.picks.length);
  const q = document.getElementById('chef-search')?.value.toLowerCase() || '';
  if (q) chefs = chefs.filter(c => c.name.toLowerCase().includes(q));

  document.getElementById('chefs-count').textContent = chefs.length + ' chefs';
  document.getElementById('chefs-list').innerHTML = chefs.map(c => `
    <div onclick="showChefDetail('${c.name.replace(/'/g, "\\'")}')" class="bg-surface-container-low rounded-xl p-5 border border-outline-variant/5 cursor-pointer active:scale-[.98] transition-transform">
      <div class="flex items-center gap-4 mb-3">
        <div class="w-12 h-12 rounded-full bg-surface-container-highest ring-2 ring-primary/20 flex items-center justify-center flex-shrink-0">
          <span class="text-primary font-bold">${c.name.charAt(0)}</span>
        </div>
        <div class="min-w-0 flex-1">
          <p class="font-headline font-semibold text-sm truncate">${c.name}</p>
          <p class="text-[10px] text-outline uppercase tracking-wider truncate">${c.restaurant || ''}</p>
        </div>
        <div class="flex-shrink-0 text-right">
          <span class="text-primary font-bold text-xl">${c.picks.length}</span>
          <span class="text-[9px] text-outline uppercase block">pick${c.picks.length > 1 ? 's' : ''}</span>
        </div>
      </div>
      <div class="flex gap-2 overflow-x-auto no-scrollbar">
        ${c.picks.map(p => `<span class="flex-shrink-0 px-3 py-1.5 bg-surface-container-highest rounded-full text-[10px] text-on-surface-variant uppercase tracking-wider">${p.name}</span>`).join('')}
      </div>
    </div>`).join('');
}
</script>
