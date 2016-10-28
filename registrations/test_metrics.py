try:
    import mock
except ImportError:
    from unittest import mock

from datetime import datetime
from django.test import TestCase

from .metrics import MetricGenerator, send_metric


class MetricsGeneratorTests(TestCase):
    def test_generate_metric(self):
        """
        The generate_metric function should call the correct function with the
        correct start and end datetimes.
        """
        generator = MetricGenerator()
        generator.foo_bar = mock.MagicMock()
        start = datetime(2016, 10, 26)
        end = datetime(2016, 10, 26)
        generator.generate_metric('foo.bar', start, end)

        generator.foo_bar.assert_called_once_with(start, end)


class SendMetricTests(TestCase):
    @mock.patch('pika.BlockingConnection')
    def test_send_metric(self, mock_BlockingConnection):
        """
        The send metric function should create a connection to the AMQP server
        and publish the correct message to the correct exchange, then close
        the connection.
        """
        url = 'amqp://guest:guest@localhost:5672/%2F'
        send_metric(url, '', 'foo.bar', 17, datetime.utcfromtimestamp(1317))

        [urlparams], _ = mock_BlockingConnection.call_args
        self.assertEqual(urlparams.host, 'localhost')
        self.assertEqual(urlparams.port, 5672)
        self.assertEqual(urlparams.virtual_host, '/')
        self.assertEqual(urlparams.credentials.username, 'guest')
        self.assertEqual(urlparams.credentials.password, 'guest')

        connection = mock_BlockingConnection.return_value
        connection.channel.assert_called_once()
        connection.close.assert_called_once()

        channel = connection.channel.return_value
        [exchange, routing_key, message, properties], _ = (
            channel.basic_publish.call_args)
        self.assertEqual(exchange, 'graphite')
        self.assertEqual(routing_key, 'foo.bar')
        self.assertEqual(message, '17.0 1317')
        self.assertEquals(properties.delivery_mode, 2)
        self.assertEquals(properties.content_type, 'text/plain')

    @mock.patch('pika.BlockingConnection')
    def test_send_metric_prefix(self, mock_BlockingConnection):
        """
        The send_metric function should add the correct prefix tot he metric
        name that it sends.
        """
        url = 'amqp://guest:guest@localhost:5672/%2F'
        send_metric(
            url, 'test.prefix', 'foo.bar', 17, datetime.utcfromtimestamp(1317))

        connection = mock_BlockingConnection.return_value
        channel = connection.channel.return_value
        [exchange, routing_key, message, properties], _ = (
            channel.basic_publish.call_args)
        self.assertEqual(exchange, 'graphite')
        self.assertEqual(routing_key, 'test.prefix.foo.bar')
        self.assertEqual(message, '17.0 1317')
        self.assertEquals(properties.delivery_mode, 2)
        self.assertEquals(properties.content_type, 'text/plain')
