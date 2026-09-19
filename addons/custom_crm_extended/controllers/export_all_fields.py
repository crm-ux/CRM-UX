# -*- coding: utf-8 -*-
import json
from odoo import http
from odoo.addons.web.controllers.export import Export
from odoo.http import content_disposition


class CustomExport(Export):

    @http.route('/web/export/xlsx', type='http', auth="user")
    def web_export_xlsx(self, data):
        response = super().web_export_xlsx(data)
        
        # Check if custom_filename was requested (Equipment Master, Service Ticket, AMC Contract)
        try:
            params = json.loads(data)
            custom_filename = params.get('custom_filename')
            if custom_filename:
                response.headers['Content-Disposition'] = content_disposition(custom_filename)
        except Exception:
            pass

        return response
