

from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import uuid
import json
from datetime import datetime, timezone
from typing import Optional

# Importa nossos módulos
from database import init_db, save_prontuario, hash_cpf
from ml_model import predict_risk

# ===========================================================
# INICIALIZAÇÃO
# ===========================================================

app = FastAPI(
    title="A.M.E.L.I.A API",
    description="Sistema de Triagem Médica com Inteligência Artificial",
    version="1.0.0"
)

# CORS: permite que o frontend (em outro domínio/porta) acesse a API
# Em produção: substitua "*" pelo domínio real do frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Inicializa o banco ao subir o servidor
@app.on_event("startup")
async def startup():
    init_db()
    print("🚀 AMÉLIA API iniciada!")


# ===========================================================
# SCHEMAS (CONTRATOS DE DADOS)
# ===========================================================
# Pydantic valida automaticamente os dados recebidos.
# Se o frontend mandar um campo errado, a API rejeita com erro claro.

class SymptomsInput(BaseModel):
    #"""Dados enviados pelo frontend após a triagem por chat/voz."""
    cpf: str = Field(..., description="CPF do paciente (será hasheado, nunca armazenado)")
    age: int = Field(..., ge=0, le=120, description="Idade em anos")
    sex: str = Field(..., pattern="^[MF]$")
    pain_level: int = Field(..., ge=1, le=10)
    fever: bool = False
    shortness_of_breath: bool = False
    duration_hours: int = Field(..., ge=1)
    description: str = Field(..., max_length=1000)
    temperature: Optional[float] = None
    password_prefix: Optional[str] = "A"  # Prefixo da senha de triagem


class TranscriptionInput(BaseModel):
    #"""Texto transcrito do áudio do paciente."""
    text: str
    cpf: str
    age: int
    sex: str = "M"


# ===========================================================
# CONTADOR DE SENHAS (em produção: use Redis ou banco)
# ===========================================================
_password_counters = {"red": 0, "yellow": 0, "green": 0}

def generate_triage_password(color: str) -> str:
    #"""Gera senha de triagem sequencial por cor."""
    prefix_map = {"red": "V", "yellow": "A", "green": "V"}
    # Vermelho=V (Vermelho), Amarelo=A, Verde=V (Verde)
    # Na prática, use prefixos distintos!
    prefixes = {"red": "VM", "yellow": "AM", "green": "VD"}
    _password_counters[color] += 1
    number = str(_password_counters[color]).zfill(3)
    return f"{prefixes[color]}{number}"


# ===========================================================
# ROTAS PRINCIPAIS
# ===========================================================

@app.get("/health")
async def health_check():
    #"""Rota de verificação — confirma que a API está online."""
    return {"status": "online", "system": "A.M.E.L.I.A", "version": "1.0.0"}


@app.post("/triage/classify")
async def classify_patient(data: SymptomsInput):
    # ROTA PRINCIPAL DE TRIAGEM
    
    #Fluxo:
   # 1. Recebe sintomas do paciente
   # 2. Roda o modelo de ML
   # 3. Gera prontuário estruturado
   # 4. Criptografa e salva no banco
   # 5. Retorna resultado para o frontend
    
    
    # PASSO 1: Classificar com ML
    risk = predict_risk({
        "pain_level":          data.pain_level,
        "fever":               data.fever,
        "shortness_of_breath": data.shortness_of_breath,
        "duration_hours":      data.duration_hours,
        "age":                 data.age,
    })

    # PASSO 2: Gerar senha de triagem
    password = generate_triage_password(risk["color"])

    # PASSO 3: Montar prontuário completo
    prontuario = {
        "id":        str(uuid.uuid4()),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "patient": {
            "id_hash": hash_cpf(data.cpf),   # CPF nunca é salvo!
            "age":     data.age,
            "sex":     data.sex,
        },
        "symptoms": {
            "description":       data.description,
            "pain_level":        data.pain_level,
            "fever":             data.fever,
            "shortness_of_breath": data.shortness_of_breath,
            "duration_hours":    data.duration_hours,
        },
        "vital_signs": {
            "temperature":        data.temperature,
            "heart_rate":         None,
            "blood_pressure":     None,
            "oxygen_saturation":  None,
        },
        "classification": {
            "color":      risk["color"],
            "priority":   risk["priority"],
            "confidence": risk["confidence"],
            "password":   password,
        }
    }

    # PASSO 4: Salvar criptografado
    save_prontuario(prontuario, data.cpf)

    # PASSO 5: Retornar ao frontend (sem dados sensíveis!)
    return {
        "prontuario_id": prontuario["id"],
        "password":      password,
        "classification": {
            "color":       risk["color"],
            "priority":    risk["priority"],
            "explanation": risk["explanation"],
            "confidence":  risk["confidence"],
        },
        "message": f"Triagem concluída. Sua senha é {password}."
    }


@app.post("/triage/from-text")
async def triage_from_text(data: TranscriptionInput):
    
   # Recebe texto (transcrito do áudio pelo frontend)
    #e extrai sintomas usando análise simples.
    
    #Em produção: use um LLM (Claude/GPT) para extração mais robusta.
  
    text = data.text.lower()

    # Extração de sintomas por palavras-chave
    # Em produção: substitua por NLP ou chamada à API Claude
    symptoms = SymptomsInput(
        cpf=data.cpf,
        age=data.age,
        sex=data.sex,
        description=data.text,
        pain_level=_extract_pain_level(text),
        fever="febre" in text or "temperatura" in text,
        shortness_of_breath=any(w in text for w in [
            "falta de ar", "respirar", "ofegar", "sufocando"
        ]),
        duration_hours=_extract_duration(text),
    )

    return await classify_patient(symptoms)


def _extract_pain_level(text: str) -> int:
   # """Extrai nível de dor do texto (busca por números 1-10)."""
    import re
    matches = re.findall(r'\b([1-9]|10)\b', text)
    if matches:
        return int(matches[0])
    # Palavras-chave de intensidade
    if any(w in text for w in ["insuportável", "horrível", "muito forte"]):
        return 9
    if any(w in text for w in ["moderada", "média"]):
        return 5
    return 3  # Padrão: dor leve

def _extract_duration(text: str) -> int:
   # """Extrai duração em horas do texto."""
    import re
    # Procura padrões como "2 dias", "3 horas", "1 semana"
    if m := re.search(r'(\d+)\s*dia', text):
        return int(m.group(1)) * 24
    if m := re.search(r'(\d+)\s*hora', text):
        return int(m.group(1))
    if m := re.search(r'(\d+)\s*semana', text):
        return int(m.group(1)) * 168
    return 24  # Padrão: 1 dia


# Para rodar: uvicorn main:app --reload --port 8000
