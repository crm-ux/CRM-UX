# -*- coding: utf-8 -*-
import re
from lxml import etree
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError

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

    # Equipment & Customer Linkage
    equipment_id = fields.Many2one('equipment.master', string='Equipment', domain="[('partner_id', '=', partner_id)]", tracking=True)
    amc_id = fields.Many2one('amc.contract', string='AMC Contract', domain="[('contract_status', '!=', 'draft')]", tracking=True)
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
    new_voucher_user_ids = fields.Many2many(
        'res.users',
        'service_ticket_quick_voucher_user_rel',
        'ticket_id',
        'user_id',
        string='Employees / Team',
        domain="[('share', '=', False)]",
        help="Select one or multiple employees to divide the total expense cost."   
    )
    new_voucher_expense_type_id = fields.Many2one('service.ticket.expense.type', string='Expense Type')
    has_km_lines = fields.Boolean(compute='_compute_has_km_lines', string='Has KM Lines')

    @api.depends('voucher_line_ids.is_km_based')
    def _compute_has_km_lines(self):
        for rec in self:
            rec.has_km_lines = any(line.is_km_based for line in rec.voucher_line_ids)

    new_voucher_is_km = fields.Boolean(related='new_voucher_expense_type_id.is_km_based', readonly=True)
    new_voucher_start_km = fields.Float(string='Start KM')
    new_voucher_end_km = fields.Float(string='End KM')
    new_voucher_total_km = fields.Float(string='Total KM')
    new_voucher_rate_per_km = fields.Float(string='Rate/KM (₹)')
    new_voucher_description = fields.Char(string='Description')
    new_voucher_amount = fields.Monetary(
        string='Amount', 
        currency_field='currency_id',
        compute='_compute_new_voucher_amount',
        store=True,
        readonly=False
    )
    new_voucher_bill_file = fields.Binary(string='Upload Bill')
    new_voucher_bill_filename = fields.Char(string='Bill Filename')
    currency_id = fields.Many2one('res.currency', string='Currency', default=lambda self: self.env.company.currency_id)

    @api.depends('new_voucher_total_km', 'new_voucher_rate_per_km', 'new_voucher_expense_type_id', 'new_voucher_expense_type_id.km_rate', 'new_voucher_expense_type_id.is_km_based')
    def _compute_new_voucher_amount(self):
        for rec in self:
            is_km = rec.new_voucher_is_km or (rec.new_voucher_expense_type_id and rec.new_voucher_expense_type_id.is_km_based)
            if is_km:
                rate = rec.new_voucher_rate_per_km or (rec.new_voucher_expense_type_id.km_rate if rec.new_voucher_expense_type_id else 0.0)
                if rec.new_voucher_total_km > 0 and rate > 0:
                    rec.new_voucher_amount = round(rec.new_voucher_total_km * rate, 2)
                elif rec.new_voucher_total_km == 0:
                    rec.new_voucher_amount = 0.0

    @api.onchange('new_voucher_expense_type_id')
    def _onchange_new_voucher_expense_type(self):
        if self.new_voucher_expense_type_id:
            if self.new_voucher_expense_type_id.is_km_based:
                self.new_voucher_rate_per_km = self.new_voucher_expense_type_id.km_rate or 0.0
                if self.new_voucher_total_km > 0:
                    self.new_voucher_amount = round(self.new_voucher_total_km * self.new_voucher_rate_per_km, 2)
            else:
                self.new_voucher_rate_per_km = 0.0

    @api.onchange('new_voucher_total_km', 'new_voucher_rate_per_km', 'new_voucher_expense_type_id')
    def _onchange_new_voucher_km_calc(self):
        is_km = self.new_voucher_is_km or (self.new_voucher_expense_type_id and self.new_voucher_expense_type_id.is_km_based)
        if is_km:
            rate = self.new_voucher_rate_per_km or (self.new_voucher_expense_type_id.km_rate if self.new_voucher_expense_type_id else 0.0)
            if self.new_voucher_total_km > 0 and rate > 0:
                self.new_voucher_amount = round(self.new_voucher_total_km * rate, 2)
            elif self.new_voucher_total_km == 0:
                self.new_voucher_amount = 0.0

    def action_add_voucher_line(self):
        self.ensure_one()
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

        for u in target_users:
            dept = u.crm_department_id or (u.crm_job_id and u.crm_job_id.department_id) or False
            self.env['service.ticket.voucher.line'].create({
                'ticket_id': self.id,
                'user_id': u.id,
                'department_id': dept.id if dept else False,
                'expense_type_id': exp_type.id,
                'is_km_based': exp_type.is_km_based,
                'total_km': split_km,
                'rate_per_km': self.new_voucher_rate_per_km,
                'description': self.new_voucher_description or '',
                'amount': user_splits.get(u.id, 0.0),
                'bill_file': self.new_voucher_bill_file,
                'bill_filename': self.new_voucher_bill_filename,
                'status': 'draft',
            })

        self.write({
            'new_voucher_expense_type_id': False,
            'new_voucher_user_ids': [(5, 0, 0)],
            'new_voucher_start_km': 0.0,
            'new_voucher_end_km': 0.0,
            'new_voucher_total_km': 0.0,
            'new_voucher_rate_per_km': 0.0,
            'new_voucher_description': False,
            'new_voucher_amount': 0.0,
            'new_voucher_bill_file': False,
            'new_voucher_bill_filename': False,
        })
        return False

    def action_clear_voucher_fields(self):
        """ Clears all Quick Add Expense inputs on Cancel / Clear click """
        self.ensure_one()
        self.write({
            'new_voucher_expense_type_id': False,
            'new_voucher_user_ids': [(5, 0, 0)],
            'new_voucher_start_km': 0.0,
            'new_voucher_end_km': 0.0,
            'new_voucher_total_km': 0.0,
            'new_voucher_rate_per_km': 0.0,
            'new_voucher_description': False,
            'new_voucher_amount': 0.0,
            'new_voucher_bill_file': False,
            'new_voucher_bill_filename': False,
        })
        return False

    # Group Voucher Submission fields & helpers
    voucher_employee_names = fields.Char(compute='_compute_voucher_strip', string='Employees')
    voucher_employee_count = fields.Integer(compute='_compute_voucher_strip', string='Employee Count')
    has_draft_vouchers = fields.Boolean(compute='_compute_voucher_strip', string='Has Draft Vouchers')
    show_voucher_strip = fields.Boolean(compute='_compute_voucher_strip', string='Show Voucher Strip')
    total_voucher_amount = fields.Monetary(compute='_compute_voucher_strip', string='Total Voucher Amount', currency_field='currency_id')

    @api.depends('voucher_line_ids', 'voucher_line_ids.status', 'voucher_line_ids.user_id', 'voucher_line_ids.amount')
    def _compute_voucher_strip(self):
        for rec in self:
            names = []
            has_draft = False
            total_amt = 0.0
            for line in rec.voucher_line_ids:
                total_amt += line.amount or 0.0
                if line.user_id and line.user_id.name and line.user_id.name not in names:
                    names.append(line.user_id.name)
                if line.status == 'draft':
                    has_draft = True
            rec.voucher_employee_names = ", ".join(names) if names else ''
            rec.voucher_employee_count = len(names)
            rec.has_draft_vouchers = has_draft
            # Strip is only visible when there are multiple employees AND active draft/pending submissions to act on
            rec.show_voucher_strip = len(names) > 1 and has_draft
            rec.total_voucher_amount = total_amt

    def action_submit_all_vouchers(self):
        """Submit all draft voucher lines together as a group."""
        self.ensure_one()
        draft_lines = self.voucher_line_ids.filtered(lambda l: l.status == 'draft')
        if not draft_lines:
            # If all are already submitted/empty, submit any pending lines
            draft_lines = self.voucher_line_ids.filtered(lambda l: l.status not in ('approved', 'rejected'))
        if draft_lines:
            draft_lines.write({'status': 'submitted'})
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
        # When ticket itself is saved by user or system, ensure temporary Quick Add voucher draft fields are reset
        res = super(ServiceTicket, self).write(vals)
        # If write was not directly updating new_voucher fields, clear them if any were left unsaved
        voucher_keys = {'new_voucher_expense_type_id', 'new_voucher_user_ids', 'new_voucher_total_km', 'new_voucher_amount', 'new_voucher_description', 'new_voucher_bill_file'}
        if not voucher_keys.intersection(vals.keys()):
            for rec in self:
                if rec.new_voucher_expense_type_id or rec.new_voucher_user_ids or rec.new_voucher_total_km or rec.new_voucher_amount:
                    super(ServiceTicket, rec).write({
                        'new_voucher_expense_type_id': False,
                        'new_voucher_user_ids': [(5, 0, 0)],
                        'new_voucher_start_km': 0.0,
                        'new_voucher_end_km': 0.0,
                        'new_voucher_total_km': 0.0,
                        'new_voucher_rate_per_km': 0.0,
                        'new_voucher_description': False,
                        'new_voucher_amount': 0.0,
                        'new_voucher_bill_file': False,
                        'new_voucher_bill_filename': False,
                    })
        return res

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
    expense_manager_id = fields.Many2one('res.users', string='Approved By', readonly=True)
    reject_reason = fields.Char(string='Rejection Reason')

    def action_approve(self):
        for rec in self:
            rec.write({
                'status': 'approved',
                'expense_manager_id': self.env.user.id,
            })
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Voucher Approved'),
                'message': _('Voucher for %s (%s) of ₹%0.2f has been approved successfully.') % (
                    self.user_id.name or 'Employee',
                    self.expense_type_id.name or 'Expense',
                    self.amount or 0.0
                ),
                'type': 'success',
                'sticky': False,
                'next': {'type': 'ir.actions.client', 'tag': 'reload'},
            }
        }

    def action_reject(self):
        for rec in self:
            rec.write({
                'status': 'rejected',
                'expense_manager_id': self.env.user.id,
            })
        reason_msg = f" Reason: {self.reject_reason}" if self.reject_reason else ""
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Voucher Rejected'),
                'message': _('Voucher for %s (%s) of ₹%0.2f has been rejected.%s') % (
                    self.user_id.name or 'Employee',
                    self.expense_type_id.name or 'Expense',
                    self.amount or 0.0,
                    reason_msg
                ),
                'type': 'danger',
                'sticky': False,
                'next': {'type': 'ir.actions.client', 'tag': 'reload'},
            }
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
        url = f'/web/content/{self._name}/{self.id}/bill_file/{self.bill_filename or "bill"}?download=false'
        return {
            'type': 'ir.actions.act_url',
            'url': url,
            'target': 'new',
        }
