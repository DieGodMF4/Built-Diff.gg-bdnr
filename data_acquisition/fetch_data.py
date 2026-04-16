"""
Adquisición de datos – Data Dragon + Meraki Analytics.
Ambas APIs públicas, sin API key.
"""

import json
import os
import sys
import time
import requests

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config


def get_latest_version():
    print("[1/5] Obteniendo versión de Data Dragon...")
    resp = requests.get(config.DDRAGON_VERSIONS_URL, timeout=15)
    resp.raise_for_status()
    v = resp.json()[0]
    print(f"       Versión: {v}")
    return v


def fetch_ddragon_champions(version):
    print("[2/5] Descargando campeones de Data Dragon...")
    url = f"{config.DDRAGON_BASE}/cdn/{version}/data/{config.DDRAGON_LANGUAGE}/champion.json"
    champ_list = requests.get(url, timeout=15).json()["data"]
    total = len(champ_list)
    print(f"       {total} campeones. Descargando detalles...")

    champions = {}
    for i, (name, _) in enumerate(champ_list.items()):
        url = f"{config.DDRAGON_BASE}/cdn/{version}/data/{config.DDRAGON_LANGUAGE}/champion/{name}.json"
        champions[name] = requests.get(url, timeout=15).json()["data"][name]
        if (i + 1) % 25 == 0:
            print(f"       ... {i + 1}/{total}")
        time.sleep(0.03)

    print(f"       ✓ {len(champions)} campeones")
    return champions


def fetch_ddragon_items(version):
    print("[3/5] Descargando items de Data Dragon...")
    url = f"{config.DDRAGON_BASE}/cdn/{version}/data/{config.DDRAGON_LANGUAGE}/item.json"
    items = requests.get(url, timeout=15).json()["data"]
    print(f"       ✓ {len(items)} items")
    return items


def fetch_meraki_champions():
    print("[4/5] Descargando campeones de Meraki Analytics (~12MB)...")
    data = requests.get(config.MERAKI_CHAMPIONS_URL, timeout=60).json()
    print(f"       ✓ {len(data)} campeones")
    return data


def fetch_meraki_items():
    print("[5/5] Descargando items de Meraki Analytics...")
    data = requests.get(config.MERAKI_ITEMS_URL, timeout=30).json()
    print(f"       ✓ {len(data)} items")
    return data


def save_raw_data(dd_c, dd_i, mk_c, mk_i):
    os.makedirs(config.DATA_DIR, exist_ok=True)
    for path, data in [(config.CHAMPIONS_RAW_DDRAGON, dd_c), (config.ITEMS_RAW_DDRAGON, dd_i),
                       (config.CHAMPIONS_RAW_MERAKI, mk_c), (config.ITEMS_RAW_MERAKI, mk_i)]:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"  ✓ {path} ({os.path.getsize(path) / 1024 / 1024:.1f} MB)")


def main():
    print("=" * 60)
    print(" Adquisición de datos – DDragon + Meraki")
    print("=" * 60)
    v = get_latest_version()
    dd_c = fetch_ddragon_champions(v)
    dd_i = fetch_ddragon_items(v)
    mk_c = fetch_meraki_champions()
    mk_i = fetch_meraki_items()
    save_raw_data(dd_c, dd_i, mk_c, mk_i)
    print("\n✓ Completado. Ejecuta: python data_acquisition/transform.py")


if __name__ == "__main__":
    main()
