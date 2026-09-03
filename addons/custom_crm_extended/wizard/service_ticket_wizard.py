# -*- coding: utf-8 -*
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

class ServiceTicketWizard(models.TransientModel):
    _name = 'service.ticket.wizard'
    _description = 'Create Service Ticket Wizard'

    step = fields.Integer(string='Step', default=1)

    # Step 1: Ticket & Equipment Info
    ticket_id = fields.Char(string='Ticket ID')
    ticket_datetime = fields.Datetime(string='Ticket Date & Time', default=fields.Datetime.now)
    partner_id = fields.Many2one('res.partner', string='Customer Name')
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
    ], string='Complaint Type', default='breakdown')
    complaint_description = fields.Text(string='Complaint Description')
    priority = fields.Selection([
        ('high', 'High'),
        ('medium', 'Medium'),
        ('low', 'Low')
    ], string='Priority', default='medium')

    # Step 3: Engineer Assignment & Schedule
    engineer_id = fields.Many2one('res.users', string='Assigned Engineer')
    engineer_contact = fields.Char(string='Engineer Contact')
    engineer_email = fields.Char(string='Engineer Email')
    visit_date = fields.Date(string='Visit Date')
    ticket_status = fields.Selection([
        ('open', 'Open'),
        ('ongoing', 'On Going'),
        ('closed', 'Closed')
    ], string='Ticket Status', default='open')

    # Step 4: Resolution & Sign-off
    root_cause = fields.Text(string='Root Cause')
    corrective_action = fields.Text(string='Corrective Action')
    spare_parts_used = fields.Char(string='Spare Parts Used')
    service_start_time = fields.Datetime(string='Service Start Time')
    service_end_time = fields.Datetime(string='Service End Time')
    # customer_signature = fields.Binary(string='Customer Signature')
    # engineer_signature = fields.Binary(string='Engineer Signature')

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        ICP = self.env['ir.config_parameter'].sudo()
        Ticket = self.env['service.ticket'].sudo()

        if ICP.get_param('crm.ticket_id_auto', 'True') == 'True':
            prefix = ICP.get_param('crm.ticket_id_prefix', 'TCK-')
            pad = int(ICP.get_param('crm.ticket_id_padding', 4))
            next_num = int(ICP.get_param('crm.ticket_id_next', 1))
            suffix = ICP.get_param('crm.ticket_id_suffix', '')

            gen_id = f"{prefix}{str(next_num).zfill(pad)}{suffix}"
            while Ticket.search_count([('ticket_id', '=', gen_id)]) > 0:
                next_num += 1
                gen_id = f"{prefix}{str(next_num).zfill(pad)}{suffix}"

            res['ticket_id'] = gen_id
        return res

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

    def action_goto_1(self):
        self.ensure_one()
        self.step = 1
        return self._reopen_wizard()

    def action_goto_2(self):
        self.ensure_one()
        if not self.ticket_id:
            raise ValidationError(_('Please enter Ticket ID before proceeding.'))
        if not self.partner_id:
            raise ValidationError(_('Please select Customer Name before proceeding.'))
        self.step = 2
        return self._reopen_wizard()

    def action_goto_3(self):
        self.ensure_one()
        if not self.ticket_id:
            raise ValidationError(_('Please enter Ticket ID before proceeding.'))
        if not self.partner_id:
            raise ValidationError(_('Please select Customer Name before proceeding.'))
        self.step = 3
        return self._reopen_wizard()

    def _reopen_wizard(self):
        return {
            'name': _('Service Ticket Creation'),
            'type': 'ir.actions.act_window',
            'res_model': 'service.ticket.wizard',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }

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

    def action_next_step(self):
        self.ensure_one()
        if self.step == 1:
            if not self.ticket_id:
                raise ValidationError(_('Please enter Ticket ID before proceeding.'))
            if not self.partner_id:
                raise ValidationError(_('Please select Customer Name before proceeding.'))
        if self.step < 3:
            self.step += 1
        return self._reopen_wizard()


    def action_prev_step(self):
        self.ensure_one()
        self.step -= 1
        return self._reopen_wizard()

    def action_save_ticket(self):
        self.ensure_one()
        if not self.ticket_id:
            raise ValidationError(_('Ticket ID is required.'))
        if not self.partner_id:
            raise ValidationError(_('Customer Name is required.'))

        ticket_vals = {
            'ticket_id': self.ticket_id,
            'ticket_datetime': self.ticket_datetime or fields.Datetime.now(),
            'partner_id': self.partner_id.id,
            'equipment_id': self.equipment_id.id if self.equipment_id else False,
            'site_name': self.site_name,
            'contact_person': self.contact_person,
            'contact_number': self.contact_number,
            'email': self.email,
            'model_number': self.model_number,
            'serial_number': self.serial_number,
            'part_number': self.part_number,
            'complaint_type': self.complaint_type or 'breakdown',
            'complaint_description': self.complaint_description,
            'priority': self.priority or 'medium',
            'engineer_id': self.engineer_id.id if self.engineer_id else False,
            'engineer_contact': self.engineer_contact,
            'engineer_email': self.engineer_email,
            'visit_date': self.visit_date,
            'ticket_status': self.ticket_status or 'open',
            'root_cause': self.root_cause,
            'corrective_action': self.corrective_action,
            'spare_parts_used': self.spare_parts_used,
            'service_start_time': self.service_start_time,
            'service_end_time': self.service_end_time,
            # 'customer_signature': self.customer_signature,
            # 'engineer_signature': self.engineer_signature,
        }
        ticket = self.env['service.ticket'].create(ticket_vals)

        # Increment Ticket ID counter in settings
        ICP = self.env['ir.config_parameter'].sudo()
        if ICP.get_param('crm.ticket_id_auto', 'True') == 'True':
            current_next = int(ICP.get_param('crm.ticket_id_next', 1))
            ICP.set_param('crm.ticket_id_next', str(current_next + 1))

        return {
            'type': 'ir.actions.act_window',
            'name': _('Service Ticket'),
            'res_model': 'service.ticket',
            'res_id': ticket.id,
            'view_mode': 'form',
            'views': [[False, 'form']],
            'target': 'current',
        }
