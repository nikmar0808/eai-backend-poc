#!/bin/bash
# Creates the POC 4 topics. Run by the one-shot Compose service kafka-topics.
# Safe to run again: --if-not-exists leaves an existing topic as it is.
set -euo pipefail                      # stop at the first failing command, unset variable or failing pipe
B=kafka:19092                          # the INTERNAL door
T=/opt/kafka/bin/kafka-topics.sh
# The main topic: 3 partitions, key = meter ID, kept 7 days.
$T --bootstrap-server $B --create --if-not-exists --topic meter-readings-stored \
   --partitions 3 --replication-factor 1 --config retention.ms=604800000
# The dead-letter topic (Stage 5): same partitions, kept 14 days.
$T --bootstrap-server $B --create --if-not-exists --topic meter-readings-stored.DLT \
   --partitions 3 --replication-factor 1 --config retention.ms=1209600000
$T --bootstrap-server $B --list
