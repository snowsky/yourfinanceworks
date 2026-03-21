"""
Prompt Improvement Service

Agentic loop that identifies the responsible prompt, generates improved versions,
tests them against real documents, evaluates results, and saves the winner.
"""

import json
import logging
from datetime import datetime, timezone
from typing import Optional, Dict, Any, Tuple

from sqlalchemy.orm import Session

from commercial.prompt_management.models.prompt_improvement_job import PromptImprovementJob
from commercial.prompt_management.services.prompt_service import get_prompt_service
from commercial.ai.services.ai_config_service import AIConfigService
from core.services.tenant_database_manager import tenant_db_manager

logger = logging.getLogger(__name__)

# All default prompt names enumerated for the LLM identification call
KNOWN_PROMPT_NAMES = [
    ("pdf_invoice_extraction", "invoice"),
    ("ocr_data_conversion", "invoice"),
    ("email_expense_classification", "expense"),
    ("invoice_data_extraction", "invoice"),
    ("invoice_classification", "invoice"),
    ("bank_transaction_extraction", "bank_statement"),
    ("bank_statement_metadata_extraction", "bank_statement"),
    ("forensic_auditor_phantom_vendor", "audit"),
    ("forensic_auditor_description_mismatch", "audit"),
    ("forensic_auditor_attachment", "audit"),
    ("invoice_review_extraction", "invoice"),
    ("expense_review_extraction", "expense"),
    ("bank_statement_review_extraction", "bank_statement"),
    ("raw_text_extraction", "generic"),
    ("expense_receipt_vision_extraction", "expense"),
    ("portfolio_data_extraction", "portfolio"),
]

DOCUMENT_TYPE_TO_PROMPTS = {
    "invoice": ["invoice_data_extraction", "pdf_invoice_extraction", "ocr_data_conversion"],
    "expense": ["expense_receipt_vision_extraction", "expense_review_extraction", "email_expense_classification"],
    "bank_statement": ["bank_transaction_extraction", "bank_statement_metadata_extraction", "bank_statement_review_extraction"],
    "portfolio": ["portfolio_data_extraction"],
}


class PromptImprovementService:
    """Manages the agentic prompt improvement loop."""

    def __init__(self, db: Session):
        self.db = db
        self.ai_config = AIConfigService.get_ai_config(db, component="chat")

    def _call_llm(self, system_prompt: str, user_content: str) -> str:
        """Call LLM and return text response."""
        if not self.ai_config:
            raise ValueError("No AI configuration available")

        provider = self.ai_config.get("provider_name", "").lower()

        if provider == "openai":
            from langchain_openai import ChatOpenAI
            from langchain_core.messages import SystemMessage, HumanMessage
            llm = ChatOpenAI(
                api_key=self.ai_config.get("api_key"),
                model=self.ai_config.get("model_name"),
                temperature=0.3,
                max_tokens=2000,
            )
            response = llm.invoke([SystemMessage(content=system_prompt), HumanMessage(content=user_content)])
            return response.content

        elif provider == "anthropic":
            from langchain_anthropic import ChatAnthropic
            from langchain_core.messages import SystemMessage, HumanMessage
            llm = ChatAnthropic(
                api_key=self.ai_config.get("api_key"),
                model=self.ai_config.get("model_name"),
                temperature=0.3,
                max_tokens=2000,
            )
            response = llm.invoke([SystemMessage(content=system_prompt), HumanMessage(content=user_content)])
            return response.content

        elif provider == "ollama":
            from langchain_ollama import OllamaLLM
            llm = OllamaLLM(
                base_url=self.ai_config.get("provider_url", "http://localhost:11434"),
                model=self.ai_config.get("model_name"),
                temperature=0.3,
                num_predict=2000,
            )
            full_prompt = f"SYSTEM: {system_prompt}\n\nUSER: {user_content}"
            return llm.invoke(full_prompt)

        else:
            raise ValueError(f"Unsupported provider: {provider}")

    async def identify_affected_prompt(
        self, message: str, document_type: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Use LLM to identify which prompt is responsible for the user's complaint.

        Returns: {prompt_name, category, confidence}
        """
        prompt_list = "\n".join(
            f"- {name} (category: {cat})" for name, cat in KNOWN_PROMPT_NAMES
        )

        # If document_type is given, narrow the candidates
        candidates = []
        if document_type and document_type in DOCUMENT_TYPE_TO_PROMPTS:
            candidates = DOCUMENT_TYPE_TO_PROMPTS[document_type]

        system_prompt = f"""You are an AI system administrator. A user has reported a data extraction problem.
Your job is to identify which prompt template is most likely responsible.

Available prompt templates:
{prompt_list}

{f'The user is working with a {document_type} document, so consider these prompts first: {candidates}' if candidates else ''}

Respond ONLY with a JSON object:
{{"prompt_name": "<name>", "category": "<category>", "confidence": "high|medium|low"}}"""

        response = self._call_llm(system_prompt, f"User complaint: {message}")

        # Parse JSON from response
        text = response.strip()
        if "```" in text:
            text = text.split("```json")[-1].split("```")[0].strip() if "```json" in text else text.split("```")[1].split("```")[0].strip()

        result = json.loads(text)
        logger.info(f"Identified prompt: {result}")
        return result

    async def generate_improved_prompt(
        self,
        prompt_name: str,
        current_content: str,
        user_message: str,
        prior_failure: Optional[str] = None,
    ) -> str:
        """Generate an improved version of the prompt."""
        failure_context = f"\n\nPrevious attempt failed: {prior_failure}" if prior_failure else ""

        system_prompt = """You are an expert at writing AI extraction prompts.
You will be given a prompt template and a user complaint about extraction failures.
Generate an improved version of the prompt that addresses the complaint.
Return ONLY the improved prompt text — no explanations, no markdown fences."""

        user_content = f"""Prompt name: {prompt_name}

Current prompt:
{current_content}

User complaint: {user_message}{failure_context}

Write an improved prompt that fixes the extraction problem described:"""

        return self._call_llm(system_prompt, user_content)

    async def test_prompt_on_document(
        self,
        prompt_content: str,
        doc_type: str,
        doc_id: Optional[int],
        db: Session,
    ) -> Dict[str, Any]:
        """
        Test the candidate prompt on the document without saving the result.

        Returns the raw extraction result dict.
        """
        doc_info = await self._resolve_document(doc_type, doc_id, db)
        if not doc_info:
            return {"error": "No document found to test against", "success": False}

        file_path = doc_info.get("file_path")
        if not file_path:
            return {"error": "Document has no associated file", "success": False}

        try:
            if doc_type == "invoice":
                from commercial.ai_invoice.services.invoice_ai_service import InvoiceAIService
                svc = InvoiceAIService(db)
                result = await svc.extract_invoice_data(file_path, custom_prompt=prompt_content)
                return result

            elif doc_type == "expense":
                from commercial.ai.services.ocr_service import _run_ocr
                result = await _run_ocr(file_path, custom_prompt=prompt_content, db_session=db)
                return result

            elif doc_type == "bank_statement":
                from commercial.ai.services.ocr_service import _run_ocr
                result = await _run_ocr(file_path, custom_prompt=prompt_content, db_session=db)
                return result

            elif doc_type == "portfolio":
                file_type = doc_info.get("file_type", "pdf").lower()
                from plugins.investments.services.llm_extraction_service import LLMExtractionService
                svc = LLMExtractionService(db)
                if file_type == "pdf":
                    result = await svc.extract_portfolio_data_from_pdf(file_path, custom_prompt=prompt_content)
                else:
                    result = await svc.extract_portfolio_data_from_csv(file_path, custom_prompt=prompt_content)
                return result

            else:
                return {"error": f"Unsupported document type: {doc_type}", "success": False}

        except Exception as e:
            logger.error(f"Test extraction failed: {e}")
            return {"error": str(e), "success": False}

    async def evaluate_result(
        self,
        extraction_result: Dict[str, Any],
        user_message: str,
        prompt_name: str,
    ) -> Dict[str, Any]:
        """
        Ask LLM to evaluate whether the extraction result addresses the user's complaint.

        Returns: {passed: bool, reason: str}
        """
        system_prompt = """You are a data quality evaluator.
A user complained about an AI extraction problem. An improved prompt was tested.
Evaluate whether the extraction result fixes the reported issue.
Respond ONLY with JSON: {"passed": true|false, "reason": "<brief explanation>"}"""

        user_content = f"""Original complaint: {user_message}

Prompt: {prompt_name}

Extraction result (truncated):
{json.dumps(extraction_result, default=str)[:1500]}

Does this result fix the problem? JSON only:"""

        response = self._call_llm(system_prompt, user_content)
        text = response.strip()
        if "```" in text:
            text = text.split("```json")[-1].split("```")[0].strip() if "```json" in text else text.split("```")[1].split("```")[0].strip()

        return json.loads(text)

    async def _resolve_document(
        self, doc_type: str, doc_id: Optional[int], db: Session
    ) -> Optional[Dict[str, Any]]:
        """
        Resolve a document to its file path.

        If doc_id is None, finds the most recent document of that type.
        """
        try:
            if doc_type == "invoice":
                from core.models.models_per_tenant import Invoice
                if doc_id:
                    doc = db.query(Invoice).filter(Invoice.id == doc_id).first()
                else:
                    doc = db.query(Invoice).order_by(Invoice.created_at.desc()).first()
                if doc and hasattr(doc, 'file_path') and doc.file_path:
                    return {"file_path": doc.file_path}

            elif doc_type == "expense":
                from core.models.models_per_tenant import Expense
                if doc_id:
                    doc = db.query(Expense).filter(Expense.id == doc_id).first()
                else:
                    doc = db.query(Expense).order_by(Expense.created_at.desc()).first()
                if doc and hasattr(doc, 'file_path') and doc.file_path:
                    return {"file_path": doc.file_path}

            elif doc_type == "bank_statement":
                from core.models.models_per_tenant import BankStatement
                if doc_id:
                    doc = db.query(BankStatement).filter(BankStatement.id == doc_id).first()
                else:
                    doc = db.query(BankStatement).order_by(BankStatement.created_at.desc()).first()
                if doc and hasattr(doc, 'file_path') and doc.file_path:
                    return {"file_path": doc.file_path}

            elif doc_type == "portfolio":
                from plugins.investments.models import InvestmentFileAttachment
                if doc_id:
                    doc = db.query(InvestmentFileAttachment).filter(
                        InvestmentFileAttachment.id == doc_id
                    ).first()
                else:
                    doc = db.query(InvestmentFileAttachment).order_by(
                        InvestmentFileAttachment.id.desc()
                    ).first()
                if doc and doc.local_path:
                    file_type = doc.file_type.value if hasattr(doc.file_type, 'value') else str(doc.file_type)
                    return {"file_path": doc.local_path, "file_type": file_type}

        except Exception as e:
            logger.warning(f"Could not resolve document (type={doc_type}, id={doc_id}): {e}")

        return None


async def run_improvement_loop(job_id: int, tenant_id: int) -> None:
    """
    Main agentic improvement loop. Creates its own DB session.

    Up to 5 iterations: generate → test → evaluate → save if passing.
    Commits job record after each iteration for live frontend polling.
    """
    SessionFactory = tenant_db_manager.get_tenant_session(tenant_id)
    db = SessionFactory()

    try:
        job = db.query(PromptImprovementJob).filter(PromptImprovementJob.id == job_id).first()
        if not job:
            logger.error(f"PromptImprovementJob {job_id} not found")
            return

        job.status = "running"
        db.commit()

        svc = PromptImprovementService(db)
        prompt_service = get_prompt_service(db)

        # Get current prompt content
        template = prompt_service._get_template(job.prompt_name)
        if not template:
            job.status = "failed"
            job.error_message = f"Prompt template '{job.prompt_name}' not found in database"
            job.completed_at = datetime.now(timezone.utc)
            db.commit()
            return

        current_content = template.template_content
        prior_failure: Optional[str] = None
        iteration_log = []

        for iteration in range(1, job.max_iterations + 1):
            job.current_iteration = iteration
            db.commit()

            logger.info(f"Job {job_id}: iteration {iteration}/{job.max_iterations}")

            try:
                # Generate improved prompt
                candidate = await svc.generate_improved_prompt(
                    prompt_name=job.prompt_name,
                    current_content=current_content,
                    user_message=job.user_message,
                    prior_failure=prior_failure,
                )

                # Test on document
                extraction_result = await svc.test_prompt_on_document(
                    prompt_content=candidate,
                    doc_type=job.document_type or "invoice",
                    doc_id=job.document_id,
                    db=db,
                )

                # Evaluate
                eval_result = await svc.evaluate_result(
                    extraction_result=extraction_result,
                    user_message=job.user_message,
                    prompt_name=job.prompt_name,
                )

                passed = eval_result.get("passed", False)
                reason = eval_result.get("reason", "")

                log_entry = {
                    "iteration": iteration,
                    "prompt_preview": candidate[:200],
                    "evaluation": "pass" if passed else "fail",
                    "reason": reason,
                }
                iteration_log.append(log_entry)
                job.iteration_log = iteration_log
                db.commit()

                if passed:
                    # Save the winning prompt as a new version
                    updated_template = prompt_service.update_prompt(
                        name=job.prompt_name,
                        updates={"template_content": candidate},
                        updated_by=job.user_id,
                    )
                    new_version = updated_template.version if updated_template else "?"

                    job.status = "succeeded"
                    job.final_prompt_content = candidate
                    job.final_prompt_version = new_version if isinstance(new_version, int) else None
                    job.result_summary = (
                        f"Prompt '{job.prompt_name}' improved and saved as v{new_version} "
                        f"after {iteration} iteration(s). {reason}"
                    )
                    job.completed_at = datetime.now(timezone.utc)
                    db.commit()
                    logger.info(f"Job {job_id}: succeeded at iteration {iteration}")
                    return

                # Prepare context for next iteration
                prior_failure = f"Iteration {iteration} failed: {reason}"
                current_content = candidate  # use last candidate as starting point

            except Exception as e:
                logger.error(f"Job {job_id} iteration {iteration} error: {e}")
                prior_failure = str(e)
                log_entry = {
                    "iteration": iteration,
                    "prompt_preview": "",
                    "evaluation": "fail",
                    "reason": f"Error: {e}",
                }
                iteration_log.append(log_entry)
                job.iteration_log = iteration_log
                db.commit()

        # Exhausted all iterations without passing
        job.status = "exhausted"
        job.result_summary = (
            f"Could not automatically fix '{job.prompt_name}' after {job.max_iterations} iterations. "
            "Please edit the prompt manually in the Prompt Management page."
        )
        job.completed_at = datetime.now(timezone.utc)
        db.commit()
        logger.info(f"Job {job_id}: exhausted all iterations")

    except Exception as e:
        logger.error(f"PromptImprovementJob {job_id} fatal error: {e}")
        try:
            job = db.query(PromptImprovementJob).filter(PromptImprovementJob.id == job_id).first()
            if job:
                job.status = "failed"
                job.error_message = str(e)
                job.completed_at = datetime.now(timezone.utc)
                db.commit()
        except Exception:
            pass
    finally:
        db.close()
