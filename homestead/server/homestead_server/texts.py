"""Texts built by the server: task summaries, calendar events, start choices.

They are shared by the web interface and the Home Assistant to-do list and
calendar, so they are written once here. English is the fallback.
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
        "harden_off": "Harden off the seedlings: {name}",
        "frost": "Protect from frost: {name} ({space})",
        "frost_night": "Forecast low: {low} °C on {day}.",
        "frost_hold": "Frost forecast on {day} ({low} °C): wait until {until}.",
        "harvest_start": "Start harvesting: {name} ({space})",
        "harvest_end": "End of harvest, clear the space: {name} ({space})",
        "crop": "{label}: {name} ({space})",
        "period": "Window: {start} – {end}.",
        "spacing": "Spacing: {plant} cm in the row, {row} cm between rows.",
        "event_sow": "Sowing: {name}",
        "event_transplant": "Planting out: {name}",
        "event_harvest": "Harvest: {name}",
        "event_step": "{label}: {name}",
        "step_sow_indoors": "Sow under cover",
        "step_sow_direct": "Sow in place",
        "step_plant": "Plant out",
        "step_transplant": "Plant out",
        "step_harden_off": "Harden off the seedlings",
        "step_harvest_start": "Harvest",
        "step_harvest_end": "End of harvest",
        "choice_sow_indoors": "Sow under cover, {start} – {end}",
        "choice_sow_direct": "Sow in place, {start} – {end}",
        "choice_plant": "Plant out, {start} – {end}",
        "note_rotation": (
            "Same family ({family}) here in {season}: {name}. "
            "Leave {years} years between them."
        ),
        "note_avoid": "Bad neighbour close by: {name}.",
        "note_companion": "Good neighbour: {name}.",
        "family_amaranthaceae": "beet family",
        "family_amaryllidaceae": "alliums",
        "family_apiaceae": "carrot family",
        "family_asteraceae": "daisy family",
        "family_brassicaceae": "brassicas",
        "family_caprifoliaceae": "valerian family",
        "family_cucurbitaceae": "cucurbits",
        "family_fabaceae": "legumes",
        "family_lamiaceae": "mint family",
        "family_poaceae": "grasses",
        "family_solanaceae": "nightshades",
        "no_space": "?",
        "date": "%Y-%m-%d",
        "decimal": ".",
    },
    "fr": {
        "sow_indoors": "Semer sous abri : {name}",
        "sow_direct": "Semer : {name} ({space})",
        "plant": "Planter : {name} ({space})",
        "transplant": "Repiquer : {name} → {space}",
        "harden_off": "Endurcir les plants : {name}",
        "frost": "Protéger du gel : {name} ({space})",
        "frost_night": "Minimum prévu : {low} °C le {day}.",
        "frost_hold": "Gel prévu le {day} ({low} °C) : attendre le {until}.",
        "harvest_start": "Début de récolte : {name} ({space})",
        "harvest_end": "Fin de récolte, libérer la place : {name} ({space})",
        "crop": "{label} : {name} ({space})",
        "period": "Période : du {start} au {end}.",
        "spacing": "Espacement : {plant} cm sur le rang, {row} cm entre les rangs.",
        "event_sow": "Semis : {name}",
        "event_transplant": "Mise en place : {name}",
        "event_harvest": "Récolte : {name}",
        "event_step": "{label} : {name}",
        "step_sow_indoors": "Semer sous abri",
        "step_sow_direct": "Semer en place",
        "step_plant": "Planter",
        "step_transplant": "Mettre en place",
        "step_harden_off": "Endurcir les plants",
        "step_harvest_start": "Récolte",
        "step_harvest_end": "Fin de récolte",
        "choice_sow_indoors": "Semis sous abri, du {start} au {end}",
        "choice_sow_direct": "Semis en place, du {start} au {end}",
        "choice_plant": "Plantation, du {start} au {end}",
        "note_rotation": (
            "Même famille ({family}) ici en {season} : {name}. "
            "Laisser {years} ans entre les deux."
        ),
        "note_avoid": "Mauvais voisin à proximité : {name}.",
        "note_companion": "Bon voisin : {name}.",
        "family_amaranthaceae": "amarantacées",
        "family_amaryllidaceae": "alliacées",
        "family_apiaceae": "ombellifères",
        "family_asteraceae": "astéracées",
        "family_brassicaceae": "crucifères",
        "family_caprifoliaceae": "valérianacées",
        "family_cucurbitaceae": "cucurbitacées",
        "family_fabaceae": "légumineuses",
        "family_lamiaceae": "lamiacées",
        "family_poaceae": "graminées",
        "family_solanaceae": "solanacées",
        "no_space": "?",
        "date": "%d/%m/%Y",
        "decimal": ",",
    },
}


class Texts:
    """Texts in the language of the garden."""

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

    def temperature(self, value: float) -> str:
        """A temperature to the tenth of a degree, without trailing zero."""
        text = f"{round(value, 1):g}".replace(".", self._texts["decimal"])
        return text.replace("-", "\u2212")

    def family(self, family: str) -> str:
        """Common name of a botanical family, or the family itself."""
        return self._texts.get(f"family_{family}", family)

    def label(self, label: dict[str, str]) -> str:
        """Label of a catalogue task."""
        return localized(label, self.language)
