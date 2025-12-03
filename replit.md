# BM Creations Discord Bot

## Overview

This is a comprehensive Python Discord bot built using discord.py with a modular cog architecture. The bot provides a complete business management system including order tracking, ticket support, shopping cart, wishlist, FAQ, moderation, analytics, and more. All data is persisted in a PostgreSQL database.

**Last Updated:** December 2, 2025

## User Preferences

Preferred communication style: Simple, everyday language.

## Project Structure

```
.
├── main.py                 # Main entry point
├── src/
│   ├── config.py           # Bot configuration
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

### 1. Persistent User Memory
- All user data stored in PostgreSQL
- Tracks purchase history, preferences, interactions
- Survives bot restarts

### 2. Ticket/Order System
- `!newticket <subject>` - Create support ticket
- `!closeticket` - Close current ticket
- `!order <details>` - Create new order
- `!trackorder <id>` - Track order status
- `!completeorder <id>` - Mark order complete (Staff)

### 3. Shopping Cart & Wishlist
- `!cart` - View cart
- `!addtocart <product>` - Add to cart
- `!wishlist` - View wishlist
- `!checkout` - Place order

### 4. Smart Answer System (FAQ)
- `!faq` - View FAQ list
- `!ask <question>` - Ask a question
- Auto-responds to questions in channels

### 5. Welcome/Onboarding
- Automatic welcome messages
- `!setwelcome #channel` - Set welcome channel
- `!setwelcomemsg <message>` - Set welcome message

### 6. Moderation
- `!warn <user> <reason>` - Issue warning
- `!warnings <user>` - View warnings
- `!mute/unmute` - Mute users
- `!kick/ban` - Remove users

### 7. Announcements
- `!announce <message>` - Send announcement
- `!broadcast <message>` - Send to all channels
- `!scheduleannounce <delay> #channel <message>` - Schedule

### 8. Feedback & Reviews
- `!feedback <message>` - Submit feedback
- `!review <1-5> <comment>` - Leave review
- `!suggest <idea>` - Submit suggestion

### 9. Reminders
- `!remind <time> <message>` - Set reminder (e.g., 1h, 30m, 1d)
- `!myreminders` - View pending reminders
- `!daily <HH:MM> <message>` - Daily reminder

### 10. Multilingual Support
Supports: English, Spanish, French, German, Portuguese, Arabic, Chinese, Japanese, Korean, Russian
- `!setlanguage <lang>` - Change language

### 11. Analytics Dashboard
- `!stats` - Server statistics
- `!dashboard` - Full overview
- `!topbuyers` - Top customers
- `!orderstats` - Order analytics

### 12. Private Recommendations
- `!recommend` - Get personalized recommendations (ticket channels only)
- `!similar <product>` - Find similar products
- `!bestsellers` - Top selling items

### 13. External API Integration
- `!weather <city>` - Get current weather
- `!crypto <symbol>` - Get cryptocurrency prices
- `!quote` - Random inspirational quote
- `!joke` - Random joke
- `!catfact` - Random cat fact
- `!github <username>` - GitHub user info
- `!define <word>` - Dictionary definition
- `!translate <lang> <text>` - Translate text
- `!apistatus` - Check API status (Admin)

### 14. Server Sync
- `!fetchserver` - Sync server data & auto-configure
- `!syncproducts #channel` - Sync products from channel
- `!syncallchannels` - Sync from all channels

### 15. Smart Support Interaction (Auto-Response)
**Automatic Features:**
- Bot auto-replies to user questions in support desk channel (no commands needed)
- Bot stops responding when Founder/Admin messages in ticket (staff handling)
- Interactive ticket welcome with "Buy Product" and "Any Queries" buttons

**Product Purchase Flow:**
1. User clicks "Buy Product" → Select category (Triggers/Rooms/Poses/Other)
2. User types product name → Bot shows product details, image, price
3. User sees PayPal link → Clicks "I've Made Payment"
4. User uploads screenshot + IMVU username → Staff processes order

**Admin Commands:**
- `!setsupportchannel #channel` - Set auto-response channel
- `!setpaypal <link>` - Set PayPal payment link
- `!setfounderrole @role` - Add Founder role (bot stops responding when they message)
- `!setadminrole @role` - Add Admin role
- `!resumebot` - Resume bot responses in ticket (after staff is done)
- `!supportstatus` - View support system configuration

## Database Schema

### Core Tables
- **users** - User profiles, preferences, language
- **products** - Product catalog
- **tickets** - Support tickets
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
- **guild_settings** - Server configuration

## Setup Commands

After adding the bot to your server:
1. `!fetchserver` - Auto-configure channels and roles
2. `!syncproducts #products-channel` - Import products
3. `!setwelcome #welcome` - Set welcome channel
4. `!setorders #order-status` - Set order channel
5. `!addfaq Question | Answer` - Add FAQ entries

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
