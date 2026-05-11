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

HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json"
}

# Colonnes de l'interface
COL_PROFILS = ["Nom du Profil", "Longueur Barre (mm)", "Largeur (mm)", "Couleur / Finition", "Quantité en stock"]
COL_LISTES = ["Référence", "Profil", "Longueur max (mm)", "Quantité", "Angle Gauche (°)", "Angle Droit (°)", "Symétrique"]
COL_STANDARDS = ["Nom du Profil", "Largeur (mm)", "Couleur / Finition"]

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

def formater_df_profils(df):
    if df is None or df.empty: return pd.DataFrame(columns=COL_PROFILS)
    df = df.copy()
    df["Nom du Profil"] = df["Nom du Profil"].fillna("").astype(str)
    df["Longueur Barre (mm)"] = pd.to_numeric(df["Longueur Barre (mm)"], errors='coerce')
    df["Largeur (mm)"] = pd.to_numeric(df["Largeur (mm)"], errors='coerce')
    df["Couleur / Finition"] = df["Couleur / Finition"].fillna("").astype(str)
    df["Quantité en stock"] = pd.to_numeric(df["Quantité en stock"], errors='coerce').astype('Int64')
    return df

def formater_df_listes(df):
    if df is None or df.empty: return pd.DataFrame(columns=COL_LISTES)
    df = df.copy()
    df["Référence"] = df["Référence"].fillna("").astype(str)
    df["Profil"] = df["Profil"].fillna("").astype(str)
    df["Longueur max (mm)"] = pd.to_numeric(df["Longueur max (mm)"], errors='coerce')
    df["Quantité"] = pd.to_numeric(df["Quantité"], errors='coerce').astype('Int64')
    df["Angle Gauche (°)"] = pd.to_numeric(df["Angle Gauche (°)"], errors='coerce')
    df["Angle Droit (°)"] = pd.to_numeric(df["Angle Droit (°)"], errors='coerce')
    df["Symétrique"] = df["Symétrique"].fillna(True).astype(bool)
    return df

# -----------------------------------------------------------------------------
# CHARGEMENT DEPUIS SUPABASE
# -----------------------------------------------------------------------------
if 'workspace' not in st.session_state:
    try:
        # On télécharge les 4 tables
        db_standards = requete_get("gp_debit_standards")
        db_projets = requete_get("gp_debit_projets")
        db_profils = requete_get("gp_debit_profils")
        db_pieces = requete_get("gp_debit_pieces")
        
        # 1. Traitement des standards
        if db_standards:
            std_data = [{"Nom du Profil": r["nom_profil"], "Largeur (mm)": r["largeur"], "Couleur / Finition": r["couleur"]} for r in db_standards]
            st.session_state.df_standards_base = pd.DataFrame(std_data)
        else:
            st.session_state.df_standards_base = pd.DataFrame(columns=COL_STANDARDS)
            
        # 2. Reconstruction de l'espace de travail
        if db_projets:
            new_workspace = {}
            for proj in db_projets:
                nom_p = proj["nom_projet"]
                
                # Récupérer les profils de ce projet
                prof_data = [{"Nom du Profil": p["nom_profil"], "Longueur Barre (mm)": p["longueur"], "Largeur (mm)": p["largeur"], "Couleur / Finition": p["couleur"], "Quantité en stock": p["quantite"]} for p in db_profils if p["nom_projet"] == nom_p]
                
                # Récupérer les pièces de ce projet et les diviser par listes
                pieces_p = [p for p in db_pieces if p["nom_projet"] == nom_p]
                listes_dict = {}
                
                if pieces_p:
                    df_pieces_temp = pd.DataFrame([{"Nom de Liste": pc["nom_liste"], "Référence": pc["reference"], "Profil": pc["profil"], "Longueur max (mm)": pc["longueur"], "Quantité": pc["quantite"], "Angle Gauche (°)": pc["angle_g"], "Angle Droit (°)": pc["angle_d"], "Symétrique": pc["symetrique"]} for pc in pieces_p])
                    
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
        # Création d'un projet par défaut si la base est vide
        st.session_state.df_standards_base = pd.DataFrame([{"Nom du Profil": "Tube 50x50", "Largeur (mm)": 50.0, "Couleur / Finition": "Noir"}])
        st.session_state.workspace = {
            "Nouveau Projet": {
                "profils": formater_df_profils(pd.DataFrame()),
                "listes": {"Liste 1": formater_df_listes(pd.DataFrame())}
            }
        }
        st.session_state.projet_actif = "Nouveau Projet"
        st.session_state.liste_active = "Liste 1"

# -----------------------------------------------------------------------------
# FONCTION D'OPTIMISATION MATHÉMATIQUE
# -----------------------------------------------------------------------------
def optimiser_projet_complet(df_pieces, df_profils, epaisseur_lame):
    resultats_finaux = {}
    df_profils = df_profils.dropna(subset=['Nom du Profil', 'Longueur Barre (mm)', 'Quantité en stock']).copy()
    df_profils = df_profils[df_profils['Nom du Profil'] != ""]
    df_pieces = df_pieces.dropna(subset=['Référence', 'Profil', 'Longueur max (mm)', 'Quantité']).copy()
    df_pieces = df_pieces[df_pieces['Profil'] != ""]

    for index, profil in df_profils.iterrows():
        nom_profil = profil['Nom du Profil']
        largeur_profil = profil.get('Largeur (mm)', 50.0) 
        if pd.isna(largeur_profil): largeur_profil = 50.0
        
        pieces_du_profil = df_pieces[df_pieces['Profil'] == nom_profil]
        if pieces_du_profil.empty: continue 
            
        pieces_liste = []
        for idx, row in pieces_du_profil.iterrows():
            for _ in range(int(row['Quantité'])):
                pieces_liste.append({
                    'liste': row.get('Nom de la Liste', 'Sans Liste'),
                    'ref': row.get('Référence', f'P{idx}'), 
                    'longueur': row['Longueur max (mm)'],
                    'angle_g': row.get('Angle Gauche (°)', 90.0),
                    'angle_d': row.get('Angle Droit (°)', 90.0)
                })

        barres_liste = [{'id': nom_profil, 'longueur': profil['Longueur Barre (mm)']} for _ in range(int(profil['Quantité en stock']))]

        if not barres_liste:
            resultats_finaux[nom_profil] = "PAS_DE_STOCK"
            continue

        max_barre = max([b['longueur'] for b in barres_liste]) if barres_liste else 0
        if any(p['longueur'] > max_barre for p in pieces_liste):
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
            resultats_finaux[nom_profil] = {"statut": "SUCCES", "barres": resultats_barres, "largeur": largeur_profil}
        else:
            resultats_finaux[nom_profil] = "ECHEC"

    return resultats_finaux

# -----------------------------------------------------------------------------
# FONCTION DE DESSIN 
# -----------------------------------------------------------------------------
def dessiner_barre(barre_info, epaisseur_lame, largeur_profil, seuil_chute):
    fig, ax = plt.subplots(figsize=(12, 2))
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
        ax.text(position_actuelle + L/2, largeur_profil/2, f"{p['ref']}\n{L}mm", ha='center', va='center', color='white', fontweight='bold', fontsize=9)
        position_actuelle += L
        
        if position_actuelle + epaisseur_lame <= longueur_totale and position_actuelle < longueur_totale:
            ax.add_patch(patches.Rectangle((position_actuelle, 0), epaisseur_lame, largeur_profil, facecolor='#F44336', edgecolor='none'))
            position_actuelle += epaisseur_lame
            
    if position_actuelle < longueur_totale:
        chute = longueur_totale - position_actuelle
        est_reutilisable = chute >= seuil_chute
        ax.add_patch(patches.Rectangle((position_actuelle, 0), chute, largeur_profil, facecolor='#C8E6C9' if est_reutilisable else '#9E9E9E', edgecolor='black', hatch='' if est_reutilisable else '//'))
        ax.text(position_actuelle + chute/2, largeur_profil/2, f"♻️ Chute à garder\n{chute:.1f} mm" if est_reutilisable else f"Déchet\n{chute:.1f} mm", ha='center', va='center', color='black', fontweight='bold' if est_reutilisable else 'normal', fontsize=9)
        
    ax.set_xlim(0, longueur_totale)
    ax.set_ylim(0, largeur_profil * 1.2)
    ax.axis('off')
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

    st.divider()
    st.header("☁️ Sauvegarde Multi-Tables")
    
    if st.button("☁️ Enregistrer le projet courant", type="primary"):
        with st.spinner("Envoi vers Supabase..."):
            try:
                nom_p = st.session_state.projet_actif
                
                # 1. Sauvegarder le nom du projet (Méthode POST avec Upsert via headers)
                url_proj = f"{SUPABASE_URL}/rest/v1/gp_debit_projets"
                r_proj = requests.post(
                    url_proj, 
                    headers={**HEADERS, "Prefer": "resolution=merge-duplicates"}, 
                    params={"on_conflict":"nom_projet"}, 
                    json=[{"nom_projet": nom_p}]
                )
                if r_proj.status_code not in [200, 201]: raise Exception(f"Erreur table projets : {r_proj.text}")
                
                # 2. Nettoyer et envoyer les profils de ce projet
                df_prof = st.session_state.workspace[nom_p].get("profils_edited", st.session_state.workspace[nom_p]["profils"])
                requete_delete("gp_debit_profils", "nom_projet", nom_p)
                
                insert_profils = []
                for _, r in df_prof.iterrows():
                    nom_profil = str(r["Nom du Profil"]).strip()
                    if nom_profil != "" and nom_profil != "nan" and nom_profil != "None":
                        insert_profils.append({
                            "nom_projet": nom_p, "nom_profil": nom_profil, 
                            "longueur": float(r["Longueur Barre (mm)"]) if pd.notna(r["Longueur Barre (mm)"]) else 0,
                            "largeur": float(r["Largeur (mm)"]) if pd.notna(r["Largeur (mm)"]) else 0, 
                            "couleur": str(r["Couleur / Finition"]), 
                            "quantite": int(r["Quantité en stock"]) if pd.notna(r["Quantité en stock"]) else 0
                        })
                    elif pd.notna(r["Longueur Barre (mm)"]) or pd.notna(r["Quantité en stock"]):
                        st.warning("⚠️ Une ligne de stock a été ignorée car le 'Nom du Profil' est vide.")
                        
                requete_insert("gp_debit_profils", insert_profils)

                # 3. Nettoyer et envoyer les listes de ce projet
                requete_delete("gp_debit_pieces", "nom_projet", nom_p)
                insert_pieces = []
                for l_name, l_base in st.session_state.workspace[nom_p]["listes"].items():
                    df_liste = st.session_state.workspace[nom_p].get("listes_edited", {}).get(l_name, l_base)
                    for _, r in df_liste.iterrows():
                        ref = str(r["Référence"]).strip()
                        if ref != "" and ref != "nan" and ref != "None":
                            insert_pieces.append({
                                "nom_projet": nom_p, "nom_liste": l_name, "reference": ref, 
                                "profil": str(r["Profil"]) if pd.notna(r["Profil"]) else "",
                                "longueur": float(r["Longueur max (mm)"]) if pd.notna(r["Longueur max (mm)"]) else 0, 
                                "quantite": int(r["Quantité"]) if pd.notna(r["Quantité"]) else 0,
                                "angle_g": float(r["Angle Gauche (°)"]) if pd.notna(r["Angle Gauche (°)"]) else 90, 
                                "angle_d": float(r["Angle Droit (°)"]) if pd.notna(r["Angle Droit (°)"]) else 90,
                                "symetrique": bool(r["Symétrique"])
                            })
                        elif pd.notna(r["Longueur max (mm)"]) or pd.notna(r["Quantité"]):
                            st.warning(f"⚠️ Une pièce de la liste '{l_name}' a été ignorée car la 'Référence' est vide.")
                            
                requete_insert("gp_debit_pieces", insert_pieces)
                
                st.success("Projet sauvegardé dans la base avec succès !")
            except Exception as e:
                st.error(f"❌ Erreur Base de données : {e}")

    st.divider()
    st.header("⚙️ Paramètres")
    epaisseur_lame = st.number_input("Lame (mm)", min_value=0.0, value=3.0, step=0.1)
    seuil_chute = st.number_input("Chute récup. (mm)", min_value=10.0, value=500.0, step=10.0)

# -----------------------------------------------------------------------------
# 3. CORPS DE L'APPLICATION
# -----------------------------------------------------------------------------
st.title(f"🪚 Projet : {st.session_state.projet_actif}")
projet_courant = st.session_state.workspace[st.session_state.projet_actif]

tab1, tab2, tab3, tab4 = st.tabs(["📚 1. Base Standard", f"📦 2. Stock ({st.session_state.projet_actif})", "📝 3. Listes de Pièces", "📊 4. Résultats & KPI"])

with tab1:
    st.subheader("Catalogue des Profils Standards (Commun)")
    st.session_state.df_standards_edited = st.data_editor(st.session_state.df_standards_base, num_rows="dynamic", use_container_width=True, key="editor_std", hide_index=True, column_config={"Nom du Profil": st.column_config.TextColumn(required=True)})
    if st.button("Sauvegarder Standards"):
        try:
            r_del = requests.delete(f"{SUPABASE_URL}/rest/v1/gp_debit_standards?nom_profil=not.is.null", headers=HEADERS)
            if r_del.status_code not in [200, 204]: raise Exception(f"Delete fail: {r_del.text}")
            
            insert_std = [{"nom_profil": str(r["Nom du Profil"]), "largeur": float(r["Largeur (mm)"]) if pd.notna(r["Largeur (mm)"]) else 0, "couleur": str(r["Couleur / Finition"])} for _, r in st.session_state.df_standards_edited.iterrows() if pd.notna(r["Nom du Profil"]) and str(r["Nom du Profil"]).strip() != ""]
            requete_insert("gp_debit_standards", insert_std)
            st.toast("Standards sauvegardés", icon="✅")
        except Exception as e:
            st.error(f"Erreur Standards : {e}")

with tab2:
    st.subheader(f"Profils et Stock dédiés au projet : {st.session_state.projet_actif}")
    projet_courant["profils_edited"] = st.data_editor(projet_courant["profils"], num_rows="dynamic", use_container_width=True, key=f"editor_stock_{st.session_state.projet_actif}", hide_index=True, column_config={"Nom du Profil": st.column_config.TextColumn(required=True)})

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
        with st.expander("➕ Créer une nouvelle liste"):
            nouvelle_liste = st.text_input("Nom")
            if st.button("Ajouter") and nouvelle_liste:
                if nouvelle_liste not in projet_courant["listes"]:
                    projet_courant["listes"][nouvelle_liste] = formater_df_listes(pd.DataFrame())
                    st.session_state.liste_active = nouvelle_liste
                    st.rerun()

    if st.session_state.liste_active in projet_courant["listes"]:
        st.markdown(f"### ✏️ Liste : **{st.session_state.liste_active}**")
        
        profils_actuels = projet_courant.get("profils_edited", projet_courant["profils"])
        noms_profils_disponibles = profils_actuels['Nom du Profil'].dropna().replace("", pd.NA).dropna().unique().tolist() if "Nom du Profil" in profils_actuels.columns and not profils_actuels.empty else ["Aucun profil défini"]

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
    if st.button("🚀 Lancer l'optimisation", type="primary"):
        with st.spinner('Calcul par l\'IA...'):
            frames_pieces = []
            for nom_liste in projet_courant["listes"].keys():
                df_l = projet_courant.get("listes_edited", {}).get(nom_liste, projet_courant["listes"][nom_liste])
                if not df_l.empty:
                    df_temp = df_l.copy()
                    df_temp['Nom de la Liste'] = nom_liste 
                    frames_pieces.append(df_temp)
            
            df_pieces_global = pd.concat(frames_pieces, ignore_index=True) if frames_pieces else pd.DataFrame()
            
            if df_pieces_global.empty: st.info("Aucune pièce.")
            else:
                resultats = optimiser_projet_complet(df_pieces_global, projet_courant.get("profils_edited", projet_courant["profils"]), epaisseur_lame)
                total_longueur_pieces = sum(p['longueur'] for res in resultats.values() if type(res) == dict and res["statut"] == "SUCCES" for b in res["barres"] for p in b['pieces'])
                total_longueur_barres = sum(b['barre_longueur'] for res in resultats.values() if type(res) == dict and res["statut"] == "SUCCES" for b in res["barres"])
                
                if total_longueur_barres > 0:
                    rendement = (total_longueur_pieces / total_longueur_barres) * 100
                    col1, col2, col3 = st.columns(3)
                    col1.metric("Matière Consommée", f"{total_longueur_barres / 1000:.2f} mètres")
                    col2.metric("Matière Utile (Pièces)", f"{total_longueur_pieces / 1000:.2f} mètres")
                    col3.metric("Rendement", f"{rendement:.1f} %", f"-{100-rendement:.1f} % de chute", delta_color="inverse")
                    st.divider()

                for nom_profil, resultat in resultats.items():
                    st.markdown(f"### 🔹 Profil : {nom_profil}")
                    if type(resultat) == str: st.error(f"❌ {resultat}")
                    else:
                        st.success(f"✅ {len(resultat['barres'])} barre(s).")
                        for idx, barre in enumerate(resultat["barres"]):
                            with st.expander(f"Barre {idx+1} (Longueur: {barre['barre_longueur']} mm) - Chute : {barre['chute']:.1f} mm", expanded=True):
                                st.pyplot(dessiner_barre(barre, epaisseur_lame, resultat["largeur"], seuil_chute))
