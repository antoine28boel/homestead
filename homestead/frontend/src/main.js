import { createApp } from "vue";
import { createRouter, createWebHashHistory } from "vue-router";

import App from "./App.vue";
import { adoptHomeAssistantTheme } from "./theme.js";
import { start } from "./store.js";
import "./style.css";

import Calendar from "./views/Calendar.vue";
import PlanEditor from "./views/PlanEditor.vue";
import PlantingDetail from "./views/PlantingDetail.vue";
import PlantingNew from "./views/PlantingNew.vue";
import Plantings from "./views/Plantings.vue";
import QuickEntry from "./views/QuickEntry.vue";
import Settings from "./views/Settings.vue";
import SpacePlan from "./views/SpacePlan.vue";
import Spaces from "./views/Spaces.vue";
import Today from "./views/Today.vue";

// Hash history: the server only serves index.html at the root.
const router = createRouter({
  history: createWebHashHistory(),
  routes: [
    { path: "/", component: Today },
    { path: "/plantings", component: Plantings },
    { path: "/plantings/new", component: PlantingNew },
    { path: "/plantings/:id", component: PlantingDetail, props: true },
    { path: "/calendar", component: Calendar },
    { path: "/log", component: QuickEntry },
    { path: "/spaces", component: Spaces },
    { path: "/plan", component: PlanEditor },
    { path: "/plan/spaces/:id", component: SpacePlan, props: true },
    { path: "/settings", component: Settings },
  ],
  scrollBehavior: () => ({ top: 0 }),
});

adoptHomeAssistantTheme();
start();
createApp(App).use(router).mount("#app");
