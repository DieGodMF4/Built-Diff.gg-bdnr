# Justificación Académica: Uso de MongoDB (NoSQL Documental)

## 1. ¿Por qué NoSQL documental?

### 1.1 Esquema flexible para datos heterogéneos
Los campeones tienen campos variables: distinto número de debilidades, stat_weights con claves diferentes, y mana_need que solo tiene sentido para campeones con maná. En SQL esto requeriría columnas NULL o tablas intermedias. En MongoDB, cada documento tiene exactamente los campos que necesita.

### 1.2 Relaciones many-to-many implícitas
Las relaciones campeón↔stats, item↔counters, item↔effects se resuelven con arrays embebidos. En SQL se necesitarían 5+ tablas intermedias con JOINs en cada consulta. En MongoDB: 2 colecciones + 1 de referencia (enums).

### 1.3 Patrón de lectura simple
El recomendador lee documentos completos y calcula en memoria. No necesita JOINs ni traversals. Una query `findOne({champion_id: "Jinx"})` devuelve todo lo necesario.

### 1.4 Adaptabilidad a parches
Riot actualiza el juego cada 2 semanas. Añadir campos nuevos (como `priority` en v3) no requiere ALTER TABLE: simplemente se insertan documentos con el campo nuevo.

## 2. Optimización: codificación entera

Los campos categóricos más repetidos (archetype, damage_profile, subclass, weaknesses, counters, effects) se almacenan como integers en vez de strings.

**Justificación técnica:**
- Un string "burst_mage" ocupa 10 bytes + overhead en BSON
- Un integer 10 ocupa 4 bytes fijos
- En arrays repetidos (weaknesses × 172 documentos) el ahorro se multiplica

**Auto-documentación:**
La colección `enums` almacena los mapeos int→string, haciendo la base de datos legible sin necesidad del código fuente.

## 3. Sistema de prioridad

El campo `priority` (1=EARLY, 2=MID, 3=LATE) en cada item es un ejemplo de **dato derivado pre-calculado**: se computa una vez durante el ETL en vez de calcularlo en cada consulta. Esto es una práctica común en NoSQL donde se prioriza velocidad de lectura sobre normalización.

## 4. Comparativa SQL vs MongoDB

**Modelo SQL equivalente:** 9+ tablas (champions, champion_weaknesses, champion_stats, items, item_counters, item_effects, item_stats, enums, ...)

**Modelo MongoDB:** 3 colecciones (champions, items, enums), documentos auto-contenidos.

**Query ejemplo - obtener campeón con todo:**
- SQL: SELECT + 4 JOINs + GROUP BY
- MongoDB: `db.champions.findOne({champion_id: "Jinx"})`

## 5. Alternativa considerada: Neo4j

El dominio de LoL es conceptualmente un grafo (campeón→counters→campeón, campeón→builds→item). Neo4j sería una alternativa válida para queries tipo "qué items están más conectados a campeones que ganan contra esta comp". Sin embargo, MongoDB se justifica porque:
- El patrón de acceso no requiere traversals profundos
- El dataset es pequeño (~170 campeones, ~140 items)

## 6. Limitaciones

- Sin integridad referencial forzada por la BD
- Analytics cruzados complejos serían más naturales en SQL
- La validación de esquema depende del código ETL
