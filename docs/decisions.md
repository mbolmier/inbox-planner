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
