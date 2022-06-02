# billing_exporter

`billing_exporter` is an application that consumes metrics from Cortex about the usage and requests of resources in a Kubernetes cluster (emitted by [kube-state-metrics](https://github.com/kubernetes/kube-state-metrics) and [cAdvisor](https://github.com/google/cadvisor)), and joins them together with node resource cost metrics emmited by [cost-model](https://github.com/kubecost/cost-model).

Doing that, it's able to calculate per-minute costs of any running workload in a Kubernetes cluster, and expose those metrics on a Prometheus HTTP scrape endpoint for later use in Prometheus/Grafana.

At the moment, the exporter is able to expose cost metrics of CPU, RAM and GPU and is tested on GCP, but should work on any platform that is supported by [cost-model](https://github.com/kubecost/cost-model).

## Install and Run

### Locally
```bash
$ pip3 install -r requirements.txt
$ CORTEX=http://your.cortex.instance python3 main.py
```

### Using Docker

```
$ docker build -t billing_exporter:latest .
$ docker run -e CORTEX=http://your.cortex.instance -e PORT=9000 -p "9000:9000" billing_exporter:latest
```

### Configuration

Check `config.py` for configuration options.
