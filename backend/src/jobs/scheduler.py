from apscheduler.schedulers.asyncio import AsyncIOScheduler
from logging import getLogger

LOGGER = getLogger(__name__)


class JobScheduler(AsyncIOScheduler):
    """
    Singleton for the job scheduler.
    """

    def __init__(self):
        super().__init__()


def init_job_scheduler() -> "JobScheduler":
    """
    Initializes and starts the job scheduler
    """
    # Check and see if the job scheduler instance has already been initialized
    tmp = getattr(JobScheduler, "instance", None)

    # If it has, then error.
    if tmp:
        raise ValueError(
            "Cannot intiialize job scheduler: job scheduler is already initalized"
        )

    # If not, then create a new instance and attach it to the class object
    js = JobScheduler()
    setattr(JobScheduler, "instance", js)

    LOGGER.info("Starting job scheduler...")

    # Start the job scheduler.
    js.start()

    return js


def kill_job_scheduler(*, wait: bool = True) -> None:
    """
    Stops the job scheduler from running
    """
    get_job_scheduler().shutdown(wait=wait)


def get_job_scheduler() -> JobScheduler:
    """
    Returns the job scheduler singleton
    """

    tmp = getattr(JobScheduler, "instance", None)

    if tmp is None:
        raise ValueError(
            "Cannot get job scheduler: job scheduler has not been initialized"
        )

    return tmp


__all__ = ["JobScheduler", "init_job_scheduler", "get_job_scheduler"]
