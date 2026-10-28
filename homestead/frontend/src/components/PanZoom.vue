<script setup>
// An SVG drawing in metres that the user can pan and zoom: one finger or the
// mouse drags, two fingers or the wheel zoom. Taps on the background are
// reported with their position; shapes stop their own pointer events.
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from "vue";

const props = defineProps({
  width: { type: Number, required: true },
  height: { type: Number, required: true },
  padding: { type: Number, default: 0.5 },
  interactive: { type: Boolean, default: true },
});
const emit = defineEmits(["tap"]);

const svg = ref(null);
const view = reactive({ x: 0, y: 0, w: 1, h: 1 });
const pixels = ref(300);

function fit() {
  view.x = -props.padding;
  view.y = -props.padding;
  view.w = props.width + 2 * props.padding;
  view.h = props.height + 2 * props.padding;
}
fit();
watch(() => [props.width, props.height], fit);

const viewBox = computed(() => `${view.x} ${view.y} ${view.w} ${view.h}`);
// Screen pixels per metre, for strokes and labels that keep their size.
const scale = computed(() => pixels.value / Math.max(view.w, 0.01));

let observer;
onMounted(() => {
  observer = new ResizeObserver(() => {
    const box = svg.value.getBoundingClientRect();
    pixels.value = Math.min(box.width, (box.height * view.w) / view.h) || 300;
  });
  observer.observe(svg.value);
});
onBeforeUnmount(() => observer?.disconnect());
watch(() => [view.w, view.h], () => {
  const box = svg.value?.getBoundingClientRect();
  if (box) pixels.value = Math.min(box.width, (box.height * view.w) / view.h) || 300;
});

function toWorld(clientX, clientY) {
  const matrix = svg.value.getScreenCTM().inverse();
  const point = new DOMPoint(clientX, clientY).matrixTransform(matrix);
  return [point.x, point.y];
}

function zoom(factor, [px, py]) {
  const largest = Math.max(props.width, props.height) * 3;
  const smallest = 0.5;
  const w = Math.min(largest, Math.max(smallest, view.w * factor));
  const applied = w / view.w;
  view.x = px - (px - view.x) * applied;
  view.y = py - (py - view.y) * applied;
  view.w = w;
  view.h *= applied;
}

const pointers = new Map();
let moved = false;
let start = null;
let pinch = null;

function down(event) {
  if (!props.interactive) {
    start = [event.clientX, event.clientY];
    return;
  }
  try {
    svg.value.setPointerCapture(event.pointerId);
  } catch {
    // The pointer is already gone: nothing to capture.
  }
  pointers.set(event.pointerId, [event.clientX, event.clientY]);
  if (pointers.size === 1) {
    moved = false;
    start = [event.clientX, event.clientY];
  } else {
    moved = true;
    pinch = null;
  }
}

function move(event) {
  if (!props.interactive || !pointers.has(event.pointerId)) return;
  const previous = pointers.get(event.pointerId);
  pointers.set(event.pointerId, [event.clientX, event.clientY]);
  if (pointers.size === 1) {
    if (!moved && Math.hypot(event.clientX - start[0], event.clientY - start[1]) < 6) return;
    moved = true;
    const [ax, ay] = toWorld(...previous);
    const [bx, by] = toWorld(event.clientX, event.clientY);
    view.x -= bx - ax;
    view.y -= by - ay;
    return;
  }
  const [a, b] = [...pointers.values()];
  const distance = Math.hypot(a[0] - b[0], a[1] - b[1]);
  const middle = [(a[0] + b[0]) / 2, (a[1] + b[1]) / 2];
  if (pinch) {
    const [ax, ay] = toWorld(...pinch.middle);
    const [bx, by] = toWorld(...middle);
    view.x -= bx - ax;
    view.y -= by - ay;
    zoom(pinch.distance / distance, toWorld(...middle));
  }
  pinch = { distance, middle };
}

function up(event) {
  const wasTap = props.interactive
    ? pointers.size === 1 && !moved
    : start && Math.hypot(event.clientX - start[0], event.clientY - start[1]) < 6;
  pointers.delete(event.pointerId);
  if (pointers.size < 2) pinch = null;
  if (wasTap) emit("tap", toWorld(event.clientX, event.clientY), event);
  if (!pointers.size) start = null;
}

function wheel(event) {
  if (!props.interactive) return;
  event.preventDefault();
  zoom(Math.exp(event.deltaY * 0.0015), toWorld(event.clientX, event.clientY));
}

defineExpose({ toWorld, fit, scale });
</script>

<template>
  <svg
    ref="svg"
    :viewBox="viewBox"
    preserveAspectRatio="xMidYMid meet"
    :class="['pan-zoom', { interactive }]"
    @pointerdown="down"
    @pointermove="move"
    @pointerup="up"
    @pointercancel="up"
    @wheel="wheel"
  >
    <slot :scale="scale" />
  </svg>
</template>

<style scoped>
.pan-zoom {
  display: block;
  width: 100%;
  height: 100%;
  user-select: none;
  -webkit-user-select: none;
}

.pan-zoom.interactive {
  touch-action: none;
  cursor: grab;
}
</style>
