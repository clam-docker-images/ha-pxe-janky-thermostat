# Janky Thermostat

This project runs the original thermostat controller as a standard OCI container on plain Docker. The Home Assistant add-on wrapper is gone, but the application behavior is the same: it now reads the SHT4x sensor over `rgpio`, drives the motor through the MC33926 stack, and publishes Home Assistant MQTT discovery entities.

## Runtime model

- The container starts with `python /app/main.py`.
- Runtime settings come from a JSON file mounted at `/config/config.json` by default.
- Standard environment variables can override MQTT, `rgpio`, I2C, and thermostat settings.
- No Supervisor, `bashio`, `with-contenv`, or `/data/options.json` is used.

## Files

- [`Dockerfile`](./Dockerfile) builds the container from the official multi-arch `python:3.11-slim` image.
- [`Dockerfile.remote`](./Dockerfile.remote) is a self-contained Dockerfile for raw-URL builds with no local checkout.
- [`compose.yaml`](./compose.yaml) is a sample standalone deployment and works as the root Compose file for Git URL deployments.
- [`config.json`](./config.json) is the sample mounted config file.

## Build

```bash
docker build -t janky-thermostat .
```

## Run With Compose

```bash
docker compose up --build -d
```

The sample Compose file mounts [`config.json`](./config.json) to `/config/config.json` and overrides the MQTT and `rgpio` connection endpoints with environment variables.

It also supports shell overrides for quick deployment:

```bash
MQTT_BROKER=broker.local \
RGPIO_ADDR=rgpio.local \
JANKY_CONFIG_PATH="$PWD/config.json" \
docker compose up --build -d
```

## Remote Builds

### Build directly from the GitHub repo URL

```bash
docker build -t janky-thermostat https://github.com/Clam-/ha-pxe-janky-thermostat.git#main
```

This works because the repo has a root [`Dockerfile`](./Dockerfile) and the full Git repository can be used as the build context.

### Run Compose directly from the GitHub repo URL

```bash
MQTT_BROKER=broker.local \
RGPIO_ADDR=rgpio.local \
JANKY_CONFIG_PATH="$PWD/config.json" \
docker compose -f https://github.com/Clam-/ha-pxe-janky-thermostat.git#main:compose.yaml up -d
```

This uses the repo as the Compose source, so no local checkout is required. `JANKY_CONFIG_PATH` lets you mount a local config file instead of the repo default.

### Build from a single raw Dockerfile URL

```bash
docker build -t janky-thermostat \
  https://raw.githubusercontent.com/Clam-/ha-pxe-janky-thermostat/main/Dockerfile.remote
```

[`Dockerfile.remote`](./Dockerfile.remote) is intentionally self-contained: it fetches the app source from GitHub during the build, so it still works when the build context is just a raw text file. `REPO_REF` can be a branch, tag, or commit SHA.

To build a specific branch, tag, or commit with the raw-file path:

```bash
docker build -t janky-thermostat \
  --build-arg REPO_REF=v0.2.1 \
  https://raw.githubusercontent.com/Clam-/ha-pxe-janky-thermostat/v0.2.1/Dockerfile.remote
```

## Run With `docker run`

```bash
docker run -d \
  --name janky-thermostat \
  --restart unless-stopped \
  -v "$(pwd)/config.json:/config/config.json:ro" \
  -e MQTT_BROKER=mosquitto \
  -e MQTT_PORT=1883 \
  -e RGPIO_ADDR=rgpio \
  -e RGPIO_PORT=8889 \
  -e I2C_BUS=0 \
  janky-thermostat
```

## Configuration

The JSON file uses the same core thermostat settings as the add-on, with MQTT and `rgpio` moved into normal runtime config:

```json
{
  "mqtt_broker": "mosquitto",
  "mqtt_port": 1883,
  "mqtt_username": null,
  "mqtt_password": null,
  "schedule": ["06:00 21.0", "22:30 18.0"],
  "min_temp": 20.0,
  "max_temp": 28.0,
  "posmin": 1034,
  "posmax": 24600,
  "posmargin": 50,
  "speed": 50.0,
  "lograte": 10,
  "updaterate": 15,
  "updir": 1,
  "i2c_bus": 0,
  "rgpio_addr": "rgpio",
  "rgpio_port": 8889,
  "loglevel": "WARNING"
}
```

### Config keys

- `mqtt_broker`, `mqtt_port`, `mqtt_username`, `mqtt_password`: MQTT connection used for Home Assistant discovery and entity state/commands.
- `schedule`: Array of `"HH:MM TEMP"` strings. Blank entries are ignored.
- `min_temp`, `max_temp`: Climate entity temperature limits.
- `posmin`, `posmax`: PID output range for the actuator position.
- `posmargin`: Acceptable actuator deadband before movement stops.
- `speed`: Motor speed percentage passed to the motor driver.
- `lograte`: Seconds between publish/log updates and schedule checks.
- `updaterate`: PID sample time in seconds.
- `updir`: Motor direction, must be `1` or `-1`.
- `i2c_bus`: I2C bus passed through to the `rgpio`-backed sensor libraries.
- `rgpio_addr`, `rgpio_port`: `rgpiod` daemon endpoint.
- `loglevel`: One of `CRITICAL`, `ERROR`, `WARNING`, `INFO`, `DEBUG`.

### Environment overrides

These override the JSON file when set:

- `JANKY_CONFIG_FILE`: Alternate config file path inside the container.
- `MQTT_BROKER`, `MQTT_PORT`, `MQTT_USERNAME`, `MQTT_PASSWORD`
- `RGPIO_ADDR`, `RGPIO_PORT`, `I2C_BUS`
- `THERMOSTAT_SCHEDULE`: JSON array of schedule strings.
- `THERMOSTAT_MIN_TEMP`, `THERMOSTAT_MAX_TEMP`
- `THERMOSTAT_POSMIN`, `THERMOSTAT_POSMAX`, `THERMOSTAT_POSMARGIN`
- `THERMOSTAT_SPEED`, `THERMOSTAT_LOGRATE`, `THERMOSTAT_UPDATERATE`
- `THERMOSTAT_UPDIR`
- `THERMOSTAT_LOGLEVEL`

## Operational notes

- The container expects an already-running MQTT broker.
- The container expects a reachable `rgpiod` instance for GPIO/I2C access.
- MQTT discovery is still published under `homeassistant/...`, so Home Assistant can discover the entities without the add-on framework.
