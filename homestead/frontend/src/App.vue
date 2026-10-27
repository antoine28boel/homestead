<script setup>
import NavBar from "./components/NavBar.vue";
import { t } from "./i18n.js";
import { store } from "./store.js";
</script>

<template>
  <main v-if="store.ready">
    <RouterView />
  </main>
  <main v-else-if="store.offline">
    <p class="empty">{{ t("offline") }}</p>
  </main>
  <main v-else>
    <p class="empty">{{ t("loading") }}</p>
  </main>
  <NavBar v-if="store.ready" />
  <div v-if="store.toast" class="toast" role="status">{{ store.toast }}</div>
</template>
