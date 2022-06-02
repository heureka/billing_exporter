import time
import aiohttp
import asyncio
import logging
from prometheus_client import start_http_server, Gauge

from config import CORTEX, PORT, REFRESH_FREQUENCY, LOG_LEVEL
from container import ContainerCost, KNOWN_CONTAINERS

logging.basicConfig(level=LOG_LEVEL.upper())

container_runtime_cost_total = Gauge('container_runtime_cost_total', 'Total cost of a resource in a workload\'s lifetime', [
    'resource', 'container', 'pod', 'namespace', 'node'])


async def request(query: str):
    logging.info(f'requests: Asking {CORTEX} about {query}')
    async with aiohttp.ClientSession() as session:
        async with session.get(f'{CORTEX}/prometheus/api/v1/query', params={'query': f'{query}'}) as response:
            result = await response.json()

    return result['data']['result']


# params stand for either cpu, ram or gpu cost
async def node_param_second_cost(param: str):
    response = await request(
        f'sum(node_{param}_hourly_cost{{}}) by (exported_instance)')

    second_cost = []
    for node in response:
        second_cost.append({"node": f"{node['metric']['exported_instance']}",
                           f"{param}_second_cost": float((node['value'][1])) / 3600})

    return second_cost


async def container_runtime_seconds() -> list:
    container_start_time_seconds = await request(
        'container_start_time_seconds{namespace!="", pod!="", container!="", node!=""}')

    container_runtime_seconds = []
    time_now = int(time.time())
    for container in container_start_time_seconds:
        container_time = int(container['value'][1])
        # There is a weird bug, where some timestamps are negative, resulting in nonsensical costs.
        # It's better to just not bill them.
        if container_time > 0:
            container['value'][1] = time_now - int(container['value'][1])
            container_runtime_seconds.append(container)

    return container_runtime_seconds


async def container_runtime_cost(param: str) -> list:
    # STAGE 1: Collect all data
    # STAGE 2: Populate Cost object (join data)
    # STAGE 3: Call calculate_cost()
    # STAGE 4: Expose result
    logging.info(f"Calculating runtime cost for param {param}")
    seconds = await container_runtime_seconds()
    node_second_cost = await node_param_second_cost(param)

    if param == "cpu":
        container_resource_usage = await request(
            'container_cpu_usage_seconds_total{namespace!="", pod!="", container!="", node!=""}')
        container_resource_requests = await request(
            'sum(kube_pod_container_resource_requests{resource="cpu", namespace!="", pod!="", container!="", node!=""}) by (pod, container, node, namespace)')
    elif param == "ram":
        container_resource_usage = await request(
            'container_memory_usage_bytes{namespace!="", pod!="", container!="", node!=""}')
        container_resource_requests = await request(
            'sum(kube_pod_container_resource_requests{resource="memory", namespace!="", pod!="", container!="", node!=""}) by (pod, container, node, namespace)')
    elif param == "gpu":
        container_resource_usage = await request(
            'sum without (exported_pod, exported_namespace, exported_instance, exported_container, endpoint, instance, job, service, prometheus, prometheus_replica) (label_replace(label_replace(label_replace(label_replace(container_gpu_allocation, "pod", "$1", "exported_pod", "(.*)"), "namespace", "$1", "exported_namespace", "(.*)"), "node", "$1", "exported_instance", "(.*)"), "container", "$1", "exported_container", "(.*)"))')
        container_resource_requests = []

    container_costs = []

    for container_usage in container_resource_usage:
        # if Promethes doesn't respond, we don't want to crash
        container = container_usage['metric']['container']
        pod = container_usage['metric']['pod']
        namespace = container_usage['metric']['namespace']
        node = container_usage['metric']['node']
        current = KNOWN_CONTAINERS.get(
            f'{param}.{container}.{pod}.{namespace}.{node}')  # returns None

        if current is None:
            try:
                current = ContainerCost(container_usage, param)
            except AttributeError as e:
                logging.error(e)
                break
            KNOWN_CONTAINERS[f'{param}.{container}.{pod}.{namespace}.{node}'] = current
        for seconds_running in seconds:
            if current == seconds_running:
                seconds_found = True
                current.add_time_running(seconds_running)
                break
        else:
            seconds_found = False
        if seconds_found:
            container_costs.append(current)
        else:
            continue
        for node in node_second_cost:
            if current.node == node['node']:
                current.add_node_cost(
                    node[f'{current.resource_type}_second_cost'])
                break
        for req in container_resource_requests:
            if current == req:
                current.add_requests(req)

    return container_costs


async def param_cost(param: str):
    for container in await container_runtime_cost(param):
        container_runtime_cost_total.labels(
            container.resource_type,
            container.container,
            container.pod,
            container.namespace,
            container.node
        ).set(container.calculate_cost())


async def main():
    start_http_server(PORT)
    frequency = REFRESH_FREQUENCY

    while True:
        tasks = [param_cost("cpu"), param_cost("ram"), param_cost("gpu")]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        for result in results:
            if isinstance(result, Exception):
                raise result
        await asyncio.sleep(frequency)


if __name__ == '__main__':
    loop = asyncio.run(main())
