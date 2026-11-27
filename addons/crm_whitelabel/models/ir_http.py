from odoo import models
from odoo.http import request


class IrHttp(models.AbstractModel):
    _inherit = 'ir.http'

    @classmethod
    def _authenticate_explicit(cls, auth):
        if request and getattr(request, 'session', None) and isinstance(request.session.uid, bool):
            request.session.uid = None
            request.session.login = None
        return super()._authenticate_explicit(auth)
