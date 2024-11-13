from typing import List, Dict, Tuple, Optional
from datetime import datetime
from json import load
from pathlib import Path
from pandas import DataFrame

def correct_range(ratio: float, lb: float, hb: float) -> bool:
    return ratio >= lb and (True if hb == 1 else ratio < hb)


def find_range(ratio: float, bounds: List[Tuple[float, float]]) -> Optional[int]:
    for i, (lb, hb) in enumerate(bounds):
        if correct_range(ratio, lb, hb):
            return i

    return None

class Payload:
    liquidator_data: Dict[str, List[List[dict]]] = {}
    symbols: dict = {}
    categories: List[str] = []
    runtimes_single: Dict[str, List[float]] = {}
    runtimes_group: Dict[str, List[float]] = {}
    timestamp: int = 0
    ranges: List[Tuple[float, float]] = []
    n_ranges: int = 0

    def __init__(self) -> None:
        pass
    
    def read_json(self, filename: Path) -> None:
        if filename.exists():
            with open(filename) as file:
                json_data = load(file)
        
            self.liquidator_data = json_data["liquidators"]
            self.symbols = json_data["symbols"]
            self.categories = [cat.lower() for cat in json_data["categories"]]
            self.timestamp = datetime.fromtimestamp(json_data["timestamp"])
            self.ranges = json_data["ranges"]
            self.n_ranges = len(self.ranges)

            self.runtimes_single = {}
            self.runtimes_group = {}

            for category in self.categories:
                self.runtimes_single[category] = []
                self.runtimes_group[category] = []

                for liquidator in self.liquidator_data[category.upper()]:
                    self.runtimes_single[category].append(liquidator["query_time_avg"])
                    self.runtimes_group[category].append(liquidator["query_time"])

    def compute_table(self) -> None:
        table_dict = {
            "range": [],
            "category": [],
            "storage_address": [],
            "user_address": [],
            "utilization_ratio": [],
            "st_ratio": [],
            "total_collateral_usd": [],
            "total_borrow_usd": [],
            **{symbol + "_borrow_usd": [] for symbol in self.symbols.values()},
            **{symbol + "_collateral_usd": [] for symbol in self.symbols.values()}
        }

        for category in self.categories:
            for liquidator in self.liquidator_data[category.upper()]:
                for loan in liquidator['jobs']:
                    table_dict['category'].append(category)

                    table_dict['storage_address'].append(
                        loan["escrowAddress"]
                    )
                    table_dict['user_address'].append(
                        loan["userAddress"]
                    )

                    table_dict['st_ratio'].append(
                        loan["stabilityRatio"]
                    )

                    ut = int(loan["totalEffectiveBorrowBalanceValue"]) / int(loan["totalEffectiveCollateralBalanceValue"])
                    table_dict['utilization_ratio'].append(ut)

                    table_dict['range'].append(find_range(ut, self.ranges))

                    table_dict['total_collateral_usd'].append(
                        int(loan["totalEffectiveCollateralBalanceValue"]) / 1e4
                    )

                    table_dict['total_borrow_usd'].append(
                        int(loan["totalEffectiveBorrowBalanceValue"]) / 1e4
                    )

                    for asset_id, symbol in self.symbols.items():
                        collaterals: list = loan['collaterals']
                        borrows: list = loan['borrows']

                        collateral = list(filter(lambda c: c['assetId'] == int(asset_id), collaterals))
                        borrow = list(filter(lambda c: c['assetId'] == int(asset_id), borrows))

                        table_dict[symbol + "_collateral_usd"].append(
                            int(collateral[0]['effectiveBalanceValue']) / 1e4 if len(collateral) != 0 else 0
                        )

                        table_dict[symbol + "_borrow_usd"].append(
                            int(borrow[0]['effectiveBorrowBalanceValue']) / 1e4 if len(borrow) != 0 else 0
                        )
    
        self.df = DataFrame(data=table_dict)