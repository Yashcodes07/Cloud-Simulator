"""The 4 required experiments + chart helpers. Outputs go to ./results/"""
import os
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from models import default_nodes, generate_workload
from simulator import Simulator
from security import login, AccessDenied, AUDIT_LOG

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results")
os.makedirs(OUT, exist_ok=True)
POLS = ["latency_first", "capacity_aware"]


def _show(title, df):
    print(f"\n=== {title} ===")
    print(df.to_string(index=False))


def plot_run(sim, path, title="Run results"):
    """Chart: node utilization + task outcome counts for one simulator run."""
    df = sim.results_df()
    fig, ax = plt.subplots(1, 2, figsize=(10, 4))
    names = [n.name for n in sim.nodes]
    ax[0].bar(names, [n.utilization() * 100 for n in sim.nodes], color="#4C78A8")
    ax[0].set_ylabel("Utilization (%)"); ax[0].set_title("Node utilization"); ax[0].set_ylim(0, 105)
    counts = df["status"].value_counts()
    ax[1].bar(counts.index, counts.values, color="#59A14F")
    ax[1].set_title("Task outcomes"); ax[1].set_ylabel("Tasks")
    fig.suptitle(title); fig.tight_layout(); fig.savefig(path, dpi=120); plt.close(fig)
    return path


def _summary_chart(summ, labels_col, path, title):
    """Grouped chart: outcomes + node utilization for several runs."""
    fig, ax = plt.subplots(1, 2, figsize=(11, 4))
    x = range(len(summ))
    w = 0.25
    for i, (col, c) in enumerate([("successful", "#59A14F"), ("sla_violated", "#F28E2B"), ("rejected", "#E15759")]):
        ax[0].bar([p + i * w for p in x], summ[col], w, label=col, color=c)
    ax[0].set_xticks([p + w for p in x]); ax[0].set_xticklabels(summ[labels_col], rotation=15, fontsize=8)
    ax[0].set_ylabel("Tasks"); ax[0].set_title("Placement outcomes"); ax[0].legend(fontsize=8)
    ucols = [c for c in summ.columns if c.startswith("util_")]
    w2 = 0.8 / len(ucols)
    for i, c in enumerate(ucols):
        ax[1].bar([p + i * w2 for p in x], summ[c], w2, label=c[5:-2])
    ax[1].set_xticks([p + 0.4 - w2 / 2 for p in x]); ax[1].set_xticklabels(summ[labels_col], rotation=15, fontsize=8)
    ax[1].set_ylabel("Utilization (%)"); ax[1].set_title("Node utilization"); ax[1].legend(fontsize=8)
    fig.suptitle(title); fig.tight_layout(); fig.savefig(path, dpi=120); plt.close(fig)


# ---------------- Experiment 1: policy comparison ----------------
def experiment1():
    print("\n##### EXPERIMENT 1: Placement policy comparison #####")
    print("Setup: same 12-task workload (seed 42), two policies.")
    print("Expected: capacity_aware gets higher success rate (respects SLA); "
          "latency_first overloads Edge and violates SLA on Fog/Cloud.")
    tasks = generate_workload(12, seed=42)
    sums, detail = [], []
    for p in POLS:
        sim = Simulator()
        df = sim.run(tasks, p)
        detail.append(df)
        sums.append(sim.summary(p))
        _show(f"Placement decisions - {p}",
              df[["task_id", "tenant", "cpu", "mem", "sensitivity", "sla_ms", "node", "latency_ms", "status"]])
        _show(f"Node utilization - {p}", sim.node_table())
    summ = pd.DataFrame(sums)
    _show("Experiment 1 summary", summ)
    pd.concat(detail).to_csv(os.path.join(OUT, "exp1_placements.csv"), index=False)
    summ.to_csv(os.path.join(OUT, "exp1_summary.csv"), index=False)
    _summary_chart(summ, "label", os.path.join(OUT, "exp1_policy_comparison.png"), "Exp 1: Policy comparison")
    return summ


# ---------------- Experiment 2: overload ----------------
def experiment2():
    print("\n##### EXPERIMENT 2: Overload scenario #####")
    print("Setup: 25 heavy tasks (2-6 CPU, 3-10 GB) sent to default nodes.")
    print("Expected: Edge fills first; tasks spill to Fog/Cloud or are rejected when no suitable node remains.")
    tasks = generate_workload(25, seed=7, heavy=True)
    sums, detail = [], []
    for p in POLS:
        sim = Simulator()
        df = sim.run(tasks, p)
        detail.append(df)
        sums.append(sim.summary(p))
        by_node = df.groupby("node")["task_id"].count().rename("tasks").reset_index()
        _show(f"Tasks per node - {p}", by_node)
        _show(f"Rejected tasks - {p}", df[df["status"] == "REJECTED"][["task_id", "cpu", "mem", "sensitivity"]])
        _show(f"Node utilization - {p}", sim.node_table())
    summ = pd.DataFrame(sums)
    _show("Experiment 2 summary", summ)
    pd.concat(detail).to_csv(os.path.join(OUT, "exp2_placements.csv"), index=False)
    summ.to_csv(os.path.join(OUT, "exp2_summary.csv"), index=False)
    _summary_chart(summ, "label", os.path.join(OUT, "exp2_overload.png"), "Exp 2: Overload (25 heavy tasks)")
    return summ


# ---------------- Experiment 3: unauthorized access ----------------
def experiment3():
    print("\n##### EXPERIMENT 3: Unauthorized tenant access #####")
    print("Setup: 12 tasks placed; alice (tenantA) tries to read tenantB's task and stop tenantB's VM.")
    print("Expected: DENIED for cross-tenant; ALLOWED for own tenant and admin.")
    sim = Simulator()
    sim.run(generate_workload(12, seed=42), "capacity_aware")
    alice, bob, admin = login("alice"), login("bob"), login("admin")
    AUDIT_LOG.clear()
    victim = next(r for r in sim.records.values() if r["tenant"] == "tenantB" and r["vm_id"] != "-")
    own = next(r for r in sim.records.values() if r["tenant"] == "tenantA")
    evidence = []

    def attempt(user, action, fn, target):
        try:
            fn()
            res = "ALLOWED"
        except AccessDenied as e:
            res = f"DENIED ({e})"
        evidence.append({"user": user["name"], "action": action, "target": target, "result": res})

    attempt(alice, "view_task", lambda: sim.get_task(alice, victim["task_id"]), f"{victim['task_id']} (tenantB)")
    attempt(alice, "view_task", lambda: sim.get_task(alice, own["task_id"]), f"{own['task_id']} (tenantA)")
    attempt(alice, "stop_vm", lambda: sim.stop_vm(victim["vm_id"], alice), f"{victim['vm_id']} (tenantB)")
    attempt(bob, "view_task", lambda: sim.get_task(bob, victim["task_id"]), f"{victim['task_id']} (tenantB)")
    attempt(admin, "view_task", lambda: sim.get_task(admin, victim["task_id"]), f"{victim['task_id']} (tenantB)")
    ev = pd.DataFrame(evidence)
    _show("Experiment 3 evidence", ev)
    ev.to_csv(os.path.join(OUT, "exp3_access_evidence.csv"), index=False)
    pd.DataFrame(AUDIT_LOG).to_csv(os.path.join(OUT, "exp3_audit_log.csv"), index=False)
    return ev


# ---------------- Experiment 4: before/after capacity/latency ----------------
def experiment4():
    print("\n##### EXPERIMENT 4: Before/after node capacity & latency change #####")
    print("Setup: capacity_aware policy, same workload (20 tasks, seed 3). Baseline vs changed nodes.")
    print("Expected: more Edge capacity -> more high-sensitivity tasks succeed; "
          "higher Fog latency -> medium tasks lose Fog and may be rejected.")
    tasks = generate_workload(20, seed=3)

    def make(edge_cpu=4, edge_ram=8, fog_lat=25, cloud_lat=100):
        n = default_nodes()
        n[0].cpu, n[0].ram = edge_cpu, edge_ram
        n[1].latency, n[2].latency = fog_lat, cloud_lat
        return n

    scen = {
        "baseline": make(),
        "edge capacity x2": make(edge_cpu=8, edge_ram=16),
        "fog latency 25->60ms": make(fog_lat=60),
        "cloud latency 100->150ms": make(cloud_lat=150),
    }
    sums, detail = [], []
    for name, nodes in scen.items():
        sim = Simulator(nodes)
        df = sim.run(tasks, "capacity_aware")
        df.insert(0, "scenario", name)
        detail.append(df)
        sums.append(sim.summary(name))
    summ = pd.DataFrame(sums)
    _show("Experiment 4 summary", summ)
    pd.concat(detail).to_csv(os.path.join(OUT, "exp4_placements.csv"), index=False)
    summ.to_csv(os.path.join(OUT, "exp4_summary.csv"), index=False)
    _summary_chart(summ, "label", os.path.join(OUT, "exp4_before_after.png"), "Exp 4: Before vs after node change")
    return summ


def run_all():
    experiment1(); experiment2(); experiment3(); experiment4()
    print(f"\nAll experiments done. CSVs and charts saved in: {OUT}")


if __name__ == "__main__":
    run_all()
