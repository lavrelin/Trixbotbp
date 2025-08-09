from apscheduler.schedulers.asyncio import AsyncIOScheduler
from services.db import db
from models import Scheduler
from sqlalchemy import select
from datetime import datetime, timedelta
from config import Config
import random
import logging
import asyncio

logger = logging.getLogger(__name__)

class SchedulerService:
    """Service for scheduled messages"""
    
    def __init__(self, bot):
        self.bot = bot
        self.scheduler = AsyncIOScheduler()
        self.job = None
        
    async def init(self):
        """Initialize scheduler"""
        self.scheduler.start()
        await self.check_and_start()
        logger.info("Scheduler service initialized")
    
    async def check_and_start(self):
        """Check if scheduler should be running"""
        async with db.get_session() as session:
            result = await session.execute(
                select(Scheduler).where(Scheduler.id == 1)
            )
            scheduler_config = result.scalar_one_or_none()
            
            if scheduler_config and scheduler_config.enabled:
                await self.start()
    
    async def start(self):
        """Start scheduler"""
        if self.job:
            self.job.remove()
        
        # Schedule next message
        await self.schedule_next_message()
        logger.info("Scheduler started")
    
    def stop(self):
        """Stop scheduler"""
        if self.job:
            self.job.remove()
            self.job = None
        logger.info("Scheduler stopped")
    
    async def schedule_next_message(self):
        """Schedule next promotional message"""
        async with db.get_session() as session:
            result = await session.execute(
                select(Scheduler).where(Scheduler.id == 1)
            )
            scheduler_config = result.scalar_one_or_none()
            
            if not scheduler_config or not scheduler_config.enabled:
                return
            
            # Calculate random interval
            interval_minutes = random.randint(
                scheduler_config.min_interval,
                scheduler_config.max_interval
            )
            
            # Schedule job
            run_time = datetime.now() + timedelta(minutes=interval_minutes)
            
            self.job = self.scheduler.add_job(
                self.send_promotional_message,
                'date',
                run_date=run_time,
                id='promo_message'
            )
            
            logger.info(f"Next promotional message scheduled in {interval_minutes} minutes")
    
    async def send_promotional_message(self):
        """Send promotional message to chat"""
        try:
            async with db.get_session() as session:
                result = await session.execute(
                    select(Scheduler).where(Scheduler.id == 1)
                )
                scheduler_config = result.scalar_one_or_none()
                
                if not scheduler_config or not scheduler_config.enabled:
                    return
                
                # Parse chat ID from URL
                chat_id = Config.CHAT_FOR_ADS
                if chat_id.startswith('https://t.me/'):
                    chat_id = '@' + chat_id.replace('https://t.me/', '')
                
                # Send message
                try:
                    await self.bot.send_message(
                        chat_id=chat_id,
                        text=scheduler_config.message_text,
                        disable_web_page_preview=True
                    )
                    
                    # Update last run time
                    scheduler_config.last_run = datetime.utcnow()
                    await session.commit()
                    
                    logger.info(f"Promotional message sent to {chat_id}")
                    
                except Exception as e:
                    logger.error(f"Failed to send promotional message: {e}")
                
                # Schedule next message
                await self.schedule_next_message()
                
        except Exception as e:
            logger.error(f"Error in send_promotional_message: {e}")
            # Try to reschedule
            await asyncio.sleep(60)
            await self.schedule_next_message()