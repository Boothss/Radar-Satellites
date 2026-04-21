"""
SENTINELLE ISS — Script de surveillance autonome 24/7
Tourne toutes les heures via GitHub Actions.
Envoie un email si l'ISS passe au-dessus de Calais dans les prochaines 12h.
"""

import smtplib
import os
import requests
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from skyfield.api import load, wgs84
from datetime import datetime, timedelta, timezone

# ==========================================
# ⚙️  CONFIG (via secrets GitHub)
# ==========================================
GMAIL_USER     = os.environ.get("GMAIL_USER",     "alexbailly82@gmail.com")
GMAIL_PASSWORD = os.environ.get("GMAIL_PASSWORD", "")
DESTINATAIRE   = os.environ.get("DESTINATAIRE",   "alexbailly82@gmail.com")

# Position de Dunkerque / Calais
MA_LATITUDE  = 50.9555
MA_LONGITUDE = 1.8842
MA_VILLE     = "Calais / Dunkerque"

# Seuil d'altitude minimum pour un beau passage (degrés)
ALTITUDE_MIN = 30.0

# Fenêtre de recherche (heures)
FENETRE_HEURES = 12

# Fichier mémoire
FICHIER_MEMOIRE = "iss_db.txt"

# ==========================================
# 💾  MÉMOIRE PERSISTANTE
# ==========================================
def charger_memoire():
    if not os.path.exists(FICHIER_MEMOIRE):
        return set()
    with open(FICHIER_MEMOIRE, "r") as f:
        ids = set(line.strip() for line in f if line.strip())
    print(f"[MÉMOIRE] {len(ids)} passage(s) déjà notifié(s)")
    return ids

def sauvegarder_passage(passage_id):
    with open(FICHIER_MEMOIRE, "a") as f:
        f.write(f"{passage_id}\n")

# ==========================================
# 🛰️  CALCUL DES PASSAGES ISS
# ==========================================
def trouver_passages():
    """Calcule tous les passages ISS visibles dans les prochaines X heures."""
    print("[ISS] Téléchargement des données TLE depuis CelesTrak...")

    try:
        ts  = load.timescale()
        t0  = ts.now()
        t1  = ts.from_datetime(t0.utc_datetime() + timedelta(hours=FENETRE_HEURES))

        stations_url = "https://celestrak.org/NORAD/elements/gp.php?GROUP=stations&FORMAT=tle"
        satellites   = load.tle_file(stations_url, reload=True)
        by_name      = {sat.name: sat for sat in satellites}

        iss = by_name.get("ISS (ZARYA)")
        if not iss:
            print("[ISS] ❌ ISS non trouvée dans le fichier TLE")
            return []

        ma_position = wgs84.latlon(MA_LATITUDE, MA_LONGITUDE)
        t, events   = iss.find_events(ma_position, t0, t1, altitude_degrees=ALTITUDE_MIN)

        passages = []
        passage_courant = {}

        for time_ev, event in zip(t, events):
            heure_utc   = time_ev.utc_datetime()
            heure_locale = heure_utc.astimezone()

            if event == 0:  # Lever
                passage_courant = {"lever": heure_locale}
            elif event == 1:  # Culmination (point le plus haut)
                # Calcul de l'altitude maximale
                difference = iss - ma_position
                topocentric = difference.at(time_ev)
                alt, az, dist = topocentric.altaz()

                passage_courant["culmination"] = heure_locale
                passage_courant["altitude_max"] = round(alt.degrees, 1)
                passage_courant["azimut"]       = round(az.degrees, 1)
                passage_courant["distance_km"]  = round(dist.km, 0)

                # Direction cardinale
                az_deg = az.degrees
                if az_deg < 22.5 or az_deg >= 337.5:   direction = "Nord"
                elif az_deg < 67.5:                      direction = "Nord-Est"
                elif az_deg < 112.5:                     direction = "Est"
                elif az_deg < 157.5:                     direction = "Sud-Est"
                elif az_deg < 202.5:                     direction = "Sud"
                elif az_deg < 247.5:                     direction = "Sud-Ouest"
                elif az_deg < 292.5:                     direction = "Ouest"
                else:                                    direction = "Nord-Ouest"
                passage_courant["direction"] = direction

            elif event == 2:  # Coucher
                passage_courant["coucher"] = heure_locale
                if "culmination" in passage_courant:
                    passages.append(dict(passage_courant))
                passage_courant = {}

        print(f"[ISS] {len(passages)} passage(s) trouvé(s) dans les {FENETRE_HEURES}h à venir")
        return passages

    except Exception as e:
        print(f"[ISS] ❌ Erreur calcul : {e}")
        return []

# ==========================================
# 🌙  CALCUL QUALITÉ D'OBSERVATION
# ==========================================
def evaluer_qualite(altitude_max):
    """Évalue la qualité du passage selon l'altitude maximale."""
    if altitude_max >= 70:
        return "⭐⭐⭐ EXCELLENT", "#22C55E"
    elif altitude_max >= 50:
        return "⭐⭐ TRÈS BON", "#3B82F6"
    elif altitude_max >= 30:
        return "⭐ BON", "#F59E0B"
    else:
        return "FAIBLE", "#6B7280"

# ==========================================
# 📧  EMAIL HTML PRO
# ==========================================
def envoyer_email(passages_nouveaux):
    """Envoie un email HTML pour les nouveaux passages ISS."""
    if not passages_nouveaux:
        return False

    msg = MIMEMultipart("alternative")

    p = passages_nouveaux[0]
    heure_str = p["culmination"].strftime("%H:%M")
    msg["Subject"] = f"🛰️ ISS visible à {heure_str} au-dessus de {MA_VILLE}"
    msg["From"]    = GMAIL_USER
    msg["To"]      = DESTINATAIRE

    # ── TEXTE PLAIN ──
    plain_lines = [
        "SENTINELLE ISS · Tracker de la Station Spatiale",
        "=" * 50,
        f"  {len(passages_nouveaux)} PASSAGE(S) PRÉVU(S)",
        "=" * 50,
    ]
    for p in passages_nouveaux:
        qualite, _ = evaluer_qualite(p.get("altitude_max", 0))
        plain_lines += [
            "",
            f"  CULMINATION : {p['culmination'].strftime('%d/%m/%Y à %H:%M:%S')}",
            f"  ALTITUDE MAX : {p.get('altitude_max', '—')}°",
            f"  DIRECTION : {p.get('direction', '—')}",
            f"  DISTANCE : {int(p.get('distance_km', 0)):,} km",
            f"  QUALITÉ : {qualite}",
            f"  LEVER : {p['lever'].strftime('%H:%M:%S') if 'lever' in p else '—'}",
            f"  COUCHER : {p['coucher'].strftime('%H:%M:%S') if 'coucher' in p else '—'}",
            "",
            "  " + "-" * 48,
        ]
    plain_lines.append("\nSource : CelesTrak TLE · Calculs Skyfield")
    plain_text = "\n".join(plain_lines)

    # ── HTML ──
    cards_html = ""
    for p in passages_nouveaux:
        alt_max  = p.get("altitude_max", 0)
        qualite, qualite_color = evaluer_qualite(alt_max)
        direction = p.get("direction", "—")
        dist_km   = int(p.get("distance_km", 0))

        heure_culmination = p["culmination"].strftime("%H:%M:%S")
        date_passage      = p["culmination"].strftime("%A %d %B %Y").capitalize()
        heure_lever       = p["lever"].strftime("%H:%M:%S")   if "lever"   in p else "—"
        heure_coucher     = p["coucher"].strftime("%H:%M:%S") if "coucher" in p else "—"

        # Barre d'altitude visuelle
        alt_pct = min(100, int((alt_max / 90) * 100))

        cards_html += f"""
        <div style="background:rgba(59,130,246,0.06);border:1px solid rgba(59,130,246,0.3);
                    border-left:4px solid #3B82F6;border-radius:10px;
                    padding:20px 24px;margin-bottom:20px;">

          <div style="font-size:10px;font-family:monospace;color:#3B82F6;
                      letter-spacing:.12em;text-transform:uppercase;margin-bottom:10px;">
            🛰️ PASSAGE ISS · {MA_VILLE.upper()}
          </div>

          <div style="font-size:22px;font-weight:700;color:#FFFFFF;margin-bottom:4px;">
            {heure_culmination}
          </div>
          <div style="font-size:13px;color:#64748B;font-family:monospace;margin-bottom:20px;">
            {date_passage}
          </div>

          <table style="width:100%;border-collapse:collapse;margin-bottom:16px;">
            <tr>
              <td style="padding:6px 12px 6px 0;font-size:11px;color:#64748B;
                         font-family:monospace;white-space:nowrap;">ALTITUDE MAX</td>
              <td style="padding:6px 0;font-size:20px;font-weight:700;color:#3B82F6;">
                {alt_max}°
              </td>
            </tr>
            <tr>
              <td style="padding:6px 12px 6px 0;font-size:11px;color:#64748B;
                         font-family:monospace;">DIRECTION</td>
              <td style="padding:6px 0;font-size:13px;color:#E2E8F0;">{direction}</td>
            </tr>
            <tr>
              <td style="padding:6px 12px 6px 0;font-size:11px;color:#64748B;
                         font-family:monospace;">DISTANCE</td>
              <td style="padding:6px 0;font-size:13px;color:#E2E8F0;font-family:monospace;">
                {dist_km:,} km
              </td>
            </tr>
            <tr>
              <td style="padding:6px 12px 6px 0;font-size:11px;color:#64748B;
                         font-family:monospace;">LEVER → COUCHER</td>
              <td style="padding:6px 0;font-size:13px;color:#E2E8F0;font-family:monospace;">
                {heure_lever} → {heure_coucher}
              </td>
            </tr>
          </table>

          <!-- Barre altitude -->
          <div style="margin-bottom:12px;">
            <div style="font-size:10px;font-family:monospace;color:#64748B;margin-bottom:6px;">
              ALTITUDE ({alt_max}° / 90° MAX)
            </div>
            <div style="height:4px;background:#0F1E38;border-radius:2px;overflow:hidden;">
              <div style="height:4px;width:{alt_pct}%;background:linear-gradient(90deg,#3B82F6,#60A5FA);
                          border-radius:2px;"></div>
            </div>
          </div>

          <!-- Badge qualité -->
          <div style="display:inline-block;padding:5px 14px;border-radius:6px;
                      background:{qualite_color}20;border:1px solid {qualite_color}50;
                      font-size:12px;font-family:monospace;color:{qualite_color};">
            {qualite}
          </div>

          <!-- Conseils observation -->
          <div style="margin-top:14px;padding:12px 14px;background:#050810;
                      border-radius:8px;font-size:12px;color:#94A3B8;line-height:1.7;">
            💡 <strong style="color:#CBD5E1;">Conseil :</strong>
            Regardez vers le <strong style="color:#FFFFFF;">{direction}</strong>.
            L'ISS ressemble à une étoile très brillante qui se déplace rapidement sans clignoter.
            Magnitude estimée entre -2 et -4 (plus brillant que Jupiter).
          </div>
        </div>"""

    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    html_body = f"""
    <html>
    <body style="margin:0;padding:0;background:#050810;">
      <div style="max-width:620px;margin:0 auto;padding:32px 24px;
                  font-family:'Segoe UI',Arial,sans-serif;">

        <!-- HEADER -->
        <div style="display:flex;align-items:center;gap:14px;margin-bottom:28px;
                    padding-bottom:20px;border-bottom:1px solid #0F1E38;">
          <div style="background:linear-gradient(135deg,#1E3A8A,#3B82F6);
                      border-radius:12px;width:48px;height:48px;
                      display:flex;align-items:center;justify-content:center;
                      font-size:24px;flex-shrink:0;">🛰️</div>
          <div>
            <div style="color:#FFFFFF;font-size:20px;font-weight:700;
                        letter-spacing:.15em;">SENTINELLE ISS</div>
            <div style="color:#4A6FA5;font-size:10px;letter-spacing:.1em;margin-top:2px;">
              TRACKER STATION SPATIALE INTERNATIONALE · {MA_VILLE.upper()}
            </div>
          </div>
        </div>

        <!-- BANNER -->
        <div style="background:rgba(59,130,246,0.08);border:1px solid rgba(59,130,246,0.3);
                    border-radius:10px;padding:14px 20px;margin-bottom:24px;">
          <div style="font-size:13px;font-family:monospace;color:#60A5FA;
                      letter-spacing:.08em;">
            ● {len(passages_nouveaux)} PASSAGE(S) PRÉVU(S) · {now_str}
          </div>
        </div>

        <!-- CARDS -->
        {cards_html}

        <!-- FOOTER -->
        <div style="margin-top:28px;padding-top:20px;border-top:1px solid #0F1E38;
                    font-size:11px;color:#374151;font-family:monospace;line-height:1.8;">
          <div>Source : CelesTrak TLE · Calculs Skyfield Python</div>
          <div>Vérification automatique toutes les heures via GitHub Actions</div>
          <div style="margin-top:6px;color:#1E3A5F;">
            Position configurée : {MA_LATITUDE}°N {MA_LONGITUDE}°E · {MA_VILLE}
          </div>
        </div>

      </div>
    </body>
    </html>"""

    msg.attach(MIMEText(plain_text, "plain"))
    msg.attach(MIMEText(html_body, "html"))

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(GMAIL_USER, GMAIL_PASSWORD)
            server.sendmail(GMAIL_USER, DESTINATAIRE, msg.as_string())
        print(f"[EMAIL] ✅ Envoyé : {len(passages_nouveaux)} passage(s) notifié(s)")
        return True
    except Exception as e:
        print(f"[EMAIL] ❌ Erreur : {e}")
        return False

# ==========================================
# 🚀  MAIN
# ==========================================
if __name__ == "__main__":
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    print(f"[SENTINELLE ISS] Scan démarré · {now}")
    print(f"[INFO] Position : {MA_LATITUDE}°N {MA_LONGITUDE}°E · {MA_VILLE}")
    print("=" * 52)

    if not GMAIL_PASSWORD:
        print("[ERREUR] GMAIL_PASSWORD non défini dans les secrets GitHub")
        exit(1)

    # Chargement mémoire
    memoire = charger_memoire()

    # Calcul des passages
    passages = trouver_passages()

    if not passages:
        print("[OK] Aucun passage visible dans les prochaines", FENETRE_HEURES, "heures")
    else:
        # Filtrage des nouveaux passages non notifiés
        passages_nouveaux = []
        for p in passages:
            # ID unique = date + heure arrondie à la minute
            passage_id = p["culmination"].strftime("%Y%m%d%H%M")
            if passage_id not in memoire:
                passages_nouveaux.append(p)
                memoire.add(passage_id)
                sauvegarder_passage(passage_id)

        if passages_nouveaux:
            print(f"[INFO] {len(passages_nouveaux)} nouveau(x) passage(s) à notifier")
            envoyer_email(passages_nouveaux)
        else:
            print("[OK] Tous les passages déjà notifiés — pas d'email")

    print("=" * 52)
    print("[SENTINELLE ISS] Scan terminé")
