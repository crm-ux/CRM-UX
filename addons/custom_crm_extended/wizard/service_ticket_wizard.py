# -*- coding: utf-8 -*-
from odoo import models, fields, api, _

class ServiceTicketWizard(models.TransientModel):
    _name = 'service.ticket.wizard'
    _description = 'Create Service Ticket Wizard'

    step = fields.Integer(string='Step', default=1)
    
    # Step 1: Ticket & Equipment Info
    ticket_datetime = fields.Datetime(string='Ticket Date & Time', default=fields.Datetime.now, required=True)
    partner_id = fields.Many2one('res.partner', string='Customer Name', required=True)
    equipment_id = fields.Many2one('equipment.master', string='Equipment')
    site_name = fields.Char(string='Site Name')
    contact_person = fields.Char(string='Contact Person')
    contact_number = fields.Char(string='Contact Number')
    email = fields.Char(string='Customer Email')
    model_number = fields.Char(string='Model Number')
    serial_number = fields.Char(string='Serial Number')
    part_number = fields.Char(string='Part Number')

    # Step 2: Complaint Details
    complaint_type = fields.Selection([
        ('breakdown', 'Breakdown'),
        ('amc', 'AMC'),
        ('pm', 'PM'),
        ('free_call', 'Free Call')
    ], string='Complaint Type', default='breakdown', required=True)
    complaint_description = fields.Text(string='Complaint Description', required=True)
    priority = fields.Selection([
        ('high', 'High'),
        ('medium', 'Medium'),
        ('low', 'Low')
    ], string='Priority', default='medium', required=True)

    # Step 3: Engineer Assignment & Schedule
    engineer_id = fields.Many2one('res.users', string='Assigned Engineer')
    engineer_contact = fields.Char(string='Engineer Contact')
    engineer_email = fields.Char(string='Engineer Email')
    visit_date = fields.Date(string='Visit Date')
    ticket_status = fields.Selection([
        ('open', 'Open'),
        ('ongoing', 'On Going'),
        ('closed', 'Closed')
    ], string='Ticket Status', default='open', required=True)

    # Step 4: Resolution & Sign-off
    root_cause = fields.Text(string='Root Cause')
    corrective_action = fields.Text(string='Corrective Action')
    spare_parts_used = fields.Char(string='Spare Parts Used')
    service_start_time = fields.Char(string='Service Start Time')
    service_end_time = fields.Char(string='Service End Time')
    customer_signature = fields.Binary(string='Customer Signature')
    engineer_signature = fields.Binary(string='Engineer Signature')

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

    def action_next_step(self):
        self.ensure_one()
        self.step += 1
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'service.ticket.wizard',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }

    def action_prev_step(self):
        self.ensure_one()
        self.step -= 1
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'service.ticket.wizard',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }

    def action_save_ticket(self):
        self.ensure_one()
        ticket_vals = {
            'ticket_datetime': self.ticket_datetime,
            'partner_id': self.partner_id.id,
            'equipment_id': self.equipment_id.id if self.equipment_id else False,
            'site_name': self.site_name,
            'contact_person': self.contact_person,
            'contact_number': self.contact_number,
            'email': self.email,
            'model_number': self.model_number,
            'serial_number': self.serial_number,
            'part_number': self.part_number,
            'complaint_type': self.complaint_type,
            'complaint_description': self.complaint_description,
            'priority': self.priority,
            'engineer_id': self.engineer_id.id if self.engineer_id else False,
            'engineer_contact': self.engineer_contact,
            'engineer_email': self.engineer_email,
            'visit_date': self.visit_date,
            'ticket_status': self.ticket_status,
            'root_cause': self.root_cause,
            'corrective_action': self.corrective_action,
            'spare_parts_used': self.spare_parts_used,
            'service_start_time': self.service_start_time,
            'service_end_time': self.service_end_time,
            'customer_signature': self.customer_signature,
            'engineer_signature': self.engineer_signature,
        }
        ticket = self.env['service.ticket'].create(ticket_vals)
        return {
            'type': 'ir.actions.act_window',
            'name': _('Service Ticket'),
            'res_model': 'service.ticket',
            'res_id': ticket.id,
            'view_mode': 'form',
            'views': [[False, 'form']],
            'target': 'current',
        }
