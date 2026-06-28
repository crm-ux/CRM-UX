from odoo import models

class IrActionsReportPatch(models.Model):
    _inherit = 'ir.actions.report'

    def _run_wkhtmltopdf(self, bodies, report_ref=False, header=None, footer=None, landscape=False, specific_paperformat_args=None, set_viewport_size=False):
        if header:
            header = header.replace(
                '</head>',
                '<style>header,.header,div.header{border:none !important;border-top:none !important;border-bottom:none !important;box-shadow:none !important;}</style></head>'
            )
        return super()._run_wkhtmltopdf(
            bodies, report_ref=report_ref, header=header, footer=footer,
            landscape=landscape, specific_paperformat_args=specific_paperformat_args,
            set_viewport_size=set_viewport_size
        )
