# PROVIDER002 — ComChain evidence

## Statut

Ce document recense les faits techniques vérifiés dans les sources
ComChain utilisées pour concevoir le provider INPUT001.

Il ne définit pas de classification métier MLCFlux.

## Sources vérifiées

Sources principales :

- `com-chain/currency`, contrat `contracts/currency.sol`
- `com-chain/pyc3l`
- `com-chain/pyc3l-cli`
- intégration ComChain existante de Lokavaluto, utilisée uniquement
  comme source complémentaire sur la forme de stockage.

## Identité des comptes

L'identité financière native est l'adresse ComChain.

Le contrat utilise les adresses comme clés pour notamment :

- `accountType`
- `accountStatus`
- `accountAlreadyUsed`
- `balanceEL`
- `balanceCM`
- `limitCredit`
- `limitDebit`
- `requestReplacementFrom`
- `newAddress`

Le provider INPUT001 applique une canonicalisation spécifique aux
adresses Ethereum reconnues :

- suppression du préfixe de présentation `0x`
- représentation des 40 chiffres hexadécimaux en minuscules

Cette règle est propre à l'identité technique ComChain/Ethereum et non
au Core INPUT001.

Elle est nécessaire notamment parce que les différentes couches
ComChain n'exposent pas systématiquement le même préfixe de
présentation.

Les identifiants qui ne correspondent pas à une adresse Ethereum
restent opaques et sont conservés tels quels.

Cette canonicalisation ne réalise :

- aucun rapprochement Odoo
- aucune classification P/U/T/X

## Types natifs de compte

Le contrat documente :

- `0` : Personal
- `1` : Business
- `2` : Super Admin
- `3` : Pledge Admin
- `4` : Property Admin

Ces valeurs constituent des faits natifs ComChain.

Elles ne doivent pas être converties en catégories métier MLCFlux par
le provider financier.

## Etat des comptes

Le contrat expose `accountStatus[address]`.

Il expose également `isActive(address)`.

Ces deux notions ne doivent pas être confondues.

`isActive()` incorpore une logique supplémentaire, notamment :

- `automaticUnlock`
- `accountAlreadyUsed`
- la logique de remplacement

Par conséquent :

- `accountStatus` est un état natif directement stocké ;
- `isActive()` est un état effectif calculé par le contrat.

INPUT001 ne doit pas projeter silencieusement l'un comme s'il était
l'autre.

## Soldes

Le contrat maintient deux composantes :

- `balanceEL` : balance in coins
- `balanceCM` : balance in mutual credit

La fonction native `balanceOf(address)` renvoie :

`balanceEL[address] + balanceCM[address]`

Cette structure confirme l'intérêt du champ
`balances.balance_component` d'INPUT001.

Une future projection peut notamment conserver séparément :

- `balanceEL`
- `balanceCM`
- éventuellement le total calculé

sans perdre les composantes natives.

## Remplacement de compte

Le contrat possède notamment :

- `requestReplacementFrom`
- `newAddress`

Lorsqu'un remplacement est accepté, le contrat :

1. transfère le type du compte ;
2. transfère les soldes `balanceEL` et `balanceCM` ;
3. remet les anciens soldes à zéro ;
4. transfère les limites de crédit et débit ;
5. remet les anciennes limites à zéro ;
6. transfère différentes autorisations ;
7. renseigne `newAddress[old] = new` ;
8. positionne `accountStatus[old] = false` ;
9. émet `AccountReplaced(time, oldAdd, newAdd, accstatus)`.

Cette mécanique justifie directement la relation optionnelle
`account_replacements` d'INPUT001.

Elle interdit en revanche d'interpréter deux adresses remplacées comme
un seul `account_id` : elles restent deux identités financières natives
distinctes reliées par un événement de remplacement.

## Nantissement

Le contrat possède un agrégat `amountPledged`.

La fonction `pledge(address, value)` :

- modifie cet agrégat ;
- modifie la position du compte cible ;
- émet `Pledge(time, to, received)`.

Le nantissement est donc une opération financière native explicite.

La correspondance exacte avec les notions métier de
conversion/reconversion reste à traiter séparément et ne doit pas être
déduite uniquement du nom de fonction.

## Transactions pyc3l-cli

Le stockage transactionnel observé contient notamment :

- hash
- block
- received_at
- caller
- contract
- contract_abi
- type
- sender
- receiver
- amount
- fn
- fn_abi
- status

La devise est portée par le contexte du store et pas nécessairement par
chaque ligne.

## Limites actuelles

Les points suivants ne sont pas encore considérés comme stabilisés dans
le provider :

- moyen exact d'extraire historiquement tous les changements
  `accountStatus` ;
- forme exacte des événements renvoyés par les API disponibles ;
- stratégie de snapshots des soldes ;
- distinction opérationnelle conversion / reconversion pour toutes les
  installations ;
- sémantique d'éventuels comptes techniques configurés hors contrat ;
- comportement de versions de contrats ComChain différentes de celle
  étudiée.

Ces sujets doivent rester optionnels tant que la source disponible ne
permet pas de les attester.

## Conséquence pour INPUT001

Les relations optionnelles existantes restent adaptées :

- `account_states`
- `balances`
- `account_replacements`

Aucune modification du core INPUT001 n'est nécessaire à ce stade.

Le prochain provider ComChain peut les alimenter lorsqu'une source
native suffisante est disponible, sans dépendre d'Odoo ni d'une
classification métier MLCFlux.

## Exactitude des lectures de solde

`pyc3l` expose les fonctions natives ComChain au travers de son ABI.

Les valeurs typées `Amount`, dont les lectures de `balanceEL`,
`balanceCM` et du solde global, sont converties par la couche haut
niveau avec une division par `100.0`.

Cette représentation est adaptée à l'affichage mais ne constitue pas
une source exacte pour INPUT001, qui stocke les montants en entier dans
l'unité minimale.

Le provider doit donc obtenir les valeurs entières natives du contrat
avant cette conversion lorsqu'il alimente `balances.amount_minor`.

Les composantes sont conservées séparément :

- `balanceEL`
- `balanceCM`

Le total peut être dérivé mais ne remplace pas les composantes natives.

## Snapshot courant et historique

Une lecture de l'état courant permet d'attester notamment :

- `accountType`
- `accountStatus`
- `balanceEL`
- `balanceCM`
- `newAddress`

Elle ne permet pas à elle seule de connaître :

- la date de début d'un `accountStatus`
- la date d'un changement de type
- l'instant effectif d'un remplacement déjà observé

Par conséquent un simple snapshot courant peut alimenter :

- `accounts`
- `balances`

mais ne suffit pas pour fabriquer :

- `account_states`
- `account_replacements`

Ces relations historiques nécessitent une source temporelle native,
par exemple les événements du contrat ou un historique équivalent.
