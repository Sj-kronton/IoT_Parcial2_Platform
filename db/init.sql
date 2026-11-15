CREATE EXTENSION IF NOT EXISTS timescaledb;
CREATE TABLE measurements(time timestamptz NOT NULL, device_id text NOT NULL,
                          variable text NOT NULL, value double precision, unit text);
SELECT create_hypertable('measurements','time');
CREATE INDEX ON measurements(device_id, variable, time DESC);
CREATE TABLE devices(device_id text PRIMARY KEY, name text, kind text, protocol text,
                     location text, enabled boolean DEFAULT true);
CREATE TABLE command_log(time timestamptz DEFAULT now(), device_id text, action text,
                         value text, who text, ack boolean);
