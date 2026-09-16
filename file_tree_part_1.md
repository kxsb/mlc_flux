mlc_flux/
├── app.py
│   └── Point d’entrée : crée l’application et expose aussi quelques routes,
│       notamment les pages, la version et les indicateurs monétaires.
│
└── server/
    ├── __init__.py
    │   └── Assemble Flask : configuration, initialisation des bases,
    │       enregistrement des routes et installation des protections.
    │
    ├── config.py
    │   └── Paramètres de l’application Flask, dont ceux des sessions.
    ├── runtime_config.py                              ★
    │   └── Résout les paramètres de connexion Cyclos depuis l’environnement.
    ├── mlc_context.py
    │   └── Détermine la monnaie de l’installation et les chemins de ses bases.
    ├── mlc_profiles.py
    │   └── Charge les profils propres aux monnaies.
    ├── runtime_lock.py                                ★
    │   └── Coordonne les verrous des traitements pour éviter leur concurrence.
    │
    ├── database.py
    │   └── Ouvre et initialise le SQLite utilisé par le backend historique.
    ├── control_db.py
    │   └── Gère la base de contrôle, notamment les comptes et l’administration.
    ├── contract_store.py                              ★
    │   └── Stocke les nouveaux contrats transactions/partenaires dans SQLite,
    │       avec leur état de synchronisation.
    │
    ├── contracts/                                     ★
    │   ├── transactions_v1.py
    │   │   └── Définit et valide le format commun des transactions entrantes.
    │   ├── partners_v1.py
    │   │   └── Définit et valide le format commun des profils partenaires.
    │   └── transactions_financial_core.py
    │       └── Transforme le contrat transactions en événements et effets
    │           financiers utilisables par le nouveau noyau.
    │
    ├── providers/                                     ★
    │   ├── cyclos_facts.py
    │   │   └── Extrait les faits natifs des réponses Cyclos.
    │   ├── cyclos_normalized.py
    │   │   └── Convertit ces faits en comptes et transactions normalisés.
    │   ├── cyclos_dataset.py
    │   │   └── Assemble un ensemble cohérent de données Cyclos pour INPUT001.
    │   │
    │   ├── comchain_facts.py
    │   │   └── Extrait les faits natifs ComChain sans leur ajouter
    │   │       de classification métier.
    │   ├── comchain_normalized.py
    │   │   └── Normalise comptes, transactions et observations de soldes
    │   │       vers les structures INPUT001.
    │   ├── comchain_postgres.py
    │   │   └── Lit les transactions natives ComChain dans PostgreSQL.
    │   ├── comchain_financial_core.py
    │   │   └── Convertit les faits ComChain en comptes, événements et effets.
    │   ├── comchain_financial_core_bridge.py
    │   │   └── Emballe ce résultat en lot publiable dans le Financial Core,
    │   │       avec couverture temporelle et empreinte du contenu.
    │   │
    │   ├── normalized_transactions_postgres.py
    │   │   └── Lit une relation PostgreSQL respectant le contrat transactions.
    │   └── odoo_partners_postgres.py
    │       └── Récupère les profils partenaires Odoo pour le contrat partenaires.
    │
    ├── input_contract/                                ★
    │   ├── schema.py
    │   │   └── Définit INPUT001 : comptes, transactions, métadonnées
    │   │       et capacités complémentaires comme les soldes.
    │   ├── writer.py
    │   │   └── Valide puis matérialise un ensemble de données dans ce schéma.
    │   ├── reader.py
    │   │   └── Fournit une interface de lecture indépendante de la source.
    │   ├── runtime.py
    │   │   └── Prépare la connexion à la base INPUT001 de l’installation.
    │   ├── shadow.py
    │   │   └── Produit un miroir INPUT001 à partir des données Cyclos,
    │   │       lorsque ce mode est activé.
    │   └── shadow_lifecycle.py
    │       └── Prépare le stockage du miroir et suit ses tentatives,
    │           réussites, erreurs et compatibilité de schéma.
    │
    ├── resolver/                                      ★
    │   ├── account_resolver.py
    │   │   └── Classe les comptes à partir de faits natifs et de règles
    │   │       explicites ; signale les cas inconnus ou contradictoires.
    │   ├── ruleset_loader.py
    │   │   └── Charge et valide les règles déclarées dans les fichiers JSON.
    │   └── account_report.py
    │       └── Compare en lecture seule les classifications du resolver
    │           avec celles de l’ancien système.
    │
    ├── financial_core/                                ★
    │   ├── schema.py
    │   │   └── Définit le noyau financier : comptes, événements, effets,
    │   │       acteurs, liens d’identité et observations financières.
    │   ├── writer.py
    │   │   └── Valide et écrit les données financières, puis leur publication.
    │   ├── publication.py
    │   │   └── Organise le passage d’un lot candidat validé
    │   │       à une publication utilisable.
    │   └── reader.py
    │       └── Lit une publication cohérente, sans mélanger plusieurs versions.
    │
    ├── sync_transactions.py
    │   └── Lance la synchronisation historique des transactions Cyclos.
    ├── backfill_transactions.py                       ★
    │   └── Point d’entrée dédié au rattrapage des transactions.
    ├── sync_mlc_instance.py
    │   └── Orchestre les étapes de synchronisation et les traitements
    │       associés pour l’installation.
    ├── sync_contracts.py                              ★
    │   └── Importe les contrats PostgreSQL vers le stockage SQLite Neutral.
    │
    ├── data_control_registry.py                       ★
    │   └── Catalogue les données nécessaires aux fonctionnalités,
    │       leurs consommateurs et leur état d’audit déclaré.
    │
    ├── auth_guards.py
    │   └── Contrôle l’accès aux routes selon l’authentification.
    ├── security_middleware.py
    │   └── Installe les protections transversales des requêtes HTTP.
    │
    ├── routes/
    │   ├── auth.py / admin_accounts.py / account_requests.py
    │   │   └── Connexion, administration des comptes et demandes d’accès.
    │   ├── health.py / status.py
    │   │   └── Exposent la santé du service et l’état des données/synchronisations.
    │   ├── current_mlc.py
    │   │   └── Expose la monnaie configurée pour l’installation.
    │   ├── transactions.py / sync.py
    │   │   └── Exposent les transactions et le déclenchement de leur sync.
    │   ├── legacy_api.py
    │   │   └── Regroupe les endpoints de l’API historique.
    │   ├── contract_analytics.py                      ★
    │   │   └── Expose l’aperçu Neutral et son API de synthèse.
    │   └── autres routes métier…
    │       └── Pilotage, professionnels, soldes, cartes, documentation.
    │
    ├── services/
    │   ├── cyclos_client.py / odoo_client.py
    │   │   └── Clients de connexion aux systèmes sources historiques.
    │   ├── cyclos_transaction_sync.py
    │   │   └── Réalise la collecte et l’écriture des transactions Cyclos.
    │   ├── transaction_semantics.py
    │   │   └── Porte les règles historiques d’interprétation des transactions.
    │   ├── contract_analytics.py                      ★
    │   │   └── Produit la synthèse utilisée par l’aperçu Neutral.
    │   └── autres services métier et caches…
    │       └── À détailler dans ta seconde phase sur les agrégats et calculs.
    │
    └── data/
        ├── mlc_profiles/*.json
        │   └── Configuration propre à chaque monnaie.
        ├── resolver_rulesets/gonette.json             ★
        │   └── Règles déclaratives de classification des comptes Gonette.
        ├── instances/
        │   └── Emplacement des données et fichiers propres aux installations.
        └── info_pages/
            └── Contenus de documentation affichés dans l’application.
