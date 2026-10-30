#!/usr/bin/env bash
set -e

source /home/krkn/env.sh

cd /home/krkn/kraken
envsubst '$WAIT_SECONDS $NAMESPACE' \
  < scenarios/scenario.yaml.template > scenarios/dev_demo.yaml

python3.11 - <<'PY'
import os
from pathlib import Path

import yaml

config = yaml.safe_load(Path("config/config.yaml").read_text(encoding="utf-8"))
config["kraken"]["kubeconfig_path"] = os.environ.get(
    "KUBECONFIG", "/home/krkn/.kube/config"
)
config["kraken"]["chaos_scenarios"] = [
    {"dev_demo_scenarios": ["scenarios/dev_demo.yaml"]}
]
config["kraken"]["publish_kraken_status"] = False
config["kraken"]["report_formats"] = []
config["tunings"]["wait_duration"] = 0
config["telemetry"]["enabled"] = False
config["telemetry"]["events_backup"] = False
config["resiliency"]["resiliency_run_mode"] = "disabled"
Path("config/dev_demo_config.yaml").write_text(
    yaml.safe_dump(config), encoding="utf-8"
)
PY

exec ./containers/entrypoint.sh --config=config/dev_demo_config.yaml
