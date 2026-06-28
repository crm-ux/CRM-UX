from odoo import models

class IrActionsReportPatch(models.Model):
    _inherit = 'ir.actions.report'

    def _prepare_html(self, html, report_model=False):
        result = super()._prepare_html(html, report_model=report_model)
        # Remove red border line from header
        if result and result.get('header'):
            result['header'] = result['header'].replace(
                '</head>',
                '<style>header,div.header,.header{border:none!important;border-top:none!important;border-bottom:none!important;box-shadow:none!important;outline:none!important;}*{border-top-color:transparent!important;}</style></head>'
            )
        return result
