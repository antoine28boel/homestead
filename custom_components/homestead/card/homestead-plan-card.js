// Homestead: the garden plan, drawn for a dashboard.
//
// The plan comes from the integration (homestead/plan/subscribe) and is
// drawn in metres. It follows the season, the weather and the time of day;
// plants grow with their stage. Tapping a space or a crop opens its entity.

const STRINGS = {
  en: {
    name: "Garden plan",
    description: "The Homestead plan, with the season, the weather and the crops.",
    spring: "Spring",
    summer: "Summer",
    autumn: "Autumn",
    winter: "Winter",
    night: "night",
    no_plan: "Draw the plan of your garden in the Homestead app to see it here.",
    not_found: "No Homestead garden is set up.",
    error: "The garden plan could not be loaded.",
    loading: "Loading the garden…",
    tasks: (count) => (count === 1 ? "1 task due" : `${count} tasks due`),
    planned: "planned",
    title: "Title",
    weather: "Weather",
    entry: "Garden",
  },
  fr: {
    name: "Plan du jardin",
    description: "Le plan Homestead, avec la saison, la météo et les cultures.",
    spring: "Printemps",
    summer: "Été",
    autumn: "Automne",
    winter: "Hiver",
    night: "nuit",
    no_plan: "Dessinez le plan de votre jardin dans l'application Homestead pour le voir ici.",
    not_found: "Aucun jardin Homestead n'est configuré.",
    error: "Le plan du jardin n'a pas pu être chargé.",
    loading: "Chargement du jardin…",
    tasks: (count) => (count === 1 ? "1 tâche à faire" : `${count} tâches à faire`),
    planned: "prévu",
    title: "Titre",
    weather: "Météo",
    entry: "Jardin",
  },
};

function strings(hass) {
  const language = (hass?.locale?.language || hass?.language
    || document.documentElement.lang || navigator.language || "en").split("-")[0];
  return STRINGS[language] || STRINGS.en;
}

// Leaves and fruits by botanical family; the app uses the same fruit colours.
const FOLIAGE = {
  solanaceae: "#4f8f3a",
  cucurbitaceae: "#5f9e3f",
  brassicaceae: "#6f9c8c",
  fabaceae: "#5a9a42",
  amaryllidaceae: "#8bb04a",
  apiaceae: "#6aa84f",
  amaranthaceae: "#4f8a3c",
  asteraceae: "#9ccc65",
  lamiaceae: "#56874a",
  poaceae: "#7fa83f",
  caprifoliaceae: "#3f7a2c",
};
const FRUIT = {
  solanaceae: "#e53935",
  cucurbitaceae: "#f9a825",
  brassicaceae: "#dcedc8",
  fabaceae: "#9ccc65",
  amaryllidaceae: "#f3e5f5",
  apiaceae: "#ff7043",
  amaranthaceae: "#ad1457",
  asteraceae: "#e6ee9c",
  lamiaceae: "#9575cd",
  poaceae: "#fdd835",
  caprifoliaceae: "#7cb342",
};
const FLOWERING = { solanaceae: "#fdd835", cucurbitaceae: "#ffca28", fabaceae: "#ffffff" };
const GLYPH = {
  solanaceae: "bush",
  cucurbitaceae: "vine",
  brassicaceae: "cabbage",
  fabaceae: "legume",
  amaryllidaceae: "allium",
  apiaceae: "feather",
  amaranthaceae: "chard",
  asteraceae: "lettuce",
  lamiaceae: "herb",
  poaceae: "grass",
};
// Share of its full size a plant has reached at each stage.
const GROWTH = {
  planned: 0.25,
  sown: 0.3,
  transplanted: 0.5,
  growing: 0.8,
  harvesting: 1,
  finished: 0.85,
};
const SPACE_SOIL = {
  bed: "#9a7356",
  raised_bed: "#86654f",
  greenhouse: "#9a7356",
  container: "#8a6a52",
};
const SPACE_EDGE = {
  bed: { colour: "#6d4c41", width: 0.04 },
  raised_bed: { colour: "#b08a5a", width: 0.1 },
  greenhouse: { colour: "#4a90c2", width: 0.08 },
  container: { colour: "#c0703f", width: 0.06 },
};
const GROUND = {
  spring: "#a9d27f",
  summer: "#a0c46c",
  autumn: "#b4b36e",
  winter: "#aab59c",
};
const CANOPY = {
  spring: ["#7cb342", "#8bc34a", "#689f38"],
  summer: ["#4f8a3c", "#5d9b45", "#447a33"],
  autumn: ["#e65100", "#f9a825", "#c62828", "#ef6c00"],
  winter: [],
};
// Plants that sway in the wind, at most (tablets keep cool); crops of many
// small plants keep still.
const MAX_ANIMATED = 700;
const MAX_ANIMATED_CROP = 200;
// Mean rain or snow drops falling over the plan.
const DROPS = { 1: 45, 2: 90 };

let instances = 0;

function escape(text) {
  return String(text ?? "").replace(
    /[&<>"']/g,
    (char) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[char],
  );
}

// The same "random" numbers on every drawing, so nothing jumps around.
function noise(...values) {
  let hash = 2166136261;
  for (const value of values.join("|")) {
    hash ^= value.charCodeAt(0);
    hash = Math.imul(hash, 16777619);
  }
  return ((hash >>> 0) % 10000) / 10000;
}

function n(value) {
  return Math.round(value * 1000) / 1000;
}

// Whether a point of the plan lies within a (turned) shape.
function inside(shape, [x, y]) {
  const angle = (-(shape.rotation || 0) * Math.PI) / 180;
  const dx = x - shape.x - shape.width / 2;
  const dy = y - shape.y - shape.height / 2;
  const lx = dx * Math.cos(angle) - dy * Math.sin(angle);
  const ly = dx * Math.sin(angle) + dy * Math.cos(angle);
  return Math.abs(lx) <= shape.width / 2 && Math.abs(ly) <= shape.height / 2;
}

function shapeTransform(shape) {
  const rotation = shape.rotation || 0;
  return `translate(${n(shape.x)} ${n(shape.y)})` +
    (rotation ? ` rotate(${rotation} ${n(shape.width / 2)} ${n(shape.height / 2)})` : "");
}

function fitLabel(name, widthPx, fontSize) {
  const room = Math.max(widthPx + 40, 64);
  const fits = (text) => text.length * fontSize * 0.55 <= room;
  if (fits(name)) return name;
  const short = name.split(/\s+[-–·]\s+/).pop();
  if (fits(short)) return short;
  const letters = Math.max(3, Math.floor(room / (fontSize * 0.55)) - 1);
  return `${short.slice(0, letters)}…`;
}

function seasonOf(today, latitude) {
  const month = Number((today || new Date().toISOString()).slice(5, 7));
  const north = ["winter", "winter", "spring", "spring", "spring", "summer",
    "summer", "summer", "autumn", "autumn", "autumn", "winter"][month - 1];
  if ((latitude ?? 0) >= 0) return north;
  return { winter: "summer", summer: "winter", spring: "autumn", autumn: "spring" }[north];
}

const WIND_TO_KMH = { "m/s": 3.6, "km/h": 1, mph: 1.609, kn: 1.852, "ft/s": 1.097 };

// What the sky does, from a weather entity.
function skyOf(weather) {
  const state = weather?.state || "";
  const attributes = weather?.attributes || {};
  const unit = attributes.wind_speed_unit || "km/h";
  let wind = Number(attributes.wind_speed) * (WIND_TO_KMH[unit] || 1) || 0;
  if (state.startsWith("windy")) wind = Math.max(wind, 40);
  return {
    state,
    rain: { rainy: 1, "snowy-rainy": 1, hail: 1, pouring: 2, "lightning-rainy": 2 }[state] || 0,
    snow: state === "snowy" || state === "snowy-rainy",
    clouds: {
      partlycloudy: 2, "windy-variant": 3, cloudy: 5, rainy: 4, pouring: 5,
      lightning: 5, "lightning-rainy": 5, snowy: 4, "snowy-rainy": 4, hail: 4,
    }[state] || 0,
    overcast: ["cloudy", "rainy", "pouring", "lightning", "lightning-rainy", "snowy",
      "snowy-rainy", "hail"].includes(state),
    fog: state === "fog",
    sun: state === "sunny",
    lightning: state.startsWith("lightning"),
    wind: Math.round(wind / 5) * 5,
    temperature: typeof attributes.temperature === "number" ? attributes.temperature : null,
  };
}

// --- Drawing -------------------------------------------------------------

function defs(p, season) {
  const leaf = "fill:var(--leaf)";
  const dark = "fill:var(--leaf);filter:brightness(.82)";
  const light = "fill:var(--leaf);filter:brightness(1.18)";
  const fruit = "fill:var(--fruit)";
  const ring = (count, radius, make) =>
    Array.from({ length: count }, (_, index) => {
      const angle = (index * 2 * Math.PI) / count;
      return make(n(Math.cos(angle) * radius), n(Math.sin(angle) * radius), (index * 360) / count, index);
    }).join("");
  return `<defs>
  <pattern id="${p}-soil" width="0.24" height="0.24" patternUnits="userSpaceOnUse">
    <circle cx="0.05" cy="0.06" r="0.018" fill="#000" opacity=".12"/>
    <circle cx="0.17" cy="0.15" r="0.014" fill="#000" opacity=".1"/>
    <circle cx="0.1" cy="0.2" r="0.012" fill="#fff" opacity=".1"/>
  </pattern>
  <pattern id="${p}-grass" width="0.5" height="0.5" patternUnits="userSpaceOnUse">
    <path d="M.08 .1l.02-.06M.3 .32l.015-.06M.42 .12l-.02-.05M.2 .44l.02-.05" stroke="#2e5a1f" stroke-width=".012" opacity=".22"/>
  </pattern>
  <pattern id="${p}-mown" width="1.2" height="1.2" patternUnits="userSpaceOnUse">
    <rect width=".6" height="1.2" fill="#fff" opacity=".07"/>
  </pattern>
  <pattern id="${p}-gravel" width="0.2" height="0.2" patternUnits="userSpaceOnUse">
    <circle cx=".04" cy=".05" r=".02" fill="#8d8170" opacity=".35"/>
    <circle cx=".14" cy=".11" r=".016" fill="#fff" opacity=".4"/>
    <circle cx=".08" cy=".17" r=".014" fill="#8d8170" opacity=".3"/>
  </pattern>
  <pattern id="${p}-planks" width="1" height="0.16" patternUnits="userSpaceOnUse">
    <path d="M0 .158H1M.4 0V.16" stroke="#8a8478" stroke-width=".012" opacity=".6"/>
  </pattern>
  <pattern id="${p}-tiles" width="0.3" height="0.2" patternUnits="userSpaceOnUse">
    <path d="M0 .198H.3M.15 0V.2" stroke="#6d5f4c" stroke-width=".015" opacity=".5"/>
  </pattern>
  <radialGradient id="${p}-water" cx=".4" cy=".35" r=".8">
    <stop offset="0" stop-color="#9fd0f0"/><stop offset="1" stop-color="#4f93c6"/>
  </radialGradient>
  <radialGradient id="${p}-sun" cx="0" cy="0" r="1.1">
    <stop offset="0" stop-color="#fff6c8" stop-opacity=".55"/>
    <stop offset=".6" stop-color="#fff6c8" stop-opacity=".12"/>
    <stop offset="1" stop-color="#fff6c8" stop-opacity="0"/>
  </radialGradient>
  <linearGradient id="${p}-glass" x1="0" y1="0" x2="1" y2="1">
    <stop offset="0" stop-color="#fff" stop-opacity=".55"/>
    <stop offset=".35" stop-color="#fff" stop-opacity=".12"/>
    <stop offset=".5" stop-color="#fff" stop-opacity=".35"/>
    <stop offset=".65" stop-color="#fff" stop-opacity=".08"/>
    <stop offset="1" stop-color="#fff" stop-opacity=".2"/>
  </linearGradient>
  <radialGradient id="${p}-fog" cx=".5" cy=".5" r=".5">
    <stop offset="0" stop-color="#fff" stop-opacity=".7"/><stop offset="1" stop-color="#fff" stop-opacity="0"/>
  </radialGradient>
  <g id="${p}-leafy">${ring(6, 0.42, (x, y, a) => `<ellipse cx="${x}" cy="${y}" rx=".55" ry=".3" transform="rotate(${a} ${x} ${y})" style="${leaf}"/>`)}<circle r=".32" style="${light}"/></g>
  <g id="${p}-bush">${ring(7, 0.52, (x, y) => `<circle cx="${x}" cy="${y}" r=".46" style="${leaf}"/>`)}<circle r=".5" style="${dark}"/>${ring(4, 0.3, (x, y) => `<circle cx="${x}" cy="${y}" r=".18" style="${light}"/>`)}</g>
  <g id="${p}-vine">${ring(3, 0.42, (x, y, a) => `<circle cx="${x}" cy="${y}" r=".56" style="${leaf}"/><path d="M0 0L${x} ${y}" stroke="#2e5a1f" stroke-width=".05" opacity=".35"/>`)}<circle r=".2" style="${dark}"/></g>
  <g id="${p}-cabbage"><circle r="1" style="${leaf}"/><circle r=".72" style="${light}"/><circle r=".44" style="${leaf}"/>${ring(6, 0.85, (x, y) => `<path d="M0 0L${x} ${y}" stroke="#fff" stroke-width=".05" opacity=".35"/>`)}</g>
  <g id="${p}-legume">${ring(8, 0.55, (x, y, a) => `<ellipse cx="${x}" cy="${y}" rx=".32" ry=".2" transform="rotate(${a} ${x} ${y})" style="${leaf}"/>`)}${ring(4, 0.2, (x, y) => `<circle cx="${x}" cy="${y}" r=".2" style="${light}"/>`)}</g>
  <g id="${p}-allium">${ring(5, 0.45, (x, y, a) => `<ellipse cx="${x}" cy="${y}" rx=".55" ry=".09" transform="rotate(${a} ${x} ${y})" style="${leaf}"/>`)}<circle r=".14" style="${light}"/></g>
  <g id="${p}-feather">${ring(7, 0.5, (x, y, a) => `<path d="M0 0L${n(x * 1.9)} ${n(y * 1.9)}" stroke="var(--leaf)" stroke-width=".07"/><circle cx="${x}" cy="${y}" r=".2" style="${leaf}"/><circle cx="${n(x * 1.6)}" cy="${n(y * 1.6)}" r=".16" style="${light}"/>`)}</g>
  <g id="${p}-chard">${ring(5, 0.45, (x, y, a) => `<ellipse cx="${x}" cy="${y}" rx=".55" ry=".32" transform="rotate(${a} ${x} ${y})" style="${leaf}"/><path d="M0 0L${n(x * 1.8)} ${n(y * 1.8)}" stroke="var(--fruit)" stroke-width=".07"/>`)}</g>
  <g id="${p}-lettuce">${ring(8, 0.5, (x, y) => `<circle cx="${x}" cy="${y}" r=".45" style="${leaf}"/>`)}${ring(5, 0.25, (x, y) => `<circle cx="${x}" cy="${y}" r=".3" style="${light}"/>`)}</g>
  <g id="${p}-herb">${ring(8, 0.55, (x, y) => `<circle cx="${x}" cy="${y}" r=".3" style="${leaf}"/>`)}${ring(4, 0.22, (x, y) => `<circle cx="${x}" cy="${y}" r=".26" style="${dark}"/>`)}</g>
  <g id="${p}-grass">${ring(6, 0.5, (x, y, a) => `<ellipse cx="${x}" cy="${y}" rx=".62" ry=".1" transform="rotate(${a} ${x} ${y})" style="${leaf}"/>`)}<circle r=".18" style="${dark}"/></g>
  <g id="${p}-fruit-solanaceae"><circle cx=".3" cy="-.2" r=".2" style="${fruit}"/><circle cx="-.32" cy=".05" r=".18" style="${fruit}"/><circle cx=".05" cy=".36" r=".19" style="${fruit}"/></g>
  <g id="${p}-fruit-cucurbitaceae"><ellipse cx=".35" cy=".3" rx=".4" ry=".32" style="${fruit}"/><path d="M.05 .3h.6M.35 0v.6" stroke="#000" stroke-width=".03" opacity=".15"/></g>
  <g id="${p}-fruit-fabaceae">${ring(3, 0.45, (x, y, a) => `<ellipse cx="${x}" cy="${y}" rx=".32" ry=".07" transform="rotate(${a + 70} ${x} ${y})" style="${fruit}"/>`)}</g>
  <g id="${p}-fruit-poaceae"><ellipse cx=".3" cy=".1" rx=".3" ry=".11" transform="rotate(30 .3 .1)" style="${fruit}"/><ellipse cx="-.25" cy="-.15" rx=".28" ry=".1" transform="rotate(200 -.25 -.15)" style="${fruit}"/></g>
  <g id="${p}-fruit-lamiaceae">${ring(5, 0.5, (x, y) => `<circle cx="${x}" cy="${y}" r=".1" style="${fruit}"/>`)}</g>
  <g id="${p}-fruit-heart"><circle r=".3" style="${fruit}"/></g>
  <g id="${p}-flowers">${ring(4, 0.48, (x, y) => `<circle cx="${x}" cy="${y}" r=".11" style="fill:var(--flower)"/>`)}</g>
</defs>`;
}

function fruitGlyph(p, family) {
  if (["solanaceae", "cucurbitaceae", "fabaceae", "poaceae", "lamiaceae"].includes(family)) {
    return `#${p}-fruit-${family}`;
  }
  return FRUIT[family] ? `#${p}-fruit-heart` : null;
}

// A tree or shrub from above, dressed for the season.
function canopy(p, item, season) {
  const w = item.width;
  const h = item.height;
  const cx = w / 2;
  const cy = h / 2;
  const radius = Math.min(w, h) / 2;
  const shrub = item.kind === "shrub";
  let out = `<ellipse cx="${n(cx + radius * 0.12)}" cy="${n(cy + radius * 0.16)}" rx="${n(w / 2)}" ry="${n(h / 2)}" fill="#1b3012" opacity="${season === "winter" ? 0.08 : 0.18}"/>`;
  const colours = CANOPY[season];
  if (!colours.length && !shrub) {
    // Bare branches.
    out += `<g class="crown" style="--sd:${(5 + noise(item.id) * 3).toFixed(1)}s">`;
    for (let branch = 0; branch < 7; branch += 1) {
      const angle = (branch / 7) * 2 * Math.PI + noise(item.id, branch);
      const length = radius * (0.75 + noise(item.id, branch, "l") * 0.25);
      const x = cx + Math.cos(angle) * length;
      const y = cy + Math.sin(angle) * length;
      const fork = angle + 0.5;
      out += `<path d="M${n(cx)} ${n(cy)}L${n(x)} ${n(y)}M${n(cx + Math.cos(angle) * length * 0.55)} ${n(cy + Math.sin(angle) * length * 0.55)}L${n(cx + Math.cos(fork) * length * 0.85)} ${n(cy + Math.sin(fork) * length * 0.85)}" stroke="#6d4c41" stroke-width="${n(radius * 0.05)}" stroke-linecap="round" fill="none"/>`;
    }
    out += `<circle cx="${n(cx)}" cy="${n(cy)}" r="${n(radius * 0.1)}" fill="#5d4037"/></g>`;
    return out;
  }
  const palette = colours.length ? colours : ["#6f8a55", "#7a9460"];
  const lobes = shrub ? 6 : 8;
  out += `<g class="crown" style="--sd:${(5 + noise(item.id) * 3).toFixed(1)}s">`;
  out += `<ellipse cx="${n(cx)}" cy="${n(cy)}" rx="${n(w * 0.38)}" ry="${n(h * 0.38)}" fill="${palette[0]}"/>`;
  for (let lobe = 0; lobe < lobes; lobe += 1) {
    const angle = (lobe / lobes) * 2 * Math.PI + noise(item.id, lobe) * 0.4;
    const x = cx + Math.cos(angle) * w * 0.27;
    const y = cy + Math.sin(angle) * h * 0.27;
    const colour = palette[Math.floor(noise(item.id, lobe, "c") * palette.length)];
    out += `<ellipse cx="${n(x)}" cy="${n(y)}" rx="${n(w * 0.22)}" ry="${n(h * 0.22)}" fill="${colour}"/>`;
  }
  out += `<ellipse cx="${n(cx - w * 0.1)}" cy="${n(cy - h * 0.1)}" rx="${n(w * 0.16)}" ry="${n(h * 0.16)}" fill="#fff" opacity=".12"/>`;
  if (season === "spring" && !shrub) {
    for (let flower = 0; flower < 16; flower += 1) {
      const angle = noise(item.id, flower, "a") * 2 * Math.PI;
      const distance = Math.sqrt(noise(item.id, flower, "d")) * 0.42;
      out += `<circle cx="${n(cx + Math.cos(angle) * w * distance)}" cy="${n(cy + Math.sin(angle) * h * distance)}" r="${n(radius * 0.05)}" fill="${flower % 3 ? "#fce4ec" : "#f8bbd0"}"/>`;
    }
  }
  out += "</g>";
  if (season === "autumn") {
    // Leaves on the ground around it.
    for (let leaf = 0; leaf < 14; leaf += 1) {
      const angle = noise(item.id, leaf, "f") * 2 * Math.PI;
      const distance = 0.5 + noise(item.id, leaf, "g") * 0.25;
      out += `<ellipse cx="${n(cx + Math.cos(angle) * w * distance)}" cy="${n(cy + Math.sin(angle) * h * distance)}" rx="${n(radius * 0.06)}" ry="${n(radius * 0.035)}" transform="rotate(${Math.round(noise(item.id, leaf) * 180)} ${n(cx + Math.cos(angle) * w * distance)} ${n(cy + Math.sin(angle) * h * distance)})" fill="${palette[leaf % palette.length]}" opacity=".85"/>`;
    }
  }
  return out;
}

function item(p, shape, ctx) {
  const w = n(shape.width);
  const h = n(shape.height);
  const { season } = ctx;
  const title = shape.label ? `<title>${escape(shape.label)}</title>` : "";
  let body;
  switch (shape.kind) {
    case "lawn":
      body = `<rect width="${w}" height="${h}" rx="${n(Math.min(w, h) * 0.05)}" fill="${GROUND[season]}" style="filter:brightness(1.06)"/>` +
        `<rect width="${w}" height="${h}" fill="url(#${p}-mown)"/><rect width="${w}" height="${h}" fill="url(#${p}-grass)"/>` +
        (season === "spring" ? daisies(shape) : "");
      break;
    case "path":
      body = `<rect width="${w}" height="${h}" rx="${n(Math.min(w, h) * 0.3)}" fill="#d9cfbd"/><rect width="${w}" height="${h}" rx="${n(Math.min(w, h) * 0.3)}" fill="url(#${p}-gravel)"/>`;
      break;
    case "terrace":
      body = `<rect width="${w}" height="${h}" fill="#cbc3b4" stroke="#a39d92" stroke-width=".03"/><rect width="${w}" height="${h}" fill="url(#${p}-planks)"/>`;
      break;
    case "water": {
      const frozen = season === "winter" && ctx.sky.temperature !== null && ctx.sky.temperature <= 0;
      const rx = n(Math.min(w, h) * 0.35);
      body = `<rect width="${w}" height="${h}" rx="${rx}" fill="${frozen ? "#dcecf5" : `url(#${p}-water)`}" stroke="#7d9fb5" stroke-width=".05"/>`;
      if (!frozen) {
        const ripples = ctx.sky.rain ? 6 : 2;
        for (let ripple = 0; ripple < ripples; ripple += 1) {
          const x = n(w * (0.2 + noise(shape.id, ripple, "x") * 0.6));
          const y = n(h * (0.2 + noise(shape.id, ripple, "y") * 0.6));
          body += `<circle class="ripple" cx="${x}" cy="${y}" r="${n(Math.min(w, h) * 0.18)}" fill="none" stroke="#fff" stroke-width=".02" style="--d:${(-noise(shape.id, ripple) * 4).toFixed(2)}s;--sd:${ctx.sky.rain ? 1.6 : 4}s"/>`;
        }
      }
      break;
    }
    case "tree":
    case "shrub":
      body = canopy(p, shape, season);
      break;
    case "hedge": {
      const colour = { spring: "#4f8a3c", summer: "#3f7a2c", autumn: "#5f7a2e", winter: "#46663a" }[season];
      const along = w >= h;
      const length = along ? w : h;
      const depth = along ? h : w;
      const count = Math.max(2, Math.round(length / (depth * 0.8)));
      body = `<rect x="${n(depth * 0.08)}" y="${n(depth * 0.12)}" width="${w}" height="${h}" rx="${n(depth / 2)}" fill="#1b3012" opacity=".15"/>` +
        `<rect width="${w}" height="${h}" rx="${n(depth / 2)}" fill="${colour}"/>`;
      for (let bump = 0; bump < count; bump += 1) {
        const at = n(((bump + 0.5) / count) * length);
        const [x, y] = along ? [at, n(h / 2)] : [n(w / 2), at];
        body += `<circle cx="${x}" cy="${y}" r="${n(depth * 0.45)}" fill="${colour}" style="filter:brightness(${(1 + noise(shape.id, bump) * 0.15).toFixed(2)})"/>`;
      }
      break;
    }
    case "compost":
      {
      const inner = `x=".1" y=".1" width="${n(Math.max(w - 0.2, 0.05))}" height="${n(Math.max(h - 0.2, 0.05))}"`;
      body = `<rect width="${w}" height="${h}" fill="#5b4330" stroke="#3e2c1e" stroke-width=".06"/><rect ${inner} fill="#6d5038"/><rect ${inner} fill="url(#${p}-soil)"/>`;
    }
      break;
    case "tank":
      body = `<ellipse cx="${n(w / 2)}" cy="${n(h / 2)}" rx="${n(w / 2)}" ry="${n(h / 2)}" fill="#78909c" stroke="#546e7a" stroke-width=".04"/><ellipse cx="${n(w / 2)}" cy="${n(h / 2)}" rx="${n(w * 0.3)}" ry="${n(h * 0.3)}" fill="#90a4ae"/>`;
      break;
    case "shed": {
      const ridge = w >= h ? `M0 ${n(h / 2)}H${w}` : `M${n(w / 2)} 0V${h}`;
      body = `<rect x="${n(Math.min(w, h) * 0.06)}" y="${n(Math.min(w, h) * 0.08)}" width="${w}" height="${h}" fill="#1b3012" opacity=".18"/>` +
        `<rect width="${w}" height="${h}" fill="#a1887f" stroke="#6d5f4c" stroke-width=".04"/><rect width="${w}" height="${h}" fill="url(#${p}-tiles)"/>` +
        `<path d="${ridge}" stroke="#6d5f4c" stroke-width=".06"/>` +
        (ctx.sky.snow ? `<rect width="${w}" height="${h}" fill="#fff" opacity=".7"/>` : "");
      break;
    }
    case "greenhouse":
      return "";
    default:
      body = `<rect width="${w}" height="${h}" fill="#cfcfcf" stroke="#9e9e9e" stroke-width=".03" stroke-dasharray=".1 .06"/>`;
  }
  if (ctx.sky.snow && ["lawn", "path", "terrace", "compost"].includes(shape.kind)) {
    body += `<rect width="${w}" height="${h}" fill="#fff" opacity=".7"/>`;
  }
  return `<g transform="${shapeTransform(shape)}">${title}${body}</g>`;
}

function daisies(shape) {
  let out = "";
  const count = Math.min(30, Math.round(shape.width * shape.height * 0.8));
  for (let index = 0; index < count; index += 1) {
    out += `<circle cx="${n(noise(shape.id, index, "x") * shape.width)}" cy="${n(noise(shape.id, index, "y") * shape.height)}" r=".03" fill="${index % 4 ? "#fff" : "#ffe082"}"/>`;
  }
  return out;
}

// Panes of glass over a greenhouse, its crops showing through.
function glass(p, shape, round) {
  const w = n(shape.width);
  const h = n(shape.height);
  const along = w >= h;
  const length = along ? w : h;
  const count = Math.max(1, Math.round(length / 0.6));
  let bars = "";
  for (let bar = 1; bar < count; bar += 1) {
    const at = n((bar / count) * length);
    bars += along ? `M${at} 0V${h}` : `M0 ${at}H${w}`;
  }
  bars += along ? `M0 ${n(h / 2)}H${w}` : `M${n(w / 2)} 0V${h}`;
  const outline = round
    ? `<ellipse cx="${n(w / 2)}" cy="${n(h / 2)}" rx="${n(w / 2)}" ry="${n(h / 2)}"`
    : `<rect width="${w}" height="${h}" rx=".04"`;
  return `${outline} fill="#e3f0f7" fill-opacity=".22" stroke="#4a90c2" stroke-width=".07"/>` +
    `${outline} fill="url(#${p}-glass)"/>` +
    `<path d="${bars}" stroke="#4a90c2" stroke-width=".025" opacity=".7"/>`;
}

function plantRadius(planting) {
  const spacing = (planting.spacing || 30) / 100;
  return Math.min(Math.max(spacing * 0.46, 0.03), 0.7);
}

function crop(p, planting, ctx, animate) {
  const { x, y, width, height } = planting.region;
  const entity = ctx.entities[planting.id];
  const family = planting.family;
  const leaf = planting.stage === "finished" ? "#a1887f" : FOLIAGE[family] || "#5f9e3f";
  const style = `--leaf:${leaf};--fruit:${FRUIT[family] || "#ef5350"};--flower:${FLOWERING[family] || "#fff"}`;
  let out = `<g class="crop" transform="translate(${n(x)} ${n(y)})" style="${style}"${entity ? ` data-entity="${escape(entity)}"` : ""}>` +
    `<title>${escape(planting.name)}</title>` +
    `<rect width="${n(width)}" height="${n(height)}" fill="transparent"/>`;
  if (!planting.in_ground) {
    // Planned, or still in the nursery: only the outline and the seed marks.
    out += `<rect x=".03" y=".03" width="${n(Math.max(width - 0.06, 0.01))}" height="${n(Math.max(height - 0.06, 0.01))}" rx=".05" fill="#fff" fill-opacity=".08" stroke="#fff" stroke-opacity=".75" stroke-width=".025" stroke-dasharray=".08 .06"/>`;
    if (planting.positions.length <= 400) {
      for (const [px, py] of planting.positions) {
        out += `<circle cx="${n(px)}" cy="${n(py)}" r="${n(plantRadius(planting) * 0.18)}" fill="#fff" opacity=".55"/>`;
      }
    }
    return `${out}</g>`;
  }
  const growth = GROWTH[planting.stage] ?? 0.8;
  const acrossRows = planting.direction !== "v";
  if (planting.layout === "rows" || planting.dense) {
    // Furrows under the plants.
    const across = acrossRows ? height : width;
    const rows = Math.max(planting.rows || 1, 1);
    let furrows = "";
    for (let row = 0; row < rows; row += 1) {
      const at = n(((row + 0.5) / rows) * across);
      furrows += acrossRows ? `M0 ${at}H${n(width)}` : `M${at} 0V${n(height)}`;
    }
    const thickness = (across / rows) * 0.55;
    out += `<path d="${furrows}" stroke="#5d4037" stroke-opacity=".28" stroke-width="${n(thickness)}" stroke-linecap="round"/>`;
    if (planting.dense) {
      const tuft = Math.max(thickness, 3 / ctx.scale) * growth;
      out += `<path d="${furrows}" stroke="${leaf}" stroke-width="${n(tuft)}" stroke-linecap="round" stroke-dasharray="${n(tuft * 0.6)} ${n(tuft * 0.5)}"/>`;
      if (planting.stage === "harvesting" && FRUIT[family]) {
        out += `<path d="${furrows}" stroke="${FRUIT[family]}" stroke-width="${n(tuft * 0.4)}" stroke-linecap="round" stroke-dasharray="0 ${n(tuft * 2.3)}"/>`;
      }
      return `${out}</g>`;
    }
  }
  // Small plants stay visible on a small screen.
  const radius = Math.max(plantRadius(planting), 2.4 / ctx.scale) * growth;
  const glyph = `#${p}-${GLYPH[family] || "leafy"}`;
  const fruit = planting.stage === "harvesting" ? fruitGlyph(p, family) : null;
  const flowers = planting.stage === "growing" && FLOWERING[family];
  planting.positions.forEach(([px, py], index) => {
    const turn = Math.round(noise(planting.id, index) * 360);
    const size = n(radius * (0.88 + noise(planting.id, index, "s") * 0.24));
    let inner = `<use href="${glyph}" transform="rotate(${turn})"/>`;
    if (flowers) inner += `<use href="#${p}-flowers" transform="rotate(${turn})"/>`;
    if (fruit) inner += `<use href="${fruit}" transform="rotate(${turn})"/>`;
    const sway = animate
      ? ` class="pl" style="--d:${(-noise(planting.id, index, "d") * 4).toFixed(2)}s"`
      : "";
    const grow = ctx.grow ? ` class="grow" style="--gd:${(noise(planting.id, index, "g") * 0.6).toFixed(2)}s"` : "";
    out += `<g transform="translate(${n(px)} ${n(py)}) scale(${size})"><g${grow}><g${sway}>${inner}</g></g></g>`;
  });
  return `${out}</g>`;
}

function space(p, shape, plantings, ctx, animated) {
  const w = n(shape.width);
  const h = n(shape.height);
  const round = shape.shape === "round";
  const entity = ctx.entities[shape.id];
  const soil = SPACE_SOIL[shape.type] || SPACE_SOIL.bed;
  const edge = shape.sheltered ? SPACE_EDGE.raised_bed : SPACE_EDGE[shape.type] || SPACE_EDGE.bed;
  const outline = (attributes) => round
    ? `<ellipse cx="${n(w / 2)}" cy="${n(h / 2)}" rx="${n(w / 2)}" ry="${n(h / 2)}" ${attributes}/>`
    : `<rect width="${w}" height="${h}" rx=".05" ${attributes}/>`;
  const clip = `${p}-clip-${shape.id}`;
  let out = `<g class="space" transform="${shapeTransform(shape)}"${entity ? ` data-entity="${escape(entity)}"` : ""}>` +
    `<title>${escape(shape.name)}</title>` +
    `<clipPath id="${clip}">${outline("")}</clipPath>` +
    outline(`fill="#1b3012" opacity=".12" transform="translate(.06 .08)"`) +
    outline(`fill="${soil}"`) +
    outline(`fill="url(#${p}-soil)"`);
  out += `<g clip-path="url(#${clip})">`;
  for (const planting of plantings) out += crop(p, planting, ctx, animated.has(planting.id));
  if (ctx.sky.snow && shape.type !== "greenhouse") {
    out += outline(`fill="#fff" opacity=".45" pointer-events="none"`);
  }
  out += "</g>";
  out += shape.type === "greenhouse" && !shape.sheltered
    ? glass(p, shape, round)
    : outline(`fill="none" stroke="${edge.colour}" stroke-width="${edge.width}"`);
  return `${out}</g>`;
}

function labels(shape, plantings, ctx) {
  const fontSize = 12 / ctx.scale;
  const name = fitLabel(shape.name, shape.width * ctx.scale, 12);
  // Above the space, wherever it is turned: at the top of its bounding box.
  const angle = ((shape.rotation || 0) * Math.PI) / 180;
  const halfHeight = (Math.abs(Math.sin(angle)) * shape.width + Math.abs(Math.cos(angle)) * shape.height) / 2;
  const cx = shape.x + shape.width / 2;
  const top = shape.y + shape.height / 2 - halfHeight;
  let out = `<text class="label" x="${n(cx)}" y="${n(top - 5 / ctx.scale)}" font-size="${n(fontSize)}" stroke-width="${n(3 / ctx.scale)}">${escape(name)}</text>`;
  const due = plantings.reduce((total, planting) => total + (planting.tasks_due || 0), 0);
  if (due) {
    const halfWidth = (Math.abs(Math.cos(angle)) * shape.width + Math.abs(Math.sin(angle)) * shape.height) / 2;
    out += `<g class="badge" transform="translate(${n(cx + halfWidth)} ${n(top)})"><title>${escape(ctx.t.tasks(due))}</title>` +
      `<circle r="${n(9 / ctx.scale)}" stroke-width="${n(1.5 / ctx.scale)}"/>` +
      `<text font-size="${n(10 / ctx.scale)}">${due}</text></g>`;
  }
  return out;
}

function weather(p, plan, ctx) {
  const W = plan.width;
  const H = plan.height;
  const unit = Math.max(W, H) / 100;
  const { sky, night, season } = ctx;
  let out = "";
  let keyframes = "";
  if (season === "winter" && sky.temperature !== null && sky.temperature <= 0 && !sky.snow) {
    out += `<rect width="${W}" height="${H}" fill="#e3f2fd" opacity=".22"/>`;
  }
  if (sky.overcast) out += `<rect width="${W}" height="${H}" fill="#5b6770" opacity=".12"/>`;
  if (sky.sun && !night) {
    out += `<rect class="glow" width="${W}" height="${H}" fill="url(#${p}-sun)" style="--sd:9s"/>`;
  }
  if (sky.clouds) {
    const size = Math.max(W, H) * 0.14;
    keyframes += `@keyframes ${p}-drift{from{transform:translateX(${n(-size * 2)}px)}to{transform:translateX(${n(W + size * 2)}px)}}`;
    for (let cloud = 0; cloud < sky.clouds; cloud += 1) {
      const y = n(H * (0.1 + noise("cloud", cloud) * 0.8));
      const duration = (90 - Math.min(sky.wind, 60)) * (0.8 + noise("cloud", cloud, "d") * 0.4);
      const blob = (dx, dy) => [0, 1, 2, 3].map((part) =>
        `<circle cx="${n(dx + (part - 1.5) * size * 0.45)}" cy="${n(dy + (part % 2 ? -size * 0.15 : size * 0.08))}" r="${n(size * (part % 3 ? 0.42 : 0.32))}"/>`).join("");
      out += `<g class="cloud" style="animation-duration:${duration.toFixed(1)}s;animation-delay:${(-noise("cloud", cloud, "s") * duration).toFixed(1)}s;animation-name:${p}-drift">` +
        `<g fill="#1b2a33" opacity=".1">${blob(size * 0.5, y + size * 0.6)}</g>` +
        `<g fill="#fff" opacity="${night ? 0.18 : 0.42}">${blob(0, y)}</g></g>`;
    }
  }
  if (sky.fog) {
    out += `<rect width="${W}" height="${H}" fill="#eef1f2" opacity=".35"/>`;
    for (let band = 0; band < 4; band += 1) {
      out += `<ellipse class="mist" cx="${n(W * noise("fog", band))}" cy="${n(H * (band + 0.5) / 4)}" rx="${n(W * 0.45)}" ry="${n(H * 0.14)}" fill="url(#${p}-fog)" style="--d:${-band * 5}s"/>`;
    }
  }
  const tilt = Math.min(sky.wind, 60) / 60;
  if (sky.rain) {
    const length = unit * 3;
    keyframes += `@keyframes ${p}-rain{from{transform:translate(0,${n(-length * 2)}px)}to{transform:translate(${n(tilt * H * 0.35)}px,${n(H + length * 2)}px)}}`;
    let drops = "";
    for (let drop = 0; drop < DROPS[sky.rain]; drop += 1) {
      const x = n((noise("rain", drop) * 1.3 - 0.3 * tilt) * W);
      const duration = (0.55 + noise("rain", drop, "d") * 0.35).toFixed(2);
      drops += `<path class="drop" d="M${x} 0l${n(-tilt * length * 0.35)} ${n(-length)}" style="animation:${p}-rain ${duration}s linear ${(-noise("rain", drop, "s") * 2).toFixed(2)}s infinite"/>`;
    }
    out += `<g stroke="#e3f0fa" stroke-width="${n(unit * 0.18)}" stroke-linecap="round" opacity=".75">${drops}</g>`;
  }
  if (sky.snow) {
    keyframes += `@keyframes ${p}-snow{0%{transform:translate(0,${n(-unit * 2)}px)}50%{transform:translate(${n(unit * 2 + tilt * W * 0.1)}px,${n(H / 2)}px)}100%{transform:translate(${n(tilt * W * 0.2)}px,${n(H + unit * 2)}px)}}`;
    let flakes = "";
    for (let flake = 0; flake < 60; flake += 1) {
      const duration = (7 + noise("snow", flake, "d") * 5).toFixed(1);
      flakes += `<circle cx="${n(noise("snow", flake) * W)}" r="${n(unit * (0.25 + noise("snow", flake, "r") * 0.35))}" style="animation:${p}-snow ${duration}s linear ${(-noise("snow", flake, "s") * 12).toFixed(1)}s infinite"/>`;
    }
    out += `<g fill="#fff" opacity=".9">${flakes}</g>`;
  }
  if (night) {
    out += `<rect width="${W}" height="${H}" fill="#0d1b3d" opacity="${sky.snow ? 0.3 : 0.45}"/>`;
    if (season === "summer" && !sky.rain && !sky.fog) {
      for (let fly = 0; fly < 10; fly += 1) {
        out += `<circle class="firefly" cx="${n(noise("fly", fly) * W)}" cy="${n(noise("fly", fly, "y") * H)}" r="${n(unit * 0.35)}" fill="#fff59d" style="--d:${(-noise("fly", fly, "d") * 5).toFixed(1)}s"/>`;
      }
    }
  }
  if (sky.lightning) out += `<rect class="flash" width="${W}" height="${H}" fill="#fff"/>`;
  return { out: `<g class="weather" pointer-events="none">${out}</g>`, keyframes };
}

function drawPlan(p, plan, ctx) {
  const W = plan.width;
  const H = plan.height;
  const placed = plan.spaces.filter((shape) => shape.placed);
  const byspace = {};
  for (const planting of plan.plantings) (byspace[planting.space_id] ??= []).push(planting);
  let budget = ctx.motion ? MAX_ANIMATED : 0;
  const animated = new Set();
  for (const planting of [...plan.plantings].sort((a, b) => a.positions.length - b.positions.length)) {
    const count = planting.positions.length;
    if (!planting.in_ground || count > MAX_ANIMATED_CROP || count > budget) continue;
    animated.add(planting.id);
    budget -= count;
  }
  const items = [...plan.items].sort((a, b) => (a.sort || 0) - (b.sort || 0));
  const frames = items.filter((shape) => shape.kind === "greenhouse");
  for (const shape of placed) {
    // Beds inside a drawn greenhouse are under its glass already.
    shape.sheltered = frames.some((frame) => inside(frame, [shape.x + shape.width / 2, shape.y + shape.height / 2]));
  }
  const sway = Math.min(1.5 + ctx.sky.wind / 6, 9);
  const { out: sky, keyframes } = weather(p, plan, ctx);
  let body = `<rect width="${W}" height="${H}" fill="${GROUND[ctx.season]}"/><rect width="${W}" height="${H}" fill="url(#${p}-grass)"/>`;
  if (ctx.sky.snow) body += `<rect width="${W}" height="${H}" fill="#fff" opacity=".7"/>`;
  body += items.map((shape) => item(p, shape, ctx)).join("");
  body += placed.map((shape) => space(p, shape, byspace[shape.id] || [], ctx, animated)).join("");
  body += items
    .filter((shape) => shape.kind === "greenhouse")
    .map((shape) => `<g transform="${shapeTransform(shape)}">${shape.label ? `<title>${escape(shape.label)}</title>` : ""}${glass(p, shape, false)}</g>`)
    .join("");
  body += sky;
  body += placed.map((shape) => labels(shape, byspace[shape.id] || [], ctx)).join("");
  return `<svg viewBox="0 0 ${W} ${H}" preserveAspectRatio="xMidYMid meet" class="${ctx.motion ? "anim" : ""}" style="--sw:${sway.toFixed(1)};--ss:${(5.5 - Math.min(ctx.sky.wind, 50) / 15).toFixed(1)}s" role="img" aria-label="${escape(ctx.garden)}">` +
    `<style>${keyframes}</style>${defs(p, ctx.season)}${body}</svg>`;
}

// --- The card ------------------------------------------------------------

const STYLE = `
:host { display: block; }
ha-card { overflow: hidden; }
.head { display: flex; align-items: baseline; justify-content: space-between; gap: 8px; padding: 12px 16px 8px; }
.title { font-size: 1.15em; font-weight: 500; color: var(--primary-text-color); }
.sub { font-size: .85em; color: var(--secondary-text-color); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.plan { line-height: 0; }
.plan svg { width: 100%; height: auto; display: block; max-height: var(--homestead-plan-max-height, 70vh); }
.message { padding: 16px; color: var(--secondary-text-color); line-height: 1.4; }
[data-entity] { cursor: pointer; }
.crop:hover > rect:first-of-type { fill: rgba(255,255,255,.12); }
.label { text-anchor: middle; fill: #1d2419; stroke: rgba(255,255,255,.85); paint-order: stroke; font-weight: 500; pointer-events: none; font-family: var(--ha-font-family-body, inherit); }
.badge circle { fill: var(--warning-color, #f39c12); stroke: #fff; }
.badge text { fill: #fff; text-anchor: middle; dominant-baseline: central; font-weight: 600; pointer-events: none; }
.anim .pl { transform-box: fill-box; transform-origin: center; animation: hs-sway var(--ss) ease-in-out var(--d, 0s) infinite alternate; }
.anim .crown { transform-box: fill-box; transform-origin: center; animation: hs-crown var(--sd) ease-in-out infinite alternate; }
.grow { transform-box: fill-box; transform-origin: center; animation: hs-grow 1.1s cubic-bezier(.2,.9,.3,1.25) var(--gd, 0s) both; }
.anim .ripple { transform-box: fill-box; transform-origin: center; animation: hs-ripple var(--sd) ease-out var(--d) infinite; }
.anim .glow { animation: hs-glow var(--sd) ease-in-out infinite alternate; }
.anim .mist { animation: hs-mist 20s ease-in-out var(--d) infinite alternate; }
.anim .firefly { animation: hs-blink 2.6s ease-in-out var(--d) infinite alternate; }
.anim .flash { animation: hs-flash 7s linear infinite; }
.flash { opacity: 0; }
.cloud { animation-timing-function: linear; animation-iteration-count: infinite; }
svg:not(.anim) .cloud, svg:not(.anim) [style*="animation"] { animation: none !important; }
@keyframes hs-sway { from { transform: rotate(calc(var(--sw) * -1deg)); } to { transform: rotate(calc(var(--sw) * 1deg)); } }
@keyframes hs-crown { from { transform: rotate(calc(var(--sw) * -.3deg)); } to { transform: rotate(calc(var(--sw) * .3deg)); } }
@keyframes hs-grow { from { transform: scale(0); } }
@keyframes hs-ripple { from { transform: scale(.1); opacity: .9; } to { transform: scale(1); opacity: 0; } }
@keyframes hs-glow { from { opacity: .7; } to { opacity: 1; } }
@keyframes hs-mist { from { transform: translateX(-4%); } to { transform: translateX(4%); } }
@keyframes hs-blink { from { opacity: .05; } to { opacity: .95; } }
@keyframes hs-flash { 0%, 88%, 100% { opacity: 0; } 89% { opacity: .65; } 90% { opacity: .1; } 91% { opacity: .5; } 93% { opacity: 0; } }
@media (prefers-reduced-motion: reduce) { .plan * { animation: none !important; } }
`;

class HomesteadPlanCard extends HTMLElement {
  static getConfigForm() {
    return {
      schema: [
        { name: "title", selector: { text: {} } },
        { name: "weather", selector: { entity: { domain: "weather" } } },
        { name: "entry_id", selector: { config_entry: { integration: "homestead" } } },
      ],
      computeLabel: (schema) => {
        const t = strings(document.querySelector("home-assistant")?.hass);
        return { title: t.title, weather: t.weather, entry_id: t.entry }[schema.name];
      },
    };
  }

  static getStubConfig(hass) {
    const weather = Object.keys(hass?.states || {}).find((id) => id.startsWith("weather."));
    return weather ? { weather } : {};
  }

  constructor() {
    super();
    instances += 1;
    this._prefix = `hs${instances}`;
    this._config = {};
    this._data = null;
    this._error = null;
    this._key = null;
    this._grown = false;
    this._width = 0;
  }

  setConfig(config) {
    const entryChanged = this._config.entry_id !== config.entry_id;
    this._config = { ...config };
    this._key = null;
    if (entryChanged && this._unsub) {
      this._unsubscribe();
      this._data = null;
      this._subscribe();
    }
    this._render();
  }

  set hass(hass) {
    this._hass = hass;
    if (this.isConnected) this._subscribe();
    this._render();
  }

  get hass() {
    return this._hass;
  }

  connectedCallback() {
    if (!this._resize && "ResizeObserver" in window) {
      this._resize = new ResizeObserver((entries) => {
        const width = Math.round(entries[0].contentRect.width / 20) * 20;
        if (width && width !== this._width) {
          this._width = width;
          this._render();
        }
      });
    }
    this._ensureDom();
    this._resize?.observe(this);
    if (this._hass) this._subscribe();
  }

  disconnectedCallback() {
    this._resize?.disconnect();
    clearTimeout(this._retry);
    this._waiting = false;
    this._unsubscribe();
  }

  getCardSize() {
    const plan = this._data?.plan;
    if (!plan) return 2;
    return 1 + Math.round((plan.height / plan.width) * 6);
  }

  getGridOptions() {
    return { columns: 12, min_columns: 6 };
  }

  _subscribe() {
    if (this._unsub || this._waiting || !this._hass?.connection) return;
    const message = { type: "homestead/plan/subscribe" };
    if (this._config.entry_id) message.entry_id = this._config.entry_id;
    this._unsub = this._hass.connection
      .subscribeMessage((data) => {
        this._data = data;
        this._version = (this._version || 0) + 1;
        this._error = null;
        this._render();
      }, message)
      .catch((err) => {
        this._error = err?.code === "not_found" ? "not_found" : "error";
        this._unsub = null;
        this._render();
        // The garden may still be starting: try again in a while.
        this._waiting = true;
        clearTimeout(this._retry);
        this._retry = setTimeout(() => {
          this._waiting = false;
          if (this.isConnected) this._subscribe();
        }, 30000);
      });
  }

  _unsubscribe() {
    const pending = this._unsub;
    this._unsub = null;
    pending?.then((unsubscribe) => unsubscribe?.()).catch(() => {});
  }

  _ensureDom() {
    if (this.shadowRoot) return;
    this.attachShadow({ mode: "open" });
    this.shadowRoot.innerHTML = `<style>${STYLE}</style><ha-card><div class="head"><span class="title"></span><span class="sub"></span></div><div class="plan"></div></ha-card>`;
    this.shadowRoot.querySelector(".plan").addEventListener("click", (event) => {
      const target = event.composedPath().find((node) => node.dataset?.entity);
      if (!target) return;
      this.dispatchEvent(new CustomEvent("hass-more-info", {
        detail: { entityId: target.dataset.entity },
        bubbles: true,
        composed: true,
      }));
    });
  }

  _render() {
    if (!this._hass) return;
    this._ensureDom();
    const t = strings(this._hass);
    const data = this._data;
    const plan = data?.plan;
    const latitude = data?.latitude ?? this._hass.config?.latitude;
    const season = seasonOf(data?.today, latitude);
    const weatherId = this._config.weather;
    const weatherState = weatherId ? this._hass.states[weatherId] : null;
    const sky = skyOf(weatherState);
    const night = this._hass.states["sun.sun"]?.state === "below_horizon" || sky.state === "clear-night";
    const motion = !window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
    const key = [this._version, this._error, season, JSON.stringify(sky), night, t.name,
      this._config.title, this._width, motion].join("|");
    if (key === this._key) return;
    this._key = key;

    const root = this.shadowRoot;
    root.querySelector(".title").textContent = this._config.title || data?.garden || t.name;
    let sub = t[season];
    if (night) sub += ` · ${t.night}`;
    if (weatherState) {
      const described = this._hass.formatEntityState?.(weatherState) ?? weatherState.state;
      const temperature = sky.temperature !== null
        ? ` · ${Math.round(sky.temperature)} ${weatherState.attributes.temperature_unit || "°C"}`
        : "";
      sub += ` · ${described}${temperature}`;
    }
    root.querySelector(".sub").textContent = sub;

    const container = root.querySelector(".plan");
    if (this._error) {
      container.innerHTML = `<div class="message">${escape(t[this._error])}</div>`;
      return;
    }
    if (!data) {
      container.innerHTML = `<div class="message">${escape(t.loading)}</div>`;
      return;
    }
    if (!plan || !plan.spaces.some((shape) => shape.placed)) {
      container.innerHTML = `<div class="message">${escape(t.no_plan)}</div>`;
      return;
    }
    const width = this._width || container.clientWidth || 400;
    // Pixels per metre, as drawn (the plan is at most 70 % of the screen high).
    const scale = Math.min(width / plan.width, (window.innerHeight * 0.7) / plan.height);
    container.innerHTML = drawPlan(this._prefix, plan, {
      t,
      season,
      sky,
      night,
      motion,
      scale,
      grow: motion && !this._grown,
      garden: this._config.title || data.garden || t.name,
      entities: data.entities || {},
    });
    // Plants grow in on the first drawings only (the width may still settle).
    this._growing ??= setTimeout(() => { this._grown = true; }, 1500);
  }
}

function register() {
  // Read the registry again: it may have been replaced since this file ran.
  const registry = window.customElements;
  if (registry.get("homestead-plan-card")) return;
  registry.define("homestead-plan-card", HomesteadPlanCard);
  const t = strings(document.querySelector("home-assistant")?.hass);
  window.customCards = window.customCards || [];
  window.customCards.push({
    type: "homestead-plan-card",
    name: t.name,
    description: t.description,
    preview: true,
    documentationURL: "https://github.com/antoine28boel/homestead",
  });
}

// Home Assistant loads this file before its interface, which then puts its
// own element registry in place: a card defined earlier would be lost. Wait
// until the interface is defined in the current registry.
if (window.customElements.get("home-assistant")) {
  register();
} else {
  const started = Date.now();
  const wait = setInterval(() => {
    if (window.customElements.get("home-assistant") || Date.now() - started > 60000) {
      clearInterval(wait);
      register();
    }
  }, 50);
}
