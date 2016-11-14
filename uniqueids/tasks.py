from celery.task import Task
from celery.utils.log import get_task_logger
from django.conf import settings

from hellomama_registration import utils


logger = get_task_logger(__name__)


class AddUniqueIDToIdentity(Task):
    def run(self, identity, unique_id, write_to, **kwargs):
        """
        identity:     the identity to receive the payload.
        unique_id:    the unique_id to add to the identity
        write_to:     the key to write the unique_id to
        """
        full_identity = utils.get_identity(identity)
        if "details" in full_identity:
            # not a 404
            partial_identity = {
                "details": full_identity["details"]
            }
            # convert to string to enable Django filter lookups
            partial_identity["details"][write_to] = str(unique_id)
            utils.patch_identity(identity, partial_identity)
            return "Identity <%s> now has <%s> of <%s>" % (
                identity, write_to, str(unique_id))
        else:
            return "Identity <%s> not found" % (identity,)

add_unique_id_to_identity = AddUniqueIDToIdentity()


class SendPersonnelCode(Task):
    def run(self, identity, personnel_code):
        text = settings.HCW_PERSONNEL_CODE_TEXT_ENG_NG.format(
            personnel_code=personnel_code)
        address = utils.get_identity_address(identity)
        result = utils.post_message({
            "to_addr": address,
            "content": text,
            "metadata": {},
        })
        return "Sent personnel code to {0}. Result: {1}".format(
            identity, result)

send_personnel_code = SendPersonnelCode()
