# -*- coding: utf-8 -*-
from odoo import models, fields, api, _

class ServiceTicket(models.Model):
    _name = 'service.ticket'
    _description = 'Service Ticket'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'id desc'

    name = fields.Char(string='Ticket Number', required=True, copy=False, readonly=True, default=lambda self: _('New'))
    ticket_datetime = fields.Datetime(string='Ticket Date & Time', default=fields.Datetime.now, required=True, tracking=True)
    
    # Equipment & Customer Linkage
    equipment_id = fields.Many2one('equipment.master', string='Equipment', tracking=True)
    partner_id = fields.Many2one('res.partner', string='Customer Name', required=True, tracking=True)
    site_name = fields.Char(string='Site Name')
    contact_person = fields.Char(string='Contact Person')
    contact_number = fields.Char(string='Contact Number')
    email = fields.Char(string='Customer Email')
    
    # Equipment Specs (Auto-filled from equipment)
    model_number = fields.Char(string='Model Number')
    serial_number = fields.Char(string='Serial Number')
    part_number = fields.Char(string='Part Number')
    
    # Complaint Details
    complaint_type = fields.Selection([
        ('breakdown', 'Breakdown'),
        ('amc', 'AMC'),
        ('pm', 'PM'),
        ('free_call', 'Free Call')
    ], string='Complaint Type', default='breakdown', required=True, tracking=True)
    complaint_description = fields.Text(string='Complaint Description', required=True, tracking=True)
    priority = fields.Selection([
        ('high', 'High'),
        ('medium', 'Medium'),
        ('low', 'Low')
    ], string='Priority', default='medium', required=True, tracking=True)
    
    # Assignment & Schedule
    engineer_id = fields.Many2one('res.users', string='Assigned Engineer', tracking=True)
    engineer_contact = fields.Char(string='Engineer Contact')
    engineer_email = fields.Char(string='Engineer Email')
    visit_date = fields.Date(string='Visit Date', tracking=True)
    
    # Resolution & Sign-off
    root_cause = fields.Text(string='Root Cause')
    corrective_action = fields.Text(string='Corrective Action')
    spare_parts_used = fields.Char(string='Spare Parts Used')
    service_start_time = fields.Char(string='Service Start Time', placeholder='e.g. 10:45 AM')
    service_end_time = fields.Char(string='Service End Time', placeholder='e.g. 01:30 PM')
    customer_signature = fields.Binary(string='Customer Signature')
    engineer_signature = fields.Binary(string='Engineer Signature')
    
    # Status
    ticket_status = fields.Selection([
        ('open', 'Open'),
        ('ongoing', 'On Going'),
        ('closed', 'Closed')
    ], string='Ticket Status', default='open', required=True, tracking=True)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code('service.ticket.seq') or _('New')
        return super(ServiceTicket, self).create(vals_list)

    @api.onchange('partner_id')
    def _onchange_partner_id(self):
        if self.partner_id:
            if self.equipment_id and self.equipment_id.partner_id != self.partner_id:
                self.equipment_id = False
            return {'domain': {'equipment_id': [('partner_id', '=', self.partner_id.id)]}}
        return {'domain': {'equipment_id': []}}

    @api.onchange('equipment_id')
    def _onchange_equipment_id(self):
        if self.equipment_id:
            eq = self.equipment_id
            self.partner_id = eq.partner_id
            self.site_name = eq.site_name
            self.contact_person = eq.contact_person
            self.contact_number = eq.contact_number
            self.email = eq.email
            self.model_number = eq.model_number
            self.serial_number = eq.serial_number
            self.part_number = eq.part_number

    @api.onchange('engineer_id')
    def _onchange_engineer_id(self):
        if self.engineer_id:
            self.engineer_contact = self.engineer_id.phone or self.engineer_id.mobile
            self.engineer_email = self.engineer_id.email
