<script setup>
import { formatDate, t } from "../i18n.js";
import { today } from "../store.js";

defineProps({ steps: { type: Array, required: true } });

// Steps run over a season, sometimes into the next year: show the year when
// it is not this one.
function day(iso) {
  const sameYear = iso.slice(0, 4) === today().slice(0, 4);
  return formatDate(iso, sameYear ? undefined : { day: "numeric", month: "short", year: "numeric" });
}

function when(step) {
  if (step.status === "done") return t("step_done_on", { day: day(step.day) });
  if (step.status === "skipped") return t("step_skipped");
  if (step.status === "dismissed") return t("step_dismissed");
  if (step.period) return `${day(step.period[0])} – ${day(step.period[1])}`;
  return day(step.day);
}

function due(step) {
  return step.status === "open" && step.day <= today();
}

// A step with a window is late only once the window has closed.
function late(step) {
  return due(step) && (step.period ? step.period[1] : step.day) < today();
}
</script>

<template>
  <ol class="steps">
    <li
      v-for="step in steps"
      :key="step.key"
      :class="[step.status, { late: late(step) }]"
    >
      <span class="mark" aria-hidden="true">{{ step.status === "done" ? "✓" : "" }}</span>
      <span class="grow">
        <span class="label">{{ step.label }}</span>
        <small class="muted">{{ when(step) }}</small>
        <small v-if="step.frost" class="frost">
          ❄ {{ t("frost_wait", { day: formatDate(step.frost.day, { weekday: "long", day: "numeric" }) }) }}
        </small>
      </span>
      <span v-if="due(step)" class="badge" :class="{ late: late(step) }">
        {{ t(late(step) ? "overdue" : "to_do") }}
      </span>
    </li>
  </ol>
</template>

<style scoped>
.steps {
  list-style: none;
  margin: 0;
  padding: 0;
}

li {
  position: relative;
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 6px 0;
}

/* The line joining the steps. */
li + li::before {
  content: "";
  position: absolute;
  left: 10px;
  top: -12px;
  height: 24px;
  border-left: 2px solid var(--hs-divider);
}

.mark {
  position: relative;
  flex: none;
  width: 22px;
  height: 22px;
  border-radius: 50%;
  border: 2px solid var(--hs-text-muted);
  background: var(--hs-card);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 13px;
  font-weight: 700;
  color: #fff;
  z-index: 1;
}

.done .mark {
  background: var(--hs-primary);
  border-color: var(--hs-primary);
}

.open .mark {
  border-color: var(--hs-warning);
  border-width: 6px;
}

.open.late .mark {
  border-color: var(--hs-error);
}

.skipped .mark,
.dismissed .mark {
  border-style: dashed;
  opacity: 0.6;
}

.label {
  display: block;
}

.frost {
  display: block;
  color: var(--hs-frost);
}

.open .label {
  font-weight: 500;
}

.skipped .label,
.dismissed .label {
  color: var(--hs-text-muted);
}
</style>
