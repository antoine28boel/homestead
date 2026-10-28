// Shared drawing rules of the garden plan: colours, geometry, snapping.
// Distances are in metres. Shapes are placed by their top-left corner and
// turned around their centre, like on the server.

export const SNAP = 0.05;
export const MIN_SIZE = 0.2;

export const SPACE_STYLE = {
  bed: { fill: "#a1785c", stroke: "#6d4c41", width: 0.04 },
  raised_bed: { fill: "#8d6e63", stroke: "#5d4037", width: 0.1 },
  greenhouse: { fill: "#d6eaf8", stroke: "#4a90c2", width: 0.08 },
  container: { fill: "#bf7a50", stroke: "#8d4a26", width: 0.05 },
};

export const ITEM_STYLE = {
  lawn: { fill: "#a5cf7a", stroke: "none" },
  path: { fill: "#d9cfbd", stroke: "none" },
  terrace: { fill: "#c9c3b8", stroke: "#a39d92" },
  water: { fill: "#7fb8e0", stroke: "#4a90c2" },
  tree: { fill: "#4f8a3c", stroke: "#2f5d22", round: true },
  shrub: { fill: "#6ea84f", stroke: "#3f7a2c", round: true },
  hedge: { fill: "#3f7a2c", stroke: "#2f5d22" },
  compost: { fill: "#6d5038", stroke: "#4e3624" },
  tank: { fill: "#90a4ae", stroke: "#607d8b", round: true },
  shed: { fill: "#b0a08a", stroke: "#7d6e58" },
  greenhouse: { fill: "#e3f0f7", stroke: "#4a90c2" },
  other: { fill: "#cfcfcf", stroke: "#9e9e9e" },
};

// Default size of a new object, in metres.
export const ITEM_SIZE = {
  lawn: [4, 3],
  path: [4, 0.8],
  terrace: [3, 3],
  water: [2, 1.5],
  tree: [4, 4],
  shrub: [1.5, 1.5],
  hedge: [5, 0.8],
  compost: [1, 1],
  tank: [1, 1],
  shed: [2.5, 2],
  greenhouse: [3, 2.5],
  other: [1, 1],
};

export const SPACE_SIZE = {
  bed: [4, 1.2],
  raised_bed: [1.2, 1.2],
  greenhouse: [3, 2],
  container: [0.6, 0.6],
};

// One colour per botanical family, so that rotations show at a glance.
export const FAMILY_COLOR = {
  solanaceae: "#e53935",
  cucurbitaceae: "#f9a825",
  brassicaceae: "#7e57c2",
  fabaceae: "#43a047",
  amaryllidaceae: "#9e9d24",
  apiaceae: "#ff7043",
  amaranthaceae: "#ad1457",
  asteraceae: "#7cb342",
  lamiaceae: "#26a69a",
  poaceae: "#d4a017",
  caprifoliaceae: "#2e7d32",
};

export function familyColor(family) {
  return FAMILY_COLOR[family] ?? "#558b2f";
}

// Metres per pixel of the background; until calibrated, it spans the plan.
export function backgroundScale(plan) {
  const background = plan.background;
  if (!background) return null;
  return background.scale || plan.width / background.width;
}

// A name that fits above a shape `width` pixels wide: long names keep their
// last part ("Greenhouse - Bed 1" becomes "Bed 1"), then are cut.
export function fitLabel(name, width, fontSize) {
  const room = Math.max(width + 40, 64);
  const fits = (text) => text.length * fontSize * 0.55 <= room;
  if (fits(name)) return name;
  const short = name.split(/\s+[-–·]\s+/).pop();
  if (fits(short)) return short;
  const letters = Math.max(3, Math.floor(room / (fontSize * 0.55)) - 1);
  return `${short.slice(0, letters)}…`;
}

export function snap(value, step = SNAP) {
  return Math.round(value / step) * step;
}

export function round(value, digits = 2) {
  const factor = 10 ** digits;
  return Math.round(value * factor) / factor;
}

function rotate([x, y], degrees) {
  const angle = (degrees * Math.PI) / 180;
  const cos = Math.cos(angle);
  const sin = Math.sin(angle);
  return [x * cos - y * sin, x * sin + y * cos];
}

export function centre(shape) {
  return [shape.x + shape.width / 2, shape.y + shape.height / 2];
}

// SVG transform drawing a shape in its own frame (0, 0, width, height).
export function shapeTransform(shape) {
  const rotation = shape.rotation || 0;
  return `translate(${shape.x} ${shape.y})` +
    (rotation ? ` rotate(${rotation} ${shape.width / 2} ${shape.height / 2})` : "");
}

// A point of the plan in the frame of a shape.
export function toLocal(shape, [x, y]) {
  const [cx, cy] = centre(shape);
  const [dx, dy] = rotate([x - cx, y - cy], -(shape.rotation || 0));
  return [dx + shape.width / 2, dy + shape.height / 2];
}

// Resize from the bottom-right handle, keeping the top-left corner in place
// on the plan even when the shape is turned.
export function resized(shape, point, minimum = MIN_SIZE) {
  const rotation = shape.rotation || 0;
  const [cx, cy] = centre(shape);
  const [ox, oy] = rotate([-shape.width / 2, -shape.height / 2], rotation);
  const corner = [cx + ox, cy + oy];
  const [lx, ly] = rotate([point[0] - corner[0], point[1] - corner[1]], -rotation);
  const width = Math.max(minimum, snap(lx));
  const height = Math.max(minimum, snap(ly));
  const [hx, hy] = rotate([width / 2, height / 2], rotation);
  return {
    x: round(corner[0] + hx - width / 2, 3),
    y: round(corner[1] + hy - height / 2, 3),
    width: round(width, 3),
    height: round(height, 3),
  };
}

// Angle from the centre to a point, as the rotation handle sits on top.
export function turned(shape, point, step = 5) {
  const [cx, cy] = centre(shape);
  const degrees = (Math.atan2(point[1] - cy, point[0] - cx) * 180) / Math.PI + 90;
  let value = Math.round(degrees / step) * step;
  if (value > 180) value -= 360;
  return value === -180 ? 180 : value;
}

// Read an image file and shrink it, so that drone photos stay light.
export async function shrinkImage(file, longest = 3000) {
  const url = URL.createObjectURL(file);
  try {
    const image = new Image();
    image.src = url;
    await image.decode();
    const ratio = Math.min(1, longest / Math.max(image.naturalWidth, image.naturalHeight));
    const width = Math.round(image.naturalWidth * ratio);
    const height = Math.round(image.naturalHeight * ratio);
    const canvas = document.createElement("canvas");
    canvas.width = width;
    canvas.height = height;
    canvas.getContext("2d").drawImage(image, 0, 0, width, height);
    const blob = await new Promise((resolve) => canvas.toBlob(resolve, "image/jpeg", 0.85));
    return { blob, width, height };
  } finally {
    URL.revokeObjectURL(url);
  }
}
