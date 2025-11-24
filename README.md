# LogisTech – Automated Warehouse System

This project implements a simplified warehouse control system based on the LogisTech problem statement.

## Features

- **Singleton Controller** (`WarehouseController`):
  - Central “control tower” for the warehouse
  - Manages bins, incoming conveyor queue, loading stack, and database connection

- **Conveyor Belt (Queue)**:
  - Incoming packages are stored in a FIFO queue (`queue_incoming`)
  - `add_package()` adds to the queue
  - `process_package()` processes them in arrival order

- **Loading Dock (Stack + Rollback)**:
  - Truck loading uses a stack (`stack_loading`) → LIFO behaviour
  - `load_fragile()` pushes packages onto the stack
  - `rollback()` pops from the stack and frees truck space

- **Best-Fit Bin Selection (Binary Search)**:
  - Bins are stored as `StorageBin` objects and sorted by capacity
  - `find_best_fit_bin()` uses binary search to find the smallest bin
    with `capacity >= package_size` in O(log N)

- **Backtracking Shipment Planner**:
  - `try_load()` uses recursion and backtracking to decide if a subset
    of fragile packages can fit into the remaining truck space
  - `load_fragile()` calls this function and then loads the chosen packages

- **SQL Persistence (SQLite)**:
  - `bin_configuration` table stores bin configuration
  - `shipment_logs` table stores:
    - `tracking_id`, `bin_id`, `timestamp`, `status`
  - All actions (bin assignment, truck load, rollback, etc.) are logged

## How to Run

1. Make sure you have Python 3 installed.
2. Run the script:

   ```bash
   python warehouse.py
