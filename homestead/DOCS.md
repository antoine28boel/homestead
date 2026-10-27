# Homestead

Homestead keeps track of your vegetable garden and greenhouse, season after season: what grows where, what to do next, what you watered, fed and harvested.

## First steps

1. Open **Homestead** in the sidebar.
2. In **Settings**, check your average frost dates. Every sowing, planting and harvest date is computed from them, so take them from a local gardener or your weather service.
3. In **Spaces**, add your beds, raised beds, greenhouse and pots. A greenhouse gains about four weeks on frost in spring and autumn; you can change that per space.
4. In **Crops**, add what you grow. Homestead proposes the ways and windows that fit the crop and the space.

## In Home Assistant

When the app starts, Home Assistant offers to add the **Homestead** integration (Settings → Devices & services). Accept it to get:

- a to-do list with the tasks of the next two weeks: ticking a task moves its crop to the next stage;
- a calendar of sowing, planting-out and harvest periods;
- a device per space and per crop in progress, with its stage, next task, expected harvest and harvested weight;
- the actions `homestead.log_harvest` and `homestead.log_journal`, for buttons and automations (for example, log a watering when a valve closes).

The integration is installed from HACS.

## Data

Everything is stored in the app's data folder, which Home Assistant backups include. Nothing leaves your network.
