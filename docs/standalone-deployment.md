# Déploiement standalone — procédure de référence

## Objet

Cette note décrit le premier déploiement réellement validé de MLCFlux Neutral.

Elle documente l'état actuel du processus sysadmin. Ce n'est pas encore
l'installateur final : les étapes encore manuelles constituent le cahier des
charges du futur bootstrap / wizard.

## Déploiement de référence validé

- branche : `mlcflux_neutral_dev`
- application : `/opt/mlcflux-neutral/app`
- environnement Python : `/opt/mlcflux-neutral/venv`
- service : `mlcflux-neutral-dev.service`
- serveur applicatif : Gunicorn
- écoute applicative : `127.0.0.1:8011`
- reverse proxy : Nginx
- domaine de test : `dev.mlcflux.org`
- TLS : Let's Encrypt / Certbot
- profil utilisé pour cette validation : `gonette`
- accès dev supplémentaire : Basic Auth Nginx

La chaîne suivante a été validée dans un navigateur :

    HTTPS
    → Basic Auth Nginx
    → login MLCFlux
    → Gunicorn
    → Flask
    → profil standalone
    → base SQLite de l'instance
    → interface navigable

## 1. Code et environnement Python

Le checkout applicatif et le venv sont séparés :

    /opt/mlcflux-neutral/app
    /opt/mlcflux-neutral/venv

Le service est lancé depuis la racine du dépôt afin que `app:app`,
les templates, les fichiers statiques et les modules `server.*`
soient résolus correctement.

## 2. Configuration runtime

La configuration actuelle est fournie par un `.env` local non versionné,
protégé en `0600`.

Pour un déploiement derrière HTTPS, les paramètres web utilisés lors de
DEVDEPLOY001 étaient :

    HOST=127.0.0.1
    FLASK_ENV=production
    SESSION_COOKIE_SECURE=1
    SESSION_COOKIE_SAMESITE=Lax

L'installation standalone doit définir une seule MLC active via
`MLCFLUX_DEFAULT_MLC_ID`.

Les identifiants fournisseurs, tokens et secrets ne doivent jamais être
versionnés.

### Dette INSTALL001

L'emplacement actuel du `.env` dans le checkout est transitoire.

Cible souhaitée :

    /etc/mlcflux/mlcflux.env

avec permissions strictes et chargement par `EnvironmentFile=` dans systemd.

## 3. Données runtime

Les données d'instance sont stockées sous :

    server/data/instances/<mlc_id>/

Les bases, mappings et autres données runtime ne sont pas versionnés.

Les sauvegardes opérationnelles doivent être placées hors du checkout, par
exemple :

    /opt/mlcflux-neutral/backups/

## 4. Premier administrateur

Une base `control.db` neuve ne contient aucun utilisateur.

Le premier démarrage opérationnel nécessite donc :

1. la création d'un utilisateur avec `global_role=admin` ;
2. l'activation du compte ;
3. l'attribution du rôle `manager` sur la MLC standalone active.

Les fonctions actuellement utilisées sont :

    server.control_db.create_or_update_user()
    server.control_db.grant_mlc_access()

Le mot de passe doit être saisi de façon interactive et ne jamais apparaître
dans une commande shell ou un fichier temporaire.

### Dette INSTALL001

La création du premier administrateur devra être intégrée au futur bootstrap.

## 5. Service systemd

Le déploiement de référence utilise le service :

    mlcflux-neutral-dev.service

Principes validés :

    WorkingDirectory=/opt/mlcflux-neutral/app
    EnvironmentFile=/opt/mlcflux-neutral/app/.env
    Environment=PYTHONPATH=/opt/mlcflux-neutral/app
    Gunicorn → 127.0.0.1:8011
    Restart=on-failure

Le service est activé au démarrage du VPS.

Validation minimale :

    systemctl status mlcflux-neutral-dev.service
    ss -ltnp | grep ':8011'
    curl http://127.0.0.1:8011/api/version

Gunicorn ne doit pas écouter sur une interface publique.

Le socket de contrôle Gunicorn actuellement créé dans le checkout
(`gunicorn.ctl`) est acceptable pour DEVDEPLOY001 mais devra être déplacé
vers un répertoire runtime adapté lors de la normalisation de l'installation.

## 6. Nginx et TLS

Nginx expose le domaine public et relaie vers :

    http://127.0.0.1:8011

Le déploiement de référence utilise un certificat Let's Encrypt valide pour :

    dev.mlcflux.org

La Basic Auth Nginx utilisée sur cet environnement est une protection
supplémentaire spécifique au serveur de développement. Elle ne fait pas
partie du fonctionnement standard attendu pour une installation MLCFlux.

Avant toute activation ou modification de configuration Nginx :

    nginx -t

La chaîne validée est :

    Internet
    → HTTPS / Let's Encrypt
    → Nginx
    → Basic Auth de développement
    → 127.0.0.1:8011
    → Gunicorn
    → MLCFlux

## 7. Vérifications fonctionnelles validées

DEVDEPLOY001 a validé :

- le démarrage du service systemd ;
- l'écoute locale de Gunicorn ;
- la réponse HTTP de Flask ;
- l'exposition HTTPS ;
- le certificat TLS ;
- la Basic Auth de développement ;
- le login applicatif MLCFlux ;
- la persistance de session ;
- les droits administrateur ;
- le chargement du profil Gonette ;
- la lecture du snapshot Gonette ;
- la navigation réelle dans l'interface.

L'interface est fonctionnelle et navigable.

Des incohérences fonctionnelles ou sémantiques restent possibles dans certaines
vues et certains indicateurs. Elles ne sont pas considérées comme bloquantes
pour la validation du déploiement lui-même.

Aucune synchronisation réelle Cyclos/Odoo n'a été déclenchée pendant cette
validation.

## 8. Points volontairement différés

DEVDEPLOY001 ne valide pas encore :

- l'installation automatisée ;
- l'onboarding d'une troisième MLC ;
- le contrat commun Cyclos / ComChain ;
- la reconstruction complète d'une base ;
- une synchronisation réelle sur cette instance ;
- le dry-run totalement sans effets de bord ;
- la cohérence finale de tous les indicateurs ;
- la simplification finale des droits hérités du multi ;
- le déplacement définitif des secrets hors checkout ;
- la normalisation du répertoire runtime Gunicorn.

Quelques dettes techniques identifiées restent également hors périmètre :

- certains anciens chemins de scripts de synchronisation pointent encore vers
  des installations historiques ;
- le modèle de droits conserve encore des abstractions issues du multi-instance ;
- certains comportements restent spécifiques aux profils Gonette / Graine ;
- le contrat d'entrée provider n'est pas encore stabilisé.

## 9. Conclusion DEVDEPLOY001

DEVDEPLOY001 démontre qu'une instance MLCFlux Neutral peut être déployée
manuellement sur un VPS dédié avec une chaîne d'exploitation complète :

    code
    → configuration
    → données
    → compte administrateur
    → systemd
    → Gunicorn
    → Nginx
    → TLS
    → authentification
    → interface MLCFlux

Cette procédure constitue la première installation sysadmin de référence.

Elle doit maintenant servir de base au futur processus automatisé
d'installation et de configuration.

## Étape suivante

Priorité suivante :

    INPUT001
    → PROVIDER001
    → adaptation Cyclos / ComChain
    → INSTALL001

L'objectif est maintenant de stabiliser le contrat d'entrée avant de construire
un installateur ou un wizard qui dépendrait trop tôt de l'implémentation Cyclos
actuelle.
