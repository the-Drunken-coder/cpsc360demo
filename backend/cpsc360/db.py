import os

import psycopg

DATABASE_URL = os.environ.get("CPSC360_DATABASE_URL", "postgresql://cpsc:cpsc@127.0.0.1:5433/cpsc360")


def connect() -> psycopg.Connection:
    return psycopg.connect(DATABASE_URL)
