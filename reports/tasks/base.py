from celery.task import Task

from reports.models import ReportTaskStatus


class BaseTask(Task):

    def on_failure(self, exc, task_id, args, kwargs, einfo):
        if kwargs.get('task_status_id'):
            task_status = ReportTaskStatus.objects.get(
                id=kwargs['task_status_id'])

            task_status.status = ReportTaskStatus.FAILED
            task_status.error = exc
            task_status.save()
            super(BaseTask, self).on_failure(exc, task_id, args, kwargs, einfo)
