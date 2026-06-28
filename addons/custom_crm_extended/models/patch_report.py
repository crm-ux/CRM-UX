from odoo import models

class IrActionsReportPatch(models.Model):
    _inherit = 'ir.actions.report'

    def _prepare_html(self, html, report_model=False):
        bodies, html_ids, header, footer, specific_paperformat_args = super()._prepare_html(html, report_model=report_model)
        fix_css = '<style>a,a:link,a:visited,a:hover,a:active{text-decoration:none!important;border:none!important;border-bottom:none!important;color:#000!important;}header,div.header,.header{border:none!important;border-top:none!important;border-bottom:none!important;box-shadow:none!important;}*{text-decoration:none!important;}</style>'
        if header:
            header = header.replace('</head>', fix_css + '</head>')
        if bodies:
            bodies = [b.replace('</head>', fix_css + '</head>') if '</head>' in b else b for b in bodies]
        return bodies, html_ids, header, footer, specific_paperformat_args
