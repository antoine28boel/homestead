<script setup>
import { computed, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";

import { api } from "../api.js";
import StepList from "../components/StepList.vue";
import { t } from "../i18n.js";
import { failed, store } from "../store.js";

const route = useRoute();
const router = useRouter();

const search = ref("");
const species = ref(route.query.species || "");
const spaceId = ref(route.query.space || store.spaces[0]?.id || "");
const options = ref([]);
const start = ref("");
const variety = ref("");
const quantity = ref("");
const notes = ref("");
const saving = ref(false);

const matches = computed(() => {
  const query = search.value.trim().toLocaleLowerCase();
  return store.catalog.filter((item) => !query || item.name.toLocaleLowerCase().includes(query));
});
const chosen = computed(() => store.catalog.find((item) => item.id === species.value));
const option = computed(() => options.value.find((item) => item.key === start.value));

watch(
  [species, spaceId],
  async () => {
    options.value = [];
    start.value = "";
    if (!species.value || !spaceId.value) return;
    try {
      options.value = await api(`catalog/${species.value}/starts`, {
        params: { space_id: spaceId.value },
      });
      const wanted = options.value.find((option) => option.method === route.query.method);
      start.value = (wanted || options.value[0])?.key || "";
    } catch (error) {
      failed(error);
    }
  },
  { immediate: true },
);

async function create() {
  saving.value = true;
  const option = options.value.find((item) => item.key === start.value);
  try {
    const planting = await api("plantings", {
      method: "POST",
      body: {
        species: species.value,
        space_id: spaceId.value || null,
        method: option?.method,
        window: option?.window,
        season: option?.season,
        variety: variety.value.trim(),
        quantity: quantity.value === "" ? null : Number(quantity.value),
        notes: notes.value,
      },
    });
    router.replace(`/plantings/${planting.id}`);
  } catch (error) {
    failed(error);
  } finally {
    saving.value = false;
  }
}
</script>

<template>
  <h1>{{ t("new_planting") }}</h1>
  <form @submit.prevent="create">
    <label class="field">
      <span>{{ t("species") }}</span>
      <template v-if="chosen">
        <div class="row">
          <strong class="grow">{{ chosen.name }}</strong>
          <button type="button" class="chip" @click="species = ''">{{ t("edit") }}</button>
        </div>
      </template>
      <template v-else>
        <input v-model="search" :placeholder="t('search_species')" autocomplete="off" />
      </template>
    </label>
    <div v-if="!chosen" class="list species-list">
      <button
        v-for="item in matches"
        :key="item.id"
        type="button"
        class="list-item"
        @click="species = item.id"
      >
        {{ item.name }}
      </button>
    </div>

    <template v-if="chosen">
      <label class="field">
        <span>{{ t("space") }}</span>
        <select v-model="spaceId" required>
          <option v-for="space in store.spaces" :key="space.id" :value="space.id">
            {{ space.name }}
          </option>
        </select>
      </label>

      <div v-if="options.length" class="field">
        <span class="muted">{{ t("start") }}</span>
        <div class="list">
          <button
            v-for="option in options"
            :key="option.key"
            type="button"
            class="list-item"
            :class="{ selected: start === option.key }"
            @click="start = option.key"
          >
            <span class="grow">{{ option.label }}</span>
            <span class="badge">{{ option.season }}</span>
          </button>
        </div>
      </div>

      <div v-if="option" class="field">
        <span class="muted">{{ t("steps_ahead") }}</span>
        <div class="card">
          <StepList :steps="option.steps" />
        </div>
      </div>

      <label class="field">
        <span>{{ t("variety") }}</span>
        <input v-model="variety" maxlength="100" />
      </label>
      <label class="field">
        <span>{{ t("quantity") }}</span>
        <input v-model="quantity" type="number" inputmode="numeric" min="1" />
      </label>
      <label class="field">
        <span>{{ t("notes") }}</span>
        <textarea v-model="notes" />
      </label>
      <div class="actions">
        <button type="button" @click="router.back()">{{ t("cancel") }}</button>
        <button class="primary" type="submit" :disabled="saving || !start">
          {{ t("schedule_planting") }}
        </button>
      </div>
    </template>
  </form>
</template>

<style scoped>
.species-list {
  max-height: 55vh;
  overflow: auto;
}

.field > .muted {
  display: block;
  font-size: 0.85rem;
  margin-bottom: 4px;
}
</style>
