# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

class EquipmentCategory(models.Model):
    _name = 'equipment.category'
    _description = 'Equipment Category'

    name = fields.Char(string='Category Name', required=True)


class EquipmentMaster(models.Model):
    _name = 'equipment.master'
    _description = 'Equipment Master for Service Tickets'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    _sql_constraints = [
        ('equipment_id_uniq', 'unique(equipment_id)', 'The Equipment ID must be unique! This ID is already assigned to another equipment.'),
        ('serial_number_uniq', 'unique(serial_number)', 'The Serial Number must be unique! This Serial Number already exists in the system.'),
    ]

    # Step 1: Equipment Info
    equipment_id  = fields.Char(string='Equipment ID', required=True, tracking=True)
    name = fields.Many2one('product.template', string='Equipment Name', tracking=True)
    category_id = fields.Char(string='Equipment Category', tracking=True)
    manufacturer = fields.Char(string='Manufacturer', tracking=True)
    model_number = fields.Char(string='Model Number', tracking=True)
    serial_number = fields.Char(string='Serial Number', tracking=True)
    part_number = fields.Char(string='Part Number', tracking=True)
    child_part_no = fields.Char(string='Child Part No', tracking=True)
    invoice_number = fields.Char(string='Invoice No', tracking=True)
    invoice_date = fields.Date(string='Invoice Date', tracking=True)
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
    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.company, tracking=True)


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

@api.onchange('partner_id')
def _onchange_partner_id(self):
    if self.partner_id:
        p = self.partner_id
        if p.is_company:
            primary_contact = p.child_ids.filtered(lambda c: c.type == 'contact')[:1]
            if primary_contact:
                self.contact_person = primary_contact.name or ""
                self.contact_number = primary_contact.phone or getattr(primary_contact, 'mobile', False) or p.phone or getattr(p, 'mobile', False) or ""
                self.email = primary_contact.email or p.email or ""
            else:
                self.contact_person = p.name or ""
                self.contact_number = p.phone or getattr(p, 'mobile', False) or ""
                self.email = p.email or ""
        else:
            self.contact_person = p.name or ""
            self.contact_number = p.phone or getattr(p, 'mobile', False) or ""
            self.email = p.email or ""

        addr_parts = [p.street, p.street2, p.city, p.state_id.name if p.state_id else False, p.country_id.name if p.country_id else False, p.zip]
        self.address = ", ".join([str(a) for a in addr_parts if a])

        self.site_name = getattr(p, 'x_site_name', False) or ""
        self.building = getattr(p, 'x_building', False) or ""
        self.floor = getattr(p, 'x_floor', False) or ""
        self.department = getattr(p, 'x_department', False) or p.function or ""
        self.room_number = getattr(p, 'x_room_number', False) or ""

    @api.depends('name', 'serial_number', 'equipment_id')
    def _compute_display_name(self):
        for rec in self:
            eq_name = rec.name.display_name if rec.name else (rec.equipment_id or '')
            if rec.serial_number:
                sn = str(rec.serial_number).strip()
                last6 = sn[-6:] if len(sn) >= 6 else sn
                rec.display_name = f"{eq_name} ...{last6}"
            else:
                rec.display_name = eq_name

    @api.model
    def name_search(self, name='', domain=None, operator='ilike', limit=100):
        domain = list(domain or [])
        if name:
            domain += ['|', '|', ('name.name', operator, name), ('serial_number', operator, name), ('equipment_id', operator, name)]
        records = self.search(domain, limit=limit)
        return [(r.id, r.display_name) for r in records]

    @api.constrains('equipment_id')
    def _check_unique_equipment_id(self):
        for rec in self:
            if rec.equipment_id:
                duplicate = self.search([
                    ('equipment_id', '=', rec.equipment_id.strip()),
                    ('id', '!=', rec.id)
                ], limit=1)
                if duplicate:
                    raise ValidationError(_("Equipment ID '%s' already exists! Please use a unique Equipment ID.") % rec.equipment_id)

    @api.constrains('serial_number')
    def _check_unique_serial_number(self):
        for rec in self:
            if rec.serial_number:
                duplicate = self.search([
                    ('serial_number', '=', rec.serial_number.strip()),
                    ('id', '!=', rec.id)
                ], limit=1)
                if duplicate:
                    raise ValidationError(_("Serial Number '%s' already exists! Each equipment must have a unique Serial Number.") % rec.serial_number)

    @api.onchange('name')
    def _onchange_name(self):
        if self.name:
            self.category_id = self.name.categ_id.display_name if self.name.categ_id else ''
            self.manufacturer = getattr(self.name, 'x_make', '') or ''
            self.part_number = getattr(self.name, 'default_code', '') or ''
        else:
            self.category_id = ''
            self.manufacturer = ''
            self.part_number = ''


    def action_create_service_ticket(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Create Service Ticket'),
            'res_model': 'crm.lead',
            'view_mode': 'form',
            'target': 'current',
            'context': {
                'default_name': f"Service Ticket - {self.name.name if self.name else ''}",
                'default_partner_id': self.partner_id.id if self.partner_id else False,
            }
        }
