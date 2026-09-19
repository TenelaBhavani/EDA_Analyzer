from fastapi import APIRouter, File, Form, HTTPException, UploadFile, status

from app.models.dataset import DatasetDataResponse, DatasetListResponse, DatasetUploadResponse
from app.services.dataset_service import DatasetUploadError, get_dataset_data, list_datasets, upload_dataset

router = APIRouter(prefix="/datasets", tags=["datasets"])


@router.get("", response_model=DatasetListResponse)
def datasets() -> DatasetListResponse:
    return DatasetListResponse(datasets=list_datasets())


@router.post("/upload", response_model=DatasetUploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_dataset_file(
    file: UploadFile = File(...),
    sheet_name: str | None = Form(default=None),
) -> DatasetUploadResponse:
    try:
        content = await file.read()
        return upload_dataset(file.filename, content, sheet_name=sheet_name)
    except DatasetUploadError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The uploaded dataset could not be processed.",
        ) from exc


@router.get("/{dataset_id}/data", response_model=DatasetDataResponse)
def dataset_data(dataset_id: str) -> DatasetDataResponse:
    try:
        return get_dataset_data(dataset_id)
    except DatasetUploadError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
