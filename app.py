import streamlit as st
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from io import BytesIO

import database as db
import optimizer as opt
import drawing as draw

# -----------------------------------------------------------------------------
# CONFIGURATION DE LA PAGE
# -----------------------------------------------------------------------------
st.set_page_config(page_title="Optimisation de Débitage Pro", page_icon="🪚", layout="wide")

# --- CONSTANTES GLOBALES (SÉCURITÉ PRODUCTION) ---
SEUIL_CHUTE = 300.0 
EPAISSEUR_LAME = 4.0   
CHUTE_MINIMUM = 30.0   

# -----------------------------------------------------------------------------
# BOUCLIER 2 : FONCTIONS D'URL SÉCURISÉES
# -----------------------------------------------------------------------------
def get_projet_url():
    try:
        if hasattr(st, 'query_params'):
            return st.query_params.get("projet")
        elif hasattr(st, 'experimental_get_query_params'):
            params = st.experimental_get_query_params()
            return params.get("projet", [None])[0]
    except:
        pass
    return None

def set_projet_url(nom):
    try:
        if hasattr(st, 'query_params'):
            st.query_params["projet"] = nom
        elif hasattr(st, 'experimental_set_query_params'):
            st.experimental_set_query_params(projet=nom)
    except:
        pass

# -----------------------------------------------------------------------------
# CHARGEMENT DEPUIS SUPABASE
# -----------------------------------------------------------------------------
if 'workspace' not in st.session_state:
    with st.spinner("Connexion à la base de données..."):
        df_standards_base, workspace = db.charger_donnees_initiales()
        
        st.session_state.df_standards_base = df_standards_base
        st.session_state.workspace = workspace
        
        liste_projets = list(workspace.keys())
        
        projet_en_url = get_projet_url()
        if projet_en_url and projet_en_url in liste_projets:
            st.session_state.projet_actif = projet_en_url
        else:
            st.session_state.projet_actif = liste_projets[0]
            
        set_projet_url(st.session_state.projet_actif)
        
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
        set_projet_url(projet_choisi) 
        st.session_state.liste_active = list(st.session_state.workspace[projet_choisi]["listes"].keys())[0] if st.session_state.workspace[projet_choisi]["listes"] else None
        st.rerun()

    with st.expander("➕ Créer un nouveau projet"):
        nouveau_projet = st.text_input("Nom du nouveau projet")
        if st.button("Créer le projet") and nouveau_projet:
            if nouveau_projet not in st.session_state.workspace:
                st.session_state.workspace[nouveau_projet] = {"profils": db.formater_df_profils(pd.DataFrame()), "listes": {"Liste 1": db.formater_df_listes(pd.DataFrame())}}
                st.session_state.projet_actif = nouveau_projet
                set_projet_url(nouveau_projet) 
                st.session_state.liste_active = "Liste 1"
                st.rerun()
            else:
                st.error("Ce nom existe déjà.")

    st.divider()
    st.header("☁️ Sauvegarde")
    
    projet_courant = st.session_state.workspace[st.session_state.projet_actif]
    
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
    st.info(f"🔪 **Épaisseur Lame :** {EPAISSEUR_LAME} mm\n\n🛡️ **Mors de serrage (chute min) :** {CHUTE_MINIMUM} mm\n\n*Ces paramètres sont verrouillés pour garantir l'usinabilité en atelier.*")

# -----------------------------------------------------------------------------
# CORPS DE L'APPLICATION
# -----------------------------------------------------------------------------
st.title(f"🪚 Projet : {st.session_state.projet_actif}")

tab1, tab2, tab3, tab4, tab5 = st.tabs(["📚 1. Base Standard", f"📦 2. Profils du Projet ({st.session_state.projet_actif})", "📝 3. Listes de Pièces", "📊 4. Résultats & Commandes", "🔍 5. Longueur Idéale"])

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

    # BOUCLIER 3 : Retrait pur et simple de 'use_container_width'
    st.session_state.df_standards_edited = st.data_editor(
        st.session_state.df_standards_base, num_rows="dynamic", key="editor_std", hide_index=True, 
        column_config={
            "Matériau": st.column_config.SelectboxColumn("Matériau", options=["ALUMINIUM", "ACIER", "INOX"], required=True),
            "Nom": st.column_config.TextColumn("Nom", required=True),
            "Longueur Barre (mm)": st.column_config.NumberColumn("Longueur Barre (mm)"),
            "Section A (mm)": st.column_config.NumberColumn("Section A (mm)", required=True),
            "Section B (mm)": st.column_config.NumberColumn("Section B (mm)", required=True)
        }
    )
    
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
                        st.warning("⚠️ Standards sauvegardés, MAIS la colonne 'longueur_barre' n'existe pas dans Supabase.")
                        st.session_state.df_standards_base = st.session_state.df_standards_edited
                    else:
                        st.error(f"Erreur Standards : {e}")

with tab2:
    st.subheader(f"Profils (Barres d'approvisionnement) : {st.session_state.projet_actif}")
    projet_courant["profils_edited"] = st.data_editor(
        projet_courant["profils"], num_rows="dynamic", key=f"editor_stock_{st.session_state.projet_actif}", hide_index=True, 
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
            st.download_button("💾 Exporter tout en Excel (.xlsx)", data=output.getvalue(), file_name=f"{st.session_state.projet_actif}_pieces.xlsx", type="primary")

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
                df_liste_active, num_rows="dynamic", key=f"editor_list_{st.session_state.projet_actif}_{st.session_state.liste_active}", hide_index=True,
                column_config={
                    "Référence": st.column_config.TextColumn(required=True),
                    "Profil": st.column_config.SelectboxColumn("Profil", options=tous_les_profils, required=True),
                    "Coupe sur Section": st.column_config.SelectboxColumn("Section", options=["A", "B"], required=True)
                }
            )

        else:
            st.info("💡 Vous pouvez tout éditer ici. Tout est synchronisé automatiquement !")
            frames_globales = []
            for l_name, df_l in projet_courant["listes"].items():
                df_temp = projet_courant.get("listes_edited", {}).get(l_name, df_l).copy()
                df_temp.insert(0, "Nom de la Liste", l_name)
                frames_globales.append(df_temp)
                
            df_global_view = pd.concat(frames_globales, ignore_index=True) if frames_globales else pd.DataFrame(columns=["Nom de la Liste"] + db.COL_LISTES)
            
            df_global_edited = st.data_editor(
                df_global_view, num_rows="dynamic", key=f"editor_global_{st.session_state.projet_actif}", hide_index=True,
                column_config={
                    "Nom de la Liste": st.column_config.SelectboxColumn("Nom de la Liste", options=noms_listes, required=True),
                    "Profil": st.column_config.SelectboxColumn("Profil", options=tous_les_profils, required=True),
                    "Coupe sur Section": st.column_config.SelectboxColumn("Section", options=["A", "B"], required=True)
                }
            )
            
            nouvelles_listes = {}
            for l_name in noms_listes: 
                df_filtre = df_global_edited[df_global_edited["Nom de la Liste"] == l_name].drop(columns=["Nom de la Liste"])
                nouvelles_listes[l_name] = df_filtre
            projet_courant["listes_edited"] = nouvelles_listes

with tab4:
    st.subheader(f"Plans de coupe et Commandes du projet : {st.session_state.projet_actif}")
    
    listes_a_optimiser = st.multiselect("Sélectionnez la ou les liste(s) à produire :", options=noms_listes, default=noms_listes)
    
    if st.button("🚀 Lancer l'optimisation", type="primary"):
        if not listes_a_optimiser:
            st.warning("Veuillez sélectionner au moins une liste à optimiser.")
        else:
            with st.spinner('Calcul ultra-rapide en cours...'):
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
                    profils_projet = projet_courant.get("profils_edited", projet_courant["profils"])
                    profils_standards = st.session_state.get("df_standards_edited", st.session_state.df_standards_base)
                    profils_a_utiliser = pd.concat([profils_projet, profils_standards]).drop_duplicates(subset=['Nom'], keep='first')
                    
                    resultats = opt.optimiser_projet_complet(df_pieces_global, profils_a_utiliser, EPAISSEUR_LAME, CHUTE_MINIMUM)
                    
                    if not resultats:
                        st.warning("⚠️ L'optimisation n'a rien pu calculer. Avez-vous bien renseigné la Longueur de Barre dans l'onglet 1 ou 2 ?")
                    else:
                        total_longueur_pieces = 0
                        total_longueur_barres = 0
                        total_poids = 0.0 # AJOUT CTO : Poids total
                        
                        # AJOUT CTO : Dictionnaire pour la peinture
                        peinture_par_couleur = {}
                        
                        for nom_profil, profil_res in resultats.items():
                            if type(profil_res) == dict and profil_res["statut"] == "SUCCES":
                                nb_barres = len(profil_res["barres"])
                                perimetre = profil_res.get("longueur_peinture", 0)
                                longueur_barre = profil_res.get("longueur_barre_standard", 0)
                                couleur = profil_res.get("couleur", "Brut")
                                poids_ml = profil_res.get("poids_ml", 0.0) # AJOUT CTO
                                
                                # Si vide, on considère Brut
                                if not couleur: couleur = "Brut"
                                
                                surface = (perimetre * longueur_barre * nb_barres) / 1000000.0
                                if surface > 0:
                                    peinture_par_couleur[couleur] = peinture_par_couleur.get(couleur, 0.0) + surface
                                    
                                # AJOUT CTO : Calcul du poids
                                poids_profil = (longueur_barre * nb_barres / 1000.0) * poids_ml
                                total_poids += poids_profil
                                
                                for b in profil_res["barres"]:
                                    total_longueur_barres += b['barre_longueur']
                                    for p in b['pieces']:
                                        total_longueur_pieces += p['longueur']
                        
                        if total_longueur_barres > 0:
                            rendement = (total_longueur_pieces / total_longueur_barres) * 100
                            
                            metrics_pdf = {
                                "conso": total_longueur_barres / 1000,
                                "utile": total_longueur_pieces / 1000,
                                "rendement": rendement,
                                "peinture_par_couleur": peinture_par_couleur,
                                "epaisseur_lame": EPAISSEUR_LAME,
                                "seuil_chute": SEUIL_CHUTE,
                                "poids_total": total_poids # AJOUT CTO
                            }
                            pdf_buffer = draw.generer_rapport_pdf(resultats, st.session_state.projet_actif, metrics_pdf)
                            
                            # Refonte visuelle web pour intégrer les différentes peintures et le poids
                            col1, col2, col3, col4, col5 = st.columns(5)
                            col1.metric("Matière Consommée", f"{total_longueur_barres / 1000:.2f} m")
                            col2.metric("Matière Utile", f"{total_longueur_pieces / 1000:.2f} m")
                            col3.metric("Poids Total", f"{total_poids:.2f} kg")
                            col4.metric("Rendement", f"{rendement:.1f} %", f"-{100-rendement:.1f} %", delta_color="inverse")
                            
                            with col5:
                                st.markdown("🎨 **Surfaces à peindre**")
                                if not peinture_par_couleur:
                                    st.caption("Aucune")
                                else:
                                    for c, s in peinture_par_couleur.items():
                                        label = c if c else "Brut"
                                        st.write(f"- {label}: **{s:.2f} m²**")
                            
                            st.divider()
                            st.download_button("📄 Télécharger le Dossier de Production PDF", data=pdf_buffer, file_name=f"Bordereau_Production_{st.session_state.projet_actif}.pdf", type="primary", use_container_width=True)
                            st.divider()

                        for nom_profil, resultat in resultats.items():
                            st.markdown(f"### 🔹 Profil : {nom_profil}")
                            
                            if type(resultat) == str: 
                                if resultat == "ERREUR_TAILLE":
                                    st.error(f"❌ Impossible : Une pièce est trop grande pour la barre (marge de sécurité de {CHUTE_MINIMUM} mm).")
                                elif resultat == "LONGUEUR_MANQUANTE":
                                    st.error("❌ Impossible : La longueur standard de cette barre n'est pas renseignée.")
                                else:
                                    st.error(f"❌ Erreur sur ce profil : {resultat}")
                            else:
                                surface_profil = (resultat.get('longueur_peinture', 0) * resultat.get('longueur_barre_standard', 0) * len(resultat['barres'])) / 1000000.0
                                poids_ml = resultat.get("poids_ml", 0.0)
                                poids_profil = (resultat.get('longueur_barre_standard', 0) * len(resultat['barres']) / 1000.0) * poids_ml
                                
                                text_peinture = f"*(Surface : {surface_profil:.2f} m²)*" if surface_profil > 0 else ""
                                text_poids = f"*(Poids : {poids_profil:.2f} kg)*" if poids_profil > 0 else ""
                                
                                st.success(f"📦 À commander : **{len(resultat['barres'])} barre(s)** de {resultat['barres'][0]['barre_longueur']} mm.  {text_poids} {text_peinture}")
                                
                                max_affichage_web = 15
                                nb_total_barres = len(resultat["barres"])
                                
                                for idx, barre in enumerate(resultat["barres"]):
                                    if idx >= max_affichage_web:
                                        break
                                        
                                    with st.expander(f"Barre {idx+1} - Chute : {barre['chute']:.1f} mm", expanded=(idx == 0)):
                                        fig = draw.dessiner_barre(barre, EPAISSEUR_LAME, resultat.get("section_a", 50.0), resultat.get("section_b", 50.0), SEUIL_CHUTE)
                                        # BOUCLIER 3 : Retrait de 'use_container_width' ici aussi
                                        st.pyplot(fig)
                                        plt.close(fig) 
                                
                                if nb_total_barres > max_affichage_web:
                                    st.warning(f"⚠️ **Affichage limité ({nb_total_barres} barres au total).**\nPour préserver la vitesse de l'application et la mémoire de votre navigateur, seules les {max_affichage_web} premières barres sont affichées à l'écran. 👉 **Téléchargez le Rapport PDF** ci-dessus pour consulter l'intégralité du plan de coupe pour l'atelier.")
                                    
                                chutes_utiles = [b['chute'] for b in resultat["barres"] if b['chute'] >= SEUIL_CHUTE]
                                if chutes_utiles:
                                    chutes_utiles.sort(reverse=True)
                                    texte_chutes = ", ".join([f"{c:.1f} mm" for c in chutes_utiles])
                                    st.info(f"♻️ Vous générerez **{len(chutes_utiles)} chute(s)** à conserver (>300mm) : {texte_chutes}.")
                            st.divider()

with tab5:
    st.subheader("🔍 Recherche de la longueur de barre optimale")
    st.write("Cet outil simule la découpe sur une plage de longueurs pour trouver celle qui offre le meilleur rendement matière.")
    
    profils_projet = projet_courant.get("profils_edited", projet_courant["profils"])
    profils_standards = st.session_state.get("df_standards_edited", st.session_state.df_standards_base)
    tous_les_profils = pd.concat([profils_projet, profils_standards])['Nom'].dropna().unique().tolist()
    
    if not tous_les_profils:
        st.warning("Aucun profil disponible dans le projet ou la base standard.")
    else:
        col_cfg1, col_cfg2 = st.columns(2)
        with col_cfg1:
            profil_a_simuler = st.selectbox("Sélectionnez le profil à analyser :", options=tous_les_profils)
            listes_pour_simulation = st.multiselect("Listes de pièces à inclure :", options=noms_listes, default=noms_listes, key="sim_listes")
        
        with col_cfg2:
            plage_longueur = st.slider("Plage de longueurs à tester (mm) :", min_value=2000, max_value=12000, value=(5000, 8000), step=100)
            pas_simulation = st.selectbox("Pas d'incrémentation (mm) :", options=[50, 100, 250, 500, 1000], index=1)
            
        if st.button("🔬 Lancer la simulation", type="primary", use_container_width=True):
            if not listes_pour_simulation:
                st.warning("Veuillez sélectionner au moins une liste.")
            else:
                frames_pieces_sim = []
                for nom_liste in listes_pour_simulation:
                    df_l = projet_courant.get("listes_edited", {}).get(nom_liste, projet_courant["listes"][nom_liste])
                    if not df_l.empty:
                        df_temp = df_l.copy()
                        df_temp['Nom de la Liste'] = nom_liste
                        frames_pieces_sim.append(df_temp)
                
                df_pieces_sim = pd.concat(frames_pieces_sim, ignore_index=True) if frames_pieces_sim else pd.DataFrame()
                
                if not df_pieces_sim.empty:
                    df_pieces_sim = df_pieces_sim[df_pieces_sim['Profil'] == profil_a_simuler]
                    
                if df_pieces_sim.empty:
                    st.warning("Aucune pièce pour ce profil dans les listes sélectionnées.")
                else:
                    with st.spinner("Analyse mathématique de toutes les combinaisons en cours..."):
                        longueurs_a_tester = list(range(plage_longueur[0], plage_longueur[1] + pas_simulation, pas_simulation))
                        max_piece_len = df_pieces_sim['Longueur (mm)'].max()
                        
                        resultats_sim = []
                        progress_bar = st.progress(0)
                        
                        for idx, L_test in enumerate(longueurs_a_tester):
                            if L_test < max_piece_len + CHUTE_MINIMUM:
                                rendement = 0.0
                                nb_barres = 0
                                chute_tot = 0.0
                                statut = "Échec (Pièce trop grande)"
                            else:
                                # On crée un faux dataframe de profil avec juste la longueur testée
                                df_prof_sim = pd.DataFrame([{
                                    "Nom": profil_a_simuler,
                                    "Longueur Barre (mm)": L_test,
                                    "Section A (mm)": 50.0,
                                    "Section B (mm)": 50.0,
                                    "Couleur": "",
                                    "Longueur Peinture (mm)": 0.0
                                }])
                                
                                # On fait appel à l'optimiseur exact pour CHAQUE longueur
                                res_opt = opt.optimiser_projet_complet(df_pieces_sim, df_prof_sim, EPAISSEUR_LAME, CHUTE_MINIMUM)
                                res_profil = res_opt.get(profil_a_simuler, {})
                                
                                if isinstance(res_profil, dict) and res_profil.get("statut") == "SUCCES":
                                    tot_pieces = 0
                                    tot_barres = 0
                                    nb_barres = len(res_profil["barres"])
                                    
                                    for b in res_profil["barres"]:
                                        tot_barres += b['barre_longueur']
                                        for p in b['pieces']:
                                            tot_pieces += p['longueur']
                                    
                                    rendement = (tot_pieces / tot_barres * 100) if tot_barres > 0 else 0
                                    chute_tot = sum([b['chute'] for b in res_profil["barres"]])
                                    statut = "Succès"
                                else:
                                    rendement = 0.0
                                    nb_barres = 0
                                    chute_tot = 0.0
                                    statut = "Échec"
                                    
                            resultats_sim.append({
                                "Longueur Barre (mm)": L_test,
                                "Rendement (%)": round(rendement, 2),
                                "Nb Barres": nb_barres,
                                "Chute Totale (mm)": round(chute_tot, 1),
                                "Statut": statut
                            })
                            progress_bar.progress((idx + 1) / len(longueurs_a_tester))
                        
                        df_res_sim = pd.DataFrame(resultats_sim)
                        df_success = df_res_sim[df_res_sim["Statut"] == "Succès"]
                        
                        if not df_success.empty:
                            meilleur = df_success.loc[df_success["Rendement (%)"].idxmax()]
                            st.success(f"🏆 **Résultat Optimal** : La longueur idéale à commander est de **{int(meilleur['Longueur Barre (mm)'])} mm** avec un rendement de **{meilleur['Rendement (%)']:.1f} %** ({int(meilleur['Nb Barres'])} barres requises).")
                            
                            # Graphique d'évolution du rendement
                            # CTO FIX: Réduction de la hauteur pour un affichage plus panoramique
                            fig, ax = plt.subplots(figsize=(10, 3.5))
                            ax.plot(df_success["Longueur Barre (mm)"], df_success["Rendement (%)"], marker='o', color='#2563eb', linewidth=2, markersize=6)
                            
                            # CTO FIX: Ajout d'un "pad" pour éloigner le titre de la courbe
                            ax.set_title(f"Évolution du Rendement selon la Longueur - Profil {profil_a_simuler}", fontsize=12, fontweight='bold', color='#1f2937', pad=20)
                            ax.set_xlabel("Longueur de Barre (mm)", fontsize=10)
                            ax.set_ylabel("Rendement (%)", fontsize=10)
                            ax.grid(True, linestyle='--', alpha=0.6)
                            
                            # CTO FIX: Ajout d'une marge mathématique sur l'axe Y pour ne pas couper le texte "Optimal"
                            y_max = df_success["Rendement (%)"].max()
                            y_min = df_success["Rendement (%)"].min()
                            marge_haute = max((y_max - y_min) * 0.25, 1.5) # Marge généreuse pour le texte sur deux lignes
                            marge_basse = max((y_max - y_min) * 0.05, 0.5)
                            ax.set_ylim(y_min - marge_basse, y_max + marge_haute)
                            
                            # Mise en évidence du point optimal (L'étoile rouge)
                            longueur_opt = meilleur['Longueur Barre (mm)']
                            rendement_opt = meilleur['Rendement (%)']
                            ax.plot(longueur_opt, rendement_opt, marker='*', color='red', markersize=14)
                            
                            # CTO FIX: Ligne de mire verticale
                            ax.axvline(x=longueur_opt, color='red', linestyle=':', alpha=0.5)
                            
                            # CTO FIX: Valeur exacte + bulle blanche de lisibilité
                            texte_opt = f"Optimal : {int(longueur_opt)} mm\n({rendement_opt:.1f} %)"
                            ax.annotate(texte_opt, 
                                        (longueur_opt, rendement_opt),
                                        textcoords="offset points", xytext=(0,12), ha='center', fontsize=10, fontweight='bold', color='red',
                                        bbox=dict(boxstyle="round,pad=0.3", fc="white", ec="red", alpha=0.9))
                            
                            # CTO FIX: Sécuriser les marges extérieures du graphique
                            fig.tight_layout()
                            
                            st.pyplot(fig)
                            plt.close(fig)
                            
                            # Tableau complet pour analyse brute
                            st.markdown("#### 📋 Détail des Simulations")
                            st.dataframe(df_res_sim, use_container_width=True, hide_index=True)
                        else:
                            st.error("❌ Aucune longueur testée n'a permis de générer un plan de coupe (Vérifiez que la longueur maximale testée est bien supérieure à la plus grande pièce de la liste).")
