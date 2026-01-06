from dotenv import load_dotenv
from fastapi import FastAPI, Request, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
import google.generativeai as genai
import os 
import requests, json, re
from typing import List

load_dotenv() 

app = FastAPI()

# --- KONFIGURACIJA ---
API_KEY = os.getenv("GEMINI_API_KEY")
if API_KEY:
    genai.configure(api_key=API_KEY)

MODEL_NAME = 'gemini-2.5-flash' # Stabilniji model za produkciju

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# --- GEOGRAFSKI KONTEKST ---
LOKALNI_KONTEKST = {
    "Kruševac": "Reke: Zapadna Morava (Jasika, Čitluk), Rasina. Komercijale: Ribnjak 'Pista' (Pepeljevac), Jezero 'Mali Borak'.",
    "Beograd": "Reke: Sava, Dunav. Komercijale: Ada Safari, Mika Alas, Živača, Bečmenska bara, Ribnjak Zmaj.",
    "Niš": "Reke: Nišava, J. Morava. Komercijale: Jezero Mramor (komercijalni deo), Ribnjak Ponišavlje, Oblačina.",
    "Novi Sad": "Reke: Dunav, Kanali. Komercijale: Međeš, Jod, Ribnjak Ečka, Kasapska Ada.",
    "Kragujevac": "Jezera: Gruža. Komercijale: Šumaričko jezero (komercijalna zona), Ribnjak Knić, Jezero u Desimirovcu.",
    "Čačak": "Reke: Zapadna Morava. Komercijale: Međuvršje (određene zone), Ribnjaci ka Požegi.",
    "Kraljevo": "Reke: Ibar, Zapadna Morava. KOMERCIJALE: Jezero Oaza (Adrani), Ribnjak Samaila, Jezero Gradište (Vrdila).",
    "Valjevo": "Reke: Kolubara. Komercijale: Ribnjak Petnica, Jezero Rovni (komercijalni delovi).",
    "Pančevo": "Reke: Tamiš, Dunav. Komercijale: Jezero Oaza (Opovo), Ribnjak Debeljača.",
    "Smederevo": "Reke: Dunav. Komercijale: Šalinačko jezero (komercijalni deo), Ribnjaci u okolini."
}

DATA = {
    "brendovi": ["Formax Elegance", "Gica Mix", "Maros Mix", "Sensas", "VDE", "Haldorado", "Benzar Mix", "Feedermania", "Meleg Bait", "Bait Service", "CPK", "Browning"],
    "vode": ["Stajaća voda", "Spori tok", "Brza reka", "Komercijala"],
    "zabrane": {
        "Šaran": "01. apr - 31. maj", "Deverika": "15. apr - 31. maj", "Mrena": "15. apr - 31. maj",
        "Skobalj": "15. apr - 31. maj", "Babuška": "Nema zabrane", "Amur": "Nema zabrane"
    },
    "radnje": {
        "Beograd": ["Formax Store", "DTD Ribarstvo", "Carpologija", "Alas", "Ribolovac"],
        "Kruševac": ["Predator", "Profi", "Rasina"],
        "Niš": ["Formax Store Niš", "Plovak-Mare", "Enter Fishing Shop"],
        "Novi Sad": ["Formax Store", "Travar", "Carpologija NS"],
        "Kragujevac": ["Ribosport", "Srebrna Udica", "Marlin", "Formax Store KG"],
        "Čačak": ["Barbus", "Ribolovac Čačak"],
        "Kraljevo": ["Ribolovac KV", "Trofej"],
        "Subotica": ["Plovak SU", "Ribomarket"],
        "Šabac": ["Zlatna Ribica", "Delfin"],
        "Pančevo": ["Tamiški Ribolovac"],
        "Valjevo": ["Kolubara Ribolov"]
    }
}

class PlanRequest(BaseModel):
    grad: str
    brendovi: List[str]
    voda: str
    riba: str
    iskustvo: str
    budzet: str

@app.get("/")
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request, "data": DATA})

@app.post("/generate")
async def generate(req: PlanRequest):
    vreme_info = "N/A"
    try:
        geo_res = requests.get(f"https://geocoding-api.open-meteo.com/v1/search?name={req.grad}&count=1&format=json", timeout=5).json()
        if "results" in geo_res:
            res = geo_res["results"][0]
            w_res = requests.get(f"https://api.open-meteo.com/v1/forecast?latitude={res['latitude']}&longitude={res['longitude']}&current_weather=true", timeout=5).json()
            vreme_info = f"{w_res['current_weather']['temperature']}°C"
    except:
        vreme_info = "N/A"

    hint = LOKALNI_KONTEKST.get(req.grad, "lokalne vode.")

    # STRIKTNI PROMPT
    prompt = f"""
    Ti si feeder ribolovac ekspert iz Srbije.
    LOKACIJA: {req.grad}
    HINTOVI ZA MESTA: {hint}
    TIP VODE: {req.voda}
    TEMP: {vreme_info}
    RIBA: {req.riba}, BRENDOVI: {req.brendovi}, BUDŽET: {req.budzet}.

    PRAVILA:
    1. Ako je TIP VODE 'Komercijala', ignoriši reke i navedi isključivo komercijalna jezera iz hintova.
    2. Odgovori isključivo u JSON formatu.
    
    JSON STRUKTURA:
    {{
      "vreme": "{vreme_info}",
      "taktika": "HTML tekst sa planom",
      "mesta": "HTML tekst sa 3 konkretne lokacije",
      "shopping": ["artikal 1", "artikal 2"]
    }}
    """

    # ISKLJUČIVANJE SAFETY FILTERA (da ne blokira reči kao što su udica)
    safety_settings = [
        {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
        {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
        {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
        {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
    ]

    try:
        model = genai.GenerativeModel(MODEL_NAME)
        response = model.generate_content(prompt, safety_settings=safety_settings)
        
        # Provera da li AI uopšte vratio tekst
        if not response.text:
            raise Exception("AI je blokirao odgovor zbog safety filtera.")

        # Čišćenje i ekstrakcija JSON-a
        json_match = re.search(r'\{.*\}', response.text, re.DOTALL)
        if json_match:
            data = json.loads(json_match.group())
            if "vreme" not in data: data["vreme"] = vreme_info
            return data
        
        raise Exception("AI nije vratio ispravan JSON format.")

    except Exception as e:
        print(f"CRITICAL ERROR: {str(e)}")
        # Fallback koji uvek radi
        return {
            "vreme": vreme_info,
            "taktika": "Trenutno imamo poteškoća. Osnovni savet: Prilagodite primamu temperaturi i koristite laganiji pribor.",
            "mesta": f"Preporučena mesta za grad {req.grad} ({req.voda}): {hint}",
            "shopping": ["Osnovna feeder hrana", "Mamci (crvići/kukuruz)", "Feeder predvezi"]
        }