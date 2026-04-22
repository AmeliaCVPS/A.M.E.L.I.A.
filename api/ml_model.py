# database.py
"""
Camada de persistência do sistema AMÉLIA.
Usa SQLite (leve, sem servidor) + criptografia Fernet (AES-128 simétrico).

LGPD: Apenas dados necessários são armazenados.
      O CPF nunca é salvo — apenas seu hash SHA-256.
"""

import sqlite3
import json
import hashlib
import os
from cryptography.fernet import Fernet
from datetime import datetime

# ===========================================================
# GERENCIAMENTO DE CHAVE DE CRIPTOGRAFIA
# ===========================================================
# A chave Fernet é como a "senha do cofre".
# Em produção: armazene em variável de ambiente ou AWS KMS.
# NUNCA comite a chave no Git!

KEY_FILE = "secret.key"

def load_or_create_key() -> bytes:
    """Carrega a chave do arquivo ou gera uma nova."""
    if os.path.exists(KEY_FILE):
        with open(KEY_FILE, "rb") as f:
            return f.read()
    else:
        key = Fernet.generate_key()
        with open(KEY_FILE, "wb") as f:
            f.write(key)
        print("⚠️  Nova chave de criptografia gerada. Guarde o arquivo 'secret.key' com segurança!")
        return key

# Instância global do objeto de criptografia
CIPHER = Fernet(load_or_create_key())


# ===========================================================
# FUNÇÕES DE CRIPTOGRAFIA
# ===========================================================

def encrypt(data: str) -> str:
    """
    Criptografa uma string usando AES-128 (Fernet).
    Retorna o texto cifrado em base64 (seguro para armazenar).
    """
    encrypted_bytes = CIPHER.encrypt(data.encode("utf-8"))
    return encrypted_bytes.decode("utf-8")

def decrypt(token: str) -> str:
    """Descriptografa um token Fernet e retorna a string original."""
    decrypted_bytes = CIPHER.decrypt(token.encode("utf-8"))
    return decrypted_bytes.decode("utf-8")

def hash_cpf(cpf: str) -> str:
    """
    Gera um hash irreversível do CPF usando SHA-256.
    Permite identificar o paciente sem expor o dado real.
    """
    cpf_clean = "".join(filter(str.isdigit, cpf))
    return hashlib.sha256(cpf_clean.encode()).hexdigest()


# ===========================================================
# CONFIGURAÇÃO DO BANCO DE DADOS
# ===========================================================

def init_db(db_path: str = "amelia.db"):
    """Cria as tabelas do banco se ainda não existirem."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS prontuarios (
            id              TEXT PRIMARY KEY,   -- UUID único
            patient_hash    TEXT NOT NULL,      -- Hash do CPF (não o CPF real!)
            timestamp       TEXT NOT NULL,
            encrypted_data  TEXT NOT NULL,      -- JSON completo criptografado
            color           TEXT NOT NULL,      -- Verde/Amarelo/Vermelho (para relatórios)
            password        TEXT NOT NULL       -- Senha de atendimento
        )
    """)

    conn.commit()
    conn.close()
    print("✅ Banco de dados inicializado.")


def save_prontuario(prontuario: dict, cpf: str, db_path: str = "amelia.db"):
    """
    Salva um prontuário no banco, criptografando os dados sensíveis.
    
    O campo 'encrypted_data' contém o JSON completo cifrado.
    Somente o hash, timestamp, cor e senha ficam em texto claro
    (para permitir relatórios sem descriptografar tudo).
    """
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Serializa o JSON e criptografa
    json_str = json.dumps(prontuario, ensure_ascii=False)
    encrypted = encrypt(json_str)

    cursor.execute("""
        INSERT OR REPLACE INTO prontuarios
        (id, patient_hash, timestamp, encrypted_data, color, password)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (
        prontuario["id"],
        hash_cpf(cpf),
        prontuario["timestamp"],
        encrypted,
        prontuario["classification"]["color"],
        prontuario["classification"]["password"],
    ))

    conn.commit()
    conn.close()


def load_prontuario(prontuario_id: str, db_path: str = "amelia.db") -> dict:
    """Carrega e descriptografa um prontuário pelo ID."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute(
        "SELECT encrypted_data FROM prontuarios WHERE id = ?",
        (prontuario_id,)
    )
    row = cursor.fetchone()
    conn.close()

    if not row:
        return None

    decrypted_json = decrypt(row[0])
    return json.loads(decrypted_json)