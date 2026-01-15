"""
Community Stock Market Database - Gamble on other members' activity!
NOTE: This is a GLOBAL stock market - shares are shared across all servers!

This module handles:
- Member stock prices based on activity
- Share purchases and sales
- Portfolio tracking
- Price history and calculations
"""

import os
import json
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Tuple

# File path for storing stock data
DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data')
STOCKS_FILE = os.path.join(DATA_DIR, 'stocks.json')

# ============================================
# STOCK MARKET CONFIGURATION
# ============================================

# Base price for new members (everyone starts here)
BASE_STOCK_PRICE = 100

# Maximum shares one person can own of another
MAX_SHARES_PER_PERSON = 100

# Maximum total shares that can exist for any member
MAX_TOTAL_SHARES = 1000

# Minimum shares to buy/sell
MIN_TRANSACTION = 1

# Price calculation weights
# Stock price = BASE + (messages_today * MSG_WEIGHT) + (xp_today * XP_WEIGHT) + (voice_mins * VOICE_WEIGHT)
ACTIVITY_WEIGHTS = {
    "messages": 0.5,      # 0.5 coins per message
    "xp_earned": 0.1,     # 0.1 coins per XP
    "voice_minutes": 1,   # 1 coin per voice minute
}

# Price volatility - how much random variance to add
VOLATILITY_PERCENT = 10

# Transaction fee (percentage of transaction)
TRANSACTION_FEE_PERCENT = 2

# Price update interval (how often prices recalculate)
PRICE_UPDATE_MINUTES = 30


# ============================================
# DATA PERSISTENCE FUNCTIONS
# ============================================

def _load_stocks_data() -> dict:
    """Load stocks data from JSON file"""
    os.makedirs(DATA_DIR, exist_ok=True)

    if os.path.exists(STOCKS_FILE):
        try:
            with open(STOCKS_FILE, 'r') as f:
                data = json.load(f)
                # Check if we need to migrate from old guild-based format
                if "guilds" in data and "members" not in data:
                    data = _migrate_to_global(data)
                return data
        except (json.JSONDecodeError, FileNotFoundError):
            pass

    return {"members": {}, "portfolios": {}, "transactions": []}


def _migrate_to_global(old_data: dict) -> dict:
    """
    Migrate from guild-based stocks to global stocks.
    Merges data from all guilds.
    """
    from utils.logger import logger
    logger.info("Migrating stocks data from guild-based to global...")

    new_data = {"members": {}, "portfolios": {}, "transactions": []}

    for guild_id, guild_data in old_data.get("guilds", {}).items():
        # Merge members
        for user_id, member_data in guild_data.get("members", {}).items():
            if user_id not in new_data["members"]:
                new_data["members"][user_id] = member_data.copy()
            else:
                # Merge - take higher values
                existing = new_data["members"][user_id]
                if member_data.get("current_price", 0) > existing.get("current_price", 0):
                    existing["current_price"] = member_data["current_price"]
                if member_data.get("base_price", 0) > existing.get("base_price", 0):
                    existing["base_price"] = member_data["base_price"]
                existing["shares_outstanding"] = existing.get("shares_outstanding", 0) + member_data.get("shares_outstanding", 0)

        # Merge portfolios
        for user_id, portfolio in guild_data.get("portfolios", {}).items():
            if user_id not in new_data["portfolios"]:
                new_data["portfolios"][user_id] = portfolio.copy()
            else:
                # Merge holdings
                existing = new_data["portfolios"][user_id]
                for target_id, holding in portfolio.get("holdings", {}).items():
                    if target_id not in existing["holdings"]:
                        existing["holdings"][target_id] = holding.copy()
                    else:
                        # Add shares together
                        existing["holdings"][target_id]["shares"] += holding.get("shares", 0)
                        existing["holdings"][target_id]["total_invested"] += holding.get("total_invested", 0)
                existing["total_invested"] = existing.get("total_invested", 0) + portfolio.get("total_invested", 0)

        # Merge transactions (keep last 100)
        new_data["transactions"].extend(guild_data.get("transactions", []))

    # Keep only last 100 transactions
    new_data["transactions"] = new_data["transactions"][-100:]

    _save_stocks_data(new_data)
    logger.info(f"Migration complete! Migrated {len(new_data['members'])} members and {len(new_data['portfolios'])} portfolios to global stocks.")
    return new_data


def _save_stocks_data(data: dict):
    """Save stocks data to JSON file"""
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(STOCKS_FILE, 'w') as f:
        json.dump(data, f, indent=2)


def _get_today_key() -> str:
    """Get today's date key"""
    return datetime.utcnow().strftime("%Y-%m-%d")


def _get_member_stock_data(guild_id: int, user_id: int) -> dict:
    """Get or create member stock data (GLOBAL - guild_id ignored)"""
    data = _load_stocks_data()
    user_str = str(user_id)

    if user_str not in data["members"]:
        data["members"][user_str] = {
            "base_price": BASE_STOCK_PRICE,
            "current_price": BASE_STOCK_PRICE,
            "shares_outstanding": 0,
            "price_history": [],
            "activity_today": {
                "messages": 0,
                "xp_earned": 0,
                "voice_minutes": 0,
                "date": _get_today_key()
            },
            "last_price_update": None
        }
        _save_stocks_data(data)

    return data["members"][user_str]


# ============================================
# ACTIVITY TRACKING (Updates stock prices)
# ============================================

def record_member_activity(guild_id: int, user_id: int, activity_type: str, amount: int = 1):
    """
    Record member activity which affects their stock price (GLOBAL - guild_id ignored)

    Args:
        guild_id: Ignored (kept for backwards compatibility)
        user_id: The member whose stock is affected
        activity_type: "messages", "xp_earned", or "voice_minutes"
        amount: Amount of activity
    """
    data = _load_stocks_data()
    user_str = str(user_id)

    # Ensure member data exists
    if user_str not in data["members"]:
        data["members"][user_str] = {
            "base_price": BASE_STOCK_PRICE,
            "current_price": BASE_STOCK_PRICE,
            "shares_outstanding": 0,
            "price_history": [],
            "activity_today": {
                "messages": 0,
                "xp_earned": 0,
                "voice_minutes": 0,
                "date": _get_today_key()
            },
            "last_price_update": None
        }

    member = data["members"][user_str]
    today = _get_today_key()

    # Reset daily activity if new day
    if member["activity_today"].get("date") != today:
        member["activity_today"] = {
            "messages": 0,
            "xp_earned": 0,
            "voice_minutes": 0,
            "date": today
        }

    # Update activity
    if activity_type in member["activity_today"]:
        member["activity_today"][activity_type] += amount

    # Recalculate price
    _update_member_price(data, user_str)

    _save_stocks_data(data)


def _update_member_price(data: dict, user_str: str):
    """Recalculate member's stock price based on activity"""
    member = data["members"][user_str]
    activity = member["activity_today"]

    # Calculate activity bonus
    activity_bonus = 0
    for act_type, weight in ACTIVITY_WEIGHTS.items():
        activity_bonus += activity.get(act_type, 0) * weight

    # Calculate new price
    base = member.get("base_price", BASE_STOCK_PRICE)
    new_price = int(base + activity_bonus)

    # Ensure minimum price
    new_price = max(10, new_price)

    # Store previous price in history (limit to last 24 entries)
    old_price = member.get("current_price", BASE_STOCK_PRICE)
    if old_price != new_price:
        member["price_history"].append({
            "price": old_price,
            "timestamp": datetime.utcnow().isoformat()
        })
        member["price_history"] = member["price_history"][-24:]

    member["current_price"] = new_price
    member["last_price_update"] = datetime.utcnow().isoformat()


# ============================================
# STOCK TRADING FUNCTIONS
# ============================================

def get_stock_price(guild_id: int, user_id: int) -> int:
    """Get current stock price for a member (GLOBAL - guild_id ignored)"""
    member = _get_member_stock_data(guild_id, user_id)
    return member.get("current_price", BASE_STOCK_PRICE)


def get_member_stock_info(guild_id: int, user_id: int) -> Dict:
    """Get full stock info for a member (GLOBAL - guild_id ignored)"""
    member = _get_member_stock_data(guild_id, user_id)

    # Calculate price change
    history = member.get("price_history", [])
    if history:
        old_price = history[0]["price"]
        current = member.get("current_price", BASE_STOCK_PRICE)
        change = current - old_price
        change_pct = (change / old_price * 100) if old_price > 0 else 0
    else:
        change = 0
        change_pct = 0

    return {
        "current_price": member.get("current_price", BASE_STOCK_PRICE),
        "base_price": member.get("base_price", BASE_STOCK_PRICE),
        "shares_outstanding": member.get("shares_outstanding", 0),
        "price_change": change,
        "price_change_percent": change_pct,
        "activity_today": member.get("activity_today", {}),
        "price_history": history[-10:]  # Last 10 price points
    }


def buy_shares(guild_id: int, investor_id: int, target_id: int, num_shares: int) -> Tuple[bool, str, int, int]:
    """
    Buy shares in another member (GLOBAL - guild_id ignored)

    Args:
        guild_id: Ignored (kept for backwards compatibility)
        investor_id: User buying shares
        target_id: User whose shares are being bought
        num_shares: Number of shares to buy

    Returns:
        (success, message, total_cost, new_holding)
    """
    if investor_id == target_id:
        return False, "You can't buy shares in yourself!", 0, 0

    if num_shares < MIN_TRANSACTION:
        return False, f"Minimum transaction is {MIN_TRANSACTION} share(s)!", 0, 0

    data = _load_stocks_data()

    investor_str = str(investor_id)
    target_str = str(target_id)

    # Ensure target member data exists
    if target_str not in data["members"]:
        data["members"][target_str] = {
            "base_price": BASE_STOCK_PRICE,
            "current_price": BASE_STOCK_PRICE,
            "shares_outstanding": 0,
            "price_history": [],
            "activity_today": {
                "messages": 0,
                "xp_earned": 0,
                "voice_minutes": 0,
                "date": _get_today_key()
            },
            "last_price_update": None
        }

    target_member = data["members"][target_str]
    current_price = target_member.get("current_price", BASE_STOCK_PRICE)

    # Check share limits
    current_outstanding = target_member.get("shares_outstanding", 0)
    if current_outstanding + num_shares > MAX_TOTAL_SHARES:
        available = MAX_TOTAL_SHARES - current_outstanding
        return False, f"Only {available} shares available for this member!", 0, 0

    # Initialize portfolio if needed
    if investor_str not in data["portfolios"]:
        data["portfolios"][investor_str] = {"holdings": {}, "total_invested": 0}

    portfolio = data["portfolios"][investor_str]

    # Check personal share limit
    current_holding = portfolio["holdings"].get(target_str, {}).get("shares", 0)
    if current_holding + num_shares > MAX_SHARES_PER_PERSON:
        available = MAX_SHARES_PER_PERSON - current_holding
        return False, f"You can only own {MAX_SHARES_PER_PERSON} shares per person! You can buy {available} more.", 0, 0

    # Calculate cost with fee
    base_cost = current_price * num_shares
    fee = int(base_cost * TRANSACTION_FEE_PERCENT / 100)
    total_cost = base_cost + fee

    # Check balance (use guild_id=0 since economy is now global)
    from utils.economy_db import get_balance, remove_coins
    balance = get_balance(0, investor_id)
    if balance < total_cost:
        return False, f"Not enough coins! Cost: {total_cost:,} (includes {fee:,} fee). You have {balance:,}.", 0, 0

    # Process transaction
    remove_coins(0, investor_id, total_cost)

    # Update holdings
    if target_str not in portfolio["holdings"]:
        portfolio["holdings"][target_str] = {
            "shares": 0,
            "avg_buy_price": 0,
            "total_invested": 0
        }

    holding = portfolio["holdings"][target_str]
    old_shares = holding["shares"]
    old_invested = holding["total_invested"]

    holding["shares"] += num_shares
    holding["total_invested"] += base_cost
    holding["avg_buy_price"] = holding["total_invested"] / holding["shares"]

    portfolio["total_invested"] += base_cost

    # Update target's outstanding shares
    target_member["shares_outstanding"] = current_outstanding + num_shares

    # Record transaction
    data["transactions"].append({
        "type": "buy",
        "investor": investor_str,
        "target": target_str,
        "shares": num_shares,
        "price": current_price,
        "total_cost": total_cost,
        "fee": fee,
        "timestamp": datetime.utcnow().isoformat()
    })

    # Keep only last 100 transactions
    data["transactions"] = data["transactions"][-100:]

    _save_stocks_data(data)

    return True, f"Purchased {num_shares} share(s) at {current_price:,} coins each!", total_cost, holding["shares"]


def sell_shares(guild_id: int, investor_id: int, target_id: int, num_shares: int) -> Tuple[bool, str, int, int]:
    """
    Sell shares in another member (GLOBAL - guild_id ignored)

    Returns:
        (success, message, total_received, profit_loss)
    """
    if num_shares < MIN_TRANSACTION:
        return False, f"Minimum transaction is {MIN_TRANSACTION} share(s)!", 0, 0

    data = _load_stocks_data()

    investor_str = str(investor_id)
    target_str = str(target_id)

    # Check if investor has shares
    if investor_str not in data["portfolios"]:
        return False, "You don't have any shares to sell!", 0, 0

    portfolio = data["portfolios"][investor_str]
    holding = portfolio["holdings"].get(target_str)

    if not holding or holding["shares"] < num_shares:
        current = holding["shares"] if holding else 0
        return False, f"You only have {current} share(s) of this member!", 0, 0

    # Get current price
    target_member = data["members"].get(target_str, {})
    current_price = target_member.get("current_price", BASE_STOCK_PRICE)

    # Calculate sale value
    gross_value = current_price * num_shares
    fee = int(gross_value * TRANSACTION_FEE_PERCENT / 100)
    net_value = gross_value - fee

    # Calculate profit/loss
    avg_buy = holding["avg_buy_price"]
    cost_basis = int(avg_buy * num_shares)
    profit_loss = net_value - cost_basis

    # Add coins to investor (use guild_id=0 since economy is now global)
    from utils.economy_db import add_coins
    add_coins(0, investor_id, net_value, source="stock_sale")

    # Update holdings
    holding["shares"] -= num_shares
    if holding["shares"] == 0:
        del portfolio["holdings"][target_str]
    else:
        # Adjust total invested proportionally
        ratio = holding["shares"] / (holding["shares"] + num_shares)
        holding["total_invested"] = int(holding["total_invested"] * ratio)

    # Update target's outstanding shares
    current_outstanding = target_member.get("shares_outstanding", 0)
    target_member["shares_outstanding"] = max(0, current_outstanding - num_shares)

    # Record transaction
    data["transactions"].append({
        "type": "sell",
        "investor": investor_str,
        "target": target_str,
        "shares": num_shares,
        "price": current_price,
        "net_received": net_value,
        "fee": fee,
        "profit_loss": profit_loss,
        "timestamp": datetime.utcnow().isoformat()
    })

    data["transactions"] = data["transactions"][-100:]

    _save_stocks_data(data)

    return True, f"Sold {num_shares} share(s) at {current_price:,} coins each!", net_value, profit_loss


def get_portfolio(guild_id: int, user_id: int) -> Dict:
    """Get user's investment portfolio (GLOBAL - guild_id ignored)"""
    data = _load_stocks_data()
    user_str = str(user_id)

    if user_str not in data["portfolios"]:
        return {
            "holdings": {},
            "total_invested": 0,
            "total_value": 0,
            "total_profit_loss": 0
        }

    portfolio = data["portfolios"][user_str]
    holdings = portfolio.get("holdings", {})

    # Calculate current values
    total_value = 0
    holdings_with_values = {}

    for target_str, holding in holdings.items():
        shares = holding["shares"]
        if shares <= 0:
            continue

        # Get current price
        target_member = data["members"].get(target_str, {})
        current_price = target_member.get("current_price", BASE_STOCK_PRICE)

        current_value = current_price * shares
        total_value += current_value

        cost_basis = holding["total_invested"]
        profit_loss = current_value - cost_basis

        holdings_with_values[target_str] = {
            "shares": shares,
            "avg_buy_price": holding["avg_buy_price"],
            "current_price": current_price,
            "current_value": current_value,
            "cost_basis": cost_basis,
            "profit_loss": profit_loss,
            "profit_loss_percent": (profit_loss / cost_basis * 100) if cost_basis > 0 else 0
        }

    total_invested = portfolio.get("total_invested", 0)
    total_profit_loss = total_value - total_invested

    return {
        "holdings": holdings_with_values,
        "total_invested": total_invested,
        "total_value": total_value,
        "total_profit_loss": total_profit_loss,
        "profit_loss_percent": (total_profit_loss / total_invested * 100) if total_invested > 0 else 0
    }


def get_top_stocks(guild_id: int, limit: int = 10) -> List[Tuple[str, int, int, float]]:
    """
    Get the top-performing stocks (GLOBAL - guild_id ignored)

    Returns:
        List of (user_id, current_price, shares_outstanding, price_change_percent)
    """
    data = _load_stocks_data()

    stocks = []
    for user_str, member in data.get("members", {}).items():
        price = member.get("current_price", BASE_STOCK_PRICE)
        shares = member.get("shares_outstanding", 0)

        # Calculate change
        history = member.get("price_history", [])
        if history:
            old_price = history[0]["price"]
            change_pct = ((price - old_price) / old_price * 100) if old_price > 0 else 0
        else:
            change_pct = 0

        stocks.append((user_str, price, shares, change_pct))

    # Sort by price (highest first)
    stocks.sort(key=lambda x: x[1], reverse=True)

    return stocks[:limit]


def get_most_invested(guild_id: int, limit: int = 10) -> List[Tuple[str, int]]:
    """Get members with the most shares outstanding (most invested in) (GLOBAL - guild_id ignored)"""
    data = _load_stocks_data()

    invested = []
    for user_str, member in data.get("members", {}).items():
        shares = member.get("shares_outstanding", 0)
        if shares > 0:
            invested.append((user_str, shares))

    invested.sort(key=lambda x: x[1], reverse=True)
    return invested[:limit]


def reset_daily_activity(guild_id: int):
    """Reset all members' daily activity (call at midnight) (GLOBAL - guild_id ignored)"""
    data = _load_stocks_data()

    today = _get_today_key()

    for user_str, member in data.get("members", {}).items():
        if member["activity_today"].get("date") != today:
            # Save yesterday's final price as new base (with decay)
            old_price = member.get("current_price", BASE_STOCK_PRICE)
            # New base is 80% of old price (decay toward BASE_STOCK_PRICE)
            new_base = int(old_price * 0.8 + BASE_STOCK_PRICE * 0.2)
            member["base_price"] = new_base
            member["current_price"] = new_base

            member["activity_today"] = {
                "messages": 0,
                "xp_earned": 0,
                "voice_minutes": 0,
                "date": today
            }

    _save_stocks_data(data)
