<script setup>
// Journal entry or harvest, for a planting or a whole space.
import { computed, ref } from "vue";

import { api } from "../api.js";
import { t } from "../i18n.js";
import { failed, store, today, toast } from "../store.js";

const props = defineProps({
  kind: { type: String, required: true }, // a journal kind, or "harvest"
  plantingId: { type: String, default: null },
  spaceId: { type: String, default: null },
});
const emit = defineEmits(["saved"]);

const day = ref(today());
const amount = ref("");
const unit = ref(props.kind === "harvest" ? "kg" : props.kind === "watering" ? "L" : "");
const note = ref("");
const saving = ref(false);

const isHarvest = computed(() => props.kind === "harvest");
const valid = computed(() => !isHarvest.value || Number(amount.value) > 0);

async function save() {
  saving.value = true;
  try {
    if (isHarvest.value) {
      await api("harvests", {
        method: "POST",
        body: {
          planting_id: props.plantingId,
          day: day.value,
          quantity: Number(amount.value),
          unit: unit.value,
          note: note.value,
        },
      });
    } else {
      await api("journal", {
        method: "POST",
        body: {
          planting_id: props.plantingId,
          space_id: props.plantingId ? null : props.spaceId,
          kind: props.kind,
          day: day.value,
          amount: amount.value === "" ? null : Number(amount.value),
          unit: amount.value === "" ? null : unit.value || null,
          note: note.value,
        },
      });
    }
    toast(t("quick_done"));
    emit("saved");
  } catch (error) {
    failed(error);
  } finally {
    saving.value = false;
  }
}
</script>

<template>
  <form @submit.prevent="save">
    <label class="field">
      <span>{{ t("day") }}</span>
      <input v-model="day" type="date" required />
    </label>
    <div class="row">
      <label class="field grow">
        <span>{{ t("amount") }}</span>
        <input
          v-model="amount"
          type="number"
          inputmode="decimal"
          min="0"
          step="any"
          :required="isHarvest"
        />
      </label>
      <label class="field">
        <span>{{ t("unit") }}</span>
        <select v-if="isHarvest" v-model="unit">
          <option v-for="item in store.info.harvest_units" :key="item" :value="item">
            {{ t(`unit_${item}`) }}
          </option>
        </select>
        <input v-else v-model="unit" maxlength="20" size="5" />
      </label>
    </div>
    <label class="field">
      <span>{{ t("note") }}</span>
      <textarea v-model="note" />
    </label>
    <div class="actions">
      <button class="primary" type="submit" :disabled="saving || !valid">{{ t("save") }}</button>
    </div>
  </form>
</template>
