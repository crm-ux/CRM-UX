# -*- coding: utf-8 -*-
import json
import re
from odoo import http, _
from odoo.addons.web.controllers.export import Export
from odoo.http import content_disposition, request
from odoo.exceptions import UserError, AccessError

class CustomExport(Export):
    def _check_export_permission(self):
        user = request.env.user
        if user.id in (2, 10, 11) or user.has_group('base.group_system'):
            return True
        perm = user.perm_export or (user.crm_job_id.perm_export if user.crm_job_id else 'none')
        if perm != 'export':
            raise UserError(_("Access Denied: You do not have permission to export Excel data."))
        return True

    @http.route('/web/export/xlsx', type='http', auth="user")
    def web_export_xlsx(self, data):
        self._check_export_permission()
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

    @http.route('/web/export/csv', type='http', auth="user")
    def web_export_csv(self, data):
        self._check_export_permission()
        return super().web_export_csv(data)
