"""Route classified local documents into YourFinanceWORKS."""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path

from .api_client import InvestmentAPIClient
from .document_classifier import DocumentClassifier
from .models import ClassifiedDocument, RoutedDocument


class DocumentIngestionAgent:
    """Scans folders, classifies documents, and sends them to the right YFW API."""

    def __init__(self, api_client: InvestmentAPIClient, classifier: DocumentClassifier):
        self.api_client = api_client
        self.classifier = classifier

    def scan_and_classify(self, folder: Path, *, recursive: bool = True) -> list[ClassifiedDocument]:
        return [self.classifier.classify(path) for path in self.classifier.scan(folder, recursive=recursive)]

    def send_to_yfw(
        self,
        documents: list[ClassifiedDocument],
        *,
        portfolio_id: int | None = None,
        export_destination_id: int | None = None,
        client_id: int | None = None,
        webhook_url: str | None = None,
        card_type: str = "auto",
    ) -> list[RoutedDocument]:
        grouped: dict[str, list[ClassifiedDocument]] = defaultdict(list)
        for document in documents:
            grouped[document.document_type].append(document)

        routed: list[RoutedDocument] = []
        batch_documents = grouped.get("expense", []) + grouped.get("invoice", []) + grouped.get("statement", [])
        if batch_documents:
            response = self.api_client.upload_batch_files(
                [Path(document.path) for document in batch_documents],
                document_types=[document.document_type for document in batch_documents],
                export_destination_id=export_destination_id,
                client_id=client_id,
                webhook_url=webhook_url,
                card_type=card_type,
            )
            routed.extend(RoutedDocument(document=document, destination="batch-processing", response=response) for document in batch_documents)

        portfolio_documents = grouped.get("portfolio", [])
        if portfolio_documents:
            if portfolio_id is None:
                raise ValueError("portfolio_id is required when portfolio documents are detected.")
            response = self.api_client.upload_portfolio_files(
                portfolio_id,
                [Path(document.path) for document in portfolio_documents],
            )
            routed.extend(RoutedDocument(document=document, destination="portfolio-import", response=response) for document in portfolio_documents)

        return routed
