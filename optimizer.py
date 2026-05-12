import pandas as pd
from ortools.sat.python import cp_model
import math

def optimiser_projet_complet(df_pieces, df_profils, epaisseur_lame, chute_minimum=30.0):
    """
    Algorithme v3 (Hybride & Indestructible).
    Combine une heuristique ultra-rapide (FFD) pour les gros volumes,
    et l'IA (CP-SAT) pour affiner les petits volumes.
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
        
        sec_a = profil.get('Section A (mm)', 50.0)
        sec_b = profil.get('Section B (mm)', 50.0)
        
        if pd.isna(sec_a) or sec_a <= 0: sec_a = 50.0
        if pd.isna(sec_b) or sec_b <= 0: sec_b = sec_a
        
        longueur_barre_standard = profil.get('Longueur Barre (mm)', 0)
        longueur_peinture = profil.get('Longueur Peinture (mm)', 0)
        
        if pd.isna(longueur_peinture): longueur_peinture = 0.0
        
        pieces_du_profil = df_pieces[df_pieces['Profil'] == nom_profil]
        if pieces_du_profil.empty: continue 
            
        items_grouped = []
        qte_totale_pieces = 0
        
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

        if not items_grouped:
            continue
            
        if longueur_barre_standard <= 0:
            resultats_finaux[nom_profil] = "LONGUEUR_MANQUANTE"
            continue
            
        # Bouclier anti-impossibilité (Chute minimum incluse)
        if any(item['longueur'] > longueur_barre_standard - chute_minimum for item in items_grouped):
            resultats_finaux[nom_profil] = "ERREUR_TAILLE"
            continue

        # =========================================================================
        # PHASE 1 : MOTEUR HEURISTIQUE (FIRST FIT DECREASING) - SPÉCIAL GROS VOLUMES
        # =========================================================================
        # On "déplie" les pièces pour l'algorithme rapide
        pieces_individuelles = []
        for item in items_grouped:
            for _ in range(item['qte']):
                pieces_individuelles.append(item.copy())
        
        # Tri des pièces de la plus grande à la plus petite (stratégie FFD)
        pieces_individuelles.sort(key=lambda x: x['longueur'], reverse=True)
        
        barres_ffd = []
        espace_initial = longueur_barre_standard - chute_minimum + epaisseur_lame
        
        for piece in pieces_individuelles:
            longueur_requise = piece['longueur'] + epaisseur_lame
            place_trouvee = False
            
            # On cherche la première barre qui a assez de place
            for barre in barres_ffd:
                if barre['espace_dispo'] >= longueur_requise:
                    barre['pieces'].append(piece)
                    barre['espace_dispo'] -= longueur_requise
                    place_trouvee = True
                    break
                    
            # Si aucune barre n'a de place, on en ouvre une nouvelle
            if not place_trouvee:
                nouvelle_barre = {
                    'barre_longueur': longueur_barre_standard,
                    'espace_dispo': espace_initial - longueur_requise,
                    'pieces': [piece]
                }
                barres_ffd.append(nouvelle_barre)

        # Formatage du résultat de l'heuristique
        resultats_barres_ffd = []
        for b in barres_ffd:
            longueur_utilisee = sum(p['longueur'] + epaisseur_lame for p in b['pieces']) - epaisseur_lame
            chute_reelle = b['barre_longueur'] - longueur_utilisee
            resultats_barres_ffd.append({
                'barre_longueur': b['barre_longueur'],
                'pieces': b['pieces'],
                'chute': chute_reelle
            })

        # =========================================================================
        # AIGUILLAGE INTELLIGENT (CTO MODE)
        # =========================================================================
        # Si on a plus de 200 pièces pour ce profil, l'IA va exploser ou timeout.
        # On renvoie directement le résultat FFD (qui est ultra-proche de l'optimum).
        if qte_totale_pieces > 200:
            resultats_finaux[nom_profil] = {
                "statut": "SUCCES", 
                "barres": resultats_barres_ffd, 
                "section_a": sec_a,
                "section_b": sec_b, 
                "longueur_peinture": longueur_peinture,
                "longueur_barre_standard": longueur_barre_standard
            }
            continue

        # =========================================================================
        # PHASE 2 : MOTEUR IA EXACT (CP-SAT) POUR AFFINER LES PETITES SÉRIES
        # =========================================================================
        # Tri des groupes pour aider l'IA
        items_grouped.sort(key=lambda item: item['longueur'], reverse=True)
        
        # Grâce au FFD, on sait exactement combien de barres on a besoin au pire.
        borne_sup_barres = len(barres_ffd)
        barres_liste = [{'id': nom_profil, 'longueur': longueur_barre_standard} for _ in range(borne_sup_barres)]

        model = cp_model.CpModel()
        
        x = {} 
        for i in range(len(items_grouped)):
            for j in range(len(barres_liste)):
                x[i, j] = model.NewIntVar(0, items_grouped[i]['qte'], f'x_{i}_{j}')
                
        y = {} 
        for j in range(len(barres_liste)):
            y[j] = model.NewBoolVar(f'y_{j}')

        for i in range(len(items_grouped)):
            model.Add(sum(x[i, j] for j in range(len(barres_liste))) == items_grouped[i]['qte'])

        for j in range(1, len(barres_liste)):
            model.Add(y[j] <= y[j-1])

        lame = int(epaisseur_lame * 10)
        chute_min_int = int(chute_minimum * 10) 
        
        for j in range(len(barres_liste)):
            capacite = int(barres_liste[j]['longueur'] * 10)
            somme_longueurs = sum((int(items_grouped[i]['longueur'] * 10) + lame) * x[i, j] for i in range(len(items_grouped)))
            model.Add(somme_longueurs <= (capacite - chute_min_int + lame) * y[j])

        poids_lourd_barre = max(10000, qte_totale_pieces * len(barres_liste) + 100)
        termes_objectif = []
        for j in range(len(barres_liste)):
            termes_objectif.append(y[j] * poids_lourd_barre)
            for i in range(len(items_grouped)):
                termes_objectif.append(x[i, j] * j)
                
        model.Minimize(sum(termes_objectif))
        
        solver = cp_model.CpSolver()
        # Timeout réduit car on a un excellent filet de sécurité (FFD)
        solver.parameters.max_time_in_seconds = 8.0 
        status = solver.Solve(model)

        if status == cp_model.OPTIMAL or status == cp_model.FEASIBLE:
            resultats_barres_cp = []
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
                    chute_reelle = barres_liste[j]['longueur'] - longueur_utilisee
                    
                    resultats_barres_cp.append({'barre_longueur': barres_liste[j]['longueur'], 'pieces': pieces_barre, 'chute': chute_reelle})
            
            # Vérification finale : Si l'IA n'a pas fait mieux que le FFD, on garde le FFD !
            if len(resultats_barres_cp) <= len(resultats_barres_ffd):
                meilleures_barres = resultats_barres_cp
            else:
                meilleures_barres = resultats_barres_ffd
                
            resultats_finaux[nom_profil] = {
                "statut": "SUCCES", 
                "barres": meilleures_barres, 
                "section_a": sec_a,
                "section_b": sec_b, 
                "longueur_peinture": longueur_peinture,
                "longueur_barre_standard": longueur_barre_standard
            }
        else:
            # Si l'IA échoue sans solution, le FFD prend le relais en douceur !
            resultats_finaux[nom_profil] = {
                "statut": "SUCCES", 
                "barres": resultats_barres_ffd, 
                "section_a": sec_a,
                "section_b": sec_b, 
                "longueur_peinture": longueur_peinture,
                "longueur_barre_standard": longueur_barre_standard
            }

    return resultats_finaux
