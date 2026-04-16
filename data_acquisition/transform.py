"""
Transformación v3 – DDragon + Meraki → documentos MongoDB con enums + prioridad.

Incluye:
  - Ratios de Meraki para stat_weights individuales por campeón
  - Heurísticas corregidas (marksman threshold, mage+support, hybrid)
  - Detección de mana_need robusta
  - Codificación entera de campos categóricos
  - Sistema de prioridad de items (1=early, 2=mid, 3=late)
"""

import json
import os
import re
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config


# ═══════════════════════════════════════════════════════════════
# CAMPEONES
# ═══════════════════════════════════════════════════════════════

def extract_spell_ratios(meraki_champ):
    """Suma los ratios AP/AD/HP de todas las habilidades (Meraki)."""
    ratios = defaultdict(float)
    for slot_name, spell_list in meraki_champ.get("abilities", {}).items():
        if not isinstance(spell_list, list):
            continue
        for spell in spell_list:
            for effect in (spell.get("effects") or []):
                for level_data in (effect.get("leveling") or []):
                    for mod in (level_data.get("modifiers") or []):
                        units = mod.get("units", [])
                        values = mod.get("values", [])
                        if not units or not values:
                            continue
                        max_val = max(values) if values else 0
                        for unit in units:
                            u = (unit or "").lower()
                            if "ap" in u:
                                ratios["ap"] += max_val
                            elif "ad" in u or "attack" in u:
                                ratios["ad"] += max_val
                            elif "hp" in u or "health" in u:
                                ratios["hp"] += max_val
    return dict(ratios)


def compute_stat_weights(ratios, archetype_str):
    """Calcula stat_weights combinando ratios de Meraki + defaults del archetype."""
    defaults = config.ARCHETYPE_DEFAULT_WEIGHTS.get(archetype_str, {"ad": 0.5})
    if not ratios:
        return defaults.copy()
    max_r = max(ratios.values()) if ratios else 1.0
    if max_r == 0:
        return defaults.copy()
    weights = defaults.copy()
    if "ap" in ratios:
        weights["ap"] = max(weights.get("ap", 0), round(min(ratios["ap"] / max_r, 1.0), 2))
    if "ad" in ratios:
        weights["ad"] = max(weights.get("ad", 0), round(min(ratios["ad"] / max_r, 1.0), 2))
    if "hp" in ratios and ratios["hp"] > 0.5:
        weights["hp"] = max(weights.get("hp", 0), 0.6)
    return weights


def compute_mana_need(dd, mk):
    """0.0 = no usa maná, 1.0 = necesita Tear."""
    champ_id = dd.get("id", "")
    if champ_id in config.MANA_NEED_OVERRIDES:
        return config.MANA_NEED_OVERRIDES[champ_id]

    resource = (mk.get("resource", "") if mk else "").upper()
    partype = dd.get("partype", "Mana")

    no_mana = {"NONE", "FURY", "RAGE", "ENERGY", "HEAT", "FEROCITY",
               "SHIELD", "BLOODTHIRST", "GRIT", "COURAGE", "FLOW",
               "CRIMSON_RUSH", "CRIMSON RUSH", "BLOOD_WELL", "BLOOD WELL"}
    no_mana_pt = {"None", "Fury", "Rage", "Energy", "Heat", "Ferocity",
                  "Shield", "Bloodthirst", "Grit", "Courage", "Flow",
                  "Crimson Rush", "Blood Well"}

    if resource in no_mana or partype in no_mana_pt:
        return 0.0

    mp_base = dd.get("stats", {}).get("mp", 300)
    if mp_base == 0:
        return 0.0

    if mp_base > 500: return 0.2
    if mp_base > 400: return 0.3
    if mp_base > 300: return 0.4
    if mp_base > 200: return 0.5
    return 0.6


def determine_damage_profile(dd, mk, ratios):
    """
    Mejora v3.1: clasifica por MAGNITUD de los ratios.
    Campeones con ratios totales bajos (Leona, Braum) ya no se mezclan
    con damage dealers reales (Akali, Zed).
    """
    total_ratios = ratios.get("ap", 0) + ratios.get("ad", 0)

    if total_ratios < 2.0:
        if mk:
            adaptive = mk.get("adaptiveType", "")
            if adaptive == "MAGIC_DAMAGE":
                return "magic"
            elif adaptive == "PHYSICAL_DAMAGE":
                return "physical"
        return "physical"

    if mk:
        adaptive = mk.get("adaptiveType", "")
        if adaptive == "MAGIC_DAMAGE":
            if ratios.get("ad", 0) > ratios.get("ap", 0) * 0.7 and ratios.get("ad", 0) > 2.0:
                return "hybrid"
            return "magic"
        elif adaptive == "PHYSICAL_DAMAGE":
            if ratios.get("ap", 0) > ratios.get("ad", 0) * 0.7 and ratios.get("ap", 0) > 2.0:
                return "hybrid"
            return "physical"

    ap, ad = ratios.get("ap", 0), ratios.get("ad", 0)
    if ap > 0 and ad > 0:
        r = ap / (ap + ad)
        if r > 0.7: return "magic"
        elif r < 0.3: return "physical"
        else: return "hybrid"
    if ap > 0: return "magic"
    if ad > 0: return "physical"

    tags = dd.get("tags", [])
    if "Mage" in tags: return "magic"
    return "physical"


def determine_archetype(dd, mk, damage_profile, ratios):
    """Archetype con overrides → heurística corregida."""
    champ_id = dd.get("id", "")
    if champ_id in config.ARCHETYPE_OVERRIDES:
        return config.ARCHETYPE_OVERRIDES[champ_id]

    tags = dd.get("tags", [])
    info = dd.get("info", {})
    attack, defense, magic = info.get("attack", 5), info.get("defense", 5), info.get("magic", 5)

    if "Mage" in tags and damage_profile == "magic":
        if "Assassin" in tags: return "assassin_ap"
        if "Support" in tags:
            return "enchanter" if magic <= 5 else "burst_mage"
        if defense >= 5 or "Fighter" in tags: return "battlemage"
        if magic >= 8: return "burst_mage"
        return "control_mage"

    if "Assassin" in tags:
        return "assassin_ap" if damage_profile == "magic" else "assassin_ad"

    if "Marksman" in tags:
        ap_r, ad_r = ratios.get("ap", 0), ratios.get("ad", 0)
        if ap_r > ad_r and ap_r > 3.0: return "on_hit_marksman"
        return "marksman"

    if "Fighter" in tags:
        if "Tank" in tags: return "juggernaut" if defense >= 7 else "bruiser"
        return "skirmisher" if attack >= 7 else "bruiser"

    if "Tank" in tags:
        if "Support" in tags: return "tank_support"
        if "Fighter" in tags: return "tank_vanguard"
        return "tank_warden" if defense >= 8 else "tank_vanguard"

    if "Support" in tags:
        return "enchanter" if damage_profile == "magic" else "catcher"

    return "burst_mage" if damage_profile == "magic" else "bruiser"


def determine_weaknesses(damage_profile, archetype_str):
    w = []
    squishies = {"burst_mage", "control_mage", "assassin_ad", "assassin_ap",
                 "marksman", "on_hit_marksman", "enchanter"}
    if archetype_str in squishies:
        w += ["burst_vulnerable", "cc_vulnerable"]
    if damage_profile == "magic":   w.append("magic_resist_countered")
    elif damage_profile == "physical": w.append("armor_countered")
    tanks = {"tank_vanguard", "tank_warden", "tank_support", "juggernaut"}
    if archetype_str in tanks:
        w += ["percent_hp_countered", "grievous_wounds_countered"]
    if archetype_str in ("juggernaut", "battlemage", "skirmisher"):
        w.append("grievous_wounds_countered")
    return list(set(w))


def transform_champion(name, dd, mk):
    ratios = extract_spell_ratios(mk) if mk else {}
    dp = determine_damage_profile(dd, mk, ratios)
    # Intensidad de dano: diferencia damage dealers reales (Akali, Zed)
    # de campeones con poco daño (Leona, Braum)
    total_ratios = ratios.get("ap", 0) + ratios.get("ad", 0)
    if total_ratios >= 5.0:
        damage_intensity = "high"
    elif total_ratios >= 2.5:
        damage_intensity = "medium"
    else:
        damage_intensity = "low"

    arch = determine_archetype(dd, mk, dp, ratios)
    sw = compute_stat_weights(ratios, arch)
    mn = compute_mana_need(dd, mk)
    weak = determine_weaknesses(dp, arch)
    stats = dd.get("stats", {})

    return {
        "name": dd.get("name", name),
        "champion_id": dd.get("id", name),
        "roles": dd.get("tags", []),
        "damage_profile": config.ENUM_DAMAGE_PROFILE.get(dp, 0),
        "archetype": config.ENUM_ARCHETYPE.get(arch, 40),
        "stat_weights": sw,
        "mana_need": round(mn, 2),
        "weaknesses": [config.ENUM_WEAKNESS[w] for w in weak if w in config.ENUM_WEAKNESS],
        "base_stats": {
            "hp": stats.get("hp", 0), "mp": stats.get("mp", 0),
            "armor": stats.get("armor", 0), "spellblock": stats.get("spellblock", 0),
            "attackdamage": stats.get("attackdamage", 0),
            "attackspeed": stats.get("attackspeedoffset", 0),
            "movespeed": stats.get("movespeed", 0), "attackrange": stats.get("attackrange", 0),
        },
        "spell_ratios": {k: round(v, 2) for k, v in ratios.items()},
        "info": dd.get("info", {}),
        "resource": (mk.get("resource", dd.get("partype", "Mana")) if mk
                     else dd.get("partype", "Mana")),
        # Guardamos strings originales para debug
        "damage_intensity": damage_intensity,
        "_debug_dp": dp,
        "_debug_arch": arch,
    }


# ═══════════════════════════════════════════════════════════════
# ITEMS
# ═══════════════════════════════════════════════════════════════

def classify_item_subclass(name, stats, tags, desc):
    desc_lower = desc.lower()
    if name in config.KNOWN_SUPPORT_ITEMS: return "support_util"
    if name in config.KNOWN_BRUISER_ITEMS: return "bruiser_ad"
    if name in config.KNOWN_LETHALITY_ITEMS: return "lethality"
    if name in config.KNOWN_TEAR_ITEMS: return "mana_item"
    if "heal and shield" in desc_lower or "heal & shield" in desc_lower: return "support_util"
    if "lethality" in desc_lower: return "lethality"

    has_ap = stats.get("FlatMagicDamageMod", 0) > 0
    has_ad = stats.get("FlatPhysicalDamageMod", 0) > 0
    has_crit = stats.get("FlatCritChanceMod", 0) > 0
    has_as = stats.get("PercentAttackSpeedMod", 0) > 0
    has_hp = stats.get("FlatHPPoolMod", 0) > 0
    has_armor = stats.get("FlatArmorMod", 0) > 0
    has_mr = stats.get("FlatSpellBlockMod", 0) > 0
    has_mana = stats.get("FlatMPPoolMod", 0) > 0

    if has_crit: return "crit_adc"
    if has_as and not has_crit and not has_ad: return "on_hit"
    if has_ad and has_hp: return "bruiser_ad"
    if has_ad and not has_hp: return "lethality"
    if has_ap:
        return "sustained_ap" if (has_hp and not has_mana) else "burst_ap"
    if has_armor and has_mr: return "tank_general"
    if has_armor: return "tank_armor"
    if has_mr: return "tank_mr"
    if has_mana and not has_ap and not has_ad: return "mana_item"
    return "utility"


def classify_item_type_broad(subclass):
    m = {"burst_ap": "ap", "sustained_ap": "ap", "support_util": "support",
         "lethality": "ad", "crit_adc": "ad", "on_hit": "ad", "bruiser_ad": "ad",
         "tank_armor": "tank", "tank_mr": "tank", "tank_general": "tank",
         "mana_item": "utility", "utility": "utility"}
    return m.get(subclass, "utility")


def extract_effects(desc):
    effects = []
    clean = re.sub(r"<[^>]+>", " ", desc).lower()
    kw = {"grievous wounds": "grievous_wounds", "shield": "shield", "slow": "slow",
          "tenacity": "tenacity", "lethality": "lethality",
          "armor penetration": "armor_penetration", "magic penetration": "magic_penetration",
          "omnivamp": "sustain", "life steal": "sustain",
          "heal and shield": "heal_shield_power", "ability haste": "ability_haste"}
    for keyword, effect in kw.items():
        if keyword in clean:
            effects.append(effect)
    return effects


def determine_counters(subclass, stats, effects):
    c = []
    if stats.get("FlatArmorMod", 0) > 0: c.append("ad_champions")
    if stats.get("FlatSpellBlockMod", 0) > 0: c.append("ap_champions")
    if "grievous_wounds" in effects: c.append("healing_champions")
    if "armor_penetration" in effects or "lethality" in effects: c.append("armor_stacking")
    if "magic_penetration" in effects: c.append("mr_stacking")
    return c


def determine_priority(name, subclass_code, gold):
    """
    Calcula la prioridad de compra de un item (1=early, 2=mid, 3=late).

    Cascada:
      1. Override manual por nombre → máxima precisión
      2. Default por subclass → items de maná/support siempre early
      3. Heurística por coste → items muy caros tienden a late
      4. Fallback → priority 2 (mid)
    """
    # 1. Override por nombre
    if name in config.ITEM_PRIORITY_OVERRIDES:
        return config.ITEM_PRIORITY_OVERRIDES[name]

    # 2. Default por subclass
    if subclass_code in config.SUBCLASS_DEFAULT_PRIORITY:
        base = config.SUBCLASS_DEFAULT_PRIORITY[subclass_code]
        # Ajustar: items muy caros dentro de subclass early → subir a mid
        if base == 1 and gold > 3200:
            return 2
        return base

    # 3. Heurística por coste
    if gold >= 3200:
        return 3  # Caro → late
    if gold <= 2400:
        return 1  # Barato → early

    return 2  # Default: mid


def is_completed_item(item):
    gold = item.get("gold", {})
    if not gold.get("purchasable", False) or gold.get("total", 0) < 2000:
        return False
    if not item.get("maps", {}).get("11", False):
        return False
    if len(item.get("into", [])) > 0 and gold.get("total", 0) < 2500:
        return False
    return True


def transform_item(item_id, raw):
    stats = raw.get("stats", {})
    tags = raw.get("tags", [])
    desc = raw.get("description", "")
    name = raw.get("name", f"Item_{item_id}")
    gold = raw.get("gold", {}).get("total", 0)

    subclass_str = classify_item_subclass(name, stats, tags, desc)
    item_type_str = classify_item_type_broad(subclass_str)
    effects_str = extract_effects(desc)
    counters_str = determine_counters(subclass_str, stats, effects_str)

    subclass_code = config.ENUM_SUBCLASS.get(subclass_str, 131)
    priority = determine_priority(name, subclass_code, gold)

    internal_stats = {}
    for sn, v in stats.items():
        if v == 0: continue
        internal_stats[config.DDRAGON_STAT_TO_INTERNAL.get(sn, sn)] = \
            internal_stats.get(config.DDRAGON_STAT_TO_INTERNAL.get(sn, sn), 0) + v

    return {
        "item_id": item_id,
        "name": name,
        "stats": {k: v for k, v in stats.items() if v != 0},
        "stats_internal": internal_stats,
        "item_type": config.ENUM_ITEM_TYPE.get(item_type_str, 4),
        "subclass": subclass_code,
        "gold": gold,
        "tags": tags,
        "effects": [config.ENUM_EFFECT[e] for e in effects_str if e in config.ENUM_EFFECT],
        "counters": [config.ENUM_COUNTER[c] for c in counters_str if c in config.ENUM_COUNTER],
        "priority": priority,
        "is_mana_item": "mana" in internal_stats or name in config.KNOWN_TEAR_ITEMS,
        "is_tear": name in config.KNOWN_TEAR_ITEMS,
        "is_support_item": name in config.KNOWN_SUPPORT_ITEMS,
        "base_weight": 1.0,
        "description_clean": re.sub(r"<[^>]+>", "", desc).strip()[:200],
        "_debug_subclass": subclass_str,
        "_debug_type": item_type_str,
    }


# ═══════════════════════════════════════════════════════════════
# PIPELINE
# ═══════════════════════════════════════════════════════════════

def main():
    print("=" * 60)
    print(" Transformación v3 – enums + prioridad")
    print("=" * 60)

    print("[1/4] Leyendo datos crudos...")
    with open(config.CHAMPIONS_RAW_DDRAGON, "r", encoding="utf-8") as f:
        dd_champs = json.load(f)
    with open(config.ITEMS_RAW_DDRAGON, "r", encoding="utf-8") as f:
        dd_items = json.load(f)

    meraki_champs = {}
    if os.path.exists(config.CHAMPIONS_RAW_MERAKI):
        with open(config.CHAMPIONS_RAW_MERAKI, "r", encoding="utf-8") as f:
            meraki_champs = json.load(f)
        print(f"       ✓ Meraki: {len(meraki_champs)} campeones")

    print(f"       DDragon: {len(dd_champs)} campeones, {len(dd_items)} items")

    print("[2/4] Transformando campeones...")
    champs = []
    for name, dd in dd_champs.items():
        mk = meraki_champs.get(name) or meraki_champs.get(dd.get("id", name))
        champs.append(transform_champion(name, dd, mk))
    print(f"       ✓ {len(champs)} campeones")

    print("[3/4] Transformando items...")
    items = []
    seen_names = {}
    filtered = 0
    duplicates = 0
    for iid, data in dd_items.items():
        if not is_completed_item(data):
            filtered += 1
            continue
        doc = transform_item(iid, data)
        name = doc["name"]

        if name in seen_names:
            existing_idx = seen_names[name]
            existing = items[existing_idx]
            if doc["gold"] < existing["gold"]:
                items[existing_idx] = doc
            duplicates += 1
            continue

        seen_names[name] = len(items)
        items.append(doc)

    print(f"       OK {len(items)} items unicos (filtrados {filtered}, duplicados {duplicates})")

    print("[4/4] Guardando...")
    os.makedirs(config.DATA_DIR, exist_ok=True)
    with open(config.CHAMPIONS_PROCESSED, "w", encoding="utf-8") as f:
        json.dump(champs, f, ensure_ascii=False, indent=2)
    with open(config.ITEMS_PROCESSED, "w", encoding="utf-8") as f:
        json.dump(items, f, ensure_ascii=False, indent=2)

    # ── Resumen ──
    print("\n─── Archetypes ───")
    ad = defaultdict(int)
    for c in champs:
        ad[c["_debug_arch"]] += 1
    for a, n in sorted(ad.items(), key=lambda x: -x[1]):
        ex = [c["name"] for c in champs if c["_debug_arch"] == a][:3]
        print(f"  {a:<20} {n:>3}  ej: {', '.join(ex)}")

    print("\n─── Damage profile ───")
    dp = defaultdict(int)
    for c in champs:
        dp[c["_debug_dp"]] += 1
    for d, n in sorted(dp.items()):
        print(f"  {d:<12} {n:>3}")

    print("\n─── Item subclass ───")
    sd = defaultdict(int)
    for i in items:
        sd[i["_debug_subclass"]] += 1
    for s, n in sorted(sd.items(), key=lambda x: -x[1]):
        ex = [i["name"] for i in items if i["_debug_subclass"] == s][:2]
        print(f"  {s:<16} {n:>3}  ej: {', '.join(ex)}")

    print("\n─── Item priority ───")
    pd = defaultdict(int)
    for i in items:
        pd[i["priority"]] += 1
    labels = {1: "EARLY", 2: "MID", 3: "LATE"}
    for p in sorted(pd):
        ex = [i["name"] for i in items if i["priority"] == p][:3]
        print(f"  {labels.get(p, '?'):<8} ({p}): {pd[p]:>3} items  ej: {', '.join(ex)}")

    print("\n─── Mana need > 0.5 ───")
    for c in sorted([c for c in champs if c["mana_need"] > 0.5], key=lambda x: -x["mana_need"])[:10]:
        print(f"  {c['name']:<16} {c['mana_need']}")

    print("\n✓ Completado. Ejecuta: python database/seed.py")


if __name__ == "__main__":
    main()
