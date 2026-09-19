# -*- coding: utf-8 -*-
import io
from lxml import etree
from odoo import http, _
from odoo.http import request
try:
    import xlsxwriter
except ImportError:
    xlsxwriter = None


class ExportAllFieldsController(http.Controller):

    @http.route('/custom_crm/export_all_fields', type='http', auth='user')
    def export_all_fields(self, model, domain='[]', **kwargs):
        if not xlsxwriter:
            return request.not_found()

        Model = request.env[model].sudo()
        domain = eval(domain) if domain else []
        records = Model.search(domain)

        # 1. DYNAMICALLY read all fields directly from the Form View architecture!
        form_view = Model.get_view(view_type='form')
        doc = etree.fromstring(form_view['arch'])

        # Skip technical / non-data fields
        IGNORE_FIELDS = {'message_follower_ids', 'activity_ids', 'message_ids', 'customer_signature', 'engineer_signature'}

        fields_to_export = []
        seen_fields = set()

        for field_node in doc.xpath('//field'):
            fname = field_node.get('name')
            if not fname or fname in seen_fields or fname in IGNORE_FIELDS:
                continue

            field_def = Model._fields.get(fname)
            if not field_def:
                continue

            # Don't export binary attachments/signatures or One2many tables directly as text
            if field_def.type in ('binary', 'one2many'):
                continue

            # Get field label: use form view string if overridden, otherwise model string
            flabel = field_node.get('string') or field_def.string or fname
            fields_to_export.append((fname, flabel, field_def.type))
            seen_fields.add(fname)

        # 2. Build Excel Spreadsheet
        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        worksheet = workbook.add_worksheet('Export')

        header_format = workbook.add_format({
            'bold': True,
            'bg_color': '#1A3D6E',
            'font_color': '#FFFFFF',
            'border': 1
        })
        cell_format = workbook.add_format({'border': 1})

        # Headers
        for col_idx, (fname, flabel, ftype) in enumerate(fields_to_export):
            worksheet.write(0, col_idx, flabel, header_format)
            worksheet.set_column(col_idx, col_idx, max(len(flabel) + 3, 16))

        # Data Rows
        for row_idx, rec in enumerate(records, start=1):
            for col_idx, (fname, flabel, ftype) in enumerate(fields_to_export):
                val = getattr(rec, fname, '')
                if ftype == 'many2one':
                    val_str = val.display_name if val else ''
                elif ftype == 'selection':
                    val_str = dict(rec._fields[fname].selection).get(val, val) if val else ''
                elif ftype == 'boolean':
                    val_str = 'Yes' if val else 'No'
                elif val is None or val is False:
                    val_str = ''
                else:
                    val_str = str(val)

                worksheet.write(row_idx, col_idx, val_str, cell_format)

        workbook.close()
        output.seek(0)

        filename = f"{model.replace('.', '_')}_all_fields.xlsx"
        return request.make_response(
            output.getvalue(),
            headers=[
                ('Content-Type', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'),
                ('Content-Disposition', f'attachment; filename="{filename}"'),
            ]
        )
