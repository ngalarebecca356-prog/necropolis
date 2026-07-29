from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from io import BytesIO
from datetime import datetime

def generer_facture(reservation):
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4)
    styles = getSampleStyleSheet()
    elements = []

    # ═══════════════════════════════════════════════════
    # 1. EN-TÊTE
    # ═══════════════════════════════════════════════════
    elements.append(Paragraph("NECROPOLIS - GESTION DE CIMETIÈRE", styles['Title']))
    elements.append(Paragraph("FACTURE DE RÉSERVATION", styles['Heading2']))
    elements.append(Spacer(1, 20))

    elements.append(Paragraph(f"Date d'émission : {datetime.now().strftime('%d/%m/%Y à %H:%M')}", styles['Normal']))
    elements.append(Paragraph(f"N° Facture : FAC-{reservation.id}-2026", styles['Normal']))
    elements.append(Spacer(1, 30))

    # ═══════════════════════════════════════════════════
    # 2. INFORMATIONS CLIENT (Le vrai client, pas forcément l'admin)
    # ═══════════════════════════════════════════════════
    elements.append(Paragraph("INFORMATIONS CLIENT", styles['Heading2']))
    
    # Logique intelligente : si c'est un tiers, on prend client_nom, sinon on prend le nom de l'utilisateur connecté
    nom_client = reservation.client_nom or (reservation.client.get_full_name() or reservation.client.username)
    prenom_client = reservation.client_prenom or ""
    email_client = reservation.client_email or reservation.client.email
    tel_client = reservation.client_telephone or "Non renseigné"

    elements.append(Paragraph(f"Nom complet : {nom_client} {prenom_client}".strip(), styles['Normal']))
    elements.append(Paragraph(f"Email : {email_client}", styles['Normal']))
    elements.append(Paragraph(f"Téléphone : {tel_client}", styles['Normal']))
    elements.append(Spacer(1, 20))

    # ═══════════════════════════════════════════════════
    # 3. TRAÇABILITÉ (Qui a enregistré et qui a validé)
    # ═══════════════════════════════════════════════════
    elements.append(Paragraph("TRAÇABILITÉ DE LA RÉSERVATION", styles['Heading2']))
    
    enregistre_par = reservation.cree_par.username if reservation.cree_par else "Système"
    elements.append(Paragraph(f"Enregistré par : {enregistre_par}", styles['Normal']))
    
    if reservation.valide_par:
        elements.append(Paragraph(f"Validé par : {reservation.valide_par.username}", styles['Normal']))
        date_val = reservation.date_validation.strftime('%d/%m/%Y à %H:%M') if reservation.date_validation else 'N/A'
        elements.append(Paragraph(f"Date de validation : {date_val}", styles['Normal']))
    else:
        elements.append(Paragraph("Statut actuel : En attente de validation", styles['Normal']))
        
    elements.append(Spacer(1, 20))

    # ═══════════════════════════════════════════════════
    # 4. DÉTAILS DE LA RÉSERVATION
    # ═══════════════════════════════════════════════════
    elements.append(Paragraph("DÉTAILS DE LA RÉSERVATION", styles['Heading2']))
    
    defunt_info = "N/A"
    if reservation.defunt:
        defunt_info = f"{reservation.defunt.prenom or ''} {reservation.defunt.nom or ''}".strip()
        if not defunt_info:
            defunt_info = "N/A"
        date_deces = reservation.defunt.date_deces.strftime('%d/%m/%Y') if reservation.defunt.date_deces else 'N/A'
    else:
        date_deces = 'N/A'

    data = [
        ['Description', 'Détails'],
        ['Caveau N°', reservation.caveau.numero],
        ['Section', reservation.caveau.section],
        ['Bloc', reservation.caveau.bloc],
        ['Défunt', defunt_info],
        ['Date de décès', date_deces],
        ['Statut', reservation.statut.upper()],
    ]

    table = Table(data, colWidths=[200, 250])
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#c9a84c')), # Couleur or NECROPOLIS
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f5f5f5')]),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]))
    elements.append(table)
    elements.append(Spacer(1, 30))

    # ═══════════════════════════════════════════════════
    # 5. MONTANT ET PIED DE PAGE
    # ═══════════════════════════════════════════════════
    # Tu pourras plus tard remplacer 150 par reservation.montant_total si tu l'as ajouté au modèle
    montant = getattr(reservation, 'montant_total', 150)
    
    elements.append(Paragraph(f"MONTANT TOTAL À PAYER : {montant} USD", styles['Heading2']))
    elements.append(Spacer(1, 20))
    elements.append(Paragraph("Merci de votre confiance. Veuillez procéder au paiement pour confirmer définitivement cette réservation.", styles['Normal']))
    elements.append(Spacer(1, 10))
    elements.append(Paragraph("NECROPOLIS - Service Funéraire", styles['Normal']))

    doc.build(elements)
    buffer.seek(0)
    return buffer