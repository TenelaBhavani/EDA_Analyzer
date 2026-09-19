from pydantic import BaseModel, Field


class ColumnMetadata(BaseModel):
    name: str
    dtype: str


class DatasetUploadResponse(BaseModel):
    dataset_id: str
    filename: str
    rows: int
    columns: int
    column_names: list[str]
    column_metadata: list[ColumnMetadata] = Field(default_factory=list)
    sheet_names: list[str] = Field(default_factory=list)
    selected_sheet: str | None = None
    uploaded_at: str
    status: str = "Uploaded"
    message: str


class DatasetDataResponse(BaseModel):
    dataset_id: str
    column_names: list[str]
    rows: list[dict[str, object]]


class DatasetListResponse(BaseModel):
    datasets: list[DatasetUploadResponse]


class AssistantMessageRequest(BaseModel):
    question: str
    dataset_id: str | None = None
    plot_type: str | None = None
    selected_columns: list[str] = Field(default_factory=list)
    graph_generated: bool = False
    graph_row_limit: int = Field(default=5000, ge=1, le=50000)


class AssistantMessageResponse(BaseModel):
    answer: str
