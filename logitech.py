import sqlite3
from collections import deque
from datetime import datetime

# Base class for any storage (bin/truck)
class StorageUnit:
    def __init__(self, capacity):
        self.capacity = capacity
        self.used_space = 0

    def occupy_space(self, amount):
        # check before occupying space
        if self.used_space + amount > self.capacity:
            raise ValueError("Not enough space")
        self.used_space += amount

    def free_space(self, amount):
        # free space if rollback happens
        self.used_space = max(0, self.used_space - amount)

    def remaining_space(self):
        return self.capacity - self.used_space


# Storage bin class
class StorageBin(StorageUnit):
    def __init__(self, bin_id, capacity, location_code):
        super().__init__(capacity)
        self.bin_id = bin_id
        self.location_code = location_code

    # sort bins by capacity
    def __lt__(self, other):
        return self.capacity < other.capacity

    def __repr__(self):
        return f"Bin({self.bin_id}, cap={self.capacity}, used={self.used_space})"


# Truck for loading packages
class Truck(StorageUnit):
    def __init__(self, truck_id, capacity):
        super().__init__(capacity)
        self.truck_id = truck_id

    def __repr__(self):
        return f"Truck({self.truck_id}, cap={self.capacity}, used={self.used_space})"


# Package info
class Package:
    def __init__(self, tracking_id, size, destination):
        self.tracking_id = tracking_id
        self.size = size
        self.destination = destination

    def __repr__(self):
        return f"Pkg({self.tracking_id}, size={self.size})"


# Singleton controller
class WarehouseController:
    _instance = None

    @staticmethod
    def get_instance():
        if WarehouseController._instance is None:
            WarehouseController._instance = WarehouseController()
        return WarehouseController._instance

    def __init__(self):
        if WarehouseController._instance is not None:
            raise Exception("Use get_instance(), not direct create")

        # sorted bin list
        self.bin_inventory = []
        # incoming packages FIFO
        self.queue_incoming = deque()
        # stack for truck loading (LIFO)
        self.stack_loading = []

        # DB
        self.db_connection = sqlite3.connect("logitech.db")
        self.db_cursor = self.db_connection.cursor()

        self.setup_database()
        self.load_bins_from_db()

    # create required tables
    def setup_database(self):
        self.db_cursor.execute("""
            CREATE TABLE IF NOT EXISTS bin_configuration (
                bin_id INTEGER PRIMARY KEY,
                capacity INTEGER,
                location_code TEXT
            );
        """)
        self.db_cursor.execute("""
            CREATE TABLE IF NOT EXISTS shipment_logs (
                tracking_id TEXT,
                bin_id INTEGER,
                timestamp TEXT,
                status TEXT
            );
        """)
        self.db_connection.commit()

    def load_bins_from_db(self):
        # if empty table insert demo bins once
        self.db_cursor.execute("SELECT COUNT(*) FROM bin_configuration")
        if self.db_cursor.fetchone()[0] == 0:
            demo = [
                (1, 10, "A1"),
                (2, 20, "A2"),
                (3, 50, "B1"),
                (4, 100, "B2")
            ]
            self.db_cursor.executemany(
                "INSERT INTO bin_configuration VALUES (?, ?, ?)",
                demo
            )
            self.db_connection.commit()

        # load bins from database
        self.db_cursor.execute("SELECT * FROM bin_configuration")
        rows = self.db_cursor.fetchall()
        self.bin_inventory = [StorageBin(r[0], r[1], r[2]) for r in rows]
        self.bin_inventory.sort(key=lambda b: b.capacity)

    def log_action(self, tracking_id, bin_id, status):
        ts = datetime.now().isoformat(timespec="seconds")
        self.db_cursor.execute(
            "INSERT INTO shipment_logs VALUES (?, ?, ?, ?)",
            (tracking_id, bin_id, ts, status)
        )

    # add to incoming queue
    def add_package(self, package):
        print("Ingest:", package)
        self.queue_incoming.append(package)

    def process_package(self):
        if not self.queue_incoming:
            print("No packages left")
            return

        pkg = self.queue_incoming.popleft()
        print("Processing:", pkg)

        try:
            idx = self.find_best_fit_bin(pkg.size)
            if idx == -1:
                print("No bin found for", pkg)
                self.log_action(pkg.tracking_id, None, "NO_BIN")
            else:
                bin_obj = self.bin_inventory[idx]
                bin_obj.occupy_space(pkg.size)
                print("Placed in", bin_obj)
                self.log_action(pkg.tracking_id, bin_obj.bin_id, "BIN_ASSIGNED")

            self.db_connection.commit()

        except Exception as e:
            print("Error:", e)
            self.db_connection.rollback()

    # binary search on sorted bin capacities
    def find_best_fit_bin(self, pkg_size):
        low, high = 0, len(self.bin_inventory)-1
        ans = -1
        while low <= high:
            mid = (low + high)//2
            if self.bin_inventory[mid].capacity >= pkg_size:
                ans = mid
                high = mid - 1
            else:
                low = mid + 1
        return ans

    # recursive try, include or skip package
    def try_load(self, pkgs, i, space, chosen):
        if i == len(pkgs):
            return len(chosen) > 0 and space >= 0

        pkg = pkgs[i]

        if pkg.size <= space:
            chosen.append(pkg)
            if self.try_load(pkgs, i+1, space - pkg.size, chosen):
                return True
            chosen.pop()

        return self.try_load(pkgs, i+1, space, chosen)

    # load fragile packages using backtracking
    def load_fragile(self, truck, fragile_pkgs):
        chosen = []
        if not self.try_load(fragile_pkgs, 0, truck.remaining_space(), chosen):
            print("Not possible in", truck.truck_id)
            return []

        print("Loading:", chosen)

        try:
            for p in chosen:
                self.stack_loading.append((truck, p))
                truck.occupy_space(p.size)
                self.log_action(p.tracking_id, None, "TRUCK_LOADED")
            self.db_connection.commit()
        except:
            self.db_connection.rollback()

        return chosen

    # undo last loads
    def rollback(self, count=None):
        print("Rollback", count if count else "all")
        try:
            removed = 0
            while self.stack_loading and (count is None or removed < count):
                truck, pkg = self.stack_loading.pop()
                truck.free_space(pkg.size)
                self.log_action(pkg.tracking_id, None, "ROLLBACK")
                removed += 1
            self.db_connection.commit()
        except:
            self.db_connection.rollback()

    def show_logs(self):
        print("\nLogs:")
        self.db_cursor.execute("SELECT * FROM shipment_logs")
        for row in self.db_cursor.fetchall():
            print(row)
        print()


# Main for demo
def main():
    w = WarehouseController.get_instance()

    p1 = Package("P001", 5, "Delhi")
    p2 = Package("P002", 12, "Mumbai")
    p3 = Package("P003", 8, "Chennai")
    p4 = Package("P004", 25, "Kolkata")
    p5 = Package("P005", 9, "Bangalore")

    for p in [p1, p2, p3, p4, p5]:
        w.add_package(p)

    for _ in range(5):
        w.process_package()

    truck = Truck("T101", 40)
    fragile = [p1, p3, p5]

    w.load_fragile(truck, fragile)
    w.rollback(1)
    w.show_logs()


if __name__ == "__main__":
    main()
