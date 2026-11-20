#!/bin/bash
cd /srv/iot
docker compose exec -T timescaledb pg_dump -U postgres iot | gzip > backups/iot_$(date +%F_%H%M).sql.gz
find backups -name '*.sql.gz' -mtime +7 -delete
