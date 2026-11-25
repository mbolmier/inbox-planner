# Journal des décisions

Chaque décision tient en trois lignes : ce qu'on a choisi, ce qu'on aurait pu faire, et pourquoi. Les plus récentes sont en bas.

---

## Étape 1 : socle

### D1. Écrire le `.gitignore` avant le premier commit
- **Décision :** `.env`, jetons OAuth, bases SQLite, exports de mails réels (`.eml`, `.mbox`, `.pst`), `CLAUDE.md` et `.claude/` sont ignorés dès le départ. Aucune exception pour les `.eml` : la boîte de démo est un fichier TOML (voir D16).
- **Alternatives :** compléter le `.gitignore` au fil de l'eau.
- **Pourquoi :** une donnée commitée reste dans l'historique git même si on la supprime ensuite. Il vaut mieux qu'un `git add .` distrait ne puisse rien embarquer de sensible.

### D2. uv pour Python, l'environnement et les dépendances
- **Décision :** uv gère la version de Python (3.12), le `.venv`, les dépendances et le verrou `uv.lock`.
- **Alternatives :** pip + venv + `requirements.txt`, Poetry.
- **Pourquoi :** un seul outil au lieu de trois, très rapide, et le verrou garantit que la CI et Docker installent exactement les mêmes versions que ma machine.

### D3. Layout `src/`
- **Décision :** le code vit dans `src/inbox_planner/`, les tests dans `tests/`.
- **Alternatives :** le paquet à la racine du dépôt.
- **Pourquoi :** les tests importent le paquet installé, pas le dossier courant. Une erreur d'empaquetage (fichier oublié, import cassé) se voit tout de suite, pas au moment de construire l'image Docker.

### D4. ruff et pytest
- **Décision :** ruff pour le lint et le formatage, pytest pour les tests.
- **Alternatives :** flake8 + isort + black, unittest.
- **Pourquoi :** ruff remplace trois outils par un seul, beaucoup plus rapide, configuré dans `pyproject.toml`. pytest est le standard en Python et ses fixtures simplifient les tests.

### D5. Scan de secrets à trois niveaux (gitleaks)
- **Décision :** gitleaks tourne avant chaque commit (changements indexés), avant chaque push (tout l'historique) et dans la CI (tout l'historique).
- **Alternatives :** seulement en CI, ou seulement en local.
- **Pourquoi :** un secret poussé sur GitHub doit être considéré comme compromis, même dans un dépôt privé. Le local bloque avant que ça parte. La CI rattrape ce qui contourne les hooks (`git commit --no-verify`). Vérifié : un faux jeton AWS généré au hasard est bien bloqué au commit.

### D6. Une seule version de chaque outil
- **Décision :** gitleaks 8.30.1 vient de Homebrew en local et la CI demande la même version. ruff tourne dans les hooks via `uv run`, donc avec la version de `uv.lock`.
- **Alternatives :** les dépôts de hooks officiels de pre-commit, qui épinglent leur propre version de chaque outil.
- **Pourquoi :** si le hook et la CI utilisent des versions différentes, un fichier peut passer en local et échouer en CI. Une seule source de vérité évite ce décalage.

### D7. Identité git locale avec l'adresse noreply de GitHub
- **Décision :** `user.name` et `user.email` sont réglés dans la config locale du dépôt, avec l'adresse `…@users.noreply.github.com`.
- **Alternatives :** la config git globale, l'adresse mail personnelle.
- **Pourquoi :** l'adresse noreply relie les commits à mon compte GitHub sans publier mon mail personnel dans l'historique, qui deviendra public.

### D8. Dépôt privé jusqu'au scan final
- **Décision :** le dépôt `mbolmier/inbox-planner` est privé. Il ne passe en public qu'après un dernier scan des secrets et des données personnelles.
- **Alternatives :** public dès le début.
- **Pourquoi :** rendre public est irréversible en pratique (forks, caches, archives). On ne publie qu'un historique vérifié.

### D9. CI GitHub Actions minimale, en lecture seule
- **Décision :** deux jobs (lint + tests, scan de secrets), lancés à chaque push sur `main` et à chaque pull request. Le jeton de la CI n'a que le droit de lire le code.
- **Alternatives :** pas de CI au début, ou des permissions par défaut.
- **Pourquoi :** la CI prouve que le projet s'installe et passe ses tests sur une machine propre, pas seulement sur la mienne. Le moindre privilège limite les dégâts si une action tierce était compromise. Coût : gratuit (quota inclus pour les dépôts privés, illimité en public).

### D9 bis. Actions GitHub épinglées par SHA de commit
- **Décision :** chaque action tierce est référencée par le SHA complet d'un commit, avec la version en commentaire (`actions/checkout@3d3c42e… # v7.0.1`).
- **Alternatives :** un tag de version majeure (`@v7`) ou exacte (`@v7.0.1`).
- **Pourquoi :** le propriétaire d'une action peut déplacer un tag vers un autre code, mais pas un SHA. C'est la recommandation de GitHub contre les attaques de chaîne d'approvisionnement. Leçon du premier run : `setup-uv` ne publie pas de tag `@v10`, et la CI avait échoué au démarrage.

### D10. Projet hors du dossier synchronisé par iCloud
- **Décision :** le projet vit dans `~/Portfolio/inbox-planner`, pas dans `~/Documents`.
- **Alternatives :** le laisser dans `~/Documents`.
- **Pourquoi :** iCloud synchronise fichier par fichier et peut créer des conflits ou des fichiers corrompus dans `.git` et `.venv`. GitHub est déjà la sauvegarde du code.

### D11. Données de démo : écoles et cours réels, personnes fictives
- **Décision :** les écoles (Université Lumière Lyon 2 / IUT Lumière, Oregon State University) et des intitulés de cours réellement suivis apparaissent, complétés par des cours inventés. Les étudiantes, profs, adresses (domaines `.example`, réservés par la RFC 2606), horaires, salles et liens sont fictifs.
- **Alternatives :** tout inventer, y compris les écoles.
- **Pourquoi :** le projet raconte mon échange, donc les vraies écoles le rendent crédible. Aucune personne réelle, aucune adresse joignable et aucun horaire réel n'apparaissent : rien ne permet de joindre ou de localiser quelqu'un.

### D12. LLM sans dépense au-delà de l'abonnement Claude
- **Décision :** la couche LLM a trois implémentations interchangeables. **Claude Code** appelle `claude -p` (mode non interactif) avec l'abonnement existant ; il sert à produire et enregistrer les réponses en local. **Replay** relit ces réponses enregistrées ; il sert à la démo, aux tests et à la CI. **API Anthropic** suit la documentation officielle pour qui a une clé, mais il n'est pas exécuté dans ce projet, et le README le dit.
- **Alternatives :** une clé API payante, un modèle local gratuit (Ollama).
- **Pourquoi :** zéro euro dépensé, et la démo tourne sans aucun compte. Les tâches simples (tri) vont sur un petit modèle, les tâches plus dures (extraction) sur un plus gros. Le README compare les modèles dans un tableau coût/qualité, avec un coût estimé au tarif public de l'API à partir des tokens consommés.

---

## Étape 2 : boîte fictive et connecteur Demo

### D13. Une branche et une pull request par étape
- **Décision :** chaque étape vit sur sa branche (`step-2-demo-mailbox`…) et arrive sur `main` par une pull request.
- **Alternatives :** tout commiter directement sur `main`.
- **Pourquoi :** la CI valide la PR avant la fusion, donc `main` reste toujours vert. L'historique des PR montre aussi la démarche, étape par étape.

### D14. Un modèle `Message` commun, avec une date obligatoirement munie de son fuseau
- **Décision :** tous les connecteurs (Demo, Gmail, Outlook, IMAP) renvoient le même objet Pydantic `Message`. Son champ `sent_at` est de type `AwareDatetime` : une date sans fuseau est refusée.
- **Alternatives :** un dictionnaire par fournisseur, des dates « naïves » converties plus tard.
- **Pourquoi :** le reste du code ignore d'où vient le mail. Et une date sans fuseau est la première source de bugs d'agenda entre Paris et l'Oregon : on la refuse à l'entrée plutôt que de la corriger après.

### D15. Une interface de connecteur en lecture seule
- **Décision :** `MailConnector` est un `Protocol` avec une seule méthode, `fetch_messages`. Il n'existe aucune méthode d'envoi.
- **Alternatives :** une classe de base abstraite, une interface lecture + envoi.
- **Pourquoi :** la lecture seule est garantie par construction : on ne peut pas appeler ce qui n'existe pas. Avec un `Protocol`, n'importe quel objet qui a la bonne méthode convient, sans héritage, ce qui simplifie les tests. Les brouillons arriveront à l'étape 6 dans une méthode séparée.

### D16. Boîte de démo en TOML, reconvertie en vrai mail puis reparsée
- **Décision :** les mails fictifs sont écrits dans un fichier TOML lisible. Le connecteur Demo transforme chaque entrée en vrai mail MIME (le format brut que renvoient IMAP et Gmail), puis le passe au même parseur que les vrais connecteurs. Les mails HTML sont convertis en texte en gardant l'URL des liens (`Rejoindre la réunion <https://…>`), avec le `HTMLParser` de la bibliothèque standard.
- **Alternatives :** des fichiers `.eml` écrits à la main, un JSON déjà « propre », BeautifulSoup pour le HTML.
- **Pourquoi :** le TOML se relit facilement, et la démo teste quand même le vrai chemin (encodages, multipart, dates). TOML est dans la bibliothèque standard, gère les dates avec fuseau et les textes multilignes. Garder les URL est indispensable : dans une invitation Teams, le lien est souvent caché derrière un texte.

### D17. Horloge de démo figée au lundi 26 octobre 2026, 8 h (Oregon)
- **Décision :** la démo et l'évaluation utilisent un « maintenant » fixe, `DEMO_NOW`.
- **Alternatives :** décaler toutes les dates pour qu'elles tombent « cette semaine ».
- **Pourquoi :** les dates des mails sont la vérité de l'évaluation, elles ne peuvent pas bouger. Cette semaine-là, l'Europe est déjà à l'heure d'hiver (25 octobre) mais pas l'Oregon (1er novembre) : l'écart est de 8 h au lieu de 9, un piège voulu.

### D18. Garde-fou de confidentialité testé en CI
- **Décision :** un test échoue si une adresse du jeu de démo n'utilise pas un domaine `.example` (réservé par la RFC 2606), ou si un lien pointe ailleurs que vers un domaine `.example` ou un fournisseur de visio. Un test vérifie aussi que le garde-fou attrape bien une vraie adresse.
- **Alternatives :** une relecture manuelle.
- **Pourquoi :** la règle « aucune donnée réelle » est vérifiée à chaque commit, pas seulement promise. Un oubli dans un des 40 mails est attrapé automatiquement.

### D19. Données de démo embarquées dans le paquet Python
- **Décision :** `mailbox.toml` vit dans `src/inbox_planner/demo_data/` et se lit avec `importlib.resources`. Vérifié : il est bien présent dans le wheel construit.
- **Alternatives :** un dossier `data/` à la racine du dépôt.
- **Pourquoi :** la démo doit marcher partout où le paquet est installé (Docker, `pip install`), pas seulement depuis le dossier du projet.

### D20. Un seul schéma pour l'extraction et pour les annotations
- **Décision :** le modèle Pydantic `ExtractedItem` décrit ce que l'agent d'extraction doit produire (étape 3). Les annotations à la main utilisent exactement le même modèle.
- **Alternatives :** un format d'annotation à part, converti au moment d'évaluer.
- **Pourquoi :** l'évaluation compare deux objets de même forme, sans traduction qui pourrait introduire des erreurs. Le schéma valide aussi la cohérence : un rendez-vous doit avoir une heure de début, une échéance une date limite, une récurrence une date de fin.

### D21. Un guide d'annotation écrit avant d'annoter
- **Décision :** `docs/guide-annotation.md` fixe les règles (catégorie = raison principale du mail, échéance sans heure = 23 h 59 chez l'expéditeur, liens Safe Links déballés…).
- **Alternatives :** annoter « au feeling ».
- **Pourquoi :** sans règles écrites, deux annotateurs (ou le même, deux jours plus tard) ne seraient pas d'accord, et la précision mesurée dépendrait de l'humeur. Les règles rendent aussi chaque étiquette défendable.

### D22. Récurrence hebdomadaire dans le schéma
- **Décision :** un rendez-vous peut porter `weekly_on` (jours) et `repeat_until` (dernier jour). Un mail « cours lundi, mercredi et vendredi » donne tout l'emploi du temps.
- **Alternatives :** importer l'emploi du temps à part, un élément par séance.
- **Pourquoi :** c'est ce que faisait l'outil d'origine : tirer l'emploi du temps des mails. Le calendrier de la démo est ainsi rempli. Limite assumée : les exceptions (séance déplacée, jour férié) ne retirent pas encore la séance d'origine.

### D23. Des tests qui vérifient les annotations elles-mêmes
- **Décision :** `tests/test_labels.py` vérifie que chaque décalage UTC est le vrai décalage de Paris ou de l'Oregon à cette date, que chaque cours commence le bon jour de la semaine, que chaque événement est postérieur à son mail et que les liens de visio sont déballés.
- **Alternatives :** faire confiance à la relecture.
- **Pourquoi :** une erreur dans la vérité terrain fausse tous les chiffres de l'évaluation, sans que personne ne le voie. Le test sur les décalages a été vérifié : il rejette `-07:00` le 5 novembre.

### D24. 40 mails, des pièges volontaires
- **Décision :** répartition 14 rendez-vous, 7 échéances, 6 démarches, 6 infos, 7 bruits, sur trois boîtes. Pièges : semaine à 8 h d'écart, échéances qui tombent après le changement d'heure, dates relatives, lien Safe Links, mail HTML seul, report de séance, dates dans des promotions, hameçonnage.
- **Alternatives :** des mails « faciles ».
- **Pourquoi :** des mails faciles donneraient des chiffres flatteurs qui ne disent rien. Les pièges viennent des vrais problèmes rencontrés pendant l'échange.

---

## Étape 3 : agents de tri et d'extraction, évaluation

### D25. Le LLM lit, le code calcule
- **Décision :** pour chaque date, le modèle renvoie une heure *locale* (`2026-11-05T12:00`) et un nom de fuseau IANA (`America/Los_Angeles`). C'est Python (`zoneinfo`) qui calcule le décalage UTC, changements d'heure compris. Les liens Outlook Safe Links sont déballés en code, pas par le modèle.
- **Alternatives :** demander au modèle une date avec son décalage (`-08:00`), lui demander de déballer les liens.
- **Pourquoi :** savoir que l'Oregon passe à -08:00 le 1er novembre à 2 h, c'est de l'arithmétique de calendrier : un LLM peut s'y tromper, `zoneinfo` jamais, et c'est testable. Même logique que pour la planification : le modèle sert là où il faut comprendre du texte, le code là où il faut un résultat exact.

### D26. Tri et extraction séparés, chacun avec son modèle
- **Décision :** deux agents, deux appels, deux modèles réglables. L'évaluation compare Haiku 5.5, Sonnet 5.5 et Opus 5.5 sur chaque tâche.
- **Alternatives :** un seul appel qui trie et extrait, un seul modèle pour tout.
- **Pourquoi :** chaque agent a une seule mission, se mesure séparément, et peut tourner sur le modèle le moins cher qui tient la qualité. En production, le bruit n'est jamais envoyé à l'extraction, plus coûteuse.

### D27. Ce que voit le modèle
- **Décision :** le prompt donne la boîte, son fuseau par défaut, la date d'envoi avec le jour de la semaine, puis le mail. Le prompt système reprend les règles du guide d'annotation, jamais les annotations.
- **Alternatives :** le mail brut seul.
- **Pourquoi :** une vraie installation connaît le fuseau de chaque boîte, et « this Monday » n'a de sens qu'avec la date d'envoi. Les règles définissent la tâche, comme un cahier des charges. Donner les réponses, en revanche, serait tricher.

### D28. Cache par empreinte, sans le prompt
- **Décision :** chaque réponse est rangée sous le hash SHA-256 de (modèle, prompt système, prompt, schéma). Le fichier garde la réponse, les tokens, la durée et une étiquette (`triage/m02`), jamais le prompt.
- **Alternatives :** une clé par identifiant de mail, stocker le prompt avec la réponse.
- **Pourquoi :** si un prompt change, l'ancienne réponse ne correspond plus. Le mode « rejeu » échoue alors franchement au lieu de servir une réponse périmée. Et comme le prompt n'est pas stocké, utiliser le cache sur de vrais mails ne recopie aucun contenu sur le disque.

### D29. Client Claude Code isolé, incapable de facturer une clé API
- **Décision :** chaque appel `claude -p` tourne dans un dossier temporaire vide, avec notre prompt système à la place de celui de Claude Code, aucun outil, aucun serveur MCP, aucune session sauvegardée. `ANTHROPIC_API_KEY` est retirée de son environnement. Si le CLI est injoignable (déconnecté, délai dépassé), l'évaluation s'arrête ; si une réponse ne respecte pas le schéma, c'est un échec compté pour ce mail.
- **Alternatives :** appeler le CLI tel quel.
- **Pourquoi :** le modèle ne doit voir que le mail, pas les fichiers du projet (il y trouverait les annotations). Retirer la clé garantit que l'abonnement est utilisé, jamais une carte bancaire. Et une panne ne doit pas se déguiser en mauvais score.

### D30. Client API Anthropic écrit, testé, mais jamais exécuté
- **Décision :** `AnthropicClient` utilise le SDK officiel (`beta.messages.parse` avec le schéma Pydantic), dans une dépendance optionnelle (`uv sync --extra anthropic`). Le repli automatique côté serveur est activé quand le modèle refuse de répondre, sauf pour Haiku, qui ne le propose pas.
- **Alternatives :** ne pas l'écrire, ou appeler l'API en HTTP brut.
- **Pourquoi :** quelqu'un qui a une clé peut s'en servir tout de suite. Comme il n'est jamais exécuté ici, les appels ont été vérifiés contre la signature du SDK installé (2.14.0), et le client est testé avec un faux SDK. Le README le dira clairement.

### D31. Ce que mesure l'évaluation
- **Décision :** tri : exactitude, précision et rappel par catégorie et pour « utile » (tout sauf le bruit). Extraction : un élément est retrouvé s'il a le bon type et *exactement* le bon instant, fuseau compris. Sont comptés à part les « bonne heure, mauvais fuseau », les liens de visio, ID et codes exacts, les récurrences et les durées. Le coût est estimé au tarif public de l'API, en borne haute (sans remise de cache).
- **Alternatives :** une tolérance d'une heure sur les dates, une similarité de titre.
- **Pourquoi :** une heure de décalage, c'est un entretien raté : la tolérance cacherait exactement l'erreur que le projet veut mesurer. Les titres ne sont pas notés, car deux formulations peuvent être justes.

### D32. Un faux modèle « parfait » doit obtenir 100 %
- **Décision :** un test fait répondre un faux modèle exactement selon les annotations, puis vérifie 100 % sur toutes les métriques, chaîne complète comprise.
- **Alternatives :** tester seulement les fonctions une par une.
- **Pourquoi :** si la conversion des fuseaux ou l'appariement perdait quelque chose en route, un modèle parfait n'aurait pas 100 %. Ce test prouve que les chiffres mesurent le modèle, pas un bug de la mesure.

### D33. Chaîne par défaut : Haiku pour le tri ET pour l'extraction
- **Décision :** `inbox-planner` utilise Haiku 5.5 pour les deux agents.
- **Alternatives :** l'intuition de départ (petit modèle pour le tri, plus gros pour l'extraction), Sonnet ou Opus partout « par prudence ».
- **Pourquoi :** c'est la mesure qui tranche. En extraction, Haiku, Sonnet et Opus retrouvent tous 29 éléments sur 29, dates et fuseaux exacts. En tri, Haiku fait 95 % contre 100 %, mais ses deux erreurs (bruit lu comme info) n'ont aucun effet sur la chaîne, puisque ni l'un ni l'autre ne part en extraction. Coût estimé pour 40 mails : 0,030 $ avec Haiku → Haiku, 0,267 $ avec Haiku → Sonnet. *(Chiffres d'avant le réenregistrement de D42 ; les chiffres à jour sont dans `docs/evaluation.md`. La conclusion ne change pas.)* **Réserve :** avec 29 éléments, un 100 % reste compatible avec un vrai taux d'erreur proche de 10 % (règle de trois : 3/29). Le jeu est trop facile pour départager les modèles. Le choix sera revu si un jeu plus difficile montre un écart.

### D34. Pas de retouche des prompts sur le jeu de test
- **Décision :** les erreurs mesurées sont documentées, pas « corrigées » en ajustant les prompts ou les annotations sur ces 40 mails.
- **Alternatives :** retoucher le prompt jusqu'à 100 % partout.
- **Pourquoi :** ajuster les prompts sur le jeu qui sert à les noter, c'est du sur-apprentissage : les chiffres monteraient sans rien prouver. Or les erreurs viennent de ma spécification, pas des modèles. (1) m22 : « Prévoyez environ 3 heures » n'est pas compté comme durée, car le prompt ne dit pas qu'une estimation de travail compte pour une échéance. (2) m31 et m34 : le guide dit à la fois « newsletter = bruit » et « événement facultatif annoncé à tous = info », et Haiku applique la seconde règle. Pour corriger proprement, il faut clarifier le guide, puis valider le nouveau prompt sur un **jeu de développement séparé**.

### D35. La CI rejoue l'évaluation et vérifie le rapport publié
- **Décision :** à chaque PR, la CI relance `inbox-planner eval` en mode rejeu (aucun appel au modèle, aucun compte), puis vérifie par `git diff` que `docs/evaluation.md` est identique. Le garde-fou de confidentialité scanne aussi les 240 réponses enregistrées.
- **Alternatives :** publier des chiffres calculés une fois à la main.
- **Pourquoi :** un chiffre du README qui ne correspond plus au code est attrapé automatiquement, et n'importe qui peut refaire le calcul. Le rapport ne contient donc pas de date, sinon il changerait tous les jours.

---

## Étape 4 : planification selon l'énergie

### D36. La planification est un algorithme, pas un LLM
- **Décision :** le plan de la semaine est calculé par un algorithme déterministe (`planning/planner.py`), sans appel à un modèle.
- **Alternatives :** demander à un LLM de « répartir les tâches dans la semaine ».
- **Pourquoi :**
  1. **Contraintes dures.** Ne jamais chevaucher un cours, ne jamais dépasser l'énergie du jour, ne jamais placer du travail après une échéance. Un LLM peut inventer un créneau qui chevauche ou oublier une tâche, et pour vérifier sa réponse il faudrait de toute façon cet algorithme.
  2. **Déterministe, donc testable.** Même entrée, même plan : on peut écrire des tests exacts, et 300 semaines aléatoires vérifient les règles à chaque commit.
  3. **Explicable.** « Cette tâche est là parce que son échéance est la plus proche » se dit en une phrase.
  4. **Gratuit, instantané, hors ligne.** Aucune donnée personnelle n'est envoyée.

  Le LLM sert là où il faut comprendre du texte libre (les mails). La planification est un problème d'optimisation bien posé, et l'algorithme y est meilleur.

### D37. Échéance la plus proche d'abord (EDF)
- **Décision :** les tâches sont prises par date limite, puis par priorité. Chacune est placée dans les premiers créneaux libres avant son échéance.
- **Alternatives :** la priorité d'abord, le placement au plus tard, un solveur d'optimisation (programmation linéaire).
- **Pourquoi :** EDF est un classique de l'ordonnancement. Quand tout est disponible dès maintenant, c'est la stratégie optimale pour tenir les échéances sur une seule ressource (règle de Jackson, 1955). Avec les contraintes d'énergie et de pauses, c'est une heuristique solide, pas une garantie mathématique. Placer au plus tôt laisse le maximum de marge, et un solveur serait plus lourd sans gain visible à cette échelle. Limite assumée : le travail est concentré en début de semaine. *(Placement revu en D64 : l'ordre EDF reste, le travail est désormais étalé.)*

### D38. L'énergie fixe la capacité du jour et la longueur des blocs
- **Décision :** Off = 0, Crevé = 2 h par blocs de 45 min, Normal = 4 h par blocs de 1 h 30, En forme = 6 h par blocs de 2 h. Les journées vont de 8 h à 22 h, avec 15 min de marge autour de chaque rendez-vous et entre deux blocs. Une tâche sans estimation compte 1 h.
- **Alternatives :** l'énergie qui change seulement l'ordre des tâches, un modèle appris.
- **Pourquoi :** des règles simples qu'on peut expliquer et régler, et l'utilisatrice comprend tout de suite l'effet de son choix. Pas assez de données pour apprendre quoi que ce soit.

### D39. Pas de miettes
- **Décision :** un bloc ne laisse jamais un reste de moins de 25 minutes. Il prend tout d'un coup, ou s'arrête assez tôt pour laisser un vrai bloc.
- **Alternatives :** couper au maximum de la longueur autorisée.
- **Pourquoi :** le premier essai sur la semaine de démo planifiait un bloc de 5 minutes, ce qui ne sert à rien. 60 minutes un jour « crevé » donnent maintenant 35 + 25 au lieu de 45 + 15.

### D40. Calcul en UTC, affichage en heure locale ; récurrences en heure locale
- **Décision :** les créneaux libres et les blocs sont calculés en UTC. Un cours hebdomadaire se répète à la même heure locale dans son fuseau.
- **Alternatives :** calculer en heure locale, répéter tous les 7 × 24 h.
- **Pourquoi :** l'arithmétique en heure locale se trompe autour des changements d'heure, et répéter tous les 7 × 24 h décalerait le cours de 10 h à 9 h après le 1er novembre. Un test vérifie que le cours de 10 h reste à 10 h (-07:00 puis -08:00).

### D41. Tests par propriétés (hypothesis) et signalement des conflits
- **Décision :** en plus des tests classiques, `hypothesis` génère 300 semaines aléatoires (rendez-vous, tâches, énergies) et vérifie 8 règles : pas de chevauchement, marges respectées, rien après l'échéance, journée de travail respectée, longueur des blocs, capacité du jour, aucune minute perdue, résultat indépendant du fuseau d'entrée. Les rendez-vous qui se chevauchent sont signalés.
- **Alternatives :** quelques exemples écrits à la main.
- **Pourquoi :** un planificateur a énormément de cas limites, et un exemple écrit à la main ne teste que ce à quoi on a pensé. Vérifié : un bug introduit exprès (capacité du jour ignorée) est attrapé aussitôt. Les conflits sont signalés parce que la semaine de démo en contient un vrai : le lab déplacé au vendredi est encore répété le jeudi (limite D22), et il vaut mieux le montrer que le cacher.

---

## Étape 5 : lieux, vue web, export .ics

### D42. Une heure de référence explicite dans chaque prompt
- **Décision :** chaque prompt commence par « Reference time (now) » : l'heure réelle en production, l'horloge figée (lundi 26 octobre 2026, 8 h) en démo. Le prompt système demande de juger par rapport à ce moment, jamais par rapport à une autre date connue.
- **Alternatives :** ne rien dire et laisser le modèle supposer la date.
- **Pourquoi :** la vue web a montré une justification de tri qui disait « déjà passée, puisque nous sommes le 25 novembre ». Le modèle connaissait la vraie date du jour, injectée par Claude Code. Sur les réponses enregistrées, 20 justifications de tri sur 40 pour Haiku et 6 pour Opus raisonnaient par rapport au 25 novembre. Les catégories et les dates extraites restaient justes, mais c'est un biais : le modèle ne vivait pas au même « maintenant » que la démo. Ce n'est pas un réglage sur le jeu de test au sens de D34 : je ne corrige pas une erreur mesurée, je corrige le contexte donné au modèle. Les 240 réponses ont été réenregistrées. **Après :** plus aucune mention du 25 novembre ou d'une date « déjà passée » (0/240). Le tri bouge : Haiku reste à 95 %, Sonnet passe de 100 à 90 %, Opus de 100 à 98 % (voir D49). L'extraction ne bouge pas (29/29 pour les trois modèles). Les tokens d'entrée de Haiku et Sonnet augmentent d'environ 50 % : ça ne vient pas de la ligne ajoutée (environ 25 tokens), mais du CLI. La version 2.1.332, imposée par Opus 5.5, ajoute environ 850 tokens de contexte par appel, alors que le premier enregistrement de Haiku et Sonnet s'était fait en 2.1.235.

### D43. Lieux cliquables, sans clé d'API
- **Décision :**
  - **Lieu physique :** l'URL de recherche documentée de Google Maps (`https://www.google.com/maps/search/?api=1&query=…`), avec la ville de la boîte ajoutée si le lieu ne la nomme pas (« Alder Hall 120, Corvallis, OR »).
  - **Visio :** le fournisseur (Zoom, Teams, Meet) est reconnu au domaine du lien, déballé des Safe Links. L'ID et le code sont affichés à côté.
  - **Sécurité :** seuls les liens `https` deviennent cliquables.
- **Alternatives :** l'API Geocoding de Google (clé, facturation), `geo:` ou Apple Plans, laisser le texte brut.
- **Pourquoi :** zéro clé, zéro coût, et le lien marche sur ordinateur comme sur téléphone. Le filtre `https` empêche un mail piégé de faire exécuter du code par un lien `javascript:` dans l'app : c'est testé.

### D44. Export .ics avec la bibliothèque `icalendar`
- **Décision :**
  - **Fuseaux :** les rendez-vous gardent leur fuseau (TZID et définition VTIMEZONE incluse). Un cours hebdomadaire devient un seul événement récurrent (RRULE) dans son fuseau, avec la date de fin en UTC comme l'exige la RFC 5545.
  - **Échéances :** un court événement qui finit à l'heure limite, avec un rappel la veille.
  - **Blocs de travail :** en option, marqués « disponible » (ils n'apparaissent pas comme occupés).
  - **Identifiants stables :** réimporter le fichier met à jour au lieu de dupliquer.
- **Alternatives :** écrire le format à la main, tout exporter en UTC, une tâche VTODO par échéance.
- **Pourquoi :** le format a des pièges (lignes coupées à 75 octets, caractères à échapper, fuseaux) que la bibliothèque gère. En UTC, le cours de 10 h passerait à 9 h après le 1er novembre. Google Agenda ignore les VTODO à l'import. Un test a montré que les annotations, qui portent un décalage fixe, perdaient le fuseau Europe/Paris : l'export utilise donc la sortie réelle du pipeline, qui porte des fuseaux IANA.

### D45. Interface : FastAPI, gabarits Jinja, HTMX, FullCalendar
- **Décision :**
  - **Trois pages reliées par de vrais liens :** Aujourd'hui, Semaine, Échéances, plus une page par mail.
  - **Énergie (HTMX) :** changer l'énergie envoie une requête et le serveur renvoie le fragment de page recalculé, sans écrire de JavaScript. Dans la vue Semaine, le serveur demande en plus au calendrier de recharger ses événements (en-tête `HX-Trigger: planChanged`).
  - **Heures (FullCalendar) :** le calendrier reçoit les heures locales de l'Oregon sans décalage. Le serveur convertit, le navigateur affiche tel quel.
- **Alternatives :** React ou Vue avec une API JSON, des vues sans JavaScript du tout, un calendrier dessiné à la main.
- **Pourquoi :** tout le calcul reste en Python et testé côté serveur. Le seul JavaScript écrit à la main fait 25 lignes. Sans la conversion côté serveur, un recruteur qui ouvre la démo depuis Paris verrait les cours de 10 h à 18 h.

### D46. Sécurité de l'interface
- **Décision :**
  - **Mails en texte :** le corps des mails est toujours affiché en texte échappé, jamais en HTML.
  - **CSP stricte :** une politique de sécurité du contenu limite les scripts à l'app et aux fichiers CDN épinglés.
  - **Empreintes SRI :** chaque fichier CDN porte son empreinte, et le navigateur refuse un fichier modifié.
  - **Anti-CSRF :** les requêtes qui modifient quelque chose exigent l'en-tête `HX-Request`, qu'un formulaire d'un autre site ne peut pas envoyer.
  - **Pas de Referer :** aucun référent n'est envoyé à Maps ou Zoom.
  - **Écoute locale :** le serveur n'écoute que sur 127.0.0.1 par défaut.
  - **Polices système :** pas de Google Fonts.
- **Alternatives :** les réglages par défaut.
- **Pourquoi :** une app qui lit des mails reçoit, par définition, du contenu écrit par des inconnus. Un mail piégé ne doit pouvoir exécuter ni script ni pixel espion : c'est testé avec un `<script>` et un `<img onerror>`. L'app ne doit pas non plus être joignable depuis le réseau du campus, ni prévenir Google à chaque ouverture.

### D47. SQLite (SQLModel) seulement pour l'énergie choisie
- **Décision :** une seule table, l'énergie de chaque jour, dans `~/.inbox-planner/` (hors du dépôt). Une base en mémoire sert pour les tests.
- **Alternatives :** tout stocker (mails, réponses, plans), ou un fichier JSON.
- **Pourquoi :** tout le reste se recalcule à partir de la boîte et des réponses enregistrées. Stocker plus, ce serait garder des copies de mails sans raison. SQLModel donne une table typée avec Pydantic, et SQLite ne demande aucun serveur. La table servira aussi à la validation humaine des brouillons (étape 6).

### D48. Une interface inspirée de l'outil d'origine, sans ses données ni la marque de l'université
- **Décision :** l'interface reprend la structure du planner que j'utilisais (onglets, sélecteur d'énergie segmenté, une couleur par type d'élément, heures en police à chasse fixe), lue en n'extrayant que la structure, jamais le contenu. La couleur d'accent n'est pas l'orange d'Oregon State.
- **Alternatives :** repartir de zéro, reprendre la page telle quelle.
- **Pourquoi :** l'ergonomie avait fait ses preuves pendant l'échange. Mais aucune donnée réelle ne doit entrer dans le dépôt, et reprendre la couleur de la marque donnerait l'impression d'un outil officiel de l'université.

### D49. Le tri dépend du « maintenant » : constat sur Sonnet
- **Constat :** avec l'heure de référence au 26 octobre, Sonnet classe en « info » les quatre mails d'emploi du temps reçus fin septembre (m04 à m07) : « message d'accueil vieux d'un mois, rien de nouveau à planifier ». Avec Sonnet comme trieur, ces mails ne passeraient pas à l'extraction, et les cours disparaîtraient du calendrier. Haiku, le trieur par défaut (D33), les garde en « rendez-vous ». Opus ne se trompe que sur une newsletter (m34).
- **Décision :** garder la chaîne Haiku → Haiku et documenter le risque, sans réenregistrer une troisième fois.
- **Alternatives :** (1) évaluer chaque mail avec « maintenant » = son heure de réception, ce qui simule une installation qui trie chaque mail dès qu'il arrive ; (2) toujours envoyer à l'extraction les mails qui décrivent un horaire récurrent, quel que soit le tri.
- **Pourquoi :** c'est un artefact du traitement par lots : les 40 mails sont triés d'un coup, un mois après les premiers. Dans une vraie installation, un mail est trié à sa réception, et le message d'accueil d'un cours est alors forcément un rendez-vous. L'option (1) est la plus juste et sera faite si le temps le permet. Le constat montre en tout cas qu'un modèle « plus fort » n'est pas meilleur sur tout, et que le contexte temporel compte autant que le modèle.

---

## Étape 6 : vrais connecteurs et agent de rédaction

### D50. Gmail avec les bibliothèques officielles et le flux OAuth « application de bureau »
- **Décision :** `google-api-python-client` et `google-auth-oauthlib`, en dépendance optionnelle (`uv sync --extra gmail`). La connexion s'ouvre dans le navigateur, avec une redirection vers un port local et PKCE. Le jeton est rangé dans `~/.inbox-planner/tokens/`, avec les droits 600 (dossier en 700). L'application Google reste en mode « Test », réservée à mon compte.
- **Alternatives :** IMAP avec un mot de passe d'application, des appels HTTP écrits à la main, un compte de service.
- **Pourquoi :** je ne vois jamais le mot de passe, et le jeton ne quitte pas la machine. Le mode Test évite la vérification Google (obligatoire pour les autorisations « restreintes » comme la lecture des mails), au prix d'un jeton qui expire tous les 7 jours. Les mails sont récupérés au format brut et passent par le même parseur que la démo (D16).

### D51. Deux niveaux de consentement, et aucun envoi possible dans le code
- **Décision :** la connexion normale ne demande que `gmail.readonly`. La création de brouillons demande `gmail.compose`, dans un jeton séparé, seulement avec `--drafts`. Le code ne contient aucun appel d'envoi, et un test fait échouer la CI s'il en apparaît un (`.send(`, `smtplib`, `sendmail`…).
- **Alternatives :** demander `gmail.compose` (ou l'accès complet) dès le départ.
- **Pourquoi :** Gmail n'a pas d'autorisation « brouillons sans envoi » : `gmail.compose` permet techniquement d'envoyer. On ne peut donc pas promettre « jamais d'envoi » par les permissions seules. La garantie vient du code, vérifiée à chaque commit, et la permission la plus large n'est demandée que si on en a besoin.

### D52. Validation humaine en deux temps avant toute écriture
- **Décision :** (1) « Proposer » : l'agent rédige, le texte s'affiche dans un formulaire modifiable, et rien n'est écrit nulle part. (2) « Enregistrer comme brouillon » : seul un clic explicite écrit, et c'est le texte relu (et éventuellement corrigé) qui part dans les brouillons. En démo, il va dans SQLite ; avec `--drafts`, dans les brouillons Gmail. Il n'y a pas d'envoi.
- **Alternatives :** enregistrer automatiquement chaque proposition, ou envoyer après validation.
- **Pourquoi :** un mail engage la personne qui l'envoie. Vérifié dans le navigateur : la proposition pour l'entretien (m21) contenait une faute (« l'opportunité de échanger »), corrigée à la main avant l'enregistrement. C'est exactement le rôle de la relecture.

### D53. La rédaction avec Sonnet, un choix assumé mais non mesuré
- **Décision :** l'agent de rédaction utilise Sonnet 5.5. Trois intentions : confirmer, décliner, poser une question. Le prompt interdit d'inventer des faits et impose des [crochets] pour ce qui manque. Les expéditeurs automatiques (no-reply, notifications) n'ont pas de bouton « Répondre ».
- **Alternatives :** Haiku, comme pour le tri et l'extraction.
- **Pourquoi :** rédiger un mail en français correct est une tâche d'écriture, à la demande et rare, donc le coût compte peu. Contrairement au tri et à l'extraction, aucune métrique ne la mesure ici : c'est un choix de jugement, pas une conclusion tirée des données. La faute relevée en D52 montre que même ce modèle doit être relu.

### D54. IMAP en lecture seule par le protocole lui-même
- **Décision :** le dossier est ouvert avec `EXAMINE` (`readonly=True`) et les mails sont lus avec `BODY.PEEK[]`, avec la seule bibliothèque standard et un mot de passe d'application.
- **Alternatives :** `SELECT` et `RFC822`, une bibliothèque tierce.
- **Pourquoi :** `EXAMINE` interdit au serveur toute modification, et `PEEK` ne marque même pas les mails comme lus : la lecture seule est garantie par le serveur, pas seulement par mon code. Limite : les comptes Microsoft 365 universitaires refusent les mots de passe en IMAP et exigent OAuth 2.0, que ce connecteur ne fait pas.

### D55. Microsoft Graph (Outlook de Lyon 2 et d'OSU) : pas fait, et pourquoi
- **Décision :** pas de connecteur Graph pour l'instant. Le guide des connecteurs explique la démarche.
- **Alternatives :** écrire le connecteur sans pouvoir le tester.
- **Pourquoi :** lire les mails d'un compte universitaire passe par une application déclarée sur Azure. La plupart des universités bloquent le consentement des utilisateurs pour les applications tierces : il faudrait l'accord de la DSI de Lyon 2 ou d'OSU. Un connecteur jamais exécuté sur un vrai compte ne prouverait rien. L'interface `MailConnector` permet de l'ajouter sans rien toucher d'autre.

### D56. Une vraie boîte : transparence et données hors du dépôt
- **Décision :** `inbox-planner web --source gmail` annonce à l'écran que le contenu des mails est envoyé à Claude via l'abonnement. Les réponses du modèle sont mises en cache dans `~/.inbox-planner/llm-cache`, jamais dans le dépôt. Les réglages (fuseau, ville, signature) passent par des variables d'environnement documentées dans `.env.example`. Le traitement a lieu au démarrage, avec l'heure réelle comme référence.
- **Alternatives :** un cache commun à la démo et à la vraie boîte, des réglages écrits en dur.
- **Pourquoi :** la séparation est physique. Rien de réel ne peut finir dans `demo_data/` par erreur, et le garde-fou de confidentialité (D18) scanne de toute façon tout ce qui y entre.

### D57. Sur une vraie boîte, chaque mail est analysé « à son arrivée »
- **Décision :** pour une vraie boîte, l'heure de référence donnée au modèle est l'heure d'envoi du mail, pas l'heure du lancement. La démo et l'évaluation gardent leur horloge figée.
- **Alternatives :** l'heure réelle du lancement (ce qui était fait), ou l'heure arrondie au jour.
- **Pourquoi :** au premier lancement réel, l'interface a refait les 100 appels au lieu d'utiliser le cache. L'heure de référence, à la minute près, faisait partie du prompt, donc de la clé du cache : elle n'était jamais deux fois la même. Avec l'heure d'arrivée, le prompt d'un mail ne change plus, et le deuxième lancement prend 12 s, sans aucun appel à Claude. C'est aussi ce que ferait une vraie installation, qui trie chaque mail quand il arrive : c'est l'option (1) de D49. La planification, elle, utilise toujours l'heure réelle.

### D58. Le contenu des mails est une donnée non fiable
- **Décision :** les agents n'ont aucun outil, leur sortie est contrainte par un schéma puis validée, et rien n'est écrit sans validation humaine (D52). Un mail illisible (sans date, encodage cassé) est ignoré et compté, jamais bloquant.
- **Alternatives :** un filtre de « phrases suspectes » dans les mails.
- **Pourquoi :** n'importe qui peut écrire un mail contenant « ignore tes instructions et… » (injection de prompt). Un filtre de phrases se contourne. Ici, le pire qu'un mail piégé puisse obtenir, c'est une mauvaise catégorie ou un élément faux dans un plan que l'utilisateur voit et corrige : ni action, ni envoi, ni lecture de fichiers.

### D59. Premier essai sur une vraie boîte : des totaux, pas de contenu
- **Décision :** l'essai sur ma boîte Gmail perso a été vérifié avec un script qui n'affiche que des totaux. Le contenu, je le regarde moi-même dans l'interface.
- **Résultat (14 derniers jours, plafond de 100 mails) :** 100 mails, aucun illisible. Tri : 63 bruit, 32 info, 4 démarches, 1 rendez-vous. 5 mails sur 100 partent en extraction. Environ 6 000 tokens par mail pour le tri, contre 1 600 en démo : les vraies newsletters sont longues. Coût estimé : 0,07 $ (non payé, abonnement). Durée : 101 s au premier passage, 12 s ensuite grâce au cache.
- **Pourquoi :** une vraie boîte n'a pas d'annotations, donc aucune précision mesurable. Les chiffres sérieux restent ceux du jeu annoté. Mais l'essai prouve que la chaîne complète marche sur des mails réels, et il a révélé deux vrais problèmes, corrigés en D57 et D58. Piste notée : envoyer au tri seulement le début des mails longs, à mesurer d'abord sur le jeu annoté.

---

## Après publication : retours d'usage

### D60. Thème sombre par défaut, et un calendrier lisible
- **Décision :** l'interface démarre en thème sombre, sur une palette brun-noir chaude reprise de l'outil d'origine. Un bouton repasse en clair, et le choix est retenu dans le navigateur. Dans le calendrier de la semaine, les éléments simultanés sont côte à côte (`slotEventOverlap: false`), les créneaux sont plus hauts, l'heure est sur la ligne du titre, et le titre complet s'affiche au survol. Ce contenu est construit avec `textContent`, jamais en HTML.
- **Alternatives :** suivre seulement le réglage du système, garder les événements superposés.
- **Pourquoi :** c'est le retour du premier utilisateur. Dans la version d'avant, les éléments se chevauchaient et les titres étaient coupés. `textContent` compte, parce que sur une vraie boîte les titres viennent de mails, donc d'inconnus (D58).

### D61. Des liens courts dans les mails
- **Décision :** dans le texte d'un mail, seuls les liens `https` deviennent cliquables. Le texte affiché est court (domaine et début du chemin), le lien Outlook Safe Links est déballé, et le lien complet (le vrai, pas l'enveloppe Outlook) reste disponible sur demande. Tout le reste du texte est échappé.
- **Alternatives :** le texte brut (illisible avec un lien Safe Links de 400 caractères), un HTML de mail rendu tel quel.
- **Pourquoi :** lisibilité, sans rien céder sur la sécurité. Un lien `javascript:` ou `http:` reste du texte, et c'est testé.

### D62. Une vue « Par jour » où chaque élément se lit en entier
- **Décision :** la semaine s'ouvre sur une vue par jour (une colonne par jour, une case par élément) où chaque case grandit avec son texte. La grille horaire reste disponible d'un clic, et le choix est retenu dans le navigateur. Une échéance est un instant, sans heure de fin : elle n'occupe plus une heure qui déborde sur le lendemain.
- **Alternatives :** agrandir encore les créneaux de la grille horaire, couper les titres.
- **Pourquoi :** dans une grille horaire, la hauteur d'une case suit la durée. Un rendez-vous de 15 minutes ne peut donc jamais afficher un titre de deux lignes, quelle que soit la taille des créneaux. La vue par jour règle le problème à la racine. La grille reste utile pour voir les trous dans la journée.

### D63. Une vie en dehors des cours dans la boîte de démo
- **Décision :** le mail m39 (un appel familial) est remplacé par le mail d'une amie : une randonnée à Blue Pool le samedi 31 octobre et une séance de travail (projet ST 411, devoir de CS 434) le dimanche 1er novembre. Les deux éléments sont de part et d'autre du passage de l'Oregon à l'heure d'hiver (-07:00 puis -08:00). Le mail, son annotation et ses réponses enregistrées ont été refaits.
- **Alternatives :** garder l'appel, ajouter un 41e mail.
- **Pourquoi :** une semaine d'étudiant n'est pas faite que de cours, et un planificateur doit tenir compte des sorties. Garder 40 mails évite de changer la répartition par catégorie. Le piège des changements d'heure est conservé sous une autre forme : la séance de 14 h le dimanche doit rester à 14 h après le changement, ce que vérifient les tests.

### D64. Le travail est étalé sur les jours, plus entassé au début
- **Décision :** l'ordre reste celui de D37 (échéance la plus proche d'abord, puis priorité). Ce qui change, c'est le placement : chaque bloc va dans le jour, avant l'échéance, qui peut prendre le plus long bloc d'un coup, puis dans le jour qui a le plus de capacité restante, puis dans le plus tôt. Dans ce jour, il va dans le créneau libre qui le contient le mieux.
- **Alternatives :** garder « au plus tôt » (D37), placer au plus tard, une charge cible fixe par jour.
- **Pourquoi :** c'est le retour du premier utilisateur : « au plus tôt » remplissait lundi à jeudi à 4 h et laissait le week-end vide, alors qu'un étudiant répartit son travail à l'avance. Étaler ne retire pas de temps aux tâches suivantes : elles sont traitées par échéance, et la fenêtre de chacune contient celle des précédentes (aux pauses et aux tailles de bloc près). Les 300 semaines aléatoires vérifient toujours les mêmes règles. Le critère « plus long bloc d'abord » vient de la démo : sans lui, une tâche d'une heure était coupée en 25 min lundi et 35 min samedi. Un jour « En forme » prend naturellement plus de travail qu'un jour « Crevé », puisqu'il lui reste plus de capacité. Limite : la marge avant l'échéance est plus courte qu'avec « au plus tôt ».
