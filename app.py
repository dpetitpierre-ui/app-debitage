import streamlit as st
import pandas as pd
from ortools.sat.python import cp_model
import matplotlib.pyplot as plt
import matplotlib.patches as patches
import json
import math
import requests 

# -----------------------------------------------------------------------------
# 1. CONFIGURATION DE LA PAGE ET CONNEXION SUPABASE
# -----------------------------------------------------------------------------
st.set_page_config(page_title="Optimisation de Débitage Pro", page_icon="🪚", layout="wide")

# Paramètres de connexion Supabase
SUPABASE_URL = "https://wlonolzfkhlyxbojprus.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Indsb25vbHpma2hseXhib2pwcnVzIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NjQyMjY2ODEsImV4cCI6MjA3OTgwMjY4MX0.FwA0c6iwp3sYfI4zEj7xOK_wJKywA3QKmhY5CVM2XHU"
NOM_TABLE_SUPABASE = "gp_debit_workspace"

HEADERS_SUPABASE = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json"
}

# -----------------------------------------------------------------------------
# 1.2 FORMATEURS STRICTS (CORRECTION DÉFINITIVE DU BUG DE DOUBLE SAISIE)
# -----------------------------------------------------------------------------
def formater_df_profils(df):
    if df is None or df.empty:
        return pd.DataFrame({"Nom du Profil": pd.Series(dtype='str'), "Longueur Barre (mm)": pd.Series(dtype='float'), "Largeur (mm)": pd.Series(dtype='float'), "Couleur / Finition": pd.Series(dtype='str'), "Quantité en stock": pd.Series(dtype='Int64')})
    df = df.copy()
    df["Nom du Profil"] = df["Nom du Profil"].fillna("").astype(str)
    df["Longueur Barre (mm)"] = pd.to_numeric(df["Longueur Barre (mm)"], errors='coerce')
    df["Largeur (mm)"] = pd.to_numeric(df["Largeur (mm)"], errors='coerce')
    df["Couleur / Finition"] = df["Couleur / Finition"].fillna("").astype(str)
    df["Quantité en stock"] = pd.to_numeric(df["Quantité en stock"], errors='coerce').astype('Int64')
    return df

def formater_df_listes(df):
    if df is None or df.empty:
        return pd.DataFrame({"Référence": pd.Series(dtype='str'), "Profil": pd.Series(dtype='str'), "Longueur max (mm)": pd.Series(dtype='float'), "Quantité": pd.Series(dtype='Int64'), "Angle Gauche (°)": pd.Series(dtype='float'), "Angle Droit (°)": pd.Series(dtype='float'), "Symétrique": pd.Series(dtype='bool')})
    df = df.copy()
    df["Référence"] = df["Référence"].fillna("").astype(str)
    df["Profil"] = df["Profil"].fillna("").astype(str)
    df["Longueur max (mm)"] = pd.to_numeric(df["Longueur max (mm)"], errors='coerce')
    df["Quantité"] = pd.to_numeric(df["Quantité"], errors='coerce').astype('Int64')
    df["Angle Gauche (°)"] = pd.to_numeric(df["Angle Gauche (°)"], errors='coerce')
    df["Angle Droit (°)"] = pd.to_numeric(df["Angle Droit (°)"], errors='coerce')
    df["Symétrique"] = df["Symétrique"].fillna(True).astype(bool)
    return df

def formater_df_standards(df):
    if df is None or df.empty:
        return pd.DataFrame({"Nom du Profil": pd.Series(dtype='str'), "Largeur (mm)": pd.Series(dtype='float'), "Couleur / Finition": pd.Series(dtype='str')})
    df = df.copy()
    df["Nom du Profil"] = df["Nom du Profil"].fillna("").astype(str)
    df["Largeur (mm)"] = pd.to_numeric(df["Largeur (mm)"], errors='coerce')
    df["Couleur / Finition"] = df["Couleur / Finition"].fillna("").astype(str)
    return df

# Transforme les NaN en null pour éviter les crashs lors de l'envoi JSON
def safe_export(df):
    return df.where(pd.notnull(df), None).to_dict(orient='records')

# -----------------------------------------------------------------------------
# FONCTIONS DE SAUVEGARDE ET CHARGEMENT CLOUD
# -----------------------------------------------------------------------------
def exporter_workspace_json():
    df_std = st.session_state.get('df_standards_edited', st.session_state.df_standards_base)
    data = {"standards": safe_export(df_std), "projets": {}}
    
    for p_name, p_data in st.session_state.workspace.items():
        df_prof = p_data.get("profils_edited", p_data["profils"])
        
        listes_export = {}
        for l_name, l_base in p_data["listes"].items():
            if "listes_edited" in p_data and l_name in p_data["listes_edited"]:
                listes_export[l_name] = safe_export(p_data["listes_edited"][l_name])
            else:
                listes_export[l_name] = safe_export(l_base)
                
        data["projets"][p_name] = {
            "profils": safe_export(df_prof),
            "listes": listes_export
        }
    return data 

def charger_donnees_dans_memoire(data):
    if 'df_standards_edited' in st.session_state: del st.session_state.df_standards_edited
    if 'standards' in data:
        st.session_state.df_standards_base = formater_df_standards(pd.DataFrame(data['standards']))
        
    if 'projets' in data:
        new_workspace = {}
        for p_name, p_data in data["projets"].items():
            df_prof = formater_df_profils(pd.DataFrame(p_data["profils"]))
            dict_listes = {l_name: formater_df_listes(pd.DataFrame(l_df)) for l_name, l_df in p_data["listes"].items()}
            new_workspace[p_name] = {"profils": df_prof, "listes": dict_listes}
            
        st.session_state.workspace = new_workspace
        st.session_state.projet_actif = list(new_workspace.keys())[0]
        prem_liste = list(new_workspace[st.session_state.projet_actif]["listes"].keys())
        st.session_state.liste_active = prem_liste[0] if prem_liste else "Liste 1"

# -----------------------------------------------------------------------------
# 1.5 INITIALISATION DE L'ESPACE DE TRAVAIL (DEPUIS LE CLOUD)
# -----------------------------------------------------------------------------
if 'workspace' not in st.session_state:
    fichier_charge = False
    
    try:
        url_get = f"{SUPABASE_URL}/rest/v1/{NOM_TABLE_SUPABASE}?id=eq.main_workspace"
        response = requests.get(url_get, headers=HEADERS_SUPABASE)
        
        if response.status_code == 200 and len(response.json()) > 0:
            charger_donnees_dans_memoire(response.json()[0]['data'])
            fichier_charge = True
            st.toast("✅ Données synchronisées depuis Supabase !", icon="☁️")
    except Exception as e:
        st.toast("Aucune donnée cloud trouvée ou erreur de connexion.", icon="⚠️")

    if not fichier_charge:
        st.session_state.df_standards_base = formater_df_standards(pd.DataFrame([
            {"Nom du Profil": "Tube Acier 50x50", "Largeur (mm)": 50.0, "Couleur / Finition": "RAL 9005 (Noir)"},
            {"Nom du Profil": "Cornière 30x30", "Largeur (mm)": 30.0, "Couleur / Finition": "Brut / Galva"}
        ]))
        st.session_state.workspace = {
            "Projet Principal": {
                "profils": formater_df_profils(pd.DataFrame([{"Nom du Profil": "Tube Acier 50x50", "Longueur Barre (mm)": 6000.0, "Largeur (mm)": 50.0, "Couleur / Finition": "RAL 9005 (Noir)", "Quantité en stock": 10}])),
                "listes": {"Châssis": formater_df_listes(pd.DataFrame([{"Référence": "Montant", "Profil": "Tube Acier 50x50", "Longueur max (mm)": 1200.0, "Quantité": 2, "Angle Gauche (°)": 45.0, "Angle Droit (°)": 90.0, "Symétrique": True}]))}
            }
        }
        st.session_state.projet_actif = "Projet Principal"
        st.session_state.liste_active = "Châssis"

# -----------------------------------------------------------------------------
# FONCTION D'OPTIMISATION (MULTI-PROFILS)
# -----------------------------------------------------------------------------
def optimiser_projet_complet(df_pieces, df_profils, epaisseur_lame):
    resultats_finaux = {}
    
    # NETTOYAGE CRITIQUE : on ignore les lignes incomplètes pour ne pas faire planter l'IA
    df_profils = df_profils.dropna(subset=['Nom du Profil', 'Longueur Barre (mm)', 'Quantité en stock']).copy()
    df_profils = df_profils[df_profils['Nom du Profil'] != ""]
    
    df_pieces = df_pieces.dropna(subset=['Référence', 'Profil', 'Longueur max (mm)', 'Quantité']).copy()
    df_pieces = df_pieces[df_pieces['Profil'] != ""]

    for index, profil in df_profils.iterrows():
        nom_profil = profil['Nom du Profil']
        largeur_profil = profil.get('Largeur (mm)', 50.0) 
        if pd.isna(largeur_profil): largeur_profil = 50.0 # Sécurité
        
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
        x_bl = x_min + min((dx_g if dx_g > 0 else 0), L)
        x_tl = x_min + min((-dx_g if dx_g < 0 else 0), L)
        x_br = x_max - min((dx_d if dx_d > 0 else 0), L)
        x_tr = x_max - min((-dx_d if dx_d < 0 else 0), L)
        
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
# 2. MENU LATÉRAL - NAVIGATION ENTRE PROJETS
# -----------------------------------------------------------------------------
with st.sidebar:
    st.header("📁 Navigation")
    
    liste_projets = list(st.session_state.workspace.keys())
    projet_choisi = st.selectbox("📌 Projet Actif", liste_projets, index=liste_projets.index(st.session_state.projet_actif))
    
    if projet_choisi != st.session_state.projet_actif:
        st.session_state.projet_actif = projet_choisi
        st.session_state.liste_active = list(st.session_state.workspace[projet_choisi]["listes"].keys())[0] if st.session_state.workspace[projet_choisi]["listes"] else None
        st.rerun()

    with st.expander("➕ Créer un nouveau projet"):
        nouveau_projet = st.text_input("Nom du nouveau projet")
        if st.button("Créer le projet") and nouveau_projet:
            if nouveau_projet not in st.session_state.workspace:
                st.session_state.workspace[nouveau_projet] = {
                    "profils": formater_df_profils(pd.DataFrame()),
                    "listes": {"Liste 1": formater_df_listes(pd.DataFrame())}
                }
                st.session_state.projet_actif = nouveau_projet
                st.session_state.liste_active = "Liste 1"
                st.rerun()
            else:
                st.error("Ce nom existe déjà.")

    st.divider()
    st.header("☁️ Sauvegarde Cloud")
    
    st.success("🟢 API Supabase Prête")
    if st.button("☁️ Enregistrer sur le Cloud", type="primary"):
        with st.spinner("Synchronisation avec Supabase en cours..."):
            try:
                data_json = exporter_workspace_json()
                url_post = f"{SUPABASE_URL}/rest/v1/{NOM_TABLE_SUPABASE}"
                headers_upsert = HEADERS_SUPABASE.copy()
                headers_upsert["Prefer"] = "resolution=merge-duplicates"
                
                payload = {"id": "main_workspace", "data": data_json}
                
                response = requests.post(url_post, headers=headers_upsert, json=payload)
                
                if response.status_code in [200, 201]:
                    st.success("Toutes les données sont sauvegardées en ligne !")
                else:
                    st.error(f"Erreur du serveur Supabase : {response.text}")
            except Exception as e:
                st.error(f"Erreur de connexion : {e}")
    
    st.divider()
    st.header("⚙️ Paramètres Machine")
    epaisseur_lame = st.number_input("Épaisseur de la lame (mm)", min_value=0.0, max_value=10.0, value=3.0, step=0.1)
    seuil_chute = st.number_input("Taille mini. chute réutilisable (mm)", min_value=10.0, max_value=5000.0, value=500.0, step=10.0)

# -----------------------------------------------------------------------------
# 3. CORPS DE L'APPLICATION
# -----------------------------------------------------------------------------
st.title(f"🪚 Projet : {st.session_state.projet_actif}")
projet_courant = st.session_state.workspace[st.session_state.projet_actif]

tab1, tab2, tab3, tab4 = st.tabs(["📚 1. Base Standard", f"📦 2. Stock ({st.session_state.projet_actif})", "📝 3. Listes de Pièces", "📊 4. Résultats & KPI"])

with tab1:
    st.subheader("Catalogue des Profils Standards (Commun à tous les projets)")
    st.session_state.df_standards_edited = st.data_editor(
        st.session_state.df_standards_base, num_rows="dynamic", use_container_width=True, key="editor_std", hide_index=True,
        column_config={
            "Nom du Profil": st.column_config.TextColumn("Nom du Profil", required=True),
            "Largeur (mm)": st.column_config.NumberColumn("Largeur (mm)", min_value=1.0, step=1.0, format="%.1f"),
            "Couleur / Finition": st.column_config.TextColumn("Couleur / Finition")
        }
    )

with tab2:
    st.subheader(f"Profils et Stock dédiés au projet : {st.session_state.projet_actif}")
    projet_courant["profils_edited"] = st.data_editor(
        projet_courant["profils"], num_rows="dynamic", use_container_width=True, key=f"editor_stock_{st.session_state.projet_actif}", hide_index=True,
        column_config={
            "Nom du Profil": st.column_config.TextColumn("Nom du Profil", required=True),
            "Longueur Barre (mm)": st.column_config.NumberColumn("Longueur Barre (mm)", min_value=1.0, step=1.0, format="%.1f"),
            "Largeur (mm)": st.column_config.NumberColumn("Largeur (mm)", min_value=1.0, step=1.0, format="%.1f"),
            "Couleur / Finition": st.column_config.TextColumn("Couleur / Finition"),
            "Quantité en stock": st.column_config.NumberColumn("Quantité en stock", min_value=0, step=1)
        }
    )

with tab3:
    col_gauche, col_droite = st.columns([1, 1])
    noms_listes = list(projet_courant["listes"].keys())
    
    with col_gauche:
        if noms_listes:
            liste_choisie = st.selectbox("📂 Liste active à modifier :", noms_listes, index=noms_listes.index(st.session_state.liste_active) if st.session_state.liste_active in noms_listes else 0)
            if liste_choisie != st.session_state.liste_active:
                st.session_state.liste_active = liste_choisie
                st.rerun()
            
    with col_droite:
        with st.expander("➕ Créer une nouvelle liste pour ce projet"):
            nouvelle_liste = st.text_input("Nom de la nouvelle liste")
            if st.button("Ajouter Liste") and nouvelle_liste:
                if nouvelle_liste not in projet_courant["listes"]:
                    projet_courant["listes"][nouvelle_liste] = formater_df_listes(pd.DataFrame())
                    st.session_state.liste_active = nouvelle_liste
                    st.rerun()
                else:
                    st.error("Ce nom existe déjà.")

    if st.session_state.liste_active in projet_courant["listes"]:
        st.markdown(f"### ✏️ Édition de la liste : **{st.session_state.liste_active}**")
        
        profils_actuels = projet_courant.get("profils_edited", projet_courant["profils"])
        if "Nom du Profil" in profils_actuels.columns and not profils_actuels.empty:
            noms_profils_disponibles = profils_actuels['Nom du Profil'].dropna().replace("", pd.NA).dropna().unique().tolist()
        else:
            noms_profils_disponibles = []
            
        if not noms_profils_disponibles: noms_profils_disponibles = ["Aucun profil défini dans le stock"]

        df_liste_active = projet_courant["listes"][st.session_state.liste_active]
        if "listes_edited" not in projet_courant: projet_courant["listes_edited"] = {}
            
        projet_courant["listes_edited"][st.session_state.liste_active] = st.data_editor(
            df_liste_active, num_rows="dynamic", use_container_width=True, key=f"editor_list_{st.session_state.projet_actif}_{st.session_state.liste_active}", hide_index=True,
            column_config={
                "Référence": st.column_config.TextColumn("Réf."),
                "Profil": st.column_config.SelectboxColumn("Profil", options=noms_profils_disponibles, required=True),
                "Longueur max (mm)": st.column_config.NumberColumn("Longueur max hors-tout", min_value=1.0, step=1.0, format="%.1f"),
                "Quantité": st.column_config.NumberColumn("Qté", min_value=1, step=1),
                "Angle Gauche (°)": st.column_config.NumberColumn("Angle G (°)", min_value=10.0, max_value=170.0, step=1.0, format="%d"),
                "Angle Droit (°)": st.column_config.NumberColumn("Angle D (°)", min_value=10.0, max_value=170.0, step=1.0, format="%d"),
                "Symétrique": st.column_config.CheckboxColumn("Symétrique", default=True)
            }
        )

with tab4:
    st.subheader(f"Plans de coupe du projet : {st.session_state.projet_actif}")
    
    if st.button("🚀 Lancer l'optimisation du projet entier", type="primary"):
        with st.spinner('Fusion des listes et calcul par l\'IA...'):
            frames_pieces = []
            for nom_liste in projet_courant["listes"].keys():
                if "listes_edited" in projet_courant and nom_liste in projet_courant["listes_edited"]:
                    df_l = projet_courant["listes_edited"][nom_liste]
                else:
                    df_l = projet_courant["listes"][nom_liste]
                    
                if not df_l.empty:
                    df_temp = df_l.copy()
                    df_temp['Nom de la Liste'] = nom_liste 
                    frames_pieces.append(df_temp)
            
            df_pieces_global = pd.concat(frames_pieces, ignore_index=True) if frames_pieces else pd.DataFrame()
            
            if df_pieces_global.empty:
                st.info("Aucune pièce à optimiser.")
            else:
                profils_a_utiliser = projet_courant.get("profils_edited", projet_courant["profils"])
                resultats = optimiser_projet_complet(df_pieces_global, profils_a_utiliser, epaisseur_lame)
                
                total_longueur_pieces = 0
                total_longueur_barres = 0
                
                for profil_res in resultats.values():
                    if type(profil_res) == dict and profil_res["statut"] == "SUCCES":
                        for b in profil_res["barres"]:
                            total_longueur_barres += b['barre_longueur']
                            for p in b['pieces']:
                                total_longueur_pieces += p['longueur']
                
                if total_longueur_barres > 0:
                    rendement = (total_longueur_pieces / total_longueur_barres) * 100
                    st.markdown("### 📈 Indicateurs de Performance")
                    col1, col2, col3 = st.columns(3)
                    col1.metric("Matière Consommée", f"{total_longueur_barres / 1000:.2f} mètres")
                    col2.metric("Matière Utile (Pièces)", f"{total_longueur_pieces / 1000:.2f} mètres")
                    col3.metric("Taux de Rendement", f"{rendement:.1f} %", f"-{100-rendement:.1f} % de chute", delta_color="inverse")
                    st.divider()

                for nom_profil, resultat in resultats.items():
                    st.markdown(f"### 🔹 Profil : {nom_profil}")
                    if resultat == "PAS_DE_STOCK": st.error("❌ Pas de barres en stock pour les pièces demandées.")
                    elif resultat == "ERREUR_TAILLE": st.error("❌ Impossible : Une pièce est plus longue que la barre.")
                    elif resultat == "ECHEC": st.error("❌ Aucune solution (vérifie tes quantités en stock).")
                    else:
                        st.success(f"✅ {len(resultat['barres'])} barre(s) utilisée(s).")
                        for idx, barre in enumerate(resultat["barres"]):
                            with st.expander(f"Barre {idx+1} (Longueur: {barre['barre_longueur']} mm) - Chute : {barre['chute']:.1f} mm", expanded=True):
                                fig = dessiner_barre(barre, epaisseur_lame, resultat["largeur"], seuil_chute)
                                st.pyplot(fig)
                                for p in barre['pieces']:
                                    st.write(f"- [Liste: **{p['liste']}**] | Réf: {p['ref']} ➔ {p['longueur']} mm (Angles : {p['angle_g']}° / {p['angle_d']}°)")
                    st.divider()
