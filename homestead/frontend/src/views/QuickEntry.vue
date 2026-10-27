<script setup>
// Quick logging in the garden, phone in hand: what, on which crop, details.
import { computed, ref, watch } from "vue";

import { api } from "../api.js";
import Icon from "../components/Icon.vue";
import LogForm from "../components/LogForm.vue";
import { t } from "../i18n.js";
import { failed, store } from "../store.js";

const KINDS = [
  { kind: "watering", icon: "water", label: "kind_watering" },
  { kind: "harvest", icon: "basket", label: "log_harvest" },
  { kind: "observation", icon: "note", label: "kind_observation" },
  { kind: "fertilizing", icon: "leaf", label: "kind_fertilizing" },
  { kind: "treatment", icon: "flask", label: "kind_treatment" },
];

const kind = ref(null);
const target = ref(null); // { plantingId } or { spaceId }
const plantings = ref([]);
const round = ref(0);

async function load() {
  try {
    plantings.value = await api("plantings", { params: { active: true } });
  } catch (error) {
    failed(error);
  }
}
watch(() => store.changes, load, { immediate: true });

const bySpace = computed(() => {
  const groups = new Map();
  for (const planting of plantings.value) {
    if (!groups.has(planting.space_name)) groups.set(planting.space_name, []);
    groups.get(planting.space_name).push(planting);
  }
  return [...groups.entries()];
});

function choose(value) {
  kind.value = value;
  target.value = null;
}

function saved() {
  kind.value = null;
  target.value = null;
  round.value += 1;
}
</script>

<template>
  <h1>{{ t("nav_quick") }}</h1>

  <h2>{{ t("quick_what") }}</h2>
  <div class="big-buttons">
    <button
      v-for="item in KINDS"
      :key="item.kind"
      :class="{ selected: kind === item.kind }"
      @click="choose(item.kind)"
    >
      <Icon :name="item.icon" :size="28" />
      {{ t(item.label) }}
    </button>
  </div>

  <template v-if="kind">
    <h2>{{ t("quick_where") }}</h2>
    <template v-for="[space, items] in bySpace" :key="space">
      <div class="muted space">{{ space }}</div>
      <div class="list">
        <button
          v-for="planting in items"
          :key="planting.id"
          class="list-item"
          :class="{ selected: target?.plantingId === planting.id }"
          @click="target = { plantingId: planting.id }"
        >
          <span class="grow">{{ planting.name }}</span>
          <span class="badge">{{ t(`stage_${planting.stage}`) }}</span>
        </button>
      </div>
    </template>
    <p v-if="!plantings.length" class="muted">{{ t("no_plantings") }}</p>

    <template v-if="kind !== 'harvest' && store.spaces.length">
      <div class="muted space">{{ t("quick_whole_space") }}</div>
      <div class="list">
        <button
          v-for="space in store.spaces"
          :key="space.id"
          class="list-item"
          :class="{ selected: target?.spaceId === space.id }"
          @click="target = { spaceId: space.id }"
        >
          {{ space.name }}
        </button>
      </div>
    </template>
  </template>

  <template v-if="kind && target">
    <h2>{{ t("quick_details") }}</h2>
    <div class="card">
      <LogForm
        :key="`${kind}-${target.plantingId || target.spaceId}-${round}`"
        :kind="kind"
        :planting-id="target.plantingId || null"
        :space-id="target.spaceId || null"
        @saved="saved"
      />
    </div>
  </template>
</template>

<style scoped>
.space {
  margin: 12px 0 4px;
}
</style>
