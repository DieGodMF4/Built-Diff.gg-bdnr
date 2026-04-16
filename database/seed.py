"""Carga datos procesados en MongoDB + colección de enums."""
import json, os, sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config
from database.connection import get_db, get_champions_collection, get_items_collection, test_connection


def seed_champions():
    print("[2/5] Insertando campeones...")
    with open(config.CHAMPIONS_PROCESSED, "r", encoding="utf-8") as f:
        data = json.load(f)
    col = get_champions_collection()
    col.delete_many({})
    result = col.insert_many(data)
    print(f"       ✓ {len(result.inserted_ids)} campeones")
    return len(result.inserted_ids)


def seed_items():
    print("[3/5] Insertando items...")
    with open(config.ITEMS_PROCESSED, "r", encoding="utf-8") as f:
        data = json.load(f)
    col = get_items_collection()
    col.delete_many({})
    result = col.insert_many(data)
    print(f"       ✓ {len(result.inserted_ids)} items")
    return len(result.inserted_ids)


def seed_enums():
    """Inserta documento de referencia con mapeos int→string (auto-documentación)."""
    print("[4/5] Insertando documento de enums...")
    db = get_db()
    db.enums.delete_many({})
    db.enums.insert_one({
        "_id": "enums",
        "damage_profile": {str(v): k for k, v in config.ENUM_DAMAGE_PROFILE.items()},
        "archetype":      {str(v): k for k, v in config.ENUM_ARCHETYPE.items()},
        "item_type":      {str(v): k for k, v in config.ENUM_ITEM_TYPE.items()},
        "subclass":       {str(v): k for k, v in config.ENUM_SUBCLASS.items()},
        "weakness":       {str(v): k for k, v in config.ENUM_WEAKNESS.items()},
        "counter":        {str(v): k for k, v in config.ENUM_COUNTER.items()},
        "effect":         {str(v): k for k, v in config.ENUM_EFFECT.items()},
        "priority":       {"1": "EARLY", "2": "MID", "3": "LATE"},
    })
    print("       ✓ Enums insertados")


def create_indexes():
    print("[5/5] Creando índices...")
    c = get_champions_collection()
    c.create_index("champion_id", unique=True)
    c.create_index("archetype")
    c.create_index("damage_profile")

    i = get_items_collection()
    i.create_index("item_type")
    i.create_index("subclass")
    i.create_index("counters")
    i.create_index("priority")
    print("       ✓ Índices creados")


def main():
    print("=" * 60)
    print(" MongoDB – Seed v3")
    print("=" * 60)

    print("[1/5] Verificando conexión...")
    if not test_connection():
        sys.exit(1)

    for p in [config.CHAMPIONS_PROCESSED, config.ITEMS_PROCESSED]:
        if not os.path.exists(p):
            print(f"✗ No encontrado: {p}")
            print("  Ejecuta primero: python data_acquisition/transform.py")
            sys.exit(1)

    nc = seed_champions()
    ni = seed_items()
    seed_enums()
    create_indexes()

    print(f"\n✓ BD '{config.MONGO_DB}' cargada: {nc} campeones, {ni} items, 1 enums")
    print("Ejecuta: python recommender/engine.py --demo")


if __name__ == "__main__":
    main()
