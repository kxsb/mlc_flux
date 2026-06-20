# Notes de version MLCFlux multi


## v1.0.7 — 20/06/2026

MLCFlux bêta v1.0.7 multi — juin 2026

Version orientée qualité des données et exploitation client.

### Résumé

Cette version ajoute l’analyse sectorielle en double lecture — catégories internes MLC et nomenclature NAF — et améliore les fiches professionnelles avec un enrichissement SIRET / NAF activable. Elle corrige aussi le ticket T-00007 : les changements de catégories professionnelles effectués dans Cyclos sont désormais récupérés automatiquement par la synchronisation quotidienne.

### Principales évolutions

- Ajout du switch d’analyse sectorielle : Interne / NAF agrégé / NAF précis.
- Ajout d’un registre économique professionnel exploitable par API.
- Ajout de l’affichage enrichi SIRET / SIREN / NAF dans les fiches professionnelles.
- Synchronisation automatique des profils professionnels Cyclos dans la sync quotidienne.
- Historisation locale des changements détectés sur les profils professionnels.
- Correction du ticket T-00007 : les catégories modifiées dans Cyclos sont répercutées dans l’analyse sectorielle.
- Compactage de la lecture de l’analyse sectorielle et amélioration du switch visuel.

Ce fichier suit les versions publiées de MLCFlux à partir de la mise en place du versionnage formalisé.

## v1.0.6 — 20/06/2026

Cette version rend les notes de version plus lisibles et directement consultables depuis l’interface, avec un historique centralisé des évolutions.

- Notes de version désormais accessibles depuis la page d’entrée et depuis l’application.
- Historique des versions affiché à partir du changelog.
- Nettoyage du format des notes pour privilégier une lecture produit.

## v1.0.5 — 20/06/2026

- Ajout des logos d’instance pour mieux distinguer La Graine et La Gonette.
- Amélioration du sélecteur de période : aperçu immédiat pendant le déplacement, rechargement seulement à la validation.
- Correction du texte de l’onglet “Réseau interprofessionnel”, désormais centré sur les échanges P→P.

## v1.0.4 — 20/06/2026

- Activation de la synchronisation automatique quotidienne : les instances peuvent désormais être mises à jour par tâche planifiée, sans relance manuelle systématique.
- Ajout d’un orchestrateur de synchronisation multi-instance pour traiter les monnaies locales configurées dans un même flux technique.
- Ajout des notes de version directement sur la page d’entrée.
- Professionnalisation de la page d’accueil publique : présentation plus sobre, introduction resserrée, chargement plus lisible des instances.

## v1.0.3 — 17/06/2026

- Stabilisation des fiches professionnelles : meilleure cohérence des onglets, des noms affichés et des libellés professionnels.
- Consolidation des vues liées aux professionnels, notamment les perspectives de réemploi et les informations utiles à l’analyse d’un acteur.
- Préparation d’une lecture plus robuste des données professionnelles entre La Gonette et La Graine.

## v1.0.2 — 16/06/2026

- Durcissement de la sécurité d’authentification et nettoyage des artefacts runtime avant déploiement.
- Stabilisation de la page publique multi-instance et de la navigation entre sélection, connexion et espace d’analyse.
- Stabilisation du guide Markdown et de la section “Info & méthodologie”.
- Ouverture de la section “Info & méthodologie” aux utilisateurs non administrateurs.
- Correction de la navigation d’administration.

## v1.0.1 — 16/06/2026

- Premier socle bêta multi-instance de MLCFlux.
- Mise en place de la sélection publique des monnaies locales.
- Première intégration des instances La Gonette et La Graine.
- Séparation entre page publique de sélection et espaces d’analyse protégés.
- Mise en place des premiers indicateurs comparables multi-MLC.
