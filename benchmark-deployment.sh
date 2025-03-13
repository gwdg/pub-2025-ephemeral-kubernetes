#!/bin/bash

#set -xe

aggregated_time=0

# Create a CSV file if it doesn't exist
CSV_FILE="deployment_times.csv"
if [ ! -f "$CSV_FILE" ]; then
  echo "Stage 1,Stage 2,Stage 3,Stage 4,Stage 5,Aggregated" > "$CSV_FILE"
fi

# Stage 1: Measure time until first node is reachable
echo "Stage 1: Waiting for first node to be reachable..."
start_time=$(date +%s.%N)
while ! (nc -z -w 1 10.0.0.1 22 || nc -z -w 1 10.0.0.2 22 || nc -z -w 1 10.0.0.8 22); do
  sleep 0.1
done
end_time=$(date +%s.%N)
stage_time=$(bc -l <<< "scale=3; $end_time - $start_time")
echo "First node is reachable. Time taken: $stage_time seconds"
aggregated_time=$(bc -l <<< "scale=3; $aggregated_time + $stage_time")
stage1_time=$stage_time

# Stage 2: Measure time until leader file is created on NFS share
echo "Stage 2: Waiting for leader file to be created on NFS share..."
start_time=$(date +%s.%N)
while [ ! -f "/share/leader" ]; do
  sleep 0.1
done
end_time=$(date +%s.%N)
stage_time=$(bc -l <<< "scale=3; $end_time - $start_time")
echo "Leader file is created on NFS share. Time taken: $stage_time seconds"
aggregated_time=$(bc -l <<< "scale=3; $aggregated_time + $stage_time")
stage2_time=$stage_time

# Stage 3: Measure time until Kubernetes https endpoint is reachable
echo "Stage 3: Waiting for Kubernetes https endpoint to be reachable..."
start_time=$(date +%s.%N)
while ! curl -s -f -k -m 1 https://vip.kubernetes.local:6443/healthz; do
  sleep 0.1
done
end_time=$(date +%s.%N)
stage_time=$(bc -l <<< "scale=3; $end_time - $start_time")
echo "Kubernetes https endpoint is reachable. Time taken: $stage_time seconds"
aggregated_time=$(bc -l <<< "scale=3; $aggregated_time + $stage_time")
stage3_time=$stage_time

# Stage 4: Measure time until leader_ready file is created on NFS share
echo "Stage 4: Waiting for leader_ready file to be created on NFS share..."
start_time=$(date +%s.%N)
while [ ! -f "/share/leader_ready" ]; do
  sleep 0.1
done
end_time=$(date +%s.%N)
stage_time=$(bc -l <<< "scale=3; $end_time - $start_time")
echo "Leader_ready file is created on NFS share. Time taken: $stage_time seconds"
aggregated_time=$(bc -l <<< "scale=3; $aggregated_time + $stage_time")
stage4_time=$stage_time

# Stage 5: Measure time until all nodes report ready status as returned by kubectl
echo "Stage 5: Waiting for all nodes to report ready status..."
start_time=$(date +%s.%N)
export KUBECONFIG=/share/kube.config
while [ $(kubectl get nodes -o=jsonpath='{.items[*].status.conditions[?(@.type=="Ready")].status}' | tr ' ' '\n' | grep -v "True" | wc -l) -gt 0 ] || [ $(kubectl get nodes -o json | jq '.items | length') -ne 5 ]; do
  sleep 0.1
done
end_time=$(date +%s.%N)
stage_time=$(bc -l <<< "scale=3; $end_time - $start_time")
echo "Ready status reported by all nodes. Time taken: $stage_time seconds"
aggregated_time=$(bc -l <<< "scale=3; $aggregated_time + $stage_time")
stage5_time=$stage_time

echo "Aggregated time for all stages: $aggregated_time seconds"
echo "$stage1_time,$stage2_time,$stage3_time,$stage4_time,$stage5_time,$aggregated_time" >> "$CSV_FILE"
