# Homestead

A Home Assistant integration for the whole homestead: vegetable garden, greenhouse, orchard and chicken coop.

> **Status: early development.** Version 0.1 only creates a garden and stores its frost dates. Nothing useful happens yet.

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
