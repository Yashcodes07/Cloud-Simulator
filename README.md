# ARM 305 Mini Project - Edge/Fog/Cloud Placement Simulator

A locally runnable Python simulator that places tasks on Edge, Fog or Cloud nodes,
simulates VMs, enforces tenant-based access control, and reports QoS results.

## Setup
```
python -m venv venv
venv\Scripts\activate        # Windows   (Linux/Mac: source venv/bin/activate)
pip install -r requirements.txt
```

## Run
- Interactive menu:  `python main.py`
- All 4 experiments (CSVs + charts into `results/`):  `python experiments.py`

## Files
| File | Purpose |
|---|---|
| models.py | Node, Task, VM classes, workload generator |
| placement.py | Policy A (latency_first), Policy B (capacity_aware) |
| security.py | Demo users, tenant/role check, audit log |
| simulator.py | VM create/stop, task submission, QoS results |
| experiments.py | 4 required experiments + charts |
| main.py | Command-line menu |

## Model
- Nodes: Edge-1 (4 CPU/8 GB/5 ms), Fog-1 (16/32/25 ms), Cloud-1 (64/256/100 ms)
- Simulated latency = base latency x (1 + utilization after placement)
- SLA limits: high <= 20 ms, medium <= 50 ms, low <= 200 ms
- Task status: SUCCESS (placed, within SLA), SLA_VIOLATED (placed, too slow), REJECTED (no node)
- Demo users (no passwords): alice (tenantA), bob (tenantB), carol (tenantC), admin

## Demo flow
1. `python main.py` -> option 3 (policy) -> option 4 (results)
2. Option 5 login as alice -> option 6 view T-id of another tenant -> ACCESS DENIED
3. Option 12 runs all experiments; check `results/`
