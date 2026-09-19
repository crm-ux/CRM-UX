# -*- coding: utf-8 -*-
import json
import re
from odoo import http
from odoo.addons.web.controllers.export import Export
from odoo.http import content_disposition, request


class CustomExport(Export):

    @http.route('/web/export/xlsx', type='http', auth="user")
    def web_export_xlsx(self, data):
        response = super().web_export_xlsx(data)

        try:
            params = json.loads(data) if isinstance(data, str) else data
            model = params.get('model')
            
            TARGET_FILENAMES = {
                'equipment.master': 'Equipment Master.xlsx',
                'service.ticket': 'Service Ticket.xlsx',
                'amc.contract': 'AMC Contract.xlsx',
            }

            if model in TARGET_FILENAMES:
                clean_name = TARGET_FILENAMES[model]
                # Replace the header directly
                new_disposition = content_disposition(clean_name)
                response.headers['Content-Disposition'] = new_disposition
                response.headers['content-disposition'] = new_disposition
        except Exception:
            pass

        return response
