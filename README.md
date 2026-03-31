# Janky Thermostat

This project runs the original thermostat controller as a standard OCI container on plain Docker. The Home Assistant add-on wrapper is gone, but the application behavior is the same: it now reads the SHT4x sensor over `rgpio`, drives the motor through the MC33926 stack, and publishes Home Assistant MQTT discovery entities.

## Runtime model

- The container starts with `python /app/main.py`.
- Runtime settings come from the JSON file mounted at `/config/config.json`.
- MQTT settings can also be imported from `MQTT_BROKER` or `MQTT_HOST`, plus `MQTT_PORT`, `MQTT_USERNAME`, and `MQTT_PASSWORD`, when the corresponding JSON keys are missing or `null`.
- The JSON `schedule` array seeds the initial retained MQTT schedule slot values; after discovery, the live schedule is edited through Home Assistant MQTT entities instead of changing the config file.
- No Supervisor, `bashio`, `with-contenv`, or `/data/options.json` is used.

## Files

- [`Dockerfile`](./Dockerfile) builds the runtime image from `debian:trixie-slim` with a multi-stage Python environment.
- [`Dockerfile.remote`](./Dockerfile.remote) is a self-contained Dockerfile for raw-URL builds with no local checkout.
- [`compose.yaml`](./compose.yaml) is a sample standalone deployment that also works well for local developer builds.
- [`config.json`](./config.json) is the sample mounted config file.
- [`Makefile`](./Makefile) provides the same `image-build` and `image-publish` targets used in `docker-rgpio`.
- [`scripts/docker-image.sh`](./scripts/docker-image.sh) is the shared `build` / `publish` helper, matching the `docker-rgpio` project structure.
- [`scripts/build-image.sh`](./scripts/build-image.sh) and [`scripts/publish-image.sh`](./scripts/publish-image.sh) remain as compatibility wrappers.

## Easy image build and publish

This repo now uses the same helper pattern as `docker-rgpio`: a single `scripts/docker-image.sh` entrypoint plus `make` targets.

Default target platform:

- `linux/arm64`

Prerequisites:

- Docker CLI installed
- `buildx` available either as `docker buildx` or standalone `docker-buildx`
- A working Docker daemon, or a Docker context that points at a reachable remote daemon
- For cross-building from a non-ARM host, `buildx` emulation support available to Docker

Build an arm64 image into your local Docker image store:

```bash
make image-build
```

Publish an arm64 image to a registry:

```bash
make image-publish IMAGE_REPO=ghcr.io/your-org/janky-thermostat IMAGE_TAG=v0.1.0
```

Build and publish with the underlying helper directly:

```bash
sh scripts/docker-image.sh build
sh scripts/docker-image.sh publish
```

Supported variables:

- `IMAGE_REPO`: image repository/name, default `janky-thermostat`
- `IMAGE_TAG`: image tag, default `latest`
- `IMAGE_PLATFORM`: target platform, default `linux/arm64`
- `BASE_IMAGE`: base image build arg, default `debian:trixie-slim`
- `BUILDER_NAME`: override the `buildx` builder name if needed
- `EXTRA_ARGS`: append raw extra flags to `docker buildx build`

The compatibility wrappers still work:

```bash
scripts/build-image.sh janky-thermostat:test
scripts/publish-image.sh ghcr.io/your-org/janky-thermostat v0.1.0
```

If you prefer the raw Docker command, the equivalent local build is:

```bash
docker buildx build \
  --target runtime \
  --platform linux/arm64 \
  --build-arg BASE_IMAGE=debian:trixie-slim \
  --tag janky-thermostat:latest \
  --load \
  .
```

## Run With Compose

```bash
docker compose up --build -d
```

The sample Compose file builds the `runtime` target from [`Dockerfile`](./Dockerfile), defaults the image tag to `janky-thermostat:latest`, accepts `BASE_IMAGE`, and mounts [`config.json`](./config.json) to `/config/config.json`.

Attach the container to the same user-defined or external Docker networks as the MQTT broker and `rgpiod`, then set `mqtt_broker` and `rgpio_addr` in `config.json` to the corresponding service or container DNS names on those networks. No host-network access or `host-gateway` aliasing is required.

You can still override the image tag, base image, or mounted config path at Compose invocation time if needed:

```bash
JANKY_CONFIG_PATH="$PWD/config.json" \
JANKY_IMAGE=janky-thermostat:latest \
BASE_IMAGE=debian:trixie-slim \
docker compose up --build -d
```

## Publish

The publish helper uses `docker buildx build --push` and defaults to `linux/arm64`. Override `IMAGE_PLATFORM` if you need a different target.


If you prefer the raw Docker command, the equivalent publish is:

```bash
docker buildx build \
  --target runtime \
  --platform linux/arm64 \
  --build-arg BASE_IMAGE=debian:trixie-slim \
  --tag ghcr.io/your-org/janky-thermostat:v0.1.0 \
  --push \
  .
```

## Remote Builds

### Build directly from the GitHub repo URL

```bash
docker buildx build \
  --target runtime \
  --platform linux/arm64 \
  --build-arg BASE_IMAGE=debian:trixie-slim \
  --tag janky-thermostat:latest \
  --load \
  https://github.com/Clam-/ha-pxe-janky-thermostat.git#main
```

This works because the repo has a root [`Dockerfile`](./Dockerfile) and the full Git repository can be used as the build context.

### Run Compose directly from the GitHub repo URL

```bash
JANKY_CONFIG_PATH="$PWD/config.json" \
JANKY_IMAGE=janky-thermostat:latest \
docker compose -f https://github.com/Clam-/ha-pxe-janky-thermostat.git#main:compose.yaml up -d
```

This uses the repo as the Compose source, so no local checkout is required. `JANKY_CONFIG_PATH` lets you mount a local config file instead of the repo default.

### Build from a single raw Dockerfile URL

```bash
docker buildx build \
  --target runtime \
  --platform linux/arm64 \
  --build-arg BASE_IMAGE=debian:trixie-slim \
  --tag janky-thermostat:latest \
  --load \
  https://raw.githubusercontent.com/Clam-/ha-pxe-janky-thermostat/main/Dockerfile.remote
```

[`Dockerfile.remote`](./Dockerfile.remote) is intentionally self-contained: it fetches the app source from GitHub during the build, so it still works when the build context is just a raw text file. `REPO_REF` can be a branch, tag, or commit SHA.

To build a specific branch, tag, or commit with the raw-file path:

```bash
docker buildx build \
  --target runtime \
  --platform linux/arm64 \
  --build-arg BASE_IMAGE=debian:trixie-slim \
  --tag janky-thermostat:v0.2.1 \
  --load \
  --build-arg REPO_REF=v0.2.1 \
  https://raw.githubusercontent.com/Clam-/ha-pxe-janky-thermostat/v0.2.1/Dockerfile.remote
```

## Run With `docker run`

```bash
docker run -d \
  --name janky-thermostat \
  --restart unless-stopped \
  -v "$(pwd)/config.json:/config/config.json:ro" \
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
  "schedule_slots": 6,
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
- `schedule`: Array of `"HH:MM TEMP"` strings used to seed retained MQTT slot state.
- `schedule_slots`: Fixed number of schedule slot entity pairs (`text` time + `number` temperature) exposed over MQTT discovery.
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

### MQTT schedule editing

The thermostat exposes a fixed number of schedule slot entities through MQTT discovery:

- `text` entities for slot times in `HH:MM`
- `number` entities for slot temperatures in `°C`
- sensors for the rendered schedule summary and the currently active schedule row

Blank time slots are ignored. The JSON `schedule` array remains useful as an initial seed, but ongoing edits are expected to happen in Home Assistant through the discovered MQTT entities.

When `mqtt_broker`, `mqtt_port`, `mqtt_username`, or `mqtt_password` are omitted from the JSON file, or set to `null`, the runtime falls back to `MQTT_BROKER`/`MQTT_HOST`, `MQTT_PORT`, `MQTT_USERNAME`, and `MQTT_PASSWORD` if those environment variables are present.

## Operational notes

- The container expects an already-running MQTT broker.
- The container expects a reachable `rgpiod` instance for GPIO/I2C access.
- When running `rgpiod` in a container, pass through the GPIO and I2C device nodes it needs, typically `/dev/gpiochip0`, `/dev/i2c-1`, and `/dev/i2c-2`.
- MQTT discovery is still published under `homeassistant/...`, so Home Assistant can discover the entities without the add-on framework.
