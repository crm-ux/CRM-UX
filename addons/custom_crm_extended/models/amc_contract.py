# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class AmcContract(models.Model):
    _name = 'amc.contract'
    _description = 'Annual Maintenance Contract'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'id desc'
    
    name = fields.Char(string='AMC No.', required=True, copy=False, default='Draft')
    date = fields.Date(string='Date', default=fields.Date.context_today, tracking=True)
    draft_name = fields.Char(string='Saved Draft Number', copy=False)
    official_name = fields.Char(string='Saved Official Number', copy=False)
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
    warranty_start_date = fields.Date(string='Warranty Start Date', tracking=True)
    warranty_end_date = fields.Date(string='Warranty End Date', tracking=True)
    contract_start_date = fields.Date(string='Contract Start Date', tracking=True)
    contract_end_date = fields.Date(string='Contract End Date', tracking=True)
    contract_value = fields.Char(string='Contract Value (₹)', tracking=True)
    gst = fields.Char(string='GST (%)', default='18')
    payment_terms = fields.Char(string='Payment Terms')
    renewal_terms = fields.Char(string='Renewal Terms')
    pm = fields.Char(string='PM')
    cm = fields.Char(string='Breakdown')

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

    @api.constrains('pm', 'cm')
    def _check_pm_cm_numeric(self):
        for rec in self:
            pm_val = rec.pm.strip() if rec.pm else ""
            cm_val = rec.cm.strip() if rec.cm else ""

            # Detect negative values
            pm_is_negative = pm_val.startswith('-') and pm_val[1:].isdigit()
            cm_is_negative = cm_val.startswith('-') and cm_val[1:].isdigit()

            # Detect other non-numeric / alphabet values
            pm_is_non_numeric = bool(pm_val and not pm_val.isdigit() and not pm_is_negative)
            cm_is_non_numeric = bool(cm_val and not cm_val.isdigit() and not cm_is_negative)

            # 1. Both are negative
            if pm_is_negative and cm_is_negative:
                raise ValidationError(_("Negative values are not allowed! Both PM ('%s') and Breakdown ('%s') visits cannot be negative.") % (pm_val, cm_val))

            # 2. Both have text / non-numeric characters
            if pm_is_non_numeric and cm_is_non_numeric:
                raise ValidationError(_("Alphabets and symbols are not allowed! Both PM ('%s') and Breakdown ('%s') must be numbers only.") % (pm_val, cm_val))

            # 3. Both are wrong (one negative, one non-numeric)
            if (pm_is_negative or pm_is_non_numeric) and (cm_is_negative or cm_is_non_numeric):
                raise ValidationError(_("Both PM ('%s') and Breakdown ('%s') values are invalid! Please enter positive numbers only.") % (pm_val, cm_val))

            # 4. Only PM is wrong
            if pm_is_negative:
                raise ValidationError(_("PM visits cannot be negative! You entered: '%s'") % pm_val)
            if pm_is_non_numeric:
                raise ValidationError(_("PM visits must be a number only! Alphabets or symbols are not allowed: '%s'") % pm_val)

            # 5. Only Breakdown is wrong
            if cm_is_negative:
                raise ValidationError(_("Breakdown visits cannot be negative! You entered: '%s'") % cm_val)
            if cm_is_non_numeric:
                raise ValidationError(_("Breakdown visits must be a number only! Alphabets or symbols are not allowed: '%s'") % cm_val)


    
    @api.onchange('partner_id')
    def _onchange_partner_id(self):
        if self.partner_id:
            p = self.partner_id
            contact_name = ""
            contact_phone = ""
            contact_email = ""

            available_gstins = []
            if p.vat:
                available_gstins.append(p.vat)
            if p.parent_id and p.parent_id.vat and p.parent_id.vat not in available_gstins:
                available_gstins.append(p.parent_id.vat)
            for child in p.child_ids:
                if child.vat and child.vat not in available_gstins:
                    available_gstins.append(child.vat)
            self.gstin = available_gstins[0] if available_gstins else ""

            def get_phone(partner):
                if not partner:
                    return ""
                return getattr(partner, 'mobile', False) or getattr(partner, 'phone', False) or ""

            if p.is_company:
                primary_contact = p.child_ids.filtered(lambda c: c.type == 'contact')[:1]
                if primary_contact:
                    c = primary_contact[0]
                    contact_name = c.name or p.name or ""
                    contact_phone = get_phone(c) or get_phone(p)
                    contact_email = c.email or p.email or ""
                else:
                    contact_name = p.name or ""
                    contact_phone = get_phone(p)
                    contact_email = p.email or ""
            else:
                contact_name = p.name or ""
                contact_phone = get_phone(p) or get_phone(p.parent_id)
                contact_email = p.email or (p.parent_id.email if p.parent_id else False) or ""

            self.contact_person = contact_name
            self.mobile = contact_phone
            self.email = contact_email
            self.gstin = p.vat or (p.parent_id.vat if p.parent_id else "") or ""
            self.location = getattr(p, 'x_site_name', False) or (getattr(p.parent_id, 'x_site_name', False) if p.parent_id else "") or p.city or ""

            addr_parts = [p.street, p.street2, p.city, p.state_id.name if p.state_id else False, p.country_id.name if p.country_id else False, p.zip]
            self.customer_address = ", ".join([str(a) for a in addr_parts if a])


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

    @api.model
    def _get_amc_sequence(self):
        """Finds existing AMC sequence from Series Settings or auto-creates default one."""
        seq = self.env['ir.sequence'].sudo().search([('code', '=', 'amc.contract')], limit=1)
        if not seq:
            seq = self.env['ir.sequence'].sudo().create({
                'name': 'AMC Numbering Series',
                'code': 'amc.contract',
                'prefix': False,
                'padding': 1,
                'number_next': 1,
                'number_increment': 1,
                'company_id': False,
            })
        return seq

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            status = vals.get('contract_status', 'draft')
            # If created directly in Active, generate AMC number; otherwise keep 'Draft'
            if status != 'draft':
                seq = self._get_amc_sequence()
                vals['name'] = seq.next_by_id() or '1'
            else:
                vals['name'] = 'Draft'
        return super().create(vals_list)

    def write(self, vals):
        new_status = vals.get('contract_status')
        if new_status:
            for record in self:
                # If moving from Draft to Active, generate official AMC sequence
                if new_status != 'draft' and (not record.name or record.name == 'Draft'):
                    seq = self._get_amc_sequence()
                    vals['name'] = seq.next_by_id() or '1'
                # If moving back to Draft
                elif new_status == 'draft':
                    vals['name'] = 'Draft'
        return super().write(vals)

    @api.onchange('contract_status')
    def _onchange_contract_status(self):
        if self.contract_status == 'draft':
            self.name = 'Draft'
        else:
            # If already has an assigned official number in DB, keep it; else preview next AMC number
            if self.name and self.name != 'Draft':
                return
            seq = self._get_amc_sequence()
            prefix = seq.prefix if seq.prefix else ''
            next_val = seq.number_next_actual if hasattr(seq, 'number_next_actual') else (seq.number_next or 1)
            pad = seq.padding or 1
            self.name = f"{prefix}{str(next_val).zfill(pad)}"


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

    