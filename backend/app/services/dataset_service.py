from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
from pathlib import Path, PurePath
import sqlite3
from uuid import uuid4

import pandas as pd

from app.models.dataset import ColumnMetadata, DatasetDataResponse, DatasetUploadResponse

ALLOWED_EXTENSIONS = {".csv", ".xlsx", ".xls"}


class DatasetUploadError(ValueError):
    """Raised when an uploaded dataset cannot be accepted or parsed."""


@dataclass
class StoredDataset:
    dataframe: pd.DataFrame
    metadata: DatasetUploadResponse


_DATASETS: dict[str, StoredDataset] = {}
_DATA_DIR = Path(__file__).parents[2] / "data"
_DATABASE_PATH = _DATA_DIR / "datasets.sqlite3"


def _initialize_storage() -> None:
    _DATA_DIR.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(_DATABASE_PATH) as connection:
        connection.execute("""
            CREATE TABLE IF NOT EXISTS datasets (
                dataset_id TEXT PRIMARY KEY,
                filename TEXT NOT NULL,
                metadata TEXT NOT NULL,
                data_path TEXT NOT NULL,
                uploaded_at TEXT NOT NULL
            )
        """)


_initialize_storage()


def _extension(filename: str) -> str:
    return PurePath(filename).suffix.lower()


def _load_dataframe(content: bytes, extension: str, sheet_name: str | None) -> tuple[pd.DataFrame, list[str], str | None]:
    if extension == ".csv":
        try:
            dataframe = pd.read_csv(BytesIO(content))
        except (pd.errors.EmptyDataError, pd.errors.ParserError, UnicodeDecodeError) as exc:
            raise DatasetUploadError("The CSV file is empty or corrupted and could not be read.") from exc
        return dataframe, [], None

    try:
        workbook = pd.ExcelFile(BytesIO(content), engine="openpyxl" if extension == ".xlsx" else "xlrd")
        sheet_names = workbook.sheet_names
        if not sheet_names:
            raise DatasetUploadError("The Excel file does not contain any worksheets.")
        selected_sheet = sheet_name or sheet_names[0]
        if selected_sheet not in sheet_names:
            raise DatasetUploadError(f"Worksheet '{selected_sheet}' was not found in the uploaded file.")
        dataframe = pd.read_excel(workbook, sheet_name=selected_sheet)
    except DatasetUploadError:
        raise
    except Exception as exc:
        raise DatasetUploadError("The Excel file is corrupted or could not be read.") from exc
    return dataframe, sheet_names, selected_sheet


def upload_dataset(filename: str | None, content: bytes, sheet_name: str | None = None) -> DatasetUploadResponse:
    safe_filename = filename or "uploaded-dataset"
    extension = _extension(safe_filename)
    if extension not in ALLOWED_EXTENSIONS:
        allowed = ", ".join(sorted(ALLOWED_EXTENSIONS))
        raise DatasetUploadError(f"Unsupported file type '{extension or 'unknown'}'. Allowed types: {allowed}.")
    if not content:
        raise DatasetUploadError("The uploaded file is empty.")

    dataframe, sheet_names, selected_sheet = _load_dataframe(content, extension, sheet_name)
    if dataframe.empty and len(dataframe.columns) == 0:
        raise DatasetUploadError("The uploaded dataset contains no rows or columns.")

    dataset_id = str(uuid4())
    metadata = DatasetUploadResponse(
        dataset_id=dataset_id,
        filename=safe_filename,
        rows=len(dataframe.index),
        columns=len(dataframe.columns),
        column_names=[str(column) for column in dataframe.columns],
        column_metadata=[
            ColumnMetadata(name=str(column), dtype=str(dtype))
            for column, dtype in dataframe.dtypes.items()
        ],
        sheet_names=sheet_names,
        selected_sheet=selected_sheet,
        uploaded_at=pd.Timestamp.now(tz="UTC").isoformat(),
        status="Uploaded",
        message="Dataset uploaded successfully",
    )
    data_path = _DATA_DIR / f"{dataset_id}.pkl"
    dataframe.to_pickle(data_path)
    with sqlite3.connect(_DATABASE_PATH) as connection:
        connection.execute(
            "INSERT INTO datasets (dataset_id, filename, metadata, data_path, uploaded_at) VALUES (?, ?, ?, ?, ?)",
            (dataset_id, safe_filename, metadata.model_dump_json(), str(data_path), metadata.uploaded_at),
        )
    _DATASETS[dataset_id] = StoredDataset(dataframe=dataframe, metadata=metadata)
    return metadata


def get_dataset(dataset_id: str) -> StoredDataset | None:
    stored_dataset = _DATASETS.get(dataset_id)
    if stored_dataset is not None:
        return stored_dataset
    with sqlite3.connect(_DATABASE_PATH) as connection:
        row = connection.execute(
            "SELECT metadata, data_path FROM datasets WHERE dataset_id = ?", (dataset_id,)
        ).fetchone()
    if row is None or not Path(row[1]).exists():
        return None
    metadata = DatasetUploadResponse.model_validate_json(row[0])
    stored_dataset = StoredDataset(dataframe=pd.read_pickle(row[1]), metadata=metadata)
    _DATASETS[dataset_id] = stored_dataset
    return stored_dataset


def list_datasets() -> list[DatasetUploadResponse]:
    with sqlite3.connect(_DATABASE_PATH) as connection:
        rows = connection.execute(
            "SELECT metadata FROM datasets ORDER BY uploaded_at DESC"
        ).fetchall()
    return [DatasetUploadResponse.model_validate_json(row[0]) for row in rows]


def get_dataset_data(dataset_id: str, limit: int = 5000) -> DatasetDataResponse:
    stored_dataset = get_dataset(dataset_id)
    if stored_dataset is None:
        raise DatasetUploadError("The requested dataset was not found.")

    dataframe = stored_dataset.dataframe.head(limit).copy()
    dataframe.columns = [str(column) for column in dataframe.columns]
    dataframe = dataframe.astype(object).where(pd.notna(dataframe), None)
    rows = dataframe.to_dict(orient="records")

    for row in rows:
        for column, value in row.items():
            if hasattr(value, "item"):
                row[column] = value.item()
            elif hasattr(value, "isoformat"):
                row[column] = value.isoformat()

    return DatasetDataResponse(
        dataset_id=dataset_id,
        column_names=list(dataframe.columns),
        rows=rows,
    )
