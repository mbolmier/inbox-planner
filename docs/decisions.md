# Journal des décisions

Chaque décision tient en trois lignes : ce qu'on a choisi, ce qu'on aurait pu faire, et pourquoi. Les plus récentes sont en bas.

---

## Étape 1 : socle

### D1. Écrire le `.gitignore` avant le premier commit
- **Décision :** `.env`, jetons OAuth, bases SQLite, exports de mails réels (`.eml`, `.mbox`, `.pst`), `CLAUDE.md` et `.claude/` sont ignorés dès le départ. Les `.eml` ne sont autorisés que dans `data/demo/`.
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
