"""Job to monitor proxy contracts and their implementations"""

from src.jobs.base import Job, JobResult
from src.models.base import Asset, AssetType
from src.backend.database import DBSessionMixin
from src.util.etherscan import EVMExplorer, fetch_verified_sources
from src.handlers.base import HandlerTrigger
from src.handlers.registry import HandlerRegistry
from src.util.logging import Logger
import os
from urllib.parse import urlparse
from src.config.config import Config
from sqlalchemy import not_
from sqlalchemy.dialects.postgresql import JSONB


class ProxyMonitorJob(Job, DBSessionMixin):
    """Job that monitors proxy contracts for implementation upgrades"""

    def __init__(self):
        super().__init__("proxy_monitor")
        self.logger = Logger("ProxyMonitorJob")
        self.explorer = EVMExplorer()
        self.handler_registry = HandlerRegistry.get_instance()
        self.config = Config()

    async def stop_handler(self) -> None:
        """Handle job stop request - nothing to clean up"""

    async def start(self) -> None:
        """Start the proxy monitoring job"""
        try:
            self.logger.info("Starting proxy contract monitoring")

            with self.get_session() as session:
                # Only check contracts that haven't been marked as non-proxies
                contracts = (
                    session.query(Asset)
                    .filter(
                        Asset.asset_type == AssetType.DEPLOYED_CONTRACT,
                        not_(Asset.extra_data.cast(JSONB).contains({"is_not_proxy": True})),
                    )
                    .all()
                )

                self.logger.info(f"Found {len(contracts)} deployed contracts to check")

                for contract in contracts:
                    try:
                        self.logger.info(f"Checking contract {contract.identifier} (extra_data: {contract.extra_data})")

                        # Check for proxy upgrade events
                        events = await self.explorer.get_proxy_upgrade_events(contract.identifier)

                        if not events:
                            # Initialize extra_data if None
                            if contract.extra_data is None:
                                contract.extra_data = {}

                            # Update in memory
                            contract.extra_data["is_not_proxy"] = True

                            # Update in database
                            session.add(contract)
                            session.commit()

                            self.logger.info(f"Marked {contract.identifier} as non-proxy (extra_data: {contract.extra_data})")
                            continue

                        # Get latest implementation address
                        latest_event = events[-1]
                        impl_address = latest_event["implementation"]

                        # Get explorer type from contract URL
                        is_supported, explorer_type = self.explorer.is_supported_explorer(contract.identifier)
                        if not is_supported:
                            self.logger.error(f"Unsupported explorer URL: {contract.identifier}")
                            continue

                        # Get explorer domain from config
                        explorer_domain = self.explorer.EXPLORERS[explorer_type]["domain"]
                        impl_url = f"https://{explorer_domain}/address/{impl_address}"

                        # Check if implementation changed
                        current_impl = contract.implementation
                        if current_impl and current_impl.identifier == impl_url:
                            continue

                        # Look for existing implementation asset
                        impl_asset = session.query(Asset).filter(Asset.identifier == impl_url).first()

                        # If implementation doesn't exist as an asset yet, create it
                        if not impl_asset:
                            # Use same directory structure as immunefi indexer
                            base_dir = os.path.join(self.config.data_dir, str(contract.project_id))
                            parsed_url = urlparse(impl_url)
                            target_dir = os.path.join(base_dir, parsed_url.netloc, parsed_url.path.strip("/"))

                            # Download implementation code
                            await fetch_verified_sources(impl_url, target_dir)

                            # Create new implementation asset
                            impl_asset = Asset(
                                identifier=impl_url,
                                project_id=contract.project_id,
                                asset_type=AssetType.DEPLOYED_CONTRACT,
                                source_url=impl_url,
                                local_path=target_dir,
                                extra_data={"is_implementation": True, "explorer_url": impl_url},
                            )
                            session.add(impl_asset)

                        # Update proxy relationship
                        old_impl = contract.implementation
                        contract.implementation = impl_asset

                        # Update implementation history
                        if contract.extra_data is None:
                            contract.extra_data = {}

                        if "implementation_history" not in contract.extra_data:
                            contract.extra_data["implementation_history"] = []

                        contract.extra_data["implementation_history"].append(
                            {
                                "address": impl_address,
                                "url": impl_url,
                                "block_number": latest_event["blockNumber"],
                                "timestamp": latest_event["timestamp"],
                            }
                        )

                        # Commit changes
                        session.commit()

                        # Always trigger upgrade event when we see a new implementation
                        await self.handler_registry.trigger_event(
                            HandlerTrigger.CONTRACT_UPGRADED,
                            {
                                "proxy": contract,
                                "old_implementation": old_impl,
                                "new_implementation": impl_asset,
                                "event": latest_event,
                            },
                        )

                    except Exception as e:
                        self.logger.error(f"Error processing contract {contract.identifier}: {str(e)}")
                        session.rollback()
                        continue

            await self.complete(JobResult(success=True, message="Proxy monitoring completed successfully"))

        except Exception as e:
            self.logger.error(f"Error in proxy monitoring job: {str(e)}")
            await self.fail(str(e))
