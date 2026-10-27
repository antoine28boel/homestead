# The species catalogue

Each crop is a YAML file in [`custom_components/homestead/catalog/`](../custom_components/homestead/catalog/), named after its `id`. Contributions are welcome: add a species, fix a value, translate the names.

```yaml
id: tomato
names: {en: Tomato, fr: Tomate, nl: Tomaat, de: Tomate}   # en is required
family: solanaceae
frost: tender               # tender, half_hardy or hardy
sow_indoors:                # sowing under cover, then transplanting
  - {start: -8, end: -6}
sow_direct: []              # sowing in place
transplant:                 # planting out (seedlings or bought plants)
  - {start: 1, end: 3}
germination_days: [6, 12]
harvest: {after: transplant, days: [60, 85], weeks: 10}
spacing_cm: {plant: 50, row: 70}
tasks:
  - {id: stake, after: transplant, days: 7, label: {en: Stake, fr: Tuteurer}}
```

## Windows

- `start` and `end` are **weeks from the average last frost of spring**. `-8` means eight weeks before it.
- Add `ref: first_frost` to count from the first frost of autumn instead, for autumn sowings such as lamb's lettuce or garlic.
- A species can have several windows per method, for example a spring and an autumn sowing of spinach.
- A window can override the days to harvest with `harvest_days: [min, max]`, for example garlic planted in autumn.
- Spaces gain weeks on frost (4 for an unheated greenhouse by default), so the same windows give earlier dates under cover.

## Harvest

- `after` is `sowing` or `transplant`: the date the days are counted from.
- `days` is the range of days to the first harvest.
- `weeks` is how long the harvest lasts.

## Tasks

One-off jobs, `days` after `sowing` or `transplant`. `label` needs at least `en`.

## Sources

Values must come from general horticultural knowledge or from sources whose licence allows reuse. Please do not copy proprietary databases or seed catalogues.
