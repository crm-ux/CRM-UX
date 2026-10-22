# -*- coding: utf-8 -*-
from odoo import models, fields, api

class SaleTermsCondition(models.Model):
    _name = 'sale.terms.condition'
    _description = 'Terms and Conditions Master'
    _order = 'sequence, id'

    name = fields.Char(string='Title', required=True)
    sequence = fields.Integer(string='Sequence', default=10)
    company_id = fields.Many2one('res.company', string='Company', help='Leave empty to apply to all companies.')
    content = fields.Text(string='Content', required=True)
    active = fields.Boolean(default=True)
