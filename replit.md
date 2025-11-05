# Overview

This is a Python Discord bot built using the discord.py library. The bot provides a complete order/ticket management system for Discord servers, allowing staff to create customer tickets, track active orders, and post completion messages to a designated order status channel. The system is designed for BM Creations Market to manage customer service and order fulfillment within Discord.

**Last Updated:** November 5, 2025

# User Preferences

Preferred communication style: Simple, everyday language.

# System Architecture

## Bot Framework
- **Technology**: discord.py library with commands extension
- **Design Pattern**: Command-based bot architecture using the `commands.Bot` class
- **Rationale**: The commands extension provides a structured way to organize bot functionality into discrete commands, making the code more maintainable and easier to extend
- **Command Prefix**: Uses "!" as the command prefix for invoking bot commands

## 24/7 Uptime System
- **Technology**: Flask web server running on port 5000 in a separate thread
- **Purpose**: Provides a web endpoint that can be pinged by UptimeRobot or similar services to keep the bot alive 24/7
- **Implementation**: Uses Python threading to run Flask alongside Discord bot without blocking
- **Endpoint**: GET / returns "✅ BM Creations Bot is alive and running!"
- **Setup**: Add your Replit web URL to UptimeRobot with HTTP(s) monitoring at 5-minute intervals

## Intents Configuration
- **Approach**: Enables default intents plus message content intent
- **Rationale**: Message content intent is required to read command arguments and process user input. This is necessary for the `!newticket` command to parse customer names and order details
- **Trade-off**: Requires privileged intent approval in Discord Developer Portal for bots in 100+ servers

## Order/Ticket Management System
- **Storage**: In-memory dictionary (`active_tickets`) keyed by order ID
- **ID Generation**: Custom format `ORD-{7chars}-{6chars}` using random alphanumeric characters
- **Rationale**: In-memory storage is suitable for a starting template and prototyping. For production use, this would need to be replaced with persistent storage
- **Limitation**: All ticket data is lost when the bot restarts

## Timestamp Handling
- **Timezone**: US Eastern Time (America/New_York)
- **Library**: pytz for timezone-aware datetime operations
- **Format**: Human-readable format (e.g., "January 15, 2024 at 03:30 PM EST")
- **Rationale**: Provides consistent timezone handling for geographically distributed teams/customers

## Available Commands

### !newticket <customer_name> <order_details>
- **Purpose**: Creates a new customer order ticket
- **Behavior**: 
  - Deletes the command message instantly
  - Generates a unique random Order ID (format: ORD-XXXXXXX-XXXXXX)
  - Stores ticket information in active_tickets dictionary
  - Displays a ticket confirmation embed with all details
  - Captures: customer name, order details, ticket channel, creation timestamp
- **Permissions**: Staff role required
- **Example**: `!newticket JohnDoe 2x Custom Avatar + Profile Background`

### !completeorder <order_id>
- **Purpose**: Marks a ticket as complete and posts to order status channel
- **Behavior**:
  - Deletes the command message instantly
  - Retrieves ticket information from active_tickets
  - Posts a completion embed to ORDER_CHANNEL_ID (order status channel)
  - Posts the same completion embed to the original ticket channel (so buyer sees it)
  - Removes ticket from active_tickets
  - Shows confirmation message if not in ticket channel (deleted after 5 seconds)
- **Permissions**: Staff role required
- **Example**: `!completeorder ORD-A8K3D9F-7H2Q1X`

### !viewtickets
- **Purpose**: View all currently active tickets
- **Behavior**:
  - Deletes the command message
  - Shows an embed listing all active tickets with their details
  - Displays: Order ID, customer name, order details (truncated if long), creation time, ticket channel
- **Permissions**: Staff role required
- **Example**: `!viewtickets`

## Permissions System
- **Staff Role**: Commands are restricted to users with a role named "Staff" (configurable via STAFF_ROLE_NAME constant)
- **Protected Commands**: !newticket, !completeorder, !viewtickets
- **Fallback**: If the Staff role doesn't exist in the server, all users can access commands (for testing purposes)

## Workflow
1. Customer makes a purchase → Staff member uses `!newticket` in the ticket/support channel
2. Bot creates ticket record and shows confirmation embed
3. Staff can use `!viewtickets` to see all active orders
4. When order is ready → Staff uses `!completeorder` with the Order ID
5. Bot posts completion message to the order status channel and removes ticket from active list

# External Dependencies

## Required Python Libraries
- **discord.py**: Core Discord API wrapper for Python
- **pytz**: Timezone database and conversion utilities
- **flask**: Web framework for the 24/7 uptime server

## Discord Platform Requirements
- **Bot Token**: Must be configured as `TOKEN` environment variable/secret
- **Bot Permissions**: Requires permissions to read messages, send messages, and delete messages
- **Privileged Intents**: Message Content intent must be enabled in Discord Developer Portal

## Configuration Requirements
- **ORDER_CHANNEL_ID**: Channel ID (1435161427878084618) for the `#『☎️』order-status` channel where completed orders are posted
- **Bot Permissions Required**: Manage Messages (to delete command messages), Send Messages, Embed Links

## Known Limitations
- **In-Memory Storage**: Active tickets are stored in RAM only. If the bot restarts, all active ticket data is lost. For production use, this should be replaced with persistent storage (database or JSON file)
- **No Message Deletion Fallback**: If the bot lacks permission to delete messages, commands will fail. Should add try/except handling for permission errors
- **No Automated Ticket Channels**: System tracks tickets but doesn't create dedicated Discord channels for each ticket (can be added if needed)