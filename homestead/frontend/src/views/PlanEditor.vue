<script setup>
import { computed, ref, watch } from "vue";
import { useRouter } from "vue-router";

import { api } from "../api.js";
import Icon from "../components/Icon.vue";
import PlanCanvas from "../components/PlanCanvas.vue";
import Sheet from "../components/Sheet.vue";
import { t } from "../i18n.js";
import { ITEM_SIZE, SPACE_SIZE, backgroundScale, round, shrinkImage } from "../plan.js";
import { failed, refreshSpaces, store, toast } from "../store.js";

const router = useRouter();
const plan = ref(null);
const selected = ref(null);
const sheet = ref(null);
const busy = ref(false);
const newSpace = ref({ name: "", type: "bed" });
// Calibration: two points tapped on the image, then their real distance.
const calibrating = ref(false);
const marks = ref([]);
const distance = ref("");
const size = ref({ width: "", height: "" });

async function load() {
  try {
    plan.value = await api("plan");
  } catch (error) {
    failed(error);
  }
}
watch(() => store.changes, load, { immediate: true });

const unplaced = computed(() => plan.value?.spaces.filter((space) => !space.placed) ?? []);
const current = computed(() => {
  if (!plan.value || !selected.value) return null;
  const list = selected.value.kind === "space" ? plan.value.spaces : plan.value.items;
  return list.find((shape) => shape.id === selected.value.id) ?? null;
});

async function save(kind, id, changes, done) {
  try {
    const path = kind === "space" ? `spaces/${id}` : `plan/items/${id}`;
    await api(path, { method: "PATCH", body: changes });
    await load();
  } catch (error) {
    failed(error);
  } finally {
    done?.();
  }
}

// A new shape goes in the middle of the plan.
function middle([width, height]) {
  return {
    x: round(Math.max(0, plan.value.width / 2 - width / 2), 2),
    y: round(Math.max(0, plan.value.height / 2 - height / 2), 2),
    width,
    height,
  };
}

async function place(space) {
  sheet.value = null;
  await save("space", space.id, {
    ...middle(SPACE_SIZE[space.type]),
    shape: space.type === "container" ? "round" : "rect",
  });
  selected.value = { kind: "space", id: space.id };
}

async function createSpace() {
  const { name, type } = newSpace.value;
  if (!name.trim()) return;
  try {
    const space = await api("spaces", {
      method: "POST",
      body: { name: name.trim(), type, sort: store.spaces.length },
    });
    newSpace.value = { name: "", type: "bed" };
    await refreshSpaces();
    await place(space);
  } catch (error) {
    failed(error);
  }
}

async function addItem(kind) {
  sheet.value = null;
  try {
    const item = await api("plan/items", {
      method: "POST",
      body: { kind, label: "", ...middle(ITEM_SIZE[kind]), sort: plan.value.items.length },
    });
    await load();
    selected.value = { kind: "item", id: item.id };
  } catch (error) {
    failed(error);
  }
}

async function removeSelected() {
  const { kind, id } = selected.value;
  selected.value = null;
  try {
    if (kind === "space") {
      await api(`spaces/${id}`, {
        method: "PATCH",
        body: { x: null, y: null, width: null, height: null },
      });
    } else {
      await api(`plan/items/${id}`, { method: "DELETE" });
    }
    await load();
  } catch (error) {
    failed(error);
  }
}

function field(name, value) {
  const number = Number(value);
  if (value === "" || Number.isNaN(number)) return;
  if ((name === "width" || name === "height") && number <= 0) return;
  save(selected.value.kind, selected.value.id, { [name]: number });
}

async function importImage(event) {
  const file = event.target.files?.[0];
  event.target.value = "";
  if (!file) return;
  busy.value = true;
  try {
    const { blob, width, height } = await shrinkImage(file);
    plan.value = await api("plan/background", {
      method: "PUT",
      body: blob,
      params: { width, height },
    });
    if (!plan.value.background.scale) startCalibration();
  } catch (error) {
    failed(error);
  } finally {
    busy.value = false;
  }
}

async function removeImage() {
  try {
    plan.value = await api("plan/background", { method: "DELETE" });
  } catch (error) {
    failed(error);
  }
}

async function putPlan(body) {
  try {
    plan.value = await api("plan", { method: "PUT", body });
  } catch (error) {
    failed(error);
  }
}

function startCalibration() {
  sheet.value = null;
  selected.value = null;
  calibrating.value = true;
  marks.value = [];
  distance.value = "";
}

async function finishCalibration() {
  const length = Number(distance.value);
  if (!(length > 0) || marks.value.length < 2) return;
  const [[ax, ay], [bx, by]] = marks.value;
  const pixels = Math.hypot(bx - ax, by - ay) / backgroundScale(plan.value);
  calibrating.value = false;
  marks.value = [];
  await putPlan({ background_scale: length / pixels });
  toast(t("saved"));
}

function tap(point) {
  if (calibrating.value) {
    marks.value = marks.value.length >= 2 ? [point] : [...marks.value, point];
  } else {
    selected.value = null;
  }
}

function openBackground() {
  size.value = plan.value.size_set
    ? { width: plan.value.width, height: plan.value.height }
    : { width: "", height: "" };
  sheet.value = "background";
}

function saveSize() {
  const width = Number(size.value.width);
  const height = Number(size.value.height);
  if (width > 0 && height > 0) putPlan({ width, height });
  else putPlan({ width: null, height: null });
}
</script>

<template>
  <div v-if="plan" class="editor">
    <div class="row">
      <button class="icon" :title="t('close')" @click="router.back()"><Icon name="back" /></button>
      <h1 class="grow">{{ t("plan") }}</h1>
      <button class="chip" @click="openBackground">{{ t("plan_background") }}</button>
      <button class="chip primary" @click="sheet = 'add'"><Icon name="plus" :size="18" />{{ t("plan_add") }}</button>
    </div>

    <p v-if="calibrating" class="card hint">
      {{ t("plan_calibrate_help") }}
    </p>
    <p v-else-if="!selected" class="muted hint">{{ t("plan_hint") }}</p>

    <div class="canvas">
      <PlanCanvas
        :plan="plan"
        :editable="!calibrating"
        :selected="selected"
        :marks="marks"
        @select="selected = $event"
        @change="save"
        @tap="tap"
      />
    </div>

    <form v-if="calibrating" class="card panel" @submit.prevent="finishCalibration">
      <label class="field">
        <span>{{ t("plan_calibrate_length") }}</span>
        <input
          v-model="distance"
          type="number"
          min="0.1"
          step="any"
          inputmode="decimal"
          :disabled="marks.length < 2"
        />
      </label>
      <div class="actions">
        <button type="button" @click="calibrating = false; marks = []">{{ t("cancel") }}</button>
        <button class="primary" type="submit" :disabled="marks.length < 2 || !(distance > 0)">
          {{ t("save") }}
        </button>
      </div>
    </form>

    <div v-else-if="current" class="card panel">
      <div class="row">
        <strong class="grow">
          {{ selected.kind === "space" ? current.name : t(`item_${current.kind}`) }}
          <span v-if="selected.kind === 'space'" class="muted">· {{ t(`space_${current.type}`) }}</span>
        </strong>
        <button class="icon" :title="t('close')" @click="selected = null"><Icon name="close" /></button>
      </div>
      <div class="grid">
        <label v-if="selected.kind === 'item'" class="field wide">
          <span>{{ t("label") }}</span>
          <input
            :value="current.label"
            maxlength="100"
            @change="save('item', current.id, { label: $event.target.value })"
          />
        </label>
        <label class="field">
          <span>{{ t("width") }}</span>
          <input
            :value="current.width"
            type="number"
            min="0.1"
            step="0.05"
            inputmode="decimal"
            @change="field('width', $event.target.value)"
          />
        </label>
        <label class="field">
          <span>{{ t("height") }}</span>
          <input
            :value="current.height"
            type="number"
            min="0.1"
            step="0.05"
            inputmode="decimal"
            @change="field('height', $event.target.value)"
          />
        </label>
        <label class="field">
          <span>{{ t("rotation") }}</span>
          <input
            :value="current.rotation"
            type="number"
            min="-180"
            max="180"
            step="5"
            inputmode="numeric"
            @change="field('rotation', $event.target.value)"
          />
        </label>
        <label v-if="selected.kind === 'space'" class="field">
          <span>{{ t("shape") }}</span>
          <select :value="current.shape" @change="save('space', current.id, { shape: $event.target.value })">
            <option value="rect">{{ t("shape_rect") }}</option>
            <option value="round">{{ t("shape_round") }}</option>
          </select>
        </label>
      </div>
      <div class="actions">
        <button class="danger" @click="removeSelected">
          {{ selected.kind === "space" ? t("plan_remove_space") : t("delete") }}
        </button>
        <span class="grow" />
        <RouterLink
          v-if="selected.kind === 'space'"
          class="button primary"
          :to="`/plan/spaces/${current.id}`"
        >
          {{ t("arrange_crops") }}
        </RouterLink>
      </div>
    </div>

    <Sheet v-if="sheet === 'add'" :title="t('plan_add')" @close="sheet = null">
      <template v-if="unplaced.length">
        <h2>{{ t("plan_not_drawn") }}</h2>
        <div class="list">
          <button v-for="space in unplaced" :key="space.id" class="list-item" @click="place(space)">
            <span class="grow">{{ space.name }} <span class="muted">· {{ t(`space_${space.type}`) }}</span></span>
            <Icon name="plus" />
          </button>
        </div>
      </template>
      <h2>{{ t("plan_new_space") }}</h2>
      <form class="row wrap" @submit.prevent="createSpace">
        <input v-model="newSpace.name" class="grow" :placeholder="t('name')" maxlength="100" />
        <select v-model="newSpace.type" class="grow">
          <option v-for="type in store.info.space_types" :key="type" :value="type">
            {{ t(`space_${type}`) }}
          </option>
        </select>
        <button class="primary" type="submit" :disabled="!newSpace.name.trim()">{{ t("add") }}</button>
      </form>
      <h2>{{ t("plan_decor") }}</h2>
      <div class="kinds">
        <button v-for="kind in store.info.plan_item_kinds" :key="kind" class="chip" @click="addItem(kind)">
          {{ t(`item_${kind}`) }}
        </button>
      </div>
    </Sheet>

    <Sheet v-if="sheet === 'background'" :title="t('plan_background')" @close="sheet = null">
      <label class="button file">
        {{ busy ? t("uploading") : plan.background ? t("plan_replace") : t("plan_import") }}
        <input type="file" accept="image/*" :disabled="busy" @change="importImage" />
      </label>
      <template v-if="plan.background">
        <p class="muted">
          <template v-if="plan.background.scale">
            {{ t("plan_scale_set", { n: Math.round(1 / plan.background.scale) }) }}
          </template>
          <template v-else>{{ t("plan_not_calibrated") }}</template>
        </p>
        <div class="actions">
          <button class="danger" @click="removeImage">{{ t("plan_remove_background") }}</button>
          <span class="grow" />
          <button class="primary" @click="startCalibration">{{ t("plan_calibrate") }}</button>
        </div>
        <label class="field">
          <span>{{ t("plan_opacity") }}</span>
          <input
            type="range"
            min="0.1"
            max="1"
            step="0.05"
            :value="plan.background.opacity"
            @change="putPlan({ background_opacity: Number($event.target.value) })"
          />
        </label>
      </template>
      <h2>{{ t("plan_size") }}</h2>
      <form class="row" @submit.prevent="saveSize">
        <input v-model="size.width" type="number" min="1" step="any" :placeholder="`${plan.width}`" />
        <span>×</span>
        <input v-model="size.height" type="number" min="1" step="any" :placeholder="`${plan.height}`" />
        <button type="submit">{{ t("save") }}</button>
      </form>
      <p class="muted">
        {{ plan.width }} × {{ plan.height }} m<template v-if="!plan.size_set"> · {{ t("plan_size_auto") }}</template>
      </p>
    </Sheet>
  </div>
  <p v-else class="empty">{{ t("loading") }}</p>
</template>

<style scoped>
.editor {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.hint {
  margin: 0;
}

.canvas {
  height: max(320px, calc(100dvh - var(--hs-nav-height) - 330px));
  border-radius: var(--hs-radius);
  overflow: hidden;
  border: 1px solid var(--hs-divider);
  background: var(--hs-card);
}

.panel {
  margin: 0;
}

.grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(110px, 1fr));
  gap: 0 8px;
  margin-top: 8px;
}

.grid .wide {
  grid-column: 1 / -1;
}

.kinds {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.button.file {
  position: relative;
  width: 100%;
  margin-bottom: 8px;
}

.button.file input {
  position: absolute;
  inset: 0;
  opacity: 0;
  cursor: pointer;
}

button.chip.primary {
  color: #fff;
}
</style>
