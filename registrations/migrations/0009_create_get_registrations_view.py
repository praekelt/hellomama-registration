# -*- coding: utf-8 -*-
# Generated by Django 1.11.10 on 2018-07-20 09:48
from __future__ import unicode_literals

from django.db import migrations

sql = """
    CREATE OR REPLACE FUNCTION get_registrations (
        db_link_conn VARCHAR, filter_state VARCHAR, filter_facility VARCHAR, filter_msisdn VARCHAR,
        status VARCHAR, filter_date VARCHAR, page_size INT, page_offset INT)
     RETURNS TABLE (
     identity_id VARCHAR,
     msisdn VARCHAR,
     receiver_role VARCHAR,
     validated BOOLEAN,
     created_at TIMESTAMP with time zone,
     updated_at TIMESTAMP with time zone,
     state VARCHAR,
     facility_name VARCHAR,
     linked_to_id VARCHAR,
     linked_to_msisdn VARCHAR,
     linked_to_receiver_role VARCHAR
    )
    AS $$
    BEGIN
     RETURN QUERY WITH identities_identity AS
          (SELECT * FROM dblink(db_link_conn,
           'select id, details, coalesce(operator_id::varchar, details->>''operator_id'') as operator_id from identities_identity')
           AS a("id" VARCHAR, "details" JSONB, "operator_id" VARCHAR))
        select
            identities_identity.id AS identity_id,
            (json_build_array(jsonb_object_keys(identities_identity.details->'addresses'->'msisdn')) ->> 0)::VARCHAR AS msisdn,
            (identities_identity.details->>'receiver_role')::VARCHAR AS receiver_role,
            registrations_registration.validated,
            registrations_registration.created_at,
            registrations_registration.updated_at,
            (identities_identity_operator.details->>'state')::VARCHAR AS state,
            (identities_identity_operator.details->>'facility_name')::VARCHAR AS facility_name,
            identities_identity_linked.id AS linked_to_id,
            CASE WHEN identities_identity_linked.details IS NOT NULL
                THEN jsonb_object_keys(identities_identity_linked.details->'addresses'->'msisdn')::VARCHAR
                ELSE '' END  AS linked_to_msisdn,
            (identities_identity_linked.details->>'receiver_role')::VARCHAR AS linked_to_receiver_role
        FROM registrations_registration,
            identities_identity
                LEFT JOIN identities_identity AS identities_identity_linked
                    ON identities_identity_linked.id = identities_identity.details->>'linked_to',
            identities_identity AS identities_identity_operator
        WHERE registrations_registration.mother_id = identities_identity.id
            AND identities_identity.operator_id = identities_identity_operator.id
            AND (identities_identity.details->'addresses'->'msisdn'?filter_msisdn OR '*' = filter_msisdn )
            AND (identities_identity_operator.details->'state'?filter_state OR '*' = filter_state)
            AND (filter_date = 'None' OR registrations_registration.created_at::date = filter_date::date)
            AND (identities_identity_operator.details->>'facility_name' ilike filter_facility OR '%*%' = filter_facility)
            AND ((registrations_registration.validated = TRUE and status in ('valid', '*')) OR (registrations_registration.validated = FALSE and status in ('invalid', '*')))
        ORDER BY created_at DESC
        LIMIT page_size + 1 OFFSET page_offset;
    END; $$

    LANGUAGE 'plpgsql';
"""

reverse_sql = """
DROP FUNCTION IF EXISTS get_registrations(VARCHAR, VARCHAR, VARCHAR, VARCHAR, VARCHAR, VARCHAR, INT, INT);
"""


class Migration(migrations.Migration):

    dependencies = [
        ('registrations', '0008_auto_20180323_1228'),
    ]

    operations = [
        migrations.RunSQL(sql, reverse_sql)
    ]
