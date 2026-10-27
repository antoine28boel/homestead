"""Texts built at runtime (task summaries, calendar events, form choices).

Home Assistant translation files cannot hold free-form texts with
placeholders for to-do items or calendar events, so they live here.
English is the fallback for missing languages.
"""

from __future__ import annotations

from datetime import date

from .catalog import localized

TEXTS: dict[str, dict[str, str]] = {
    "en": {
        "sow_indoors": "Sow under cover: {name}",
        "sow_direct": "Sow: {name} ({space})",
        "plant": "Plant out: {name} ({space})",
        "transplant": "Transplant: {name} → {space}",
        "harvest_start": "Start harvesting: {name} ({space})",
        "harvest_end": "End of harvest, clear the space: {name} ({space})",
        "crop": "{label}: {name} ({space})",
        "period": "Window: {start} – {end}.",
        "spacing": "Spacing: {plant} cm in the row, {row} cm between rows.",
        "event_sow": "Sowing: {name}",
        "event_transplant": "Planting out: {name}",
        "event_harvest": "Harvest: {name}",
        "choice_sow_indoors": "Sow under cover, {start} – {end}",
        "choice_sow_direct": "Sow in place, {start} – {end}",
        "choice_plant": "Plant out, {start} – {end}",
        "no_space": "?",
        "date": "%Y-%m-%d",
    },
    "fr": {
        "sow_indoors": "Semer sous abri : {name}",
        "sow_direct": "Semer : {name} ({space})",
        "plant": "Planter : {name} ({space})",
        "transplant": "Repiquer : {name} → {space}",
        "harvest_start": "Début de récolte : {name} ({space})",
        "harvest_end": "Fin de récolte, libérer la place : {name} ({space})",
        "crop": "{label} : {name} ({space})",
        "period": "Période : du {start} au {end}.",
        "spacing": "Espacement : {plant} cm sur le rang, {row} cm entre les rangs.",
        "event_sow": "Semis : {name}",
        "event_transplant": "Mise en place : {name}",
        "event_harvest": "Récolte : {name}",
        "choice_sow_indoors": "Semis sous abri, du {start} au {end}",
        "choice_sow_direct": "Semis en place, du {start} au {end}",
        "choice_plant": "Plantation, du {start} au {end}",
        "no_space": "?",
        "date": "%d/%m/%Y",
    },
}


class Texts:
    """Texts in the language of Home Assistant."""

    def __init__(self, language: str) -> None:
        """Pick the language, falling back to English."""
        self.language = language
        short = language.split("-")[0]
        self._texts = TEXTS["en"] | TEXTS.get(short, {}) | TEXTS.get(language, {})

    def __call__(self, key: str, **values: object) -> str:
        """Format a text."""
        return self._texts[key].format(**values)

    def date(self, value: date) -> str:
        """Format a date the way the language usually writes it."""
        return value.strftime(self._texts["date"])

    def label(self, label: dict[str, str]) -> str:
        """Label of a catalogue task."""
        return localized(label, self.language)
