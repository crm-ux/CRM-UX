from odoo import models
import base64

class IrActionsReportPatch(models.Model):
    _inherit = 'ir.actions.report'

    def _prepare_html(self, html, report_model=False):
        bodies, html_ids, header, footer, specific_paperformat_args = super()._prepare_html(html, report_model=report_model)
        
        fix_css = '<style>header,div.header,.header{border:none!important;border-top:none!important;border-bottom:none!important;box-shadow:none!important;}a,a:link,a:visited{text-decoration:none!important;color:#000!important;}</style>'
        
        # Get company logo
        logo_html = ''
        try:
            company = self.env.company
            if company.logo_web:
                logo_b64 = company.logo_web.decode('utf-8') if isinstance(company.logo_web, bytes) else company.logo_web
                logo_html = '<div style="text-align:right;padding:2mm 0 1mm 0;"><img src="data:image/png;base64,%s" style="max-height:120px;max-width:280px;object-fit:contain;"/></div>' % logo_b64
        except Exception:
            pass

        if header:
            # Inject CSS and logo into header
            header = header.replace('</head>', fix_css + '</head>')
            header = header.replace('<body>', '<body>' + logo_html)
        if bodies:
            bodies = [b.replace('</head>', fix_css + '</head>') if '</head>' in b else b for b in bodies]
        
        return bodies, html_ids, header, footer, specific_paperformat_args
