# Homestead

Your whole homestead in Home Assistant: vegetable garden, greenhouse, orchard and chicken coop. Every planting, season after season, with photos.

> **Status: early development.** Version 0.2 is a stand-alone integration with a working crop calendar. The project is now moving to an **app + companion integration** architecture (see below). Not ready for everyday use yet.

## Goals

- **A crop calendar that works anywhere.** Sowing, transplanting and harvest windows follow *your* average frost dates, in both hemispheres.
- **Every planting, year after year:** stages, journal, harvests, photos, comparison between seasons, rotation and companion planting checks, seed stock, succession sowing.
- **A garden plan** you draw yourself.
- **Native to-do list and calendar** in Home Assistant, plus advice for each crop.
- **Water and climate:** a FAO-56 water balance that knows what grows in each bed and at which stage, soil moisture sensors, rain tank, frost alerts, greenhouse overheating, growing degree days. Valves are driven by Home Assistant automations, always with a maximum duration.
- **Photos:** album per planting, camera timelapse, growth tracking (green cover), plant identification, pest and disease detection, optional AI diagnosis.
- **Orchard and perennials:** fruit trees, soft fruit, perennial herbs, pruning, treatments, flowering and pollination, grafts.
- **Chicken coop:** flock register, daily eggs, automatic door, water and feed levels, care, temperature and lighting, camera.
- **Local first:** no account needed. Online services (Pl@ntNet, AI vision) are opt-in.

## Architecture

| Part | Role |
|---|---|
| **Homestead app** (container, sidebar page through ingress) | User interface, SQLite database with every season, photos, image processing, crop calendar and water balance |
| **Companion integration** (HACS) | Native entities (to-do list, calendar, stages, sensors), actions, dashboard cards, blueprints |

On Home Assistant OS, the app installs from the app store and the integration from HACS. On Container or Core installs, the same Docker image runs next to Home Assistant.

The detailed design (in French) is in [docs/CONCEPTION.fr.md](docs/CONCEPTION.fr.md). The crop catalogue format is described in [docs/catalog.md](docs/catalog.md).

## Development

The current integration (0.2) is tested with:

```bash
python3.14 -m venv .venv
. .venv/bin/activate
pip install -r requirements_test.txt
pytest
```

Home Assistant does not run on Windows: use Linux, macOS, WSL or a container.

## License

Code: [MIT](LICENSE).
