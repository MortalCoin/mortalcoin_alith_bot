# 🤖 MortalCoin Trading Bot

<div align="center">

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-%3E%3D3.8-blue)](https://www.python.org/)
[![Web3.py](https://img.shields.io/badge/Web3.py-%3E%3D6.0.0-green)](https://web3py.readthedocs.io/)
[![Alith AI](https://img.shields.io/badge/Alith%20AI-Powered-purple)](https://alith.lazai.network/)
[![Docker](https://img.shields.io/badge/Docker-Ready-blue)](https://www.docker.com/)

**⚔️ AI-powered trading bot for MortalCoin PvP battles ⚔️**

### 🔗 Quick Links

[🎮 Play MortalCoin](https://stage.mortalcoin.app/) • [🌐 Website](https://mortalcoin.app/) • [📄 Whitepaper](https://docs.mortalcoin.app/) • [📚 Smart Contracts](https://github.com/MortalCoin/mortalcoin-evm) • [🛠️ CLI Tool](https://github.com/MortalCoin/mortalcoin-evm-cli)

</div>

---

AI-powered trading bot for MortalCoin game using [Alith AI](https://alith.lazai.network/) for intelligent decision making.

## Features

- 🤖 **AI-Powered Trading**: Uses Alith AI to make intelligent trading decisions
- 🔄 **Automated Game Management**: Monitors and joins games automatically
- 📊 **Real-time Price Analysis**: Analyzes Uniswap V2 pool prices in real-time
- 💾 **Trade History**: Maintains complete history of games and positions
- 🔐 **Secure**: All signatures obtained through backend API
- 🐳 **Docker Support**: Easy deployment with Docker

## Architecture

### Key Components

- **Game Manager**: Handles game lifecycle and coordination
- **Alith AI Client**: Integrates with Alith AI for trading decisions
- **Backend Client**: Communicates with MortalCoin backend API for signatures
- **Price Feed**: Monitors Uniswap V2 pools for real-time price data
- **Database**: SQLite storage for game and position history
- **Blockchain Module**: Self-contained blockchain interaction utilities

## Installation

### Requirements

- Python 3.8+
- Ethereum wallet with ETH for gas and betting
- Alith AI API credentials
- Access to MortalCoin backend API

### Setup

1. **Clone the repository**:
   ```bash
   git clone https://github.com/MortalCoin/mortalcoin_alith_bot
   cd mortalcoin_alith_bot
   ```

2. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure environment**:
   ```bash
   cp env.example .env
   # Edit .env with your settings
   ```

4. **Required environment variables**:
   - `MORTALCOIN_RPC_URL`: Ethereum RPC endpoint
   - `MORTALCOIN_CONTRACT_ADDRESS`: MortalCoin contract address
   - `MORTALCOIN_BOT_PRIVATE_KEY`: Bot's private key (with or without 0x prefix)
   - `MORTALCOIN_PRIVY_KEY`: Your Privy key for backend authentication
   - `MORTALCOIN_BACKEND_API_URL`: Backend API URL (default: https://testapi.mortalcoin.app)
   - `OPENAI_API_KEY`: Your OpenAI API key (used by Alith)
   - `MORTALCOIN_BOT_POOL_ADDRESS`: Bot's whitelisted pool address

## Usage

### Run the bot

```bash
python main.py run
```

### Check bot status

```bash
python main.py status
```

### View game history

```bash
python main.py history --limit 10
```

### Test components

```bash
python test_bot.py
```

## Docker Deployment

### Build and run with Docker

```bash
docker build -t mortalcoin_alith_bot .
docker run --env-file .env mortalcoin_alith_bot
```

### Using Docker Compose

```bash
docker-compose up -d
```

## Configuration

### Trading Parameters

- `MORTALCOIN_BET_AMOUNT`: Bet amount in ETH (default: 0.0001)
- `MORTALCOIN_POSITION_HOLD_MIN`: ~~Minimum position hold time in seconds (default: 10)~~ **Removed - no minimum hold time restriction**
- `MORTALCOIN_POSITION_HOLD_MAX`: Maximum position hold time in seconds (default: 50)

### Alith AI Configuration

- `ALITH_MODEL`: AI model to use (default: gpt-4)
- Custom prompts can be configured in `alith_client.py`

## How It Works

1. **Game Discovery**: Bot monitors the blockchain for available games
2. **Signature Exchange**: Obtains join signatures from backend API
3. **Game Entry**: Joins games with appropriate bet amount
4. **Market Analysis**: Monitors Uniswap V2 pool prices in real-time
5. **AI Decision Making**: Alith AI analyzes market conditions and opponent behavior
6. **Position Management**: Opens/closes positions based on AI recommendations
7. **Game Completion**: Handles game ending and settlement

## Alith AI Integration

This bot uses [Alith AI](https://alith.lazai.network/) - a decentralized AI network for building autonomous agents.

### What is Alith AI?

Alith AI is part of the Laz AI ecosystem, providing:
- **Decentralized AI Agents**: Run AI models without centralized control
- **Customizable Behavior**: Fine-tune agent responses and strategies
- **Real-time Decision Making**: Fast inference for time-sensitive trading
- **Secure Execution**: Your strategies remain private

### How the Bot Uses Alith

The bot leverages Alith AI to:
1. **Analyze Market Conditions**: Evaluate price trends and volatility
2. **Assess Opponent Behavior**: Understand opponent's trading patterns
3. **Make Trading Decisions**: Determine when to open/close positions
4. **Risk Management**: Balance aggressive vs conservative strategies

Learn more about Alith AI:
- [Documentation](https://alith.lazai.network/docs)
- [Tutorials](https://alith.lazai.network/docs/tutorials)
- [API Reference](https://alith.lazai.network/docs/api)

## API Integration

### Backend API Endpoints

- `/api/v1/games/join-signature/` - Get signature for joining games
- `/api/v1/games/position-signature/` - Get signature for posting positions
- `/api/v1/games/available/` - Get available games to join
- `/api/v1/pools/{pool_address}/price/` - Get price data for pools

### Blockchain Interaction

The bot includes a self-contained blockchain module that handles:
- Web3 connection management
- Contract interaction
- Transaction building and signing
- Gas estimation and optimization

### ABI Files Layout

- **Smart contract ABI**: stored in `contract_abi.json` at the project root. The bot loads this by default in `blockchain/connection.py` via `get_contract(...)`.
- **Backend ABI utilities**: stored in `backend_abi.yaml` at the project root for reference/utilities. The previous Python module `backend_abi.py` has been removed.

Notes:
- The old `abi.json` file has been removed. If you need to point to a custom ABI, pass an explicit `abi_path` to `blockchain.get_contract(...)`.

## Database Schema

### Games Table
- `game_id`: Unique game identifier
- `bot_address`: Bot's wallet address
- `opponent_address`: Opponent's wallet address
- `bet_amount`: Bet amount in ETH
- `started_at`: Game start timestamp
- `ended_at`: Game end timestamp
- `status`: Game status (active/completed/error)
- `role`: Bot's role (player1/player2)

### Positions Table
- `game_id`: Associated game ID
- `direction`: Position direction (Long/Short)
- `nonce`: Random nonce for position
- `opened_at`: Position open timestamp
- `closed_at`: Position close timestamp
- `entry_price`: Entry price
- `exit_price`: Exit price
- `pnl`: Position P&L
- `reasoning`: AI reasoning for the position

## Key Updates

### Backend API Integration
- **Signature Management**: All signatures (join game, post position) are now obtained through the backend API
- **No Backend Private Key**: The bot no longer needs the backend private key
- **API Endpoints**:
  - `/api/v1/games/join-signature/` - Get signature for joining games
  - `/api/v1/games/position-signature/` - Get signature for posting positions
  - `/api/v1/games/available/` - Get available games to join
  - `/api/v1/pools/{pool_address}/price/` - Get price data for pools

### Price Feed from Uniswap V2 Pools
- **Real Price Data**: Prices are calculated directly from Uniswap V2 pool reserves
- **Stable Token Support**: Handles different stable token positions (token0 or token1)
- **Price History**: Maintains local price history for trend analysis

### Fixed Game Duration
- **60 Second Games**: All games have a fixed duration of 60 seconds
- **Automatic Timeout**: Games automatically end after 60 seconds

## Limitations & Future Improvements

### Current Limitations
1. **API Dependencies**: Requires backend API to be available for signatures
2. **Single Bot Instance**: Designed for single bot instance. Multi-bot would need coordination
3. **Pool Whitelist**: Bot can only use whitelisted pools

### Future Improvements
1. **Real Price Feeds**: Integrate with Chainlink or other oracle services
2. **Advanced Strategies**: Implement more sophisticated trading strategies
3. **Multi-Game Optimization**: Optimize decisions across multiple concurrent games
4. **Performance Metrics**: Add detailed analytics and performance tracking

## Troubleshooting

### Common Issues

1. **Connection errors**: Check RPC URL and network connectivity
2. **Signature failures**: Verify backend API is accessible
3. **Transaction failures**: Ensure sufficient ETH for gas
4. **Pool errors**: Verify pool is whitelisted in contract

### Logs

Bot logs are written to console and can be redirected:
```bash
python main.py run > bot.log 2>&1
```

## Contributing

1. Fork the repository
2. Create your feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

## About MortalCoin

MortalCoin is a revolutionary Web3 trading game where players battle using real cryptocurrencies. Think of it as **"Mortal Kombat meets DeFi Trading"**.

### Game Mechanics
- **Real Stakes**: Players bet actual ETH, not virtual currency
- **Winner Takes All**: Better price prediction wins the entire pot
- **60-Second Battles**: Quick, intense trading duels
- **Multiple Pools**: Trade on any whitelisted Uniswap V2 pool

### Resources
- **Play Now**: [stage.mortalcoin.app](https://stage.mortalcoin.app/)
- **Documentation**: [docs.mortalcoin.app](https://docs.mortalcoin.app/)
- **Smart Contracts**: [github.com/MortalCoin/mortalcoin-evm](https://github.com/MortalCoin/mortalcoin-evm)
- **Community**: Join us on [Telegram](https://t.me/mortalcoin_news) and [Twitter](https://twitter.com/themortalcoin)

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Acknowledgments

- Built for the MortalCoin ecosystem
- Powered by [Alith AI](https://alith.lazai.network/)
- Uses Uniswap V2 for price feeds