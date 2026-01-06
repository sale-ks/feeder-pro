from fastapi import FastAPI, Request, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
import google.generativeai as genai
import requests, json, re
from typing import List

app = FastAPI()

# --- KONFIGURACIJA ---
API_KEY = "AIzaSyC6SpW9O2Dl8hgCW3jOj7hrWwfWMG2DCxA"
genai.configure(api_key=API_KEY)
MODEL_NAME = 'gemini-2.5-flash' 

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

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
        "Niš": ["Formax Niš", "Plovak-Mare", "Enter Fishing"],
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
        geo = requests.get(f"https://geocoding-api.open-meteo.com/v1/search?name={req.grad}&count=1&format=json").json()
        if "results" in geo:
            res = geo["results"][0]
            w = requests.get(f"https://api.open-meteo.com/v1/forecast?latitude={res['latitude']}&longitude={res['longitude']}&current_weather=true").json()
            vreme_info = f"{w['current_weather']['temperature']}°C"
    except: pass

    # POJAČAN PROMPT ZA KONKRETNE LOKACIJE
    prompt = f"""
    Ti si feeder ekspert u Srbiji.
    PARAMETRI: Grad: {req.grad}, Vreme: {vreme_info}, Riba: {req.riba}, Voda: {req.voda}, Brendovi: {req.brendovi}, Budžet: {req.budzet}, Iskustvo: {req.iskustvo}.
    
    VRATI ISKLJUČIVO JSON OBJEKAT:
    {{
      "taktika": "Detaljan plan (prihrana, mamac, predvez) u HTML formatu sa <ul><li> tagovima.",
      "mesta": "Navedi tačno 3 KONKRETNA GEOGRAFSKA MESTA (reke, jezera, potezi) u okolini grada {req.grad} pogodna za {req.riba}. Koristi HTML.",
      "shopping": ["stavka 1", "stavka 2", "stavka 3"]
    }}
    """
    
    try:
        model = genai.GenerativeModel(MODEL_NAME)
        response = model.generate_content(prompt)
        clean_json = re.search(r'\{.*\}', response.text, re.DOTALL).group()
        return json.loads(clean_json)
    except Exception as e:
        if "429" in str(e): raise HTTPException(status_code=429, detail="Limit dostignut. Sačekaj 30s.")
        raise HTTPException(status_code=500, detail="Greška servera.")