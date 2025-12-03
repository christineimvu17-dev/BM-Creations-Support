# BM Creations Discord Bot

## Overview

This is a comprehensive Python Discord bot built using discord.py with a modular cog architecture. The bot provides a complete business management system including order tracking, ticket support, shopping cart, wishlist, FAQ, moderation, analytics, and more. All data is persisted in a PostgreSQL database.

**Last Updated:** December 3, 2025

## User Preferences

Preferred communication style: Simple, everyday language.

## Recent Changes

- **December 3, 2025**: Added interactive product buttons for Permanent Triggers (7 products) and Gifting Triggers (2 products)
- **December 3, 2025**: Implemented order timeline with 4 stages: Order Confirmed → Payment Received → Processing → Complete
- **December 3, 2025**: Enhanced completion messages with dual messaging (ticket + order status channel)
- **December 3, 2025**: Added privacy features: blurred customer names, hidden order IDs and ticket channels
- **December 3, 2025**: Branding in all messages: Website link, Instagram link, "Trusted since 2020" footer
- **December 3, 2025**: Close Ticket button added to prevent orphaned tickets
- **December 3, 2025**: Ticket limit only counts OPEN tickets (not total lifetime)
- **December 3, 2025**: Dynamic channel naming: username-pending → username-complete

## Access Control

### Command Permissions
- **Owner (@sizuka42)**: Full access to all 37 commands
- **Server Administrators**: Full access to all commands
- **Public Commands (all users)**: `/newticket`, `/order`, `/trackorder`, `/setlanguage`
- **Other commands**: Owner and admin only

### Auto-Response Rules
1. **When Founder/Admin messages in a ticket**: Bot STOPS responding (staff is handling)
2. **To resume bot**: Use `/resumebot` command
3. **Ignored Categories**: "Chat Zone" and "More Fun" - bot never responds there

## Project Structure

```
.
├── main.py                 # Main entry point (includes owner-only command check)
├── src/
│   ├── config.py           # Bot configuration (owner username, keywords, ignored categories)
│   ├── bot.py              # Alternative entry point
│   ├── models/
│   │   └── database.py     # SQLAlchemy database models
│   ├── services/
│   │   └── database.py     # Database service layer
│   ├── cogs/
│   │   ├── core.py         # Core bot functionality
│   │   ├── tickets.py      # Ticket management
│   │   ├── orders.py       # Order tracking
│   │   ├── commerce.py     # Cart & wishlist
│   │   ├── faq.py          # FAQ system
│   │   ├── moderation.py   # Moderation tools
│   │   ├── announcements.py # Broadcast system
│   │   ├── feedback.py     # Review collection
│   │   ├── reminders.py    # Scheduled reminders
│   │   ├── analytics.py    # Stats dashboard
│   │   ├── recommendations.py # Personalized recommendations
│   │   ├── sync.py         # Server/product sync
│   │   ├── external_api.py # External API integration
│   │   └── support_interaction.py # Smart auto-response & purchase flow
│   └── utils/
│       ├── helpers.py      # Utility functions
│       └── translations.py # Multilingual support
```

## Features

### 1. Channel-Based Auto-Response System (NEW!)

| Channel Type | Bot Behavior |
|--------------|--------------|
| **Support Desk** | Replies to ALL messages automatically |
| **Products Channel** | Creates ticket + welcomes user with Buy/Queries buttons |
| **General Chat** | Only replies to purchase keywords (buy, price, cost, etc.) |
| **Chat Zone / More Fun** | Bot completely ignores these |
| **Threads** | Auto-creates ticket, welcomes user, answers questions |

### 2. Automatic Thread Support
- When anyone creates a thread in ANY channel (except ignored categories):
  - Creates a support ticket for that user
  - Sends welcome message: "Staff is coming to you shortly, until then I'm here to help!"
  - Shows Buy Product and Any Queries buttons
  - Answers questions automatically without commands
- Users don't need to use any commands - just create a thread and chat!

### 3. Ticket/Order System
- `/newticket <subject>` - Create support ticket
- `/closeticket` - Close current ticket
- `/viewtickets` - View all active tickets (Staff)
- `/order <details>` - Create new order
- `/trackorder <id>` - Track order status
- `/myorders` - View your orders
- `/completeorder <id>` - Mark order complete (Staff)

### 4. Shopping Cart & Wishlist
- `/cart` - View cart
- `/addtocart <product>` - Add to cart
- `/clearcart` - Clear your cart
- `/wishlist` - View wishlist
- `/addtowishlist` - Add item to wishlist

### 5. Smart Answer System
- Bot auto-responds to questions in threads and support desk
- Searches FAQs and products to answer questions
- Purchase keywords trigger helpful responses: buy, purchase, price, cost, order, how much, trigger, room, pose

### 6. Welcome/Onboarding
- Automatic welcome messages for new members
- `/setwelcome #channel` - Set welcome channel
- `/setwelcomemsg <message>` - Set welcome message

### 7. Moderation
- `/warn <user> <reason>` - Issue warning
- `/warnings <user>` - View warnings
- Kick/ban functionality available

### 8. Announcements
- `/announce <message>` - Send announcement
- Broadcast and scheduled announcement features

### 9. Feedback & Reviews
- `/feedback <message>` - Submit feedback
- Review collection system

### 10. Reminders
- `/remind <time> <message>` - Set reminder
- View pending reminders

### 11. Multilingual Support
Supports: English, Spanish, French, German, Portuguese, Arabic, Chinese, Japanese, Korean, Russian
- `/setlanguage <lang>` - Change language

### 12. Analytics Dashboard
- `/stats` - Server statistics
- Order analytics and top buyers

### 13. Support System Configuration (Admin)
- `/setsupportchannel #channel` - Set support desk channel (bot replies to ALL)
- `/setproductschannel #channel` - Set products channel (creates tickets)
- `/setgeneralchat #channel` - Set general chat (only purchase messages)
- `/setpaypal <link>` - Set PayPal payment link
- `/setfounderrole @role` - Add Founder role (bot stops responding when they message)
- `/setadminrole @role` - Add Admin role
- `/resumebot` - Resume bot responses in ticket (after staff is done)
- `/supportstatus` - View support system configuration

### 14. Data Sync Commands (Admin)
- `/syncall` - Sync all products from all channels (only @sizuka42's messages)
- `/syncchannel #channel` - Sync products from specific channel
- `/fetchserver` - Auto-configure server channels and roles
- `/listproducts` - View all synced products
- `/clearproducts` - Clear all products from database
- `/addproduct` - Manually add a product
- `/serverstats` - View detailed server and product statistics

### 15. Interactive Purchase Flow
1. User creates thread or clicks "Buy Product" button
2. User selects category (Triggers/Rooms/Poses/Other)
3. User types product name → Bot shows product details, image, price
4. User sees PayPal link → Clicks "I've Made Payment"
5. User uploads screenshot + IMVU username
6. **Bot automatically creates a professional order with:**
   - Unique BM-XXXX order ID (e.g., BM-4321)
   - Customer info, product, time, status
   - Payment screenshot attached
   - "Mark Completed" button (only owner can use!)
7. Order is sent to Order Status channel
8. Owner clicks "Mark Completed" → Order shows as COMPLETED
9. Customer gets DM notification

## Database Schema

### Core Tables
- **users** - User profiles, preferences, language
- **products** - Product catalog
- **tickets** - Support tickets (including thread tickets)
- **orders** - Customer orders
- **order_items** - Order line items
- **order_events** - Order status history

### Commerce Tables
- **cart_items** - Shopping cart
- **wishlist_items** - User wishlists
- **recommendations** - Personalized recommendations

### Support Tables
- **faqs** - FAQ entries
- **announcements** - Scheduled announcements
- **warnings** - User warnings
- **feedback** - Reviews and feedback
- **reminders** - Scheduled reminders
- **user_interactions** - Activity log
- **analytics** - Daily metrics
- **guild_settings** - Server configuration (includes products_channel_id, general_chat_id, ignored_category_ids)

## Configuration

Environment variables required:
- `TOKEN` - Discord bot token
- `DATABASE_URL` - PostgreSQL connection string (auto-configured)

## Dependencies

- discord.py - Discord API
- SQLAlchemy - Database ORM
- asyncpg - PostgreSQL driver
- Flask - Keep-alive server
- APScheduler - Task scheduling
- pytz - Timezone handling
- aiohttp - Async HTTP (for external API calls)
- python-dateutil - Date parsing

## 24/7 Uptime

Flask server runs on port 5000 for monitoring:
- Endpoint: GET / returns status message
- Configure UptimeRobot to ping every 5 minutes

## Privacy Features

- Personalized recommendations only in ticket channels
- User data scoped per server
- Secure token management

## Quick Setup

1. Run `/fetchserver` - Auto-detects your channels and roles
2. Run `/syncall` - Syncs products from your messages
3. Run `/setpaypal <link>` - Set your PayPal payment link
4. Run `/supportstatus` - Verify configuration

Bot is now ready to help customers automatically!
