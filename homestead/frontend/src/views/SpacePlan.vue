<script setup>
// One space, seen from above and straightened: each crop has an area, and
// its plants are placed in a grid, in rows, staggered or freely.
import { computed, reactive, ref, watch } from "vue";
import { useRouter } from "vue-router";

import { api } from "../api.js";
import Icon from "../components/Icon.vue";
import PanZoom from "../components/PanZoom.vue";
import { t } from "../i18n.js";
import { MIN_SIZE, SPACE_STYLE, familyColor, round, snap } from "../plan.js";
import { failed, store } from "../store.js";

const props = defineProps({ id: { type: String, required: true } });
const router = useRouter();

const plan = ref(null);
const selectedId = ref(router.currentRoute.value.query.planting ?? null);
const zoomer = ref(null);
const draft = reactive({});

async function load() {
  try {
    plan.value = await api("plan");
  } catch (error) {
    failed(error);
  }
}
watch(() => store.changes, load, { immediate: true });

const space = computed(() => plan.value?.spaces.find((item) => item.id === props.id));
const plantings = computed(() =>
  (plan.value?.plantings ?? [])
    .filter((planting) => planting.space_id === props.id)
    .map((planting) => ({ ...planting, region: { ...planting.region, ...(draft[planting.id] || {}) } })),
);
const selected = computed(() => plantings.value.find((planting) => planting.id === selectedId.value));
const defaults = computed(() => {
  const species = store.catalog.find((item) => item.id === selected.value?.species);
  return species?.spacing_cm ?? [null, null];
});

function radius(planting) {
  return Math.min(((planting.spacing || 30) / 100) * 0.42, 0.35);
}

async function patch(planting, body) {
  try {
    await api(`plantings/${planting.id}`, { method: "PATCH", body });
    await load();
  } catch (error) {
    failed(error);
  }
}

let drag = null;

function begin(event, planting, mode) {
  selectedId.value = planting.id;
  if (planting.layout === "free" && mode === "move") return;
  event.stopPropagation();
  drag = {
    planting,
    mode,
    region: { ...planting.region },
    start: zoomer.value.toWorld(event.clientX, event.clientY),
    moved: false,
  };
  window.addEventListener("pointermove", onMove);
  window.addEventListener("pointerup", onUp, { once: true });
}

function onMove(event) {
  if (!drag) return;
  const [px, py] = zoomer.value.toWorld(event.clientX, event.clientY);
  const { region, start, mode } = drag;
  const { width: maxW, height: maxH } = space.value;
  if (mode === "move") {
    if (!drag.moved && Math.hypot(px - start[0], py - start[1]) * zoomer.value.scale < 6) return;
    draft[drag.planting.id] = {
      x: round(Math.min(Math.max(0, snap(region.x + px - start[0])), maxW - region.width), 3),
      y: round(Math.min(Math.max(0, snap(region.y + py - start[1])), maxH - region.height), 3),
    };
  } else {
    draft[drag.planting.id] = {
      width: round(Math.min(Math.max(MIN_SIZE / 2, snap(px - region.x)), maxW - region.x), 3),
      height: round(Math.min(Math.max(MIN_SIZE / 2, snap(py - region.y)), maxH - region.y), 3),
    };
  }
  drag.moved = true;
}

// Crops that share the space keep the strip they have now, rather than
// being cut again around the one that moved.
async function freeze(except) {
  const others = plantings.value.filter((planting) => planting.id !== except && !planting.region_set);
  await Promise.all(
    others.map((planting) =>
      api(`plantings/${planting.id}`, {
        method: "PATCH",
        body: {
          region_x: planting.region.x,
          region_y: planting.region.y,
          region_width: planting.region.width,
          region_height: planting.region.height,
        },
      }),
    ),
  );
}

async function onUp() {
  window.removeEventListener("pointermove", onMove);
  const current = drag;
  drag = null;
  if (!current?.moved) return;
  const region = { ...current.region, ...draft[current.planting.id] };
  try {
    await freeze(current.planting.id);
  } catch (error) {
    failed(error);
  }
  await patch(current.planting, {
    region_x: region.x,
    region_y: region.y,
    region_width: region.width,
    region_height: region.height,
  });
  delete draft[current.planting.id];
}

function inside(planting, [x, y]) {
  const { region } = planting;
  return x >= region.x && y >= region.y && x <= region.x + region.width && y <= region.y + region.height;
}

// Free layout: a tap adds a plant, or removes the one under the finger.
function tap(point) {
  const target = selected.value;
  if (target?.layout === "free" && inside(target, point)) {
    const local = [round(point[0] - target.region.x, 3), round(point[1] - target.region.y, 3)];
    const near = target.positions.findIndex(
      ([x, y]) => Math.hypot(x - local[0], y - local[1]) < Math.max(radius(target), 0.08),
    );
    const points = near >= 0
      ? target.positions.filter((_, index) => index !== near)
      : [...target.positions, local];
    patch(target, { points, region_x: target.region.x, region_y: target.region.y, region_width: target.region.width, region_height: target.region.height });
    return;
  }
  selectedId.value = plantings.value.find((planting) => inside(planting, point))?.id ?? null;
}

function setLayout(layout) {
  const body = { layout };
  // A free layout starts from the plants of the current one.
  if (layout === "free" && !selected.value.points?.length) body.points = selected.value.positions;
  patch(selected.value, body);
}

function number(name, value) {
  const parsed = Number(value);
  patch(selected.value, { [name]: value === "" || !(parsed > 0) ? null : parsed });
}

function share() {
  patch(selected.value, { region_x: null, region_y: null, region_width: null, region_height: null });
}

function rows(planting) {
  const across = planting.direction === "v" ? planting.region.width : planting.region.height;
  const count = Math.max(1, planting.rows);
  return Array.from({ length: count }, (_, index) => ((index + 0.5) * across) / count);
}
</script>

<template>
  <div v-if="plan" class="space-plan">
    <div class="row">
      <button class="icon" :title="t('close')" @click="router.back()"><Icon name="back" /></button>
      <h1 class="grow">{{ space?.name }}</h1>
    </div>

    <p v-if="!space?.placed" class="card">
      {{ t("space_not_drawn") }}
      <RouterLink to="/plan">{{ t("edit_plan") }}</RouterLink>
    </p>
    <template v-else>
      <p class="muted hint">
        {{ selected?.layout === "free" ? t("free_hint") : t("region_hint") }}
      </p>
      <div class="canvas" :style="{ aspectRatio: `${space.width * 1.12} / ${space.height * 1.12}` }">
        <PanZoom
          ref="zoomer"
          :width="space.width"
          :height="space.height"
          :padding="Math.max(space.width, space.height) * 0.06"
          @tap="tap"
        >
          <template #default="{ scale }">
            <rect
              :width="space.width"
              :height="space.height"
              :fill="SPACE_STYLE[space.type].fill"
              :stroke="SPACE_STYLE[space.type].stroke"
              :stroke-width="SPACE_STYLE[space.type].width"
              rx="0.03"
            />
            <g
              v-for="planting in plantings"
              :key="planting.id"
              :transform="`translate(${planting.region.x} ${planting.region.y})`"
              class="region"
              @pointerdown="begin($event, planting, 'move')"
            >
              <rect
                :width="planting.region.width"
                :height="planting.region.height"
                :fill="familyColor(planting.family)"
                :fill-opacity="planting.dense ? 0.35 : 0.15"
                :stroke="familyColor(planting.family)"
                :stroke-width="(planting.id === selectedId ? 3 : 1) / scale"
                :stroke-dasharray="planting.in_ground ? null : `${5 / scale} ${4 / scale}`"
              />
              <template v-if="planting.dense">
                <line
                  v-for="(offset, index) in rows(planting)"
                  :key="index"
                  :x1="planting.direction === 'v' ? offset : 0"
                  :y1="planting.direction === 'v' ? 0 : offset"
                  :x2="planting.direction === 'v' ? offset : planting.region.width"
                  :y2="planting.direction === 'v' ? planting.region.height : offset"
                  :stroke="familyColor(planting.family)"
                  :stroke-width="Math.max(2 / scale, 0.02)"
                />
              </template>
              <circle
                v-for="(position, index) in planting.positions"
                v-else
                :key="index"
                :cx="position[0]"
                :cy="position[1]"
                :r="radius(planting)"
                :fill="familyColor(planting.family)"
                :fill-opacity="planting.in_ground ? 0.85 : 0.3"
              />
              <text
                :x="planting.region.width / 2"
                :y="12 / scale"
                :font-size="11 / scale"
                class="label"
                :stroke-width="3 / scale"
              >{{ planting.name }}</text>
              <rect
                v-if="planting.id === selectedId"
                :x="planting.region.width - 11 / scale"
                :y="planting.region.height - 11 / scale"
                :width="22 / scale"
                :height="22 / scale"
                :rx="4 / scale"
                class="handle"
                :stroke-width="2 / scale"
                @pointerdown="begin($event, planting, 'resize')"
              />
            </g>
          </template>
        </PanZoom>
      </div>

      <p v-if="!plantings.length" class="card">{{ t("no_crops_here") }}</p>

      <div v-if="!selected" class="list">
        <button
          v-for="planting in plantings"
          :key="planting.id"
          class="list-item"
          @click="selectedId = planting.id"
        >
          <span class="dot" :style="{ background: familyColor(planting.family) }" />
          <span class="grow">
            {{ planting.name }}
            <span class="muted">· {{ t(`stage_${planting.stage}`) }}</span>
          </span>
          <span class="muted">{{ t(planting.dense ? "plants_dense" : "plants_count", { n: planting.count }) }}</span>
        </button>
      </div>

      <div v-else class="card panel">
        <div class="row">
          <span class="dot" :style="{ background: familyColor(selected.family) }" />
          <strong class="grow">{{ selected.name }}</strong>
          <span class="muted">{{ t(selected.dense ? "plants_dense" : "plants_count", { n: selected.count }) }}</span>
          <button class="icon" :title="t('close')" @click="selectedId = null"><Icon name="close" /></button>
        </div>
        <h2>{{ t("layout") }}</h2>
        <div class="row wrap">
          <button
            v-for="layout in store.info.layouts"
            :key="layout"
            :class="['chip', { selected: selected.layout === layout }]"
            @click="setLayout(layout)"
          >
            {{ t(`layout_${layout}`) }}
          </button>
        </div>
        <div v-if="selected.layout !== 'free'" class="grid">
          <label class="field">
            <span>{{ t("spacing") }}</span>
            <input
              :key="`${selected.id}-spacing`"
              :value="selected.spacing ?? ''"
              type="number"
              min="1"
              step="1"
              inputmode="numeric"
              :placeholder="defaults[0] ?? ''"
              @change="number('spacing', $event.target.value)"
            />
            <small v-if="defaults[0]" class="muted">{{ t("default_value", { n: defaults[0] }) }}</small>
          </label>
          <label v-if="selected.layout === 'rows'" class="field">
            <span>{{ t("row_spacing") }}</span>
            <input
              :key="`${selected.id}-rows`"
              :value="selected.row_spacing ?? ''"
              type="number"
              min="1"
              step="1"
              inputmode="numeric"
              :placeholder="defaults[1] ?? ''"
              @change="number('row_spacing', $event.target.value)"
            />
            <small v-if="defaults[1]" class="muted">{{ t("default_value", { n: defaults[1] }) }}</small>
          </label>
          <label v-if="selected.layout !== 'grid'" class="field">
            <span>{{ t("direction") }}</span>
            <select :value="selected.direction" @change="patch(selected, { direction: $event.target.value })">
              <option value="h">{{ t("direction_h") }}</option>
              <option value="v">{{ t("direction_v") }}</option>
            </select>
          </label>
        </div>
        <div class="actions">
          <button v-if="selected.region_set" @click="share">{{ t("region_share") }}</button>
          <span class="grow" />
          <RouterLink class="button" :to="`/plantings/${selected.id}`">{{ t("open_crop") }}</RouterLink>
        </div>
      </div>
    </template>
  </div>
  <p v-else class="empty">{{ t("loading") }}</p>
</template>

<style scoped>
.space-plan {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.hint {
  margin: 0;
}

.canvas {
  width: 100%;
  min-height: 200px;
  max-height: 50vh;
  border-radius: var(--hs-radius);
  overflow: hidden;
  border: 1px solid var(--hs-divider);
  background: var(--hs-card);
}

.region {
  cursor: pointer;
}

.label {
  text-anchor: middle;
  dominant-baseline: hanging;
  fill: #1d2419;
  stroke: rgba(255, 255, 255, 0.85);
  paint-order: stroke;
  pointer-events: none;
}

.handle {
  fill: #fff;
  stroke: var(--hs-primary);
  cursor: grab;
}

.dot {
  width: 12px;
  height: 12px;
  border-radius: 50%;
  flex: none;
}

.panel {
  margin: 0;
}

.panel h2 {
  margin-top: 12px;
}

.grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(140px, 1fr));
  gap: 0 8px;
  margin-top: 12px;
}
</style>
