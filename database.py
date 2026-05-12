import requests
import pandas as pd

# -----------------------------------------------------------------------------
# CONFIGURATION SUPABASE
# -----------------------------------------------------------------------------
SUPABASE_URL = "https://wlonolzfkhlyxbojprus.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Indsb25vbHpma2hseXhib2pwcnVzIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NjQyMjY2ODEsImV4cCI6MjA3OTgwMjY4MX0.FwA0c6iwp3sYfI4zEj7xOK_wJKywA3QKmhY5CVM2XHU"

HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json"
}

# -----------------------------------------------------------------------------
# DÉFINITION GLOBALE DES COLONNES
# -----------------------------------------------------------------------------
COL_STANDARDS = ["Matériau", "Nom", "Longueur Barre (mm)", "Section A (mm)", "Section B (mm)", "Épaisseur (mm)", "Poids (kg/m)"]
COL_PROFILS = ["Nom", "Longueur Barre (mm)", "Section A (mm)", "Section B (mm)", "Épaisseur (mm)", "Poids (kg/m)", "Couleur", "Longueur Peinture (mm)"]
# AJOUT : "Coupe sur Section"
COL_LISTES = ["Référence", "Profil", "Longueur (mm)", "Quantité", "Coupe sur Section", "Angle Gauche (°)", "Angle Droite (°)", "Symétrique"]

# -----------------------------------------------------------------------------
# FONCTIONS UTILITAIRES INTERNES
# -----------------------------------------------------------------------------
def _requete_get(table):
    r = requests.get(f"{SUPABASE_URL}/rest/v1/{table}", headers=HEADERS)
    if r.status_code == 200:
        return r.json()
    else:
        raise Exception(f"Erreur de lecture ({table}) : {r.text}")

def _requete_delete(table, colonne, valeur):
    url = f"{SUPABASE_URL}/rest/v1/{table}?{colonne}=eq.{valeur}"
    r = requests.delete(url, headers=HEADERS)
    if r.status_code not in [200, 204]:
        raise Exception(f"Erreur suppression ({table}) : {r.text}")

def _requete_insert(table, data):
    if not data: return
    r = requests.post(f"{SUPABASE_URL}/rest/v1/{table}", headers=HEADERS, json=data)
    if r.status_code not in [200, 201]:
        raise Exception(f"Erreur insertion ({table}) : {r.text}")

# --- FORMATAGE SÉCURISÉ DES DONNÉES ---
def formater_df_standards(df):
    if df is None or df.empty: return pd.DataFrame(columns=COL_STANDARDS)
    df = df.copy()
    for col in COL_STANDARDS:
        if col not in df.columns: df[col] = None
    df["Matériau"] = df["Matériau"].fillna("").astype(str)
    df["Nom"] = df["Nom"].fillna("").astype(str)
    df["Longueur Barre (mm)"] = pd.to_numeric(df["Longueur Barre (mm)"], errors='coerce')
    df["Section A (mm)"] = pd.to_numeric(df["Section A (mm)"], errors='coerce')
    df["Section B (mm)"] = pd.to_numeric(df["Section B (mm)"], errors='coerce')
    df["Épaisseur (mm)"] = pd.to_numeric(df["Épaisseur (mm)"], errors='coerce')
    df["Poids (kg/m)"] = pd.to_numeric(df["Poids (kg/m)"], errors='coerce')
    df["Couleur"] = df["Couleur"].fillna("").astype(str)
    df["Longueur Peinture (mm)"] = pd.to_numeric(df["Longueur Peinture (mm)"], errors='coerce')
    return df

def formater_df_listes(df):
    if df is None or df.empty: return pd.DataFrame(columns=COL_LISTES)
    df = df.copy()
    for col in COL_LISTES:
        if col not in df.columns: df[col] = None
    df["Référence"] = df["Référence"].fillna("").astype(str)
    df["Profil"] = df["Profil"].fillna("").astype(str)
    df["Longueur (mm)"] = pd.to_numeric(df["Longueur (mm)"], errors='coerce')
    df["Quantité"] = pd.to_numeric(df["Quantité"], errors='coerce').astype('Int64')
    df["Coupe sur Section"] = df["Coupe sur Section"].fillna("A").astype(str) # NOUVEAU
    df["Angle Gauche (°)"] = pd.to_numeric(df["Angle Gauche (°)"], errors='coerce')
    df["Angle Droite (°)"] = pd.to_numeric(df["Angle Droite (°)"], errors='coerce')
    df["Symétrique"] = df["Symétrique"].fillna(False).astype(bool)
    return df

# -----------------------------------------------------------------------------
# L'API PUBLIQUE DU MODULE
# -----------------------------------------------------------------------------

def charger_donnees_initiales():
    try:
        db_standards = _requete_get("gp_debit_standards")
        db_projets = _requete_get("gp_debit_projets")
        db_profils = _requete_get("gp_debit_profils")
        db_pieces = _requete_get("gp_debit_pieces")
        
        if db_standards:
            std_data = [{"Matériau": r.get("materiau", ""), "Nom": r["nom_profil"], "Longueur Barre (mm)": r.get("longueur_barre"), "Section A (mm)": r.get("section_a"), "Section B (mm)": r.get("section_b"), "Épaisseur (mm)": r.get("epaisseur"), "Poids (kg/m)": r.get("poids_ml")} for r in db_standards]
            df_standards_base = formater_df_standards(pd.DataFrame(std_data))
        else:
            df_standards_base = pd.DataFrame(columns=COL_STANDARDS)
            
        workspace = {}
        if db_projets:
            for proj in db_projets:
                nom_p = proj["nom_projet"]
                
                prof_data = [{"Nom": p["nom_profil"], "Longueur Barre (mm)": p.get("longueur"), "Section A (mm)": p.get("section_a"), "Section B (mm)": p.get("section_b"), "Épaisseur (mm)": p.get("epaisseur"), "Poids (kg/m)": p.get("poids_ml"), "Couleur": p.get("couleur", ""), "Longueur Peinture (mm)": p.get("longueur_peinture")} for p in db_profils if p["nom_projet"] == nom_p]
                pieces_p = [p for p in db_pieces if p["nom_projet"] == nom_p]
                listes_dict = {}
                
                if pieces_p:
                    df_pieces_temp = pd.DataFrame([{"Nom de Liste": pc["nom_liste"], "Référence": pc["reference"], "Profil": pc["profil"], "Longueur (mm)": pc["longueur"], "Quantité": pc["quantite"], "Coupe sur Section": pc.get("coupe_section", "A"), "Angle Gauche (°)": pc["angle_g"], "Angle Droite (°)": pc["angle_d"], "Symétrique": pc["symetrique"]} for pc in pieces_p])
                    for nom_l in df_pieces_temp["Nom de Liste"].unique():
                        listes_dict[nom_l] = formater_df_listes(df_pieces_temp[df_pieces_temp["Nom de Liste"] == nom_l])
                else:
                    listes_dict["Liste 1"] = formater_df_listes(pd.DataFrame())
                    
                workspace[nom_p] = {
                    "profils": formater_df_profils(pd.DataFrame(prof_data)),
                    "listes": listes_dict
                }
            return df_standards_base, workspace
        else:
            raise Exception("Aucun projet trouvé.")
            
    except Exception as e:
        df_standards_base = formater_df_standards(pd.DataFrame([{"Matériau": "ACIER", "Nom": "Tube 50x50", "Longueur Barre (mm)": 6000.0, "Section A (mm)": 50.0, "Section B (mm)": 50.0, "Épaisseur (mm)": 2.0, "Poids (kg/m)": None}]))
        workspace = {
            "Nouveau Projet": {
                "profils": formater_df_profils(pd.DataFrame()),
                "listes": {"Liste 1": formater_df_listes(pd.DataFrame())}
            }
        }
        return df_standards_base, workspace

def sauvegarder_projet(nom_projet, df_profils, dict_listes):
    insert_profils = []
    for _, r in df_profils.iterrows():
        nom_profil = str(r["Nom"]).strip()
        if nom_profil != "" and nom_profil != "nan" and nom_profil != "None":
            insert_profils.append({
                "nom_projet": nom_projet, "nom_profil": nom_profil, 
                "longueur": float(r["Longueur Barre (mm)"]) if pd.notna(r["Longueur Barre (mm)"]) else 0,
                "section_a": float(r["Section A (mm)"]) if pd.notna(r["Section A (mm)"]) else None,
                "section_b": float(r["Section B (mm)"]) if pd.notna(r["Section B (mm)"]) else None,
                "epaisseur": float(r["Épaisseur (mm)"]) if pd.notna(r["Épaisseur (mm)"]) else None,
                "poids_ml": float(r["Poids (kg/m)"]) if pd.notna(r["Poids (kg/m)"]) else None,
                "couleur": str(r["Couleur"]) if pd.notna(r["Couleur"]) else "",
                "longueur_peinture": float(r["Longueur Peinture (mm)"]) if pd.notna(r["Longueur Peinture (mm)"]) else None
            })

    insert_pieces = []
    pieces_ignorees = []
    for l_name, df_liste in dict_listes.items():
        for _, r in df_liste.iterrows():
            ref = str(r["Référence"]).strip()
            if ref != "" and ref != "nan" and ref != "None":
                insert_pieces.append({
                    "nom_projet": nom_projet, "nom_liste": l_name, "reference": ref, 
                    "profil": str(r["Profil"]).strip() if pd.notna(r["Profil"]) else "",
                    "longueur": float(r["Longueur (mm)"]) if pd.notna(r["Longueur (mm)"]) else 0, 
                    "quantite": int(r["Quantité"]) if pd.notna(r["Quantité"]) else 0,
                    "coupe_section": str(r.get("Coupe sur Section", "A")), # NOUVEAU
                    "angle_g": float(r["Angle Gauche (°)"]) if pd.notna(r["Angle Gauche (°)"]) else 90, 
                    "angle_d": float(r["Angle Droite (°)"]) if pd.notna(r["Angle Droite (°)"]) else 90,
                    "symetrique": bool(r["Symétrique"])
                })
            elif pd.notna(r["Longueur (mm)"]) or pd.notna(r["Quantité"]):
                pieces_ignorees.append(l_name)

    url_proj = f"{SUPABASE_URL}/rest/v1/gp_debit_projets"
    r_proj = requests.post(url_proj, headers={**HEADERS, "Prefer": "resolution=merge-duplicates"}, params={"on_conflict":"nom_projet"}, json=[{"nom_projet": nom_projet}])
    if r_proj.status_code not in [200, 201]: raise Exception(f"Erreur table projets : {r_proj.text}")
    
    _requete_delete("gp_debit_profils", "nom_projet", nom_projet)
    if insert_profils: _requete_insert("gp_debit_profils", insert_profils)

    _requete_delete("gp_debit_pieces", "nom_projet", nom_projet)
    
    # BOUCLIER CTO : Rétrocompatibilité avec Supabase
    if insert_pieces:
        try:
            _requete_insert("gp_debit_pieces", insert_pieces)
        except Exception as e:
            if "coupe_section" in str(e).lower():
                # La colonne manque dans Supabase, on la retire à la volée et on réessaie
                for p in insert_pieces:
                    p.pop("coupe_section", None)
                _requete_insert("gp_debit_pieces", insert_pieces)
                raise Exception("WARNING_COLONNE_MANQUANTE")
            else:
                raise e

    return pieces_ignorees

def sauvegarder_standards(df_standards):
    insert_std = []
    for _, r in df_standards.iterrows():
        if pd.notna(r["Nom"]) and str(r["Nom"]).strip() != "":
            insert_std.append({
                "nom_profil": str(r["Nom"]).strip(),
                "materiau": str(r["Matériau"]) if pd.notna(r["Matériau"]) else "ACIER",
                "longueur_barre": float(r["Longueur Barre (mm)"]) if pd.notna(r["Longueur Barre (mm)"]) else None,
                "section_a": float(r["Section A (mm)"]) if pd.notna(r["Section A (mm)"]) else 0,
                "section_b": float(r["Section B (mm)"]) if pd.notna(r["Section B (mm)"]) else 0,
                "epaisseur": float(r["Épaisseur (mm)"]) if pd.notna(r["Épaisseur (mm)"]) else None,
                "poids_ml": float(r["Poids (kg/m)"]) if pd.notna(r["Poids (kg/m)"]) else None
            })
            
    r_del = requests.delete(f"{SUPABASE_URL}/rest/v1/gp_debit_standards?nom_profil=not.is.null", headers=HEADERS)
    if r_del.status_code not in [200, 204]: raise Exception(f"Delete fail: {r_del.text}")
    
    if insert_std: 
        try:
            _requete_insert("gp_debit_standards", insert_std)
        except Exception as e:
            if "longueur_barre" in str(e).lower():
                # La colonne manque dans Supabase, on la retire à la volée et on réessaie
                for s in insert_std:
                    s.pop("longueur_barre", None)
                _requete_insert("gp_debit_standards", insert_std)
                raise Exception("WARNING_COLONNE_MANQUANTE_STD")
            else:
                raise e
