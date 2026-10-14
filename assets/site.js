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
words.innerHTML = words.textContent.split(' ').map(w => `<span>${w}</span>`).join(' ');
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

// Run replay: track points are [x, y, seconds, bpm, metres, elevation] in the 900×1200 map image.
const replay = document.querySelector('[data-replay]');
const trail = replay.querySelector('.trail');
const ghost = replay.querySelector('.trail-ghost');
const runner = replay.querySelector('.runner');
const halo = replay.querySelector('.runner-halo');
const hud = Object.fromEntries([...replay.querySelectorAll('[data-hud]')].map(el => [el.dataset.hud, el]));
let points = [];

const clock = s => `${Math.floor(s / 60)}:${String(Math.floor(s % 60)).padStart(2, '0')}`;

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
}

fetch('/assets/lake-run.json')
  .then(r => r.json())
  .then(data => {
    points = data.points;
    ghost.setAttribute('d', 'M' + points.map(p => p[0] + ' ' + p[1]).join('L'));
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
