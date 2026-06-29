from odoo import models
import tempfile, os

class IrActionsReportPatch(models.Model):
    _inherit = 'ir.actions.report'

    def _run_wkhtmltopdf(self, bodies, report_ref=False, header=None, footer=None,
                          landscape=False, specific_paperformat_args=None, set_viewport_size=False):
        # Get company logo
        logo_html = ''
        try:
            company = self.env.company
            if company.logo_web:
                logo_b64 = company.logo_web.decode('utf-8') if isinstance(company.logo_web, bytes) else company.logo_web
                logo_html = '<img src="data:image/png;base64,%s" style="max-height:80px;max-width:200px;object-fit:contain;float:right;"/>' % logo_b64
        except Exception:
            pass

        # Build custom header HTML
        custom_header = '''<!DOCTYPE html>
<html><head><meta charset="utf-8"/>
<style>
body{margin:0;padding:2mm 5mm 1mm 5mm;}
header,div.header,.header{border:none!important;border-top:none!important;border-bottom:none!important;box-shadow:none!important;}
</style>
</head>
<body>
<div style="width:100%;overflow:hidden;">%s</div>
</body></html>''' % logo_html

        # Write custom header to temp file
        fd, header_path = tempfile.mkstemp(suffix='.html', prefix='report.logo.header.')
        try:
            with os.fdopen(fd, 'w', encoding='utf-8') as f:
                f.write(custom_header)

            # Override specific_paperformat_args to use our header
            if specific_paperformat_args is None:
                specific_paperformat_args = {}
            specific_paperformat_args['data-report-header-spacing'] = '15'

            # Call original with our header file replacing header param
            result = super()._run_wkhtmltopdf(
                bodies, report_ref=report_ref,
                header=custom_header,
                footer=footer,
                landscape=landscape,
                specific_paperformat_args=specific_paperformat_args,
                set_viewport_size=set_viewport_size
            )
        finally:
            try:
                os.unlink(header_path)
            except Exception:
                pass

        return result

    def _prepare_html(self, html, report_model=False):
        bodies, html_ids, header, footer, specific_paperformat_args = super()._prepare_html(html, report_model=report_model)
        fix_css = '<style>header,div.header,.header{border:none!important;border-top:none!important;border-bottom:none!important;box-shadow:none!important;}a,a:link,a:visited{text-decoration:none!important;color:#000!important;}</style>'
        if header:
            header = header.replace('</head>', fix_css + '</head>')
        if bodies:
            bodies = [b.replace('</head>', fix_css + '</head>') if '</head>' in b else b for b in bodies]
        return bodies, html_ids, header, footer, specific_paperformat_args
