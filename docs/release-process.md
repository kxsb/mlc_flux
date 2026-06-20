# Process de release MLCFlux

Le versionnage officiel de MLCFlux commence à partir de `v1.0.4`.

## Principes

- Le code source est historisé par Git.
- Chaque version publiée à partir de `v1.0.4` doit être associée à un tag Git.
- Le fichier `VERSION` contient la version courante.
- Le fichier `CHANGELOG.md` résume les changements par version.
- Le dossier `docs/releases/` contient les notes détaillées des versions importantes.

## Préparer une version

1. Mettre à jour `VERSION`.
2. Mettre à jour les libellés visibles dans l’interface.
3. Mettre à jour `CHANGELOG.md`.
4. Créer ou mettre à jour `docs/releases/vX.Y.Z.md`.
5. Tester en dev.
6. Déployer en production.
7. Committer l’état livré.
8. Créer le tag Git correspondant.

## Taguer une version

Après validation et commit :

    git tag -a vX.Y.Z -m "MLCFlux bêta vX.Y.Z multi"
    git push origin vX.Y.Z

## Règle retenue

Les versions antérieures à `v1.0.4` ne sont pas taguées rétroactivement. Elles restent des jalons historiques de la bêta multi-instance.
