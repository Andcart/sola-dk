import os
import json
import asyncio
import logging
from typing import Dict, Any, AsyncGenerator

import aiohttp
from web3 import Web3
from web3.exceptions import MismatchedABI
from web3.contract import Contract
from web3.datastructures import AttributeDict
from dotenv import load_dotenv

# --- Configuration Setup ---

# Load environment variables from .env file
load_dotenv()

# Configure logging for clear and structured output
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - [%(name)s] - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

# --- Constants & Mock Data ---

# For simulation purposes, we'll monitor the Wrapped Ether (WETH) contract on Ethereum mainnet.
# We will treat a `Transfer` event to a fictional 'bridge' address as a 'TokensLocked' event.
SOURCE_CHAIN_CONTRACT_ADDRESS = '0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2'  # WETH Address

# A fictional bridge address that users would 'lock' funds into.
# In a real scenario, this would be the address of the deployed bridge contract.
BRIDGE_VAULT_ADDRESS = '0x1111111111111111111111111111111111111111'

# A simplified ABI for the ERC-20 `Transfer` event, which we will listen for.
# This allows us to decode event logs from the blockchain.
ERC20_TRANSFER_ABI = json.loads('''
[
  {
    "anonymous": false,
    "inputs": [
      {"indexed": true, "name": "src", "type": "address"},
      {"indexed": true, "name": "dst", "type": "address"},
      {"indexed": false, "name": "wad", "type": "uint256"}
    ],
    "name": "Transfer",
    "type": "event"
  }
]
''')

# The destination chain ID (e.g., 137 for Polygon) where tokens should be unlocked/minted.
# This would typically be encoded in the `data` field of the lock transaction.
# For this simulation, we'll use a fixed value.
DESTINATION_CHAIN_ID = 137

# Mock CoinGecko API endpoint for fetching token prices.
COINGECKO_API_URL = 'https://api.coingecko.com/api/v3/simple/price'

# --- Core Architectural Components ---

class BlockchainConnector:
    """Manages connection to a blockchain node via a Web3 provider."""

    def __init__(self, chain_name: str, rpc_url: str):
        """
        Initializes the connector with a chain name and RPC URL.

        Args:
            chain_name (str): A human-readable name for the chain (e.g., 'Ethereum').
            rpc_url (str): The HTTP or WebSocket URL of the blockchain node.
        """
        self.chain_name = chain_name
        self.rpc_url = rpc_url
        self.web3: Web3 = None
        self.logger = logging.getLogger(self.__class__.__name__)

    async def connect(self) -> Web3:
        """
        Establishes and tests the connection to the blockchain node.

        Returns:
            Web3: An initialized and connected Web3 instance.
        
        Raises:
            ConnectionError: If the connection to the RPC endpoint fails.
        """
        if not self.rpc_url:
            self.logger.error(f"RPC URL for {self.chain_name} is not configured.")
            raise ValueError(f"RPC URL for {self.chain_name} is missing.")

        self.logger.info(f"Connecting to {self.chain_name} via {self.rpc_url[:30]}...")
        self.web3 = Web3(Web3.HTTPProvider(self.rpc_url))
        
        try:
            # Asynchronously check if the connection is alive
            latest_block = await asyncio.to_thread(self.web3.eth.get_block, 'latest')
            self.logger.info(f"Successfully connected to {self.chain_name}. Latest block: {latest_block.number}")
            return self.web3
        except Exception as e:
            self.logger.error(f"Failed to connect to {self.chain_name}: {e}")
            raise ConnectionError(f"Could not connect to {self.chain_name} RPC.") from e

class BridgeContractMonitor:
    """
    Monitors a specific contract on the source chain for relevant events.
    In this simulation, it looks for 'Transfer' events to our fictional vault.
    """

    def __init__(self, web3_instance: Web3, contract_address: str, contract_abi: Dict[str, Any]):
        """
        Initializes the monitor with a Web3 instance and contract details.

        Args:
            web3_instance (Web3): The connected Web3 instance for the source chain.
            contract_address (str): The address of the contract to monitor.
            contract_abi (Dict[str, Any]): The ABI of the contract, specifically including the event.
        """
        self.web3 = web3_instance
        self.logger = logging.getLogger(self.__class__.__name__)
        try:
            self.contract: Contract = self.web3.eth.contract(address=contract_address, abi=contract_abi)
            self.logger.info(f"Monitoring contract at {contract_address}")
        except Exception as e:
            self.logger.error(f"Failed to initialize contract at {contract_address}: {e}")
            raise

    async def poll_for_events(self, from_block: int) -> AsyncGenerator[AttributeDict, None]:
        """
        Polls for 'Transfer' events sent to the bridge vault address from a given block number.

        Args:
            from_block (int): The block number to start scanning from.

        Yields:
            AsyncGenerator[AttributeDict, None]: An asynchronous generator of event log objects.
        """
        self.logger.info(f"Polling for 'Transfer' events to {BRIDGE_VAULT_ADDRESS} from block {from_block}...")
        try:
            # This filter specifically looks for Transfer events where the destination (`dst`) is our vault.
            event_filter = await asyncio.to_thread(
                self.contract.events.Transfer.create_filter,
                fromBlock=from_block,
                argument_filters={'dst': BRIDGE_VAULT_ADDRESS}
            )
            
            new_entries = await asyncio.to_thread(event_filter.get_new_entries)
            if new_entries:
                self.logger.info(f"Found {len(new_entries)} new event(s).")
                for event in new_entries:
                    yield event
            # In a real implementation, you'd persist the last polled block number.
        except MismatchedABI:
            self.logger.error("ABI mismatch. Ensure the provided ABI contains the 'Transfer' event signature.")
        except Exception as e:
            self.logger.error(f"An error occurred while polling for events: {e}")

class EventProcessor:
    """
    Parses, validates, and enriches raw event data.
    This includes fetching supplementary data like token prices from external APIs.
    """

    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)

    async def _fetch_token_price_usd(self, token_id: str = 'ethereum') -> float:
        """
        Fetches the current price of a token in USD from CoinGecko.
        Uses aiohttp for non-blocking HTTP requests.

        Args:
            token_id (str): The CoinGecko identifier for the token (e.g., 'ethereum', 'usd-coin').

        Returns:
            float: The price in USD, or 0.0 if the fetch fails.
        """
        params = {'ids': token_id, 'vs_currencies': 'usd'}
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(COINGECKO_API_URL, params=params) as response:
                    response.raise_for_status()  # Raises HTTPError for bad responses (4xx or 5xx)
                    data = await response.json()
                    price = data.get(token_id, {}).get('usd', 0.0)
                    self.logger.info(f"Fetched price for '{token_id}': ${price}")
                    return float(price)
        except aiohttp.ClientError as e:
            self.logger.error(f"API request to CoinGecko failed: {e}")
            return 0.0
        except Exception as e:
            self.logger.error(f"An error occurred during price fetch: {e}")
            return 0.0

    async def process_event(self, event: AttributeDict) -> Dict[str, Any]:
        """
        Transforms a raw web3 event log into a structured, enriched message for cross-chain processing.

        Args:
            event (AttributeDict): The raw event log from web3.py.

        Returns:
            Dict[str, Any]: A dictionary containing processed and enriched event data.
        """
        self.logger.info(f"Processing event from transaction: {event.transactionHash.hex()}")
        
        # 1. Parse raw event data
        args = event.args
        amount_wei = args.wad
        amount_ether = Web3.from_wei(amount_wei, 'ether')
        
        # 2. Fetch external data for enrichment
        # Since we are monitoring WETH, the token ID is 'ethereum'.
        token_price_usd = await self._fetch_token_price_usd('ethereum')
        value_usd = float(amount_ether) * token_price_usd

        # 3. Structure the data for the next step in the pipeline
        processed_data = {
            'sourceTransactionHash': event.transactionHash.hex(),
            'sourceBlockNumber': event.blockNumber,
            'lockingUser': args.src,
            'lockedTokenAddress': event.address,
            'lockedAmount': str(amount_wei), # Use string for uint256 precision
            'lockedAmountDecimal': float(amount_ether),
            'lockedValueUSD': round(value_usd, 2),
            'destinationChainId': DESTINATION_CHAIN_ID
        }
        
        self.logger.info(f"Successfully processed event. Locked value: ${processed_data['lockedValueUSD']:.2f}")
        return processed_data

class TransactionBroadcaster:
    """
    Simulates the action of broadcasting a transaction on the destination chain.
    In a real system, this component would hold a private key, construct, sign, and send a transaction.
    """

    def __init__(self, destination_connector: BlockchainConnector):
        """
        Initializes the broadcaster with a connector for the destination chain.

        Args:
            destination_connector (BlockchainConnector): The connector for the target network.
        """
        self.destination_connector = destination_connector
        self.logger = logging.getLogger(self.__class__.__name__)

    async def simulate_broadcast_unlock(self, processed_data: Dict[str, Any]):
        """
        Logs the details of the transaction that would be sent to the destination chain.

        Args:
            processed_data (Dict[str, Any]): The structured data from the EventProcessor.
        """
        self.logger.warning("--- SIMULATION MODE --- Not broadcasting a real transaction.")
        
        log_message = (f"\n"        
            f">>> SIMULATING UNLOCK TRANSACTION ON CHAIN '{self.destination_connector.chain_name}' <<\n"
            f"    -> To User: {processed_data['lockingUser']}\n"
            f"    -> Token Address (on dest. chain): [Corresponding wrapped asset address]\n"
            f"    -> Amount: {processed_data['lockedAmount']} (wei equivalent)\n"
            f"    -> Source Tx Hash: {processed_data['sourceTransactionHash']}\n"
            f"----------------------------------------------------------------------")
        
        self.logger.info(log_message)
        # In a real implementation:
        # 1. Get nonce: `nonce = web3.eth.get_transaction_count(self.signer_address)`
        # 2. Build transaction: `tx = contract.functions.unlockTokens(...).build_transaction(...)`
        # 3. Sign transaction: `signed_tx = web3.eth.account.sign_transaction(tx, private_key)`
        # 4. Send transaction: `tx_hash = web3.eth.send_raw_transaction(signed_tx.rawTransaction)`
        # 5. Wait for receipt: `receipt = web3.eth.wait_for_transaction_receipt(tx_hash)`
        await asyncio.sleep(1) # Simulate network latency
        self.logger.info(f"Simulation complete for source tx {processed_data['sourceTransactionHash']}.")

# --- Main Orchestrator ---

class CrossChainBridgeListener:
    """
    Orchestrates the entire process from listening for events to simulating the final transaction.
    """

    def __init__(self, config: Dict[str, Any]):
        """
        Initializes all components based on the provided configuration.

        Args:
            config (Dict[str, Any]): A dictionary containing all necessary configuration parameters.
        """
        self.logger = logging.getLogger(self.__class__.__name__)
        self.config = config
        self.last_polled_block = config['start_block']
        
        # Initialize core components
        self.source_connector = BlockchainConnector('SourceChain', config['source_rpc_url'])
        self.destination_connector = BlockchainConnector('DestinationChain', config['destination_rpc_url'])
        self.event_processor = EventProcessor()
        self.tx_broadcaster = TransactionBroadcaster(self.destination_connector)
        self.monitor = None

    async def run(self):
        """The main execution loop for the listener service."""
        self.logger.info("Initializing Cross-Chain Bridge Listener service...")
        
        # Establish blockchain connections
        source_web3 = await self.source_connector.connect()
        await self.destination_connector.connect() # Connect to destination to ensure it's available

        self.monitor = BridgeContractMonitor(
            source_web3,
            self.config['contract_address'],
            self.config['contract_abi']
        )

        self.logger.info("Service started. Listening for new cross-chain events...")
        while True:
            try:
                current_block = await asyncio.to_thread(source_web3.eth.get_block_number)
                # Process a limited range of blocks to avoid overwhelming the RPC node
                to_block = min(self.last_polled_block + self.config['block_scan_range'], current_block)

                if self.last_polled_block >= to_block:
                    self.logger.info(f"No new blocks to scan. Current block: {current_block}. Waiting...")
                    await asyncio.sleep(self.config['poll_interval_seconds'])
                    continue
                
                async for event in self.monitor.poll_for_events(self.last_polled_block + 1):
                    processed_event_data = await self.event_processor.process_event(event)
                    await self.tx_broadcaster.simulate_broadcast_unlock(processed_event_data)

                self.last_polled_block = to_block
                await asyncio.sleep(self.config['poll_interval_seconds'])

            except ConnectionError:
                self.logger.error("Connection lost. Attempting to reconnect...")
                await asyncio.sleep(30) # Wait longer before retrying a failed connection
                await self.source_connector.connect() # Attempt to reconnect
            except Exception as e:
                self.logger.error(f"An unexpected error occurred in the main loop: {e}", exc_info=True)
                await asyncio.sleep(15)

async def main():
    """Entry point for the script."""
    config = {
        'source_rpc_url': os.getenv('SOURCE_CHAIN_RPC_URL'),
        'destination_rpc_url': os.getenv('DESTINATION_CHAIN_RPC_URL'),
        'contract_address': SOURCE_CHAIN_CONTRACT_ADDRESS,
        'contract_abi': ERC20_TRANSFER_ABI,
        'poll_interval_seconds': 15,
        'block_scan_range': 100, # Number of blocks to scan in each iteration
        # For this simulation, we start from a recent block to find events quickly.
        # In a production system, this would be the block the contract was deployed at.
        'start_block': 19500000
    }

    if not config['source_rpc_url'] or not config['destination_rpc_url']:
        logging.error("CRITICAL: SOURCE_CHAIN_RPC_URL and DESTINATION_CHAIN_RPC_URL must be set in the .env file.")
        return

    listener_service = CrossChainBridgeListener(config)
    await listener_service.run()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.info("Service stopped by user.")
