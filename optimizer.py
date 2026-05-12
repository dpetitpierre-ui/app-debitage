import pandas as pd
from ortools.sat.python import cp_model
import math

def optimiser_projet_complet(df_pieces, df_profils, epaisseur_lame):
    """
    Algorithme v2 (Scalable).
    Utilise des variables entières (IntVar) plutôt que d'éclater les quantités.
    Ceci empêche l'explosion combinatoire de la mémoire sur de grosses listes.
    """
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
            
        # NOUVELLE LOGIQUE: On garde les pièces groupées par "lot"
        items_grouped = []
        qte_totale_pieces = 0
        longueur_totale_pieces = 0
        
        for idx, row in pieces_du_profil.iterrows():
            qte = int(row['Quantité'])
            L = row['Longueur (mm)']
            if qte <= 0 or L <= 0: continue
            
            items_grouped.append({
                'liste': row.get('Nom de la Liste', 'Sans Liste'),
                'ref': row.get('Référence', f'P{idx}'),
                'longueur': L,
                'angle_g': row.get('Angle Gauche (°)', 90.0),
                'angle_d': row.get('Angle Droite (°)', 90.0),
                'coupe_section': row.get('Coupe sur Section', 'A'),
                'qte': qte
            })
            qte_totale_pieces += qte
            longueur_totale_pieces += (L + epaisseur_lame) * qte

        if not items_grouped:
            continue
            
        if longueur_barre_standard <= 0:
            resultats_finaux[nom_profil] = "LONGUEUR_MANQUANTE"
            continue
            
        if any(item['longueur'] > longueur_barre_standard for item in items_grouped):
            resultats_finaux[nom_profil] = "ERREUR_TAILLE"
            continue

        # Tri intelligent (les plus grandes pièces d'abord)
        items_grouped.sort(key=lambda item: item['longueur'], reverse=True)

        # Calculer une borne max raisonnable de barres pour ne pas surcharger l'IA
        borne_sup_barres = int(math.ceil(longueur_totale_pieces / longueur_barre_standard) * 1.2) + 2
        borne_sup_barres = min(borne_sup_barres, qte_totale_pieces) # Au pire, 1 barre par pièce
        
        barres_liste = [{'id': nom_profil, 'longueur': longueur_barre_standard} for _ in range(borne_sup_barres)]

        model = cp_model.CpModel()
        
        # x[i, j] = Nombre de pièces du type 'i' mises dans la barre 'j' (Variable Entière !)
        x = {} 
        for i in range(len(items_grouped)):
            for j in range(len(barres_liste)):
                x[i, j] = model.NewIntVar(0, items_grouped[i]['qte'], f'x_{i}_{j}')
                
        # y[j] = 1 si la barre 'j' est utilisée, 0 sinon
        y = {} 
        for j in range(len(barres_liste)):
            y[j] = model.NewBoolVar(f'y_{j}')

        # Contrainte : Toutes les pièces de chaque type doivent être placées
        for i in range(len(items_grouped)):
            model.Add(sum(x[i, j] for j in range(len(barres_liste))) == items_grouped[i]['qte'])

        # Symétrie : Remplir la barre j avant la barre j+1
        for j in range(1, len(barres_liste)):
            model.Add(y[j] <= y[j-1])

        # Contrainte de capacité de la barre
        lame = int(epaisseur_lame * 10)
        for j in range(len(barres_liste)):
            capacite = int(barres_liste[j]['longueur'] * 10)
            somme_longueurs = sum((int(items_grouped[i]['longueur'] * 10) + lame) * x[i, j] for i in range(len(items_grouped)))
            model.Add(somme_longueurs <= (capacite + lame) * y[j])

        # Fonction objectif : Tassement à gauche
        poids_lourd_barre = max(10000, qte_totale_pieces * len(barres_liste) + 100)
        termes_objectif = []
        for j in range(len(barres_liste)):
            termes_objectif.append(y[j] * poids_lourd_barre)
            for i in range(len(items_grouped)):
                termes_objectif.append(x[i, j] * j)
                
        model.Minimize(sum(termes_objectif))
        
        # Résolution
        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = 15.0
        status = solver.Solve(model)

        if status == cp_model.OPTIMAL or status == cp_model.FEASIBLE:
            resultats_barres = []
            for j in range(len(barres_liste)):
                if solver.Value(y[j]):
                    pieces_barre = []
                    longueur_utilisee = 0
                    for i in range(len(items_grouped)):
                        qte_dans_barre_j = solver.Value(x[i, j])
                        for _ in range(qte_dans_barre_j):
                            piece_copie = items_grouped[i].copy()
                            pieces_barre.append(piece_copie)
                            longueur_utilisee += piece_copie['longueur'] + epaisseur_lame
                            
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
