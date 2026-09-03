# -*- coding: utf-8 -*-
from odoo import api, fields, models, _

class CrmCustomSettings(models.TransientModel):
    _name = 'crm.custom.settings'
    _description = 'CRM Custom System Settings'

    name = fields.Char(default='CRM System Settings')

    # Equipment Master Auto-Number Settings
    equipment_id_prefix = fields.Char(string='Equipment ID Prefix', default='EQ')
    equipment_id_auto = fields.Boolean(string='Auto-generate Equipment ID', default=True)

    serial_number_prefix = fields.Char(string='Serial Number Prefix', default='SN')
    serial_number_auto = fields.Boolean(string='Auto-generate Serial Number', default=False)

    def action_open_numbering_master(self):
        return {
            'type': 'ir.actions.act_window',
            'name': _('Numbering Master'),
            'res_model': 'custom.numbering.master',
            'view_mode': 'list,form',
            'target': 'current',
        }
