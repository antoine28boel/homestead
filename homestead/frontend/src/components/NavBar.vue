<script setup>
import { t } from "../i18n.js";
import Icon from "./Icon.vue";

const items = [
  { to: "/", icon: "today", label: "nav_today", exact: true },
  { to: "/plantings", icon: "sprout", label: "nav_plantings" },
  { to: "/log", icon: "pencil", label: "nav_quick" },
  { to: "/spaces", icon: "grid", label: "nav_spaces" },
  { to: "/settings", icon: "cog", label: "nav_settings" },
];
</script>

<template>
  <nav>
    <RouterLink
      v-for="item in items"
      :key="item.to"
      :to="item.to"
      :class="item.exact ? 'exact' : ''"
      :exact-active-class="item.exact ? 'active' : ''"
      :active-class="item.exact ? '' : 'active'"
    >
      <Icon :name="item.icon" />
      <span>{{ t(item.label) }}</span>
    </RouterLink>
  </nav>
</template>

<style scoped>
nav {
  position: fixed;
  left: 0;
  right: 0;
  bottom: 0;
  height: calc(var(--hs-nav-height) + env(safe-area-inset-bottom));
  padding-bottom: env(safe-area-inset-bottom);
  display: flex;
  background: var(--hs-card);
  border-top: 1px solid var(--hs-divider);
  z-index: 10;
}

a {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 2px;
  font-size: 0.75rem;
  color: var(--hs-text-muted);
  text-decoration: none;
}

a.active {
  color: var(--hs-primary);
  font-weight: 500;
}
</style>
