# MLCFlux — contrat de données interne et entrées attendues

État de référence : 2026-09-19

Ce document décrit les données que le backend doit être capable d'alimenter pour permettre à MLCFlux d'exploiter l'ensemble de ses fonctions analytiques.

Le schéma physique ci-dessous est extrait automatiquement de la base SQLite actuelle. Il constitue donc le point de référence concret au moment de CLEAN001.

## 1. Niveaux de données

MLCFlux distingue trois catégories :

### Entrées primaires

- transactions ;
- soldes particuliers ;
- soldes professionnels ;
- registre/enrichissement professionnel ;
- indicateurs monétaires.

### Données dérivées

- caches quotidiens de pilotage ;
- caches annuels de pilotage ;
- agrégats calculés à la volée par les services analytics.

### Présentation

L'API et le frontend doivent consommer le modèle interne et non les structures natives du provider.

## 2. Matrice fonctionnelle

| Dataset | Niveau | Utilité principale |
|---|---|---|
| `transactions` | essentiel | activité, flux, réseaux, chaînes professionnelles, analyses sectorielles |
| `professional_enrichment` | fortement recommandé | noms, secteurs, fiches pros, enrichissement économique et géographique |
| `professional_daily_balances` | recommandé | stocks professionnels et indicateurs de détention |
| `individual_daily_balances` | recommandé | stocks particuliers et pilotage monétaire avancé |
| `monetary_indicators_daily` | recommandé | masse, garanties et rapprochements quotidiens |
| `monetary_indicators_yearly` | recommandé | historique annuel monétaire |
| `pilotage_holdings_daily_cache` | dérivé | accélération du pilotage |
| `pilotage_yearly_cache` | dérivé | accélération des analyses annuelles |

Un backend ne disposant que de `transactions` peut faire fonctionner une partie importante de MLCFlux, mais pas son plein potentiel.

## 3. Schéma physique actuel

### `individual_daily_balances`

| Colonne | Type SQLite | NOT NULL | PK | Défaut |
|---|---|---:|---:|---|
| `pseudonym` | `TEXT` | oui | oui | `` |
| `balance_date` | `TEXT` | oui | oui | `` |
| `balance` | `REAL` | oui | non | `` |
| `fetched_at` | `TEXT` | oui | non | `` |
| `source` | `TEXT` | oui | non | `'cyclos_balances_history_daily'` |

### `monetary_indicators_daily`

| Colonne | Type SQLite | NOT NULL | PK | Défaut |
|---|---|---:|---:|---|
| `snapshot_date` | `TEXT` | non | oui | `` |
| `year` | `INTEGER` | oui | non | `` |
| `month` | `INTEGER` | oui | non | `` |
| `day` | `INTEGER` | oui | non | `` |
| `numeric_circulation` | `REAL` | oui | non | `` |
| `paper_circulation` | `REAL` | oui | non | `` |
| `total_circulation` | `REAL` | oui | non | `` |
| `numeric_guarantee_fund` | `REAL` | oui | non | `` |
| `paper_guarantee_fund` | `REAL` | oui | non | `` |
| `numeric_guarantee_gap` | `REAL` | oui | non | `` |
| `paper_guarantee_gap` | `REAL` | oui | non | `` |
| `fetched_at` | `TEXT` | oui | non | `` |
| `source` | `TEXT` | oui | non | `'odoo_jsonrpc'` |

### `monetary_indicators_yearly`

| Colonne | Type SQLite | NOT NULL | PK | Défaut |
|---|---|---:|---:|---|
| `year` | `INTEGER` | non | oui | `` |
| `numeric_circulation` | `REAL` | oui | non | `` |
| `paper_circulation` | `REAL` | oui | non | `` |
| `total_circulation` | `REAL` | oui | non | `` |
| `numeric_guarantee_fund` | `REAL` | oui | non | `` |
| `paper_guarantee_fund` | `REAL` | oui | non | `` |
| `numeric_guarantee_gap` | `REAL` | oui | non | `` |
| `paper_guarantee_gap` | `REAL` | oui | non | `` |
| `fetched_at` | `TEXT` | oui | non | `` |
| `source` | `TEXT` | oui | non | `'odoo_jsonrpc'` |

### `pilotage_holdings_daily_cache`

| Colonne | Type SQLite | NOT NULL | PK | Défaut |
|---|---|---:|---:|---|
| `day` | `TEXT` | non | oui | `` |
| `positive_user_stock` | `REAL` | oui | non | `` |
| `positive_professional_network_stock` | `REAL` | oui | non | `` |
| `positive_operator_professional_stock` | `REAL` | oui | non | `` |
| `positive_professional_total_stock` | `REAL` | oui | non | `` |
| `numeric_mass` | `REAL` | oui | non | `` |
| `computed_at` | `TEXT` | oui | non | `` |

### `pilotage_yearly_cache`

| Colonne | Type SQLite | NOT NULL | PK | Défaut |
|---|---|---:|---:|---|
| `series_key` | `TEXT` | oui | oui | `` |
| `year` | `INTEGER` | oui | oui | `` |
| `item_json` | `TEXT` | oui | non | `` |
| `computed_at` | `TEXT` | oui | non | `` |

### `professional_daily_balances`

| Colonne | Type SQLite | NOT NULL | PK | Défaut |
|---|---|---:|---:|---|
| `professional_ref` | `TEXT` | oui | oui | `` |
| `balance_date` | `TEXT` | oui | oui | `` |
| `balance` | `REAL` | oui | non | `` |
| `fetched_at` | `TEXT` | oui | non | `` |
| `source` | `TEXT` | oui | non | `'cyclos_professional_balances_history_daily'` |

### `professional_enrichment`

| Colonne | Type SQLite | NOT NULL | PK | Défaut |
|---|---|---:|---:|---|
| `professional_ref` | `TEXT` | non | oui | `` |
| `source_provider` | `TEXT` | oui | non | `` |
| `external_professional_ref` | `TEXT` | non | non | `` |
| `actor_type_internal` | `TEXT` | non | non | `` |
| `display_name` | `TEXT` | non | non | `` |
| `legal_name` | `TEXT` | non | non | `` |
| `industry_name` | `TEXT` | non | non | `` |
| `industry_internal_name` | `TEXT` | non | non | `` |
| `secondary_industries_json` | `TEXT` | non | non | `` |
| `secondary_industry_internal_names_json` | `TEXT` | non | non | `` |
| `payment_methods_accepted_json` | `TEXT` | non | non | `` |
| `detailed_activity` | `TEXT` | non | non | `` |
| `short_description` | `TEXT` | non | non | `` |
| `keywords` | `TEXT` | non | non | `` |
| `website` | `TEXT` | non | non | `` |
| `siret` | `TEXT` | non | non | `` |
| `siren` | `TEXT` | non | non | `` |
| `street` | `TEXT` | non | non | `` |
| `zip` | `TEXT` | non | non | `` |
| `city` | `TEXT` | non | non | `` |
| `latitude` | `REAL` | non | non | `` |
| `longitude` | `REAL` | non | non | `` |
| `raw_safe_json` | `TEXT` | non | non | `` |
| `fetched_at` | `TEXT` | oui | non | `` |
| `updated_at` | `TEXT` | oui | non | `` |

### `transactions`

| Colonne | Type SQLite | NOT NULL | PK | Défaut |
|---|---|---:|---:|---|
| `transaction_number` | `TEXT` | non | oui | `` |
| `external_transaction_id` | `TEXT` | non | non | `` |
| `date` | `TEXT` | oui | non | `` |
| `group_label` | `TEXT` | non | non | `` |
| `from_label` | `TEXT` | non | non | `` |
| `to_label` | `TEXT` | non | non | `` |
| `amount` | `REAL` | non | non | `` |
| `type_label` | `TEXT` | non | non | `` |

## 4. Attentes par dataset

### `transactions`

Chaque ligne doit représenter un fait transactionnel unique.

Attentes principales :

- identifiant externe stable lorsqu'il existe ;
- date/heure ou date normalisée ;
- acteur émetteur ;
- acteur destinataire ;
- montant ;
- typologie ou libellé de transaction lorsqu'elle est disponible ;
- absence de duplication liée aux jointures d'enrichissement.

La clé externe doit permettre une synchronisation idempotente lorsque le provider fournit un identifiant stable.

### `professional_enrichment`

Cette table représente le registre interne des professionnels.

Pour exploiter pleinement les fiches professionnelles et les analyses sectorielles, il est souhaitable de disposer de :

- référence professionnelle interne ;
- référence externe provider ;
- nom d'affichage ;
- raison sociale lorsque disponible ;
- secteur interne ;
- secteur/nomenclature économique ;
- secteurs secondaires ;
- description d'activité ;
- mots-clés ;
- site web ;
- SIRET/SIREN lorsque disponibles ;
- adresse ;
- code postal ;
- ville ;
- latitude/longitude lorsque disponibles ;
- provenance ;
- payload brut sûr ou informations de traçabilité lorsque pertinent.

Les informations géographiques doivent rester indépendantes de la logique transactionnelle.

### `individual_daily_balances`

Un historique quotidien permet les analyses de stock détenu par les particuliers.

L'entrée attendue associe au minimum :

- identifiant interne/pseudonymisé de l'acteur ;
- date ;
- solde ;
- provenance.

### `professional_daily_balances`

Même principe pour les professionnels :

- référence professionnelle ;
- date ;
- solde ;
- provenance.

### `monetary_indicators_daily`

Cette série fournit les stocks monétaires et éléments de garantie disponibles quotidiennement.

L'adaptateur doit remplir uniquement les indicateurs réellement fournis ou reconstructibles de manière fiable.

Aucune valeur ne doit être inventée pour satisfaire artificiellement le schéma.

### `monetary_indicators_yearly`

Cette table fournit le niveau annuel des mêmes familles d'indicateurs.

Elle peut provenir d'une source comptable directe ou d'une consolidation fiable des données internes.

### Caches `pilotage_*`

Ces tables sont dérivées.

Un adaptateur externe ne doit pas les alimenter directement. Elles doivent être recalculées à partir des datasets internes.

## 5. Provenances actuellement présentes

### `individual_daily_balances`

- `cyclos_balances_history_daily` : 2324515 ligne(s)
- `reconstructed_after_cyclos_404_from_last_balance_and_transactions` : 282 ligne(s)

### `monetary_indicators_daily`

- `odoo_jsonrpc_daily_reconstruction` : 986 ligne(s)

### `monetary_indicators_yearly`

- `odoo_jsonrpc` : 3 ligne(s)

### `professional_daily_balances`

- `cyclos_professional_balances_history_daily` : 581718 ligne(s)

### `professional_enrichment`

- `legacy_odoo_snapshot` : 201 ligne(s)

Les provenances historiques sont conservées comme faits de traçabilité.

Le nouveau backend Lokavaluto devra introduire ses propres valeurs de provenance explicites sans renommer rétroactivement les données existantes.

## 6. Configuration runtime actuellement référencée

Les noms de variables d'environnement ci-dessous sont détectés dans `server/config.py`. Les valeurs ne sont volontairement pas documentées ici.

- `ADMIN_API_TOKEN`
- `FLASK_ENV`
- `HOST`
- `MLCFLUX_SECRET_KEY`
- `PERMANENT_SESSION_LIFETIME_SECONDS`
- `PORT`
- `SECRET_KEY`
- `SESSION_COOKIE_SAMESITE`
- `SESSION_COOKIE_SECURE`
- `SYNC_API_TOKEN`

Les secrets et credentials doivent rester dans l'environnement du serveur ou dans un mécanisme de secrets approprié. Ils ne doivent jamais être inscrits dans un profil MLC versionné.

## 7. Profils/configurations JSON actuellement présents

### `server/data/info_pages_overrides.json`

- `cadre-general`
- `pilotage-monetaire`

### `server/data/instances/gonette/actor_user_links.json`

- `links`
- `updated_at`
- `version`

### `server/data/instances/gonette/consumption_postal_areas.json`

- `area_count`
- `areas`
- `failure_count`
- `failures`
- `generated_at`
- `mlc_id`
- `postal_code_count_requested`
- `schema_version`
- `source`
- `territorial_scope`

### `server/data/instances/gonette/individual_balance_reconstruction_rules.json`

- `comment`
- `rules`

### `server/data/instances/gonette/private_actor_mapping.json`

- `firstname_dictionary`
- `items`
- `next_sequence`
- `strategy`

### `server/data/instances/gonette/professional_actor_user_links.json`

- `links`
- `updated_at`
- `version`

### `server/data/instances/gonette/professional_mapping.json`

- `kind`
- `mappings`
- `mlc_id`
- `version`

### `server/data/instances/graine/actor_user_links.json`

- `links`
- `updated_at`
- `version`

### `server/data/instances/graine/consumption_postal_areas.json`

- `area_count`
- `areas`
- `failure_count`
- `failures`
- `generated_at`
- `mlc_id`
- `postal_code_count_requested`
- `schema_version`
- `source`
- `territorial_scope`

### `server/data/instances/graine/private_actor_mapping.json`

- `firstname_dictionary`
- `items`
- `next_sequence`
- `strategy`

### `server/data/instances/graine/professional_actor_user_links.json`

- `links`
- `updated_at`
- `version`

### `server/data/instances/graine/professional_mapping.json`

- `kind`
- `mappings`
- `mlc_id`
- `version`

### `server/data/mlc_profiles/gonette.json`

- `actor_classification`
- `classification`
- `currency_name`
- `currency_symbol`
- `data_strategy`
- `description`
- `features`
- `id`
- `monetary_indicators`
- `name`
- `notes`
- `professional_enrichment`
- `short_name`
- `sources`
- `status`
- `territorial_scope`
- `transaction_semantics`

### `server/data/mlc_profiles/graine.json`

- `actor_classification`
- `classification`
- `currency_name`
- `currency_symbol`
- `data_strategy`
- `description`
- `features`
- `id`
- `known_differences`
- `monetary_indicators`
- `name`
- `operator_accounts`
- `professional_enrichment`
- `short_name`
- `sources`
- `status`
- `territorial_scope`
- `transaction_semantics`

### `server/data/user_mapping.json`

- `actor:1258847393216179481`
- `actor:1258847411469790489`
- `actor:1258847412811967769`
- `actor:1258847425159998745`
- `actor:1258847426770611481`
- `actor:1258847427307482393`
- `actor:1258847430528707865`
- `actor:1258847431065578777`
- `actor:1258847431334014233`
- `actor:1258847431870885145`
- `actor:1258847442876738841`
- `actor:1258847445024222489`
- `actor:1258847446903270681`
- `actor:1258847447708577049`
- `actor:1258847447977012505`
- `actor:1258847448245447961`
- `actor:1258847448513883417`
- `actor:1258847456566947097`
- `actor:1258847462472527129`
- `actor:1258848471521406233`
- `actor:1258848533261561113`
- `actor:1258848533529996569`
- `actor:1258848534066867481`
- `actor:1258848534872173849`
- `actor:1258848545878027545`
- `actor:1258848552588913945`
- `actor:1258848555004833049`
- `actor:1258848555810139417`
- `actor:1258848567621299481`
- `actor:1258848567889734937`
- `actor:1258848568695041305`
- `actor:1258848568963476761`
- `actor:1258848569500347673`
- `actor:1258848570305654041`
- `actor:1258848633387986201`
- `actor:1258848697544060185`
- `actor:1258848699691543833`
- `actor:1258848699959979289`
- `actor:1258848700228414745`
- `actor:1258848700496850201`
- `actor:1258848700765285657`
- `actor:1258848701033721113`
- `actor:1258848701302156569`
- `actor:1258848701570592025`
- `actor:1258848701839027481`
- `actor:1258848702375898393`
- `actor:1258848702644333849`
- `actor:1258848707476172057`
- `actor:1258848717408283929`
- `actor:1258848723582299417`
- `actor:1258848724119170329`
- `actor:1258848724387605785`
- `actor:1258848724656041241`
- `actor:1258848728951008537`
- `actor:1258848741567474969`
- `actor:1258848741835910425`
- `actor:1258848742372781337`
- `actor:1258848757136731417`
- `actor:1258849004634221849`
- `actor:1258849004902657305`
- `actor:1258849005171092761`
- `actor:1258849005439528217`
- `actor:1258849005707963673`
- `actor:1258849005976399129`
- `actor:1258849006244834585`
- `actor:1258849006513270041`
- `actor:1258849007318576409`
- `actor:1258849010002930969`
- `actor:1258849016176946457`
- `actor:1258849017519123737`
- `actor:1258849020471913753`
- `actor:1258849028524977433`
- `actor:1258849029330283801`
- `actor:1258849029867154713`
- `actor:1258849036846476569`
- `actor:1258849037114912025`
- `actor:1258849037383347481`
- `actor:1258849037651782937`
- `actor:1258849048120765721`
- `actor:1258849049731378457`
- `actor:1258849050268249369`
- `actor:1258849051878862105`
- `actor:1258849052147297561`
- `actor:1258849053221039385`
- `actor:1258849053489474841`
- `actor:1258849053757910297`
- `actor:1258849055636958489`
- `actor:1258849057247571225`
- `actor:1258849058858183961`
- `actor:1258849060468796697`
- `actor:1258849060737232153`
- `actor:1258849066911247641`
- `actor:1258849067716554009`
- `actor:1258849072279956761`
- `actor:1258849081943633177`
- `actor:1258849218308844825`
- `actor:1258849221530070297`
- `actor:1258849222603812121`
- `actor:1258849223140683033`
- `actor:1258849226093473049`
- `actor:1258849227435650329`
- `actor:1258849227704085785`
- `actor:1258849403260874009`
- `actor:1258849424467275033`
- `actor:1258849429835984153`
- `actor:1258849459900755225`
- `actor:1258849460437626137`
- `actor:1258849460706061593`
- `actor:1258849467416947993`
- `actor:1258849467685383449`
- `actor:1258849469832867097`
- `actor:1258849473322528025`
- `actor:1258849475470011673`
- `actor:1258849484865252633`
- `actor:1258849493455187225`
- `actor:1258849493992058137`
- `actor:1258849496944848153`
- `actor:1258849498555460889`
- `actor:1258849498823896345`
- `actor:1258849499360767257`
- `actor:1258849500166073625`
- `actor:1258849500434509081`
- `actor:1258849503118863641`
- `actor:1258849520298732825`
- `actor:1258849525130571033`
- `actor:1258849525667441945`
- `actor:1258849526204312857`
- `actor:1258849527814925593`
- `actor:1258849529157102873`
- `actor:1258849529962409241`
- `actor:1258849532378328345`
- `actor:1258849533183634713`
- `actor:1258849533988941081`
- `actor:1258849534257376537`
- `actor:1258849534525811993`
- `actor:1258849534794247449`
- `actor:1258849535062682905`
- `actor:1258849535331118361`
- `actor:1258849535599553817`
- `actor:1258849535867989273`
- `actor:1258849536673295641`
- `actor:1258849539357650201`
- `actor:1258849539626085657`
- `actor:1258849540431392025`
- `actor:1258849540968262937`
- `actor:1258849541236698393`
- `actor:1258849541505133849`
- `actor:1258849541773569305`
- `actor:1258849543921052953`
- `actor:1258849544457923865`
- `actor:1258849546336972057`
- `actor:1258849546873842969`
- `actor:1258849547410713881`
- `actor:1258849547679149337`
- `actor:1258849547947584793`
- `actor:1258849549021326617`
- `actor:1258849549826632985`
- `actor:1258849550095068441`
- `actor:1258849550363503897`
- `actor:1258849550631939353`
- `actor:1258849550900374809`
- `actor:1258849551705681177`
- `actor:1258849553584729369`
- `actor:1258849558685003033`
- `actor:1258849558953438489`
- `actor:1258849559221873945`
- `actor:1258849559490309401`
- `actor:1258849560295615769`
- `actor:1258849563785276697`
- `actor:1258849564322147609`
- `actor:1258849565127453977`
- `actor:1258849565395889433`
- `actor:1258849565932760345`
- `actor:1258849606198078745`
- `actor:1258849606734949657`
- `actor:1258849607003385113`
- `actor:1258849608077126937`
- `actor:1258849608345562393`
- `actor:1258849608882433305`
- `actor:1258849609150868761`
- `actor:1258849609419304217`
- `actor:1258849609956175129`
- `actor:1258849610493046041`
- `actor:1258849611566787865`
- `actor:1258849613982706969`
- `actor:1258849614251142425`
- `actor:1258849635994414361`
- `actor:1258849636531285273`
- `actor:1258849636799720729`
- `actor:1258849637068156185`
- `actor:1258849637336591641`
- `actor:1258849637873462553`
- `actor:1258849638141898009`
- `actor:1258849638410333465`
- `actor:1258849638678768921`
- `actor:1258849638947204377`
- `actor:1258849639752510745`
- `actor:1258849640020946201`
- `actor:1258849674649120025`
- `actor:1258849674917555481`
- `actor:1258849675185990937`
- `actor:1258849675454426393`
- `actor:1258849679212522777`
- `actor:1258849682165312793`
- `actor:1258849682433748249`
- `actor:1258849682970619161`
- `actor:1258849683239054617`
- `actor:1258849683775925529`
- `actor:1258849685118102809`
- `actor:1258849685386538265`
- `actor:1258849685923409177`
- `actor:1258849690755247385`
- `actor:1258849726188727577`
- `actor:1258849726994033945`
- `actor:1258849727262469401`
- `actor:1258849727530904857`
- `actor:1258849728873082137`
- `actor:1258849729678388505`
- `actor:1258849729946823961`
- `actor:1258849730215259417`
- `actor:1258849756521934105`
- `actor:1258849756790369561`
- `actor:1258849757864111385`
- `actor:1258849804571880729`
- `actor:1258849804840316185`
- `actor:1258849805108751641`
- `actor:1258849805645622553`
- `actor:1258849805914058009`
- `actor:1258849806182493465`
- `actor:1258849806450928921`
- `actor:1258849807256235289`
- `actor:1258849808329977113`
- `actor:1258849810209025305`
- `actor:1258849810745896217`
- `actor:1258849852890262809`
- `actor:1258849853695569177`
- `actor:1258849919999126809`
- `actor:1258849927246884121`
- `actor:1258849928052190489`
- `actor:1258849966706896153`
- `actor:1258849968049073433`
- `actor:1258849968585944345`
- `actor:1258849988450168089`
- `actor:1258849989255474457`
- `actor:1258849989523909913`
- `actor:1258849989792345369`
- `actor:1258849990060780825`
- `actor:1258849990329216281`
- `actor:1258849990597651737`
- `actor:1258849990866087193`
- `actor:1258849991134522649`
- `actor:1258849996771667225`
- `actor:1258849997845409049`
- `actor:1258849998650715417`
- `actor:1258849999187586329`
- `actor:1258850035426372889`
- `actor:1258850035963243801`
- `actor:1258850036231679257`
- `actor:1258850037573856537`
- `actor:1258850038916033817`
- `actor:1258850039184469273`
- `actor:1258850061464612121`
- `actor:1258850061733047577`
- `actor:1258850062001483033`
- `actor:1258850068712369433`
- `actor:1258850068980804889`
- `actor:1258850069517675801`
- `actor:1258850126157557017`
- `actor:1258850128305040665`
- `actor:1258850128573476121`
- `actor:1258850129647217945`
- `actor:1258850190582066457`
- `actor:1258850191655808281`
- `actor:1258850191924243737`
- `actor:1258850195145469209`
- `actor:1258850195413904665`
- `actor:1258850197561388313`
- `actor:1258850220109966617`
- `actor:1258850220378402073`
- `actor:1258850220915272985`
- `actor:1258850221720579353`
- `actor:1258850261985897753`
- `actor:1258850266549300505`
- `actor:1258850289097878809`
- `actor:1258850329900068121`
- `actor:1258850330168503577`
- `actor:1258850332852858137`
- `actor:1258850333121293593`
- `actor:1258850357548920089`
- `actor:1258850357817355545`
- `actor:1258850358354226457`
- `actor:1258850359159532825`
- `actor:1258850359427968281`
- `actor:1258850430563364121`
- `actor:1258850431905541401`
- `actor:1258850437811121433`
- `actor:1258850461433441561`
- `actor:1258850461701877017`
- `actor:1258850463580925209`
- `actor:1258850518878629145`
- `actor:1258850520220806425`
- `actor:1258850588403412249`
- `actor:1258850593503685913`
- `actor:1258850606657023257`
- `actor:1258850608804506905`
- `actor:1258850609072942361`
- `actor:1258850610415119641`
- `actor:1258850610683555097`
- `actor:1258850614978522393`
- `actor:1258850654170098969`
- `actor:1258850654975405337`
- `actor:1258850655243840793`
- `actor:1258850655512276249`
- `actor:1258850655780711705`
- `actor:1258850656049147161`
- `actor:1258850656317582617`
- `actor:1258850656586018073`
- `actor:1258850656854453529`
- `actor:1258850657122888985`
- `actor:1258850657391324441`
- `actor:1258850657659759897`
- `actor:1258850658196630809`
- `actor:1258850658465066265`
- `actor:1258850658733501721`
- `actor:1258850659001937177`
- `actor:1258850659538808089`
- `actor:1258850660612549913`
- `actor:1258850661417856281`
- `actor:1258850661686291737`
- `actor:1258850662223162649`
- `actor:1258850662491598105`
- `actor:1258850663028469017`
- `actor:1258850664907517209`
- `actor:1258850665175952665`
- `actor:1258850666249694489`
- `actor:1258850670007790873`
- `actor:1258850670276226329`
- `actor:1258850670544661785`
- `actor:1258850671081532697`
- `actor:1258850671349968153`
- `actor:1258850671618403609`
- `actor:1258850671886839065`
- `actor:1258850672155274521`
- `actor:1258850672423709977`
- `actor:1258850672692145433`
- `actor:1258850672960580889`
- `actor:1258850673229016345`
- `actor:1258850673497451801`
- `actor:1258850673765887257`
- `actor:1258850674034322713`
- `actor:1258850674302758169`
- `actor:1258850674571193625`
- `actor:1258850674839629081`
- `actor:1258850675108064537`
- `actor:1258850675376499993`
- `actor:1258850675644935449`
- `actor:1258850675913370905`
- `actor:1258850676181806361`
- `actor:1258850676450241817`
- `actor:1258850676718677273`
- `actor:1258850676987112729`
- `actor:1258850677255548185`
- `actor:1258850677523983641`
- `actor:1258850677792419097`
- `actor:1258850678060854553`
- `actor:1258850678329290009`
- `actor:1258850678597725465`
- `actor:1258850678866160921`
- `actor:1258850679134596377`
- `actor:1258850679403031833`
- `actor:1258850679671467289`
- `actor:1258850679939902745`
- `actor:1258850680208338201`
- `actor:1258850680476773657`
- `actor:1258850680745209113`
- `actor:1258850681013644569`
- `actor:1258850681282080025`
- `actor:1258850681550515481`
- `actor:1258850681818950937`
- `actor:1258850682087386393`
- `actor:1258850682355821849`
- `actor:1258850682624257305`
- `actor:1258850682892692761`
- `actor:1258850683161128217`
- `actor:1258850683429563673`
- `actor:1258850683697999129`
- `actor:1258850683966434585`
- `actor:1258850684503305497`
- `actor:1258850684771740953`
- `actor:1258850685040176409`
- `actor:1258850685308611865`
- `actor:1258850685845482777`
- `actor:1258850686113918233`
- `actor:1258850686382353689`
- `actor:1258850686650789145`
- `actor:1258850686919224601`
- `actor:1258850687187660057`
- `actor:1258850687456095513`
- `actor:1258850687992966425`
- `actor:1258850688798272793`
- `actor:1258850689066708249`
- `actor:1258850689335143705`
- `actor:1258850689603579161`
- `actor:1258850690140450073`
- `actor:1258850690408885529`
- `actor:1258850690677320985`
- `actor:1258850690945756441`
- `actor:1258850691214191897`
- `actor:1258850691482627353`
- `actor:1258850691751062809`
- `actor:1258850692019498265`
- `actor:1258850692287933721`
- `actor:1258850692556369177`
- `actor:1258850692824804633`
- `actor:1258850693093240089`
- `actor:1258850693361675545`
- `actor:1258850693898546457`
- `actor:1258850694166981913`
- `actor:1258850694435417369`
- `actor:1258850694703852825`
- `actor:1258850694972288281`
- `actor:1258850695240723737`
- `actor:1258850695509159193`
- `actor:1258850695777594649`
- `actor:1258850696046030105`
- `actor:1258850696314465561`
- `actor:1258850696582901017`
- `actor:1258850696851336473`
- `actor:1258850697119771929`
- `actor:1258850697388207385`
- `actor:1258850697656642841`
- `actor:1258850698193513753`
- `actor:1258850698461949209`
- `actor:1258850698730384665`
- `actor:1258850698998820121`
- `actor:1258850699267255577`
- `actor:1258850699535691033`
- `actor:1258850699804126489`
- `actor:1258850700340997401`
- `actor:1258850700609432857`
- `actor:1258850700877868313`
- `actor:1258850701146303769`
- `actor:1258850701414739225`
- `actor:1258850701951610137`
- `actor:1258850702220045593`
- `actor:1258850702488481049`
- `actor:1258850702756916505`
- `actor:1258850703025351961`
- `actor:1258850703293787417`
- `actor:1258850703562222873`
- `actor:1258850703830658329`
- `actor:1258850704099093785`
- `actor:1258850704367529241`
- `actor:1258850704635964697`
- `actor:1258850704904400153`
- `actor:1258850705172835609`
- `actor:1258850705441271065`
- `actor:1258850705709706521`
- `actor:1258850706246577433`
- `actor:1258850706515012889`
- `actor:1258850706783448345`
- `actor:1258850707051883801`
- `actor:1258850707320319257`
- `actor:1258850707588754713`
- `actor:1258850707857190169`
- `actor:1258850708125625625`
- `actor:1258850708394061081`
- `actor:1258850708662496537`
- `actor:1258850708930931993`
- `actor:1258850709199367449`
- `actor:1258850709467802905`
- `actor:1258850709736238361`
- `actor:1258850710541544729`
- `actor:1258850711078415641`
- `actor:1258850711883722009`
- `actor:1258850712420592921`
- `actor:1258850712689028377`
- `actor:1258850712957463833`
- `actor:1258850713225899289`
- `actor:1258850714031205657`
- `actor:1258850714299641113`
- `actor:1258850714568076569`
- `actor:1258850714836512025`
- `actor:1258850715104947481`
- `actor:1258850715373382937`
- `actor:1258850715641818393`
- `actor:1258850715910253849`
- `actor:1258850716178689305`
- `actor:1258850716447124761`
- `actor:1258850716715560217`
- `actor:1258850716983995673`
- `actor:1258850717252431129`
- `actor:1258850717520866585`
- `actor:1258850717789302041`
- `actor:1258850718057737497`
- `actor:1258850718326172953`
- `actor:1258850718594608409`
- `actor:1258850718863043865`
- `actor:1258850719131479321`
- `actor:1258850719399914777`
- `actor:1258850719668350233`
- `actor:1258850719936785689`
- `actor:1258850720205221145`
- `actor:1258850720473656601`
- `actor:1258850720742092057`
- `actor:1258850721010527513`
- `actor:1258850721278962969`
- `actor:1258850721547398425`
- `actor:1258850721815833881`
- `actor:1258850722084269337`
- `actor:1258850722352704793`
- `actor:1258850722621140249`
- `actor:1258850722889575705`
- `actor:1258850723158011161`
- `actor:1258850723426446617`
- `actor:1258850723694882073`
- `actor:1258850723963317529`
- `actor:1258850724231752985`
- `actor:1258850724500188441`
- `actor:1258850724768623897`
- `actor:1258850725037059353`
- `actor:1258850725305494809`
- `actor:1258850725573930265`
- `actor:1258850726379236633`
- `actor:1258850726647672089`
- `actor:1258850726916107545`
- `actor:1258850727184543001`
- `actor:1258850727452978457`
- `actor:1258850727721413913`
- `actor:1258850727989849369`
- `actor:1258850728258284825`
- `actor:1258850728526720281`
- `actor:1258850728795155737`
- `actor:1258850729063591193`
- `actor:1258850729332026649`
- `actor:1258850729600462105`
- `actor:1258850729868897561`
- `actor:1258850730137333017`
- `actor:1258850730405768473`
- `actor:1258850730674203929`
- `actor:1258850730942639385`
- `actor:1258850731211074841`
- `actor:1258850731479510297`
- `actor:1258850731747945753`
- `actor:1258850732016381209`
- `actor:1258850732284816665`
- `actor:1258850732553252121`
- `actor:1258850732821687577`
- `actor:1258850733090123033`
- `actor:1258850733358558489`
- `actor:1258850733626993945`
- `actor:1258850733895429401`
- `actor:1258850734163864857`
- `actor:1258850734432300313`
- `actor:1258850734700735769`
- `actor:1258850734969171225`
- `actor:1258850735237606681`
- `actor:1258850735506042137`
- `actor:1258850735774477593`
- `actor:1258850736042913049`
- `actor:1258850736311348505`
- `actor:1258850736579783961`
- `actor:1258850736848219417`
- `actor:1258850737116654873`
- `actor:1258850737385090329`
- `actor:1258850737653525785`
- `actor:1258850737921961241`
- `actor:1258850738190396697`
- `actor:1258850738458832153`
- `actor:1258850738727267609`
- `actor:1258850738995703065`
- `actor:1258850739264138521`
- `actor:1258850739532573977`
- `actor:1258850739801009433`
- `actor:1258850740069444889`
- `actor:1258850740337880345`
- `actor:1258850740606315801`
- `actor:1258850740874751257`
- `actor:1258850741143186713`
- `actor:1258850741411622169`
- `actor:1258850741680057625`
- `actor:1258850741948493081`
- `actor:1258850742216928537`
- `actor:1258850742485363993`
- `actor:1258850742753799449`
- `actor:1258850743022234905`
- `actor:1258850743290670361`
- `actor:1258850743559105817`
- `actor:1258850743827541273`
- `actor:1258850744095976729`
- `actor:1258850744364412185`
- `actor:1258850744632847641`
- `actor:1258850744901283097`
- `actor:1258850745169718553`
- `actor:1258850745438154009`
- `actor:1258850745706589465`
- `actor:1258850745975024921`
- `actor:1258850746243460377`
- `actor:1258850746511895833`
- `actor:1258850746780331289`
- `actor:1258850747048766745`
- `actor:1258850747317202201`
- `actor:1258850747585637657`
- `actor:1258850747854073113`
- `actor:1258850748122508569`
- `actor:1258850748390944025`
- `actor:1258850748659379481`
- `actor:1258850748927814937`
- `actor:1258850749196250393`
- `actor:1258850749733121305`
- `actor:1258850750001556761`
- `actor:1258850750269992217`
- `actor:1258850750538427673`
- `actor:1258850750806863129`
- `actor:1258850751075298585`
- `actor:1258850751612169497`
- `actor:1258850751880604953`
- `actor:1258850752149040409`
- `actor:1258850752417475865`
- `actor:1258850752685911321`
- `actor:1258850752954346777`
- `actor:1258850753222782233`
- `actor:1258850753491217689`
- `actor:1258850753759653145`
- `actor:1258850754028088601`
- `actor:1258850754296524057`
- `actor:1258850754564959513`
- `actor:1258850754833394969`
- `actor:1258850755101830425`
- `actor:1258850755370265881`
- `actor:1258850755638701337`
- `actor:1258850755907136793`
- `actor:1258850756175572249`
- `actor:1258850756444007705`
- `actor:1258850756712443161`
- `actor:1258850757517749529`
- `actor:1258850757786184985`
- `actor:1258850758054620441`
- `actor:1258850758323055897`
- `actor:1258850758859926809`
- `actor:1258850759128362265`
- `actor:1258850759396797721`
- `actor:1258850759933668633`
- `actor:1258850760202104089`
- `actor:1258850760470539545`
- `actor:1258850760738975001`
- `actor:1258850761007410457`
- `actor:1258850761275845913`
- `actor:1258850761544281369`
- `actor:1258850761812716825`
- `actor:1258850762081152281`
- `actor:1258850762618023193`
- `actor:1258850762886458649`
- `actor:1258850764765506841`
- `actor:1258850765033942297`
- `actor:1258850765839248665`
- `actor:1258850766107684121`
- `actor:1258850766376119577`
- `actor:1258850766644555033`
- `actor:1258850767181425945`
- `actor:1258850767986732313`
- `actor:1258850768792038681`
- `actor:1258850769060474137`
- `actor:1258850769328909593`
- `actor:1258850769597345049`
- `actor:1258850770134215961`
- `actor:1258850770402651417`
- `actor:1258850770939522329`
- `actor:1258850771476393241`
- `actor:1258850771744828697`
- `actor:1258850772013264153`
- `actor:1258850772550135065`
- `actor:1258850773355441433`
- `actor:1258850776576666905`
- `actor:1258850776845102361`
- `actor:1258850777918844185`
- `actor:1258850779261021465`
- `actor:1258850779797892377`
- `actor:1258850781408505113`
- `actor:1258850783824424217`
- `actor:1258850784092859673`
- `actor:1258850784629730585`
- `actor:1258850784898166041`
- `actor:1258850785435036953`
- `actor:1258850785703472409`
- `actor:1258850786777214233`
- `actor:1258850787582520601`
- `actor:1258850787850956057`
- `actor:1258850788119391513`
- `actor:1258850789461568793`
- `actor:1258850790803746073`
- `actor:1258850791877487897`
- `actor:1258850794561842457`
- `actor:1258850795367148825`
- `actor:1258850801004293401`
- `actor:1258850803957083417`
- `actor:1258850804225518873`
- `actor:1258850805299260697`
- `actor:1258850805836131609`
- `actor:1258850806104567065`
- `actor:1258850806641437977`
- `actor:1258850807446744345`
- `actor:1258850807715179801`
- `actor:1258850807983615257`
- `actor:1258850808252050713`
- `actor:1258850808788921625`
- `actor:1258850809325792537`
- `actor:1258850810667969817`
- `actor:1258850813889195289`
- `actor:1258850814962937113`
- `actor:1258850816573549849`
- `actor:1258850817110420761`
- `actor:1258850817378856217`
- `actor:1258850817647291673`
- `actor:1258850817915727129`
- `actor:1258850818184162585`
- `actor:1258850818452598041`
- `actor:1258850818721033497`
- `actor:1258850818989468953`
- `actor:1258850819794775321`
- `actor:1258850820063210777`
- `actor:1258850821405388057`
- `actor:1258850821673823513`
- `actor:1258850821942258969`
- `actor:1258850822210694425`
- `actor:1258850822479129881`
- `actor:1258850822747565337`
- `actor:1258850823016000793`
- `actor:1258850823284436249`
- `actor:1258850823552871705`
- `actor:1258850823821307161`
- `actor:1258850824089742617`
- `actor:1258850824358178073`
- `actor:1258850824626613529`
- `actor:1258850824895048985`
- `actor:1258850825163484441`
- `actor:1258850825431919897`
- `actor:1258850837511515417`
- `actor:1258850838048386329`
- `actor:1258850843148659993`
- `actor:1258850844490837273`
- `actor:1258850844759272729`
- `actor:1258850848785804569`
- `actor:1258850851738594585`
- `actor:1258850852275465497`
- `actor:1258850854959820057`
- `actor:1258850857375739161`
- `actor:1258850860596964633`
- `actor:1258850860865400089`
- `actor:1258850863281319193`
- `actor:1258850863549754649`
- `actor:1258850864891931929`
- `actor:1258850867307851033`
- `actor:1258850867576286489`
- `actor:1258850867844721945`
- `actor:1258850868381592857`
- `actor:1258850872676560153`
- `actor:1258850874824043801`
- `actor:1258850875092479257`
- `actor:1258850875360914713`
- `actor:1258850875629350169`
- `actor:1258850875897785625`
- `actor:1258850876703091993`
- `actor:1258850876971527449`
- `actor:1258850887977381145`
- `actor:1258850890124864793`
- `actor:1258850890393300249`
- `actor:1258850890661735705`
- `actor:1258850891198606617`
- `actor:1258850891467042073`
- `actor:1258850891735477529`
- `actor:1258850892003912985`
- `actor:1258850892272348441`
- `actor:1258850892540783897`
- `actor:1258850892809219353`
- `actor:1258850893077654809`
- `actor:1258850893882961177`
- `actor:1258850907304733977`
- `actor:1258850907573169433`
- `actor:1258850907841604889`
- `actor:1258850908110040345`
- `actor:1258850908915346713`
- `actor:1258850912941878553`
- `actor:1258850914284055833`
- `actor:1258850914552491289`
- `actor:1258850929853312281`
- `actor:1258850930121747737`
- `actor:1258850930927054105`
- `actor:1258850931195489561`
- `actor:1258850931463925017`
- `actor:1258850931732360473`
- `actor:1258850932537666841`
- `actor:1258850933074537753`
- `actor:1258850933342973209`
- `actor:1258850934148279577`
- `actor:1258850934685150489`
- `actor:1258850938443246873`
- `actor:1258850938711682329`
- `actor:1258850939248553241`
- `actor:1258850940053859609`
- `actor:1258850943811955993`
- `actor:1258850944617262361`
- `actor:1258850944885697817`
- `actor:1258850945691004185`
- `actor:1258850959649647897`
- `actor:1258850980319178009`
- `actor:1258850980856048921`
- `actor:1258850981124484377`
- `actor:1258850987030064409`
- `actor:1258850987835370777`
- `actor:1258850988103806233`
- `actor:1258850988372241689`
- `actor:1258850988640677145`
- `actor:1258850989982854425`
- `actor:1258850990251289881`
- `actor:1258850991056596249`
- `actor:1258850991325031705`
- `actor:1258850996425305369`
- `actor:1258850997230611737`
- `actor:1258851018437012761`
- `actor:1258851031858785561`
- `actor:1258851032127221017`
- `actor:1258851032395656473`
- `actor:1258851032664091929`
- `actor:1258851032932527385`
- `actor:1258851033200962841`
- `actor:1258851033469398297`
- `actor:1258851033737833753`
- `actor:1258851034543140121`
- `actor:1258851038032801049`
- `actor:1258851039374978329`
- `actor:1258851039643413785`
- `actor:1258851039911849241`
- `actor:1258851040180284697`
- `actor:1258851042059332889`
- `actor:1258851044743687449`
- `actor:1258851046622735641`
- `actor:1258851047428042009`
- `actor:1258851048233348377`
- `actor:1258851085009005849`
- `actor:1258851095746424089`
- `actor:1258851096283295001`
- `actor:1258851096551730457`
- `actor:1258851096820165913`
- `actor:1258851097088601369`
- `actor:1258851097893907737`
- `actor:1258851098699214105`
- `actor:1258851098967649561`
- `actor:1258851099236085017`
- `actor:1258851100578262297`
- `actor:1258851100846697753`
- `actor:1258851101652004121`
- `actor:1258851101920439577`
- `actor:1258851102188875033`
- `actor:1258851102457310489`
- `actor:1258851102725745945`
- `actor:1258851102994181401`
- `actor:1258851103262616857`
- `actor:1258851103531052313`
- `actor:1258851103799487769`
- `actor:1258851104067923225`
- `actor:1258851104336358681`
- `actor:1258851104604794137`
- `actor:1258851106752277785`
- `actor:1258851107020713241`
- `actor:1258851107826019609`
- `actor:1258851132253646105`
- `actor:1258851160439368985`
- `actor:1258851162586852633`
- `actor:1258851164465900825`
- `actor:1258851178424544537`
- `actor:1258851182182640921`
- `actor:1258851182451076377`
- `actor:1258851183256382745`
- `actor:1258851184598560025`
- `actor:1258851184866995481`
- `actor:1258851185403866393`
- `actor:1258851185672301849`
- `actor:1258851185940737305`
- `actor:1258851186209172761`
- `actor:1258851216542379289`
- `actor:1258851216810814745`
- `actor:1258851217079250201`
- `actor:1258851217347685657`
- `actor:1258851238017215769`
- `actor:1258851238822522137`
- `actor:1258851239359393049`
- `actor:1258851239896263961`
- `actor:1258851240701570329`
- `actor:1258851242043747609`
- `actor:1258851244728102169`
- `actor:1258851259492052249`
- `actor:1258851259760487705`
- `actor:1258851260028923161`
- `actor:1258851260297358617`
- `actor:1258851260565794073`
- `actor:1258851260834229529`
- `actor:1258851261102664985`
- `actor:1258851261371100441`
- `actor:1258851262176406809`
- `actor:1258851266471374105`
- `actor:1258851267008245017`
- `actor:1258851267276680473`
- `actor:1258851267545115929`
- `actor:1258851267813551385`
- `actor:1258851268887293209`
- `actor:1258851270229470489`
- `actor:1258851272108518681`
- `actor:1258851307810434329`
- `actor:1258851308347305241`
- `actor:1258851309689482521`
- `actor:1258851309957917977`
- `actor:1258851310763224345`
- `actor:1258851313447578905`
- `actor:1258851316131933465`
- `actor:1258851316400368921`
- `actor:1258851316937239833`
- `actor:1258851317205675289`
- `actor:1258851318010981657`
- `actor:1258851322305948953`
- `actor:1258851322842819865`
- `actor:1258851323648126233`
- `actor:1258851336801463577`
- `actor:1258851337069899033`
- `actor:1258851337338334489`
- `actor:1258851337606769945`
- `actor:1258851337875205401`
- `actor:1258851338143640857`
- `actor:1258851338412076313`
- `actor:1258851338680511769`
- `actor:1258851339485818137`
- `actor:1258851339754253593`
- `actor:1258851358276300057`
- `actor:1258851358544735513`
- `actor:1258851359350041881`
- `actor:1258851359886912793`
- `actor:1258851360960654617`
- `actor:1258851361229090073`
- `actor:1258851362034396441`
- `actor:1258851362302831897`
- `actor:1258851364987186457`
- `actor:1258851365255621913`
- `actor:1258851365524057369`
- `actor:1258851365792492825`
- `actor:1258851380288007449`
- `actor:1258851384046103833`
- `actor:1258851384314539289`
- `actor:1258851384582974745`
- `actor:1258851384851410201`
- `actor:1258851385119845657`
- `actor:1258851385388281113`
- `actor:1258851385656716569`
- `actor:1258851385925152025`
- `actor:1258851386193587481`
- `actor:1258851386462022937`
- `actor:1258851386730458393`
- `actor:1258851386998893849`
- `actor:1258851387804200217`
- `actor:1258851388072635673`
- `actor:1258851388341071129`
- `actor:1258851389146377497`
- `actor:1258851389951683865`
- `actor:1258851391562296601`
- `actor:1258851391830732057`
- `actor:1258851392367602969`
- `actor:1258851409815907609`
- `actor:1258851410084343065`
- `actor:1258851410621213977`
- `actor:1258851411158084889`
- `actor:1258851411426520345`
- `actor:1258851411694955801`
- `actor:1258851411963391257`
- `actor:1258851412500262169`
- `actor:1258851413574003993`
- `actor:1258851427532647705`
- `actor:1258851428606389529`
- `actor:1258851428874824985`
- `actor:1258851429680131353`
- `actor:1258851431290744089`
- `actor:1258851431559179545`
- `actor:1258851431827615001`
- `actor:1258851432096050457`
- `actor:1258851432364485913`
- `actor:1258851432632921369`
- `actor:1258851432901356825`
- `actor:1258851433169792281`
- `actor:1258851433438227737`
- `actor:1258851433706663193`
- `actor:1258851433975098649`
- `actor:1258851434243534105`
- `actor:1258851434511969561`
- `actor:1258851434780405017`
- `actor:1258851435048840473`
- `actor:1258851435317275929`
- `actor:1258851436659453209`
- `actor:1258851438001630489`
- `actor:1258851438806936857`
- `actor:1258851439075372313`
- `actor:1258851439343807769`
- `actor:1258851439612243225`
- `actor:1258851440149114137`
- `actor:1258851441222855961`
- `actor:1258851500547091737`
- `actor:1258851500815527193`
- `actor:1258851506452671769`
- `actor:1258851507526413593`
- `actor:1258851507794849049`
- `actor:1258851517190090009`
- `actor:1258851517458525465`
- `actor:1258851517726960921`
- `actor:1258851517995396377`
- `actor:1258851518263831833`
- `actor:1258851518532267289`
- `actor:1258851518800702745`
- `actor:1258851519069138201`
- `actor:1258851519874444569`
- `actor:1258851522290363673`
- `actor:1258851526853766425`
- `actor:1258851527122201881`
- `actor:1258851528732814617`
- `actor:1258851529001250073`
- `actor:1258851529806556441`
- `actor:1258851566313778457`
- `actor:1258851566582213913`
- `actor:1258851566850649369`
- `actor:1258851567655955737`
- `actor:1258851567924391193`
- `actor:1258851568192826649`
- `actor:1258851568461262105`
- `actor:1258851568998133017`
- `actor:1258851569535003929`
- `actor:1258851570071874841`
- `actor:1258851570608745753`
- `actor:1258851570877181209`
- `actor:1258851571145616665`
- `actor:1258851571414052121`
- `actor:1258851571950923033`
- `actor:1258851572219358489`
- `actor:1258851572756229401`
- `actor:1258851574366842137`
- `actor:1258851575440583961`
- `actor:1258851575709019417`
- `actor:1258851594499501337`
- `actor:1258851594767936793`
- `actor:1258851595036372249`
- `actor:1258851595304807705`
- `actor:1258851596110114073`
- `actor:1258851634496384281`
- `actor:1258851640401964313`
- `actor:1258851641207270681`
- `actor:1258851641744141593`
- `actor:1258851643086318873`
- `actor:1258851644160060697`
- `actor:1258851644428496153`
- `actor:1258851645502237977`
- `actor:1258851645770673433`
- `actor:1258851646039108889`
- `actor:1258851647112850713`
- `actor:1258851648723463449`
- `actor:1258851648991898905`
- `actor:1258851649528769817`
- `actor:1258851684962250009`
- `actor:1258851685767556377`
- `actor:1258851686035991833`
- `actor:1258851686304427289`
- `actor:1258851686572862745`
- `actor:1258851687378169113`
- `actor:1258851687646604569`
- `actor:1258851689794088217`
- `actor:1258851692746878233`
- `actor:1258851696773410073`
- `actor:1258851737038728473`
- `actor:1258851737575599385`
- `actor:1258851737844034841`
- `actor:1258851738112470297`
- `actor:1258851738380905753`
- `actor:1258851738649341209`
- `actor:1258851739186212121`
- `actor:1258851739454647577`
- `actor:1258851739723083033`
- `actor:1258851739991518489`
- `actor:1258851740259953945`
- `actor:1258851741602131225`
- `actor:1258851741870566681`
- `actor:1258851743481179417`
- `actor:1258851858103119129`
- `actor:1258851860787473689`
- `actor:1258851861055909145`
- `actor:1258851861324344601`
- `actor:1258851861592780057`
- `actor:1258851862398086425`
- `actor:1258851862934957337`
- `actor:1258851863203392793`
- `actor:1258851863740263705`
- `actor:1258851864545570073`
- `actor:1258851865350876441`
- `actor:1258851865619311897`
- `actor:1258851865887747353`
- `actor:1258851866424618265`
- `actor:1258851867229924633`
- `actor:1258851867766795545`
- `actor:1258851868303666457`
- `actor:1258851868572101913`
- `actor:1258851872598633753`
- `actor:1258851872867069209`
- `actor:1258851873403940121`
- `actor:1258851874746117401`
- `actor:1258851875014552857`
- `actor:1258851876356730137`
- `actor:1258851876625165593`
- `actor:1258851877162036505`
- `actor:1258851880114826521`
- `actor:1258851881457003801`
- `actor:1258851904274017561`
- `actor:1258851925748854041`
- `actor:1258851926554160409`
- `actor:1258851927091031321`
- `actor:1258851927359466777`
- `actor:1258851928164773145`
- `actor:1258851932728175897`
- `actor:1258851932996611353`
- `actor:1258852028291198233`
- `actor:1258852028559633689`
- `actor:1258852028828069145`
- `actor:1258852029096504601`
- `actor:1258852029364940057`
- `actor:1258852029633375513`
- `actor:1258852029901810969`
- `actor:1258852030170246425`
- `actor:1258852030975552793`
- `actor:1258852031243988249`
- `actor:1258852032854600985`
- `actor:1258852033123036441`
- `actor:1258852035807391001`
- `actor:1258852036075826457`
- `actor:1258852036344261913`
- `actor:1258852036612697369`
- `actor:1258852037149568281`
- `actor:1258852037954874649`
- `actor:1258852038223310105`
- `actor:1258852039028616473`
- `actor:1258852039297051929`
- `actor:1258852039565487385`
- `actor:1258852040370793753`
- `actor:1258852040639229209`
- `actor:1258852040907664665`
- `actor:1258852041712971033`
- `actor:1258852041981406489`
- `actor:1258852042518277401`
- `actor:1258852042786712857`
- `actor:1258852043860454681`
- `actor:1258852045202631961`
- `actor:1258852097279110425`
- `actor:1258852098084416793`
- `actor:1258852098621287705`
- `actor:1258852098889723161`
- `actor:1258852099158158617`
- `actor:1258852099426594073`
- `actor:1258852100231900441`
- `actor:1258852100500335897`
- `actor:1258852100768771353`
- `actor:1258852101037206809`
- `actor:1258852101305642265`
- `actor:1258852102647819545`
- `actor:1258852104795303193`
- `actor:1258852105600609561`
- `actor:1258852105869045017`
- `actor:1258852106137480473`
- `actor:1258852106405915929`
- `actor:1258852106674351385`
- `actor:1258852107211222297`
- `actor:1258852107479657753`
- `actor:1258852107748093209`
- `actor:1258852108284964121`
- `actor:1258852108553399577`
- `actor:1258852109358705945`
- `actor:1258852112579931417`
- `actor:1258852113116802329`
- `actor:1258852113385237785`
- `actor:1258852114190544153`
- `actor:1258852114458979609`
- `actor:1258852114727415065`
- `actor:1258852115264285977`
- `actor:1258852115532721433`
- `actor:1258852115801156889`
- `actor:1258852116069592345`
- `actor:1258852116874898713`
- `actor:1258852117143334169`
- `actor:1258852119022382361`
- `actor:1258852120632995097`
- `actor:1258852120901430553`
- `actor:1258852121438301465`
- `actor:1258852121706736921`
- `actor:1258852122243607833`
- `actor:1258852122512043289`
- `actor:1258852123048914201`
- `actor:1258852123317349657`
- `actor:1258852123585785113`
- `actor:1258852124659526937`
- `actor:1258852126538575129`
- `actor:1258852127612316953`
- `actor:1258852131370413337`
- `actor:1258852131638848793`
- `actor:1258852132444155161`
- `actor:1258852132712590617`
- `actor:1258852132981026073`
- `actor:1258852133249461529`
- `actor:1258852133517896985`
- `actor:1258852133786332441`
- `actor:1258852134054767897`
- `actor:1258852134323203353`
- `actor:1258852134860074265`
- `actor:1258852135396945177`
- `actor:1258852137812864281`
- `actor:1258852144255315225`
- `actor:1258852144792186137`
- `actor:1258852145060621593`
- `actor:1258852148550282521`
- `actor:1258852148818717977`
- `actor:1258852149087153433`
- `actor:1258852149355588889`
- `actor:1258852150160895257`
- `actor:1258852151771507993`
- `actor:1258852153918991641`
- `actor:1258852154187427097`
- `actor:1258852154455862553`
- `actor:1258852154724298009`
- `actor:1258852155261168921`
- `actor:1258852155529604377`
- `actor:1258852155798039833`
- `actor:1258852156066475289`
- `actor:1258852156334910745`
- `actor:1258852156871781657`
- `actor:1258852161972055321`
- `actor:1258852165730151705`
- `actor:1258852165998587161`
- `actor:1258852166267022617`
- `actor:1258852166535458073`
- `actor:1258852167072328985`
- `actor:1258852167340764441`
- `actor:1258852167609199897`
- `actor:1258852170025119001`
- `actor:1258852170293554457`
- `actor:1258852170561989913`
- `actor:1258852170830425369`
- `actor:1258852171098860825`
- `actor:1258852171635731737`
- `actor:1258852171904167193`
- `actor:1258852172172602649`
- `actor:1258852172441038105`
- `actor:1258852173246344473`
- `actor:1258852173783215385`
- `actor:1258852174051650841`
- `actor:1258852174320086297`
- `actor:1258852174856957209`
- `actor:1258852175125392665`
- `actor:1258852177541311769`
- `actor:1258852177809747225`
- `actor:1258852178346618137`
- `actor:1258852180762537241`
- `actor:1258852181030972697`
- `actor:1258852181299408153`
- `actor:1258852181567843609`
- `actor:1258852181836279065`
- `actor:1258852182104714521`
- `actor:1258852182373149977`
- `actor:1258852182641585433`
- `actor:1258852183178456345`
- `actor:1258852183983762713`
- `actor:1258852184252198169`
- `actor:1258852184520633625`
- `actor:1258852184789069081`
- `actor:1258852185057504537`
- `actor:1258852185325939993`
- `actor:1258852185594375449`
- `actor:1258852185862810905`
- `actor:1258852187204988185`
- `actor:1258852187473423641`
- `actor:1258852187741859097`
- `actor:1258852188010294553`
- `actor:1258852188278730009`
- `actor:1258852188815600921`
- `actor:1258852189084036377`
- `actor:1258852189352471833`
- `actor:1258852189620907289`
- `actor:1258852189889342745`
- `actor:1258852190157778201`
- `actor:1258852190426213657`
- `actor:1258852190694649113`
- `actor:1258852190963084569`
- `actor:1258852191231520025`
- `actor:1258852191499955481`
- `actor:1258852191768390937`
- `actor:1258852192305261849`
- `actor:1258852192573697305`
- `actor:1258852192842132761`
- `actor:1258852193110568217`
- `actor:1258852193379003673`
- `actor:1258852193647439129`
- `actor:1258852193915874585`
- `actor:1258852194184310041`
- `actor:1258852194452745497`
- `actor:1258852194721180953`
- `actor:1258852194989616409`
- `actor:1258852195258051865`
- `actor:1258852195526487321`
- `actor:1258852195794922777`
- `actor:1258852198747712793`
- `actor:1258852217269759257`
- `actor:1258852217538194713`
- `actor:1258852217806630169`
- `actor:1258852218075065625`
- `actor:1258852218343501081`
- `actor:1258852218611936537`
- `actor:1258852218880371993`
- `actor:1258852219148807449`
- `actor:1258852219417242905`
- `actor:1258852219685678361`
- `actor:1258852219954113817`
- `actor:1258852220222549273`
- `actor:1258852220490984729`
- `actor:1258852220759420185`
- `actor:1258852221027855641`
- `actor:1258852221296291097`
- `actor:1258852223712210201`
- `actor:1258852223980645657`
- `actor:1258852224517516569`
- `actor:1258852224785952025`
- `actor:1258852225054387481`
- `actor:1258852225322822937`
- `actor:1258852225591258393`
- `actor:1258852242771127577`
- `actor:1258852243307998489`
- `actor:1258852243576433945`
- `actor:1258852243844869401`
- `actor:1258852244113304857`
- `actor:1258852244381740313`
- `actor:1258852244650175769`
- `actor:1258852244918611225`
- `actor:1258852245187046681`
- `actor:1258852245455482137`
- `actor:1258852245723917593`
- `actor:1258852245992353049`
- `actor:1258852246260788505`
- `actor:1258852246529223961`
- `actor:1258852246797659417`
- `actor:1258852247066094873`
- `actor:1258852247334530329`
- `actor:1258852247602965785`
- `actor:1258852247871401241`
- `actor:1258852248139836697`
- `actor:1258852248408272153`
- `actor:1258852248676707609`
- `actor:1258852248945143065`
- `actor:1258852249213578521`
- `actor:1258852249482013977`
- `actor:1258852249750449433`
- `actor:1258852250018884889`
- `actor:1258852250287320345`
- `actor:1258852250555755801`
- `actor:1258852250824191257`
- `actor:1258852251092626713`
- `actor:1258852251361062169`
- `actor:1258852251629497625`
- `actor:1258852251897933081`
- `actor:1258852252434803993`
- `actor:1258852262366915865`
- `actor:1258852268272495897`
- `actor:1258852277399301401`
- `actor:1258852281694268697`
- `actor:1258852282231139609`
- `actor:1258852282499575065`
- `actor:1258852284647058713`
- `actor:1258852303169105177`
- `actor:1258852304511282457`
- `actor:1258852304779717913`
- `actor:1258852305853459737`
- `actor:1258852306121895193`
- `actor:1258852308000943385`
- `actor:1258852312027475225`
- `actor:1258852312295910681`
- `actor:1258852312564346137`
- `actor:1258852313101217049`
- `actor:1258852313638087961`
- `actor:1258852313906523417`
- `actor:1258852314174958873`
- `actor:1258852314980265241`
- `actor:1258852315248700697`
- `actor:1258852315517136153`
- `actor:1258852315785571609`
- `actor:1258852316590877977`
- `actor:1258852316859313433`
- `actor:1258852317127748889`
- `actor:1258852317396184345`
- `actor:1258852317664619801`
- `actor:1258852317933055257`
- `actor:1258852320080538905`
- `actor:1258852321422716185`
- `actor:1258852321691151641`
- `actor:1258852322228022553`
- `actor:1258852322764893465`
- `actor:1258852323033328921`
- `actor:1258852324107070745`
- `actor:1258852324375506201`
- `actor:1258852324643941657`
- `actor:1258852325717683481`
- `actor:1258852325986118937`
- `actor:1258852326254554393`
- `actor:1258852326522989849`
- `actor:1258852327328296217`
- `actor:1258852327596731673`
- `actor:1258852328938908953`
- `actor:1258852329207344409`
- `actor:1258852331086392601`
- `actor:1258852331354828057`
- `actor:1258852331891698969`
- `actor:1258852338334149913`
- `actor:1258852338602585369`
- `actor:1258852338871020825`
- `actor:1258852339139456281`
- `actor:1258852340481633561`
- `actor:1258852341823810841`
- `actor:1258852342092246297`
- `actor:1258852342629117209`
- `actor:1258852343434423577`
- `actor:1258852343702859033`
- `actor:1258852344239729945`
- `actor:1258852345581907225`
- `actor:1258852345850342681`
- `actor:1258852347192519961`
- `actor:1258852347460955417`
- `actor:1258852347729390873`
- `actor:1258852347997826329`
- `actor:1258852348266261785`
- `actor:1258852348803132697`
- `actor:1258852349071568153`
- `actor:1258852350413745433`
- `actor:1258852350950616345`
- `actor:1258852351219051801`
- `actor:1258852351487487257`
- `actor:1258852352292793625`
- `actor:1258852354171841817`
- `actor:1258852354440277273`
- `actor:1258852354708712729`
- `actor:1258852354977148185`
- `actor:1258852355514019097`
- `actor:1258852355782454553`
- `actor:1258852356050890009`
- `actor:1258852356319325465`
- `actor:1258852356587760921`
- `actor:1258852356856196377`
- `actor:1258852357393067289`
- `actor:1258852358735244569`
- `actor:1258852360077421849`
- `actor:1258852360345857305`
- `actor:1258852361956470041`
- `actor:1258852362224905497`
- `actor:1258852362493340953`
- `actor:1258852363030211865`
- `actor:1258852363298647321`
- `actor:1258852363835518233`
- `actor:1258852364103953689`
- `actor:1258852368935791897`
- `actor:1258852369204227353`
- `actor:1258852370814840089`
- `actor:1258852371083275545`
- `actor:1258852372157017369`
- `actor:1258852373767630105`
- `actor:1258852376183549209`
- `actor:1258852376451984665`
- `actor:1258852376720420121`
- `actor:1258852376988855577`
- `actor:1258852382089129241`
- `actor:1258852386920967449`
- `actor:1258852387189402905`
- `actor:1258852387994709273`
- `actor:1258852388263144729`
- `actor:1258852388531580185`
- `actor:1258852388800015641`
- `actor:1258852391484370201`
- `actor:1258852392826547481`
- `actor:1258852393094982937`
- `actor:1258852397658385689`
- `actor:1258852398195256601`
- `actor:1258852398463692057`
- `actor:1258852399268998425`
- `actor:1258852401953352985`
- `actor:1258852402221788441`
- `actor:1258852403563965721`
- `actor:1258852404369272089`
- `actor:1258852405711449369`
- `actor:1258852419133222169`
- `actor:1258852419401657625`
- `actor:1258852419938528537`
- `actor:1258852420743834905`
- `actor:1258852458056363289`
- `actor:1258852459398540569`
- `actor:1258852459666976025`
- `actor:1258852465304120601`
- `actor:1258852465572556057`
- `actor:1258852476041538841`
- `actor:1258852477115280665`
- `actor:1258852477920587033`
- `actor:1258852478189022489`
- `actor:1258852480336506137`
- `actor:1258852481141812505`
- `actor:1258852481410247961`
- `actor:1258852481947118873`
- `actor:1258852482483989785`
- `actor:1258852482752425241`
- `actor:1258852483826167065`
- `actor:1258852484363037977`
- `actor:1258852485436779801`
- `actor:1258852485705215257`
- `actor:1258852486242086169`
- `actor:1258852486778957081`
- `actor:1258852487584263449`
- `actor:1258852487852698905`
- `actor:1258852488658005273`
- `actor:1258852488926440729`
- `actor:1258852489463311641`
- `actor:1258852489731747097`
- `actor:1258852491342359833`
- `actor:1258852491610795289`
- `actor:1258852492147666201`
- `actor:1258852493758278937`
- `actor:1258852494563585305`
- `actor:1258852495368891673`
- `actor:1258852495637327129`
- `actor:1258852495905762585`
- `actor:1258852496174198041`
- `actor:1258852498053246233`
- `actor:1258852498321681689`
- `actor:1258852498590117145`
- `actor:1258852499126988057`
- `actor:1258852502885084441`
- `actor:1258852503153519897`
- `actor:1258852504495697177`
- `actor:1258852507448487193`
- `actor:1258852508253793561`
- `actor:1258852509059099929`
- `actor:1258852509595970841`
- `actor:1258852510938148121`
- `actor:1258852511206583577`
- `actor:1258852513622502681`
- `actor:1258852513890938137`
- `actor:1258852514159373593`
- `actor:1258852514427809049`
- `actor:1258852518991211801`
- `actor:1258852521138695449`
- `actor:1258852521944001817`
- `actor:1258852522749308185`
- `actor:1258852523017743641`
- `actor:1258852526238969113`
- `actor:1258852530802371865`
- `actor:1258852531876113689`
- `actor:1258852532681420057`
- `actor:1258852539929177369`
- `actor:1258852540734483737`
- `actor:1258852541002919193`
- `actor:1258852541539790105`
- `actor:1258852541808225561`
- `actor:1258852542076661017`
- `actor:1258852542345096473`
- `actor:1258852543150402841`
- `actor:1258852545029451033`
- `actor:1258852545834757401`
- `actor:1258852546371628313`
- `actor:1258852546640063769`
- `actor:1258852548787547417`
- `actor:1258852549592853785`
- `actor:1258852550129724697`
- `actor:1258852552545643801`
- `actor:1258852552814079257`
- `actor:1258852557109046553`
- `actor:1258852557377482009`
- `actor:1258852559793401113`
- `actor:1258852560061836569`
- `actor:1258852560330272025`
- `actor:1258852560867142937`
- `actor:1258852561404013849`
- `actor:1258852561672449305`
- `actor:1258852563283062041`
- `actor:1258852563551497497`
- `actor:1258852563819932953`
- `actor:1258852564088368409`
- `actor:1258852564356803865`
- `actor:1258852564625239321`
- `actor:1258852564893674777`
- `actor:1258852568383335705`
- `actor:1258852568651771161`
- `actor:1258852568920206617`
- `actor:1258852569188642073`
- `actor:1258852569457077529`
- `actor:1258852569725512985`
- `actor:1258852569993948441`
- `actor:1258852570262383897`
- `actor:1258852571067690265`
- `actor:1258852573752044825`
- `actor:1258852574020480281`
- `actor:1258852575362657561`
- `actor:1258852576973270297`
- `actor:1258852577778576665`
- `actor:1258852590931914009`
- `actor:1258852591200349465`
- `actor:1258852591737220377`
- `actor:1258852592005655833`
- `actor:1258852592274091289`
- `actor:1258852592542526745`
- `actor:1258852592810962201`
- `actor:1258852614554234137`
- `actor:1258852615091105049`
- `actor:1258852615359540505`
- `actor:1258852616970153241`
- `actor:1258852619117636889`
- `actor:1258852619922943257`
- `actor:1258852620191378713`
- `actor:1258852620459814169`
- `actor:1258852620728249625`
- `actor:1258852620996685081`
- `actor:1258852621265120537`
- `actor:1258852622070426905`
- `actor:1258852622338862361`
- `actor:1258852622607297817`
- `actor:1258852622875733273`
- `actor:1258852623681039641`
- `actor:1258852629586619673`
- `actor:1258852629855055129`
- `actor:1258852630123490585`
- `actor:1258852630391926041`
- `actor:1258852630660361497`
- `actor:1258852630928796953`
- `actor:1258852631197232409`
- `actor:1258852631465667865`
- `actor:1258852631734103321`
- `actor:1258852632002538777`
- `actor:1258852632270974233`
- `actor:1258852632539409689`
- `actor:1258852632807845145`
- `actor:1258852633076280601`
- `actor:1258852633344716057`
- `actor:1258852633613151513`
- `actor:1258852633881586969`
- `actor:1258852634150022425`
- `actor:1258852634418457881`
- `actor:1258852634686893337`
- `actor:1258852634955328793`
- `actor:1258852635223764249`
- `actor:1258852635492199705`
- `actor:1258852635760635161`
- `actor:1258852636029070617`
- `actor:1258852636297506073`
- `actor:1258852636565941529`
- `actor:1258852636834376985`
- `actor:1258852637102812441`
- `actor:1258852637371247897`
- `actor:1258852637639683353`
- `actor:1258852637908118809`
- `actor:1258852638176554265`
- `actor:1258852638444989721`
- `actor:1258852638713425177`
- `actor:1258852638981860633`
- `actor:1258852639250296089`
- `actor:1258852639518731545`
- `actor:1258852639787167001`
- `actor:1258852640055602457`
- `actor:1258852640324037913`
- `actor:1258852640592473369`
- `actor:1258852640860908825`
- `actor:1258852641129344281`
- `actor:1258852641666215193`
- `actor:1258852641934650649`
- `actor:1258852642203086105`
- `actor:1258852642471521561`
- `actor:1258852642739957017`
- `actor:1258852643545263385`
- `actor:1258852643813698841`
- `actor:1258852644082134297`
- `actor:1258852644350569753`
- `actor:1258852644619005209`
- `actor:1258852644887440665`
- `actor:1258852645155876121`
- `actor:1258852645424311577`
- `actor:1258852645692747033`
- `actor:1258852645961182489`
- `actor:1258852646229617945`
- `actor:1258852646498053401`
- `actor:1258852648377101593`
- `actor:1258852648645537049`
- `actor:1258852649987714329`
- `actor:1258852650256149785`
- `actor:1258852650793020697`
- `actor:1258852651061456153`
- `actor:1258852651329891609`
- `actor:1258852651598327065`
- `actor:1258852651866762521`
- `actor:1258852652135197977`
- `actor:1258852655356423449`
- `actor:1258852655624858905`
- `actor:1258852655893294361`
- `actor:1258852656161729817`
- `actor:1258852656430165273`
- `actor:1258852656698600729`
- `actor:1258852656967036185`
- `actor:1258852657235471641`
- `actor:1258852657503907097`
- `actor:1258852657772342553`
- `actor:1258852658040778009`
- `actor:1258852658309213465`
- `actor:1258852658577648921`
- `actor:1258852658846084377`
- `actor:1258852659114519833`
- `actor:1258852659382955289`
- `actor:1258852659651390745`
- `actor:1258852659919826201`
- `actor:1258852660188261657`
- `actor:1258852660456697113`
- `actor:1258852660725132569`
- `actor:1258852660993568025`
- `actor:1258852661262003481`
- `actor:1258852661530438937`
- `actor:1258852661798874393`
- `actor:1258852662067309849`
- `actor:1258852662335745305`
- `actor:1258852662604180761`
- `actor:1258852662872616217`
- `actor:1258852663141051673`
- `actor:1258852663409487129`
- `actor:1258852663677922585`
- `actor:1258852666630712601`
- `actor:1258852668241325337`
- `actor:1258852668509760793`
- `actor:1258852668778196249`
- `actor:1258852669046631705`
- `actor:1258852669315067161`
- `actor:1258852669583502617`
- `actor:1258852669851938073`
- `actor:1258852670120373529`
- `actor:1258852670925679897`
- `actor:1258852672804728089`
- `actor:1258852674146905369`
- `actor:1258852674415340825`
- `actor:1258852675757518105`
- `actor:1258852676025953561`
- `actor:1258852676562824473`
- `actor:1258852677368130841`
- `actor:1258852681663098137`
- `actor:1258852688373984537`
- `actor:1258852688642419993`
- `actor:1258852688910855449`
- `actor:1258852689447726361`
- `actor:1258852691595210009`
- `actor:1258852698306096409`
- `actor:1258852698574531865`
- `actor:1258852699111402777`
- `actor:1258852702869499161`
- `actor:1258852704480111897`
- `actor:1258852705016982809`
- `actor:1258852705822289177`
- `actor:1258852706359160089`
- `actor:1258852706627595545`
- `actor:1258852709848821017`
- `actor:1258852710385691929`
- `actor:1258852713070046489`
- `actor:1258852713875352857`
- `actor:1258852714143788313`
- `actor:1258852721123110169`
- `actor:1258852726223383833`
- `actor:1258852726491819289`
- `actor:1258852727028690201`
- `actor:1258852727297125657`
- `actor:1258852727565561113`
- `actor:1258852727833996569`
- `actor:1258852730786786585`
- `actor:1258852732128963865`
- `actor:1258852732665834777`
- `actor:1258852733739576601`
- `actor:1258852734008012057`
- `actor:1258852734813318425`
- `actor:1258852735081753881`
- `actor:1258852735618624793`
- `actor:1258852736423931161`
- `actor:1258852736960802073`
- `actor:1258852737229237529`
- `actor:1258852737497672985`
- `actor:1258852738034543897`
- `actor:1258852738302979353`
- `actor:1258852738839850265`
- `actor:1258852739376721177`
- `actor:1258852740182027545`
- `actor:1258852740987333913`
- `actor:1258852742866382105`
- `actor:1258852743134817561`
- `actor:1258852746892913945`
- `actor:1258852749040397593`
- `actor:1258852749577268505`
- `actor:1258852750382574873`
- `actor:1258852751187881241`
- `actor:1258852751993187609`
- `actor:1258852752261623065`
- `actor:1258852752530058521`
- `actor:1258852752798493977`
- `actor:1258852753066929433`
- `actor:1258852753603800345`
- `actor:1258852753872235801`
- `actor:1258852754140671257`
- `actor:1258852754409106713`
- `actor:1258852754677542169`
- `actor:1258852754945977625`
- `actor:1258852755751283993`
- `actor:1258852756019719449`
- `actor:1258852756288154905`
- `actor:1258852757361896729`
- `actor:1258852762462170393`
- `actor:1258852784473877785`
- `actor:1258852784742313241`
- `actor:1258852785010748697`
- `actor:1258852785279184153`
- `actor:1258852785547619609`
- `actor:1258852786352925977`
- `actor:1258852787158232345`
- `actor:1258852789574151449`
- `actor:1258852790916328729`
- `actor:1258852791721635097`
- `actor:1258852792258506009`
- `actor:1258852792526941465`
- `actor:1258852793869118745`
- `actor:1258852794942860569`
- `actor:1258852795211296025`
- `actor:1258852795748166937`
- `actor:1258852796016602393`
- `actor:1258852796285037849`
- `actor:1258852805948714265`
- `actor:1258852806754020633`
- `actor:1258852807290891545`
- `actor:1258852807827762457`
- `actor:1258852808096197913`
- `actor:1258852809438375193`
- `actor:1258852809706810649`
- `actor:1258852809975246105`
- `actor:1258852810243681561`
- `actor:1258852810780552473`
- `actor:1258852811585858841`
- `actor:1258852812122729753`
- `actor:1258852812659600665`
- `actor:1258852812928036121`
- `actor:1258852813464907033`
- `actor:1258852814001777945`
- `actor:1258852816149261593`
- `actor:1258852816954567961`
- `actor:1258852821786406169`
- `actor:1258852822054841625`
- `actor:1258852822323277081`
- `actor:1258852822591712537`
- `actor:1258852823128583449`
- `actor:1258852823933889817`
- `actor:1258852824202325273`
- `actor:1258852824470760729`
- `actor:1258852824739196185`
- `actor:1258852825544502553`
- `actor:1258852836013485337`
- `actor:1258852836281920793`
- `actor:1258852836550356249`
- `actor:1258852837355662617`
- `actor:1258852837624098073`
- `actor:1258852842724371737`
- `actor:1258852842992807193`
- `actor:1258852843261242649`
- `actor:1258852843529678105`
- `actor:1258852843798113561`
- `actor:1258852844066549017`
- `actor:1258852844603419929`
- `actor:1258852848629951769`
- `actor:1258852849166822681`
- `actor:1258852849435258137`

## 8. Obligations de l'adaptateur

Pour chaque dataset qu'il sait fournir, l'adaptateur doit garantir :

- déterminisme ;
- idempotence ;
- absence de doublons ;
- conservation des identifiants externes utiles ;
- précision financière ;
- dates normalisées ;
- provenance explicite ;
- valeurs nulles lorsque l'information n'existe pas ;
- séparation entre faits transactionnels et enrichissement.

## 9. Niveau de fonctionnement attendu

### Niveau minimal

Transactions fiables uniquement.

Permet principalement les analyses de flux et d'activité.

### Niveau intermédiaire

Transactions + registre professionnel.

Ajoute les fiches professionnelles, secteurs, nomenclatures et une grande partie des analyses réseau.

### Niveau avancé

Transactions + professionnels + historiques de soldes.

Ajoute les analyses de détention et le pilotage des stocks.

### Plein potentiel

Transactions + registre professionnel + soldes particuliers + soldes professionnels + indicateurs monétaires quotidiens/annuels.

Les caches et indicateurs dérivés sont ensuite reconstruits par MLCFlux.

## 10. Principe de compatibilité future

Un futur adaptateur Cyclos, Kohinos ou autre devra produire le même modèle interne.

Les différences de provider doivent être absorbées dans `server/adapters/<provider>/` et ne doivent pas réapparaître dans les analytics ou le frontend.


## 11. Modèle géographique GEO001

La géographie possède désormais un modèle interne dédié :

- `geographic_areas` : référentiel des territoires, centroïdes
  et géométries ;
- `actor_geography` : géographie canonique résolue des acteurs.

Ces deux tables sont indépendantes du provider.

Les champs historiques `street`, `zip`, `city`, `latitude` et
`longitude` de `professional_enrichment` restent disponibles
pendant la transition, mais ne constituent plus l'architecture
géographique cible.

Le contrat détaillé est documenté dans
`docs/architecture/GEO001-GEOGRAPHY-MODEL.md`.
