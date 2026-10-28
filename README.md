# Homestead

Your whole homestead in Home Assistant: vegetable garden, greenhouse, orchard and chicken coop. Every planting, season after season, with photos.

> **Status: early development.** Version 0.6 computes your **frost dates** from thirty years of local weather and watches the **forecast**: crops in the open get a task before a frost, and planting out waits. Version 0.5 schedules **every step of a crop** (sowing, pricking out, hardening off, planting out, staking, earthing up, harvest…) in the calendar. Version 0.4 added the **garden plan**: draw it over an aerial view or a drone photo, lay out every crop (grid, rows, staggered, free), and see it come alive on a dashboard card with the season and the weather. Version 0.3 brought the app + companion integration: spaces, seasons, crops, stages, tasks, calendar, journal and harvests. Not ready for everyday use yet.

## Goals

- **A crop calendar that works anywhere.** Sowing, transplanting and harvest windows follow *your* average frost dates, in both hemispheres.
- **Every planting, year after year:** stages, journal, harvests, photos, comparison between seasons, rotation and companion planting checks, seed stock, succession sowing.
- **A garden plan** you draw yourself, over an aerial view or a drone photo, with every plant in its place; on a dashboard it follows the season, the weather and the growth of each crop.
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

On Home Assistant OS, the app installs from the app store and the integration from HACS; the app announces itself, so the integration needs no address or token. On Container or Core installs, the same Docker image runs next to Home Assistant:

```bash
docker run -d --name homestead -p 8099:8099 -v homestead:/data -e TZ=Europe/Brussels -e HOMESTEAD_LANGUAGE=fr ghcr.io/antoine28boel/homestead:0.6.0
```

The API token for the integration is printed in the container log at startup. Set `HOMESTEAD_REQUIRE_TOKEN=1` to also protect the web interface; open it once with `/login?token=…`.

The detailed design (in French) is in [docs/CONCEPTION.fr.md](docs/CONCEPTION.fr.md). The crop catalogue format is described in [docs/catalog.md](docs/catalog.md).

## Development

| Folder | What | Tests |
|---|---|---|
| `homestead/server` | Python server (FastAPI, SQLAlchemy, Alembic) | `pip install "./homestead/server[test]"`, then `pytest` in that folder |
| `homestead/frontend` | Web interface (Vue 3, Vite) | `npm ci && npm run build`; `npm run dev` proxies `/api` to a server on port 8099 |
| `custom_components/homestead` | Companion integration | `pip install -r requirements_test.txt`, then `pytest` at the root (Python 3.14; Home Assistant does not run on Windows) |
| `homestead/` | App: `config.yaml`, `Dockerfile` | `docker build homestead` |

## License

Code: [MIT](LICENSE).
