# the actual celery worker that executes task plan_steps one by one
# picks up tasks from the queue and runs them using the orchestrator

import logging

from orchestrator.escalation_engine import EscalationEngine
from models.datatypes import TaskStatus

logger = logging.getLogger("backend.workers.task_runner")

class TaskRunner:
    def __init__(self, tool_registry:dict):
        # handles the task with the given list of tools
        self.tool_registry = tool_registry
        self.escalation = EscalationEngine()

    def run(self, task):
        total = len(task.task_plan.plan_steps)
        task.status = TaskStatus.IN_PROGRESS # start running
        logger.info("task_id=%s starting run, total_steps=%d", task.id, total)

        while not task.task_plan.is_done():
            # get each step then run, if met somethign that needs escalation, give control to orchestrator to handle it.
            # we can always get back to running in the next step
            step = task.task_plan.current_step()
            step_num = task.task_plan.step_counter + 1
            logger.info(
                "task_id=%s step=%d/%d tool=%s status=PENDING",
                task.id, step_num, total, step.tool,
            )

            if self.escalation.step_needs_escalation(step):
                task.status = TaskStatus.ESCALATION_PENDING
                logger.info("task_id=%s step=%d/%d tool=%s escalation_triggered", task.id, step_num, total, step.tool)
                return

            # should add some gurads and asserts later on what to do if required adaptres is not in registery
            # for now I will just raise error
            adapter= self.tool_registry.get(step.tool)
            if adapter is None:
                raise KeyError(f"No adapter registered for tool:{step.tool}") # will add catch in orchestrator or upper layer. maybe we shoud pass control more nicely.
            if adapter:
                result = adapter.execute(step.params)
                step.result = result
                if self.escalation.step_result_needs_escalation(step, result or {}):
                    task.status = TaskStatus.ESCALATION_PENDING
                    logger.info(
                        "task_id=%s step=%d/%d tool=%s escalation_triggered (conflict)",
                        task.id, step_num, total, step.tool,
                    )
                    return
            step.status = TaskStatus.COMPLETED
            logger.info(
                "task_id=%s step=%d/%d tool=%s status=COMPLETED",
                task.id, step_num, total, step.tool,
            )
            task.task_plan.to_next_step() # carry on


        # reached the end
        task.status = TaskStatus.COMPLETED
        logger.info("task_id=%s status=COMPLETED", task.id)

