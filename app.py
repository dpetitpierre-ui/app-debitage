import streamlit as st
import pandas as pd
from ortools.sat.python import cp_model
import matplotlib.pyplot as plt
import matplotlib.patches as patches
import math

# IMPORT DE NOTRE NOUVEAU MODULE DE BASE DE DONNÉES
import database as db

# -----------------------------------------------------------------------------
# CONFIGURATION DE LA PAGE
# -----------------------------------------------------------------------------
st.set_page_config(page_title="Optimisation de Débitage Pro", page_icon="🪚", layout="wide")

# Constantes de l'application
SEUIL_CHUTE = 300.0 # Chute réutilisable à 30cm minimum

# -----------------------------------------------------------------------------
# CHARGEMENT DEPUIS SUPABASE (Désormais délégué à database.py)
# -----------------------------------------------------------------------------
if 'workspace' not in st.session_state:
    with st.spinner("Connexion à la base de données..."):
        df_standards_base, workspace = db.charger_donnees_initiales()
        
        st.session_state.df_standards_base = df_standards_base
        st.session_state.workspace = workspace
        st.session_state.projet_actif = list(workspace.keys())[0]
        st.session_state.liste_active = list(workspace[st.session_state.projet_actif]["listes"].keys())[0] if workspace[st.session_state.projet_actif]["listes"] else None
        st.toast("✅ Base de données connectée", icon="☁️")

# -----------------------------------------------------------------------------
# FONCTION D'OPTIMISATION MATHÉMATIQUE (TASSEMENT MAXIMAL)
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
            
        pieces_liste.sort(key=lambda item: item['longueur'], reverse=True)

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

        for j in range(1, len(barres_liste)):
            model.Add(y[j] <= y[j-1])

        lame = int(epaisseur_lame * 10)
        for j in range(len(barres_liste)):
            capacite = int(barres_liste[j]['longueur'] * 10)
            model.Add(sum((int(pieces_liste[i]['longueur'] * 10) + lame) * x[i, j] for i in range(len(pieces_liste))) <= (capacite + lame) * y[j])

        poids_lourd_barre = max(10000, len(pieces_liste) * len(barres_liste) + 100)
        
        termes_objectif = []
        for j in range(len(barres_liste)):
            termes_objectif.append(y[j] * poids_lourd_barre)
            for i in range(len(pieces_liste)):
                termes_objectif.append(x[i, j] * j)
                
        model.Minimize(sum(termes_objectif))
        
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
# FONCTION DE DESSIN
# -----------------------------------------------------------------------------
def dessiner_barre(barre_info, epaisseur_lame, largeur_profil, seuil_chute):
    fig, ax = plt.subplots(figsize=(20, 0.4)) 
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
        ax.text(position_actuelle + L/2, largeur_profil/2, f"{p['ref']}\n{L}mm", ha='center', va='center', color='white', fontweight='bold', fontsize=7)
        position_actuelle += L
        
        if position_actuelle + epaisseur_lame <= longueur_totale and position_actuelle < longueur_totale:
            ax.add_patch(patches.Rectangle((position_actuelle, 0), epaisseur_lame, largeur_profil, facecolor='#F44336', edgecolor='none'))
            position_actuelle += epaisseur_lame
            
    if position_actuelle < longueur_totale:
        chute = longueur_totale - position_actuelle
        est_reutilisable = chute >= seuil_chute
        ax.add_patch(patches.Rectangle((position_actuelle, 0), chute, largeur_profil, facecolor='#C8E6C9' if est_reutilisable else '#9E9E9E', edgecolor='black', hatch='' if est_reutilisable else '//'))
        ax.text(position_actuelle + chute/2, largeur_profil/2, f"♻️ Chute\n{chute:.1f} mm" if est_reutilisable else f"Déchet\n{chute:.1f} mm", ha='center', va='center', color='black', fontweight='bold' if est_reutilisable else 'normal', fontsize=7)
        
    ax.set_xlim(0, longueur_totale)
    ax.set_ylim(0, largeur_profil * 1.05)
    ax.axis('off')
    
    fig.subplots_adjust(left=0, right=1, top=1, bottom=0, wspace=0, hspace=0)
    return fig

# -----------------------------------------------------------------------------
# MENU LATÉRAL
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
                st.session_state.workspace[nouveau_projet] = {"profils": db.formater_df_profils(pd.DataFrame()), "listes": {"Liste 1": db.formater_df_listes(pd.DataFrame())}}
                st.session_state.projet_actif = nouveau_projet
                st.session_state.liste_active = "Liste 1"
                st.rerun()
            else:
                st.error("Ce nom existe déjà.")

    st.divider()
    st.header("☁️ Sauvegarde")
    
    if st.button("☁️ Enregistrer le projet courant", type="primary"):
        with st.spinner("Envoi vers Supabase..."):
            try:
                nom_p = st.session_state.projet_actif
                projet_courant = st.session_state.workspace[nom_p]
                
                # Extraction propre des données éditées par l'utilisateur
                df_prof = projet_courant.get("profils_edited", projet_courant["profils"])
                dict_listes = {}
                for l_name, l_base in projet_courant["listes"].items():
                    dict_listes[l_name] = projet_courant.get("listes_edited", {}).get(l_name, l_base)
                
                # Appel au nouveau module de base de données
                pieces_ignorees = db.sauvegarder_projet(nom_p, df_prof, dict_listes)
                
                if pieces_ignorees:
                    for nom_l in set(pieces_ignorees):
                        st.warning(f"⚠️ Une pièce de la liste '{nom_l}' a été ignorée car la 'Référence' est vide.")
                        
                st.success("Projet sauvegardé avec succès !")
            except Exception as e:
                st.error(f"❌ Erreur Base de données : {e}")

    st.divider()
    st.header("⚙️ Paramètres Machine")
    epaisseur_lame = st.number_input("Lame (mm)", min_value=0.0, value=3.0, step=0.1)

# -----------------------------------------------------------------------------
# CORPS DE L'APPLICATION
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
        with st.spinner("Sauvegarde en cours..."):
            try:
                db.sauvegarder_standards(st.session_state.df_standards_edited)
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
                    projet_courant["listes"][nouvelle_liste] = db.formater_df_listes(pd.DataFrame())
                    st.session_state.liste_active = nouvelle_liste
                    st.rerun()
                else:
                    st.error("Ce nom existe déjà.")
                    
        with st.expander(f"📥 Importer depuis Excel dans la liste actuelle"):
            fichier_excel = st.file_uploader(f"Ajouter au {st.session_state.liste_active} (.xlsx)", type=["xlsx"])
            
            if st.button("Importer les pièces", type="primary") and fichier_excel:
                try:
                    df_excel = pd.read_excel(fichier_excel)
                    df_formate = db.formater_df_listes(df_excel)
                    df_formate = df_formate.dropna(subset=["Référence", "Profil"], how='all')
                    
                    liste_actuelle = st.session_state.liste_active
                    df_existante = projet_courant.get("listes_edited", {}).get(liste_actuelle, projet_courant["listes"][liste_actuelle])
                    
                    df_fusion = pd.concat([df_existante, df_formate], ignore_index=True)
                    
                    projet_courant["listes"][liste_actuelle] = df_fusion
                    if "listes_edited" not in projet_courant:
                        projet_courant["listes_edited"] = {}
                    projet_courant["listes_edited"][liste_actuelle] = df_fusion
                    
                    st.rerun()
                except Exception as e:
                    st.error(f"Erreur lors de la lecture du fichier : {e}")

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
                    
                    # APPEL À L'OPTIMISEUR (Reste intact pour l'instant)
                    resultats = optimiser_projet_complet(df_pieces_global, profils_a_utiliser, epaisseur_lame)
                    
                    if not resultats:
                        st.warning("⚠️ L'optimisation n'a rien pu calculer. Voici ce qu'il manque :")
                        st.info("1. Avez-vous bien renseigné la **Longueur de Barre** dans l'onglet 2 ?\n"
                                "2. Les noms des profils dans vos listes sont-ils **exactement les mêmes** que ceux de l'onglet 2 ?")
                    else:
                        total_longueur_pieces = 0
                        total_longueur_barres = 0
                        total_surface_peinture = 0.0
                        
                        for profil_res in resultats.values():
                            if type(profil_res) == dict and profil_res["statut"] == "SUCCES":
                                nb_barres = len(profil_res["barres"])
                                perimetre = profil_res.get("longueur_peinture", 0)
                                longueur_barre = profil_res.get("longueur_barre_standard", 0)
                                
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
                                surface_profil = (resultat.get('longueur_peinture', 0) * resultat.get('longueur_barre_standard', 0) * len(resultat['barres'])) / 1000000.0
                                st.success(f"📦 À commander : {len(resultat['barres'])} barre(s) de {resultat['barres'][0]['barre_longueur']} mm.  *(Surface de peinture : {surface_profil:.2f} m²)*")
                                
                                for idx, barre in enumerate(resultat["barres"]):
                                    with st.expander(f"Barre {idx+1} (Longueur: {barre['barre_longueur']} mm) - Chute : {barre['chute']:.1f} mm", expanded=True):
                                        st.pyplot(dessiner_barre(barre, epaisseur_lame, resultat["largeur"], SEUIL_CHUTE), use_container_width=True)
                                
                                chutes_utiles = [b['chute'] for b in resultat["barres"] if b['chute'] >= SEUIL_CHUTE]
                                if chutes_utiles:
                                    chutes_utiles.sort(reverse=True)
                                    texte_chutes = ", ".join([f"{c:.1f} mm" for c in chutes_utiles])
                                    st.info(f"♻️ **Bilan des chutes réutilisables (>300 mm) :** Vous générerez **{len(chutes_utiles)} chute(s)** à conserver en stock ({texte_chutes}).")
                                        
                            st.divider()
