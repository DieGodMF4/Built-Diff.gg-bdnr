# BuiltDiff.gg

Sistema de recomendación de itemización para **League of Legends** que genera una **build sugerida (core + situacionales)** a partir del draft:

- Tu campeón
- Aliados (opcional)
- Enemigos (opcional)

El flujo es:

1) Descargar datos públicos (Riot Data Dragon + Meraki)
2) Transformarlos (clasificación + features derivadas + enums + prioridad)
3) Cargarlo en MongoDB
4) Calcular recomendaciones por *scoring* y ordenar por prioridad de compra

---

## Qué hace (y qué no)

**Sí:**
- Clasifica campeones por `archetype` y `damage_profile`.
- Estima `stat_weights` por campeón usando ratios de habilidades (Meraki) + defaults.
- Calcula `mana_need` y favorece items de maná cuando aplica.
- Clasifica items (`subclass`, `effects`, `counters`) y les asigna `priority` (EARLY/MID/LATE).
- Recomienda **6 items core** (ordenados por prioridad) + **3 situacionales** por score.

**No:**
- No usa datos de partidas (winrate/pickrate). Es un sistema **heurístico + basado en stats**.
- No optimiza por rol/posición de línea de forma explícita (usa tags/archetype).

---

## Stack y fuentes de datos

- **Python** (scripts ETL + recomendador + API opcional)
- **MongoDB** (documental)
- **Data Dragon (Riot)**: campeones, items, stats base, tags
- **Meraki Analytics (CDN público)**: ratios de habilidades y `adaptiveType`

No se requieren API keys.

---

## Arquitectura (pipeline)

```
data_acquisition/fetch_data.py
    ├─ descarga DDragon (champions + items)
    └─ descarga Meraki (champions + items)
                    ↓
data_acquisition/transform.py
    ├─ champions_processed.json (con enums + features derivadas)
    └─ items_processed.json     (con enums + priority)
                    ↓
database/seed.py
    ├─ inserta en MongoDB: champions, items
    ├─ inserta db.enums (mapeos int → string)
    └─ crea índices
                    ↓
recommender/engine.py
    └─ recommend(champion, allies, enemies)
```

---

## Requisitos

- Python 3.10+ recomendado
- MongoDB (local) **o** Docker (para levantar MongoDB con `docker-compose`)

Dependencias Python:

```bash
pip install -r requirements.txt
```

---

## Puesta en marcha (rápida)

### 1) Levantar MongoDB

Opción A — Docker (recomendado):

```bash
docker compose up -d
```

Esto levanta:
- MongoDB en `localhost:27017`
- Mongo Express en `http://localhost:8081`

Opción B — MongoDB local:
- Asegúrate de tener MongoDB corriendo en `mongodb://localhost:27017`

> Nota: La URI/DB/colecciones se configuran en `config.py`.

### 2) Descargar datos

```bash
python data_acquisition/fetch_data.py
```

Genera (en `data/`):
- `champions_ddragon.json`, `items_ddragon.json`
- `champions_meraki.json`, `items_meraki.json`

### 3) Transformar (ETL)

```bash
python data_acquisition/transform.py
```

Genera (en `data/`):
- `champions_processed.json`
- `items_processed.json`

### 4) Cargar a MongoDB

```bash
python database/seed.py
```

### 5) Ejecutar recomendador

Demo con drafts de ejemplo:

```bash
python recommender/engine.py --demo
```

Modo interactivo:

```bash
python recommender/engine.py
```

---

## Cómo funciona el recomendador (resumen)

La recomendación es un **ranking de items** por campeón y composición enemiga.

1) Se analiza la composición enemiga (`heavy_ad`, `heavy_ap`, `mixed`) y amenazas (assassin, tank, adc, etc.)
2) Se calcula un **score** por item combinando:
     - Encaje con `stat_weights` del campeón
     - Compatibilidad `archetype` ↔ `subclass` (tabla de compatibilidades)
     - Sinergia por tipo de daño (AD/AP)
     - Bonus por maná si el campeón lo necesita
     - Bonus por counters (vs debilidades o tipo de comp)
     - Penalizaciones por anti-sinergia (ej. AP en campeón AD sin razón)
3) Se eligen los mejores items por score y se reordenan por **prioridad de compra**:
     - `priority = 1` → EARLY
     - `priority = 2` → MID
     - `priority = 3` → LATE

Los pesos del scoring y el tamaño de la build son configurables en `config.py` (`WEIGHTS`, `NUM_CORE_ITEMS`, etc.).

---

## Sistema de prioridad de items

Cada item lleva un campo `priority` calculado en el ETL:

- **EARLY (1):** items que conviene comprar pronto (Tear/RoA/Hidras/support, etc.)
- **MID (2):** core estándar (valor por defecto)
- **LATE (3):** multiplicadores y penetración que rinden más con base de stats (Rabadon/IE/Void/LDR, etc.)

La prioridad se calcula en cascada:

1) Override por nombre (`ITEM_PRIORITY_OVERRIDES` en `config.py`)
2) Default por `subclass` (`SUBCLASS_DEFAULT_PRIORITY`)
3) Heurística por coste (caro → late, barato → early)
4) Fallback a MID

---

## Base de datos (MongoDB)

La BD por defecto es `lol_recommender` (configurable en `config.py`).

### Colecciones

- `champions`
    - `champion_id`, `name`, `roles`
    - `archetype` (int), `damage_profile` (int)
    - `stat_weights` (dict), `mana_need` (float)
    - `weaknesses` (array[int])
    - campos de debug: `_debug_dp`, `_debug_arch`

- `items`
    - `item_id`, `name`, `gold`
    - `item_type` (int), `subclass` (int)
    - `stats_internal` (dict), `effects` (array[int]), `counters` (array[int])
    - `priority` (1/2/3)
    - flags: `is_mana_item`, `is_tear`, `is_support_item`

- `enums`
    - Documento `_id = "enums"` con mapeos `int → string` para auto-documentar la BD

### Índices

`database/seed.py` crea índices en campos consultados frecuentemente (`champion_id`, `archetype`, `damage_profile`, `subclass`, `counters`, `priority`, etc.).

---

## API REST (opcional)

Hay una API FastAPI mínima en `api/main.py` que expone el recomendador.

Levantarla:

```bash
uvicorn api.main:app --reload
```

Endpoints:

- `GET /health` → estado de conexión a MongoDB
- `GET /champions` → lista básica de campeones
- `GET /items` → lista básica de items
- `POST /recommend` → recomendación para un draft

Ejemplo de request:

```bash
curl -X POST http://127.0.0.1:8000/recommend \
    -H "Content-Type: application/json" \
    -d '{
        "champion": "Jinx",
        "allies": ["Thresh", "Orianna"],
        "enemies": ["Malphite", "Sejuani", "Swain", "Caitlyn", "Leona"]
    }'
```

---

## Configuración y personalización

Archivo principal: `config.py`

- MongoDB: `MONGO_URI`, `MONGO_DB`, `COLLECTION_CHAMPIONS`, `COLLECTION_ITEMS`
- Enum/codificación: `ENUM_*` y `ENUM_REVERSE`
- Pesos del scoring: `WEIGHTS`
- Tamaño de la build: `NUM_CORE_ITEMS`, `NUM_SITUATIONAL_ITEMS`, `SCORE_THRESHOLD_SITUATIONAL`
- Priorización: `ITEM_PRIORITY_OVERRIDES`, `SUBCLASS_DEFAULT_PRIORITY`
- Correcciones manuales: `ARCHETYPE_OVERRIDES`, `MANA_NEED_OVERRIDES`

---

## Troubleshooting

- **"Error de conexión" / Mongo no responde**
    - Verifica que MongoDB esté accesible en `config.MONGO_URI`.
    - Si usas Docker: `docker compose ps` y comprueba el puerto `27017`.

- **"No encontrado: data/..._processed.json" al ejecutar `database/seed.py`**
    - Ejecuta antes `python data_acquisition/transform.py`.

- **Fallo al descargar Meraki**
    - La descarga de campeones de Meraki es grande (~12MB) y puede tardar.
    - Reintenta o revisa tu conectividad; el endpoint es público.

---

## Estructura del repo

```
.
├── config.py
├── docker-compose.yml
├── requirements.txt
├── data/
├── data_acquisition/
│   ├── fetch_data.py
│   └── transform.py
├── database/
│   ├── connection.py
│   └── seed.py
├── recommender/
│   └── engine.py
├── api/
│   └── main.py
└── docs/
        └── justificacion_academica.md
```

---

## Documento académico

Se incluye un documento con la justificación académica en el contexto del desarrollo del proyecto.
