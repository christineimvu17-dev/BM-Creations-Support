from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete, func, and_, or_
from sqlalchemy.orm import selectinload
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
import random
import string

from src.models.database import (
    User, Product, Ticket, TicketMessage, Order, OrderItem, OrderEvent,
    CartItem, WishlistItem, Recommendation, FAQ, Announcement, Warning,
    Feedback, Reminder, UserInteraction, Analytics, GuildSettings,
    TicketStatus, OrderStatus, WarningLevel, get_async_session, init_db
)

class DatabaseService:
    def __init__(self):
        self.session_factory = None
        self._initialized = False
    
    async def initialize(self):
        if self._initialized:
            return
        await init_db()
        self.session_factory = await get_async_session()
        self._initialized = True
    
    async def ensure_initialized(self):
        if not self._initialized or self.session_factory is None:
            await self.initialize()
    
    async def get_session(self) -> AsyncSession:
        return self.session_factory()
    
    def generate_id(self, prefix: str = "ORD") -> str:
        random_id = ''.join(random.choices(string.ascii_uppercase + string.digits, k=7))
        random_suffix = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
        return f"{prefix}-{random_id}-{random_suffix}"
    
    async def get_or_create_user(self, discord_id: int, guild_id: int, username: str = None, display_name: str = None) -> User:
        await self.ensure_initialized()
        async with self.session_factory() as session:
            result = await session.execute(
                select(User).where(and_(User.discord_id == discord_id, User.guild_id == guild_id))
            )
            user = result.scalar_one_or_none()
            
            if not user:
                user = User(
                    discord_id=discord_id,
                    guild_id=guild_id,
                    username=username,
                    display_name=display_name
                )
                session.add(user)
                await session.commit()
                await session.refresh(user)
            else:
                user.last_active = datetime.utcnow()
                if username:
                    user.username = username
                if display_name:
                    user.display_name = display_name
                await session.commit()
            
            return user
    
    async def update_user_preferences(self, discord_id: int, guild_id: int, preferences: Dict) -> User:
        async with self.session_factory() as session:
            result = await session.execute(
                select(User).where(and_(User.discord_id == discord_id, User.guild_id == guild_id))
            )
            user = result.scalar_one_or_none()
            if user:
                current_prefs = user.preferences or {}
                current_prefs.update(preferences)
                user.preferences = current_prefs
                await session.commit()
            return user
    
    async def set_user_language(self, discord_id: int, guild_id: int, language: str) -> User:
        async with self.session_factory() as session:
            result = await session.execute(
                select(User).where(and_(User.discord_id == discord_id, User.guild_id == guild_id))
            )
            user = result.scalar_one_or_none()
            if user:
                user.language = language
                await session.commit()
            return user
    
    async def get_user_history(self, discord_id: int, guild_id: int) -> Dict:
        async with self.session_factory() as session:
            result = await session.execute(
                select(User)
                .options(selectinload(User.orders), selectinload(User.tickets), 
                        selectinload(User.interactions), selectinload(User.feedback))
                .where(and_(User.discord_id == discord_id, User.guild_id == guild_id))
            )
            user = result.scalar_one_or_none()
            if not user:
                return {}
            
            return {
                "user": user,
                "orders": user.orders,
                "tickets": user.tickets,
                "interactions": user.interactions[-50:] if user.interactions else [],
                "feedback": user.feedback
            }
    
    async def create_product(self, guild_id: int, name: str, description: str = None, 
                            price: float = 0.0, category: str = None, **kwargs) -> Product:
        async with self.session_factory() as session:
            product = Product(
                guild_id=guild_id,
                name=name,
                description=description,
                price=price,
                category=category,
                **kwargs
            )
            session.add(product)
            await session.commit()
            await session.refresh(product)
            return product
    
    async def get_products(self, guild_id: int, category: str = None, 
                          available_only: bool = True) -> List[Product]:
        async with self.session_factory() as session:
            query = select(Product).where(Product.guild_id == guild_id)
            if category:
                query = query.where(Product.category == category)
            if available_only:
                query = query.where(Product.is_available == True)
            
            result = await session.execute(query)
            return result.scalars().all()
    
    async def search_products(self, guild_id: int, search_term: str) -> List[Product]:
        async with self.session_factory() as session:
            query = select(Product).where(
                and_(
                    Product.guild_id == guild_id,
                    Product.is_available == True,
                    or_(
                        Product.name.ilike(f"%{search_term}%"),
                        Product.description.ilike(f"%{search_term}%"),
                        Product.category.ilike(f"%{search_term}%")
                    )
                )
            )
            result = await session.execute(query)
            return result.scalars().all()
    
    async def create_ticket(self, guild_id: int, user_id: int, channel_id: int, 
                           subject: str = None, category: str = None) -> Ticket:
        async with self.session_factory() as session:
            ticket = Ticket(
                ticket_id=self.generate_id("TKT"),
                guild_id=guild_id,
                user_id=user_id,
                channel_id=channel_id,
                subject=subject,
                category=category
            )
            session.add(ticket)
            await session.commit()
            await session.refresh(ticket)
            return ticket
    
    async def get_ticket(self, ticket_id: str = None, channel_id: int = None) -> Optional[Ticket]:
        async with self.session_factory() as session:
            if ticket_id:
                query = select(Ticket).where(Ticket.ticket_id == ticket_id)
            elif channel_id:
                query = select(Ticket).where(Ticket.channel_id == channel_id)
            else:
                return None
            
            result = await session.execute(query.options(selectinload(Ticket.user)))
            return result.scalar_one_or_none()
    
    async def get_active_tickets(self, guild_id: int) -> List[Ticket]:
        async with self.session_factory() as session:
            result = await session.execute(
                select(Ticket)
                .options(selectinload(Ticket.user))
                .where(and_(
                    Ticket.guild_id == guild_id,
                    Ticket.status.in_([TicketStatus.OPEN, TicketStatus.IN_PROGRESS, TicketStatus.PENDING])
                ))
                .order_by(Ticket.created_at.desc())
            )
            return result.scalars().all()
    
    async def update_ticket_status(self, ticket_id: str, status: TicketStatus, 
                                   assigned_staff_id: int = None) -> Ticket:
        async with self.session_factory() as session:
            result = await session.execute(
                select(Ticket).where(Ticket.ticket_id == ticket_id)
            )
            ticket = result.scalar_one_or_none()
            if ticket:
                ticket.status = status
                if assigned_staff_id:
                    ticket.assigned_staff_id = assigned_staff_id
                if status in [TicketStatus.RESOLVED, TicketStatus.CLOSED]:
                    ticket.closed_at = datetime.utcnow()
                await session.commit()
            return ticket
    
    async def update_ticket_extra_data(self, ticket_id: str, extra_data: Dict) -> Ticket:
        async with self.session_factory() as session:
            result = await session.execute(
                select(Ticket).where(Ticket.ticket_id == ticket_id)
            )
            ticket = result.scalar_one_or_none()
            if ticket:
                ticket.extra_data = extra_data
                await session.commit()
            return ticket
    
    async def get_all_products(self, guild_id: int) -> List[Product]:
        async with self.session_factory() as session:
            result = await session.execute(
                select(Product).where(
                    and_(Product.guild_id == guild_id, Product.is_available == True)
                )
            )
            return result.scalars().all()
    
    async def add_ticket_message(self, ticket_id: int, author_id: int, content: str, 
                                 message_id: int = None, is_staff: bool = False) -> TicketMessage:
        async with self.session_factory() as session:
            message = TicketMessage(
                ticket_id=ticket_id,
                discord_message_id=message_id,
                author_id=author_id,
                content=content,
                is_staff=is_staff
            )
            session.add(message)
            await session.commit()
            return message
    
    async def create_order(self, guild_id: int, user_id: int, ticket_id: int = None, 
                          items: List[Dict] = None, notes: str = None) -> Order:
        async with self.session_factory() as session:
            order = Order(
                order_id=self.generate_id("ORD"),
                guild_id=guild_id,
                user_id=user_id,
                ticket_id=ticket_id,
                notes=notes
            )
            session.add(order)
            await session.flush()
            
            total = 0.0
            if items:
                for item in items:
                    order_item = OrderItem(
                        order_id=order.id,
                        product_id=item.get("product_id"),
                        product_name=item.get("name", "Unknown"),
                        quantity=item.get("quantity", 1),
                        unit_price=item.get("price", 0.0),
                        total_price=item.get("price", 0.0) * item.get("quantity", 1),
                        notes=item.get("notes")
                    )
                    total += order_item.total_price
                    session.add(order_item)
            
            order.total_amount = total
            
            event = OrderEvent(
                order_id=order.id,
                event_type="created",
                description="Order created"
            )
            session.add(event)
            
            await session.commit()
            await session.refresh(order)
            return order
    
    async def get_order(self, order_id: str) -> Optional[Order]:
        async with self.session_factory() as session:
            result = await session.execute(
                select(Order)
                .options(selectinload(Order.items), selectinload(Order.events), selectinload(Order.user))
                .where(Order.order_id == order_id)
            )
            return result.scalar_one_or_none()
    
    async def get_user_orders(self, discord_id: int, guild_id: int) -> List[Order]:
        async with self.session_factory() as session:
            user_result = await session.execute(
                select(User).where(and_(User.discord_id == discord_id, User.guild_id == guild_id))
            )
            user = user_result.scalar_one_or_none()
            if not user:
                return []
            
            result = await session.execute(
                select(Order)
                .options(selectinload(Order.items), selectinload(Order.events))
                .where(Order.user_id == user.id)
                .order_by(Order.created_at.desc())
            )
            return result.scalars().all()
    
    async def update_order_status(self, order_id: str, status: OrderStatus, 
                                  tracking_number: str = None, staff_id: int = None) -> Order:
        async with self.session_factory() as session:
            result = await session.execute(
                select(Order).where(Order.order_id == order_id)
            )
            order = result.scalar_one_or_none()
            if order:
                old_status = order.status
                order.status = status
                if tracking_number:
                    order.tracking_number = tracking_number
                if status == OrderStatus.DELIVERED:
                    order.completed_at = datetime.utcnow()
                
                event = OrderEvent(
                    order_id=order.id,
                    event_type="status_change",
                    description=f"Status changed from {old_status.value} to {status.value}",
                    created_by=staff_id,
                    metadata={"old_status": old_status.value, "new_status": status.value}
                )
                session.add(event)
                await session.commit()
            return order
    
    async def add_to_cart(self, discord_id: int, guild_id: int, product_id: int, 
                         quantity: int = 1) -> CartItem:
        async with self.session_factory() as session:
            user = await self.get_or_create_user(discord_id, guild_id)
            
            result = await session.execute(
                select(CartItem).where(and_(
                    CartItem.user_id == user.id,
                    CartItem.product_id == product_id
                ))
            )
            cart_item = result.scalar_one_or_none()
            
            if cart_item:
                cart_item.quantity += quantity
            else:
                cart_item = CartItem(
                    user_id=user.id,
                    product_id=product_id,
                    quantity=quantity
                )
                session.add(cart_item)
            
            await session.commit()
            await session.refresh(cart_item)
            return cart_item
    
    async def get_cart(self, discord_id: int, guild_id: int) -> List[CartItem]:
        async with self.session_factory() as session:
            user_result = await session.execute(
                select(User).where(and_(User.discord_id == discord_id, User.guild_id == guild_id))
            )
            user = user_result.scalar_one_or_none()
            if not user:
                return []
            
            result = await session.execute(
                select(CartItem)
                .options(selectinload(CartItem.product))
                .where(CartItem.user_id == user.id)
            )
            return result.scalars().all()
    
    async def clear_cart(self, discord_id: int, guild_id: int):
        async with self.session_factory() as session:
            user_result = await session.execute(
                select(User).where(and_(User.discord_id == discord_id, User.guild_id == guild_id))
            )
            user = user_result.scalar_one_or_none()
            if user:
                await session.execute(
                    delete(CartItem).where(CartItem.user_id == user.id)
                )
                await session.commit()
    
    async def add_to_wishlist(self, discord_id: int, guild_id: int, product_id: int) -> WishlistItem:
        async with self.session_factory() as session:
            user = await self.get_or_create_user(discord_id, guild_id)
            
            result = await session.execute(
                select(WishlistItem).where(and_(
                    WishlistItem.user_id == user.id,
                    WishlistItem.product_id == product_id
                ))
            )
            wishlist_item = result.scalar_one_or_none()
            
            if not wishlist_item:
                wishlist_item = WishlistItem(
                    user_id=user.id,
                    product_id=product_id
                )
                session.add(wishlist_item)
                await session.commit()
                await session.refresh(wishlist_item)
            
            return wishlist_item
    
    async def get_wishlist(self, discord_id: int, guild_id: int) -> List[WishlistItem]:
        async with self.session_factory() as session:
            user_result = await session.execute(
                select(User).where(and_(User.discord_id == discord_id, User.guild_id == guild_id))
            )
            user = user_result.scalar_one_or_none()
            if not user:
                return []
            
            result = await session.execute(
                select(WishlistItem)
                .options(selectinload(WishlistItem.product))
                .where(WishlistItem.user_id == user.id)
            )
            return result.scalars().all()
    
    async def create_recommendation(self, ticket_id: int, user_discord_id: int, 
                                   product_ids: List[int], message: str, reason: str = None) -> Recommendation:
        async with self.session_factory() as session:
            recommendation = Recommendation(
                ticket_id=ticket_id,
                user_discord_id=user_discord_id,
                product_ids=product_ids,
                message=message,
                reason=reason
            )
            session.add(recommendation)
            await session.commit()
            await session.refresh(recommendation)
            return recommendation
    
    async def get_or_create_faq(self, guild_id: int, question: str, answer: str, 
                                keywords: List[str] = None, category: str = None) -> FAQ:
        async with self.session_factory() as session:
            faq = FAQ(
                guild_id=guild_id,
                question=question,
                answer=answer,
                keywords=keywords or [],
                category=category
            )
            session.add(faq)
            await session.commit()
            await session.refresh(faq)
            return faq
    
    async def search_faq(self, guild_id: int, search_term: str, language: str = "en") -> List[FAQ]:
        async with self.session_factory() as session:
            result = await session.execute(
                select(FAQ).where(and_(
                    FAQ.guild_id == guild_id,
                    FAQ.is_active == True,
                    or_(
                        FAQ.question.ilike(f"%{search_term}%"),
                        FAQ.answer.ilike(f"%{search_term}%")
                    )
                ))
            )
            return result.scalars().all()
    
    async def get_all_faqs(self, guild_id: int) -> List[FAQ]:
        async with self.session_factory() as session:
            result = await session.execute(
                select(FAQ).where(and_(FAQ.guild_id == guild_id, FAQ.is_active == True))
            )
            return result.scalars().all()
    
    async def create_announcement(self, guild_id: int, title: str, content: str, 
                                  created_by: int, channel_ids: List[int] = None,
                                  scheduled_at: datetime = None) -> Announcement:
        async with self.session_factory() as session:
            announcement = Announcement(
                guild_id=guild_id,
                title=title,
                content=content,
                created_by=created_by,
                channel_ids=channel_ids or [],
                scheduled_at=scheduled_at
            )
            session.add(announcement)
            await session.commit()
            await session.refresh(announcement)
            return announcement
    
    async def get_pending_announcements(self) -> List[Announcement]:
        async with self.session_factory() as session:
            result = await session.execute(
                select(Announcement).where(and_(
                    Announcement.is_sent == False,
                    Announcement.scheduled_at <= datetime.utcnow()
                ))
            )
            return result.scalars().all()
    
    async def mark_announcement_sent(self, announcement_id: int):
        async with self.session_factory() as session:
            result = await session.execute(
                select(Announcement).where(Announcement.id == announcement_id)
            )
            announcement = result.scalar_one_or_none()
            if announcement:
                announcement.is_sent = True
                announcement.sent_at = datetime.utcnow()
                await session.commit()
    
    async def add_warning(self, guild_id: int, user_id: int, moderator_id: int,
                         reason: str, level: WarningLevel = WarningLevel.VERBAL,
                         expires_at: datetime = None) -> Warning:
        async with self.session_factory() as session:
            warning = Warning(
                guild_id=guild_id,
                user_id=user_id,
                moderator_id=moderator_id,
                level=level,
                reason=reason,
                expires_at=expires_at
            )
            session.add(warning)
            await session.commit()
            await session.refresh(warning)
            return warning
    
    async def get_user_warnings(self, discord_id: int, guild_id: int) -> List[Warning]:
        async with self.session_factory() as session:
            user_result = await session.execute(
                select(User).where(and_(User.discord_id == discord_id, User.guild_id == guild_id))
            )
            user = user_result.scalar_one_or_none()
            if not user:
                return []
            
            result = await session.execute(
                select(Warning).where(and_(
                    Warning.user_id == user.id,
                    Warning.is_active == True
                )).order_by(Warning.created_at.desc())
            )
            return result.scalars().all()
    
    async def add_feedback(self, guild_id: int, user_id: int, rating: int = None,
                          comment: str = None, order_id: int = None, 
                          category: str = None, is_public: bool = False) -> Feedback:
        async with self.session_factory() as session:
            feedback = Feedback(
                guild_id=guild_id,
                user_id=user_id,
                order_id=order_id,
                rating=rating,
                comment=comment,
                category=category,
                is_public=is_public
            )
            session.add(feedback)
            await session.commit()
            await session.refresh(feedback)
            return feedback
    
    async def create_reminder(self, guild_id: int, user_discord_id: int, channel_id: int,
                             message: str, scheduled_at: datetime, 
                             is_recurring: bool = False, pattern: str = None) -> Reminder:
        async with self.session_factory() as session:
            reminder = Reminder(
                guild_id=guild_id,
                user_discord_id=user_discord_id,
                channel_id=channel_id,
                message=message,
                scheduled_at=scheduled_at,
                is_recurring=is_recurring,
                recurrence_pattern=pattern
            )
            session.add(reminder)
            await session.commit()
            await session.refresh(reminder)
            return reminder
    
    async def get_pending_reminders(self) -> List[Reminder]:
        async with self.session_factory() as session:
            result = await session.execute(
                select(Reminder).where(and_(
                    Reminder.is_sent == False,
                    Reminder.scheduled_at <= datetime.utcnow()
                ))
            )
            return result.scalars().all()
    
    async def mark_reminder_sent(self, reminder_id: int):
        async with self.session_factory() as session:
            result = await session.execute(
                select(Reminder).where(Reminder.id == reminder_id)
            )
            reminder = result.scalar_one_or_none()
            if reminder:
                if reminder.is_recurring:
                    pass
                else:
                    reminder.is_sent = True
                await session.commit()
    
    async def log_interaction(self, user_id: int, guild_id: int, interaction_type: str,
                             channel_id: int = None, content: str = None, 
                             metadata: Dict = None) -> UserInteraction:
        async with self.session_factory() as session:
            interaction = UserInteraction(
                user_id=user_id,
                guild_id=guild_id,
                interaction_type=interaction_type,
                channel_id=channel_id,
                content=content,
                metadata=metadata or {}
            )
            session.add(interaction)
            await session.commit()
            return interaction
    
    async def get_guild_analytics(self, guild_id: int, days: int = 30) -> Dict:
        async with self.session_factory() as session:
            start_date = datetime.utcnow() - timedelta(days=days)
            
            users_count = await session.execute(
                select(func.count(User.id)).where(User.guild_id == guild_id)
            )
            
            orders_count = await session.execute(
                select(func.count(Order.id)).where(and_(
                    Order.guild_id == guild_id,
                    Order.created_at >= start_date
                ))
            )
            
            revenue = await session.execute(
                select(func.sum(Order.total_amount)).where(and_(
                    Order.guild_id == guild_id,
                    Order.created_at >= start_date,
                    Order.status == OrderStatus.DELIVERED
                ))
            )
            
            tickets_count = await session.execute(
                select(func.count(Ticket.id)).where(and_(
                    Ticket.guild_id == guild_id,
                    Ticket.created_at >= start_date
                ))
            )
            
            return {
                "total_users": users_count.scalar() or 0,
                "orders_count": orders_count.scalar() or 0,
                "total_revenue": revenue.scalar() or 0.0,
                "tickets_count": tickets_count.scalar() or 0
            }
    
    async def get_or_create_guild_settings(self, guild_id: int) -> GuildSettings:
        async with self.session_factory() as session:
            result = await session.execute(
                select(GuildSettings).where(GuildSettings.guild_id == guild_id)
            )
            settings = result.scalar_one_or_none()
            
            if not settings:
                settings = GuildSettings(guild_id=guild_id)
                session.add(settings)
                await session.commit()
                await session.refresh(settings)
            
            return settings
    
    async def update_guild_settings(self, guild_id: int, **kwargs) -> GuildSettings:
        async with self.session_factory() as session:
            result = await session.execute(
                select(GuildSettings).where(GuildSettings.guild_id == guild_id)
            )
            settings = result.scalar_one_or_none()
            
            if settings:
                for key, value in kwargs.items():
                    if hasattr(settings, key):
                        setattr(settings, key, value)
                await session.commit()
            
            return settings

db_service = DatabaseService()
