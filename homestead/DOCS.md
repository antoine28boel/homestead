# Homestead

Homestead keeps track of your vegetable garden and greenhouse, season after season: what grows where, what to do next, what you watered, fed and harvested.

## First steps

1. Open **Homestead** in the sidebar.
2. In **Settings**, set your frost dates. Every sowing, planting and harvest date is computed from them. **Compute from past weather** proposes them from the last thirty years where your garden is.
3. In **Spaces**, add your beds, raised beds, greenhouse and pots. A greenhouse gains about four weeks on frost in spring and autumn; you can change that per space.
4. In **Crops**, schedule what you grow. Homestead proposes the ways and windows that fit the crop and the space, and shows the steps ahead before you confirm.
5. Draw your **plan** (button on **Today** or **Spaces**), so that **Today** opens on it.

## The garden plan

- **Background:** import an aerial view (a screenshot of a map) or a drone photo, then **calibrate** it: tap the two ends of something you know the length of (a bed, a wall) and enter that length. Everything is then drawn to scale, in metres.
- **Spaces and objects:** place your beds, raised beds, greenhouse and pots, and add lawn, paths, a terrace, a pond, trees, shrubs, hedges, the compost, a rain tank, a shed or a greenhouse frame. Drag to move; the square handle resizes, the round one turns.
- **Crops:** open a space (**Arrange the crops**) to give each crop its own area, and choose how it is planted: grid, rows, staggered or free (tap to add or remove a plant). The spacing comes from the crop; you can change it. Crops without an area share the space.

## Steps and calendar

Each crop goes through its own steps, taken from the catalogue: sow under cover or in place, prick out into pots, harden off the seedlings (not for a greenhouse), plant out, then the jobs of the crop (stake, remove side shoots, thin out, earth up, pinch out…), the harvest and the end of harvest.

- Dates are first estimated from your frost dates and the space. When you record a real date (sown, planted out, harvest started), the steps that follow move with it.
- The crop's page lists its steps: done, to do, still to come, or passed without being ticked.
- **Calendar** (from **Crops** or **Today**) shows every step of every crop over the next twelve months.
- Steps due in the next two weeks are in **Today**'s to-do list; ticking them moves the crop on.

## Frost

- **Frost dates.** In **Settings**, **Compute from past weather** reads thirty years of daily minimum temperatures at your garden's position (from Home Assistant, rounded to about 10 km, sent once to [Open-Meteo](https://open-meteo.com/)). It proposes the dates after which frost came in spring, or before which it came in autumn, only one year in ten, with the averages for comparison. Nothing is saved until you choose **Use these dates** and save.
- **Forecast.** Homestead reads the daily minimums of a weather entity of Home Assistant every hour (the first one, or the one you choose in **Settings**). When a frosty night is forecast within a week:
  - crops standing in the open get a **Protect from frost** task the day before: tender crops (tomato, bean, squash…) from 1 °C, half-hardy ones (lettuce, chard…) from −2 °C; a greenhouse counts for 3 °C more;
  - planting out (and sowing tender crops in place) waits until the day after the last frosty night, with a ❄ note;
  - **Today** shows the coming frost.

## In Home Assistant

When the app starts, Home Assistant offers to add the **Homestead** integration (Settings → Devices & services). Accept it to get:

- a to-do list with the tasks of the next two weeks: ticking a task moves its crop to the next stage;
- a calendar of sowing, planting-out and harvest periods, with the jobs in between on their own day (ticked ones are marked ✓);
- a **Next frost** sensor (date, with the forecast minimum), for notifications;
- a device per space and per crop in progress, with its stage, next task, expected harvest and harvested weight;
- the actions `homestead.log_harvest` and `homestead.log_journal`, for buttons and automations (for example, log a watering when a valve closes);
- the **Garden plan** dashboard card (`custom:homestead-plan-card`), for every user of Home Assistant, not only administrators. The plan follows the season and, if you choose a weather entity, the weather (sun, clouds, rain, snow, fog, storm, wind) and the night. Plants grow with their stage and bear fruit at harvest time; planned crops are dashed. Tap a space to zoom in on it: its crops are named on the plan and listed below it, with their stage, number of plants, layout and next task. Tap a crop in the list to open it; tap × or outside the space to zoom out.

```yaml
type: custom:homestead-plan-card
weather: weather.home   # optional
title: Garden           # optional
```

The integration is installed from HACS.

## Data

Everything is stored in the app's data folder, which Home Assistant backups include. Nothing leaves your network.
