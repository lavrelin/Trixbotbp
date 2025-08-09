from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, JSON, Text, BigInteger, Enum
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime
import enum

Base = declarative_base()

class PostStatus(enum.Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EDITED = "edited"

class Gender(enum.Enum):
    MALE = "M"
    FEMALE = "F"
    OTHER = "other"
    UNKNOWN = "unknown"

class ActionType(enum.Enum):
    BAN = "ban"
    MUTE = "mute"

class ModerationAction(enum.Enum):
    APPROVE = "approve"
    REJECT = "reject"
    EDIT = "edit"

class User(Base):
    __tablename__ = 'users'
    
    id = Column(BigInteger, primary_key=True)  # Telegram user ID
    username = Column(String(255), nullable=True)
    first_name = Column(String(255), nullable=True)
    last_name = Column(String(255), nullable=True)
    gender = Column(Enum(Gender), default=Gender.UNKNOWN)
    birthdate = Column(DateTime, nullable=True)
    xp = Column(Integer, default=0)
    level = Column(Integer, default=1)
    banned = Column(Boolean, default=False)
    mute_until = Column(DateTime, nullable=True)
    referral_code = Column(String(50), unique=True, nullable=True)
    referred_by = Column(BigInteger, ForeignKey('users.id'), nullable=True)
    cooldown_expires_at = Column(DateTime, nullable=True)
    link_violations = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    posts = relationship("Post", back_populates="user")
    xp_events = relationship("XPEvent", back_populates="user")
    
class Post(Base):
    __tablename__ = 'posts'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, ForeignKey('users.id'))
    category = Column(String(100))
    subcategory = Column(String(100), nullable=True)
    text = Column(Text)
    media = Column(JSON, default=list)  # List of file_ids
    hashtags = Column(JSON, default=list)
    status = Column(Enum(PostStatus), default=PostStatus.PENDING)
    created_at = Column(DateTime, default=datetime.utcnow)
    moderated_by = Column(BigInteger, nullable=True)
    moderated_at = Column(DateTime, nullable=True)
    channel_message_id = Column(Integer, nullable=True)
    moderation_message_id = Column(Integer, nullable=True)
    anonymous = Column(Boolean, default=False)
    
    # For Piar posts
    is_piar = Column(Boolean, default=False)
    piar_name = Column(String(255), nullable=True)
    piar_profession = Column(String(255), nullable=True)
    piar_districts = Column(JSON, nullable=True)
    piar_phone = Column(String(50), nullable=True)
    piar_contacts = Column(JSON, nullable=True)
    piar_price = Column(String(100), nullable=True)
    
    # Relationships
    user = relationship("User", back_populates="posts")
    moderation_logs = relationship("ModerationLog", back_populates="post")
    
class ModerationLog(Base):
    __tablename__ = 'moderation_logs'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    post_id = Column(Integer, ForeignKey('posts.id'))
    moderator_id = Column(BigInteger)
    action = Column(Enum(ModerationAction))
    reason = Column(Text, nullable=True)
    new_text = Column(Text, nullable=True)
    timestamp = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    post = relationship("Post", back_populates="moderation_logs")
    
class Admin(Base):
    __tablename__ = 'admins'
    
    id = Column(BigInteger, primary_key=True)  # Telegram user ID
    role = Column(String(50), default='moderator')  # 'admin' or 'moderator'
    added_by = Column(BigInteger)
    added_at = Column(DateTime, default=datetime.utcnow)
    
class XPEvent(Base):
    __tablename__ = 'xp_events'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, ForeignKey('users.id'))
    event_type = Column(String(50))
    xp_amount = Column(Integer)
    timestamp = Column(DateTime, default=datetime.utcnow)
    extra = Column(JSON, nullable=True)
    
    # Relationships
    user = relationship("User", back_populates="xp_events")
    
class BanMute(Base):
    __tablename__ = 'bans_mutes'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger)
    type = Column(Enum(ActionType))
    until = Column(DateTime, nullable=True)
    reason = Column(Text, nullable=True)
    imposed_by = Column(BigInteger)
    created_at = Column(DateTime, default=datetime.utcnow)
    
class Scheduler(Base):
    __tablename__ = 'scheduler'
    
    id = Column(Integer, primary_key=True, default=1)
    enabled = Column(Boolean, default=False)
    min_interval = Column(Integer, default=120)
    max_interval = Column(Integer, default=160)
    message_text = Column(Text)
    last_run = Column(DateTime, nullable=True)
    
class Settings(Base):
    __tablename__ = 'settings'
    
    key = Column(String(100), primary_key=True)
    value = Column(Text)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)