import streamlit as st
import pandas as pd
from io import BytesIO

import database as db
import optimizer as opt
import drawing as draw

# -----------------------------------------------------------------------------
# CONFIGURATION DE LA PAGE
# -----------------------------------------------------------------------------
st.set_page_config(page_title="Optimisation de Débitage Pro", page_icon="🪚", layout="wide")
SEUIL_CHUTE = 300.0 

# -----------------------------------------------------------------------------
# CHARGEMENT DEPUIS SUPABASE
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
    
    projet_courant = st.session_state.workspace[st.session_state.projet_actif]
    
    # SECURITÉ 2.1 : Détection suppression Profils de Projet
    df_prof_actuel = projet_courant.get("profils_edited", projet_courant["profils"])
    a_supprime_prof = len(df_prof_actuel) < len(projet_courant["profils"])
    pwd_proj = ""
    
    if a_supprime_prof:
        st.warning("⚠️ Des profils ont été supprimés.")
        pwd_proj = st.text_input("Mot de passe requis pour supprimer", type="password", key="pwd_proj")
        
    if st.button("☁️ Enregistrer le projet courant", type="primary"):
        if a_supprime_prof and pwd_proj != "4855":
            st.error("❌ Mot de passe incorrect. Enregistrement bloqué.")
        else:
            with st.spinner("Envoi vers Supabase..."):
                try:
                    dict_listes = {}
                    for l_name, l_base in projet_courant["listes"].items():
                        dict_listes[l_name] = projet_courant.get("listes_edited", {}).get(l_name, l_base)
                    
                    try:
                        pieces_ignorees = db.sauvegarder_projet(st.session_state.projet_actif, df_prof_actuel, dict_listes)
                        # Mise à jour de la base locale après succès
                        projet_courant["profils"] = df_prof_actuel
                        
                        if pieces_ignorees:
                            for nom_l in set(pieces_ignorees):
                                st.warning(f"⚠️ Une pièce de la liste '{nom_l}' a été ignorée car la 'Référence' est vide.")
                        st.success("Projet sauvegardé avec succès !")
                    except Exception as db_err:
                        if str(db_err) == "WARNING_COLONNE_MANQUANTE":
                            st.warning("⚠️ Sauvegardé, MAIS la colonne 'coupe_section' n'existe pas dans Supabase.")
                        else:
                            raise db_err

                except Exception as e:
                    st.error(f"❌ Erreur Base de données : {e}")

    st.divider()
    st.header("⚙️ Paramètres Machine")
    epaisseur_lame = st.number_input("Lame (mm)", min_value=0.0, value=3.0, step=0.1)

# -----------------------------------------------------------------------------
# CORPS DE L'APPLICATION
# -----------------------------------------------------------------------------
st.title(f"🪚 Projet : {st.session_state.projet_actif}")

tab1, tab2, tab3, tab4 = st.tabs(["📚 1. Base Standard", f"📦 2. Profils du Projet ({st.session_state.projet_actif})", "📝 3. Listes de Pièces", "📊 4. Résultats & Commandes"])

with tab1:
    col1, col2 = st.columns([2, 1])
    with col1:
        st.subheader("Catalogue des Profils Standards (Commun)")
    with col2:
        with st.expander("📥 Importer depuis Excel"):
            st.info("Colonnes requises : Matériau, Nom, Longueur Barre (mm), Section A (mm), Section B (mm), Épaisseur (mm), Poids (kg/m)")
            fichier_std = st.file_uploader("Fichier Standards (.xlsx)", type=["xlsx", "xls"], key="import_std")
            if fichier_std and st.button("Ajouter à la base"):
                try:
                    df_new_std = pd.read_excel(fichier_std)
                    df_new_std = db.formater_df_standards(df_new_std)
                    df_combined = pd.concat([st.session_state.df_standards_base, df_new_std]).drop_duplicates(subset=["Nom"], keep="last")
                    st.session_state.df_standards_base = df_combined
                    st.rerun()
                except Exception as e:
                    st.error(f"Erreur d'import : {e}")

    st.session_state.df_standards_edited = st.data_editor(
        st.session_state.df_standards_base, num_rows="dynamic", use_container_width=True, key="editor_std", hide_index=True, 
        column_config={
            "Matériau": st.column_config.SelectboxColumn("Matériau", options=["ALUMINIUM", "ACIER", "INOX"], required=True),
            "Nom": st.column_config.TextColumn("Nom", required=True),
            "Longueur Barre (mm)": st.column_config.NumberColumn("Longueur Barre (mm)"),
            "Section A (mm)": st.column_config.NumberColumn("Section A (mm)", required=True),
            "Section B (mm)": st.column_config.NumberColumn("Section B (mm)", required=True)
        }
    )
    
    # SECURITÉ 1.1 : Détection suppression Standards
    a_supprime_std = len(st.session_state.df_standards_edited) < len(st.session_state.df_standards_base)
    pwd_std = ""
    if a_supprime_std:
        st.warning("⚠️ Vous avez supprimé des profils standards.")
        pwd_std = st.text_input("Mot de passe requis", type="password", key="pwd_std")

    if st.button("Sauvegarder Standards dans la Base", type="primary"):
        if a_supprime_std and pwd_std != "4855":
            st.error("❌ Mot de passe incorrect.")
        else:
            with st.spinner("Sauvegarde en cours..."):
                try:
                    db.sauvegarder_standards(st.session_state.df_standards_edited)
                    st.session_state.df_standards_base = st.session_state.df_standards_edited
                    st.toast("Standards sauvegardés", icon="✅")
                except Exception as e:
                    if str(e) == "WARNING_COLONNE_MANQUANTE_STD":
                        st.warning("⚠️ Standards sauvegardés, MAIS la colonne 'longueur_barre' n'existe pas dans la table 'gp_debit_standards' sur Supabase.")
                        st.session_state.df_standards_base = st.session_state.df_standards_edited
                    else:
                        st.error(f"Erreur Standards : {e}")

with tab2:
    st.subheader(f"Profils (Barres d'approvisionnement) : {st.session_state.projet_actif}")
    projet_courant["profils_edited"] = st.data_editor(
        projet_courant["profils"], num_rows="dynamic", use_container_width=True, key=f"editor_stock_{st.session_state.projet_actif}", hide_index=True, 
        column_config={"Nom": st.column_config.TextColumn(required=True)}
    )

with tab3:
    col_gauche, col_droite = st.columns([3, 1])
    noms_listes = list(projet_courant["listes"].keys())
    
    with col_droite:
        st.markdown("### 📊 Aperçu du Projet")
        total_pieces = 0
        frames_pour_export = []
        for nom_l in noms_listes:
            df_apercu = projet_courant.get("listes_edited", {}).get(nom_l, projet_courant["listes"][nom_l])
            
            # Conversion sécurisée en nombre pour éviter l'erreur de type lors de l'édition du tableau
            qte = int(pd.to_numeric(df_apercu['Quantité'], errors='coerce').fillna(0).sum()) if not df_apercu.empty else 0
            
            st.write(f"- **{nom_l}** : {qte} pièce(s)")
            total_pieces += qte
            
            if not df_apercu.empty:
                df_export = df_apercu.copy()
                df_export.insert(0, "Nom de la Liste", nom_l)
                frames_pour_export.append(df_export)
                
        st.divider()
        if frames_pour_export:
            df_global_export = pd.concat(frames_pour_export, ignore_index=True)
            output = BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                df_global_export.to_excel(writer, index=False, sheet_name="Toutes les pièces")
            st.download_button("💾 Exporter tout en Excel (.xlsx)", data=output.getvalue(), file_name=f"{st.session_state.projet_actif}_pieces.xlsx", type="primary", use_container_width=True)

    with col_gauche:
        mode_vue = st.radio("Mode d'affichage", ["Vue par Liste (Classique)", "Toutes les Pièces (Vue Globale)"], horizontal=True)
        
        profils_projet = projet_courant.get("profils_edited", projet_courant["profils"])['Nom'].dropna().unique().tolist()
        profils_standards = st.session_state.df_standards_base['Nom'].dropna().unique().tolist()
        tous_les_profils = sorted(list(set(profils_projet + profils_standards)))

        if mode_vue == "Vue par Liste (Classique)":
            c1, c2, c3 = st.columns([2, 1, 1])
            with c1:
                liste_choisie = st.selectbox("📂 Liste active :", noms_listes, index=noms_listes.index(st.session_state.liste_active) if st.session_state.liste_active in noms_listes else 0)
                if liste_choisie != st.session_state.liste_active:
                    st.session_state.liste_active = liste_choisie
                    st.rerun()
            with c2:
                with st.expander("⚙️ Options Liste"):
                    st.markdown("**Renommer**")
                    nouveau_nom = st.text_input("Nouveau nom", value=st.session_state.liste_active, key="rename_list")
                    if st.button("Valider"):
                        if nouveau_nom != st.session_state.liste_active and nouveau_nom not in projet_courant["listes"]:
                            anc_nom = st.session_state.liste_active
                            projet_courant["listes"][nouveau_nom] = projet_courant["listes"].pop(anc_nom)
                            if "listes_edited" in projet_courant and anc_nom in projet_courant["listes_edited"]:
                                projet_courant["listes_edited"][nouveau_nom] = projet_courant["listes_edited"].pop(anc_nom)
                            st.session_state.liste_active = nouveau_nom
                            st.rerun()
                        elif nouveau_nom in projet_courant["listes"] and nouveau_nom != st.session_state.liste_active:
                            st.error("Nom déjà pris.")
                            
                    st.divider()
                    st.markdown("**Supprimer**")
                    pwd_list = st.text_input("Mot de passe", type="password", key="pwd_list")
                    if st.button("🗑️ Supprimer"):
                        if pwd_list == "4855":
                            anc_nom = st.session_state.liste_active
                            del projet_courant["listes"][anc_nom]
                            if "listes_edited" in projet_courant and anc_nom in projet_courant["listes_edited"]:
                                del projet_courant["listes_edited"][anc_nom]
                            
                            restantes = list(projet_courant["listes"].keys())
                            if restantes: st.session_state.liste_active = restantes[0]
                            else:
                                projet_courant["listes"]["Liste 1"] = db.formater_df_listes(pd.DataFrame())
                                st.session_state.liste_active = "Liste 1"
                            st.rerun()
                        elif pwd_list != "":
                            st.error("Mot de passe incorrect.")

            with c3:
                with st.expander("➕ Ajouter"):
                    st.markdown("**Nouvelle Liste**")
                    nouvelle_liste = st.text_input("Nom", key="add_list")
                    if st.button("Créer") and nouvelle_liste:
                        if nouvelle_liste not in projet_courant["listes"]:
                            projet_courant["listes"][nouvelle_liste] = db.formater_df_listes(pd.DataFrame())
                            st.session_state.liste_active = nouvelle_liste
                            st.rerun()
                    st.divider()
                    st.markdown("**Importer Excel ici**")
                    st.caption("Col: Référence, Profil, Longueur (mm), Quantité, Coupe sur Section, Angle Gauche (°), Angle Droite (°), Symétrique")
                    fichier_excel = st.file_uploader("Fichier", type=["xlsx"], label_visibility="collapsed")
                    if st.button("Importer") and fichier_excel:
                        try:
                            df_excel = pd.read_excel(fichier_excel)
                            df_formate = db.formater_df_listes(df_excel)
                            df_formate = df_formate.dropna(subset=["Référence", "Profil"], how='all')
                            liste_actuelle = st.session_state.liste_active
                            df_existante = projet_courant.get("listes_edited", {}).get(liste_actuelle, projet_courant["listes"][liste_actuelle])
                            df_fusion = pd.concat([df_existante, df_formate], ignore_index=True)
                            projet_courant["listes"][liste_actuelle] = df_fusion
                            if "listes_edited" not in projet_courant: projet_courant["listes_edited"] = {}
                            projet_courant["listes_edited"][liste_actuelle] = df_fusion
                            st.rerun()
                        except Exception as e:
                            st.error(f"Erreur d'import : {e}")

            df_liste_active = projet_courant.get("listes_edited", {}).get(st.session_state.liste_active, projet_courant["listes"][st.session_state.liste_active])
            if "listes_edited" not in projet_courant: projet_courant["listes_edited"] = {}
                
            projet_courant["listes_edited"][st.session_state.liste_active] = st.data_editor(
                df_liste_active, num_rows="dynamic", use_container_width=True, key=f"editor_list_{st.session_state.projet_actif}_{st.session_state.liste_active}", hide_index=True,
                column_config={
                    "Référence": st.column_config.TextColumn(required=True),
                    "Profil": st.column_config.SelectboxColumn("Profil", options=tous_les_profils, required=True),
                    "Coupe sur Section": st.column_config.SelectboxColumn("Section", options=["A", "B"], required=True)
                }
            )

        else:
            st.info("💡 Tu peux changer la colonne 'Nom de la Liste' d'une pièce pour la déplacer, puis clique sur Valider.")
            frames_globales = []
            for l_name, df_l in projet_courant["listes"].items():
                df_temp = projet_courant.get("listes_edited", {}).get(l_name, df_l).copy()
                df_temp.insert(0, "Nom de la Liste", l_name)
                frames_globales.append(df_temp)
                
            df_global_view = pd.concat(frames_globales, ignore_index=True) if frames_globales else pd.DataFrame(columns=["Nom de la Liste"] + db.COL_LISTES)
            
            df_global_edited = st.data_editor(
                df_global_view, num_rows="dynamic", use_container_width=True, key=f"editor_global_{st.session_state.projet_actif}", hide_index=True,
                column_config={
                    "Nom de la Liste": st.column_config.SelectboxColumn("Nom de la Liste", options=noms_listes, required=True),
                    "Profil": st.column_config.SelectboxColumn("Profil", options=tous_les_profils, required=True),
                    "Coupe sur Section": st.column_config.SelectboxColumn("Section", options=["A", "B"], required=True)
                }
            )
            
            if st.button("✅ Valider les déplacements inter-listes", type="primary"):
                nouvelles_listes = {}
                for l_name in noms_listes: 
                    df_filtre = df_global_edited[df_global_edited["Nom de la Liste"] == l_name].drop(columns=["Nom de la Liste"])
                    nouvelles_listes[l_name] = df_filtre
                projet_courant["listes_edited"] = nouvelles_listes
                st.success("Modifications répercutées avec succès !")
                st.rerun()

with tab4:
    st.subheader(f"Plans de coupe et Commandes du projet : {st.session_state.projet_actif}")
    
    listes_a_optimiser = st.multiselect("Sélectionnez la ou les liste(s) à produire :", options=noms_listes, default=noms_listes)
    
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
                    resultats = opt.optimiser_projet_complet(df_pieces_global, profils_a_utiliser, epaisseur_lame)
                    
                    if not resultats:
                        st.warning("⚠️ L'optimisation n'a rien pu calculer. Avez-vous bien renseigné la Longueur de Barre dans l'onglet 2 ?")
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
                            
                            # --- GÉNÉRATION DU PDF A4 EN ARRIÈRE-PLAN ---
                            metrics_pdf = {
                                "conso": total_longueur_barres / 1000,
                                "utile": total_longueur_pieces / 1000,
                                "rendement": rendement,
                                "peinture": total_surface_peinture,
                                "epaisseur_lame": epaisseur_lame,
                                "seuil_chute": SEUIL_CHUTE
                            }
                            pdf_buffer = draw.generer_rapport_pdf(resultats, st.session_state.projet_actif, metrics_pdf)
                            
                            col1, col2, col3, col4, col5 = st.columns([1.5, 1.5, 1.5, 1.5, 2])
                            col1.metric("Matière Consommée", f"{total_longueur_barres / 1000:.2f} m")
                            col2.metric("Matière Utile", f"{total_longueur_pieces / 1000:.2f} m")
                            col3.metric("Rendement", f"{rendement:.1f} %", f"-{100-rendement:.1f} %", delta_color="inverse")
                            col4.metric("Surface Peinture", f"{total_surface_peinture:.2f} m²")
                            with col5:
                                st.download_button("📄 Télécharger Rapport PDF (A4)", data=pdf_buffer, file_name=f"Rapport_{st.session_state.projet_actif}.pdf", mime="application/pdf", type="primary", use_container_width=True)
                            st.divider()

                        for nom_profil, resultat in resultats.items():
                            st.markdown(f"### 🔹 Profil : {nom_profil}")
                            if type(resultat) == str: 
                                st.error(f"❌ Erreur sur ce profil : {resultat}")
                            else:
                                surface_profil = (resultat.get('longueur_peinture', 0) * resultat.get('longueur_barre_standard', 0) * len(resultat['barres'])) / 1000000.0
                                st.success(f"📦 À commander : {len(resultat['barres'])} barre(s) de {resultat['barres'][0]['barre_longueur']} mm.  *(Surface de peinture : {surface_profil:.2f} m²)*")
                                
                                for idx, barre in enumerate(resultat["barres"]):
                                    with st.expander(f"Barre {idx+1} - Chute : {barre['chute']:.1f} mm", expanded=True):
                                        st.pyplot(draw.dessiner_barre(barre, epaisseur_lame, resultat["largeur"], SEUIL_CHUTE), use_container_width=True)
                                
                                chutes_utiles = [b['chute'] for b in resultat["barres"] if b['chute'] >= SEUIL_CHUTE]
                                if chutes_utiles:
                                    chutes_utiles.sort(reverse=True)
                                    texte_chutes = ", ".join([f"{c:.1f} mm" for c in chutes_utiles])
                                    st.info(f"♻️ Vous générerez **{len(chutes_utiles)} chute(s)** à conserver (>300mm) : {texte_chutes}.")
                            st.divider()
