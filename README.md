# EDF Tempo pour Home Assistant

[![HACS Custom](https://img.shields.io/badge/HACS-Custom-41BDF5?logo=homeassistantcommunitystore&logoColor=white)](https://github.com/hacs/integration)
[![Hassfest](https://img.shields.io/badge/Hassfest-valid%C3%A9-41BDF5?logo=homeassistant&logoColor=white)](https://github.com/andry-paris/edf-tempo-HA/actions/workflows/validate.yml)
[![Validation](https://github.com/andry-paris/edf-tempo-HA/actions/workflows/validate.yml/badge.svg?branch=main)](https://github.com/andry-paris/edf-tempo-HA/actions/workflows/validate.yml)
[![Home Assistant 2025.1+](https://img.shields.io/badge/Home%20Assistant-2025.1%2B-18BCF2?logo=homeassistant&logoColor=white)](https://www.home-assistant.io/)
[![GitHub release](https://img.shields.io/github/v/release/andry-paris/edf-tempo-HA?logo=github)](https://github.com/andry-paris/edf-tempo-HA/releases/latest)
[![Licence Apache 2.0](https://img.shields.io/github/license/andry-paris/edf-tempo-HA)](LICENSE)

Suivez facilement les couleurs **EDF Tempo** dans Home Assistant et anticipez les jours où votre consommation d’électricité mérite une attention particulière.

L’intégration affiche la couleur du jour, celle du lendemain dès sa publication par RTE, ainsi que l’avancement complet de la saison Tempo. Elle propose également plusieurs cartes visuelles pour retrouver toutes ces informations directement dans votre tableau de bord.

> Ce projet communautaire est indépendant d’EDF, de RTE et du projet Home Assistant.

## Ce que vous pouvez faire

### Connaître la couleur du jour et du lendemain

Retrouvez immédiatement la couleur Tempo en cours :

- **bleu** : tarif généralement le plus avantageux ;
- **blanc** : tarif intermédiaire ;
- **rouge** : journée pendant laquelle il est particulièrement utile de limiter sa consommation aux heures pleines.

La couleur du lendemain apparaît automatiquement dès qu’elle est publiée par RTE. Vous pouvez ainsi adapter à l’avance le chauffage, la recharge d’un véhicule ou le fonctionnement des appareils les plus énergivores.

### Suivre les jours restants

Trois capteurs indiquent séparément le nombre de jours bleus, blancs et rouges encore disponibles pendant la saison en cours.

Vous pouvez rapidement savoir combien de jours rouges restent à venir et mieux anticiper la fin de la saison Tempo.

### Consulter la saison en un coup d’œil

Le calendrier saisonnier présente les couleurs déjà placées depuis septembre et permet de parcourir les saisons précédentes à partir de 2015–2016.

Une vue mensuelle est également disponible pour examiner plus facilement une période précise.

### Créer des automatisations

Les informations Tempo deviennent des entités Home Assistant classiques. Elles peuvent donc être utilisées pour :

- envoyer une notification lorsqu’un jour rouge est annoncé ;
- réduire automatiquement une consigne de chauffage ;
- reporter la recharge d’un véhicule ;
- différer le chauffe-eau ou certains appareils ;
- changer la couleur d’un éclairage ou d’un indicateur visuel.

## Aperçu

### Aujourd’hui et demain

| Thème Home Assistant | Thème Frosted |
|---|---|
| ![Carte EDF Tempo pour aujourd’hui et demain avec le thème Home Assistant](docs/screenshots/Carte-EDF%20Tempo-26-27-Juillet-2026-HA-Theme.png) | ![Carte EDF Tempo pour aujourd’hui et demain avec le thème Frosted](docs/screenshots/Carte-EDF%20Tempo-26-27-Juillet-2026-Frosted-Theme.png) |

### Calendrier mensuel

| Juillet — thème Home Assistant | Juillet — thème Frosted |
|---|---|
| ![Calendrier mensuel EDF Tempo de juillet avec le thème Home Assistant](docs/screenshots/Carte-EDF%20Tempo%20Mensuel-Juillet-2026-HA-Theme.png) | ![Calendrier mensuel EDF Tempo de juillet avec le thème Frosted](docs/screenshots/Carte-EDF%20Tempo%20Mensuel-Juillet-2026-Frosted-Theme.png) |

| Mars — thème Home Assistant | Mars — thème Frosted |
|---|---|
| ![Calendrier mensuel EDF Tempo de mars avec le thème Home Assistant](docs/screenshots/Carte-EDF%20Tempo%20Mensuel-Mars-2026-HA-Theme.png) | ![Calendrier mensuel EDF Tempo de mars avec le thème Frosted](docs/screenshots/Carte-EDF%20Tempo%20Mensuel-Mars-2026-Frosted-Theme.png) |

### Calendrier de la saison

| Thème Home Assistant | Thème Frosted |
|---|---|
| ![Calendrier de la saison EDF Tempo avec le thème Home Assistant](docs/screenshots/Carte-Calendrier%20EDF%20Tempo-2026-HA-Theme.png) | ![Calendrier de la saison EDF Tempo avec le thème Frosted](docs/screenshots/Carte-Calendrier%20EDF%20Tempo-2026-Frosted-Theme.png) |

D’autres exemples visuels sont disponibles dans le dossier [`docs/screenshots`](docs/screenshots/).

## Informations disponibles dans Home Assistant

Après son installation, l’intégration ajoute :

- la couleur Tempo d’aujourd’hui ;
- la couleur Tempo de demain ;
- une synthèse de la saison en cours ;
- le nombre de jours bleus restants ;
- le nombre de jours blancs restants ;
- le nombre de jours rouges restants.

La couleur de demain est affichée comme inconnue tant que RTE ne l’a pas encore publiée. L’intégration se met ensuite à jour automatiquement.

## Cartes pour le tableau de bord

Quatre cartes facultatives permettent de personnaliser l’affichage :

- une carte compacte pour aujourd’hui et demain ;
- une synthèse de la saison ;
- un calendrier couvrant toute la saison ;
- un calendrier mensuel.

Les cartes s’adaptent au thème clair ou sombre de Home Assistant et disposent d’un éditeur visuel.

## Avant l’installation

Vous avez besoin :

- de Home Assistant 2025.1.0 ou d’une version plus récente ;
- d’un accès Internet depuis Home Assistant ;
- d’identifiants gratuits pour l’API Tempo de RTE.

Pour obtenir ces identifiants, créez une application sur [data.rte-france.org](https://data.rte-france.org/) et souscrivez-la à l’API Tempo.

L'inscription à l'API Tempo RTE se fait sur ce site : https://data.rte-france.com/catalog/-/api/consumption/Tempo-Like-Supply-Contract/v1.1

## Installation avec HACS

Tant que l’intégration n’est pas présente dans le catalogue HACS par défaut :

1. Ouvrez **HACS** dans Home Assistant.
2. Sélectionnez **Dépôts personnalisés** dans le menu.
3. Ajoutez `https://github.com/andry-paris/edf-tempo-HA` dans la catégorie **Intégration**.
4. Recherchez puis installez **EDF Tempo**.
5. Redémarrez Home Assistant.


## Première configuration

Après le redémarrage :

1. Ouvrez **Paramètres > Appareils et services**.
2. Sélectionnez **Ajouter une intégration**.
3. Recherchez **EDF Tempo**.
4. Saisissez les deux identifiants fournis par RTE.

L’intégration vérifie les identifiants et commence ensuite à récupérer les informations Tempo. Une seule configuration EDF Tempo est nécessaire par installation Home Assistant.

La configuration s’effectue exclusivement depuis l’interface de Home Assistant : aucune configuration YAML n’est nécessaire. Les identifiants proposés aux nouvelles entités restent entièrement gérés par Home Assistant, qui conserve les renommages et personnalisations effectués par l’utilisateur.

## Ajouter les cartes visuelles

Les cartes sont installées et enregistrées automatiquement avec l’intégration. Après le redémarrage de Home Assistant, actualisez votre navigateur puis ajoutez la carte EDF Tempo souhaitée depuis l’éditeur du tableau de bord. La ressource Lovelace créée automatiquement est supprimée lors de la désinstallation définitive de l’intégration.

Si vos ressources Lovelace sont gérées manuellement en mode YAML, ajoutez `/edf_tempo/card.js?v=1.2.5` comme module JavaScript dans votre configuration.

## Données et confidentialité

Les couleurs Tempo proviennent de l’API officielle de RTE. Dans Home Assistant, l’appareil est donc présenté comme une intégration communautaire et son modèle indique explicitement RTE comme source des données. Les données des saisons consultées sont conservées localement par Home Assistant afin de réduire les demandes inutiles. Si ce cache devient incomplet ou illisible, l’intégration l’ignore et le reconstruit automatiquement depuis RTE.

Les diagnostics masquent les identifiants et les jetons de connexion. Le client secret est également affiché comme un mot de passe dans les formulaires et n’est jamais prérempli lors d’une reconfiguration : laissez ce champ vide pour conserver le secret actuel. Ne partagez néanmoins jamais vos identifiants RTE dans une capture d’écran, un journal ou un signalement de problème.

## Limites connues

- La disponibilité de la couleur du lendemain dépend de sa publication par RTE.
- L’intégration présente les couleurs Tempo, mais pas les tarifs particuliers de votre contrat.
- L’enregistrement automatique des cartes nécessite le mode de gestion standard des ressources Lovelace. Le mode YAML demande une déclaration manuelle.
- L’historique disponible commence avec la saison 2015–2016.

## Signaler un problème

Vous pouvez utiliser les [issues GitHub](https://github.com/andry-paris/edf-tempo-HA/issues) pour signaler un problème reproductible. Indiquez les versions de Home Assistant et de l’intégration, sans inclure de donnée confidentielle.

Ce logiciel est fourni gratuitement, sans garantie et sans engagement d’assistance individuelle. Son utilisation reste sous votre responsabilité.

## Qualité et validation

Chaque modification est contrôlée automatiquement avec HACS, Hassfest et les tests Python et JavaScript. Les tests des cartes simulent notamment une navigation rapide entre plusieurs saisons pour vérifier que chaque calendrier demandé est chargé sans doublon. Une matrice exécute les tests d’intégration avec la version minimale prise en charge, Home Assistant 2025.1.0, et avec la version actuelle utilisée par le projet. Ces tests utilisent les fixtures officielles de Home Assistant pour vérifier le cycle complet d’installation, de rechargement, de réauthentification et de désinstallation, ainsi que l’enregistrement des cartes dans Lovelace. Ils répètent également les installations et désinstallations après renommage des entités afin de détecter les doublons et les entrées orphelines.

Les outils utilisés par ces contrôles sont figés sur des versions précises afin de garantir des validations reproductibles. Dependabot surveille leurs mises à jour et propose automatiquement les évolutions disponibles.

## Licence

Copyright 2026 **andry-paris**.

Ce projet est distribué sous licence [Apache License 2.0](LICENSE). Consultez également le fichier [NOTICE](NOTICE).
