# EDF Tempo pour Home Assistant

[![HACS Custom](https://img.shields.io/badge/HACS-Custom-41BDF5?logo=homeassistantcommunitystore&logoColor=white)](https://github.com/hacs/integration)
[![Home Assistant 2025.1+](https://img.shields.io/badge/Home%20Assistant-2025.1%2B-18BCF2?logo=homeassistant&logoColor=white)](https://www.home-assistant.io/)
[![GitHub release](https://img.shields.io/github/v/release/andry-paris/edf-tempo-HA?logo=github)](https://github.com/andry-paris/edf-tempo-HA/releases/latest)
[![Licence Apache 2.0](https://img.shields.io/github/license/andry-paris/edf-tempo-HA?logo=apache&logoColor=white)](LICENSE)

Suivez facilement les couleurs **EDF Tempo** dans Home Assistant et anticipez les jours où votre consommation d’électricité mérite une attention particulière.

L’intégration affiche la couleur du jour, celle du lendemain dès sa publication par RTE, ainsi que l’avancement complet de la saison Tempo. Elle propose également plusieurs cartes visuelles pour retrouver toutes ces informations directement dans votre tableau de bord.

> Ce projet communautaire est indépendant d’EDF, de RTE et du projet Home Assistant.

## Installation en 3 minutes

1. Installez **EDF Tempo** depuis HACS.
2. Renseignez votre **ID Client** et votre **ID Secret** RTE.
3. Ajoutez l’une des cartes EDF Tempo à votre tableau de bord.

L’intégration s’occupe ensuite de récupérer et d’actualiser automatiquement les couleurs Tempo.

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

> Anticipez les jours rouges, adaptez vos équipements et visualisez toute votre saison Tempo depuis Home Assistant.

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

- **EDF Tempo Quotidien** : la couleur d’aujourd’hui et celle de demain ;
- **EDF Tempo Synthèse Saison** : les jours utilisés et restants pour chaque couleur ;
- **Calendrier EDF Tempo** : toute la saison, avec navigation entre les années ;
- **EDF Tempo Mensuel** : un mois à la fois, avec navigation entre les mois.

Les cartes s’adaptent au thème clair ou sombre de Home Assistant et disposent d’un éditeur visuel.

## Avant l’installation

Vous avez besoin :

- de Home Assistant 2025.1.0 ou d’une version plus récente ;
- d’un accès Internet depuis Home Assistant ;
- d’identifiants gratuits pour l’API Tempo de RTE.

Pour obtenir gratuitement ces identifiants :

1. [Créez votre compte sur le portail RTE](https://data.rte-france.org/).
2. Ouvrez la page [API Tempo — Contrat de fourniture](https://data.rte-france.com/catalog/-/api/consumption/Tempo-Like-Supply-Contract/v1.1).
3. Souscrivez à l’API Tempo et récupérez votre **ID Client** et votre **ID Secret**.

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
4. Saisissez votre "ID Client" et votre "ID Secret" fournis par RTE lors de votre souscription à l'API Tempo.

## Ajouter les cartes visuelles

Les cartes sont installées et enregistrées automatiquement avec l’intégration. Après le redémarrage de Home Assistant, actualisez votre navigateur puis ajoutez la carte EDF Tempo souhaitée depuis l’éditeur du tableau de bord. La ressource Lovelace créée automatiquement est supprimée lors de la désinstallation définitive de l’intégration.

Si vos ressources Lovelace sont gérées manuellement en mode YAML, ajoutez `/edf_tempo/card.js?v=1.2.9` comme module JavaScript dans votre configuration.

## Exemple de notification Tempo

Vous pouvez créer une notification directement depuis l’éditeur graphique des automatisations de Home Assistant, sans écrire de YAML. Choisissez un déclenchement à 18 h, ajoutez la condition « EDF Tempo demain est Rouge », puis sélectionnez votre téléphone comme cible de notification.

Pour les utilisateurs qui préfèrent le YAML, l’exemple suivant envoie la même notification lorsqu’un jour rouge est prévu le lendemain :

<details>
<summary>Afficher l’exemple YAML</summary>

```yaml
alias: "EDF Tempo - Alerte jour rouge demain"
description: "Notifie à 18 h lorsqu'un jour rouge est prévu le lendemain."
triggers:
  - trigger: time
    at: "18:00:00"

conditions:
  - condition: state
    entity_id: sensor.edf_tempo_tomorrow
    state: "red"

actions:
  - action: notify.send_message
    target:
      entity_id: notify.mobile_app_mon_telephone
    data:
      title: "EDF Tempo"
      message: "Attention : demain est un jour rouge Tempo."

mode: single
```

</details>

Avant d’enregistrer cette automatisation :

- remplacez `notify.mobile_app_mon_telephone` par votre propre entité de notification ;
- vérifiez l’identifiant du capteur si vous l’avez renommé ou s’il a été créé avec une ancienne version de l’intégration ;
- conservez la valeur technique anglaise `red`, même lorsque Home Assistant affiche l’état traduit « Rouge » ;
- testez l’action depuis **Outils de développement > Actions**.

L’action [`notify.send_message`](https://www.home-assistant.io/actions/notify.send_message/) est recommandée pour les entités de notification récentes. Certaines intégrations plus anciennes fournissent uniquement leur propre action `notify.*` : dans ce cas, sélectionnez l’action proposée par votre appareil dans l’éditeur Home Assistant.

## Données et confidentialité

Les couleurs Tempo proviennent de l’API officielle de RTE. Dans Home Assistant, l’appareil est donc présenté comme une intégration communautaire et son modèle indique explicitement RTE comme source des données. Les données des saisons consultées sont conservées localement par Home Assistant afin de réduire les demandes inutiles.

## Limites connues

- La disponibilité de la couleur du lendemain dépend de sa publication par RTE.
- L’intégration présente les couleurs Tempo, mais pas les tarifs particuliers de votre contrat.
- L’enregistrement automatique des cartes nécessite le mode de gestion standard des ressources Lovelace. Le mode YAML demande une déclaration manuelle.
- L’historique disponible commence avec la saison 2015–2016.

## À propos du projet

Ce logiciel est fourni gratuitement, sans garantie et sans engagement d’assistance individuelle. Son utilisation reste sous votre responsabilité.


## Licence

Copyright 2026 **andry-paris**.

Ce projet est distribué sous licence [Apache License 2.0](LICENSE). Consultez également le fichier [NOTICE](NOTICE).
