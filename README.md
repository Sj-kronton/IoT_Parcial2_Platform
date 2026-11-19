# IoT Campus UNAB

Plataforma IoT en una VM de Azure con Docker: 11 dispositivos (real / digital twin / API / dataset),
broker EMQX (MQTT), TimescaleDB, Grafana, API de control (FastAPI), panel web y analisis con IA.

## Arquitectura
(insertar imagen del diagrama)

## Despliegue
1. Copiar `.env.example` a `.env` y completar los valores.
2. `docker compose up -d --build`
3. Crear usuarios MQTT en EMQX (devices, ingestor, api).

## Estructura
- `docker-compose.yml` plataforma · `docker-compose.devices.yml` dispositivos y servicios
- `devices/` simuladores y conectores · `ingestor/` MQTT a DB · `api/` control y analisis · `panel/` interfaz web
- `grafana/` dashboards exportados · `db/init.sql` esquema

## Integrantes

- Juan Alejandro Sierra - U00178520
- Maria Herrera Taborda - U00173188
