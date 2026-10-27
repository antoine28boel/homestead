<script setup>
import { ref, watch } from "vue";

import { api } from "../api.js";
import { t } from "../i18n.js";
import { failed, store, toast, today } from "../store.js";

const year = today().slice(0, 4);
const form = ref(null);
const saving = ref(false);

async function load() {
  try {
    const garden = await api("garden");
    form.value = {
      name: garden.name,
      last_frost: `${year}-${garden.last_frost}`,
      first_frost: `${year}-${garden.first_frost}`,
    };
  } catch (error) {
    failed(error);
  }
}
watch(() => store.changes, load, { immediate: true });

async function save() {
  saving.value = true;
  try {
    await api("garden", { method: "PUT", body: { ...form.value, name: form.value.name.trim() } });
    store.info.garden = form.value.name.trim();
    toast(t("saved"));
  } catch (error) {
    failed(error);
  } finally {
    saving.value = false;
  }
}
</script>

<template>
  <h1>{{ t("settings") }}</h1>
  <p v-if="!form" class="muted">{{ t("loading") }}</p>
  <form v-else class="card" @submit.prevent="save">
    <label class="field">
      <span>{{ t("garden_name") }}</span>
      <input v-model="form.name" required maxlength="100" />
    </label>
    <label class="field">
      <span>{{ t("last_frost") }}</span>
      <input v-model="form.last_frost" type="date" required />
    </label>
    <label class="field">
      <span>{{ t("first_frost") }}</span>
      <input v-model="form.first_frost" type="date" required />
    </label>
    <p class="muted">{{ t("frost_help") }}</p>
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
