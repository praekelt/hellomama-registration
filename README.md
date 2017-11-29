# hellomama-registration

HelloMama Registration accepts registrations for [the HelloMama project](https://www.praekelt.org/hellomama/).

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

##### registrations.created.last
`last` Total number of registrations created

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

##### registrations.language.{{language}}.sum
`sum` Number of registrations per language

##### registrations.language.{{language}}.last
`last` Total number of registrations per language

##### registrations.state.{{state}}.sum
`sum` Number of registrations per state

##### registrations.state.{{state}}.last
`last` Total number of registrations per state

##### registrations.role.{{role}}.sum
`sum` Number of registrations per role

##### registrations.role.{{role}}.last
`last` Total number of registrations per role

## Releasing
Releasing is done by building a new docker image. This is done automatically as
part of the travis build.

For every merge into develop, a new versioned develop release is created, with
the tag of the commit has.

For every new tag, a new versioned released is created, tagged with the git
tag.

To release a version for QA purposes, just merge to develop and a new image
will be built.

To release a version for production purposes, update the version in setup.py,
and tag the commit that updates the version to the version that it updates to,
and then push that tag. A new docker image and tag will be created according to
the version specified in the git tag.
