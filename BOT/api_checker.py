import threading
import time
import logging
import google.generativeai as genai
import os
from dotenv import load_dotenv

# Logging einrichten
logger = logging.getLogger(__name__)

# GEMINI_API_KEY aus Umgebungsvariablen laden
load_dotenv()
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
MODEL_NAME = 'gemini-pro'  # oder dein gewünschtes Modell

class API_Checker(threading.Thread):
    def __init__(self, api_key, interval=3600):  # Standardmäßig alle 60 Minuten (3600 Sekunden)
        threading.Thread.__init__(self)
        self.api_key = api_key
        self.interval = interval
        self.api_available = True
        self.stop_event = threading.Event()  # Event zum Anhalten des Threads

    def run(self):
        while not self.stop_event.is_set():
            if self.check_api_availability():
                logger.info("API is available.")
                self.api_available = True
            else:
                logger.warning("API is unavailable.")
                self.api_available = False
            time.sleep(self.interval)

    def check_api_availability(self):
        try:
            genai.configure(api_key=self.api_key)
            model = genai.GenerativeModel(MODEL_NAME)
            response = model.generate_content("Test")
            return True  # API scheint zu funktionieren
        except Exception as e:
            logger.error(f"API check failed: {e}")
            return False

    def stop(self):
        self.stop_event.set()  # Thread sicher anhalten
        self.join()  # Warten, bis der Thread beendet ist

if __name__ == '__main__':
    # Beispiel-Verwendung (zum Testen)
    api_checker = API_Checker(GEMINI_API_KEY, interval=60)  # Prüft alle 60 Sekunden
    api_checker.start()
    time.sleep(300)  # Läuft 5 Minuten
    api_checker.stop()
