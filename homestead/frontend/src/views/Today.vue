<script setup>
import { computed, ref, watch } from "vue";

import { api } from "../api.js";
import TaskRow from "../components/TaskRow.vue";
import { formatDate, t } from "../i18n.js";
import { failed, store, today } from "../store.js";

const tasks = ref(null);
const sowNow = ref([]);
const newItem = ref("");
const showDone = ref(false);

async function load() {
  try {
    [tasks.value, sowNow.value] = await Promise.all([api("tasks"), api("sow-now")]);
  } catch (error) {
    failed(error);
  }
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

  <h2>{{ t("to_do") }}</h2>
  <p v-if="tasks === null" class="muted">{{ t("loading") }}</p>
  <template v-else>
    <div class="list">
      <template v-for="key in ['overdue', 'today', 'this_week', 'later']" :key="key">
        <div v-if="groups[key].length" class="list-item muted group">{{ t(key) }}</div>
        <TaskRow v-for="task in groups[key]" :key="task.uid" :task="task" @changed="load" />
      </template>
      <div v-if="!open" class="empty">{{ t("nothing_to_do") }}</div>
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
</template>

<style scoped>
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
