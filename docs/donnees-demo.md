# Données de démo : ce qui est réel, ce qui est inventé

La boîte mail de démo (`src/inbox_planner/demo_data/mailbox.toml`) raconte un échange universitaire entre Lyon et l'Oregon. Aucun mail réel n'a été utilisé : chaque message a été écrit pour ce projet.

| Élément | Statut | Détail |
|---|---|---|
| Écoles | **Réel** | Université Lumière Lyon 2, IUT Lumière, BUT Science des données ; Oregon State University (Corvallis, Oregon). |
| Codes et intitulés des cours OSU | **Réel, à vérifier** | Tirés du catalogue public d'OSU. Le catalogue (catalog.oregonstate.edu) était hors service le 25/11/2026 : les intitulés seront revérifiés avant la fusion de l'étape 2. |
| Étudiante (Camille Roux), profs, conseillers, tuteurs | Inventé | Toute ressemblance avec une personne réelle serait fortuite. |
| Adresses mail | Inventé | Uniquement des domaines `.example`, réservés par la RFC 2606 : ils ne pointent vers aucun serveur. Vérifié automatiquement par `tests/test_demo_privacy.py`. |
| Bâtiments et salles | Inventé | Aucun bâtiment réel du campus d'OSU. |
| Dates, horaires, échéances | Inventé | Cohérents avec l'automne 2026 et les vrais changements d'heure (25 octobre en Europe, 1er novembre aux États-Unis). |
| Liens de visio (Zoom, Teams, Meet) | Inventé | Format réel pour tester l'extraction, mais identifiants, codes et mots de passe inventés : aucune réunion n'existe. |
| Entreprises, commerces, newsletters | Inventé | Noms et domaines fictifs. |
| Démarches (I-20, ENT, alternance…) | Générique | Noms courants de démarches réelles, contenu inventé. |

## Cours OSU utilisés

| Code | Intitulé | Statut |
|---|---|---|
| ST 411 | Methods of Data Analysis | À vérifier dans le catalogue |
| ST 421 | Introduction to Mathematical Statistics | À vérifier dans le catalogue |
| CS 340 | Introduction to Databases | À vérifier dans le catalogue |
| CS 434 | Machine Learning and Data Mining | À vérifier dans le catalogue |

Les horaires, salles, bâtiments (Alder Hall, Hemlock Hall, Larchmont Hall, Fernwood Center, Cypress Auditorium, Juniper Student Center) et enseignants de ces cours sont inventés.
