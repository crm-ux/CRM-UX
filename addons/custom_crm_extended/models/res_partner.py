# -*- coding: utf-8 -*-
from odoo import fields, models

class ResPartner(models.Model):
    _inherit = 'res.partner'

    x_site_name = fields.Char(string='Site Name')
    x_building = fields.Char(string='Building')
    x_floor = fields.Char(string='Floor')
    x_department = fields.Char(string='Department')
    x_room_number = fields.Char(string='Room Number')
