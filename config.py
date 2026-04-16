"""
Configuración global – v3 (enums + priority).

Fuentes de datos:
  1. Data Dragon (Riot): Stats base, tags → sin API key
  2. Meraki Analytics CDN: Ratios de habilidades, adaptiveType → sin API key

Mejoras acumuladas:
  v2: Clasificación multidimensional (damage_profile + archetype + stat_weights + mana_need)
  v3: Codificación entera de campos categóricos + sistema de prioridad de items
"""

# ─── Endpoints ─────────────────────────────────────────────────
DDRAGON_BASE = "https://ddragon.leagueoflegends.com"
DDRAGON_VERSIONS_URL = f"{DDRAGON_BASE}/api/versions.json"
DDRAGON_LANGUAGE = "en_US"

MERAKI_CHAMPIONS_URL = "http://cdn.merakianalytics.com/riot/lol/resources/latest/en-US/champions.json"
MERAKI_ITEMS_URL = "http://cdn.merakianalytics.com/riot/lol/resources/latest/en-US/items.json"

# ─── MongoDB ───────────────────────────────────────────────────
MONGO_URI = "mongodb://localhost:27017"
MONGO_DB = "lol_recommender"
COLLECTION_CHAMPIONS = "champions"
COLLECTION_ITEMS = "items"

# ─── Rutas locales ─────────────────────────────────────────────
DATA_DIR = "data"
CHAMPIONS_RAW_DDRAGON = f"{DATA_DIR}/champions_ddragon.json"
CHAMPIONS_RAW_MERAKI = f"{DATA_DIR}/champions_meraki.json"
ITEMS_RAW_DDRAGON = f"{DATA_DIR}/items_ddragon.json"
ITEMS_RAW_MERAKI = f"{DATA_DIR}/items_meraki.json"
CHAMPIONS_PROCESSED = f"{DATA_DIR}/champions_processed.json"
ITEMS_PROCESSED = f"{DATA_DIR}/items_processed.json"


# ═══════════════════════════════════════════════════════════════
# CODIFICACIÓN ENTERA DE CAMPOS CATEGÓRICOS
# ═══════════════════════════════════════════════════════════════
# Justificación: integers ocupan menos en BSON que strings repetidas
# y las comparaciones numéricas son más rápidas en índices.
#
# Criterio de numeración:
#   damage_profile: 0-2
#   archetype: decenas por familia (10s mages, 20s assassins, 30s marksmen,
#              40s fighters, 50s tanks, 60s supports)
#   item_type: 0-4
#   subclass: centenas (100s AP, 110s AD, 120s tank, 130s otros)
#   weakness/counter/effect: secuencial desde 0

ENUM_DAMAGE_PROFILE = {
    "physical": 0, "magic": 1, "hybrid": 2,
}

ENUM_ARCHETYPE = {
    "burst_mage": 10, "control_mage": 11, "battlemage": 12,
    "assassin_ad": 20, "assassin_ap": 21,
    "marksman": 30, "on_hit_marksman": 31,
    "bruiser": 40, "juggernaut": 41, "skirmisher": 42,
    "tank_vanguard": 50, "tank_warden": 51,
    "enchanter": 60, "catcher": 61, "tank_support": 62,
}

ENUM_ITEM_TYPE = {
    "ad": 0, "ap": 1, "tank": 2, "support": 3, "utility": 4,
}

ENUM_SUBCLASS = {
    "burst_ap": 100, "sustained_ap": 101, "support_util": 102,
    "lethality": 110, "crit_adc": 111, "on_hit": 112, "bruiser_ad": 113,
    "tank_armor": 120, "tank_mr": 121, "tank_general": 122,
    "mana_item": 130, "utility": 131,
}

ENUM_WEAKNESS = {
    "burst_vulnerable": 0, "cc_vulnerable": 1,
    "armor_countered": 2, "magic_resist_countered": 3,
    "percent_hp_countered": 4, "grievous_wounds_countered": 5,
}

ENUM_COUNTER = {
    "ad_champions": 0, "ap_champions": 1,
    "healing_champions": 2, "tank_champions": 3,
    "armor_stacking": 4, "mr_stacking": 5,
}

ENUM_EFFECT = {
    "grievous_wounds": 0, "shield": 1, "slow": 2, "tenacity": 3,
    "lethality": 4, "armor_penetration": 5, "magic_penetration": 6,
    "sustain": 7, "heal_shield_power": 8, "ability_haste": 9,
}

# Mapeos inversos (int → string) para mostrar al usuario
ENUM_REVERSE = {
    "damage_profile": {v: k for k, v in ENUM_DAMAGE_PROFILE.items()},
    "archetype":      {v: k for k, v in ENUM_ARCHETYPE.items()},
    "item_type":      {v: k for k, v in ENUM_ITEM_TYPE.items()},
    "subclass":       {v: k for k, v in ENUM_SUBCLASS.items()},
    "weakness":       {v: k for k, v in ENUM_WEAKNESS.items()},
    "counter":        {v: k for k, v in ENUM_COUNTER.items()},
    "effect":         {v: k for k, v in ENUM_EFFECT.items()},
}


# ═══════════════════════════════════════════════════════════════
# SISTEMA DE PRIORIDAD DE ITEMS
# ═══════════════════════════════════════════════════════════════
#
# Cada item tiene un campo "priority" (1-3) que indica CUÁNDO comprarlo:
#
#   1 = EARLY (comprar primero)
#       → Items de maná/Tear, Vara de las Edades, Hidras (waveclear),
#         boots tier 2, items baratos con power spike temprano
#       → Razón: estos items necesitan tiempo para stackear (Tear, RoA)
#         o dan utilidad fundamental desde el minuto 1 (waveclear, maná)
#
#   2 = MID (core de mid-game, el grueso de la build)
#       → La mayoría de items ofensivos y defensivos principales
#       → Es el default para items sin clasificación especial
#
#   3 = LATE (comprar último)
#       → Items multiplicadores caros (Rabadon, IE con passive de crit)
#       → Items de penetración pura (Void Staff, Lord Dominik's)
#       → Razón: estos items escalan con los stats que ya tienes;
#         sin base previa, su efecto es menor
#
# La prioridad NO reemplaza el score, sino que lo complementa:
# entre items con score similar, se prefiere el de mayor prioridad.

PRIORITY_EARLY = 1
PRIORITY_MID = 2
PRIORITY_LATE = 3

# Items identificados por nombre → prioridad manual
ITEM_PRIORITY_OVERRIDES = {
    # ─── EARLY (priority 1): comprar primero ─────────────
    # Tear y derivados: necesitan stackearse cuanto antes
    "Tear of the Goddess":   1,
    "Manamune":              1,
    "Archangel's Staff":     1,
    "Fimbulwinter":          1,
    "Winter's Approach":     1,

    # Rod of Ages: necesita 10 min para stackear
    "Rod of Ages":           1,

    # Hidras: waveclear fundamental para laners
    "Ravenous Hydra":        1,
    "Titanic Hydra":         1,
    "Profane Hydra":         1,

    # Bruiser spikes tempranos
    "Trinity Force":         1,
    "Goredrinker":           1,
    "Stridebreaker":         1,
    "Eclipse":               1,
    "Sundered Sky":          1,

    # Items de support: se compran primero por economía
    "Shurelya's Battlesong": 1,
    "Shurelya's Requiem":    1,
    "Locket of the Iron Solari": 1,
    "Moonstone Renewer":     1,
    "Imperial Mandate":      1,
    "Echoes of Helia":       1,
    "Dream Maker":           1,
    "Celestial Opposition":  1,
    "Solstice Sleigh":       1,

    # Jungler items / early mythics
    "Hextech Rocketbelt":    1,

    # Lethality primer item
    "Youmuu's Ghostblade":   1,
    "Voltaic Cyclosword":    1,
    "Opportunity":           1,

    # ─── LATE (priority 3): comprar último ───────────────
    # Multiplicadores: necesitan base de stats para ser eficientes
    "Rabadon's Deathcap":    3,
    "Infinity Edge":         3,  # Passive requiere 60% crit

    # Penetración pura: mejor cuando el enemigo ya tiene resistencias
    "Void Staff":            3,
    "Cryptbloom":            3,
    "Lord Dominik's Regards":3,
    "Serylda's Grudge":      3,

    # Items defensivos de último recurso
    "Guardian Angel":        3,
    "Zhonya's Hourglass":    3,  # Bueno en mid pero se suele dejar para 3ro+
    "Banshee's Veil":        3,
    "Warmog's Armor":        3,  # Solo útil con mucha HP base

    # Items situacionales de late
    "Mejai's Soulstealer":   3,  # Snowball item, arriesgado
}

# Heurística de prioridad por subclass (para items sin override manual)
SUBCLASS_DEFAULT_PRIORITY = {
    # subclass_code: default_priority
    130: 1,   # mana_item → siempre early
    102: 1,   # support_util → supports compran su primer item ASAP
    113: 2,   # bruiser_ad → mid
    100: 2,   # burst_ap → mid
    101: 2,   # sustained_ap → mid
    110: 2,   # lethality → mid (excepto overrides de early)
    111: 2,   # crit_adc → mid
    112: 2,   # on_hit → mid
    120: 2,   # tank_armor → mid
    121: 2,   # tank_mr → mid
    122: 2,   # tank_general → mid
    131: 2,   # utility → mid
}

# Heurística de prioridad por coste (fallback final)
# Items muy caros tienden a ser de late game
PRIORITY_COST_THRESHOLDS = {
    "expensive": (3200, 3),  # > 3200 gold → tendencia a late (priority 3)
    "cheap":     (2400, 1),  # < 2400 gold → tendencia a early (priority 1)
}


# ═══════════════════════════════════════════════════════════════
# PESOS DEL RECOMENDADOR
# ═══════════════════════════════════════════════════════════════

WEIGHTS = {
    "base":              1.0,
    "stat_weight_match": 5.0,    # SUBIDO de 4.0: las stats del campeón pesan más
    "scaling_match":     3.0,
    "subclass_bonus":    4.0,    # SUBIDO de 2.5: el archetype manda
    "synergy_tag":       2.5,    # SUBIDO de 2.0
    "counter_champion":  1.0,    # BAJADO de 2.0: ya no aplasta al subclass
    "counter_comp_type": 1.0,    # BAJADO de 1.5
    "mana_bonus":        2.5,    # SUBIDO de 1.5: items de Tear deben aparecer
    "anti_synergy":     -3.0,    # MAS PENALIZACION
    "priority_bonus":    1.0,
}

NUM_CORE_ITEMS = 6          # Ahora 6 items ordenados por prioridad
NUM_SITUATIONAL_ITEMS = 3
SCORE_THRESHOLD_SITUATIONAL = 2.0


# ═══════════════════════════════════════════════════════════════
# STAT MAPPING
# ═══════════════════════════════════════════════════════════════

DDRAGON_STAT_TO_INTERNAL = {
    "FlatPhysicalDamageMod":   "ad",
    "PercentPhysicalDamageMod":"ad",
    "FlatMagicDamageMod":      "ap",
    "PercentMagicDamageMod":   "ap",
    "FlatHPPoolMod":           "hp",
    "PercentHPPoolMod":        "hp",
    "FlatArmorMod":            "armor",
    "PercentArmorMod":         "armor",
    "FlatSpellBlockMod":       "mr",
    "PercentSpellBlockMod":    "mr",
    "FlatCritChanceMod":       "crit",
    "PercentAttackSpeedMod":   "attack_speed",
    "FlatMPPoolMod":           "mana",
    "FlatMPRegenMod":          "mana_regen",
    "PercentMovementSpeedMod": "movespeed",
    "FlatMovementSpeedMod":    "movespeed",
    "PercentLifeStealMod":     "lifesteal",
    "FlatHPRegenMod":          "hp_regen",
}


# ═══════════════════════════════════════════════════════════════
# ARCHETYPE DEFAULTS (fallback si Meraki no da ratios)
# ═══════════════════════════════════════════════════════════════

ARCHETYPE_DEFAULT_WEIGHTS = {
    "burst_mage":       {"ap": 1.0, "magic_pen": 0.8, "mana": 0.6, "ability_haste": 0.7},
    "control_mage":     {"ap": 0.9, "mana": 0.7, "ability_haste": 0.8, "hp": 0.4},
    "battlemage":       {"ap": 0.8, "hp": 0.6, "ability_haste": 0.7, "armor": 0.3, "mr": 0.3},
    "assassin_ad":      {"ad": 1.0, "lethality": 0.9, "ability_haste": 0.5},
    "assassin_ap":      {"ap": 1.0, "magic_pen": 0.9, "ability_haste": 0.5},
    "marksman":         {"ad": 0.9, "crit": 1.0, "attack_speed": 0.8, "lifesteal": 0.5},
    "on_hit_marksman":  {"attack_speed": 1.0, "ad": 0.6, "ap": 0.3},
    "bruiser":          {"ad": 0.7, "hp": 0.8, "ability_haste": 0.6, "armor": 0.4},
    "juggernaut":       {"ad": 0.6, "hp": 1.0, "armor": 0.7, "mr": 0.5, "ability_haste": 0.5},
    "tank_vanguard":    {"hp": 1.0, "armor": 0.9, "mr": 0.8, "ability_haste": 0.6},
    "tank_warden":      {"hp": 0.9, "armor": 1.0, "mr": 0.9, "ability_haste": 0.5},
    "enchanter":        {"ability_haste": 1.0, "ap": 0.4, "mana_regen": 0.7, "hp": 0.3},
    "catcher":          {"ability_haste": 0.8, "ap": 0.5, "hp": 0.5, "mana": 0.6},
    "tank_support":     {"hp": 0.9, "armor": 0.8, "mr": 0.7, "ability_haste": 0.8},
    "skirmisher":       {"ad": 0.8, "attack_speed": 0.7, "lifesteal": 0.6, "hp": 0.5},
}


# ═══════════════════════════════════════════════════════════════
# OVERRIDES DE ARCHETYPE (~120 campeones)
# ═══════════════════════════════════════════════════════════════

ARCHETYPE_OVERRIDES = {
    # ─── ENCHANTERS ───────────────────────────────────────
    "Nami": "enchanter", "Janna": "enchanter", "Sona": "enchanter",
    "Soraka": "enchanter", "Yuumi": "enchanter", "Lulu": "enchanter",
    "Karma": "enchanter", "Milio": "enchanter", "Renata": "enchanter",
    "Seraphine": "enchanter", "Ivern": "enchanter",

    # ─── TANK SUPPORTS ────────────────────────────────────
    "Taric": "tank_support", "Rell": "tank_support",
    "Braum": "tank_warden", "Alistar": "tank_vanguard",
    "Leona": "tank_vanguard", "Nautilus": "tank_vanguard",

    # ─── CATCHERS ─────────────────────────────────────────
    "Blitzcrank": "catcher", "Thresh": "catcher", "Pyke": "catcher",
    "Bard": "catcher", "Rakan": "catcher",

    # ─── DAMAGE MAGES (NO enchanters aunque se jueguen supp)
    "Brand": "burst_mage", "Zyra": "burst_mage", "Velkoz": "burst_mage",
    "Xerath": "burst_mage", "Lux": "burst_mage",

    # ─── BURST MAGES ─────────────────────────────────────
    "Syndra": "burst_mage", "Veigar": "burst_mage", "Annie": "burst_mage",
    "Neeko": "burst_mage", "Zoe": "burst_mage", "Ahri": "burst_mage",
    "Ziggs": "burst_mage",
    "Hwei": "control_mage", "LeBlanc": "assassin_ap", "Azir": "control_mage",

    # ─── CONTROL MAGES ───────────────────────────────────
    "Anivia": "control_mage", "Orianna": "control_mage",
    "Viktor": "control_mage", "AurelionSol": "control_mage",
    "Taliyah": "control_mage", "Malzahar": "control_mage",
    "Heimerdinger": "control_mage",

    # ─── BATTLEMAGES ─────────────────────────────────────
    "Vladimir": "battlemage", "Ryze": "battlemage", "Cassiopeia": "battlemage",
    "Swain": "battlemage", "Rumble": "battlemage", "Karthus": "battlemage",
    "Lillia": "battlemage", "Kennen": "battlemage", "Singed": "battlemage",
    "Fiddlesticks": "battlemage", "Teemo": "battlemage",

    # ─── AP ASSASSINS ────────────────────────────────────
    "Akali": "assassin_ap", "Katarina": "assassin_ap", "Diana": "assassin_ap",
    "Evelynn": "assassin_ap", "Fizz": "assassin_ap", "Kassadin": "assassin_ap",
    "Ekko": "assassin_ap", "Elise": "assassin_ap", "Nidalee": "assassin_ap",
    "Aurora": "assassin_ap",

    # ─── AD ASSASSINS ────────────────────────────────────
    "Zed": "assassin_ad", "Talon": "assassin_ad", "Khazix": "assassin_ad",
    "Qiyana": "assassin_ad", "Naafiri": "assassin_ad", "Shaco": "assassin_ad",
    "Rengar": "assassin_ad",

    # ─── MARKSMEN ────────────────────────────────────────
    "Jinx": "marksman", "Caitlyn": "marksman", "Ashe": "marksman",
    "MissFortune": "marksman", "Tristana": "marksman", "Sivir": "marksman",
    "Xayah": "marksman", "Aphelios": "marksman", "Draven": "marksman",
    "Jhin": "marksman", "Lucian": "marksman", "Samira": "marksman",
    "Zeri": "marksman", "Smolder": "marksman", "Twitch": "marksman",
    "KaiSa": "marksman", "Kalista": "marksman", "Ezreal": "marksman",
    "Corki": "marksman", "Kindred": "marksman", "Quinn": "marksman",
    "Akshan": "marksman", "Nilah": "marksman", "Varus": "marksman",

    # ─── ON-HIT MARKSMEN ─────────────────────────────────
    "KogMaw": "on_hit_marksman", "Vayne": "on_hit_marksman",

    # ─── JUGGERNAUTS ─────────────────────────────────────
    "Illaoi": "juggernaut", "Darius": "juggernaut", "Garen": "juggernaut",
    "Nasus": "juggernaut", "Mordekaiser": "juggernaut", "Urgot": "juggernaut",
    "Volibear": "juggernaut", "DrMundo": "juggernaut", "Sett": "juggernaut",
    "Yorick": "juggernaut", "Trundle": "juggernaut", "Shyvana": "juggernaut",
    "Udyr": "juggernaut",

    # ─── BRUISERS ────────────────────────────────────────
    "Camille": "bruiser", "Aatrox": "bruiser", "Riven": "bruiser",
    "Renekton": "bruiser", "Kled": "bruiser", "Gnar": "bruiser",
    "Wukong": "bruiser", "JarvanIV": "bruiser", "Hecarim": "bruiser",
    "Olaf": "bruiser", "Pantheon": "bruiser", "Ambessa": "bruiser",
    "XinZhao": "bruiser", "Vi": "bruiser", "Warwick": "bruiser",
    "BelVeth": "bruiser", "RekSai": "bruiser", "LeeSin": "bruiser",
    "Jayce": "bruiser", "Graves": "bruiser",

    # ─── SKIRMISHERS ─────────────────────────────────────
    "Fiora": "skirmisher", "Jax": "skirmisher", "Irelia": "skirmisher",
    "Yasuo": "skirmisher", "Yone": "skirmisher", "Tryndamere": "skirmisher",
    "Gangplank": "skirmisher", "Viego": "skirmisher", "Gwen": "skirmisher",

    # ─── TANKS ───────────────────────────────────────────
    "Malphite": "tank_vanguard", "Ornn": "tank_warden", "Rammus": "tank_warden",
    "Amumu": "tank_vanguard", "Maokai": "tank_vanguard",
    "Sejuani": "tank_vanguard", "Zac": "tank_vanguard",
    "Sion": "tank_vanguard", "TahmKench": "tank_warden",
    "Shen": "tank_warden", "Galio": "tank_vanguard", "Poppy": "tank_warden",
    "ChoGath": "tank_vanguard", "Nunu": "tank_vanguard",

    # ─── SPECIAL ─────────────────────────────────────────
    "Kayn": "assassin_ad",
}


# ═══════════════════════════════════════════════════════════════
# OVERRIDES DE MANA NEED
# ═══════════════════════════════════════════════════════════════

MANA_NEED_OVERRIDES = {
    # Necesitan Tear
    "Jayce": 1.0, "Ezreal": 1.0, "Cassiopeia": 1.0, "Ryze": 1.0,
    # Necesitan al menos un item de maná
    "Anivia": 0.9, "Kassadin": 0.8,
    "AurelionSol": 0.7, "Xerath": 0.7, "Ziggs": 0.7,
    "Orianna": 0.6, "Viktor": 0.6, "Syndra": 0.5, "Lux": 0.5,
    # Poco maná necesario
    "Nasus": 0.3, "Yorick": 0.3,
    # No usan maná (seguro: evitar errores de detección)
    "Aatrox": 0.0, "Garen": 0.0, "Katarina": 0.0, "Akali": 0.0,
    "Zed": 0.0, "Kennen": 0.0, "Shen": 0.0, "LeeSin": 0.0,
    "Gnar": 0.0, "Renekton": 0.0, "Tryndamere": 0.0, "DrMundo": 0.0,
    "Vladimir": 0.0, "Mordekaiser": 0.0, "Rumble": 0.0, "Yone": 0.0,
    "Yasuo": 0.0, "Viego": 0.0, "Riven": 0.0, "Sett": 0.0,
    "Kled": 0.0, "Shyvana": 0.0, "RekSai": 0.0, "Rengar": 0.0,
    "Nilah": 0.0, "Gwen": 0.0, "BelVeth": 0.0, "Ambessa": 0.0, "Samira": 0.0,
}


# ═══════════════════════════════════════════════════════════════
# ITEMS CONOCIDOS POR NOMBRE (clasificación precisa)
# ═══════════════════════════════════════════════════════════════

KNOWN_SUPPORT_ITEMS = {
    "Shurelya's Battlesong", "Shurelya's Requiem",
    "Locket of the Iron Solari", "Moonstone Renewer",
    "Staff of Flowing Water", "Ardent Censer", "Redemption",
    "Mikael's Blessing", "Mikael's Crucible", "Imperial Mandate",
    "Echoes of Helia", "Dream Maker", "Dawncore",
    "Celestial Opposition", "Solstice Sleigh",
}

KNOWN_TEAR_ITEMS = {
    "Tear of the Goddess", "Manamune", "Muramana",
    "Archangel's Staff", "Seraph's Embrace",
    "Fimbulwinter", "Winter's Approach",
}

KNOWN_BRUISER_ITEMS = {
    "Trinity Force", "Black Cleaver", "Sterak's Gage",
    "Death's Dance", "Spear of Shojin", "Goredrinker",
    "Stridebreaker", "Sundered Sky", "Iceborn Gauntlet",
    "Ravenous Hydra", "Titanic Hydra", "Hullbreaker",
    "Eclipse", "Jak'Sho, The Protean",
}

KNOWN_LETHALITY_ITEMS = {
    "Youmuu's Ghostblade", "Edge of Night", "Serpent's Fang",
    "The Collector", "Umbral Glaive", "Opportunity",
    "Hubris", "Profane Hydra", "Voltaic Cyclosword",
}

RESOURCELESS_TYPES = [
    "None", "Fury", "Rage", "Energy", "Heat",
    "Ferocity", "Shield", "Bloodthirst", "Grit",
    "Courage", "Flow", "Crimson Rush",
]
