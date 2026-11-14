# -*- coding: utf-8 -*-
import re
from lxml import etree
from odoo import models, fields, api, _
from odoo.osv import expression
from odoo.exceptions import ValidationError, UserError

class ServiceTicketComplaintType(models.Model):
    _name = 'service.ticket.complaint.type'
    _description = 'Service Ticket Complaint Type'
    _order = 'sequence, id'

    name = fields.Char(string='Complaint Type', required=True)
    sequence = fields.Integer(string='Sequence', default=10)
    active = fields.Boolean(string='Active', default=True)

    def unlink(self):
        for rec in self:
            name_clean = (rec.name or '').strip().lower()
            if name_clean in ('breakdown', 'pm'):
                raise UserError(_(
                    "The Complaint Type '%s' is a core system requirement and cannot be deleted."
                ) % rec.name)

            count = self.env['service.ticket'].search_count([('complaint_type_id', '=', rec.id)])
            if count > 0:
                raise UserError(_(
                    "The Complaint Type '%s' is used in %s Service Ticket(s) and cannot be deleted. You can uncheck 'Active' to archive it."
                ) % (rec.name, count))
        return super().unlink()

    def write(self, vals):
        if 'name' in vals:
            for rec in self:
                name_clean = (rec.name or '').strip().lower()
                new_clean = (vals.get('name') or '').strip().lower()
                if name_clean in ('breakdown', 'pm') and name_clean != new_clean:
                    raise UserError(_(
                        "The Complaint Type '%s' is a core system requirement and cannot be renamed."
                    ) % rec.name)
        if vals.get('active') is False:
            for rec in self:
                name_clean = (rec.name or '').strip().lower()
                if name_clean in ('breakdown', 'pm'):
                    raise UserError(_(
                        "The Complaint Type '%s' is a core system requirement and cannot be deactivated."
                    ) % rec.name)
        return super().write(vals)


class ServiceTicket(models.Model):
    _name = 'service.ticket'
    _description = 'Service Ticket'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _rec_name = 'ticket_id'
    _order = 'id desc'

    name = fields.Char(string='Ticket Number', required=True, copy=False, readonly=True, default=lambda self: _('New'))
    ticket_id = fields.Char(string='Ticket ID', required=True, copy=False, tracking=True, readonly=True)
    ticket_datetime = fields.Datetime(string='Ticket Date & Time', default=fields.Datetime.now, required=True, tracking=True, readonly=True)
    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.company, tracking=True)

    def init(self):
        super().init()
        # Pure Odoo ORM backfill - zero plain SQL queries
        ComplaintType = self.env['service.ticket.complaint.type'].sudo()
        bd = ComplaintType.search([('name', '=ilike', 'Breakdown')], limit=1)
        pm = ComplaintType.search([('name', '=ilike', 'PM')], limit=1)
        fc = ComplaintType.search([('name', '=ilike', 'Free Call')], limit=1)
        inst = ComplaintType.search([('name', '=ilike', 'Installation')], limit=1)

        Ticket = self.sudo()
        if bd:
            Ticket.search([('complaint_type', '=', 'breakdown'), ('complaint_type_id', '=', False)]).write({'complaint_type_id': bd.id})
        if pm:
            Ticket.search([('complaint_type', '=', 'pm'), ('complaint_type_id', '=', False)]).write({'complaint_type_id': pm.id})
        if fc:
            Ticket.search([('complaint_type', '=', 'free_call'), ('complaint_type_id', '=', False)]).write({'complaint_type_id': fc.id})
        if inst:
            Ticket.search([('complaint_type', '=', 'installation'), ('complaint_type_id', '=', False)]).write({'complaint_type_id': inst.id})

        # Any remaining ticket without complaint_type_id defaults to Breakdown
        if bd:
            Ticket.search([('complaint_type_id', '=', False)]).write({'complaint_type_id': bd.id})

    # Equipment & Customer Linkage
    equipment_id = fields.Many2one('equipment.master', string='Equipment', tracking=True)
    amc_id = fields.Many2one('amc.contract', string='AMC Contract', domain="[('contract_status', '!=', 'draft')]", tracking=True)
    partner_id = fields.Many2one('res.partner', string='Customer Name')
    site_name = fields.Char(string='Site Name')
    contact_person = fields.Char(string='Contact Person')
    contact_number = fields.Char(string='Contact Number')
    email = fields.Char(string='Customer Email')

    allowed_partner_ids = fields.Many2many('res.partner', compute='_compute_allowed_partners_equipments')
    allowed_equipment_ids = fields.Many2many('equipment.master', compute='_compute_allowed_partners_equipments')

    @api.depends('equipment_id', 'partner_id')
    def _compute_allowed_partners_equipments(self):
        for rec in self:
            # 1. Calculate allowed partners for equipment
            if rec.equipment_id and rec.equipment_id.partner_id:
                eq_p = rec.equipment_id.partner_id
                company_p = eq_p.commercial_partner_id or (eq_p.parent_id if eq_p.parent_id else eq_p)
                rec.allowed_partner_ids = eq_p | company_p | eq_p.child_ids
            else:
                rec.allowed_partner_ids = self.env['res.partner'].search([])

            # 2. Calculate allowed equipments for partner
            if rec.partner_id:
                p = rec.partner_id
                comp = p.commercial_partner_id or (p.parent_id if p.parent_id else p)
                partner_set = (p | comp | p.child_ids).ids
                rec.allowed_equipment_ids = self.env['equipment.master'].search([('partner_id', 'in', partner_set)])
            else:
                rec.allowed_equipment_ids = self.env['equipment.master'].search([])
    
    # Equipment Specs (Auto-filled from equipment)
    model_number = fields.Char(string='Model Number')
    serial_number = fields.Char(string='Serial Number')
    part_number = fields.Char(string='Part Number')

    @api.constrains('equipment_id', 'partner_id')
    def _check_equipment_partner_match(self):
        for rec in self:
            if rec.equipment_id and rec.partner_id:
                eq_partner = rec.equipment_id.partner_id
                if eq_partner:
                    valid_partners = rec.partner_id | rec.partner_id.commercial_partner_id | rec.partner_id.child_ids
                    if eq_partner not in valid_partners and rec.partner_id not in (eq_partner | eq_partner.commercial_partner_id | eq_partner.child_ids):
                        raise ValidationError(_(
                            "Equipment '%s' (Serial: %s) belongs to customer '%s', not '%s'. Please select matching customer and equipment."
                        ) % (
                            rec.equipment_id.display_name,
                            rec.equipment_id.serial_number or '-',
                            eq_partner.display_name,
                            rec.partner_id.display_name
                        ))

    @api.onchange('partner_id')
    def _onchange_partner_id_sync_equipment(self):
        if not self.partner_id:
            self.equipment_id = False
            self.model_number = False
            self.serial_number = False
            self.part_number = False
            self.site_name = False
            self.contact_person = False
            self.contact_number = False
            self.email = False
            self.amc_id = False
            return {'domain': {'equipment_id': []}}

        p = self.partner_id
        company_partner = p.commercial_partner_id or (p.parent_id if p.parent_id else p)

        # Basic customer contact info
        if not self.contact_person:
            self.contact_person = p.name
        if not self.contact_number:
            self.contact_number = getattr(p, 'phone', False) or getattr(p, 'mobile', False) or False
        if not self.email:
            self.email = getattr(p, 'email', False) or False
        if not self.site_name:
            self.site_name = getattr(p, 'x_site_name', False) or getattr(company_partner, 'x_site_name', False) or False

        # Find all equipments owned by this partner or its parent/branches
        partner_ids = (p | company_partner | p.child_ids).ids
        equipments = self.env['equipment.master'].search([('partner_id', 'in', partner_ids)])

        if len(equipments) == 1:
            # Single equipment holder: auto-select and auto-fill specs!
            eq = equipments[0]
            self.equipment_id = eq
            self.site_name = eq.site_name or self.site_name
            self.contact_person = eq.contact_person or self.contact_person
            self.contact_number = eq.contact_number or self.contact_number
            self.email = eq.email or self.email
            self.model_number = eq.model_number
            self.serial_number = eq.serial_number
            self.part_number = eq.part_number
        else:
            # Multiple equipments or none: if current equipment doesn't belong to this partner, clear it
            if self.equipment_id and self.equipment_id.partner_id.id not in partner_ids:
                self.equipment_id = False
                self.model_number = False
                self.serial_number = False
                self.part_number = False

        # Auto-detect Active AMC
        amcs = self.env['amc.contract'].search([
            ('contract_status', '!=', 'draft'),
            '|', ('partner_id', '=', p.id), ('partner_id', '=', company_partner.id)
        ])
        if len(amcs) == 1:
            self.amc_id = amcs[0].id
        elif not amcs:
            self.amc_id = False

        return {'domain': {'equipment_id': [('partner_id', 'in', partner_ids)]}}

    @api.onchange('equipment_id')
    def _onchange_equipment_id_sync_partner(self):
        if self.equipment_id:
            eq = self.equipment_id
            p = eq.partner_id
            if p:
                self.partner_id = p
                company_partner = p.commercial_partner_id or (p.parent_id if p.parent_id else p)
                self.site_name = eq.site_name or getattr(p, 'x_site_name', False) or getattr(company_partner, 'x_site_name', False) or False
                self.contact_person = eq.contact_person or p.name or False
                self.contact_number = eq.contact_number or getattr(p, 'phone', False) or getattr(p, 'mobile', False) or False
                self.email = eq.email or getattr(p, 'email', False) or False
            else:
                self.site_name = eq.site_name or False
                self.contact_person = eq.contact_person or False
                self.contact_number = eq.contact_number or False
                self.email = eq.email or False

            self.model_number = eq.model_number
            self.serial_number = eq.serial_number
            self.part_number = eq.part_number

            # Check if equipment is covered under an active AMC
            eq_amcs = self.env['amc.contract'].search([
                ('contract_status', '=', 'active'),
                ('line_ids.equipment_id', '=', eq.id)
            ], limit=1)
            if eq_amcs:
                self.amc_id = eq_amcs.id
            elif p:
                cust_amcs = self.env['amc.contract'].search([
                    ('contract_status', '!=', 'draft'),
                    '|', ('partner_id', '=', p.id), ('partner_id', '=', company_partner.id)
                ])
                if len(cust_amcs) == 1:
                    self.amc_id = cust_amcs.id

            if p:
                allowed_partners = (p | company_partner | p.child_ids).ids
                return {'domain': {'partner_id': [('id', 'in', allowed_partners)]}}
        else:
            # When Equipment is cleared in Form view, clear customer details & equipment specs
            self.partner_id = False
            self.site_name = False
            self.contact_person = False
            self.contact_number = False
            self.email = False
            self.model_number = False
            self.serial_number = False
            self.part_number = False
            self.amc_id = False
            return {'domain': {'partner_id': []}}
    
    # Complaint Details
    complaint_type_id = fields.Many2one(
        'service.ticket.complaint.type', 
        string='Complaint Type', 
        ondelete='restrict',
        tracking=True
    )
    complaint_type = fields.Selection([
        ('breakdown', 'Breakdown'),
        ('pm', 'PM'),
        ('free_call', 'Free Call')
    ], string='Legacy Complaint Type', default='breakdown')
    complaint_description = fields.Text(string='Complaint Description', tracking=True)
    priority = fields.Selection([
        ('high', 'High'),
        ('medium', 'Medium'),
        ('low', 'Low')
    ], string='Priority', default='medium', tracking=True)

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        if 'complaint_type_id' in fields_list and not res.get('complaint_type_id'):
            ct = self.env['service.ticket.complaint.type'].search([('name', '=ilike', 'Breakdown')], limit=1)
            if ct:
                res['complaint_type_id'] = ct.id
        res.update({
            'new_voucher_date': False,
            'new_voucher_user_ids': [(5, 0, 0)],
            'new_voucher_expense_type_id': False,
            'new_voucher_amount': 0.0,
            'new_voucher_description': False,
            'new_voucher_total_km': 0.0,
            'new_voucher_start_km': 0.0,
            'new_voucher_end_km': 0.0,
            'new_voucher_bill_file': False,
            'new_voucher_bill_filename': False,
        })
        return res

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            cid = vals.get('complaint_type_id')
            if cid:
                ct = self.env['service.ticket.complaint.type'].browse(cid)
                name_lower = (ct.name or '').strip().lower()
                if 'breakdown' in name_lower:
                    vals['complaint_type'] = 'breakdown'
                elif 'pm' in name_lower:
                    vals['complaint_type'] = 'pm'
                elif 'free' in name_lower:
                    vals['complaint_type'] = 'free_call'
            elif vals.get('complaint_type') and not cid:
                code = vals.get('complaint_type')
                ct = self.env['service.ticket.complaint.type'].search([
                    ('name', '=ilike', 'PM' if code == 'pm' else ('Free Call' if code == 'free_call' else 'Breakdown'))
                ], limit=1)
                if ct:
                    vals['complaint_type_id'] = ct.id
        records = super().create(vals_list)
        for rec in records:
            if rec.engineer_id and rec.engineer_id.id != self.env.user.id and rec.engineer_id.partner_id:
                p_name = rec.partner_id.name if rec.partner_id else '-'
                s_name = rec.site_name or '-'
                v_date = rec.visit_date.strftime('%d/%m/%Y') if rec.visit_date else '-'
                c_desc = rec.complaint_description or 'No complaint description.'
                tck_title = f"{rec.ticket_id or 'Ticket'}: {rec.complaint_type_id.name if rec.complaint_type_id else 'Service Call'}"
                body_msg = (
                    f"<b>Service Ticket Assigned</b><br/>"
                    f"Ticket <b>{tck_title}</b> has been assigned to you by <b>{self.env.user.name}</b>.<br/>"
                    f"Customer: <b>{p_name}</b> (Site: <b>{s_name}</b>)<br/>"
                    f"Priority: <b>{rec.priority.title() if rec.priority else 'Medium'}</b> | Visit Date: <b>{v_date}</b><br/>"
                    f"Problem: {c_desc}"
                )
                rec.message_post(
                    body=body_msg,
                    subject=f"Ticket Assigned: {tck_title}",
                    partner_ids=[rec.engineer_id.partner_id.id],
                    message_type='notification',
                    subtype_xmlid='mail.mt_comment',
                )
                try:
                    self.env['bus.bus']._sendone(
                        rec.engineer_id.partner_id,
                        'crm_notification',
                        {
                            'title': 'Service Ticket Assigned',
                            'message': f"Ticket {tck_title} assigned to you.",
                            'model': 'service.ticket',
                            'res_id': rec.id,
                        }
                    )
                except Exception:
                    pass
        return records

    def write(self, vals):
        cid = vals.get('complaint_type_id')
        if cid:
            ct = self.env['service.ticket.complaint.type'].browse(cid)
            name_lower = (ct.name or '').strip().lower()
            if 'breakdown' in name_lower:
                vals['complaint_type'] = 'breakdown'
            elif 'pm' in name_lower:
                vals['complaint_type'] = 'pm'
            elif 'free' in name_lower:
                vals['complaint_type'] = 'free_call'
        elif vals.get('complaint_type') and not cid:
            code = vals.get('complaint_type')
            ct = self.env['service.ticket.complaint.type'].search([
                ('name', '=ilike', 'PM' if code == 'pm' else ('Free Call' if code == 'free_call' else 'Breakdown'))
            ], limit=1)
            if ct:
                vals['complaint_type_id'] = ct.id

        old_engineers = {rec.id: rec.engineer_id.id for rec in self} if vals.get('engineer_id') else {}
        res = super().write(vals)

        if vals.get('engineer_id'):
            for rec in self:
                if rec.engineer_id and rec.engineer_id.id != old_engineers.get(rec.id) and rec.engineer_id.id != self.env.user.id:
                    if rec.engineer_id.partner_id:
                        p_name = rec.partner_id.name if rec.partner_id else '-'
                        s_name = rec.site_name or '-'
                        v_date = rec.visit_date.strftime('%d/%m/%Y') if rec.visit_date else '-'
                        c_desc = rec.complaint_description or 'No complaint description.'
                        tck_title = f"{rec.ticket_id or 'Ticket'}: {rec.complaint_type_id.name if rec.complaint_type_id else 'Service Call'}"
                        body_msg = (
                            f"<b>Service Ticket Assigned</b><br/>"
                            f"Ticket <b>{tck_title}</b> has been assigned to you by <b>{self.env.user.name}</b>.<br/>"
                            f"Customer: <b>{p_name}</b> (Site: <b>{s_name}</b>)<br/>"
                            f"Priority: <b>{rec.priority.title() if rec.priority else 'Medium'}</b> | Visit Date: <b>{v_date}</b><br/>"
                            f"Problem: {c_desc}"
                        )
                        rec.message_post(
                            body=body_msg,
                            subject=f"Ticket Assigned: {tck_title}",
                            partner_ids=[rec.engineer_id.partner_id.id],
                            message_type='notification',
                            subtype_xmlid='mail.mt_comment',
                        )
                        try:
                            self.env['bus.bus']._sendone(
                                rec.engineer_id.partner_id,
                                'crm_notification',
                                {
                                    'title': 'Service Ticket Assigned',
                                    'message': f"Ticket {tck_title} assigned to you.",
                                    'model': 'service.ticket',
                                    'res_id': rec.id,
                                }
                            )
                        except Exception:
                            pass
        return res

    # Assignment & Schedule
    engineer_id = fields.Many2one('res.users', string='Assigned Engineer', tracking=True)
    engineer_contact = fields.Char(string='Engineer Contact')
    engineer_email = fields.Char(string='Engineer Email')
    visit_date = fields.Date(string='Visit Date', tracking=True)

    @api.onchange('visit_date')
    def _onchange_visit_date_warning(self):
        if self.visit_date:
            today = fields.Date.today()
            if self.visit_date < today:
                inv_date = self.visit_date.strftime('%d-%m-%Y')
                today_str = today.strftime('%d-%m-%Y')
                self.visit_date = False
                return {
                    'warning': {
                        'title': _('Invalid Visit Date'),
                        'message': _("Visit Date (%s) cannot be a past date. Please select today (%s) or a future date.") % (inv_date, today_str),
                    }
                }

    @api.constrains('visit_date')
    def _check_visit_date(self):
        today = fields.Date.today()
        for rec in self:
            if rec.visit_date and rec.visit_date < today:
                raise ValidationError(_(
                    "Visit Date (%s) cannot be a past date. Please select today (%s) or a future date."
                ) % (rec.visit_date.strftime('%d-%m-%Y'), today.strftime('%d-%m-%Y')))

    # Service Report & Attachment
    report_number = fields.Char(string='Report No.', tracking=True)
    report_filename = fields.Char(string='Report Filename')
    report_attachment = fields.Binary(string='Report Attachment', attachment=True)

    def action_preview_service_report(self):
        """Action button for Service Report preview."""
        return True

    @api.model
    def action_get_report_preview_content(self, res_id=None, raw_b64=None, filename=None, field_name='report_attachment'):
        """Extract preview content for Service Ticket attachments (delegates to universal parser)."""
        if res_id:
            rec = self.sudo().browse(int(res_id))
            if rec.exists():
                raw_b64 = rec.report_attachment or raw_b64
                filename = rec.report_filename or filename

        return self.env['equipment.master'].action_get_invoice_preview_content(
            res_id=False, raw_b64=raw_b64, filename=filename
        )
    
    # Resolution & Sign-off
    root_cause = fields.Text(string='Root Cause')
    corrective_action = fields.Text(string='Corrective Action')
    spare_parts_used = fields.Char(string='Spare Parts Used')
    service_start_time = fields.Datetime(string='Service Start Time')
    service_end_time = fields.Datetime(string='Service End Time')
    voucher_line_ids = fields.One2many('service.ticket.voucher.line', 'ticket_id', string='Voucher Lines')
    draft_voucher_line_ids = fields.One2many('service.ticket.voucher.line', 'ticket_id', string='Pending Expenses', domain=[('status', '=', 'draft')])
    submitted_voucher_line_ids = fields.One2many('service.ticket.voucher.line', 'ticket_id', string='Submitted Vouchers', domain=[('status', '!=', 'draft')])
    voucher_batch_ids = fields.One2many('service.ticket.voucher.batch', 'ticket_id', string='Voucher Submissions', domain=[('line_ids', '!=', False)])
    has_submitted_batches = fields.Boolean(compute='_compute_has_submitted_batches', string='Has Submitted Vouchers')
    has_submitted_vouchers = fields.Boolean(compute='_compute_has_submitted_vouchers', string='Has Submitted Voucher Lines')
    customer_signature = fields.Binary(string='Customer Signature')
    engineer_signature = fields.Binary(string='Engineer Signature')
    
    # Status (5 Stages)
    ticket_status = fields.Selection([
        ('new', 'New'),
        ('contacted', 'Contacted'),
        ('ongoing', 'Ongoing'),
        ('pending', 'Pending'),
        ('closed', 'Close')
    ], string='Ticket Status', default='new', tracking=True)

    # Quick Add Voucher Fields on Ticket
    @api.depends('submitted_voucher_line_ids')
    def _compute_has_submitted_vouchers(self):
        for rec in self:
            rec.has_submitted_vouchers = bool(rec.submitted_voucher_line_ids)

    submitted_voucher_names = fields.Char(compute='_compute_submitted_voucher_names', string='Voucher IDs')

    @api.depends('voucher_batch_ids', 'voucher_batch_ids.name')
    def _compute_submitted_voucher_names(self):
        for rec in self:
            names = [b.name for b in rec.voucher_batch_ids if b.name]
            rec.submitted_voucher_names = ", ".join(names) if names else ''

    @api.depends('voucher_batch_ids', 'voucher_batch_ids.line_ids')
    def _compute_has_submitted_batches(self):
        for rec in self:
            rec.has_submitted_batches = any(batch.line_ids for batch in rec.voucher_batch_ids)

    submitted_vouchers_html = fields.Html(
        string='Submitted Expenses Display',
        compute='_compute_submitted_vouchers_html',
        sanitize=False,
    )

    @api.depends('voucher_batch_ids', 'voucher_batch_ids.line_ids', 'voucher_batch_ids.name', 'voucher_batch_ids.total_amount', 'voucher_batch_ids.status')
    def _compute_submitted_vouchers_html(self):
        for rec in self:
            rec._separate_mixed_voucher_batches()
            batches = rec.voucher_batch_ids.filtered(lambda b: b.line_ids).sorted(key=lambda b: (b.submission_date or fields.Date.today(), b.id), reverse=True)
            if not batches:
                rec.submitted_vouchers_html = False
                continue

            html_parts = []
            for batch in batches:
                st = batch.status or 'submitted'
                badge_bg = '#fef3c7'
                badge_color = '#d97706'
                badge_border = '#fde68a'
                if st in ('approved', 'partially_approved'):
                    badge_bg = '#d1fae5'
                    badge_color = '#059669'
                    badge_border = '#86efac'
                elif st in ('paid', 'partially_paid'):
                    badge_bg = '#e0f2fe'
                    badge_color = '#0284c7'
                    badge_border = '#bae6fd'
                elif st == 'rejected':
                    badge_bg = '#fee2e2'
                    badge_color = '#dc2626'
                    badge_border = '#fca5a5'
                st_label = dict(batch._fields['status'].selection).get(st, st.replace('_', ' ').title())

                vch_name = batch.name or 'New'
                # Live compute unique expense dates from lines
                line_dates = [l.expense_date.strftime('%d/%m/%Y') for l in batch.line_ids if l.expense_date]
                unique_exp_dates = list(dict.fromkeys(line_dates))
                vch_exp_dates = ", ".join(unique_exp_dates) if unique_exp_dates else ''
                
                # Submission date when sent to manager
                sub_dt = batch.create_date or batch.submission_date
                vch_sub_date = sub_dt.strftime('%d/%m/%Y') if sub_dt else ''
                vch_emps = batch.all_employee_names or (batch.user_id.name if batch.user_id else '')

                strip_html = f"""
                <div class="d-flex align-items-center justify-content-between p-2 px-3 mb-2 rounded border bg-white shadow-sm flex-wrap" style="border-left: 4px solid #0b3d91 !important;">
                    <div class="d-flex align-items-center gap-2 flex-wrap">
                        <span class="fw-bold" style="color: #0b3d91; font-size: 13px;">Voucher ID:</span>
                        <span class="badge py-1 px-2 fw-bold" style="background-color: #e8f0fe; color: #0b3d91; border: 1px solid #b8d0f8; font-size: 13px;">{vch_name}</span>
                        <span class="text-muted fw-bold mx-1">|</span>
                        <span class="fw-bold text-dark" style="font-size: 13px;">Submitted Date:</span>
                        <span class="badge py-1 px-2 fw-bold" style="background-color: #f1f5f9; color: #334155; border: 1px solid #cbd5e1; font-size: 13px;">{vch_sub_date}</span>
                        <span class="text-muted fw-bold mx-1">|</span>
                        <span class="fw-bold text-dark" style="font-size: 13px;">Employee(s):</span>
                        <span class="badge py-1 px-2 fw-bold" style="background-color: #e8f0fe; color: #0b3d91; border: 1px solid #b8d0f8; font-size: 13px;">{vch_emps}</span>
                    </div>
                    <div>
                        <span class="badge py-1 px-2 fw-bold" style="background-color: {badge_bg}; color: {badge_color}; border: 1px solid {badge_border}; font-size: 12px; border-radius: 4px;">{st_label}</span>
                    </div>
                </div>
                """

                has_km = any(l.is_km_based for l in batch.line_ids)
                km_header = '<th style="padding: 8px; border-bottom: 2px solid #dee2e6; text-align: right;">Total KM</th><th style="padding: 8px; border-bottom: 2px solid #dee2e6; text-align: right;">Rate/KM (₹)</th>' if has_km else ''

                rows_html = []
                for line in batch.line_ids:
                    l_date = line.expense_date.strftime('%d/%m/%Y') if line.expense_date else ''
                    l_emp = line.user_id.name if line.user_id else ''
                    l_type = line.expense_type_id.name if line.expense_type_id else ''
                    l_km = f"{line.total_km:.2f}" if line.is_km_based else "0.00"
                    l_rate = f"{line.rate_per_km:.2f}" if line.is_km_based else "0.00"
                    l_km_cells = f'<td style="padding: 8px; text-align: right;">{l_km}</td><td style="padding: 8px; text-align: right;">{l_rate}</td>' if has_km else ''
                    l_desc = line.description or ''
                    l_amt = f"₹ {line.amount:,.2f}" if line.amount else "₹ 0.00"
                    if line.status in ('approved', 'partially_approved', 'paid'):
                        # If approved_amount is set use it; otherwise fallback to line.amount (for records approved previously)
                        eff_approved = line.approved_amount if line.approved_amount else line.amount
                        l_approved_amt = f"₹ {eff_approved:,.2f}" if eff_approved else "-"
                    else:
                        l_approved_amt = "-"
                    
                    if line.bill_file:
                        fn = line.bill_filename or 'Bill'
                        bill_link = f'<button type="button" class="btn btn-sm p-0 o_voucher_bill_preview_btn text-truncate" data-line-id="{line.id}" data-filename="{fn}" style="color: #0b3d91 !important; font-weight: 600; text-decoration: underline; max-width: 160px; display: inline-block; vertical-align: middle; border: none; background: transparent; cursor: pointer;" title="Preview {fn}">{fn}</button>'
                    else:
                        bill_link = '<span class="text-muted">-</span>'

                    l_st = line.status or 'submitted'
                    l_badge_bg = '#fef3c7'
                    l_badge_color = '#d97706'
                    l_badge_border = '#fde68a'
                    if l_st in ('approved', 'partially_approved'):
                        l_badge_bg = '#d1fae5'
                        l_badge_color = '#059669'
                        l_badge_border = '#86efac'
                    elif l_st in ('paid', 'partially_paid'):
                        l_badge_bg = '#e0f2fe'
                        l_badge_color = '#0284c7'
                        l_badge_border = '#bae6fd'
                    elif l_st == 'rejected':
                        l_badge_bg = '#fee2e2'
                        l_badge_color = '#dc2626'
                        l_badge_border = '#fca5a5'
                    l_st_label = dict(line._fields['status'].selection).get(l_st, l_st.replace('_', ' ').title())
                    l_badge = f'<span class="badge py-1 px-2 fw-semibold" style="background-color: {l_badge_bg}; color: {l_badge_color}; border: 1px solid {l_badge_border}; border-radius: 4px;">{l_st_label}</span>'

                    l_reason = line.reject_reason or ''
                    l_reason_td = f'<span style="color: #334155; font-size: 12px; font-weight: 500;">{l_reason}</span>' if (l_st == 'rejected' and l_reason) else '<span class="text-muted">-</span>'

                    row = f"""
                    <tr style="border-bottom: 1px solid #f1f5f9;">
                        <td style="padding: 8px;">{l_date}</td>
                        <td style="padding: 8px; font-weight: 500;">{l_emp}</td>
                        <td style="padding: 8px; font-weight: 600; color: #1e293b;">{l_type}</td>
                        {l_km_cells}
                        <td style="padding: 8px; color: #475569;">{l_desc}</td>
                        <td style="padding: 8px; text-align: right; font-weight: 600; color: #1e293b;">{l_amt}</td>
                        <td style="padding: 8px; text-align: right; font-weight: 600; color: #1e293b;">{l_approved_amt}</td>
                        <td style="padding: 8px; text-align: center;">{bill_link}</td>
                        <td style="padding: 8px; text-align: center;">{l_badge}</td>
                        <td style="padding: 8px;">{l_reason_td}</td>
                    </tr>
                    """
                    rows_html.append(row)

                batch_total_submitted = f"₹ {sum(l.amount or 0.0 for l in batch.line_ids):,.2f}"
                def _get_eff_approved(l):
                    return (l.approved_amount or l.amount or 0.0) if l.status in ('approved', 'paid') else 0.0
                batch_total_approved = f"₹ {sum(_get_eff_approved(l) for l in batch.line_ids):,.2f}"
                col_span = 6 if has_km else 4

                table_html = f"""
                <div class="table-responsive mb-4">
                    <table class="table table-sm align-middle w-100" style="background-color: #ffffff; border: 1px solid #e2e8f0; border-radius: 6px; overflow: hidden; margin-bottom: 0;">
                        <thead style="background-color: #f8fafc; font-size: 13px; color: #475569; font-weight: 600;">
                            <tr>
                                <th style="padding: 8px; border-bottom: 2px solid #dee2e6;">Expense Date</th>
                                <th style="padding: 8px; border-bottom: 2px solid #dee2e6;">Employee</th>
                                <th style="padding: 8px; border-bottom: 2px solid #dee2e6;">Expense Type</th>
                                {km_header}
                                <th style="padding: 8px; border-bottom: 2px solid #dee2e6;">Description</th>
                                <th style="padding: 8px; border-bottom: 2px solid #dee2e6; text-align: right;">Submitted Amount</th>
                                <th style="padding: 8px; border-bottom: 2px solid #dee2e6; text-align: right; color: #1e293b;">Approved Amount</th>
                                <th style="padding: 8px; border-bottom: 2px solid #dee2e6; text-align: center;">Bill</th>
                                <th style="padding: 8px; border-bottom: 2px solid #dee2e6; text-align: center;">Status</th>
                                <th style="padding: 8px; border-bottom: 2px solid #dee2e6;">Reject Reason</th>
                            </tr>
                        </thead>
                        <tbody style="font-size: 13px;">
                            {''.join(rows_html)}
                        </tbody>
                        <tfoot style="background-color: #f8fafc; border-top: 2px solid #e2e8f0;">
                            <tr>
                                <td colspan="{col_span}" style="padding: 8px; text-align: right; font-weight: 700; color: #334155;">Subtotal:</td>
                                <td style="padding: 8px; text-align: right; font-weight: 700; font-size: 13px; color: #1e293b;">{batch_total_submitted}</td>
                                <td style="padding: 8px; text-align: right; font-weight: 700; font-size: 13px; color: #1e293b;">{batch_total_approved}</td>
                                <td colspan="3"></td>
                            </tr>
                        </tfoot>
                    </table>
                </div>
                """
                html_parts.append(strip_html + table_html)

            rec.submitted_vouchers_html = "".join(html_parts)

    new_voucher_user_ids = fields.Many2many(
        'res.users',
        'service_ticket_quick_voucher_user_rel',
        'ticket_id',
        'user_id',
        string='Employees / Team',
        domain="[('share', '=', False), ('id', 'not in', new_voucher_user_ids)]",
        help="Select one or multiple employees to divide the total expense cost."   
    )
    new_voucher_date = fields.Date(string='Expense Date')
    new_voucher_date_to = fields.Date(string='To Date')
    new_voucher_is_daily = fields.Boolean(compute='_compute_new_voucher_is_daily', string='Is Daily')
    new_voucher_days = fields.Integer(compute='_compute_new_voucher_days', string='Days Count')
    new_voucher_days_display_html = fields.Html(compute='_compute_new_voucher_days', string='Days Badge HTML')

    @api.depends('new_voucher_expense_type_id')
    def _compute_new_voucher_is_daily(self):
        for rec in self:
            rec.new_voucher_is_daily = bool(rec.new_voucher_expense_type_id and rec.new_voucher_expense_type_id.calculation_type == 'daily' and not rec.new_voucher_expense_type_id.is_km_based)

    @api.depends('new_voucher_date', 'new_voucher_date_to', 'new_voucher_is_daily')
    def _compute_new_voucher_days(self):
        for rec in self:
            if rec.new_voucher_is_daily and rec.new_voucher_date and rec.new_voucher_date_to and rec.new_voucher_date_to >= rec.new_voucher_date:
                days = (rec.new_voucher_date_to - rec.new_voucher_date).days + 1
            else:
                days = 1
            rec.new_voucher_days = days
            rec.new_voucher_days_display_html = False

    new_voucher_bill_attachment_ids = fields.Many2many(
        'ir.attachment',
        'service_ticket_new_voucher_attachment_rel',
        'ticket_id',
        'attachment_id',
        string='Bills & Receipts',
    )
    new_voucher_expense_type_id = fields.Many2one('service.ticket.expense.type', string='Expense Type')
    allowed_voucher_expense_type_ids = fields.Many2many(
        'service.ticket.expense.type',
        compute='_compute_allowed_voucher_expense_type_ids',
        string='Allowed Expense Types',
    )

    @api.depends('new_voucher_user_ids')
    def _compute_allowed_voucher_expense_type_ids(self):
        all_types = self.env['service.ticket.expense.type'].search([('active', '=', True)])
        for rec in self:
            target_users = rec.new_voucher_user_ids or self.env.user
            allowed_ids = []
            for t in all_types:
                if not t.job_ids:
                    # Global expense type -> allowed for everyone
                    allowed_ids.append(t.id)
                else:
                    # Restricted expense type -> all target users must have an allowed job position
                    user_ok = True
                    for u in target_users:
                        u_jobs = t._get_user_job_positions(user=u)
                        if not any(j.id in u_jobs for j in t.job_ids):
                            user_ok = False
                            break
                    if user_ok:
                        allowed_ids.append(t.id)
            rec.allowed_voucher_expense_type_ids = all_types.browse(allowed_ids)

    @api.onchange('new_voucher_user_ids')
    def _onchange_new_voucher_user_ids_filter_type(self):
        self._compute_allowed_voucher_expense_type_ids()
        exp_type = self.new_voucher_expense_type_id
        if exp_type and exp_type.job_ids:
            for u in self.new_voucher_user_ids:
                u_jobs = exp_type._get_user_job_positions(user=u)
                if not any(j.id in u_jobs for j in exp_type.job_ids):
                    self.new_voucher_expense_type_id = False
                    break
        self._compute_new_voucher_budget_info_html()

    new_voucher_budget_info_html = fields.Html(
        compute='_compute_new_voucher_budget_info_html',
        string='Budget Info Display',
        sanitize=False,
    )

    def _get_user_role_display(self, user):
        """Returns the Job Position title dynamically for any user/employee/manager."""
        if not user:
            return ""
        if getattr(user, 'crm_job_id', None) and user.crm_job_id:
            return user.crm_job_id.name
        job_ids = self.env['service.ticket.expense.type']._get_user_job_positions(user=user)
        if job_ids:
            exp_type = getattr(self, 'new_voucher_expense_type_id', None)
            if exp_type:
                for rule in exp_type.limit_rule_ids:
                    if rule.active:
                        matched = rule.job_ids.filtered(lambda j: j.id in job_ids)
                        if matched:
                            return matched[0].name
            job = self.env['hr.job'].sudo().browse(list(job_ids)[0])
            if job.exists():
                return job.name
        return ""

    # Removed auto-recomputing on every focus/blur to prevent unwanted page re-renders/freezes
    def _onchange_new_voucher_inputs_warning(self):
        pass

    @api.depends('new_voucher_user_ids', 'new_voucher_expense_type_id', 'new_voucher_amount', 'new_voucher_total_km')
    def _compute_new_voucher_budget_info_html(self):
        for rec in self:
            exp_type = rec.new_voucher_expense_type_id
            if not exp_type:
                rec.new_voucher_budget_info_html = False
                continue

            target_users = rec.new_voucher_user_ids or (rec.engineer_id or self.env.user)
            if not target_users:
                rec.new_voucher_budget_info_html = False
                continue

            pill_badge = "background:#e0f2fe; color:#0369a1; border:1px solid #bae6fd; font-weight:600; border-radius:9999px; padding:2px 10px; white-space:nowrap;"
            pill_total = "background:#e0f2fe; color:#0369a1; border:1px solid #bae6fd; font-weight:700; border-radius:9999px; padding:2px 10px; white-space:nowrap;"

            emp_names = ", ".join(target_users.mapped('name')) if target_users else ''

            if exp_type.is_km_based:
                items_html = []
                for u in target_users:
                    role_name = rec._get_user_role_display(u)
                    role_str = f" ({role_name})" if role_name else ""
                    rate = exp_type.get_effective_km_rate(user=u)
                    items_html.append(f"<span class='badge' style='{pill_badge}'>{u.name}{role_str}: ₹{rate:,.2f}/KM</span>")

                missing_km_html = ""

                rec.new_voucher_budget_info_html = f"""
                <div class="d-flex align-items-center gap-2 flex-wrap py-1" style="font-size:12px; color:#0c4a6e; line-height:1.6; row-gap:6px;">
                    <span style="white-space:nowrap;">Allowed Rate for <strong>KM Expense</strong>:</span>
                    {" ".join(items_html)}
                </div>
                """
            else:
                total_limit = 0.0
                has_any_limit = False
                items_html = []
                days = rec.new_voucher_days if exp_type.calculation_type == 'daily' else 1
                days_label = f" ({days} Days)" if (exp_type.calculation_type == 'daily' and days > 1) else ""
                for u in target_users:
                    role_name = rec._get_user_role_display(u)
                    role_str = f" ({role_name})" if role_name else ""
                    base_limit = exp_type.get_effective_budget_limit(user=u)
                    limit = base_limit * days
                    if limit > 0:
                        has_any_limit = True
                        total_limit += limit
                        items_html.append(f"<span class='badge' style='{pill_badge}'>{u.name}{role_str}: ₹{limit:,.2f}{days_label}</span>")
                    else:
                        items_html.append(f"<span class='badge' style='background:#f1f5f9; color:#475569; border:1px solid #cbd5e1; border-radius:9999px; padding:2px 10px; white-space:nowrap;'>{u.name}{role_str}: No Limit</span>")

                entered_amount = rec.new_voucher_amount or 0.0
                is_exceeded = bool(has_any_limit and total_limit > 0 and entered_amount > total_limit)
                diff = entered_amount - total_limit if is_exceeded else 0.0

                if exp_type.calculation_type == 'daily':
                    unit_label = f" / {days} Days" if days > 1 else " / day"
                else:
                    unit_label = " / visit"
                if len(target_users) > 1 and has_any_limit:
                    rec.new_voucher_budget_info_html = f"""
                    <div class="d-flex align-items-center gap-2 flex-wrap py-1" style="font-size:12px; color:#0c4a6e; line-height:1.6; row-gap:6px;">
                        <span style="white-space:nowrap;">Allowed Limit for <strong>Group Budget Pool</strong>:</span>
                        <span class="badge" style="{pill_total}">₹{total_limit:,.2f}{unit_label}</span>
                        <span class="text-muted fw-bold mx-1">|</span>
                        {" ".join(items_html)}
                    </div>
                    """
                elif has_any_limit:
                    u = target_users[:1]
                    role_name = rec._get_user_role_display(u)
                    role_str = f" ({role_name})" if role_name else ""
                    rec.new_voucher_budget_info_html = f"""
                    <div class="d-flex align-items-center gap-2 flex-wrap py-1" style="font-size:12px; color:#0c4a6e; line-height:1.6; row-gap:6px;">
                        <span style="white-space:nowrap;">Allowed Limit for <strong>{u.name}{role_str}</strong>:</span>
                        <span class="badge" style="{pill_total}">₹{total_limit:,.2f}{unit_label}</span>
                    </div>
                    """
                else:
                    rec.new_voucher_budget_info_html = f"""
                    <div class="py-1" style="font-size:12px; color:#64748b;">
                        <span>No budget limit restriction for this expense type.</span>
                    </div>
                    """

    has_km_lines = fields.Boolean(compute='_compute_has_km_lines', string='Has KM Lines')

    @api.depends('voucher_line_ids.is_km_based')
    def _compute_has_km_lines(self):
        for rec in self:
            rec.has_km_lines = any(line.is_km_based for line in rec.voucher_line_ids)

    new_voucher_is_km = fields.Boolean(compute='_compute_new_voucher_is_km', string='Is KM Based')

    @api.depends('new_voucher_expense_type_id', 'new_voucher_expense_type_id.is_km_based')
    def _compute_new_voucher_is_km(self):
        for rec in self:
            rec.new_voucher_is_km = bool(rec.new_voucher_expense_type_id and rec.new_voucher_expense_type_id.is_km_based)
    
    new_voucher_start_km = fields.Float(string='Start KM')
    new_voucher_end_km = fields.Float(string='End KM')
    new_voucher_total_km = fields.Float(string='Total KM')
    new_voucher_rate_per_km = fields.Float(
        related='new_voucher_expense_type_id.km_rate', 
        string='Rate/KM (₹)', 
        readonly=True
    )
    new_voucher_description = fields.Char(string='Description')
    new_voucher_amount = fields.Monetary(
        string='Amount', 
        currency_field='currency_id',
        default=0.0
    )
    new_voucher_bill_file = fields.Binary(string='Upload Bill')
    new_voucher_bill_filename = fields.Char(string='Bill Filename')
    currency_id = fields.Many2one('res.currency', string='Currency', default=lambda self: self.env.company.currency_id)

    @api.onchange('new_voucher_expense_type_id')
    def _onchange_new_voucher_expense_type(self):
        if self.new_voucher_expense_type_id:
            self.new_voucher_is_km = bool(self.new_voucher_expense_type_id.is_km_based)
            if self.new_voucher_is_km:
                rate = self.new_voucher_expense_type_id.km_rate or 0.0
                if self.new_voucher_total_km > 0 and rate > 0:
                    self.new_voucher_amount = round(self.new_voucher_total_km * rate, 2)
            else:
                self.new_voucher_total_km = 0.0
                self.new_voucher_start_km = 0.0
                self.new_voucher_end_km = 0.0
        else:
            self.new_voucher_is_km = False
            self.new_voucher_total_km = 0.0

    def _onchange_voucher_dates_update_pool(self):
        pass

    def _onchange_new_voucher_amount_warning(self):
        pass

    def action_add_voucher_line(self):
        self.ensure_one()
        missing_fields = []
        if not self.new_voucher_user_ids:
            missing_fields.append("Employee(s)")
        if not self.new_voucher_date:
            missing_fields.append("Expense Date")
        if self.new_voucher_is_daily and not self.new_voucher_date_to:
            missing_fields.append("To Date")
        if not self.new_voucher_expense_type_id:
            missing_fields.append("Expense Type")
        if not self.new_voucher_amount or self.new_voucher_amount <= 0:
            missing_fields.append("Amount")

        if missing_fields:
            fields_str = ", ".join(missing_fields)
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Missing Required Fields',
                    'message': f"Please fill in the required field(s): {fields_str}.",
                    'type': 'warning',
                    'sticky': False,
                }
            }

        exp_date = self.new_voucher_date
        today = fields.Date.context_today(self)
        if exp_date and exp_date > today:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Invalid Expense Date',
                    'message': 'Expense Date cannot be in the future.',
                    'type': 'warning',
                    'sticky': False,
                }
            }

        if self.new_voucher_is_daily and self.new_voucher_date_to:
            if self.new_voucher_date_to > today:
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': 'Invalid To Date',
                        'message': 'To Date cannot be in the future.',
                        'type': 'warning',
                        'sticky': False,
                    }
                }
            if self.new_voucher_date_to < exp_date:
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': 'Invalid Date Range',
                        'message': 'To Date cannot be earlier than From Date.',
                        'type': 'warning',
                        'sticky': False,
                    }
                }

        target_users = self.new_voucher_user_ids
        user_count = len(target_users)
        exp_type = self.new_voucher_expense_type_id

        # Validate that all target users are authorized for this expense type
        if exp_type.job_ids:
            for u in target_users:
                u_jobs = exp_type._get_user_job_positions(user=u)
                if not any(j.id in u_jobs for j in exp_type.job_ids):
                    allowed_names = ", ".join(exp_type.job_ids.mapped('name'))
                    return {
                        'type': 'ir.actions.client',
                        'tag': 'display_notification',
                        'params': {
                            'title': 'Job Position Restricted',
                            'message': f"Expense Type '{exp_type.name}' is only allowed for Job Position(s): {allowed_names}. Employee '{u.name}' is not authorized.",
                            'type': 'danger',
                            'sticky': True,
                        }
                    }

        split_km = round(self.new_voucher_total_km / user_count, 2) if (user_count > 0 and self.new_voucher_is_km) else self.new_voucher_total_km

        # 1. Determine each user's specific limit for this expense category
        # If calculation_type is 'daily', multiply by days count
        days = self.new_voucher_days if exp_type.calculation_type == 'daily' else 1
        user_limits = {}
        for u in target_users:
            user_limits[u.id] = exp_type.get_effective_budget_limit(user=u) * days

        # 2. Proportional Split Calculation
        total_budget = sum(user_limits.values())
        has_positive_limits = total_budget > 0 and all(user_limits[u.id] > 0 for u in target_users)

        user_splits = {}
        exceeded_users = []
        if not exp_type.is_km_based and has_positive_limits:
            for u in target_users:
                u_ratio = user_limits[u.id] / total_budget
                u_raw = round(self.new_voucher_amount * u_ratio, 2)
                u_lim = user_limits[u.id]
                if u_raw > u_lim:
                    exceeded_users.append((u, u_raw, u_lim))
                user_splits[u.id] = u_raw
        else:
            raw_split = round(self.new_voucher_amount / user_count, 2) if user_count > 0 else self.new_voucher_amount
            for u in target_users:
                u_lim = user_limits.get(u.id, 0.0)
                if not exp_type.is_km_based and u_lim > 0 and raw_split > u_lim:
                    exceeded_users.append((u, raw_split, u_lim))
                user_splits[u.id] = raw_split

        if not exp_type.is_km_based and exceeded_users and not self.env.context.get('voucher_budget_confirmed'):
            items_str = "".join([f"<li><strong>{u.name}</strong>: Entered share is <strong>₹{raw:,.2f}</strong>, but this voucher can only pass up to allowed budget limit of <strong>₹{lim:,.2f}</strong>.</li>" for u, raw, lim in exceeded_users])
            msg = f"""
            <div class="p-2" style="font-size:13px; color:#1e293b;">
                <p class="mb-2">The entered bill amount exceeds the allowed budget limit for the following person(s):</p>
                <ul class="mb-0 ps-3" style="color:#b91c1c;">
                    {items_str}
                </ul>
            </div>
            """
            wiz = self.env['service.ticket.voucher.budget.confirm.wizard'].create({
                'ticket_id': self.id,
                'message_html': msg,
            })
            return {
                'name': _('Budget Limit Notice'),
                'type': 'ir.actions.act_window',
                'res_model': 'service.ticket.voucher.budget.confirm.wizard',
                'res_id': wiz.id,
                'view_mode': 'form',
                'target': 'new',
            }

        km_val = self.new_voucher_total_km if exp_type.is_km_based else 0.0
        split_km = round(km_val / user_count, 2) if (user_count > 0 and exp_type.is_km_based) else km_val

        login_user = self.env.user
        bill_file = self.new_voucher_bill_file
        bill_filename = self.new_voucher_bill_filename
        if not bill_file and self.new_voucher_bill_attachment_ids:
            first_att = self.new_voucher_bill_attachment_ids[0]
            bill_file = first_att.datas
            bill_filename = first_att.name

        for u in target_users:
            dept = u.crm_department_id or (u.crm_job_id and u.crm_job_id.department_id) or False
            other_names = ", ".join([other.name for other in target_users if other.id != u.id and other.id != login_user.id])
            user_rate = self.new_voucher_rate_per_km or exp_type.get_effective_km_rate(user=u) or 0.0
            self.env['service.ticket.voucher.line'].sudo().create({
                'ticket_id': self.id,
                'expense_date': exp_date,
                'expense_date_to': self.new_voucher_date_to if (exp_type.calculation_type == 'daily') else False,
                'user_id': u.id,
                'submitted_by_user_id': login_user.id,
                'other_employee_names': other_names or '',
                'department_id': dept.id if dept else False,
                'expense_type_id': exp_type.id,
                'is_km_based': exp_type.is_km_based,
                'total_km': split_km if exp_type.is_km_based else 0.0,
                'rate_per_km': user_rate if exp_type.is_km_based else 0.0,
                'description': self.new_voucher_description or '',
                'amount': user_splits.get(u.id, 0.0),
                'bill_file': bill_file,
                'bill_filename': bill_filename,
                'bill_attachment_ids': [(6, 0, self.new_voucher_bill_attachment_ids.ids)] if self.new_voucher_bill_attachment_ids else False,
                'status': 'draft',
            })

        self.sudo().write({
            'new_voucher_date': False,
            'new_voucher_date_to': False,
            'new_voucher_expense_type_id': False,
            'new_voucher_user_ids': [(5, 0, 0)],
            'new_voucher_start_km': 0.0,
            'new_voucher_end_km': 0.0,
            'new_voucher_total_km': 0.0,
            'new_voucher_description': False,
            'new_voucher_amount': 0.0,
            'new_voucher_bill_file': False,
            'new_voucher_bill_filename': False,
            'new_voucher_bill_attachment_ids': [(5, 0, 0)],
        })
        return False

    def action_clear_voucher_fields(self):
        """ Clears all Quick Add Expense inputs instantly without reloading the entire ticket """
        self.ensure_one()
        self.sudo().write({
            'new_voucher_date': False,
            'new_voucher_date_to': False,
            'new_voucher_expense_type_id': False,
            'new_voucher_user_ids': [(5, 0, 0)],
            'new_voucher_start_km': 0.0,
            'new_voucher_end_km': 0.0,
            'new_voucher_total_km': 0.0,
            'new_voucher_description': False,
            'new_voucher_amount': 0.0,
            'new_voucher_bill_file': False,
            'new_voucher_bill_filename': False,
            'new_voucher_bill_attachment_ids': [(5, 0, 0)],
        })
        return True

    # Group Voucher Submission fields & helpers
    voucher_employee_names = fields.Char(compute='_compute_voucher_strip', string='Employees')
    voucher_employee_count = fields.Integer(compute='_compute_voucher_strip', string='Employee Count')
    voucher_draft_dates = fields.Char(compute='_compute_voucher_strip', string='Expense Dates')
    has_draft_vouchers = fields.Boolean(compute='_compute_voucher_strip', string='Has Draft Vouchers')
    show_voucher_strip = fields.Boolean(compute='_compute_voucher_strip', string='Show Voucher Strip')
    total_voucher_amount = fields.Monetary(compute='_compute_voucher_strip', string='Total Voucher Amount', currency_field='currency_id')

    @api.depends('voucher_line_ids', 'voucher_line_ids.status', 'voucher_line_ids.user_id', 'voucher_line_ids.amount', 'voucher_line_ids.expense_date')
    def _compute_voucher_strip(self):
        for rec in self:
            names = []
            dates = []
            has_draft = False
            total_amt = 0.0
            for line in rec.voucher_line_ids.filtered(lambda l: l.status == 'draft'):
                has_draft = True
                total_amt += line.amount or 0.0
                if line.user_id and line.user_id.name and line.user_id.name not in names:
                    names.append(line.user_id.name)
                if line.expense_date:
                    d_str = line.expense_date.strftime('%d/%m/%Y')
                    if d_str not in dates:
                        dates.append(d_str)
            rec.voucher_employee_names = ", ".join(names) if names else ''
            rec.voucher_employee_count = len(names)
            rec.voucher_draft_dates = ", ".join(dates) if dates else ''
            rec.has_draft_vouchers = has_draft
            rec.show_voucher_strip = has_draft
            rec.total_voucher_amount = total_amt

    def _separate_mixed_voucher_batches(self):
        """Do not split batches by expense date; vouchers are grouped by submission date."""
        pass

    def _get_voucher_approver_for_employee(self, emp):
        """Resolves the approver in strict hierarchy:
        Tier 1: Direct Reports To (Manager) e.g. Anurag (crm_manager_id or hr.employee parent_id).
        Tier 2: Department Voucher Manager from Active Voucher Configuration (voucher_manager_id).
        Tier 3: User with crm_voucher_department_ids covering this department.
        Tier 4: Global Expense Manager (company.crm_authorized_expense_manager_ids).
        Tier 5: System Administrator (last resort).
        """
        admin_user = self.env.ref('base.user_admin', raise_if_not_found=False) or self.env['res.users'].sudo().search([('id', '=', 2)], limit=1)
        if not emp:
            global_mgr = self.env.company.crm_authorized_expense_manager_ids.filtered(lambda u: u.active)[:1]
            return global_mgr or admin_user

        emp = emp.sudo()
        company = emp.company_id or self.env.company

        # ── TIER 1: Direct Reports To (Manager) e.g. Anurag ──
        emp_rec = emp.employee_id or self.env['hr.employee'].sudo().search([('user_id', '=', emp.id)], limit=1)
        direct_mgr = emp.crm_manager_id or (emp_rec.parent_id.user_id if emp_rec and emp_rec.parent_id else False)
        if direct_mgr and direct_mgr.active and direct_mgr.id != emp.id:
            return direct_mgr.sudo()

        # ── TIER 2: Department Voucher Manager from Active Voucher Settings ──
        emp_dept = (emp.crm_department_id or (emp_rec and emp_rec.department_id) or (emp.crm_job_id and emp.crm_job_id.department_id) or False)
        if emp_dept:
            emp_dept = emp_dept.sudo()
            # Only use voucher_manager_id (the configured voucher approver)
            if emp_dept.voucher_approval_active and emp_dept.voucher_manager_id:
                mgr = emp_dept.voucher_manager_id
                if mgr.active and mgr.id != emp.id:
                    return mgr

            # Check sub-departments in managing department
            managing_dept = self.env['hr.department'].sudo().search([
                ('voucher_approval_active', '=', True),
                ('voucher_manager_id', '!=', False),
                ('extra_department_ids', 'in', [emp_dept.id]),
            ], limit=1)
            if managing_dept and managing_dept.voucher_manager_id.active and managing_dept.voucher_manager_id.id != emp.id:
                return managing_dept.voucher_manager_id

            # Check manager assigned to this department
            v_user = self.env['res.users'].sudo().search([
                ('crm_voucher_department_ids', 'in', [emp_dept.id]),
                ('active', '=', True),
                ('id', '!=', emp.id),
            ], limit=1)
            if v_user:
                return v_user

        # ── TIER 3: Global Expense Manager ──
        global_mgrs = company.sudo().crm_authorized_expense_manager_ids.filtered(lambda u: u.active and u.id != emp.id)
        if global_mgrs:
            return global_mgrs[:1]

        # ── TIER 4: Administrator Direct Fallback ──
        return admin_user

    def action_submit_all_vouchers(self):
        """Submit all draft voucher lines into a single batch based on submission date."""
        self.ensure_one()
        draft_lines = self.voucher_line_ids.filtered(lambda l: l.status == 'draft')
        if not draft_lines:
            draft_lines = self.voucher_line_ids.filtered(lambda l: l.status not in ('approved', 'rejected') and not l.batch_id)
        if not draft_lines:
            return True

        primary_emp = draft_lines[0].user_id if draft_lines else False
        dept_approver = self._get_voucher_approver_for_employee(primary_emp)
        approver_uid = dept_approver.id if dept_approver else 2
        submit_date = fields.Date.context_today(self)
        ticket_name = self.ticket_id or self.name or 'TCK'

        all_names = []
        for emp in draft_lines.mapped('user_id'):
            if emp.name and emp.name not in all_names:
                all_names.append(emp.name)
        for line in draft_lines:
            if line.other_employee_names:
                for n in line.other_employee_names.split(','):
                    n_clean = n.strip()
                    if n_clean and n_clean not in all_names:
                        all_names.append(n_clean)

        combined_emp_names = ", ".join(all_names)
        submitter_user = self.env.user if self.env.user and self.env.user.id != 1 else (primary_emp or self.engineer_id)
        submitter_name = submitter_user.name if submitter_user else ''
        other_names_list = [n for n in all_names if n != submitter_name]
        other_team_names = ", ".join(other_names_list)

        # Batch name is based on submit_date
        d_str = submit_date.strftime('%d-%b-%Y')
        base_name = f"VCH/{ticket_name}/{d_str}"
        existing_count = self.env['service.ticket.voucher.batch'].search_count([
            ('ticket_id', '=', self.id),
            ('name', '=like', f"{base_name}%")
        ])
        if existing_count == 0:
            batch_name = base_name
        else:
            batch_name = f"{base_name}-{existing_count + 1:02d}"

        submitter_id = self.env.user.id if self.env.user and self.env.user.id != 1 else (primary_emp.id if primary_emp else 2)
        batch_rec = self.env['service.ticket.voucher.batch'].create({
            'ticket_id': self.id,
            'name': batch_name,
            'submission_date': submit_date,
            'user_id': primary_emp.id if primary_emp else False,
            'submitted_by_user_id': submitter_id,
            'expense_manager_id': approver_uid,
            'other_employee_names': other_team_names,
            'all_employee_names': combined_emp_names,
        })

        draft_lines.write({
            'status': 'submitted',
            'batch_id': batch_rec.id,
            'submitted_by_user_id': submitter_id,
            'expense_manager_id': approver_uid,
        })

        # Post notification to designated approver
        if dept_approver and dept_approver.partner_id:
            batch_tot = sum(draft_lines.mapped('amount'))
            exp_names = ", ".join(filter(None, set(draft_lines.mapped('expense_type_id.name'))))
            tck_name = self.ticket_id or self.name or 'Service Ticket'
            body_msg = (
                f"<b>New Voucher Approval Request</b><br/>"
                f"Voucher <b>{batch_name}</b> submitted by <b>{submitter_name}</b> for approval.<br/>"
                f"Amount: <b>₹ {batch_tot:,.2f}</b><br/>"
                f"Ticket: <b>{tck_name}</b> | Expenses: <b>{exp_names}</b>"
            )
            batch_rec.message_post(
                body=body_msg,
                subject=f"Voucher Approval: {batch_name}",
                partner_ids=[dept_approver.partner_id.id],
                message_type='notification',
                subtype_xmlid='mail.mt_comment',
            )
            try:
                self.env['bus.bus']._sendone(
                    dept_approver.partner_id,
                    'crm_notification',
                    {
                        'title': 'Voucher Approval Request',
                        'message': f"Voucher {batch_name} submitted by {submitter_name} (₹ {batch_tot:,.2f}).",
                        'model': 'service.ticket.voucher.batch',
                        'res_id': batch_rec.id,
                    }
                )
            except Exception:
                pass
            try:
                self.env['crm.notification'].create_notification(
                    user=dept_approver,
                    title='Voucher Approval Request',
                    summary=f"Voucher {batch_name} submitted by {submitter_name} (₹ {batch_tot:,.2f}).",
                    category='voucher',
                    sender=self.env.user,
                    res_model='service.ticket.voucher.batch',
                    res_id=batch_rec.id,
                    record_ref_name=batch_name,
                )
            except Exception:
                pass

        self.invalidate_recordset()
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Vouchers Submitted'),
                'message': _('Vouchers submitted for approval successfully.'),
                'type': 'success',
                'sticky': False,
            }
        }

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

    def action_rollback_to_new(self):
        for rec in self:
            if rec.submitted_voucher_line_ids:
                raise UserError(_("Cannot rollback to New because voucher(s) have already been submitted for approval."))
            if rec.draft_voucher_line_ids:
                raise UserError(_("Cannot rollback to New because %d draft expense line(s) exist. Please delete or clear them in the Voucher tab before rolling back.") % len(rec.draft_voucher_line_ids))
        self.write({'ticket_status': 'new'})

    def action_rollback_to_contacted(self):
        for rec in self:
            if rec.submitted_voucher_line_ids:
                raise UserError(_("Cannot rollback to Contacted because voucher(s) have already been submitted for approval."))
            if rec.draft_voucher_line_ids:
                raise UserError(_("Cannot rollback to Contacted because %d draft expense line(s) exist. Please delete or clear them in the Voucher tab before rolling back.") % len(rec.draft_voucher_line_ids))
        self.write({'ticket_status': 'contacted'})

    def action_rollback_to_ongoing(self):
        self.write({'ticket_status': 'ongoing'})

    def write(self, vals):
        return super(ServiceTicket, self).write(vals)

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
        default.update({
            'new_voucher_date': fields.Date.today(),
            'new_voucher_user_ids': [(5, 0, 0)],
            'new_voucher_expense_type_id': False,
            'new_voucher_amount': 0.0,
            'new_voucher_description': False,
            'new_voucher_total_km': 0.0,
            'new_voucher_start_km': 0.0,
            'new_voucher_end_km': 0.0,
            'new_voucher_bill_file': False,
            'new_voucher_bill_filename': False,
        })
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

    def _user_can(self, perm_name, default=True):
        user = self.env.user
        if user._is_admin() or user.has_group('base.group_system'):
            return True
        if user.custom_perm_override:
            val = getattr(user, perm_name, None)
            return bool(val if val is not None else default)
        if user.crm_job_id and hasattr(user.crm_job_id, perm_name):
            return bool(getattr(user.crm_job_id, perm_name))
        val = getattr(user, perm_name, None)
        return bool(val if val is not None else default)

    @api.model
    def get_views(self, views, options=None):
        res = super(ServiceTicket, self).get_views(views, options=options)
        user = self.env.user
        if not user._is_admin() and not user.has_group('base.group_system'):
            can_create = self._user_can('perm_ticket_create', False)
            can_write = self._user_can('perm_ticket_write', False)
            can_delete = self._user_can('perm_ticket_unlink', False)

            for vtype in ['form', 'list', 'tree', 'kanban']:
                if vtype in res.get('views', {}):
                    arch_str = res['views'][vtype].get('arch')
                    if arch_str:
                        doc = etree.fromstring(arch_str)
                        if not can_create:
                            doc.attrib['create'] = 'false'
                        if not can_write:
                            doc.attrib['edit'] = 'false'
                        if not can_delete:
                            doc.attrib['delete'] = 'false'
                        res['views'][vtype]['arch'] = etree.tostring(doc, encoding='unicode')
        return res

    @api.model
    def check_access_rights(self, operation, raise_exception=True):
        user = self.env.user
        if not user._is_admin() and not user.has_group('base.group_system'):
            if operation == 'create' and not self._user_can('perm_ticket_create', False):
                if raise_exception:
                    raise UserError(_("Access Denied: You do not have permission to create Service Tickets."))
                return False
            if operation == 'write' and not self._user_can('perm_ticket_write', False):
                if raise_exception:
                    raise UserError(_("Access Denied: You do not have permission to update Service Tickets."))
                return False
            if operation == 'unlink' and not self._user_can('perm_ticket_unlink', False):
                if raise_exception:
                    raise UserError(_("Access Denied: You do not have permission to delete Service Tickets."))
                return False
        return super(ServiceTicket, self).check_access_rights(operation, raise_exception=raise_exception)

    @api.model_create_multi
    def create(self, vals_list):
        user = self.env.user
        if not user._is_admin() and not user.has_group('base.group_system'):
            if not self._user_can('perm_ticket_create', False):
                raise UserError(_("Access Denied: You do not have permission to create Service Tickets."))
        return super(ServiceTicket, self).create(vals_list)

    def write(self, vals):
        user = self.env.user
        if not user._is_admin() and not user.has_group('base.group_system'):
            if not self._user_can('perm_ticket_write', False):
                raise UserError(_("Access Denied: You do not have permission to update Service Tickets."))

        cid = vals.get('complaint_type_id')
        if cid:
            ct = self.env['service.ticket.complaint.type'].browse(cid)
            name_lower = (ct.name or '').strip().lower()
            if 'breakdown' in name_lower:
                vals['complaint_type'] = 'breakdown'
            elif 'pm' in name_lower:
                vals['complaint_type'] = 'pm'
            elif 'free' in name_lower:
                vals['complaint_type'] = 'free_call'
        elif vals.get('complaint_type') and not cid:
            code = vals.get('complaint_type')
            ct = self.env['service.ticket.complaint.type'].search([
                ('name', '=ilike', 'PM' if code == 'pm' else ('Free Call' if code == 'free_call' else 'Breakdown'))
            ], limit=1)
            if ct:
                vals['complaint_type_id'] = ct.id

        res = super(ServiceTicket, self).write(vals)
        return res

    def unlink(self):
        for rec in self:
            user = self.env.user
            if not user._is_admin() and not user.has_group('base.group_system'):
                if not self._user_can('perm_ticket_unlink', False):
                    raise UserError(_("Access Denied: You do not have permission to delete Service Tickets."))
        return super(ServiceTicket, self).unlink()

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
            
class ServiceTicketExpenseType(models.Model):
    _name = 'service.ticket.expense.type'
    _description = 'Service Ticket Expense Type'
    _order = 'sequence, name'

    name = fields.Char(string='Expense Type', required=True)
    sequence = fields.Integer(string='Sequence', default=10)
    is_km_based = fields.Boolean(string='Calculate by KM', default=False)
    km_rate = fields.Float(string='Rate per KM (₹)', default=0.0)
    budget_limit = fields.Float(string='Limit Amount (₹)', default=0.0)
    calculation_type = fields.Selection([
        ('daily', 'Per Day'),
        ('fixed', 'Fixed (Per Visit)'),
        ('km', '-'),
    ], string='Calculation Type', default='daily')

    @api.onchange('is_km_based')
    def _onchange_is_km_based(self):
        for rec in self:
            if rec.is_km_based:
                rec.calculation_type = 'km'
                rec.budget_limit_display = '-'
                rec.km_rate_display = f"{rec.km_rate:,.2f}" if rec.km_rate else "0.00"
            else:
                if rec.calculation_type == 'km' or not rec.calculation_type:
                    rec.calculation_type = 'daily'
                rec.km_rate_display = '-'
                if rec.budget_limit:
                    suffix = " / Day" if rec.calculation_type == 'daily' else " / Visit"
                    rec.budget_limit_display = f"{rec.budget_limit:,.2f}{suffix}"
                else:
                    rec.budget_limit_display = "0.00"

    @api.onchange('calculation_type')
    def _onchange_calculation_type(self):
        for rec in self:
            if not rec.is_km_based and rec.budget_limit:
                suffix = " / Day" if rec.calculation_type == 'daily' else " / Visit"
                rec.budget_limit_display = f"{rec.budget_limit:,.2f}{suffix}"

    def write(self, vals):
        if 'is_km_based' in vals:
            if vals['is_km_based']:
                vals['calculation_type'] = 'km'
            else:
                if vals.get('calculation_type') == 'km' or not vals.get('calculation_type'):
                    vals['calculation_type'] = 'daily'
        return super().write(vals)

    def init(self):
        super().init()
        self.env.cr.execute("""
            UPDATE service_ticket_expense_type
            SET calculation_type = 'km'
            WHERE is_km_based = TRUE AND (calculation_type IS NULL OR calculation_type != 'km');
            UPDATE service_ticket_expense_type
            SET calculation_type = 'daily'
            WHERE is_km_based = FALSE AND calculation_type = 'km';
        """)
    budget_cycle = fields.Selection([
        ('per_ticket', 'Per Visit / Ticket'),
        ('monthly', 'Monthly'),
    ], string='Reset Frequency', default='per_ticket')
    job_ids = fields.Many2many(
        'hr.job',
        'expense_type_job_rel',
        'expense_type_id',
        'job_id',
        string='Allowed Job Positions',
        help='Select one or multiple job positions allowed to claim this expense. Leave empty to allow all positions.'
    )
    active = fields.Boolean(string='Active', default=True)
    budget_limit_display = fields.Char(
        string='Limit Per Visit (₹)',
        compute='_compute_budget_limit_display',
        inverse='_inverse_budget_limit_display',
    )
    km_rate_display = fields.Char(
        string='Rate / KM (₹)',
        compute='_compute_km_rate_display',
        inverse='_inverse_km_rate_display',
    )

    @api.depends('budget_limit', 'is_km_based', 'calculation_type')
    def _compute_budget_limit_display(self):
        for rec in self:
            if rec.is_km_based:
                rec.budget_limit_display = '-'
            elif rec.budget_limit:
                suffix = " / Day" if rec.calculation_type == 'daily' else " / Visit"
                rec.budget_limit_display = f"{rec.budget_limit:,.2f}{suffix}"
            else:
                rec.budget_limit_display = "0.00"

    def _inverse_budget_limit_display(self):
        for rec in self:
            if not rec.is_km_based and rec.budget_limit_display:
                val = rec.budget_limit_display.strip()
                if val != '-':
                    clean = val.replace(',', '').replace('₹', '').replace('/ Day', '').replace('/ Visit', '').replace('/Day', '').replace('/Visit', '').strip()
                    try:
                        rec.budget_limit = float(clean)
                    except ValueError:
                        pass

    @api.depends('km_rate', 'is_km_based')
    def _compute_km_rate_display(self):
        for rec in self:
            if not rec.is_km_based:
                rec.km_rate_display = '-'
            else:
                rec.km_rate_display = f"{rec.km_rate:,.2f}" if rec.km_rate else "0.00"

    def _inverse_km_rate_display(self):
        for rec in self:
            if rec.is_km_based and rec.km_rate_display:
                val = rec.km_rate_display.strip()
                if val != '-':
                    clean = val.replace(',', '').replace('₹', '').strip()
                    try:
                        rec.km_rate = float(clean)
                    except ValueError:
                        pass

    limit_rule_ids = fields.One2many(
        'service.ticket.expense.limit.rule',
        'expense_type_id',
        string='Position Budget Rules'
    )

    def action_open_settings(self):
        self.ensure_one()
        # Clean up any leftover blank rules with no job positions selected
        empty_rules = self.limit_rule_ids.filtered(lambda r: not r.job_ids)
        if empty_rules:
            empty_rules.unlink()
        view_id = self.env.ref('custom_crm_extended.view_service_ticket_expense_type_limit_form', raise_if_not_found=False)
        return {
            'name': _('Position-Wise Budget Limits: %s') % (self.name or ''),
            'type': 'ir.actions.act_window',
            'res_model': 'service.ticket.expense.type',
            'res_id': self.id,
            'view_mode': 'form',
            'view_id': view_id.id if view_id else False,
            'target': 'new',
        }

    @api.model
    def _get_user_job_positions(self, user=None, job_id=None):
        user = user or self.env.user
        job_ids = set()
        if job_id:
            job_ids.add(job_id)
        if not user:
            return job_ids

        # 1. Direct crm_job_id on user
        if getattr(user, 'crm_job_id', None) and user.crm_job_id:
            job_ids.add(user.crm_job_id.id)

        # Extract genuine integer ID to avoid passing NewId to SQL domain queries
        real_uid = user._origin.id if getattr(user, '_origin', None) and user._origin.id else (user.id if isinstance(user.id, int) else False)

        if real_uid:
            # 2. Linked employee records via user_id, work_email, or name
            emps = self.env['hr.employee'].sudo().search([
                '|', '|',
                ('user_id', '=', real_uid),
                ('work_email', '=', user.email or ''),
                ('name', '=ilike', user.name or '')
            ])
            if hasattr(user, 'employee_id') and user.employee_id:
                emps |= user.employee_id.sudo()
            if hasattr(user, 'employee_ids'):
                emps |= user.employee_ids.sudo()

            for emp in emps:
                if emp.job_id:
                    job_ids.add(emp.job_id.id)
                if emp.job_title:
                    m_jobs = self.env['hr.job'].sudo().search([('name', '=ilike', emp.job_title.strip())])
                    job_ids.update(m_jobs.ids)

            # 3. Direct assignment on hr.job via stored user_ids relation
            assigned_jobs = self.env['hr.job'].sudo().search([('user_ids', 'in', [real_uid])])
            job_ids.update(assigned_jobs.ids)

            # 4. Department management manager roles
            managed_depts = self.env['hr.department'].sudo().search([
                '|', ('manager_user_id', '=', real_uid),
                ('manager_id.user_id', '=', real_uid)
            ])
            for dept in managed_depts:
                mgr_jobs = self.env['hr.job'].sudo().search([
                    ('department_id', '=', dept.id),
                    ('is_manager_role', '=', True)
                ])
                job_ids.update(mgr_jobs.ids)
                if dept.manager_id and dept.manager_id.job_id:
                    job_ids.add(dept.manager_id.job_id.id)
        return job_ids

    def get_effective_budget_limit(self, user=None, job_id=None):
        """Returns the custom limit for the given user's job position if active rule exists, else global budget_limit."""
        self.ensure_one()
        user_job_ids = self._get_user_job_positions(user=user, job_id=job_id)
        matching_rules = self.limit_rule_ids.filtered(lambda r: r.active and any(j.id in user_job_ids for j in r.job_ids))
        if matching_rules:
            return max(matching_rules.mapped('budget_limit'))
        return self.budget_limit

    def get_effective_km_rate(self, user=None, job_id=None):
        """Returns the custom rate per KM for the given user's job position if active rule exists, else global km_rate."""
        self.ensure_one()
        user_job_ids = self._get_user_job_positions(user=user, job_id=job_id)
        matching_rules = self.limit_rule_ids.filtered(lambda r: r.active and any(j.id in user_job_ids for j in r.job_ids))
        if matching_rules:
            return max(matching_rules.mapped('km_rate'))
        return self.km_rate


class ServiceTicketExpenseLimitRule(models.Model):
    _name = 'service.ticket.expense.limit.rule'
    _description = 'Position-Wise Expense Budget Limit Rule'
    _order = 'id asc'

    expense_type_id = fields.Many2one(
        'service.ticket.expense.type',
        string='Expense Type',
        required=True,
        ondelete='cascade'
    )
    is_km_based = fields.Boolean(
        related='expense_type_id.is_km_based',
        string='Calculate by KM',
        readonly=True
    )
    available_job_ids = fields.Many2many(
        'hr.job',
        compute='_compute_available_job_ids',
        string='Available Job Positions'
    )
    job_ids = fields.Many2many(
        'hr.job',
        'expense_rule_job_rel',
        'rule_id',
        'job_id',
        string='Job Positions (Multi-Select)',
        required=True,
        help='Select one or multiple job positions for this budget limit rule.'
    )
    budget_limit = fields.Float(string='Budget Limit / Visit (₹)', default=0.0)
    calculation_type = fields.Selection(
        related='expense_type_id.calculation_type',
        string='Budget Type',
        readonly=True,
    )
    km_rate = fields.Float(string='Rate / KM (₹)', default=0.0)
    dummy_dash = fields.Char(string='-', default='-', readonly=True)
    active = fields.Boolean(string='Active', default=True)

    @api.depends('expense_type_id', 'expense_type_id.job_ids')
    def _compute_available_job_ids(self):
        all_jobs = self.env['hr.job'].search([])
        for rec in self:
            if rec.expense_type_id and rec.expense_type_id.job_ids:
                rec.available_job_ids = rec.expense_type_id.job_ids
            else:
                rec.available_job_ids = all_jobs

    @api.constrains('job_ids', 'expense_type_id')
    def _check_job_ids_in_allowed(self):
        for rec in self:
            if rec.expense_type_id and rec.expense_type_id.job_ids and rec.job_ids:
                invalid_jobs = rec.job_ids - rec.expense_type_id.job_ids
                if invalid_jobs:
                    invalid_names = ", ".join(invalid_jobs.mapped('name'))
                    allowed_names = ", ".join(rec.expense_type_id.job_ids.mapped('name'))
                    raise ValidationError(
                        _("Job Position(s) '%(invalid)s' cannot be configured for Expense Type '%(type)s'.\n\n"
                          "This expense type is restricted only to Allowed Job Position(s): %(allowed)s.\n"
                          "Please select only from the allowed positions, or add '%(invalid)s' to 'Allowed Job Positions' in the main table first.")
                        % {
                            'invalid': invalid_names,
                            'type': rec.expense_type_id.name,
                            'allowed': allowed_names,
                        }
                    )

class ServiceTicketVoucherLine(models.Model):
    _name = 'service.ticket.voucher.line'
    _description = 'Service Ticket Voucher Line'
    _order = 'id desc'

    active = fields.Boolean(string='Active', default=True)
    ticket_id = fields.Many2one('service.ticket', string='Service Ticket', ondelete='cascade', required=False)
    expense_date = fields.Date(string='Date', default=fields.Date.context_today, required=True, index=True)
    user_id = fields.Many2one('res.users', string='Employee', required=False, default=lambda self: self.env.user)
    department_id = fields.Many2one('hr.department', string='Department')
    expense_type_id = fields.Many2one('service.ticket.expense.type', string='Expense Type', required=True)
    allowed_expense_type_ids = fields.Many2many(
        'service.ticket.expense.type',
        compute='_compute_allowed_expense_type_ids',
        string='Allowed Expense Types',
    )
    is_km_based = fields.Boolean(related='expense_type_id.is_km_based', string='KM Based', store=True, readonly=True)

    @api.depends('user_id')
    def _compute_allowed_expense_type_ids(self):
        all_types = self.env['service.ticket.expense.type'].search([('active', '=', True)])
        for rec in self:
            u = rec.user_id or self.env.user
            allowed = all_types.filtered(
                lambda t: not t.job_ids or any(j.id in t._get_user_job_positions(user=u) for j in t.job_ids)
            )
            rec.allowed_expense_type_ids = allowed

    @api.constrains('expense_type_id', 'user_id')
    def _check_expense_type_job_permission(self):
        for rec in self:
            if rec.expense_type_id and rec.expense_type_id.job_ids:
                u = rec.user_id or self.env.user
                u_jobs = rec.expense_type_id._get_user_job_positions(user=u)
                if not any(j.id in u_jobs for j in rec.expense_type_id.job_ids):
                    allowed_names = ", ".join(rec.expense_type_id.job_ids.mapped('name'))
                    raise ValidationError(
                        _("Expense Type '%(type)s' is restricted to Job Position(s): %(jobs)s. Employee '%(user)s' is not authorized to claim this expense.")
                        % {'type': rec.expense_type_id.name, 'jobs': allowed_names, 'user': u.name}
                    )

    @api.constrains('expense_date')
    def _check_expense_date_no_future(self):
        today = fields.Date.context_today(self)
        for rec in self:
            if rec.expense_date and rec.expense_date > today:
                raise ValidationError(_("Expense Date (%s) cannot be in the future.") % rec.expense_date.strftime('%d/%m/%Y'))

    @api.depends('ticket_id.engineer_id', 'ticket_id.create_uid', 'batch_id.user_id')
    def _compute_user_id(self):
        for rec in self:
            if not rec.user_id:
                rec.user_id = (rec.ticket_id.engineer_id or rec.ticket_id.create_uid) if rec.ticket_id else (rec.batch_id.user_id if rec.batch_id and rec.batch_id.user_id else self.env.user)
    total_km = fields.Float(string='Total KM')
    rate_per_km = fields.Float(string='Rate/KM (₹)')
    description = fields.Char(string='Description', placeholder='Enter description...')
    expense_date_to = fields.Date(string='To Date')
    days_count = fields.Integer(string='Days', compute='_compute_days_count', store=True)

    @api.depends('expense_date', 'expense_date_to', 'expense_type_id.calculation_type')
    def _compute_days_count(self):
        for rec in self:
            if rec.expense_type_id and rec.expense_type_id.calculation_type == 'daily' and rec.expense_date and rec.expense_date_to and rec.expense_date_to >= rec.expense_date:
                rec.days_count = (rec.expense_date_to - rec.expense_date).days + 1
            else:
                rec.days_count = 1

    currency_id = fields.Many2one('res.currency', string='Currency', compute='_compute_currency_id', store=True, readonly=False)

    @api.depends('ticket_id.currency_id', 'batch_id.currency_id')
    def _compute_currency_id(self):
        for rec in self:
            rec.currency_id = rec.ticket_id.currency_id if rec.ticket_id else (rec.batch_id.currency_id if rec.batch_id and rec.batch_id.currency_id else self.env.company.currency_id)

    amount = fields.Monetary(string='Submitted Amount', currency_field='currency_id')
    approved_amount = fields.Monetary(string='Approved Amount', currency_field='currency_id', compute='_compute_approved_amount')

    @api.depends('status', 'amount', 'allowed_budget_limit')
    def _compute_approved_amount(self):
        for rec in self:
            if rec.status in ('approved', 'partially_approved', 'paid'):
                if rec.allowed_budget_limit and rec.allowed_budget_limit > 0 and (rec.amount or 0.0) > rec.allowed_budget_limit:
                    rec.approved_amount = rec.allowed_budget_limit
                else:
                    rec.approved_amount = rec.amount or 0.0
            else:
                rec.approved_amount = 0.0
    is_over_budget = fields.Boolean(compute='_compute_budget_status', string='Is Over Budget', store=True)
    allowed_budget_limit = fields.Float(compute='_compute_budget_status', string='Allowed Limit', store=True)
    over_budget_badge_html = fields.Html(compute='_compute_budget_status', string='Budget Status', sanitize=False)

    @api.depends('amount', 'expense_type_id', 'user_id', 'is_km_based', 'days_count')
    def _compute_budget_status(self):
        for rec in self:
            if rec.expense_type_id and not rec.is_km_based and rec.user_id:
                base_limit = rec.expense_type_id.get_effective_budget_limit(user=rec.user_id)
                days = rec.days_count or 1 if rec.expense_type_id.calculation_type == 'daily' else 1
                limit = base_limit * days
                rec.allowed_budget_limit = limit
                if limit > 0 and rec.amount > limit:
                    rec.is_over_budget = True
                    rec.over_budget_badge_html = f'<span class="badge py-1 px-2" style="background:#fee2e2; color:#dc2626; border:1px solid #fca5a5; font-size:11px; font-weight:600; border-radius:4px; white-space:nowrap;" title="Exceeds allowed budget of ₹{limit:,.2f}">Max: ₹{limit:,.2f}</span>'
                else:
                    rec.is_over_budget = False
                    rec.over_budget_badge_html = False
            else:
                rec.allowed_budget_limit = 0.0
                rec.is_over_budget = False
                rec.over_budget_badge_html = False

    @api.onchange('expense_type_id')
    def _onchange_voucher_line_expense_type(self):
        if self.expense_type_id:
            self.is_km_based = self.expense_type_id.is_km_based
            if self.is_km_based:
                self.rate_per_km = self.expense_type_id.km_rate or 0.0
                if self.total_km and self.rate_per_km:
                    self.amount = self.total_km * self.rate_per_km

    @api.onchange('total_km', 'rate_per_km')
    def _onchange_voucher_line_km_calc(self):
        if self.is_km_based and self.total_km and self.rate_per_km:
            self.amount = self.total_km * self.rate_per_km
    bill_file = fields.Binary(string='Upload Bill', required=False)
    bill_filename = fields.Char(string='File Name')
    bill_attachment_ids = fields.Many2many(
        'ir.attachment',
        'service_ticket_voucher_line_attachment_rel',
        'line_id',
        'attachment_id',
        string='Bills & Receipts',
    )
    bill_count = fields.Integer(compute='_compute_bill_count', string='Bills')

    @api.depends('bill_file', 'bill_attachment_ids')
    def _compute_bill_count(self):
        for rec in self:
            cnt = len(rec.bill_attachment_ids)
            if not cnt and rec.bill_file:
                cnt = 1
            rec.bill_count = cnt

    bill_preview = fields.Binary(related='bill_file', string='Bill Preview', readonly=True)
    bill_preview_html = fields.Html(compute='_compute_bill_preview_html', string='Bill Preview HTML', sanitize=False)

    @api.depends('bill_file', 'bill_filename', 'bill_attachment_ids')
    def _compute_bill_preview_html(self):
        for rec in self:
            items = []
            if rec.bill_attachment_ids:
                for att in rec.bill_attachment_ids:
                    fname = (att.name or 'receipt').lower()
                    ext = fname.split('.')[-1] if '.' in fname else ''
                    items.append({
                        'name': att.name or 'Receipt',
                        'ext': ext,
                        'url': f"/web/content/{att.id}?download=false",
                        'download_url': f"/web/content/{att.id}?download=true",
                    })
            elif rec.bill_file:
                fname = (rec.bill_filename or 'receipt').lower()
                ext = fname.split('.')[-1] if '.' in fname else ''
                items.append({
                    'name': rec.bill_filename or 'Receipt',
                    'ext': ext,
                    'url': f"/web/content?model=service.ticket.voucher.line&id={rec.id}&field=bill_file&filename={rec.bill_filename or 'receipt'}&download=false",
                    'download_url': f"/web/content?model=service.ticket.voucher.line&id={rec.id}&field=bill_file&filename={rec.bill_filename or 'receipt'}&download=true",
                })

            if not items:
                rec.bill_preview_html = '<div class="text-center p-4 text-muted">No attachment uploaded.</div>'
                continue

            total_bills = len(items)
            slides_html = []
            for idx, itm in enumerate(items):
                display_style = "display: block;" if idx == 0 else "display: none;"
                if itm['ext'] in ('png', 'jpg', 'jpeg', 'webp', 'gif', 'svg'):
                    content = f'<img src="{itm["url"]}" class="img-fluid rounded" style="max-height: 76vh; max-width: 100%; object-fit: contain; background: #fff;" alt="Bill Image"/>'
                elif itm['ext'] == 'pdf':
                    content = f'<iframe src="{itm["url"]}#toolbar=1" style="width: 100%; height: 78vh; border: none;" title="Bill PDF"></iframe>'
                else:
                    content = f'<div class="text-center p-4"><p class="text-muted">File: {itm["name"]}</p><a href="{itm["download_url"]}" class="btn btn-primary" download>Download File</a></div>'

                slides_html.append(f'''
                    <div id="bill_slide_{rec.id}_{idx}" class="bill-slide-{rec.id}" style="{display_style} text-align: center; width: 100%;">
                        {content}
                    </div>
                ''')

            # Show navigation arrows ONLY if multiple bills exist
            nav_buttons = ""
            if total_bills > 1:
                nav_buttons = f'''
                    <div class="d-flex align-items-center gap-2">
                        <button type="button" class="btn btn-sm btn-outline-primary fw-bold px-3 py-1 shadow-sm" onclick="prevBill_{rec.id}()">&#8592; Prev</button>
                        <span class="badge bg-light text-dark border px-2 py-1" id="bill_counter_{rec.id}">1 of {total_bills}</span>
                        <button type="button" class="btn btn-sm btn-outline-primary fw-bold px-3 py-1 shadow-sm" onclick="nextBill_{rec.id}()">Next &#8594;</button>
                    </div>
                '''

            first_name = items[0]['name']
            all_names_js = str([it['name'] for it in items]).replace("'", '"')

            rec.bill_preview_html = f'''
            <div class="bill-preview-wrapper p-0 m-0" style="background: transparent; border: none; width: 100%;">
                {"<div class='d-flex align-items-center justify-content-end p-2 mb-2 bg-white rounded border shadow-sm'>" + nav_buttons + "</div>" if nav_buttons else ""}

                <!-- Slide Content flush to top with no extra strip or blank gaps -->
                <div class="d-flex align-items-center justify-content-center p-0 m-0" style="width: 100%; height: 78vh; overflow: hidden; background: #ffffff;">
                    {"".join(slides_html)}
                </div>
            </div>

            <script type="text/javascript">
                (function() {{
                    var total = {total_bills};
                    if (total &lt;= 1) return;
                    var curIdx = 0;
                    var names = {all_names_js};

                    function updateSlide(idx) {{
                        for (var i = 0; i &lt; total; i++) {{
                            var el = document.getElementById("bill_slide_{rec.id}_" + i);
                            if (el) el.style.display = (i === idx) ? "block" : "none";
                        }}
                        var headEl = document.getElementById("bill_heading_{rec.id}");
                        if (headEl) headEl.innerText = names[idx];
                        var countEl = document.getElementById("bill_counter_{rec.id}");
                        if (countEl) countEl.innerText = (idx + 1) + " of " + total;
                    }}

                    window.prevBill_{rec.id} = function() {{
                        curIdx = (curIdx - 1 + total) % total;
                        updateSlide(curIdx);
                    }};

                    window.nextBill_{rec.id} = function() {{
                        curIdx = (curIdx + 1) % total;
                        updateSlide(curIdx);
                    }};
                }})();
            </script>
            '''
    status = fields.Selection([
        ('draft', 'Draft'),
        ('submitted', 'Submitted'),
        ('partially_approved', 'Partially Approved'),
        ('approved', 'Approved'),
        ('partially_paid', 'Partially Paid'),
        ('paid', 'Paid'),
        ('rejected', 'Rejected'),
    ], string='Status', default='draft', required=True)

    voucher_status = fields.Selection([
        ('draft', 'Draft'),
        ('submitted', 'Submitted'),
        ('partially_approved', 'Partially Approved'),
        ('approved', 'Approved'),
        ('partially_paid', 'Partially Paid'),
        ('paid', 'Paid'),
        ('rejected', 'Rejected'),
    ], string='Voucher Status', compute='_compute_voucher_status')

    @api.depends('batch_id.status', 'status')
    def _compute_voucher_status(self):
        for rec in self:
            if rec.batch_id:
                rec.voucher_status = rec.batch_id.status
            else:
                rec.voucher_status = rec.status

    @api.model
    def _search(self, domain, offset=0, limit=None, order=None):
        """Draft voucher lines are private to the employee/creator."""
        user = self.env.user
        extra_domain = [
            '|',
            ('user_id', '=', user.id),
            '|',
            ('submitted_by_user_id', '=', user.id),
            ('status', '!=', 'draft'),
        ]
        domain = expression.AND([domain, extra_domain])
        return super(ServiceTicketVoucherLine, self)._search(domain, offset=offset, limit=limit, order=order)

    batch_id = fields.Many2one('service.ticket.voucher.batch', string='Submission Batch', ondelete='cascade', index=True)
    voucher_id = fields.Char(related='batch_id.name', string='Voucher ID', store=True, readonly=True)
    name = fields.Char(related='voucher_id', string='Voucher ID', readonly=True)
    batch_key = fields.Char(string='Batch Key', index=True)
    submitted_by_user_id = fields.Many2one(
        'res.users',
        string='Submitted By',
        compute='_compute_submitted_by_user_id',
        store=True,
        readonly=False,
    )
    

    @api.depends('create_uid', 'user_id')
    def _compute_submitted_by_user_id(self):
        for rec in self:
            if not rec.submitted_by_user_id or rec.submitted_by_user_id.id == 1:
                rec.submitted_by_user_id = rec.create_uid if rec.create_uid and rec.create_uid.id != 1 else rec.user_id

    other_employee_names = fields.Char(
        string='Other Employees',
        compute='_compute_other_employee_names',
        store=True,
        readonly=False,
    )

    @api.depends('batch_id.other_employee_names', 'batch_id.submitted_by_user_id', 'batch_id.line_ids.user_id.name', 'user_id')
    def _compute_other_employee_names(self):
        for rec in self:
            if rec.batch_id:
                rec.other_employee_names = rec.batch_id.other_employee_names or ""
            elif not rec.other_employee_names:
                rec.other_employee_names = ""
    ticket_voucher_line_ids = fields.Many2many(
        'service.ticket.voucher.line',
        compute='_compute_ticket_voucher_line_ids',
        string='Voucher Expenses',
    )
    voucher_employee_names = fields.Char(compute='_compute_voucher_employee_names', string='Employees', readonly=True)

    @api.depends('ticket_id.voucher_employee_names', 'batch_id.all_employee_names')
    def _compute_voucher_employee_names(self):
        for rec in self:
            rec.voucher_employee_names = (rec.ticket_id.voucher_employee_names if rec.ticket_id else (rec.batch_id.all_employee_names if rec.batch_id else '')) or ''

    @api.depends('batch_id', 'batch_id.line_ids', 'voucher_id', 'ticket_id')
    def _compute_ticket_voucher_line_ids(self):
        for rec in self:
            if rec.batch_id and rec.batch_id.line_ids:
                rec.ticket_voucher_line_ids = rec.batch_id.line_ids
            elif rec.voucher_id:
                rec.ticket_voucher_line_ids = self.search([
                    ('ticket_id', '=', rec.ticket_id.id),
                    ('voucher_id', '=', rec.voucher_id),
                    ('status', '!=', 'draft'),
                ])
            else:
                rec.ticket_voucher_line_ids = rec

    def action_submit_line(self): 
        """Submit this single draft voucher line."""
        for rec in self:
            if rec.status == 'draft':
                dept_approver = rec.ticket_id._get_voucher_approver_for_employee(rec.user_id) if rec.ticket_id else self.env['service.ticket']._get_voucher_approver_for_employee(rec.user_id)
                approver_uid = dept_approver.id if dept_approver else 2
                today_str = fields.Date.today().strftime('%d/%m/%Y')
                batch_name = f"VCH/{rec.ticket_id.ticket_id or rec.ticket_id.name}/{today_str}"
                batch_rec = self.env['service.ticket.voucher.batch'].create({
                    'ticket_id': rec.ticket_id.id,
                    'user_id': rec.user_id.id,
                    'submitted_by_user_id': self.env.user.id if self.env.user and self.env.user.id != 1 else (rec.user_id.id or 2),
                    'expense_manager_id': approver_uid,
                    'other_employee_names': rec.other_employee_names or '',
                    'all_employee_names': rec.user_id.name or '',
                    'name': batch_name,
                })
                rec.write({
                    'status': 'submitted',
                    'batch_id': batch_rec.id,
                    'expense_manager_id': approver_uid,
                })
        return True

    def action_open_batch_detail(self):
        self.ensure_one()
        domain = [('batch_id', '=', self.batch_id.id)] if self.batch_id else [('id', '=', self.id)]
        return {
            'name': _('Expense Details - %s') % (self.user_id.name or 'Employee'),
            'type': 'ir.actions.act_window',
            'res_model': 'service.ticket.voucher.line',
            'view_mode': 'list,form',
            'view_id': self.env.ref('custom_crm_extended.view_service_ticket_voucher_line_detail_tree').id,
            'domain': domain,
            'target': 'current',
        }

    expense_manager_id = fields.Many2one(
        'res.users',
        string='Approver',
        compute='_compute_expense_manager_id',
        store=True,
        readonly=False,
    )

    @api.depends('batch_id.expense_manager_id', 'user_id')
    def _compute_expense_manager_id(self):
        for rec in self:
            if rec.batch_id and rec.batch_id.expense_manager_id:
                rec.expense_manager_id = rec.batch_id.expense_manager_id
            elif rec.user_id:
                approver = self.env['service.ticket']._get_voucher_approver_for_employee(rec.user_id)
                rec.expense_manager_id = approver.id if approver else False
    reject_reason = fields.Char(string='Rejection Reason')

    def _check_voucher_approval_access(self):
        user = self.env.user
        for line in self:
            # Self-approval restriction: Cannot approve own vouchers unless Admin
            if (line.user_id.id == user.id or (line.submitted_by_user_id and line.submitted_by_user_id.id == user.id)):
                if not (user._is_admin() or user.has_group('base.group_system')):
                    raise ValidationError(_("Access Denied: You cannot approve your own expense voucher. It must be approved by a Global Expense Manager or Administrator."))

        if user._is_admin() or user.has_group('base.group_system'):
            return True
        company = self.env.company
        if user.id in company.sudo().crm_authorized_expense_manager_ids.ids:
            return True
        for line in self:
            dept = line.department_id or (line.user_id and line.user_id.crm_department_id)
            if not dept:
                raise ValidationError(_("Access Denied: Only System Administrators and Global Expense Managers can approve vouchers without an assigned department."))
            eff_approver = dept.voucher_manager_id or dept.manager_user_id
            is_direct_mgr = (eff_approver and eff_approver.id == user.id and dept.voucher_approval_active)
            is_extra_mgr = bool(self.env['hr.department'].sudo().search([
                ('voucher_approval_active', '=', True),
                ('extra_department_ids', 'in', [dept.id]),
                '|',
                ('voucher_manager_id', '=', user.id),
                ('manager_user_id', '=', user.id),
            ], limit=1))
            if not (is_direct_mgr or is_extra_mgr):
                raise ValidationError(_("Access Denied: You are only authorized to approve vouchers for your assigned department (%s).") % (dept.name or ''))
        return True



    can_approve = fields.Boolean(compute='_compute_can_approve', string='Can Approve')

    @api.depends_context('uid')
    def _compute_can_approve(self):
        user = self.env.user
        is_admin_or_global = user._is_admin() or user.has_group('base.group_system') or (user.id in self.env.company.sudo().crm_authorized_expense_manager_ids.ids)
        managed_depts = self.env['hr.department'].sudo().search([
            ('voucher_approval_active', '=', True),
            '|',
            ('voucher_manager_id', '=', user.id),
            ('manager_user_id', '=', user.id),
        ])
        for rec in self:
            if is_admin_or_global:
                rec.can_approve = True
            elif managed_depts:
                # Manager cannot approve their own expense
                is_own = (rec.user_id.id == user.id or (rec.submitted_by_user_id and rec.submitted_by_user_id.id == user.id))
                rec.can_approve = not is_own
            else:
                rec.can_approve = False

    def action_approve(self):
        self._check_voucher_approval_access()
        # If over budget and not confirmed, prompt manager with wizard showing max allowed budget
        if not self.env.context.get('budget_approved_confirmed'):
            over_budget_lines = []
            for rec in self:
                max_amt = rec.allowed_budget_limit or 0.0
                if max_amt > 0 and (rec.amount or 0.0) > max_amt:
                    over_budget_lines.append(rec)
            if over_budget_lines:
                msg = "<div class='p-2'><p class='mb-2'>The following expense exceeds the allowed budget:</p><ul class='mb-3'>"
                for l in over_budget_lines:
                    msg += f"<li><b>{l.user_id.name or 'Employee'}</b> ({l.expense_type_id.name or 'Expense'}): Entered <b>₹ {l.amount:,.2f}</b>, Allowed Budget Limit is <b>₹ {l.allowed_budget_limit:,.2f}</b>.</li>"
                total_allowed = sum(l.allowed_budget_limit for l in over_budget_lines)
                msg += f"</ul><p class='text-muted small mb-0'>Approving will pass only the allowed budget amount (₹ {total_allowed:,.2f}) instead of the full over-budget amount. Do you wish to continue?</p></div>"
                view = self.env.ref('custom_crm_extended.view_service_ticket_voucher_budget_confirm_wizard_form', raise_if_not_found=False)
                return {
                    'name': _('Over Budget Expense Approval Confirmation'),
                    'type': 'ir.actions.act_window',
                    'res_model': 'service.ticket.voucher.budget.confirm.wizard',
                    'view_mode': 'form',
                    'view_id': view.id if view else False,
                    'target': 'new',
                    'context': {
                        'default_message_html': msg,
                        'voucher_approval_target_ids': self.ids,
                    },
                }

        for rec in self:
            approved_val = rec.amount or 0.0
            if rec.allowed_budget_limit and rec.allowed_budget_limit > 0 and (rec.amount or 0.0) > rec.allowed_budget_limit:
                approved_val = rec.allowed_budget_limit
            vals = {
                'status': 'approved',
                'approved_amount': approved_val,
                'expense_manager_id': self.env.user.id,
                'reject_reason': False,
            }
            rec.sudo().write(vals)
            if rec.batch_id:
                rec.batch_id._compute_status()
        return {'type': 'ir.actions.client', 'tag': 'reload'}

    def action_approve_all(self):
        self._check_voucher_approval_access()
        # If over budget and not confirmed, prompt manager with wizard
        if not self.env.context.get('budget_approved_confirmed'):
            all_lines = self.batch_id.line_ids if self.batch_id else self
            over_budget_lines = all_lines.filtered(lambda l: (l.allowed_budget_limit or 0.0) > 0 and (l.amount or 0.0) > l.allowed_budget_limit)
            if over_budget_lines:
                msg = "<div class='p-2'><p class='mb-2'>The following expense(s) exceed the allowed budget:</p><ul class='mb-3'>"
                for l in over_budget_lines:
                    msg += f"<li><b>{l.user_id.name or 'Employee'}</b> ({l.expense_type_id.name or 'Expense'}): Entered <b>₹ {l.amount:,.2f}</b>, Allowed Budget Limit is <b>₹ {l.allowed_budget_limit:,.2f}</b>.</li>"
                msg += "</ul><p class='text-muted small mb-0'>Approving will pass only the allowed budget amount instead of over-budget amounts. Do you wish to continue?</p></div>"
                view = self.env.ref('custom_crm_extended.view_service_ticket_voucher_budget_confirm_wizard_form', raise_if_not_found=False)
                return {
                    'name': _('Over Budget Expense Approval Confirmation'),
                    'type': 'ir.actions.act_window',
                    'res_model': 'service.ticket.voucher.budget.confirm.wizard',
                    'view_mode': 'form',
                    'view_id': view.id if view else False,
                    'target': 'new',
                    'context': {
                        'default_message_html': msg,
                        'voucher_approval_all_batch_id': self.batch_id.id if self.batch_id else False,
                    },
                }

        for rec in self:
            target = rec.batch_id.line_ids if rec.batch_id else rec
            for t_line in target:
                appr_val = t_line.amount or 0.0
                if t_line.allowed_budget_limit and t_line.allowed_budget_limit > 0 and (t_line.amount or 0.0) > t_line.allowed_budget_limit:
                    appr_val = t_line.allowed_budget_limit
                vals = {
                    'status': 'approved',
                    'approved_amount': appr_val,
                    'expense_manager_id': self.env.user.id,
                    'reject_reason': False,
                }
                t_line.sudo().write(vals)
            if rec.batch_id:
                rec.batch_id.sudo().write({'expense_manager_id': self.env.user.id})
                rec.batch_id._compute_status()
                submitter = rec.batch_id.submitted_by_user_id or rec.batch_id.user_id
                if submitter and submitter.partner_id:
                    rec.batch_id.message_post(
                        body=f"<b>Voucher Approved</b><br/>"
                             f"Your voucher <b>{rec.batch_id.name}</b> has been approved by <b>{self.env.user.name}</b>.",
                        subject=f"Voucher Approved: {rec.batch_id.name}",
                        partner_ids=[submitter.partner_id.id],
                        message_type='notification',
                        subtype_xmlid='mail.mt_comment',
                    )
                    try:
                        self.env['bus.bus']._sendone(
                            submitter.partner_id,
                            'crm_notification',
                            {
                                'title': 'Voucher Approved',
                                'message': f"Your voucher {rec.batch_id.name} was approved (₹ {rec.batch_id.total_amount:,.2f}).",
                                'model': 'service.ticket.voucher.batch',
                                'res_id': rec.batch_id.id,
                            }
                        )
                    except Exception:
                        pass
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('All Expenses Approved'),
                'message': _('All lines in this voucher have been approved.'),
                'type': 'success',
                'sticky': False,
                'next': {'type': 'ir.actions.client', 'tag': 'reload'},
            }
        }

    def action_reject_all(self):
        self._check_voucher_approval_access()
        for rec in self:
            target = rec.batch_id.line_ids if rec.batch_id else rec
            target.sudo().write({
                'status': 'rejected',
                'expense_manager_id': self.env.user.id,
            })
            if rec.batch_id:
                rec.batch_id.sudo().write({'expense_manager_id': self.env.user.id})
                rec.batch_id._compute_status()
                submitter = rec.batch_id.submitted_by_user_id or rec.batch_id.user_id
                if submitter and submitter.partner_id:
                    rec.batch_id.message_post(
                        body=f"<b>Voucher Rejected</b><br/>"
                             f"Your voucher <b>{rec.batch_id.name}</b> has been rejected by <b>{self.env.user.name}</b>.",
                        subject=f"Voucher Rejected: {rec.batch_id.name}",
                        partner_ids=[submitter.partner_id.id],
                        message_type='notification',
                        subtype_xmlid='mail.mt_comment',
                    ) 
                    try:
                        self.env['bus.bus']._sendone(
                            submitter.partner_id,
                            'crm_notification',
                            {
                                'title': 'Voucher Rejected',
                                'message': f"Your voucher {rec.batch_id.name} was rejected by {self.env.user.name}.",
                                'model': 'service.ticket.voucher.batch',
                                'res_id': rec.batch_id.id,
                            }
                        )
                    except Exception:
                        pass
                    try:
                        self.env['bus.bus']._sendone(
                            submitter.partner_id,
                            'crm_notification',
                            {
                                'title': 'Voucher Approved',
                                'message': f"Your voucher {rec.batch_id.name} was approved (₹ {rec.batch_id.total_amount:,.2f}).",
                                'model': 'service.ticket.voucher.batch',
                                'res_id': rec.batch_id.id,
                            }
                        )
                    except Exception:
                        pass
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('All Expenses Rejected'),
                'message': _('All lines in this voucher have been rejected.'),
                'type': 'danger',
                'sticky': False,
                'next': {'type': 'ir.actions.client', 'tag': 'reload'},
            }
        }

    def action_mark_paid(self):
        for rec in self:
            target = rec.batch_id.line_ids if rec.batch_id else rec
            to_pay = target.filtered(lambda l: l.status != 'rejected')
            if to_pay:
                to_pay.sudo().write({'status': 'paid'})
            elif target:
                target.sudo().write({'status': 'paid'})
            if rec.batch_id:
                rec.batch_id._compute_status()
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Payment Recorded'),
                'message': _('Voucher marked as Paid.'),
                'type': 'success',
                'sticky': False,
                'next': {'type': 'ir.actions.client', 'tag': 'reload'},
            }
        }

    def action_reset_to_submitted(self):
        """Rollback: Reset all lines in the voucher back to Submitted so manager can re-evaluate."""
        for rec in self:
            target = rec.batch_id.line_ids if rec.batch_id else rec
            target.sudo().write({
                'status': 'submitted',
                'reject_reason': False,
            })
            if rec.batch_id:
                rec.batch_id._compute_status()
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Voucher Rolled Back'),
                'message': _('Voucher lines reset to Submitted for re-evaluation.'),
                'type': 'info',
                'sticky': False,
                'next': {'type': 'ir.actions.client', 'tag': 'reload'},
            }
        }

    def action_reset_line(self):
        """Rollback a single line back to Submitted."""
        for rec in self:
            rec.sudo().write({
                'status': 'submitted',
                'reject_reason': False,
            })
            if rec.batch_id:
                rec.batch_id._compute_status()
        return {'type': 'ir.actions.client', 'tag': 'reload'}

    def action_reject(self):
        line = self[:1]
        if not line:
            return False
        view = self.env.ref('custom_crm_extended.view_service_ticket_voucher_reject_wizard_form', raise_if_not_found=False)
        return {
            'name': _('Reject Voucher Remark'),
            'type': 'ir.actions.act_window',
            'res_model': 'service.ticket.voucher.reject.wizard',
            'view_mode': 'form',
            'view_id': view.id if view else False,
            'target': 'new',
            'context': {
                'default_voucher_line_id': line.id,
                'default_reject_reason': line.reject_reason or '',
            },
        }

    def action_view_description(self):
        self.ensure_one()
        return {
            'name': _('Expense Description'),
            'type': 'ir.actions.act_window',
            'res_model': 'service.ticket.voucher.desc.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_description': self.description or 'No description provided.',
                'default_voucher_line_id': self.id,
            },
        }

    def action_open_expense_settings(self):
        setting = self.env['expense.setting'].sudo().get_setting()
        return {
            'name': _('Voucher Settings'),
            'type': 'ir.actions.act_window',
            'res_model': 'expense.setting',
            'res_id': setting.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_preview_bill(self):
        self.ensure_one()
        if not self.bill_file:
            return False
        view = self.env.ref('custom_crm_extended.view_service_ticket_voucher_line_preview_form', raise_if_not_found=False)
        return {
            'name': _('Bill Preview - %s') % (self.bill_filename or self.expense_type_id.name or 'Receipt'),
            'type': 'ir.actions.act_window',
            'res_model': 'service.ticket.voucher.line',
            'res_id': self.id,
            'view_mode': 'form',
            'view_id': view.id if view else False,
            'target': 'new',
        }


class ServiceTicketVoucherBudgetConfirmWizard(models.TransientModel):
    _name = 'service.ticket.voucher.budget.confirm.wizard'
    _description = 'Confirm Over Budget Voucher Warning'

    ticket_id = fields.Many2one('service.ticket', string='Service Ticket', required=False)
    batch_id = fields.Many2one('service.ticket.voucher.batch', string='Voucher Submission', required=False)
    message_html = fields.Html(string='Message', readonly=True, sanitize=False)

    def action_confirm(self):
        self.ensure_one()
        # If confirming approval from manager side
        target_ids = self.env.context.get('voucher_approval_target_ids')
        if target_ids:
            lines = self.env['service.ticket.voucher.line'].browse(target_ids)
            return lines.with_context(budget_approved_confirmed=True).action_approve()

        batch_id = self.env.context.get('voucher_approval_all_batch_id')
        if batch_id:
            batch = self.env['service.ticket.voucher.batch'].browse(batch_id)
            lines = batch.line_ids
            return lines.with_context(budget_approved_confirmed=True).action_approve_all()

        if self.batch_id:
            return self.batch_id.with_context(voucher_budget_confirmed=True).action_add_voucher_line()
        if self.ticket_id:
            return self.ticket_id.with_context(voucher_budget_confirmed=True).action_add_voucher_line()
        return {'type': 'ir.actions.act_window_close'}


class ServiceTicketVoucherRejectWizard(models.TransientModel):
    _name = 'service.ticket.voucher.reject.wizard'
    _description = 'Reject Voucher Remark Wizard'

    voucher_line_id = fields.Many2one('service.ticket.voucher.line', string='Voucher Line', required=False)
    batch_id = fields.Many2one('service.ticket.voucher.batch', string='Voucher Submission')
    batch_name = fields.Char(related='batch_id.name', string='Voucher ID', readonly=True)
    batch_employee_names = fields.Char(related='batch_id.all_employee_names', string='Employees', readonly=True)
    batch_total_amount = fields.Monetary(related='batch_id.total_amount', string='Total Amount', currency_field='currency_id', readonly=True)
    employee_name = fields.Char(related='voucher_line_id.user_id.name', string='Employee', readonly=True)
    expense_type_name = fields.Char(related='voucher_line_id.expense_type_id.name', string='Expense Type', readonly=True)
    amount = fields.Monetary(related='voucher_line_id.amount', string='Amount', currency_field='currency_id', readonly=True)
    currency_id = fields.Many2one('res.currency', string='Currency', default=lambda self: self.env.company.currency_id.id)
    reject_reason = fields.Text(string='Rejection Remark / Reason', required=True)

    def action_confirm_reject(self):
        self.ensure_one()
        reason = self.reject_reason or 'No reason specified'

        # If launched for a specific line, reject ONLY that specific line
        if self.voucher_line_id:
            line = self.voucher_line_id
            line.sudo().write({
                'status': 'rejected',
                'reject_reason': reason,
                'expense_manager_id': self.env.user.id,
            })
            batch = line.batch_id
            if batch:
                batch.invalidate_recordset()
                batch._compute_status()
                submitter = batch.submitted_by_user_id or batch.user_id
                if submitter and submitter.partner_id:
                    emp_name = line.user_id.name or 'Employee'
                    batch.message_post(
                        body=f"<b>Voucher Line Rejected</b><br/>"
                             f"Expense line for <b>{emp_name}</b> ({line.expense_type_id.name or 'Expense'}: {line.amount}) in <b>{batch.name}</b> has been rejected by <b>{self.env.user.name}</b>.<br/>"
                             f"Reason: <i>{reason}</i>",
                        subject=f"Voucher Line Rejected: {batch.name}",
                        partner_ids=[submitter.partner_id.id],
                        message_type='notification',
                        subtype_xmlid='mail.mt_comment',
                    )
            return {'type': 'ir.actions.act_window_close'}

        batch = self.batch_id
        if batch:
            batch.line_ids.sudo().write({
                'status': 'rejected',
                'reject_reason': reason,
                'expense_manager_id': self.env.user.id,
            })
            batch.sudo().write({
                'status': 'rejected',
                'expense_manager_id': self.env.user.id,
            })
            batch.invalidate_recordset()
            batch._compute_status()
            submitter = batch.submitted_by_user_id or batch.user_id
            if submitter and submitter.partner_id:
                batch.message_post(
                    body=f"<b>Voucher Rejected</b><br/>"
                         f"Your voucher <b>{batch.name}</b> has been rejected by <b>{self.env.user.name}</b>.<br/>"
                         f"Reason: <i>{reason}</i>",
                    subject=f"Voucher Rejected: {batch.name}",
                    partner_ids=[submitter.partner_id.id],
                    message_type='notification',
                    subtype_xmlid='mail.mt_comment',
                )
                try:
                    self.env['bus.bus']._sendone(
                        submitter.partner_id,
                        'crm_notification',
                        {
                            'title': f'Voucher Rejected: {batch.name}',
                            'message': f"Voucher {batch.name} was rejected: {reason}",
                            'model': 'service.ticket.voucher.batch',
                            'res_id': batch.id,
                        }
                    )
                except Exception:
                    pass
                try:
                    self.env['crm.notification'].create_notification(
                        user=submitter,
                        title=f'Voucher Rejected: {batch.name}',
                        summary=f"Voucher {batch.name} was rejected by {self.env.user.name}. Reason: {reason}",
                        category='voucher',
                        sender=self.env.user,
                        res_model='service.ticket.voucher.batch',
                        res_id=batch.id,
                        record_ref_name=batch.name,
                    )
                except Exception:
                    pass
        elif self.voucher_line_id:
            line = self.voucher_line_id
            line.sudo().write({
                'status': 'rejected',
                'reject_reason': reason,
                'expense_manager_id': self.env.user.id,
            })
            if line.batch_id:
                line.batch_id.invalidate_recordset()
                line.batch_id._compute_status()

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Voucher Rejected'),
                'message': _('Voucher rejected successfully.'),
                'type': 'danger',
                'sticky': False,
                'next': {'type': 'ir.actions.client', 'tag': 'reload'},
            }
        }


class ServiceTicketVoucherDescWizard(models.TransientModel):
    _name = 'service.ticket.voucher.desc.wizard'
    _description = 'View Expense Description'

    voucher_line_id = fields.Many2one('service.ticket.voucher.line', string='Voucher Line', readonly=True)
    description = fields.Text(string='Description', readonly=True)


class ServiceTicketVoucherBatch(models.Model):
    _name = 'service.ticket.voucher.batch'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'Service Ticket Voucher Submission'
    _order = 'id desc'

    active = fields.Boolean(string='Active', default=True)
    name = fields.Char(string='Voucher ID', default=lambda self: _('New'))
    voucher_id = fields.Char(related='name', string='Voucher ID', store=True, readonly=True)
    create_date = fields.Datetime(string='Submitted Date', readonly=True)

    def write(self, vals):
        res = super(ServiceTicketVoucherBatch, self).write(vals)
        if 'active' in vals:
            self.mapped('line_ids').write({'active': vals['active']})
        return res

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('name') or vals.get('name') == _('New'):
                if vals.get('ticket_id'):
                    seq_val = self.env['ir.sequence'].next_by_code('service.ticket.voucher.seq')
                    if not seq_val:
                        year = fields.Date.today().year
                        count = self.search_count([('ticket_id', '!=', False)]) + 1
                        seq_val = f"VCH-{year}-{count:05d}"
                    vals['name'] = seq_val
                else:
                    seq_val = self.env['ir.sequence'].next_by_code('general.voucher.seq')
                    if not seq_val:
                        year = fields.Date.today().year
                        count = self.search_count([('ticket_id', '=', False)]) + 1
                        seq_val = f"GEN-VCH-{year}-{count:05d}"
                    vals['name'] = seq_val
            emp_id = vals.get('user_id') or self.env.user.id
            emp = self.env['res.users'].browse(emp_id)
            approver = self.env['service.ticket']._get_voucher_approver_for_employee(emp)
            if approver:
                vals['expense_manager_id'] = approver.id
        return super(ServiceTicketVoucherBatch, self).create(vals_list)
    submission_date = fields.Date(string='Expense Date', default=fields.Date.context_today, index=True)
    expense_date = fields.Date(related='submission_date', string='Expense Date', readonly=True)
    expense_dates = fields.Char(string='Expense Dates', compute='_compute_expense_dates', store=True)
    ticket_id = fields.Many2one('service.ticket', string='Service Ticket', required=False, ondelete='cascade')
    voucher_type = fields.Selection([
        ('ticket', 'Service Ticket'),
        ('general', 'General Expense'),
    ], string='Voucher Type', compute='_compute_voucher_type', store=True)

    @api.depends('ticket_id')
    def _compute_voucher_type(self):
        for rec in self:
            rec.voucher_type = 'ticket' if rec.ticket_id else 'general'

    user_id = fields.Many2one('res.users', string='Employee', required=True, default=lambda self: self.env.user)
    is_voucher_owner = fields.Boolean(
        string='Is Voucher Owner',
        compute='_compute_is_voucher_owner',
        store=False,
    )

    def _compute_is_voucher_owner(self):
        user = self.env.user
        for rec in self:
            rec.is_voucher_owner = bool(
                rec.user_id.id == user.id or
                rec.submitted_by_user_id.id == user.id
            )

    @api.model
    def _search(self, domain, offset=0, limit=None, order=None):
        """Strict Draft Privacy:
        Draft vouchers are private to the creator/submitting employee only.
        Administrators, Global Expense Managers, and Department Approvers can only see
        vouchers once submitted (status != 'draft'), unless it is their own draft voucher.
        """
        user = self.env.user
        extra_domain = [
            '|',
            ('user_id', '=', user.id),
            '|',
            ('submitted_by_user_id', '=', user.id),
            ('status', '!=', 'draft'),
        ]
        domain = expression.AND([domain, extra_domain])
        return super(ServiceTicketVoucherBatch, self)._search(domain, offset=offset, limit=limit, order=order)
    submitted_by_user_id = fields.Many2one(
        'res.users',
        string='Submitted By',
        compute='_compute_submitted_by_user_id',
        store=True,
        readonly=False,
        default=lambda self: self.env.user,
    )

    @api.depends('create_uid', 'user_id')
    def _compute_submitted_by_user_id(self):
        for rec in self:
            if not rec.submitted_by_user_id or rec.submitted_by_user_id.id == 1:
                rec.submitted_by_user_id = rec.create_uid if rec.create_uid and rec.create_uid.id != 1 else rec.user_id

    other_employee_names = fields.Char(
        string='Other Employees',
        compute='_compute_other_employee_names',
        store=True,
        readonly=False,
    )

    @api.depends('submitted_by_user_id', 'user_id', 'line_ids.user_id.name')
    def _compute_other_employee_names(self):
        for rec in self:
            submitter_name = (rec.submitted_by_user_id.name if rec.submitted_by_user_id and rec.submitted_by_user_id.id != 1 else rec.user_id.name) or ''
            names = []
            for emp_name in rec.line_ids.mapped('user_id.name'):
                if emp_name and emp_name != submitter_name and emp_name not in names:
                    names.append(emp_name)
            rec.other_employee_names = ", ".join(names) if names else ""
    all_employee_names = fields.Char(compute='_compute_all_employee_names', string='Employees', store=True)
    voucher_employee_names = fields.Char(related='all_employee_names', string='Employees', readonly=True)
    ticket_voucher_line_ids = fields.One2many(related='line_ids', string='Voucher Expenses', readonly=True)

    @api.depends('line_ids.expense_date')
    def _compute_expense_dates(self):
        for rec in self:
            dates = [d.strftime('%d/%m/%Y') for d in rec.line_ids.mapped('expense_date') if d]
            unique_dates = list(dict.fromkeys(dates))
            rec.expense_dates = ", ".join(unique_dates) if unique_dates else ""

    @api.depends('user_id.name', 'other_employee_names', 'line_ids.user_id.name')
    def _compute_all_employee_names(self):
        for rec in self:
            names = []
            if rec.user_id and rec.user_id.name:
                names.append(rec.user_id.name)
            if rec.other_employee_names:
                for n in rec.other_employee_names.split(','):
                    n_clean = n.strip()
                    if n_clean and n_clean not in names:
                        names.append(n_clean)
            for line in rec.line_ids:
                if line.user_id and line.user_id.name and line.user_id.name not in names:
                    names.append(line.user_id.name)
            rec.all_employee_names = ", ".join(names) if names else (rec.user_id.name or "")

    line_ids = fields.One2many('service.ticket.voucher.line', 'batch_id', string='Expense Lines')

    # Quick Add Expense fields for Voucher Batch Form (General Expenses & Service Ticket)
    new_voucher_user_ids = fields.Many2many(
        'res.users',
        'voucher_batch_new_users_rel',
        'batch_id',
        'user_id',
        string='Employee(s)',
        domain="[('share', '=', False)]",
        default=lambda self: [self.env.user.id],
    )
    new_voucher_expense_type_id = fields.Many2one(
        'service.ticket.expense.type',
        string='Expense Type',
        domain="[('active', '=', True)]",
    )
    allowed_voucher_expense_type_ids = fields.Many2many(
        'service.ticket.expense.type',
        compute='_compute_batch_allowed_voucher_expense_type_ids',
        string='Allowed Expense Types',
    )
    new_voucher_is_km = fields.Boolean(
        compute='_compute_batch_new_voucher_is_km',
        string='Is KM Based',
    )
    new_voucher_is_daily = fields.Boolean(
        compute='_compute_batch_new_voucher_is_daily',
        string='Is Daily Calculation',
    )
    new_voucher_date = fields.Date(
        string='Expense Date',
        default=fields.Date.context_today,
    )
    new_voucher_date_to = fields.Date(string='To Date')
    new_voucher_days = fields.Integer(
        compute='_compute_batch_new_voucher_days',
        string='Days',
    )
    new_voucher_total_km = fields.Float(string='Total KM')
    new_voucher_rate_per_km = fields.Float(
        related='new_voucher_expense_type_id.km_rate',
        string='Rate/KM (₹)',
        readonly=True,
    )
    new_voucher_description = fields.Char(string='Description')
    new_voucher_amount = fields.Monetary(
        string='Amount',
        currency_field='currency_id',
        default=0.0,
    )
    new_voucher_bill_attachment_ids = fields.Many2many(
        'ir.attachment',
        'voucher_batch_new_bill_att_rel',
        'batch_id',
        'att_id',
        string='Bills & Receipts',
    )
    new_voucher_budget_info_html = fields.Html(
        compute='_compute_batch_new_voucher_budget_info_html',
        string='Budget Info Display',
        sanitize=False,
    )
    has_km_lines = fields.Boolean(
        compute='_compute_batch_has_km_lines',
        string='Has KM Lines',
    )
    voucher_draft_dates = fields.Char(
        compute='_compute_batch_draft_strip',
        string='Expense Dates',
    )
    has_draft_lines = fields.Boolean(
        compute='_compute_batch_draft_strip',
        string='Has Draft Lines',
    )

    @api.depends('new_voucher_user_ids')
    def _compute_batch_allowed_voucher_expense_type_ids(self):
        all_types = self.env['service.ticket.expense.type'].search([('active', '=', True)])
        for rec in self:
            target_users = rec.new_voucher_user_ids or self.env.user
            allowed_ids = []
            for t in all_types:
                if not t.job_ids:
                    # Global expense type -> allowed for everyone
                    allowed_ids.append(t.id)
                else:
                    # Restricted expense type -> all target users must have an allowed job position
                    user_ok = True
                    for u in target_users:
                        u_jobs = t._get_user_job_positions(user=u)
                        if not any(j.id in u_jobs for j in t.job_ids):
                            user_ok = False
                            break
                    if user_ok:
                        allowed_ids.append(t.id)
            rec.allowed_voucher_expense_type_ids = all_types.browse(allowed_ids)

    @api.onchange('new_voucher_user_ids')
    def _onchange_batch_new_voucher_user_ids_filter_type(self):
        self._compute_batch_allowed_voucher_expense_type_ids()
        exp_type = self.new_voucher_expense_type_id
        if exp_type and exp_type.job_ids:
            for u in self.new_voucher_user_ids:
                u_jobs = exp_type._get_user_job_positions(user=u)
                if not any(j.id in u_jobs for j in exp_type.job_ids):
                    self.new_voucher_expense_type_id = False
                    break
        self._compute_batch_new_voucher_budget_info_html()

    @api.depends('new_voucher_expense_type_id', 'new_voucher_expense_type_id.is_km_based')
    def _compute_batch_new_voucher_is_km(self):
        for rec in self:
            rec.new_voucher_is_km = bool(rec.new_voucher_expense_type_id and rec.new_voucher_expense_type_id.is_km_based)

    @api.depends('new_voucher_expense_type_id', 'new_voucher_expense_type_id.calculation_type')
    def _compute_batch_new_voucher_is_daily(self):
        for rec in self:
            rec.new_voucher_is_daily = bool(rec.new_voucher_expense_type_id and rec.new_voucher_expense_type_id.calculation_type == 'daily')

    @api.depends('new_voucher_date', 'new_voucher_date_to', 'new_voucher_expense_type_id.calculation_type')
    def _compute_batch_new_voucher_days(self):
        for rec in self:
            if rec.new_voucher_expense_type_id and rec.new_voucher_expense_type_id.calculation_type == 'daily' and rec.new_voucher_date and rec.new_voucher_date_to:
                diff = (rec.new_voucher_date_to - rec.new_voucher_date).days + 1
                rec.new_voucher_days = max(diff, 1)
            else:
                rec.new_voucher_days = 1

    @api.depends('line_ids.is_km_based')
    def _compute_batch_has_km_lines(self):
        for rec in self:
            rec.has_km_lines = any(l.is_km_based for l in rec.line_ids)

    @api.depends('line_ids.status', 'line_ids.expense_date')
    def _compute_batch_draft_strip(self):
        for rec in self:
            drafts = rec.line_ids.filtered(lambda l: l.status == 'draft')
            rec.has_draft_lines = bool(drafts)
            dates = [d.strftime('%d/%m/%Y') for d in drafts.mapped('expense_date') if d]
            unique_dates = list(dict.fromkeys(dates))
            rec.voucher_draft_dates = ", ".join(unique_dates) if unique_dates else ""

    @api.depends('new_voucher_expense_type_id', 'new_voucher_user_ids', 'new_voucher_date', 'new_voucher_date_to', 'new_voucher_days')
    def _compute_batch_new_voucher_budget_info_html(self):
        for rec in self:
            exp_type = rec.new_voucher_expense_type_id
            if not exp_type:
                rec.new_voucher_budget_info_html = False
                continue

            target_users = rec.new_voucher_user_ids or self.env.user
            pill_badge = "background:#e0f2fe; color:#0369a1; border:1px solid #bae6fd; font-weight:600; border-radius:9999px; padding:2px 10px; white-space:nowrap;"
            pill_total = "background:#e0f2fe; color:#0369a1; border:1px solid #bae6fd; font-weight:700; border-radius:9999px; padding:2px 10px; white-space:nowrap;"

            if exp_type.is_km_based:
                items_html = []
                for u in target_users:
                    role_name = self.env['service.ticket']._get_user_role_display(u)
                    role_str = f" ({role_name})" if role_name else ""
                    rate = exp_type.get_effective_km_rate(user=u)
                    items_html.append(f"<span class='badge' style='{pill_badge}'>{u.name}{role_str}: ₹{rate:,.2f}/KM</span>")
                rec.new_voucher_budget_info_html = f"""
                <div class="d-flex align-items-center gap-2 flex-wrap py-1" style="font-size:12px; color:#0c4a6e; line-height:1.6; row-gap:6px;">
                    <span style="white-space:nowrap;">Allowed Rate for <strong>KM Expense</strong>:</span>
                    {" ".join(items_html)}
                </div>
                """
            else:
                total_limit = 0.0
                has_any_limit = False
                items_html = []
                days = rec.new_voucher_days if exp_type.calculation_type == 'daily' else 1
                days_label = f" ({days} Days)" if (exp_type.calculation_type == 'daily' and days > 1) else ""
                for u in target_users:
                    role_name = self.env['service.ticket']._get_user_role_display(u)
                    role_str = f" ({role_name})" if role_name else ""
                    base_limit = exp_type.get_effective_budget_limit(user=u)
                    limit = base_limit * days
                    if limit > 0:
                        has_any_limit = True
                        total_limit += limit
                        items_html.append(f"<span class='badge' style='{pill_badge}'>{u.name}{role_str}: ₹{limit:,.2f}{days_label}</span>")
                    else:
                        items_html.append(f"<span class='badge' style='background:#f1f5f9; color:#475569; border:1px solid #cbd5e1; border-radius:9999px; padding:2px 10px; white-space:nowrap;'>{u.name}{role_str}: No Limit</span>")

                unit_label = f" / {days} Days" if (exp_type.calculation_type == 'daily' and days > 1) else (" / day" if exp_type.calculation_type == 'daily' else " / visit")
                if len(target_users) > 1 and has_any_limit:
                    rec.new_voucher_budget_info_html = f"""
                    <div class="d-flex align-items-center gap-2 flex-wrap py-1" style="font-size:12px; color:#0c4a6e; line-height:1.6; row-gap:6px;">
                        <span style="white-space:nowrap;">Allowed Limit for <strong>Group Budget Pool</strong>:</span>
                        <span class="badge" style="{pill_total}">₹{total_limit:,.2f}{unit_label}</span>
                        <span class="text-muted fw-bold mx-1">|</span>
                        {" ".join(items_html)}
                    </div>
                    """
                elif has_any_limit:
                    u = target_users[:1]
                    role_name = self.env['service.ticket']._get_user_role_display(u)
                    role_str = f" ({role_name})" if role_name else ""
                    rec.new_voucher_budget_info_html = f"""
                    <div class="d-flex align-items-center gap-2 flex-wrap py-1" style="font-size:12px; color:#0c4a6e; line-height:1.6; row-gap:6px;">
                        <span style="white-space:nowrap;">Allowed Limit for <strong>{u.name}{role_str}</strong>:</span>
                        <span class="badge" style="{pill_total}">₹{total_limit:,.2f}{unit_label}</span>
                    </div>
                    """
                else:
                    rec.new_voucher_budget_info_html = f"""
                    <div class="py-1" style="font-size:12px; color:#64748b;">
                        <span>No budget limit restriction for this expense type.</span>
                    </div>
                    """

    @api.onchange('new_voucher_expense_type_id', 'new_voucher_total_km')
    def _onchange_batch_new_voucher_expense_type(self):
        if self.new_voucher_expense_type_id:
            self.new_voucher_is_km = bool(self.new_voucher_expense_type_id.is_km_based)
            if self.new_voucher_is_km:
                rate = self.new_voucher_expense_type_id.km_rate or 0.0
                if self.new_voucher_total_km > 0 and rate > 0:
                    self.new_voucher_amount = round(self.new_voucher_total_km * rate, 2)
            else:
                self.new_voucher_total_km = 0.0
        else:
            self.new_voucher_is_km = False
            self.new_voucher_total_km = 0.0

    def action_add_voucher_line(self):
        self.ensure_one()
        missing_fields = []
        if not self.new_voucher_user_ids:
            missing_fields.append("Employee(s)")
        if not self.new_voucher_date:
            missing_fields.append("Expense Date")
        if self.new_voucher_is_daily and not self.new_voucher_date_to:
            missing_fields.append("To Date")
        if not self.new_voucher_expense_type_id:
            missing_fields.append("Expense Type")
        if not self.new_voucher_amount or self.new_voucher_amount <= 0:
            missing_fields.append("Amount")

        if missing_fields:
            fields_str = ", ".join(missing_fields)
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Missing Required Fields',
                    'message': f"Please fill in the required field(s): {fields_str}.",
                    'type': 'warning',
                    'sticky': False,
                }
            }

        exp_date = self.new_voucher_date
        today = fields.Date.context_today(self)
        if exp_date > today:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Invalid Expense Date',
                    'message': 'Expense Date cannot be in the future.',
                    'type': 'warning',
                    'sticky': False,
                }
            }

        if self.new_voucher_is_daily and self.new_voucher_date_to:
            if self.new_voucher_date_to > today:
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': 'Invalid To Date',
                        'message': 'To Date cannot be in the future.',
                        'type': 'warning',
                        'sticky': False,
                    }
                }
            if self.new_voucher_date_to < exp_date:
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': 'Invalid Date Range',
                        'message': 'To Date cannot be earlier than From Date.',
                        'type': 'warning',
                        'sticky': False,
                    }
                }

        target_users = self.new_voucher_user_ids
        user_count = len(target_users)
        exp_type = self.new_voucher_expense_type_id

        if exp_type.job_ids:
            for u in target_users:
                u_jobs = exp_type._get_user_job_positions(user=u)
                if not any(j.id in u_jobs for j in exp_type.job_ids):
                    allowed_names = ", ".join(exp_type.job_ids.mapped('name'))
                    return {
                        'type': 'ir.actions.client',
                        'tag': 'display_notification',
                        'params': {
                            'title': 'Job Position Restricted',
                            'message': f"Expense Type '{exp_type.name}' is only allowed for Job Position(s): {allowed_names}. Employee '{u.name}' is not authorized.",
                            'type': 'danger',
                            'sticky': True,
                        }
                    }

        split_km = round(self.new_voucher_total_km / user_count, 2) if (user_count > 0 and self.new_voucher_is_km) else self.new_voucher_total_km
        days = self.new_voucher_days if exp_type.calculation_type == 'daily' else 1
        user_limits = {}
        for u in target_users:
            user_limits[u.id] = exp_type.get_effective_budget_limit(user=u) * days

        total_budget = sum(user_limits.values())
        has_positive_limits = total_budget > 0 and all(user_limits[u.id] > 0 for u in target_users)

        user_splits = {}
        exceeded_users = []
        if not exp_type.is_km_based and has_positive_limits:
            for u in target_users:
                u_ratio = user_limits[u.id] / total_budget
                u_raw = round(self.new_voucher_amount * u_ratio, 2)
                u_lim = user_limits[u.id]
                if u_raw > u_lim:
                    exceeded_users.append((u, u_raw, u_lim))
                user_splits[u.id] = u_raw
        else:
            raw_split = round(self.new_voucher_amount / user_count, 2) if user_count > 0 else self.new_voucher_amount
            for u in target_users:
                u_lim = user_limits.get(u.id, 0.0)
                if not exp_type.is_km_based and u_lim > 0 and raw_split > u_lim:
                    exceeded_users.append((u, raw_split, u_lim))
                user_splits[u.id] = raw_split

        if not exp_type.is_km_based and exceeded_users and not self.env.context.get('voucher_budget_confirmed'):
            items_str = "".join([f"<li><strong>{u.name}</strong>: Entered share is <strong>₹{raw:,.2f}</strong>, but this voucher can only pass up to allowed budget limit of <strong>₹{lim:,.2f}</strong>.</li>" for u, raw, lim in exceeded_users])
            msg = f"""
            <div class="p-2" style="font-size:13px; color:#1e293b;">
                <p class="mb-2">The entered bill amount exceeds the allowed budget limit for the following person(s):</p>
                <ul class="mb-0 ps-3" style="color:#b91c1c;">
                    {items_str}
                </ul>
            </div>
            """
            wiz = self.env['service.ticket.voucher.budget.confirm.wizard'].create({
                'batch_id': self.id,
                'ticket_id': self.ticket_id.id if self.ticket_id else False,
                'message_html': msg,
            })
            return {
                'name': _('Budget Limit Notice'),
                'type': 'ir.actions.act_window',
                'res_model': 'service.ticket.voucher.budget.confirm.wizard',
                'res_id': wiz.id,
                'view_mode': 'form',
                'target': 'new',
            }

        km_val = self.new_voucher_total_km if exp_type.is_km_based else 0.0
        split_km = round(km_val / user_count, 2) if (user_count > 0 and exp_type.is_km_based) else km_val
        login_user = self.env.user

        for u in target_users:
            dept = u.crm_department_id or (u.crm_job_id and u.crm_job_id.department_id) or False
            other_names = ", ".join([other.name for other in target_users if other.id != u.id and other.id != login_user.id])
            user_rate = self.new_voucher_rate_per_km or exp_type.get_effective_km_rate(user=u) or 0.0
            self.env['service.ticket.voucher.line'].sudo().create({
                'batch_id': self.id,
                'ticket_id': self.ticket_id.id if self.ticket_id else False,
                'expense_date': exp_date,
                'expense_date_to': self.new_voucher_date_to if (exp_type.calculation_type == 'daily') else False,
                'user_id': u.id,
                'submitted_by_user_id': login_user.id,
                'other_employee_names': other_names or '',
                'department_id': dept.id if dept else False,
                'expense_type_id': exp_type.id,
                'is_km_based': exp_type.is_km_based,
                'total_km': split_km if exp_type.is_km_based else 0.0,
                'rate_per_km': user_rate if exp_type.is_km_based else 0.0,
                'description': self.new_voucher_description or '',
                'amount': user_splits.get(u.id, 0.0),
                'bill_attachment_ids': [(6, 0, self.new_voucher_bill_attachment_ids.ids)] if self.new_voucher_bill_attachment_ids else False,
                'status': 'draft',
            })

        first_emp = target_users[0] if target_users else False
        approver = self.env['service.ticket']._get_voucher_approver_for_employee(first_emp) if first_emp else False

        update_vals = {
            'new_voucher_date': False,
            'new_voucher_date_to': False,
            'new_voucher_expense_type_id': False,
            'new_voucher_user_ids': [(5, 0, 0)],
            'new_voucher_total_km': 0.0,
            'new_voucher_description': False,
            'new_voucher_amount': 0.0,
            'new_voucher_bill_attachment_ids': [(5, 0, 0)],
        }
        if first_emp:
            update_vals['user_id'] = first_emp.id
            if approver:
                update_vals['expense_manager_id'] = approver.id

        self.sudo().write(update_vals)
        self._compute_all_employee_names()
        self._compute_expense_dates()
        self._compute_total_amount()
        return False

    def action_clear_voucher_fields(self):
        self.ensure_one()
        self.sudo().write({
            'new_voucher_date': False,
            'new_voucher_date_to': False,
            'new_voucher_expense_type_id': False,
            'new_voucher_user_ids': [(5, 0, 0)],
            'new_voucher_total_km': 0.0,
            'new_voucher_description': False,
            'new_voucher_amount': 0.0,
            'new_voucher_bill_attachment_ids': [(5, 0, 0)],
        })
        return True
    expense_type_id = fields.Many2one('service.ticket.expense.type', string='Expense Type', compute='_compute_batch_summary_fields')
    description = fields.Text(string='Description', compute='_compute_batch_summary_fields')
    is_km_based = fields.Boolean(string='KM Based', compute='_compute_batch_summary_fields')
    total_km = fields.Float(string='Total KM', compute='_compute_batch_summary_fields')
    rate_per_km = fields.Float(string='Rate/KM', compute='_compute_batch_summary_fields')
    amount = fields.Monetary(string='Amount', currency_field='currency_id', compute='_compute_batch_summary_fields')
    reject_reason = fields.Char(string='Reject Reason', compute='_compute_batch_summary_fields')
    bill_file = fields.Binary(string='Bill', compute='_compute_batch_summary_fields')
    bill_filename = fields.Char(string='Bill Filename', compute='_compute_batch_summary_fields')
    bill_preview = fields.Binary(related='bill_file', string='Bill Preview', readonly=True)

    def _compute_batch_summary_fields(self):
        for rec in self:
            first_line = rec.line_ids[:1]
            rec.expense_type_id = first_line.expense_type_id.id if first_line else False
            rec.description = ", ".join(filter(None, rec.line_ids.mapped('description'))) if rec.line_ids else ""
            rec.is_km_based = any(rec.line_ids.mapped('is_km_based'))
            rec.total_km = sum(rec.line_ids.mapped('total_km'))
            rec.rate_per_km = first_line.rate_per_km if first_line else 0.0
            rec.amount = rec.total_amount
            rec.reject_reason = ", ".join(filter(None, rec.line_ids.mapped('reject_reason'))) if rec.line_ids else ""
            rec.bill_file = first_line.bill_file if first_line else False
            rec.bill_filename = first_line.bill_filename if first_line else False


    currency_id = fields.Many2one('res.currency', string='Currency', compute='_compute_currency_id', store=True, readonly=False)

    @api.depends('ticket_id.currency_id')
    def _compute_currency_id(self):
        for rec in self:
            rec.currency_id = rec.ticket_id.currency_id if rec.ticket_id else self.env.company.currency_id

    can_approve = fields.Boolean(compute='_compute_batch_can_approve', string='Can Approve')

    @api.depends_context('uid')
    def _compute_batch_can_approve(self):
        user = self.env.user
        is_admin_or_global = user._is_admin() or user.has_group('base.group_system') or (user.id in self.env.company.sudo().crm_authorized_expense_manager_ids.ids)
        managed_depts = self.env['hr.department'].sudo().search([
            ('voucher_approval_active', '=', True),
            '|',
            ('voucher_manager_id', '=', user.id),
            ('manager_user_id', '=', user.id),
        ])
        for rec in self:
            if is_admin_or_global:
                rec.can_approve = True
            elif managed_depts:
                is_own = (rec.user_id.id == user.id or (rec.submitted_by_user_id and rec.submitted_by_user_id.id == user.id) or any(l.user_id.id == user.id for l in rec.line_ids))
                rec.can_approve = not is_own
            else:
                rec.can_approve = False
    total_amount = fields.Monetary(compute='_compute_total_amount', string='Total Amount', currency_field='currency_id', store=True)
    status = fields.Selection([
        ('draft', 'Draft'),
        ('submitted', 'Submitted'),
        ('partially_approved', 'Partially Approved'),
        ('approved', 'Approved'),
        ('partially_paid', 'Partially Paid'),
        ('paid', 'Paid'),
        ('rejected', 'Rejected'),
    ], string='Status', compute='_compute_status', store=True, default='draft')
    def _default_expense_manager_id(self):
        emp = self.env.user
        approver = self.env['service.ticket']._get_voucher_approver_for_employee(emp)
        if approver:
            return approver.id
        mgr = self.env.company.crm_authorized_expense_manager_ids[:1]
        return mgr.id if mgr else 2

    expense_manager_id = fields.Many2one('res.users', string='Approver', compute='_compute_expense_manager_id', store=True, readonly=False, default=_default_expense_manager_id)

    @api.onchange('user_id')
    def _onchange_user_id_approver(self):
        if self.user_id:
            approver = self.env['service.ticket']._get_voucher_approver_for_employee(self.user_id)
            if approver:
                self.expense_manager_id = approver.id

    @api.depends('user_id', 'line_ids.user_id')
    def _compute_expense_manager_id(self):
        for rec in self:
            emp = rec.user_id or (rec.line_ids[:1].user_id if rec.line_ids else False)
            if emp:
                approver = self.env['service.ticket']._get_voucher_approver_for_employee(emp)
                rec.expense_manager_id = approver or emp.crm_expense_manager_id

    @api.depends('line_ids.amount')
    def _compute_total_amount(self):
        for rec in self:
            rec.total_amount = sum(rec.line_ids.mapped('amount'))

    @api.depends('line_ids.status')
    def _compute_status(self):
        for rec in self:
            statuses = set(rec.line_ids.mapped('status'))
            if not statuses or 'draft' in statuses:
                rec.status = 'draft'
            elif all(s == 'paid' for s in statuses):
                rec.status = 'paid'
            elif any(s == 'paid' for s in statuses):
                rec.status = 'partially_paid'
            elif all(s == 'approved' for s in statuses):
                rec.status = 'approved'
            elif all(s == 'rejected' for s in statuses):
                rec.status = 'rejected'
            elif any(s in ('approved', 'rejected') for s in statuses):
                rec.status = 'partially_approved'
            else:
                rec.status = 'submitted'

    def action_submit_batch(self):
        for rec in self:
            if not rec.line_ids:
                raise UserError(_("Please add at least one expense line before submitting."))
            for line in rec.line_ids:
                if not line.amount or line.amount <= 0:
                    raise UserError(_("Each expense line must have a submitted amount greater than 0."))
                if not line.expense_date:
                    raise UserError(_("Please select an expense date for all lines."))
                if line.is_km_based and (not line.total_km or line.total_km <= 0):
                    raise UserError(_("Please enter total KM for KM-based expense '%s'.") % (line.expense_type_id.name or ''))
                line.write({'status': 'submitted'})
            rec._compute_status()
            rec._compute_total_amount()
            emp = rec.user_id or (rec.line_ids[:1].user_id if rec.line_ids else False) or self.env.user
            eff_approver = self.env['service.ticket']._get_voucher_approver_for_employee(emp)
            if eff_approver:
                rec.expense_manager_id = eff_approver.id
                rec.line_ids.write({'expense_manager_id': eff_approver.id})
            approver = rec.expense_manager_id
            if approver and approver.partner_id:
                try:
                    self.env['bus.bus']._sendone(
                        approver.partner_id,
                        'crm_notification',
                        {
                            'title': 'New Voucher Submitted',
                            'message': f"Voucher {rec.name} (₹{rec.total_amount:,.2f}) submitted by {rec.submitted_by_user_id.name or self.env.user.name}.",
                            'model': 'service.ticket.voucher.batch',
                            'res_id': rec.id,
                        }
                    )
                except Exception:
                    pass
        return True

    def _check_voucher_approval_access(self):
        user = self.env.user
        for line in self:
            # Self-approval restriction: Cannot approve own vouchers unless Admin
            if (line.user_id.id == user.id or (line.submitted_by_user_id and line.submitted_by_user_id.id == user.id)):
                if not (user._is_admin() or user.has_group('base.group_system')):
                    raise ValidationError(_("Access Denied: You cannot approve your own expense voucher. It must be approved by a Global Expense Manager or Administrator."))

        if user._is_admin() or user.has_group('base.group_system'):
            return True
        company = self.env.company
        if user.id in company.sudo().crm_authorized_expense_manager_ids.ids:
            return True
        for line in self:
            dept = line.department_id or (line.user_id and line.user_id.crm_department_id)
            if not dept:
                raise ValidationError(_("Access Denied: Only System Administrators and Global Expense Managers can approve vouchers without an assigned department."))
            eff_approver = dept.voucher_manager_id or dept.manager_user_id
            is_direct_mgr = (eff_approver and eff_approver.id == user.id and dept.voucher_approval_active)
            is_extra_mgr = bool(self.env['hr.department'].sudo().search([
                ('voucher_approval_active', '=', True),
                ('extra_department_ids', 'in', [dept.id]),
                '|',
                ('voucher_manager_id', '=', user.id),
                ('manager_user_id', '=', user.id),
            ], limit=1))
            if not (is_direct_mgr or is_extra_mgr):
                raise ValidationError(_("Access Denied: You are only authorized to approve vouchers for your assigned department (%s).") % (dept.name or ''))
        return True



    can_approve = fields.Boolean(compute='_compute_can_approve', string='Can Approve')

    @api.depends_context('uid')
    def _compute_can_approve(self):
        user = self.env.user
        is_admin_or_global = user._is_admin() or user.has_group('base.group_system') or (user.id in self.env.company.sudo().crm_authorized_expense_manager_ids.ids)
        managed_depts = self.env['hr.department'].sudo().search([
            ('voucher_approval_active', '=', True),
            '|',
            ('voucher_manager_id', '=', user.id),
            ('manager_user_id', '=', user.id),
        ])
        for rec in self:
            if is_admin_or_global:
                rec.can_approve = True
            elif managed_depts:
                # Manager cannot approve their own expense
                is_own = (rec.user_id.id == user.id or (rec.submitted_by_user_id and rec.submitted_by_user_id.id == user.id))
                rec.can_approve = not is_own
            else:
                rec.can_approve = False

    def action_approve(self):
        self._check_voucher_approval_access()
        """ Alias for batch-level approval """
        return self.action_approve_all()

    def action_reject(self):
        """ Opens reject wizard for the batch or rejects all lines """
        line = self.line_ids[:1]
        view = self.env.ref('custom_crm_extended.view_service_ticket_voucher_reject_wizard_form', raise_if_not_found=False)
        return {
            'name': _('Reject Voucher Submission'),
            'type': 'ir.actions.act_window',
            'res_model': 'service.ticket.voucher.reject.wizard',
            'view_mode': 'form',
            'view_id': view.id if view else False,
            'target': 'new',
            'context': {
                'default_voucher_line_id': line.id if line else False,
                'default_reject_reason': '',
            },
        }

    def action_preview_bill(self):
        line = self.line_ids.filtered(lambda l: l.bill_file)[:1]
        if not line:
            return False
        return line.action_preview_bill()

    def action_approve_all(self):
        self._check_voucher_approval_access()
        for rec in self:
            rec.line_ids.sudo().write({
                'status': 'approved',
                'expense_manager_id': self.env.user.id,
                'reject_reason': False,
            })
            rec.sudo().write({'expense_manager_id': self.env.user.id})
            rec._compute_status()
            submitter = rec.submitted_by_user_id or rec.user_id
            if submitter and submitter.partner_id:
                rec.message_post(
                    body=f"<b>Voucher Approved</b><br/>"
                         f"Your voucher <b>{rec.name}</b> has been approved by <b>{self.env.user.name}</b>.<br/>"
                         f"Approved Amount: <b>₹ {rec.total_amount:,.2f}</b>",
                    subject=f"Voucher Approved: {rec.name}",
                    partner_ids=[submitter.partner_id.id],
                    message_type='notification',
                    subtype_xmlid='mail.mt_comment',
                )
                try:
                    self.env['bus.bus']._sendone(
                        submitter.partner_id,
                        'crm_notification',
                        {
                            'title': 'Voucher Approved',
                            'message': f"Your voucher {rec.name} was approved (₹ {rec.total_amount:,.2f}).",
                            'model': 'service.ticket.voucher.batch',
                            'res_id': rec.id,
                        }
                    )
                except Exception:
                    pass
                try:
                    self.env['crm.notification'].create_notification(
                        user=submitter,
                        title='Voucher Approved',
                        summary=f"Your voucher {rec.name} was approved by {self.env.user.name}. Approved Amount: ₹ {rec.total_amount:,.2f}",
                        category='voucher',
                        sender=self.env.user,
                        res_model='service.ticket.voucher.batch',
                        res_id=rec.id,
                        record_ref_name=rec.name,
                    )
                except Exception:
                    pass
        self.invalidate_recordset()
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Voucher Approved'),
                'message': _('All voucher expenses approved successfully.'),
                'type': 'success',
                'sticky': False,
                'next': {'type': 'ir.actions.client', 'tag': 'reload'},
            }
        }

    def action_reject_all(self):
        self._check_voucher_approval_access()
        self.ensure_one()
        view = self.env.ref('custom_crm_extended.view_service_ticket_voucher_reject_wizard_form', raise_if_not_found=False)
        line = self.line_ids[:1]
        return {
            'name': _('Reject Voucher Submission'),
            'type': 'ir.actions.act_window',
            'res_model': 'service.ticket.voucher.reject.wizard',
            'view_mode': 'form',
            'view_id': view.id if view else False,
            'target': 'new',
            'context': {
                'default_voucher_line_id': line.id if line else False,
                'default_batch_id': self.id,
                'default_reject_reason': '',
            },
        }

    def action_mark_paid(self):
        for rec in self:
            to_pay = rec.line_ids.filtered(lambda l: l.status != 'rejected')
            if to_pay:
                to_pay.sudo().write({'status': 'paid'})
            elif rec.line_ids:
                rec.line_ids.sudo().write({'status': 'paid'})
            rec._compute_status()
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Payment Recorded'),
                'message': _('Voucher marked as Paid.'),
                'type': 'success',
                'sticky': False,
                'next': {'type': 'ir.actions.client', 'tag': 'reload'},
            }
        }

    def action_reset_to_submitted(self):
        """Rollback: Reset all lines in the voucher back to Submitted so manager can re-evaluate."""
        for rec in self:
            rec.line_ids.sudo().write({
                'status': 'submitted',
                'reject_reason': False,
            })
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Voucher Rolled Back'),
                'message': _('Voucher reset to Submitted for re-evaluation.'),
                'type': 'info',
                'sticky': False,
                'next': {'type': 'ir.actions.client', 'tag': 'reload'},
            }
        }

    def action_open_expense_settings(self):
        setting = self.env['expense.setting'].search([], limit=1)
        if not setting:
            setting = self.env['expense.setting'].create({})
        return {
            'name': _('Voucher Management'),
            'type': 'ir.actions.act_window',
            'res_model': 'expense.setting',
            'view_mode': 'form',
            'res_id': setting.id,
            'target': 'current',
        }


