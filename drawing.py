import matplotlib.pyplot as plt
import matplotlib.patches as patches
from matplotlib.backends.backend_pdf import PdfPages
import pandas as pd
import math
import io
from datetime import datetime

def dessiner_barre(barre_info, epaisseur_lame, section_a, section_b, seuil_chute):
    largeur_visuelle = section_a if section_a > 0 else 50.0
    
    fig, ax = plt.subplots(figsize=(20, 0.4)) 
    longueur_totale = barre_info['barre_longueur']
    
    faces = set()
    for p in barre_info['pieces']:
        section = p.get('coupe_section', 'A')
        face = section_b if section == 'B' else section_a
        if pd.notna(face) and face > 0:
            faces.add(f"{face:g}")
            
    face_str = " & ".join(sorted(faces))
    if face_str:
        ax.set_title(f"Face(s) de coupe : {face_str} mm", loc='left', fontsize=9, fontweight='bold', color='#333333', pad=5)

    ax.add_patch(patches.Rectangle((0, 0), longueur_totale, largeur_visuelle, facecolor='#f0f0f0', edgecolor='black'))
    position_actuelle = 0
    
    for p in barre_info['pieces']:
        L = p['longueur']
        ang_g = p.get('angle_g', 90.0)
        ang_d = p.get('angle_d', 90.0)
        
        if pd.isna(ang_g) or ang_g <= 0: ang_g = 90.0
        if pd.isna(ang_d) or ang_d <= 0: ang_d = 90.0
        
        tan_g = math.tan(math.radians(ang_g))
        dx_g = largeur_visuelle / tan_g if abs(tan_g) > 0.001 else 0
        
        tan_d = math.tan(math.radians(ang_d))
        dx_d = largeur_visuelle / tan_d if abs(tan_d) > 0.001 else 0
        
        x_min, x_max = position_actuelle, position_actuelle + L
        x_bl, x_tl = x_min + min((dx_g if dx_g > 0 else 0), L), x_min + min((-dx_g if dx_g < 0 else 0), L)
        x_br, x_tr = x_max - min((dx_d if dx_d > 0 else 0), L), x_max - min((-dx_d if dx_d < 0 else 0), L)
        
        ax.add_patch(patches.Polygon([(x_bl, 0), (x_tl, largeur_visuelle), (x_tr, largeur_visuelle), (x_br, 0)], closed=True, facecolor='#4CAF50', edgecolor='black', linewidth=1))
        
        if L >= 300:
            texte = f"{p['ref']}   |   {L:g} mm"
            ax.text(position_actuelle + L/2, largeur_visuelle/2, texte, ha='center', va='center', color='white', fontweight='bold', fontsize=8)
        elif L >= 120:
            texte = f"{p['ref']}\n{L:g} mm"
            ax.text(position_actuelle + L/2, largeur_visuelle/2, texte, ha='center', va='center', color='white', fontweight='bold', fontsize=7)
        elif L >= 60:
            texte = f"{p['ref']} | {L:g} mm"
            ax.text(position_actuelle + L/2, largeur_visuelle/2, texte, ha='center', va='center', color='white', fontweight='bold', fontsize=6, rotation=90)
        elif L >= 20:
            texte = f"{L:g}"
            ax.text(position_actuelle + L/2, largeur_visuelle/2, texte, ha='center', va='center', color='white', fontsize=5, rotation=90)
            
        position_actuelle += L
        
        if position_actuelle + epaisseur_lame <= longueur_totale and position_actuelle < longueur_totale:
            ax.add_patch(patches.Rectangle((position_actuelle, 0), epaisseur_lame, largeur_visuelle, facecolor='#F44336', edgecolor='none'))
            position_actuelle += epaisseur_lame
            
    if position_actuelle < longueur_totale:
        chute = longueur_totale - position_actuelle
        est_reutilisable = chute >= seuil_chute
        ax.add_patch(patches.Rectangle((position_actuelle, 0), chute, largeur_visuelle, facecolor='#C8E6C9' if est_reutilisable else '#9E9E9E', edgecolor='black', hatch='' if est_reutilisable else '//'))
        
        label = f"[ CHUTE ]\n{chute:.1f} mm" if est_reutilisable else f"[ DÉCHET ]\n{chute:.1f} mm"
        ax.text(position_actuelle + chute/2, largeur_visuelle/2, label, ha='center', va='center', color='black', fontweight='bold' if est_reutilisable else 'normal', fontsize=7)
        
    ax.set_xlim(0, longueur_totale)
    ax.set_ylim(0, largeur_visuelle * 1.05)
    ax.axis('off')
    
    fig.subplots_adjust(left=0.01, right=0.99, top=0.85, bottom=0.05, wspace=0, hspace=0)
    return fig

def dessiner_barre_pdf(ax, barre_info, epaisseur_lame, section_a, section_b, seuil_chute, longueur_standard):
    largeur_visuelle = section_a if section_a > 0 else 50.0
    longueur_totale = barre_info['barre_longueur']
    
    ax.add_patch(patches.Rectangle((0, 0), longueur_totale, largeur_visuelle, facecolor='#ecf0f1', edgecolor='#bdc3c7', linewidth=0.5))
    position_actuelle = 0
    
    for p in barre_info['pieces']:
        L = p['longueur']
        ang_g = p.get('angle_g', 90.0)
        ang_d = p.get('angle_d', 90.0)
        
        if pd.isna(ang_g) or ang_g <= 0: ang_g = 90.0
        if pd.isna(ang_d) or ang_d <= 0: ang_d = 90.0
        
        tan_g = math.tan(math.radians(ang_g))
        dx_g = largeur_visuelle / tan_g if abs(tan_g) > 0.001 else 0
        
        tan_d = math.tan(math.radians(ang_d))
        dx_d = largeur_visuelle / tan_d if abs(tan_d) > 0.001 else 0
        
        x_min, x_max = position_actuelle, position_actuelle + L
        x_bl, x_tl = x_min + min((dx_g if dx_g > 0 else 0), L), x_min + min((-dx_g if dx_g < 0 else 0), L)
        x_br, x_tr = x_max - min((dx_d if dx_d > 0 else 0), L), x_max - min((-dx_d if dx_d < 0 else 0), L)
        
        ax.add_patch(patches.Polygon([(x_bl, 0), (x_tl, largeur_visuelle), (x_tr, largeur_visuelle), (x_br, 0)], 
                                     closed=True, facecolor='#27ae60', edgecolor='black', linewidth=0.5))
        
        if L >= 350:
            texte = f"{p['ref']}   |   {L:g} mm"
            ax.text(position_actuelle + L/2, largeur_visuelle/2, texte, ha='center', va='center', color='white', fontweight='bold', fontsize=6)
        elif L >= 150:
            texte = f"{p['ref']}\n{L:g} mm"
            ax.text(position_actuelle + L/2, largeur_visuelle/2, texte, ha='center', va='center', color='white', fontweight='bold', fontsize=5)
        elif L >= 60:
            texte = f"{p['ref']} | {L:g} mm"
            ax.text(position_actuelle + L/2, largeur_visuelle/2, texte, ha='center', va='center', color='white', fontweight='bold', fontsize=4.5, rotation=90)
        elif L >= 20:
            texte = f"{L:g}"
            ax.text(position_actuelle + L/2, largeur_visuelle/2, texte, ha='center', va='center', color='white', fontsize=4, rotation=90)
            
        position_actuelle += L
        
        if position_actuelle + epaisseur_lame <= longueur_totale and position_actuelle < longueur_totale:
            ax.add_patch(patches.Rectangle((position_actuelle, 0), epaisseur_lame, largeur_visuelle, facecolor='#e74c3c', edgecolor='none'))
            position_actuelle += epaisseur_lame
            
    if position_actuelle < longueur_totale:
        chute = longueur_totale - position_actuelle
        est_reutilisable = chute >= seuil_chute
        couleur = '#2ecc71' if est_reutilisable else '#bdc3c7'
        alpha = 0.4 if est_reutilisable else 0.3
        
        ax.add_patch(patches.Rectangle((position_actuelle, 0), chute, largeur_visuelle, facecolor=couleur, alpha=alpha, edgecolor='black', linewidth=0.5))
        
        if chute > 150:
            label = f"[ CHUTE ]\n{chute:.1f} mm" if est_reutilisable else f"[ DÉCHET ]\n{chute:.1f} mm"
            ax.text(position_actuelle + chute/2, largeur_visuelle/2, label, ha='center', va='center', color='#2c3e50', fontsize=5, fontweight='bold' if est_reutilisable else 'normal')
            
    ax.set_xlim(-10, longueur_standard + 10)
    ax.set_ylim(0, largeur_visuelle * 1.3)
    ax.axis('off')

def generer_rapport_pdf(resultats, nom_projet, metrics):
    buffer = io.BytesIO()
    date_generation = datetime.now().strftime("%d/%m/%Y à %H:%M")
    page_actuelle = 1
    
    with PdfPages(buffer) as pdf:
        
        # 1. PRÉPARATION DES DONNÉES DU BORDEREAU
        commandes = []
        for nom_profil, res in resultats.items():
            if type(res) == dict and res["statut"] == "SUCCES":
                commandes.append({
                    "profil": nom_profil,
                    "qte": len(res['barres']),
                    "longueur": res['barres'][0]['barre_longueur'],
                    "couleur": res.get('couleur', '')
                })
        
        commandes = sorted(commandes, key=lambda x: x['profil'])
        
        items_par_page = 35
        nb_pages_resume = max(1, math.ceil(len(commandes) / items_par_page))
        
        # 2. GÉNÉRATION DES PAGES DE BORDEREAU ET RÉSUMÉ
        for page_idx in range(nb_pages_resume):
            fig_resume, ax = plt.subplots(figsize=(8.27, 11.69))
            ax.axis('off')
            
            # --- BANDEAU D'EN-TÊTE ---
            ax.add_patch(patches.Rectangle((0, 0.90), 1, 0.10, facecolor='#1f2937', transform=ax.transAxes, clip_on=False))
            ax.text(0.05, 0.95, "BORDEREAU D'APPROVISIONNEMENT & COUPE", fontsize=16, fontweight='bold', color='white', transform=ax.transAxes)
            ax.text(0.05, 0.92, f"Projet : {nom_projet}", fontsize=12, color='#9ca3af', transform=ax.transAxes)
            
            y_pos = 0.83
            
            # --- BLOC STATISTIQUES (Seulement sur la première page) ---
            if page_idx == 0:
                ax.text(0.05, y_pos, "📊 RÉSUMÉ GLOBAL DE MATIÈRE", fontsize=12, fontweight='bold', color='#2563eb', transform=ax.transAxes)
                y_pos -= 0.04
                
                # Positions X strictes pour éviter tout écrasement (0.05, 0.38, 0.70)
                ax.text(0.05, y_pos, "Matière Consommée :", fontsize=10, color='#4b5563', transform=ax.transAxes)
                ax.text(0.24, y_pos, f"{metrics.get('conso', 0):.2f} m", fontsize=10, fontweight='bold', transform=ax.transAxes)
                
                ax.text(0.38, y_pos, "Matière Utile :", fontsize=10, color='#4b5563', transform=ax.transAxes)
                ax.text(0.51, y_pos, f"{metrics.get('utile', 0):.2f} m", fontsize=10, fontweight='bold', transform=ax.transAxes)
                
                ax.text(0.70, y_pos, "Rendement :", fontsize=10, color='#4b5563', transform=ax.transAxes)
                ax.text(0.83, y_pos, f"{metrics.get('rendement', 0):.1f} %", fontsize=10, fontweight='bold', color='#16a34a', transform=ax.transAxes)
                
                y_pos -= 0.06
                
                # Titre Section Peinture
                ax.text(0.05, y_pos, "🎨 SURFACES À PEINDRE PAR FINITION", fontsize=12, fontweight='bold', color='#2563eb', transform=ax.transAxes)
                y_pos -= 0.04
                
                peintures = metrics.get('peinture_par_couleur', {})
                if not peintures:
                    ax.text(0.05, y_pos, "Aucune surface à peindre détectée sur ces profils.", fontsize=10, style='italic', color='#6b7280', transform=ax.transAxes)
                    y_pos -= 0.03
                else:
                    for coul, surf in peintures.items():
                        # Strict respect de la demande : Affichage de la valeur brute (ex: 1)
                        label_coul = f"{coul}" if coul else "Brut / Sans finition"
                        ax.text(0.05, y_pos, f"• {label_coul}", fontsize=10, fontweight='bold', color='#111827', transform=ax.transAxes)
                        ax.text(0.20, y_pos, f":   {surf:.2f} m²", fontsize=10, transform=ax.transAxes)
                        y_pos -= 0.025
                    y_pos -= 0.02

            # --- TABLEAU BORDEREAU DE COMMANDE ---
            ax.text(0.05, y_pos, "📦 RÉCAPITULATIF DES COMMANDES", fontsize=12, fontweight='bold', color='#2563eb', transform=ax.transAxes)
            y_pos -= 0.02
            
            # En-tête du tableau (Fond gris clair moderne)
            ax.add_patch(patches.Rectangle((0.05, y_pos-0.01), 0.9, 0.025, facecolor='#f3f4f6', edgecolor='#d1d5db', linewidth=0.5, transform=ax.transAxes, clip_on=False))
            ax.text(0.06, y_pos, "PROFIL", fontsize=9, fontweight='bold', color='#374151', transform=ax.transAxes)
            ax.text(0.40, y_pos, "FINITION", fontsize=9, fontweight='bold', color='#374151', transform=ax.transAxes)
            ax.text(0.65, y_pos, "LONGUEUR", fontsize=9, fontweight='bold', color='#374151', transform=ax.transAxes)
            ax.text(0.90, y_pos, "QTÉ", fontsize=9, fontweight='bold', color='#374151', ha='center', transform=ax.transAxes)
            y_pos -= 0.03
            
            # Lignes du tableau
            start_idx = page_idx * items_par_page
            end_idx = min(start_idx + items_par_page, len(commandes))
            
            for i, cmd in enumerate(commandes[start_idx:end_idx]):
                if i % 2 == 0:
                    ax.add_patch(patches.Rectangle((0.05, y_pos-0.012), 0.9, 0.024, facecolor='#f9fafb', edgecolor='none', transform=ax.transAxes, clip_on=False))
                
                ax.text(0.06, y_pos, str(cmd['profil']), fontsize=9, color='#111827', transform=ax.transAxes)
                
                finition = str(cmd['couleur']) if cmd['couleur'] else "Brut"
                ax.text(0.40, y_pos, finition, fontsize=9, color='#6b7280' if finition=="Brut" else '#111827', transform=ax.transAxes)
                
                ax.text(0.65, y_pos, f"{cmd['longueur']:g} mm", fontsize=9, color='#111827', transform=ax.transAxes)
                ax.text(0.90, y_pos, f"{cmd['qte']}", fontsize=10, fontweight='bold', color='#111827', ha='center', transform=ax.transAxes)
                
                # Ligne séparatrice fine
                ax.plot([0.05, 0.95], [y_pos-0.012, y_pos-0.012], color='#e5e7eb', lw=0.5, transform=ax.transAxes)
                y_pos -= 0.024

            # Traçabilité et pagination
            ax.text(0.05, 0.02, f"Généré le {date_generation}", fontsize=8, color='#9ca3af', transform=ax.transAxes)
            ax.text(0.95, 0.02, f"Page {page_actuelle}", fontsize=8, color='#9ca3af', ha='right', transform=ax.transAxes)
            page_actuelle += 1
            
            pdf.savefig(fig_resume)
            plt.close(fig_resume)
        
        # 3. GÉNÉRATION DES PLANS DE COUPE
        barres_a_dessiner = []
        for nom_profil, resultat in resultats.items():
            if type(resultat) == dict and resultat["statut"] == "SUCCES":
                for idx, barre in enumerate(resultat["barres"]):
                    barres_a_dessiner.append({
                        'profil': nom_profil,
                        'idx': idx + 1,
                        'total': len(resultat["barres"]),
                        'barre': barre,
                        'section_a': resultat.get('section_a', 50.0),
                        'section_b': resultat.get('section_b', 50.0),
                        'longueur_standard': resultat['longueur_barre_standard']
                    })
                    
        barres_par_page = 10
        for i in range(0, len(barres_a_dessiner), barres_par_page):
            lot = barres_a_dessiner[i:i+barres_par_page]
            fig, axes = plt.subplots(nrows=barres_par_page, ncols=1, figsize=(8.27, 11.69))
            
            if barres_par_page == 1: axes = [axes]
            
            fig.subplots_adjust(left=0.05, right=0.95, top=0.91, bottom=0.06, hspace=0.8)
            
            rect = patches.Rectangle((0, 0.96), 1, 0.04, facecolor='#1f2937', transform=fig.transFigure, clip_on=False)
            fig.patches.append(rect)
            fig.text(0.05, 0.972, f"PLANS DE COUPE - {nom_projet}", fontsize=11, fontweight='bold', color='white')
            
            # Traçabilité bas de page
            fig.text(0.05, 0.02, f"Généré le {date_generation}", fontsize=8, color='#9ca3af')
            fig.text(0.95, 0.02, f"Page {page_actuelle}", fontsize=8, color='#9ca3af', ha='right')
            
            for j in range(barres_par_page):
                ax = axes[j]
                if j < len(lot):
                    info = lot[j]
                    
                    faces = set()
                    for p in info['barre']['pieces']:
                        section = p.get('coupe_section', 'A')
                        face = info['section_b'] if section == 'B' else info['section_a']
                        if pd.notna(face) and face > 0:
                            faces.add(f"{face:g}")
                            
                    face_str = " & ".join(sorted(faces))
                    face_info = f"   |   Face(s) de coupe: {face_str} mm" if face_str else ""
                    
                    titre = f"Profil: {info['profil']}{face_info}   |   Barre {info['idx']} sur {info['total']}   |   Chute: {info['barre']['chute']:.1f} mm"
                    
                    ax.set_title(titre, fontsize=8, loc='left', color='#374151', pad=5, fontweight='bold')
                    dessiner_barre_pdf(ax, info['barre'], metrics['epaisseur_lame'], info['section_a'], info['section_b'], metrics['seuil_chute'], info['longueur_standard'])
                else:
                    ax.axis('off') 
                    
            pdf.savefig(fig)
            plt.close(fig)
            page_actuelle += 1
            
    buffer.seek(0)
    return buffer
