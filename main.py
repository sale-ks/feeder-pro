from dotenv import load_dotenv
from fastapi import FastAPI, Request, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
import google.generativeai as genai
import os 
import requests, json, re
from typing import List

# Učitava varijable iz .env fajla
load_dotenv() 

app = FastAPI()

# --- KONFIGURACIJA ---
API_KEY = os.getenv("GEMINI_API_KEY")
if API_KEY:
    genai.configure(api_key=API_KEY)

# Preporuka: 1.5-flash je stabilniji za free kvote
MODEL_NAME = 'gemini-2.5-flash' 

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# --- GEOGRAFSKI KONTEKST ZA PRECIZNOST AI MODELA ---
LOKALNI_KONTEKST = {
    "Kruševac": "Zapadna Morava (potezi Jasika, Čitluk, Kukljin), reka Rasina, jezero Ćelije (potezi Zlatari i Vasići).",
    "Beograd": "Sava (Makiš, Umka, Boljevci), Dunav (Višnjica, Grocka, Zemunski kej), Ada Safari.",
    "Niš": "Nišava, Južna Morava (Mramor, Lalinac), Oblačinsko jezero.",
    "Novi Sad": "Dunav (Kamenjar, Kej), kanal DTD, Šodroš, jezero Međeš.",
    "Kragujevac": "Jezero Gruža, Šumaričko jezero, Lepenica.",
    "Čačak": "Zapadna Morava (Međuvršje, Ovčar Banja, Parmenac).",
    "Kraljevo": "Ibar, Zapadna Morava (Sirča, Adrani).",
    "Valjevo": "Kolubara, jezero Rovni, Gradac.",
    "Smederevo": "Dunav (Tvrđava, ušće Jezave), Šalinačko jezero.",
    "Pančevo": "Tamiš (Kej, Jabuka, Glogonj), Dunav.",
    "Subotica": "Palićko jezero, Ludaško jezero, kanal DTD."
}

# --- KOMPLETNI PODACI ---
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
        # 1. Geocoding
        geo_res = requests.get(f"https://geocoding-api.open-meteo.com/v1/search?name={req.grad}&count=1&format=json", timeout=5).json()
        if "results" in geo_res:
            res = geo_res["results"][0]
            # 2. Weather
            w_res = requests.get(f"https://api.open-meteo.com/v1/forecast?latitude={res['latitude']}&longitude={res['longitude']}&current_weather=true", timeout=5).json()
            vreme_info = f"{w_res['current_weather']['temperature']}°C"
    except Exception as e:
        print(f"Weather Fetch Error: {e}")
        vreme_info = "N/A"

    # Dohvatanje hintova za grad
    hint = LOKALNI_KONTEKST.get(req.grad, "lokalne reke i jezera.")

    prompt = f"""
    Ti si profesionalni feeder ribolovac. 
    LOKACIJA: {req.grad} (Kontekst: {hint})
    VREME: {vreme_info}
    PARAMETRI: Riba {req.riba}, Voda {req.voda}, Brendovi {req.brendovi}, Budžet {req.budzet}, Iskustvo {req.iskustvo}.

    ZADATAK:
    1. Prilagodi taktiku (prihrana, mamac) temperaturi od {vreme_info}.
    2. Navedi 3 KONKRETNA MESTA (reke/jezera) u okolini grada {req.grad} koristeći hint: {hint}.
    
    VRATI ISKLJUČIVO JSON OBJEKAT:
    {{
      "vreme": "{vreme_info}",
      "taktika": "HTML formatiran tekst",
      "mesta": "HTML formatiran tekst sa 3 lokacije",
      "shopping": ["stavka 1", "stavka 2"]
    }}
    """
    
    try:
        model = genai.GenerativeModel(MODEL_NAME)
        response = model.generate_content(prompt)
        
        # Ekstrakcija JSON-a
        json_match = re.search(r'\{.*\}', response.text, re.DOTALL)
        if json_match:
            data = json.loads(json_match.group())
            
            # OSIGURANJE: Ako AI zaboravi ključ "vreme", mi ga dodajemo pre slanja frontendu
            if "vreme" not in data or data["vreme"] == "undefined":
                data["vreme"] = vreme_info
                
            return data
        
        raise Exception("Neispravan JSON format od AI modela")

    except Exception as e:
        print(f"Generate Error: {e}")
        # Fallback odgovor u slučaju greške
        return {
            "vreme": vreme_info,
            "taktika": "Trenutno ne mogu da generišem plan. Molim vas pokušajte ponovo.",
            "mesta": f"Proverite lokacije u blizini: {hint}",
            "shopping": []
        }