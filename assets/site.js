const reduced = matchMedia('(prefers-reduced-motion: reduce)').matches;

const supported = ['en', 'de', 'fr', 'it', 'es', 'pt-BR', 'nl', 'ja'];
const pathFor = code => code === 'en' ? '/' : `/${code.toLowerCase()}/`;

function savedLang() {
  try {
    const saved = localStorage.getItem('lang');
    return supported.includes(saved) ? saved : null;
  } catch {
    return null;
  }
}

function preferredLang() {
  for (const tag of navigator.languages) {
    const exact = supported.find(s => s.toLowerCase() === tag.toLowerCase());
    if (exact) return exact;
    const base = supported.find(s => s.split('-')[0] === tag.split('-')[0].toLowerCase());
    if (base) return base;
  }
  return 'en';
}

if (!savedLang() && document.documentElement.lang === 'en') {
  const preferred = preferredLang();
  if (preferred !== 'en') location.replace(pathFor(preferred));
}

const revealer = new IntersectionObserver(entries => {
  for (const e of entries) if (e.isIntersecting) { e.target.classList.add('in'); revealer.unobserve(e.target); }
}, { rootMargin: '0px 0px -12% 0px' });
document.querySelectorAll('.reveal, .fade').forEach(el => revealer.observe(el));

const words = document.querySelector('[data-words]');
// Japanese has no spaces between words, so it lights character by character.
const sep = words.textContent.trim().includes(' ') ? ' ' : '';
words.innerHTML = words.textContent.trim().split(sep).map(w => `<span>${w}</span>`).join(sep);
const wordSpans = [...words.children];

const steps = [...document.querySelectorAll('.step')];
const shots = [...document.querySelectorAll('.story-device img')];
const stepper = new IntersectionObserver(entries => {
  for (const e of entries) {
    if (!e.isIntersecting) continue;
    steps.forEach(s => s.classList.toggle('active', s === e.target));
    shots.forEach((img, i) => img.classList.toggle('on', i === +e.target.dataset.shot));
  }
}, { rootMargin: '-45% 0px -45% 0px' });
steps.forEach(s => stepper.observe(s));

const video = document.querySelector('.dev-phone');
new IntersectionObserver(([e]) => e.isIntersecting && !reduced ? video.play().catch(() => {}) : video.pause()).observe(video);
if (reduced) video.pause();

const hl = document.querySelector('[data-hl]');
const hlCards = [...hl.children];
const hlDots = document.querySelector('.hl-dots');
hlCards.forEach(card => {
  const dot = document.createElement('button');
  dot.type = 'button';
  dot.setAttribute('role', 'tab');
  dot.setAttribute('aria-label', card.querySelector('strong').textContent);
  dot.addEventListener('click', () => hl.scrollTo({ left: card.offsetLeft - hlCards[0].offsetLeft, behavior: reduced ? 'auto' : 'smooth' }));
  hlDots.append(dot);
});
// Several cards are visible at once, so the dot follows the leftmost one, and the last once the track ends.
function markHighlight() {
  const step = hlCards[1].offsetLeft - hlCards[0].offsetLeft;
  const atEnd = hl.scrollLeft + hl.clientWidth >= hl.scrollWidth - 2;
  const current = atEnd ? hlCards.length - 1 : Math.round(hl.scrollLeft / step);
  [...hlDots.children].forEach((d, i) => d.setAttribute('aria-selected', i === current));
}
hl.addEventListener('scroll', markHighlight, { passive: true });
markHighlight();
document.querySelectorAll('.hl-arrow').forEach(b => b.addEventListener('click', () =>
  hl.scrollBy({ left: +b.dataset.step * (hlCards[1].offsetLeft - hlCards[0].offsetLeft), behavior: reduced ? 'auto' : 'smooth' })));

// Marathon replay: points are [x, y, seconds, bpm, metres, elevation, planned seconds] in the 1350×1980 map image.
const replay = document.querySelector('[data-replay]');
const trail = replay.querySelector('.trail');
const ghost = replay.querySelector('.trail-ghost');
const runner = replay.querySelector('.runner');
const halo = replay.querySelector('.runner-halo');
const gels = replay.querySelector('.gels');
const hud = Object.fromEntries([...replay.querySelectorAll('[data-hud]')].map(el => [el.dataset.hud, el]));
let points = [], gelAt = [];

const two = n => String(Math.floor(n)).padStart(2, '0');
const clock = s => s >= 3600 ? `${Math.floor(s / 3600)}:${two(s % 3600 / 60)}:${two(s % 60)}` : `${Math.floor(s / 60)}:${two(s % 60)}`;

function drawReplay() {
  if (!points.length) return;
  const box = replay.getBoundingClientRect();
  const progress = Math.min(Math.max(-box.top / (box.height - innerHeight), 0), 1);
  const f = progress * (points.length - 1);
  const i = Math.floor(f), t = f - i;
  const a = points[i], b = points[Math.min(i + 1, points.length - 1)];
  const lerp = k => a[k] + (b[k] - a[k]) * t;
  const x = lerp(0), y = lerp(1);
  trail.setAttribute('d', 'M' + points.slice(0, i + 1).map(p => p[0] + ' ' + p[1]).join('L') + `L${x} ${y}`);
  for (const c of [runner, halo]) { c.setAttribute('cx', x); c.setAttribute('cy', y); }
  const back = points[Math.max(i - 6, 0)];
  const metres = lerp(4) - back[4], seconds = lerp(2) - back[2];
  hud.time.textContent = clock(lerp(2));
  hud.dist.textContent = (lerp(4) / 1000).toFixed(2);
  hud.pace.textContent = metres > 20 ? clock(seconds / metres * 1000) : '–';
  hud.hr.textContent = Math.round(lerp(3));
  hud.ele.textContent = Math.round(lerp(5));
  const gap = Math.round(lerp(2) - lerp(6));
  hud.pilot.textContent = clock(Math.abs(gap));
  hud.pilotWord.textContent = gap > 0 ? hud.pilotWord.dataset.behind : hud.pilotWord.dataset.ahead;
  hud.pilot.parentElement.classList.toggle('behind', gap > 0);
  gelAt.forEach((at, k) => gels.children[k].classList.toggle('taken', f >= at));
}

fetch('/assets/zurich-marathon.json')
  .then(r => r.json())
  .then(data => {
    points = data.points;
    gelAt = data.gels;
    ghost.setAttribute('d', 'M' + points.map(p => p[0] + ' ' + p[1]).join('L'));
    gels.innerHTML = gelAt.map(i => `<circle cx="${points[i][0]}" cy="${points[i][1]}" r="9"></circle>`).join('');
    drawReplay();
  });

// Insights: the phone screen scrolls through the real page; it rests on each card, then glides to the next.
const ins = document.querySelector('[data-ins]');
const insLong = ins.querySelector('.ins-long');
const insScreen = ins.querySelector('.ins-screen');
const insItems = [...ins.querySelectorAll('.ins-list li')];

function drawInsights() {
  const box = ins.getBoundingClientRect();
  const progress = Math.min(Math.max(-box.top / (box.height - innerHeight), 0), 1);
  const scale = insLong.clientWidth / insLong.getAttribute('width');
  const max = insLong.getAttribute('height') - insScreen.clientHeight / scale;
  const stops = insItems.map((li, i) => i ? Math.min(Math.max(li.dataset.at - 140, 0), max) : 0);
  const f = progress * stops.length;
  const i = Math.min(Math.floor(f), stops.length - 1);
  const k = Math.min(Math.max((f - i - .55) / .45, 0), 1);
  const y = stops[i] + (stops[Math.min(i + 1, stops.length - 1)] - stops[i]) * k * k * (3 - 2 * k);
  insLong.style.transform = `translateY(${-y * scale}px)`;
  insItems.forEach((li, j) => li.classList.toggle('on', j === i));
}
addEventListener('resize', drawInsights);

let queued = false;
addEventListener('scroll', () => {
  if (queued) return;
  queued = true;
  requestAnimationFrame(() => {
    queued = false;
    drawReplay();
    drawInsights();
    const r = words.getBoundingClientRect();
    const lit = Math.round((1 - (r.top - innerHeight * .2) / (innerHeight * .6)) * wordSpans.length);
    wordSpans.forEach((s, i) => s.classList.toggle('lit', reduced || i < lit));
  });
}, { passive: true });
dispatchEvent(new Event('scroll'));

const langBox = document.querySelector('.footer-lang');
const picker = langBox.querySelector('select');
langBox.hidden = false;
picker.value = document.documentElement.lang;
picker.addEventListener('change', () => {
  try { localStorage.setItem('lang', picker.value); } catch {}
  location.assign(pathFor(picker.value));
});
