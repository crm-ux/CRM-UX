from odoo import models, fields

class SaleTermsTemplate(models.Model):
    _name = 'sale.terms.template'
    _description = 'Terms & Conditions Template'
    _order = 'sequence, id'

    name = fields.Char(string='Title', required=True)
    sequence = fields.Integer(string='Sequence', default=10)
    content = fields.Text(string='Content', required=True)
    active = fields.Boolean(string='Active', default=True)
