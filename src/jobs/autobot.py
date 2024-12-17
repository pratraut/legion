"""Job that runs an agent with a custom prompt"""

from datetime import datetime
from src.jobs.base import Job, JobResult
from src.ai.autobot import Autobot
from src.actions.registry import ActionRegistry


class AutobotJob(Job):
    """Job that runs an agent with a custom prompt"""

    def __init__(self, prompt: str):
        super().__init__(job_type="autobot")
        self.prompt = prompt
        # Get the singleton instance of ActionRegistry that's already initialized
        action_registry = ActionRegistry()
        action_registry.initialize()
        self.agent = Autobot(action_registry=action_registry)

    async def start(self) -> None:
        """Start the autobot job"""
        try:
            self.started_at = datetime.utcnow()

            # Create task for the agent
            task = {"prompt": self.prompt, "timestamp": self.started_at.isoformat()}

            # Execute the task
            result = await self.agent.execute_task(task)

            # Create job result
            if result.success:
                # The agent's final message is in result.data["result"]
                message = result.data.get("result", "Task completed successfully")

                job_result = JobResult(
                    success=True,
                    message=message,
                    data={
                        "prompt": self.prompt,
                        "execution_time": (datetime.utcnow() - self.started_at).total_seconds(),
                    },
                )

                # Complete the job with success
                await self.complete(job_result)
            else:
                # Handle error case
                error_msg = result.error or "Task failed without specific error message"
                await self.fail(error_msg)

        except Exception as e:
            self.logger.error(f"Autobot job failed: {str(e)}")
            await self.fail(str(e))

    async def stop_handler(self) -> None:
        """Handle cleanup when stopping the job"""
        # No special cleanup needed for autobot jobs
        pass
