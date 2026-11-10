import psycopg
from psycopg.rows import dict_row
from app.config import DATABASE_URL

def connection():
    c = psycopg.connect(DATABASE_URL, row_factory=dict_row, options="-c timezone=UTC", connect_timeout=5)

    from psycopg.types import TypeInfo
    from psycopg.types.array import register_array
    from psycopg.types.string import TextLoader
    for name in ["role_type","service_type","pet_species"]:
        info = TypeInfo.fetch(c,name)
        if info:
            c.adapters.register_loader(info.oid,TextLoader)
            register_array(info,c)
    return c
