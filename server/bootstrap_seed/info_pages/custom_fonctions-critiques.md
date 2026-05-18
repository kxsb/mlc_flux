# MLCFlux — Inventaire des fonctions clés

|MLCFlux — Inventaire des fonctions clés pour le rendez-vous technique| | | | | |
|---|---|---|---|---|---|
|| | | | | |
| | | | | | |
|Domaine|Fichier|Fonction clé|Ce qu’elle fait techniquement|Explication humaine|Priorité|
| 1. Connexion et extraction Cyclos| | | | | |
|API Cyclos|server/services/cyclos_client.py|build_basic_auth(...)|Construit l’en-tête Basic Auth à partir des identifiants de configuration.|Prépare la manière propre de s’identifier auprès de Cyclos.|Très haute|
|API Cyclos|server/services/cyclos_client.py|create_session_token(...)|Ouvre une session Cyclos et récupère le jeton de session utilisé ensuite pour les appels API.|MLCFlux ne lance pas des requêtes anonymes : il établit d’abord une session autorisée.|Très haute|
|API Cyclos|server/services/cyclos_client.py|_is_date_only(...)|Détecte si une date est fournie au format jour seul, sans heure.|Permet de comprendre que « 2026-05-15 » signifie un jour civil, pas un instant ambigu.|Haute|
|API Cyclos|server/services/cyclos_client.py|_parse_date(...)|Normalise les dates reçues, en tenant compte de la logique Europe/Paris avant conversion pour l’API.|Évite de perdre ou de décaler des transactions à cause des fuseaux horaires ou des changements d’heure.|Très haute|
|API Cyclos|server/services/cyclos_client.py|get_transactions(...)|Appelle l’endpoint /transactions, applique datePeriod, pagine toutes les réponses et retourne le lot complet.|C’est la fonction qui va réellement chercher les transactions Cyclos.|Critique|
|2. Synchronisation des transactions et état d’import| | | | | |
|Sync transactions|server/sync_transactions.py|insert_transactions(...)|Écrit les transactions anonymisées en SQLite avec logique d’upsert.|Insère les données utiles sans dupliquer les mêmes opérations lors d’un resync.|Critique|
|Sync transactions|server/sync_transactions.py|run_sync(...)|Orchestre une synchronisation : récupération Cyclos, anonymisation, insertion en base, résumé d’exécution.|C’est le chef d’orchestre de l’import transactionnel.|Critique|
|Suivi sync|server/sync_transactions.py / couche base|save_sync_state(...)|Mémorise l’état d’une synchronisation : dernière exécution, statut, message.|Permet de savoir si une synchronisation est passée correctement.|Haute|
|3. Anonymisation et typage des acteurs| | | | | |
|Anonymisation|server/utils/anonymizer.py|extract_private_actor_key(...)|Construit la clé stable d’un particulier, avec priorité à actor.id et repli si nécessaire.|C’est ce qui évite de regrouper artificiellement plusieurs particuliers sous un même faux nom.|Critique|
|Anonymisation|server/utils/anonymizer.py|get_or_create_private_pseudo(...)|Retourne un pseudonyme déjà existant ou en crée un nouveau dans le mapping persistant.|Le même particulier conserve le même pseudonyme au fil des imports.|Très haute|
|Anonymisation|server/utils/anonymizer.py|load_device_private_actor_ids(...)|Charge le registre des comptes particuliers de dispositif.|Permet d’identifier les comptes temporaires ou liés à un dispositif spécifique.|Haute|
|Anonymisation|server/utils/anonymizer.py|is_device_private_actor(...)|Teste si un acteur appartient au registre des particuliers de dispositif.|Décide si un compte particulier doit devenir U_* ou UD_*.|Très haute|
|Anonymisation|server/utils/anonymizer.py|_extract_professional_code(...)|Récupère le code professionnel Pxxxx dans le libellé de l’acteur.|Retrouve l’identifiant métier stable du professionnel malgré les variations d’affichage.|Haute|
|Anonymisation|server/utils/anonymizer.py|is_professional_label(...)|Détermine si un libellé correspond à un professionnel.|Permet de reconnaître les pros avant la ventilation analytique.|Haute|
|Anonymisation|server/utils/anonymizer.py|clean_professional_label(...)|Produit un libellé professionnel canonique du type Pxxxx - Nom.|Évite qu’un même pro apparaisse sous plusieurs écritures différentes.|Haute|
|Anonymisation|server/utils/anonymizer.py|_technical_actor_label(...)|Mappe les acteurs système Cyclos vers des labels lisibles comme T_Émission ou T_Conversion.|Distingue les comptes techniques des vrais usagers et professionnels.|Critique|
|Anonymisation|server/utils/anonymizer.py|anonymize_actor_label(...)|Applique l’ordre de reconnaissance des acteurs : technique, professionnel, particulier, cas résiduels.|C’est la porte d’entrée du typage des acteurs.|Critique|
|Anonymisation|server/utils/anonymizer.py|anonymize_transaction(...)|Transforme une transaction Cyclos en transaction anonymisée prête à être stockée.|Chaque transaction est sécurisée et normalisée avant d’entrer dans la base analytique.|Critique|
|4. Lecture des transactions et classification analytique| | | | | |
|Analytics|server/analytics.py|fetch_transactions(...)|Lit les transactions anonymisées depuis SQLite pour une période donnée.|L’interface analytique repart de la base locale, pas de Cyclos en direct.|Très haute|
|Analytics|server/analytics.py|_actor_flow_family(label)|Ramène un libellé détaillé à une famille analytique P, U ou T.|Convertit les labels lisibles en langage d’analyse commun.|Critique|
|Analytics|server/analytics.py|_is_operator_account_label(...)|Détecte les comptes opérateurs P0000 et P9999.|Évite de traiter les comptes opérateurs comme de simples professionnels ordinaires.|Critique|
|Analytics|server/analytics.py|_operator_account_code(...)|Extrait le code d’un compte opérateur reconnu.|Permet de distinguer proprement P0000 et P9999 dans les analyses techniques.|Haute|
|Analytics|server/analytics.py|_classify_analytical_transaction(row)|Classe chaque transaction dans son compartiment analytique : activité économique, alimentation, sortie, opérations techniques, etc.|C’est le cœur de la doctrine de ventilation de MLCFlux.|Critique|
|Analytics|server/analytics.py|_operations_family_key(...)|Regroupe les opérations hors activité économique centrale en grandes familles.|Sert à lire les mouvements associatifs ou techniques sans les confondre avec les paiements courants.|Très haute|
|Analytics|server/analytics.py|_operator_operation_profile(...)|Décompose les opérations impliquant les comptes opérateurs.|Permet de dire qui va vers P0000/P9999 et dans quel sens.|Haute|
|Analytics|server/analytics.py|_operations_functional_flow_key(...)|Produit des catégories fonctionnelles lisibles : professionnel → compte opérateur, opérateur → professionnel, particulier → technique, etc.|Transforme des flux techniques en catégories compréhensibles pour les non-développeurs.|Très haute|
|5. Agrégats, indicateurs et graphiques| | | | | |
|Analytics|server/analytics.py|compute_global_stats(...)|Calcule les KPI de synthèse sur une période ; ne renvoie plus les transactions détaillées par défaut.|Produit les grands chiffres de la vue statistiques sans surcharger inutilement le réseau.|Critique|
|Analytics|server/analytics.py|compute_stats_charts(...)|Construit les séries temporelles et distributions utilisées dans les graphiques.|Prépare les données visuelles de la page statistiques.|Critique|
|6. Fonctions / briques complémentaires à citer si le sujet élargit| | | | | |
|Soldes Cyclos|services / scripts dédiés de soldes|fonctions de lecture de /accounts/{accountType}/user-balances|Récupèrent les soldes des comptes par type de compte, notamment compteparticulier et comptepro.|Pour les soldes, MLCFlux interroge une API Cyclos spécifique, différente des transactions.|Haute|
|Pont actor ↔ user|scripts de reconstruction / données actor_user_links|fonctions de rapprochement actor.id ↔ user.id|Relient les identifiants visibles dans les transactions aux identifiants utiles pour les routes utilisateurs et soldes.|C’est le pont entre les flux transactionnels et les informations de compte.|Haute|
|Odoo monétaire|server/services/odoo_monetary_indicators.py|fonctions de calcul des indicateurs de masse monétaire et de garanties|Interrogent la comptabilité Odoo et produisent des grandeurs de stock à fin d’année.|Cyclos sert aux usages numériques ; Odoo sert aux grandeurs comptables et aux garanties.|Moyenne|
