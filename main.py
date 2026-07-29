import flet as ft
import httpx
import webbrowser
import sys
from datetime import datetime



API_URL = "http://127.0.0.1:8000/api"

# Jeton de session transmis en argument par authentification.py après la
# vérification MFA (voir subprocess.Popen([..., main_path, token, username])).
# Sans ce jeton, l'API ne peut pas savoir qui appelle et ne peut donc pas
# filtrer les données par cimetière.
SESSION_TOKEN = sys.argv[1] if len(sys.argv) > 1 else ""
SESSION_USER  = sys.argv[2] if len(sys.argv) > 2 else ""
SESSION_ROLE  = sys.argv[3] if len(sys.argv) > 3 else "client"
HEADERS = {"Authorization": f"Bearer {SESSION_TOKEN}"} if SESSION_TOKEN else {}

# Palette 2026
BG      = "#0a0a0f"
CARD    = "#12121a"
SURFACE = "#1a1a24"
BORDER  = "#2a2a3a"
OR      = "#d4a857"
OR2     = "#f0c674"
BLANC   = "#f5f5f7"
GRIS    = "#8a8a9a"
VERT    = "#4ade80"
ORANGE  = "#fb923c"
ROUGE   = "#ef4444"
BLEU    = "#3b82f6"

def main(page: ft.Page):
    page.title = "NECROPOLIS — Gestion de Cimetiere"
    page.theme_mode = ft.ThemeMode.DARK
    page.bgcolor = BG
    page.padding = 0
    page.window_width = 1360
    page.window_height = 860

    contenu_principal = ft.Column(expand=True, scroll=ft.ScrollMode.AUTO)
    titre_page = ft.Text("Tableau de bord", size=22, weight=ft.FontWeight.W_600, color=BLANC)
    status_msg = ft.Container(visible=False)

    def show_msg(texte, couleur=VERT):
        status_msg.content = ft.Container(
            content=ft.Row([
                ft.Icon(ft.Icons.CHECK_CIRCLE if couleur == VERT else ft.Icons.ERROR_OUTLINE,
                        color=couleur, size=16),
                ft.Text(texte, color=couleur, size=13),
            ], spacing=8),
            bgcolor=SURFACE,
            border_radius=8,
            padding=14,
            border=ft.border.all(1, BORDER),
        )
        status_msg.visible = True
        page.update()

    # ── SIDEBAR ─────────────────────────────────────
    def nav_item(icone, texte, page_nom):
        def on_click(e):
            afficher_page(page_nom)
        return ft.Container(
            content=ft.Row([
                ft.Icon(icone, color=OR, size=18),
                ft.Text(texte, color=BLANC, size=13, weight=ft.FontWeight.W_400),
            ], spacing=14),
            padding=ft.padding.only(left=18, right=18, top=12, bottom=12),
            border_radius=8,
            on_click=on_click,
            ink=True,
        )

    # ── Menu filtré selon le rôle (RBAC — cahier des charges 2.1) ──
    NAV_PAR_ROLE = {
        "admin": ["dashboard", "caveaux", "reservations", "defunts", "concessions",
                  "exhumations", "paiements", "carte", "statistiques", "exports", "equipe"],
        "agent": ["dashboard", "caveaux", "carte"],
        "secretariat": ["dashboard", "reservations", "defunts", "concessions",
                         "exhumations", "paiements", "carte", "exports"],
        "client": ["dashboard", "recherche", "carte", "reservations", "concessions", "exhumations", "paiements"], # Ajouté recherche, concessions, exhumations
    }
    pages_autorisees = NAV_PAR_ROLE.get(SESSION_ROLE, NAV_PAR_ROLE["client"])

    TOUS_LES_NAV = [
        (ft.Icons.DASHBOARD, "Tableau de bord", "dashboard"),
        (ft.Icons.SEARCH, "Recherche", "recherche"),
        (ft.Icons.GRID_VIEW, "Caveaux", "caveaux"),
        (ft.Icons.BOOKMARK, "Reservations", "reservations"),
        (ft.Icons.PERSON, "Defunts", "defunts"),
        (ft.Icons.DESCRIPTION, "Concessions", "concessions"),
        (ft.Icons.SWAP_VERT, "Exhumations", "exhumations"),
        (ft.Icons.CREDIT_CARD, "Paiements", "paiements"),
        (ft.Icons.MAP, "Carte", "carte"),
        (ft.Icons.BAR_CHART, "Statistiques", "statistiques"),
        (ft.Icons.DOWNLOAD, "Exports", "exports"),
        (ft.Icons.GROUP, "Equipe", "equipe"),
        (ft.Icons.GROUP, "Clients", "clients"),
    ]
    nav_items_visibles = [
        nav_item(icone, texte, nom) for (icone, texte, nom) in TOUS_LES_NAV
        if nom in pages_autorisees
    ]

    sidebar = ft.Container(
        content=ft.Column([
            ft.Container(
                content=ft.Column([
                    ft.Container(height=28),
                    ft.Icon(ft.Icons.CHURCH, color=OR, size=40),
                    ft.Container(height=8),
                    ft.Text("NECROPOLIS", size=18, weight=ft.FontWeight.BOLD, color=OR),
                    ft.Text("Gestion de Cimetiere", size=10, color=GRIS),
                    ft.Container(height=24),
                ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=0),
            ),
            ft.Container(height=1, bgcolor=BORDER),
            ft.Container(height=12),
            *nav_items_visibles,
            ft.Container(expand=True),
            ft.Container(height=1, bgcolor=BORDER),
            ft.Container(
                content=ft.Column([
                    ft.Row([
                        ft.Container(width=8, height=8, bgcolor=VERT, border_radius=4),
                        ft.Text("Systeme en ligne", color=GRIS, size=11),
                    ], spacing=8),
                    ft.Text(f"{SESSION_USER} — {SESSION_ROLE}", color=GRIS, size=10),
                ], spacing=6),
                padding=16,
            ),
        ], spacing=2, expand=True),
        bgcolor=CARD,
        width=220,
        border=ft.border.only(right=ft.BorderSide(1, BORDER)),
    )

    # ── HEADER ──────────────────────────────────────
    header = ft.Container(
        content=ft.Row([
            titre_page,
            ft.Row([
                ft.Icon(ft.Icons.ACCOUNT_CIRCLE, color=OR, size=26),
                ft.Text(SESSION_USER.title() if SESSION_USER else "Utilisateur", color=BLANC, size=13, weight=ft.FontWeight.W_500),
            ], spacing=10),
        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
        bgcolor=CARD,
        padding=ft.padding.only(left=28, right=28, top=18, bottom=18),
        border=ft.border.only(bottom=ft.BorderSide(1, BORDER)),
    )

    # ── COMPOSANTS ─────────────────────────────────
    def card(contenu, padding=22):
        return ft.Container(
            content=contenu,
            bgcolor=CARD,
            border_radius=12,
            padding=padding,
            border=ft.border.all(1, BORDER),
        )

    def stat_card(titre, valeur, couleur, icone):
        return ft.Container(
            content=ft.Column([
                ft.Row([
                    ft.Container(
                        content=ft.Icon(icone, color=couleur, size=20),
                        bgcolor=SURFACE,
                        border_radius=8,
                        padding=10,
                    ),
                    ft.Text(titre, color=GRIS, size=11, weight=ft.FontWeight.W_500),
                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                ft.Container(height=14),
                ft.Text(str(valeur), size=32, weight=ft.FontWeight.BOLD, color=BLANC),
            ]),
            bgcolor=CARD,
            border_radius=12,
            padding=22,
            expand=True,
            border=ft.border.all(1, BORDER),
        )

    def badge(texte, couleur):
        libelles = {
            "disponible": "DISPONIBLE",
            "reserve": "RESERVE",
            "occupe": "OCCUPE",
            "non_exploitable": "NON EXPLOIT.",
            "en_attente": "EN ATTENTE",
            "validee": "VALIDEE",
            "annulee": "ANNULEE",
            "demande": "DEMANDE",
        }
        label = libelles.get(texte, texte.upper().replace("_", " "))
        return ft.Container(
            content=ft.Text(label, size=10, color=BLANC, weight=ft.FontWeight.BOLD),
            bgcolor=couleur,
            border_radius=6,
            padding=ft.padding.only(left=10, right=10, top=6, bottom=6),
        )

    def separateur(texte):
        return ft.Container(
            content=ft.Row([
                ft.Text(texte, color=GRIS, size=12, weight=ft.FontWeight.W_600),
            ]),
            padding=ft.padding.only(left=4, top=8, bottom=8),
        )

    def field(label, width=150):
        return ft.TextField(
            label=label,
            width=width,
            bgcolor=SURFACE,
            color=BLANC,
            border_color=BORDER,
            focused_border_color=OR,
            label_style=ft.TextStyle(color=GRIS, size=12),
            text_size=13,
            border_radius=8,
        )

    def btn_or(texte, icone, on_click):
        return ft.FilledButton(
            texte,
            icon=icone,
            on_click=on_click,
            style=ft.ButtonStyle(
                bgcolor=OR,
                color=BG,
            ),
        )

    # ── PAGE DASHBOARD ──────────────────────────────
    def page_dashboard():
        titre_page.value = "Tableau de bord"
        nom_cimetiere = "Cimetière non défini"
        try:
            reponse = httpx.get(f"{API_URL}/cimetiere/actuel", headers=HEADERS)
            if reponse.status_code == 200:
                data = reponse.json()
                nom_cimetiere = data.get("nom", "Cimetière non défini")
        except Exception as e:
            print(f"❌ DEBUG: Exception = {e}")
            
        carte_cimetiere = ft.Container(
            content=ft.Row([
                ft.Icon(ft.Icons.LOCATION_CITY, color=OR, size=32),
                ft.Container(width=14),
                ft.Column([
                    ft.Text("Cimetière géré", color=GRIS, size=11),
                    ft.Text(nom_cimetiere, color=BLANC, size=16, weight=ft.FontWeight.BOLD),
                ], spacing=2),
                ft.Container(expand=True),
                ft.Icon(ft.Icons.CHECK_CIRCLE, color=VERT, size=24),
            ]),
            bgcolor=CARD, border_radius=12, padding=20, border=ft.border.all(1, BORDER),
        )
        stats = ft.Row(spacing=14, expand=True)
        activite = ft.Column(spacing=8)
        
        # Si c'est un client
        if SESSION_ROLE == "client":
            try:
                res_list = httpx.get(f"{API_URL}/reservations", headers=HEADERS).json()
                if res_list:
                    for res in res_list[:6]:
                        col = ORANGE if res["statut"] == "en_attente" else VERT if res["statut"] == "validee" else ROUGE
                        cav_id = res.get("caveau_id") or res.get("caveau") or "?"
                        activite.controls.append(
                            ft.Container(
                                content=ft.Row([
                                    ft.Container(width=3, bgcolor=col, border_radius=2),
                                    ft.Container(width=14),
                                    ft.Column([
                                        ft.Text(f"Reservation #{res['id']}", color=BLANC, size=13, weight=ft.FontWeight.W_500),
                                        ft.Text(f"Caveau ID : {cav_id}", color=GRIS, size=11),
                                    ], spacing=2, expand=True),
                                    badge(res["statut"], col),
                                ]),
                                bgcolor=SURFACE, border_radius=8, padding=14,
                            )
                        )
                else:
                    activite.controls.append(ft.Text("Aucune reservation pour le moment.", color=GRIS, size=13))
            except:
                pass
            return ft.Column([
                carte_cimetiere,
                ft.Container(height=14),
                card(ft.Column([
                    ft.Text(f"Bienvenue, {SESSION_USER} !", color=OR, size=18, weight=ft.FontWeight.W_600),
                    ft.Container(height=10),
                    ft.Text("Consultez la carte pour trouver un caveau disponible près de chez vous.", color=BLANC, size=14),
                ])),
                ft.Container(height=24),
                separateur("MES RESERVATIONS"),
                card(activite),
            ], spacing=0)
            
        # Sinon (Admin/Agent/Secrétariat)
        try:
            d = httpx.get(f"{API_URL}/dashboard/stats", headers=HEADERS).json()
            stats.controls = [
                stat_card("Total Caveaux", d.get("caveaux", 0), OR, ft.Icons.GRID_VIEW),
                stat_card("Disponibles", d.get("disponibles", 0), VERT, ft.Icons.CHECK_CIRCLE),
                stat_card("Defunts", d.get("defunts", 0), ORANGE, ft.Icons.PERSON),
                stat_card("Reservations", d.get("reservations", 0), BLEU, ft.Icons.BOOKMARK),
                stat_card("Concessions", d.get("concessions", 0), OR2, ft.Icons.DESCRIPTION),
            ]
            
            # ALERTES PROFESSIONNELLES
            alertes = ft.Column(spacing=10)
            concessions_alerte = d.get("concessions_a_renouveler", 0)
            if concessions_alerte > 0:
                alertes.controls.append(
                    ft.Container(
                        content=ft.Row([
                            ft.Icon(ft.Icons.WARNING_AMBER, color="#FFA500", size=30),
                            ft.Container(width=15),
                            ft.Column([
                                ft.Text("Concessions à renouveler", color=BLANC, weight=ft.FontWeight.BOLD, size=14),
                                ft.Text(f"{concessions_alerte} contrat(s) expirent dans moins de 6 mois.", color=GRIS, size=12)
                            ], spacing=2, expand=True),
                            ft.IconButton(ft.Icons.ARROW_FORWARD, icon_color="#FFA500", tooltip="Voir les concessions", on_click=lambda e: afficher_page("concessions"))
                        ]),
                        bgcolor=SURFACE, border_radius=10, padding=15, border=ft.border.all(2, "#FFA500"), margin=ft.margin.only(top=10)
                    )
                )
                
            exhumations_attente = d.get("exhumations_en_attente", 0)
            if exhumations_attente > 0:
                alertes.controls.append(
                    ft.Container(
                        content=ft.Row([
                            ft.Icon(ft.Icons.PENDING_ACTIONS, color="#FF4444", size=30),
                            ft.Container(width=15),
                            ft.Column([
                                ft.Text("Exhumations en attente", color=BLANC, weight=ft.FontWeight.BOLD, size=14),
                                ft.Text(f"{exhumations_attente} demande(s) à traiter.", color=GRIS, size=12)
                            ], spacing=2, expand=True),
                            ft.IconButton(ft.Icons.ARROW_FORWARD, icon_color="#FF4444", tooltip="Voir les exhumations", on_click=lambda e: afficher_page("exhumations"))
                        ]),
                        bgcolor=SURFACE, border_radius=10, padding=15, border=ft.border.all(2, "#FF4444"), margin=ft.margin.only(top=10)
                    )
                )
                
            # ALERTE RETARDS DE PAIEMENT (CDC 6)
            try:
                retards = httpx.get(f"{API_URL}/dashboard/alertes-paiements", headers=HEADERS, timeout=5).json()
                if retards and len(retards) > 0:
                    total_du = sum(r.get('montant_du', 0) for r in retards)
                    total_du_fmt = f"{total_du:,.0f}".replace(",", " ")
                    alertes.controls.append(
                        ft.Container(
                            content=ft.Row([
                                ft.Icon(ft.Icons.MONEY_OFF, color="#FF0000", size=30),
                                ft.Container(width=15),
                                ft.Column([
                                    ft.Text(f"Retards de paiement ({len(retards)} dossier(s))", color=BLANC, weight=ft.FontWeight.BOLD, size=14),
                                    ft.Text(f"Total impayé depuis +48h : {total_du_fmt} FCFA", color=GRIS, size=12)
                                ], spacing=2, expand=True),
                                ft.IconButton(ft.Icons.ARROW_FORWARD, icon_color="#FF0000", tooltip="Voir les paiements", on_click=lambda e: afficher_page("paiements"))
                            ]),
                            bgcolor=SURFACE, border_radius=10, padding=15, border=ft.border.all(2, "#FF0000"), margin=ft.margin.only(top=10)
                        )
                    )
            except Exception as e:
                print(f"⚠️ Erreur chargement alertes paiements: {e}")
                
        except Exception as ex:
            stats.controls = [ft.Text(f"Serveur non disponible : {ex}", color=ROUGE)]
            alertes = ft.Column(spacing=10)
            
        try:
            res_list = httpx.get(f"{API_URL}/reservations", headers=HEADERS).json()
            if res_list:
                for res in res_list[:6]:
                    col = ORANGE if res["statut"] == "en_attente" else VERT if res["statut"] == "validee" else ROUGE
                    cav_id = res.get("caveau_id") or res.get("caveau") or "?"
                    activite.controls.append(
                        ft.Container(
                            content=ft.Row([
                                ft.Container(width=3, bgcolor=col, border_radius=2),
                                ft.Container(width=14),
                                ft.Column([
                                    ft.Text(f"Reservation #{res['id']}", color=BLANC, size=13, weight=ft.FontWeight.W_500),
                                    ft.Text(f"Caveau ID : {cav_id}", color=GRIS, size=11),
                                ], spacing=2, expand=True),
                                badge(res["statut"], col),
                            ]),
                            bgcolor=SURFACE, border_radius=8, padding=14,
                        )
                    )
            else:
                activite.controls.append(ft.Text("Aucune reservation", color=GRIS, size=13))
        except:
            pass
            
        layout = ft.Column([carte_cimetiere, ft.Container(height=14), stats], spacing=0)
        if 'alertes' in locals() and alertes.controls:
            layout.controls.append(ft.Container(height=20))
            layout.controls.append(separateur("⚠️ ALERTES"))
            layout.controls.append(alertes)
            
        layout.controls.append(ft.Container(height=24))
        layout.controls.append(separateur("ACTIVITE RECENTE"))
        layout.controls.append(card(activite))
        return layout

    # ── PAGE CARTE ─────────────────────────────────────
    def page_carte():
        titre_page.value = "Carte des cimetières"
        def ouvrir_carte(e):
            try:
                import tempfile, os, webbrowser
                r = httpx.get(f"{API_URL}/carte", headers=HEADERS, timeout=15)
                if r.status_code == 200:
                    chemin = os.path.join(tempfile.gettempdir(), "necropolis_carte.html")
                    with open(chemin, "w", encoding="utf-8") as f:
                        f.write(r.text)
                    webbrowser.open(f"file:///{chemin}")
                    show_msg("La carte s'est ouverte dans votre navigateur. Cliquez sur un caveau VERT pour réserver.", VERT)
                else:
                    show_msg(f"Erreur de chargement de la carte (code {r.status_code})", ROUGE)
            except Exception as ex:
                show_msg(f"Erreur : {ex}", ROUGE)
        return ft.Column([
            ft.Container(height=20),
            card(ft.Column([
                ft.Text("Carte interactive des cimetières", color=OR, size=18, weight=ft.FontWeight.BOLD),
                ft.Container(height=10),
                ft.Text("Visualisez l'emplacement de tous les caveaux et réservez directement en cliquant sur un caveau disponible.", color=GRIS, size=13),
                ft.Container(height=20),
                ft.Row([
                    ft.Container(width=16, bgcolor=VERT, border_radius=4), ft.Text(" Disponible", color=BLANC, size=12),
                    ft.Container(width=15),
                    ft.Container(width=16, bgcolor=ORANGE, border_radius=4), ft.Text(" Réservé", color=BLANC, size=12),
                    ft.Container(width=15),
                    ft.Container(width=16, bgcolor=ROUGE, border_radius=4), ft.Text(" Occupé", color=BLANC, size=12),
                ], spacing=5),
                ft.Container(height=25),
                ft.FilledButton("🗺️ Ouvrir la carte dans le navigateur", icon=ft.Icons.MAP, on_click=ouvrir_carte, style=ft.ButtonStyle(bgcolor=OR, color=BG, padding=ft.padding.symmetric(horizontal=30, vertical=15))),
            ])),
        ], spacing=0)        

    # ── PAGE CAVEAUX ──────────────────────────────
    def page_caveaux():
        titre_page.value = "Caveaux"
        liste = ft.Column(spacing=8)
        
        # Champs pour ajouter un caveau
        f_section = ft.Dropdown(
            label="Section", width=150,
            bgcolor=SURFACE, color=BLANC,
            border_color=BORDER, focused_border_color=OR,
            label_style=ft.TextStyle(color=GRIS, size=12),
            options=[
                ft.dropdown.Option("A", "Section A"),
                ft.dropdown.Option("B", "Section B"),
                ft.dropdown.Option("C", "Section C"),
                ft.dropdown.Option("D", "Section D"),
            ]
        )
        f_bloc = ft.Dropdown(
            label="Bloc", width=150,
            bgcolor=SURFACE, color=BLANC,
            border_color=BORDER, focused_border_color=OR,
            label_style=ft.TextStyle(color=GRIS, size=12),
            options=[ft.dropdown.Option(str(i), f"Bloc {i}") for i in range(1, 20)]
        )
        f_numero_auto = ft.Text("", color=OR, size=12, italic=True)
        f_statut = ft.Dropdown(
            label="Statut", width=180,
            bgcolor=SURFACE, color=BLANC,
            border_color=BORDER, focused_border_color=OR,
            label_style=ft.TextStyle(color=GRIS, size=12),
            options=[
                ft.dropdown.Option("disponible", "Disponible"),
                ft.dropdown.Option("reserve", "Réservé"),
                ft.dropdown.Option("occupe", "Occupé"),
                ft.dropdown.Option("non_exploitable", "Non exploitable"),
            ]
        )

        def generer_numero(e):
            if f_section.value and f_bloc.value:
                # Compter les caveaux existants pour cette section/bloc
                try:
                    caveaux = httpx.get(f"{API_URL}/caveaux", headers=HEADERS).json()
                    count = sum(1 for c in caveaux if c.get("section") == f_section.value and str(c.get("bloc")) == str(f_bloc.value))
                    numero = f"{f_section.value}-{str(f_bloc.value).zfill(2)}-{str(count + 1).zfill(3)}"
                    f_numero_auto.value = f"Numéro généré : {numero}"
                except:
                    f_numero_auto.value = "Erreur de génération"
            else:
                f_numero_auto.value = ""
            page.update()

        f_section.on_change = generer_numero
        f_bloc.on_change = generer_numero

        def ajouter(e):
            if not f_section.value or not f_bloc.value or not f_statut.value:
                show_msg("Remplissez tous les champs !", ROUGE)
                return
            
            # Générer le numéro
            try:
                caveaux = httpx.get(f"{API_URL}/caveaux", headers=HEADERS).json()
                count = sum(1 for c in caveaux if c.get("section") == f_section.value and str(c.get("bloc")) == str(f_bloc.value))
                numero = f"{f_section.value}-{str(f_bloc.value).zfill(2)}-{str(count + 1).zfill(3)}"
            except:
                numero = f"{f_section.value}-{str(f_bloc.value).zfill(2)}-001"
            
            try:
                data = {
                    "numero": numero,
                    "section": f_section.value,
                    "bloc": str(f_bloc.value),
                    "statut": f_statut.value,
                }
                print(f"📤 Envoi : {data}")  # ← Pour debug
                r = httpx.post(f"{API_URL}/caveaux", json=data, headers=HEADERS)
                print(f"📥 Reponse : {r.status_code} - {r.text}")  # ← Pour debug
                
                if r.status_code == 200:
                    show_msg(f"Caveau {numero} ajouté avec succès !", VERT)
                    f_section.value = f_bloc.value = f_statut.value = ""
                    f_numero_auto.value = ""
                    charger_caveaux()
                else:
                    show_msg(f"Erreur {r.status_code} : {r.text}", ROUGE)
            except Exception as ex:
                show_msg(f"Exception : {ex}", ROUGE)

        def charger_caveaux():
            liste.controls.clear()
            try:
                caveaux = httpx.get(f"{API_URL}/caveaux", headers=HEADERS).json()
                for c in caveaux:
                    col = VERT if c["statut"] == "disponible" else ORANGE if c["statut"] == "reserve" else ROUGE
                    liste.controls.append(
                        ft.Container(
                            content=ft.Row([
                                ft.Container(
                                    content=ft.Text(c["numero"], color=BLANC, size=18, weight=ft.FontWeight.W_600),
                                    bgcolor=col, border_radius=8, padding=10,
                                ),
                                ft.Container(width=14),
                                ft.Column([
                                    ft.Text(f"Section {c['section']} - Bloc {c['bloc']}", color=BLANC),
                                    ft.Text(f"Statut : {c['statut']}", color=GRIS, size=12),
                                ], spacing=2),
                                ft.Container(expand=True),
                                ft.IconButton(
                                    ft.Icons.DELETE, icon_color=ROUGE,
                                    tooltip="Supprimer",
                                    on_click=lambda e, c_id=c["id"]: supprimer_caveau(c_id),
                                ),
                            ]),
                            bgcolor=SURFACE, border_radius=12, padding=16, border=ft.border.all(1, BORDER),
                        )
                    )
                if not caveaux:
                    liste.controls.append(ft.Text("Aucun caveau enregistré", color=GRIS, size=13))
            except Exception as ex:
                liste.controls.append(ft.Text(f"Erreur : {ex}", color=ROUGE))
            page.update()

        def supprimer_caveau(c_id):
            try:
                httpx.delete(f"{API_URL}/caveaux/{c_id}", headers=HEADERS)
                show_msg("Caveau supprimé !", VERT)
                charger_caveaux()
            except Exception as ex:
                show_msg(str(ex), ROUGE)

        charger_caveaux()
        
        return ft.Column([
            card(ft.Column([
                ft.Text("Ajouter un caveau", color=OR, size=14, weight=ft.FontWeight.W_600),
                ft.Container(height=12),
                ft.Row([
                    f_section,
                    f_bloc,
                    f_statut,
                ], spacing=10, wrap=True),
                ft.Container(height=8),
                f_numero_auto,
                ft.Container(height=14),
                btn_or("Ajouter le caveau", ft.Icons.ADD, ajouter),
            ])),
            ft.Container(height=20),
            ft.Text("LISTE DES CAVEAUX", color=OR2, size=14, weight=ft.FontWeight.W_600),
            ft.Container(height=10),
            liste,
        ], spacing=0)

     # ── PAGE RESERVATIONS COMPLÈTE ET CORRIGÉE ───────────────────
    def page_reservations(caveau_id_preselectionne=None):
        titre_page.value = "Réservations"
        
        # Dropdown pour sélectionner un caveau disponible
        f_cav = ft.Dropdown(
            label="Sélectionner un caveau",
            width=350,
            bgcolor=SURFACE,
            color=BLANC,
            border_color=BORDER,
            focused_border_color=OR,
            label_style=ft.TextStyle(color=GRIS, size=12),
            options=[],
            value=str(caveau_id_preselectionne) if caveau_id_preselectionne else None,
        )
        
        # CHAMPS CLIENT (Uniquement pour Admin / Secrétaire)
        if SESSION_ROLE in ['admin', 'secretariat']:
            f_client_nom = field("Nom du client", 150)
            f_client_prenom = field("Prénom du client", 150)
            f_client_email = field("Email du client", 200)
            f_client_tel = field("Téléphone du client", 150)
        else:
            f_client_nom = f_client_prenom = f_client_email = f_client_tel = None

        # Champs DÉFUNT (pour tout le monde)
        f_nom = field("Nom du défunt", 150)
        f_prenom = field("Prénom du défunt", 150)
        f_date = field("Date de décès (YYYY-MM-DD)", 200)
        
        liste = ft.Column(spacing=8)

        # 1. Charger les caveaux disponibles
        def charger_caveaux():
            try:
                caveaux = httpx.get(f"{API_URL}/caveaux?statut=disponible", headers=HEADERS).json()
                f_cav.options = []
                for c in caveaux:
                    label = f"Caveau N°{c['numero']} - Section {c['section']} (Bloc {c['bloc']})"
                    f_cav.options.append(ft.dropdown.Option(key=str(c["id"]), text=label))
                if not f_cav.options:
                    f_cav.options.append(ft.dropdown.Option(key="", text="Aucun caveau disponible"))
                page.update()
            except Exception as ex:
                print(f"Erreur chargement caveaux: {ex}")

        # 2. Charger la liste des RÉSERVATIONS
        def charger():
            liste.controls.clear()
            try:
                reservations = httpx.get(f"{API_URL}/reservations", headers=HEADERS, timeout=10).json()
                
                for res in reservations:
                    col = ORANGE if res["statut"] == "en_attente" else VERT if res["statut"] == "validee" else ROUGE
                    icone = ft.Icons.HOURGLASS_EMPTY if res["statut"] == "en_attente" else ft.Icons.CHECK_CIRCLE
                    cav_id = res.get("caveau_numero") or res.get("caveau_id") or "?"
                    rid = res["id"]
                    nom_client = res.get("client_nom") or res.get("client", "Inconnu")
                    
                    liste.controls.append(
                        ft.Container(
                            content=ft.Column([
                                ft.Row([
                                    ft.Container(content=ft.Icon(icone, color=col, size=20), bgcolor=SURFACE, border_radius=50, padding=8),
                                    ft.Container(width=14),
                                    ft.Column([
                                        ft.Text(f"Réservation #{rid}", color=BLANC, weight=ft.FontWeight.W_600, size=14),
                                        ft.Text(f"Caveau : {cav_id} | Défunt : {res.get('nom_defunt', '')} {res.get('prenom_defunt', '')}", color=GRIS, size=12),
                                        ft.Text(f"Client : {nom_client}", color=BLEU, size=11),
                                    ], spacing=2, expand=True),
                                    badge(res["statut"], col),
                                ]),
                                ft.Container(height=8),
                                ft.Divider(height=1, color=BORDER),
                                ft.Container(height=8),
                                ft.Row([
                                    ft.IconButton(ft.Icons.CHECK_CIRCLE, icon_color=VERT, tooltip="Valider", 
                                                visible=(SESSION_ROLE in ['admin', 'secretariat'] and res["statut"] == "en_attente"), 
                                                on_click=lambda e, r_id=rid: valider(r_id)),
                                    ft.IconButton(ft.Icons.PICTURE_AS_PDF, icon_color=OR, tooltip="Facture", 
                                                on_click=lambda e, r_id=rid: telecharger_facture(r_id)),
                                    ft.IconButton(ft.Icons.DELETE, icon_color=ROUGE, tooltip="Supprimer", 
                                                visible=(SESSION_ROLE in ['admin', 'secretariat']), 
                                                on_click=lambda e, r_id=rid: supprimer(r_id)),
                                    ft.Container(expand=True),
                                    ft.Text(f"Créée le {res.get('date_reservation', 'N/A')[:10]}", color=GRIS, size=11),
                                ]),
                            ], spacing=0),
                            bgcolor=SURFACE, border_radius=12, padding=16, border=ft.border.all(1, BORDER),
                        )
                    )
                if not reservations:
                    liste.controls.append(ft.Text("Aucune réservation", color=GRIS, size=13, text_align=ft.TextAlign.CENTER))
            except Exception as e:
                print(f"❌ Erreur chargement réservations: {e}")
                liste.controls.append(ft.Text(f"Erreur: {e}", color=ROUGE))
            page.update()

        def valider(rid):
            try:
                r = httpx.put(f"{API_URL}/reservations/{rid}/valider", headers=HEADERS)
                if r.status_code == 200:
                    show_msg(f"Reservation #{rid} validee !", VERT)
                    charger()
                else:
                    show_msg(f"Erreur : {r.text}", ROUGE)
            except Exception as ex:
                show_msg(str(ex), ROUGE)

        def telecharger_facture(rid):
            try:
                r = httpx.get(f"{API_URL}/reservations/{rid}/facture", headers=HEADERS, timeout=15)
                if r.status_code == 200:
                    import tempfile, os as _os
                    chemin = _os.path.join(tempfile.gettempdir(), f"facture_{rid}.pdf")
                    with open(chemin, "wb") as f:
                        f.write(r.content)
                    webbrowser.open(f"file:///{chemin}")
                else:
                    show_msg("Impossible de generer la facture", ROUGE)
            except Exception as ex:
                show_msg(f"Erreur : {ex}", ROUGE)

        def supprimer(rid):
            try:
                r = httpx.delete(f"{API_URL}/reservations/{rid}", headers=HEADERS)
                if r.status_code == 200:
                    show_msg(f"Reservation #{rid} supprimee", VERT)
                    charger()
                    charger_caveaux()
                else:
                    show_msg(f"Erreur suppression: {r.text}", ROUGE)
            except Exception as ex:
                show_msg(f"Exception: {ex}", ROUGE)

        def creer(e):
            if not f_cav.value or not f_nom.value or not f_date.value:
                show_msg("Remplissez tous les champs obligatoires !", ROUGE)
                return
            
            try:
                from datetime import datetime
                date_deces = datetime.strptime(f_date.value, "%Y-%m-%d").date()
                if date_deces > datetime.now().date():
                    show_msg("La date de décès ne peut pas être dans le futur !", ROUGE)
                    return
            except ValueError:
                show_msg("Format de date invalide. Utilisez AAAA-MM-JJ", ROUGE)
                return
            
            data = {
                "caveau_id": int(f_cav.value),
                "nom_defunt": f_nom.value,
                "prenom_defunt": f_prenom.value,
                "date_deces": f_date.value,
            }
            
            if SESSION_ROLE in ['admin', 'secretariat']:
                if not f_client_nom.value or not f_client_email.value:
                    show_msg("Le nom et l'email du client sont obligatoires !", ROUGE)
                    return
                data.update({
                    "client_nom": f_client_nom.value,
                    "client_prenom": f_client_prenom.value,
                    "client_email": f_client_email.value,
                    "client_telephone": f_client_tel.value,
                })
            
            try:
                r = httpx.post(f"{API_URL}/reservations", json=data, headers=HEADERS)
                res_json = r.json()
                
                if r.status_code == 200:
                    show_msg("Réservation créée avec succès !", VERT)
                    f_nom.value = f_prenom.value = f_date.value = ""
                    if SESSION_ROLE in ['admin', 'secretariat']:
                        f_client_nom.value = f_client_prenom.value = f_client_email.value = f_client_tel.value = ""
                    charger()
                    charger_caveaux()
                else:
                    show_msg(f"Erreur {r.status_code} : {res_json}", ROUGE)
            except Exception as ex:
                show_msg(str(ex), ROUGE)

        # 3. FONCTION D'IMPRESSION DU REGISTRE
        def imprimer(e):
            import webbrowser, tempfile, os
            from datetime import datetime
            try:
                reservations = httpx.get(f"{API_URL}/reservations", headers=HEADERS).json()
                
                rows_html = ""
                for res in reservations:
                    client_info = res.get("client_nom") or res.get("client", "N/A")
                    enregistre_par = res.get("cree_par", "Système")
                    rows_html += f"""
                    <tr>
                        <td>#{res['id']}</td>
                        <td>{res.get('caveau_numero') or res.get('caveau_id', '')}</td>
                        <td>{res.get('nom_defunt', '')} {res.get('prenom_defunt', '')}</td>
                        <td>{client_info}</td>
                        <td>{res.get('date_deces', '')}</td>
                        <td class='status-{res['statut']}'>{res['statut'].upper()}</td>
                        <td>{enregistre_par}</td>
                        <td>{res.get('date_reservation', '')[:10]}</td>
                    </tr>
                    """
                
                html = f"""
                <!DOCTYPE html>
                <html>
                <head>
                    <title>Réservations - NECROPOLIS</title>
                    <style>
                        body {{ font-family: Arial; padding: 30px; background: white; color: black; }}
                        h1 {{ color: #c9a84c; border-bottom: 3px solid #c9a84c; padding-bottom: 10px; }}
                        table {{ width: 100%; border-collapse: collapse; margin-top: 20px; font-size: 12px; }}
                        th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
                        th {{ background: #c9a84c; color: white; }}
                        tr:nth-child(even) {{ background: #f5f5f5; }}
                        .status-en_attente {{ color: orange; font-weight: bold; }}
                        .status-validee {{ color: green; font-weight: bold; }}
                        .status-annulee {{ color: red; font-weight: bold; }}
                        .header {{ margin-bottom: 30px; }}
                        .date {{ color: #666; font-size: 14px; }}
                        @media print {{ .no-print {{ display: none; }} }}
                    </style>
                </head>
                <body>
                    <div class="header">
                        <h1>📋 Registre des Réservations</h1>
                        <p class="date">Généré le {datetime.now().strftime('%d/%m/%Y à %H:%M')}</p>
                    </div>
                    <table>
                        <thead>
                            <tr>
                                <th>ID</th>
                                <th>Caveau</th>
                                <th>Défunt</th>
                                <th>Client</th>
                                <th>Date décès</th>
                                <th>Statut</th>
                                <th>Enregistré par</th>
                                <th>Date</th>
                            </tr>
                        </thead>
                        <tbody>
                            {rows_html}
                        </tbody>
                    </table>
                    <button class="no-print" onclick="window.print()" style="margin-top: 20px; padding: 10px 20px; background: #c9a84c; color: white; border: none; cursor: pointer; border-radius: 5px;">🖨️ Imprimer le registre</button>
                </body>
                </html>
                """
                chemin = os.path.join(tempfile.gettempdir(), "reservations.html")
                with open(chemin, "w", encoding="utf-8") as f:
                    f.write(html)
                webbrowser.open(f"file:///{chemin}")
            except Exception as ex:
                show_msg(f"Erreur impression: {ex}", ROUGE)

        def verifier_selection_depuis_carte():
            try:
                # On utilise HEADERS directement (c'est la variable qui marche pour le reste de l'appli)
                # print(f"🔍 Headers envoyés: {HEADERS}") # Décommente si tu veux voir le token
                
                r = httpx.get(f"{API_URL}/caveau-selectionne", headers=HEADERS, timeout=5)
                
                if r.status_code == 200:
                    data = r.json()
                    if data.get("caveau_id"):
                        caveau_id = str(data["caveau_id"])
                        caveau_numero = data.get("caveau_numero", "?")
                        
                        # Mettre à jour l'interface
                        charger_caveaux() 
                        f_cav.value = caveau_id
                        show_msg(f"✅ Caveau N°{caveau_numero} sélectionné depuis la carte !", VERT)
                        page.update()
                        
                elif r.status_code == 401:
                    # Si ça fait encore 401, c'est que le token dans HEADERS a expiré
                    print("⚠️ Erreur 401 : Le token de connexion a peut-être expiré. Reconnecte-toi.")
                    
            except Exception as e:
                pass # On ignore les erreurs réseau pour ne pas spammer
            
            # Relancer la vérification dans 3 secondes
            import threading
            threading.Timer(3.0, verifier_selection_depuis_carte).start()

        # Initialisation
        verifier_selection_depuis_carte()
        charger_caveaux()
        charger()
        
        # 5. CONSTRUCTION DE L'INTERFACE (LE RETURN EST OBLIGATOIRE)
        colonnes_formulaire = [f_cav, f_nom, f_prenom, f_date]
        if SESSION_ROLE in ['admin', 'secretariat']:
            colonnes_formulaire = [f_cav, f_client_nom, f_client_prenom, f_client_email, f_client_tel, f_nom, f_prenom, f_date]

        return ft.Column([
            card(ft.Column([
                ft.Text("Nouvelle reservation", color=OR, size=16, weight=ft.FontWeight.BOLD),
                ft.Container(height=14),
                ft.Row(colonnes_formulaire, spacing=10, wrap=True),
                ft.Container(height=14),
                btn_or("Creer la reservation", ft.Icons.SAVE, creer),
            ])),
            ft.Container(height=20),
            ft.Row([
                ft.Text("LISTE DES RESERVATIONS", color=OR2, size=14, weight=ft.FontWeight.BOLD),
                ft.Container(expand=True),
                ft.FilledButton("🖨️ Imprimer", on_click=imprimer, style=ft.ButtonStyle(bgcolor=BORDER, color=BLANC)),
                ft.Container(width=10),
                ft.FilledButton("🔄 Actualiser", on_click=lambda e: charger(), style=ft.ButtonStyle(bgcolor=BORDER, color=BLANC)),
            ]),
            ft.Container(height=14),
            liste,
        ], spacing=0)

    # ── PAGE DEFUNTS ────────────────────────────────
    def page_defunts():
        titre_page.value = "Defunts"
        liste = ft.Column(spacing=8)

        try:
            reservations = httpx.get(f"{API_URL}/reservations", headers=HEADERS).json()
            if reservations:
                for res in reservations:
                    cav_id = res.get("caveau_id") or res.get("caveau") or "?"
                    nom = res.get("nom_defunt") or res.get("defunt_nom") or "Non precise"
                    prenom = res.get("prenom_defunt") or res.get("defunt_prenom") or ""
                    col = ORANGE if res["statut"] == "en_attente" else VERT if res["statut"] == "validee" else ROUGE
                    liste.controls.append(
                        ft.Container(
                            content=ft.Row([
                                ft.Container(width=3, bgcolor=col, border_radius=2),
                                ft.Container(width=14),
                                ft.Column([
                                    ft.Text(f"{nom} {prenom}".strip(), color=BLANC, weight=ft.FontWeight.W_500, size=13),
                                    ft.Text(f"Caveau N° {cav_id}  •  Reservation #{res['id']}", color=GRIS, size=11),
                                ], spacing=2, expand=True),
                                badge(res["statut"], col),
                            ]),
                            bgcolor=SURFACE,
                            border_radius=8,
                            padding=14,
                        )
                    )
            else:
                liste.controls.append(ft.Text("Aucun defunt enregistre", color=GRIS, size=13))
        except Exception as ex:
            liste.controls.append(ft.Text(f"Erreur : {ex}", color=ROUGE))

        return ft.Column([
            card(ft.Column([
                ft.Text("Les defunts sont enregistres automatiquement lors d'une reservation.", color=GRIS, size=13),
                ft.Text("Pour ajouter un defunt, creez une reservation avec ses informations.", color=GRIS, size=13),
            ])),
            ft.Container(height=20),
            separateur("REGISTRE DES DEFUNTS"),
            liste,
        ], spacing=0)

    # ── PAGE PAIEMENTS AMÉLIORÉE (PARTIEL + HISTORIQUE) ──────────────────────
    def page_paiements():
        titre_page.value = "Paiements"
        
        # 1. Dropdown pour sélectionner une réservation
        f_res = ft.Dropdown(
            label="Sélectionner une réservation",
            width=350, bgcolor=SURFACE, color=BLANC,
            border_color=BORDER, focused_border_color=OR,
            label_style=ft.TextStyle(color=GRIS, size=12),
            options=[],
        )
        
        # 2. NOUVEAU : Champ pour le montant (permet les paiements partiels)
        f_montant = ft.TextField(
            label="Montant à payer (FCFA)",
            width=200, bgcolor=SURFACE, color=BLANC,
            border_color=BORDER, focused_border_color=OR,
            label_style=ft.TextStyle(color=GRIS, size=12),
            keyboard_type=ft.KeyboardType.NUMBER,
        )
        
        f_tel = field("Numéro de téléphone (04, 05, 06)", 180)
        f_methode = ft.Dropdown(
            label="Méthode de paiement", width=210,
            bgcolor=SURFACE, color=BLANC,
            border_color=BORDER, focused_border_color=OR,
            label_style=ft.TextStyle(color=GRIS, size=12),
            options=[
                ft.dropdown.Option("airtel_money", "Airtel Money"),
                ft.dropdown.Option("mtn_money", "MTN Money"),
                ft.dropdown.Option("mpesa", "M-Pesa"),
                ft.dropdown.Option("especes", "Espèces"),
                ft.dropdown.Option("virement", "Virement bancaire"),
            ]
        )

        # Zone pour l'historique des transactions
        zone_historique = ft.Column(spacing=8)

        # ── Fonctions de chargement ──
        def charger_reservations():
            try:
                reservations = httpx.get(f"{API_URL}/reservations", headers=HEADERS).json()
                reservations_payables = [r for r in reservations if r.get("statut") != "payee"]
                f_res.options = []
                for r in reservations_payables:
                    caveau_info = f"Caveau N°{r.get('caveau_numero', r.get('caveau_id', '?'))}"
                    defunt_info = f"{r.get('prenom_defunt', '')} {r.get('nom_defunt', '')}".strip()
                    montant_total = r.get('montant_total', 750000)
                    label = f"#{r['id']} - {caveau_info} ({defunt_info}) | Total: {montant_total} FCFA"
                    f_res.options.append(ft.dropdown.Option(key=str(r["id"]), text=label))
                if not f_res.options:
                    f_res.options.append(ft.dropdown.Option(key="", text="Aucune réservation en attente"))
                page.update()
            except Exception as ex:
                print(f"Erreur chargement réservations: {ex}")

        def charger_historique(reservation_id):
            zone_historique.controls.clear()
            if not reservation_id:
                page.update()
                return
            try:
                r = httpx.get(f"{API_URL}/paiement/historique/{reservation_id}", headers=HEADERS, timeout=5)
                if r.status_code == 200:
                    transactions = r.json()
                    if transactions:
                        zone_historique.controls.append(
                            ft.Text(f"📜 Historique des transactions ({len(transactions)} paiement(s))", 
                                    color=OR2, size=13, weight=ft.FontWeight.BOLD)
                        )
                        for t in transactions:
                            date_fmt = t.get('date', '')[:16]
                            zone_historique.controls.append(
                                ft.Container(
                                    content=ft.Row([
                                        ft.Icon(ft.Icons.RECEIPT_LONG, color=VERT, size=16),
                                        ft.Container(width=10),
                                        ft.Column([
                                            ft.Text(f"{t.get('montant', 0):,.0f} FCFA via {t.get('methode', 'N/A')}".replace(",", " "), 
                                                    color=BLANC, size=12, weight=ft.FontWeight.W_600),
                                            ft.Text(f"Réf: {t.get('reference', '')} | {date_fmt}", color=GRIS, size=10),
                                        ], spacing=2),
                                        ft.Container(expand=True),
                                        ft.Icon(ft.Icons.CHECK_CIRCLE, color=VERT, size=16),
                                    ]),
                                    bgcolor=SURFACE, border_radius=8, padding=12, border=ft.border.all(1, BORDER),
                                )
                            )
                    else:
                        zone_historique.controls.append(
                            ft.Text("Aucun paiement enregistré pour cette réservation.", color=GRIS, size=12, italic=True)
                        )
            except Exception as e:
                pass
            page.update()

        def on_res_change(e):
            if f_res.value:
                charger_historique(f_res.value)
        f_res.on_change = on_res_change

        # ── Fonction de paiement ──
        def payer(e):
            if not f_res.value or not f_methode.value or not f_tel.value or not f_montant.value:
                show_msg("Veuillez remplir TOUS les champs (y compris le montant).", ROUGE)
                return
            
            tel = f_tel.value.replace(" ", "").replace("-", "")
            if not tel.isdigit() or len(tel) != 9 or not tel.startswith(("04", "05", "06")):
                show_msg("Numéro invalide (9 chiffres, commence par 04/05/06).", ROUGE)
                return

            try:
                montant_a_payer = float(f_montant.value)
                if montant_a_payer <= 0:
                    show_msg("Le montant doit être supérieur à 0.", ROUGE)
                    return
            except ValueError:
                show_msg("Montant invalide.", ROUGE)
                return

            try:
                data = {
                    "reservation_id": int(f_res.value),
                    "methode": f_methode.value,
                    "numero_telephone": tel,
                    "montant": montant_a_payer,
                }
                r = httpx.post(f"{API_URL}/paiement/simuler", json=data, headers=HEADERS, timeout=10)
                res = r.json()
                if r.status_code == 200:
                    show_msg(res.get("message", "Paiement enregistré !"), VERT)
                    f_tel.value = f_montant.value = ""
                    charger_reservations()
                    charger_historique(f_res.value)
                else:
                    show_msg(f"Erreur: {res.get('error', r.text)}", ROUGE)
            except Exception as ex:
                show_msg(str(ex), ROUGE)

        # Initialisation
        charger_reservations()

        # ── Interface (LE RETURN EST OBLIGATOIRE) ──
        return ft.Column([
            card(ft.Column([
                ft.Text("Encaissement et suivi des paiements", color=OR, size=16, weight=ft.FontWeight.BOLD),
                ft.Text("Vous pouvez régler une réservation en plusieurs fois (paiement partiel).", color=GRIS, size=12),
                ft.Container(height=16),
                ft.Row([f_res, f_montant], spacing=10, wrap=True),
                ft.Container(height=10),
                ft.Row([f_tel, f_methode], spacing=10, wrap=True),
                ft.Container(height=14),
                btn_or("Valider le paiement", ft.Icons.CREDIT_CARD, payer),
            ])),
            ft.Container(height=20),
            zone_historique,
        ], spacing=0)
    
        # ── PAGE RECHERCHE PUBLIQUE (client uniquement) ────────
    def page_recherche_publique():
        titre_page.value = "Recherche de Caveaux"
        
        f_ville = ft.Dropdown(
            label="Sélectionner une ville",
            width=300,
            bgcolor=SURFACE,
            color=BLANC,
            border_color=BORDER,
            focused_border_color=OR,
            label_style=ft.TextStyle(color=GRIS, size=12),
            options=[],
        )
        
        resultats = ft.Column(spacing=8)
        stats_villes = ft.Column(spacing=10)
        
        def charger_stats():
            try:
                r = httpx.get(f"{API_URL}/cimetières/par-ville", headers=HEADERS)
                if r.status_code == 200:
                    villes_data = r.json()
                    stats_villes.controls.clear()
                    options_ville = []
                    
                    for v in villes_data:
                        ville_nom = v.get('ville') or "Non spécifié"
                        total = v.get('total_caveaux', 0)
                        dispo = v.get('caveaux_disponibles', 0)
                        
                        options_ville.append(ft.dropdown.Option(ville_nom))
                        
                        stats_villes.controls.append(
                            ft.Container(
                                content=ft.Row([
                                    ft.Container(
                                        content=ft.Icon(ft.Icons.LOCATION_CITY, color=OR, size=20),
                                        bgcolor=SURFACE, border_radius=10, padding=10,
                                    ),
                                    ft.Container(width=14),
                                    ft.Column([
                                        ft.Text(f"{ville_nom}", color=BLANC, size=13, weight=ft.FontWeight.W_600),
                                        ft.Text(f"{dispo} caveau(x) disponible(s) sur {total}", color=GRIS, size=11),
                                    ], spacing=2, expand=True),
                                    ft.Container(
                                        content=ft.Text(f"{dispo}/{total}", color=VERT, size=12, weight=ft.FontWeight.BOLD),
                                        bgcolor=SURFACE, border_radius=6, padding=ft.padding.only(left=10, right=10, top=5, bottom=5),
                                    ),
                                ]),
                                bgcolor=CARD, border_radius=10, padding=14, border=ft.border.all(1, BORDER),
                            )
                        )
                    
                    f_ville.options = options_ville
                    page.update()
            except Exception as ex:
                print(f"Erreur chargement stats: {ex}")
        
        def rechercher(e):
            if not f_ville.value:
                show_msg("Sélectionnez une ville", ROUGE)
                return
            
            try:
                r = httpx.get(f"{API_URL}/caveaux/recherche?ville={f_ville.value}", headers=HEADERS)
                if r.status_code == 200:
                    caveaux = r.json()
                    resultats.controls.clear()
                    
                    if caveaux:
                        for c in caveaux:
                            resultats.controls.append(
                                ft.Container(
                                    content=ft.Row([
                                        ft.Container(width=4, bgcolor=VERT, border_radius=2),
                                        ft.Container(width=14),
                                        ft.Column([
                                            ft.Text(f"Caveau N° {c['numero']}", color=BLANC, size=13, weight=ft.FontWeight.W_500),
                                            ft.Text(f"Section {c['section']} - Bloc {c['bloc']}", color=GRIS, size=11),
                                            ft.Text(f"Cimetière: {c['cimetiere']}", color=OR, size=11),
                                        ], spacing=2, expand=True),
                                        ft.Icon(ft.Icons.CHECK_CIRCLE, color=VERT, size=20),
                                    ]),
                                    bgcolor=SURFACE, border_radius=8, padding=14,
                                )
                            )
                        show_msg(f"{len(caveaux)} caveau(x) trouvé(s)", VERT)
                    else:
                        resultats.controls.append(ft.Text("Aucun caveau disponible dans cette ville", color=GRIS, size=13))
                    page.update()
            except Exception as ex:
                show_msg(f"Erreur: {ex}", ROUGE)
        
        charger_stats()
        
        return ft.Column([
            card(ft.Column([
                ft.Text("Disponibilité par ville", color=OR, size=14, weight=ft.FontWeight.W_600),
                ft.Container(height=14),
                stats_villes,
            ])),
            ft.Container(height=20),
            card(ft.Column([
                ft.Text("Rechercher un caveau", color=OR, size=14, weight=ft.FontWeight.W_600),
                ft.Container(height=14),
                f_ville,
                ft.Container(height=14),
                btn_or("Rechercher les disponibilités", ft.Icons.SEARCH, rechercher),
            ])),
            ft.Container(height=20),
            separateur("RÉSULTATS"),
            resultats,
        ], spacing=0)

    
    # ─ PAGE STATISTIQUES AVEC GRAPHIQUES ──────────────
    def page_statistiques():
        titre_page.value = "Statistiques"
        
        # Récupérer les données
        try:
            stats = httpx.get(f"{API_URL}/dashboard/stats", headers=HEADERS).json()
            caveaux = httpx.get(f"{API_URL}/caveaux", headers=HEADERS).json()
            reservations = httpx.get(f"{API_URL}/reservations", headers=HEADERS).json()
            concessions = httpx.get(f"{API_URL}/concessions", headers=HEADERS).json()
        except:
            stats = {"caveaux": 0, "disponibles": 0, "defunts": 0, "reservations": 0, "concessions": 0}
            caveaux = []
            reservations = []
            concessions = []

        # Calculer les pourcentages
        total = stats.get("caveaux", 0) or 1
        disponibles = stats.get("disponibles", 0)
        occupes = stats.get("occupes", 0)
        reserves = stats.get("reserves", 0)
        pct_dispo = (disponibles / total) * 100
        pct_occupe = (occupes / total) * 100
        pct_reserve = (reserves / total) * 100

        # Créer un fichier HTML avec Chart.js
        import tempfile, os, webbrowser
        from datetime import datetime, timedelta
        
        # Générer des données pour le graphique des revenus (6 derniers mois)
        mois_labels = []
        revenus_data = []
        today = datetime.now()
        for i in range(5, -1, -1):
            date = today - timedelta(days=i*30)
            mois_labels.append(date.strftime("%b %Y"))
            revenus_data.append(0)  # À remplacer par de vraies données
        
        # Générer des données pour les réservations par mois
        reservations_mois = [0] * 6
        for res in reservations:
            # Compter les réservations par mois
            pass
        
        html_content = f"""
        <!DOCTYPE html>
        <html lang="fr">
        <head>
            <meta charset="UTF-8">
            <title>Statistiques - NECROPOLIS</title>
            <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
            <style>
                * {{ margin: 0; padding: 0; box-sizing: border-box; }}
                body {{ 
                    font-family: 'Segoe UI', Arial, sans-serif;
                    background: linear-gradient(135deg, #0a0a14 0%, #1a1a2e 100%);
                    color: #e0e0e0;
                    padding: 20px;
                    min-height: 100vh;
                }}
                .header {{
                    background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
                    padding: 20px 30px;
                    border-radius: 12px;
                    margin-bottom: 20px;
                    border: 1px solid #c9a84c;
                    box-shadow: 0 4px 20px rgba(0,0,0,0.3);
                }}
                .header h1 {{
                    color: #c9a84c;
                    font-size: 24px;
                    margin-bottom: 5px;
                }}
                .header p {{
                    color: #888;
                    font-size: 13px;
                }}
                .stats-grid {{
                    display: grid;
                    grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
                    gap: 15px;
                    margin-bottom: 20px;
                }}
                .stat-card {{
                    background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
                    padding: 20px;
                    border-radius: 12px;
                    border: 1px solid #333;
                    box-shadow: 0 4px 15px rgba(0,0,0,0.2);
                }}
                .stat-card h3 {{
                    color: #888;
                    font-size: 13px;
                    margin-bottom: 10px;
                    text-transform: uppercase;
                }}
                .stat-card .value {{
                    font-size: 32px;
                    font-weight: bold;
                    color: #c9a84c;
                }}
                .stat-card .trend {{
                    font-size: 12px;
                    color: #4caf50;
                    margin-top: 5px;
                }}
                .charts-grid {{
                    display: grid;
                    grid-template-columns: repeat(auto-fit, minmax(400px, 1fr));
                    gap: 20px;
                    margin-bottom: 20px;
                }}
                .chart-container {{
                    background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
                    padding: 20px;
                    border-radius: 12px;
                    border: 1px solid #333;
                    box-shadow: 0 4px 15px rgba(0,0,0,0.2);
                }}
                .chart-container h3 {{
                    color: #c9a84c;
                    margin-bottom: 15px;
                    font-size: 16px;
                }}
                .chart-wrapper {{
                    position: relative;
                    height: 300px;
                }}
                .btn-print {{
                    background: #c9a84c;
                    color: #0a0a14;
                    border: none;
                    padding: 12px 24px;
                    border-radius: 8px;
                    cursor: pointer;
                    font-weight: bold;
                    font-size: 14px;
                    margin-bottom: 20px;
                    transition: all 0.3s;
                }}
                .btn-print:hover {{
                    background: #e0c068;
                    transform: translateY(-2px);
                }}
                @media print {{
                    .btn-print {{ display: none; }}
                    body {{ background: white; color: black; }}
                    .stat-card, .chart-container {{ 
                        background: white; 
                        border: 1px solid #ddd;
                        box-shadow: none;
                    }}
                    .stat-card .value, .header h1 {{ color: black; }}
                }}
            </style>
        </head>
        <body>
            <div class="header">
                <h1>📊 Tableau de bord statistique</h1>
                <p>Vue d'ensemble de l'occupation et de l'activité du cimetière</p>
            </div>
            
            <button class="btn-print" onclick="window.print()">🖨️ Imprimer le rapport</button>
            
            <div class="stats-grid">
                <div class="stat-card">
                    <h3>Total Caveaux</h3>
                    <div class="value">{total}</div>
                    <div class="trend">100% du parc</div>
                </div>
                <div class="stat-card">
                    <h3>Disponibles</h3>
                    <div class="value" style="color: #4caf50;">{disponibles}</div>
                    <div class="trend">{pct_dispo:.1f}% disponibles</div>
                </div>
                <div class="stat-card">
                    <h3>Occupés</h3>
                    <div class="value" style="color: #f44336;">{occupes}</div>
                    <div class="trend">{pct_occupe:.1f}% occupés</div>
                </div>
                <div class="stat-card">
                    <h3>Réservés</h3>
                    <div class="value" style="color: #ff9800;">{reserves}</div>
                    <div class="trend">{pct_reserve:.1f}% réservés</div>
                </div>
                <div class="stat-card">
                    <h3>Défunts</h3>
                    <div class="value">{stats.get('defunts', 0)}</div>
                    <div class="trend">Enregistrés</div>
                </div>
                <div class="stat-card">
                    <h3>Réservations</h3>
                    <div class="value">{stats.get('reservations', 0)}</div>
                    <div class="trend">Actives</div>
                </div>
            </div>
            
            <div class="charts-grid">
                <div class="chart-container">
                    <h3>🥧 Répartition des caveaux</h3>
                    <div class="chart-wrapper">
                        <canvas id="pieChart"></canvas>
                    </div>
                </div>
                <div class="chart-container">
                    <h3>📈 Évolution des réservations</h3>
                    <div class="chart-wrapper">
                        <canvas id="lineChart"></canvas>
                    </div>
                </div>
            </div>
            
            <div class="charts-grid">
                <div class="chart-container" style="grid-column: 1 / -1;">
                    <h3>📊 Occupation par section</h3>
                    <div class="chart-wrapper">
                        <canvas id="barChart"></canvas>
                    </div>
                </div>
            </div>

            <script>
                // Graphique camembert - Répartition
                new Chart(document.getElementById('pieChart'), {{
                    type: 'doughnut',
                    data: {{
                        labels: ['Disponibles', 'Occupés', 'Réservés'],
                        datasets: [{{
                            data: [{disponibles}, {occupes}, {reserves}],
                            backgroundColor: ['#4caf50', '#f44336', '#ff9800'],
                            borderWidth: 0
                        }}]
                    }},
                    options: {{
                        responsive: true,
                        maintainAspectRatio: false,
                        plugins: {{
                            legend: {{
                                position: 'bottom',
                                labels: {{ color: '#e0e0e0', padding: 15 }}
                            }}
                        }}
                    }}
                }});

                // Graphique ligne - Évolution
                new Chart(document.getElementById('lineChart'), {{
                    type: 'line',
                    data: {{
                        labels: {mois_labels},
                        datasets: [{{
                            label: 'Réservations',
                            data: {reservations_mois},
                            borderColor: '#c9a84c',
                            backgroundColor: 'rgba(201, 168, 76, 0.1)',
                            fill: true,
                            tension: 0.4
                        }}]
                    }},
                    options: {{
                        responsive: true,
                        maintainAspectRatio: false,
                        plugins: {{
                            legend: {{
                                labels: {{ color: '#e0e0e0' }}
                            }}
                        }},
                        scales: {{
                            x: {{
                                ticks: {{ color: '#888' }},
                                grid: {{ color: '#333' }}
                            }},
                            y: {{
                                ticks: {{ color: '#888' }},
                                grid: {{ color: '#333' }},
                                beginAtZero: true
                            }}
                        }}
                    }}
                }});

                // Graphique barres - Par section
                new Chart(document.getElementById('barChart'), {{
                    type: 'bar',
                    data: {{
                        labels: ['Section A', 'Section B', 'Section C', 'Section D'],
                        datasets: [{{
                            label: 'Occupés',
                            data: [12, 8, 15, 6],
                            backgroundColor: '#f44336'
                        }}, {{
                            label: 'Disponibles',
                            data: [18, 22, 15, 24],
                            backgroundColor: '#4caf50'
                        }}]
                    }},
                    options: {{
                        responsive: true,
                        maintainAspectRatio: false,
                        plugins: {{
                            legend: {{
                                labels: {{ color: '#e0e0e0' }}
                            }}
                        }},
                        scales: {{
                            x: {{
                                stacked: true,
                                ticks: {{ color: '#888' }},
                                grid: {{ color: '#333' }}
                            }},
                            y: {{
                                stacked: true,
                                ticks: {{ color: '#888' }},
                                grid: {{ color: '#333' }},
                                beginAtZero: true
                            }}
                        }}
                    }}
                }});
            </script>
        </body>
        </html>
        """
        
        # Sauvegarder et ouvrir
        chemin = os.path.join(tempfile.gettempdir(), "necropolis_stats.html")
        with open(chemin, "w", encoding="utf-8") as f:
            f.write(html_content)
        
        def ouvrir_stats(e):
            webbrowser.open(f"file:///{chemin}")
        
        return ft.Column([
            card(ft.Column([
                ft.Text("Statistiques avancées", color=OR, size=16, weight=ft.FontWeight.BOLD),
                ft.Container(height=10),
                ft.Text("Visualisez l'occupation et l'activité de votre cimetière avec des graphiques interactifs.", color=GRIS),
                ft.Container(height=20),
                ft.FilledButton(
                    "Ouvrir le tableau de bord statistique",
                    icon=ft.Icons.ANALYTICS,
                    on_click=ouvrir_stats,
                    style=ft.ButtonStyle(bgcolor=OR, color=BG),
                ),
            ])),
        ], spacing=0)

        # ── PAGE CONCESSIONS AMÉLIORÉE ───────────────────
    def page_concessions():
        titre_page.value = "Concessions"
        liste = ft.Column(spacing=10)
        
        # Dropdown avec les numéros de caveaux
        f_cav = ft.Dropdown(
            label="Sélectionner un caveau",
            width=300,
            bgcolor=SURFACE,
            color=BLANC,
            border_color=BORDER,
            focused_border_color=OR,
            label_style=ft.TextStyle(color=GRIS, size=12),
            options=[],
        )
        f_type = ft.Dropdown(
            label="Type", width=190, bgcolor=SURFACE, color=BLANC,
            border_color=BORDER, focused_border_color=OR,
            label_style=ft.TextStyle(color=GRIS, size=12),
            options=[
                ft.dropdown.Option("temporaire", "Temporaire (5 ans)"),
                ft.dropdown.Option("perpetuelle", "Perpétuelle"),
            ]
        )
        f_debut = field("Date debut (YYYY-MM-DD)", 190)
        f_fin = field("Date fin (YYYY-MM-DD)", 190)

        # 1. Charger les caveaux disponibles
        def charger_caveaux_concessions():
            try:
                caveaux = httpx.get(f"{API_URL}/caveaux?statut=disponible", headers=HEADERS).json()
                f_cav.options = []
                for c in caveaux:
                    label = f"Caveau N°{c['numero']} - Section {c['section']} (Bloc {c['bloc']})"
                    f_cav.options.append(ft.dropdown.Option(key=str(c["id"]), text=label))
                if not f_cav.options:
                    f_cav.options.append(ft.dropdown.Option(key="", text="Aucun caveau disponible"))
                page.update()
            except Exception as ex:
                print(f"❌ Erreur chargement caveaux: {ex}")

        # 2. Charger la liste des concessions (CORRECTION INDENTATION ICI)
        def charger():
            liste.controls.clear()
            try:
                concessions = httpx.get(f"{API_URL}/concessions", headers=HEADERS, timeout=10).json()
                
                for c in concessions:
                    couleur = VERT if c.get("type_concession") == "perpetuelle" else ORANGE
                    caveau_numero = c.get("caveau_numero") or f"N°{c.get('caveau_id', '?')}"
                    
                    # Déterminer si on peut résilier (seulement admin/secrétaire)
                    peut_resilier = SESSION_ROLE in ['admin', 'secretariat']
                    
                    liste.controls.append(
                        ft.Container(
                            content=ft.Row([
                                ft.Container(
                                    content=ft.Icon(ft.Icons.DESCRIPTION, color=couleur, size=24),
                                    bgcolor=SURFACE, border_radius=10, padding=12,
                                ),
                                ft.Container(width=14),
                                ft.Column([
                                    ft.Text(f"Concession {c.get('type_concession', 'N/A')}", color=BLANC, size=14, weight=ft.FontWeight.W_600),
                                    ft.Text(f"{caveau_numero} | Du {c.get('date_debut', 'N/A')} au {c.get('date_fin', 'Perpétuelle')}", color=GRIS, size=12),
                                ], spacing=4, expand=True),
                                ft.Container(
                                    content=ft.Text(f"{c.get('montant', 0)} FCFA", color=VERT, size=14, weight=ft.FontWeight.BOLD),
                                    bgcolor=SURFACE, border_radius=8, padding=ft.padding.only(left=15, right=15, top=8, bottom=8),
                                ),
                                # BOUTON RÉSILIER
                                ft.IconButton(
                                    ft.Icons.CANCEL,  # ✅ Icône valide
                                    icon_color=ROUGE, 
                                    tooltip="Résilier cette concession",
                                    visible=peut_resilier,
                                    on_click=lambda e, cid=c["id"], cav=caveau_numero: resilier_concession(cid, cav),
                                ) if peut_resilier else ft.Container(width=48),
                            ]),
                            bgcolor=CARD, border_radius=12, padding=16, border=ft.border.all(1, BORDER),
                        )
                    )
                
                if not concessions:
                    liste.controls.append(ft.Text("Aucune concession active", color=GRIS, size=13, text_align=ft.TextAlign.CENTER))
                    
            except Exception as e:
                print(f"❌ ERREUR CHARGEMENT CONCESSIONS: {e}")
                liste.controls.append(ft.Text(f"Erreur: {e}", color=ROUGE))
            
            page.update()
        
        # 3. Créer une concession
        def creer(e):
            if not f_cav.value or not f_type.value or not f_debut.value:
                show_msg("Remplissez tous les champs obligatoires !", ROUGE)
                return
            try:
                data = {
                    "caveau_id": int(f_cav.value),
                    "type_concession": f_type.value,
                    "date_debut": f_debut.value,
                    "date_fin": f_fin.value or None,
                }
                r = httpx.post(f"{API_URL}/concessions", json=data, headers=HEADERS, timeout=10)
                if r.status_code == 200:
                    show_msg("Concession creee avec succes !", VERT)
                    f_debut.value = f_fin.value = ""
                    page.update()
                    charger()
                    charger_caveaux_concessions()
                else:
                    show_msg(f"Erreur: {r.text}", ROUGE)
            except Exception as ex:
                show_msg(str(ex), ROUGE)
        
        # 4. Imprimer le registre
        def imprimer(e):
            import webbrowser, tempfile, os
            from datetime import datetime
            try:
                concessions = httpx.get(f"{API_URL}/concessions", headers=HEADERS).json()
                html = f"""
                <!DOCTYPE html>
                <html>
                <head>
                    <title>Concessions - NECROPOLIS</title>
                    <style>
                        body {{ font-family: Arial; padding: 30px; background: white; color: black; }}
                        h1 {{ color: #c9a84c; border-bottom: 3px solid #c9a84c; padding-bottom: 10px; }}
                        table {{ width: 100%; border-collapse: collapse; margin-top: 20px; }}
                        th, td {{ border: 1px solid #ddd; padding: 12px; text-align: left; }}
                        th {{ background: #c9a84c; color: white; }}
                        tr:nth-child(even) {{ background: #f5f5f5; }}
                        .header {{ margin-bottom: 30px; }}
                        .date {{ color: #666; font-size: 14px; }}
                        @media print {{ .no-print {{ display: none; }} }}
                    </style>
                </head>
                <body>
                    <div class="header">
                        <h1>📜 Registre des Concessions</h1>
                        <p class="date">Généré le {datetime.now().strftime('%d/%m/%Y à %H:%M')}</p>
                    </div>
                    <table>
                        <thead>
                            <tr>
                                <th>Type</th>
                                <th>Caveau</th>
                                <th>Date début</th>
                                <th>Date fin</th>
                                <th>Montant</th>
                            </tr>
                        </thead>
                        <tbody>
                            {''.join([f"<tr><td>{c.get('type_concession', '')}</td><td>{c.get('caveau_numero') or 'N/A'}</td><td>{c.get('date_debut', '')}</td><td>{c.get('date_fin', '')}</td><td>{c.get('montant', 0)} FCFA</td></tr>" for c in concessions])}
                        </tbody>
                    </table>
                    <button class="no-print" onclick="window.print()" style="margin-top: 20px; padding: 10px 20px; background: #c9a84c; color: white; border: none; cursor: pointer;">🖨️ Imprimer</button>
                </body>
                </html>
                """
                chemin = os.path.join(tempfile.gettempdir(), "concessions.html")
                with open(chemin, "w", encoding="utf-8") as f:
                    f.write(html)
                webbrowser.open(f"file:///{chemin}")
            except Exception as ex:
                show_msg(f"Erreur impression: {ex}", ROUGE)

        # 5. Résilier une concession
        def resilier_concession(cid, caveau_numero):
            def confirmer(e):
                try:
                    r = httpx.post(f"{API_URL}/concessions/{cid}/resilier", headers=HEADERS)
                    if r.status_code == 200:
                        show_msg(f"Concession du caveau {caveau_numero} résiliée !", VERT)
                        charger()
                        charger_caveaux_concessions() # Rafraîchir les caveaux dispo
                    else:
                        show_msg(f"Erreur: {r.json().get('error', 'Inconnu')}", ROUGE)
                except Exception as ex:
                    show_msg(str(ex), ROUGE)
                page.overlay.remove(dlg)
                page.update()

            def annuler(e):
                page.overlay.remove(dlg)
                page.update()

            dlg = ft.AlertDialog(
                title=ft.Text("Confirmer la résiliation"),
                content=ft.Text(f"Êtes-vous sûr de vouloir résilier la concession du caveau {caveau_numero} ?\nLe caveau sera remis en statut 'Disponible'."),
                actions=[
                    ft.TextButton("Annuler", on_click=annuler),
                    ft.TextButton("Résilier", on_click=confirmer, style=ft.ButtonStyle(color=ROUGE)),
                ],
            )
            page.overlay.append(dlg)
            dlg.open = True
            page.update()

        # Initialisation
        charger_caveaux_concessions()
        charger()

        return ft.Column([
            card(ft.Column([
                ft.Text("Nouvelle concession funeraire", color=OR, size=16, weight=ft.FontWeight.BOLD),
                ft.Text("Attribution, renouvellement et suivi des contrats de concession.", color=GRIS, size=12),
                ft.Container(height=16),
                ft.Row([f_cav, f_type, f_debut, f_fin], spacing=10, wrap=True),
                ft.Container(height=14),
                btn_or("Creer la concession", ft.Icons.SAVE, creer),
            ])),
            ft.Container(height=20),
            ft.Row([
                ft.Text("LISTE DES CONCESSIONS", color=OR2, size=14, weight=ft.FontWeight.BOLD),
                ft.Container(expand=True),
                ft.FilledButton("🖨️ Imprimer", on_click=imprimer, style=ft.ButtonStyle(bgcolor=BORDER, color=BLANC)),
            ]),
            ft.Container(height=14),
            liste,
        ], spacing=0)

    
    # ── PAGE EXHUMATIONS AMÉLIORÉE ────────────────────
    def page_exhumations():
        titre_page.value = "Exhumations"
        liste = ft.Column(spacing=10)
        
        # Dropdown pour sélectionner un défunt
        f_def = ft.Dropdown(
            label="Sélectionner un défunt",
            width=350,
            bgcolor=SURFACE,
            color=BLANC,
            border_color=BORDER,
            focused_border_color=OR,
            label_style=ft.TextStyle(color=GRIS, size=12),
            options=[],
        )
        f_motif = ft.TextField(
            label="Motif de la demande",
            width=450,
            bgcolor=SURFACE,
            color=BLANC,
            border_color=BORDER,
            focused_border_color=OR,
            label_style=ft.TextStyle(color=GRIS, size=12),
            multiline=True,
            min_lines=2,
        )

        # 1. Charger la liste des défunts
        def charger_defunts():
            try:
                defunts = httpx.get(f"{API_URL}/defunts", headers=HEADERS, timeout=10).json()
                f_def.options = []
                for d in defunts:
                    label = f"{d.get('prenom', '')} {d.get('nom', '')} (Décédé le {d.get('date_deces', 'N/A')})"
                    f_def.options.append(ft.dropdown.Option(key=str(d["id"]), text=label))
                if not f_def.options:
                    f_def.options.append(ft.dropdown.Option(key="", text="Aucun défunt enregistré"))
                page.update()
            except Exception as ex:
                print(f"❌ Erreur chargement défunts: {ex}")

        # 2. Charger la liste des exhumations
        def charger_exhumations():
            liste.controls.clear()
            try:
                reponse = httpx.get(f"{API_URL}/exhumations", headers=HEADERS, timeout=10)
                if reponse.status_code != 200:
                    liste.controls.append(ft.Text(f"Erreur API: {reponse.status_code}", color=ROUGE))
                    page.update()
                    return
                
                exhumations = reponse.json()
                
                for exh in exhumations:
                    col = ORANGE if exh.get("statut") == "en_attente" else VERT if exh.get("statut") == "validee" else ROUGE
                    icone = ft.Icons.HOURGLASS_TOP if exh.get("statut") == "en_attente" else ft.Icons.CHECK_CIRCLE
                    
                    defunt_nom = exh.get("defunt_nom") or f"Défunt ID: {exh.get('defunt_id', 'N/A')}"
                    ex_id = exh.get("id")
                    
                    liste.controls.append(
                        ft.Container(
                            content=ft.Column([
                                ft.Row([
                                    ft.Container(
                                        content=ft.Icon(icone, color=col, size=24),
                                        bgcolor=SURFACE, border_radius=50, padding=12,
                                    ),
                                    ft.Container(width=15),
                                    ft.Column([
                                        ft.Text(f"Demande #{ex_id}", color=BLANC, size=14, weight=ft.FontWeight.BOLD),
                                        ft.Text(f"Motif : {exh.get('motif', 'N/A')}", color=GRIS, size=12),
                                        ft.Text(defunt_nom, color=GRIS, size=11),
                                    ], spacing=3, expand=True),
                                    badge(exh.get("statut", "inconnu"), col),
                                ]),
                                ft.Container(height=12),
                                ft.Divider(height=1, color=BORDER),
                                ft.Container(height=8),
                                ft.Row([
                                    ft.IconButton(
                                        ft.Icons.CHECK_CIRCLE, icon_color=VERT, tooltip="Valider la demande", 
                                        visible=(SESSION_ROLE in ['admin', 'secretariat'] and exh.get("statut") == "en_attente"), 
                                        on_click=lambda e, eid=ex_id: valider_exhumation(eid)
                                    ),
                                    ft.IconButton(
                                        ft.Icons.DO_NOT_DISTURB_ON, icon_color=ORANGE, tooltip="Marquer comme réalisé", 
                                        visible=(SESSION_ROLE in ['admin', 'agent'] and exh.get("statut") == "validee"), 
                                        on_click=lambda e, eid=ex_id: realiser_exhumation(eid)
                                    ),
                                    ft.IconButton(
                                        ft.Icons.PICTURE_AS_PDF, icon_color=OR, tooltip="Télécharger le Procès-Verbal", 
                                        visible=(exh.get("statut") == "realisee"), 
                                        on_click=lambda e, eid=ex_id: telecharger_pv(eid)
                                    ),
                                    ft.Container(expand=True),
                                ], spacing=5),
                            ], spacing=0),
                            bgcolor=CARD, border_radius=12, padding=16, border=ft.border.all(1, BORDER),
                        )
                    )
                
                if not exhumations:
                    liste.controls.append(ft.Text("Aucune demande d'exhumation", color=GRIS, size=13, text_align=ft.TextAlign.CENTER))
            except Exception as e:
                print(f"❌ EXCEPTION EXHUMATIONS: {e}")
                liste.controls.append(ft.Text(f"Erreur: {str(e)}", color=ROUGE))
            page.update()

        # 3. Créer une demande
        def creer(e):
            if not f_def.value or not f_motif.value:
                show_msg("Veuillez sélectionner un défunt et remplir le motif", ROUGE)
                return
            try:
                data = {
                    "defunt_id": int(f_def.value),
                    "motif": f_motif.value,
                    "document_legal": "Document en attente",
                    "date_souhaitee": None
                }
                r = httpx.post(f"{API_URL}/exhumations", json=data, headers=HEADERS, timeout=10)
                if r.status_code == 200:
                    show_msg("Demande d'exhumation soumise avec succès !", VERT)
                    f_motif.value = ""
                    charger_exhumations()
                else:
                    show_msg(f"Erreur: {r.text}", ROUGE)
            except Exception as ex:
                show_msg(str(ex), ROUGE)
        
        # 4. Imprimer le registre
        def imprimer(e):
            import webbrowser, tempfile, os
            from datetime import datetime
            try:
                exhumations = httpx.get(f"{API_URL}/exhumations", headers=HEADERS).json()
                html = f"""
                <!DOCTYPE html>
                <html>
                <head>
                    <title>Exhumations - NECROPOLIS</title>
                    <style>
                        body {{ font-family: Arial; padding: 30px; background: white; color: black; }}
                        h1 {{ color: #c9a84c; border-bottom: 3px solid #c9a84c; padding-bottom: 10px; }}
                        table {{ width: 100%; border-collapse: collapse; margin-top: 20px; }}
                        th, td {{ border: 1px solid #ddd; padding: 12px; text-align: left; }}
                        th {{ background: #c9a84c; color: white; }}
                        tr:nth-child(even) {{ background: #f5f5f5; }}
                        @media print {{ .no-print {{ display: none; }} }}
                    </style>
                </head>
                <body>
                    <div class="header">
                        <h1>⚖️ Registre des Demandes d'Exhumation</h1>
                        <p class="date">Généré le {datetime.now().strftime('%d/%m/%Y à %H:%M')}</p>
                    </div>
                    <table>
                        <thead>
                            <tr>
                                <th>ID Demande</th>
                                <th>Défunt</th>
                                <th>Motif</th>
                                <th>Statut</th>
                            </tr>
                        </thead>
                        <tbody>
                            {''.join([f"<tr><td>#{exh.get('id')}</td><td>{exh.get('defunt_nom', 'N/A')}</td><td>{exh.get('motif')}</td><td>{exh.get('statut', '').upper()}</td></tr>" for exh in exhumations])}
                        </tbody>
                    </table>
                    <button class="no-print" onclick="window.print()" style="margin-top: 20px; padding: 10px 20px; background: #c9a84c; color: white; border: none; cursor: pointer; border-radius: 5px;">🖨️ Imprimer</button>
                </body>
                </html>
                """
                chemin = os.path.join(tempfile.gettempdir(), "exhumations.html")
                with open(chemin, "w", encoding="utf-8") as f:
                    f.write(html)
                webbrowser.open(f"file:///{chemin}")
            except Exception as ex:
                show_msg(f"Erreur impression: {ex}", ROUGE)

        # 5. Fonctions d'action (INDENTATION CORRECTE : 8 espaces pour être dans page_exhumations)
        def valider_exhumation(eid):
            try:
                r = httpx.post(f"{API_URL}/exhumations/{eid}/valider", headers=HEADERS)
                if r.status_code == 200:
                    show_msg("Exhumation validée avec succès !", VERT)
                    charger_exhumations()
                else:
                    show_msg(f"Erreur: {r.text}", ROUGE)
            except Exception as ex:
                show_msg(str(ex), ROUGE)

        def realiser_exhumation(eid):
            try:
                r = httpx.post(f"{API_URL}/exhumations/{eid}/realiser", headers=HEADERS)
                if r.status_code == 200:
                    show_msg("Exhumation marquée comme réalisée ! Le caveau est libéré.", VERT)
                    charger_exhumations()
                else:
                    show_msg(f"Erreur: {r.text}", ROUGE)
            except Exception as ex:
                show_msg(str(ex), ROUGE)

        def telecharger_pv(eid):
            try:
                r = httpx.get(f"{API_URL}/exhumations/{eid}/pv", headers=HEADERS, timeout=15)
                if r.status_code == 200:
                    import tempfile, os
                    chemin = os.path.join(tempfile.gettempdir(), f"PV_Exhumation_{eid}.pdf")
                    with open(chemin, "wb") as f:
                        f.write(r.content)
                    webbrowser.open(f"file:///{chemin}")
                    show_msg("Procès-Verbal téléchargé et ouvert !", VERT)
                else:
                    show_msg(f"Erreur de génération du PV: {r.text}", ROUGE)
            except Exception as ex:
                show_msg(f"Erreur réseau : {ex}", ROUGE)

        # Initialisation
        charger_defunts()
        charger_exhumations()

        # Return final (8 espaces)
        return ft.Column([
            card(ft.Column([
                ft.Text("Nouvelle demande d'exhumation", color=OR, size=16, weight=ft.FontWeight.BOLD),
                ft.Text("Enregistrement de la demande avec validation administrative et traçabilité complète.", color=GRIS, size=12),
                ft.Container(height=16),
                ft.Row([f_def, f_motif], spacing=10, wrap=True),
                ft.Container(height=14),
                btn_or("Soumettre la demande", ft.Icons.SEND, creer),
            ])),
            ft.Container(height=20),
            ft.Row([
                ft.Text("LISTE DES DEMANDES", color=OR2, size=14, weight=ft.FontWeight.BOLD),
                ft.Container(expand=True),
                ft.FilledButton("🖨️ Imprimer", on_click=imprimer, style=ft.ButtonStyle(bgcolor=BORDER, color=BLANC)),
            ]),
            ft.Container(height=14),
            liste,
        ], spacing=0)

        # ══════════════════════════════════════════════
    # NOUVELLE PAGE : CLIENTS INSCRITS
    # ═══════════════════════════════════════════════
    def page_clients():
        titre_page.value = "Clients Inscrits"
        liste_clients = ft.Column(spacing=10)
        
        def charger_clients():
            liste_clients.controls.clear()
            try:
                reponse = httpx.get(f"{API_URL}/clients", headers=HEADERS, timeout=10)
                clients = reponse.json()
                
                for client in clients:
                    liste_clients.controls.append(
                        ft.Container(
                            content=ft.Row([
                                ft.Container(
                                    content=ft.Text(client.get('username', '?')[0].upper(), color=BLANC),
                                    bgcolor=BLEU, border_radius=50, padding=15,
                                ),
                                ft.Container(width=15),
                                ft.Column([
                                    ft.Text(f"{client.get('nom', '')} {client.get('prenom', '')}".strip() or client.get('username'), 
                                          color=BLANC, size=14, weight=ft.FontWeight.BOLD),
                                    ft.Text(f"📧 {client.get('email', '')} | 📱 {client.get('telephone', 'N/A')}", 
                                          color=GRIS, size=11),
                                    ft.Text(f"Inscrit le {client.get('date_inscription', 'N/A')}", color=GRIS, size=10),
                                ], spacing=3, expand=True),
                                ft.Container(
                                    content=ft.Text(f"{client.get('nb_reservations', 0)} réservations", color=OR, size=12),
                                    bgcolor=SURFACE, border_radius=8, padding=10,
                                ),
                            ]),
                            bgcolor=CARD, border_radius=12, padding=16, border=ft.border.all(1, BORDER),
                        )
                    )
            except Exception as e:
                print(f"❌ Erreur chargement clients: {e}")
                liste_clients.controls.append(ft.Text(f"Erreur: {e}", color=ROUGE))
            page.update()
        
        charger_clients()
        
        return ft.Column([
            ft.Row([
                ft.Text("LISTE DES CLIENTS INSCRITS", color=OR2, size=16, weight=ft.FontWeight.BOLD),
                ft.Container(expand=True),
                ft.FilledButton("🔄 Rafraîchir", on_click=lambda e: charger_clients(), 
                              style=ft.ButtonStyle(bgcolor=BORDER, color=BLANC)),
            ]),
            ft.Container(height=20),
            liste_clients,
        ], spacing=0)

        # ── PAGE EQUIPE ───────────────────────────────
    def page_equipe():
        titre_page.value = "Equipe"
        liste_membres = ft.Column(spacing=10)
        
        # Formulaire d'ajout COMPLET avec nom, prénom, téléphone
        f_user = field("Nom d'utilisateur", 200)
        f_email = field("Email", 250)
        f_mdp = ft.TextField(
            label="Mot de passe",
            width=200,
            password=True,
            can_reveal_password=True,
            bgcolor=SURFACE,
            color=BLANC,
            border_color=BORDER,
            focused_border_color=OR,
            label_style=ft.TextStyle(color=GRIS, size=12),
        )
        f_nom = field("Nom", 150)
        f_prenom = field("Prénom", 150)
        f_tel = field("Téléphone (04/05/06)", 180)
        f_role = ft.Dropdown(
            label="Role", width=180,
            bgcolor=SURFACE, color=BLANC,
            border_color=BORDER, focused_border_color=OR,
            label_style=ft.TextStyle(color=GRIS, size=12),
            options=[
                ft.dropdown.Option("secretariat", "Secrétaire"),
                ft.dropdown.Option("agent", "Agent de terrain"),
            ]
        )

        def charger_equipe():
            liste_membres.controls.clear()
            try:
                equipe = httpx.get(f"{API_URL}/equipe", headers=HEADERS).json()
                
                for membre in equipe:
                    role_badge = badge(membre.get("role", "inconnu"), OR if membre.get("role")=="admin" else BLEU)
                    
                    # Affichage avec nom complet si disponible
                    nom_complet = membre.get("nom") or membre.get("username", "?")
                    prenom = membre.get("prenom", "")
                    tel = membre.get("telephone", "")
                    
                    liste_membres.controls.append(
                        ft.Container(
                            content=ft.Row([
                                ft.Container(
                                    content=ft.Text(nom_complet[0].upper(), color=BLANC),
                                    bgcolor=OR if membre.get("role")=="admin" else BLEU,
                                    border_radius=50, padding=15,
                                ),
                                ft.Container(width=14),
                                ft.Column([
                                    ft.Text(f"{nom_complet} {prenom}".strip(), color=BLANC, weight=ft.FontWeight.W_600),
                                    ft.Text(f"{membre.get('email', '')} | {tel}", color=GRIS, size=12),
                                ], spacing=2, expand=True),
                                role_badge,
                            ]),
                            bgcolor=CARD, border_radius=12, padding=16, border=ft.border.all(1, BORDER),
                        )
                    )
                
                if not equipe:
                    liste_membres.controls.append(ft.Text("Aucun membre pour l'instant.", color=GRIS))
            except Exception as ex:
                print(f"❌ Erreur chargement équipe: {ex}")
                liste_membres.controls.append(ft.Text(f"Erreur: {ex}", color=ROUGE))
            page.update()
        
        def ajouter_membre(e):
            if not f_user.value or not f_email.value or not f_mdp.value or not f_role.value:
                show_msg("Remplissez tous les champs obligatoires !", ROUGE)
                return
            
            # Validation du téléphone
            tel = f_tel.value.replace(" ", "").replace("-", "")
            if tel and (not tel.isdigit() or len(tel) != 9 or not tel.startswith(("04", "05", "06"))):
                show_msg("Téléphone invalide. Doit être 9 chiffres commençant par 04, 05 ou 06.", ROUGE)
                return
            
            try:
                data = {
                    "username": f_user.value,
                    "email": f_email.value,
                    "password": f_mdp.value,
                    "role": f_role.value,
                    "nom": f_nom.value,
                    "prenom": f_prenom.value,
                    "telephone": tel,
                }
                r = httpx.post(f"{API_URL}/equipe", json=data, headers=HEADERS)
                if r.status_code == 200:
                    show_msg("Membre ajouté avec succès !", VERT)
                    f_user.value = f_email.value = f_mdp.value = f_nom.value = f_prenom.value = f_tel.value = ""
                    charger_equipe()
                else:
                    show_msg(f"Erreur: {r.text}", ROUGE)
            except Exception as ex:
                show_msg(str(ex), ROUGE)

        charger_equipe()
        
        return ft.Column([
            card(ft.Column([
                ft.Text("Ajouter un membre de l'équipe", color=OR, size=14, weight=ft.FontWeight.W_600),
                ft.Text("Créez un compte Secrétaire ou Agent de terrain rattaché à votre cimetière.", color=GRIS, size=12),
                ft.Container(height=16),
                ft.Row([f_user, f_email, f_mdp], spacing=10, wrap=True),
                ft.Container(height=10),
                ft.Row([f_nom, f_prenom, f_tel], spacing=10, wrap=True),
                ft.Container(height=10),
                ft.Row([f_role, btn_or("Créer le compte", ft.Icons.PERSON_ADD, ajouter_membre)], spacing=10, wrap=True),
            ])),
            ft.Container(height=20),
            ft.Text("Membres de l'équipe", color=OR2, size=14, weight=ft.FontWeight.W_600),
            ft.Container(height=10),
            liste_membres,
        ], spacing=0)

        # ─ PAGE EXPORTS AMÉLIORÉE ────────────────────────
    def page_exports():
        titre_page.value = "Exports"
        
        def exporter_caveaux_csv(e):
            try:
                r = httpx.get(f"{API_URL}/export/caveaux/csv", headers=HEADERS)
                if r.status_code == 200:
                    import tempfile, os
                    chemin = os.path.join(tempfile.gettempdir(), "caveaux.csv")
                    with open(chemin, "wb") as f:
                        f.write(r.content)
                    webbrowser.open(f"file:///{chemin}")
                    show_msg("Export CSV des caveaux généré !", VERT)
            except Exception as ex:
                show_msg(f"Erreur : {ex}", ROUGE)
        
        def exporter_caveaux_excel(e):
            try:
                r = httpx.get(f"{API_URL}/export/caveaux/excel", headers=HEADERS)
                if r.status_code == 200:
                    import tempfile, os
                    chemin = os.path.join(tempfile.gettempdir(), "caveaux.xlsx")
                    with open(chemin, "wb") as f:
                        f.write(r.content)
                    webbrowser.open(f"file:///{chemin}")
                    show_msg("Export Excel des caveaux généré !", VERT)
            except Exception as ex:
                show_msg(f"Erreur : {ex}", ROUGE)
        
        def exporter_reservations_csv(e):
            try:
                r = httpx.get(f"{API_URL}/export/reservations/csv", headers=HEADERS)
                if r.status_code == 200:
                    import tempfile, os
                    chemin = os.path.join(tempfile.gettempdir(), "reservations.csv")
                    with open(chemin, "wb") as f:
                        f.write(r.content)
                    webbrowser.open(f"file:///{chemin}")
                    show_msg("Export CSV des réservations généré !", VERT)
            except Exception as ex:
                show_msg(f"Erreur : {ex}", ROUGE)
        
        def exporter_defunts_excel(e):
            try:
                r = httpx.get(f"{API_URL}/exports/defunts/excel", headers=HEADERS)
                if r.status_code == 200:
                    import tempfile, os
                    chemin = os.path.join(tempfile.gettempdir(), "defunts.xlsx")
                    with open(chemin, "wb") as f:
                        f.write(r.content)
                    webbrowser.open(f"file:///{chemin}")
                    show_msg("Export Excel des défunts généré !", VERT)
            except Exception as ex:
                show_msg(f"Erreur : {ex}", ROUGE)
        
        def exporter_concessions_pdf(e):
            try:
                r = httpx.get(f"{API_URL}/exports/concessions/pdf", headers=HEADERS)
                if r.status_code == 200:
                    import tempfile, os
                    chemin = os.path.join(tempfile.gettempdir(), "concessions.pdf")
                    with open(chemin, "wb") as f:
                        f.write(r.content)
                    webbrowser.open(f"file:///{chemin}")
                    show_msg("Export PDF des concessions généré !", VERT)
                else:
                    show_msg(f"Erreur API: {r.status_code} - {r.text}", ROUGE)
            except Exception as ex:
                show_msg(f"Erreur : {ex}", ROUGE)
        
        return ft.Column([
            card(ft.Column([
                ft.Text("Extraction des registres", color=OR, size=16, weight=ft.FontWeight.BOLD),
                ft.Container(height=8),
                ft.Text("Exportez vos données en CSV, Excel ou PDF pour archivage et reporting.", color=GRIS, size=12),
                ft.Container(height=20),
                
                # Section Caveaux
                ft.Text("📦 Caveaux", color=BLANC, size=14, weight=ft.FontWeight.W_600),
                ft.Container(height=10),
                ft.Row([
                    ft.FilledButton("📄 CSV", on_click=exporter_caveaux_csv, style=ft.ButtonStyle(bgcolor=BLEU, color=BLANC)),
                    ft.FilledButton("📊 Excel", on_click=exporter_caveaux_excel, style=ft.ButtonStyle(bgcolor=VERT, color=BLANC)),
                ], spacing=10),
                
                ft.Container(height=20),
                ft.Divider(color=BORDER),
                ft.Container(height=20),
                
                # Section Réservations
                ft.Text("📋 Réservations", color=BLANC, size=14, weight=ft.FontWeight.W_600),
                ft.Container(height=10),
                ft.Row([
                    ft.FilledButton("📄 CSV", on_click=exporter_reservations_csv, style=ft.ButtonStyle(bgcolor=BLEU, color=BLANC)),
                ], spacing=10),
                
                ft.Container(height=20),
                ft.Divider(color=BORDER),
                ft.Container(height=20),
                
                # Section Défunts
                ft.Text("⚰️ Défunts", color=BLANC, size=14, weight=ft.FontWeight.W_600),
                ft.Container(height=10),
                ft.Row([
                    ft.FilledButton("📊 Excel", on_click=exporter_defunts_excel, style=ft.ButtonStyle(bgcolor=VERT, color=BLANC)),
                ], spacing=10),
                
                ft.Container(height=20),
                ft.Divider(color=BORDER),
                ft.Container(height=20),
                
                # Section Concessions
                ft.Text("📜 Concessions", color=BLANC, size=14, weight=ft.FontWeight.W_600),
                ft.Container(height=10),
                ft.Row([
                    ft.FilledButton("📕 PDF", on_click=exporter_concessions_pdf, style=ft.ButtonStyle(bgcolor=ROUGE, color=BLANC)),
                ], spacing=10),
                
                ft.Container(height=20),
                ft.Container(
                    content=ft.Row([
                        ft.Icon(ft.Icons.INFO_OUTLINE, color=OR, size=20),
                        ft.Container(width=10),
                        ft.Text(
                            "Les exports sont générés au format standard pour une compatibilité maximale "
                            "avec Excel, LibreOffice et les logiciels de gestion.",
                            color=GRIS, size=12, expand=True,
                        ),
                    ]),
                    padding=14, 
                    bgcolor=SURFACE, 
                    border_radius=10, 
                    border=ft.border.all(1, BORDER),
                ),
            ])),
        ], spacing=0)    

    # ── NAVIGATION ──────────────────────────────────
    def afficher_page(nom):
        contenu_principal.controls.clear()
        status_msg.visible = False
        pages = {
            "dashboard": page_dashboard,
            "caveaux": page_caveaux,
            "reservations": page_reservations,
            "defunts": page_defunts,
            "paiements": page_paiements,
            "carte": page_carte,
            "statistiques": page_statistiques,
            "concessions": page_concessions,
            "exhumations": page_exhumations,
            "exports": page_exports,
            "equipe": page_equipe,
            "recherche": page_recherche_publique,
            "clients": page_clients,
        }
        if nom in pages:
            contenu_principal.controls.append(pages[nom]())
        contenu_principal.controls.append(ft.Container(height=24))
        contenu_principal.controls.append(status_msg)
        page.update()

    # ─ LAYOUT GLOBAL ───────────────────────────────
    page.add(
        ft.Row([
            sidebar,
            ft.Column([
                header,
                ft.Container(
                    content=contenu_principal,
                    expand=True,
                    padding=26,
                ),
            ], expand=True, spacing=0),
        ], expand=True, spacing=0)
    )

    afficher_page("dashboard")

    

    

ft.app(target=main)