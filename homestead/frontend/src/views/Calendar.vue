<script setup>
import { computed, ref, watch } from "vue";

import { api } from "../api.js";
import Icon from "../components/Icon.vue";
import { formatDate, language, t } from "../i18n.js";
import { failed, store, today } from "../store.js";

// From the start of this month, over a year.
const MONTHS = 12;

const events = ref(null);

function shift(iso, months) {
  const [year, month] = iso.split("-").map(Number);
  const day = new Date(Date.UTC(year, month - 1 + months, 1));
  return day.toISOString().slice(0, 10);
}

async function load() {
  const start = `${today().slice(0, 7)}-01`;
  try {
    events.value = await api("calendar", { params: { start, end: shift(start, MONTHS) } });
  } catch (error) {
    failed(error);
  }
}
watch(() => store.changes, load, { immediate: true });

function lastDay(event) {
  const day = new Date(`${event.end}T12:00:00Z`);
  day.setUTCDate(day.getUTCDate() - 1);
  return day.toISOString().slice(0, 10);
}

// Each event under the month it starts in, or this month for one under way.
const months = computed(() => {
  const first = `${today().slice(0, 7)}-01`;
  const groups = new Map();
  for (const event of events.value || []) {
    const key = (event.start < first ? first : event.start).slice(0, 7);
    if (!groups.has(key)) groups.set(key, []);
    groups.get(key).push({ ...event, last: lastDay(event) });
  }
  return [...groups.entries()].map(([key, items]) => ({
    key,
    title: new Intl.DateTimeFormat(language.value, { month: "long", year: "numeric" }).format(
      new Date(`${key}-15T12:00:00`),
    ),
    items,
  }));
});

function when(event) {
  if (event.last === event.start) return formatDate(event.start, { weekday: "short", day: "numeric" });
  return `${formatDate(event.start)} – ${formatDate(event.last)}`;
}
</script>

<template>
  <h1>{{ t("calendar") }}</h1>
  <p class="muted">{{ t("calendar_help") }}</p>

  <p v-if="events === null" class="muted">{{ t("loading") }}</p>
  <p v-else-if="!events.length" class="empty">{{ t("calendar_empty") }}</p>
  <section v-for="month in months" :key="month.key">
    <h2 class="month">{{ month.title }}</h2>
    <div class="list">
      <RouterLink
        v-for="event in month.items"
        :key="event.uid"
        :to="`/plantings/${event.planting_id}`"
        class="list-item"
        :class="{ past: event.last < today() }"
      >
        <span class="when" :class="event.kind">{{ when(event) }}</span>
        <span class="grow">
          {{ event.summary }}
          <small v-if="event.location" class="muted">· {{ event.location }}</small>
        </span>
      </RouterLink>
    </div>
  </section>

  <RouterLink to="/plantings/new" class="button primary fab" :title="t('new_planting')">
    <Icon name="plus" :size="28" />
  </RouterLink>
</template>

<style scoped>
.month::first-letter {
  text-transform: uppercase;
}

.when {
  flex: none;
  width: 7.5em;
  font-size: 0.85rem;
  color: var(--hs-text-muted);
}

/* Periods stand out from one-day jobs. */
.when.sow,
.when.transplant,
.when.harvest {
  color: var(--hs-primary);
  font-weight: 500;
}

.past {
  opacity: 0.6;
}

.button.primary {
  background: var(--hs-primary);
  border-color: var(--hs-primary);
  color: #fff;
}
</style>
