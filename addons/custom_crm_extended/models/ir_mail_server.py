# -*- coding: utf-8 -*-
from odoo import models


class IrMailServerPatch(models.Model):
    _inherit = 'ir.mail_server'

    def _smtp_login__(self, connection, smtp_user, smtp_password):
        # RFC 3207: After STARTTLS, client must re-issue EHLO to reload AUTH capabilities
        try:
            connection.ehlo_or_helo_if_needed()
            connection.ehlo()
        except Exception:
            pass
        return super()._smtp_login__(connection, smtp_user, smtp_password)
