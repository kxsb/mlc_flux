# GEO001 — modèle géographique interne MLCFlux

État initial : 2026-09-19.

## 1. Objectif

La géographie de MLCFlux doit être indépendante du provider
qui fournit les données.

Architecture cible :

    source provider native
            |
            v
    normalisation provider
            |
            v
    résolution géographique
            |
            +--------------------+
            |                    |
            v                    v
    actor_geography      geographic_areas
            |
            v
    analytics géographiques
            |
            v
    API neutre
            |
            v
    frontend cartographique

Les analytics, routes métier et composants frontend ne doivent
pas lire directement une table Lokavaluto, Cyclos, Odoo ou autre.

## 2. Pourquoi GEO001A ne crée pas de geo_raw

Une table `geo_raw` distincte n'est pas retenue à ce stade.

La couche provider normalisée constitue déjà la donnée source
persistée. Le resolver peut lire cette couche et produire la
géographie interne canonique.

La traçabilité nécessaire est conservée dans :

- `resolution_sources_json` ;
- `resolution_trace_json` ;
- `resolution_method` ;
- `resolved_at`.

Si un besoin réel d'historisation de plusieurs observations
géographiques concurrentes apparaît ultérieurement, une table
d'observations pourra être ajoutée sans modifier le contrat
consommé par les analytics.

## 3. geographic_areas

`geographic_areas` représente les objets territoriaux
réutilisables.

Exemples d'identifiants envisagés :

- `FR:postal:69007`
- `FR:commune:69387`
- `FR:mlc:gonette`

Une aire peut contenir :

- un type de territoire ;
- un code stable ;
- un nom ;
- un parent ;
- un centroïde ;
- une géométrie GeoJSON ;
- sa provenance.

Les géométries ne doivent pas être dupliquées pour chaque acteur.

## 4. actor_geography

`actor_geography` contient une seule géographie canonique
résolue par acteur.

La même ligne peut exprimer plusieurs granularités :

- territoire général de la MLC ;
- zone postale ;
- commune ;
- adresse textuelle ;
- latitude / longitude.

La colonne `precision_level` décrit ce que l'on sait réellement.

Valeurs initiales envisagées :

- `unknown`
- `mlc_territory`
- `postal_area`
- `commune`
- `address`
- `exact_point`

Cette liste est un contrat métier, pas une contrainte SQL fermée,
afin de permettre de futurs niveaux comme EPCI ou département.

## 5. Précision et confiance

La précision géographique et la confiance sont deux notions
distinctes.

Exemples :

    precision_level = exact_point
    confidence_level = low

Un point est disponible mais plusieurs sources divergent.

À l'inverse :

    precision_level = postal_area
    confidence_level = high

Plusieurs sources concordent sur la zone mais aucune ne permet
une localisation plus précise.

## 6. Particuliers et confidentialité

Le modèle autorise une politique différente selon la famille
d'acteurs.

Un professionnel peut disposer d'un point cartographique précis.

Un particulier peut être limité à :

- un territoire général ;
- une commune ;
- une zone postale.

Aucun point individuel n'est nécessaire pour les analyses
agrégées U→P historiques.

## 7. Compatibilité transitoire

Les champs géographiques actuellement présents dans
`professional_enrichment` sont conservés pendant la migration.

À terme, les analytics géographiques devront lire
`actor_geography`.

`professional_enrichment` ne devra plus constituer une seconde
source de vérité géographique.

## 8. Étapes suivantes

GEO001B :

- importer le référentiel territorial existant vers
  `geographic_areas`.

GEO001C :

- migrer les professionnels historiques vers `actor_geography` ;
- produire la résolution à partir des preuves Odoo/Cyclos
  conservées dans le snapshot legacy.

Puis les représentations cartographiques seront reconnectées une
par une sur le nouveau modèle.

## 9. GEO001B — référentiel territorial

Le référentiel historique
`consumption_postal_areas.json` peut être importé dans
`geographic_areas`.

L'import est idempotent et indépendant des analytics.

Pour la France, les identifiants utilisent notamment :

- `FR:mlc:<mlc_id>` pour le périmètre fonctionnel d'une MLC ;
- `FR:postal:<code>` pour une zone postale.

Le territoire MLC n'est pas utilisé comme `parent_area_id` des
zones postales : l'appartenance au périmètre d'un dispositif ne
constitue pas une relation administrative de parenté géographique.

Les géométries historiques issues de `geo.api.gouv.fr/communes`
conservent leur sémantique
`commune_contours_by_postal_code`.

Elles sont donc décrites comme des contours communaux regroupés
par code postal et non comme des limites postales exactes.

## 10. GEO001C — résolution des professionnels

La première alimentation de `actor_geography` migre le registre
professionnel existant.

Cette migration utilise `professional_enrichment` comme source
transitoire. Les preuves historiques conservées dans
`raw_safe_json` servent uniquement à qualifier la confiance dans
la résolution.

Les noms des anciens providers peuvent apparaître dans
`resolution_sources_json` ou `resolution_trace_json` à titre de
traçabilité. Ils ne font pas partie du schéma ni du contrat
consommé par les analytics.

La précision et la confiance restent indépendantes.

Exemples :

- deux sources concordantes avec un point :
  `exact_point / high / cross_source_confirmed` ;
- deux sources divergentes mais point disponible :
  `exact_point / low / cross_source_mismatch` ;
- une seule source exploitable :
  `exact_point / medium` ;
- adresse connue sans coordonnées :
  `address / medium`.

Le rattachement à `postal_area_id` n'est réalisé que si la zone
existe réellement dans `geographic_areas`.

Un code postal connu mais absent du référentiel reste conservé
dans `actor_geography.postal_code` sans création artificielle
d'une aire vide.

## 11. GEO002A — premier consommateur du modèle GEO

La carte « bassin de paiement » de la fiche professionnelle est
le premier composant reconnecté au modèle géographique neutre.

L'endpoint :

`/api/pro/<professional_ref>/payment-basin-map`

utilise désormais :

- `actor_geography` pour le professionnel étudié ;
- `actor_geography` pour les professionnels payeurs P→P ;
- `actor_geography` pour les particuliers U lorsque leur
  géographie est disponible ;
- `geographic_areas` pour les centroïdes et géométries postales ;
- `professional_enrichment` uniquement pour les métadonnées de
  présentation non géographiques ;
- `transactions` pour les flux.

Il ne lit plus les anciennes tables Odoo/Cyclos ni
`consumption_postal_areas.json` au runtime.

Les coordonnées avec `confidence_level = low` ne sont pas
publiées sur la carte.

Tant que les acteurs U ne sont pas encore alimentés dans
`actor_geography`, leurs paiements restent comptabilisés dans la
couverture mais sont signalés comme non cartographiables.

## 12. GEO002A2 — fond territorial simplifié

Le bassin de paiement dispose d'un fond cartographique interne
construit exclusivement depuis `geographic_areas`.

Le backend expose :

`geometry.territory_area_geojson`

pour le fond territorial général, tandis que :

`geometry.visible_source_area_geojson`

reste réservé aux zones effectivement impliquées dans les flux
des particuliers.

Les contours issus de plusieurs zones postales sont dédupliqués
à partir de l'identifiant de la géométrie source lorsque celui-ci
est disponible.

Cette déduplication est notamment nécessaire lorsque plusieurs
codes postaux partagent le même contour communal.

Aucun fichier `consumption_postal_areas.json` n'est lu par
l'endpoint au runtime.
