# IPGEI Nouakchott — Plateforme de résultats MPSI

Application Flask + SQLite pour la consultation en ligne des résultats des
étudiants MPSI 1 et MPSI 2 de l'IPGEI.

## Structure du projet

```
ipgei/
├── app.py                  # Application Flask (routes, logique, import)
├── requirements.txt        # Dépendances Python
├── Procfile                # Commande de lancement pour Render/Heroku
├── .gitignore
├── ipgei.db                 # Base SQLite (créée automatiquement au 1er lancement)
├── templates/
│   ├── base.html            # Gabarit commun (Bootstrap 5)
│   ├── index.html           # Page d'accueil / recherche
│   ├── resultats.html       # Relevé de notes de l'étudiant
│   ├── admin_login.html     # Connexion admin
│   └── admin_panel.html     # Import Excel/CSV + statistiques
├── static/
│   └── css/
└── uploads/                 # Dossier temporaire pour les fichiers importés
```

## Lancer le projet en local

```bash
python3 -m venv venv
source venv/bin/activate        # Windows : venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

L'application est accessible sur http://127.0.0.1:5000

- Mot de passe admin par défaut : `ipgei2026` (variable d'environnement `ADMIN_PASSWORD`)
- Base de données : `ipgei.db` (créée automatiquement)

## Format du fichier d'import (Excel ou CSV)

Colonnes attendues (voir `modele_resultats_MPSI.xlsx` fourni) :

| Colonne | Obligatoire | Description |
|---|---|---|
| numero_inscription | Oui | Identifiant unique de l'étudiant |
| nom | Oui | Nom de l'étudiant |
| prenom | Non | Prénom |
| niveau | Oui | `MPSI 1` ou `MPSI 2` exactement |
| note_maths | Non | Note sur 20 |
| note_physique | Non | Note sur 20 |
| note_chimie | Non | Note sur 20 |
| note_sii | Non | Note sur 20 |
| note_informatique | Non | Note sur 20 |
| note_francais_philo | Non | Note sur 20 |
| note_anglais | Non | Note sur 20 |
| decision | Non | Si vide, calculée automatiquement (moyenne ≥ 10) |

Réimporter un fichier avec le même `numero_inscription` met à jour l'étudiant existant.

## Déploiement gratuit sur Render

1. **Créer un dépôt Git** (GitHub/GitLab) contenant tous les fichiers du projet
   (y compris `Procfile` et `requirements.txt`), puis pousser le code :
   ```bash
   git init
   git add .
   git commit -m "Première version - plateforme résultats MPSI"
   git branch -M main
   git remote add origin <URL_DE_VOTRE_DEPOT>
   git push -u origin main
   ```

2. **Créer un compte sur https://render.com** (gratuit, connexion possible via GitHub).

3. Cliquer sur **New +** → **Web Service**, puis sélectionner votre dépôt GitHub.

4. Configurer le service :
   - **Name** : `ipgei-resultats` (ou autre)
   - **Region** : la plus proche (Europe par exemple)
   - **Branch** : `main`
   - **Runtime** : Python 3
   - **Build Command** : `pip install -r requirements.txt`
   - **Start Command** : `gunicorn app:app`
   - **Instance Type** : `Free`

5. Dans l'onglet **Environment**, ajouter les variables :
   - `SECRET_KEY` = une longue chaîne aléatoire
   - `ADMIN_PASSWORD` = le mot de passe admin que vous souhaitez utiliser

6. Cliquer sur **Create Web Service**. Render installe les dépendances et
   démarre l'application. Au bout de quelques minutes, vous obtenez un lien
   du type :
   ```
   https://ipgei-resultats.onrender.com
   ```
   C'est ce lien que vous partagez avec les étudiants.

### Remarque importante sur SQLite et Render (plan gratuit)

Sur le plan **Free** de Render, le système de fichiers est **éphémère** :
si le service redémarre ou se met en veille (après inactivité), le fichier
`ipgei.db` peut être réinitialisé et les données importées perdues.

Deux solutions :
- **Solution simple** : réimporter le fichier Excel/CSV des résultats après
  chaque redémarrage (acceptable si les résultats sont publiés une fois par
  session et consultés pendant une période courte).
- **Solution robuste (recommandée pour une utilisation durable)** : ajouter
  un **Render Disk** (persistant, disponible aussi sur le plan gratuit
  avec une limite de stockage) et faire pointer `DB_PATH` vers ce disque,
  ou migrer vers une base **PostgreSQL gratuite** proposée par Render
  (« New + » → « PostgreSQL »), ce qui nécessite d'adapter légèrement
  `app.py` (remplacer `sqlite3` par `psycopg2`/SQLAlchemy).

## Alternative : hébergement sur Vercel

Vercel est conçu pour des fonctions serverless et convient moins naturellement
à une application Flask avec état (base SQLite persistante). Si vous
souhaitez malgré tout utiliser Vercel, il faudra :
- adapter le projet avec un fichier `vercel.json` et exposer l'app via un
  handler serverless,
- utiliser une base de données externe (ex. **Supabase**, **PlanetScale**,
  **Neon**) plutôt que SQLite, car le système de fichiers de Vercel est
  également non persistant et en lecture seule à l'exécution.

**Render reste donc le choix le plus simple** pour ce type de projet Flask + SQLite.

## Sécurité — à faire avant une mise en production réelle

- Changer `ADMIN_PASSWORD` et `SECRET_KEY` (ne jamais garder les valeurs par défaut).
- Envisager un vrai système de compte administrateur (email + mot de passe haché)
  si plusieurs personnes doivent importer des résultats.
- Servir le site en HTTPS (Render le fait automatiquement).
