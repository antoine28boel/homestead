<script setup>
import { computed, ref, watch } from "vue";
import { useRouter } from "vue-router";

import { api, ApiError } from "../api.js";
import Icon from "../components/Icon.vue";
import LogForm from "../components/LogForm.vue";
import Sheet from "../components/Sheet.vue";
import TaskRow from "../components/TaskRow.vue";
import { formatAmounts, formatDate, formatPeriod, t } from "../i18n.js";
import { failed, store, toast, today } from "../store.js";

const props = defineProps({ id: { type: String, required: true } });
const router = useRouter();

const planting = ref(null);
const logKind = ref(null);
const stageSheet = ref(null);
const stageDay = ref(today());
const editing = ref(null);

async function load() {
  try {
    planting.value = await api(`plantings/${props.id}`);
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) router.replace("/plantings");
    else failed(error);
  }
}
watch([() => props.id, () => store.changes], load, { immediate: true });

const stages = computed(() => {
  const reached = planting.value?.dates || {};
  const current = store.info.stages.indexOf(planting.value?.stage);
  return store.info.stages
    // Sown in place: never planted out. Bought plants: never sown here.
    .filter((stage) => !(stage === "transplanted" && planting.value?.method === "sow_direct"))
    .filter((stage) => !(stage === "sown" && planting.value?.method === "plant"))
    .map((stage) => ({
      stage,
      day: reached[stage],
      reached: store.info.stages.indexOf(stage) <= current,
      current: stage === planting.value?.stage,
    }));
});

const periods = computed(() =>
  ["sow", "transplant", "harvest"]
    .map((key) => ({ key, period: planting.value?.schedule[key] }))
    .filter((item) => item.period),
);

function openStage(stage) {
  stageSheet.value = stage;
  stageDay.value = planting.value.dates[stage] || today();
}

async function setStage() {
  try {
    await api(`plantings/${props.id}/stage`, {
      method: "POST",
      body: { stage: stageSheet.value, day: stageSheet.value === "planned" ? null : stageDay.value },
    });
    stageSheet.value = null;
    await load();
  } catch (error) {
    failed(error);
  }
}

function startEdit() {
  const { variety, quantity, notes, space_id } = planting.value;
  editing.value = { variety, quantity: quantity ?? "", notes, space_id: space_id || "" };
}

async function saveEdit() {
  try {
    await api(`plantings/${props.id}`, {
      method: "PATCH",
      body: {
        variety: editing.value.variety.trim(),
        quantity: editing.value.quantity === "" ? null : Number(editing.value.quantity),
        notes: editing.value.notes,
        space_id: editing.value.space_id || null,
      },
    });
    editing.value = null;
    toast(t("saved"));
    await load();
  } catch (error) {
    failed(error);
  }
}

async function removePlanting() {
  if (!window.confirm(t("confirm_delete"))) return;
  try {
    await api(`plantings/${props.id}`, { method: "DELETE" });
    router.replace("/plantings");
  } catch (error) {
    failed(error);
  }
}

async function removeEntry(kind, id) {
  if (!window.confirm(t("confirm_delete"))) return;
  try {
    await api(`${kind}/${id}`, { method: "DELETE" });
    await load();
  } catch (error) {
    failed(error);
  }
}

async function logged() {
  logKind.value = null;
  await load();
}
</script>

<template>
  <p v-if="!planting" class="muted">{{ t("loading") }}</p>
  <template v-else>
    <div class="row">
      <button class="icon" :title="t('close')" @click="router.back()"><Icon name="back" /></button>
      <div class="grow">
        <h1>{{ planting.name }}</h1>
        <div class="muted">{{ planting.space_name }} · {{ t("season") }} {{ planting.season }}</div>
      </div>
      <button class="chip" @click="startEdit">{{ t("edit") }}</button>
    </div>

    <div class="big-buttons quick">
      <button @click="logKind = 'watering'"><Icon name="water" />{{ t("log_watering") }}</button>
      <button @click="logKind = 'harvest'"><Icon name="basket" />{{ t("log_harvest") }}</button>
      <button @click="logKind = 'observation'"><Icon name="note" />{{ t("log_observation") }}</button>
    </div>

    <h2>{{ t("stage") }}</h2>
    <div class="stages">
      <button
        v-for="item in stages"
        :key="item.stage"
        :class="{ reached: item.reached, current: item.current }"
        @click="openStage(item.stage)"
      >
        {{ t(`stage_${item.stage}`) }}
        <small>{{ item.day ? formatDate(item.day) : " " }}</small>
      </button>
    </div>

    <h2>{{ t("schedule") }}</h2>
    <div class="card">
      <dl class="periods">
        <template v-for="item in periods" :key="item.key">
          <dt>{{ t(`period_${item.key}`) }}</dt>
          <dd>{{ formatPeriod(item.period) }}</dd>
        </template>
      </dl>
      <p v-if="planting.notes" class="muted notes">{{ planting.notes }}</p>
    </div>

    <template v-if="planting.tasks.length">
      <h2>{{ t("tasks") }}</h2>
      <div class="list">
        <TaskRow v-for="task in planting.tasks" :key="task.uid" :task="task" @changed="load" />
      </div>
    </template>

    <h2>
      {{ t("harvests") }}
      <span v-if="planting.harvests.length">· {{ formatAmounts(planting.harvested) }}</span>
    </h2>
    <div class="list">
      <div v-for="entry in planting.harvests" :key="entry.id" class="list-item">
        <span class="grow">
          {{ formatDate(entry.day) }} · {{ formatAmounts({ [entry.unit]: entry.quantity }) }}
          <span v-if="entry.note" class="muted">· {{ entry.note }}</span>
        </span>
        <button class="icon" :title="t('delete')" @click="removeEntry('harvests', entry.id)">
          <Icon name="delete" :size="20" />
        </button>
      </div>
      <div v-if="!planting.harvests.length" class="empty">{{ t("no_entries") }}</div>
    </div>

    <h2>{{ t("journal") }}</h2>
    <div class="list">
      <div v-for="entry in planting.journal" :key="entry.id" class="list-item">
        <span class="grow">
          {{ formatDate(entry.day) }} · {{ t(`kind_${entry.kind}`) }}
          <span v-if="entry.amount !== null">· {{ entry.amount }} {{ entry.unit }}</span>
          <span v-if="entry.note" class="muted"><br />{{ entry.note }}</span>
        </span>
        <button class="icon" :title="t('delete')" @click="removeEntry('journal', entry.id)">
          <Icon name="delete" :size="20" />
        </button>
      </div>
      <div v-if="!planting.journal.length" class="empty">{{ t("no_entries") }}</div>
    </div>

    <h2>{{ t("history") }}</h2>
    <div class="list">
      <RouterLink
        v-for="other in planting.history"
        :key="other.id"
        :to="`/plantings/${other.id}`"
        class="list-item"
      >
        <span class="badge">{{ other.season }}</span>
        <span class="grow">{{ other.name }} <span class="muted">· {{ other.space_name }}</span></span>
        <span class="muted">{{ formatAmounts(other.harvested) || t(`stage_${other.stage}`) }}</span>
      </RouterLink>
      <div v-if="!planting.history.length" class="empty">{{ t("no_history") }}</div>
    </div>

    <div class="actions bottom">
      <button class="danger" @click="removePlanting">{{ t("delete_planting") }}</button>
    </div>

    <Sheet v-if="logKind" :title="t(logKind === 'harvest' ? 'log_harvest' : `kind_${logKind}`)" @close="logKind = null">
      <LogForm :kind="logKind" :planting-id="planting.id" @saved="logged" />
    </Sheet>

    <Sheet v-if="stageSheet" :title="t(`stage_${stageSheet}`)" @close="stageSheet = null">
      <form @submit.prevent="setStage">
        <label v-if="stageSheet !== 'planned'" class="field">
          <span>{{ t("stage_day") }}</span>
          <input v-model="stageDay" type="date" required />
        </label>
        <div class="actions">
          <button type="button" @click="stageSheet = null">{{ t("cancel") }}</button>
          <button class="primary" type="submit">{{ t("set_stage") }}</button>
        </div>
      </form>
    </Sheet>

    <Sheet v-if="editing" :title="planting.name" @close="editing = null">
      <form @submit.prevent="saveEdit">
        <label class="field">
          <span>{{ t("variety") }}</span>
          <input v-model="editing.variety" maxlength="100" />
        </label>
        <label class="field">
          <span>{{ t("space") }}</span>
          <select v-model="editing.space_id">
            <option value="">{{ t("no_space") }}</option>
            <option v-for="space in store.spaces" :key="space.id" :value="space.id">
              {{ space.name }}
            </option>
          </select>
        </label>
        <label class="field">
          <span>{{ t("quantity") }}</span>
          <input v-model="editing.quantity" type="number" inputmode="numeric" min="1" />
        </label>
        <label class="field">
          <span>{{ t("notes") }}</span>
          <textarea v-model="editing.notes" />
        </label>
        <div class="actions">
          <button type="button" @click="editing = null">{{ t("cancel") }}</button>
          <button class="primary" type="submit">{{ t("save") }}</button>
        </div>
      </form>
    </Sheet>
  </template>
</template>

<style scoped>
.quick {
  margin-top: 16px;
  grid-template-columns: repeat(3, 1fr);
}

.notes {
  white-space: pre-line;
  margin: 12px 0 0;
}

.bottom {
  margin-top: 32px;
  justify-content: center;
}
</style>
