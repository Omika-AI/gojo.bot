# CLAUDE.md - Gojo Discord Bot Development Rules

## Project Overview
This is a Discord bot project called **Gojo**. Follow these rules strictly to ensure everything works correctly.

---

## Core Rules

### 1. Language
- **Use Python for EVERYTHING** - No exceptions
- Python 3.10+ required
- Use `discord.py` library for Discord functionality

### 2. Command Structure
- **ONE command = ONE Python file**
- All command files go in the `commands/` directory
- Each command file must be self-contained and follow this naming convention: `command_name.py`
- Example structure:
  ```
  gojo.bot/
  ├── bot.py              # Main bot entry point
  ├── commands/
  │   ├── __init__.py
  │   ├── ping.py         # /ping command
  │   ├── help.py         # /help command
  │   └── chat.py         # /chat command (AI)
  ├── utils/              # Shared utilities
  ├── config.py           # Configuration
  └── requirements.txt
  ```

### 3. AI Features
- **Use OpenRouter API** for all AI/LLM features
- OpenRouter endpoint: `https://openrouter.ai/api/v1/chat/completions`
- Store API key in environment variable: `OPENROUTER_API_KEY`
- Never hardcode API keys

### 4. Version Control
- **Commit after EVERY update** - No exceptions
- Write clear, descriptive commit messages explaining what was done
- Format: `type: description`
  - `feat:` - New feature
  - `fix:` - Bug fix
  - `refactor:` - Code refactoring
  - `docs:` - Documentation changes
  - `chore:` - Maintenance tasks

### 5. Environment Variables
Store all secrets in a `.env` file (never commit this):
```
DISCORD_TOKEN=your_discord_bot_token
OPENROUTER_API_KEY=your_openrouter_api_key
```

### 6. Code Quality
- Add comments explaining what each section does
- Use type hints for function parameters
- Handle errors gracefully with try/except blocks
- Always test commands before committing

### 7. Dependencies
- Keep `requirements.txt` updated
- Core dependencies:
  - `discord.py`
  - `python-dotenv`
  - `aiohttp` (for OpenRouter API calls)

---

## Important Reminders
- The person working on this may not know how to code - **everything must work out of the box**
- Test thoroughly before committing
- Keep code simple and well-documented
- If something breaks, fix it before moving on

---

## CRITICAL: User Cannot Program

**The owner of this project CANNOT program.** This means:

1. **Always provide step-by-step instructions** for anything they need to do manually
2. **Explain what you're doing** in simple terms
3. **Never assume they know** terminal commands, programming concepts, or technical jargon
4. **If something requires manual action**, give them the exact commands to copy/paste
5. **After making code changes**, tell them exactly how to test it

---

## Bot Management (manage.sh)

The bot uses `manage.sh` for all operations. **ALWAYS use this script** instead of running Python directly.

### Commands:
```bash
./manage.sh start    # Start the bot in the background
./manage.sh stop     # Stop the running bot
./manage.sh restart  # Restart the bot (stop + start)
./manage.sh status   # Check if the bot is running
./manage.sh logs     # View the bot logs (live)
./manage.sh logs 50  # View last 50 lines of logs
```

### IMPORTANT RULES:
- **After ANY code changes**, always run: `./manage.sh restart`
- **To check if bot is working**, run: `./manage.sh status`
- **If something goes wrong**, check logs: `./manage.sh logs`
- The bot runs in the background - closing the terminal won't stop it
- Logs are saved to `logs/bot.log`

---

## Logging System

All bot activity is logged to `logs/bot.log`:
- Bot startup/shutdown events
- Command usage (who used what command)
- Errors and warnings
- API calls and responses

To view logs:
```bash
./manage.sh logs      # Live view (Ctrl+C to exit)
./manage.sh logs 100  # Last 100 lines
```

---

## After Making Changes Checklist

Every time code is modified, Claude MUST:
1. Commit the changes with a descriptive message
2. Tell the user to run: `./manage.sh restart`
3. Tell them how to verify it works: `./manage.sh status` and `./manage.sh logs`
