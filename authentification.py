import flet as ft
import requests
import subprocess
import sys
import os
import random
import string
import time
import threading

API = "http://127.0.0.1:8000/api"

# ── Palette NECROPOLIS Premium ───────────────────────
NOIR     = "#05050d"
CARD     = "#0b0b18"
SURFACE  = "#12122a"
SURFACE2 = "#1a1a35"
BORDER   = "#2a2a50"
OR       = "#d4a857"
OR2      = "#f0c96a"
OR_DIM   = "#7a5a20"
BLANC    = "#ffffff"
GRIS     = "#a0a0c0"
GRIS2    = "#606080"
VERT     = "#00e676"
ROUGE    = "#ff5252"
BLEU     = "#448aff"


def main(page: ft.Page):
    page.title = "NECROPOLIS — Gestion de Cimetière"
    page.bgcolor = NOIR
    page.vertical_alignment   = ft.MainAxisAlignment.CENTER
    page.horizontal_alignment = ft.CrossAxisAlignment.CENTER
    page.window_width  = 540
    page.window_height = 880
    page.padding = 0

    store        = {}
    status_ctrl  = {"ref": ft.Container(visible=False)}

    # ─────────────────────────────────────
    # HELPERS COMPATIBLES FLET 0.85
    # ─────────────────────────────────────
    def border_box(color=BORDER, w=1):
        s = ft.BorderSide(w, color)
        return ft.Border(top=s, bottom=s, left=s, right=s)

    def champ(label, width=420, password=False, hint="", valeur=""):
        return ft.TextField(
            label=label, hint_text=hint, value=valeur,
            width=width, bgcolor=SURFACE2, color=BLANC,
            border_color=BORDER, focused_border_color=OR,
            border_radius=12,
            label_style=ft.TextStyle(color=OR2, size=12, weight=ft.FontWeight.W_500),
            hint_style=ft.TextStyle(color=GRIS2, size=12),
            text_style=ft.TextStyle(color=BLANC, size=14),
            cursor_color=OR,
            password=password, can_reveal_password=password,
            content_padding=16,
        )

    def btn_gold(texte, on_click, width=420, icone=None):
        return ft.Container(
            content=ft.ElevatedButton(
                texte, width=width, on_click=on_click,
                icon=icone,
                style=ft.ButtonStyle(
                    bgcolor=OR, color=NOIR,
                    elevation=6,
                    padding=16,
                ),
            ),
            shadow=ft.BoxShadow(
                spread_radius=0,
                blur_radius=20,
                color="#40d4a857",
                offset=ft.Offset(0, 4),
            ),
        )

    def btn_outline(texte, on_click, width=200):
        return ft.OutlinedButton(
            texte, width=width, on_click=on_click,
            style=ft.ButtonStyle(
                color=OR,
                side=ft.BorderSide(1, OR),
                padding=14,
            ),
        )

    # ── Ticker moderne — animation CSS via ft.AnimatedSwitcher ──────────
    def ticker_moderne(messages: list):
        """
        Affiche les messages un par un avec un fondu/slide élégant.
        Sobre, 2026, sans emoji enfantins.
        """
        idx_state = {"i": 0, "running": False}

        label = ft.Text(
            messages[0],
            color=OR,
            size=11,
            weight=ft.FontWeight.W_600,
            text_align=ft.TextAlign.CENTER,
            no_wrap=True,
        )

        dot_left  = ft.Container(width=4, height=4, bgcolor=OR_DIM, border_radius=4)
        dot_right = ft.Container(width=4, height=4, bgcolor=OR_DIM, border_radius=4)

        conteneur_ticker = ft.Container(
            content=ft.Row(
                [
                    dot_left,
                    ft.Container(width=10),
                    label,
                    ft.Container(width=10),
                    dot_right,
                ],
                alignment=ft.MainAxisAlignment.CENTER,
            ),
            width=420,
            padding=ft.Padding(left=16, right=16, top=9, bottom=9),
            bgcolor=SURFACE,
            border_radius=30,
            border=border_box(BORDER, 1),
        )

        def _cycle():
            while idx_state["running"]:
                time.sleep(3.5)
                if not idx_state["running"]:
                    break
                idx_state["i"] = (idx_state["i"] + 1) % len(messages)
                label.value = messages[idx_state["i"]]
                # Faire clignoter les dots pour indiquer le changement
                dot_left.bgcolor  = OR
                dot_right.bgcolor = OR
                try:
                    page.update()
                except Exception:
                    break
                time.sleep(0.25)
                dot_left.bgcolor  = OR_DIM
                dot_right.bgcolor = OR_DIM
                try:
                    page.update()
                except Exception:
                    break

        def start():
            if not idx_state["running"]:
                idx_state["running"] = True
                threading.Thread(target=_cycle, daemon=True).start()

        def stop():
            idx_state["running"] = False

        return conteneur_ticker, start, stop

    # ── Bloc conseil / info contextuelle ──────────────────────────────
    def bloc_conseil(texte, icone=ft.Icons.INFO_OUTLINE, couleur=OR):
        """
        Affiche un conseil entièrement visible, propre et sobre.
        Pas de Row avec expand qui coupe le texte.
        """
        return ft.Container(
            content=ft.Column(
                [
                    ft.Row([
                        ft.Container(
                            content=ft.Icon(icone, color=couleur, size=14),
                            bgcolor=SURFACE2,
                            border_radius=20,
                            padding=6,
                        ),
                        ft.Container(width=10),
                        ft.Text(
                            "Conseil",
                            color=couleur,
                            size=11,
                            weight=ft.FontWeight.W_700,
                        ),
                    ]),
                    ft.Container(height=6),
                    ft.Text(
                        texte,
                        color=GRIS,
                        size=12,
                        text_align=ft.TextAlign.LEFT,
                    ),
                ],
                spacing=0,
            ),
            width=420,
            padding=ft.Padding(left=14, right=14, top=12, bottom=12),
            bgcolor=SURFACE,
            border_radius=14,
            border=border_box(BORDER, 1),
        )

    def badge_etape(n, total=7):
        return ft.Container(
            content=ft.Text(f"  {n} / {total}  ", size=11, color=OR, weight=ft.FontWeight.BOLD),
            bgcolor=SURFACE2, border_radius=20,
            border=border_box(OR, 1),
            padding=ft.Padding(left=12, right=12, top=5, bottom=5),
        )

    def barre_prog(n, total=7):
        segments = []
        for i in range(total):
            segments.append(ft.Container(
                expand=True, height=4,
                bgcolor=OR if i < n else SURFACE2,
                border_radius=4,
            ))
            if i < total - 1:
                segments.append(ft.Container(width=4))
        return ft.Row(segments, width=420)

    def icone_logo(size=44):
        return ft.Container(
            content=ft.Icon(ft.Icons.CHURCH, color=OR, size=size),
            bgcolor=SURFACE2,
            border_radius=size,
            padding=size // 3,
            shadow=ft.BoxShadow(
                spread_radius=0, blur_radius=24,
                color="#50d4a857", offset=ft.Offset(0, 0),
            ),
        )

    def logo_complet(taille=38):
        return ft.Column([
            icone_logo(taille),
            ft.Container(height=10),
            ft.Text("NECROPOLIS", size=22, weight=ft.FontWeight.BOLD,
        color=BLANC),
            ft.Text("Système de gestion funéraire", color=GRIS, size=11),
        ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=2)

    def ligne_sep(texte=""):
        if texte:
            return ft.Row([
                ft.Container(height=1, expand=True, bgcolor=BORDER),
                ft.Container(
                    content=ft.Text(f"  {texte}  ", size=11, color=GRIS2),
                ),
                ft.Container(height=1, expand=True, bgcolor=BORDER),
            ])
        return ft.Container(height=1, bgcolor=BORDER)

    def set_status(texte, couleur=ROUGE):
        c = status_ctrl["ref"]
        c.content = ft.Row([
            ft.Icon(ft.Icons.CHECK_CIRCLE if couleur == VERT else ft.Icons.ERROR_OUTLINE,
                    color=couleur, size=16),
            ft.Text(texte, color=couleur, size=12),
        ], spacing=8)
        c.bgcolor      = SURFACE2
        c.border_radius = 10
        c.padding      = 12
        c.visible      = True
        page.update()

    def clear_status():
        status_ctrl["ref"].visible = False
        page.update()

    def new_status():
        s = ft.Container(visible=False)
        status_ctrl["ref"] = s
        return s

    def retour_btn(destination, label="← Retour"):
        return ft.TextButton(
            label, on_click=lambda e: afficher(destination()),
            style=ft.ButtonStyle(color=GRIS),
        )

    # ─────────────────────────────────────
    # NAVIGATION
    # ─────────────────────────────────────
    conteneur = ft.Column(
        scroll=ft.ScrollMode.AUTO,
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        expand=True,
    )

    def afficher(contenu):
        conteneur.controls = [
            ft.Container(height=24),
            ft.Container(
                content=contenu,
                width=480,
                padding=36,
                bgcolor=CARD,
                border_radius=28,
                border=border_box(BORDER),
                shadow=ft.BoxShadow(
                    spread_radius=0, blur_radius=40,
                    color="#20d4a857", offset=ft.Offset(0, 8),
                ),
            ),
            ft.Container(height=24),
        ]
        page.update()

    # ─────────────────────────────────────
    # PAGE ACCUEIL
    # ─────────────────────────────────────
    def page_accueil():
        s = new_status()

        # ── Ticker moderne ──
        msgs_ticker = [
            "Gestion de caveaux & concessions",
            "Authentification à double facteur",
            "Réservations sécurisées en ligne",
            "Tableau de bord en temps réel",
            "Données protégées et chiffrées",
        ]
        ticker, ticker_start, _ = ticker_moderne(msgs_ticker)

        def _start():
            time.sleep(0.4)
            ticker_start()
        threading.Thread(target=_start, daemon=True).start()

        return ft.Column([
            logo_complet(40),
            ft.Container(height=12),
            ticker,
            ft.Container(height=16),
            ligne_sep(),
            ft.Container(height=20),

            ft.Container(
                content=ft.Column([
                    ft.Text("Bienvenue sur Nécropolie", size=20,
                             weight=ft.FontWeight.BOLD, color=BLANC),
                    ft.Container(height=8),
                    ft.Text(
                        "La plateforme moderne de gestion des espaces funéraires. "
                        "Simplifiez la gestion de vos caveaux, réservations "
                        "et concessions en toute sécurité.",
                        color=GRIS, size=13, text_align=ft.TextAlign.CENTER,
                    ),
                ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=0),
                padding=20, bgcolor=SURFACE,
                border_radius=16, border=border_box(BORDER),
            ),

            ft.Container(height=28),
            btn_gold("Créer mon compte",
                     lambda e: afficher(page_choix_type()),
                     icone=ft.Icons.PERSON_ADD_ALT_1),
            ft.Container(height=14),
            ligne_sep("déjà membre ?"),
            ft.Container(height=14),
            btn_outline("Se connecter",
                        lambda e: afficher(page_connexion()), width=420),
            ft.Container(height=8),
            s,
        ], spacing=8, horizontal_alignment=ft.CrossAxisAlignment.CENTER)

    # ─────────────────────────────────────
    # CHOIX TYPE DE COMPTE
    # ─────────────────────────────────────
    def page_choix_type():
        s = new_status()

        def carte_option(icone, titre, desc, couleur, dest):
            return ft.Container(
                content=ft.Row([
                    ft.Container(
                        content=ft.Icon(icone, color=couleur, size=26),
                        bgcolor=SURFACE2, border_radius=12, padding=14,
                    ),
                    ft.Container(width=14),
                    ft.Column([
                        ft.Text(titre, color=BLANC, size=14, weight=ft.FontWeight.W_600),
                        ft.Text(desc, color=GRIS, size=11),
                    ], spacing=3, expand=True),
                    ft.Icon(ft.Icons.CHEVRON_RIGHT, color=GRIS2, size=18),
                ]),
                padding=18, bgcolor=SURFACE,
                border_radius=16, border=border_box(BORDER),
                on_click=lambda e: afficher(dest()),
                ink=True,
            )

        return ft.Column([
            retour_btn(page_accueil),
            ft.Container(height=12),
            icone_logo(34),
            ft.Container(height=16),
            ft.Text("Quel type de compte ?", size=20, weight=ft.FontWeight.BOLD, color=BLANC),
            ft.Text("Choisissez selon votre profil pour commencer", color=GRIS, size=12),
            ft.Container(height=24),
            carte_option(
                ft.Icons.FAMILY_RESTROOM,
                "Compte Client",
                "Pour les citoyens, familles et particuliers",
                VERT,
                page_etape1,
            ),
            ft.Container(height=12),
            carte_option(
                ft.Icons.MANAGE_ACCOUNTS,
                "Compte Administration",
                "Pour le personnel et gestionnaires du cimetière",
                OR,
                page_choix_poste,
            ),
            ft.Container(height=8),
            s,
        ], spacing=8, horizontal_alignment=ft.CrossAxisAlignment.CENTER)

    # ─────────────────────────────────────
    # CHOIX POSTE ADMIN
    # ─────────────────────────────────────
    def page_choix_poste():
        s = new_status()
        dd = ft.Dropdown(
            label="Sélectionnez votre poste",
            width=420, bgcolor=SURFACE2, color=BLANC,
            border_color=BORDER, focused_border_color=OR,
            border_radius=12,
            label_style=ft.TextStyle(color=OR2, size=12),
            text_style=ft.TextStyle(color=BLANC, size=14),
            options=[
                ft.dropdown.Option(
                    key="admin",
                    content=ft.Row([
                        ft.Icon(ft.Icons.ADMIN_PANEL_SETTINGS, color=OR, size=16),
                        ft.Container(width=8),
                        ft.Text("Administrateur", color=BLANC, size=13),
                    ]),
                ),
                ft.dropdown.Option(
                    key="secretaire",
                    content=ft.Row([
                        ft.Icon(ft.Icons.EDIT_NOTE, color=BLEU, size=16),
                        ft.Container(width=8),
                        ft.Text("Secrétaire", color=BLANC, size=13),
                    ]),
                ),
                ft.dropdown.Option(
                    key="agent",
                    content=ft.Row([
                        ft.Icon(ft.Icons.ENGINEERING, color=VERT, size=16),
                        ft.Container(width=8),
                        ft.Text("Agent de terrain", color=BLANC, size=13),
                    ]),
                ),
            ],
        )

        def suivant(e):
            if not dd.value:
                set_status("Veuillez sélectionner votre poste")
                return
            if dd.value == "admin":
                store["est_admin"] = True
                afficher(page_etape1(est_admin=True))
            else:
                afficher(page_refus())

        return ft.Column([
            retour_btn(page_choix_type),
            ft.Container(height=12),
            ft.Icon(ft.Icons.MANAGE_ACCOUNTS, color=OR, size=44),
            ft.Container(height=12),
            ft.Text("Votre poste", size=20, weight=ft.FontWeight.BOLD, color=BLANC),
            ft.Container(height=20),
            dd,
            ft.Container(height=14),
            bloc_conseil(
                "Créez d'abord le compte Administrateur pour configurer votre cimetière, "
                "puis enregistrez les autres postes depuis le tableau de bord.",
                icone=ft.Icons.LIGHTBULB_OUTLINE,
            ),
            ft.Container(height=8),
            s,
            ft.Container(height=12),
            btn_gold("Continuer →", suivant, icone=ft.Icons.ARROW_FORWARD),
        ], spacing=8, horizontal_alignment=ft.CrossAxisAlignment.CENTER)

    # ─────────────────────────────────────
    # PAGE REFUS
    # ─────────────────────────────────────
    def page_refus():
        return ft.Column([
            retour_btn(page_choix_poste),
            ft.Container(height=30),
            ft.Container(
                content=ft.Icon(ft.Icons.NO_ACCOUNTS, color=OR, size=56),
                bgcolor=SURFACE2, border_radius=50, padding=18,
            ),
            ft.Container(height=20),
            ft.Text("Inscription restreinte", size=20, weight=ft.FontWeight.BOLD, color=BLANC),
            ft.Container(height=16),
            ft.Container(
                content=ft.Column([
                    ft.Text("Accès réservé à l'administration", color=OR2, size=13,
                             weight=ft.FontWeight.W_500),
                    ft.Container(height=8),
                    ft.Text(
                        "Les secrétaires et agents de terrain sont enregistrés "
                        "directement par l'Administrateur du système.\n\n"
                        "Si votre compte a déjà été créé, connectez-vous "
                        "avec les identifiants fournis par votre administrateur.",
                        color=GRIS, size=13, text_align=ft.TextAlign.CENTER,
                    ),
                ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=0),
                padding=20, bgcolor=SURFACE,
                border_radius=16, border=border_box(BORDER),
            ),
            ft.Container(height=24),
            btn_gold("Se connecter", lambda e: afficher(page_connexion()), icone=ft.Icons.LOGIN),
            ft.Container(height=10),
            btn_outline("← Retour à l'accueil", lambda e: afficher(page_accueil()), width=420),
        ], spacing=8, horizontal_alignment=ft.CrossAxisAlignment.CENTER)

    # ─────────────────────────────────────
    # ÉTAPE 1 — NOM / PRÉNOM
    # ─────────────────────────────────────
    def page_etape1(est_admin=False):
        s = new_status()
        f_nom    = champ("Nom de famille *", hint="Entrez votre nom")
        f_prenom = champ("Prénom(s) *", hint="Entrez votre prénom")

        def suivant(e):
            if not f_nom.value.strip() or not f_prenom.value.strip():
                set_status("Veuillez renseigner vos nom et prénom")
                return
            store["nom"]       = f_nom.value.strip()
            store["prenom"]    = f_prenom.value.strip()
            store["est_admin"] = est_admin
            afficher(page_etape2())

        return ft.Column([
            retour_btn(page_choix_type),
            ft.Container(height=10),
            badge_etape(1),
            ft.Container(height=6),
            barre_prog(1),
            ft.Container(height=20),
            ft.Text("Votre identité", size=20, weight=ft.FontWeight.BOLD, color=BLANC),
            ft.Text("Étape 1 · Noms et prénoms", color=GRIS, size=12),
            ft.Container(height=22),
            f_nom,
            f_prenom,
            ft.Container(height=8),
            s,
            ft.Container(height=14),
            btn_gold("Suivant →", suivant, icone=ft.Icons.ARROW_FORWARD),
        ], spacing=8, horizontal_alignment=ft.CrossAxisAlignment.CENTER)

    # ─────────────────────────────────────
    # ÉTAPE 2 — DATE & GENRE
    # ─────────────────────────────────────
    def page_etape2():
        s = new_status()

        mois_noms = ["Janvier","Février","Mars","Avril","Mai","Juin",
                     "Juillet","Août","Septembre","Octobre","Novembre","Décembre"]

        style_dd = {
            "bgcolor": SURFACE2, "color": BLANC,
            "border_color": BORDER, "focused_border_color": OR,
            "border_radius": 12,
            "label_style": ft.TextStyle(color=OR2, size=11),
            "text_style": ft.TextStyle(color=BLANC, size=14),
        }

        def opt(key, label):
            return ft.dropdown.Option(
                key=key,
                content=ft.Text(label, color=BLANC, size=13),
            )

        f_jour = ft.Dropdown(label="Jour", width=120,
            options=[opt(str(i), str(i)) for i in range(1, 32)], **style_dd)
        f_mois = ft.Dropdown(label="Mois", width=160,
            options=[opt(str(i+1), m) for i, m in enumerate(mois_noms)], **style_dd)
        f_an   = ft.Dropdown(label="Année", width=120,
            options=[opt(str(i), str(i)) for i in range(1940, 2009)], **style_dd)
        f_genre = ft.Dropdown(label="Genre", width=420,
            options=[
                opt("homme", "Homme"),
                opt("femme",  "Femme"),
                opt("autre",  "Préfère ne pas préciser"),
            ], **style_dd)

        def suivant(e):
            if not f_jour.value or not f_mois.value or not f_an.value:
                set_status("Date de naissance incomplète")
                return
            from datetime import date
            try:
                naissance = date(int(f_an.value), int(f_mois.value), int(f_jour.value))
            except ValueError:
                set_status("Date invalide")
                return
            age = (date.today() - naissance).days // 365
            if age < 18:
                set_status(f"Âge insuffisant ({age} ans) — 18 ans minimum requis")
                return
            store["date_naissance"] = f"{f_an.value}-{f_mois.value.zfill(2)}-{f_jour.value.zfill(2)}"
            store["genre"]          = f_genre.value or "autre"
            afficher(page_etape3())

        return ft.Column([
            retour_btn(page_etape1),
            ft.Container(height=10),
            badge_etape(2),
            ft.Container(height=6),
            barre_prog(2),
            ft.Container(height=20),
            ft.Text("Date de naissance & genre", size=20, weight=ft.FontWeight.BOLD, color=BLANC),
            ft.Text("Étape 2 · Informations personnelles", color=GRIS, size=12),
            ft.Container(height=22),
            ft.Row([f_jour, f_mois, f_an], spacing=10),
            ft.Container(height=12),
            f_genre,
            ft.Container(height=12),
            bloc_conseil(
                "Âge minimum requis : 18 ans. Vos données personnelles sont protégées "
                "et ne seront jamais partagées avec des tiers.",
                icone=ft.Icons.VERIFIED_USER,
                couleur=VERT,
            ),
            ft.Container(height=8),
            s,
            ft.Container(height=14),
            btn_gold("Suivant →", suivant, icone=ft.Icons.ARROW_FORWARD),
        ], spacing=8, horizontal_alignment=ft.CrossAxisAlignment.CENTER)

    # ─────────────────────────────────────
    # ÉTAPE 3 — EMAIL / MOT DE PASSE
    # ─────────────────────────────────────
    def page_etape3():
        s = new_status()
        f_email = champ("Adresse email *", hint="exemple@gmail.com")
        f_mdp   = champ("Mot de passe *", hint="Minimum 6 caractères", password=True)
        f_mdp2  = champ("Confirmer le mot de passe *", hint="Répétez votre mot de passe", password=True)

        def suivant(e):
            if not f_email.value or not f_mdp.value or not f_mdp2.value:
                set_status("Tous les champs sont obligatoires")
                return
            if "@" not in f_email.value or "." not in f_email.value:
                set_status("Adresse email invalide")
                return
            if len(f_mdp.value) < 6:
                set_status("Mot de passe trop court — 6 caractères minimum")
                return
            if f_mdp.value != f_mdp2.value:
                set_status("Les mots de passe ne correspondent pas")
                return
            store["email"]    = f_email.value.lower().strip()
            store["password"] = f_mdp.value
            afficher(page_etape4())

        return ft.Column([
            retour_btn(page_etape2),
            ft.Container(height=10),
            badge_etape(3),
            ft.Container(height=6),
            barre_prog(3),
            ft.Container(height=20),
            ft.Text("Vos identifiants", size=20, weight=ft.FontWeight.BOLD, color=BLANC),
            ft.Text("Étape 3 · Email et mot de passe", color=GRIS, size=12),
            ft.Container(height=8),
            bloc_conseil(
                "Votre adresse email servira à la connexion et à la réception "
                "du code MFA à chaque authentification.",
                icone=ft.Icons.EMAIL_OUTLINED,
            ),
            ft.Container(height=14),
            f_email,
            f_mdp,
            f_mdp2,
            ft.Container(height=8),
            s,
            ft.Container(height=14),
            btn_gold("Suivant →", suivant, icone=ft.Icons.ARROW_FORWARD),
        ], spacing=8, horizontal_alignment=ft.CrossAxisAlignment.CENTER)

    # ─────────────────────────────────────
    # ÉTAPE 4 — TÉLÉPHONE
    # ─────────────────────────────────────
    def page_etape4():
        s = new_status()
        f_tel = champ("Numéro de téléphone", hint="+242 06 XXX XXXX")
        f_ville = champ("Ville de résidence", hint="Ex : Pointe-Noire, Brazzaville")

        def gen_username():
            base    = store.get("prenom","user").lower().replace(" ","")[:6]
            suffixe = ''.join(random.choices(string.digits, k=4))
            store["username"] = f"{base}{suffixe}"

        def suivant(e):
            store["telephone"] = f_tel.value.strip() if f_tel.value else ""
            store["ville"] = f_ville.value.strip() if f_ville.value else ""
            gen_username()
            afficher(page_etape5())

        def ignorer(e):
            store["telephone"] = ""
            store["ville"]     = ""
            gen_username()
            afficher(page_etape5())

        return ft.Column([
            retour_btn(page_etape3),
            ft.Container(height=10),
            badge_etape(4),
            ft.Container(height=6),
            barre_prog(4),
            ft.Container(height=20),
            ft.Text("Vos coordonnées", size=20, weight=ft.FontWeight.BOLD, color=BLANC),
            ft.Text("Étape 4 · Optionnel — vous pouvez ignorer", color=GRIS, size=12),
            ft.Container(height=22),
            f_tel,
            f_ville,
            ft.Container(height=12),
            bloc_conseil(
                "Ces informations restent confidentielles. La ville permet de vous "
                "rattacher à la juridiction funéraire la plus proche.",
                icone=ft.Icons.LOCK_OUTLINE,
            ),
            ft.Container(height=8),
            s,
            ft.Container(height=14),
            ft.Row([
                btn_outline("Ignorer", ignorer, width=190),
                ft.Container(width=12),
                btn_gold("Suivant →", suivant, width=206, icone=ft.Icons.ARROW_FORWARD),
            ]),
        ], spacing=8, horizontal_alignment=ft.CrossAxisAlignment.CENTER)

    # ─────────────────────────────────────
    # ÉTAPE 5 — USERNAME & RÉCAP
    # ─────────────────────────────────────
    def page_etape5():
        s = new_status()
        f_user = ft.TextField(
            label="Nom d'utilisateur *", value=store.get("username",""),
            width=420, bgcolor=SURFACE2, color=BLANC,
            border_color=BORDER, focused_border_color=OR,
            border_radius=12,
            label_style=ft.TextStyle(color=OR2, size=12, weight=ft.FontWeight.W_500),
            text_style=ft.TextStyle(color=BLANC, size=14),
            cursor_color=OR,
            content_padding=16,
        )

        def suivant(e):
            if not f_user.value or len(f_user.value) < 4:
                set_status("Le nom d'utilisateur doit contenir au moins 4 caractères")
                page.update()
                return
            store["username"] = f_user.value.strip()
            if store.get("est_admin") == False:
                afficher(page_etape6())  # Page licence directement
            else:
                afficher(page_cimetiere())
            page.update()

        def info_row(icone, valeur):
            return ft.Row([
                ft.Icon(icone, color=OR, size=16),
                ft.Container(width=10),
                ft.Text(valeur, color=BLANC, size=13),
            ], spacing=0)
            

        return ft.Column([
            retour_btn(page_etape4),
            ft.Container(height=10),
            badge_etape(5),
            ft.Container(height=6),
            barre_prog(5),
            ft.Container(height=20),
            ft.Text("Récapitulatif & username", size=20, weight=ft.FontWeight.BOLD, color=BLANC),
            ft.Text("Étape 5 · Vérifiez vos informations", color=GRIS, size=12),
            ft.Container(height=18),
            ft.Container(
                content=ft.Column([
                    info_row(ft.Icons.PERSON, f"{store.get('nom','')} {store.get('prenom','')}"),
                    ft.Container(height=2, bgcolor=BORDER),
                    info_row(ft.Icons.EMAIL_OUTLINED, store.get('email','')),
                    ft.Container(height=2, bgcolor=BORDER),
                    info_row(ft.Icons.PHONE, store.get('telephone','') or 'Non renseigné'),
                    ft.Container(height=2, bgcolor=BORDER),
                    info_row(ft.Icons.LOCATION_CITY, store.get('ville','') or 'Non renseignée'),  # ← AJOUTE CETTE LIGNE
                    ft.Container(height=2, bgcolor=BORDER),
                    info_row(ft.Icons.CAKE, f"Né(e) le {store.get('date_naissance','')}"),
                ], spacing=10),
                padding=18, bgcolor=SURFACE,
                border_radius=14, border=border_box(BORDER),
            ),
            ft.Container(height=16),
            ft.Text(
                "Nécropolie vous a généré un nom d'utilisateur — modifiable ci-dessous :",
                color=GRIS, size=12,
            ),
            ft.Container(height=8),
            f_user,
            ft.Container(height=8),
            s,
            ft.Container(height=14),
            btn_gold("Suivant →", suivant, icone=ft.Icons.ARROW_FORWARD),
        ], spacing=8, horizontal_alignment=ft.CrossAxisAlignment.CENTER)

        # ─────────────────────────────────────
    # ÉTAPE 6 — CRÉATION CIMETIÈRE (Admin uniquement)
    # ─────────────────────────────────────
    def page_cimetiere():
        s = new_status()
        
        f_nom        = champ("Nom du cimetière", hint="Ex : Cimetière Municipal de Vindoulou")
        f_quartier   = champ("Quartier", hint="Ex : Vindoulou, Ouenzé, Makélékélé")
        f_ville      = champ("Ville", hint="Ex : Pointe-Noire, Brazzaville")
        f_superficie = champ("Superficie totale (m²)", hint="Ex : 5000")
        f_mdp        = champ("Mot de passe d'accès", hint="Minimum 4 caractères", password=True)
        
        # Coordonnées GPS
        f_lat = champ("Latitude (centre)", width=200, hint="Ex : -4.7833")
        f_lng = champ("Longitude (centre)", width=200, hint="Ex : 11.8667")
        
        # Limites du rectangle
        f_limite_nord  = champ("Limite Nord (latitude)", width=200, hint="Ex : -4.7815")
        f_limite_sud   = champ("Limite Sud (latitude)", width=200, hint="Ex : -4.7851")
        f_limite_est   = champ("Limite Est (longitude)", width=200, hint="Ex : 11.8685")
        f_limite_ouest = champ("Limite Ouest (longitude)", width=200, hint="Ex : 11.8649")

                # Bouton pour ouvrir la carte interactive
        def ouvrir_carte_assistance(e):
            import webbrowser
            import os
            
            # Chemin absolu vers le fichier HTML
            chemin = r"C:\Users\hp\Downloads\cimetiere_fix_carte_exports\Cimetiere\carte_selection.html"
            
            if os.path.exists(chemin):
                webbrowser.open(f"file:///{chemin}")
                set_status("Carte ouverte ! Dessinez votre cimetière.", VERT)
            else:
                set_status(f"Erreur : fichier introuvable à {chemin}", ROUGE)
        btn_carte = ft.Container(
            content=ft.Row([
                ft.Icon(ft.Icons.MAP, color=OR, size=18),
                ft.Text("Ouvrir la carte interactive pour délimiter votre cimetière", color=BLANC, size=12),
            ], alignment=ft.MainAxisAlignment.CENTER),
            padding=12,
            bgcolor=SURFACE,
            border_radius=8,
            border=border_box(OR),
            on_click=ouvrir_carte_assistance,
            ink=True,
        )

        def suivant(e):
            if not f_nom.value or not f_mdp.value:
                set_status("Nom du cimetière et mot de passe obligatoires")
                return
            if len(f_mdp.value) < 4:
                set_status("Mot de passe trop court (4 caractères minimum)")
                return
            
            # Sauvegarder les données dans le store
            store["cimetiere_mode"] = "creer"
            store["nom_cimetiere"] = f_nom.value.strip()
            store["mot_de_passe_cimetiere"] = f_mdp.value
            store["quartier"] = f_quartier.value.strip() if f_quartier.value else ""
            store["ville"] = f_ville.value.strip() if f_ville.value else ""
            store["pays"] = "République du Congo"
            store["superficie_totale"] = float(f_superficie.value) if f_superficie.value else 0
            
            # Coordonnées GPS
            try:
                store["latitude"] = float(f_lat.value) if f_lat.value else None
                store["longitude"] = float(f_lng.value) if f_lng.value else None
                store["limite_nord"] = float(f_limite_nord.value) if f_limite_nord.value else None
                store["limite_sud"] = float(f_limite_sud.value) if f_limite_sud.value else None
                store["limite_est"] = float(f_limite_est.value) if f_limite_est.value else None
                store["limite_ouest"] = float(f_limite_ouest.value) if f_limite_ouest.value else None
            except ValueError:
                store["latitude"] = store["longitude"] = None
                store["limite_nord"] = store["limite_sud"] = None
                store["limite_est"] = store["limite_ouest"] = None
            
            afficher(page_etape6())

        return ft.Column([
            retour_btn(page_etape5),
            ft.Container(height=10),
            badge_etape(6),
            ft.Container(height=6),
            barre_prog(6),
            ft.Container(height=20),
            ft.Text("Créer votre cimetière", size=20, weight=ft.FontWeight.BOLD, color=BLANC),
            ft.Text("Étape 6 · Configuration de l'espace funéraire", color=GRIS, size=12),
            ft.Container(height=22),
            f_nom,
            f_quartier,
            ft.Row([f_ville, f_superficie], spacing=10),
            ft.Container(height=14),
            ft.Text("Coordonnées GPS et délimitation", color=OR, size=13, weight=ft.FontWeight.W_500),
            ft.Text("Utilisez https://www.latlong.net/ pour trouver les coordonnées exactes", color=GRIS, size=11),
            ft.Container(height=10),
            ft.Row([f_lat, f_lng], spacing=10),
            ft.Row([f_limite_nord, f_limite_sud], spacing=10),
            ft.Row([f_limite_est, f_limite_ouest], spacing=10),
            ft.Container(height=10),
            btn_carte,  # ← AJOUTE CETTE LIGNE
            ft.Container(height=10),
            f_mdp,
            ft.Container(height=12),
            bloc_conseil(
                "Les 4 limites (Nord, Sud, Est, Ouest) définissent le rectangle de délimitation "
                "qui sera affiché sur la carte. Assurez-vous que le rectangle ne couvre que "
                "votre cimetière, pas les routes ou bâtiments voisins.",
                icone=ft.Icons.MAP,
            ),
            ft.Container(height=8),
            s,
            ft.Container(height=14),
            btn_gold("Continuer →", suivant, icone=ft.Icons.ARROW_FORWARD),
        ], spacing=8, horizontal_alignment=ft.CrossAxisAlignment.CENTER)

    # ─────────────────────────────────────
    # ÉTAPE 7 — LICENCE / RÈGLEMENT
    # ─────────────────────────────────────
    def page_etape6():
        s = new_status()
        accept = ft.Checkbox(
            label="J'ai lu et j'accepte les Conditions Générales d'Utilisation",
            value=False, active_color=OR,
            check_color=NOIR,
            label_style=ft.TextStyle(color=BLANC, size=13),
        )
        loading = ft.ProgressRing(color=OR, width=28, height=28, visible=False)

        licence_texte = """CONTRAT DE LICENCE D'UTILISATION FINALE — NECROPOLIS
Version 1.0 — En vigueur à compter du 1er juin 2026

ARTICLE 1 — OBJET DU CONTRAT
Le présent Contrat de Licence d'Utilisation Finale (« CLUF ») est conclu entre vous (ci-après « l'Utilisateur ») et NECROPOLIS (ci-après « l'Éditeur »). Il régit l'accès et l'utilisation de la plateforme de gestion funéraire NECROPOLIS.

ARTICLE 2 — ACCEPTATION DES CONDITIONS
En créant un compte, vous reconnaissez avoir lu, compris et accepté l'intégralité des présentes conditions. Si vous n'acceptez pas ces conditions, vous ne devez pas utiliser le Service.

ARTICLE 3 — UTILISATION AUTORISÉE
L'Utilisateur est autorisé à accéder au Service uniquement dans le cadre de ses attributions légitimes (gestion de caveau, réservation, consultation). Toute utilisation frauduleuse, abusive ou contraire à l'ordre public est strictement interdite.

ARTICLE 4 — PROTECTION DES DONNÉES PERSONNELLES
Conformément aux lois en vigueur sur la protection des données, NECROPOLIS s'engage à :
• Ne collecter que les données strictement nécessaires au fonctionnement du Service.
• Ne jamais céder, vendre ou partager vos données à des tiers sans votre consentement explicite.
• Garantir la sécurité de vos informations par chiffrement et authentification renforcée (MFA).
• Vous permettre d'accéder, modifier ou supprimer vos données à tout moment.
• Vos données personnelles sont stockées de manière sécurisée et ne seront transmises à l'administration d'un cimetière que lors de la validation d'une demande de réservation effective. En tant que client, vous conservez le contrôle total de vos informations.

ARTICLE 5 — RESPONSABILITÉ DE L'UTILISATEUR
L'Utilisateur s'engage à :
• Fournir des informations exactes et sincères lors de son inscription.
• Maintenir la confidentialité de ses identifiants et codes d'accès.
• Signaler immédiatement toute utilisation non autorisée de son compte.
• Respecter les lois et réglementations relatives aux espaces funéraires.

ARTICLE 6 — PROPRIÉTÉ INTELLECTUELLE
L'ensemble des éléments composant la plateforme NECROPOLIS (code, design, base de données, algorithmes) est la propriété exclusive de l'Éditeur et est protégé par les lois sur la propriété intellectuelle.

ARTICLE 7 — SUSPENSION ET RÉSILIATION
NECROPOLIS se réserve le droit de suspendre ou de résilier votre accès en cas de violation des présentes conditions, sans préavis ni indemnité.

ARTICLE 8 — LIMITATION DE RESPONSABILITÉ
NECROPOLIS ne saurait être tenu responsable des dommages indirects résultant de l'utilisation ou de l'impossibilité d'utiliser le Service.

ARTICLE 9 — DROIT APPLICABLE
Le présent CLUF est régi par le droit en vigueur en République du Congo. Tout litige sera soumis aux tribunaux compétents de Pointe-Noire.

© 2026 NECROPOLIS — Tous droits réservés"""

        def terminer(e):
            if not accept.value:
                set_status("Vous devez accepter les CGU pour créer votre compte")
                return
            loading.visible = True
            s.visible = False
            page.update()
            try:
                data = {
                    "username": store["username"],
                    "email": store["email"],
                    "nom": store.get("nom", ""),        # <-- AJOUTE
                    "prenom": store.get("prenom", ""),  # <-- AJOUTE
                    "password": store["password"],
                    "role": "admin" if store.get("est_admin") else "client",
                    "mode": store.get("cimetiere_mode"),
                    "nom_cimetiere": store.get("nom_cimetiere", ""),
                    "mot_de_passe_cimetiere": store.get("mot_de_passe_cimetiere", ""),
                    "ville": store.get("ville", ""),
                    "quartier": store.get("quartier", ""),  # ← AJOUTE CETTE LIGNE
                    "pays": store.get("pays", "République du Congo"),
                    "latitude": store.get("latitude"),
                    "longitude": store.get("longitude"),
                    "limite_nord": store.get("limite_nord"),
                    "limite_sud": store.get("limite_sud"),
                    "limite_est": store.get("limite_est"),
                    "limite_ouest": store.get("limite_ouest"),
                    "superficie_totale": store.get("superficie_totale", 0),
                    "tombeau_longueur": store.get("tombeau_longueur", 2.5),
                    "tombeau_largeur": store.get("tombeau_largeur", 1.2),
}
                r = requests.post(f"{API}/auth/register", json=data)
                loading.visible = False
                if r.status_code == 200:
                    afficher(page_succes())
                else:
                    d = r.json()
                    set_status(d.get("error", "Erreur lors de l'inscription"))
            except Exception as ex:
                loading.visible = False
                set_status(f"Connexion impossible : {ex}")
            page.update()

        return ft.Column([
            retour_btn(page_etape5),
            ft.Container(height=10),
            badge_etape(7),
            ft.Container(height=6),
            barre_prog(7),
            ft.Container(height=20),
            ft.Text("Conditions d'utilisation", size=20, weight=ft.FontWeight.BOLD, color=BLANC),
            ft.Text("Étape 7 · Lecture et acceptation requises", color=GRIS, size=12),
            ft.Container(height=16),
            ft.Container(
                content=ft.Column([
                    ft.Row([
                        ft.Icon(ft.Icons.GAVEL, color=OR, size=16),
                        ft.Container(width=8),
                        ft.Text("LICENCE D'UTILISATION NECROPOLIS", color=OR2, size=11,
                                 weight=ft.FontWeight.BOLD),
                    ]),
                    ft.Container(height=8),
                    ft.ListView(
                        controls=[ft.Text(licence_texte, color=GRIS, size=10, selectable=True)],
                        height=200, spacing=0, padding=0, auto_scroll=False,
                    ),
                ]),
                padding=16, bgcolor=SURFACE,
                border_radius=14, border=border_box(BORDER),
                height=260,
            ),
            ft.Container(height=16),
            ft.Container(
                content=accept,
                padding=14, bgcolor=SURFACE2,
                border_radius=12, border=border_box(OR_DIM),
            ),
            ft.Container(height=8),
            s,
            loading,
            ft.Container(height=14),
            btn_gold("Créer mon compte", terminer, icone=ft.Icons.CHECK_CIRCLE),
        ], spacing=8, horizontal_alignment=ft.CrossAxisAlignment.CENTER)

    # ─────────────────────────────────────
    # PAGE SUCCÈS
    # ─────────────────────────────────────
    def page_succes():
        prenom = store.get("prenom", "")
        role   = "Administrateur" if store.get("est_admin") else "Client"
        return ft.Column([
            ft.Container(height=20),
            ft.Container(
                content=ft.Icon(ft.Icons.CHECK_CIRCLE, color=VERT, size=60),
                bgcolor=SURFACE2, border_radius=60, padding=20,
                shadow=ft.BoxShadow(spread_radius=0, blur_radius=30,
                                     color="#5000e676", offset=ft.Offset(0,0)),
            ),
            ft.Container(height=20),
            ft.Text(f"Bienvenue, {prenom} !", size=24, weight=ft.FontWeight.BOLD, color=BLANC),
            ft.Text("Votre compte a été créé avec succès", color=GRIS, size=13),
            ft.Container(height=20),
            ft.Container(
                content=ft.Column([
                    ft.Row([ft.Icon(ft.Icons.ALTERNATE_EMAIL, color=OR, size=16),
                            ft.Container(width=10),
                            ft.Text(f"@{store.get('username','')}", color=BLANC, size=13,
                                     weight=ft.FontWeight.W_500)], spacing=0),
                    ft.Container(height=2, bgcolor=BORDER),
                    ft.Row([ft.Icon(ft.Icons.EMAIL_OUTLINED, color=OR, size=16),
                            ft.Container(width=10),
                            ft.Text(store.get('email',''), color=BLANC, size=13)], spacing=0),
                    ft.Container(height=2, bgcolor=BORDER),
                    ft.Row([ft.Icon(ft.Icons.BADGE, color=OR, size=16),
                            ft.Container(width=10),
                            ft.Text(role, color=BLANC, size=13)], spacing=0),
                ], spacing=12),
                padding=18, bgcolor=SURFACE,
                border_radius=14, border=border_box(BORDER),
            ),
            ft.Container(height=24),
            btn_gold("Se connecter maintenant", lambda e: afficher(page_connexion()),
                     icone=ft.Icons.LOGIN),
            ft.Container(height=10),
            btn_outline("← Retour à l'accueil", lambda e: afficher(page_accueil()), width=420),
        ], spacing=8, horizontal_alignment=ft.CrossAxisAlignment.CENTER)

    # ─────────────────────────────────────
    # PAGE CONNEXION
    # ─────────────────────────────────────
    def page_connexion():
        s       = new_status()
        f_login = champ("Email ou nom d'utilisateur", hint="email ou @username")
        f_mdp   = champ("Mot de passe", password=True)
        f_code  = champ("Code MFA — 6 chiffres", hint="Code reçu par email")
        f_code.visible = False
        loading = ft.ProgressRing(color=OR, width=28, height=28, visible=False)
        b_continuer = ft.Container()
        b_verifier  = ft.Container()

        def envoyer(e):
            if not f_login.value or not f_mdp.value:
                set_status("Veuillez remplir tous les champs")
                return
            loading.visible = True
            s.visible = False
            page.update()
            try:
                r = requests.post(f"{API}/auth/login",
                                  json={"username": f_login.value, "password": f_mdp.value},
                                  timeout=10)
                d = r.json()
                loading.visible = False
                if r.status_code == 200:
                    store["email"] = d["email"]
                    f_code.hint_text = f"Indice DEV : {d.get('debug_code','???')}"
                    f_login.visible = False
                    f_mdp.visible   = False
                    b_continuer.content.visible = False
                    f_code.visible  = True
                    b_verifier.content.visible  = True
                    s.content = ft.Row([
                        ft.Icon(ft.Icons.MARK_EMAIL_READ, color=VERT, size=16),
                        ft.Text(f"Code envoyé à {d['email']}", color=VERT, size=12),
                    ], spacing=8)
                    s.bgcolor = SURFACE2
                    s.border_radius = 10
                    s.padding = 12
                    s.visible = True
                else:
                    set_status(d.get("error","Identifiants incorrects"))
            except Exception as ex:
                loading.visible = False
                set_status(f"Erreur : {ex}")
            page.update()

        def verifier(e):
            if not f_code.value or len(f_code.value.strip()) != 6:
                set_status("Le code doit contenir exactement 6 chiffres")
                return
            loading.visible = True
            page.update()
            try:
                r = requests.post(f"{API}/auth/verify",
                                  json={"email": store.get("email"), "code": f_code.value.strip()},
                                  timeout=10)
                loading.visible = False
                if r.status_code == 200:
                    d = r.json()
                    s.content = ft.Row([
                        ft.Icon(ft.Icons.VERIFIED, color=VERT, size=16),
                        ft.Text(f"Connexion réussie — Rôle : {d.get('role','')}", color=VERT, size=12),
                    ], spacing=8)
                    s.bgcolor = SURFACE2
                    s.border_radius = 10
                    s.padding = 12
                    s.visible = True
                    page.update()
                    base_dir  = os.path.dirname(os.path.abspath(__file__))
                    main_path = os.path.join(base_dir, "main.py")
                    subprocess.Popen([sys.executable, main_path, d.get("token", ""), d.get("user", ""), d.get("role", "client")])
                    time.sleep(1)
                    page.window.close()
                else:
                    set_status("Code MFA invalide — vérifiez votre email")
            except Exception as ex:
                loading.visible = False
                set_status(f"Erreur : {ex}")
            page.update()

        b_continuer.content = btn_gold("Continuer", envoyer, icone=ft.Icons.SEND)
        b_verifier.content  = btn_gold("Vérifier le code MFA", verifier, icone=ft.Icons.VERIFIED)
        b_verifier.content.visible = False

        return ft.Column([
            retour_btn(page_accueil),
            ft.Container(height=14),
            icone_logo(36),
            ft.Container(height=14),
            ft.Text("Connexion", size=22, weight=ft.FontWeight.BOLD, color=BLANC),
            ft.Text("Accédez à votre tableau de bord sécurisé", color=GRIS, size=12),
            ft.Container(height=22),
            f_login,
            f_mdp,
            f_code,
            ft.Container(height=8),
            s,
            loading,
            ft.Container(height=12),
            b_continuer,
            b_verifier,
            ft.Container(height=16),
            ligne_sep("pas encore de compte ?"),
            ft.Container(height=12),
            btn_outline("Créer un compte", lambda e: afficher(page_choix_type()), width=420),
        ], spacing=8, horizontal_alignment=ft.CrossAxisAlignment.CENTER)

    # ─────────────────────────────────────
    # LANCEMENT
    # ─────────────────────────────────────
    page.add(
        ft.Container(
            content=conteneur,
            expand=True,
            bgcolor=NOIR,
        )
    )
    afficher(page_accueil())

ft.app(target=main)