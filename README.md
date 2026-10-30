# Krkn custom plugin demo

All paths are absolute. Start with `cd /tmp` so Git has a valid working
directory even if a previous `/tmp/krkn` checkout was removed while your shell
was inside it. The workflow assumes that `/tmp/krkn` does not exist yet. If it
already contains work, choose a different `KRKN_DIR`; do not delete a checkout
with local changes.

## 1. Set the paths and clone the repositories

```sh
cd /tmp

export KRKN_DIR=/tmp/krkn
export KRKN_DEV_PLUGIN_DIR="$KRKN_DIR/krkn/scenario_plugins/dev_demo"
export KRKN_BASE_IMAGE=krkn-dev-demo:base
export KRKN_SCENARIO_IMAGE=krkn-dev-demo:scenario

git clone https://github.com/krkn-chaos/krkn.git "$KRKN_DIR"
git clone git@github.com:krkn-chaos/krkn-dev-demo.git "$KRKN_DEV_PLUGIN_DIR"
```

The plugin directory must be named `dev_demo`. Krkn's plugin factory rejects
directory names containing `scenario` or `plugin`. The module name
`dev_demo_scenario_plugin.py` matches the class name `DevDemoScenarioPlugin`.

## 2. Complete the plugin during the demo

Open `$KRKN_DEV_PLUGIN_DIR/dev_demo_scenario_plugin.py`. The `execute_demo()`
method is already implemented. It reads the scenario YAML path passed to
`run()`, validates `wait` and `namespace`, sleeps, checks that the namespace
exists through `krkn-lib`, and logs the pod names. It returns `0` on success
and `1` on failure.

Add `from krkn_lib.models.telemetry import ScenarioTelemetry` to the imports,
then implement the two abstract methods in `DevDemoScenarioPlugin`:

```python
def get_scenario_types(self) -> list[str]:
    return ["dev_demo_scenarios"]

def run(
    self,
    run_uuid: str,
    scenario: str,
    lib_telemetry: KrknTelemetryOpenshift,
    scenario_telemetry: ScenarioTelemetry,
) -> int:
    return self.execute_demo(scenario, lib_telemetry)
```

The plugin remains abstract until these methods are added, so Krkn cannot
load it before the live coding step.

For a direct Krkn run, copy the example scenario and create a separate Krkn
configuration:

```sh
cp "$KRKN_DEV_PLUGIN_DIR/scenario.yaml" "$KRKN_DIR/scenarios/dev_demo.yaml"
cp "$KRKN_DIR/config/config.yaml" "$KRKN_DIR/config/dev_demo_config.yaml"
```

In `$KRKN_DIR/config/dev_demo_config.yaml`, set `kraken.chaos_scenarios` to
`- dev_demo_scenarios: [scenarios/dev_demo.yaml]`.

## 3. Build the Krkn base image with the plugin

After implementing the abstract methods, build a base image derived from the
published Krkn image. Use the cloned plugin directory as the build context:

```sh
podman build \
  -f "$KRKN_DEV_PLUGIN_DIR/Dockerfile.base" \
  -t "$KRKN_BASE_IMAGE" \
  "$KRKN_DEV_PLUGIN_DIR"
```

`Dockerfile.base` copies the two Python plugin files into the Krkn image. The
upstream Dockerfile in `containers/` clones Krkn from GitHub during its build;
using it unchanged would omit this local plugin.

## 4. Build the standalone scenario image

The scenario image includes `krknctl.*` labels and the two input fields from
`krknctl-input.json`. It builds directly from the plugin repository. There is
no krkn-hub checkout or rebuild.

```sh
export KRKNCTL_INPUT="$(tr -d '\n' < "$KRKN_DEV_PLUGIN_DIR/krknctl-input.json")"
envsubst '${KRKNCTL_INPUT}' \
  < "$KRKN_DEV_PLUGIN_DIR/Dockerfile.template" \
  > "$KRKN_DEV_PLUGIN_DIR/Dockerfile"
podman build \
  -f "$KRKN_DEV_PLUGIN_DIR/Dockerfile" \
  -t "$KRKN_SCENARIO_IMAGE" \
  "$KRKN_DEV_PLUGIN_DIR"
```

`krknctl-input.json` exposes `wait` and `namespace`. At runtime, `run.sh`
inserts those values into the scenario YAML, derives a dedicated Krkn
configuration from the base image's `config/config.yaml`, and runs only
`dev_demo_scenarios`.
