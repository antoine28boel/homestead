# Homestead – jardin, serre, verger et poulailler dans Home Assistant

*Conception commencée le 25/10/2026, revue le 27/10/2026 : périmètre et architecture validés par le propriétaire (application + intégration compagnon, hébergée dans HA OS).*

**Objectif :** suivre dans Home Assistant chaque culture du potager, de la serre et du verger, d'année en année et en photos, ainsi que le futur poulailler. Savoir quand semer, repiquer, arroser, récolter, tailler ou traiter. Le projet doit pouvoir être **installé par n'importe quel utilisateur de HA**, quels que soient son climat et ses capteurs.

---

## 1. Ce qui existe déjà (et ce qui manque)

| Projet | Ce qu'il fait | Limite pour notre besoin |
|---|---|---|
| `plant` (cœur de HA) | Seuils d'humidité, de lumière et de température par plante, à partir d'un capteur (MiFlora…) | Pas de calendrier ni de cycle de culture. En YAML uniquement |
| [Plant Monitor (Olen)](https://github.com/Olen/homeassistant-plant) + OpenPlantbook + flower-card | Un appareil par plante, avec des seuils récupérés automatiquement selon l'espèce | Pensé pour une plante en pot avec son capteur, pas pour une planche de 20 poireaux |
| [Smart Irrigation](https://github.com/altmenorg/HAsmartirrigation) | Durée d'arrosage calculée à partir de l'évapotranspiration, de la pluie et des prévisions, par zone | Ne sait rien des cultures ni de leur stade |
| [HomeGrow](https://github.com/magikh0e/ha-home-grow) (alpha, 06/2026) | Une plante = un appareil : stade, santé, âge, calendrier de fertilisation | Orienté culture en intérieur, sans calendrier de saison ni météo |
| [Seedtime](https://community.home-assistant.io/t/seedtime-integration/982670) | Affiche dans HA le plan et le calendrier d'un service en ligne | Dépend d'un service payant dans le nuage |
| [MijnTuin](https://github.com/myTselection/MijnTuin) | Plantes et travaux de jardin (service belge) | Ne fonctionne plus depuis la fermeture du service (05/2024) |
| Poulailler | Rien de dédié : bricolages ESPHome (porte au lever et au coucher du soleil, niveaux d'eau et de grain), porte Omlet | Pas de suivi du troupeau ni des œufs |

**Le vide à combler :** rien ne relie aujourd'hui **le calendrier du jardinier**, **le suivi de chaque culture** (stade, récoltes, photos, historique) et **les capteurs et la météo**.

---

## 2. Périmètre retenu (27/10/2026)

| Domaine | Fonctionnalités |
|---|---|
| **Cultures** | Calendrier selon les dates de gel ; stades ; journal (arrosages, apports, traitements, observations) ; récoltes pesées ou comptées ; historique et comparaison d'année en année ; rotation ; associations ; plan du jardin dessiné ; grainothèque (stock, péremption) ; semis échelonnés |
| **Guidage** | Liste de tâches HA ; calendrier HA ; conseils par culture |
| **Eau et climat** | Besoin en eau calculé avec la météo ; sondes d'humidité du sol ; pilotage des vannes ; alertes de gel ; surchauffe et ventilation de la serre ; cuve d'eau de pluie ; degrés-jours |
| **Photos** | Album par culture et par saison ; timelapse avec une caméra ; suivi de croissance (surface verte) ; identification de plantes et de mauvaises herbes ; détection de maladies et de ravageurs ; diagnostic par IA de vision (en ligne, en option) ; maturité et comptage des fruits |
| **Verger et vivaces** | Arbres fruitiers ; petits fruits ; aromatiques vivaces ; taille et traitements ; floraison et pollinisation ; greffes |
| **Poulailler** | Registre des poules ; ponte quotidienne ; porte automatique ; niveaux d'eau et de grain ; soins (vermifuge, mue, poux) ; température et éclairage ; caméra |
| **Interface** | Page dans la barre latérale ; cartes de tableau de bord ; saisie rapide au jardin sur smartphone ; statistiques (rendement par culture et par m²) |
| **Permaculture** (proposée le 29/10/2026) | Sol vivant (paillis, compost, engrais verts) ; fonctions des plantes ; planches mixtes et vivaces ; zones et ensoleillement ; eau captée ; strates et guildes ; biodiversité ; compost et boucles avec le poulailler ; graines produites sur place ; bilan d'autonomie (voir §7) |

**Écartés pour l'instant :** notification du matin, travaux de saison généraux, calendrier lunaire, dépenses, export CSV/PDF, plusieurs jardiniers.

---

## 3. Principes

1. **Tout reste chez soi.** Aucun compte ni service en ligne obligatoire. Les services en ligne (Pl@ntNet, IA de vision) sont des options désactivées par défaut. Les données sont incluses dans les sauvegardes de HA.
2. **Fonctionne sans capteur.** Avec seulement la météo de HA, on a le calendrier, les tâches et une estimation de l'arrosage. Chaque capteur ajouté rend le résultat plus précis.
3. **Indépendant du climat.** Les dates du catalogue sont exprimées **par rapport aux dates de gel** du lieu. Ça fonctionne à Profondeville comme à Montréal, hémisphère sud compris.
4. **L'application propose, HA exécute.** Vannes, ouvrants de serre et porte du poulailler sont pilotés par des automatisations et des blueprints, toujours avec une durée maximale et un état vérifié. L'application ne commande jamais un appareil directement.
5. **Standards de la communauté :** code en anglais, interface traduite en anglais et en français dès le départ, configuration par l'interface, tests automatisés.

---

## 4. Architecture

Sur le modèle de Frigate ou de Music Assistant : une **application** qui fait le travail, et une **intégration compagnon** qui l'expose dans HA.

```
┌─────────────── Application Homestead (conteneur, ingress) ───────────────┐
│ Interface web : page « Jardin » dans la barre latérale (et dans l'app     │
│ mobile HA) : plan, fiches, journal, récoltes, album, grainothèque,        │
│ verger, poulailler, statistiques                                          │
│ API REST + WebSocket (événements)                                         │
│ Base SQLite : toutes les saisons, depuis la première                      │
│ Photos et vignettes (dossier de données de l'application)                 │
│ Traitement d'image : OpenCV, petits modèles ONNX, Pl@ntNet, IA en option  │
│ Moteur : catalogue, calendrier, tâches, bilan hydrique, degrés-jours      │
│ Lecture de HA : météo, sondes, caméras (API Supervisor ou jeton)          │
└──────────────────────────────────┬────────────────────────────────────────┘
                                   │ API locale
┌──────────────────────────────────┴───────── Intégration compagnon (HACS) ─┐
│ Découverte automatique de l'application                                    │
│ Entités : liste de tâches, calendrier, stades, prochaine tâche, récolte    │
│ prévue, besoin en eau, gel, serre, cuve, ponte, degrés-jours               │
│ Actions : noter une récolte, une ponte, un arrosage, changer un stade      │
│ Cartes de tableau de bord (JavaScript livré avec l'intégration)            │
│ Blueprints : arrosage, gel, serre, porte du poulailler                     │
└────────────────────────────────────────────────────────────────────────────┘
```

**Pourquoi deux briques.** Les photos, le plan dessiné, l'historique pluriannuel et le traitement d'image demandent une base de données, du stockage et une interface riche : c'est le rôle d'une application. Mais une application ne peut créer ni liste de tâches ni calendrier dans HA : l'intégration s'en charge, pour que tout reste utilisable dans les automatisations et les tableaux de bord.

**Installations prises en charge :**
- **HA OS :** l'application s'installe depuis le magasin d'applications de HA (dépôt ajouté une fois), et l'intégration via HACS.
- **HA Container ou Core :** même image Docker, lancée à côté de HA. On donne à l'intégration l'adresse de l'application, et à l'application un jeton d'accès à HA.

**Chez nous :** application dans la VM HA OS (4 vCPU, 8 Go), pour profiter des sauvegardes de HA et de la page dans la barre latérale. Le développement et les tests se font sur le serveur Debian.

### Dépôt unique `antoine28boel/homestead`

```
homestead/
├── repository.yaml              ← dépôt d'applications HA
├── homestead/                   ← application : config.yaml, Dockerfile, DOCS.md
│   ├── server/                  ← serveur Python (FastAPI)
│   │   ├── homestead_server/
│   │   │   ├── catalog/  catalog.py  planner.py  texts.py  (repris de la phase 1)
│   │   │   ├── orm.py  db.py  migrations/   (tables, Alembic)
│   │   │   ├── garden.py  api.py  events.py  ha.py
│   │   │   └── (plus tard : vision/  water/)
│   │   └── tests/
│   └── frontend/                ← interface web (Vue, construite en fichiers statiques)
├── custom_components/homestead/ ← intégration compagnon (HACS)
├── hacs.json
└── docs/
```

Le serveur et l'interface sont dans le dossier de l'application parce que le Supervisor construit une application locale avec ce seul dossier comme contexte Docker. L'application et l'intégration partagent un numéro de version, publié en même temps. On séparera les dépôts plus tard si la communauté le demande.

### Choix techniques

| Sujet | Choix | Pourquoi |
|---|---|---|
| Serveur | Python 3.13+, FastAPI, SQLAlchemy, Alembic | Même langage que HA et que le code déjà écrit ; migrations de base fiables d'une version à l'autre |
| Base | SQLite dans le dossier de l'application | Aucun service à part, incluse dans les sauvegardes |
| Interface | Vue 3 + Vite, construite en fichiers statiques servis par le serveur | Écosystème riche (plan interactif, graphiques), fonctionne derrière l'ingress de HA |
| Image | Pillow, OpenCV, ONNX Runtime (processeur, sans carte graphique) | Tourne sur un PC ou un Raspberry Pi 4/5 |
| Construction | GitHub Actions : images Docker amd64 et aarch64, tests, validation HACS et hassfest | Rien à installer chez soi |

---

## 5. Modèle de données

```
Jardin : dates de gel, position, sources météo
├── Espaces : type (pleine terre, carré, serre, pots, verger, poulailler), forme et position
│   sur le plan, surface, abri (semaines gagnées sur le gel), sondes, vanne, caméra
├── Saisons (une par année)
│   └── Cultures : espèce, variété, espace (et zone sur le plan), mode de démarrage,
│       quantité, lot de graines, stade et dates, succession (semis échelonnés)
│       ├── Journal : arrosage, apport, traitement, observation, intervention
│       ├── Récoltes : date, poids ou nombre
│       └── Photos : date, culture ou espace, analyses (surface verte, identification, diagnostic)
├── Grainothèque : lots (espèce, variété, fournisseur, quantité, date de péremption)
├── Vivaces et arbres : espèce, variété, porte-greffe, plantation, position ;
│   tailles, traitements, floraisons, greffes, récoltes (d'année en année)
├── Troupeau : poules (nom, race, naissance, arrivée, départ), pontes quotidiennes, soins
└── Catalogue personnel : variétés et espèces ajoutées par l'utilisateur
```

### Catalogue

- Le format de la phase 1 est conservé (voir [catalog.md](catalog.md)).
- Champs à ajouter :
  - **associations :** compagnons et plantes à éviter ;
  - **rotation :** groupe et nombre d'années avant le retour au même endroit ;
  - **eau :** coefficients culturaux Kc par stade (FAO-56) et profondeur des racines ;
  - **degrés-jours :** température de base et somme nécessaire ;
  - **conseils :** courts textes traduits ;
  - **succession :** intervalle conseillé entre deux semis ;
  - **permaculture :** fonctions, ensoleillement, strate, durée de vie, engrais vert, isolement des porte-graines (voir §7).
- Nouvelles familles de fichiers : arbres fruitiers, petits fruits, aromatiques vivaces (taille, traitements, floraison, groupes de pollinisation).
- Les valeurs sont rédigées à partir de connaissances agronomiques générales ou de sources dont la licence permet la réutilisation (calendrier légumier de l'INRAE sous Etalab 2.0, FAO-56). Aucune base propriétaire n'est recopiée.

---

## 6. Calculs

### Bilan hydrique (par espace, chaque jour)

```
réserve du sol (mm) = réserve d'hier + pluie efficace + arrosages − ET0 × Kc(cultures, stades)
```

- **ET0** : méthode de Hargreaves à partir de la météo de HA, ou valeur lue dans Smart Irrigation s'il est installé.
- **Kc** : moyenne des cultures de l'espace selon leur stade.
- **Serre :** pas de pluie ; température intérieure si une sonde existe.
- **Sonde d'humidité du sol :** elle prime, et le calcul est recalé sur sa mesure. Le calcul reste un garde-fou si la sonde se décharge ou tombe en panne.
- **Résultat :** des mm, convertis en litres (surface) puis en minutes (débit de la vanne).
- **Cuve :** litres disponibles, et alerte si elle ne suffit pas pour l'arrosage prévu.

### Degrés-jours

Somme quotidienne de (température moyenne − température de base de l'espèce), depuis le semis ou la plantation. Elle affine la date de récolte prévue d'une année à l'autre.

### Rotation et associations

Au moment de placer une culture, l'interface signale :
- une culture de la même famille ou du même groupe à cet endroit dans les N dernières années ;
- un mauvais voisin sur le plan.

### Traitement d'image

| Fonction | Méthode | Où |
|---|---|---|
| Album, comparaison d'une saison à l'autre | Classement par culture, espace et date ; vignettes | Local |
| Timelapse | Image de la caméra HA à heure fixe, montage vidéo | Local |
| Surface verte | Indice de vert (ExG) et segmentation OpenCV, sur des photos cadrées pareil | Local |
| Identification | API Pl@ntNet (clé gratuite, quota journalier) | En ligne, option |
| Maladies et ravageurs | IA de vision (fiable) ; petit modèle local en complément (fiabilité limitée sur des photos prises au jardin) | En ligne en option, ou local |
| Maturité et comptage | Détection d'objets (modèle type YOLO) | Local, expérimental, en dernier |

---

## 7. Permaculture

*Proposée le 29/10/2026, à valider : rien n'est encore codé.*

Homestead applique déjà plusieurs principes de la permaculture : tout reste chez soi, on observe avant d'agir (journal, photos), les associations sont gérées, on prévoit la cuve et le bilan hydrique, et le poulailler fait partie du même système que le jardin. Il manque ce qui fait voir le jardin comme **un ensemble de relations** (sol, eau, plantes, animaux, déchets), et non comme une simple liste de cultures.

**Règles :**
- **Tout est optionnel.** Dans le même esprit que « fonctionne sans capteur », Homestead reste utile à qui ne pratique pas la permaculture. Il n'y a pas de « mode permaculture » à part : seulement des champs à remplir si on le souhaite et des suggestions.
- **Des rappels, jamais des interdictions**, comme pour la rotation et les voisins.
- **Des valeurs sourcées**, comme pour le reste du catalogue. Les associations et les « fonctions » des plantes sont inégalement étayées : on n'en retient que celles qu'une source reconnue appuie. La notion d'« accumulateur dynamique » est écartée, car elle repose sur trop peu de preuves.

### Sol vivant (en premier)

- **Journal :** trois nouveaux types d'entrée, `mulching`, `compost` et `green_manure`.
  - Paillage : matière, épaisseur en cm, part couverte (%).
  - Compost ou amendement : quantité (kg ou seaux) et origine.
  - Engrais vert : couché, fauché ou enfoui.
- **Travail du sol par espace :** champ `tillage`, à choisir parmi `none` (pas de travail), `light` (grelinette) ou `dug` (bêché). Ce champ informe : il ne change aucun calcul.
- **Paillis :** chaque matière a une durée de vie, réglable. Quand la couverture estimée passe sous un seuil, la tâche « Renouveler le paillis » apparaît, et elle est avancée avant une période chaude prévue.
- **Engrais verts au catalogue :** phacélie, moutarde blanche, trèfle incarnat, seigle-vesce, sarrasin.
  - Champs : `green_manure: true`, fenêtres de semis en place, et `terminate` (combien de semaines après le semis il faut le coucher, avant la montée en graines).
  - Ce sont des cultures comme les autres : elles comptent dans la rotation. Par exemple, la moutarde est une crucifère et reviendrait trop tôt derrière des choux.
- **Proposition automatique :** quand un espace (ou une zone) reste libre plus de 6 semaines (seuil réglable) avant la prochaine culture prévue, l'application propose un engrais vert qui convient à la date, au gel et à la rotation.
- **Jours de sol nu :** pour chaque espace, nombre de jours de l'année sans culture, sans engrais vert et sans paillis. Les périodes de culture et le journal suffisent pour le calculer.

### Fonctions des plantes

- **Nouveau champ `functions` au catalogue :** `nitrogen_fixer` (fixe l'azote), `pollinators` (nourrit les pollinisateurs), `beneficials` (attire les auxiliaires), `trap_crop` (plante piège), `mulch` (feuillage coupé et laissé sur place comme paillis), `ground_cover` (couvre-sol), `windbreak` (brise-vent).
- **Espèces à ajouter :** capucine, souci, bourrache, phacélie, trèfle, consoude (vivace, avec la phase E).
- **Fiche d'un espace :** fonctions présentes et fonctions absentes, par exemple « aucune fleur pour les pollinisateurs en juillet ». Une suggestion propose alors une espèce qui comble ce manque et qui est compatible avec les voisins.
- **Nouveau champ `sun` :** `full` (plein soleil), `partial` (mi-ombre) ou `shade` (ombre). Il sert aussi aux zones et à l'ensoleillement.

### Polyculture et vivaces

- **Planche mixte :** espace marqué `mixed: true`. La rotation ne se juge plus famille par famille, mais sur l'ensemble de la planche. Il n'y a de rappel que si une même famille occupe plus de la moitié de la surface deux saisons de suite (seuil à valider).
- **Cultures pluriannuelles** (rhubarbe, artichaut, oseille, fraisier, chou perpétuel) : champ `lifespan_years`. Elles restent en place plusieurs saisons sans être reprogrammées et ne comptent pas dans la rotation.
- **Autosemis :** nouveau mode de démarrage `self_sown` pour les plantes qui se ressèment seules (bourrache, mâche, roquette, souci). On les enregistre sans étape de semis, au stade où on les trouve.

### Zones et secteurs (sur le plan)

- **Zones 0 à 5 :** un champ par espace et par objet. Par défaut, la zone est calculée à partir de la distance à la maison, qui devient un objet de décor (seuils réglables). Usages :
  - dans « Aujourd'hui », les tâches de la zone 1 passent en premier ;
  - un rappel suggère de placer près de la maison ce qui se cueille souvent (aromatiques, salades).
- **Ensoleillement :**
  - Les objets de décor (maison, abri, arbre, haie, serre) reçoivent une hauteur. Un arbre caduc laisse passer le soleil en hiver.
  - Avec la position du soleil, calculée depuis les coordonnées de HA, l'application calcule les heures de soleil direct en chaque point du plan, pour une date donnée (solstices, équinoxes, aujourd'hui).
  - Le résultat est une carte de chaleur, et les heures de soleil de chaque espace sont comparées au champ `sun` de ses cultures.
- **Vent dominant :** rose des vents calculée avec l'archive Open-Meteo, déjà utilisée pour les gelées, et affichée sur le plan pour placer les haies brise-vent.

### Eau captée

- **Nouveaux objets de décor :** mare et baissière. On les dessine sans faire de calcul.
- **Toiture reliée à la cuve :** litres captés = pluie (mm) × surface du toit (m²) × coefficient de ruissellement (0,8 par défaut).
- **Bilan de la saison :** litres captés, arrosés depuis la cuve et perdus par débordement de la cuve pleine.
- **Paillis dans le bilan hydrique :** un paillis organique réduit l'évaporation du sol d'environ 5 % pour chaque tranche de 10 % de surface couverte (FAO-56, chapitre 7). Les entrées `mulching` du journal suffisent pour en tenir compte.

### Strates et guildes (avec la phase E)

- **Nouveau champ `layer` :** `canopy` (canopée), `small_tree` (petit arbre), `shrub` (arbuste), `herbaceous` (herbacée), `ground_cover` (couvre-sol), `climber` (grimpante), `root` (racine).
- **Guilde :** groupe nommé autour d'un arbre du plan. L'application propose des compagnons :
  - pour couvrir les fonctions qui manquent (azote, pollinisateurs, paillis, couvre-sol) ;
  - sur des strates différentes ;
  - en tenant compte de l'ombre de l'arbre et des mauvais voisins.

### Biodiversité

- **Observations de faune :** nouvelle entrée de journal `wildlife`.
  - On choisit dans une courte liste : abeilles, bourdons, syrphes, coccinelles, carabes, hérissons, oiseaux, limaces, pucerons, doryphores…
  - Chaque observation porte une abondance (une, quelques-unes, beaucoup). La liste distingue auxiliaires et ravageurs.
  - D'une année à l'autre, on voit si les auxiliaires arrivent avant les ravageurs.
- **Floraison continue :** à partir des périodes de floraison du catalogue (cultures, vivaces, engrais verts), l'application signale les mois sans fleurs dans le jardin.

### Boucles fermées (surtout avec la phase F)

- **Compost :**
  - Espace de type `compost`, qui reçoit des entrées : déchets verts, épluchures, litière du poulailler.
  - Il est mûr à une date estimée, avec une durée réglable.
  - Une sortie vers un espace crée l'entrée `compost` dans le journal de cet espace.
- **Poulailler :**
  - La litière changée part au compost et les épluchures vont aux poules.
  - **Parcours tournant :** en fin de saison, on peut mettre les poules sur une planche pour qu'elles désherbent et fertilisent. La planche est alors marquée « poules », avec des dates. Avant de récolter des légumes mangés crus, un délai réglable s'applique après le fumier frais (règle d'hygiène).
- **Graines produites sur place :**
  - Nouveau stade « porte-graines » après la récolte.
  - Une récolte de graines crée un lot dans la grainothèque, qui garde son origine (culture et saison).
  - Rappels : une variété hybride F1 (champ `f1` de la variété) ne redonne pas la même plante, et les espèces qui se croisent entre elles ont besoin d'une distance d'isolement (champ `seed_isolation_m`, par exemple pour les courges).

### Bilan d'autonomie (avec la phase G)

Ce bilan est calculé par saison et comparé d'une année à l'autre :
- kg récoltés (au total et par m²) et œufs ;
- litres de pluie captés et eau de réseau utilisée ;
- compost produit et lots de graines produits sur place ;
- jours de sol nu et part de la surface couverte.

### Ce qu'on ne fait pas

- **Calendrier lunaire et biodynamie :** ils restent écartés (voir §2).
- **Associations et fonctions sans source :** on ne les retient pas.
- **Ajouts de l'utilisateur :** une association ou une fonction ajoutée à son catalogue personnel reste chez lui.

### Ordre proposé

1. **Phase B, avant les semis de février :**
   - entrées de journal `mulching`, `compost` et `green_manure`, et champ `tillage` ;
   - champs `functions` et `sun`, et espèces de la section « Fonctions des plantes » ;
   - engrais verts et proposition quand un espace se libère ;
   - planches mixtes, cultures pluriannuelles et `self_sown` ;
   - stade « porte-graines », avec la grainothèque.
2. **Plan, après la phase B :** zones, hauteurs des objets, ensoleillement, vent dominant.
3. **Phase C :** paillis dans le bilan hydrique, eau captée, jours de sol nu.
4. **Phase D :** observations de faune, à mettre en lien avec les photos.
5. **Phase E :** strates, guildes, floraison continue.
6. **Phase F :** compost et boucles avec le poulailler.
7. **Phase G :** bilan d'autonomie.

---

## 8. Ce que voit l'utilisateur dans HA

| Entité | Rôle |
|---|---|
| `todo` | Tâches des 14 prochains jours. Cocher une tâche fait avancer la culture |
| `calendar` | Périodes de semis, de mise en place, de récolte, de taille et de traitement |
| `select` par culture | Stade |
| `sensor` par culture | Prochaine tâche, échéance, récolte prévue, kg récoltés, degrés-jours |
| `sensor` / `binary_sensor` par espace | Besoin en eau, réserve du sol, à arroser, risque de gel, surchauffe, « à semer maintenant » |
| `sensor` jardin | Niveau de la cuve, récoltes de la saison |
| `sensor` poulailler | Œufs du jour et des 7 derniers jours, niveaux d'eau et de grain, prochain soin |
| Actions | `homestead.log_harvest`, `homestead.log_eggs`, `homestead.log_watering`, `homestead.set_stage`… |

**Blueprints :**
- alerte de gel ;
- serre trop chaude (ventilation, ouvrants) ;
- arrosage par vanne : durée maximale, pas d'arrosage s'il a plu ou s'il va pleuvoir ;
- porte du poulailler au lever et au coucher du soleil, avec vérification de la fermeture.

---

## 9. Phases

| Phase | Contenu | Visé pour |
|---|---|---|
| ~~0–1~~ | ~~Intégration seule : dates de gel, espaces, cultures, tâches, calendrier (v0.2)~~ | Faites le 27/10/2026 ; le moteur est repris dans l'application |
| **A. Socle** | Application (serveur, base, interface derrière l'ingress) ; espaces, saisons, cultures, stades, journal, récoltes ; saisie rapide sur smartphone ; intégration compagnon (découverte, tâches, calendrier, stades, capteurs) ; images Docker et dépôt d'applications | Code écrit et testé le 27/10/2026 (v0.3.0) ; installé dans HA OS le 28/10/2026 |
| **B. Planification** | Plan dessiné, rotation, associations, semis échelonnés, grainothèque, conseils par culture ; sol vivant, fonctions des plantes, engrais verts, planches mixtes, porte-graines ; puis zones et ensoleillement sur le plan (§7) | Plan dessiné fait le 28/10/2026 (v0.4.0) ; rotation, associations et conseils le 29/10/2026 (v0.7.0) ; semis échelonnés et grainothèque avant les semis de février |
| **C. Eau et climat** | Bilan hydrique (avec le paillis), degrés-jours, sondes, gel, serre, cuve et eau captée, vannes et blueprints ; jours de sol nu | Mars–avril 2027 |
| **D. Photos** | Album, timelapse, surface verte, identification, diagnostic par IA, maladies ; observations de faune ; maturité en dernier | Printemps 2027 |
| **E. Verger et vivaces** | Arbres, petits fruits, aromatiques, taille, traitements, floraison et pollinisation, greffes ; strates, guildes, floraison continue | Été 2027 |
| **F. Poulailler** | Registre, ponte, porte, niveaux, soins, température et éclairage, caméra ; compost, parcours tournant et boucles avec le jardin | À l'arrivée des poules |
| **G. Finitions** | Statistiques de rendement, bilan d'autonomie, cartes de tableau de bord, documentation, publication | En continu |

Avant chaque publication : tests automatisés, puis essai sur une installation HA vierge, pas seulement chez nous.

---

## 10. Questions ouvertes

1. **Capteurs et matériel** (phase C) : sondes d'humidité du sol, station météo ou pluviomètre, vannes, capteur de niveau de la cuve, ouvrants de serre. Quels modèles (Zigbee, ESPHome, Gardena…) ?
2. **Caméras** (phase D) : une caméra est-elle prévue pour la serre ou le potager ?
3. **IA de vision** (phase D) : quel service, avec quelle clé ? Ce sera une option, désactivée par défaut.
4. **Dépôt public** : HACS et le magasin d'applications de HA exigent un dépôt public. À rendre public au plus tard pour le premier essai chez nous.

### Phase A, état au 27/10/2026

- **Serveur** : FastAPI + SQLite (migrations Alembic), API REST sous `/api`, avis de changement par WebSocket `/api/ws` (et un avis à minuit, car les tâches dépendent de la date). 56 tests.
- **Accès** : derrière l'ingress, le Supervisor authentifie l'utilisateur ; tout autre appel (l'intégration) doit porter le jeton d'API, créé au premier démarrage dans `/data/api_token`. Un serveur autonome est ouvert sur le réseau local sauf `HOMESTEAD_REQUIRE_TOKEN=1`, mais un jeton fourni doit toujours être le bon.
- **Découverte** : au démarrage, l'application s'annonce au Supervisor (`/discovery`, service `homestead`) avec son nom d'hôte, son port et le jeton ; HA propose alors d'ajouter l'intégration sans rien saisir.
- **Interface** : Aujourd'hui (tâches, à lancer maintenant), Cultures par saison et par espace, fiche culture (stades, prévu, tâches, récoltes, journal, saisons précédentes), Saisie rapide, Espaces, Réglages. Français et anglais, thème repris de HA dans l'ingress.
- **Intégration 0.3.0** : configuration par découverte ou par adresse + jeton, réauthentification ; appareils jardin → espaces → cultures en cours (une culture terminée disparaît) ; liste de tâches, calendrier, stade, capteurs (prochaine tâche, échéance, récolte prévue, récolté en kg, cultures et « à lancer » par espace) ; actions `homestead.log_harvest` et `homestead.log_journal`. 18 tests, hassfest valide.
- **Essai** : image construite et lancée sur le serveur Debian (port 8099 lié à 127.0.0.1), interface vérifiée sur mobile, client de l'intégration vérifié contre le vrai serveur.

### Phase B, le plan (v0.4.0, 28/10/2026)

- **Plan** : en mètres, sur un fond optionnel (vue aérienne ou photo de drone, réduite à 3000 px dans le navigateur) étalonné en touchant deux points d'une longueur connue. Espaces et objets de décor (pelouse, allée, terrasse, mare, arbre, arbuste, haie, compost, cuve, abri, serre…) déplacés, redimensionnés et tournés au doigt.
- **Disposition des cultures** : chaque culture reçoit une zone de son espace (sinon les cultures se partagent l'espace en bandes) et une disposition : grille, lignes, quinconce ou libre ; l'espacement vient du catalogue. Au-delà de 1500 plants, la zone est remplie au lieu de dessiner chaque plant.
- **Aujourd'hui** s'ouvre sur le plan ; toucher un espace montre ses cultures et ses tâches.
- **Carte de tableau de bord** fournie par l'intégration (`custom:homestead-plan-card`), visible par tous les utilisateurs : saison (selon l'hémisphère), météo réelle (soleil, nuages, pluie, neige, brouillard, orage, vent), nuit ; plantes dessinées par famille, qui grandissent avec le stade et portent leurs fruits à la récolte ; arbres en fleurs, en feuilles, en couleurs ou nus selon la saison. Toucher un espace zoome dessus et liste ses cultures (stade, plants, disposition, prochaine tâche) ; toucher une culture de la liste ouvre son entité (v0.4.2). Le plan arrive par la commande WebSocket `homestead/plan/subscribe`.
- **Plus tard** : récupérer la vue aérienne automatiquement ; sondes du sol sur la carte (phase C).

### Phase B, les étapes de chaque culture (v0.5.0, 28/10/2026)

- **Programmer une culture** : en choisissant la culture, l'espace et la façon de la lancer, l'application montre les étapes prévues avant de confirmer.
- **Étapes** : semis (sous abri ou en place) ou plantation, repiquage en godets (catalogue, seulement pour les semis sous abri), endurcissement une semaine avant la mise en place (sauf en serre), mise en place, travaux du catalogue (tuteurer, gourmands, éclaircir, butter, pincer…), récolte, fin de récolte. Dates estimées depuis les gelées, puis recalculées dès qu'une date réelle est saisie. Statuts : fait, à faire, prévu, passé (non coché), ignoré.
- **Calendrier** : page de l'application (12 mois, par mois) ; dans HA, les travaux s'ajoutent aux périodes, un jour chacun, avec description ; ceux qui sont faits sont marqués ✓.
- Les travaux de pépinière (repiquage) disparaissent de la liste de tâches une fois la culture mise en place.

### Phase B, les gelées (v0.6.0, 28/10/2026)

- **Dates de gelée calculées** : Réglages → « Calculer d'après la météo passée ». Archive Open-Meteo (minimales journalières à 2 m, 30 ans), position de HA arrondie à 0,1° (≈ 10 km), altitude de HA si elle est renseignée. Gel = minimale ≤ 0 °C. Dates retenues : celles qui ne sont dépassées qu'une année sur dix (dernière gelée au printemps, première en automne) ; la médiane est affichée pour comparaison. Proposées, jamais enregistrées sans action. Pour le jardin (28/10/2026) : 30 avril et 21 octobre (médianes 15 avril et 12 novembre).
- **Prévisions** : l'app lit toutes les heures `weather.get_forecasts` (quotidien, `templow`) de l'entité météo choisie (par défaut la première ; ici `weather.maison`, IRM). Nuit gélive sur 7 jours : tâche « Protéger du gel » pour les cultures en place (sensibles ≤ 1 °C, semi-rustiques ≤ −2 °C, serre +3 °C), due la veille ; plantation, mise en place et semis en place des cultures sensibles reportés au lendemain de la dernière nuit gélive (❄ dans les étapes et les tâches). Bandeau sur Aujourd'hui ; capteur HA « Prochaine gelée » (date + température).
- **Pas encore** : décaler tout le calendrier selon la chaleur réellement observée (degrés-jours), alertes de canicule et d'arrosage (phase C).

### Phase B, rotation, voisins et conseils (v0.7.0, 29/10/2026)

- **Catalogue** : champs `rotation_years` (années avant le retour de la famille au même endroit : 4 pour solanacées, choux, navet et pois, 2 pour radis, salades, radis, épinard, basilic, maïs, mâche, 3 pour les autres), `companions`, `avoid` et `tips` (deux conseils fr/en par espèce, pour les 30 espèces). Un seul côté suffit pour un voisin ; les deux côtés doivent être d'accord, et chaque id doit exister (vérifié au chargement).
- **Calcul** (`rotation.py`, `Garden.placement`) : pour une culture, on regarde les autres cultures de son espace.
  - Rotation : même famille, saison antérieure de moins de `rotation_years` ans.
  - Voisins : bon ou mauvais voisin présent en même temps (période en place : semis en place ou mise en place, jusqu'à la fin de récolte, réelles ou prévues).
  - Si les deux cultures ont une zone dessinée : rotation seulement si les zones se chevauchent, voisins seulement à moins d'un mètre. Une culture prévue pour une saison passée mais jamais lancée ne compte pas.
- **Interface** : « Dans cet espace » avant de confirmer une culture (pour chaque façon de la lancer) et sur la fiche culture ; section « Conseils » de la fiche (conseils, bons voisins, à éloigner, règle de rotation). Ce sont des rappels, jamais des interdictions.
- **Pas encore** : voisins entre espaces proches sur le plan, alertes sur le plan lui-même.

*Décisions déjà prises : nom Homestead (27/10) ; Plant-it supprimé (27/10) ; jardin = un carré surélevé, une serre avec 2 bacs, un potager d'environ 8 × 4 m (27/10) ; périmètre, architecture et ordre des phases (27/10).*
