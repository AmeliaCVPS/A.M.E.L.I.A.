from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import uuid
from datetime import datetime, timezone
from .database import init_db, save_prontuario
from .ml_model import predict_risk, SymptomsInput

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Inicializa o banco de dados na subida da API
@app.on_event("startup")
async def startup_event():
    init_db()

@app.post("/api/classify")
async def classify_patient(data: SymptomsInput):
    try:
        # 1. Gera a classificação via ML
        result = predict_risk(data)
        
        # 2. Monta o objeto do prontuário
        prontuario = {
            "id": str(uuid.uuid4()),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "patient_info": {
                "age": data.age,
                "sex": data.sex,
                "description": data.description
            },
            "classification": result
        }
        
        # 3. Salva no banco de dados remoto (PostgreSQL)
        save_prontuario(prontuario, data.cpf)
        
        return prontuario
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/health")
def health():
    return {"status": "ok"}
