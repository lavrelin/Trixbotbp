from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import sessionmaker
from contextlib import asynccontextmanager
from typing import Optional
import logging
from config import Config
from models import Base

logger = logging.getLogger(__name__)

class Database:
    def __init__(self):
        self.engine = None
        self.async_session = None
        
    async def init(self):
        """Initialize database connection"""
        try:
            # Convert postgresql:// to postgresql+asyncpg:// for async
            db_url = Config.DATABASE_URL
            if db_url.startswith("postgresql://"):
                db_url = db_url.replace("postgresql://", "postgresql+asyncpg://")
            elif db_url.startswith("postgres://"):
                db_url = db_url.replace("postgres://", "postgresql+asyncpg://")
                
            self.engine = create_async_engine(
                db_url,
                echo=False,
                pool_pre_ping=True,
                pool_size=20,
                max_overflow=0
            )
            
            self.async_session = async_sessionmaker(
                self.engine,
                class_=AsyncSession,
                expire_on_commit=False
            )
            
            # Create tables if they don't exist
            async with self.engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
                
            logger.info("Database initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize database: {e}")
            raise
            
    async def close(self):
        """Close database connection"""
        if self.engine:
            await self.engine.dispose()
            
    @asynccontextmanager
    async def get_session(self):
        """Get database session"""
        async with self.async_session() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise
            finally:
                await session.close()
                
    async def execute(self, query, *args, **kwargs):
        """Execute raw SQL query"""
        async with self.get_session() as session:
            result = await session.execute(query, *args, **kwargs)
            return result
            
# Global database instance
db = Database()
