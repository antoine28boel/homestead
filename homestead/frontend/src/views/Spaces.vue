<script setup>
import { ref, watch } from "vue";

import { api } from "../api.js";
import Icon from "../components/Icon.vue";
import Sheet from "../components/Sheet.vue";
import { t } from "../i18n.js";
import { failed, refreshSpaces, store, toast } from "../store.js";

const DEFAULT_SHIFT = { bed: 0, raised_bed: 1, greenhouse: 4, container: 0 };

const showArchived = ref(false);
const archived = ref([]);
const editing = ref(null);

async function loadArchived() {
  if (!showArchived.value) return;
  try {
    archived.value = (await api("spaces", { params: { archived: true } })).filter(
      (space) => space.archived,
    );
  } catch (error) {
    failed(error);
  }
}
watch([showArchived, () => store.changes], loadArchived);

function edit(space) {
  editing.value = space
    ? { ...space, frost_shift: space.frost_shift ?? "", area: space.area ?? "" }
    : { id: null, name: "", type: "bed", frost_shift: "", area: "" };
}

async function save() {
  const { id, name, type, frost_shift, area } = editing.value;
  const body = {
    name: name.trim(),
    type,
    frost_shift: frost_shift === "" ? null : Number(frost_shift),
    area: area === "" ? null : Number(area),
  };
  try {
    if (id) await api(`spaces/${id}`, { method: "PATCH", body });
    else await api("spaces", { method: "POST", body: { ...body, sort: store.spaces.length } });
    editing.value = null;
    toast(t("saved"));
    await refreshSpaces();
  } catch (error) {
    failed(error);
  }
}

async function archive(space, value) {
  if (value && !window.confirm(t("confirm_delete_space"))) return;
  try {
    if (value) await api(`spaces/${space.id}`, { method: "DELETE" });
    else await api(`spaces/${space.id}`, { method: "PATCH", body: { archived: false } });
    editing.value = null;
    await refreshSpaces();
    await loadArchived();
  } catch (error) {
    failed(error);
  }
}
</script>

<template>
  <h1>{{ t("spaces") }}</h1>

  <div class="list">
    <button v-for="space in store.spaces" :key="space.id" class="list-item" @click="edit(space)">
      <span class="grow">
        {{ space.name }}
        <span class="muted">
          · {{ t(`space_${space.type}`) }}<template v-if="space.area"> · {{ space.area }} m²</template>
        </span>
      </span>
      <span v-if="space.effective_frost_shift" class="badge">
        {{ t("weeks_short", { n: space.effective_frost_shift }) }}
      </span>
    </button>
    <div v-if="!store.spaces.length" class="empty">{{ t("no_spaces") }}</div>
  </div>
  <div class="actions">
    <label class="row muted"><input v-model="showArchived" type="checkbox" /> {{ t("show_archived") }}</label>
    <span class="grow" />
    <button class="primary" @click="edit(null)"><Icon name="plus" :size="20" />{{ t("add_space") }}</button>
  </div>

  <template v-if="showArchived && archived.length">
    <h2>{{ t("archived") }}</h2>
    <div class="list">
      <div v-for="space in archived" :key="space.id" class="list-item">
        <span class="grow">{{ space.name }}</span>
        <button class="chip" @click="archive(space, false)">{{ t("restore") }}</button>
      </div>
    </div>
  </template>

  <Sheet v-if="editing" :title="editing.id ? editing.name : t('add_space')" @close="editing = null">
    <form @submit.prevent="save">
      <label class="field">
        <span>{{ t("name") }}</span>
        <input v-model="editing.name" required maxlength="100" />
      </label>
      <label class="field">
        <span>{{ t("type") }}</span>
        <select v-model="editing.type">
          <option v-for="type in store.info.space_types" :key="type" :value="type">
            {{ t(`space_${type}`) }}
          </option>
        </select>
      </label>
      <label class="field">
        <span>{{ t("frost_shift") }}</span>
        <input v-model="editing.frost_shift" type="number" min="-8" max="16" inputmode="numeric" />
        <small class="muted">{{ t("frost_shift_help", { n: DEFAULT_SHIFT[editing.type] ?? 0 }) }}</small>
      </label>
      <label class="field">
        <span>{{ t("area") }}</span>
        <input v-model="editing.area" type="number" min="0" step="any" inputmode="decimal" />
      </label>
      <div class="actions">
        <button v-if="editing.id" type="button" class="danger" @click="archive(editing, true)">
          {{ t("delete") }}
        </button>
        <span class="grow" />
        <button type="button" @click="editing = null">{{ t("cancel") }}</button>
        <button class="primary" type="submit">{{ t("save") }}</button>
      </div>
    </form>
  </Sheet>
</template>
