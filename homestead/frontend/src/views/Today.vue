<script setup>
import { computed, ref, watch } from "vue";

import { api } from "../api.js";
import PlanCanvas from "../components/PlanCanvas.vue";
import Sheet from "../components/Sheet.vue";
import TaskRow from "../components/TaskRow.vue";
import { formatDate, formatNumber, t } from "../i18n.js";
import { familyColor } from "../plan.js";
import { failed, store, today } from "../store.js";

const tasks = ref(null);
const nights = ref([]);
const sowNow = ref([]);
const plan = ref(null);
const newItem = ref("");
const showDone = ref(false);
const openSpace = ref(null);

async function load() {
  try {
    [tasks.value, sowNow.value, plan.value, { nights: nights.value }] = await Promise.all([
      api("tasks"),
      api("sow-now"),
      api("plan"),
      api("weather"),
    ]);
  } catch (error) {
    failed(error);
  }
}

// The first frosty night of the coming week.
const frost = computed(() => {
  const now = today();
  const week = new Date(now);
  week.setDate(week.getDate() + 7);
  const end = week.toISOString().slice(0, 10);
  return nights.value.find((night) => night.day >= now && night.day < end && night.low <= 0);
});

const drawn = computed(() => plan.value?.spaces.some((space) => space.placed));
const space = computed(() => plan.value?.spaces.find((item) => item.id === openSpace.value));
const spacePlantings = computed(() =>
  (plan.value?.plantings ?? []).filter((planting) => planting.space_id === openSpace.value),
);

function selectOnPlan(selection) {
  if (selection?.kind === "space") openSpace.value = selection.id;
}
watch(() => store.changes, load, { immediate: true });

const groups = computed(() => {
  const now = today();
  const week = new Date(now);
  week.setDate(week.getDate() + 7);
  const weekEnd = week.toISOString().slice(0, 10);
  const result = { overdue: [], today: [], this_week: [], later: [], done: [] };
  for (const task of tasks.value || []) {
    if (task.completed) result.done.push(task);
    else if (!task.due || task.due === now) result.today.push(task);
    else if (task.due < now) result.overdue.push(task);
    else if (task.due <= weekEnd) result.this_week.push(task);
    else result.later.push(task);
  }
  return result;
});

const open = computed(
  () =>
    groups.value.overdue.length +
    groups.value.today.length +
    groups.value.this_week.length +
    groups.value.later.length,
);

const starts = computed(() =>
  sowNow.value
    .map((entry) => ({
      ...entry,
      items: Object.entries(entry.methods).flatMap(([method, species]) =>
        species.map((item) => ({ ...item, method })),
      ),
    }))
    .filter((entry) => entry.items.length),
);

async function addItem() {
  const summary = newItem.value.trim();
  if (!summary) return;
  try {
    await api("tasks", { method: "POST", body: { summary } });
    newItem.value = "";
    await load();
  } catch (error) {
    failed(error);
  }
}
</script>

<template>
  <h1>{{ store.info.garden }}</h1>
  <p class="muted">{{ formatDate(today(), { weekday: "long", day: "numeric", month: "long" }) }}</p>

  <p v-if="!store.spaces.length" class="card">
    {{ t("no_spaces") }}
    <RouterLink to="/spaces">{{ t("add_space") }}</RouterLink>
  </p>
  <div v-else-if="drawn" class="plan">
    <div class="plan-box" :style="{ aspectRatio: `${plan.width + 1} / ${plan.height + 1}` }">
      <PlanCanvas
        :plan="plan"
        :interactive="false"
        :selected="openSpace ? { kind: 'space', id: openSpace } : null"
        @select="selectOnPlan"
      />
    </div>
    <RouterLink to="/plan" class="muted edit">{{ t("edit_plan") }}</RouterLink>
  </div>
  <p v-else-if="plan" class="card">
    {{ t("draw_plan_help") }}
    <RouterLink to="/plan">{{ t("draw_plan") }}</RouterLink>
  </p>

  <p v-if="frost" class="card frost">
    ❄ {{ t("frost_ahead", {
      day: formatDate(frost.day, { weekday: "long", day: "numeric", month: "long" }),
      low: formatNumber(frost.low),
    }) }}
  </p>

  <h2>{{ t("to_do") }}</h2>
  <p v-if="tasks === null" class="muted">{{ t("loading") }}</p>
  <template v-else>
    <div class="list">
      <template v-for="key in ['overdue', 'today', 'this_week', 'later']" :key="key">
        <div v-if="groups[key].length" class="list-item muted group">{{ t(key) }}</div>
        <TaskRow v-for="task in groups[key]" :key="task.uid" :task="task" @changed="load" />
      </template>
      <div v-if="!open" class="empty">{{ t("nothing_to_do") }}</div>
      <RouterLink to="/calendar" class="list-item muted">{{ t("see_calendar") }}</RouterLink>
      <form class="list-item" @submit.prevent="addItem">
        <input v-model="newItem" :placeholder="t('new_item')" maxlength="255" />
        <button type="submit" :disabled="!newItem.trim()">{{ t("add") }}</button>
      </form>
    </div>
    <template v-if="groups.done.length">
      <h2>
        <button class="chip" @click="showDone = !showDone">
          {{ t("done_recently") }} ({{ groups.done.length }})
        </button>
      </h2>
      <div v-if="showDone" class="list">
        <TaskRow v-for="task in groups.done" :key="task.uid" :task="task" @changed="load" />
      </div>
    </template>
  </template>

  <h2>{{ t("sow_now") }}</h2>
  <p v-if="store.spaces.length && !starts.length" class="muted">{{ t("sow_now_empty") }}</p>
  <div v-for="entry in starts" :key="entry.space_id" class="card">
    <strong>{{ entry.space_name }}</strong>
    <div class="row wrap chips">
      <RouterLink
        v-for="item in entry.items"
        :key="`${item.id}-${item.method}`"
        class="button chip"
        :to="{
          path: '/plantings/new',
          query: { species: item.id, space: entry.space_id, method: item.method },
        }"
        :title="t(`method_${item.method}`)"
      >
        {{ item.name }}
        <small class="muted">· {{ t(`method_${item.method}`) }}</small>
      </RouterLink>
    </div>
  </div>

  <Sheet v-if="space" :title="space.name" @close="openSpace = null">
    <div class="list">
      <RouterLink
        v-for="planting in spacePlantings"
        :key="planting.id"
        :to="`/plantings/${planting.id}`"
        class="list-item"
      >
        <span class="dot" :style="{ background: familyColor(planting.family) }" />
        <span class="grow">
          {{ planting.name }}
          <span class="muted">· {{ t(`stage_${planting.stage}`) }}</span>
          <br />
          <small v-if="planting.next_task" class="muted">
            {{ t("next_task") }} : {{ planting.next_task.summary }} · {{ formatDate(planting.next_task.due) }}
          </small>
        </span>
        <span v-if="planting.tasks_due" class="badge late">{{ t("tasks_due", { n: planting.tasks_due }) }}</span>
      </RouterLink>
      <div v-if="!spacePlantings.length" class="empty">{{ t("no_crops_here") }}</div>
    </div>
    <div class="actions">
      <RouterLink class="button" :to="{ path: '/plantings/new', query: { space: space.id } }">
        {{ t("new_planting") }}
      </RouterLink>
      <RouterLink class="button primary" :to="`/plan/spaces/${space.id}`">{{ t("arrange_crops") }}</RouterLink>
    </div>
  </Sheet>
</template>

<style scoped>
.plan {
  margin: 12px 0 4px;
}

.plan-box {
  width: 100%;
  max-height: 55vh;
  border-radius: var(--hs-radius);
  overflow: hidden;
  border: 1px solid var(--hs-divider);
  background: var(--hs-card);
}

.edit {
  display: block;
  text-align: right;
  margin-top: 4px;
}

.frost {
  margin-top: 12px;
  background: color-mix(in srgb, #4fa3e0 16%, var(--hs-card));
  color: var(--hs-frost);
  font-weight: 500;
}

.dot {
  width: 12px;
  height: 12px;
  border-radius: 50%;
  flex: none;
}

.group {
  min-height: 36px;
  padding-top: 6px;
  padding-bottom: 6px;
  font-size: 0.8rem;
  text-transform: uppercase;
  letter-spacing: 0.04em;
}

.chips {
  margin-top: 8px;
}

.button.chip {
  min-height: 34px;
  padding: 4px 12px;
  font-size: 0.9rem;
  font-weight: 400;
}
</style>
