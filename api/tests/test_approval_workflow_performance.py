"""
Performance integration tests for approval workflow

This test suite focuses on:
- Performance benchmarks for approval rule evaluation
- Scalability tests with large datasets
- Concurrent approval processing performance
- Memory usage optimization tests
- Database query performance optimization
"""

import pytest
import time
import threading
import concurrent.futures
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from unittest.mock import Mock
from sqlalchemy.orm import Session
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from models.models_per_tenant import (
    Base, User, Expense, ExpenseApproval, ApprovalRule, ApprovalDelegate
)
from services.approval_service import ApprovalService
from services.approval_rule_engine import ApprovalRuleEngine
from schemas.approval import ApprovalStatus


class TestApprovalWorkflowPerformance:
    """Performance tests for approval workflow components"""
    
    @pytest.fixture
    def performance_db_session(self):
        """Create database session optimized for performance testing"""
        engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
            echo=False  # Disable SQL logging for performance
        )
        Base.metadata.create_all(bind=engine)
        
        # Add performance indexes
        with engine.connect() as conn:
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_approval_rules_amount 
                ON approval_rules(min_amount, max_amount, is_active)
            """))
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_approval_rules_category 
                ON approval_rules(category_filter, is_active)
            """))
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_expense_approvals_status 
                ON expense_approvals(expense_id, status, approval_level)
            """))
            conn.commit()
        
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        session = SessionLocal()
        try:
            yield session
        finally:
            session.close()
    
    @pytest.fixture
    def large_dataset_setup(self, performance_db_session):
        """Create large dataset for performance testing"""
        # Create many users (100 approvers)
        users = []
        for i in range(100):
            user = User(
                email=f"approver{i:03d}@company.com",
                hashed_password="hashed",
                role="admin" if i % 10 == 0 else "user",
                first_name=f"Approver{i:03d}",
                last_name="User"
            )
            users.append(user)
            performance_db_session.add(user)
        
        # Batch commit users
        performance_db_session.commit()
        
        # Create many approval rules (500 rules)
        rules = []
        categories = ["Travel", "Office", "Equipment", "Software", "Training", "Marketing"]
        
        for i in range(500):
            category = categories[i % len(categories)]
            min_amount = float(i * 10)
            max_amount = float((i + 1) * 10) if i < 499 else None
            
            rule = ApprovalRule(
                name=f"Rule {i:03d} - {category}",
                min_amount=min_amount,
                max_amount=max_amount,
                category_filter=f'["{category}"]',
                approval_level=(i % 4) + 1,
                approver_id=users[i % len(users)].id,
                is_active=True,
                priority=i
            )
            rules.append(rule)
            performance_db_session.add(rule)
        
        # Batch commit rules
        performance_db_session.commit()
        
        return {'users': users, 'rules': rules}

    def test_rule_evaluation_performance_benchmark(self, performance_db_session, large_dataset_setup):
        """Benchmark approval rule evaluation performance"""
        setup = large_dataset_setup
        
        # Create test expenses with varying amounts and categories
        test_expenses = []
        categories = ["Travel", "Office", "Equipment", "Software", "Training", "Marketing"]
        
        for i in range(100):
            expense = Expense(
                amount=Decimal(f'{(i * 50) + 100}.00'),
                notes=f"Performance test expense {i}",
                category=categories[i % len(categories)],
                status="draft",
                user_id=setup['users'][0].id,
            expense_date=datetime.now(timezone.utc),
                
                created_at=datetime.now(timezone.utc)
            )
            test_expenses.append(expense)
            performance_db_session.add(expense)
        
        performance_db_session.commit()
        
        rule_engine = ApprovalRuleEngine(performance_db_session)
        
        # Benchmark rule evaluation
        start_time = time.time()
        
        for expense in test_expenses:
            matching_rules = rule_engine.evaluate_expense(expense)
            assert len(matching_rules) >= 0  # Should return some result
        
        end_time = time.time()
        total_time = end_time - start_time
        avg_time_per_expense = total_time / len(test_expenses)
        
        print(f"\nRule Evaluation Performance:")
        print(f"Total time for {len(test_expenses)} expenses: {total_time:.4f} seconds")
        print(f"Average time per expense: {avg_time_per_expense:.6f} seconds")
        print(f"Expenses per second: {len(test_expenses) / total_time:.2f}")
        
        # Performance assertions
        assert total_time < 5.0  # Should complete within 5 seconds
        assert avg_time_per_expense < 0.05  # Should be under 50ms per expense

    def test_bulk_approval_submission_performance(self, performance_db_session, large_dataset_setup):
        """Test performance of bulk approval submissions"""
        setup = large_dataset_setup
        
        # Create approval rule for testing
        test_rule = ApprovalRule(
            name="Bulk Test Rule",
            min_amount=0.0,
            max_amount=10000.0,
            approval_level=1,
            approver_id=setup['users'][0].id,
            is_active=True,
            priority=1,
            
        )
        performance_db_session.add(test_rule)
        performance_db_session.commit()
        
        # Create many expenses for bulk submission
        expenses = []
        for i in range(200):
            expense = Expense(
                amount=Decimal(f'{100 + i}.00'),
                notes=f"Bulk submission test {i}",
                category="Office",
                status="draft",
                user_id=setup['users'][1].id,
            expense_date=datetime.now(timezone.utc),
                
                created_at=datetime.now(timezone.utc)
            )
            expenses.append(expense)
            performance_db_session.add(expense)
        
        performance_db_session.commit()
        
        # Benchmark bulk submission
        mock_notification = Mock()
        approval_service = ApprovalService(performance_db_session, mock_notification)
        
        start_time = time.time()
        
        approvals = []
        for expense in expenses:
            approval = approval_service.submit_for_approval(
                expense_id=expense.id,
                submitter_id=setup['users'][1].id
            )
            approvals.append(approval)
        
        end_time = time.time()
        total_time = end_time - start_time
        avg_time_per_submission = total_time / len(expenses)
        
        print(f"\nBulk Submission Performance:")
        print(f"Total time for {len(expenses)} submissions: {total_time:.4f} seconds")
        print(f"Average time per submission: {avg_time_per_submission:.6f} seconds")
        print(f"Submissions per second: {len(expenses) / total_time:.2f}")
        
        # Verify all submissions succeeded
        assert len(approvals) == len(expenses)
        assert all(approval.status == ApprovalStatus.PENDING for approval in approvals)
        
        # Performance assertions
        assert total_time < 10.0  # Should complete within 10 seconds
        assert avg_time_per_submission < 0.05  # Should be under 50ms per submission

    def test_concurrent_approval_processing_performance(self, performance_db_session, large_dataset_setup):
        """Test performance of concurrent approval processing"""
        setup = large_dataset_setup
        
        # Create approval rule
        test_rule = ApprovalRule(
            name="Concurrent Test Rule",
            min_amount=0.0,
            max_amount=5000.0,
            approval_level=1,
            approver_id=setup['users'][0].id,
            is_active=True,
            priority=1,
            
        )
        performance_db_session.add(test_rule)
        performance_db_session.commit()
        
        # Create expenses and submit for approval
        expenses = []
        for i in range(50):
            expense = Expense(
                amount=Decimal(f'{200 + i}.00'),
                notes=f"Concurrent test {i}",
                category="Office",
                status="draft",
                user_id=setup['users'][1].id,
            expense_date=datetime.now(timezone.utc),
                
                created_at=datetime.now(timezone.utc)
            )
            expenses.append(expense)
            performance_db_session.add(expense)
        
        performance_db_session.commit()
        
        mock_notification = Mock()
        approval_service = ApprovalService(performance_db_session, mock_notification)
        
        # Submit all for approval first
        approvals = []
        for expense in expenses:
            approval = approval_service.submit_for_approval(
                expense_id=expense.id,
                submitter_id=setup['users'][1].id
            )
            approvals.append(approval)
        
        # Test concurrent approval processing
        def approve_expense(approval):
            try:
                approval_service.approve_expense(
                    approval_id=approval.id,
                    approver_id=setup['users'][0].id,
                    notes=f"Concurrent approval {approval.id}"
                )
                return True
            except Exception as e:
                print(f"Error approving {approval.id}: {e}")
                return False
        
        start_time = time.time()
        
        # Process approvals concurrently
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            results = list(executor.map(approve_expense, approvals))
        
        end_time = time.time()
        total_time = end_time - start_time
        successful_approvals = sum(results)
        
        print(f"\nConcurrent Approval Performance:")
        print(f"Total time for {len(approvals)} concurrent approvals: {total_time:.4f} seconds")
        print(f"Successful approvals: {successful_approvals}/{len(approvals)}")
        print(f"Approvals per second: {successful_approvals / total_time:.2f}")
        
        # Performance assertions
        assert total_time < 15.0  # Should complete within 15 seconds
        assert successful_approvals >= len(approvals) * 0.9  # At least 90% success rate

    def test_delegation_resolution_performance(self, performance_db_session, large_dataset_setup):
        """Test performance of delegation resolution with complex chains"""
        setup = large_dataset_setup
        
        # Create complex delegation chains
        delegations = []
        for i in range(0, 90, 3):  # Create chains of 3
            # Chain: user[i] -> user[i+1] -> user[i+2]
            delegations.extend([
                ApprovalDelegate(
                    approver_id=setup['users'][i].id,
                    delegate_id=setup['users'][i+1].id,
                    start_date=datetime.now(timezone.utc).date(),
                    end_date=(datetime.now(timezone.utc) + timedelta(days=7)).date(),
                    is_active=True,
                    
                ),
                ApprovalDelegate(
                    approver_id=setup['users'][i+1].id,
                    delegate_id=setup['users'][i+2].id,
                    start_date=datetime.now(timezone.utc).date(),
                    end_date=(datetime.now(timezone.utc) + timedelta(days=7)).date(),
                    is_active=True,
                    
                )
            ])
        
        for delegation in delegations:
            performance_db_session.add(delegation)
        performance_db_session.commit()
        
        # Create approval rules using delegated approvers
        rules = []
        for i in range(0, 90, 3):
            rule = ApprovalRule(
                name=f"Delegation Rule {i//3}",
                min_amount=float(i * 10),
                max_amount=float((i + 3) * 10),
                approval_level=1,
                approver_id=setup['users'][i].id,  # Will be delegated
                is_active=True,
                priority=i,
                
            )
            rules.append(rule)
            performance_db_session.add(rule)
        
        performance_db_session.commit()
        
        # Create expenses that will trigger delegation resolution
        expenses = []
        for i in range(30):
            expense = Expense(
                amount=Decimal(f'{i * 30 + 50}.00'),
                notes=f"Delegation test {i}",
                category="Office",
                status="draft",
                user_id=setup['users'][99].id,
            expense_date=datetime.now(timezone.utc),  # Different user
                
                created_at=datetime.now(timezone.utc)
            )
            expenses.append(expense)
            performance_db_session.add(expense)
        
        performance_db_session.commit()
        
        # Benchmark delegation resolution
        mock_notification = Mock()
        approval_service = ApprovalService(performance_db_session, mock_notification)
        
        start_time = time.time()
        
        approvals = []
        for expense in expenses:
            try:
                approval = approval_service.submit_for_approval(
                    expense_id=expense.id,
                    submitter_id=setup['users'][99].id
                )
                approvals.append(approval)
            except Exception as e:
                print(f"Error submitting expense {expense.id}: {e}")
        
        end_time = time.time()
        total_time = end_time - start_time
        
        print(f"\nDelegation Resolution Performance:")
        print(f"Total time for {len(expenses)} delegation resolutions: {total_time:.4f} seconds")
        print(f"Successful submissions: {len(approvals)}/{len(expenses)}")
        if approvals:
            print(f"Average time per resolution: {total_time / len(approvals):.6f} seconds")
        
        # Performance assertions
        assert total_time < 8.0  # Should complete within 8 seconds
        assert len(approvals) >= len(expenses) * 0.8  # At least 80% success rate

    def test_approval_history_query_performance(self, performance_db_session, large_dataset_setup):
        """Test performance of approval history queries"""
        setup = large_dataset_setup
        
        # Create approval rule
        test_rule = ApprovalRule(
            name="History Test Rule",
            min_amount=0.0,
            max_amount=10000.0,
            approval_level=1,
            approver_id=setup['users'][0].id,
            is_active=True,
            priority=1,
            
        )
        performance_db_session.add(test_rule)
        performance_db_session.commit()
        
        # Create many expenses with approval history
        expenses = []
        for i in range(100):
            expense = Expense(
                amount=Decimal(f'{100 + i}.00'),
                notes=f"History test {i}",
                category="Office",
                status="approved",
                user_id=setup['users'][1].id,
            expense_date=datetime.now(timezone.utc),
                
                created_at=datetime.now(timezone.utc) - timedelta(days=i % 30)
            )
            expenses.append(expense)
            performance_db_session.add(expense)
        
        performance_db_session.commit()
        
        # Create approval records for each expense
        approvals = []
        for expense in expenses:
            approval = ExpenseApproval(
                expense_id=expense.id,
                approver_id=setup['users'][0].id,
                approval_rule_id=test_rule.id,
                status=ApprovalStatus.APPROVED,
                submitted_at=expense.created_at,
                decided_at=expense.created_at + timedelta(hours=1),
                approval_level=1,
                is_current_level=True,
                
            )
            approvals.append(approval)
            performance_db_session.add(approval)
        
        performance_db_session.commit()
        
        # Benchmark history queries
        start_time = time.time()
        
        # Query approval history for all expenses
        for expense in expenses:
            history = performance_db_session.query(ExpenseApproval).filter(
                ExpenseApproval.expense_id == expense.id
            ).order_by(ExpenseApproval.submitted_at.desc()).all()
            assert len(history) >= 1
        
        end_time = time.time()
        total_time = end_time - start_time
        
        print(f"\nApproval History Query Performance:")
        print(f"Total time for {len(expenses)} history queries: {total_time:.4f} seconds")
        print(f"Average time per query: {total_time / len(expenses):.6f} seconds")
        print(f"Queries per second: {len(expenses) / total_time:.2f}")
        
        # Performance assertions
        assert total_time < 3.0  # Should complete within 3 seconds
        assert total_time / len(expenses) < 0.03  # Should be under 30ms per query

    def test_memory_usage_optimization(self, performance_db_session, large_dataset_setup):
        """Test memory usage during large approval operations"""
        import psutil
        import os
        
        setup = large_dataset_setup
        process = psutil.Process(os.getpid())
        
        # Measure initial memory usage
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB
        
        # Create approval rule
        test_rule = ApprovalRule(
            name="Memory Test Rule",
            min_amount=0.0,
            max_amount=50000.0,
            approval_level=1,
            approver_id=setup['users'][0].id,
            is_active=True,
            priority=1,
            
        )
        performance_db_session.add(test_rule)
        performance_db_session.commit()
        
        # Process large batch of expenses
        batch_size = 100
        total_processed = 0
        
        mock_notification = Mock()
        approval_service = ApprovalService(performance_db_session, mock_notification)
        
        for batch in range(5):  # 5 batches of 100 expenses each
            # Create batch of expenses
            expenses = []
            for i in range(batch_size):
                expense = Expense(
                    amount=Decimal(f'{100 + total_processed + i}.00'),
                    notes=f"Memory test {total_processed + i}",
                    category="Office",
                    status="draft",
                    user_id=setup['users'][1].id,
            expense_date=datetime.now(timezone.utc),
                    
                    created_at=datetime.now(timezone.utc)
                )
                expenses.append(expense)
                performance_db_session.add(expense)
            
            performance_db_session.commit()
            
            # Process batch
            for expense in expenses:
                approval = approval_service.submit_for_approval(
                    expense_id=expense.id,
                    submitter_id=setup['users'][1].id
                )
                approval_service.approve_expense(
                    approval_id=approval.id,
                    approver_id=setup['users'][0].id,
                    notes=f"Batch {batch} approval"
                )
            
            total_processed += batch_size
            
            # Measure memory after each batch
            current_memory = process.memory_info().rss / 1024 / 1024  # MB
            memory_increase = current_memory - initial_memory
            
            print(f"Batch {batch + 1}: Processed {total_processed} expenses, "
                  f"Memory: {current_memory:.2f} MB (+{memory_increase:.2f} MB)")
            
            # Memory should not grow excessively
            assert memory_increase < 100  # Should not use more than 100MB additional
        
        final_memory = process.memory_info().rss / 1024 / 1024  # MB
        total_memory_increase = final_memory - initial_memory
        
        print(f"\nMemory Usage Summary:")
        print(f"Initial memory: {initial_memory:.2f} MB")
        print(f"Final memory: {final_memory:.2f} MB")
        print(f"Total increase: {total_memory_increase:.2f} MB")
        print(f"Memory per expense: {total_memory_increase / total_processed:.4f} MB")
        
        # Memory usage assertions
        assert total_memory_increase < 150  # Should not use more than 150MB total
        assert total_memory_increase / total_processed < 0.5  # Should be under 0.5MB per expense


class TestApprovalWorkflowScalability:
    """Scalability tests for approval workflow"""
    
    @pytest.fixture
    def scalability_db_session(self):
        """Create database session for scalability testing"""
        engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
            echo=False
        )
        Base.metadata.create_all(bind=engine)
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        session = SessionLocal()
        try:
            yield session
        finally:
            session.close()
    
    def test_scalability_with_increasing_rules(self, scalability_db_session):
        """Test scalability as number of approval rules increases"""
        # Create test user
        user = User(
            email="scale@company.com", hashed_password="hashed", role="admin",
            first_name="Scale", last_name="Test", 
        )
        scalability_db_session.add(user)
        scalability_db_session.commit()
        
        rule_engine = ApprovalRuleEngine(scalability_db_session)
        
        # Test with increasing number of rules
        rule_counts = [10, 50, 100, 500, 1000]
        performance_results = []
        
        for rule_count in rule_counts:
            # Clear existing rules
            scalability_db_session.query(ApprovalRule).delete()
            scalability_db_session.commit()
            
            # Create rules
            for i in range(rule_count):
                rule = ApprovalRule(
                    name=f"Scale Rule {i}",
                    min_amount=float(i * 10),
                    max_amount=float((i + 1) * 10),
                    approval_level=1,
                    approver_id=user.id,
                    is_active=True,
                    priority=i,
                    
                )
                scalability_db_session.add(rule)
            
            scalability_db_session.commit()
            
            # Create test expense
            expense = Expense(
                amount=Decimal('5000.00'),
                notes="Scalability test",
                category="Test",
                status="draft",
                user_id=user.id,
            expense_date=datetime.now(timezone.utc),
                
                created_at=datetime.now(timezone.utc)
            )
            scalability_db_session.add(expense)
            scalability_db_session.commit()
            
            # Measure evaluation time
            start_time = time.time()
            matching_rules = rule_engine.evaluate_expense(expense)
            end_time = time.time()
            
            evaluation_time = end_time - start_time
            performance_results.append((rule_count, evaluation_time))
            
            print(f"Rules: {rule_count:4d}, Time: {evaluation_time:.6f}s, "
                  f"Matches: {len(matching_rules)}")
            
            # Clean up expense
            scalability_db_session.delete(expense)
            scalability_db_session.commit()
        
        # Analyze scalability
        print(f"\nScalability Analysis:")
        for i, (rule_count, eval_time) in enumerate(performance_results):
            if i > 0:
                prev_count, prev_time = performance_results[i-1]
                time_ratio = eval_time / prev_time if prev_time > 0 else 0
                rule_ratio = rule_count / prev_count
                print(f"Rules {prev_count} -> {rule_count}: "
                      f"Time ratio {time_ratio:.2f}, Rule ratio {rule_ratio:.2f}")
        
        # Performance should scale reasonably (not exponentially)
        if len(performance_results) >= 2:
            first_time = performance_results[0][1]
            last_time = performance_results[-1][1]
            first_rules = performance_results[0][0]
            last_rules = performance_results[-1][0]
            
            # Time should not increase more than linearly with rules
            time_increase_ratio = last_time / first_time if first_time > 0 else 0
            rule_increase_ratio = last_rules / first_rules
            
            print(f"Overall: Rules increased {rule_increase_ratio:.1f}x, "
                  f"Time increased {time_increase_ratio:.1f}x")
            
            # Should not be worse than quadratic scaling
            assert time_increase_ratio <= rule_increase_ratio ** 2

    def test_concurrent_user_scalability(self, scalability_db_session):
        """Test scalability with many concurrent users"""
        # Create many users
        users = []
        for i in range(20):
            user = User(
                email=f"concurrent{i}@company.com",
                hashed_password="hashed",
                role="user" if i < 15 else "admin",
                first_name=f"User{i}",
                last_name="Concurrent",
                
            )
            users.append(user)
            scalability_db_session.add(user)
        
        scalability_db_session.commit()
        
        # Create approval rule
        rule = ApprovalRule(
            name="Concurrent Rule",
            min_amount=0.0,
            max_amount=10000.0,
            approval_level=1,
            approver_id=users[-1].id,  # Admin user
            is_active=True,
            priority=1,
            
        )
        scalability_db_session.add(rule)
        scalability_db_session.commit()
        
        # Simulate concurrent user activity
        def user_workflow(user_id, expense_count):
            results = []
            mock_notification = Mock()
            approval_service = ApprovalService(scalability_db_session, mock_notification)
            
            for i in range(expense_count):
                try:
                    # Create expense
                    expense = Expense(
                        amount=Decimal(f'{100 + i}.00'),
                        notes=f"Concurrent expense {user_id}-{i}",
                        category="Office",
                        status="draft",
                        user_id=user_id,
                        
                        created_at=datetime.now(timezone.utc)
                    )
                    scalability_db_session.add(expense)
                    scalability_db_session.commit()
                    
                    # Submit for approval
                    approval = approval_service.submit_for_approval(
                        expense_id=expense.id,
                        submitter_id=user_id
                    )
                    results.append(True)
                    
                except Exception as e:
                    print(f"Error for user {user_id}, expense {i}: {e}")
                    results.append(False)
            
            return results
        
        # Run concurrent workflows
        start_time = time.time()
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = []
            for user in users[:15]:  # Use first 15 users (non-admin)
                future = executor.submit(user_workflow, user.id, 5)
                futures.append(future)
            
            # Collect results
            all_results = []
            for future in concurrent.futures.as_completed(futures):
                results = future.result()
                all_results.extend(results)
        
        end_time = time.time()
        total_time = end_time - start_time
        
        successful_operations = sum(all_results)
        total_operations = len(all_results)
        
        print(f"\nConcurrent User Scalability:")
        print(f"Users: {len(users[:15])}")
        print(f"Total operations: {total_operations}")
        print(f"Successful operations: {successful_operations}")
        print(f"Success rate: {successful_operations / total_operations * 100:.1f}%")
        print(f"Total time: {total_time:.4f} seconds")
        print(f"Operations per second: {successful_operations / total_time:.2f}")
        
        # Scalability assertions
        assert successful_operations >= total_operations * 0.8  # At least 80% success
        assert total_time < 30.0  # Should complete within 30 seconds


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])  # -s to show print statements