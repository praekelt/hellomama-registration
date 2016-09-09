# hellomama-registration
HelloMama Registration accepts registrations for the Hello Mama project.

This app uses the Django cache framework for efficient calculation of metrics,
so if you are running multiple instances, make sure to setup a shared Django
cache backend for them.

## Apps & Models:
  * registrations
    * Source
    * Registration
    * SubscriptionRequest
  * changes
    * Change

## Metrics
##### registrations.created.sum
`sum` Total number of registrations created

##### registrations.source.ussd.sum
`sum` Total number of registrations created via USSD

##### registrations.source.ivr.sum
`sum` Total number of registrations created via IVR

##### registrations.unique_operators.sum
`sum` Total number of unique health workers who have completed registrations

##### registrations.msg_type.{{type}}.sum
`sum` Number of registrations per message type

##### registrations.msg_type.{{type}}.last
`last` Total number of registrations per message type

##### registrations.receiver_type.{{type}}.sum
`sum` Number of registrations per receiver type

##### registrations.receiver_type.{{type}}.last
`last` Total number of registrations per receiver type
