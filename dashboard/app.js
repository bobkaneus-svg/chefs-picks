// ══════════════════════════════════════
// CHEFS' PICKS — App Logic v2
// ══════════════════════════════════════

let currentSort = 'score';
let activeFilters = { city: '', price: '' };
let map, markers = {}, currentScreen = 'explore';
window.restaurants = [];

// ── INIT ──
async function initApp() {
  try {
    const res = await fetch('data.json');
    if (!res.ok) throw new Error('HTTP ' + res.status);
    window.restaurants = await res.json();
  } catch (e) {
    console.error('Data load error:', e);
    window.restaurants = [];
    return;
  }

  if (window.Telegram && window.Telegram.WebApp) {
    window.Telegram.WebApp.ready();
    window.Telegram.WebApp.expand();
    try {
      window.Telegram.WebApp.setHeaderColor('#131313');
      window.Telegram.WebApp.setBackgroundColor('#131313');
    } catch (e) {}
  }

  initMap();
  showScreen('explore');

  var mapSearch = document.getElementById('map-search');
  if (mapSearch) mapSearch.addEventListener('input', onMapSearch);
  var listSearch = document.getElementById('list-search');
  if (listSearch) listSearch.addEventListener('input', function() { renderList(); });
  var chefSearch = document.getElementById('chef-search');
  if (chefSearch) chefSearch.addEventListener('input', function() { renderChefs(); });
}

document.addEventListener('DOMContentLoaded', function() {
  // Wait for Leaflet to be ready
  if (typeof L !== 'undefined') {
    initApp();
  } else {
    // Retry after Leaflet loads
    setTimeout(initApp, 500);
  }
});

// ── HELPERS ──
function escapeHtml(str) {
  if (!str) return '';
  return str.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

function escapeAttr(str) {
  if (!str) return '';
  return str.replace(/\\/g, '\\\\').replace(/'/g, "\\'").replace(/"/g, '\\"');
}

// ── DRAWER ──
function toggleDrawer() {
  var d = document.getElementById('drawer');
  var o = document.getElementById('drawer-overlay');
  var closed = d.classList.contains('-translate-x-full');
  if (closed) {
    d.classList.remove('-translate-x-full');
    d.classList.add('translate-x-0');
    o.classList.remove('hidden');
  } else {
    d.classList.add('-translate-x-full');
    d.classList.remove('translate-x-0');
    o.classList.add('hidden');
  }
}

// ── NAVIGATION ──
function showScreen(name) {
  if (name !== 'detail') {
    var detailEl = document.getElementById('screen-detail');
    if (detailEl) detailEl.classList.remove('active', 'screen-enter');
  }
  var screens = document.querySelectorAll('.screen:not(#screen-detail)');
  for (var i = 0; i < screens.length; i++) screens[i].classList.remove('active');
  var el = document.getElementById('screen-' + name);
  if (el) el.classList.add('active');
  currentScreen = name;

  var tabs = document.querySelectorAll('.nav-tab');
  for (var i = 0; i < tabs.length; i++) {
    var t = tabs[i];
    var a = t.getAttribute('data-tab') === name;
    t.className = 'nav-tab flex flex-col items-center cursor-pointer transition-all duration-300 ' +
      (a ? 'text-[#ffc66b] font-bold scale-110' : 'text-[#9d8e7c] hover:text-[#e8a838]');
    var icon = t.querySelector('.material-symbols-outlined');
    if (icon) icon.style.fontVariationSettings = a ? "'FILL' 1" : "'FILL' 0";
  }

  if (name === 'explore') setTimeout(function() { if (map) map.invalidateSize(); }, 150);
  if (name === 'discover') renderList();
  if (name === 'chefs') renderChefs();
}

// ── DETAIL ──
function showDetail(id) {
  var r = null;
  for (var i = 0; i < restaurants.length; i++) {
    if (restaurants[i].id === id) { r = restaurants[i]; break; }
  }
  if (!r) return;

  var mapsUrl = r.google_maps_url || ('https://www.google.com/maps/search/?api=1&query=' + encodeURIComponent((r.address || '') + ' ' + r.city));

  var photoHtml = r.photo_url
    ? '<img src="' + r.photo_url + '" class="w-full h-full object-cover brightness-75" alt="' + escapeHtml(r.name) + '"/>'
    : '<div class="w-full h-full bg-gradient-to-br from-surface-container-high to-surface-container-lowest flex items-center justify-center"><span class="material-symbols-outlined text-[80px] text-outline/20">restaurant</span></div>';

  var tagsHtml = '';
  if (r.tags) {
    for (var i = 0; i < r.tags.length; i++) {
      tagsHtml += '<div class="flex items-center gap-2 px-4 py-2 bg-surface-container-highest rounded-full flex-shrink-0"><div class="w-1.5 h-1.5 bg-primary rounded-full"></div><span class="text-xs font-medium uppercase tracking-[.5pt]">' + escapeHtml(r.tags[i]) + '</span></div>';
    }
  }

  var recsHtml = '';
  for (var i = 0; i < r.recommendations.length; i++) {
    var rec = r.recommendations[i];
    var badgeClass = rec.platform === 'social' ? 'badge-social' : rec.platform === 'podcast' ? 'badge-podcast' : 'badge-presse';
    var badgeLabel = rec.platform === 'social' ? 'Social' : rec.platform === 'podcast' ? 'Podcast' : 'Presse';
    var quoteHtml = rec.quote ? '<blockquote class="serif-quote text-on-surface text-lg leading-snug">"' + escapeHtml(rec.quote) + '"</blockquote>' : '';

    recsHtml += '<div class="min-w-[280px] bg-surface-container-high rounded-xl p-6 flex flex-col space-y-4 shadow-xl border border-outline-variant/5">' +
      '<div onclick="showChefDetailSafe(\'' + escapeAttr(rec.chef_name) + '\')" class="flex items-center gap-4 cursor-pointer hover:opacity-80 transition-opacity">' +
        '<div class="w-12 h-12 rounded-full bg-surface-container-highest ring-2 ring-primary/20 flex items-center justify-center flex-shrink-0"><span class="text-primary font-bold">' + rec.chef_name.charAt(0) + '</span></div>' +
        '<div><p class="font-headline font-semibold text-sm">' + escapeHtml(rec.chef_name) + '</p><p class="text-[10px] text-outline uppercase tracking-wider">' + escapeHtml(rec.chef_restaurant || '') + '</p></div>' +
      '</div>' +
      quoteHtml +
      '<div class="pt-2 flex items-center justify-between"><span class="px-2 py-1 ' + badgeClass + ' text-[10px] font-bold uppercase rounded tracking-widest">' + badgeLabel + ' — ' + escapeHtml(rec.source || '') + '</span><span class="text-[10px] text-outline">' + escapeHtml(rec.date || '') + '</span></div>' +
    '</div>';
  }

  var ratingHtml = r.rating ? '<div class="flex items-center gap-2"><span class="material-symbols-outlined text-primary text-sm" style="font-variation-settings:\'FILL\' 1">star</span><span class="text-sm text-on-surface">' + r.rating + '/5</span><span class="text-xs text-outline">(' + (r.reviews_count || 0) + ' avis)</span></div>' : '';
  var phoneHtml = r.phone ? '<a href="tel:' + r.phone + '" class="flex items-center gap-3 text-outline hover:text-primary"><span class="material-symbols-outlined text-lg">call</span><span class="text-sm">' + r.phone + '</span></a>' : '';

  document.getElementById('detail-content').innerHTML =
    '<main style="padding-bottom:calc(96px + var(--safe-bottom-raw))">' +
      '<section class="relative w-full h-[400px] overflow-hidden bg-surface-container-low">' +
        photoHtml +
        '<div class="absolute inset-0 bg-gradient-to-t from-background via-background/30 to-transparent"></div>' +
        '<button onclick="goBack()" class="absolute left-6 w-10 h-10 bg-background/60 backdrop-blur-md rounded-full flex items-center justify-center z-10" style="top:calc(24px + var(--safe-top))"><span class="material-symbols-outlined text-[#e8a838]">arrow_back</span></button>' +
        '<div class="absolute right-6 bg-background/80 backdrop-blur-md px-3 py-1.5 rounded-full flex items-center gap-2" style="top:calc(24px + var(--safe-top))"><span class="text-primary font-bold text-sm">' + r.confidence_score + '</span><span class="text-[10px] text-outline uppercase font-bold tracking-tighter">Score</span></div>' +
        '<div class="absolute bottom-16 left-6 flex flex-wrap gap-2">' +
          '<span class="px-3 py-1 bg-surface-container-highest/80 backdrop-blur-sm rounded-full text-[10px] uppercase tracking-wider text-primary border border-primary/10">' + escapeHtml(r.cuisine_type) + '</span>' +
          '<span class="px-3 py-1 bg-surface-container-highest/80 backdrop-blur-sm rounded-full text-[10px] uppercase tracking-wider text-on-surface border border-outline-variant/10">' + r.price_range + '</span>' +
          (r.vibe ? '<span class="px-3 py-1 bg-surface-container-highest/80 backdrop-blur-sm rounded-full text-[10px] uppercase tracking-wider text-on-surface border border-outline-variant/10">' + escapeHtml(r.vibe) + '</span>' : '') +
        '</div>' +
        '<h2 class="absolute bottom-4 left-6 right-6 font-headline font-extrabold text-4xl tracking-tighter text-on-surface drop-shadow-lg">' + escapeHtml(r.name) + '</h2>' +
      '</section>' +
      '<section class="px-6 mt-6 space-y-4">' +
        '<a href="' + mapsUrl + '" target="_blank" rel="noopener" class="flex items-center gap-3 text-outline hover:text-primary transition-colors group"><span class="material-symbols-outlined text-lg">location_on</span><span class="text-sm font-light tracking-wide border-b border-outline-variant/30 group-hover:border-primary/50">' + escapeHtml(r.address) + (r.address ? ', ' : '') + escapeHtml(r.city) + '</span></a>' +
        ratingHtml + phoneHtml +
        '<div class="flex gap-3 overflow-x-auto no-scrollbar pt-2">' + tagsHtml + '</div>' +
      '</section>' +
      '<section class="mt-12 bg-surface-container-low py-10">' +
        '<div class="px-6 mb-6"><h3 class="font-headline font-light text-2xl uppercase tracking-tighter">Recommandé par <span class="text-primary font-bold">' + r.recommendation_count + ' chef' + (r.recommendation_count > 1 ? 's' : '') + '</span></h3></div>' +
        '<div class="flex gap-5 overflow-x-auto no-scrollbar px-6">' + recsHtml + '</div>' +
      '</section>' +
      '<section class="px-6 mt-12 grid grid-cols-2 gap-4">' +
        '<a href="' + mapsUrl + '" target="_blank" rel="noopener" class="flex items-center justify-center gap-2 py-4 rounded-xl bg-gradient-to-tr from-primary-container to-primary text-on-primary-fixed font-bold uppercase tracking-widest text-sm active:scale-95 transition-transform shadow-lg no-underline"><span class="material-symbols-outlined">directions</span> Y ALLER</a>' +
        '<button onclick="shareResto(\'' + escapeAttr(r.id) + '\')" class="flex items-center justify-center gap-2 py-4 rounded-xl bg-surface-container-high border border-outline-variant/20 text-on-surface font-semibold uppercase tracking-widest text-sm active:scale-95 transition-transform"><span class="material-symbols-outlined">share</span> PARTAGER</button>' +
      '</section>' +
    '</main>';

  document.getElementById('screen-detail').classList.add('active', 'screen-enter');
  document.getElementById('screen-detail').scrollTop = 0;
}

function goBack() {
  document.getElementById('screen-detail').classList.remove('active', 'screen-enter');
  if (window.Telegram && window.Telegram.WebApp) {
    try { window.Telegram.WebApp.BackButton.hide(); } catch(e) {}
  }
}

function shareResto(id) {
  var r = null;
  for (var i = 0; i < restaurants.length; i++) {
    if (restaurants[i].id === id) { r = restaurants[i]; break; }
  }
  if (!r) return;
  var text = r.name + ' — ' + r.city + '\n' + r.cuisine_type + ' · ' + r.price_range + '\nRecommandé par ' + r.recommendation_count + ' chef(s)\n\n' + window.location.href;
  if (navigator.share) {
    navigator.share({ title: r.name + " — Chefs' Picks", text: text, url: window.location.href }).catch(function(){});
  } else if (navigator.clipboard) {
    navigator.clipboard.writeText(text).then(function() { alert('Lien copié !'); });
  }
}

// ── CHEF DETAIL ──
function showChefDetailSafe(chefName) {
  showChefDetail(chefName);
}

function showChefDetail(chefName) {
  var picks = [];
  for (var i = 0; i < restaurants.length; i++) {
    var r = restaurants[i];
    for (var j = 0; j < r.recommendations.length; j++) {
      if (r.recommendations[j].chef_name === chefName) {
        picks.push({ restaurant: r, recommendation: r.recommendations[j] });
      }
    }
  }
  if (!picks.length) return;

  var rec0 = picks[0].recommendation;
  var picksHtml = '';
  for (var i = 0; i < picks.length; i++) {
    var r = picks[i].restaurant;
    var rec = picks[i].recommendation;
    var imgHtml = r.photo_url
      ? '<img src="' + r.photo_url + '" class="w-full h-full object-cover" alt="' + escapeHtml(r.name) + '"/>'
      : '<span class="material-symbols-outlined text-[48px] text-outline/15">restaurant</span>';
    var quoteHtml = rec.quote ? '<p class="serif-quote text-sm text-on-surface-variant mt-3">"' + escapeHtml(rec.quote) + '"</p>' : '';

    picksHtml +=
      '<div onclick="showDetail(\'' + escapeAttr(r.id) + '\')" class="bg-surface-container-low rounded-2xl overflow-hidden cursor-pointer active:scale-[.98] transition-transform border border-outline-variant/5">' +
        '<div class="h-40 bg-surface-container-high flex items-center justify-center overflow-hidden">' + imgHtml + '</div>' +
        '<div class="p-5">' +
          '<div class="flex justify-between items-start mb-2">' +
            '<div><h4 class="font-headline font-bold text-lg">' + escapeHtml(r.name) + '</h4><p class="text-xs text-outline uppercase tracking-wider">' + escapeHtml(r.city) + ' · ' + escapeHtml(r.cuisine_type) + ' · ' + r.price_range + '</p></div>' +
            '<div class="bg-background/80 px-2 py-1 rounded-full"><span class="text-primary font-bold text-xs">' + r.confidence_score + '</span></div>' +
          '</div>' +
          quoteHtml +
        '</div>' +
      '</div>';
  }

  document.getElementById('detail-content').innerHTML =
    '<main style="padding-bottom:calc(96px + var(--safe-bottom-raw))">' +
      '<header class="sticky top-0 z-10 bg-[#131313]/80 backdrop-blur-md px-6 flex items-center gap-4" style="padding-top:calc(16px + var(--safe-top));padding-bottom:16px">' +
        '<button onclick="goBack()" class="w-10 h-10 bg-surface-container-high rounded-full flex items-center justify-center"><span class="material-symbols-outlined text-[#e8a838]">arrow_back</span></button>' +
        '<div><h1 class="font-headline font-bold text-lg">' + escapeHtml(chefName) + '</h1><p class="text-xs text-outline uppercase tracking-wider">' + escapeHtml(rec0.chef_restaurant || '') + '</p></div>' +
      '</header>' +
      '<section class="px-6 mt-6">' +
        '<div class="flex items-center gap-6 mb-8">' +
          '<div class="w-20 h-20 rounded-full bg-surface-container-highest ring-2 ring-primary/20 flex items-center justify-center flex-shrink-0"><span class="text-primary font-bold text-3xl">' + chefName.charAt(0) + '</span></div>' +
          '<div><h2 class="font-headline font-bold text-2xl">' + escapeHtml(chefName) + '</h2><p class="text-sm text-outline mt-1">' + escapeHtml(rec0.chef_restaurant || '') + '</p><p class="text-primary font-bold mt-2">' + picks.length + ' adresse' + (picks.length > 1 ? 's' : '') + ' recommandée' + (picks.length > 1 ? 's' : '') + '</p></div>' +
        '</div>' +
        '<h3 class="font-headline font-light text-xl uppercase tracking-tighter mb-6">Ses <span class="text-primary font-bold">picks</span></h3>' +
        '<div class="space-y-6">' + picksHtml + '</div>' +
      '</section>' +
    '</main>';

  document.getElementById('screen-detail').classList.add('active', 'screen-enter');
  document.getElementById('screen-detail').scrollTop = 0;
}

// ── MAP ──
var clusterGroup = null;

function initMap() {
  if (typeof L === 'undefined') { console.error('Leaflet not loaded'); return; }

  map = L.map('map', { zoomControl: false, attributionControl: false, tap: true }).setView([46.5, 2.5], 6);
  L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', { maxZoom: 19 }).addTo(map);

  // Cluster group for clean zoom behavior
  clusterGroup = L.markerClusterGroup({
    maxClusterRadius: 40,
    spiderfyOnMaxZoom: true,
    showCoverageOnHover: false,
    zoomToBoundsOnClick: true,
    disableClusteringAtZoom: 15,
    iconCreateFunction: function(cluster) {
      var count = cluster.getChildCount();
      var size = count > 20 ? 52 : count > 5 ? 44 : 36;
      var cls = count > 20 ? 'pin-hot' : count > 5 ? 'pin-warm' : 'pin-cool';
      return L.divIcon({
        className: '',
        html: '<div class="pin-wrap ' + cls + '"><div class="pin-circle" style="width:' + size + 'px;height:' + size + 'px"><span>' + count + '</span></div><div class="pin-stem"></div></div>',
        iconSize: [size, size + 12],
        iconAnchor: [size / 2, size + 12]
      });
    }
  });

  for (var i = 0; i < restaurants.length; i++) {
    var r = restaurants[i];
    if (!r.coordinates || !r.coordinates.lat || !r.coordinates.lng) continue;
    var n = r.recommendation_count || 1;
    var cls = n >= 3 ? 'pin-hot' : n >= 2 ? 'pin-warm' : 'pin-cool';
    var sz = n >= 3 ? 48 : n >= 2 ? 40 : 32;
    var icon = L.divIcon({
      className: '',
      html: '<div class="pin-wrap ' + cls + '"><div class="pin-circle" style="width:' + sz + 'px;height:' + sz + 'px"><span>' + n + '</span></div><div class="pin-stem"></div></div>',
      iconSize: [sz, sz + 12],
      iconAnchor: [sz / 2, sz + 12]
    });
    var m = L.marker([r.coordinates.lat, r.coordinates.lng], { icon: icon });
    (function(restaurant) {
      m.on('click', function(e) {
        L.DomEvent.stopPropagation(e);
        showMapPreview(restaurant);
      });
    })(r);
    markers[r.id] = m;
    clusterGroup.addLayer(m);
  }

  map.addLayer(clusterGroup);

  // Update carousel when map moves or zooms
  var carouselUpdateTimeout = null;
  map.on('moveend zoomend', function() {
    clearTimeout(carouselUpdateTimeout);
    carouselUpdateTimeout = setTimeout(function() {
      if (!carouselScrolling) updateCarousel();
    }, 300);
  });

  // Close preview when clicking empty map area
  map.on('click', function() {
    document.getElementById('map-preview').style.display = 'none';
  });

  var chefs = {};
  for (var i = 0; i < restaurants.length; i++) {
    for (var j = 0; j < restaurants[i].recommendations.length; j++) {
      chefs[restaurants[i].recommendations[j].chef_name] = true;
    }
  }
  var statsEl = document.getElementById('drawer-stats');
  if (statsEl) statsEl.textContent = restaurants.length + ' adresses · ' + Object.keys(chefs).length + ' chefs';
  buildMapFilters();
}

// ── CAROUSEL ──
var carouselItems = [];
var carouselIndex = 0;
var carouselTouchStartX = 0;
var carouselScrolling = false;

function buildPreviewCard(r) {
  var photoHtml = r.photo_url
    ? '<img src="' + r.photo_url + '" class="w-full h-full object-cover" alt="' + escapeHtml(r.name) + '"/>'
    : '<div class="w-full h-full bg-surface-container-high flex items-center justify-center"><span class="material-symbols-outlined text-[40px] text-outline/30">restaurant</span></div>';

  var chefsAvatars = '';
  var limit = Math.min(r.recommendations.length, 2);
  for (var i = 0; i < limit; i++) {
    chefsAvatars += '<div class="w-6 h-6 rounded-full bg-surface-container-highest border border-surface-container-low flex items-center justify-center"><span class="text-[9px] font-bold text-primary">' + r.recommendations[i].chef_name.charAt(0) + '</span></div>';
  }
  if (r.recommendation_count > 2) {
    chefsAvatars += '<div class="w-6 h-6 rounded-full bg-primary-container flex items-center justify-center text-[10px] font-bold text-on-primary-fixed border border-surface-container-low">+' + (r.recommendation_count - 2) + '</div>';
  }

  return '<div class="carousel-card flex-shrink-0 w-[85vw] max-w-[380px] snap-center" data-id="' + escapeHtml(r.id) + '">' +
    '<div onclick="showDetail(\'' + escapeAttr(r.id) + '\')" class="bg-surface-container-low/90 backdrop-blur-2xl rounded-3xl overflow-hidden shadow-[0_20px_50px_rgba(0,0,0,.5)] border border-outline-variant/10 flex cursor-pointer active:scale-[.98] transition-transform">' +
      '<div class="w-28 h-28 flex-shrink-0 overflow-hidden">' + photoHtml + '</div>' +
      '<div class="flex-1 p-4 flex flex-col justify-center min-w-0">' +
        '<div class="flex justify-between items-start gap-2">' +
          '<div class="min-w-0"><h2 class="text-base font-headline font-bold text-on-surface tracking-tight truncate">' + escapeHtml(r.name) + '</h2><p class="text-xs text-outline font-label uppercase tracking-widest mt-0.5 truncate">' + escapeHtml(r.cuisine_type) + ' · ' + r.price_range + '</p></div>' +
          '<span class="material-symbols-outlined text-primary flex-shrink-0 text-xl">bookmark</span>' +
        '</div>' +
        '<div class="mt-3 flex items-center gap-2">' +
          '<div class="flex -space-x-2">' + chefsAvatars + '</div>' +
          '<span class="text-[10px] font-label font-semibold text-primary uppercase tracking-tighter">Chosen by ' + r.recommendation_count + ' Chef' + (r.recommendation_count > 1 ? 's' : '') + '</span>' +
        '</div>' +
      '</div>' +
    '</div>' +
  '</div>';
}

function getVisibleRestaurants() {
  if (!map) return [];
  var bounds = map.getBounds();
  var visible = [];
  for (var i = 0; i < restaurants.length; i++) {
    var r = restaurants[i];
    if (!r.coordinates) continue;
    // Check if marker is in cluster group (not filtered out)
    if (!markers[r.id]) continue;
    if (!clusterGroup.hasLayer(markers[r.id])) continue;
    if (bounds.contains([r.coordinates.lat, r.coordinates.lng])) {
      visible.push(r);
    }
  }
  // Sort by score
  visible.sort(function(a, b) { return (b.confidence_score || 0) - (a.confidence_score || 0); });
  return visible;
}

function updateCarousel() {
  var el = document.getElementById('map-preview');
  var visible = getVisibleRestaurants();
  carouselItems = visible;

  if (visible.length === 0) {
    el.style.display = 'none';
    return;
  }

  el.style.display = 'block';

  // Dots indicator
  var dotsHtml = '';
  if (visible.length > 1 && visible.length <= 20) {
    dotsHtml = '<div class="flex justify-center gap-1.5 mt-2">';
    for (var i = 0; i < Math.min(visible.length, 10); i++) {
      dotsHtml += '<div class="carousel-dot w-1.5 h-1.5 rounded-full ' + (i === 0 ? 'bg-primary' : 'bg-outline/30') + '" data-index="' + i + '"></div>';
    }
    if (visible.length > 10) dotsHtml += '<span class="text-[9px] text-outline ml-1">+' + (visible.length - 10) + '</span>';
    dotsHtml += '</div>';
  }

  // Cards
  var cardsHtml = '';
  for (var i = 0; i < visible.length; i++) {
    cardsHtml += buildPreviewCard(visible[i]);
  }

  el.innerHTML =
    '<div class="carousel-container flex gap-3 overflow-x-auto snap-x snap-mandatory no-scrollbar pb-1" id="carousel-scroll">' +
      cardsHtml +
    '</div>' +
    dotsHtml;

  // Scroll listener to highlight pin and update dots
  var scrollEl = document.getElementById('carousel-scroll');
  if (scrollEl) {
    scrollEl.addEventListener('scroll', onCarouselScroll);
  }
}

function onCarouselScroll() {
  var scrollEl = document.getElementById('carousel-scroll');
  if (!scrollEl || carouselScrolling) return;

  var cardWidth = scrollEl.firstElementChild ? scrollEl.firstElementChild.offsetWidth + 12 : 300;
  var newIndex = Math.round(scrollEl.scrollLeft / cardWidth);
  if (newIndex === carouselIndex) return;
  carouselIndex = newIndex;

  // Update dots
  var dots = document.querySelectorAll('.carousel-dot');
  for (var i = 0; i < dots.length; i++) {
    if (i === newIndex) {
      dots[i].classList.remove('bg-outline/30');
      dots[i].classList.add('bg-primary');
    } else {
      dots[i].classList.remove('bg-primary');
      dots[i].classList.add('bg-outline/30');
    }
  }

  // Pan map to current card's restaurant
  if (carouselItems[newIndex] && carouselItems[newIndex].coordinates) {
    var r = carouselItems[newIndex];
    map.panTo([r.coordinates.lat, r.coordinates.lng], { animate: true, duration: 0.3 });
  }
}

function showMapPreview(r) {
  // Show carousel and scroll to the clicked restaurant
  updateCarousel();

  var scrollEl = document.getElementById('carousel-scroll');
  if (!scrollEl) return;

  // Find index of clicked restaurant in carousel
  var targetIndex = -1;
  for (var i = 0; i < carouselItems.length; i++) {
    if (carouselItems[i].id === r.id) { targetIndex = i; break; }
  }

  if (targetIndex >= 0) {
    var cardWidth = scrollEl.firstElementChild ? scrollEl.firstElementChild.offsetWidth + 12 : 300;
    carouselScrolling = true;
    scrollEl.scrollTo({ left: targetIndex * cardWidth, behavior: 'smooth' });
    carouselIndex = targetIndex;
    setTimeout(function() { carouselScrolling = false; }, 400);

    // Update dots
    var dots = document.querySelectorAll('.carousel-dot');
    for (var i = 0; i < dots.length; i++) {
      if (i === targetIndex) { dots[i].classList.remove('bg-outline/30'); dots[i].classList.add('bg-primary'); }
      else { dots[i].classList.remove('bg-primary'); dots[i].classList.add('bg-outline/30'); }
    }
  }

  if (map.getZoom() < 12) {
    map.setView([r.coordinates.lat, r.coordinates.lng], 14, { animate: true });
  } else {
    map.panTo([r.coordinates.lat, r.coordinates.lng], { animate: true });
  }
}

function buildMapFilters() {
  var counts = {};
  for (var i = 0; i < restaurants.length; i++) {
    var city = restaurants[i].city;
    counts[city] = (counts[city] || 0) + 1;
  }
  var entries = [];
  for (var city in counts) entries.push([city, counts[city]]);
  entries.sort(function(a, b) { return b[1] - a[1]; });
  var top = entries.slice(0, 8);

  var html = '';
  for (var i = 0; i < top.length; i++) {
    html += '<button data-city="' + escapeHtml(top[i][0]) + '" onclick="filterMapCity(this,\'' + escapeAttr(top[i][0]) + '\')" class="map-city-btn flex items-center gap-2 px-5 py-2 rounded-full bg-surface-container-highest text-on-surface-variant font-label text-xs uppercase tracking-wider whitespace-nowrap border border-outline-variant/10">' + escapeHtml(top[i][0]) + ' <span class="text-outline text-[10px]">' + top[i][1] + '</span></button>';
  }
  document.getElementById('map-filters').innerHTML = html;
}

function rebuildCluster(filterFn) {
  clusterGroup.clearLayers();
  for (var id in markers) {
    var r = null;
    for (var i = 0; i < restaurants.length; i++) { if (restaurants[i].id === id) { r = restaurants[i]; break; } }
    if (r && filterFn(r)) {
      clusterGroup.addLayer(markers[id]);
    }
  }
}

function filterMapCity(btn, city) {
  var isActive = btn.classList.contains('bg-primary-container');
  var buttons = document.querySelectorAll('.map-city-btn');
  for (var i = 0; i < buttons.length; i++) {
    buttons[i].classList.remove('bg-primary-container', 'text-on-primary-fixed', 'font-bold', 'shadow-lg');
    buttons[i].classList.add('bg-surface-container-highest', 'text-on-surface-variant');
    var cname = buttons[i].getAttribute('data-city');
    var cnt = 0;
    for (var j = 0; j < restaurants.length; j++) { if (restaurants[j].city === cname) cnt++; }
    buttons[i].innerHTML = escapeHtml(cname) + ' <span class="text-outline text-[10px]">' + cnt + '</span>';
  }

  if (isActive) {
    rebuildCluster(function() { return true; });
    map.setView([46.5, 2.5], 6);
  } else {
    btn.classList.remove('bg-surface-container-highest', 'text-on-surface-variant');
    btn.classList.add('bg-primary-container', 'text-on-primary-fixed', 'font-bold', 'shadow-lg');
    btn.innerHTML = escapeHtml(city) + ' <span class="material-symbols-outlined text-[16px]">close</span>';

    rebuildCluster(function(r) { return r.city === city; });

    var cityCoords = [];
    for (var i = 0; i < restaurants.length; i++) {
      var r = restaurants[i];
      if (r.city === city && r.coordinates) cityCoords.push([r.coordinates.lat, r.coordinates.lng]);
    }
    if (cityCoords.length > 0) {
      map.fitBounds(L.latLngBounds(cityCoords), { padding: [80, 80], maxZoom: 15 });
    }
  }
  document.getElementById('map-preview').style.display = 'none';
}

function onMapSearch(e) {
  var q = e.target.value.toLowerCase().trim();
  if (!q) {
    rebuildCluster(function() { return true; });
    map.setView([46.5, 2.5], 6);
    return;
  }

  var matching = [];
  rebuildCluster(function(r) {
    var parts = [r.name, r.city, r.country || '', r.cuisine_type];
    if (r.tags) parts = parts.concat(r.tags);
    for (var j = 0; j < r.recommendations.length; j++) parts.push(r.recommendations[j].chef_name);
    var hay = parts.join(' ').toLowerCase();
    var match = hay.indexOf(q) !== -1;
    if (match && r.coordinates) matching.push(r);
    return match;
  });

  if (matching.length > 0) {
    var bounds = L.latLngBounds(matching.map(function(r) { return [r.coordinates.lat, r.coordinates.lng]; }));
    map.fitBounds(bounds, { padding: [80, 80], maxZoom: 14 });
  }
}

// ── LIST ──
function getFiltered() {
  var qEl = document.getElementById('list-search');
  var q = qEl ? qEl.value.toLowerCase() : '';
  var results = [];

  for (var i = 0; i < restaurants.length; i++) {
    var r = restaurants[i];
    if (activeFilters.city && r.city !== activeFilters.city) continue;
    if (activeFilters.price && r.price_range !== activeFilters.price) continue;
    if (q) {
      var parts = [r.name, r.city, r.cuisine_type];
      if (r.tags) parts = parts.concat(r.tags);
      for (var j = 0; j < r.recommendations.length; j++) parts.push(r.recommendations[j].chef_name);
      if (parts.join(' ').toLowerCase().indexOf(q) === -1) continue;
    }
    results.push(r);
  }

  if (currentSort === 'score') results.sort(function(a, b) { return (b.confidence_score || 0) - (a.confidence_score || 0); });
  else if (currentSort === 'chefs') results.sort(function(a, b) { return (b.recommendation_count || 0) - (a.recommendation_count || 0); });
  else results.sort(function(a, b) { return a.name.localeCompare(b.name); });
  return results;
}

function renderList() {
  var data = getFiltered();
  var countEl = document.getElementById('list-count');
  if (countEl) countEl.textContent = data.length + ' tables';

  var sortBtns = document.querySelectorAll('.sort-btn');
  for (var i = 0; i < sortBtns.length; i++) {
    var a = sortBtns[i].getAttribute('data-sort') === currentSort;
    sortBtns[i].className = 'sort-btn px-4 py-2 rounded-full text-sm font-semibold whitespace-nowrap flex items-center gap-1 ' +
      (a ? 'bg-primary-container text-on-primary-fixed shadow-lg' : 'bg-surface-container-highest text-on-surface-variant border border-outline-variant/10');
  }

  var cities = {};
  for (var i = 0; i < restaurants.length; i++) cities[restaurants[i].city] = true;
  var cityList = Object.keys(cities).sort();

  var filterHtml = '<select onchange="activeFilters.city=this.value;renderList()" class="bg-surface-container-high border-none rounded-full px-4 py-2 text-sm text-on-surface-variant"><option value="">Toutes villes</option>';
  for (var i = 0; i < cityList.length; i++) {
    filterHtml += '<option value="' + escapeHtml(cityList[i]) + '"' + (activeFilters.city === cityList[i] ? ' selected' : '') + '>' + escapeHtml(cityList[i]) + '</option>';
  }
  filterHtml += '</select>';
  filterHtml += '<select onchange="activeFilters.price=this.value;renderList()" class="bg-surface-container-high border-none rounded-full px-4 py-2 text-sm text-on-surface-variant"><option value="">Tous prix</option><option value="€">€</option><option value="€€">€€</option><option value="€€€">€€€</option><option value="€€€€">€€€€</option></select>';
  document.getElementById('list-filters').innerHTML = filterHtml;

  var cardsHtml = '';
  var max = Math.min(data.length, 60);
  for (var i = 0; i < max; i++) {
    var r = data[i];
    var photoHtml = r.photo_url
      ? '<img src="' + r.photo_url + '" class="w-full h-full object-cover group-hover:scale-105 transition-transform duration-700" alt="' + escapeHtml(r.name) + '"/>'
      : '<div class="w-full h-full bg-gradient-to-br from-surface-container-highest to-surface-container-low flex items-center justify-center"><span class="material-symbols-outlined text-[56px] text-outline/10">restaurant</span></div>';

    var tagsHtml = '';
    if (r.tags) {
      for (var j = 0; j < Math.min(r.tags.length, 2); j++) {
        tagsHtml += '<span class="bg-primary/20 backdrop-blur-md text-primary px-3 py-1 rounded-full text-[10px] font-bold uppercase tracking-wider">' + escapeHtml(r.tags[j]) + '</span>';
      }
    }

    var chefsHtml = '';
    for (var j = 0; j < Math.min(r.recommendations.length, 2); j++) {
      chefsHtml += '<div class="w-8 h-8 rounded-full bg-surface-container-highest border-2 border-background flex items-center justify-center"><span class="text-[10px] font-bold text-primary">' + r.recommendations[j].chef_name.charAt(0) + '</span></div>';
    }
    if (r.recommendation_count > 2) {
      chefsHtml += '<div class="w-8 h-8 rounded-full bg-surface-container-high border-2 border-background flex items-center justify-center"><span class="text-[10px] font-bold">+' + (r.recommendation_count - 2) + '</span></div>';
    }

    cardsHtml +=
      '<article onclick="showDetail(\'' + escapeAttr(r.id) + '\')" class="group cursor-pointer">' +
        '<div class="relative aspect-[16/10] overflow-hidden rounded-2xl mb-4 bg-surface-container-low">' +
          photoHtml +
          '<div class="absolute top-4 right-4 bg-background/80 backdrop-blur-md px-3 py-1.5 rounded-full flex items-center gap-2"><span class="text-primary font-bold text-sm leading-none">' + r.confidence_score + '</span><span class="text-[10px] text-outline uppercase font-bold tracking-tighter">Score</span></div>' +
          '<div class="absolute bottom-4 left-4 flex gap-2">' + tagsHtml + '</div>' +
        '</div>' +
        '<div class="flex justify-between items-start">' +
          '<div><h3 class="text-2xl font-light font-headline tracking-tight text-on-surface">' + escapeHtml(r.name) + '</h3><p class="text-outline text-sm font-medium mt-0.5">' + escapeHtml(r.city) + ' · ' + escapeHtml(r.cuisine_type) + ' · ' + r.price_range + '</p></div>' +
          '<div class="flex -space-x-2">' + chefsHtml + '</div>' +
        '</div>' +
      '</article>';
  }
  document.getElementById('list-cards').innerHTML = cardsHtml;
}

function setSort(s) { currentSort = s; renderList(); }

// ── CHEFS ──
function renderChefs() {
  var cm = {};
  for (var i = 0; i < restaurants.length; i++) {
    var r = restaurants[i];
    for (var j = 0; j < r.recommendations.length; j++) {
      var rec = r.recommendations[j];
      var k = rec.chef_name;
      if (!cm[k]) cm[k] = { name: k, restaurant: rec.chef_restaurant, picks: [] };
      cm[k].picks.push({ id: r.id, name: r.name, city: r.city });
    }
  }

  var chefs = [];
  for (var k in cm) chefs.push(cm[k]);
  chefs.sort(function(a, b) { return b.picks.length - a.picks.length; });

  var qEl = document.getElementById('chef-search');
  var q = qEl ? qEl.value.toLowerCase() : '';
  if (q) {
    chefs = chefs.filter(function(c) { return c.name.toLowerCase().indexOf(q) !== -1; });
  }

  var countEl = document.getElementById('chefs-count');
  if (countEl) countEl.textContent = chefs.length + ' chefs';

  var html = '';
  for (var i = 0; i < chefs.length; i++) {
    var c = chefs[i];
    var picksHtml = '';
    for (var j = 0; j < c.picks.length; j++) {
      picksHtml += '<span class="flex-shrink-0 px-3 py-1.5 bg-surface-container-highest rounded-full text-[10px] text-on-surface-variant uppercase tracking-wider">' + escapeHtml(c.picks[j].name) + '</span>';
    }

    html +=
      '<div onclick="showChefDetailSafe(\'' + escapeAttr(c.name) + '\')" class="bg-surface-container-low rounded-xl p-5 border border-outline-variant/5 cursor-pointer active:scale-[.98] transition-transform">' +
        '<div class="flex items-center gap-4 mb-3">' +
          '<div class="w-12 h-12 rounded-full bg-surface-container-highest ring-2 ring-primary/20 flex items-center justify-center flex-shrink-0"><span class="text-primary font-bold">' + c.name.charAt(0) + '</span></div>' +
          '<div class="min-w-0 flex-1"><p class="font-headline font-semibold text-sm truncate">' + escapeHtml(c.name) + '</p><p class="text-[10px] text-outline uppercase tracking-wider truncate">' + escapeHtml(c.restaurant || '') + '</p></div>' +
          '<div class="flex-shrink-0 text-right"><span class="text-primary font-bold text-xl">' + c.picks.length + '</span><span class="text-[9px] text-outline uppercase block">pick' + (c.picks.length > 1 ? 's' : '') + '</span></div>' +
        '</div>' +
        '<div class="flex gap-2 overflow-x-auto no-scrollbar">' + picksHtml + '</div>' +
      '</div>';
  }
  document.getElementById('chefs-list').innerHTML = html;
}
