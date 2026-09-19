from fastapi import APIRouter, HTTPException, status

from app.models.dataset import AssistantMessageRequest, AssistantMessageResponse
from app.services.assistant_service import answer_question
from app.services.dataset_service import DatasetUploadError

router = APIRouter(prefix="/assistant", tags=["assistant"])


@router.post("/messages", response_model=AssistantMessageResponse)
def assistant_message(request: AssistantMessageRequest) -> AssistantMessageResponse:
    try:
        return answer_question(request)
    except DatasetUploadError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc