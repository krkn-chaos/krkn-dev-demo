# Copyright 2026 The Krkn Authors
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import logging
import time

import yaml
from krkn_lib.telemetry.ocp import KrknTelemetryOpenshift

from krkn.scenario_plugins.abstract_scenario_plugin import AbstractScenarioPlugin


class DevDemoScenarioPlugin(AbstractScenarioPlugin):
    """The abstract methods are intentionally left for the live demo."""

    def execute_demo(
        self, scenario: str, lib_telemetry: KrknTelemetryOpenshift
    ) -> int:
        """Read one scenario file, wait, then log the pods in its namespace."""
        try:
            with open(scenario, encoding="utf-8") as scenario_file:
                config = yaml.safe_load(scenario_file)

            if not isinstance(config, dict):
                raise ValueError("scenario file must contain a YAML mapping")

            wait = config.get("wait")
            namespace = config.get("namespace")
            if isinstance(wait, bool) or not isinstance(wait, int) or not 0 <= wait <= 60:
                raise ValueError("wait must be an integer from 0 to 60")
            if not isinstance(namespace, str) or not namespace.strip():
                raise ValueError("namespace must be a non-empty string")

            logging.info("Waiting %s seconds before listing pods", wait)
            time.sleep(wait)

            kubernetes = lib_telemetry.get_lib_kubernetes()
            kubernetes.get_namespace_status(namespace)
            pods = kubernetes.list_pods(namespace)
            logging.info(
                "Pods in namespace %s: %s",
                namespace,
                ", ".join(pods) if pods else "(none)",
            )
            return 0
        except Exception:
            logging.exception("Dev demo scenario failed")
            return 1

