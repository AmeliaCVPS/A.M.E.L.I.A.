import os
import psycopg2
from psycopg2.extras import RealDictCursor
from cryptography.fernet import Fernet
import hashlib
import json

# 1. Carrega as chaves das Variáveis de Ambiente
DATABASE_URL = os.getenv("DATABASE_URL")
FERNET_KEY = os.getenv("FERNET_KEY", Fernet.generate_key().decode())
CIPHER = Fernet(FERNET_KEY.encode())

def get_connection():
    # Conecta ao PostgreSQL na nuvem
    return psycopg2.connect(DATABASE_URL)

def hash_cpf(cpf: str) -> str:
    """
    Cria um hash SHA-256 do CPF para armazenamento seguro (LGPD).
    Remove caracteres especiais antes de gerar o hash.
    """
    cpf_limpo = str(cpf).replace(".", "").replace("-", "").strip()
    return hashlib.sha256(cpf_limpo.encode()).hexdigest()

def init_db():
    conn = get_connection()
    cursor = conn.cursor()
    # Cria a tabela de prontuários se não existir
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

def save_prontuario(prontuario, cpf):
    conn = get_connection()
    cursor = conn.cursor()
    
    # Criptografa os dados sensíveis (o JSON completo)
    json_str = json.dumps(prontuario, ensure_ascii=False)
    encrypted = CIPHER.encrypt(json_str.encode()).decode()

    # Salva no banco de dados
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
