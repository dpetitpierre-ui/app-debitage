import matplotlib.pyplot as plt
import matplotlib.patches as patches
from matplotlib.backends.backend_pdf import PdfPages
import pandas as pd
import math
import io

def dessiner_barre(barre_info, epaisseur_lame, largeur_profil, seuil_chute):
    fig, ax = plt.subplots(figsize=(20, 0.4)) 
    longueur_totale = barre_info['barre_longueur']
    
    ax.add_patch(patches.Rectangle((0, 0), longueur_totale, largeur_profil, facecolor='#f0f0f0', edgecolor='black'))
    position_actuelle = 0
    
    for p in barre_info['pieces']:
        L = p['longueur']
        ang_g, ang_d = p.get('angle_g', 90.0), p.get('angle_d', 90.0)
        section = p.get('coupe_section', 'A') 
        if pd.isna(ang_g): ang_g = 90.0
        if pd.isna(ang_d): ang_d = 90.0
        
        dx_g = largeur_profil / math.tan(math.radians(ang_g)) if ang_g != 90 else 0
        dx_d = largeur_profil / math.tan(math.radians(ang_d)) if ang_d != 90 else 0
        
        x_min, x_max = position_actuelle, position_actuelle + L
        x_bl, x_tl = x_min + min((dx_g if dx_g > 0 else 0), L), x_min + min((-dx_g if dx_g < 0 else 0), L)
        x_br, x_tr = x_max - min((dx_d if dx_d > 0 else 0), L), x_max - min((-dx_d if dx_d < 0 else 0), L)
        
        ax.add_patch(patches.Polygon([(x_bl, 0), (x_tl, largeur_profil), (x_tr, largeur_profil), (x_br, 0)], closed=True, facecolor='#4CAF50', edgecolor='black', linewidth=1))
        
        texte_piece = f"{p['ref']}\n{L}mm"
        if section == 'B': texte_piece += "\n(Sect. B)"
            
        ax.text(position_actuelle + L/2, largeur_profil/2, texte_piece, ha='center', va='center', color='white', fontweight='bold', fontsize=7)
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

def generer_rapport_pdf(resultats, nom_projet, metrics):
    """
    Crée un fichier PDF en mémoire contenant le résumé et tous les plans de coupe.
    """
    buffer = io.BytesIO()
    with PdfPages(buffer) as pdf:
        
        # 1. PAGE DE GARDE / RÉSUMÉ
        fig_resume, ax = plt.subplots(figsize=(8.27, 11.69)) # Format A4
        ax.axis('off')
        
        ax.text(0.5, 0.95, f"Rapport de Débitage : {nom_projet}", fontsize=20, ha='center', fontweight='bold', color='#2c3e50')
        
        y = 0.85
        ax.text(0.05, y, "📊 Résumé de l'Optimisation", fontsize=14, fontweight='bold')
        y -= 0.05
        ax.text(0.05, y, f"- Matière Consommée : {metrics.get('conso', 0):.2f} mètres linéaires", fontsize=12)
        y -= 0.03
        ax.text(0.05, y, f"- Matière Utile (Pièces) : {metrics.get('utile', 0):.2f} mètres linéaires", fontsize=12)
        y -= 0.03
        ax.text(0.05, y, f"- Rendement Matière : {metrics.get('rendement', 0):.1f} %", fontsize=12)
        y -= 0.03
        ax.text(0.05, y, f"- Surface à Peindre : {metrics.get('peinture', 0):.2f} m²", fontsize=12)
        
        y -= 0.08
        ax.text(0.05, y, "📦 Récapitulatif des Barres à Commander", fontsize=14, fontweight='bold')
        y -= 0.05
        for nom_profil, resultat in resultats.items():
            if type(resultat) == dict and resultat["statut"] == "SUCCES":
                texte_cmd = f"Profil '{nom_profil}' : {len(resultat['barres'])} barre(s) de {resultat['barres'][0]['barre_longueur']} mm"
                ax.text(0.05, y, f"• {texte_cmd}", fontsize=11)
                y -= 0.03
                
        pdf.savefig(fig_resume)
        plt.close(fig_resume)
        
        # 2. PAGES DES PLANS DE COUPE
        for nom_profil, resultat in resultats.items():
            if type(resultat) == dict and resultat["statut"] == "SUCCES":
                for idx, barre in enumerate(resultat["barres"]):
                    fig_barre = dessiner_barre(barre, metrics['epaisseur_lame'], resultat['largeur'], metrics['seuil_chute'])
                    # On ajoute un titre au-dessus de chaque barre pour le PDF
                    fig_barre.suptitle(f"Profil: {nom_profil} | Barre {idx+1}/{len(resultat['barres'])} (Chute: {barre['chute']:.1f}mm)", fontsize=10, fontweight='bold', y=1.2)
                    # Sauvegarde dans le PDF avec un encadrement resserré
                    pdf.savefig(fig_barre, bbox_inches='tight')
                    plt.close(fig_barre)
                    
    buffer.seek(0)
    return buffer
