from fastapi import Depends
from typing import Dict
from langchain_openai import ChatOpenAI
import re
import asyncio
from core.request_dependencies import get_lecture_repo, get_langchain_client
from core import Settings, get_settings
from repositories import LectureRepo
from services.summarize.summarize_chain import build_summarize_chain
from helpers.utils import serialize_content
from services.summarize.summarize_exceptions import (
    SummarizeNotFoundError,
    SummarizeProcessingError,
)
from integrations.llm import LCOpenAI
from helpers import get_logger
from models import LectureModel

logger = get_logger(__name__)




class SummarizeService:
    def __init__(self, lecture_repo: LectureRepo,summary_llm: ChatOpenAI) :
        self.lecture_repo = lecture_repo
        self.chain = build_summarize_chain(summary_llm)

    async def generate_all_summaries(self, lecture_content) -> Dict[str, str]:
        content = serialize_content(lecture_content)

        # Prefer the markdown/text content field when available.
        if isinstance(content, dict) and isinstance(content.get("content"), str):
            content_text = content["content"]
        else:
            content_text = str(content)

        content_text = self.clean_markdown(content_text)

        tasks = [
            self._generate_summary(content_text, level)
            for level in [0, 1, 2]
        ]

        results = await asyncio.gather(*tasks)
        # MongoDB documents require string keys.
        return {"0": results[0], "1": results[1], "2": results[2]}

            
    async def get_summary(self, lecture_id: str, level: int) -> str:

        lecture = await self.lecture_repo.get_lecture_by_lecture_id(lecture_id)
        if lecture is None:
            raise SummarizeNotFoundError(details={"lecture_id": lecture_id})


        cached = None
        if lecture.summaries:
            if level in lecture.summaries:
                cached = lecture.summaries[level]
            elif str(level) in lecture.summaries: 
                cached = lecture.summaries[str(level)]

        if cached:
            logger.info(f"Returning cached summary for lecture {lecture_id}, level {level}")
            return cached
        else:
            raise SummarizeNotFoundError(
                details={"lecture_id": lecture_id, "level": level, "message": "Summary not generated during lecture creation"}
            )



    async def _generate_summary(self, content_text: str, level: int) -> str:

        try:

            summary: str = await self.chain.ainvoke({"lecture_text": content_text, "level": level})
            return summary
        except Exception as e:
            logger.error(
                f"Failed to generate summary",
                extra={"error": str(e), "level": level},
            )
            raise SummarizeProcessingError(
                message="Failed to generate summary",
                details={"level": level, "error": str(e)},
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
    lc_openai_client: LCOpenAI = Depends(get_langchain_client),
    settings: Settings = Depends(get_settings),
) -> SummarizeService:
    summary_llm = lc_openai_client.get_langchain_llm(
        model=settings.GENERATION_MODEL_ID,
        temperature=0.1,
        top_p=0.85,
    )

    return SummarizeService(lecture_repo=lecture_repo, summary_llm=summary_llm)