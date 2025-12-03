from sqlalchemy import (
    Column, Integer, BigInteger, String, Text, Boolean, DateTime, Float, 
    ForeignKey, JSON, Enum as SQLEnum, create_engine, Index
)
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, relationship, declarative_base
from datetime import datetime
import enum
import os

Base = declarative_base()

class TicketStatus(enum.Enum):
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    PENDING = "pending"
    RESOLVED = "resolved"
    CLOSED = "closed"

class OrderStatus(enum.Enum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    PROCESSING = "processing"
    SHIPPED = "shipped"
    DELIVERED = "delivered"
    CANCELLED = "cancelled"
    REFUNDED = "refunded"

class WarningLevel(enum.Enum):
    VERBAL = "verbal"
    WRITTEN = "written"
    FINAL = "final"
    BAN = "ban"

class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    discord_id = Column(BigInteger, unique=True, nullable=False, index=True)
    guild_id = Column(BigInteger, nullable=False, index=True)
    username = Column(String(100))
    display_name = Column(String(100))
    language = Column(String(10), default="en")
    preferences = Column(JSON, default=dict)
    joined_at = Column(DateTime, default=datetime.utcnow)
    last_active = Column(DateTime, default=datetime.utcnow)
    total_orders = Column(Integer, default=0)
    total_spent = Column(Float, default=0.0)
    is_vip = Column(Boolean, default=False)
    notes = Column(Text)
    
    tickets = relationship("Ticket", back_populates="user")
    orders = relationship("Order", back_populates="user")
    cart_items = relationship("CartItem", back_populates="user")
    wishlist_items = relationship("WishlistItem", back_populates="user")
    warnings = relationship("Warning", back_populates="user")
    feedback = relationship("Feedback", back_populates="user")
    interactions = relationship("UserInteraction", back_populates="user")

class Product(Base):
    __tablename__ = "products"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    guild_id = Column(BigInteger, nullable=False, index=True)
    channel_id = Column(BigInteger, index=True)
    message_id = Column(BigInteger)
    name = Column(String(255), nullable=False)
    description = Column(Text)
    price = Column(Float, default=0.0)
    category = Column(String(100))
    image_url = Column(Text)
    is_available = Column(Boolean, default=True)
    stock = Column(Integer, default=-1)
    tags = Column(JSON, default=list)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    order_items = relationship("OrderItem", back_populates="product")
    cart_items = relationship("CartItem", back_populates="product")
    wishlist_items = relationship("WishlistItem", back_populates="product")

class Ticket(Base):
    __tablename__ = "tickets"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    ticket_id = Column(String(50), unique=True, nullable=False, index=True)
    guild_id = Column(BigInteger, nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    channel_id = Column(BigInteger, nullable=False)
    category = Column(String(100))
    subject = Column(String(255))
    status = Column(SQLEnum(TicketStatus), default=TicketStatus.OPEN)
    priority = Column(Integer, default=1)
    assigned_staff_id = Column(BigInteger)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    closed_at = Column(DateTime)
    extra_data = Column(JSON, default=dict)
    
    user = relationship("User", back_populates="tickets")
    orders = relationship("Order", back_populates="ticket")
    messages = relationship("TicketMessage", back_populates="ticket")
    recommendations = relationship("Recommendation", back_populates="ticket")

class TicketMessage(Base):
    __tablename__ = "ticket_messages"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    ticket_id = Column(Integer, ForeignKey("tickets.id"), nullable=False)
    discord_message_id = Column(BigInteger)
    author_id = Column(BigInteger, nullable=False)
    content = Column(Text)
    is_staff = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    ticket = relationship("Ticket", back_populates="messages")

class Order(Base):
    __tablename__ = "orders"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    order_id = Column(String(50), unique=True, nullable=False, index=True)
    guild_id = Column(BigInteger, nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    ticket_id = Column(Integer, ForeignKey("tickets.id"))
    status = Column(SQLEnum(OrderStatus), default=OrderStatus.PENDING)
    total_amount = Column(Float, default=0.0)
    notes = Column(Text)
    tracking_number = Column(String(100))
    shipping_info = Column(JSON, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    completed_at = Column(DateTime)
    
    user = relationship("User", back_populates="orders")
    ticket = relationship("Ticket", back_populates="orders")
    items = relationship("OrderItem", back_populates="order")
    events = relationship("OrderEvent", back_populates="order")

class OrderItem(Base):
    __tablename__ = "order_items"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=False)
    product_id = Column(Integer, ForeignKey("products.id"))
    product_name = Column(String(255), nullable=False)
    quantity = Column(Integer, default=1)
    unit_price = Column(Float, default=0.0)
    total_price = Column(Float, default=0.0)
    notes = Column(Text)
    
    order = relationship("Order", back_populates="items")
    product = relationship("Product", back_populates="order_items")

class OrderEvent(Base):
    __tablename__ = "order_events"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=False)
    event_type = Column(String(50), nullable=False)
    description = Column(Text)
    created_by = Column(BigInteger)
    created_at = Column(DateTime, default=datetime.utcnow)
    extra_data = Column(JSON, default=dict)
    
    order = relationship("Order", back_populates="events")

class CartItem(Base):
    __tablename__ = "cart_items"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    quantity = Column(Integer, default=1)
    added_at = Column(DateTime, default=datetime.utcnow)
    notes = Column(Text)
    
    user = relationship("User", back_populates="cart_items")
    product = relationship("Product", back_populates="cart_items")

class WishlistItem(Base):
    __tablename__ = "wishlist_items"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    added_at = Column(DateTime, default=datetime.utcnow)
    priority = Column(Integer, default=1)
    notes = Column(Text)
    
    user = relationship("User", back_populates="wishlist_items")
    product = relationship("Product", back_populates="wishlist_items")

class Recommendation(Base):
    __tablename__ = "recommendations"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    ticket_id = Column(Integer, ForeignKey("tickets.id"), nullable=False)
    user_discord_id = Column(BigInteger, nullable=False)
    product_ids = Column(JSON, default=list)
    message = Column(Text)
    reason = Column(Text)
    is_accepted = Column(Boolean)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    ticket = relationship("Ticket", back_populates="recommendations")

class FAQ(Base):
    __tablename__ = "faqs"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    guild_id = Column(BigInteger, nullable=False, index=True)
    question = Column(Text, nullable=False)
    answer = Column(Text, nullable=False)
    keywords = Column(JSON, default=list)
    category = Column(String(100))
    language = Column(String(10), default="en")
    is_active = Column(Boolean, default=True)
    usage_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class Announcement(Base):
    __tablename__ = "announcements"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    guild_id = Column(BigInteger, nullable=False, index=True)
    title = Column(String(255), nullable=False)
    content = Column(Text, nullable=False)
    channel_ids = Column(JSON, default=list)
    scheduled_at = Column(DateTime)
    sent_at = Column(DateTime)
    is_sent = Column(Boolean, default=False)
    created_by = Column(BigInteger, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

class Warning(Base):
    __tablename__ = "warnings"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    guild_id = Column(BigInteger, nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    moderator_id = Column(BigInteger, nullable=False)
    level = Column(SQLEnum(WarningLevel), default=WarningLevel.VERBAL)
    reason = Column(Text, nullable=False)
    is_active = Column(Boolean, default=True)
    expires_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    user = relationship("User", back_populates="warnings")

class Feedback(Base):
    __tablename__ = "feedback"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    guild_id = Column(BigInteger, nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    order_id = Column(Integer, ForeignKey("orders.id"))
    rating = Column(Integer)
    comment = Column(Text)
    category = Column(String(100))
    is_public = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    user = relationship("User", back_populates="feedback")

class Reminder(Base):
    __tablename__ = "reminders"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    guild_id = Column(BigInteger, nullable=False, index=True)
    user_discord_id = Column(BigInteger, nullable=False)
    channel_id = Column(BigInteger, nullable=False)
    message = Column(Text, nullable=False)
    scheduled_at = Column(DateTime, nullable=False)
    is_sent = Column(Boolean, default=False)
    is_recurring = Column(Boolean, default=False)
    recurrence_pattern = Column(String(50))
    created_at = Column(DateTime, default=datetime.utcnow)

class UserInteraction(Base):
    __tablename__ = "user_interactions"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    guild_id = Column(BigInteger, nullable=False, index=True)
    interaction_type = Column(String(50), nullable=False)
    channel_id = Column(BigInteger)
    content = Column(Text)
    extra_data = Column(JSON, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    user = relationship("User", back_populates="interactions")

class Analytics(Base):
    __tablename__ = "analytics"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    guild_id = Column(BigInteger, nullable=False, index=True)
    date = Column(DateTime, nullable=False)
    total_users = Column(Integer, default=0)
    new_users = Column(Integer, default=0)
    active_users = Column(Integer, default=0)
    total_orders = Column(Integer, default=0)
    total_revenue = Column(Float, default=0.0)
    tickets_opened = Column(Integer, default=0)
    tickets_closed = Column(Integer, default=0)
    commands_used = Column(Integer, default=0)
    messages_sent = Column(Integer, default=0)
    extra_data = Column(JSON, default=dict)

class GuildSettings(Base):
    __tablename__ = "guild_settings"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    guild_id = Column(BigInteger, unique=True, nullable=False, index=True)
    welcome_channel_id = Column(BigInteger)
    welcome_message = Column(Text)
    order_channel_id = Column(BigInteger)
    ticket_category_id = Column(BigInteger)
    log_channel_id = Column(BigInteger)
    support_channel_id = Column(BigInteger)
    paypal_link = Column(Text)
    founder_role_ids = Column(JSON, default=list)
    admin_role_ids = Column(JSON, default=list)
    staff_role_ids = Column(JSON, default=list)
    mod_role_ids = Column(JSON, default=list)
    auto_responses = Column(JSON, default=dict)
    settings = Column(JSON, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

async def get_async_engine():
    database_url = os.getenv("DATABASE_URL")
    if database_url and database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql+asyncpg://", 1)
    elif database_url and database_url.startswith("postgresql://"):
        database_url = database_url.replace("postgresql://", "postgresql+asyncpg://", 1)
    if database_url and "?" in database_url:
        base_url, params = database_url.split("?", 1)
        param_list = params.split("&")
        filtered_params = [p for p in param_list if not p.startswith("sslmode=")]
        if filtered_params:
            database_url = base_url + "?" + "&".join(filtered_params)
        else:
            database_url = base_url
    return create_async_engine(database_url, echo=False)

async def get_async_session():
    engine = await get_async_engine()
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    return async_session

async def init_db():
    engine = await get_async_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    return engine
