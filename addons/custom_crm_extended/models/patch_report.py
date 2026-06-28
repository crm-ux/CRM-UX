from odoo import models

class IrActionsReportPatch(models.Model):
    _inherit = 'ir.actions.report'

    def _prepare_html(self, html, report_model=False):
        bodies, html_ids, header, footer, specific_paperformat_args = super()._prepare_html(html, report_model=report_model)
        if header:
            header = header.replace(
                '</head>',
                '<style>header,div.header,.header{border:none!important;border-top:none!important;border-bottom:none!important;box-shadow:none!important;}</style></head>'
            )
        return bodies, html_ids, header, footer, specific_paperformat_args
