from fastapi import APIRouter, Request, HTTPException, Depends
from fastapi.responses import JSONResponse
import json
import logging
import re
import os
from typing import Dict, Any, Optional
from datetime import datetime, date, timedelta
from sqlalchemy.orm import Session

from models.database import get_db, set_tenant_context
from models.models_per_tenant import Client, Invoice, Payment, User
from schemas.client import ClientCreate
from schemas.invoice import InvoiceCreate
from services.tenant_database_manager import tenant_db_manager
from sqlalchemy import func

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/slack", tags=["slack"])

def get_slack_db():
    """Get database session for Slack - defaults to tenant 1"""
    tenant_id = 1  # Default to tenant 1 for Slack
    set_tenant_context(tenant_id)
    tenant_session = tenant_db_manager.get_tenant_session(tenant_id)
    db = tenant_session()
    try:
        yield db
    finally:
        db.close()

class SlackCommandParser:
    """Parse Slack commands into structured operations"""
    
    def __init__(self):
        self.patterns = {
            'create_client': [
                r'create client (?P<name>[^,]+)(?:,\s*email:\s*(?P<email>\S+))?(?:,\s*phone:\s*(?P<phone>[^,]+))?',
            ],
            'create_invoice': [
                r'create invoice for (?P<client_name>[^,]+),?\s*amount:\s*(?P<amount>[\d.]+)(?:,\s*due:\s*(?P<due_date>[\d-]+))?',
            ],
            'list_clients': [r'list clients?', r'show clients?'],
            'list_invoices': [r'list invoices?', r'show invoices?'],
            'search_client': [r'find client (?P<query>.+)'],
            'overdue_invoices': [r'overdue invoices?'],
            'outstanding_balance': [r'outstanding balance'],
            'invoice_stats': [r'invoice stats', r'statistics'],
            'analyze_patterns': [r'analyze patterns', r'invoice analysis'],
            'business_recommendations': [r'recommendations', r'business advice'],
            'list_expenses': [r'list expenses?', r'show expenses?'],
            'list_payments': [r'list payments?', r'show payments?'],
            'pending_approvals': [r'pending approvals?', r'my approvals?'],
            'list_reminders': [r'list reminders?', r'show reminders?', r'my reminders?'],
            'due_today': [r'due today', r'reminders today'],
            'overdue_reminders': [r'overdue reminders?'],
            'low_stock': [r'low stock', r'inventory alerts?'],
            'list_inventory': [r'list inventory', r'show inventory']
        }
    
    def parse(self, text: str) -> Dict[str, Any]:
        """Parse Slack command text into structured operation"""
        text = text.strip().lower()
        
        for operation, patterns in self.patterns.items():
            for pattern in patterns:
                match = re.search(pattern, text, re.IGNORECASE)
                if match:
                    return {
                        'operation': operation,
                        'params': match.groupdict() if hasattr(match, 'groupdict') else {}
                    }
        
        return {'operation': 'unknown', 'params': {}, 'original_text': text}

class SlackInvoiceBot:
    """Slack bot with enhanced database operations for business intelligence"""
    
    def __init__(self):
        self.parser = SlackCommandParser()
    
    async def process_command(self, command_data: Dict[str, Any], db: Session) -> Dict[str, Any]:
        """Process Slack command and return response"""
        parsed = self.parser.parse(command_data.get('text', ''))
        operation = parsed['operation']
        params = parsed['params']
        
        try:
            if operation == 'create_client':
                return await self._create_client(params, db)
            elif operation == 'create_invoice':
                return await self._create_invoice(params, db)
            elif operation == 'list_clients':
                return await self._list_clients(db)
            elif operation == 'list_invoices':
                return await self._list_invoices(db)
            elif operation == 'search_client':
                return await self._search_clients(params.get('query', ''), db)
            elif operation == 'overdue_invoices':
                return await self._get_overdue_invoices(db)
            elif operation == 'outstanding_balance':
                return await self._get_outstanding_balance(db)
            elif operation == 'invoice_stats':
                return await self._get_invoice_stats(db)
            elif operation == 'analyze_patterns':
                return await self._analyze_patterns(db)
            elif operation == 'business_recommendations':
                return await self._get_recommendations(db)
            elif operation == 'list_expenses':
                return await self._list_expenses(db)
            elif operation == 'list_payments':
                return await self._list_payments(db)
            elif operation == 'pending_approvals':
                return await self._pending_approvals(db)
            elif operation == 'list_reminders':
                return await self._list_reminders(db)
            elif operation == 'due_today':
                return await self._due_today(db)
            elif operation == 'overdue_reminders':
                return await self._overdue_reminders(db)
            elif operation == 'low_stock':
                return await self._low_stock(db)
            elif operation == 'list_inventory':
                return await self._list_inventory(db)
            else:
                return self._help_response()
        
        except Exception as e:
            logger.error(f"Error processing command: {e}")
            return self._error_response(f"Error: {str(e)}")
    
    async def _create_client(self, params: Dict[str, Any], db: Session) -> Dict[str, Any]:
        """Create a new client with enhanced validation"""
        name = params.get('name', params.get('n', '')).strip()
        email = params.get('email', f"client_{datetime.now().timestamp()}@example.com")
        
        if not name:
            return self._error_response("Client name is required")
        
        try:
            client = Client(
                name=name,
                email=email,
                phone=params.get('phone'),
                created_at=datetime.now(),
                updated_at=datetime.now()
            )
            db.add(client)
            db.commit()
            db.refresh(client)
            
            return self._success_response(
                f"✅ Client created: *{client.name}*\n"
                f"ID: {client.id}\n" +
                (f"Email: {client.email}\n" if client.email else "") +
                (f"Phone: {client.phone}\n" if client.phone else "")
            )
        except Exception as e:
            db.rollback()
            return self._error_response(f"Failed to create client: {str(e)}")
    
    async def _create_invoice(self, params: Dict[str, Any], db: Session) -> Dict[str, Any]:
        """Create a new invoice using MCP tools"""
        client_name = params.get('client_name', '').strip()
        amount = params.get('amount')
        
        if not client_name or not amount:
            return self._error_response("Client name and amount are required")
        
        try:
            tools = self._get_mcp_tools(db)
            
            # Find client by name
            search_result = await tools.search_clients(client_name)
            if not search_result.get('success') or not search_result.get('data'):
                return self._error_response(f"Client '{client_name}' not found")
            
            client = search_result['data'][0]
            
            # Parse due date or use default (30 days from now)
            due_date = params.get('due_date')
            if not due_date:
                due_date = (datetime.now() + timedelta(days=30)).strftime('%Y-%m-%d')
            
            result = await tools.create_invoice(
                client_id=client['id'],
                amount=float(amount),
                due_date=due_date,
                status='draft'
            )
            
            if result.get('success'):
                invoice = result['data']
                return self._success_response(
                    f"✅ Invoice created: *#{invoice['number']}*\n"
                    f"Client: {client['name']}\n"
                    f"Amount: ${invoice['amount']:.2f}\n"
                    f"Due: {invoice['due_date']}\n"
                    f"Status: {invoice['status']}"
                )
            else:
                return self._error_response(result.get('error', 'Failed to create invoice'))
        except Exception as e:
            return self._error_response(f"Failed to create invoice: {str(e)}")
    
    async def _list_clients(self, db: Session) -> Dict[str, Any]:
        """List all clients using MCP tools"""
        try:
            clients = db.query(Client).limit(10).all()
            
            if not clients:
                return self._success_response("No clients found")
            
            text = "📋 *Clients:*\n"
            for client in clients:
                # Calculate outstanding balance
                outstanding = db.query(func.sum(Invoice.amount)).filter(
                    Invoice.client_id == client.id,
                    Invoice.status.in_(['pending', 'sent'])
                ).scalar() or 0
                
                balance_text = f" (${outstanding:.2f})" if outstanding > 0 else ""
                text += f"• {client.name}{balance_text}\n"
            
            return self._success_response(text)
        except Exception as e:
            return self._error_response(f"Failed to list clients: {str(e)}")
    
    async def _list_invoices(self, db: Session) -> Dict[str, Any]:
        """List recent invoices using MCP tools"""
        try:
            tools = self._get_mcp_tools(db)
            result = await tools.list_invoices(limit=10)
            
            if result.get('success'):
                invoices = result['data']
                if not invoices:
                    return self._success_response("No invoices found")
                
                text = "📄 *Recent Invoices:*\n"
                for invoice in invoices:
                    status_emoji = "✅" if invoice['status'] == 'paid' else "⏳"
                    client_name = invoice.get('client_name', 'Unknown')
                    text += f"{status_emoji} #{invoice['number']} - {client_name} - ${invoice['amount']:.2f}\n"
                
                return self._success_response(text)
            else:
                return self._error_response(result.get('error', 'Failed to list invoices'))
        except Exception as e:
            return self._error_response(f"Failed to list invoices: {str(e)}")
    
    async def _search_clients(self, query: str, db: Session) -> Dict[str, Any]:
        """Search for clients using MCP tools"""
        try:
            tools = self._get_mcp_tools(db)
            result = await tools.search_clients(query)
            
            if result.get('success'):
                clients = result['data']
                if not clients:
                    return self._success_response(f"No clients found matching '{query}'")
                
                text = f"🔍 *Clients matching '{query}':*\n"
                for client in clients[:5]:
                    text += f"• {client['name']}"
                    if client.get('email'):
                        text += f" ({client['email']})"
                    text += "\n"
                
                return self._success_response(text)
            else:
                return self._error_response(result.get('error', 'Failed to search clients'))
        except Exception as e:
            return self._error_response(f"Failed to search clients: {str(e)}")
    
    async def _get_overdue_invoices(self, db: Session) -> Dict[str, Any]:
        """Get overdue invoices using MCP tools"""
        try:
            tools = self._get_mcp_tools(db)
            result = await tools.get_overdue_invoices()
            
            if result.get('success'):
                invoices = result['data']
                if not invoices:
                    return self._success_response("🎉 No overdue invoices!")
                
                text = f"⚠️ *{len(invoices)} Overdue Invoices:*\n"
                total_overdue = 0
                for invoice in invoices[:10]:
                    client_name = invoice.get('client_name', 'Unknown')
                    text += f"• #{invoice['number']} - {client_name} - ${invoice['amount']:.2f}\n"
                    total_overdue += invoice['amount']
                
                text += f"\n💰 Total overdue: ${total_overdue:.2f}"
                return self._success_response(text)
            else:
                return self._error_response(result.get('error', 'Failed to get overdue invoices'))
        except Exception as e:
            return self._error_response(f"Failed to get overdue invoices: {str(e)}")
    
    async def _get_outstanding_balance(self, db: Session) -> Dict[str, Any]:
        """Get clients with outstanding balance using MCP tools"""
        try:
            tools = self._get_mcp_tools(db)
            result = await tools.get_clients_with_outstanding_balance()
            
            if result.get('success'):
                clients = result['data']
                if not clients:
                    return self._success_response("🎉 No outstanding balances!")
                
                text = f"💰 *Clients with Outstanding Balance:*\n"
                total_outstanding = 0
                for client in clients[:10]:
                    balance = client.get('outstanding_balance', 0)
                    text += f"• {client['name']}: ${balance:.2f}\n"
                    total_outstanding += balance
                
                text += f"\n💰 Total outstanding: ${total_outstanding:.2f}"
                return self._success_response(text)
            else:
                return self._error_response(result.get('error', 'Failed to get outstanding balance'))
        except Exception as e:
            return self._error_response(f"Failed to get outstanding balance: {str(e)}")
    
    async def _get_invoice_stats(self, db: Session) -> Dict[str, Any]:
        """Get invoice statistics using MCP tools"""
        try:
            tools = self._get_mcp_tools(db)
            result = await tools.get_invoice_stats()
            
            if result.get('success'):
                stats = result['data']
                text = "📊 *Invoice Statistics:*\n"
                if 'total_income' in stats:
                    text += f"💰 Total Income: ${stats['total_income']:.2f}\n"
                
                # Get additional stats
                invoices_result = await tools.list_invoices(limit=1000)
                if invoices_result.get('success'):
                    invoices = invoices_result['data']
                    paid_count = len([i for i in invoices if i['status'] == 'paid'])
                    pending_count = len([i for i in invoices if i['status'] in ['pending', 'sent']])
                    
                    text += f"📄 Total Invoices: {len(invoices)}\n"
                    text += f"✅ Paid: {paid_count}\n"
                    text += f"⏳ Pending: {pending_count}\n"
                
                return self._success_response(text)
            else:
                return self._error_response(result.get('error', 'Failed to get invoice stats'))
        except Exception as e:
            return self._error_response(f"Failed to get stats: {str(e)}")
    
    async def _analyze_patterns(self, db: Session) -> Dict[str, Any]:
        """Analyze invoice patterns with business intelligence"""
        try:
            # Get invoice data for analysis
            invoices = db.query(Invoice).join(Client).all()
            
            if not invoices:
                return self._success_response("No invoices found for analysis")
            
            # Basic pattern analysis
            total_amount = sum(inv.amount for inv in invoices)
            avg_amount = total_amount / len(invoices)
            paid_count = len([inv for inv in invoices if inv.status == 'paid'])
            overdue_count = len([inv for inv in invoices if inv.due_date < datetime.now() and inv.status != 'paid'])
            
            text = f"📈 *Invoice Pattern Analysis:*\n"
            text += f"• Average invoice: ${avg_amount:.2f}\n"
            text += f"• Payment rate: {(paid_count/len(invoices)*100):.1f}%\n"
            text += f"• Overdue rate: {(overdue_count/len(invoices)*100):.1f}%\n"
            
            return self._success_response(text)
        except Exception as e:
            return self._error_response(f"Failed to analyze patterns: {str(e)}")
    
    async def _get_recommendations(self, db: Session) -> Dict[str, Any]:
        """Get business recommendations based on data analysis"""
        try:
            # Analyze data for recommendations
            overdue_invoices = db.query(Invoice).filter(
                Invoice.due_date < datetime.now(),
                Invoice.status != 'paid'
            ).count()
            
            total_outstanding = db.query(func.sum(Invoice.amount)).filter(
                Invoice.status.in_(['pending', 'sent'])
            ).scalar() or 0
            
            recommendations = []
            
            if overdue_invoices > 0:
                recommendations.append(f"⚠️ Follow up on {overdue_invoices} overdue invoices")
            
            if total_outstanding > 1000:
                recommendations.append(f"💰 ${total_outstanding:.2f} in outstanding payments - consider payment reminders")
            
            if not recommendations:
                recommendations.append("✅ Business is running smoothly!")
            
            text = f"💡 *Business Recommendations:*\n"
            for rec in recommendations:
                text += f"• {rec}\n"
            
            return self._success_response(text)
        except Exception as e:
            return self._error_response(f"Failed to get recommendations: {str(e)}")
    
    async def _list_expenses(self, db: Session) -> Dict[str, Any]:
        """List recent expenses"""
        try:
            from models.models_per_tenant import Expense
            expenses = db.query(Expense).order_by(Expense.expense_date.desc()).limit(10).all()
            
            if not expenses:
                return self._success_response("No expenses found")
            
            text = "💳 *Recent Expenses:*\n"
            total = 0
            for exp in expenses:
                text += f"• ${exp.amount:.2f} - {exp.category} - {exp.vendor or 'N/A'}\n"
                total += exp.amount
            text += f"\n💰 Total: ${total:.2f}"
            
            return self._success_response(text)
        except Exception as e:
            return self._error_response(f"Failed to list expenses: {str(e)}")
    
    async def _list_payments(self, db: Session) -> Dict[str, Any]:
        """List recent payments"""
        try:
            payments = db.query(Payment).order_by(Payment.payment_date.desc()).limit(10).all()
            
            if not payments:
                return self._success_response("No payments found")
            
            text = "💵 *Recent Payments:*\n"
            total = 0
            for payment in payments:
                text += f"• ${payment.amount:.2f} - {payment.payment_method}\n"
                total += payment.amount
            text += f"\n💰 Total: ${total:.2f}"
            
            return self._success_response(text)
        except Exception as e:
            return self._error_response(f"Failed to list payments: {str(e)}")
    
    async def _pending_approvals(self, db: Session) -> Dict[str, Any]:
        """Get pending approvals"""
        try:
            from models.models_per_tenant import ExpenseApproval, Expense
            approvals = db.query(ExpenseApproval).join(Expense).filter(
                ExpenseApproval.status == 'pending'
            ).limit(10).all()
            
            if not approvals:
                return self._success_response("🎉 No pending approvals!")
            
            text = f"⏳ *{len(approvals)} Pending Approvals:*\n"
            for approval in approvals:
                expense = db.query(Expense).filter(Expense.id == approval.expense_id).first()
                if expense:
                    text += f"• ${expense.amount:.2f} - {expense.category}\n"
            
            return self._success_response(text)
        except Exception as e:
            return self._error_response(f"Failed to get pending approvals: {str(e)}")
    
    async def _list_reminders(self, db: Session) -> Dict[str, Any]:
        """List active reminders"""
        try:
            from models.models_per_tenant import Reminder
            reminders = db.query(Reminder).filter(
                Reminder.status.in_(['pending', 'snoozed']),
                Reminder.is_deleted == False
            ).order_by(Reminder.due_date).limit(10).all()
            
            if not reminders:
                return self._success_response("No active reminders")
            
            text = "🔔 *Active Reminders:*\n"
            for reminder in reminders:
                status_emoji = "⏰" if reminder.status == 'pending' else "😴"
                text += f"{status_emoji} {reminder.title} - Due: {reminder.due_date.strftime('%Y-%m-%d')}\n"
            
            return self._success_response(text)
        except Exception as e:
            return self._error_response(f"Failed to list reminders: {str(e)}")
    
    async def _due_today(self, db: Session) -> Dict[str, Any]:
        """Get reminders due today"""
        try:
            from models.models_per_tenant import Reminder
            from datetime import timezone
            today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
            today_end = today_start + timedelta(days=1)
            
            reminders = db.query(Reminder).filter(
                Reminder.status == 'pending',
                Reminder.due_date >= today_start,
                Reminder.due_date < today_end,
                Reminder.is_deleted == False
            ).all()
            
            if not reminders:
                return self._success_response("🎉 No reminders due today!")
            
            text = f"📅 *{len(reminders)} Reminders Due Today:*\n"
            for reminder in reminders:
                text += f"• {reminder.title}\n"
            
            return self._success_response(text)
        except Exception as e:
            return self._error_response(f"Failed to get due today reminders: {str(e)}")
    
    async def _overdue_reminders(self, db: Session) -> Dict[str, Any]:
        """Get overdue reminders"""
        try:
            from models.models_per_tenant import Reminder
            from datetime import timezone
            now = datetime.now(timezone.utc)
            
            reminders = db.query(Reminder).filter(
                Reminder.status == 'pending',
                Reminder.due_date < now,
                Reminder.is_deleted == False
            ).all()
            
            if not reminders:
                return self._success_response("🎉 No overdue reminders!")
            
            text = f"⚠️ *{len(reminders)} Overdue Reminders:*\n"
            for reminder in reminders:
                days_overdue = (now - reminder.due_date).days
                text += f"• {reminder.title} ({days_overdue}d overdue)\n"
            
            return self._success_response(text)
        except Exception as e:
            return self._error_response(f"Failed to get overdue reminders: {str(e)}")
    
    async def _low_stock(self, db: Session) -> Dict[str, Any]:
        """Get low stock inventory items"""
        try:
            from models.models_per_tenant import InventoryItem
            items = db.query(InventoryItem).filter(
                InventoryItem.track_stock == True,
                InventoryItem.current_stock <= InventoryItem.minimum_stock,
                InventoryItem.is_active == True
            ).limit(10).all()
            
            if not items:
                return self._success_response("🎉 No low stock items!")
            
            text = f"📦 *{len(items)} Low Stock Items:*\n"
            for item in items:
                text += f"• {item.name}: {item.current_stock} (min: {item.minimum_stock})\n"
            
            return self._success_response(text)
        except Exception as e:
            return self._error_response(f"Failed to get low stock items: {str(e)}")
    
    async def _list_inventory(self, db: Session) -> Dict[str, Any]:
        """List inventory items"""
        try:
            from models.models_per_tenant import InventoryItem
            items = db.query(InventoryItem).filter(
                InventoryItem.is_active == True
            ).limit(10).all()
            
            if not items:
                return self._success_response("No inventory items found")
            
            text = "📦 *Inventory Items:*\n"
            for item in items:
                stock_info = f" ({item.current_stock} in stock)" if item.track_stock else ""
                text += f"• {item.name} - ${item.unit_price:.2f}{stock_info}\n"
            
            return self._success_response(text)
        except Exception as e:
            return self._error_response(f"Failed to list inventory: {str(e)}")
    
    def _success_response(self, text: str) -> Dict[str, Any]:
        """Format success response for Slack"""
        return {
            "response_type": "in_channel",
            "text": text
        }
    
    def _error_response(self, error: str) -> Dict[str, Any]:
        """Format error response for Slack"""
        return {
            "response_type": "ephemeral",
            "text": f"❌ {error}"
        }
    
    def _help_response(self) -> Dict[str, Any]:
        """Show help message"""
        help_text = """
🤖 *Invoice Bot Commands:*

*Clients:*
• `create client John Doe, email: john@example.com`
• `list clients` | `find client John`

*Invoices:*
• `create invoice for John Doe, amount: 500, due: 2024-02-15`
• `list invoices` | `overdue invoices`

*Expenses & Payments:*
• `list expenses` | `list payments`

*Approvals:*
• `pending approvals` | `my approvals`

*Reminders:*
• `list reminders` | `due today` | `overdue reminders`

*Inventory:*
• `list inventory` | `low stock`

*Reports:*
• `outstanding balance` | `invoice stats`
• `analyze patterns` | `recommendations`
        """
        return self._success_response(help_text.strip())

# Global bot instance
bot = SlackInvoiceBot()

@router.post("/commands")
async def handle_slack_command(request: Request, db: Session = Depends(get_slack_db)):
    """Handle Slack slash commands"""
    try:
        
        # Parse form data from Slack
        form_data = await request.form()
        command_data = {
            'token': form_data.get('token'),
            'text': form_data.get('text', ''),
            'user_name': form_data.get('user_name'),
            'channel_name': form_data.get('channel_name')
        }
        
        # Verify Slack token
        expected_token = os.getenv('SLACK_VERIFICATION_TOKEN')
        if expected_token and command_data.get('token') != expected_token:
            raise HTTPException(status_code=401, detail="Invalid token")
        
        # Process command with direct database access
        response = await bot.process_command(command_data, db)
        return JSONResponse(response)
        
    except Exception as e:
        logger.error(f"Error handling Slack command: {e}")
        return JSONResponse({
            "response_type": "ephemeral",
            "text": f"❌ Error processing command: {str(e)}"
        })

@router.get("/health")
async def slack_health_check():
    """Health check for Slack integration"""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat()
    }