# -*- coding: utf-8 -*-
import re
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

class ServiceTicket(models.Model):
    _name = 'service.ticket'
    _description = 'Service Ticket'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _rec_name = 'ticket_id'
    _order = 'id desc'

    name = fields.Char(string='Ticket Number', required=True, copy=False, readonly=True, default=lambda self: _('New'))
    ticket_id = fields.Char(string='Ticket ID', required=True, copy=False, tracking=True)
    ticket_datetime = fields.Datetime(string='Ticket Date & Time', default=fields.Datetime.now, required=True, tracking=True)
    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.company, tracking=True)

    # Equipment & Customer Linkage
    equipment_id = fields.Many2one('equipment.master', string='Equipment', tracking=True)
    partner_id = fields.Many2one('res.partner', string='Customer Name')
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
    ], string='Complaint Type', default='breakdown', tracking=True)
    complaint_description = fields.Text(string='Complaint Description', tracking=True)
    priority = fields.Selection([
        ('high', 'High'),
        ('medium', 'Medium'),
        ('low', 'Low')
    ], string='Priority', default='medium', tracking=True)


    # Assignment & Schedule
    engineer_id = fields.Many2one('res.users', string='Assigned Engineer', tracking=True)
    engineer_contact = fields.Char(string='Engineer Contact')
    engineer_email = fields.Char(string='Engineer Email')
    visit_date = fields.Date(string='Visit Date', tracking=True)
    
    # Resolution & Sign-off
    root_cause = fields.Text(string='Root Cause')
    corrective_action = fields.Text(string='Corrective Action')
    spare_parts_used = fields.Char(string='Spare Parts Used')
    service_start_time = fields.Datetime(string='Service Start Time')
    service_end_time = fields.Datetime(string='Service End Time')
    customer_signature = fields.Binary(string='Customer Signature')
    engineer_signature = fields.Binary(string='Engineer Signature')
    
    # Status
        # Status (5 Stages)
    ticket_status = fields.Selection([
        ('new', 'New'),
        ('contacted', 'Contacted'),
        ('ongoing', 'Ongoing'),
        ('pending', 'Pending'),
        ('closed', 'Close')
    ], string='Ticket Status', default='new', tracking=True)

    stage_visible = fields.Char(compute='_compute_stage_visible', store=False)
    @api.depends('ticket_status')
    def _compute_stage_visible(self):
        for rec in self:
            rec.stage_visible = rec.ticket_status or 'new'

    def action_move_to_contacted(self):
        self.write({'ticket_status': 'contacted'})

    def action_move_to_ongoing(self):
        self.write({'ticket_status': 'ongoing'})

    def action_move_to_pending(self):
        self.write({'ticket_status': 'pending'})

    def action_move_to_closed(self):
        self.write({'ticket_status': 'closed'})

    def action_reopen(self):
        self.write({'ticket_status': 'new'})

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code('service.ticket.seq') or _('New')
        return super(ServiceTicket, self).create(vals_list)

    def copy(self, default=None):
        default = dict(default or {})
        if 'ticket_id' not in default:
            orig_id = self.ticket_id or ''
            match = re.search(r'^(.*?)(\d+)$', orig_id)
            if match:
                prefix = match.group(1)
                num_str = match.group(2)
                num_len = len(num_str)
                next_num = int(num_str) + 1
                new_id = f"{prefix}{str(next_num).zfill(num_len)}"
                while self.search_count([('ticket_id', '=', new_id)]):
                    next_num += 1
                    new_id = f"{prefix}{str(next_num).zfill(num_len)}"
                default['ticket_id'] = new_id
            else:
                default['ticket_id'] = f"{orig_id}-1"
        if 'name' not in default:
            default['name'] = default['ticket_id']
        return super(ServiceTicket, self).copy(default)


    @api.onchange('partner_id')
    def _onchange_partner_id(self):
        if self.partner_id:
            equipments = self.env['equipment.master'].search([('partner_id', '=', self.partner_id.id)])
            if len(equipments) == 1:
                eq = equipments[0]
                self.equipment_id = eq
                self.site_name = eq.site_name
                self.contact_person = eq.contact_person
                self.contact_number = eq.contact_number
                self.email = eq.email
                self.model_number = eq.model_number
                self.serial_number = eq.serial_number
                self.part_number = eq.part_number
            else:
                if self.equipment_id and self.equipment_id.partner_id != self.partner_id:
                    self.equipment_id = False
                    self.model_number = False
                    self.serial_number = False
                    self.part_number = False
                self.contact_person = self.partner_id.name
                self.contact_number = getattr(self.partner_id, 'phone', False) or getattr(self.partner_id, 'mobile', False) or False
                self.email = getattr(self.partner_id, 'email', False) or False
                self.site_name = getattr(self.partner_id, 'x_site_name', False) or False
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
            partner = self.engineer_id.partner_id
            phone = getattr(self.engineer_id, 'phone', False) or (getattr(partner, 'phone', False) if partner else False) or (getattr(partner, 'mobile', False) if partner else False)
            email = getattr(self.engineer_id, 'email', False) or (getattr(partner, 'email', False) if partner else False)
            self.engineer_contact = phone or False
            self.engineer_email = email or False
        else:
            self.engineer_contact = False
            self.engineer_email = False

    _sql_constraints = [
        ('ticket_id_uniq', 'unique(ticket_id)', 'The Ticket ID must be unique! This Ticket ID is already assigned to another ticket.'),
    ]

    @api.constrains('ticket_id')
    def _check_unique_ticket_id(self):
        for rec in self:
            if rec.ticket_id:
                duplicate = self.search([
                    ('ticket_id', '=', rec.ticket_id.strip()),
                    ('id', '!=', rec.id)
                ], limit=1)
                if duplicate:
                    raise ValidationError(_("Ticket ID '%s' already exists! Each service ticket must have a unique Ticket ID.") % rec.ticket_id)
