"""HTTP surface for evidence-grounded answers."""

from typing import Annotated, cast

from fastapi import APIRouter, Depends, Request, status

from ai_knowledge_platform.answers.ports import AnswerGenerator
from ai_knowledge_platform.answers.schemas import AnswerRequest, AnswerResponse
from ai_knowledge_platform.answers.service import answer_question
from ai_knowledge_platform.config import Settings, get_settings
from ai_knowledge_platform.errors import ErrorResponse

router = APIRouter(tags=["answers"])
SettingsDep = Annotated[Settings, Depends(get_settings)]


def get_answer_generator(request: Request) -> AnswerGenerator | None:
    return cast("AnswerGenerator | None", request.app.state.answer_generator)


AnswerGeneratorDep = Annotated[AnswerGenerator | None, Depends(get_answer_generator)]


@router.post(
    "/answers",
    summary="Answer a question only from retrieved evidence",
    responses={
        status.HTTP_404_NOT_FOUND: {"model": ErrorResponse},
        status.HTTP_409_CONFLICT: {"model": ErrorResponse},
        status.HTTP_422_UNPROCESSABLE_CONTENT: {"model": ErrorResponse},
        status.HTTP_502_BAD_GATEWAY: {"model": ErrorResponse},
        status.HTTP_503_SERVICE_UNAVAILABLE: {"model": ErrorResponse},
        status.HTTP_504_GATEWAY_TIMEOUT: {"model": ErrorResponse},
    },
)
async def create_answer(
    request: AnswerRequest,
    settings: SettingsDep,
    generator: AnswerGeneratorDep,
) -> AnswerResponse:
    answer = await answer_question(
        request.question,
        generator=generator,
        documents_dir=settings.documents_dir,
        database_path=settings.knowledge_db_path,
        evidence_limit=settings.answer_evidence_limit,
        document_id=request.document_id,
    )
    return AnswerResponse.from_domain(answer)
