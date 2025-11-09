# Sola-DK: Cross-Chain Bridge Event Listener Simulator

This project is a Python-based simulation of a critical backend component for a cross-chain bridge. It serves as an architectural showcase, demonstrating a robust, modular, and asynchronous approach to monitoring blockchain events and orchestrating cross-chain actions.

## Concept

A cross-chain bridge allows users to transfer assets or data from one blockchain (the *source chain*) to another (the *destination chain*). A common mechanism for this is the "lock-and-mint" model:

1.  A user **locks** their assets in a smart contract on the source chain (e.g., locking WETH on Ethereum).
2.  A network of off-chain listeners (oracles) detects this `TokensLocked` event.
3.  These listeners then trigger a transaction on the destination chain to **mint** a corresponding wrapped asset (e.g., minting WETH-on-Polygon).

This project simulates the off-chain listener component. It monitors a contract on a source chain for specific events, processes the event data, enriches it with external information (like token price), and then simulates the final transaction on the destination chain.

## Code Architecture

The script is designed with a clear separation of concerns, using distinct classes for each major function. This makes the system easier to understand, maintain, and extend.

-   `CrossChainBridgeListener`: The main orchestrator. It initializes all other components and runs the primary event loop, coordinating the flow of data.

-   `BlockchainConnector`: A reusable utility for managing connections to blockchain nodes via Web3.py. It handles connection setup and verification.

-   `BridgeContractMonitor`: Responsible for the core task of listening to the blockchain. It creates event filters and polls the source chain's bridge contract for new `TokensLocked` events (simulated using the standard ERC20 `Transfer` event for this example).

-   `EventProcessor`: Acts as the data transformation layer. It takes raw event logs from the monitor, decodes them, and enriches them with valuable metadata. In this simulation, it makes an asynchronous API call to CoinGecko to fetch the real-time USD price of the locked asset.

-   `TransactionBroadcaster`: This component represents the final step. In a real-world scenario, it would sign and broadcast a transaction on the destination chain to complete the bridge transfer. In this simulation, it logs a detailed, formatted message that simulates the transaction it *would* have broadcast, providing a clear view of the intended action without requiring private keys or funds.

### Orchestration Example

The modular design allows for a clean composition of components in the main script, illustrating the dependency injection pattern.

```python
# A simplified view of how components are orchestrated in script.py
def main():
    # Load configuration from .env
    config = load_config()

    # Instantiate each component with its dependencies
    source_connector = BlockchainConnector(config.source_rpc, "SourceChain")
    monitor = BridgeContractMonitor(source_connector, config.contract_address)
    processor = EventProcessor()
    broadcaster = TransactionBroadcaster("DestinationChain")

    # The main listener orchestrates the components
    listener = CrossChainBridgeListener(
        monitor=monitor,
        processor=processor,
        broadcaster=broadcaster
    )

    # Start the asynchronous event loop
    asyncio.run(listener.run())
```

### Data Flow

The data flows through the system in a clear, sequential pipeline:

```
[Source Chain RPC] <---(Polls for Events)-- [BridgeContractMonitor]
                                                      |
                                                      v (Raw Event Log)
                                                      |
[CoinGecko API] <----(Fetches Price)---- [EventProcessor]
                                                      |
                                                      v (Enriched Data)
                                                      |
[TransactionBroadcaster] --(Simulated Tx Log)--> [Console Output]
```

## How It Works

1.  **Initialization**: The `CrossChainBridgeListener` starts, reading configuration details (like RPC URLs and contract addresses) from a `.env` file and instantiating all necessary components.

2.  **Connection**: It uses `BlockchainConnector` instances to establish and verify connections to both the source and destination chain RPC endpoints.

3.  **Listening Loop**: The `BridgeContractMonitor` enters an asynchronous loop. In each iteration, it queries a range of blocks on the source chain for new `Transfer` events directed to the configured "bridge vault" address.

4.  **Event Processing**: When a new event is detected, its raw log data is passed to the `EventProcessor`. The processor decodes the event's arguments (e.g., sender, amount) and then makes a non-blocking HTTP request to the CoinGecko API to get the current USD price of the transferred token (WETH in this simulation).

5.  **Broadcast Simulation**: The enriched data—now including the transaction hash, user address, amount, and USD value—is sent to the `TransactionBroadcaster`. It formats this data into a human-readable log message that clearly describes the action that would be taken on the destination chain (e.g., "Simulating UNLOCK transaction...").

6.  **Continuous Operation**: The loop continues by updating the last polled block number and pausing for a configured interval before scanning the next block range. The entire process is asynchronous, making efficient use of I/O-bound operations like network requests.

## Usage Guide

Follow these steps to run the event listener simulation.

### 1. Prerequisites

-   Python 3.8+ and `pip`
-   Git

### 2. Clone the Repository

```bash
git clone https://github.com/your-username/sola-dk.git
cd sola-dk
```

### 3. Set Up a Virtual Environment

It is highly recommended to use a virtual environment to manage dependencies.

```bash
# For macOS / Linux
python3 -m venv venv
source venv/bin/activate

# For Windows
python -m venv venv
venv\Scripts\activate
```

### 4. Install Dependencies

Create a `requirements.txt` file in the project root with the following content:

```
web3
python-dotenv
aiohttp
```

Then, install the libraries using pip:

```bash
pip install -r requirements.txt
```

### 5. Configure Environment Variables

Create a file named `.env` in the root of the project directory. You will need RPC endpoint URLs for an Ethereum node (source) and a Polygon node (destination), which you can get for free from services like [Infura](https://infura.io/) or [Alchemy](https://www.alchemy.com/). You also need to specify the contract address to monitor and the "vault" address where assets are locked.

Copy the following into your `.env` file and replace the placeholders with your actual RPC URLs:

```env
# .env file

# RPC endpoint URLs (get free ones from Infura, Alchemy, etc.)
SOURCE_CHAIN_RPC_URL="https://mainnet.infura.io/v3/YOUR_INFURA_PROJECT_ID"
DESTINATION_CHAIN_RPC_URL="https://polygon-mainnet.infura.io/v3/YOUR_INFURA_PROJECT_ID"

# Address of the token contract to monitor on the source chain
# (Example: WETH contract on Ethereum Mainnet)
CONTRACT_ADDRESS="0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2"

# The "vault" address that receives locked tokens.
# The script will monitor Transfer events where this is the destination.
BRIDGE_VAULT_ADDRESS="0x1111111111111111111111111111111111111111"
```

### 6. Run the Script

Execute the main script from your terminal:

```bash
python script.py
```

### 7. Expected Output

The script will start, connect to the chains, and begin polling for events from the hardcoded start block. You should see output similar to the following as it finds and processes events:

```
2023-10-27 14:30:00 - INFO - [CrossChainBridgeListener] - Initializing Cross-Chain Bridge Listener service...
2023-10-27 14:30:01 - INFO - [BlockchainConnector] - Connecting to SourceChain via https://mainnet.infura.io/v3/...
2023-10-27 14:30:03 - INFO - [BlockchainConnector] - Successfully connected to SourceChain. Latest block: 19500125
2023-10-27 14:30:03 - INFO - [BlockchainConnector] - Connecting to DestinationChain via https://polygon-mainnet.infura.io/v3/...
2023-10-27 14:30:05 - INFO - [BlockchainConnector] - Successfully connected to DestinationChain. Latest block: 55403210
2023-10-27 14:30:05 - INFO - [BridgeContractMonitor] - Monitoring contract at 0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2
2023-10-27 14:30:05 - INFO - [CrossChainBridgeListener] - Service started. Listening for new cross-chain events...
2023-10-27 14:30:05 - INFO - [BridgeContractMonitor] - Polling for 'Transfer' events to 0x1111111111111111111111111111111111111111 from block 19500001...
2023-10-27 14:30:08 - INFO - [BridgeContractMonitor] - Found 1 new event(s).
2023-10-27 14:30:08 - INFO - [EventProcessor] - Processing event from transaction: 0x...hash...
2023-10-27 14:30:09 - INFO - [EventProcessor] - Fetched price for 'ethereum': $3150.75
2023-10-27 14:30:09 - INFO - [EventProcessor] - Successfully processed event. Locked value: $1575.38
2023-10-27 14:30:09 - WARNING - [TransactionBroadcaster] - --- SIMULATION MODE --- Not broadcasting a real transaction.
2023-10-27 14:30:09 - INFO - [TransactionBroadcaster] - 
>>> SIMULATING UNLOCK TRANSACTION ON CHAIN 'DestinationChain' <<
    -> To User: 0x...user_address...
    -> Token Address (on dest. chain): [Corresponding wrapped asset address]
    -> Amount: 500000000000000000 (wei equivalent)
    -> Source Tx Hash: 0x...hash...
----------------------------------------------------------------------
2023-10-27 14:30:10 - INFO - [TransactionBroadcaster] - Simulation complete for source tx 0x...hash...
```