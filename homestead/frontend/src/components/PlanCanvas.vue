<script setup>
// The garden plan, drawn simply: background, objects, spaces and the plants
// of each crop. In edit mode, shapes can be moved, resized and turned.
import { computed, reactive, ref } from "vue";

import {
  ITEM_STYLE,
  SPACE_STYLE,
  backgroundScale,
  familyColor,
  fitLabel,
  resized,
  round,
  shapeTransform,
  snap,
  turned,
} from "../plan.js";
import PanZoom from "./PanZoom.vue";

const props = defineProps({
  plan: { type: Object, required: true },
  editable: { type: Boolean, default: false },
  interactive: { type: Boolean, default: true },
  selected: { type: Object, default: null },
  marks: { type: Array, default: () => [] },
});
const emit = defineEmits(["select", "change", "tap"]);

const zoomer = ref(null);
// Geometry being dragged, before it is saved.
const draft = reactive({});

const shown = (kind, shape) => ({ ...shape, ...(draft[`${kind}:${shape.id}`] || {}) });
const spaces = computed(() =>
  props.plan.spaces.filter((space) => space.placed).map((space) => shown("space", space)),
);
const items = computed(() => props.plan.items.map((item) => shown("item", item)));
const plantingsBySpace = computed(() => {
  const result = {};
  for (const planting of props.plan.plantings) {
    (result[planting.space_id] ||= []).push(planting);
  }
  return result;
});

const background = computed(() => {
  const value = props.plan.background;
  if (!value) return null;
  const scale = backgroundScale(props.plan);
  return { ...value, w: value.width * scale, h: value.height * scale };
});

const isSelected = (kind, id) => props.selected?.kind === kind && props.selected?.id === id;
const selectedShape = computed(() => {
  if (!props.selected) return null;
  const list = props.selected.kind === "space" ? spaces.value : items.value;
  return list.find((shape) => shape.id === props.selected.id) ?? null;
});

function rows(planting) {
  const { width, height } = planting.region;
  const across = planting.direction === "v" ? width : height;
  const count = Math.max(1, planting.rows);
  return Array.from({ length: count }, (_, index) => ((index + 0.5) * across) / count);
}

function plantRadius(planting) {
  const spacing = (planting.spacing || 30) / 100;
  return Math.min(spacing * 0.42, 0.35);
}

function spaceTasks(id) {
  return (plantingsBySpace.value[id] || []).reduce((sum, planting) => sum + planting.tasks_due, 0);
}

let drag = null;

function begin(event, kind, shape, mode) {
  if (!props.editable) return;
  event.stopPropagation();
  emit("select", { kind, id: shape.id });
  drag = {
    kind,
    shape: { ...shape },
    mode,
    start: zoomer.value.toWorld(event.clientX, event.clientY),
    moved: false,
  };
  window.addEventListener("pointermove", onMove);
  window.addEventListener("pointerup", onUp, { once: true });
}

function onMove(event) {
  if (!drag) return;
  const point = zoomer.value.toWorld(event.clientX, event.clientY);
  const { shape, mode, start } = drag;
  let change;
  if (mode === "move") {
    if (!drag.moved && Math.hypot(point[0] - start[0], point[1] - start[1]) * zoomer.value.scale < 6) {
      return;
    }
    change = {
      x: round(snap(shape.x + point[0] - start[0]), 3),
      y: round(snap(shape.y + point[1] - start[1]), 3),
    };
  } else if (mode === "resize") {
    change = resized(shape, point);
  } else {
    change = { rotation: turned(shape, point) };
  }
  drag.moved = true;
  draft[`${drag.kind}:${shape.id}`] = change;
}

function onUp() {
  window.removeEventListener("pointermove", onMove);
  if (drag?.moved) {
    const key = `${drag.kind}:${drag.shape.id}`;
    emit("change", drag.kind, drag.shape.id, draft[key], () => delete draft[key]);
  }
  drag = null;
}

function tapShape(kind, shape) {
  if (!props.editable) emit("select", { kind, id: shape.id });
}

defineExpose({ toWorld: (...args) => zoomer.value.toWorld(...args) });
</script>

<template>
  <PanZoom
    ref="zoomer"
    :width="plan.width"
    :height="plan.height"
    :interactive="interactive"
    @tap="(point) => emit('tap', point)"
  >
    <template #default="{ scale }">
      <rect
        :x="0"
        :y="0"
        :width="plan.width"
        :height="plan.height"
        class="ground"
        :stroke-width="1 / scale"
      />
      <image
        v-if="background"
        :href="background.url"
        x="0"
        y="0"
        :width="background.w"
        :height="background.h"
        :opacity="background.opacity"
        preserveAspectRatio="none"
      />

      <g
        v-for="item in items"
        :key="`item-${item.id}`"
        :transform="shapeTransform(item)"
        class="shape"
        @pointerdown="begin($event, 'item', item, 'move')"
        @click="tapShape('item', item)"
      >
        <ellipse
          v-if="ITEM_STYLE[item.kind].round"
          :cx="item.width / 2"
          :cy="item.height / 2"
          :rx="item.width / 2"
          :ry="item.height / 2"
          :fill="ITEM_STYLE[item.kind].fill"
          :stroke="ITEM_STYLE[item.kind].stroke"
          :stroke-width="1.5 / scale"
          fill-opacity="0.85"
        />
        <rect
          v-else
          :width="item.width"
          :height="item.height"
          :fill="ITEM_STYLE[item.kind].fill"
          :stroke="ITEM_STYLE[item.kind].stroke"
          :stroke-width="(item.kind === 'greenhouse' ? 3 : 1.5) / scale"
          fill-opacity="0.85"
          :rx="item.kind === 'path' ? 0 : 0.05"
        />
        <text
          v-if="item.label"
          :x="item.width / 2"
          :y="item.kind === 'greenhouse' ? item.height + 8 / scale : item.height / 2"
          :font-size="11 / scale"
          class="label"
          :stroke-width="3 / scale"
        >{{ item.label }}</text>
      </g>

      <g
        v-for="space in spaces"
        :key="`space-${space.id}`"
        :transform="shapeTransform(space)"
        class="shape"
        @pointerdown="begin($event, 'space', space, 'move')"
        @click="tapShape('space', space)"
      >
        <ellipse
          v-if="space.shape === 'round'"
          :cx="space.width / 2"
          :cy="space.height / 2"
          :rx="space.width / 2"
          :ry="space.height / 2"
          :fill="SPACE_STYLE[space.type].fill"
          :stroke="SPACE_STYLE[space.type].stroke"
          :stroke-width="SPACE_STYLE[space.type].width"
        />
        <rect
          v-else
          :width="space.width"
          :height="space.height"
          :fill="SPACE_STYLE[space.type].fill"
          :stroke="SPACE_STYLE[space.type].stroke"
          :stroke-width="SPACE_STYLE[space.type].width"
          rx="0.03"
        />
        <g
          v-for="planting in plantingsBySpace[space.id] || []"
          :key="planting.id"
          :transform="`translate(${planting.region.x} ${planting.region.y})`"
        >
          <rect
            :width="planting.region.width"
            :height="planting.region.height"
            :fill="familyColor(planting.family)"
            :fill-opacity="planting.in_ground ? (planting.dense ? 0.35 : 0.12) : 0.06"
            :stroke="familyColor(planting.family)"
            :stroke-width="1 / scale"
            :stroke-dasharray="planting.in_ground ? null : `${4 / scale} ${3 / scale}`"
          />
          <template v-if="planting.in_ground && planting.dense">
            <line
              v-for="(offset, index) in rows(planting)"
              :key="index"
              :x1="planting.direction === 'v' ? offset : 0"
              :y1="planting.direction === 'v' ? 0 : offset"
              :x2="planting.direction === 'v' ? offset : planting.region.width"
              :y2="planting.direction === 'v' ? planting.region.height : offset"
              :stroke="familyColor(planting.family)"
              :stroke-width="Math.max(2 / scale, 0.03)"
              stroke-linecap="round"
            />
          </template>
          <template v-else-if="planting.in_ground">
            <circle
              v-for="(position, index) in planting.positions"
              :key="index"
              :cx="position[0]"
              :cy="position[1]"
              :r="plantRadius(planting)"
              :fill="familyColor(planting.family)"
              fill-opacity="0.85"
            />
          </template>
          <text
            v-if="planting.region.width * scale > 30"
            :x="planting.region.width / 2"
            :y="planting.region.height / 2"
            :font-size="10 / scale"
            class="label small"
            :stroke-width="3 / scale"
          >{{ fitLabel(planting.name, planting.region.width * scale - 24, 10) }}</text>
        </g>
        <text
          :x="space.width / 2"
          :y="-6 / scale"
          :font-size="12 / scale"
          class="label title"
          :stroke-width="3 / scale"
        >{{ fitLabel(space.name, space.width * scale, 12) }}</text>
        <g
          v-if="spaceTasks(space.id)"
          :transform="`translate(${space.width} 0)`"
        >
          <circle :r="9 / scale" class="badge" />
          <text :font-size="10 / scale" class="badge-text">{{ spaceTasks(space.id) }}</text>
        </g>
      </g>

      <g v-if="selectedShape" :transform="shapeTransform(selectedShape)">
        <rect
          :x="-3 / scale"
          :y="-3 / scale"
          :width="selectedShape.width + 6 / scale"
          :height="selectedShape.height + 6 / scale"
          class="selection"
          :stroke-width="2 / scale"
          :stroke-dasharray="`${6 / scale} ${4 / scale}`"
        />
        <template v-if="editable">
          <line
            :x1="selectedShape.width / 2"
            :y1="0"
            :x2="selectedShape.width / 2"
            :y2="-28 / scale"
            class="selection"
            :stroke-width="1.5 / scale"
          />
          <circle
            :cx="selectedShape.width / 2"
            :cy="-28 / scale"
            :r="11 / scale"
            class="handle"
            :stroke-width="2 / scale"
            @pointerdown="begin($event, selected.kind, selectedShape, 'rotate')"
          />
          <rect
            :x="selectedShape.width - 11 / scale"
            :y="selectedShape.height - 11 / scale"
            :width="22 / scale"
            :height="22 / scale"
            :rx="4 / scale"
            class="handle"
            :stroke-width="2 / scale"
            @pointerdown="begin($event, selected.kind, selectedShape, 'resize')"
          />
        </template>
      </g>

      <g v-for="(mark, index) in marks" :key="`mark-${index}`">
        <circle :cx="mark[0]" :cy="mark[1]" :r="7 / scale" class="mark" :stroke-width="2 / scale" />
      </g>
      <line
        v-if="marks.length === 2"
        :x1="marks[0][0]"
        :y1="marks[0][1]"
        :x2="marks[1][0]"
        :y2="marks[1][1]"
        class="mark-line"
        :stroke-width="2 / scale"
      />
    </template>
  </PanZoom>
</template>

<style scoped>
.ground {
  fill: color-mix(in srgb, var(--hs-primary) 10%, var(--hs-card));
  stroke: var(--hs-divider);
}

.shape {
  cursor: pointer;
}

.label {
  text-anchor: middle;
  dominant-baseline: middle;
  fill: #1d2419;
  stroke: rgba(255, 255, 255, 0.85);
  paint-order: stroke;
  pointer-events: none;
}

.label.title {
  dominant-baseline: auto;
  font-weight: 500;
}

.badge {
  fill: var(--hs-warning);
  stroke: #fff;
}

.badge-text {
  fill: #fff;
  text-anchor: middle;
  dominant-baseline: central;
  font-weight: 600;
  pointer-events: none;
}

.selection {
  fill: none;
  stroke: var(--hs-primary);
  pointer-events: none;
}

.handle {
  fill: #fff;
  stroke: var(--hs-primary);
  cursor: grab;
}

.mark {
  fill: rgba(255, 255, 255, 0.8);
  stroke: #d81b60;
}

.mark-line {
  stroke: #d81b60;
}
</style>
