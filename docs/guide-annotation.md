# Guide d'annotation

Ces règles ont été écrites **avant** d'annoter les 40 mails de démo (`src/inbox_planner/demo_data/labels.toml`). Elles rendent les annotations cohérentes entre elles et explicables. Sans elles, les chiffres de précision ne voudraient rien dire.

## 1. Catégorie (une seule par mail)

La catégorie est **la raison principale** pour laquelle le mail compte pour l'étudiante.

| Catégorie | Quand | Exemples |
|---|---|---|
| `appointment` | Il faut être quelque part, ou en ligne, à une heure donnée. | Cours, examen, entretien, rendez-vous, appel prévu |
| `deadline` | Un travail doit être rendu avant une date. | Devoir, quiz, projet, test technique, rapport |
| `procedure` | Une démarche administrative à accomplir. | Assurance, adresse, contrat d'études, dossier d'alternance |
| `info` | Bon à savoir, rien à planifier. | Notes publiées, fermeture, jour férié, coupure d'eau |
| `noise` | Rien d'utile. | Promotion, newsletter, réseau social, hameçonnage |

Pièges volontaires :
- Une **date dans une promotion ou une newsletter** (« jusqu'au 27 octobre », « exposition jusqu'au 30 novembre ») ne fait pas une échéance : le mail reste `noise`.
- Un **événement facultatif annoncé à tout le monde** (salon de l'emploi) est une `info`, pas un rendez-vous.
- Les **permanences libres** (office hours sans réservation) ne sont pas des rendez-vous. Une permanence **réservée** en est un.

## 2. Éléments extraits

Un mail `noise` ou `info` n'a aucun élément. Un mail `appointment` a au moins un rendez-vous, un mail `deadline` ou `procedure` au moins une échéance. Un mail peut contenir plusieurs éléments (brouillon lundi, relectures mercredi).

| Champ | Règle |
|---|---|
| `kind` | `appointment` (avec `starts_at`) ou `deadline` (avec `due_at`). |
| `starts_at`, `due_at` | Date et heure **avec le décalage UTC réel à cette date**. |
| `duration_minutes` | Seulement si le mail la donne (« 20 minutes », « 3 heures », heure de fin, durée d'un quiz chronométré). Sinon vide. |
| `weekly_on`, `repeat_until` | Pour les cours hebdomadaires : jours (`MO`…`SU`) et dernier jour inclus. `starts_at` est la première séance. |
| `location` | Lieu physique tel qu'écrit dans le mail (salle, adresse, aéroport). |
| `video_url` | L'URL réelle de la réunion. Un lien Outlook Safe Links est **déballé** : on garde le lien Teams d'origine. |
| `meeting_id`, `passcode` | Tels qu'écrits dans le mail. |
| `priority` | Voir § 4. |

## 3. Dates et fuseaux

1. **Heure sans fuseau** : c'est l'heure de l'expéditeur. OSU et les entreprises américaines sont en heure de l'Oregon, Lyon 2 et les entreprises françaises en heure de Paris. Une heure explicite (« 17 h, heure de Paris ») l'emporte.
2. **Échéance sans heure** : 23 h 59 dans le fuseau de l'expéditeur.
3. **Dates relatives** (« this Monday », « demain ») : elles se comptent à partir de la date d'envoi du mail.
4. **Changements d'heure 2026** : Paris passe de +02:00 à +01:00 le 25 octobre, l'Oregon de -07:00 à -08:00 le 1er novembre. Le décalage s'écrit selon la date de l'événement, pas celle du mail.
5. **Report** : seul le nouveau créneau est annoté.

Les tests de `tests/test_labels.py` vérifient automatiquement les règles 4 et 5 (décalage réel à chaque date, premier cours le bon jour de la semaine, événement postérieur au mail, lien de visio déballé).

## 4. Priorité

- `high` : examen, projet noté important, démarche administrative avec conséquence (crédits, statut, assurance), entretien d'embauche.
- `medium` : cours, devoir courant, rendez-vous ordinaire.
- `low` : facultatif ou personnel (groupe de révision, appel familial).

La priorité est un jugement : elle est rapportée dans l'évaluation, mais ce n'est pas un chiffre phare.

## 5. Qui a annoté

Les annotations ont été rédigées avec un assistant IA, puis relues à la main par Martin le 25/11/2026, mail par mail, avec ce guide sous les yeux (page de relecture : chaque mail à côté de son annotation, et les désaccords avec le modèle signalés). Aucune correction n'a été jugée nécessaire. Le mail m39 a été réécrit ensuite, à la demande de Martin (D63) ; sa nouvelle annotation a été relue et validée par Martin le même jour, sans correction.
