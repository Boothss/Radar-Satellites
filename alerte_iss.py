import smtplib
from email.message import EmailMessage
from skyfield.api import load, wgs84
from datetime import datetime, timedelta
import time
import locale

# --- CONFIGURATION ---
# On essaie de mettre les dates en français (si ton système le permet)
try:
    locale.setlocale(locale.LC_TIME, "fr_FR.UTF-8")
except:
    pass 

MA_LATITUDE = 50.9555
MA_LONGITUDE = 1.8842

GMAIL_USER = "alexbailly82@gmail.com"
GMAIL_PASSWORD = "typa rnce bazv ryyi" 
DESTINATAIRE = "alexbailly82@gmail.com"

# Cette variable sert à ne pas envoyer plusieurs mails pour le même passage
dernier_passage_alerte = None

def envoyer_email(heure_passage):
    # Formatage propre : "Lundi 20 Avril à 21:30"
    date_texte = heure_passage.strftime('%A %d %B à %H:%M')
    
    msg = EmailMessage()
    msg.set_content(f"🚨 ALERTE ISS : L'ISS sera visible au-dessus de Calais le {date_texte} !\n\nPrépare tes yeux ou tes jumelles. Le satellite passera à plus de 30° d'altitude.")
    msg['Subject'] = f"🛰️ Passage ISS prévu : {heure_passage.strftime('%H:%M')}"
    msg['From'] = GMAIL_USER
    msg['To'] = DESTINATAIRE

    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
            smtp.login(GMAIL_USER, GMAIL_PASSWORD)
            smtp.send_message(msg)
        print(f"📧 Mail envoyé pour le passage de {date_texte}")
    except Exception as e:
        print(f"❌ Erreur mail : {e}")

def trouver_prochain_passage():
    ts = load.timescale()
    t0 = ts.now()
    
    # On télécharge les données fraîches de la NASA
    stations_url = 'http://celestrak.org/NORAD/elements/stations.txt'
    satellites = load.tle_file(stations_url)
    iss = {sat.name: sat for sat in satellites}['ISS (ZARYA)']
    
    ma_maison = wgs84.latlon(MA_LATITUDE, MA_LONGITUDE)
    
    # On cherche sur les prochaines 48 heures
    t1 = ts.from_datetime(t0.utc_datetime() + timedelta(days=2))
    
    # On cherche les événements (0=lever, 1=culmination, 2=coucher)
    t, events = iss.find_events(ma_maison, t0, t1, altitude_degrees=30.0)
    
    for time_pass, event in zip(t, events):
        if event == 1: # On ne prend que le point le plus haut (culmination)
            heure_locale = time_pass.utc_datetime().astimezone()
            
            # CRUCIAL : On vérifie que le passage est bien dans le FUTUR
            if heure_locale > datetime.now().astimezone():
                return heure_locale
    return None

if __name__ == "__main__":
    print("🛰️ DÉMARRAGE DE LA SENTINELLE ISS (Version Pro)")
    print(f"📍 Position : {MA_LATITUDE}, {MA_LONGITUDE}")
    print("-" * 40)

    while True:
        try:
            prochain = trouver_prochain_passage()
            
            if prochain:
                # Si c'est un nouveau passage qu'on n'a pas encore traité
                if prochain != dernier_passage_alerte:
                    print(f"✨ Nouveau passage détecté : {prochain.strftime('%d/%m %H:%M')}")
                    envoyer_email(prochain)
                    dernier_passage_alerte = prochain
                else:
                    print(f"😴 Passage de {prochain.strftime('%H:%M')} déjà notifié. En attente...")
            else:
                print("☁️ Aucun passage visible dans les prochaines 48h.")

        except Exception as e:
            print(f"⚠️ Erreur lors de la vérification : {e}")

        # Pause de 1 heure avant la prochaine vérification des données
        print("⏳ Prochaine vérification dans 1 heure...")
        time.sleep(3600)