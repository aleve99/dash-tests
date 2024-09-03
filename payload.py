from typing import List, Dict
from datetime import datetime
from json import load
from pathlib import Path
from pandas import DataFrame


class Payload:
    loans_data: Dict[str, Dict[str, Dict[str, List[dict]]]] = {}
    symbols: dict = {}
    runtimes_single: dict = {}
    runtimes_group: dict = {}
    timestamp: int = 0
    ranges: List[str] = []
    n_ranges: int = 0

    def __init__(self) -> None:
        self.compute_table()
    
    def read_json(self, filename: Path) -> None:
        if filename.exists():
            with open(filename) as file:
                json_data = load(file)
        
            self.loans_data = json_data["LOANS"]
            self.symbols = json_data["SYMBOLS"]
            self.runtimes_single = json_data["RUNTIMES"]["single"]
            self.runtimes_group = json_data["RUNTIMES"]["group"]
            self.timestamp = datetime.fromtimestamp(json_data["TIMESTAMP"])
            self.ranges = list(self.loans_data['other'].keys())
            self.n_ranges = len(self.ranges)
    
    def compute_table(self) -> None:
        table_dict = {
            "range": [],
            "class": [],
            "storage_address": [],
            "utilization_ratio": [],
            "total_collateral_usd": [],
            "total_borrow_usd": [],
            "loan_type": [],
            **{symbol + "_borrow_usd": [] for symbol in self.symbols.values()},
            **{symbol + "_collateral_usd": [] for symbol in self.symbols.values()}
        }

        for cl ,loans_by_class in self.loans_data.items():
            for r, loans_by_range in loans_by_class.items():
                for loan_type, loans in loans_by_range.items():
                    for loan in loans:
                        table_dict['range'].append(r)
                        table_dict['class'].append(cl)

                        table_dict['storage_address'].append(
                            loan["escrowAddress"]
                        )

                        table_dict['utilization_ratio'].append(
                            int(loan["borrowUtilisationRatio"]) / 1e4
                        )

                        table_dict['total_collateral_usd'].append(
                            int(loan["totalEffectiveCollateralBalanceValue"]) / 1e4
                        )

                        table_dict['total_borrow_usd'].append(
                            int(loan["totalEffectiveBorrowBalanceValue"]) / 1e4
                        )
                        table_dict['loan_type'].append(
                            loan_type
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