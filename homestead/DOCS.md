# Homestead

Homestead keeps track of your vegetable garden and greenhouse, season after season: what grows where, what to do next, what you watered, fed and harvested.

## First steps

1. Open **Homestead** in the sidebar.
2. In **Settings**, check your average frost dates. Every sowing, planting and harvest date is computed from them, so take them from a local gardener or your weather service.
3. In **Spaces**, add your beds, raised beds, greenhouse and pots. A greenhouse gains about four weeks on frost in spring and autumn; you can change that per space.
4. In **Crops**, add what you grow. Homestead proposes the ways and windows that fit the crop and the space.
5. Draw your **plan** (button on **Today** or **Spaces**), so that **Today** opens on it.

## The garden plan

- **Background:** import an aerial view (a screenshot of a map) or a drone photo, then **calibrate** it: tap the two ends of something you know the length of (a bed, a wall) and enter that length. Everything is then drawn to scale, in metres.
- **Spaces and objects:** place your beds, raised beds, greenhouse and pots, and add lawn, paths, a terrace, a pond, trees, shrubs, hedges, the compost, a rain tank, a shed or a greenhouse frame. Drag to move; the square handle resizes, the round one turns.
- **Crops:** open a space (**Arrange the crops**) to give each crop its own area, and choose how it is planted: grid, rows, staggered or free (tap to add or remove a plant). The spacing comes from the crop; you can change it. Crops without an area share the space.

## In Home Assistant

When the app starts, Home Assistant offers to add the **Homestead** integration (Settings → Devices & services). Accept it to get:

- a to-do list with the tasks of the next two weeks: ticking a task moves its crop to the next stage;
- a calendar of sowing, planting-out and harvest periods;
- a device per space and per crop in progress, with its stage, next task, expected harvest and harvested weight;
- the actions `homestead.log_harvest` and `homestead.log_journal`, for buttons and automations (for example, log a watering when a valve closes);
- the **Garden plan** dashboard card (`custom:homestead-plan-card`), for every user of Home Assistant, not only administrators. The plan follows the season and, if you choose a weather entity, the weather (sun, clouds, rain, snow, fog, storm, wind) and the night. Plants grow with their stage and bear fruit at harvest time; planned crops are dashed. Tap a space or a crop to open it.

```yaml
type: custom:homestead-plan-card
weather: weather.home   # optional
title: Garden           # optional
```

The integration is installed from HACS.

## Data

Everything is stored in the app's data folder, which Home Assistant backups include. Nothing leaves your network.
