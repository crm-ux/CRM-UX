# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class ExpenseSetting(models.Model):
    _name = 'expense.setting'
    _description = 'Voucher Management'

    name = fields.Char(string="Name", default="Voucher Management")

    # Authorized Expense Managers who can access this page alongside Admin
    authorized_manager_ids = fields.Many2many(
        'res.users',
        'expense_setting_authorized_users_rel',
        'setting_id',
        'user_id',
        string="Authorized Expense Managers",
        domain="[('share', '=', False)]",
        compute='_compute_authorized_managers',
        inverse='_inverse_authorized_managers',
        store=False,
        help="Selected users will have permission to view and manage Expense Settings alongside System Admins."
    )

    # Expense Configuration Fields
    new_expense_type_name = fields.Char(string="New Expense Type")
    new_expense_type_is_km = fields.Boolean(string="Calculate by KM", default=False)
    new_expense_type_km_rate = fields.Float(string="Rate per KM (₹)", default=0.0)
    new_expense_type_budget_limit = fields.Float(string="Limit Per Visit (₹)", default=0.0)
    new_expense_type_job_ids = fields.Many2many(
        'hr.job',
        'expense_setting_new_type_job_rel',
        'setting_id',
        'job_id',
        string="Allowed Job Positions",
        help="Select one or multiple job positions. Leave empty for all."
    )
    
    expense_type_ids = fields.Many2many(
        'service.ticket.expense.type',
        string="Expense Types",
        compute='_compute_expense_type_ids',
        readonly=False
    )

    show_department_table = fields.Boolean(
        string="Show Departments",
        default=True,
        help="Toggle to expand or shrink the Department Approver table."
    )

    has_active_department_approvers = fields.Boolean(
        string="Has Active Approvers",
        compute='_compute_has_active_department_approvers',
        store=False,
        help="Indicates whether any department currently has an active voucher approver."
    )

    department_ids = fields.Many2many(
        'hr.department',
        string="Departments",
        compute='_compute_department_ids',
        inverse='_inverse_department_ids',
        readonly=False
    )

    def _compute_department_ids(self):
        depts = self.env['hr.department'].search([])
        for rec in self:
            rec.department_ids = depts

    def _inverse_department_ids(self):
        pass

    @api.depends('department_ids.voucher_manager_id', 'department_ids.voucher_approval_active')
    def _compute_has_active_department_approvers(self):
        for rec in self:
            has_active = any(bool(d.voucher_approval_active and d.voucher_manager_id) for d in rec.department_ids)
            rec.has_active_department_approvers = has_active
            if has_active:
                rec.show_department_table = True

    def write(self, vals):
        if 'department_ids' in vals:
            for cmd in vals['department_ids']:
                if isinstance(cmd, (list, tuple)) and len(cmd) == 3 and cmd[0] == 1:
                    dept_id = cmd[1]
                    dept_vals = cmd[2]
                    if dept_vals:
                        self.env['hr.department'].browse(dept_id).write(dept_vals)
        if 'show_department_table' in vals and not vals['show_department_table']:
            for rec in self:
                if rec.has_active_department_approvers:
                    vals['show_department_table'] = True
                    break
        return super().write(vals)

    def _compute_authorized_managers(self):
        company = self.env.company
        for rec in self:
            rec.authorized_manager_ids = company.crm_authorized_expense_manager_ids

    def _inverse_authorized_managers(self):
        company = self.env.company
        for rec in self:
            company.sudo().write({
                'crm_authorized_expense_manager_ids': [(6, 0, rec.authorized_manager_ids.ids)]
            })

    @api.model
    def check_access_rights(self, operation, raise_exception=True):
        user = self.env.user
        if user._is_admin() or user.has_group('base.group_system'):
            return super().check_access_rights(operation, raise_exception=raise_exception)
        
        # Check if user is in authorized_manager_ids
        company = self.env.company
        authorized_ids = company.sudo().crm_authorized_expense_manager_ids.ids
        if user.id in authorized_ids:
            return super().check_access_rights(operation, raise_exception=raise_exception)

        if raise_exception:
            raise ValidationError(_("Access Denied: Only System Administrators and Authorized Expense Managers can view or modify Expense Settings."))
        return False

    @api.model
    def user_has_expense_settings_access(self):
        """Helper called by dashboard to check if logged-in user has permission."""
        user = self.env.user
        if user._is_admin() or user.has_group('base.group_system'):
            return True
        company = self.env.company
        return user.id in company.sudo().crm_authorized_expense_manager_ids.ids

    def _compute_expense_type_ids(self):
        all_types = self.env['service.ticket.expense.type'].search([])
        for rec in self:
            rec.expense_type_ids = all_types

    def action_add_expense_type(self):
        self.ensure_one()
        if self.new_expense_type_name:
            name = self.new_expense_type_name.strip()
            if name:
                self.env['service.ticket.expense.type'].create({
                    'name': name,
                    'is_km_based': bool(self.new_expense_type_is_km),
                    'km_rate': self.new_expense_type_km_rate or 0.0,
                    'budget_limit': self.new_expense_type_budget_limit or 0.0,
                    'budget_cycle': 'per_ticket',
                    'job_ids': [(6, 0, self.new_expense_type_job_ids.ids)] if self.new_expense_type_job_ids else False,
                    'active': True,
                })
            self.new_expense_type_name = False
            self.new_expense_type_is_km = False
            self.new_expense_type_km_rate = 0.0
            self.new_expense_type_budget_limit = 0.0
            self.new_expense_type_job_ids = [(5, 0, 0)]
        return {
            'type': 'ir.actions.client',
            'tag': 'reload',
        }

    def action_back_to_submissions(self):
        self.ensure_one()
        return {
            'name': _('Voucher Submissions'),
            'type': 'ir.actions.act_window',
            'res_model': 'service.ticket.voucher.line',
            'view_mode': 'list,form',
            'context': {'search_default_filter_submitted': 1},
            'target': 'current',
        }


class IrSequence(models.Model):
    _inherit = 'ir.sequence'

    equipment_sequence_type = fields.Selection([
        ('equipment_id', 'Equipment ID'),
        ('serial_number', 'Equipment Serial Number'),
    ], string='Name', compute='_compute_equipment_sequence_type', inverse='_inverse_equipment_sequence_type', store=True, readonly=False)

    # Equipment Category linkage for Category-wise Equipment IDs
    equipment_category_id = fields.Many2one(
        'product.category', 
        string="Category", 
        ondelete='set null', 
        help="Assign this Equipment ID sequence to a specific category. Leave blank for default."
    )

    # Link Serial Number to Equipment ID
    linked_equipment_id_seq_id = fields.Many2one(
        'ir.sequence',
        string="Linked Equipment ID Series",
        domain="[('code', '=', 'crm.equipment.id')]",
        ondelete='set null',
        help="Select which Equipment ID series this Serial Number series belongs to."
    )

    @api.depends('name', 'prefix', 'equipment_category_id')
    def _compute_display_name(self):
        for rec in self:
            if rec.code in ('crm.equipment.id', 'crm.equipment.serial'):
                prefix_info = f" [Prefix: {rec.prefix}]" if rec.prefix else ""
                cat_info = f" ({rec.equipment_category_id.name})" if rec.equipment_category_id else ""
                rec.display_name = f"{rec.name or 'Sequence'}{prefix_info}{cat_info}"
            else:
                super(IrSequence, rec)._compute_display_name()

    @api.depends('code')
    def _compute_equipment_sequence_type(self):
        for rec in self:
            if rec.code == 'crm.equipment.id':
                rec.equipment_sequence_type = 'equipment_id'
            elif rec.code == 'crm.equipment.serial':
                rec.equipment_sequence_type = 'serial_number'
            else:
                rec.equipment_sequence_type = False

    def _inverse_equipment_sequence_type(self):
        for rec in self:
            if rec.equipment_sequence_type == 'equipment_id':
                rec.code = 'crm.equipment.id'
            elif rec.equipment_sequence_type == 'serial_number':
                rec.code = 'crm.equipment.serial'

    @api.onchange('equipment_sequence_type')
    def _onchange_equipment_sequence_type(self):
        if self.equipment_sequence_type == 'equipment_id':
            self.code = 'crm.equipment.id'
            self.name = 'Equipment ID'
        elif self.equipment_sequence_type == 'serial_number':
            self.code = 'crm.equipment.serial'
            self.name = 'Equipment Serial Number'
            self.equipment_category_id = False

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            # Force company_id = False for All Companies
            if vals.get('code') in ('crm.equipment.id', 'crm.equipment.serial', 'service.ticket'):
                vals['company_id'] = False

            if vals.get('equipment_sequence_type') == 'equipment_id':
                vals['code'] = 'crm.equipment.id'
                vals['name'] = 'Equipment ID'
            elif vals.get('equipment_sequence_type') == 'serial_number':
                vals['code'] = 'crm.equipment.serial'
                vals['name'] = 'Equipment Serial Number'
                vals['equipment_category_id'] = False
        return super().create(vals_list)

    def write(self, vals):
        for record in self:
            code = vals.get('code', record.code)
            if code in ('crm.equipment.id', 'crm.equipment.serial', 'service.ticket'):
                if 'company_id' in vals and vals['company_id']:
                    vals['company_id'] = False
        return super().write(vals)

    @api.constrains('code', 'prefix', 'equipment_category_id', 'active')
    def _check_unique_equipment_sequence(self):
        for rec in self:
            if rec.code == 'crm.equipment.id' and rec.active and rec.prefix:
                clean_prefix = (rec.prefix or '').strip()

                # 1. Unique prefix among ACTIVE series
                is_module_loading = bool(
                    self.env.context.get('install_mode')
                    or self.env.context.get('module')
                    or self.env.context.get('noupdate')
                )
                if clean_prefix:
                    dup_prefix = self.sudo().search([
                        ('id', '!=', rec.id),
                        ('code', '=', 'crm.equipment.id'),
                        ('active', '=', True),
                        ('prefix', '=', clean_prefix),
                    ], limit=1)
                    if dup_prefix and not is_module_loading:
                        raise ValidationError(_(
                            "An active Equipment Series with prefix '%s' already exists (Name: %s)! "
                            "\nPlease use a unique prefix or inactivate the existing one first."
                        ) % (clean_prefix, dup_prefix.display_name or dup_prefix.name))

                # 2. Only ONE ACTIVE General series (where Category is empty)
                if not rec.equipment_category_id:
                    dup_gen = self.sudo().search([
                        ('id', '!=', rec.id),
                        ('code', '=', 'crm.equipment.id'),
                        ('active', '=', True),
                        ('equipment_category_id', '=', False),
                    ], limit=1)
                    if dup_gen and not is_module_loading:
                        raise ValidationError(_(
                            "An active General Equipment Series already exists (Name: %s)! "
                            "\nOnly one General series can be active at a time. \nPlease inactivate the existing one before activating this one."
                        ) % (dup_gen.display_name or dup_gen.name))

                # 3. Only ONE ACTIVE series per Category
                if rec.equipment_category_id:
                    dup_cat = self.sudo().search([
                        ('id', '!=', rec.id),
                        ('code', '=', 'crm.equipment.id'),
                        ('active', '=', True),
                        ('equipment_category_id', '=', rec.equipment_category_id.id),
                    ], limit=1)
                    if dup_cat:
                        raise ValidationError(_(
                            "An active series already exists for category '%s'."
                            "Each category can have only one active series to keep numbering organized. Please turn off the existing one before activating this new series."
                        ) % (rec.equipment_category_id.name, dup_cat.display_name or dup_cat.name))

