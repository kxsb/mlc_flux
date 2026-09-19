"""
MLCFlux Lite — cartographie volontairement absente.

IMPORTANT
=========

La cartographie présente précédemment dans cette branche provenait du chantier
multi / mlcflux_neutral_dev. Elle a été volontairement supprimée lors de la
simplification Lokavaluto Lite.

NE PAS restaurer cette implémentation.

Lorsque le chantier cartographique sera repris, la source de référence devra
être la branche Git `main` de MLCFlux.

Objectif futur
==============

Reprendre depuis `main` la logique cartographique jugée pertinente, puis
l'adapter au modèle de données interne neutre de MLCFlux Lite.

La future cartographie ne devra pas dépendre directement :

- de Cyclos ;
- d'Odoo ;
- de Lokavaluto ;
- d'un provider source spécifique.

Elle devra consommer uniquement les données internes normalisées de MLCFlux.

Référence Git à consulter lors de la reprise :

    branche : main
    dépôt   : kxsb/mlc_flux

Ce fichier est volontairement non fonctionnel.
Il sert uniquement de marqueur architectural et de mémo pour le futur chantier.
"""
