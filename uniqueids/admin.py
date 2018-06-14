import csv
import os
import io

from django.contrib import admin
from django.conf import settings

from hellomama_registration import utils
from .models import Record, State, Facility, Community, PersonnelUpload
from .tasks import send_personnel_code


class RecordAdmin(admin.ModelAdmin):
    list_display = [
        "id", "identity", "write_to", "created_at", "updated_at"]
    list_filter = ["write_to", "created_at"]
    search_fields = ["identity", "write_to"]
    actions = ["resend_personnel_code"]

    def resend_personnel_code(self, request, queryset):
        created = 0
        for record in queryset.filter(write_to="personnel_code").iterator():
            send_personnel_code.apply_async(kwargs={
                "identity": str(record.identity),
                "personnel_code": record.id})
            created += 1
        if created == 1:
            created_text = "%s Record was" % created
        else:
            created_text = "%s Records were" % created
        self.message_user(request, "%s resent." % created_text)

    resend_personnel_code.short_description = (
        "Send code by SMS (personnel code only)")


class StateAdmin(admin.ModelAdmin):
    list_display = ["name", "created_at", "updated_at"]
    search_fields = ["name"]


class FacilityAdmin(admin.ModelAdmin):
    list_display = ["name", "created_at", "updated_at"]
    search_fields = ["name"]


class CommunityAdmin(admin.ModelAdmin):
    list_display = ["name", "created_at", "updated_at"]
    search_fields = ["name"]


class PersonnelUploadAdmin(admin.ModelAdmin):
    list_display_links = None
    list_display = ["import_type", "created_at", "valid", "error"]
    exclude = ["valid", "error"]

    required_keys = [
        "address_type", "address", "preferred_language",
        "receiver_role", "uniqueid_field_name",
        "uniqueid_field_length", "name", "surname"]

    required_keys_type = {
        PersonnelUpload.CORP_TYPE: ["community"],
        PersonnelUpload.PERSONNEL_TYPE: ["role", "facility_name", "state"]
    }

    def validate_keys(self, record, import_type):
        required = set(
            self.required_keys + self.required_keys_type[import_type])
        missing = required - set(record.keys())

        return missing

    def validate_values(self, record, import_type):
        missing = set()
        required = set(
            self.required_keys + self.required_keys_type[import_type])

        for key, value in record.items():
            if key in required and not value:
                missing.add(key)
            elif key == "address_type" and value != "msisdn":
                missing.add(key)
            elif (key == "preferred_language"
                    and value not in settings.LANGUAGES):
                missing.add(key)
            elif (key == "uniqueid_field_name"
                    and value not in ['personnel_code', 'corp_code']):
                missing.add(key)
            elif (key == "uniqueid_field_length" and not value.isdigit()
                    and value.find('-') == -1):
                missing.add(key)

        return missing

    def validate_address(self, record):
        msisdn = utils.normalize_msisdn(record["address"], '234')

        identities = utils.search_identities(
            "details__addresses__{}".format(record["address_type"]), msisdn)

        for key in identities:
            return True

        if len(msisdn) != 13:
            return True

        return False

    def save_model(self, request, obj, form, change):
        csvfile = io.StringIO(request.FILES['csv_file'].read().decode())
        reader = csv.DictReader(csvfile, delimiter=',')

        obj.valid = True
        obj.error = ''

        states = []
        facilities = []
        communities = []

        if obj.import_type == PersonnelUpload.PERSONNEL_TYPE:
            states = State.objects.values_list('name', flat=True)
            facilities = Facility.objects.values_list('name', flat=True)
        elif obj.import_type == PersonnelUpload.CORP_TYPE:
            communities = Community.objects.values_list('name', flat=True)

        missing_states = set()
        missing_facilities = set()
        missing_communities = set()
        missing_fields = set()
        invalid_values = set()
        existing_address = set()
        errors = []

        rows = list(reader)

        if not rows:
            errors.append("No Rows")
            obj.valid = False
        else:
            for line in rows:
                if ("address" in line and "address_type" in line):
                    if (self.validate_address(line)):
                        existing_address.add(line["address"])

                missing_keys = self.validate_keys(line, obj.import_type)

                if missing_keys:
                    for key in missing_keys:
                        missing_fields.add(key)

                missing_keys = self.validate_values(line, obj.import_type)

                if missing_keys:
                    for key in missing_keys:
                        invalid_values.add(key)

                if obj.import_type == PersonnelUpload.PERSONNEL_TYPE:

                    state = line.get('state')
                    if state and state not in states:
                        missing_states.add(state)

                    facility = line.get('facility_name')
                    if facility and facility not in facilities:
                        missing_facilities.add(facility)

                elif obj.import_type == PersonnelUpload.CORP_TYPE:
                    community = line.get('community')
                    if community and community not in communities:
                        missing_communities.add(community)

            if existing_address:
                errors.append(
                    "Address invalid or already exists: {}".format(
                        ', '.join(sorted(existing_address))))
            if missing_fields:
                errors.append("Missing fields: {}".format(', '.join(
                    sorted(missing_fields))))
            if missing_keys:
                errors.append("Missing or invalid values: {}".format(', '.join(
                    sorted(missing_keys))))
            if missing_states:
                errors.append("Invalid States: {}".format(', '.join(
                    sorted(missing_states))))
            if missing_facilities:
                errors.append("Invalid Facilities: {}".format(', '.join(
                    sorted(missing_facilities))))
            if missing_communities:
                errors.append("Invalid Communities: {}".format(', '.join(
                    sorted(missing_communities))))

        if errors:
            obj.valid = False
            obj.error = ', '.join(errors)
        else:
            for line in rows:
                identity = {
                    "communicate_through": line.get("communicate_through"),
                    "details": {
                        "addresses": {
                            line["address_type"]: {
                                line["address"]: {"default": True}
                            }
                        },
                        "default_addr_type": line["address_type"]
                    }
                }
                for key, value in line.items():
                    if key not in (
                            "address_type", "address", "communicate_through"):
                        identity["details"][key] = value

                utils.create_identity(identity)

        obj.save()

        os.remove('{}/{}'.format(settings.MEDIA_ROOT, obj.csv_file))


admin.site.register(PersonnelUpload, PersonnelUploadAdmin)
admin.site.register(Record, RecordAdmin)
admin.site.register(State, StateAdmin)
admin.site.register(Facility, FacilityAdmin)
admin.site.register(Community, CommunityAdmin)
