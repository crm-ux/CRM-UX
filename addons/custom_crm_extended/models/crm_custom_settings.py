# -*- coding: utf-8 -*-
from odoo import api, fields, models, _

class CrmCustomSettings(models.TransientModel):
    _name = 'crm.custom.settings'
    _description = 'CRM Custom System Settings'

    name = fields.Char(default='CRM System Settings')

    def action_open_numbering_master(self):
        return {
            'type': 'ir.actions.act_window',
            'name': _('Numbering Master'),
            'res_model': 'custom.numbering.master',
            'view_mode': 'list,form',
            'target': 'current',
        }
