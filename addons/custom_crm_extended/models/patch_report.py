from odoo import models

class IrActionsReportPatch(models.Model):
    _inherit = 'ir.actions.report'

    def _prepare_html(self, html, report_model=False):
        bodies, html_ids, header, footer, specific_paperformat_args = super()._prepare_html(html, report_model=report_model)
        if header:
            header = header.replace(
                '</head>',
                '<style>header,div.header,.header{border:none!important;border-top:none!important;border-bottom:none!important;box-shadow:none!important;outline:none!important;}a,a:link,a:visited,a:hover{text-decoration:none!important;border:none!important;color:#000!important;}*{border-top-color:#fff!important;border-bottom-color:#fff!important;}</style></head>'
            )
        return bodies, html_ids, header, footer, specific_paperformat_args
