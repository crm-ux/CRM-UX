from odoo import models, fields, api

class ResUsers(models.Model):
    _inherit = 'res.users'

    # Hierarchy & Organization dropdowns
    employee_id = fields.Many2one('hr.employee', string='Related Employee', compute='_compute_employee_id', readonly=True)
    crm_department_id = fields.Many2one('hr.department', string='Department')
    crm_job_id = fields.Many2one('hr.job', string='Job Position / Role')
    crm_manager_id = fields.Many2one('res.users', string='Reports To (Manager)', domain="[('share', '=', False)]")
    crm_expense_manager_id = fields.Many2one('res.users', string='Expense / Voucher Approver', domain="[('share', '=', False)]")
    crm_employee_tag_ids = fields.Many2many('hr.employee.category', string='Employee Tags')
    crm_subordinate_ids = fields.One2many('res.users', 'crm_manager_id', string='Direct Reports / Subordinates')

    # Department Scope (Inherited from Job Role)
    crm_department_ids = fields.Many2many('hr.department', 'res_users_hr_department_rel', 'user_id', 'department_id', string='Allowed Departments', compute='_compute_department_scope', store=True)

    def action_revoke_role(self):
        """Unassigns this role from the user."""
        for user in self:
            user.sudo().write({'crm_job_id': False})
        return True

    perm_export = fields.Selection([
        ('none', 'No'),
        ('export', 'Yes'),
    ], string='Excel Export', default='none')

    perm_company = fields.Selection([
        ('none', 'No'),
        ('create', 'Yes'),
    ], string='Company Creation', default='none')

    perm_lead_quote = fields.Selection([
        ('none', 'No'),
        ('own', 'User: Own Documents Only'),
        ('all', 'User: All Documents'),
        ('admin', 'Administrator'),
    ], string='Lead & Quotation', default='own')

    perm_service_ticket = fields.Selection([
        ('none', 'No'),
        ('own', 'User: Own Documents Only'),
        ('all', 'User: All Documents'),
        ('admin', 'Administrator'),
    ], string='Service Ticket', default='own')

    perm_amc = fields.Selection([
        ('none', 'No'),
        ('own', 'User: Own Documents Only'),
        ('all', 'User: All Documents'),
        ('admin', 'Administrator'),
    ], string='AMC Contract', default='own')

    perm_product_create = fields.Boolean(string='Create Product', default=True)
    perm_product_write = fields.Boolean(string='Update Product', default=True)
    perm_product_read = fields.Boolean(string='View Product', default=True)
    perm_product_unlink = fields.Boolean(string='Delete Product', default=False)

    perm_customer_create = fields.Boolean(string='Create Customer', default=True)
    perm_customer_write = fields.Boolean(string='Update Customer', default=True)
    perm_customer_read = fields.Boolean(string='View Customer', default=True)
    perm_customer_unlink = fields.Boolean(string='Delete Customer', default=False)

    perm_equipment_create = fields.Boolean(string='Create Equipment', default=True)
    perm_equipment_write = fields.Boolean(string='Update Equipment', default=True)
    perm_equipment_read = fields.Boolean(string='View Equipment', default=True)
    perm_equipment_unlink = fields.Boolean(string='Delete Equipment', default=False)


    @api.onchange('crm_job_id')
    def _onchange_crm_job_id_sync_permissions(self):
        """When Job Position is selected on user form, apply group permissions to this user."""
        if self.crm_job_id and self._origin.id:
            # Safely apply to the real database record
            real_user = self.env['res.users'].browse(self._origin.id)

    def _apply_job_permissions(self, job):
        """Applies permissions defined on hr.job down to this user (1-way sync only)."""
        for user in self:
            if not user.id or user.id in (2, 10, 11) or user.has_group('base.group_system'):
                continue

            g_own = self.env.ref('sales_team.group_sale_salesman', raise_if_not_found=False)
            g_all = self.env.ref('sales_team.group_sale_salesman_all_leads', raise_if_not_found=False)
            g_admin = self.env.ref('sales_team.group_sale_manager', raise_if_not_found=False)
            
    
            group_ops = []

            # 1. Excel Export
            g_export = self.env.ref('base.group_allow_export', raise_if_not_found=False)
            if g_export:
                if job.perm_export == 'export':
                    group_ops.append((4, g_export.id))
                else:
                    group_ops.append((3, g_export.id))

            # 2. Company Creation (Multi Company)
            g_multi = self.env.ref('base.group_multi_company', raise_if_not_found=False)
            if g_multi:
                if job.perm_company == 'create':
                    group_ops.append((4, g_multi.id))

            # 3. Equipment Master permissions
            g_eq_own = self.env.ref('custom_crm_extended.group_equipment_own', raise_if_not_found=False)
            g_eq_all = self.env.ref('custom_crm_extended.group_equipment_all', raise_if_not_found=False)
            if g_eq_own and g_eq_all:
                group_ops.append((3, g_eq_own.id))
                group_ops.append((3, g_eq_all.id))
                if getattr(job, 'perm_equipment', None) == 'own':
                    group_ops.append((4, g_eq_own.id))
                elif getattr(job, 'perm_equipment', None) in ('all', 'admin'):
                    group_ops.append((4, g_eq_all.id))

            # 4. Lead & Quotation Sales groups
            sales_gids = [g.id for g in [g_own, g_all, g_admin] if g]
            for sg_id in sales_gids:
                group_ops.append((3, sg_id))

            target_sale_gid = None
            if job.perm_lead_quote == 'admin' and g_admin:
                target_sale_gid = g_admin.id
            elif job.perm_lead_quote == 'all' and g_all:
                target_sale_gid = g_all.id
            elif job.perm_lead_quote == 'own' and g_own:
                target_sale_gid = g_own.id

            if target_sale_gid:
                group_ops.append((4, target_sale_gid))

            # 5. Customer / Contact Creation
            g_contact = self.env.ref('base.group_partner_manager', raise_if_not_found=False)
            if g_contact:
                if job.perm_customer_create:
                    group_ops.append((4, g_contact.id))
                else:
                    group_ops.append((3, g_contact.id))

            # 6. Product Catalog
            if job.perm_product_create and g_admin:
                group_ops.append((4, g_admin.id))

            # Apply all permission group changes via safe ORM
            user_vals = {
                'perm_lead_quote': job.perm_lead_quote,
                'perm_export': job.perm_export,
                'perm_company': job.perm_company,
                'perm_service_ticket': job.perm_service_ticket,
                'perm_amc': job.perm_amc,
                'perm_product_create': job.perm_product_create,
                'perm_product_write': job.perm_product_write,
                'perm_product_read': job.perm_product_read,
                'perm_product_unlink': job.perm_product_unlink,
                'perm_customer_create': job.perm_customer_create,
                'perm_customer_write': job.perm_customer_write,
                'perm_customer_read': job.perm_customer_read,
                'perm_customer_unlink': job.perm_customer_unlink,
                'perm_equipment_create': job.perm_equipment_create,
                'perm_equipment_write': job.perm_equipment_write,
                'perm_equipment_read': job.perm_equipment_read,
                'perm_equipment_unlink': job.perm_equipment_unlink,
            }
            user.sudo().with_context(skip_sync=True).write(user_vals)

            pass


    @api.depends('name', 'employee_ids')
    def _compute_employee_id(self):
        for user in self:
            if user.id:
                emp = self.env['hr.employee'].sudo().search([('user_id', '=', user.id)], limit=1)
                user.employee_id = emp.id if emp else False
            else:
                user.employee_id = False

    def _compute_employee_count(self):
        super()._compute_employee_count()
        for user in self:
            if not user.employee_count and user.id:
                emp_cnt = self.env['hr.employee'].sudo().search_count([('user_id', '=', user.id)])
                user.employee_count = emp_cnt

    @api.model_create_multi
    def create(self, vals_list):
        users = super().create(vals_list)
        self._assign_default_groups(users)
        for user, vals in zip(users, vals_list):
            if vals.get('crm_job_id'):
                job = self.env['hr.job'].browse(vals['crm_job_id'])
                user._apply_job_permissions(job)
        return users

    def write(self, vals):
        # 1. When archiving (active=False), release the login so new employees can reuse the name/login
        if vals.get('active') is False:
            for user in self:
                if user.active and user.login and not user.login.startswith('archived_'):
                    super(ResUsers, user).write({'login': f"archived_{user.id}_{user.login}"})

        # 2. When unarchiving (active=True), safely restore the original login if not taken
        elif vals.get('active') is True:
            for user in self:
                if not user.active and user.login and user.login.startswith(f"archived_{user.id}_"):
                    orig_login = user.login.split(f"archived_{user.id}_", 1)[1]
                    # Only restore if another user hasn't claimed it while archived
                    taken = self.env['res.users'].sudo().search_count([('login', '=', orig_login), ('id', '!=', user.id)])
                    if not taken:
                        super(ResUsers, user).write({'login': orig_login})

        res = super().write(vals)
        if 'crm_job_id' in vals and vals['crm_job_id']:
            job = self.env['hr.job'].browse(vals['crm_job_id'])
            self._apply_job_permissions(job)
        if not self.env.context.get('skip_sync'):
            self.with_context(skip_sync=True)._sync_employee_records(self)
        return res

    
    def _assign_default_groups(self, users):
        try:
            portal_group = self.env.ref('base.group_portal')
            public_group = self.env.ref('base.group_public')
            internal_group = self.env.ref('base.group_user')

            groups_to_add = [
                'sales_team.group_sale_salesman',
                'base.group_multi_company',
            ]
            all_companies = self.env['res.company'].sudo().search([])

            for user in users:
                # Assign all companies if not already assigned
                c_ops = [(4, c.id) for c in all_companies if c not in user.company_ids]
                if c_ops:
                    user.sudo().with_context(skip_sync=True).write({'company_ids': c_ops})
        except Exception:
            pass

    def unlink(self):
        # Safely delete linked hr.employee records first so Odoo doesn't raise restrict error
        employees = self.env['hr.employee'].sudo().search([('user_id', 'in', self.ids)])
        if employees:
            employees.unlink()
        return super(ResUsers, self).unlink()

    def _sync_employee_records(self, users):
        for user in users:
            if user.share or not user.id:
                continue

            try:
                emp = self.env['hr.employee'].sudo().search([('user_id', '=', user.id)], limit=1)
                # If no employee exists yet, do NOTHING until admin clicks "Create Employee"
                if not emp:
                    continue

                employee_name = (user.partner_id.name or user.name or '').strip()
                if not employee_name:
                    continue

                emp_vals = {
                    'name': employee_name,
                    'work_email': user.email or user.login,
                    'company_id': user.company_id.id if user.company_id else False,
                    'department_id': user.crm_department_id.id if user.crm_department_id else False,
                    'job_id': user.crm_job_id.id if user.crm_job_id else False,
                    'expense_manager_id': user.crm_expense_manager_id.id if user.crm_expense_manager_id else False,
                    'category_ids': [(6, 0, user.crm_employee_tag_ids.ids)] if user.crm_employee_tag_ids else [(5, 0, 0)],
                }
                if user.crm_manager_id:
                    mgr = self.env['hr.employee'].sudo().search([('user_id', '=', user.crm_manager_id.id)], limit=1)
                    emp_vals['parent_id'] = mgr.id if mgr else False
                else:
                    emp_vals['parent_id'] = False

                emp.with_context(skip_sync=True).sudo().write(emp_vals)
            except Exception as e:
                pass

    @api.depends('crm_job_id', 'crm_job_id.department_id', 'crm_job_id.sub_department_ids', 'crm_department_id')
    def _compute_department_scope(self):
        for user in self:
            scope_ids = set()
            if user.crm_job_id:
                if user.crm_job_id.department_id:
                    scope_ids.add(user.crm_job_id.department_id.id)
                if user.crm_job_id.sub_department_ids:
                    scope_ids.update(user.crm_job_id.sub_department_ids.ids)
            elif user.crm_department_id:
                scope_ids.add(user.crm_department_id.id)

            if scope_ids:
                user.crm_department_ids = [(6, 0, list(scope_ids))]
            else:
                user.crm_department_ids = [(5, 0, 0)]

    @api.onchange('crm_job_id')
    def _onchange_crm_job_id_defaults(self):
        if self.crm_job_id:
            dept = self.crm_job_id.department_id
            # Auto-assign Primary Department from Job Role
            if dept:
                self.crm_department_id = dept.id

            # Determine Reporting Manager:
            # Check if this user is the head/manager of this department
            is_dept_manager = False
            if dept and dept.manager_id and dept.manager_id.user_id:
                if self._origin and self._origin.id == dept.manager_id.user_id.id:
                    is_dept_manager = True
                elif not self._origin.id and self.id and self.id == dept.manager_id.user_id.id:
                    is_dept_manager = True

            if is_dept_manager:
                # User is Department Head! Never report to themselves.
                # Auto-assign Parent Department manager (e.g. Director / CEO)
                parent_dept = dept.parent_id
                if parent_dept and parent_dept.manager_id and parent_dept.manager_id.user_id:
                    self.crm_manager_id = parent_dept.manager_id.user_id.id
                else:
                    self.crm_manager_id = False
            else:
                # Regular employee/executive: Auto-fill Department Head
                if self.crm_job_id.default_manager_id:
                    self.crm_manager_id = self.crm_job_id.default_manager_id.id

class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    company_id = fields.Many2one('res.company', string='Company', default=False)
    expense_manager_id = fields.Many2one('res.users', string='Expense / Voucher Approver', domain="[('share', '=', False)]")

    def write(self, vals):
        res = super().write(vals)
        if not self.env.context.get('skip_sync'):
            self.with_context(skip_sync=True)._sync_user_records()
        return res

    def _sync_user_records(self):
        for emp in self:
            if not emp.user_id:
                continue
            user = emp.user_id.sudo()
            user_vals = {
                'crm_department_id': emp.department_id.id if emp.department_id else False,
                'crm_job_id': emp.job_id.id if emp.job_id else False,
                'crm_expense_manager_id': emp.expense_manager_id.id if emp.expense_manager_id else False,
                'crm_employee_tag_ids': [(6, 0, emp.category_ids.ids)] if emp.category_ids else [(5, 0, 0)],
            }
            if emp.parent_id and emp.parent_id.user_id:
                user_vals['crm_manager_id'] = emp.parent_id.user_id.id
            else:
                user_vals['crm_manager_id'] = False

            user.with_context(skip_sync=True).write(user_vals)

class HrJob(models.Model):
    _inherit = 'hr.job'

    company_id = fields.Many2one('res.company', string='Company', default=False)

    # 1. Primary Department (Home Base)
    department_id = fields.Many2one(
        'hr.department',
        string='Primary Department',
        ondelete='restrict',
        help='The main department where this role belongs.'
    )

    # 2. Managed Sub-Departments (Smaller departments managed under this role)
    sub_department_ids = fields.Many2many(
        'hr.department',
        'hr_job_sub_department_rel',
        'job_id',
        'department_id',
        string='Managed Sub-Departments',
        help='Specific sub-departments that this role is allowed to manage.'
    )

    # 3. Manager Role Toggle
    is_manager_role = fields.Boolean(
        string='Is Department Head / Manager',
        default=False,
        groups='base.group_erp_manager',
        help='Check if this role represents the head or manager of the department. If checked, this role reports to the parent department manager instead of this department itself.'
    )

    # 4. Reporting Manager (Auto-fetched from Primary Department or Parent Department)
    default_manager_id = fields.Many2one(
        'res.users',
        string='Reporting Manager',
        domain="[('share', '=', False)]",
        compute='_compute_default_manager_id',
        store=True,
        readonly=False,
        help='Default manager automatically suggested for users with this job position.',
    )

    user_ids = fields.One2many(
        'res.users',
        'crm_job_id',
        string='Assigned Users / Employees',
        domain="[('share', '=', False)]"
    )

    assigned_employee_ids = fields.Many2many(
        'res.users',
        'hr_job_assigned_user_rel',
        'job_id',
        'user_id',
        string='Assigned Employees',
        compute='_compute_assigned_employee_ids',
        inverse='_set_assigned_employee_ids',
        help='Active employees assigned this role, excluding the department manager.'
    )

    assigned_employee_count = fields.Integer(
        string='Employee Count',
        compute='_compute_assigned_employee_ids'
    )

    @api.depends('user_ids', 'department_id', 'department_id.manager_id', 'department_id.manager_id.user_id')
    def _compute_assigned_employee_ids(self):
        for job in self:
            mgr_user_id = job.department_id.manager_id.user_id.id if (job.department_id and job.department_id.manager_id and job.department_id.manager_id.user_id) else False
            if mgr_user_id and not job.is_manager_role:
                # Exclude the department manager from regular employee list!
                emps = job.user_ids.filtered(lambda u: u.id != mgr_user_id)
            else:
                emps = job.user_ids
            job.assigned_employee_ids = emps
            job.assigned_employee_count = len(emps)

    def _set_assigned_employee_ids(self):
        """When employees are added or removed in assigned_employee_ids, update their crm_job_id and sync permissions!"""
        for job in self:
            current_users = job.user_ids
            new_users = job.assigned_employee_ids

            # Users added
            added_users = new_users - current_users
            for u in added_users:
                u.sudo().write({'crm_job_id': job.id})
                u._apply_job_permissions(job)

            # Users removed
            removed_users = current_users - new_users
            for u in removed_users:
                if not job.is_manager_role and job.department_id and job.department_id.manager_id and job.department_id.manager_id.user_id.id == u.id:
                    continue  # do not touch manager
                u.sudo().write({'crm_job_id': False})

    def action_revoke_employee(self):
        """Action button on the row to revoke an employee from this role."""
        user_id = self.env.context.get('revoke_user_id')
        if user_id:
            user = self.env['res.users'].browse(user_id)
            if user.exists() and user.crm_job_id.id == self.id:
                user.sudo().write({'crm_job_id': False})
        return True

    def action_cancel_to_list(self):
        """Cancel button action: directly returns to Job Positions list view instead of Dashboard."""
        action = self.env.ref('hr.action_hr_job', raise_if_not_found=False)
        if action:
            res = action.read()[0]
            res['target'] = 'current'
            return res
        return {
            'type': 'ir.actions.act_window',
            'name': 'Job Positions',
            'res_model': 'hr.job',
            'view_mode': 'list,form',
            'target': 'current',
        }

    @api.depends('department_id', 'department_id.manager_user_id', 'department_id.senior_manager_user_id', 'department_id.manager_id', 'department_id.manager_id.user_id', 'department_id.parent_id', 'department_id.parent_id.manager_id', 'is_manager_role')
    def _compute_default_manager_id(self):
        for rec in self:
            if not rec.department_id:
                rec.default_manager_id = False
                continue

            dept = rec.department_id
            if rec.is_manager_role:
                # If this is a Manager/Head role: prioritize senior_manager_user_id on department
                if dept.senior_manager_user_id:
                    rec.default_manager_id = dept.senior_manager_user_id.id
                else:
                    parent_dept = dept.parent_id
                    if parent_dept and parent_dept.manager_user_id:
                        rec.default_manager_id = parent_dept.manager_user_id.id
                    elif parent_dept and parent_dept.manager_id and parent_dept.manager_id.user_id:
                        rec.default_manager_id = parent_dept.manager_id.user_id.id
                    else:
                        rec.default_manager_id = False
            else:
                # Regular staff/executive role: report to this department's appointed manager
                if dept.manager_user_id:
                    rec.default_manager_id = dept.manager_user_id.id
                elif dept.manager_id and dept.manager_id.user_id:
                    rec.default_manager_id = dept.manager_id.user_id.id
                else:
                    rec.default_manager_id = False

    @api.onchange('department_id', 'is_manager_role')
    def _onchange_department_id_fetch_manager(self):
        """When Primary Department or is_manager_role changes, auto-fetch reporting manager."""
        if not self.department_id:
            self.default_manager_id = False
            return

        dept = self.department_id
        if self.is_manager_role:
            if dept.senior_manager_user_id:
                self.default_manager_id = dept.senior_manager_user_id.id
            else:
                parent_dept = dept.parent_id
                if parent_dept and parent_dept.manager_user_id:
                    self.default_manager_id = parent_dept.manager_user_id.id
                elif parent_dept and parent_dept.manager_id and parent_dept.manager_id.user_id:
                    self.default_manager_id = parent_dept.manager_id.user_id.id
                else:
                    self.default_manager_id = False
        else:
            if dept.manager_user_id:
                self.default_manager_id = dept.manager_user_id.id
            elif dept.manager_id and dept.manager_id.user_id:
                self.default_manager_id = dept.manager_id.user_id.id
            else:
                self.default_manager_id = False

    perm_lead_quote = fields.Selection([
        ('none', 'No'),
        ('own', 'User: Own Documents Only'),
        ('all', 'User: All Documents'),
        ('admin', 'Administrator'),
    ], string='Lead & Quotation', default='own')

    perm_service_ticket = fields.Selection([
        ('none', 'No'),
        ('own', 'User: Own Documents Only'),
        ('all', 'User: All Documents'),
        ('admin', 'Administrator'),
    ], string='Service Ticket', default='own')

    perm_amc = fields.Selection([
        ('none', 'No'),
        ('own', 'User: Own Documents Only'),
        ('all', 'User: All Documents'),
        ('admin', 'Administrator'),
    ], string='AMC Contract', default='own')

    perm_product_create = fields.Boolean(string='Create Product', default=True)
    perm_product_write = fields.Boolean(string='Update Product', default=True)
    perm_product_read = fields.Boolean(string='View Product', default=True)
    perm_product_unlink = fields.Boolean(string='Delete Product', default=False)

    perm_customer_create = fields.Boolean(string='Create Customer', default=True)
    perm_customer_write = fields.Boolean(string='Update Customer', default=True)
    perm_customer_read = fields.Boolean(string='View Customer', default=True)
    perm_customer_unlink = fields.Boolean(string='Delete Customer', default=False)

    perm_equipment_create = fields.Boolean(string='Create Equipment', default=True)
    perm_equipment_write = fields.Boolean(string='Update Equipment', default=True)
    perm_equipment_read = fields.Boolean(string='View Equipment', default=True)
    perm_equipment_unlink = fields.Boolean(string='Delete Equipment', default=False)

    perm_export = fields.Selection([
        ('none', 'No'),
        ('export', 'Yes'),
    ], string='Excel Export', default='none')

    perm_company = fields.Selection([
        ('none', 'No'),
        ('create', 'Yes'),
    ], string='Company Creation', default='none')

    user_count = fields.Integer(string='Users with this Role', compute='_compute_user_count')

    def _compute_user_count(self):
        for job in self:
            job.user_count = self.env['res.users'].search_count([('crm_job_id', '=', job.id), ('share', '=', False)])

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if 'is_manager_role' in vals or 'department_id' in vals:
                dept_id = vals.get('department_id')
                is_mgr = vals.get('is_manager_role', False)
                dept = self.env['hr.department'].browse(dept_id) if dept_id else False
                if is_mgr:
                    if dept and dept.senior_manager_user_id:
                        vals['default_manager_id'] = dept.senior_manager_user_id.id
                    else:
                        parent_dept = dept.parent_id if dept else False
                        if parent_dept and parent_dept.manager_user_id:
                            vals['default_manager_id'] = parent_dept.manager_user_id.id
                        elif parent_dept and parent_dept.manager_id and parent_dept.manager_id.user_id:
                            vals['default_manager_id'] = parent_dept.manager_id.user_id.id
                        else:
                            vals['default_manager_id'] = False
                else:
                    if dept and dept.manager_user_id:
                        vals['default_manager_id'] = dept.manager_user_id.id
                    elif dept and dept.manager_id and dept.manager_id.user_id:
                        vals['default_manager_id'] = dept.manager_id.user_id.id
                    else:
                        vals['default_manager_id'] = False
        return super().create(vals_list)

    def write(self, vals):
        if 'is_manager_role' in vals or 'department_id' in vals:
            for job in self:
                is_mgr = vals.get('is_manager_role', job.is_manager_role)
                dept_id = vals.get('department_id', job.department_id.id if job.department_id else False)
                dept = self.env['hr.department'].browse(dept_id) if dept_id else False
                if is_mgr:
                    if dept and dept.senior_manager_user_id:
                        vals['default_manager_id'] = dept.senior_manager_user_id.id
                    else:
                        parent_dept = dept.parent_id if dept else False
                        if parent_dept and parent_dept.manager_user_id:
                            vals['default_manager_id'] = parent_dept.manager_user_id.id
                        elif parent_dept and parent_dept.manager_id and parent_dept.manager_id.user_id:
                            vals['default_manager_id'] = parent_dept.manager_id.user_id.id
                        else:
                            vals['default_manager_id'] = False
                else:
                    if dept and dept.manager_user_id:
                        vals['default_manager_id'] = dept.manager_user_id.id
                    elif dept and dept.manager_id and dept.manager_id.user_id:
                        vals['default_manager_id'] = dept.manager_id.user_id.id
                    else:
                        vals['default_manager_id'] = False

        res = super().write(vals)
        perm_keys = [
            'perm_lead_quote', 'perm_service_ticket', 'perm_amc',
            'perm_product_create', 'perm_product_write', 'perm_product_read', 'perm_product_unlink',
            'perm_customer_create', 'perm_customer_write', 'perm_customer_read', 'perm_customer_unlink',
            'perm_equipment_create', 'perm_equipment_write', 'perm_equipment_read', 'perm_equipment_unlink',
            'perm_export', 'perm_company'
        ]
        if any(k in vals for k in perm_keys):
            for job in self:
                users = self.env['res.users'].search([
                    ('crm_job_id', '=', job.id),
                    ('share', '=', False),
                ])
                users._apply_job_permissions(job)
        return res

class HrDepartment(models.Model):
    _inherit = 'hr.department'
    company_id = fields.Many2one('res.company', string='Company', default=False)

    manager_user_id = fields.Many2one(
        'res.users',
        string='Department Head',
        domain="[('share', '=', False)]",
        help='The appointed manager or head of this department (e.g. Sales Manager).'
    )

    senior_manager_user_id = fields.Many2one(
        'res.users',
        string='Reporting Manager',
        domain="[('share', '=', False)]",
        help='The senior manager whom the department head reports to (e.g. Director, VP, CEO).'
    )

    member_user_ids = fields.One2many(
        'res.users',
        'crm_department_id',
        string='Department Members',
        domain="[('share', '=', False)]"
    )

    @api.onchange('manager_user_id')
    def _onchange_manager_user_id(self):
        """Sync manager_user_id to standard hr.employee manager_id if employee exists."""
        if self.manager_user_id:
            emp = self.env['hr.employee'].sudo().search([('user_id', '=', self.manager_user_id.id)], limit=1)
            if emp:
                self.manager_id = emp.id
        else:
            self.manager_id = False

    @api.onchange('manager_id')
    def _onchange_manager_id_sync_user(self):
        """Sync standard hr.department manager_id to manager_user_id."""
        if self.manager_id and self.manager_id.user_id:
            self.manager_user_id = self.manager_id.user_id.id
