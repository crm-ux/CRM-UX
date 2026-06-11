from odoo import models

class SaleOrderPatch(models.Model):
    _inherit = 'sale.order'
    _check_company_auto = False
