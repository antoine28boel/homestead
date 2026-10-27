<script setup>
import { t } from "../i18n.js";
import Icon from "./Icon.vue";

defineProps({ title: { type: String, required: true } });
const emit = defineEmits(["close"]);
</script>

<template>
  <div class="sheet-backdrop" @click.self="emit('close')">
    <div class="sheet" role="dialog" :aria-label="title">
      <div class="row">
        <h1 class="grow">{{ title }}</h1>
        <button class="icon" :title="t('close')" @click="emit('close')">
          <Icon name="close" />
        </button>
      </div>
      <slot />
    </div>
  </div>
</template>
