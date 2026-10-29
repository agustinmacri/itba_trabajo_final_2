import os

import psycopg
from dotenv import load_dotenv


# Lee las variables del archivo .env
load_dotenv()


def get_connection():
    return psycopg.connect(
        host=os.getenv("POSTGRES_HOST", "localhost"),
        port=os.getenv("POSTGRES_PORT", "5432"),
        dbname=os.getenv("POSTGRES_DB"),
        user=os.getenv("AGENT_DB_USER"),
        password=os.getenv("AGENT_DB_PASSWORD"),
    )
