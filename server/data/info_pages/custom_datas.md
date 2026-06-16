# datas

types et sources des données
> Données transactionnelles
id transaction Cyclos > liste transactions > Cyclos
numéro de transaction > liste transactions > Cyclos
montant > liste transactions > Cyclos
date > liste transactions > Cyclos
heure > liste transactions > Cyclos
date complète / timestamp > liste transactions > Cyclos
acteur émetteur > liste transactions > Cyclos
acteur récepteur > liste transactions > Cyclos
compte émetteur > liste transactions > Cyclos
compte récepteur > liste transactions > Cyclos
groupe de l’émetteur > liste transactions > Cyclos
groupe du récepteur > liste transactions > Cyclos
auteur / réalisé par > liste transactions > Cyclos
reçu par > liste transactions > Cyclos
type de paiement > liste transactions > Cyclos
description de transaction > liste transactions > Cyclos
source paiement euro > liste transactions > Cyclos
____
> Données acteurs / comptes Cyclos
id acteur > acteurs / comptes > Cyclos
id utilisateur > acteurs / comptes > Cyclos
nom affiché acteur > acteurs / comptes > Cyclos
libellé compte > comptes > Cyclos
type de compte > comptes > Cyclos
groupe Cyclos > acteurs / groupes > Cyclos
statut du compte > acteurs / comptes > Cyclos
solde numérique > compte / balance > Cyclos
date de création du compte > acteurs / comptes > Cyclos
date de dernière activité > transactions / compte > Cyclos
____
> Données professionnelles enrichies
secteur d’activité des pros > fiche partenaire / contact > Odoo
adresse des pros > fiche partenaire / contact > Odoo
code postal des pros > fiche partenaire / contact > Odoo
ville des pros > fiche partenaire / contact > Odoo
nom structure > fiche partenaire / contact > Odoo
statut / informations d’adhésion éventuelles > fiche partenaire / contact > Odoo
coordonnées géographiques éventuelles > enrichissement Odoo ou géocodage
____
> logique de fallback :
code postal prioritaire > Odoo
code postal secondaire > Cyclos
code postal final > Odoo si disponible, sinon Cyclos
____
> Données comptables / masse monétaire
lignes comptables > account.move.line > Odoo
comptes comptables > plan comptable > Odoo
date d’écriture > account.move.line > Odoo
débit > account.move.line > Odoo
crédit > account.move.line > Odoo
solde comptable cumulé > account.move.line / read_group > Odoo
circulation numérique > calcul depuis comptes comptables > Odoo
circulation papier > calcul depuis comptes comptables > Odoo
masse monétaire totale > calcul depuis comptes comptables > Odoo
fonds de garantie numérique > calcul depuis comptes comptables > Odoo
fonds de garantie papier > calcul depuis comptes comptables > Odoo
écart circulation / garantie > calcul MLCFlux depuis Odoo
année d’indicateur > stock comptable au 31/12 > Odoo

stock à fin d’année > lignes comptables cumulées jusqu’au 31/12 > Odoo
flux de l’année > lignes comptables entre 01/01 et 31/12 > Odoo
____
> Données de classification MLCFlux
liste des prénoms de pseudonymisation > prenoms.csv > fichier local
mapping pseudonyme stable > user_mapping.json > fichier runtime local
classification comptes particuliers de dispositif > device_private_actor_registry.json > fichier local
identification UD_* > actor.id + registre local > Cyclos + fichier local
identification U_* > actor.id / groupe Cyclos + anonymiseur > Cyclos + MLCFlux
identification P_* > acteur professionnel Cyclos > Cyclos + MLCFlux
identification T_* > comptes système Cyclos > Cyclos + MLCFlux
identification P0000 / P9999 > libellés / IDs comptes opérateurs > Cyclos + règles MLCFlux
____
> Données territoriales et cartographiques
adresse > Odoo ou Cyclos
code postal > Odoo ou Cyclos
ville > Odoo ou Cyclos
coordonnées latitude / longitude > Odoo, géocodage ou fichier enrichi
territoire > code postal / commune / découpage local > MLCFlux
commune > adresse ou code postal > BAN / INSEE / enrichissement local
département > code postal / commune > INSEE / table locale
région > commune / département > INSEE / table locale
____
> Données de configuration technique
URL Cyclos > .env > configuration serveur
token API Cyclos > .env > configuration serveur
URL Odoo > .env > configuration serveur
base Odoo > .env > configuration serveur
identifiant Odoo > .env > configuration serveur
mot de passe / token Odoo > .env > configuration serveur
chemin base SQLite > configuration serveur > MLCFlux
token sync > .env > configuration serveur
token admin > .env > configuration serveur
port application > service systemd / env > serveur
domaine public > NGINX / DNS > infrastructure
