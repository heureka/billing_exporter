import logging

log = logging.getLogger('root')

# TODO: Optimize to lower lookup: split this dict for cpu/gpu/ram/whatever
KNOWN_CONTAINERS = {}


class ContainerCost:
    def __init__(self, usage_metric, resource_type) -> None:
        self.resource_type = resource_type
        self.container = usage_metric['metric']['container']
        self.pod = usage_metric['metric']['pod']
        self.namespace = usage_metric['metric']['namespace']
        self.node = usage_metric['metric']['node']
        self.usage_value = float(usage_metric['value'][1])
        # We want to return the ram usage in GB instead of bytes
        if resource_type == 'ram':
            self.usage_value = self.usage_value / 1_000_000_000
        self.request_value = None
        self.node_cost = None
        self.seconds_running = None
        self._last_cost = None

    def add_time_running(self, runtime_seconds_metric):
        self.seconds_running = float(runtime_seconds_metric['value'][1])
        # Calculate usage seconds into per second average
        if self.resource_type == 'cpu':
            self.usage_value = self.usage_value / self.seconds_running

    def add_requests(self, request_metric):
        self.request_value = float(request_metric['value'][1])
        if self.resource_type == 'ram':
            self.request_value = self.request_value / 1_000_000_000

    def add_node_cost(self, cost):
        self.node_cost = float(cost)

    def calculate_cost(self):

        use_request = False
        if self.request_value is not None:
            if self.request_value >= self.usage_value:
                use_request = True
        if use_request:
            resource_time_spent = self.request_value * self.seconds_running
        else:
            resource_time_spent = self.usage_value * self.seconds_running
        result = resource_time_spent * self.node_cost

        if self._last_cost is not None and self._last_cost > result:
            return self._last_cost

        self._last_cost = result
        return result

    def __eq__(self, other):
        return all([
            self.container == other['metric']['container'],
            self.pod == other['metric']['pod'],
            self.namespace == other['metric']['namespace'],
            self.node == other['metric']['node']
        ])
