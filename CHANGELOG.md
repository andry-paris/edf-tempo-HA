# Journal des modifications

Ce fichier présente les évolutions notables d’EDF Tempo pour Home Assistant.

Les versions `1.2.3` et `1.2.4` ne figurent pas dans l’historique Git disponible sous la forme de
versions identifiables. Elles ne sont donc pas reconstituées artificiellement dans ce journal.

## Non publié

### Corrigé

- Conservation des champs d’entités vides pendant la saisie, sans rétablissement immédiat de
  leur valeur par défaut lorsque le dernier caractère est effacé.

- Chargement préalable du sélecteur Home Assistant dans les éditeurs Aujourd’hui / Demain et
  Synthèse de saison, avec saisie et suggestions de secours si le chargement échoue.

- Mutualisation du téléchargement d’une saison absente du cache lorsque plusieurs cartes la
  demandent simultanément, pour éviter les appels RTE en double.
- Conservation du choix d’affichage des horodatages dès la première sélection, sans reconstruire
  le formulaire à chaque mise à jour de Home Assistant.
- Alignement des dates et des couleurs entre les deux colonnes lorsque le libellé Aujourd’hui
  occupe plusieurs lignes : les deux libellés partagent la même hauteur.
- Suppression du basculement automatique des blocs Aujourd’hui et Demain en une colonne sous
  640 px, avec retour à la ligne du texte lorsque la largeur disponible est insuffisante
  ([#12](https://github.com/andry-paris/edf-tempo-HA/issues/12)).

### Ajouté

- Blueprint d’alerte pour la couleur du lendemain, disponible en français et en anglais, avec
  couleurs et actions configurables et limitation à une exécution automatique par jour.
- Choix des jours affichés dans la carte EDF Tempo : aujourd’hui, demain ou les deux. Un seul
  jour utilise toute la largeur ; les préférences de colonnes et d’horodatages sont conservées.
- Affichage facultatif de la mise à jour RTE pour demain et de la dernière récupération réussie,
  sous le titre ou sous les jours. Ajout de `fetched_at` aux attributs du capteur Demain.
  Les anciens horodatages ne sont pas affichés lorsque le capteur devient indisponible.
- Choix d’une ou deux colonnes pour la carte Aujourd’hui / Demain, dans l’éditeur visuel et en
  YAML, avec deux colonnes par défaut. Affichage validé à 300 px de largeur de carte.

## [1.2.10] — 2026-09-19

### Corrigé

- Reprise plus rapide après une indisponibilité de l’API RTE, avec une nouvelle tentative toutes
  les cinq minutes.
- Conservation des dernières valeurs valides pendant une panne tant que leur date reste valable.
- Passage des capteurs à `unavailable` après minuit lorsque l’API n’a pas récupéré.
- Réduction des notifications répétées pendant une panne prolongée.

### Documentation

- Clarification de la responsabilité de l’intégration : les données officielles de RTE sont
  restituées sans validation ni correction locale des règles métier Tempo.

### Maintenance

- Mise à jour des dépendances de test et des actions de validation GitHub.

## [1.2.9] — 2026-07-29

### Ajouté

- Ressources d’identité visuelle utilisées par HACS.
- Exemple de notification lorsqu’un jour rouge est annoncé pour le lendemain.

### Modifié

- Déclaration de Home Assistant 2025.1.0 comme version minimale prise en charge.
- Simplification du parcours d’installation et de la documentation relative aux identifiants RTE.
- Présentation plus claire des quatre cartes Lovelace disponibles.
- Mise à jour des actions de validation GitHub.

## [1.2.8] — 2026-07-29

### Ajouté

- Tests de cohérence des métadonnées de release et des traductions.
- Couverture JavaScript supplémentaire pour les cartes et leur localisation.

### Modifié

- Amélioration de la localisation française et anglaise des cartes Lovelace.
- Harmonisation des états et libellés des capteurs dans Home Assistant.

## [1.2.7] — 2026-07-28

### Corrigé

- Stabilisation des identifiants d’entités et utilisation des sélecteurs de capteurs Home Assistant
  dans les éditeurs de cartes.
- Conservation de l’état du frontend en dehors des données de l’intégration.
- Conservation de noms de capteurs internes en anglais afin d’éviter des identifiants dépendants de
  la langue de Home Assistant.

## [1.2.6] — 2026-07-28

### Corrigé

- Compatibilité de l’enregistrement des ressources Lovelace avec Home Assistant 2025.1.
- Nouvelle tentative d’enregistrement automatique de la carte lorsque Lovelace est temporairement
  indisponible.
- Gestion propre des réponses JSON invalides provenant de l’API RTE.

### Documentation

- Mise à jour du lien d’inscription à l’API Tempo de RTE.
- Ajout des badges d’état du projet.

## [1.2.5] — 2026-07-27

### Ajouté

- Tests d’intégration reposant sur les outils officiels de test Home Assistant.
- Tests JavaScript des cartes Lovelace.
- Configuration Dependabot et durcissement des versions des actions GitHub.

### Corrigé

- Respect des identifiants d’entités personnalisés par l’utilisateur.
- Déclaration explicite d’une configuration exclusivement gérée par config entry.
- Renforcement du cache saisonnier, du flux de configuration et de la gestion des ressources
  Lovelace.

## [1.2.2] — 2026-07-27

### Ajouté

- Première version publique de l’intégration EDF Tempo.
- Configuration graphique avec identifiants OAuth2 RTE.
- Capteurs pour les couleurs du jour et du lendemain et le suivi de la saison Tempo.
- Historique des saisons Tempo et cache local.
- Quatre cartes Lovelace pour les vues quotidienne, mensuelle et saisonnière.
- Diagnostics, traductions française et anglaise, tests et validation HACS.

[1.2.10]: https://github.com/andry-paris/edf-tempo-HA/releases/tag/v1.2.10
[1.2.9]: https://github.com/andry-paris/edf-tempo-HA/releases/tag/v1.2.9
[1.2.8]: https://github.com/andry-paris/edf-tempo-HA/releases/tag/v1.2.8
[1.2.7]: https://github.com/andry-paris/edf-tempo-HA/releases/tag/v1.2.7
[1.2.6]: https://github.com/andry-paris/edf-tempo-HA/commit/8217392
[1.2.5]: https://github.com/andry-paris/edf-tempo-HA/commit/871389c
[1.2.2]: https://github.com/andry-paris/edf-tempo-HA/commit/259e8e6
