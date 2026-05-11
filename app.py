import streamlit as st
import pandas as pd
from ortools.sat.python import cp_model
import matplotlib.pyplot as plt
import matplotlib.patches as patches
import math
import requests 

# -----------------------------------------------------------------------------
# 1. CONFIGURATION DE LA PAGE ET CONNEXION SUPABASE (REST API)
# -----------------------------------------------------------------------------
st.set_page_config(page_title="Optimisation de Débitage Pro", page_icon="🪚", layout="wide")

SUPABASE_URL = "https://wlonolzfkhlyxbojprus.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Indsb25vbHpma2hseXhib2pwcnVzIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NjQyMjY2ODEsImV4cCI6MjA3OTgwMjY4MX0.FwA0c6iwp3sYfI4zEj7xOK_wJKywA3QKmhY5CVM2XHU"
NOM_TABLE_SUPABASE = "gp_debit_workspace" 

HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json"
}

# Colonnes de l'interface (Notion de Stock supprimée !)
COL_STANDARDS = ["Matériau", "Nom", "Section A (mm)", "Section B (mm)", "Épaisseur (mm)", "Poids (kg/m)"]
COL_PROFILS = ["Nom", "Longueur Barre (mm)", "Section A (mm)", "Section B (mm)", "Épaisseur (mm)", "Poids (kg/m)", "Couleur", "Longueur Peinture (mm)"]
COL_LISTES = ["Référence", "Profil", "Longueur (mm)", "Quantité", "Angle Gauche (°)", "Angle Droite (°)", "Symétrique"]

# -----------------------------------------------------------------------------
# OUTILS DE BASE DE DONNÉES (TRADUCTION INTERFACE <-> SQL)
# -----------------------------------------------------------------------------
def requete_get(table):
    r = requests.get(f"{SUPABASE_URL}/rest/v1/{table}", headers=HEADERS)
    if r.status_code == 200:
        return r.json()
    else:
        st.error(f"Erreur de lecture ({table}) : {r.text}")
        return []

def requete_delete(table, colonne, valeur):
    url = f"{SUPABASE_URL}/rest/v1/{table}?{colonne}=eq.{valeur}"
    r = requests.delete(url, headers=HEADERS)
    if r.status_code not in [200, 204]:
        raise Exception(f"Erreur suppression ({table}) : {r.text}")

def requete_insert(table, data):
    if not data: return
    r = requests.post(f"{SUPABASE_URL}/rest/v1/{table}", headers=HEADERS, json=data)
    if r.status_code not in [200, 201]:
        raise Exception(f"Erreur insertion ({table}) : {r.text}")

def formater_df_standards(df):
    if df is None or df.empty: return pd.DataFrame(columns=COL_STANDARDS)
    df = df.copy()
    for col in COL_STANDARDS:
        if col not in df.columns: df[col] = None
            
    df["Matériau"] = df["Matériau"].fillna("").astype(str)
    df["Nom"] = df["Nom"].fillna("").astype(str)
    df["Section A (mm)"] = pd.to_numeric(df["Section A (mm)"], errors='coerce')
    df["Section B (mm)"] = pd.to_numeric(df["Section B (mm)"], errors='coerce')
    df["Épaisseur (mm)"] = pd.to_numeric(df["Épaisseur (mm)"], errors='coerce')
    df["Poids (kg/m)"] = pd.to_numeric(df["Poids (kg/m)"], errors='coerce')
    return df

def formater_df_profils(df):
    if df is None or df.empty: return pd.DataFrame(columns=COL_PROFILS)
    df = df.copy()
    for col in COL_PROFILS:
        if col not in df.columns: df[col] = None
            
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
    df["Angle Gauche (°)"] = pd.to_numeric(df["Angle Gauche (°)"], errors='coerce')
    df["Angle Droite (°)"] = pd.to_numeric(df["Angle Droite (°)"], errors='coerce')
    df["Symétrique"] = df["Symétrique"].fillna(False).astype(bool)
    return df

# -----------------------------------------------------------------------------
# CHARGEMENT DEPUIS SUPABASE
# -----------------------------------------------------------------------------
if 'workspace' not in st.session_state:
    try:
        db_standards = requete_get("gp_debit_standards")
        db_projets = requete_get("gp_debit_projets")
        db_profils = requete_get("gp_debit_profils")
        db_pieces = requete_get("gp_debit_pieces")
        
        if db_standards:
            std_data = [{"Matériau": r.get("materiau", ""), "Nom": r["nom_profil"], "Section A (mm)": r.get("section_a"), "Section B (mm)": r.get("section_b"), "Épaisseur (mm)": r.get("epaisseur"), "Poids (kg/m)": r.get("poids_ml")} for r in db_standards]
            st.session_state.df_standards_base = formater_df_standards(pd.DataFrame(std_data))
        else:
            st.session_state.df_standards_base = pd.DataFrame(columns=COL_STANDARDS)
            
        if db_projets:
            new_workspace = {}
            for proj in db_projets:
                nom_p = proj["nom_projet"]
                
                # Récupération sans la "Quantité en stock"
                prof_data = [{"Nom": p["nom_profil"], "Longueur Barre (mm)": p.get("longueur"), "Section A (mm)": p.get("section_a"), "Section B (mm)": p.get("section_b"), "Épaisseur (mm)": p.get("epaisseur"), "Poids (kg/m)": p.get("poids_ml"), "Couleur": p.get("couleur", ""), "Longueur Peinture (mm)": p.get("longueur_peinture")} for p in db_profils if p["nom_projet"] == nom_p]
                
                pieces_p = [p for p in db_pieces if p["nom_projet"] == nom_p]
                listes_dict = {}
                
                if pieces_p:
                    df_pieces_temp = pd.DataFrame([{"Nom de Liste": pc["nom_liste"], "Référence": pc["reference"], "Profil": pc["profil"], "Longueur (mm)": pc["longueur"], "Quantité": pc["quantite"], "Angle Gauche (°)": pc["angle_g"], "Angle Droite (°)": pc["angle_d"], "Symétrique": pc["symetrique"]} for pc in pieces_p])
                    for nom_l in df_pieces_temp["Nom de Liste"].unique():
                        listes_dict[nom_l] = formater_df_listes(df_pieces_temp[df_pieces_temp["Nom de Liste"] == nom_l])
                else:
                    listes_dict["Liste 1"] = formater_df_listes(pd.DataFrame())
                    
                new_workspace[nom_p] = {
                    "profils": formater_df_profils(pd.DataFrame(prof_data)),
                    "listes": listes_dict
                }
                
            st.session_state.workspace = new_workspace
            st.session_state.projet_actif = list(new_workspace.keys())[0]
            st.session_state.liste_active = list(new_workspace[st.session_state.projet_actif]["listes"].keys())[0]
            st.toast("✅ Base de données connectée", icon="☁️")
        else:
            raise Exception("Base vide")
            
    except Exception as e:
        st.session_state.df_standards_base = formater_df_standards(pd.DataFrame([{"Matériau": "ACIER", "Nom": "Tube 50x50", "Section A (mm)": 50.0, "Section B (mm)": 50.0, "Épaisseur (mm)": 2.0, "Poids (kg/m)": None}]))
        st.session_state.workspace = {
            "Nouveau Projet": {
                "profils": formater_df_profils(pd.DataFrame()),
                "listes": {"Liste 1": formater_df_listes(pd.DataFrame())}
            }
        }
        st.session_state.projet_actif = "Nouveau Projet"
        st.session_state.liste_active = "Liste 1"

# -----------------------------------------------------------------------------
# FONCTION D'OPTIMISATION MATHÉMATIQUE (CALCUL DES COMMANDES)
# -----------------------------------------------------------------------------
def optimiser_projet_complet(df_pieces, df_profils, epaisseur_lame):
    resultats_finaux = {}
    
    df_profils = df_profils.dropna(subset=['Nom', 'Longueur Barre (mm)']).copy()
    df_profils['Nom'] = df_profils['Nom'].astype(str).str.strip()
    df_profils = df_profils[df_profils['Nom'] != ""]
    
    df_pieces = df_pieces.dropna(subset=['Référence', 'Profil', 'Longueur (mm)', 'Quantité']).copy()
    df_pieces['Profil'] = df_pieces['Profil'].astype(str).str.strip()
    df_pieces = df_pieces[df_pieces['Profil'] != ""]

    for index, profil in df_profils.iterrows():
        nom_profil = profil['Nom']
        largeur_profil = profil.get('Section A (mm)', 50.0) 
        longueur_barre_standard = profil.get('Longueur Barre (mm)', 0)
        longueur_peinture = profil.get('Longueur Peinture (mm)', 0)
        
        if pd.isna(largeur_profil): largeur_profil = 50.0
        if pd.isna(longueur_peinture): longueur_peinture = 0.0
        
        pieces_du_profil = df_pieces[df_pieces['Profil'] == nom_profil]
        if pieces_du_profil.empty: continue 
            
        pieces_liste = []
        for idx, row in pieces_du_profil.iterrows():
            if row['Quantité'] <= 0 or row['Longueur (mm)'] <= 0: continue
            for _ in range(int(row['Quantité'])):
                pieces_liste.append({
                    'liste': row.get('Nom de la Liste', 'Sans Liste'),
                    'ref': row.get('Référence', f'P{idx}'), 
                    'longueur': row['Longueur (mm)'],
                    'angle_g': row.get('Angle Gauche (°)', 90.0),
                    'angle_d': row.get('Angle Droite (°)', 90.0)
                })

        if not pieces_liste:
            continue
            
        if longueur_barre_standard <= 0:
            resultats_finaux[nom_profil] = "LONGUEUR_MANQUANTE"
            continue

        # L'IA génère autant de barres virtuelles qu'il y a de pièces (Pire des cas = 1 barre commandée par pièce)
        qte_barres_a_fournir_ia = len(pieces_liste)
        barres_liste = [{'id': nom_profil, 'longueur': longueur_barre_standard} for _ in range(qte_barres_a_fournir_ia)]

        if any(p['longueur'] > longueur_barre_standard for p in pieces_liste):
            resultats_finaux[nom_profil] = "ERREUR_TAILLE"
            continue

        model = cp_model.CpModel()
        x = {} 
        for i in range(len(pieces_liste)):
            for j in range(len(barres_liste)):
                x[i, j] = model.NewBoolVar(f'x_{i}_{j}')
        y = {} 
        for j in range(len(barres_liste)):
            y[j] = model.NewBoolVar(f'y_{j}')

        for i in range(len(pieces_liste)):
            model.AddExactlyOne(x[i, j] for j in range(len(barres_liste)))

        # Anti-explosion & Symétrie : L'IA doit remplir les barres dans l'ordre (1, puis 2, puis 3...)
        for j in range(1, len(barres_liste)):
            model.Add(y[j] <= y[j-1])

        lame = int(epaisseur_lame * 10)
        for j in range(len(barres_liste)):
            capacite = int(barres_liste[j]['longueur'] * 10)
            model.Add(sum((int(pieces_liste[i]['longueur'] * 10) + lame) * x[i, j] for i in range(len(pieces_liste))) <= (capacite + lame) * y[j])

        model.Minimize(sum(int(barres_liste[j]['longueur'] * 10) * y[j] for j in range(len(barres_liste))))
        
        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = 10.0
        status = solver.Solve(model)

        if status == cp_model.OPTIMAL or status == cp_model.FEASIBLE:
            resultats_barres = []
            for j in range(len(barres_liste)):
                if solver.Value(y[j]):
                    pieces_barre = []
                    longueur_utilisee = 0
                    for i in range(len(pieces_liste)):
                        if solver.Value(x[i, j]):
                            pieces_barre.append(pieces_liste[i])
                            longueur_utilisee += pieces_liste[i]['longueur'] + epaisseur_lame
                    longueur_utilisee -= epaisseur_lame 
                    resultats_barres.append({'barre_longueur': barres_liste[j]['longueur'], 'pieces': pieces_barre, 'chute': barres_liste[j]['longueur'] - longueur_utilisee})
            
            resultats_finaux[nom_profil] = {
                "statut": "SUCCES", 
                "barres": resultats_barres, 
                "largeur": largeur_profil,
                "longueur_peinture": longueur_peinture,
                "longueur_barre_standard": longueur_barre_standard
            }
        else:
            resultats_finaux[nom_profil] = "ECHEC"

    return resultats_finaux

# -----------------------------------------------------------------------------
# FONCTION DE DESSIN (COMPACTE)
# -----------------------------------------------------------------------------
def dessiner_barre(barre_info, epaisseur_lame, largeur_profil, seuil_chute):
    fig, ax = plt.subplots(figsize=(12, 0.6)) 
    longueur_totale = barre_info['barre_longueur']
    
    ax.add_patch(patches.Rectangle((0, 0), longueur_totale, largeur_profil, facecolor='#f0f0f0', edgecolor='black'))
    position_actuelle = 0
    
    for p in barre_info['pieces']:
        L = p['longueur']
        ang_g, ang_d = p.get('angle_g', 90.0), p.get('angle_d', 90.0)
        if pd.isna(ang_g): ang_g = 90.0
        if pd.isna(ang_d): ang_d = 90.0
        
        dx_g = largeur_profil / math.tan(math.radians(ang_g)) if ang_g != 90 else 0
        dx_d = largeur_profil / math.tan(math.radians(ang_d)) if ang_d != 90 else 0
        
        x_min, x_max = position_actuelle, position_actuelle + L
        x_bl, x_tl = x_min + min((dx_g if dx_g > 0 else 0), L), x_min + min((-dx_g if dx_g < 0 else 0), L)
        x_br, x_tr = x_max - min((dx_d if dx_d > 0 else 0), L), x_max - min((-dx_d if dx_d < 0 else 0), L)
        
        ax.add_patch(patches.Polygon([(x_bl, 0), (x_tl, largeur_profil), (x_tr, largeur_profil), (x_br, 0)], closed=True, facecolor='#4CAF50', edgecolor='black', linewidth=1))
        ax.text(position_actuelle + L/2, largeur_profil/2, f"{p['ref']}\n{L}mm", ha='center', va='center', color='white', fontweight='bold', fontsize=8)
        position_actuelle += L
        
        if position_actuelle + epaisseur_lame <= longueur_totale and position_actuelle < longueur_totale:
            ax.add_patch(patches.Rectangle((position_actuelle, 0), epaisseur_lame, largeur_profil, facecolor='#F44336', edgecolor='none'))
            position_actuelle += epaisseur_lame
            
    if position_actuelle < longueur_totale:
        chute = longueur_totale - position_actuelle
        est_reutilisable = chute >= seuil_chute
        ax.add_patch(patches.Rectangle((position_actuelle, 0), chute, largeur_profil, facecolor='#C8E6C9' if est_reutilisable else '#9E9E9E', edgecolor='black', hatch='' if est_reutilisable else '//'))
        ax.text(position_actuelle + chute/2, largeur_profil/2, f"♻️ Chute\n{chute:.1f} mm" if est_reutilisable else f"Déchet\n{chute:.1f} mm", ha='center', va='center', color='black', fontweight='bold' if est_reutilisable else 'normal', fontsize=8)
        
    ax.set_xlim(0, longueur_totale)
    ax.set_ylim(0, largeur_profil * 1.2)
    ax.axis('off')
    
    fig.subplots_adjust(left=0, right=1, top=1, bottom=0)
    
    return fig

# -----------------------------------------------------------------------------
# 2. MENU LATÉRAL
# -----------------------------------------------------------------------------
with st.sidebar:
    st.header("📁 Navigation")
    
    liste_projets = list(st.session_state.workspace.keys())
    projet_choisi = st.selectbox("📌 Projet Actif", liste_projets, index=liste_projets.index(st.session_state.projet_actif) if st.session_state.projet_actif in liste_projets else 0)
    
    if projet_choisi != st.session_state.projet_actif:
        st.session_state.projet_actif = projet_choisi
        st.session_state.liste_active = list(st.session_state.workspace[projet_choisi]["listes"].keys())[0] if st.session_state.workspace[projet_choisi]["listes"] else None
        st.rerun()

    with st.expander("➕ Créer un nouveau projet"):
        nouveau_projet = st.text_input("Nom du nouveau projet")
        if st.button("Créer le projet") and nouveau_projet:
            if nouveau_projet not in st.session_state.workspace:
                st.session_state.workspace[nouveau_projet] = {"profils": formater_df_profils(pd.DataFrame()), "listes": {"Liste 1": formater_df_listes(pd.DataFrame())}}
                st.session_state.projet_actif = nouveau_projet
                st.session_state.liste_active = "Liste 1"
                st.rerun()
            else:
                st.error("Ce nom existe déjà.")

    st.divider()
    st.header("☁️ Sauvegarde Multi-Tables")
    
    if st.button("☁️ Enregistrer le projet courant", type="primary"):
        with st.spinner("Envoi vers Supabase..."):
            try:
                nom_p = st.session_state.projet_actif
                
                url_proj = f"{SUPABASE_URL}/rest/v1/gp_debit_projets"
                r_proj = requests.post(url_proj, headers={**HEADERS, "Prefer": "resolution=merge-duplicates"}, params={"on_conflict":"nom_projet"}, json=[{"nom_projet": nom_p}])
                if r_proj.status_code not in [200, 201]: raise Exception(f"Erreur table projets : {r_proj.text}")
                
                df_prof = st.session_state.workspace[nom_p].get("profils_edited", st.session_state.workspace[nom_p]["profils"])
                requete_delete("gp_debit_profils", "nom_projet", nom_p)
                
                insert_profils = []
                for _, r in df_prof.iterrows():
                    nom_profil = str(r["Nom"]).strip()
                    if nom_profil != "" and nom_profil != "nan" and nom_profil != "None":
                        insert_profils.append({
                            "nom_projet": nom_p, "nom_profil": nom_profil, 
                            "longueur": float(r["Longueur Barre (mm)"]) if pd.notna(r["Longueur Barre (mm)"]) else 0,
                            "section_a": float(r["Section A (mm)"]) if pd.notna(r["Section A (mm)"]) else None,
                            "section_b": float(r["Section B (mm)"]) if pd.notna(r["Section B (mm)"]) else None,
                            "epaisseur": float(r["Épaisseur (mm)"]) if pd.notna(r["Épaisseur (mm)"]) else None,
                            "poids_ml": float(r["Poids (kg/m)"]) if pd.notna(r["Poids (kg/m)"]) else None,
                            "couleur": str(r["Couleur"]) if pd.notna(r["Couleur"]) else "",
                            "longueur_peinture": float(r["Longueur Peinture (mm)"]) if pd.notna(r["Longueur Peinture (mm)"]) else None,
                            "quantite": 0 
                        })
                requete_insert("gp_debit_profils", insert_profils)

                requete_delete("gp_debit_pieces", "nom_projet", nom_p)
                insert_pieces = []
                for l_name, l_base in st.session_state.workspace[nom_p]["listes"].items():
                    df_liste = st.session_state.workspace[nom_p].get("listes_edited", {}).get(l_name, l_base)
                    for _, r in df_liste.iterrows():
                        ref = str(r["Référence"]).strip()
                        if ref != "" and ref != "nan" and ref != "None":
                            insert_pieces.append({
                                "nom_projet": nom_p, "nom_liste": l_name, "reference": ref, 
                                "profil": str(r["Profil"]).strip() if pd.notna(r["Profil"]) else "",
                                "longueur": float(r["Longueur (mm)"]) if pd.notna(r["Longueur (mm)"]) else 0, 
                                "quantite": int(r["Quantité"]) if pd.notna(r["Quantité"]) else 0,
                                "angle_g": float(r["Angle Gauche (°)"]) if pd.notna(r["Angle Gauche (°)"]) else 90, 
                                "angle_d": float(r["Angle Droite (°)"]) if pd.notna(r["Angle Droite (°)"]) else 90,
                                "symetrique": bool(r["Symétrique"])
                            })
                        elif pd.notna(r["Longueur (mm)"]) or pd.notna(r["Quantité"]):
                            st.warning(f"⚠️ Une pièce de la liste '{l_name}' a été ignorée car la 'Référence' est vide.")
                            
                requete_insert("gp_debit_pieces", insert_pieces)
                st.success("Projet sauvegardé avec succès !")
            except Exception as e:
                st.error(f"❌ Erreur Base de données : {e}")

    st.divider()
    st.header("⚙️ Paramètres Machine")
    epaisseur_lame = st.number_input("Lame (mm)", min_value=0.0, value=3.0, step=0.1)
    seuil_chute = st.number_input("Chute récup. (mm)", min_value=10.0, value=500.0, step=10.0)

# -----------------------------------------------------------------------------
# 3. CORPS DE L'APPLICATION
# -----------------------------------------------------------------------------
st.title(f"🪚 Projet : {st.session_state.projet_actif}")
projet_courant = st.session_state.workspace[st.session_state.projet_actif]

tab1, tab2, tab3, tab4 = st.tabs(["📚 1. Base Standard", f"📦 2. Profils du Projet ({st.session_state.projet_actif})", "📝 3. Listes de Pièces", "📊 4. Résultats & Commandes"])

with tab1:
    st.subheader("Catalogue des Profils Standards (Commun)")
    st.session_state.df_standards_edited = st.data_editor(
        st.session_state.df_standards_base, num_rows="dynamic", use_container_width=True, key="editor_std", hide_index=True, 
        column_config={
            "Matériau": st.column_config.SelectboxColumn("Matériau", options=["ALUMINIUM", "ACIER", "INOX"], required=True),
            "Nom": st.column_config.TextColumn("Nom", required=True),
            "Section A (mm)": st.column_config.NumberColumn("Section A (mm)", required=True),
            "Section B (mm)": st.column_config.NumberColumn("Section B (mm)", required=True)
        }
    )
    if st.button("Sauvegarder Standards"):
        try:
            r_del = requests.delete(f"{SUPABASE_URL}/rest/v1/gp_debit_standards?nom_profil=not.is.null", headers=HEADERS)
            if r_del.status_code not in [200, 204]: raise Exception(f"Delete fail: {r_del.text}")
            
            insert_std = []
            for _, r in st.session_state.df_standards_edited.iterrows():
                if pd.notna(r["Nom"]) and str(r["Nom"]).strip() != "":
                    insert_std.append({
                        "nom_profil": str(r["Nom"]).strip(),
                        "materiau": str(r["Matériau"]) if pd.notna(r["Matériau"]) else "ACIER",
                        "section_a": float(r["Section A (mm)"]) if pd.notna(r["Section A (mm)"]) else 0,
                        "section_b": float(r["Section B (mm)"]) if pd.notna(r["Section B (mm)"]) else 0,
                        "epaisseur": float(r["Épaisseur (mm)"]) if pd.notna(r["Épaisseur (mm)"]) else None,
                        "poids_ml": float(r["Poids (kg/m)"]) if pd.notna(r["Poids (kg/m)"]) else None
                    })
            requete_insert("gp_debit_standards", insert_std)
            st.toast("Standards sauvegardés", icon="✅")
        except Exception as e:
            st.error(f"Erreur Standards : {e}")

with tab2:
    st.subheader(f"Profils (Barres d'approvisionnement) : {st.session_state.projet_actif}")
    projet_courant["profils_edited"] = st.data_editor(
        projet_courant["profils"], num_rows="dynamic", use_container_width=True, key=f"editor_stock_{st.session_state.projet_actif}", hide_index=True, 
        column_config={"Nom": st.column_config.TextColumn(required=True)}
    )

with tab3:
    col_gauche, col_droite = st.columns([1, 1])
    noms_listes = list(projet_courant["listes"].keys())
    
    with col_gauche:
        if noms_listes:
            liste_choisie = st.selectbox("📂 Liste active :", noms_listes, index=noms_listes.index(st.session_state.liste_active) if st.session_state.liste_active in noms_listes else 0)
            if liste_choisie != st.session_state.liste_active:
                st.session_state.liste_active = liste_choisie
                st.rerun()
            
    with col_droite:
        with st.expander("➕ Créer une nouvelle liste manuellement"):
            nouvelle_liste = st.text_input("Nom de la nouvelle liste")
            if st.button("Ajouter Liste") and nouvelle_liste:
                if nouvelle_liste not in projet_courant["listes"]:
                    projet_courant["listes"][nouvelle_liste] = formater_df_listes(pd.DataFrame())
                    st.session_state.liste_active = nouvelle_liste
                    st.rerun()
                else:
                    st.error("Ce nom existe déjà.")
                    
        with st.expander("📥 Importer une liste depuis Excel"):
            fichier_excel = st.file_uploader("Glisser un fichier .xlsx", type=["xlsx"])
            nom_import = st.text_input("Nom de la liste importée", value="Import Excel" if fichier_excel else "")
            
            if st.button("Importer le fichier", type="primary") and fichier_excel and nom_import:
                if nom_import not in projet_courant["listes"]:
                    try:
                        df_excel = pd.read_excel(fichier_excel)
                        projet_courant["listes"][nom_import] = formater_df_listes(df_excel)
                        st.session_state.liste_active = nom_import
                        st.rerun()
                    except Exception as e:
                        st.error(f"Erreur lors de la lecture du fichier : {e}")
                else:
                    st.error("Ce nom de liste existe déjà.")

    if st.session_state.liste_active in projet_courant["listes"]:
        st.markdown(f"### ✏️ Liste : **{st.session_state.liste_active}**")
        
        profils_actuels = projet_courant.get("profils_edited", projet_courant["profils"])
        noms_profils_disponibles = profils_actuels['Nom'].dropna().replace("", pd.NA).dropna().unique().tolist() if "Nom" in profils_actuels.columns and not profils_actuels.empty else ["Aucun profil défini"]

        df_liste_active = projet_courant["listes"][st.session_state.liste_active]
        if "listes_edited" not in projet_courant: projet_courant["listes_edited"] = {}
            
        projet_courant["listes_edited"][st.session_state.liste_active] = st.data_editor(
            df_liste_active, num_rows="dynamic", use_container_width=True, key=f"editor_list_{st.session_state.projet_actif}_{st.session_state.liste_active}", hide_index=True,
            column_config={
                "Référence": st.column_config.TextColumn(required=True),
                "Profil": st.column_config.SelectboxColumn("Profil", options=noms_profils_disponibles, required=True),
            }
        )

with tab4:
    st.subheader(f"Plans de coupe et Commandes du projet : {st.session_state.projet_actif}")
    
    noms_toutes_listes = list(projet_courant["listes"].keys())
    listes_a_optimiser = st.multiselect(
        "Sélectionnez la ou les liste(s) à produire :", 
        options=noms_toutes_listes, 
        default=noms_toutes_listes,
        help="Vous pouvez décocher les listes que vous ne voulez pas optimiser pour l'instant."
    )
    
    if st.button("🚀 Lancer l'optimisation", type="primary"):
        if not listes_a_optimiser:
            st.warning("Veuillez sélectionner au moins une liste à optimiser.")
        else:
            with st.spinner('Calcul des barres à commander par l\'IA...'):
                frames_pieces = []
                for nom_liste in listes_a_optimiser:
                    df_l = projet_courant.get("listes_edited", {}).get(nom_liste, projet_courant["listes"][nom_liste])
                    if not df_l.empty:
                        df_temp = df_l.copy()
                        df_temp['Nom de la Liste'] = nom_liste 
                        frames_pieces.append(df_temp)
                
                df_pieces_global = pd.concat(frames_pieces, ignore_index=True) if frames_pieces else pd.DataFrame()
                
                if df_pieces_global.empty: 
                    st.info("Aucune pièce à optimiser dans ces listes.")
                else:
                    profils_a_utiliser = projet_courant.get("profils_edited", projet_courant["profils"])
                    resultats = optimiser_projet_complet(df_pieces_global, profils_a_utiliser, epaisseur_lame)
                    
                    if not resultats:
                        st.warning("⚠️ L'optimisation n'a rien pu calculer. Voici ce qu'il manque :")
                        st.info("1. Avez-vous bien renseigné la **Longueur de Barre** dans l'onglet 2 ?\n"
                                "2. Les noms des profils dans vos listes sont-ils **exactement les mêmes** que ceux de l'onglet 2 ?")
                    else:
                        total_longueur_pieces = 0
                        total_longueur_barres = 0
                        total_surface_peinture = 0.0 # Ajout du total global de peinture
                        
                        for profil_res in resultats.values():
                            if type(profil_res) == dict and profil_res["statut"] == "SUCCES":
                                nb_barres = len(profil_res["barres"])
                                perimetre = profil_res.get("longueur_peinture", 0)
                                longueur_barre = profil_res.get("longueur_barre_standard", 0)
                                
                                # Calcul de la surface en m2 : (Périmètre * Longueur Barre * Nombre) / 1000000
                                total_surface_peinture += (perimetre * longueur_barre * nb_barres) / 1000000.0
                                
                                for b in profil_res["barres"]:
                                    total_longueur_barres += b['barre_longueur']
                                    for p in b['pieces']:
                                        total_longueur_pieces += p['longueur']
                        
                        if total_longueur_barres > 0:
                            rendement = (total_longueur_pieces / total_longueur_barres) * 100
                            col1, col2, col3, col4 = st.columns(4)
                            col1.metric("Matière Consommée", f"{total_longueur_barres / 1000:.2f} mètres")
                            col2.metric("Matière Utile (Pièces)", f"{total_longueur_pieces / 1000:.2f} mètres")
                            col3.metric("Rendement", f"{rendement:.1f} %", f"-{100-rendement:.1f} % de chute", delta_color="inverse")
                            col4.metric("Surface à Peindre", f"{total_surface_peinture:.2f} m²")
                            st.divider()

                        for nom_profil, resultat in resultats.items():
                            st.markdown(f"### 🔹 Profil : {nom_profil}")
                            if resultat == "LONGUEUR_MANQUANTE": 
                                st.error("❌ Longueur de barre standard manquante pour ce profil. Allez dans l'onglet 2 pour définir la longueur des barres d'approvisionnement.")
                            elif resultat == "ERREUR_TAILLE": 
                                st.error("❌ Impossible : Vous avez demandé une pièce qui est plus longue que la barre standard que vous avez définie !")
                            elif resultat == "ECHEC": 
                                st.error("❌ Échec inattendu de l'optimiseur.")
                            elif type(resultat) == dict and resultat["statut"] == "SUCCES":
                                # Calcul de la surface pour ce profil précis
                                surface_profil = (resultat.get('longueur_peinture', 0) * resultat.get('longueur_barre_standard', 0) * len(resultat['barres'])) / 1000000.0
                                st.success(f"📦 À commander : {len(resultat['barres'])} barre(s) de {resultat['barres'][0]['barre_longueur']} mm.  *(Surface de peinture : {surface_profil:.2f} m²)*")
                                
                                for idx, barre in enumerate(resultat["barres"]):
                                    with st.expander(f"Barre {idx+1} (Longueur: {barre['barre_longueur']} mm) - Chute : {barre['chute']:.1f} mm", expanded=True):
                                        st.pyplot(dessiner_barre(barre, epaisseur_lame, resultat["largeur"], seuil_chute))
                            st.divider()
