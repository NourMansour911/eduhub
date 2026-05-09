from fastapi import Depends
from typing import Optional
from langchain_openai import ChatOpenAI
import re
from core.request_dependencies import get_lecture_repo, get_langchain_client
from core import Settings, get_settings
from repositories import LectureRepo
from services.summarize.summarize_chain import build_summarize_chain
from services.summarize.summarize_exceptions import (
    SummarizeNotFoundError,
    SummarizeProcessingError,
    SummarizeValidationError,
)
from integrations.llm import LCOpenAI
from helpers import get_logger
from helpers.utils import serialize_content
from src.models.lecture_model import LectureModel

logger = get_logger(__name__)


class SummarizeService:
    def __init__(self, lecture_repo: LectureRepo, settings: Settings, lc_openai_client: LCOpenAI) -> None:
        self.lecture_repo = lecture_repo
        self.settings = settings

        self.llm: ChatOpenAI = lc_openai_client.get_langchain_llm(model=settings.GENERATION_MODEL_ID, temperature=0.1, top_p=0.85)

    async def summarize(self, lecture_id: str, level: int) -> str:
        if not lecture_id:
            raise SummarizeValidationError(details={"field": "lecture_id"})

        lecture = await self.lecture_repo.get_lecture_by_lecture_id(lecture_id)
        if lecture is None:
            raise SummarizeNotFoundError(details={"lecture_id": lecture_id})
        
        lecture_content = serialize_content(lecture.content.content)
        
        lecture_content = self.clean_markdown(lecture_content)

        try:
            chain = build_summarize_chain(self.llm)
            output_text: str = await chain.ainvoke({"lecture_text": lecture_content, "level": level})
            return output_text
        except Exception as e:
            logger.error(
                f"Failed to generate summary for lecture {lecture_id}",
                extra={"error": str(e), "lecture_id": lecture_id},
            )
            raise SummarizeProcessingError(
                message="Failed to generate summary",
                details={"lecture_id": lecture_id, "error": str(e)},
            )
            
            
    def clean_markdown(self, md: str) -> str:
        # Remove page markers
        md = re.sub(r"<!--\s*PageBreak\s*-->", "\n", md)
        md = re.sub(r"<!--\s*PageFooter=.*?-->", "", md)
        md = re.sub(r"<!--\s*PageHeader=.*?-->", "", md)

        # Remove empty figures
        md = re.sub(r"<figure>\s*</figure>", "", md, flags=re.DOTALL)

        # Remove UI artifacts
        ui_noise = [r":selected:", r":unselected:", r"☒", r"☐"]
        for p in ui_noise:
            md = re.sub(p, "", md)

        # Normalize bullets
        md = re.sub(r"\n[·•\-]\s+", "\n- ", md)

        # Remove long numbers
        md = re.sub(r"\b\d{12,}\b", "", md)

        # Collapse whitespace
        md = re.sub(r"[ \t]+", " ", md)
        md = re.sub(r"\n{3,}", "\n\n", md)

        # Trim lines
        md = "\n".join(line.strip() for line in md.splitlines())

        # Final cleanup
        md = re.sub(r"\n{3,}", "\n\n", md)

        return md.strip()


def get_summarize_service(
    lecture_repo: LectureRepo = Depends(get_lecture_repo),
    settings: Settings = Depends(get_settings),
    lc_openai_client: LCOpenAI = Depends(get_langchain_client),
) -> SummarizeService:
    return SummarizeService(lecture_repo=lecture_repo, settings=settings, lc_openai_client=lc_openai_client)
