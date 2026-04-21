import smtplib
from email.message import EmailMessage
from skyfield.api import load, wgs84
from datetime import datetime, timedelta
import time
import pytz

# ==========================================
# 1. CONFIGURATION (Identique)
# ==========================================

MA_LATITUDE = 50.9555
MA_LONGITUDE = 1.8842

GMAIL_USER = "alexbailly82@gmail.com"
GMAIL_PASSWORD = "typa rnce bazv ryyi"
DESTINATAIRE = "alexbailly82@gmail.com"

# On définit le fuseau horaire français
FUSEAU_FRANCE = pytz.timezone('Europe/Paris')

# Mémoire du système pour ne pas spammer
dernier_passage_alerte = None

# ==========================================
# 2. DESIGN ET ENVOI DE L'EMAIL (STYLE BRIEFING NASA)
# ==========================================

def envoyer_email(heure_passage_france):
    # L'heure et la date formatées en français
    heure_exacte = heure_passage_france.strftime('%H:%M')
    date_texte = heure_passage_france.strftime('%A %d %B')

    msg = EmailMessage()
    # Sujet pro et formel
    msg['Subject'] = f"⚠️ ALERTE ORBITALE : ISS Visibilité Confirmée - {date_texte} à {heure_exacte}"

    # L'expéditeur personnalisé qui s'affiche dans la boîte mail
    msg['From'] = f"NASA Mission Control Centre <{GMAIL_USER}>"
    msg['To'] = DESTINATAIRE

    # Version texte brut (sécurité)
    msg.set_content(f"Alerte d'observation de l'ISS au-dessus de Calais. Passage prévu le {date_texte} à {heure_exacte}.")

    # Version HTML "Briefing Officiel NASA" (Fond blanc, Bleu/Rouge NASA)
    design_nasa = f"""
    <!DOCTYPE html>
    <html>
    <body style="background-color: #ffffff; color: #333333; font-family: Arial, Helvetica, sans-serif; padding: 20px; font-size: 16px;">

        <div style="border: 1px solid #d1d1d1; padding: 0; max-width: 650px; margin: auto; background-color: #ffffff; box-shadow: 0 4px 10px rgba(0,0,0,0.1);">

            <div style="background-color: #0B3D91; color: #ffffff; padding: 20px; text-align: center; border-bottom: 4px solid #FC3D21;">
                <img src="https://upload.wikimedia.org/wikipedia/commons/thumb/e/e5/NASA_logo.svg/100px-NASA_logo.svg.png" alt="NASA Logo" style="width: 80px; margin-bottom: 10px;">
                <h1 style="color: #ffffff; margin: 0; text-transform: uppercase; letter-spacing: 1px; font-size: 22px;">National Aeronautics and Space Administration</h1>
                <p style="margin: 5px 0 0 0; color: #e1e1e1; font-weight: bold;">Mission Control Centre // Orbital Event Notification</p>
            </div>

            <div style="padding: 30px;">
                <h2 style="color: #0B3D91; border-bottom: 2px solid #0B3D91; padding-bottom: 10px; margin-top: 0;">Alerte d'Observation Orbitale N° {datetime.now().strftime('%Y-%m%d-%H%M')}</h2>

                <p><strong>ATTENTION OBSERVATION OFFICER BAILLY.</strong></p>
                <p style="line-height: 1.6;">Le département de Télémétrie et de Suivi Spatial a confirmé une opportunité d'observation visuelle de la Station Spatiale Internationale au-dessus de vos coordonnées actuelles (Base d'Observation de Calais).</p>

                <table style="width: 100%; border-collapse: collapse; margin-top: 25px; margin-bottom: 25px; border: 1px solid #d1d1d1;">
                    <thead style="background-color: #f1f1f1;">
                        <tr>
                            <th style="padding: 12px; text-align: left; border: 1px solid #d1d1d1; color: #0B3D91;">Paramètre</th>
                            <th style="padding: 12px; text-align: left; border: 1px solid #d1d1d1; color: #0B3D91;">Donnée</th>
                        </tr>
                    </thead>
                    <tbody>
                        <tr>
                            <td style="padding: 12px; border: 1px solid #d1d1d1;"><strong>Identifiant de la Cible</strong></td>
                            <td style="padding: 12px; border: 1px solid #d1d1d1;">ISS (ZARYA) // NORAD ID 25544</td>
                        </tr>
                        <tr>
                            <td style="padding: 12px; border: 1px solid #d1d1d1;"><strong>Coordonnées d'Observation</strong></td>
                            <td style="padding: 12px; border: 1px solid #d1d1d1;">LAT {MA_LATITUDE} | LON {MA_LONGITUDE} (Base de Calais)</td>
                        </tr>
                        <tr>
                            <td style="padding: 12px; border: 1px solid #d1d1d1;"><strong>Date du Phénomène</strong></td>
                            <td style="padding: 12px; border: 1px solid #d1d1d1; text-transform: uppercase;">{date_texte}</td>
                        </tr>
                        <tr style="background-color: #FFF5F5;">
                            <td style="padding: 15px; border: 1px solid #FC3D21; color: #FC3D21;"><strong>⚡ HEURE CRITIQUE D'INTERCEPTION</strong></td>
                            <td style="padding: 15px; border: 1px solid #FC3D21; color: #FC3D21; font-weight: bold; font-size: 20px;">
                                {heure_exacte} (HEURE LOCALE)
                            </td>
                        </tr>
                    </tbody>
                </table>

                <h3 style="color: #0B3D91; margin-top: 25px;">Directives d'Observation :</h3>
                <ul style="line-height: 1.6; color: #555555; padding-left: 20px;">
                    <li><strong>Météo :</strong> Vérifiez les conditions de couverture nuageuse locale avant déploiement.</li>
                    <li><strong>Visibilité :</strong> La cible apparaîtra comme un point lumineux non clignotant, traversant le ciel de façon constante.</li>
                    <li><strong>Préparation :</strong> L'élévation de {30.0}° garantit une réflectivité solaire maximale pour une observation à l'œil nu.</li>
                </ul>

                <p style="text-align: center; margin-top: 40px; color: #888888; font-size: 13px; border-top: 1px solid #d1d1d1; padding-top: 20px;">
                    Ceci est une transmission automatisée générée par Sentinelle Python v2.1.<br>
                    © National Aeronautics and Space Administration.
                </p>
            </div>
        </div>
    </body>
    </html>
    """

    msg.add_alternative(design_nasa, subtype='html')

    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
            smtp.login(GMAIL_USER, GMAIL_PASSWORD)
            smtp.send_message(msg)
        print(f"📧 Rapport Officiel envoyé pour le {date_texte} à {heure_exacte}")
    except Exception as e:
        print(f"❌ Échec de la transmission officielle : {e}")

# ==========================================
# 3. CALCUL DU PASSAGE ORBITAL (Identique)
# ==========================================

def trouver_prochain_passage():
    ts = load.timescale()
    t0 = ts.now()

    stations_url = 'http://celestrak.org/NORAD/elements/stations.txt'
    satellites = load.tle_file(stations_url)
    iss = {sat.name: sat for sat in satellites}['ISS (ZARYA)']

    ma_maison = wgs84.latlon(MA_LATITUDE, MA_LONGITUDE)
    t1 = ts.from_datetime(t0.utc_datetime() + timedelta(days=2))

    # Recherche des événements à plus de 30 degrés au-dessus de l'horizon
    t, events = iss.find_events(ma_maison, t0, t1, altitude_degrees=30.0)

    for time_pass, event in zip(t, events):
        if event == 1: # 1 = point culminant
            # On convertit en heure de France
            heure_utc = time_pass.utc_datetime()
            heure_france = heure_utc.replace(tzinfo=pytz.utc).astimezone(FUSEAU_FRANCE)
            maintenant_france = datetime.now(FUSEAU_FRANCE)

            # On s'assure que le passage est bien dans le futur
            if heure_france > maintenant_france:
                return heure_france
    return None

# ==========================================
# 4. BOUCLE PRINCIPALE (Identique)
# ==========================================

if __name__ == "__main__":
    print("🛰️ NASA Briefing System - Activation 🚀")
    print("-" * 40)

    while True:
        try:
            prochain = trouver_prochain_passage()

            if prochain:
                if prochain != dernier_passage_alerte:
                    print(f"✨ Cible validée pour le : {prochain.strftime('%d/%m à %H:%M')}")
                    envoyer_email(prochain)
                    dernier_passage_alerte = prochain
                else:
                    print(f"😴 Rapport déjà généré pour {prochain.strftime('%H:%M')}.")
            else:
                print("☁️ Aucun événement orbital significatif détecté dans les prochaines 48h.")

        except Exception as e:
            print(f"⚠️ Alerte système : {e}")

        # Pause de 1 heure avant la prochaine vérification
        print("⏳ Attente avant prochain cycle de télémétrie (1 heure)...")
        time.sleep(3600)
