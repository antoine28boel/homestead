// Shared state: server settings, spaces and catalogue, and a change counter
// that pages watch to reload when the server says something changed.
import { reactive } from "vue";

import { api, listen } from "./api.js";
import { setLanguage, t } from "./i18n.js";

export const store = reactive({
  ready: false,
  offline: false,
  info: null,
  catalog: [],
  spaces: [],
  changes: 0,
  toast: "",
});

let toastTimer;
export function toast(message) {
  store.toast = message;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => {
    store.toast = "";
  }, 2500);
}

export function failed(error) {
  toast(t("error", { message: error.message }));
}

export async function refreshSpaces() {
  store.spaces = await api("spaces");
}

export function speciesName(id) {
  return store.catalog.find((species) => species.id === id)?.name ?? id;
}

// Today as YYYY-MM-DD in the garden's time zone, as the server sees it.
export function today() {
  return store.info?.today ?? new Date().toISOString().slice(0, 10);
}

export async function start() {
  try {
    store.info = await api("info");
    setLanguage(store.info.language);
    [store.catalog] = await Promise.all([api("catalog"), refreshSpaces()]);
    store.ready = true;
  } catch {
    store.offline = true;
    return;
  }
  listen(async () => {
    store.info = await api("info").catch(() => store.info);
    await refreshSpaces().catch(() => {});
    store.changes += 1;
  });
}
