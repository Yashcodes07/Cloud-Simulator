"""ARM 305 - Edge/Fog/Cloud placement simulator (command-line menu)."""
import os
from models import Task, generate_workload, SLA_LIMITS_MS, TENANTS
from simulator import Simulator
from security import USERS, login, AccessDenied, AUDIT_LOG
import experiments
import pandas as pd

MENU = """
========== Edge/Fog/Cloud Simulator ==========
 1  Show nodes
 2  Show workload (tasks)
 3  Run workload with a placement policy
 4  Show results table + QoS summary
 5  Login (switch user)
 6  View a task record (access control)
 7  List VMs
 8  Create VM manually
 9  Stop a VM
10  Add / submit a custom task
11  Save results CSV + chart (current run)
12  Run all 4 experiments
13  Show audit log
 0  Exit
"""


def ask(prompt):
    try:
        return input(prompt).strip()
    except EOFError:
        return "0"


def pick_policy():
    c = ask("Policy [1=latency_first, 2=capacity_aware]: ")
    return "latency_first" if c == "1" else "capacity_aware"


def main():
    sim, tasks, user, policy = Simulator(), generate_workload(12, seed=42), None, None
    while True:
        print(MENU)
        print(f"[user: {user['name'] if user else 'not logged in'} | policy: {policy or 'none'} | tasks: {len(tasks)}]")
        c = ask("Choose: ")
        if c == "0":
            print("Bye."); break
        elif c == "1":
            print(sim.node_table().to_string(index=False))
        elif c == "2":
            print(pd.DataFrame([t.__dict__ for t in tasks]).to_string(index=False))
        elif c == "3":
            policy = pick_policy()
            sim = Simulator()
            sim.run(tasks, policy)
            print(f"Ran {len(tasks)} tasks with {policy}.")
            print(sim.results_df()[["task_id", "tenant", "sensitivity", "sla_ms", "node", "vm_id", "latency_ms", "status"]].to_string(index=False))
        elif c == "4":
            if not sim.records:
                print("Run a workload first (option 3)."); continue
            print(sim.results_df().to_string(index=False))
            print("\nNode utilization:"); print(sim.node_table().to_string(index=False))
            print("\nQoS summary:")
            for k, v in sim.summary(policy or "").items():
                print(f"  {k}: {v}")
        elif c == "5":
            print("Demo users:", ", ".join(USERS))
            u = login(ask("Username: "))
            if u: user = u; print(f"Logged in as {u['name']} (tenant={u['tenant']}, role={u['role']})")
            else: print("Unknown user.")
        elif c == "6":
            if not user: print("Login first (option 5)."); continue
            try:
                rec = sim.get_task(user, ask("Task ID (e.g. T01): ").upper())
                print(rec if rec else "Task not found.")
            except AccessDenied as e:
                print("ACCESS DENIED:", e)
        elif c == "7":
            if not sim.vms: print("No VMs yet."); continue
            print(pd.DataFrame([v.__dict__ for v in sim.vms.values()]).to_string(index=False))
        elif c == "8":
            if not user: print("Login first (option 5)."); continue
            tenant = user["tenant"] or ask("Tenant for VM (e.g. tenantA): ")
            node = sim.node(ask("Node name (Edge-1/Fog-1/Cloud-1): "))
            if not node: print("Unknown node."); continue
            try:
                vm = sim.create_vm(node, tenant, int(ask("vCPU: ")), int(ask("RAM GB: ")))
            except ValueError:
                print("Enter whole numbers."); continue
            print(vm if vm else "Not enough free capacity on that node.")
        elif c == "9":
            if not user: print("Login first (option 5)."); continue
            try:
                print("Result:", sim.stop_vm(ask("VM ID (e.g. VM001): ").upper(), user))
            except AccessDenied as e:
                print("ACCESS DENIED:", e)
        elif c == "10":
            try:
                tid = f"T{len(tasks) + 1:02d}"
                tenant = ask("Tenant (tenantA/B/C): ")
                if tenant not in TENANTS:
                 print("Use tenantA, tenantB or tenantC."); continue
                cpu, mem = int(ask("CPU: ")), int(ask("Memory GB: "))
                sens = ask("Sensitivity (low/medium/high): ").lower()
                if sens not in SLA_LIMITS_MS: print("Invalid sensitivity."); continue
                t = Task(tid, tenant, cpu, mem, sens)
            except ValueError:
                print("Enter whole numbers."); continue
            tasks.append(t)
            policy = policy or pick_policy()
            print("Placed:", sim.submit(t, policy))
        elif c == "11":
            if not sim.records: print("Run a workload first."); continue
            csv = os.path.join(experiments.OUT, "current_run.csv")
            sim.results_df().to_csv(csv, index=False)
            png = experiments.plot_run(sim, os.path.join(experiments.OUT, "current_run.png"), f"Policy: {policy}")
            print("Saved:", csv, "and", png)
        elif c == "12":
            experiments.run_all()
        elif c == "13":
            print(pd.DataFrame(AUDIT_LOG).to_string(index=False) if AUDIT_LOG else "Audit log empty.")
        else:
            print("Invalid choice.")


if __name__ == "__main__":
    main()
