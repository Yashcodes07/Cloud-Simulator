"""Core simulator: nodes, VMs, task submission, QoS results."""
import pandas as pd
from models import VM, default_nodes
from placement import POLICIES
from security import AccessDenied, can_access, log_access


class Simulator:
    def __init__(self, nodes=None):
        self.nodes = nodes if nodes is not None else default_nodes()
        self.vms = {}        # vm_id -> VM
        self.records = {}    # task_id -> result dict (protected, per tenant)
        self._vm_n = 0

    def node(self, name):
        return next((n for n in self.nodes if n.name == name), None)

    # ---------- VM simulation ----------
    def create_vm(self, node, tenant, cpu, ram, task_id=""):
        if not node.can_fit(cpu, ram):
            return None
        node.used_cpu += cpu
        node.used_ram += ram
        self._vm_n += 1
        vm = VM(f"VM{self._vm_n:03d}", node.name, tenant, cpu, ram, "running", task_id)
        self.vms[vm.vm_id] = vm
        return vm

    def stop_vm(self, vm_id, user=None):
        vm = self.vms.get(vm_id)
        if vm is None:
            return "not found"
        if user is not None:
            ok = can_access(user, vm.tenant)
            log_access(user, "stop_vm", vm_id, ok)
            if not ok:
                raise AccessDenied(f"{user['name']} cannot stop {vm_id} (owned by {vm.tenant})")
        if vm.status == "stopped":
            return "already stopped"
        node = self.node(vm.host_node)
        node.used_cpu -= vm.cpu
        node.used_ram -= vm.ram
        vm.status = "stopped"
        return "stopped"

    # ---------- Task submission ----------
    def submit(self, task, policy):
        node = POLICIES[policy](self.nodes, task)
        rec = {"task_id": task.task_id, "tenant": task.tenant, "cpu": task.cpu,
               "mem": task.mem, "sensitivity": task.sensitivity,
               "sla_ms": task.sla_ms, "policy": policy}
        if node is None:
            rec.update(node="-", vm_id="-", latency_ms=None, status="REJECTED")
        else:
            lat = round(node.est_latency(task), 2)
            vm = self.create_vm(node, task.tenant, task.cpu, task.mem, task.task_id)
            ok = lat <= task.sla_ms
            rec.update(node=node.name, vm_id=vm.vm_id, latency_ms=lat,
                       status="SUCCESS" if ok else "SLA_VIOLATED")
        self.records[task.task_id] = rec
        return rec

    def run(self, tasks, policy):
        for t in tasks:
            self.submit(t, policy)
        return self.results_df()

    # ---------- Protected access ----------
    def get_task(self, user, task_id):
        rec = self.records.get(task_id)
        if rec is None:
            return None
        ok = can_access(user, rec["tenant"])
        log_access(user, "view_task", task_id, ok)
        if not ok:
            raise AccessDenied(f"{user['name']} ({user['tenant']}) cannot view "
                               f"{task_id} owned by {rec['tenant']}")
        return rec

    # ---------- Results ----------
    def results_df(self):
        return pd.DataFrame(list(self.records.values()))

    def node_table(self):
        return pd.DataFrame([{
            "node": n.name, "tier": n.tier, "cpu": n.cpu, "ram_gb": n.ram,
            "latency_ms": n.latency, "used_cpu": n.used_cpu, "used_ram": n.used_ram,
            "utilization_%": round(n.utilization() * 100, 1)} for n in self.nodes])

    def summary(self, label=""):
        df = self.results_df()
        total = len(df)
        placed = df[df["status"] != "REJECTED"]
        s = {"label": label, "total_tasks": total,
             "successful": int((df["status"] == "SUCCESS").sum()),
             "sla_violated": int((df["status"] == "SLA_VIOLATED").sum()),
             "rejected": int((df["status"] == "REJECTED").sum()),
             "avg_latency_ms": round(placed["latency_ms"].astype(float).mean(), 2) if len(placed) else 0}
        s["failed"] = s["sla_violated"] + s["rejected"]
        s["success_rate_%"] = round(100 * s["successful"] / total, 1) if total else 0
        for n in self.nodes:
            s[f"util_{n.name}_%"] = round(n.utilization() * 100, 1)
        return s
