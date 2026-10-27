# -*- coding: utf-8 -*-
import re
from lxml import etree
from odoo import models, fields, api, _
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
    ticket_datetime = fields.Datetime(string='Ticket Date & Time', default=fields.Datetime.now, required=True, tracking=True)
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
        return super().create(vals_list)

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
        return super().write(vals)

    # Assignment & Schedule
    engineer_id = fields.Many2one('res.users', string='Assigned Engineer', tracking=True)
    engineer_contact = fields.Char(string='Engineer Contact')
    engineer_email = fields.Char(string='Engineer Email')
    visit_date = fields.Date(string='Visit Date', tracking=True)

    @api.onchange('visit_date', 'ticket_datetime')
    def _onchange_visit_date_warning(self):
        if self.visit_date and self.ticket_datetime:
            ticket_date = self.ticket_datetime.date()
            if self.visit_date < ticket_date:
                inv_date = self.visit_date.strftime('%d-%m-%Y')
                t_date = ticket_date.strftime('%d-%m-%Y')
                self.visit_date = False
                return {
                    'warning': {
                        'title': _('Invalid Visit Date'),
                        'message': _("Visit Date (%s) cannot be earlier than Ticket Date (%s).") % (inv_date, t_date),
                    }
                }

    @api.constrains('visit_date', 'ticket_datetime')
    def _check_visit_date(self):
        for rec in self:
            if rec.visit_date and rec.ticket_datetime:
                ticket_date = rec.ticket_datetime.date()
                if rec.visit_date < ticket_date:
                    raise ValidationError(_(
                        "Visit Date (%s) cannot be earlier than Ticket Date (%s)."
                    ) % (rec.visit_date.strftime('%d-%m-%Y'), ticket_date.strftime('%d-%m-%Y')))

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
            batches = rec.voucher_batch_ids.filtered(lambda b: b.line_ids)
            if not batches:
                rec.submitted_vouchers_html = False
                continue

            html_parts = []
            for batch in batches:
                st = batch.status or 'submitted'
                badge_bg = '#fef3c7'
                badge_color = '#d97706'
                if st == 'approved':
                    badge_bg = '#d1fae5'
                    badge_color = '#059669'
                elif st == 'rejected':
                    badge_bg = '#fee2e2'
                    badge_color = '#dc2626'
                st_label = st.capitalize()

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
                        <span class="fw-bold text-dark" style="font-size: 13px;">Submitted:</span>
                        <span class="badge py-1 px-2 fw-bold" style="background-color: #f1f5f9; color: #334155; border: 1px solid #cbd5e1; font-size: 13px;">{vch_sub_date}</span>
                        <span class="text-muted fw-bold mx-1">|</span>
                        <span class="fw-bold text-dark" style="font-size: 13px;">Expense Date(s):</span>
                        <span class="badge py-1 px-2 fw-bold" style="background-color: #e8f0fe; color: #0b3d91; border: 1px solid #b8d0f8; font-size: 13px;">{vch_exp_dates}</span>
                        <span class="text-muted fw-bold mx-1">|</span>
                        <span class="fw-bold text-dark" style="font-size: 13px;">Employee(s):</span>
                        <span class="badge py-1 px-2 fw-bold" style="background-color: #e8f0fe; color: #0b3d91; border: 1px solid #b8d0f8; font-size: 13px;">{vch_emps}</span>
                    </div>
                    <div>
                        <span class="badge py-1 px-2 fw-bold" style="background-color: {badge_bg}; color: {badge_color}; font-size: 12px; border-radius: 4px;">{st_label}</span>
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
                    
                    if line.bill_file:
                        fn = line.bill_filename or 'Bill'
                        bill_link = f'<a href="/web/content/service.ticket.voucher.line/{line.id}/bill_file/{fn}?download=true" target="_blank" class="btn btn-sm p-0" style="color: #0b3d91 !important; font-weight: 600;" title="View / Download Bill"><i class="fa fa-paperclip me-1"></i>View Bill</a>'
                    else:
                        bill_link = '<span class="text-muted">-</span>'

                    l_st = line.status or 'submitted'
                    l_badge_bg = '#fef3c7'
                    l_badge_color = '#d97706'
                    if l_st == 'approved':
                        l_badge_bg = '#d1fae5'
                        l_badge_color = '#059669'
                    elif l_st == 'rejected':
                        l_badge_bg = '#fee2e2'
                        l_badge_color = '#dc2626'
                    l_badge = f'<span class="badge py-1 px-2 fw-semibold" style="background-color: {l_badge_bg}; color: {l_badge_color};">{l_st.capitalize()}</span>'

                    row = f"""
                    <tr style="border-bottom: 1px solid #f1f5f9;">
                        <td style="padding: 8px;">{l_date}</td>
                        <td style="padding: 8px; font-weight: 500;">{l_emp}</td>
                        <td style="padding: 8px; font-weight: 600; color: #1e293b;">{l_type}</td>
                        {l_km_cells}
                        <td style="padding: 8px; color: #475569;">{l_desc}</td>
                        <td style="padding: 8px; text-align: right; font-weight: 700; color: #0f172a;">{l_amt}</td>
                        <td style="padding: 8px; text-align: center;">{bill_link}</td>
                        <td style="padding: 8px; text-align: center;">{l_badge}</td>
                    </tr>
                    """
                    rows_html.append(row)

                batch_total = f"₹ {batch.total_amount:,.2f}" if batch.total_amount else "₹ 0.00"
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
                                <th style="padding: 8px; border-bottom: 2px solid #dee2e6; text-align: right;">Amount</th>
                                <th style="padding: 8px; border-bottom: 2px solid #dee2e6; text-align: center;">Bill</th>
                                <th style="padding: 8px; border-bottom: 2px solid #dee2e6; text-align: center;">Status</th>
                            </tr>
                        </thead>
                        <tbody style="font-size: 13px;">
                            {''.join(rows_html)}
                        </tbody>
                        <tfoot style="background-color: #f8fafc; border-top: 2px solid #e2e8f0;">
                            <tr>
                                <td colspan="{col_span}" style="padding: 8px; text-align: right; font-weight: 700; color: #334155;">Subtotal:</td>
                                <td style="padding: 8px; text-align: right; font-weight: 800; font-size: 14px; color: #0b3d91;">{batch_total}</td>
                                <td colspan="2"></td>
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
        domain="[('share', '=', False)]",
        help="Select one or multiple employees to divide the total expense cost."   
    )
    new_voucher_date = fields.Date(string='Expense Date')
    new_voucher_expense_type_id = fields.Many2one('service.ticket.expense.type', string='Expense Type')
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
            self.new_voucher_amount = 0.0

    @api.onchange('new_voucher_total_km', 'new_voucher_expense_type_id')
    def _onchange_new_voucher_km_calc(self):
        is_km = self.new_voucher_is_km or (self.new_voucher_expense_type_id and self.new_voucher_expense_type_id.is_km_based)
        if is_km:
            rate = self.new_voucher_expense_type_id.km_rate if self.new_voucher_expense_type_id else 0.0
            if self.new_voucher_total_km > 0 and rate > 0:
                self.new_voucher_amount = round(self.new_voucher_total_km * rate, 2)
            elif self.new_voucher_total_km == 0:
                self.new_voucher_amount = 0.0

    def action_add_voucher_line(self):
        self.ensure_one()
        if not self.new_voucher_date:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Missing Expense Date',
                    'message': 'Please select an Expense Date.',
                    'type': 'warning',
                    'sticky': False,
                }
            }
        if not self.new_voucher_user_ids:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Missing Employee',
                    'message': 'Please select at least one Employee before adding an expense.',
                    'type': 'warning',
                    'sticky': False,
                }
            }
        if not self.new_voucher_amount or self.new_voucher_amount <= 0:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Missing Amount',
                    'message': 'Please enter a valid expense Amount greater than 0.',
                    'type': 'warning',
                    'sticky': False,
                }
            }
        if not self.new_voucher_expense_type_id:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Missing Expense Type',
                    'message': 'Please select an Expense Type.',
                    'type': 'warning',
                    'sticky': False,
                }
            }

        target_users = self.new_voucher_user_ids
        user_count = len(target_users)
        exp_type = self.new_voucher_expense_type_id
        split_km = round(self.new_voucher_total_km / user_count, 2) if (user_count > 0 and self.new_voucher_is_km) else self.new_voucher_total_km

        # 1. Determine each user's specific per-visit limit for this expense category
        # Look for position-specific rule or fallback to exp_type.budget_limit
        user_limits = {}
        for u in target_users:
            user_job = u.crm_job_id
            u_limit = 0.0
            if user_job:
                # Look for expense type specifically matching this user's job position with same base name
                # e.g., "Food (Manager)" or where job_ids contains user_job
                pos_types = self.env['service.ticket.expense.type'].search([
                    ('active', '=', True),
                    ('job_ids', 'in', [user_job.id]),
                    ('is_km_based', '=', exp_type.is_km_based),
                ])
                # Check if matching base category or fallback
                matched = pos_types.filtered(lambda t: exp_type.name.split('(')[0].strip().lower() in t.name.lower())
                if matched:
                    u_limit = matched[0].budget_limit or 0.0
            
            # If no specific position limit found, use the selected exp_type limit
            if u_limit <= 0.0:
                u_limit = exp_type.budget_limit or 0.0

            user_limits[u.id] = u_limit

        # 2. Proportional Split Calculation
        total_budget = sum(user_limits.values())
        has_positive_limits = total_budget > 0 and all(user_limits[u.id] > 0 for u in target_users)

        user_splits = {}
        if not exp_type.is_km_based and has_positive_limits:
            # Total bill is distributed according to each person's limit ratio: (user_limit / total_budget)
            # Capped at each individual's maximum allowed limit
            for u in target_users:
                u_ratio = user_limits[u.id] / total_budget
                u_share = round(self.new_voucher_amount * u_ratio, 2)
                # Cap strictly to individual limit
                if u_share > user_limits[u.id]:
                    u_share = user_limits[u.id]
                user_splits[u.id] = u_share
        else:
            # Equal division fallback (capped if limit defined)
            raw_split = round(self.new_voucher_amount / user_count, 2) if user_count > 0 else self.new_voucher_amount
            for u in target_users:
                u_limit = user_limits.get(u.id, 0.0)
                if not exp_type.is_km_based and u_limit > 0 and raw_split > u_limit:
                    user_splits[u.id] = u_limit
                else:
                    user_splits[u.id] = raw_split

        rate_val = self.new_voucher_rate_per_km or exp_type.km_rate or 0.0
        km_val = self.new_voucher_total_km if exp_type.is_km_based else 0.0
        split_km = round(km_val / user_count, 2) if (user_count > 0 and exp_type.is_km_based) else km_val

        login_user = self.env.user
        for u in target_users:
            dept = u.crm_department_id or (u.crm_job_id and u.crm_job_id.department_id) or False
            other_names = ", ".join([other.name for other in target_users if other.id != u.id and other.id != login_user.id])
            self.env['service.ticket.voucher.line'].create({
                'ticket_id': self.id,
                'expense_date': self.new_voucher_date or fields.Date.context_today(self),
                'user_id': u.id,
                'submitted_by_user_id': login_user.id,
                'other_employee_names': other_names or '',
                'department_id': dept.id if dept else False,
                'expense_type_id': exp_type.id,
                'is_km_based': exp_type.is_km_based,
                'total_km': split_km if exp_type.is_km_based else 0.0,
                'rate_per_km': rate_val if exp_type.is_km_based else 0.0,
                'description': self.new_voucher_description or '',
                'amount': user_splits.get(u.id, 0.0),
                'bill_file': self.new_voucher_bill_file,
                'bill_filename': self.new_voucher_bill_filename,
                'status': 'draft',
            })

        self.new_voucher_date = False
        self.new_voucher_expense_type_id = False
        self.new_voucher_user_ids = [(5, 0, 0)]
        self.new_voucher_start_km = 0.0
        self.new_voucher_end_km = 0.0
        self.new_voucher_total_km = 0.0
        self.new_voucher_description = False
        self.new_voucher_amount = 0.0
        self.new_voucher_bill_file = False
        self.new_voucher_bill_filename = False
        return True

    def action_clear_voucher_fields(self):
        """ Clears all Quick Add Expense inputs instantly without reloading the entire ticket """
        self.ensure_one()
        self.write({
            'new_voucher_date': False,
            'new_voucher_expense_type_id': False,
            'new_voucher_user_ids': [(5, 0, 0)],
            'new_voucher_start_km': 0.0,
            'new_voucher_end_km': 0.0,
            'new_voucher_total_km': 0.0,
            'new_voucher_description': False,
            'new_voucher_amount': 0.0,
            'new_voucher_bill_file': False,
            'new_voucher_bill_filename': False,
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

    def action_submit_all_vouchers(self):
        """Submit all draft voucher lines together to the Expense Manager."""
        self.ensure_one()
        draft_lines = self.voucher_line_ids.filtered(lambda l: l.status == 'draft')
        if not draft_lines:
            draft_lines = self.voucher_line_ids.filtered(lambda l: l.status not in ('approved', 'rejected'))
        if draft_lines:
            # Group lines by employee and assign batch_id if not already assigned
            now_ts = fields.Datetime.now().strftime('%Y%m%d%H%M%S')
            mgr = self.env.company.crm_authorized_expense_manager_ids[:1]
            approver_uid = mgr.id if mgr else 2
            
            # Combine all employee names into one group submission
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
            primary_emp = draft_lines[0].user_id
            # In "Other Employees", only show the team members excluding who submitted it
            submitter_name = self.env.user.name
            other_names_list = [n for n in all_names if n != submitter_name]
            other_team_names = ", ".join(other_names_list)
            
            # Check if there is already an existing pending batch (not yet approved/rejected) on this ticket
            pending_batch = self.voucher_batch_ids.filtered(lambda b: b.status == 'submitted')[:1]
            if pending_batch:
                batch_rec = pending_batch
                # Update employee names on existing batch
                existing_names = [n.strip() for n in (batch_rec.all_employee_names or '').split(',') if n.strip()]
                for n in all_names:
                    if n not in existing_names:
                        existing_names.append(n)
                batch_rec.all_employee_names = ", ".join(existing_names)
            else:
                seq_val = self.env['ir.sequence'].next_by_code('service.ticket.voucher.seq')
                if not seq_val:
                    year = fields.Date.today().year
                    count = self.env['service.ticket.voucher.batch'].search_count([]) + 1
                    seq_val = f"VCH-{year}-{count:05d}"
                batch_rec = self.env['service.ticket.voucher.batch'].create({
                    'ticket_id': self.id,
                    'user_id': primary_emp.id,
                    'submitted_by_user_id': self.env.user.id,
                    'expense_manager_id': approver_uid,
                    'other_employee_names': other_team_names,
                    'all_employee_names': combined_emp_names,
                    'name': seq_val,
                })
            
            # Link ALL lines together into this batch
            draft_lines.write({
                'status': 'submitted',
                'batch_id': batch_rec.id,
                'submitted_by_user_id': self.env.user.id,
            })
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Expenses Submitted'),
                    'message': _('%d expense voucher(s) have been submitted to the Expense Manager.') % len(draft_lines),
                    'type': 'success',
                    'sticky': False,
                }
            }
        return True

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
        return super(ServiceTicket, self).write(vals)

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
    budget_limit = fields.Float(string='Limit Per Visit (₹)', default=0.0)
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

class ServiceTicketVoucherLine(models.Model):
    _name = 'service.ticket.voucher.line'
    _description = 'Service Ticket Voucher Line'
    _order = 'id desc'

    ticket_id = fields.Many2one('service.ticket', string='Service Ticket', ondelete='cascade', required=True)
    expense_date = fields.Date(string='Date', default=fields.Date.context_today, required=True, index=True)
    user_id = fields.Many2one('res.users', string='Employee', required=False, default=lambda self: self.env.user)
    department_id = fields.Many2one('hr.department', string='Department')
    expense_type_id = fields.Many2one('service.ticket.expense.type', string='Expense Type', required=True)
    is_km_based = fields.Boolean(related='expense_type_id.is_km_based', string='KM Based', store=True, readonly=True)

    @api.depends('ticket_id.engineer_id', 'ticket_id.create_uid')
    def _compute_user_id(self):
        for rec in self:
            if not rec.user_id:
                rec.user_id = rec.ticket_id.engineer_id or rec.ticket_id.create_uid or self.env.user
    total_km = fields.Float(string='Total KM')
    rate_per_km = fields.Float(string='Rate/KM (₹)')
    description = fields.Char(string='Description', placeholder='Enter description...')
    currency_id = fields.Many2one('res.currency', string='Currency', related='ticket_id.currency_id', store=True)
    amount = fields.Monetary(string='Amount', currency_field='currency_id')

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
    bill_preview = fields.Binary(related='bill_file', string='Bill Preview', readonly=True)
    status = fields.Selection([
        ('draft', 'Draft'),
        ('submitted', 'Submitted'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ], string='Status', default='draft', required=True)

    batch_id = fields.Many2one('service.ticket.voucher.batch', string='Submission Batch', ondelete='cascade', index=True)
    voucher_id = fields.Char(related='batch_id.name', string='Voucher ID', store=True, readonly=True)
    batch_key = fields.Char(string='Batch Key', index=True)
    submitted_by_user_id = fields.Many2one('res.users', string='Submitted By', default=lambda self: self.env.user)
    other_employee_names = fields.Char(string='Other Employees')
    ticket_voucher_line_ids = fields.One2many(related='ticket_id.voucher_line_ids', string='All Ticket Expenses', readonly=True)
    voucher_employee_names = fields.Char(related='ticket_id.voucher_employee_names', string='Employees', readonly=True)

    def action_submit_line(self): 
        """Submit this single draft voucher line."""
        for rec in self:
            if rec.status == 'draft':
                mgr = rec.ticket_id.company_id.crm_authorized_expense_manager_ids[:1] if rec.ticket_id.company_id else False
                approver_uid = mgr.id if mgr else 2
                today_str = fields.Date.today().strftime('%d/%m/%Y')
                batch_name = f"VCH/{rec.ticket_id.ticket_id or rec.ticket_id.name}/{today_str}"
                batch_rec = self.env['service.ticket.voucher.batch'].create({
                    'ticket_id': rec.ticket_id.id,
                    'user_id': rec.user_id.id,
                    'submitted_by_user_id': self.env.user.id,
                    'expense_manager_id': approver_uid,
                    'other_employee_names': rec.other_employee_names or '',
                    'all_employee_names': rec.user_id.name or '',
                    'name': batch_name,
                })
                rec.write({
                    'status': 'submitted',
                    'batch_id': batch_rec.id,
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

    expense_manager_id = fields.Many2one('res.users', string='Approved By')
    reject_reason = fields.Char(string='Rejection Reason')

    def action_approve(self):
        for rec in self:
            rec.sudo().write({
                'status': 'approved',
                'expense_manager_id': self.env.user.id,
            })
        msg = _('Voucher approved successfully.')
        if len(self) == 1:
            msg = _('Voucher for %s (%s) of ₹%0.2f has been approved successfully.') % (
                self.user_id.name or 'Employee',
                self.expense_type_id.name or 'Expense',
                self.amount or 0.0
            )
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Voucher Approved'),
                'message': msg,
                'type': 'success',
                'sticky': False,
                'next': {'type': 'ir.actions.client', 'tag': 'reload'},
            }
        }

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


class ServiceTicketVoucherRejectWizard(models.TransientModel):
    _name = 'service.ticket.voucher.reject.wizard'
    _description = 'Reject Voucher Remark Wizard'

    voucher_line_id = fields.Many2one('service.ticket.voucher.line', string='Voucher Line', required=True)
    employee_name = fields.Char(related='voucher_line_id.user_id.name', string='Employee', readonly=True)
    expense_type_name = fields.Char(related='voucher_line_id.expense_type_id.name', string='Expense Type', readonly=True)
    amount = fields.Monetary(related='voucher_line_id.amount', string='Amount', currency_field='currency_id', readonly=True)
    currency_id = fields.Many2one(related='voucher_line_id.currency_id', readonly=True)
    reject_reason = fields.Text(string='Rejection Remark / Reason', required=True)

    def action_confirm_reject(self):
        self.ensure_one()
        line = self.voucher_line_id
        line.sudo().write({
            'status': 'rejected',
            'reject_reason': self.reject_reason,
            'expense_manager_id': self.env.user.id,
        })
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Voucher Rejected'),
                'message': _('Voucher for %s (%s) of ₹%0.2f has been rejected. Reason: %s') % (
                    line.user_id.name or 'Employee',
                    line.expense_type_id.name or 'Expense',
                    line.amount or 0.0,
                    self.reject_reason
                ),
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
    _description = 'Service Ticket Voucher Submission'
    _order = 'id desc'

    name = fields.Char(string='Voucher ID', default=lambda self: _('New'))
    create_date = fields.Datetime(string='Submitted Date', readonly=True)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('name') or vals.get('name') == _('New'):
                seq_val = self.env['ir.sequence'].next_by_code('service.ticket.voucher.seq')
                if not seq_val:
                    year = fields.Date.today().year
                    count = self.search_count([]) + 1
                    seq_val = f"VCH-{year}-{count:05d}"
                vals['name'] = seq_val
        return super(ServiceTicketVoucherBatch, self).create(vals_list)
    submission_date = fields.Date(string='Expense Date', default=fields.Date.context_today, index=True)
    expense_date = fields.Date(related='submission_date', string='Expense Date', readonly=True)
    expense_dates = fields.Char(string='Expense Dates', compute='_compute_expense_dates', store=True)
    ticket_id = fields.Many2one('service.ticket', string='Service Ticket', required=True, ondelete='cascade')
    user_id = fields.Many2one('res.users', string='Employee', required=True)
    submitted_by_user_id = fields.Many2one('res.users', string='Submitted By', default=lambda self: self.env.user)
    other_employee_names = fields.Char(string='Other Employees')
    all_employee_names = fields.Char(compute='_compute_all_employee_names', string='Employees', store=True)
    voucher_employee_names = fields.Char(related='all_employee_names', string='Employees', readonly=True)
    ticket_voucher_line_ids = fields.One2many(related='ticket_id.voucher_line_ids', string='All Ticket Expenses', readonly=True)

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


    currency_id = fields.Many2one('res.currency', string='Currency', related='ticket_id.currency_id')
    total_amount = fields.Monetary(compute='_compute_total_amount', string='Total Amount', currency_field='currency_id', store=True)
    status = fields.Selection([
        ('submitted', 'Submitted'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ], string='Status', compute='_compute_status', store=True)
    def _default_expense_manager_id(self):
        mgr = self.env.company.crm_authorized_expense_manager_ids[:1]
        return mgr.id if mgr else 2

    expense_manager_id = fields.Many2one('res.users', string='Approver', default=_default_expense_manager_id)

    @api.depends('line_ids.amount')
    def _compute_total_amount(self):
        for rec in self:
            rec.total_amount = sum(rec.line_ids.mapped('amount'))

    @api.depends('line_ids.status')
    def _compute_status(self):
        for rec in self:
            statuses = rec.line_ids.mapped('status')
            if all(s == 'approved' for s in statuses) if statuses else False:
                rec.status = 'approved'
            elif any(s == 'rejected' for s in statuses):
                rec.status = 'rejected'
            else:
                rec.status = 'submitted'

    def action_approve(self):
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
        for rec in self:
            rec.line_ids.sudo().write({
                'status': 'approved',
                'expense_manager_id': self.env.user.id,
            })
            rec.sudo().write({'expense_manager_id': self.env.user.id})
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Vouchers Approved'),
                'message': _('All vouchers in this submission have been approved.'),
                'type': 'success',
                'sticky': False,
                'next': {'type': 'ir.actions.client', 'tag': 'reload'},
            }
        }

    def action_reject_all(self):
        for rec in self:
            rec.line_ids.sudo().write({
                'status': 'rejected',
                'expense_manager_id': self.env.user.id,
            })
            rec.sudo().write({'expense_manager_id': self.env.user.id})
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Vouchers Rejected'),
                'message': _('All vouchers in this submission have been rejected.'),
                'type': 'danger',
                'sticky': False,
                'next': {'type': 'ir.actions.client', 'tag': 'reload'},
            }
        }


