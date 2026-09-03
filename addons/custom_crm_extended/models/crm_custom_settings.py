# -*- coding: utf-8 -*-
from odoo import api, fields, models, _

class CrmCustomSettings(models.TransientModel):
    _name = 'crm.custom.settings'
    _description = 'CRM Custom System Settings'

    name = fields.Char(default='CRM System Settings')

    # --- 1. Equipment ID Settings ---
    equipment_id_auto = fields.Boolean(string='Auto-generate Equipment ID', default=True)
    equipment_id_prefix = fields.Char(string='Prefix', default='EQ-')
    equipment_id_padding = fields.Integer(string='Digits (Padding)', default=4)
    equipment_id_next = fields.Integer(string='Next Number', default=1)
    equipment_id_suffix = fields.Char(string='Suffix', default='')
    equipment_id_preview = fields.Char(string='Preview', compute='_compute_equipment_id_preview')

    # --- 2. Serial Number Settings ---
    serial_number_auto = fields.Boolean(string='Auto-generate Serial Number', default=True)
    serial_number_prefix = fields.Char(string='Prefix', default='SN-')
    serial_number_padding = fields.Integer(string='Digits (Padding)', default=4)
    serial_number_next = fields.Integer(string='Next Number', default=1)
    serial_number_suffix = fields.Char(string='Suffix', default='')
    serial_number_preview = fields.Char(string='Preview', compute='_compute_serial_number_preview')

    @api.depends('equipment_id_prefix', 'equipment_id_padding', 'equipment_id_next', 'equipment_id_suffix')
    def _compute_equipment_id_preview(self):
        for rec in self:
            pad = max(1, rec.equipment_id_padding or 4)
            num_str = str(rec.equipment_id_next or 1).zfill(pad)
            prefix = rec.equipment_id_prefix or ''
            suffix = rec.equipment_id_suffix or ''
            rec.equipment_id_preview = f"{prefix}{num_str}{suffix}"

    @api.depends('serial_number_prefix', 'serial_number_padding', 'serial_number_next', 'serial_number_suffix')
    def _compute_serial_number_preview(self):
        for rec in self:
            pad = max(1, rec.serial_number_padding or 4)
            num_str = str(rec.serial_number_next or 1).zfill(pad)
            prefix = rec.serial_number_prefix or ''
            suffix = rec.serial_number_suffix or ''
            rec.serial_number_preview = f"{prefix}{num_str}{suffix}"

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        # Load saved settings from ir.config_parameter
        ICP = self.env['ir.config_parameter'].sudo()
        res['equipment_id_auto'] = ICP.get_param('crm.equipment_id_auto', 'True') == 'True'
        res['equipment_id_prefix'] = ICP.get_param('crm.equipment_id_prefix', 'EQ-')
        res['equipment_id_padding'] = int(ICP.get_param('crm.equipment_id_padding', 4))
        res['equipment_id_next'] = int(ICP.get_param('crm.equipment_id_next', 1))
        res['equipment_id_suffix'] = ICP.get_param('crm.equipment_id_suffix', '')

        res['serial_number_auto'] = ICP.get_param('crm.serial_number_auto', 'True') == 'True'
        res['serial_number_prefix'] = ICP.get_param('crm.serial_number_prefix', 'SN-')
        res['serial_number_padding'] = int(ICP.get_param('crm.serial_number_padding', 4))
        res['serial_number_next'] = int(ICP.get_param('crm.serial_number_next', 1))
        res['serial_number_suffix'] = ICP.get_param('crm.serial_number_suffix', '')
        return res

    def action_save_settings(self):
        self.ensure_one()
        ICP = self.env['ir.config_parameter'].sudo()
        ICP.set_param('crm.equipment_id_auto', str(self.equipment_id_auto))
        ICP.set_param('crm.equipment_id_prefix', self.equipment_id_prefix or '')
        ICP.set_param('crm.equipment_id_padding', str(self.equipment_id_padding or 4))
        ICP.set_param('crm.equipment_id_next', str(self.equipment_id_next or 1))
        ICP.set_param('crm.equipment_id_suffix', self.equipment_id_suffix or '')

        ICP.set_param('crm.serial_number_auto', str(self.serial_number_auto))
        ICP.set_param('crm.serial_number_prefix', self.serial_number_prefix or '')
        ICP.set_param('crm.serial_number_padding', str(self.serial_number_padding or 4))
        ICP.set_param('crm.serial_number_next', str(self.serial_number_next or 1))
        ICP.set_param('crm.serial_number_suffix', self.serial_number_suffix or '')
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Settings Saved'),
                'message': _('Auto-numbering settings updated successfully!'),
                'type': 'success',
                'sticky': False,
            }
        }
