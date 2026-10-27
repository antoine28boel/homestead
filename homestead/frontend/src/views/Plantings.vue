<script setup>
import { computed, ref, watch } from "vue";

import { api } from "../api.js";
import Icon from "../components/Icon.vue";
import { formatAmounts, formatDate, t } from "../i18n.js";
import { failed, store, today } from "../store.js";

const thisYear = Number(today().slice(0, 4));
const season = ref(thisYear);
const activeOnly = ref(false);
const seasons = ref([]);
const plantings = ref(null);

async function load() {
  try {
    const [found, listed] = await Promise.all([
      api("plantings", {
        params: { season: season.value, active: activeOnly.value ? true : null },
      }),
      api("seasons"),
    ]);
    plantings.value = found;
    seasons.value = listed;
  } catch (error) {
    failed(error);
  }
}
watch([() => store.changes, season, activeOnly], load, { immediate: true });

const seasonChoices = computed(() => {
  const years = new Set([thisYear, thisYear + 1, ...seasons.value.map((item) => item.season)]);
  return [...years].sort((a, b) => b - a);
});

const bySpace = computed(() => {
  const groups = new Map();
  for (const planting of plantings.value || []) {
    const key = planting.space_name;
    if (!groups.has(key)) groups.set(key, []);
    groups.get(key).push(planting);
  }
  return [...groups.entries()];
});
</script>

<template>
  <h1>{{ t("nav_plantings") }}</h1>
  <div class="row wrap filters">
    <select v-model.number="season" :aria-label="t('season')" class="season">
      <option v-for="year in seasonChoices" :key="year" :value="year">
        {{ t("season") }} {{ year }}
      </option>
    </select>
    <button class="chip" :class="{ selected: !activeOnly }" @click="activeOnly = false">
      {{ t("all_plantings") }}
    </button>
    <button class="chip" :class="{ selected: activeOnly }" @click="activeOnly = true">
      {{ t("active_only") }}
    </button>
  </div>

  <p v-if="plantings === null" class="muted">{{ t("loading") }}</p>
  <p v-else-if="!plantings.length" class="empty">{{ t("no_plantings") }}</p>
  <section v-for="[space, items] in bySpace" :key="space">
    <h2>{{ space }}</h2>
    <RouterLink
      v-for="planting in items"
      :key="planting.id"
      :to="`/plantings/${planting.id}`"
      class="card"
    >
      <div class="row">
        <strong class="grow">{{ planting.name }}</strong>
        <span class="badge">{{ t(`stage_${planting.stage}`) }}</span>
      </div>
      <div v-if="planting.next_task" class="muted">
        {{ formatDate(planting.next_task.due) }} · {{ planting.next_task.summary }}
      </div>
      <div v-if="Object.keys(planting.harvested).length" class="muted">
        {{ t("harvested_amount", { amount: formatAmounts(planting.harvested) }) }}
      </div>
    </RouterLink>
  </section>

  <RouterLink to="/plantings/new" class="button primary fab" :title="t('new_planting')">
    <Icon name="plus" :size="28" />
  </RouterLink>
</template>

<style scoped>
.filters {
  margin: 12px 0;
}

.season {
  width: auto;
}

.button.primary {
  background: var(--hs-primary);
  border-color: var(--hs-primary);
  color: #fff;
}
</style>
