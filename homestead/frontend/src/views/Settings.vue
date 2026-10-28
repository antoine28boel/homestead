<script setup>
import { computed, ref, watch } from "vue";

import { api } from "../api.js";
import { formatDate, t } from "../i18n.js";
import { failed, store, toast, today } from "../store.js";

const year = today().slice(0, 4);
const form = ref(null);
const saving = ref(false);
const weather = ref(null);
const computing = ref(false);
const proposal = ref(null);

async function load() {
  try {
    const [garden, found] = await Promise.all([api("garden"), api("weather")]);
    form.value = {
      name: garden.name,
      last_frost: `${year}-${garden.last_frost}`,
      first_frost: `${year}-${garden.first_frost}`,
      // null: the first weather entity of Home Assistant; "": none.
      weather_entity: garden.weather_entity ?? "auto",
    };
    weather.value = found;
  } catch (error) {
    failed(error);
  }
}
watch(() => store.changes, load, { immediate: true });

async function save() {
  saving.value = true;
  const { weather_entity, ...rest } = form.value;
  const body = { ...rest, name: rest.name.trim() };
  if (weather_entity !== "auto") body.weather_entity = weather_entity;
  try {
    await api("garden", { method: "PUT", body });
    store.info.garden = body.name;
    toast(t("saved"));
  } catch (error) {
    failed(error);
  } finally {
    saving.value = false;
  }
}

async function compute() {
  computing.value = true;
  proposal.value = null;
  try {
    proposal.value = await api("garden/frost-dates", { method: "POST" });
  } catch (error) {
    failed(error);
  } finally {
    computing.value = false;
  }
}

function useProposal() {
  form.value.last_frost = `${year}-${proposal.value.last_frost}`;
  form.value.first_frost = `${year}-${proposal.value.first_frost}`;
  proposal.value = null;
}

const monthDay = (value) => formatDate(`${year}-${value}`, { day: "numeric", month: "long" });

// The coming nights, coldest highlighted.
const nights = computed(() =>
  (weather.value?.nights || []).filter((night) => night.day >= today()).slice(0, 7),
);
</script>

<template>
  <h1>{{ t("settings") }}</h1>
  <p v-if="!form" class="muted">{{ t("loading") }}</p>
  <form v-else class="card" @submit.prevent="save">
    <label class="field">
      <span>{{ t("garden_name") }}</span>
      <input v-model="form.name" required maxlength="100" />
    </label>

    <h2 class="section">{{ t("frost_dates") }}</h2>
    <label class="field">
      <span>{{ t("last_frost") }}</span>
      <input v-model="form.last_frost" type="date" required />
    </label>
    <label class="field">
      <span>{{ t("first_frost") }}</span>
      <input v-model="form.first_frost" type="date" required />
    </label>
    <p class="muted">{{ t("frost_help") }}</p>
    <button type="button" :disabled="computing" @click="compute">
      {{ computing ? t("frost_computing") : t("frost_compute") }}
    </button>
    <p class="muted small">{{ t("frost_compute_help") }}</p>
    <div v-if="proposal" class="proposal">
      <p>
        {{ t("frost_found_last", { day: monthDay(proposal.last_frost), median: monthDay(proposal.last_median) }) }}<br />
        {{ t("frost_found_first", { day: monthDay(proposal.first_frost), median: monthDay(proposal.first_median) }) }}
      </p>
      <p class="muted small">{{ t("frost_found_help", { n: proposal.years }) }}</p>
      <div class="actions">
        <button type="button" @click="proposal = null">{{ t("cancel") }}</button>
        <button type="button" class="primary" @click="useProposal">{{ t("frost_use") }}</button>
      </div>
    </div>

    <h2 class="section">{{ t("weather") }}</h2>
    <template v-if="weather?.connected">
      <label class="field">
        <span>{{ t("weather_entity") }}</span>
        <select v-model="form.weather_entity">
          <option value="auto">{{ t("weather_auto") }}</option>
          <option v-for="entity in weather.entities" :key="entity.entity_id" :value="entity.entity_id">
            {{ entity.name }}
          </option>
          <option value="">{{ t("none") }}</option>
        </select>
      </label>
      <p class="muted">{{ t("weather_help") }}</p>
      <div v-if="nights.length" class="nights">
        <span v-for="night in nights" :key="night.day" :class="{ frost: night.low <= 0 }">
          <small>{{ formatDate(night.day, { weekday: "short" }) }}</small>
          {{ Math.round(night.low) }}°
        </span>
      </div>
    </template>
    <p v-else class="muted">{{ t("weather_unavailable") }}</p>

    <div class="actions">
      <button class="primary" type="submit" :disabled="saving">{{ t("save") }}</button>
    </div>
  </form>

  <h2>{{ t("about") }}</h2>
  <div class="card muted">
    <div>Homestead · {{ t("version", { version: store.info.version }) }}</div>
    <div>{{ t("catalog_size", { n: store.info.species }) }}</div>
  </div>
</template>

<style scoped>
.section {
  margin: 20px 0 8px;
  font-size: 1rem;
}

.small {
  font-size: 0.85rem;
}

.proposal {
  border: 1px solid var(--hs-primary);
  border-radius: var(--hs-radius);
  padding: 4px 12px 12px;
  margin-top: 8px;
}

.nights {
  display: flex;
  gap: 4px;
  flex-wrap: wrap;
}

.nights span {
  display: flex;
  flex-direction: column;
  align-items: center;
  min-width: 38px;
  padding: 4px 6px;
  border-radius: 10px;
  background: color-mix(in srgb, var(--hs-text-muted) 10%, transparent);
}

.nights span.frost {
  background: color-mix(in srgb, #4fa3e0 22%, transparent);
  color: var(--hs-frost);
  font-weight: 500;
}
</style>
