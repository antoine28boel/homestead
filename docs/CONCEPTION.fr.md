# Homestead – intégration Home Assistant pour le jardin, la serre, le verger et le poulailler

*Proposition du 25/10/2026, mise à jour le 27/10/2026 (nom retenu : **Homestead**, domaine `homestead`). Ce document sert de base de discussion.*

**Objectif :** suivre dans Home Assistant chaque culture du potager, de la serre et du verger, ainsi que le futur poulailler. Il s'agit de savoir quand arroser, semer, repiquer, récolter, tailler ou traiter, et ce qu'il y a à faire au jardin tout au long de l'année. L'intégration doit pouvoir être **installée par n'importe quel utilisateur de HA** (via HACS), quels que soient son climat et ses capteurs.

---

## 1. Ce qui existe déjà (et ce qui manque)

| Projet | Ce qu'il fait | Limite pour notre besoin |
|---|---|---|
| `plant` (cœur de HA) | Seuils d'humidité, de lumière et de température par plante, à partir d'un capteur (MiFlora…) | Pas de calendrier ni de cycle de culture. En YAML uniquement |
| [Plant Monitor (Olen)](https://github.com/Olen/homeassistant-plant) + OpenPlantbook + flower-card | Un appareil par plante, avec des seuils récupérés automatiquement selon l'espèce | Pensé pour une plante en pot avec son capteur, pas pour une planche de 20 poireaux |
| [Smart Irrigation](https://github.com/altmenorg/HAsmartirrigation) | Calcule la durée d'arrosage à partir de l'évapotranspiration, de la pluie et des prévisions, par zone | Ne sait rien des cultures ni de leur stade. Le besoin d'une salade qui vient d'être repiquée n'est pas celui d'une courge en août |
| [HomeGrow](https://github.com/magikh0e/ha-home-grow) (alpha, 06/2026) | Une plante = un appareil : stade, santé, âge, calendrier de fertilisation | Orienté culture en intérieur, sans calendrier de saison ni météo |
| [Seedtime](https://community.home-assistant.io/t/seedtime-integration/982670) | Affiche dans HA le plan et le calendrier d'un service en ligne | Dépend d'un service payant dans le nuage |
| [MijnTuin](https://github.com/myTselection/MijnTuin) | Plantes et travaux de jardin (service belge) | Ne fonctionne plus depuis la fermeture du service (05/2024) |
| Plant-it (déjà sur le serveur) | Carnet de soins des plantes, photos | Pas de lien avec HA, ne connaît ni la météo ni les capteurs |
| Poulailler | Rien de dédié : bricolages ESPHome (porte au lever et au coucher du soleil, niveaux d'eau et de grain), porte Omlet | Pas de suivi du troupeau ni des œufs |

**Le vide à combler :** rien ne relie aujourd'hui **le calendrier du jardinier** (quoi faire, quand, selon le climat), **le suivi de chaque culture** (stade, récoltes) et **les capteurs et la météo** (arrosage, gel, chaleur dans la serre). C'est le cœur de l'intégration.

---

## 2. Principes

1. **Tout reste dans HA**, sans compte ni service en ligne obligatoire. Les données sont stockées par HA et incluses dans ses sauvegardes.
2. **Fonctionne sans aucun capteur.** Avec seulement la météo de HA, on a déjà le calendrier, les tâches et une estimation de l'arrosage. Chaque capteur ajouté rend le résultat plus précis.
3. **Indépendant du climat.** Les dates du catalogue ne sont pas fixées au calendrier (« semer en avril »). Elles sont exprimées **par rapport aux dates de gel** du lieu (« semer sous abri 6 semaines avant les dernières gelées »). Ça fonctionne aussi bien à Profondeville qu'à Montréal ou en Australie, hémisphère sud compris.
4. **Ne pas refaire ce qui existe.** OpenPlantbook, Plant Monitor et Smart Irrigation peuvent être utilisés s'ils sont installés.
5. **Aucune action physique imposée.** L'intégration *dit* qu'il faut arroser ou fermer la serre. Ouvrir une vanne ou une porte, c'est le rôle des automatisations et des blueprints fournis, que l'utilisateur choisit d'activer. Elle peut piloter une vanne, mais seulement si l'utilisateur la désigne explicitement, et toujours avec une durée maximale.
6. **Standards de la communauté :** code en anglais, traductions en anglais et en français dès le départ, configuration 100 % par l'interface, tests et validation HACS/hassfest.

---

## 3. Modèle de données

```
Jardin (une entrée d'intégration)
├── Profil climatique : position (celle de HA), dates moyennes des dernières et premières gelées,
│                       hémisphère, sources météo (weather.*, pluviomètre, capteur de température)
├── Espaces (sous-entrées)
│   ├── type : planche / carré potager / serre / tunnel / pots / verger / pelouse / poulailler
│   ├── surface, exposition, sol, abri (oui/non)
│   ├── capteurs facultatifs : humidité du sol, température, humidité de l'air, vanne d'arrosage
│   └── Cultures
│       ├── espèce (catalogue) + variété libre
│       ├── quantité, mode (semis direct, semis sous abri, plant acheté)
│       ├── cycle : prévue → semée → levée → repiquée → en croissance → en récolte → terminée
│       └── journal : arrosages, apports, traitements, récoltes (kg ou pièces), observations
├── Vivaces et arbres (verger, petits fruits, aromatiques) : taille, traitements, récolte, chaque année
└── Troupeau (poulailler) : poules (nom, race, date de naissance), œufs du jour, grain, eau, porte
```

### Le catalogue (le vrai trésor communautaire)

Un fichier par espèce, en YAML, dans le dépôt. Chacun peut l'enrichir par une demande de fusion (*pull request*) :

```yaml
# catalogue/legumes/tomate.yaml
id: tomato
famille: solanaceae
noms: { fr: Tomate, en: Tomato, nl: Tomaat }
semis_abri:      { debut: -8, fin: -6, reference: derniere_gelee }   # en semaines
repiquage:       { debut: +1, fin: +3, reference: derniere_gelee, temperature_min: 10 }
semis_direct:    null
recolte:         { jours_apres_repiquage: [60, 85] }
gel: sensible                      # sensible / rustique / tres_rustique
temperature: { min: 10, optimale: [20, 27], max: 35 }
eau:
  kc: { initial: 0.6, croissance: 1.15, fin: 0.8 }    # coefficients culturaux FAO-56
  profondeur_racines_cm: 70
espacement_cm: { rang: 70, plant: 50 }
compagnons: [basil, carrot]
a_eviter: [potato, fennel]
rotation: { groupe: fruits, retour_ans: 4 }
taches:
  - { quoi: tuteurer, quand: { jours_apres_repiquage: 15 } }
  - { quoi: egourmander, recurrence_jours: 7, periode: croissance }
openplantbook_pid: solanum lycopersicum
```

- Pour démarrer : une **cinquantaine d'espèces courantes** (légumes, aromatiques, petits fruits, arbres fruitiers) rédigées à partir de connaissances agronomiques générales. Aucune base existante n'est recopiée.
- Les coefficients d'eau (Kc) viennent de la méthode FAO-56, qui est publique.
- Pour les sources externes, il faudra vérifier les licences. Les données d'OpenFarm, fermé en 2025, ont un statut flou. Le calendrier des cultures légumières de l'INRAE est sous licence Etalab 2.0, ce qui permet de le réutiliser en citant la source.
- Un **catalogue personnel** (dans HA) permet d'ajouter ses propres variétés, sans passer par le dépôt.

---

## 4. Ce que voit l'utilisateur dans HA

| Entité | Exemple | Rôle |
|---|---|---|
| `todo` (liste de tâches native) | `todo.<jardin>_taches` | « Semer les tomates sous abri », « Tuteurer les tomates (planche 2) », « Tailler le pommier ». Générée automatiquement ; cocher une tâche l'inscrit au journal |
| `calendar` | `calendar.<jardin>` | Fenêtres de semis, de repiquage et de récolte, à afficher dans le calendrier de HA |
| `sensor` par culture | stade, jours depuis le semis, récolte prévue, kg récoltés | Suivi de la culture |
| `sensor` par espace | besoin en eau (mm), réserve du sol (%), degrés-jours | Arrosage et croissance |
| `binary_sensor` par espace | à arroser, risque de gel, surchauffe de la serre | Déclencheurs des automatisations |
| `sensor` / `number` troupeau | œufs aujourd'hui et sur 7 jours, ponte moyenne, niveau d'eau | Poulailler |
| Actions (services) | `homestead.add_planting`, `homestead.log_watering`, `homestead.log_harvest`, `homestead.log_eggs`, `homestead.set_stage` | Utilisables dans les scripts, les automatisations et les boutons du tableau de bord |
| Événements | `homestead_task_due`, `homestead_alert` | Pour les notifications |

**Blueprints fournis :**
- notification du matin « au jardin aujourd'hui » ;
- alerte de gel : rentrer les pots, voiler, fermer la serre ;
- serre trop chaude : ouvrir ou ventiler ;
- arrosage par vanne avec durée maximale, sans arroser s'il a plu ou s'il va pleuvoir ;
- porte du poulailler au lever et au coucher du soleil, avec vérification qu'elle est bien fermée.

---

## 5. Le calcul de l'arrosage

Pour chaque espace, un **bilan hydrique** quotidien, inspiré de FAO-56 :

```
réserve du sol (mm) = réserve d'hier + pluie efficace + arrosages notés − ET0 × Kc(culture, stade)
```

- **ET0** (évapotranspiration de référence) : calculée à partir de la météo de HA (température min et max, et rayonnement s'il est disponible) avec la méthode de Hargreaves, ou lue dans Smart Irrigation s'il est installé.
- **Kc** : la moyenne des cultures présentes dans l'espace, selon leur stade. C'est ce qui nous distingue de Smart Irrigation.
- **Serre / abri** : pas de pluie, ET0 corrigée par la température intérieure.
- **Capteur d'humidité du sol présent** : il prime sur le calcul, qui est recalé sur sa mesure. Le calcul sert alors de garde-fou si le capteur tombe en panne ou se décharge.
- **Résultat :** « arroser 12 mm » (→ litres selon la surface, → minutes si le débit de la vanne est connu).

---

## 6. Interface

- **Phase 1** : uniquement les cartes natives (liste de tâches, calendrier, tuiles). Aucune dépendance.
- **Phase suivante :** un **panneau latéral « Jardin »** pour gérer les espaces, les cultures et le journal confortablement (comme le panneau de Smart Irrigation), puis une **carte de tableau de bord** : plan du jardin, chronologie des cultures.
- Pour notre maison : des fiches Bubble Card générées par `tools/dashboard_app.py`, dans le style du tableau de bord « Smartphones » (le décor de saison d'`accueil_deco.py` pourrait montrer le potager réel).

---

## 7. Étapes proposées

| Phase | Contenu | Résultat |
|---|---|---|
| 0. Fondations | Nom, dépôt GitHub, squelette d'intégration, tests (`pytest-homeassistant-custom-component`), validation HACS et hassfest automatisée | S'installe dans HA et ne fait encore rien |
| 1. Calendrier | Profil climatique, catalogue de 30 à 50 espèces, espaces, cultures, cycle, liste de tâches, calendrier, traductions fr/en | Utilisable chez nous dès cet hiver pour planifier la saison 2027 |
| 2. Capteurs et arrosage | Bilan hydrique, risques de gel et de surchauffe, blueprints, capteurs d'humidité du sol, vannes | Prêt pour les premiers semis sous abri (février-mars 2027) |
| 3. Verger et poulailler | Vivaces et arbres (taille, traitements), troupeau, œufs, porte | Prêt à l'arrivée des poules |
| 4. Communauté | Panneau et carte, catalogue enrichi, néerlandais et allemand, documentation, demande d'inscription dans la liste par défaut de HACS | Version 1.0 publique |

Avant de publier : tester sur une installation HA vierge (conteneur de développement) et pas seulement chez nous.

---

## 8. Questions à trancher

1. ~~**Nom**~~ : **Homestead**, domaine `homestead` (27/10/2026).
2. **Dépôt GitHub** : sur ton compte personnel ? Je prépare le code, mais c'est toi qui crées le dépôt et qui publies.
3. ~~**Plant-it**~~ : supprimé par le propriétaire le 27/10/2026. Il n'y a rien à importer.
4. **Capteurs prévus** : quels modèles d'humidité du sol, de station météo et de vannes (Zigbee, ESPHome, Gardena…) ? Pas bloquant pour la phase 1, mais utile pour bien concevoir la phase 2.
5. **Le jardin lui-même** : la liste des espaces (combien de planches, la taille de la serre, les arbres du verger) permettra de choisir les premières espèces du catalogue et de tester avec de vraies données.
