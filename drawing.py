import matplotlib.pyplot as plt
import matplotlib.patches as patches
from matplotlib.backends.backend_pdf import PdfPages
import pandas as pd
import math
import io

def dessiner_barre(barre_info, epaisseur_lame, section_a, section_b, seuil_chute):
    """ Dessin adapté pour l'affichage web (Streamlit) """
    largeur_visuelle = section_a if section_a > 0 else 50.0
    
    fig, ax = plt.subplots(figsize=(20, 0.4)) 
    longueur_totale = barre_info['barre_longueur']
    
    # --- LOGIQUE CTO : Ajout du titre directement dans le graphique web ---
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
        ang_g, ang_d = p.get('angle_g', 90.0), p.get('angle_d', 90.0)
        
        if pd.isna(ang_g): ang_g = 90.0
        if pd.isna(ang_d): ang_d = 90.0
        
        dx_g = largeur_visuelle / math.tan(math.radians(ang_g)) if ang_g != 90 else 0
        dx_d = largeur_visuelle / math.tan(math.radians(ang_d)) if ang_d != 90 else 0
        
        x_min, x_max = position_actuelle, position_actuelle + L
        x_bl, x_tl = x_min + min((dx_g if dx_g > 0 else 0), L), x_min + min((-dx_g if dx_g < 0 else 0), L)
        x_br, x_tr = x_max - min((dx_d if dx_d > 0 else 0), L), x_max - min((-dx_d if dx_d < 0 else 0), L)
        
        ax.add_patch(patches.Polygon([(x_bl, 0), (x_tl, largeur_visuelle), (x_tr, largeur_visuelle), (x_br, 0)], closed=True, facecolor='#4CAF50', edgecolor='black', linewidth=1))
        
        # --- LOGIQUE D'AFFICHAGE WEB (Texte épuré) ---
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
        ax.text(position_actuelle + chute/2, largeur_visuelle/2, f"♻️ Chute\n{chute:.1f} mm" if est_reutilisable else f"Déchet\n{chute:.1f} mm", ha='center', va='center', color='black', fontweight='bold' if est_reutilisable else 'normal', fontsize=7)
        
    ax.set_xlim(0, longueur_totale)
    ax.set_ylim(0, largeur_visuelle * 1.05)
    ax.axis('off')
    
    fig.subplots_adjust(left=0.01, right=0.99, top=0.85, bottom=0.05, wspace=0, hspace=0)
    return fig

def dessiner_barre_pdf(ax, barre_info, epaisseur_lame, section_a, section_b, seuil_chute, longueur_standard):
    """ Dessin Ultra-Qualitatif adapté pour l'impression A4 (Multi-Barres) """
    largeur_visuelle = section_a if section_a > 0 else 50.0
    longueur_totale = barre_info['barre_longueur']
    
    ax.add_patch(patches.Rectangle((0, 0), longueur_totale, largeur_visuelle, facecolor='#ecf0f1', edgecolor='#bdc3c7', linewidth=0.5))
    position_actuelle = 0
    
    for p in barre_info['pieces']:
        L = p['longueur']
        ang_g, ang_d = p.get('angle_g', 90.0), p.get('angle_d', 90.0)
        
        if pd.isna(ang_g): ang_g = 90.0
        if pd.isna(ang_d): ang_d = 90.0
        
        dx_g = largeur_visuelle / math.tan(math.radians(ang_g)) if ang_g != 90 else 0
        dx_d = largeur_visuelle / math.tan(math.radians(ang_d)) if ang_d != 90 else 0
        
        x_min, x_max = position_actuelle, position_actuelle + L
        x_bl, x_tl = x_min + min((dx_g if dx_g > 0 else 0), L), x_min + min((-dx_g if dx_g < 0 else 0), L)
        x_br, x_tr = x_max - min((dx_d if dx_d > 0 else 0), L), x_max - min((-dx_d if dx_d < 0 else 0), L)
        
        ax.add_patch(patches.Polygon([(x_bl, 0), (x_tl, largeur_visuelle), (x_tr, largeur_visuelle), (x_br, 0)], 
                                     closed=True, facecolor='#27ae60', edgecolor='black', linewidth=0.5))
        
        # --- LOGIQUE D'AFFICHAGE PDF (Texte épuré) ---
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
            label = f"♻️ Chute ({chute:.1f} mm)" if est_reutilisable else f"Déchet ({chute:.1f} mm)"
            ax.text(position_actuelle + chute/2, largeur_visuelle/2, label, ha='center', va='center', color='#2c3e50', fontsize=5)
            
    ax.set_xlim(-10, longueur_standard + 10)
    ax.set_ylim(0, largeur_visuelle * 1.3)
    ax.axis('off')

def generer_rapport_pdf(resultats, nom_projet, metrics):
    """ Générateur de rapport PDF au format A4 Professionnel """
    buffer = io.BytesIO()
    with PdfPages(buffer) as pdf:
        
        # ---------------- PAGE 1 : PAGE DE GARDE ----------------
        fig_resume, ax = plt.subplots(figsize=(8.27, 11.69)) # Format A4
        ax.axis('off')
        
        ax.text(0.5, 0.90, "RAPPORT DE DÉBITAGE", fontsize=24, ha='center', fontweight='bold', color='#2c3e50')
        ax.text(0.5, 0.86, f"Projet : {nom_projet}", fontsize=16, ha='center', color='#34495e')
        ax.plot([0.1, 0.9], [0.83, 0.83], color='#bdc3c7', lw=1) 
        
        y = 0.75
        ax.text(0.1, y, "📊 RÉSUMÉ GLOBAL", fontsize=14, fontweight='bold', color='#2980b9')
        y -= 0.05
        ax.text(0.12, y, f"• Matière Consommée : {metrics.get('conso', 0):.2f} mètres", fontsize=12)
        y -= 0.03
        ax.text(0.12, y, f"• Matière Utile : {metrics.get('utile', 0):.2f} mètres", fontsize=12)
        y -= 0.03
        ax.text(0.12, y, f"• Rendement : {metrics.get('rendement', 0):.1f} %", fontsize=12, fontweight='bold', color='#27ae60')
        y -= 0.03
        ax.text(0.12, y, f"• Surface à Peindre : {metrics.get('peinture', 0):.2f} m²", fontsize=12)
        
        y -= 0.08
        ax.plot([0.1, 0.9], [y+0.02, y+0.02], color='#bdc3c7', lw=0.5)
        ax.text(0.1, y-0.02, "📦 COMMANDES REQUISES", fontsize=14, fontweight='bold', color='#2980b9')
        y -= 0.06
        
        for nom_profil, resultat in resultats.items():
            if type(resultat) == dict and resultat["statut"] == "SUCCES":
                qte = len(resultat['barres'])
                longueur = resultat['barres'][0]['barre_longueur']
                ax.text(0.12, y, f"✓ {qte} barre(s) de {longueur} mm  (Profil: {nom_profil})", fontsize=11)
                y -= 0.03
                if y < 0.1:
                    ax.text(0.12, y, "... (suite sur les pages de coupe)", fontsize=10, style='italic')
                    break
                    
        pdf.savefig(fig_resume)
        plt.close(fig_resume)
        
        # ---------------- PAGES SUIVANTES : PLANS DE COUPE ----------------
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
            
            if barres_par_page == 1: axes = [axes] # Sécurité
            
            fig.subplots_adjust(left=0.05, right=0.95, top=0.92, bottom=0.05, hspace=0.8)
            fig.suptitle(f"Plans de coupe - {nom_projet} (Page {i//barres_par_page + 1})", fontsize=12, fontweight='bold', color='#2c3e50', y=0.98)
            
            for j in range(barres_par_page):
                ax = axes[j]
                if j < len(lot):
                    info = lot[j]
                    
                    # --- LOGIQUE CTO : Extraire les faces uniques de cette barre ---
                    faces = set()
                    for p in info['barre']['pieces']:
                        section = p.get('coupe_section', 'A')
                        face = info['section_b'] if section == 'B' else info['section_a']
                        if pd.notna(face) and face > 0:
                            faces.add(f"{face:g}")
                            
                    face_str = " & ".join(sorted(faces))
                    face_info = f"   |   Face(s) de coupe: {face_str} mm" if face_str else ""
                    
                    # Le titre contient désormais toutes les infos cruciales
                    titre = f"Profil: {info['profil']}{face_info}   |   Barre {info['idx']} sur {info['total']}   |   Chute: {info['barre']['chute']:.1f} mm"
                    
                    ax.set_title(titre, fontsize=8, loc='left', color='#34495e', pad=5, fontweight='bold')
                    dessiner_barre_pdf(ax, info['barre'], metrics['epaisseur_lame'], info['section_a'], info['section_b'], metrics['seuil_chute'], info['longueur_standard'])
                else:
                    ax.axis('off') 
                    
            pdf.savefig(fig)
            plt.close(fig)
            
    buffer.seek(0)
    return buffer
