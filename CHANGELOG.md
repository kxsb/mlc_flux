# Notes de version MLCFlux multi

## v1.0.5 — 20 juin 2026

### Interface multi-MLC
- Ajout des logos d’instance dans l’interface applicative pour mieux distinguer La Graine et La Gonette.
- Ajout d’une mention visuelle `DEV` sur les environnements de développement.
- Ajout du favicon dynamique selon l’instance MLC active.

### Sélecteur de période
- Amélioration du sélecteur de période : l’affichage de la période suit désormais le déplacement du curseur avant validation.
- Les données ne sont rechargées qu’au relâchement du curseur, afin d’éviter des rechargements inutiles pendant le déplacement.

### Vue professionnels
- Correction du texte d’introduction de l’onglet « Réseau interprofessionnel ».
- L’onglet ne mentionne plus les particuliers dans une vue centrée sur les échanges P→P.
- La formulation est désormais générique et ne cite plus directement le nom de l’instance dans ce bloc.


# Changelog MLCFlux

Ce fichier suit les versions publiées de MLCFlux à partir de la mise en place du versionnage formalisé.

Le versionnage officiel commence à `v1.0.4`. Les versions antérieures `v1.0.1`, `v1.0.2` et `v1.0.3` correspondent à des jalons bêta de stabilisation multi-instance, mais ne font pas l’objet de tags Git rétrospectifs.

## [1.0.4] - 2026-06-20

### Ajouté

- Activation de la synchronisation automatique quotidienne par tâche planifiée.
- Ajout d’un orchestrateur de synchronisation multi-instance.
- Ajout d’une fenêtre “Notes de version” sur la page d’entrée.
- Création du socle de versionnage officiel du dépôt : fichier `VERSION`, changelog et documentation de release.

### Modifié

- Professionnalisation de la page d’accueil publique.
- Harmonisation de l’affichage de version en `v1.0.4` sur l’interface publique et l’application interne.
- Réorganisation des notes de version pour mettre en avant les changements fonctionnels majeurs plutôt que les micro-corrections d’interface.

### Corrigé

- Correction du chargement visuel des cartes d’instances après suppression du bandeau “Ouvrir une instance”.
- Nettoyage de l’affichage de la page d’entrée multi-instance.

### Notes

`v1.0.4` est la première version destinée à être taguée officiellement dans Git.
