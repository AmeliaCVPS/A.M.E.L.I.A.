import os
import psycopg2
from psycopg2.extras import RealDictCursor
from cryptography.fernet import Fernet
import hashlib

# 1. Carrega as chaves das Variáveis de Ambiente
DATABASE_URL = os.getenv("DATABASE_URL")
# Se não houver chave no ambiente, ele gera uma (apenas para teste local)
FERNET_KEY = os.getenv("FERNET_KEY", Fernet.generate_key().decode())
CIPHER = Fernet(FERNET_KEY.encode())

def hash_cpf(cpf: str) -> str:
    """
    Cria um hash SHA-256 do CPF para armazenamento seguro (LGPD).
    Transforma o CPF em uma string única e irreversível.
    """
    # Remove pontos e traços caso o frontend envie o CPF formatado
    cpf_limpo = str(cpf).replace(".", "").replace("-", "").strip()
    
    # Gera o hash
    return hashlib.sha256(cpf_limpo.encode()).hexdigest()

def get_connection():
    # Conecta ao PostgreSQL na nuvem
    return psycopg2.connect(DATABASE_URL)

def init_db():
    conn = get_connection()
    cursor = conn.cursor()
    # Sintaxe Postgres é levemente diferente do SQLite
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
    
    # Criptografa os dados
    import json
    json_str = json.dumps(prontuario, ensure_ascii=False)
    encrypted = CIPHER.encrypt(json_str.encode()).decode()

    cursor.execute("""
        INSERT INTO prontuarios (id, patient_hash, timestamp, encrypted_data, color, password)
        VALUES (%s, %s, %s, %s, %s, %s)
        ON CONFLICT (id) DO UPDATE SET encrypted_data = EXCLUDED.encrypted_data
    """, (
        prontuario["id"],
        hashlib.sha256(cpf.encode()).hexdigest(),
        prontuario["timestamp"],
        encrypted,
        prontuario["classification"]["color"],
        prontuario["classification"]["password"]
    ))
    conn.commit()
    cursor.close()
    conn.close()
