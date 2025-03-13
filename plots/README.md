# Ephemeral Kubernetes Benchmarking

In order to run the benchmarks, the deployment process must be functional such that the
`rebuild-and-restart.sh` script in the base folder works.
The `benchmark-deployment.sh` script in the same folder is to measure how long it takes for
- The first control node to become available
- The leader file to be created
- The Kubernetes API to become responsive
- The leader_ready file to be created
- The cluster to be ready

These tests work with the default settings except for the first one, which requires the IPs of the control nodes to be listed in the benchmark file.

Once both scripts work, the `deploy-and-benchmark.sh` script can be run, which redeploys the cluster 50 times.
The results are captured in a csv file `deployment_times.csv`.

## Building the plots

Install the requirements in `requirements.txt` and run `python make-plots.py` with the `deployment_times.csv` file in the same folder.
This generates the boxplot used in the paper.
