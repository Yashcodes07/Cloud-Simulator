"""Rule-based placement policies. Each takes (nodes, task) -> Node or None."""


def policy_latency_first(nodes, task):
    """Policy A - Lowest-latency-first.
    Rule 1: sort nodes by base latency (Edge < Fog < Cloud).
    Rule 2: pick the first node with enough free CPU and RAM.
    Rule 3: if none fits, reject. (Ignores the task's SLA and balance.)"""
    for node in sorted(nodes, key=lambda n: n.latency):
        if node.can_fit(task.cpu, task.mem):
            return node
    return None


def policy_capacity_aware(nodes, task):
    """Policy B - Capacity-aware.
    Rule 1: keep nodes with enough free CPU and RAM.
    Rule 2: keep nodes whose estimated latency meets the task's SLA limit
            (high<=20ms, medium<=50ms, low<=200ms).
    Rule 3: among them choose the node with the LOWEST utilization after
            placement (tie-break: lower latency). This spreads load and keeps
            Edge free for latency-critical tasks.
    Rule 4: if no node qualifies, reject."""
    ok = [n for n in nodes
          if n.can_fit(task.cpu, task.mem) and n.est_latency(task) <= task.sla_ms]
    if not ok:
        return None
    return min(ok, key=lambda n: (n.utilization(task.cpu, task.mem), n.latency))


POLICIES = {
    "latency_first": policy_latency_first,
    "capacity_aware": policy_capacity_aware,
}
