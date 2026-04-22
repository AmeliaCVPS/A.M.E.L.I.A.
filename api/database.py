import os
import psycopg2
from psycopg2.extras import RealDictCursor
from cryptography.fernet import Fernet
import hashlib
import json

# Variáveis de Ambiente (Configurar no Vercel)
DATABASE_URL = os.getenv("DATABASE_URL")
FERNET_KEY = os.getenv("FERNET_KEY")
CIPHER = Fernet(FERNET_KEY.encode() if FERNET_KEY else Fernet.generate_key())

def get_connection():
    return psycopg2.connect(DATABASE_URL, sslmode='require')

def init_db():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS prontuarios (
            id TEXT PRIMARY KEY,
            patient_hash TEXT,
            timestamp TEXT,
            encrypted_data TEXT,
            color TEXT,
            password TEXT
        )
    """)
    conn.commit()
    cursor.close()
    conn.close()

def hash_cpf(cpf: str) -> str:
    return hashlib.sha256(cpf.encode()).hexdigest()

def save_prontuario(prontuario, cpf):
    conn = get_connection()
    cursor = conn.cursor()
    
    # Criptografa o JSON completo para LGPD
    json_str = json.dumps(prontuario, ensure_ascii=False)
    encrypted = CIPHER.encrypt(json_str.encode()).decode()

    cursor.execute("""
        INSERT INTO prontuarios (id, patient_hash, timestamp, encrypted_data, color, password)
        VALUES (%s, %s, %s, %s, %s, %s)
        ON CONFLICT (id) DO UPDATE SET encrypted_data = EXCLUDED.encrypted_data
    """, (
        prontuario["id"],
        hash_cpf(cpf),
        prontuario["timestamp"],
        encrypted,
        prontuario["classification"]["color"],
        prontuario["classification"]["password"]
    ))
    conn.commit()
    cursor.close()
    conn.close()
