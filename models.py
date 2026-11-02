"""Data models: Node, Task, VM + workload generator."""
import random
from dataclasses import dataclass

# Latency limit (ms) a task of each sensitivity can tolerate (its SLA)
SLA_LIMITS_MS = {"high": 20, "medium": 50, "low": 200}
TENANTS = ["tenantA", "tenantB", "tenantC"]


@dataclass
class Node:
    name: str
    tier: str            # Edge / Fog / Cloud
    cpu: int             # total vCPUs
    ram: int             # total GB
    latency: float       # base latency in ms
    used_cpu: float = 0.0
    used_ram: float = 0.0

    @property
    def free_cpu(self):
        return self.cpu - self.used_cpu

    @property
    def free_ram(self):
        return self.ram - self.used_ram

    def utilization(self, extra_cpu=0.0, extra_ram=0.0):
        """Utilization (0..1) = the more loaded of CPU and RAM."""
        return max((self.used_cpu + extra_cpu) / self.cpu,
                   (self.used_ram + extra_ram) / self.ram)

    def can_fit(self, cpu, ram):
        return self.free_cpu >= cpu and self.free_ram >= ram

    def est_latency(self, task):
        """Simulated latency = base * (1 + utilization after placing task)."""
        return self.latency * (1 + self.utilization(task.cpu, task.mem))


@dataclass
class Task:
    task_id: str
    tenant: str
    cpu: int
    mem: int
    sensitivity: str     # low / medium / high

    @property
    def sla_ms(self):
        return SLA_LIMITS_MS[self.sensitivity]


@dataclass
class VM:
    vm_id: str
    host_node: str
    tenant: str
    cpu: int
    ram: int
    status: str = "running"   # running / stopped
    task_id: str = ""


def default_nodes():
    return [
        Node("Edge-1", "Edge", cpu=4, ram=8, latency=5),
        Node("Fog-1", "Fog", cpu=16, ram=32, latency=25),
        Node("Cloud-1", "Cloud", cpu=64, ram=256, latency=100),
    ]


def generate_workload(n=12, seed=42, heavy=False):
    """Reproducible random workload (fixed seed)."""
    rnd = random.Random(seed)
    tasks = []
    for i in range(1, n + 1):
        sens = rnd.choices(["low", "medium", "high"], weights=[3, 3, 4])[0]
        if heavy:
            cpu, mem = rnd.randint(2, 6), rnd.randint(3, 10)
        else:
            cpu, mem = rnd.randint(1, 3), rnd.randint(1, 4)
        tasks.append(Task(f"T{i:02d}", TENANTS[(i - 1) % len(TENANTS)], cpu, mem, sens))
    return tasks
