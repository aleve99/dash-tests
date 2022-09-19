from json import dump
from algorand_modules import Clients
from algorand_modules.custom_clients.algofi_lending_client import LendingVersion
from algosdk.error import AlgodHTTPError, IndexerHTTPError
from urllib.error import URLError
from multiprocessing.pool import ThreadPool
from app import PATH

NUM_THREADS, run, storage_addresses = 6, True, None
clients = Clients(lending_version=LendingVersion.V2)
MIN_USD = 1

def sublist(starting_list: list, num_out: int):
    to_return, i = [[] for _ in range(num_out)], 0
    for item in starting_list:
        to_return[i].append(item)
        i += 1
        if i == num_out:
            i = 0

    return to_return

def deserialize(starting_list):
    to_return = []
    for item in starting_list:
        for sub_item in item:
            to_return.append(sub_item)

    return to_return

def threads_update():
    global run, storage_addresses

    if storage_addresses == None:
        storage_addresses = clients.algofi_client.storage_accounts()

    jobs = sublist(storage_addresses, NUM_THREADS)

    def register_utilization_ratio(addresses):
        states = []
        for address in addresses:
            try:
                user_state = clients.algofi_client.get_user_lending_state(address)
                if user_state["info"]["total_collateral_usd"] > MIN_USD:
                    states.append(user_state)
                else:
                    storage_addresses.remove(address)
            except (AlgodHTTPError, IndexerHTTPError, URLError):
                pass
        return states

    pool = ThreadPool(NUM_THREADS)
    results = pool.map(register_utilization_ratio, jobs)
    pool.close()
   
    with open(PATH, "w") as file:
        dump([ {"ranges_index": None, "jobs": result} for result in results ], file)

if __name__ == "__main__":
    while True:
        threads_update()
        print("Jobs updated")