from odoo import models, fields


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    x_make = fields.Char(string='Make / Brand')
