from __future__ import annotations

from collections import Counter
from dataclasses import dataclass


STATUS_META = {
    "available": {
        "label": "Donnée récupérée",
        "short_label": "Récupérée",
        "color": "green",
        "rank": 5,
    },
    "processing": {
        "label": "Donnée existante, traitement incomplet",
        "short_label": "Traitement incomplet",
        "color": "yellow",
        "rank": 4,
    },
    "missing": {
        "label": "Donnée non récupérée",
        "short_label": "Non récupérée",
        "color": "orange",
        "rank": 3,
    },
    "unavailable": {
        "label": "Donnée non récupérable",
        "short_label": "Non récupérable",
        "color": "red",
        "rank": 2,
    },
    "unaudited": {
        "label": "Donnée non auditée",
        "short_label": "Non auditée",
        "color": "gray",
        "rank": 1,
    },
}


@dataclass(frozen=True)
class DataRequirement:
    key: str
    label: str
    domain: str
    source: str
    consumers: tuple[str, ...]
    status: str = "unaudited"
    note: str = ""

    @property
    def usage_count(self) -> int:
        return len(self.consumers)

    def as_dict(self) -> dict[str, object]:
        status_meta = STATUS_META[self.status]
        return {
            "key": self.key,
            "label": self.label,
            "domain": self.domain,
            "source": self.source,
            "consumers": self.consumers,
            "usage_count": self.usage_count,
            "status": self.status,
            "status_label": status_meta["label"],
            "status_short_label": status_meta["short_label"],
            "status_color": status_meta["color"],
            "note": self.note,
        }


# DATACTRL001
#
# Ce registre décrit les DONNÉES DONT MLCFlux A BESOIN, pas les colonnes
# techniques propres à Odoo, ComChain ou Cyclos. Les adaptateurs sources
# peuvent changer sans modifier les clés ci-dessous.
#
# Les états sont volontairement prudents :
# - available : la chaîne Neutral sait déjà récupérer la donnée ;
# - processing : la donnée est identifiée dans la source, mais une couche de
#   jointure / normalisation / publication reste à consolider ;
# - missing : le besoin est connu mais aucun chemin de collecte Neutral n'est
#   encore établi ;
# - unavailable : uniquement après audit démontrant l'indisponibilité ;
# - unaudited : pas encore vérifié.
DATA_REQUIREMENTS: tuple[DataRequirement, ...] = (
    DataRequirement(
        key="transaction.amount",
        label="Montant de la transaction",
        domain="Transactions",
        source="CONTRACT001 / ComChain PostgreSQL",
        status="available",
        consumers=(
            "Volume d’activité économique",
            "Montant moyen des transactions",
            "Séries temporelles de volumes",
            "Classement des professionnels",
            "Analyse interprofessionnelle B2B",
            "Analyse particuliers → professionnels",
            "Analyse professionnels → particuliers",
            "Analyse sectorielle",
            "Analyse territoriale",
            "Graphe du réseau professionnel",
            "Fiches professionnels",
            "Taux de réutilisation",
            "Flux d’alimentation du circuit",
            "Flux de sortie / reconversion",
            "Opérations associatives / techniques",
        ),
        note="Champ amount de TRANSACTIONS001, projeté vers le Financial Core.",
    ),
    DataRequirement(
        key="transaction.received_at",
        label="Date et heure de la transaction",
        domain="Transactions",
        source="CONTRACT001 / ComChain PostgreSQL",
        status="available",
        consumers=(
            "Sélecteur de période",
            "Bornes de période disponibles",
            "Activité quotidienne",
            "Activité hebdomadaire",
            "Activité mensuelle",
            "Répartition horaire",
            "Répartition par jour de semaine",
            "Cumul d’activité",
            "Historique des professionnels",
            "Réseau professionnel par période",
            "Analyses sectorielles par période",
            "Analyses territoriales par période",
        ),
        note="Champ received_at normalisé par TRANSACTIONS001.",
    ),
    DataRequirement(
        key="transaction.sender_partner_id",
        label="Partenaire émetteur de la transaction",
        domain="Transactions / identité",
        source="CONTRACT001 / ComChain PostgreSQL",
        status="available",
        consumers=(
            "Identification des acteurs émetteurs",
            "Classification des flux économiques",
            "Analyse interprofessionnelle B2B",
            "Classement des professionnels",
            "Fiches professionnels",
            "Graphe du réseau professionnel",
            "Analyse sectorielle des émissions",
            "Analyse territoriale des émissions",
            "Taux de réutilisation",
            "Lien transactions ↔ profils partenaires",
        ),
        note="Identifiant administratif exposé directement par TRANSACTIONS001.",
    ),
    DataRequirement(
        key="transaction.receiver_partner_id",
        label="Partenaire destinataire de la transaction",
        domain="Transactions / identité",
        source="CONTRACT001 / ComChain PostgreSQL",
        status="available",
        consumers=(
            "Identification des acteurs destinataires",
            "Classification des flux économiques",
            "Analyse particuliers → professionnels",
            "Analyse interprofessionnelle B2B",
            "Classement des professionnels",
            "Fiches professionnels",
            "Graphe du réseau professionnel",
            "Analyse sectorielle des réceptions",
            "Analyse territoriale des réceptions",
            "Lien transactions ↔ profils partenaires",
        ),
        note="Identifiant administratif exposé directement par TRANSACTIONS001.",
    ),
    DataRequirement(
        key="partner.actor_family",
        label="Type d’acteur analytique",
        domain="Acteurs",
        source="Odoo + règles Neutral à consolider",
        status="processing",
        consumers=(
            "Particulier / professionnel",
            "Activité économique U↔P",
            "Analyse B2B",
            "Analyse B2C",
            "Professionnels → particuliers",
            "Transferts entre particuliers",
            "Nombre d’acteurs actifs",
            "Classement des professionnels",
            "Réseau professionnel",
            "Filtres des opérations techniques",
        ),
        note="PARTNERS002 expose déjà is_company/member_type, mais la règle neutre de famille analytique reste à figer.",
    ),
    DataRequirement(
        key="transaction.type",
        label="Famille native de l’opération",
        domain="Transactions / sémantique",
        source="CONTRACT001 / ComChain PostgreSQL",
        status="available",
        consumers=(
            "Classification des transactions",
            "Paiements économiques",
            "Alimentations du circuit",
            "Sorties / reconversions",
            "Opérations techniques",
            "Pilotage monétaire",
            "Audit des opérations atypiques",
            "Contrôle de cohérence des flux",
        ),
        note="Champ type conservé sans surinterprétation métier dans TRANSACTIONS001.",
    ),
    DataRequirement(
        key="transaction.fn_abi",
        label="Sous-type / code natif de l’opération",
        domain="Transactions / sémantique",
        source="CONTRACT001 / ComChain PostgreSQL",
        status="available",
        consumers=(
            "Classification fine des transactions",
            "Détection des opérations de nantissement",
            "Détection des opérations pour compte de tiers",
            "Pilotage monétaire",
            "Audit des opérations atypiques",
            "Future nomenclature commune des opérations",
        ),
        note="Conservé comme information analytique native ; la nomenclature métier reste à construire depuis les cas observés.",
    ),
    DataRequirement(
        key="partner.name",
        label="Nom du partenaire / professionnel",
        domain="Profils partenaires",
        source="PARTNERS002 / Odoo PostgreSQL",
        status="processing",
        consumers=(
            "Liste des professionnels",
            "Fiches professionnels",
            "Recherche de professionnels",
            "Libellés du graphe réseau",
            "Libellés cartographiques",
            "Contrôle manuel des correspondances",
        ),
        note="La source Odoo est identifiée et l’adaptateur PARTNERS002 existe ; publication vers les lectures applicatives à consolider.",
    ),
    DataRequirement(
        key="partner.industry",
        label="Secteur d’activité interne",
        domain="Profils partenaires",
        source="PARTNERS002 / Odoo PostgreSQL",
        status="processing",
        consumers=(
            "Analyse sectorielle",
            "Volumes reçus par secteur",
            "Volumes émis par secteur",
            "Taux de réutilisation par secteur",
            "Fiches professionnels",
            "Recherche / filtrage des professionnels",
        ),
        note="industry_code et industry_name sont déjà prévus dans PARTNERS002.",
    ),
    DataRequirement(
        key="partner.zip",
        label="Code postal du partenaire",
        domain="Territoires",
        source="PARTNERS002 / Odoo PostgreSQL",
        status="processing",
        consumers=(
            "Analyse territoriale",
            "Volumes reçus par territoire",
            "Volumes émis par territoire",
            "Couverture territoriale des professionnels",
            "Fiches professionnels",
            "Recherche / filtrage des professionnels",
        ),
        note="Champ zip présent dans PARTNERS002 ; branchement Neutral vers les analyses existantes à faire.",
    ),
    DataRequirement(
        key="partner.coordinates",
        label="Latitude / longitude du partenaire",
        domain="Territoires",
        source="PARTNERS002 / Odoo PostgreSQL",
        status="processing",
        consumers=(
            "Carte des professionnels",
            "Relief d’activité cartographique",
            "Clusters géographiques",
            "Contrôle de couverture géographique",
            "Fiches professionnels",
        ),
        note="Latitude et longitude sont prévues dans PARTNERS002 ; qualité et couverture restent à auditer.",
    ),
    DataRequirement(
        key="partner.city",
        label="Ville du partenaire",
        domain="Territoires",
        source="PARTNERS002 / Odoo PostgreSQL",
        status="processing",
        consumers=(
            "Analyse territoriale",
            "Libellés des territoires",
            "Carte des professionnels",
            "Fiches professionnels",
            "Recherche de professionnels",
        ),
        note="Champ city présent dans PARTNERS002.",
    ),
    DataRequirement(
        key="partner.member_type",
        label="Type d’adhésion / catégorie de membre",
        domain="Profils partenaires",
        source="PARTNERS002 / Odoo PostgreSQL",
        status="processing",
        consumers=(
            "Qualification des acteurs",
            "Annuaire des professionnels",
            "Filtres d’analyse par population",
            "Contrôle des acteurs économiques",
            "Futurs indicateurs d’adhésion",
        ),
        note="Libellé métier exposé par PARTNERS002 ; interprétation analytique à consolider.",
    ),
    DataRequirement(
        key="transaction.hash",
        label="Identifiant unique de transaction",
        domain="Transactions",
        source="CONTRACT001 / ComChain PostgreSQL",
        status="available",
        consumers=(
            "Déduplication",
            "Traçabilité d’ingestion",
            "Contrôle d’intégrité",
            "Publication Financial Core",
            "Diagnostic de synchronisation",
        ),
        note="Un hash = une transaction normalisée dans TRANSACTIONS001.",
    ),
    DataRequirement(
        key="partner.active",
        label="Statut actif du partenaire",
        domain="Profils partenaires",
        source="PARTNERS002 / Odoo PostgreSQL",
        status="processing",
        consumers=(
            "Annuaire des professionnels actifs",
            "Qualification du réseau courant",
            "Contrôle des anciens membres",
            "Filtres des analyses partenaires",
        ),
        note="Champ active présent dans PARTNERS002 ; doctrine d’usage analytique à fixer.",
    ),
    DataRequirement(
        key="partner.is_published",
        label="Statut de publication du partenaire",
        domain="Profils partenaires",
        source="PARTNERS002 / Odoo PostgreSQL",
        status="processing",
        consumers=(
            "Annuaire / carte publique",
            "Filtrage des professionnels visibles",
            "Contrôle de publication des profils",
        ),
        note="Champ is_published présent dans PARTNERS002.",
    ),
    DataRequirement(
        key="partner.legal_activity_code",
        label="Code d’activité légale / NAF",
        domain="Profils partenaires",
        source="PARTNERS002 / Odoo PostgreSQL",
        status="processing",
        consumers=(
            "Analyse sectorielle NAF",
            "Enrichissement économique des professionnels",
            "Comparaisons réseau MLC / économie territoriale",
            "Fiches professionnels",
        ),
        note="Champ legal_activity_code présent dans PARTNERS002 ; nomenclature NAF et branchement analytique restent à consolider.",
    ),
    DataRequirement(
        key="partner.siret",
        label="SIRET du partenaire",
        domain="Identité légale",
        source="PARTNERS002 / Odoo PostgreSQL",
        status="processing",
        consumers=(
            "Identification légale des professionnels",
            "Enrichissement INSEE / SIRENE",
            "Déduplication des structures",
            "Fiches professionnels",
        ),
        note="Champ siret présent dans PARTNERS002 ; aucune valeur n’est déduite si absente.",
    ),
    DataRequirement(
        key="partner.siren",
        label="SIREN du partenaire",
        domain="Identité légale",
        source="PARTNERS002 / Odoo PostgreSQL",
        status="processing",
        consumers=(
            "Identification des organisations",
            "Enrichissement SIRENE",
            "Regroupement des établissements",
        ),
        note="Champ siren présent dans PARTNERS002.",
    ),
    DataRequirement(
        key="transaction.external_flags",
        label="Indication émetteur / destinataire externe",
        domain="Transactions / identité",
        source="CONTRACT001 / ComChain PostgreSQL",
        status="available",
        consumers=(
            "Contrôle des flux hors réseau",
            "Qualification des endpoints non résolus",
            "Audit des transactions sans partner_id",
        ),
        note="is_sender_external et is_receiver_external sont conservés indépendamment de partner_id.",
    ),
    DataRequirement(
        key="account.current_balance",
        label="Solde courant des comptes",
        domain="Soldes / stocks",
        source="ComChain PostgreSQL à auditer",
        status="missing",
        consumers=(
            "Avoirs détenus par les acteurs",
            "Pilotage monétaire",
            "Contrôle masse transactionnelle / stocks",
            "Futurs indicateurs de concentration des soldes",
        ),
        note="Besoin connu ; pas encore intégré au contrat Neutral de données.",
    ),
    DataRequirement(
        key="account.daily_balance",
        label="Historique quotidien des soldes",
        domain="Soldes / stocks",
        source="ComChain PostgreSQL à auditer",
        status="missing",
        consumers=(
            "Évolution des avoirs détenus",
            "Pilotage monétaire historique",
            "Concentration des soldes dans le temps",
        ),
        note="L’ancien MLCFlux synchronisait des soldes quotidiens ; équivalent Lokavaluto à localiser.",
    ),
    DataRequirement(
        key="monetary.total_supply",
        label="Masse monétaire totale suivie",
        domain="Pilotage monétaire",
        source="ComChain / Odoo à auditer",
        status="missing",
        consumers=(
            "KPI masse monétaire",
            "Pilotage monétaire",
            "Contrôle de cohérence des stocks",
        ),
        note="La source autoritative doit être déterminée pour l’architecture Neutral.",
    ),
    DataRequirement(
        key="monetary.guarantee",
        label="Montant de garantie / nantissement",
        domain="Pilotage monétaire",
        source="ComChain / Odoo à auditer",
        status="missing",
        consumers=(
            "KPI de garantie",
            "Pilotage monétaire",
            "Contrôle masse / garantie",
        ),
        note="Certaines opérations sont repérables via fn_abi, mais le stock autoritatif reste à auditer.",
    ),
    DataRequirement(
        key="account.medium",
        label="Support du compte / de la valeur (numérique, papier, bonus…)",
        domain="Comptes / supports",
        source="Lokavaluto à auditer",
        status="unaudited",
        consumers=(
            "Ventilation papier / numérique",
            "Pilotage monétaire par support",
            "Classification des opérations de change",
        ),
        note="Ne pas recréer une nomenclature avant d’avoir observé la structure native Lokavaluto.",
    ),
    DataRequirement(
        key="account.owner_relation",
        label="Relation compte financier → partenaire administratif",
        domain="Comptes / identité",
        source="ComChain ↔ Odoo à auditer",
        status="unaudited",
        consumers=(
            "Audit de la structure native des comptes",
            "Analyse multi-comptes par partenaire",
            "Contrôle des endpoints transactionnels",
        ),
        note="CONTRACT001 fournit déjà partner_id dans les transactions, mais la structure native des comptes reste volontairement hors contrat et doit être auditée séparément.",
    ),
    DataRequirement(
        key="partner.legal_name",
        label="Raison sociale distincte du nom affiché",
        domain="Identité légale",
        source="Odoo à auditer",
        status="unaudited",
        consumers=(
            "Fiches professionnels",
            "Recherche et contrôle d’identité",
        ),
        note="À distinguer de partner.name uniquement si la source fournit réellement deux concepts utiles.",
    ),
    DataRequirement(
        key="partner.address",
        label="Adresse postale détaillée",
        domain="Territoires",
        source="Odoo à auditer",
        status="unaudited",
        consumers=(
            "Contrôle géographique",
            "Fiches professionnels",
        ),
        note="Le code postal, la ville et les coordonnées sont déjà dans PARTNERS002 ; l’utilité de l’adresse complète reste à confirmer.",
    ),
)


def _validate_registry() -> None:
    seen: set[str] = set()

    for item in DATA_REQUIREMENTS:
        if item.key in seen:
            raise RuntimeError(f"Clé DATACTRL dupliquée : {item.key}")
        seen.add(item.key)

        if item.status not in STATUS_META:
            raise RuntimeError(
                f"Statut DATACTRL invalide pour {item.key}: {item.status}"
            )

        if not item.consumers:
            raise RuntimeError(
                f"Aucun consommateur déclaré pour {item.key}"
            )


_validate_registry()


def get_data_control_rows() -> list[dict[str, object]]:
    rows = [item.as_dict() for item in DATA_REQUIREMENTS]
    rows.sort(
        key=lambda row: (
            -int(row["usage_count"]),
            str(row["label"]).casefold(),
        )
    )
    return rows


def get_data_control_summary() -> dict[str, object]:
    rows = get_data_control_rows()
    counts = Counter(str(row["status"]) for row in rows)

    return {
        "total": len(rows),
        "status_counts": {
            key: counts.get(key, 0)
            for key in STATUS_META
        },
        "audited": sum(
            counts.get(key, 0)
            for key in (
                "available",
                "processing",
                "missing",
                "unavailable",
            )
        ),
    }
