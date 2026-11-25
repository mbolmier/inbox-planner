# Évaluation

*Générée par `inbox-planner eval --output docs/evaluation.md` à partir des réponses enregistrées. Ne pas modifier à la main : la CI vérifie que ce fichier est à jour.*

- **Jeu de test :** 40 mails fictifs annotés à la main ([guide d'annotation](guide-annotation.md)), 31 éléments attendus.
- **Réponses des modèles :** enregistrées avec Claude Code (`claude -p`, abonnement Claude), puis rejouées depuis le cache : les chiffres sont reproductibles sans compte.
- **Coût :** *estimé* au tarif public de l'API Anthropic, tous les tokens d'entrée au plein tarif (sans remise de cache). Aucun euro n'a été dépensé.
- **Temps :** temps de réponse du modèle, moyenne par mail.

## Tri

« Utile » = tout sauf le bruit.

| Modèle | Exactitude | Précision « utile » | Rappel « utile » | Échecs | Tokens entrée / sortie | Coût estimé (40 mails) | Temps / mail |
|---|---|---|---|---|---|---|---|
| haiku-5-5 | 95 % | 94 % | 100 % | 0 | 99 955 / 11 753 | 0,016 $ | 2,5 s |
| sonnet-5-5 | 90 % | 100 % | 100 % | 0 | 99 079 / 5 162 | 0,250 $ | 1,9 s |
| opus-5-5 | 98 % | 97 % | 100 % | 0 | 98 942 / 7 349 | 0,543 $ | 4,2 s |

## Extraction (sur les 40 mails)

Un élément est **retrouvé** s'il a le bon type et exactement le bon instant, fuseau compris. Le rappel est donc l'exactitude des dates.

| Modèle | Précision | Rappel (dates exactes) | Mauvais fuseau | Liens visio | ID + code | Récurrences | Durées | Coût estimé | Temps / mail |
|---|---|---|---|---|---|---|---|---|---|
| haiku-5-5 | 100 % | 100 % (31/31) | 0 | 4/4 | 4/4 | 6/6 | 16/18 | 0,023 $ | 2,8 s |
| sonnet-5-5 | 100 % | 100 % (31/31) | 0 | 4/4 | 4/4 | 6/6 | 17/18 | 0,371 $ | 2,1 s |
| opus-5-5 | 100 % | 100 % (31/31) | 0 | 4/4 | 4/4 | 6/6 | 17/18 | 0,782 $ | 5,5 s |

## Chaîne retenue : tri haiku-5-5 → extraction haiku-5-5

L'extraction ne tourne que sur les mails que le tri juge utiles à planifier (rendez-vous, échéance, démarche).

- Précision : **100 %**, rappel : **100 %** (31/31 éléments retrouvés).
- Mails envoyés à l'extraction : 27 sur 40.
- Coût estimé pour les 40 mails : **0,034 $** (tri 0,016 $, extraction 0,018 $).

### Tri par catégorie

| Catégorie | Précision | Rappel | Effectif |
|---|---|---|---|
| rendez-vous | 100 % | 100 % | 14 |
| échéance | 100 % | 100 % | 7 |
| démarche | 100 % | 100 % | 6 |
| info | 75 % | 100 % | 6 |
| bruit | 100 % | 71 % | 7 |

## Erreurs à analyser

### Tri

- `m31` : attendu *bruit*, prédit *info*
- `m34` : attendu *bruit*, prédit *info*

### Extraction (haiku-5-5)

Aucune.
