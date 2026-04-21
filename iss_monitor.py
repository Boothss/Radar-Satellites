"""
SENTINELLE ISS — Script de surveillance autonome 24/7
Tourne toutes les heures via GitHub Actions.
Envoie un email si l'ISS passe au-dessus de Calais dans les prochaines 12h.
"""

import smtplib
import pytz
import os
import requests
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from skyfield.api import load, wgs84
from datetime import datetime, timedelta, timezone

# Fuseau horaire France
FUSEAU_FRANCE = pytz.timezone("Europe/Paris")

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
ALTITUDE_MIN = 10.0

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
            heure_locale = heure_utc.replace(tzinfo=pytz.utc).astimezone(FUSEAU_FRANCE)

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
    heure_str   = p["culmination"].strftime("%H:%M")
    date_str    = p["culmination"].strftime("%A %d %B").upper()
    msg["Subject"] = f"⚠️ ALERTE ORBITALE : ISS Visibilité Confirmée - {date_str} à {heure_str}"
    msg["From"]    = f"NASA Mission Control Centre <{GMAIL_USER}>"
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

    # ── HTML — Style NASA Mission Control (design original) ──
    now_str  = datetime.now(timezone.utc).strftime("%Y-%m-%d-%H%M")

    rows_html = ""
    for p in passages_nouveaux:
        alt_max       = p.get("altitude_max", 0)
        qualite, _    = evaluer_qualite(alt_max)
        direction     = p.get("direction", "—")
        dist_km       = int(p.get("distance_km", 0))
        heure_exacte  = p["culmination"].strftime("%H:%M")
        date_texte    = p["culmination"].strftime("%A %d %B %Y").upper()
        heure_lever   = p["lever"].strftime("%H:%M:%S")   if "lever"   in p else "—"
        heure_coucher = p["coucher"].strftime("%H:%M:%S") if "coucher" in p else "—"

        rows_html += f"""
        <!-- SÉPARATEUR ENTRE PASSAGES -->
        <tr><td colspan="2" style="padding:0;height:8px;background:#f1f1f1;"></td></tr>
        <tr style="background-color:#e8f0fe;">
          <td colspan="2" style="padding:10px 12px;font-size:13px;
              color:#0B3D91;font-weight:bold;border:1px solid #d1d1d1;">
            🛰️ PASSAGE #{passages_nouveaux.index(p)+1} sur {len(passages_nouveaux)}
          </td>
        </tr>
        <tr>
          <td style="padding:12px;border:1px solid #d1d1d1;">
            <strong>Identifiant de la Cible</strong>
          </td>
          <td style="padding:12px;border:1px solid #d1d1d1;">
            ISS (ZARYA) // NORAD ID 25544
          </td>
        </tr>
        <tr>
          <td style="padding:12px;border:1px solid #d1d1d1;">
            <strong>Coordonnées d'Observation</strong>
          </td>
          <td style="padding:12px;border:1px solid #d1d1d1;">
            LAT {MA_LATITUDE} | LON {MA_LONGITUDE} (Base de Calais)
          </td>
        </tr>
        <tr>
          <td style="padding:12px;border:1px solid #d1d1d1;">
            <strong>Date du Phénomène</strong>
          </td>
          <td style="padding:12px;border:1px solid #d1d1d1;">{date_texte}</td>
        </tr>
        <tr style="background-color:#FFF5F5;">
          <td style="padding:15px;border:1px solid #FC3D21;color:#FC3D21;">
            <strong>⚡ HEURE CRITIQUE D'INTERCEPTION</strong>
          </td>
          <td style="padding:15px;border:1px solid #FC3D21;color:#FC3D21;
              font-weight:bold;font-size:20px;">
            {heure_exacte} (HEURE LOCALE)
          </td>
        </tr>
        <tr>
          <td style="padding:12px;border:1px solid #d1d1d1;">
            <strong>Altitude Maximale</strong>
          </td>
          <td style="padding:12px;border:1px solid #d1d1d1;font-weight:bold;">
            {alt_max}° — {qualite}
          </td>
        </tr>
        <tr>
          <td style="padding:12px;border:1px solid #d1d1d1;">
            <strong>Direction d'Observation</strong>
          </td>
          <td style="padding:12px;border:1px solid #d1d1d1;">{direction}</td>
        </tr>
        <tr>
          <td style="padding:12px;border:1px solid #d1d1d1;">
            <strong>Distance ISS</strong>
          </td>
          <td style="padding:12px;border:1px solid #d1d1d1;font-family:monospace;">
            {dist_km:,} km
          </td>
        </tr>
        <tr>
          <td style="padding:12px;border:1px solid #d1d1d1;">
            <strong>Fenêtre d'Observation</strong>
          </td>
          <td style="padding:12px;border:1px solid #d1d1d1;font-family:monospace;">
            {heure_lever} → {heure_coucher}
          </td>
        </tr>"""

    html_body = f"""
    <!DOCTYPE html>
    <html>
    <body style="background-color:#ffffff;color:#333333;
                 font-family:Arial,Helvetica,sans-serif;padding:20px;font-size:16px;">

      <div style="border:1px solid #d1d1d1;padding:0;max-width:650px;margin:auto;
                  background-color:#ffffff;box-shadow:0 4px 10px rgba(0,0,0,0.1);">

        <!-- HEADER NASA -->
        <div style="background-color:#0B3D91;color:#ffffff;padding:20px;
                    text-align:center;border-bottom:4px solid #FC3D21;">
          <img src="https://upload.wikimedia.org/wikipedia/commons/thumb/e/e5/NASA_logo.svg/100px-NASA_logo.svg.png"
               alt="NASA Logo" style="width:80px;margin-bottom:10px;">
          <h1 style="color:#ffffff;margin:0;text-transform:uppercase;
                     letter-spacing:1px;font-size:22px;">
            National Aeronautics and Space Administration
          </h1>
          <p style="margin:5px 0 0 0;color:#e1e1e1;font-weight:bold;">
            Mission Control Centre // Orbital Event Notification
          </p>
        </div>

        <!-- CORPS -->
        <div style="padding:30px;">
          <h2 style="color:#0B3D91;border-bottom:2px solid #0B3D91;
                     padding-bottom:10px;margin-top:0;">
            Alerte d'Observation Orbitale N° {now_str}
          </h2>

          <p><strong>ATTENTION OBSERVATION OFFICER BAILLY.</strong></p>
          <p style="line-height:1.6;">
            Le département de Télémétrie et de Suivi Spatial a confirmé
            <strong>{len(passages_nouveaux)} opportunité(s)</strong> d'observation visuelle
            de la Station Spatiale Internationale au-dessus de vos coordonnées actuelles
            (Base d'Observation de Calais).
          </p>

          <table style="width:100%;border-collapse:collapse;margin-top:25px;
                        margin-bottom:25px;border:1px solid #d1d1d1;">
            <thead style="background-color:#f1f1f1;">
              <tr>
                <th style="padding:12px;text-align:left;border:1px solid #d1d1d1;
                            color:#0B3D91;">Paramètre</th>
                <th style="padding:12px;text-align:left;border:1px solid #d1d1d1;
                            color:#0B3D91;">Donnée</th>
              </tr>
            </thead>
            <tbody>
              {rows_html}
            </tbody>
          </table>

          <h3 style="color:#0B3D91;margin-top:25px;">Directives d'Observation :</h3>
          <ul style="line-height:1.6;color:#555555;padding-left:20px;">
            <li><strong>Météo :</strong> Vérifiez les conditions de couverture nuageuse
                locale avant déploiement.</li>
            <li><strong>Visibilité :</strong> La cible apparaîtra comme un point lumineux
                non clignotant, traversant le ciel de façon constante.</li>
            <li><strong>Préparation :</strong> L'élévation de {ALTITUDE_MIN}° garantit
                une réflectivité solaire maximale pour une observation à l'œil nu.</li>
          </ul>

          <p style="text-align:center;margin-top:40px;color:#888888;font-size:13px;
                    border-top:1px solid #d1d1d1;padding-top:20px;">
            Ceci est une transmission automatisée générée par Sentinelle Python v2.1.<br>
            © National Aeronautics and Space Administration.
          </p>
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
