# Données de démo : ce qui est réel, ce qui est inventé

La boîte mail de démo (`src/inbox_planner/demo_data/mailbox.toml`) raconte un échange universitaire entre Lyon et l'Oregon. Aucun mail réel n'a été utilisé : chaque message a été écrit pour ce projet.

| Élément | Statut | Détail |
|---|---|---|
| Écoles | **Réel** | Université Lumière Lyon 2, IUT Lumière, BUT Science des données ; Oregon State University (Corvallis, Oregon). |
| Codes et intitulés des cours OSU | **Réel, vérifié** | Vérifiés dans le catalogue public d'OSU (catalog.oregonstate.edu) le 25/11/2026. |
| Étudiante (Camille Roux), amie (Margaux Delorme), profs, conseillers, tuteurs | Inventé | Toute ressemblance avec une personne réelle serait fortuite. |
| Adresses mail | Inventé | Uniquement des domaines `.example`, réservés par la RFC 2606 : ils ne pointent vers aucun serveur. Vérifié automatiquement par `tests/test_demo_privacy.py`. |
| Bâtiments et salles | Inventé | Aucun bâtiment réel du campus d'OSU. |
| Lieux hors campus | **Réel** | Corvallis (ville) et Tamolitch Blue Pool (sentier de randonnée public sur la McKenzie River, mail m39). Seuls les noms sont utilisés ; la sortie, les horaires et les participantes sont inventés. |
| Dates, horaires, échéances | Inventé | Cohérents avec l'automne 2026 et les vrais changements d'heure (25 octobre en Europe, 1er novembre aux États-Unis). |
| Liens de visio (Zoom, Teams, Meet) | Inventé | Format réel pour tester l'extraction, mais identifiants, codes et mots de passe inventés : aucune réunion n'existe. |
| Entreprises, commerces, newsletters | Inventé | Noms et domaines fictifs. |
| Démarches (I-20, ENT, alternance…) | Générique | Noms courants de démarches réelles, contenu inventé. |

## Cours OSU utilisés

| Code | Intitulé | Statut |
|---|---|---|
| ST 411 | Methods of Data Analysis | Vérifié (4 crédits) |
| ST 421 | Introduction to Mathematical Statistics | Vérifié (4 crédits) |
| CS 340 | Introduction to Databases | Vérifié (4 crédits) |
| CS 434 | Machine Learning and Data Mining | Vérifié (4 crédits) |

Les horaires, salles, bâtiments (Alder Hall, Hemlock Hall, Larchmont Hall, Fernwood Center, Cypress Auditorium, Juniper Student Center) et enseignants de ces cours sont inventés.
