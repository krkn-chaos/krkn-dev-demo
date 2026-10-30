#!/usr/bin/env bash
set -e

source /home/krkn/main_env.sh
source /home/krkn/env.sh
source /home/krkn/common_run.sh

checks
cd /home/krkn/kraken
envsubst < scenarios/scenario.yaml.template > scenarios/dev_demo.yaml
envsubst < config/config.yaml.template > config/dev_demo_config.yaml
python3.11 run_kraken.py --config=config/dev_demo_config.yaml
