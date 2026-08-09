"""
IPGEI Nouakchott - Plateforme de consultation des résultats MPSI
-----------------------------------------------------------------
Flask + SQLite (module standard sqlite3) + import Excel/CSV pour l'administration.
"""

import os
import sqlite3
from datetime import datetime

import pandas as pd
from flask import (
    Flask, render_template, request, redirect,
    url_for, session, flash, g
)
from werkzeug.utils import secure_filename

# ----------------------------------------------------------------------
# Configuration
# ----------------------------------------------------------------------
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DB_PATH = os.path.join(BASE_DIR, 'ipgei.db')

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'change-moi-en-production')
app.config['UPLOAD_FOLDER'] = os.path.join(BASE_DIR, 'uploads')
app.config['MAX_CONTENT_LENGTH'] = 5 * 1024 * 1024  # 5 Mo

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Mot de passe admin (à changer / à définir via variable d'environnement sur Render)
ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD', 'ipgei2026')

# ----------------------------------------------------------------------
# Matières et coefficients MPSI (modifiable selon le programme réel)
# ----------------------------------------------------------------------
MATIERES = {
    'maths':          {'label': 'Mathématiques',        'coef': 9},
    'physique':       {'label': 'Physique',              'coef': 5},
    'chimie':         {'label': 'Chimie',                 'coef': 2},
    'sii':            {'label': 'SII',                    'coef': 4},
    'informatique':   {'label': 'Informatique',           'coef': 2},
    'francais_philo': {'label': 'Français / Philosophie', 'coef': 2},
    'anglais':        {'label': 'Anglais',                'coef': 2},
}
TOTAL_COEF = sum(m['coef'] for m in MATIERES.values())
NIVEAUX = ['MPSI 1', 'MPSI 2']


# ----------------------------------------------------------------------
# Connexion base de données (sqlite3 standard)
# ----------------------------------------------------------------------
def get_db():
    if 'db' not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
    return g.db


@app.teardown_appcontext
def close_db(exception=None):
    db = g.pop('db', None)
    if db is not None:
        db.close()


def init_db():
    db = sqlite3.connect(DB_PATH)
    colonnes_notes = ", ".join(f"note_{cle} REAL" for cle in MATIERES)
    db.execute(f"""
        CREATE TABLE IF NOT EXISTS etudiants (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            numero_inscription TEXT UNIQUE NOT NULL,
            nom TEXT NOT NULL,
            prenom TEXT,
            niveau TEXT NOT NULL,
            {colonnes_notes},
            decision_manuelle TEXT,
            date_import TEXT
        )
    """)
    db.commit()
    db.close()


# ----------------------------------------------------------------------
# Fonctions utilitaires calcul moyenne / décision
# ----------------------------------------------------------------------
def moyenne_generale(etudiant_row):
    somme_points = 0.0
    somme_coefs = 0
    for cle, infos in MATIERES.items():
        note = etudiant_row[f'note_{cle}']
        if note is not None:
            somme_points += note * infos['coef']
            somme_coefs += infos['coef']
    if somme_coefs == 0:
        return None
    return round(somme_points / somme_coefs, 2)


def calculer_decision(etudiant_row, moyenne):
    if etudiant_row['decision_manuelle']:
        return etudiant_row['decision_manuelle']
    if moyenne is None:
        return "Notes incomplètes"
    if etudiant_row['niveau'] == 'MPSI 1':
        return "Admis en MPSI 2" if moyenne >= 10 else "Non admis en MPSI 2"
    else:
        return "Admissible aux concours" if moyenne >= 10 else "Non admissible"


# ----------------------------------------------------------------------
# Routes publiques
# ----------------------------------------------------------------------
@app.route('/')
def index():
    return render_template('index.html', niveaux=NIVEAUX)


@app.route('/resultats', methods=['GET', 'POST'])
def resultats():
    if request.method == 'POST':
        niveau = request.form.get('niveau', '').strip()
        identifiant = request.form.get('identifiant', '').strip()
    else:
        niveau = request.args.get('niveau', '').strip()
        identifiant = request.args.get('identifiant', '').strip()

    if not niveau or not identifiant:
        flash("Merci de renseigner le niveau et votre numéro d'inscription ou votre nom.", "warning")
        return redirect(url_for('index'))

    db = get_db()
    etudiant = db.execute(
        """SELECT * FROM etudiants
           WHERE niveau = ?
           AND (numero_inscription = ? OR nom LIKE ?)
           LIMIT 1""",
        (niveau, identifiant, f"%{identifiant}%")
    ).fetchone()

    if not etudiant:
        flash("Aucun résultat trouvé pour ces informations. Vérifiez le niveau et le numéro/nom saisi.", "danger")
        return redirect(url_for('index'))

    notes = {cle: etudiant[f'note_{cle}'] for cle in MATIERES}
    moyenne = moyenne_generale(etudiant)
    decision = calculer_decision(etudiant, moyenne)

    return render_template(
        'resultats.html',
        etudiant=etudiant,
        matieres=MATIERES,
        notes=notes,
        moyenne=moyenne,
        decision=decision,
        total_coef=TOTAL_COEF,
    )


# ----------------------------------------------------------------------
# Espace administration
# ----------------------------------------------------------------------
def admin_connecte():
    return session.get('admin_ok', False)


@app.route('/admin', methods=['GET', 'POST'])
def admin_login():
    if admin_connecte():
        return redirect(url_for('admin_panel'))

    if request.method == 'POST':
        mot_de_passe = request.form.get('mot_de_passe', '')
        if mot_de_passe == ADMIN_PASSWORD:
            session['admin_ok'] = True
            return redirect(url_for('admin_panel'))
        flash("Mot de passe incorrect.", "danger")

    return render_template('admin_login.html')


@app.route('/admin/logout')
def admin_logout():
    session.pop('admin_ok', None)
    return redirect(url_for('index'))


@app.route('/admin/panel', methods=['GET', 'POST'])
def admin_panel():
    if not admin_connecte():
        return redirect(url_for('admin_login'))

    if request.method == 'POST':
        fichier = request.files.get('fichier')
        if not fichier or fichier.filename == '':
            flash("Merci de sélectionner un fichier Excel (.xlsx) ou CSV (.csv).", "warning")
            return redirect(url_for('admin_panel'))

        nom_fichier = secure_filename(fichier.filename)
        chemin = os.path.join(app.config['UPLOAD_FOLDER'], nom_fichier)
        fichier.save(chemin)

        try:
            nb_importes, nb_erreurs = importer_fichier(chemin)
            flash(f"{nb_importes} étudiant(s) importé(s) avec succès. "
                  f"{nb_erreurs} ligne(s) ignorée(s) (données invalides).", "success")
        except Exception as exc:
            flash(f"Erreur lors de l'import : {exc}", "danger")
        finally:
            if os.path.exists(chemin):
                os.remove(chemin)

        return redirect(url_for('admin_panel'))

    db = get_db()
    total_etudiants = db.execute("SELECT COUNT(*) AS n FROM etudiants").fetchone()['n']
    derniers = db.execute(
        "SELECT * FROM etudiants ORDER BY date_import DESC LIMIT 10"
    ).fetchall()
    return render_template('admin_panel.html', total=total_etudiants, derniers=derniers)


def importer_fichier(chemin):
    """Lit un fichier Excel/CSV et met à jour (ou crée) les étudiants correspondants."""
    if chemin.lower().endswith('.csv'):
        df = pd.read_csv(chemin)
    else:
        df = pd.read_excel(chemin)

    df.columns = [str(c).strip().lower() for c in df.columns]

    colonnes_requises = {'numero_inscription', 'nom', 'niveau'}
    if not colonnes_requises.issubset(set(df.columns)):
        manquantes = colonnes_requises - set(df.columns)
        raise ValueError(f"Colonnes manquantes dans le fichier : {', '.join(manquantes)}")

    db = get_db()
    nb_importes = 0
    nb_erreurs = 0

    colonnes_notes = [f'note_{cle}' for cle in MATIERES]

    for _, ligne in df.iterrows():
        try:
            numero = str(ligne['numero_inscription']).strip()
            nom = str(ligne['nom']).strip()
            niveau = str(ligne['niveau']).strip()

            if not numero or not nom or niveau not in NIVEAUX:
                nb_erreurs += 1
                continue

            prenom = str(ligne.get('prenom', '') or '').strip() or None
            decision_manuelle = None
            if 'decision' in df.columns and pd.notna(ligne.get('decision')):
                decision_manuelle = str(ligne['decision']).strip()

            valeurs_notes = {}
            for colonne in colonnes_notes:
                if colonne in df.columns and pd.notna(ligne.get(colonne)):
                    valeurs_notes[colonne] = float(ligne[colonne])
                else:
                    valeurs_notes[colonne] = None

            existant = db.execute(
                "SELECT id FROM etudiants WHERE numero_inscription = ?", (numero,)
            ).fetchone()

            if existant:
                set_clause = ", ".join(f"{c} = ?" for c in colonnes_notes)
                db.execute(
                    f"""UPDATE etudiants SET nom = ?, prenom = ?, niveau = ?,
                        {set_clause}, decision_manuelle = ?, date_import = ?
                        WHERE numero_inscription = ?""",
                    [nom, prenom, niveau] + [valeurs_notes[c] for c in colonnes_notes] +
                    [decision_manuelle, datetime.utcnow().isoformat(), numero]
                )
            else:
                colonnes_sql = ["numero_inscription", "nom", "prenom", "niveau"] + colonnes_notes + \
                                ["decision_manuelle", "date_import"]
                placeholders = ", ".join("?" * len(colonnes_sql))
                valeurs = [numero, nom, prenom, niveau] + [valeurs_notes[c] for c in colonnes_notes] + \
                          [decision_manuelle, datetime.utcnow().isoformat()]
                db.execute(
                    f"INSERT INTO etudiants ({', '.join(colonnes_sql)}) VALUES ({placeholders})",
                    valeurs
                )

            nb_importes += 1
        except Exception:
            nb_erreurs += 1
            continue

    db.commit()
    return nb_importes, nb_erreurs


# ----------------------------------------------------------------------
# Initialisation
# ----------------------------------------------------------------------
init_db()


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
