from odoo import models

class IrActionsReportPatch(models.Model):
    _inherit = 'ir.actions.report'

    def _run_wkhtmltopdf(self, bodies, report_ref=False, header=None, footer=None,
                          landscape=False, specific_paperformat_args=None, set_viewport_size=False):
        logo_html = ''
        try:
            company = self.env.company
            if company.logo_web:
                logo_b64 = company.logo_web.decode('utf-8') if isinstance(company.logo_web, bytes) else company.logo_web
                logo_html = '<img src="data:image/png;base64,' + logo_b64 + '" style="height:80px;max-width:220px;object-fit:contain;object-position:right;display:block;margin-left:auto;"/>'
        except Exception:
            pass

        custom_header = (
            '<!DOCTYPE html><html><head><meta charset="utf-8"/>'
            '<style>'
            'body{margin:0;padding:3mm 8mm 2mm 8mm;}'
            'header,div.header,.header{border:none!important;border-top:none!important;border-bottom:none!important;box-shadow:none!important;}'
            '</style></head><body>'
            '<div style="width:100%;text-align:right;">' + logo_html + '</div>'
            '</body></html>'
        )

        return super()._run_wkhtmltopdf(
            bodies, report_ref=report_ref,
            header=custom_header,
            footer=footer,
            landscape=landscape,
            specific_paperformat_args=specific_paperformat_args,
            set_viewport_size=set_viewport_size
        )

    def _prepare_html(self, html, report_model=False):
        bodies, html_ids, header, footer, specific_paperformat_args = super()._prepare_html(html, report_model=report_model)
        fix_css = '<style>header,div.header,.header{border:none!important;border-top:none!important;border-bottom:none!important;box-shadow:none!important;}a,a:link,a:visited{text-decoration:none!important;color:#000!important;}</style>'
        if header:
            header = header.replace('</head>', fix_css + '</head>')
        if bodies:
            bodies = [b.replace('</head>', fix_css + '</head>') if '</head>' in b else b for b in bodies]
        return bodies, html_ids, header, footer, specific_paperformat_args
