# Krkn plugin development demo

This directory is the starter material. The plugin deliberately has only
`execute_demo()`: implement `run()` and `get_scenario_types()` live before trying
to load or build it. The directory under `krkn/scenario_plugins/` must be named
`dev_demo`, because Krkn rejects plugin directory names containing `scenario`
or `plugin`.

## Live coding

Copy `__init__.py` and `dev_demo_scenario_plugin.py` into
`krkn/scenario_plugins/dev_demo/` in the clean Krkn checkout. Add these methods
to `DevDemoScenarioPlugin`:

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

Add `from krkn_lib.models.telemetry import ScenarioTelemetry` to the imports.
The `scenario` argument is the path injected by Krkn; `execute_demo()` loads
that YAML, checks `wait` and `namespace`, sleeps, verifies that the namespace
exists, and logs its pod names. Missing namespace or other errors return `1`.

For a direct Krkn run, add `dev_demo_scenarios: [scenarios/dev_demo.yaml]` to
`kraken.chaos_scenarios` in a demo copy of `config/config.yaml`. Keep the normal
configuration for the other Krkn sections. `scenario.yaml` is a ready input.

## Scenario image material

For the krkn-hub-style image, copy `Dockerfile.template`, `env.sh`, `run.sh`,
`scenario.yaml.template`, and `krknctl-input.json` into a `dev-demo/` directory
in a krkn-hub checkout. The Dockerfile uses the shared `config.yaml.template`,
`env.sh`, and `common_run.sh` from the hub root. Generate `dev-demo/Dockerfile`
with `KRKNCTL_INPUT` set to the compact contents of `krknctl-input.json`, as
done by the hub's `build.sh`.

`Dockerfile.base` builds a quick derived Krkn base image from the checkout after
the plugin is implemented. Use the Krkn checkout as the build context:

```sh
podman build -f /path/to/dev_demo/Dockerfile.base -t krkn-dev-demo:base /path/to/krkn
```

From the krkn-hub checkout, compile and build the scenario image after copying
the files to `dev-demo/`:

```sh
export KRKNCTL_INPUT="$(tr -d '\n' < dev-demo/krknctl-input.json)"
envsubst '${KRKNCTL_INPUT}' < dev-demo/Dockerfile.template > dev-demo/Dockerfile
podman build -f dev-demo/Dockerfile -t krkn-hub:dev-demo .
```

The hub's `build.sh` has a fixed scenario list, so its default run will not
generate this new Dockerfile until `dev-demo` is added to that list.

For a full Krkn base rebuild, adapt the upstream
`containers/Dockerfile.template` to copy the local checkout instead of running
`git clone`; otherwise it will build without this plugin.
