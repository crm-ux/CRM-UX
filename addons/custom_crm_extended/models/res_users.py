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
            if not user.id or user.has_group('base.group_system'):
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

            # Apply security group additions and removals on group records directly
            for op, gid in group_ops:
                g = self.env['res.groups'].sudo().browse(gid)
                if not g.exists():
                    continue
                if op == 4 and user not in g.users:
                    g.write({'users': [(4, user.id)]})
                elif op == 3 and user in g.users:
                    g.write({'users': [(3, user.id)]})


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
        # DO NOT auto-create employee here
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
                # Skip portal and public users
                if portal_group in user.groups_id or public_group in user.groups_id:
                    continue
                # Only internal users
                if internal_group not in user.groups_id:
                    continue

                for group_ref in groups_to_add:
                    g = self.env.ref(group_ref, raise_if_not_found=False)
                    if g and user not in g.users:
                        g.sudo().write({'users': [(4, user.id)]})

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
            # Auto-assign Primary Department from Job Role
            if self.crm_job_id.department_id:
                self.crm_department_id = self.crm_job_id.department_id.id
            # Auto-fill Reporting Manager from Job Role
            if self.crm_job_id.default_manager_id and not self.crm_manager_id:
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

    # 3. Reporting Manager (Auto-fetched from Primary Department)
    default_manager_id = fields.Many2one(
        'res.users',
        string='Reporting Manager',
        domain="[('share', '=', False)]",
        help='Default manager automatically suggested for users with this job position.'
    )

    user_ids = fields.One2many(
        'res.users',
        'crm_job_id',
        string='Assigned Users / Employees',
        domain="[('share', '=', False)]"
    )

    @api.onchange('department_id')
    def _onchange_department_id_fetch_manager(self):
        """When Primary Department is selected, auto-fetch that department's manager!"""
        if self.department_id and self.department_id.manager_id and self.department_id.manager_id.user_id:
            self.default_manager_id = self.department_id.manager_id.user_id.id

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

    def write(self, vals):
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
        string='Department Head / Manager',
        domain="[('share', '=', False)]",
        help='The user who manages this department.'
    )

    member_user_ids = fields.One2many(
        'res.users',
        'crm_department_id',
        string='Department Members',
        domain="[('share', '=', False)]"
    )
