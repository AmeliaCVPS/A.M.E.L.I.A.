import os
import json
import hashlib
from cryptography.fernet import Fernet
from pydantic import BaseModel

# Configuração de Criptografia via Variável de Ambiente
# No Vercel, adicione FERNET_KEY nas Settings
FERNET_KEY = os.getenv("FERNET_KEY")
if not FERNET_KEY:
    # Fallback apenas para não quebrar em dev, mas em prod DEVE estar no Vercel
    FERNET_KEY = Fernet.generate_key().decode()

CIPHER = Fernet(FERNET_KEY.encode())

class SymptomsInput(BaseModel):
    cpf: str
    age: int
    sex: str
    description: str
    pain_level: int
    fever: bool
    shortness_of_breath: bool
    duration_hours: int

def predict_risk(data: SymptomsInput):
    """
    Lógica de Classificação de Risco (Protocolo de Manchester adaptado)
    """
    score = 0
    
    # Pontuação por sintomas críticos
    if data.shortness_of_breath: score += 10
    if data.pain_level >= 8: score += 7
    if data.fever: score += 3
    if data.age > 60 or data.age < 5: score += 2

    # Classificação
    if score >= 10:
        return {"color": "red", "priority": "Emergência", "wait_time": "Imediato", "password": f"U-{os.urandom(2).hex().upper()}"}
    elif score >= 5:
        return {"color": "orange", "priority": "Muito Urgente", "wait_time": "10 min", "password": f"M-{os.urandom(2).hex().upper()}"}
    else:
        return {"color": "green", "priority": "Pouco Urgente", "wait_time": "120 min", "password": f"L-{os.urandom(2).hex().upper()}"}
