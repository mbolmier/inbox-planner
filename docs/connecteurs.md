# Connecteurs : brancher une vraie boîte mail

La démo n'a besoin d'aucun compte. Ce guide sert à brancher **ta** boîte. Tout ce qui est réel reste dans `~/.inbox-planner/` (jetons, fichier client, cache des réponses), jamais dans le dépôt.

## Gmail (lecture, brouillons en option)

### 1. Créer l'accès sur Google Cloud (une fois, gratuit)
1. Sur [console.cloud.google.com](https://console.cloud.google.com), crée un projet `inbox-planner`.
2. **API et services → Bibliothèque → Gmail API → Activer.**
3. **Google Auth Platform** :
   - **Branding :** le nom de l'app et ton adresse Gmail.
   - **Audience :** externe, statut **En test**, et ton adresse Gmail comme utilisateur de test.
   - **Accès aux données :** `gmail.readonly`, plus `gmail.compose` si tu veux les brouillons.
4. **Clients → Créer un client**, type **Application de bureau**. Télécharge le JSON.
5. Range-le hors du dépôt :
   ```bash
   mkdir -p ~/.inbox-planner && mv ~/Downloads/client_secret_*.json ~/.inbox-planner/google-client-secret.json
   ```
   ```bash
   chmod 600 ~/.inbox-planner/google-client-secret.json
   ```

En mode « Test », Google ne demande pas de vérification, mais le jeton expire au bout de 7 jours : il suffit alors de se reconnecter.

### 2. Se connecter
```bash
uv sync --extra gmail
```
```bash
uv run inbox-planner gmail login
```
Ton navigateur s'ouvre et tu acceptes la **lecture seule**. Pour autoriser aussi les brouillons (consentement séparé) :
```bash
uv run inbox-planner gmail login --drafts
```

### 3. Utiliser
```bash
uv run --env-file .env inbox-planner web --source gmail
```
Ajoute `--drafts` pour que « Enregistrer comme brouillon » écrive dans tes brouillons Gmail. Sans cette option, les brouillons restent sur ton ordinateur.

**Ce qui se passe :** les mails des 14 derniers jours sont lus, puis envoyés à Claude via `claude -p`, avec ton abonnement, pour le tri et l'extraction. Les réponses sont gardées dans `~/.inbox-planner/llm-cache`.

**Ce qui ne se passe jamais :** l'envoi d'un mail. Gmail n'a pas d'autorisation « brouillons sans envoi » (`gmail.compose` permettrait d'envoyer), mais le code ne contient aucun appel d'envoi, et un test le vérifie à chaque commit.

## IMAP (lecture seule garantie par le serveur)
Le dossier est ouvert avec `EXAMINE` et les mails sont lus avec `BODY.PEEK[]` : rien n'est modifié, et rien n'est même marqué comme lu. Il faut un **mot de passe d'application** (Gmail, iCloud, Outlook.com…). Le connecteur existe (`ImapConnector`) mais n'est pas encore branché à la commande `web`.

## Outlook / Microsoft 365 (Lyon 2, Oregon State)
Ce n'est pas fait (voir la décision D55). Les comptes universitaires refusent les mots de passe en IMAP, et l'accès par Microsoft Graph demande une application Azure, que les universités bloquent souvent sans l'accord de leur DSI.
