from src.actions.base import BaseAction, ActionSpec, ActionArgument, AsyncAction
from src.jobs.indexer import IndexerJob
import asyncio

@AsyncAction
class ImmunefiSyncAction(BaseAction):
    """Action to sync Immunefi data"""
    
    spec = ActionSpec(
        name="sync",
        description="Sync Immunefi data",
        arguments=[]
    )
    
    def __init__(self, initialize_mode: bool = False):
        """Initialize the action"""
        self.initialize_mode = initialize_mode
        
    async def initialize(self) -> None:
        """Initialize Immunefi data"""
        indexer = IndexerJob(platform="immunefi", initialize_mode=True)
        await indexer.start()
    
    async def execute(self, *args, **kwargs) -> str:
        """Execute the sync action"""
        # Import JobManager here to avoid circular imports
        from src.jobs.manager import JobManager
        
        job = IndexerJob(platform="immunefi", initialize_mode=False)
        job_manager = JobManager()
        job_id = await job_manager.submit_job(job)
        return f"Started Immunefi sync (Job ID: {job_id})"