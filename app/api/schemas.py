from pydantic import BaseModel, HttpUrl
from typing import List, Optional, Union

class ScanRequest(BaseModel):
    url: HttpUrl

class ScanResponse(BaseModel):
    task_id: str

class LinkCheckResult(BaseModel):
    url: str
    status: Union[int, str]
    type: str
    parent: Optional[str]
    details: str

class TaskStatus(BaseModel):
    task_id: str
    status: str
    result: Optional[dict] = None

class ResultsResponse(BaseModel):
    task_id: str
    results: List[LinkCheckResult]
    message: Optional[str] = None 