import logging
import traceback
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Literal
import numpy as np
from pyarrow import Table
from ray.data import Dataset, ActorPoolStrategy


class BaseRayActor(ABC):
    """Base class for all Ray actors with common initialization and error handling."""
    
    def __init__(self, exclude_columns: list[str] | Literal['*'] = None):
        self.exclude_columns = exclude_columns
        if self.exclude_columns is None:
            self.exclude_columns = []
        elif isinstance(self.exclude_columns, list):
            self.exclude_columns = self.exclude_columns
        elif self.exclude_columns == '*':
            self.exclude_columns = '*'
        else:
            raise ValueError(
                f"input_exclude_columns must be list or '*' but got {type(self.exclude_columns)}"
            )

    def _log_error(self, error: Exception, context: str = "actor process"):
        """Common error logging method."""
        logging.error(f"{datetime.now()} Error in {context}: {error}")
        traceback.print_exc()


class BaseRayFlatMapActor(BaseRayActor):
    def __call__(self, row: dict[str, Any]) -> list[dict[str, Any]]:
        try:
            ret = self._call(row)
            columns = self.exclude_columns
            match columns:
                case list():
                    for column in columns:
                        if column in row:
                            del row[column]
                case '*':
                    row = {}
            return [{**row ,**item} for item in ret]
        except Exception as e:
            self._log_error(e, "actor process row")
            return []

    @abstractmethod
    def _call(self, row: dict[str, Any]) -> list[dict[str, Any]]:
        """Process a single row and return a list of transformed rows."""
        raise NotImplementedError


class BaseRayMapBatchActor(BaseRayActor):
    def __call__(self, batch: dict[str, np.ndarray]) -> dict[str, np.ndarray]:
        try:
            ret = self._call(batch)
            columns = self.exclude_columns
            match columns:
                case list():
                    for column in columns:
                        if column in batch:
                            del batch[column]
                case '*':
                    batch = {}
            return {**batch, **ret}
        except Exception as e:
            self._log_error(e, "actor process batch")
            return {}

    @abstractmethod
    def _call(self, rows: dict[str, np.ndarray]) -> dict[str, np.ndarray]:
        """Process a batch of rows and return transformed batch."""
        raise NotImplementedError


class BaseRayMapBatchPyarrowActor(BaseRayActor):
    def __call__(self, table: Table) -> Table:
        try:
            ret = self._call(table)
            remain_cols = []
            columns = self.exclude_columns
            ret_columns = ret.num_columns
            match columns:
                case list():
                    remain_cols = [col for col in table.column_names if col not in columns]
                case '*':
                    remain_cols = []
            for i, col in enumerate(remain_cols):
                ret = ret.add_column(ret_columns + i, col, table.column(col))
            return ret

        except Exception as e:
            self._log_error(e, "actor process table")
            return table.slice(offset=0, length=0)

    @abstractmethod
    def _call(self, table: Table) -> Table:
        """Process a PyArrow table and return transformed table."""
        raise NotImplementedError


class BaseRayDatasetActor(BaseRayActor):
    def __init__(
        self,
        exclude_columns: list[str] | Literal['*'] = None,
        default_compute: ActorPoolStrategy = None,
        num_cpus: float = None, 
        num_gpus: float = None,
        conda_env: str = None,
    ):
        super().__init__(exclude_columns)
        self.default_compute = default_compute
        self.num_cpus = num_cpus
        self.num_gpus = num_gpus
        self.conda_env = conda_env
    
    def __call__(self, ds: Dataset) -> Dataset:
        try:
            ret = self._call(ds)
            columns = self.exclude_columns
            match columns:
                case list():
                    original_columns = set(ds.columns())
                    ret_columns = set(ret.columns())
                    to_drop = [col for col in columns if col in original_columns and col not in ret_columns]
                    if to_drop:
                        ret = ret.drop_columns(to_drop)
                case '*':
                    pass
            return ret
        except Exception as e:
            self._log_error(e, "actor process dataset")
            return ds.limit(0)
    
    @abstractmethod
    def _call(self, ds: Dataset) -> Dataset:
        """Process a Ray dataset and return transformed dataset."""
        raise NotImplementedError
