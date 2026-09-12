# Données de l'installation MLCFlux

Une installation utilise uniquement le sous-dossier du profil défini par
`MLCFLUX_DEFAULT_MLC_ID`. L'arborescence par identifiant est conservée pour
préserver les chemins des bases, mappings et caches existants ; elle ne constitue
pas un portail de sélection de monnaies.

Exemples de chemins selon le profil installé :

- `graine/mlcflux.db`
- `gonette/mlcflux.db`

Les bases SQLite, mappings de pseudonymisation, caches et locks ne doivent pas être versionnés.
Les profils déclaratifs publics sont stockés dans `server/data/mlc_profiles/`.
