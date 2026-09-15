# -*- coding: utf-8 -*-
from odoo import models, fields, api, _

class AmcContract(models.Model):
    _name = 'amc.contract'
    _description = 'Annual Maintenance Contract'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'id desc'

    name = fields.Char(string='AMC No.', default=lambda self: _('New'), tracking=True)
    date = fields.Date(string='Date', default=fields.Date.context_today, tracking=True)

    contract_status = fields.Selection([
        ('draft', 'Draft'),
        ('active', 'Active'),
        ('expired', 'Expired'),
        ('renewed', 'Renewed'),
        ('cancelled', 'Cancelled'),
    ], string='Contract Status', default='draft', required=True, tracking=True)

    # Customer & Contact Details
    partner_id = fields.Many2one('res.partner', string='Customer / Company Name', tracking=True)
    customer_address = fields.Text(string='Customer Address')
    gstin = fields.Char(string='GSTIN')
    contact_person = fields.Char(string='Contact Person')
    mobile = fields.Char(string='Mobile')
    location = fields.Char(string='Location')
    email = fields.Char(string='Email')

    # Contract Duration & Commercials
    contract_start_date = fields.Date(string='Contract Start Date', tracking=True)
    contract_end_date = fields.Date(string='Contract End Date', tracking=True)
    contract_value = fields.Char(string='Contract Value (₹)', tracking=True)
    gst = fields.Char(string='GST (%)', default='18')
    payment_terms = fields.Char(string='Payment Terms')
    renewal_terms = fields.Char(string='Renewal Terms')
    pm = fields.Char(string='PM')
    cm = fields.Char(string='CM')

    # Line Items
    line_ids = fields.One2many('amc.contract.line', 'contract_id', string='Equipment Details')
    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.company)

    # State actions
    def action_set_active(self):
        self.write({'contract_status': 'active'})

    def action_set_draft(self):
        self.write({'contract_status': 'draft'})

    def action_set_expired(self):
        self.write({'contract_status': 'expired'})

    def action_set_cancelled(self):
        self.write({'contract_status': 'cancelled'})

    @api.onchange('partner_id')
    def _onchange_partner_id(self):
        if self.partner_id:
            p = self.partner_id
            contact_name = ""
            contact_phone = ""
            contact_email = ""

            if p.is_company:
                primary_contact = p.child_ids.filtered(lambda c: c.type == 'contact')[:1]
                if primary_contact:
                    contact_name = primary_contact.name or p.name or ""
                    contact_phone = primary_contact.phone or primary_contact.mobile or p.phone or p.mobile or ""
                    contact_email = primary_contact.email or p.email or ""
                else:
                    contact_name = p.name or ""
                    contact_phone = p.phone or p.mobile or ""
                    contact_email = p.email or ""
            else:
                contact_name = p.name or ""
                parent = p.parent_id
                contact_phone = p.phone or p.mobile or (parent.phone if parent else False) or (parent.mobile if parent else False) or ""
                contact_email = p.email or (parent.email if parent else False) or ""

            self.contact_person = contact_name
            self.mobile = contact_phone
            self.email = contact_email
            self.gstin = p.vat or (p.parent_id.vat if p.parent_id else "") or ""
            self.location = getattr(p, 'x_site_name', False) or (getattr(p.parent_id, 'x_site_name', False) if p.parent_id else "") or p.city or ""

            addr_parts = [p.street, p.street2, p.city, p.state_id.name if p.state_id else False, p.country_id.name if p.country_id else False, p.zip]
            self.customer_address = ", ".join([str(a) for a in addr_parts if a])


class AmcContractLine(models.Model):
    _name = 'amc.contract.line'
    _description = 'AMC Contract Equipment Line'

    contract_id = fields.Many2one('amc.contract', string='Contract Reference', ondelete='cascade')
    sequence = fields.Integer(string='Sr. No.', default=1)
    equipment_id = fields.Many2one('equipment.master', string='Equipment / System', required=True)
    make = fields.Char(string='Make')
    part_no = fields.Char(string='Part No')
    serial_no = fields.Char(string='Serial No.')
    location = fields.Char(string='Location')
    end_user = fields.Char(string='End User')
    mobile = fields.Char(string='Mobile')
    email = fields.Char(string='Email')
    remarks = fields.Text(string='Remarks')

    @api.onchange('equipment_id')
    def _onchange_equipment_id(self):
        if self.equipment_id:
            eq = self.equipment_id
            self.make = eq.manufacturer or ""
            self.part_no = eq.part_number or ""
            self.serial_no = eq.serial_number or ""
            self.location = eq.site_name or eq.room_number or ""
            self.end_user = eq.contact_person or ""
            self.mobile = eq.contact_number or ""
            self.email = eq.email or ""

    def action_save_and_close(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Annual Maintenance Contracts'),
            'res_model': 'amc.contract',
            'view_mode': 'list,form',
            'target': 'current',
        }

    def action_cancel_contract(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Annual Maintenance Contracts'),
            'res_model': 'amc.contract',
            'view_mode': 'list,form',
            'target': 'current',
        }

