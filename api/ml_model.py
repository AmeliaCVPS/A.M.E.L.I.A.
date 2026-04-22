# ml_model.py
"""
Camada de Inteligência Artificial e Criptografia do sistema AMÉLIA.
"""

import json
import hashlib
import os
from cryptography.fernet import Fernet
from datetime import datetime

# ===========================================================
# GERENCIAMENTO DE CRIPTOGRAFIA (MODO VERCEL)
# ===========================================================

# No Vercel, não podemos criar arquivos. Usamos a chave da variável de ambiente.
# A mesma lógica usada no database.py
FERNET_KEY = os.getenv("FERNET_KEY", "b'7_XW-3_2kM_Z6_X9J-9_XW-3_2kM_Z6_X9J-9_XW-3_2k='")
try:
    CIPHER = Fernet(FERNET_KEY.encode())
except Exception:
    # Caso a chave acima não esteja em formato válido, gera uma temporária
    CIPHER = Fernet(Fernet.generate_key())

def hash_cpf(cpf: str) -> str:
    """Cria um hash SHA-256 do CPF."""
    cpf_limpo = str(cpf).replace(".", "").replace("-", "").strip()
    return hashlib.sha256(cpf_limpo.encode()).hexdigest()

# ===========================================================
# LÓGICA DE PREDIÇÃO (SIMULADA PARA A FEIRA)
# ===========================================================

def predict_risk(data):
    """
    Simula o modelo de Machine Learning para classificação de risco.
    Em um sistema real, aqui carregaríamos um modelo .pkl do scikit-learn.
    """
    score = 0
    
    # Critérios de Urgência (Simplificado)
    if data.pain_level >= 8: score += 50
    if data.shortness_of_breath: score += 40
    if data.fever: score += 15
    if data.age > 60: score += 10
    
    # Classificação baseada no score
    if score >= 70:
        return {"color": "red", "label": "EMERGÊNCIA", "priority": 1}
    elif score >= 40:
        return {"color": "orange", "label": "MUITO URGENTE", "priority": 2}
    elif score >= 20:
        return {"color": "yellow", "label": "URGENTE", "priority": 3}
    else:
        return {"color": "green", "label": "POUCO URGENTE", "priority": 4}

# Removidas as funções antigas de save/load que usavam SQLite local
# pois agora usamos o database.py com PostgreSQL
