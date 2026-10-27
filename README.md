# Homestead

A Home Assistant integration for the whole homestead: vegetable garden, greenhouse, orchard and chicken coop.

> **Status: early development (0.2).** The crop calendar works: spaces, plantings, stages, to-do list and calendar. Watering, orchard and coop come next.

## What it does today

- **A garden** with its average frost dates, which every date is computed from.
- **Spaces** (open ground, raised bed, greenhouse, pots), added from the garden's page. Sheltered spaces gain weeks on frost.
- **Plantings**: pick a space and a crop from the [catalogue](docs/catalog.md) (30 common vegetables and herbs), then how and when to start it. Each planting is a device with:
  - a **stage** selector: planned, sown, planted out, growing, harvesting, finished;
  - its **next task** and when it is due;
  - the **expected harvest** date.
- **A to-do list** of the tasks due in the next two weeks: sow, transplant, stake, earth up, start harvesting… Ticking a task moves its planting to the next stage. You can add your own items too.
- **A calendar** of sowing, planting-out and harvest periods.
- Per space, the crops **that can be sown or planted now**.
- English and French.

## Goals

- **Crop calendar that works anywhere.** Sowing, transplanting and harvest windows are expressed relative to *your* average frost dates, not to fixed months. They work in both hemispheres.
- **Track every planting** from sowing to harvest: stage, journal, yields.
- **A native to-do list and calendar** of what to do in the garden today, this week, this season.
- **Watering guidance** from Home Assistant's weather, a FAO-56 water balance that knows what grows in each bed and at which stage, and soil moisture sensors if you have any.
- **Greenhouse and frost alerts**, and blueprints to act on them (valves, vents, coop door).
- **Orchard and coop:** pruning and treatment reminders, flock and egg log.
- **Local only:** no account, no cloud. Everything is stored in Home Assistant and included in its backups.

The detailed design (in French) is in [docs/CONCEPTION.fr.md](docs/CONCEPTION.fr.md).

## Installation (HACS custom repository)

1. In HACS, open the menu ⋮ → *Custom repositories*, add `https://github.com/antoine28boel/homestead` with the type *Integration*.
2. Install **Homestead** and restart Home Assistant.
3. Go to *Settings → Devices & services → Add integration → Homestead*.

## Development

```bash
python3.14 -m venv .venv
. .venv/bin/activate
pip install -r requirements_test.txt
pytest
```

Home Assistant does not run on Windows: use Linux, macOS, WSL or a container.

## License

Code: [MIT](LICENSE).
