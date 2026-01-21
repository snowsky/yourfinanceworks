import pytest
from sqlalchemy.orm import Session
from datetime import datetime, timezone, timedelta
from core.models.models_per_tenant import Expense, BankStatementTransaction, Anomaly
from commercial.anomaly_detection.service import AnomalyDetectionService
from core.models.database import set_tenant_context

@pytest.mark.asyncio
async def test_anomaly_detection_integration(db_session: Session):
    """Test that multiple rules can detect anomalies on a single expense"""
    # 1. Setup - Create an expense that triggers multiple rules
    # Round number + duplicate-ish + Sunday (Temporal)
    expense = Expense(
        user_id=1,
        vendor="PHANTOM VENDOR INC",
        amount=500.00,  # Round number
        currency="USD",
        expense_date=datetime(2023, 10, 1, 14, 0, tzinfo=timezone.utc),  # A Sunday
        category="Consulting",
        description="Software consulting for phantom project",
        status="recorded"
    )
    db_session.add(expense)
    db_session.commit()
    db_session.refresh(expense)

    # 2. Run Anomaly Detection
    service = AnomalyDetectionService(db_session)
    await service.analyze_entity(expense, "expense")

    # 3. Verify Anomalies were created
    anomalies = db_session.query(Anomaly).filter(Anomaly.entity_id == expense.id).all()
    
    # We expect at least: Rounding, Phantom Vendor (keyword), Temporal (Sunday)
    rule_ids = [a.rule_id for a in anomalies]
    assert "rounding_anomaly" in rule_ids
    assert "phantom_vendor" in rule_ids
    assert "temporal_anomaly" in rule_ids
    
    # 4. Test Threshold Splitting
    # Create 3 expenses just under $1000 threshold to same vendor
    for i in range(3):
        split_exp = Expense(
            user_id=1,
            vendor="SPLIT VENDOR",
            amount=950.00,
            currency="USD",
            expense_date=datetime.now(timezone.utc),
            category="Hardware",
            status="recorded"
        )
        db_session.add(split_exp)
    db_session.commit()
    
    # Analyze the last one
    last_split = db_session.query(Expense).filter(Expense.vendor == "SPLIT VENDOR").first()
    await service.analyze_entity(last_split, "expense")
    
    split_anomalies = db_session.query(Anomaly).filter(
        Anomaly.entity_id == last_split.id,
        Anomaly.rule_id == "threshold_splitting"
    ).all()
    assert len(split_anomalies) > 0
    print(f"✅ Successfully detected {len(anomalies)} anomalies and splitting logic.")

if __name__ == "__main__":
    # For manual runs if needed
    pass
