# REL002 — sécurité des writers transactionnels

## Objet

REL002 ferme les contournements évidents du verrou commun autour du pipeline de
synchronisation actuellement retenu pour la baseline Neutral.

Le verrou reste un verrou advisory Linux/POSIX basé sur `flock`. Il est commun
à l'instance MLC active et couvre les opérations transactionnelles supportées :

- synchronisation quotidienne via `server.sync_transactions` ;
- réconciliation via `server.sync_transactions --reconcile-days ...` ;
- appels HTTP qui utilisent directement `run_sync()` ;
- backfill historique via `server.backfill_transactions --execute`.

`run_sync()` prend désormais lui-même le verrou. Le verrou transactionnel est
réentrant dans un même thread pour une même opération afin que le CLI puisse
conserver une garde extérieure : un conflit est alors détecté avant toute
écriture de `sync_state`, sans deadlock lors de l'appel imbriqué à `run_sync()`.

## Backups de backfill

Les sauvegardes pré-backfill sont créées avec des permissions privées :

- répertoire de sauvegarde : `0700` ;
- fichiers SQLite : `0600` dès leur création ;
- un backup incomplet est supprimé en cas d'échec de l'API SQLite backup.

Ces permissions protègent aussi `input001.db`, qui peut contenir des
identifiants et des faits financiers sensibles.

## Sémantique de réconciliation

La réconciliation est un upsert idempotent :

- transaction absente du legacy mais présente dans la source : insertion ;
- transaction déjà connue : mise à jour / upsert ;
- transaction absente du lot source : conservation dans le legacy.

L'absence dans la source **n'est pas interprétée comme une suppression ou une
annulation**. Une politique destructive nécessiterait une sémantique source
attestée (annulation, reversal, suppression, finalité) et des tests dédiés.

Le résultat de `run_sync()` expose donc `source_absence_policy="preserve"`.

## Writers alternatifs encore présents

Deux chemins historiques utilisent encore
`server.services.cyclos_transaction_sync` et ne font pas partie de la voie de
synchronisation supportée par REL002 :

- `server.build_mlc_db` ;
- `server.sync_mlc_instance`.

Ils restent utiles comme outils de caractérisation / migration de l'ancienne
architecture, notamment parce qu'ils embarquent encore une classification
legacy différente. Ils ne doivent pas être utilisés comme scheduler concurrent
de `server.sync_transactions` ou du backfill.

La suite du nettoyage doit choisir explicitement entre :

1. les raccorder au même verrou sans double acquisition ;
2. les rendre read-only / dry-run pour la baseline Neutral ;
3. les retirer lorsque leurs usages ont été absorbés par le pipeline neutre.

Il est préférable de prendre cette décision pendant l'allégement du legacy
plutôt que de consacrer ces outils comme une deuxième chaîne officielle.
