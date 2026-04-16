# 🎮 LoL Draft Item Recommender v3

Sistema de recomendación de itemización para League of Legends basado en el draft.

## Características

- **Datos reales** de Data Dragon (Riot) + Meraki Analytics (ratios de habilidades)
- **Clasificación inteligente**: archetype (15 subclases), damage_profile, stat_weights individuales
- **Dependencia de maná** calculada automáticamente
- **Sistema de prioridad** de items (EARLY / MID / LATE)
- **Codificación entera** de campos categóricos (optimización BSON)
- **MongoDB** como base de datos documental

## Ejecución

```bash
pip install pymongo requests

# 1. Descargar datos (DDragon + Meraki)
python data_acquisition/fetch_data.py

# 2. Transformar y clasificar
python data_acquisition/transform.py

# 3. Iniciar MongoDB (debe estar corriendo)
# 4. Cargar en MongoDB
python database/seed.py

# 5. Recomendador
python recommender/engine.py --demo     # Demo con drafts de ejemplo
python recommender/engine.py            # Modo interactivo
```

## Estructura

```
├── config.py                  # Configuración, enums, overrides, prioridades
├── data_acquisition/
│   ├── fetch_data.py          # Descarga DDragon + Meraki
│   └── transform.py           # ETL: clasificación + enums + prioridad
├── database/
│   ├── connection.py          # Conexión MongoDB
│   └── seed.py                # Inserción + índices + colección enums
├── recommender/
│   └── engine.py              # Algoritmo de scoring + ordenación por prioridad
├── api/
│   └── main.py                # (Opcional) FastAPI
└── docs/
    └── justificacion_academica.md
```
