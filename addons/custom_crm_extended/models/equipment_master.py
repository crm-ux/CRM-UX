# -*- coding: utf-8 -*-
from odoo import api, fields, models, _

class EquipmentCategory(models.Model):
    _name = 'equipment.category'
    _description = 'Equipment Category'

    name = fields.Char(string='Category Name', required=True)


class EquipmentMaster(models.Model):
    _name = 'equipment.master'
    _description = 'Equipment Master for Service Tickets'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    # Step 1: Equipment Info
    # equipment_id = fields.Char(string='Equipment ID', required=True, copy=False, default=lambda self: _('New'), tracking=True)
    equipment_id  = fields.Char(string='Equipment ID', required=True, tracking=True)
    name = fields.Char(string='Equipment Name', tracking=True)
    category_id = fields.Char(string='Equipment Category', tracking=True)
    manufacturer = fields.Char(string='Manufacturer', tracking=True)
    model_number = fields.Char(string='Model Number', tracking=True)
    serial_number = fields.Char(string='Serial Number', tracking=True)
    part_number = fields.Char(string='Part Number', tracking=True)
    child_part_no = fields.Char(string='Child Part No', tracking=True)
    equipment_status = fields.Selection([
        ('active', 'Active'),
        ('inactive', 'Inactive'),
        ('under_repair', 'Under Repair'),
    ], string='Equipment Status', default='active', tracking=True)
    criticality = fields.Selection([
        ('high', 'High'),
        ('medium', 'Medium'),
        ('low', 'Low'),
    ], string='Criticality', default='medium', tracking=True)

    # Step 2: Location & Contact
    partner_id = fields.Many2one('res.partner', string='Customer Name', tracking=True)
    site_name = fields.Char(string='Site Name', tracking=True)
    building = fields.Char(string='Building', tracking=True)
    floor = fields.Char(string='Floor', tracking=True)
    department = fields.Char(string='Department', tracking=True)
    room_number = fields.Char(string='Room Number', tracking=True)
    address = fields.Text(string='Address')
    contact_person = fields.Char(string='Contact Person', tracking=True)
    contact_number = fields.Char(string='Contact Number', tracking=True)
    email = fields.Char(string='Email', tracking=True)

    # Step 3: Maintenance & Contract
    installation_date = fields.Date(string='Installation Date')
    warranty_start_date = fields.Date(string='Warranty Start Date')
    warranty_end_date = fields.Date(string='Warranty End Date')
    service_contract = fields.Selection([
        ('amc', 'AMC'),
        ('cmc', 'CMC'),
        ('warranty', 'Warranty'),
        ('none', 'None'),
    ], string='Service Contract', default='amc', tracking=True)
    last_preventive_maintenance = fields.Date(string='Last PM Date')
    next_preventive_maintenance = fields.Date(string='Next PM Date')
    last_breakdown_date = fields.Date(string='Last Breakdown Date')
    calibration_due_date = fields.Date(string='Calibration Due Date')
    running_status = fields.Selection([
        ('running', 'Running'),
        ('stopped', 'Stopped'),
    ], string='Current Running Status', default='running', tracking=True)

    # Step 4: Specs & Remarks
    firmware_version = fields.Char(string='Software/Firmware Version')
    accessories = fields.Text(string='Accessories')
    remarks = fields.Text(string='Remarks')

    @api.model_create_multi
    def create(self, vals_list):
        # for vals in vals_list:
        #     if not vals.get('equipment_id') or vals['equipment_id'] == _('New'):
        #         vals['equipment_id'] = self.env['ir.sequence'].next_by_code('equipment.master') or _('New')
        return super().create(vals_list)
