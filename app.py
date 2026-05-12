import streamlit as st
import pandas as pd

# IMPORT DE NOS TROIS NOUVEAUX MODULES EXPERTS
import database as db
import optimizer as opt
import drawing as draw

# -----------------------------------------------------------------------------
# CONFIGURATION DE LA PAGE
# -----------------------------------------------------------------------------
st.set_page_config(page_title="Optimisation de Débitage Pro", page_icon="🪚", layout="wide")

# Constantes de l'application
SEUIL_CHUTE = 300.0 # Chute réutilisable à 30cm minimum

# -----------------------------------------------------------------------------
# CHARGEMENT DEPUIS SUPABASE (Délégué à database.py)
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
                
                # Appel au module de base de données
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
                    
                    # APPEL À L'OPTIMISEUR (Délégué à optimizer.py)
                    resultats = opt.optimiser_projet_complet(df_pieces_global, profils_a_utiliser, epaisseur_lame)
                    
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
                                        # APPEL AU RENDU GRAPHIQUE (Délégué à drawing.py)
                                        st.pyplot(draw.dessiner_barre(barre, epaisseur_lame, resultat["largeur"], SEUIL_CHUTE), use_container_width=True)
                                
                                chutes_utiles = [b['chute'] for b in resultat["barres"] if b['chute'] >= SEUIL_CHUTE]
                                if chutes_utiles:
                                    chutes_utiles.sort(reverse=True)
                                    texte_chutes = ", ".join([f"{c:.1f} mm" for c in chutes_utiles])
                                    st.info(f"♻️ **Bilan des chutes réutilisables (>300 mm) :** Vous générerez **{len(chutes_utiles)} chute(s)** à conserver en stock ({texte_chutes}).")
                                        
                            st.divider()
