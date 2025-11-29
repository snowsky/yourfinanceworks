"""
Batch Completion Worker

Background worker that runs the BatchCompletionMonitor service.
This can be run as a separate process or integrated into the main application.
"""

import asyncio
import logging
import signal
import sys
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from config import get_settings
from core.services.batch_completion_monitor import get_batch_completion_monitor

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class BatchCompletionWorker:
    """
    Worker process for running the batch completion monitor.
    
    Handles graceful shutdown on SIGTERM/SIGINT signals.
    """

    def __init__(self):
        """Initialize the worker."""
        self.monitor = None
        self.shutdown_event = asyncio.Event()
        
        # Set up signal handlers for graceful shutdown
        signal.signal(signal.SIGTERM, self._handle_shutdown_signal)
        signal.signal(signal.SIGINT, self._handle_shutdown_signal)

    def _handle_shutdown_signal(self, signum, frame):
        """Handle shutdown signals."""
        logger.info(f"Received signal {signum}, initiating graceful shutdown...")
        self.shutdown_event.set()

    def create_db_session_factory(self):
        """
        Create a database session factory.
        
        Returns:
            Function that creates database sessions
        """
        settings = get_settings()
        
        # Create engine for master database
        # Note: In production, you may want to use a connection pool
        engine = create_engine(
            settings.DATABASE_URL,
            pool_pre_ping=True,
            pool_recycle=3600
        )
        
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        
        return SessionLocal

    async def run(self):
        """
        Run the batch completion monitor.
        
        Starts the monitor and waits for shutdown signal.
        """
        try:
            logger.info("Starting Batch Completion Worker...")
            
            # Create database session factory
            db_session_factory = self.create_db_session_factory()
            
            # Get monitor instance
            self.monitor = get_batch_completion_monitor(db_session_factory)
            
            # Start monitor in background task
            monitor_task = asyncio.create_task(self.monitor.start())
            
            # Wait for shutdown signal
            await self.shutdown_event.wait()
            
            # Stop monitor
            logger.info("Stopping batch completion monitor...")
            await self.monitor.stop()
            
            # Wait for monitor task to complete
            await monitor_task
            
            logger.info("Batch Completion Worker stopped successfully")
            
        except Exception as e:
            logger.error(f"Error in batch completion worker: {e}", exc_info=True)
            sys.exit(1)


def main():
    """Main entry point for the worker."""
    worker = BatchCompletionWorker()
    
    try:
        asyncio.run(worker.run())
    except KeyboardInterrupt:
        logger.info("Worker interrupted by user")
    except Exception as e:
        logger.error(f"Worker failed: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
