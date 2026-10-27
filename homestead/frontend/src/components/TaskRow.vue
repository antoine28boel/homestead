<script setup>
import { computed } from "vue";

import { api } from "../api.js";
import { formatDate, t } from "../i18n.js";
import { failed, today } from "../store.js";
import Icon from "./Icon.vue";

const props = defineProps({ task: { type: Object, required: true } });
const emit = defineEmits(["changed"]);

const days = computed(() => {
  if (!props.task.due) return null;
  const due = new Date(props.task.due);
  const now = new Date(today());
  return Math.round((due - now) / 86400000);
});

const when = computed(() => {
  if (props.task.completed || days.value === null) return "";
  if (days.value < 0) return t("late_days", { n: -days.value });
  if (days.value === 0) return t("today");
  if (days.value === 1) return t("tomorrow");
  if (days.value < 7) return t("in_days", { n: days.value });
  return formatDate(props.task.due);
});

async function toggle(event) {
  try {
    await api(`tasks/${encodeURIComponent(props.task.uid)}`, {
      method: "PATCH",
      body: { completed: event.target.checked },
    });
    emit("changed");
  } catch (error) {
    event.target.checked = !event.target.checked;
    failed(error);
  }
}

async function remove() {
  try {
    await api(`tasks/${encodeURIComponent(props.task.uid)}`, { method: "DELETE" });
    emit("changed");
  } catch (error) {
    failed(error);
  }
}
</script>

<template>
  <div class="list-item">
    <input type="checkbox" :checked="!!task.completed" :aria-label="task.summary" @change="toggle" />
    <div class="grow">
      <RouterLink
        v-if="task.planting_id && !task.completed"
        :to="`/plantings/${task.planting_id}`"
        class="summary"
      >
        {{ task.summary }}
      </RouterLink>
      <span v-else class="summary" :class="{ done: task.completed }">{{ task.summary }}</span>
      <div v-if="task.description" class="muted description">{{ task.description }}</div>
    </div>
    <span v-if="when" class="badge" :class="{ late: days < 0 }">{{ when }}</span>
    <button v-if="!task.completed" class="icon" :title="t('delete')" @click="remove">
      <Icon name="close" :size="20" />
    </button>
  </div>
</template>

<style scoped>
.summary {
  color: inherit;
  text-decoration: none;
}

.summary.done {
  text-decoration: line-through;
  color: var(--hs-text-muted);
}

.description {
  white-space: pre-line;
}
</style>
