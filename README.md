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

## 5. Test the scenario locally with Podman and Kind

This test requires the Kind cluster to be running.

Kind's host kubeconfig usually points to `127.0.0.1`, which is not the Kind API
server from inside the scenario container. Generate an internal kubeconfig in
your home directory, where Podman Machine can mount it, and run the image on
Kind's container network. The temporary file is removed when the command ends.

```sh
(
  set -e
  KIND_CLUSTER_NAME=kind
  KRKN_TEST_KUBECONFIG="$(mktemp "$HOME/.kube/krkn-kind-demo.XXXXXX")"
  trap 'rm -f "$KRKN_TEST_KUBECONFIG"' EXIT
  kind get kubeconfig --internal --name "$KIND_CLUSTER_NAME" > "$KRKN_TEST_KUBECONFIG"
  export KUBECONFIG="$KRKN_TEST_KUBECONFIG"

  podman run --rm --user 0 --network kind \
    -e WAIT_SECONDS=2 \
    -e NAMESPACE=default \
    -e KUBECONFIG=/home/krkn/.kube/config \
    -v "$(realpath "$KUBECONFIG"):/home/krkn/.kube/config:ro" \
    "$KRKN_SCENARIO_IMAGE"
)
```

The output should contain the `##### DEVELOPMENT SCENARIO #####` banner and
the pod names from `default`. Change `NAMESPACE` to test another namespace.

## 6. Create a dedicated Kind management cluster

The operator and a private Docker Distribution registry run on the management
cluster. The user supplies a target already registered in the operator;
target registration is outside this walkthrough. `kind-config.yml` maps host
`127.0.0.1:5001` to the registry NodePort `30500`. A distinct cluster name
leaves any existing `kind` cluster untouched.

```sh
export KIND_EXPERIMENTAL_PROVIDER=podman
export KRKN_MGMT_CLUSTER=krkn-dev-demo-mgmt
export KRKN_OPERATOR_NAMESPACE=krkn-operator-system

kind create cluster --name "$KRKN_MGMT_CLUSTER" \
  --config "$KRKN_DEV_PLUGIN_DIR/kind-config.yml"

export KRKN_MGMT_CONTEXT="kind-$KRKN_MGMT_CLUSTER"
kubectl --context "$KRKN_MGMT_CONTEXT" get nodes
```

These commands require a running Podman Machine and free host port `5001`.
Keep the management Kind cluster running for the remaining steps.

## 7. Install the private registry in the management cluster

The [Twuni Docker Registry chart](https://github.com/twuni/docker-registry.helm)
installs Docker Distribution with basic authentication. `registry-values.yml`
sets a NodePort and uses disposable storage. Generate credentials outside this
repository; the chart receives only the htpasswd file.

```sh
export KRKN_DEMO_STATE_DIR="$(mktemp -d /tmp/krkn-dev-demo.XXXXXX)"
chmod 700 "$KRKN_DEMO_STATE_DIR"
export REGISTRY_USER=demo
export REGISTRY_PASSWORD="$(openssl rand -hex 16)"
htpasswd -Bbn "$REGISTRY_USER" "$REGISTRY_PASSWORD" \
  > "$KRKN_DEMO_STATE_DIR/registry.htpasswd"
chmod 600 "$KRKN_DEMO_STATE_DIR/registry.htpasswd"

helm repo add twuni https://twuni.github.io/docker-registry.helm
helm repo update twuni
helm upgrade --install demo-registry twuni/docker-registry \
  --version 3.0.0 \
  --kube-context "$KRKN_MGMT_CONTEXT" \
  --namespace registry --create-namespace \
  --values "$KRKN_DEV_PLUGIN_DIR/registry-values.yml" \
  --set-file "secrets.htpasswd=$KRKN_DEMO_STATE_DIR/registry.htpasswd" \
  --wait --timeout 5m

kubectl --context "$KRKN_MGMT_CONTEXT" -n registry \
  get service demo-registry-docker-registry
```

Find the management node's address on the `kind` Podman network. The operator
uses this address to reach the same registry that the host sees at
`localhost:5001`.

```sh
export KRKN_MGMT_NODE="$(kind get nodes --name "$KRKN_MGMT_CLUSTER" | head -n 1)"
export KRKN_REGISTRY_IP="$(podman inspect -f \
  '{{(index .NetworkSettings.Networks "kind").IPAddress}}' \
  "$KRKN_MGMT_NODE")"
export KRKN_REGISTRY_URL="$KRKN_REGISTRY_IP:30500"
printf 'Registry address for the operator: %s\n' "$KRKN_REGISTRY_URL"
```

The selected target must be able to reach this address and its container
runtime must allow HTTP pulls from it. If the target is outside the local Kind
network, publish the registry at an address reachable from that target and
register that address instead. The host port mapping alone does not make
`localhost:5001` reachable from a different cluster. Target networking and
runtime configuration are outside this walkthrough.

## 8. Push the scenario image

The private scenario repository must include an organization and repository
name. The tag `dev-demo` is what the operator presents as the scenario name.
The host push uses the forwarded port; the operator later uses
`$KRKN_REGISTRY_URL` for the same image.

```sh
export KRKN_PRIVATE_SCENARIO=localhost:5001/demo/krkn-hub:dev-demo
podman tag "$KRKN_SCENARIO_IMAGE" "$KRKN_PRIVATE_SCENARIO"
printf '%s' "$REGISTRY_PASSWORD" | podman login \
  --tls-verify=false --username "$REGISTRY_USER" --password-stdin localhost:5001
podman push --tls-verify=false "$KRKN_PRIVATE_SCENARIO"
curl --fail --silent --show-error -u "$REGISTRY_USER:$REGISTRY_PASSWORD" \
  "http://localhost:5001/v2/demo/krkn-hub/tags/list"
```

## 9. Install Krkn Operator

Install the published [Krkn Operator Helm chart](https://github.com/krkn-chaos/krkn-operator)
on the management cluster. Version `1.1.2` is used for this walkthrough.

```sh
helm upgrade --install krkn-operator \
  oci://quay.io/krkn-chaos/charts/krkn-operator \
  --version 1.1.2 \
  --kube-context "$KRKN_MGMT_CONTEXT" \
  --namespace "$KRKN_OPERATOR_NAMESPACE" --create-namespace \
  --wait --timeout 10m

kubectl --context "$KRKN_MGMT_CONTEXT" \
  -n "$KRKN_OPERATOR_NAMESPACE" get pods,services
```

Open the web console in a separate terminal and keep the port-forward running:

```sh
kubectl --context "$KRKN_MGMT_CONTEXT" \
  -n "$KRKN_OPERATOR_NAMESPACE" \
  port-forward service/krkn-operator-console 3000:3000
```

Visit `http://localhost:3000`, create the first administrator account, and log
in. The console communicates with the operator API through its own service.

## 10. Register the private registry

In **Settings → Private Registries**, add a registry with these values:

- Name: `dev-demo-registry`
- Registry URL: the value printed for `$KRKN_REGISTRY_URL` (no `http://`)
- Scenario repository: `demo/krkn-hub`
- Authentication: **Username & Password**, with `$REGISTRY_USER` and
  `$REGISTRY_PASSWORD`
- **Allow Insecure HTTP**: enabled for this local HTTP registry
- **Skip TLS Verification**: leave disabled; this registry has no TLS
- **Available to All Users**: enabled for this isolated demo

The custom image has no Cosign signature. On the same **Settings → Private
Registries** tab, disable **Image signature verification** for this disposable
management cluster.
The operator enables verification by default; keep it enabled for signed
images in normal environments.

## 11. Run and inspect the scenario

In the console, choose **Run Scenario**, select a target that you have already
registered and configured to pull from this registry, choose
`dev-demo-registry`, then select the `dev-demo` scenario. Set `wait` to `2` and
`namespace` to `default`, and start the run. In **Jobs**, inspect its phase and
logs. The output should include `##### DEVELOPMENT SCENARIO #####` and the
names of pods in the target cluster's `default` namespace.

```sh
kubectl --context "$KRKN_MGMT_CONTEXT" \
  -n "$KRKN_OPERATOR_NAMESPACE" get krknscenarioruns,jobs,pods
```

To demonstrate the failure path, run it again with a missing namespace. The
plugin returns `1` and logs a short error without a Python traceback.

The registry has no persistent volume, so its images disappear when the
management Kind cluster is removed. Keep the generated registry credentials
in `$KRKN_DEMO_STATE_DIR` only for the demo session.
