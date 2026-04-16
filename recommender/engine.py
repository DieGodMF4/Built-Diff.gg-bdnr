"""
Recomendador v3 – scoring + prioridad de compra.

La salida ahora es una lista ORDENADA de 6 items core donde:
  - El score determina QUÉ items son buenos
  - La prioridad determina en QUÉ ORDEN comprarlos

Ejemplo de salida:
  1. Manamune        (score 8.2, priority EARLY)  ← comprar primero
  2. Black Cleaver   (score 9.1, priority MID)    ← core mid-game
  3. Death's Dance   (score 7.5, priority MID)
  4. Sterak's Gage   (score 7.0, priority MID)
  5. Maw of Malmortius(score 6.8, priority MID)
  6. Serylda's Grudge(score 6.5, priority LATE)   ← comprar último
"""

import os, sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config
from database.connection import get_champions_collection, get_items_collection, test_connection

E = config.ENUM_REVERSE  # Shortcut para prints

# Qué subclases de items son compatibles con qué archetypes (usando códigos int)
ARCHETYPE_ITEM_SUBCLASSES = {
    10: [100, 101],              # burst_mage → burst_ap, sustained_ap
    11: [100, 101],              # control_mage
    12: [101, 100, 122],         # battlemage → sustained_ap, burst_ap, tank_general
    20: [110],                   # assassin_ad → lethality
    21: [100],                   # assassin_ap → burst_ap
    30: [111],                   # marksman → crit_adc
    31: [112, 111],              # on_hit_marksman
    40: [113, 120, 121],         # bruiser
    41: [113, 120, 121, 122],    # juggernaut
    42: [113, 111, 112],         # skirmisher
    50: [120, 121, 122],         # tank_vanguard
    51: [120, 121, 122],         # tank_warden
    60: [102, 100],              # enchanter → support_util, burst_ap
    61: [102, 100, 122],         # catcher
    62: [120, 121, 122, 102],    # tank_support
}

SUPPORT_ARCHETYPES = {60, 61, 62}
PRIORITY_LABELS = {1: "EARLY", 2: "MID", 3: "LATE"}


def analyze_enemy_comp(enemy_docs):
    counts = {"physical": 0, "magic": 0, "hybrid": 0}
    threats = []
    for ch in enemy_docs:
        dp_name = E["damage_profile"].get(ch.get("damage_profile", 0), "physical")
        counts[dp_name] = counts.get(dp_name, 0) + 1
        arch = ch.get("archetype", 40)
        if arch in (20, 21): threats.append("assassin")
        if arch == 10:       threats.append("burst_mage")
        if arch in (50, 51, 41): threats.append("tank")
        if arch == 30:       threats.append("adc")

    if counts.get("physical", 0) >= 3:     dom = "heavy_ad"
    elif counts.get("magic", 0) >= 3:      dom = "heavy_ap"
    else:                                    dom = "mixed"

    return {"dominant": dom, "damage_counts": counts, "threats": list(set(threats))}


def score_item(item, my_champ, enemy_comp, enemy_docs):
    W = config.WEIGHTS
    score = item.get("base_weight", 1.0) * W["base"]
    bd = {"base": round(score, 2)}

    my_arch   = my_champ.get("archetype", 40)
    my_dp     = my_champ.get("damage_profile", 0)
    my_sw     = my_champ.get("stat_weights", {})
    my_mana   = my_champ.get("mana_need", 0)
    my_intensity = my_champ.get("damage_intensity", "medium")

    i_sub     = item.get("subclass", 131)
    i_type    = item.get("item_type", 4)
    i_stats   = item.get("stats_internal", {})
    i_counters= set(item.get("counters", []))
    i_effects = set(item.get("effects", []))

    # ── 1: Stat weights match ──
    if my_sw and i_stats:
        wsum = sum(my_sw.get(s, 0) for s in i_stats)
        if wsum > 0:
            avg = wsum / len(i_stats)
            bonus = W["stat_weight_match"] * avg
            score += bonus
            bd["stat_weights"] = round(bonus, 2)

    # ── 2: Subclass match ──
    compat = ARCHETYPE_ITEM_SUBCLASSES.get(my_arch, [])
    if i_sub in compat:
        score += W["subclass_bonus"]
        bd["subclass"] = W["subclass_bonus"]

    # ── 3: Damage type synergy ──
    dp_name = E["damage_profile"].get(my_dp, "physical")
    type_name = E["item_type"].get(i_type, "utility")
    match = ((dp_name == "physical" and type_name == "ad") or
             (dp_name == "magic" and type_name == "ap") or
             (dp_name == "hybrid" and type_name in ("ad", "ap")))
    if match:
        score += W["synergy_tag"]
        bd["damage_syn"] = W["synergy_tag"]

    # ── 4: Mana bonus ──
    if item.get("is_mana_item") and my_mana > 0:
        b = W["mana_bonus"] * my_mana
        score += b
        bd["mana"] = round(b, 2)

    # ── 5: Counter enemies ──
    cbonus = 0
    n_en = max(len(enemy_docs), 1)
    for en in enemy_docs:
        en_weak = set(en.get("weaknesses", []))
        en_dp = en.get("damage_profile", 0)
        if i_counters & en_weak:
            cbonus += W["counter_champion"] / n_en
        if en_dp == 0 and 0 in i_counters:  # physical → ad_champions counter
            cbonus += W["counter_champion"] / n_en
        elif en_dp == 1 and 1 in i_counters:  # magic → ap_champions counter
            cbonus += W["counter_champion"] / n_en
        # grievous wounds
        if 0 in i_effects and 5 in en_weak:  # grievous_wounds effect vs grievous_countered
            cbonus += W["counter_champion"] / n_en
    if cbonus > 0:
        score += cbonus
        bd["counter_champs"] = round(cbonus, 2)

    # ── 6: Counter comp ──
    dom = enemy_comp.get("dominant", "mixed")
    comp_b = 0
    if dom == "heavy_ad" and 0 in i_counters:   comp_b = W["counter_comp_type"]
    elif dom == "heavy_ap" and 1 in i_counters:  comp_b = W["counter_comp_type"]
    if comp_b > 0:
        score += comp_b
        bd["counter_comp"] = round(comp_b, 2)

    # ── 7: Anti-synergy ──
    has_counter = cbonus > 0 or comp_b > 0

    if dp_name == "physical" and type_name == "ap" and not has_counter:
        score += W["anti_synergy"]; bd["anti_syn"] = W["anti_synergy"]
    elif dp_name == "magic" and type_name == "ad" and not has_counter:
        score += W["anti_synergy"]; bd["anti_syn"] = W["anti_synergy"]

    if item.get("is_support_item") and my_arch not in SUPPORT_ARCHETYPES:
        score += W["anti_synergy"]; bd["anti_support"] = W["anti_synergy"]

    if item.get("is_tear") and my_mana < 0.3:
        score += W["anti_synergy"]; bd["anti_tear"] = W["anti_synergy"]

    # Campeones de damage_intensity high no deben hacerse build full tank
    # (evita que Jayce/Akali/Zed se vayan a tank vs heavy_ad)
    if my_intensity == "high" and i_sub in (120, 121):  # tank_armor, tank_mr
        if cbonus < 1.0:
            score += W["anti_synergy"]
            bd["anti_full_tank"] = W["anti_synergy"]

    return round(score, 3), bd


def recommend(my_name, ally_names, enemy_names):
    cc = get_champions_collection()
    ic = get_items_collection()

    def find_champ(name):
        return (cc.find_one({"champion_id": name}) or
                cc.find_one({"champion_id": {"$regex": f"^{name}$", "$options": "i"}}) or
                cc.find_one({"name": {"$regex": f"^{name}$", "$options": "i"}}))

    my = find_champ(my_name)
    if not my:
        return {"error": f"Campeón '{my_name}' no encontrado."}

    enemies = [d for n in enemy_names if (d := find_champ(n))]
    comp = analyze_enemy_comp(enemies)

    scored = []
    for item in ic.find({}):
        s, bd = score_item(item, my, comp, enemies)
        scored.append({
            "name": item["name"], "item_id": item.get("item_id"),
            "subclass": item.get("subclass"), "item_type": item.get("item_type"),
            "gold": item.get("gold", 0), "priority": item.get("priority", 2),
            "score": s, "breakdown": bd, "effects": item.get("effects", []),
        })

    # Ordenar por score descendente para seleccionar los mejores
    scored.sort(key=lambda x: x["score"], reverse=True)

    # Seleccionar top N como core
    core = scored[:config.NUM_CORE_ITEMS]

    # REORDENAR core por prioridad (1→2→3) manteniendo score como desempate
    core.sort(key=lambda x: (x["priority"], -x["score"]))

    # Situacionales: los siguientes con score suficiente
    situational = [
        i for i in scored[config.NUM_CORE_ITEMS:]
        if i["score"] >= config.SCORE_THRESHOLD_SITUATIONAL
    ][:config.NUM_SITUATIONAL_ITEMS]

    return {
        "champion": {
            "name": my["name"],
            "archetype": my.get("archetype"),
            "damage_profile": my.get("damage_profile"),
            "stat_weights": my.get("stat_weights"),
            "mana_need": my.get("mana_need"),
            "roles": my.get("roles"),
        },
        "enemy_analysis": comp,
        "core_items": core,
        "situational_items": situational,
    }


def print_result(r):
    if "error" in r:
        print(f"\nERROR: {r['error']}")
        return

    c = r["champion"]
    arch = E["archetype"].get(c["archetype"], "?")
    dp = E["damage_profile"].get(c["damage_profile"], "?")
    intensity = c.get("damage_intensity", "?")

    print(f"\n{'=' * 70}")
    print(f"  CAMPEON: {c['name']}")
    print(f"  Archetype: {arch}")
    print(f"  Perfil de dano: {dp} (intensidad: {intensity})")
    print(f"  Necesidad de mana: {c.get('mana_need', '?')}")

    sw = c.get("stat_weights", {})
    top = sorted(sw.items(), key=lambda x: -x[1])[:5]
    print(f"  Stats clave: {', '.join(f'{s}={w}' for s, w in top)}")
    print(f"{'=' * 70}")

    ea = r["enemy_analysis"]
    print(f"\n  Composicion enemiga: {ea['dominant']}")
    dc = ea["damage_counts"]
    print(f"    Physical: {dc.get('physical',0)} | Magic: {dc.get('magic',0)} | "
          f"Hybrid: {dc.get('hybrid',0)}")

    for section, title in [("core_items", "BUILD RECOMENDADA (orden de compra)"),
                           ("situational_items", "ITEMS SITUACIONALES")]:
        items = r[section]
        if not items:
            continue
        print(f"\n{'-' * 70}")
        print(f"  {title}")
        print(f"{'-' * 70}")
        for i, item in enumerate(items, 1):
            prio = PRIORITY_LABELS.get(item["priority"], "?")
            sub = E["subclass"].get(item.get("subclass"), "?")
            print(f"\n  {i}. {item['name']}")
            print(f"     Score: {item['score']:.2f}  |  Priority: {prio}  |  "
                  f"Subclass: {sub}  |  Coste: {item['gold']} oro")
            bd = item["breakdown"]
            parts = []
            if "stat_weights" in bd:    parts.append(f"stats +{bd['stat_weights']:.1f}")
            if "subclass" in bd:        parts.append(f"subclass +{bd['subclass']:.1f}")
            if "damage_syn" in bd:      parts.append(f"dano +{bd['damage_syn']:.1f}")
            if "mana" in bd:            parts.append(f"mana +{bd['mana']:.1f}")
            if "counter_champs" in bd:  parts.append(f"counter +{bd['counter_champs']:.1f}")
            if "counter_comp" in bd:    parts.append(f"vs comp +{bd['counter_comp']:.1f}")
            if "anti_syn" in bd:        parts.append(f"penalizacion {bd['anti_syn']:.1f}")
            if "anti_full_tank" in bd:  parts.append(f"penalizacion full-tank {bd['anti_full_tank']:.1f}")
            if parts:
                print(f"     {'  |  '.join(parts)}")

    print(f"\n{'=' * 70}\n")


def demo():
    demos = [
        ("Jayce (bruiser, necesita Tear) vs comp mixta",
         "Jayce", ["Thresh","Graves","Orianna","Gnar"],
         ["Zed","LeeSin","Ahri","Caitlyn","Leona"]),
        ("Nami (enchanter) vs heavy AD",
         "Nami", ["Jinx","Graves","Orianna","Gnar"],
         ["Zed","LeeSin","Talon","Draven","Nautilus"]),
        ("Jinx (marksman) vs comp con tanks",
         "Jinx", ["Thresh","Graves","Orianna","Gnar"],
         ["Malphite","Sejuani","Swain","Caitlyn","Leona"]),
    ]
    for title, champ, allies, enemies in demos:
        print(f"\nDEMO: {title}")
        print(f"  Campeon: {champ}")
        print(f"  Aliados: {', '.join(allies)}")
        print(f"  Enemigos: {', '.join(enemies)}")
        print_result(recommend(champ, allies, enemies))

def interactive():
    print("=" * 65)
    print(" LoL Draft Item Recommender v3")
    print("=" * 65)
    champ = input("\nTu campeón:\n  > ").strip()
    allies = [a.strip() for a in input("Aliados (coma):\n  > ").split(",") if a.strip()]
    enemies = [e.strip() for e in input("Enemigos (coma):\n  > ").split(",") if e.strip()]
    print_result(recommend(champ, allies, enemies))


if __name__ == "__main__":
    if not test_connection(): sys.exit(1)
    demo() if "--demo" in sys.argv else interactive()
