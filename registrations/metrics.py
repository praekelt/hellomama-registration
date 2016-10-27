import pika

from hellomama_registration import utils


class MetricGenerator(object):
    def generate_metric(self, name, start, end):
        """
        Generates a metric value for the given parameters.

        args:
            name: The name of the metric
            start: Datetime for where the metric window starts
            end: Datetime for where the metric window ends
        """
        metric_func = getattr(self, name.replace('.', '_'))
        return metric_func(start, end)


def send_metric(amqp_url, name, value, timestamp):
    parameters = pika.URLParameters(amqp_url)
    connection = pika.BlockingConnection(parameters)
    channel = connection.channel()

    timestamp = utils.timestamp_to_epoch(timestamp)

    channel.basic_publish(
        'graphite', name, '{} {}'.format(float(value), int(timestamp)),
        pika.BasicProperties(content_type='text/plain', delivery_mode=2))

    connection.close()
