import pandas as pd
from ortools.sat.python import cp_model

def optimiser_projet_complet(df_pieces, df_profils, epaisseur_lame):
    """
    Le 'Cerveau' de l'application. 
    Prend en entrée les tableaux de pièces et de profils, et retourne la configuration de coupe optimale.
    Ne contient aucune notion d'interface graphique (Streamlit) ni de base de données.
    """
    resultats_finaux = {}
    
    # Nettoyage sécurisé des profils
    df_profils = df_profils.dropna(subset=['Nom', 'Longueur Barre (mm)']).copy()
    df_profils['Nom'] = df_profils['Nom'].astype(str).str.strip()
    df_profils = df_profils[df_profils['Nom'] != ""]
    
    # Nettoyage sécurisé des pièces
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
            
        # Tri intelligent (les plus grandes pièces d'abord pour aider l'IA)
        pieces_liste.sort(key=lambda item: item['longueur'], reverse=True)

        qte_barres_a_fournir_ia = len(pieces_liste)
        barres_liste = [{'id': nom_profil, 'longueur': longueur_barre_standard} for _ in range(qte_barres_a_fournir_ia)]

        if any(p['longueur'] > longueur_barre_standard for p in pieces_liste):
            resultats_finaux[nom_profil] = "ERREUR_TAILLE"
            continue

        # Initialisation du solveur OR-Tools
        model = cp_model.CpModel()
        x = {} 
        for i in range(len(pieces_liste)):
            for j in range(len(barres_liste)):
                x[i, j] = model.NewBoolVar(f'x_{i}_{j}')
        y = {} 
        for j in range(len(barres_liste)):
            y[j] = model.NewBoolVar(f'y_{j}')

        # Contrainte : chaque pièce dans exactement une barre
        for i in range(len(pieces_liste)):
            model.AddExactlyOne(x[i, j] for j in range(len(barres_liste)))

        # Symétrie : Remplir la barre j avant la barre j+1
        for j in range(1, len(barres_liste)):
            model.Add(y[j] <= y[j-1])

        # Contrainte de capacité (longueur pièce + lame)
        lame = int(epaisseur_lame * 10)
        for j in range(len(barres_liste)):
            capacite = int(barres_liste[j]['longueur'] * 10)
            model.Add(sum((int(pieces_liste[i]['longueur'] * 10) + lame) * x[i, j] for i in range(len(pieces_liste))) <= (capacite + lame) * y[j])

        # Loi de gravité / Tassement à gauche
        poids_lourd_barre = max(10000, len(pieces_liste) * len(barres_liste) + 100)
        
        termes_objectif = []
        for j in range(len(barres_liste)):
            termes_objectif.append(y[j] * poids_lourd_barre)
            for i in range(len(pieces_liste)):
                termes_objectif.append(x[i, j] * j)
                
        model.Minimize(sum(termes_objectif))
        
        # Résolution
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