# familyconnect-registration
FamilyConnect Registration

## Registration validity requirements
All registrations should have the following information:
- contact (identity-store id)
- registered_by (identity-store id)
- language (this will also be stored to the identity)
- message_type (this will also be stored to the identity)

Specific stages of pregnancy will require additional information:
- prebirth: last_period_date, message_receiver
- postbirth: baby_dob, message_receiver
- loss: loss_reason

Health worker registrations require additional information:
(hoh = head of household)
- hoh_name
- hoh_surname
- mama_name
- mama_surname
- mama_id_type
- mama_id_no OR mama_dob
- hiv messages?

Registrations that show a pregnancy period shorter than 1 week or longer than 42 weeks will be rejected server side.
