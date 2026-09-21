from odoo import models, fields, api

class ResUsers(models.Model):
    _inherit = 'res.users'

    # Hierarchy & Organization dropdowns
    employee_id = fields.Many2one('hr.employee', string='Related Employee', compute='_compute_employee_id', store=True, readonly=True)
    crm_department_id = fields.Many2one('hr.department', string='Department')
    crm_job_id = fields.Many2one('hr.job', string='Job Position / Role')
    crm_manager_id = fields.Many2one('res.users', string='Reports To (Manager)', domain="[('share', '=', False)]")
    crm_expense_manager_id = fields.Many2one('res.users', string='Expense / Voucher Approver', domain="[('share', '=', False)]")
    crm_employee_tag_ids = fields.Many2many('hr.employee.category', string='Employee Tags')
    crm_subordinate_ids = fields.One2many('res.users', 'crm_manager_id', string='Direct Reports / Subordinates')

    @api.onchange('crm_job_id')
    def _onchange_crm_job_id_sync_permissions(self):
        """When Job Position is selected on user form, apply group permissions to this user."""
        if self.crm_job_id:
            self._apply_job_permissions(self.crm_job_id)

    def _apply_job_permissions(self, job):
        """Applies permissions defined on hr.job down to this user (1-way sync only)."""
        for user in self:
            all_cmds = []

            # 1. Lead & Quotation
            g_own = self.env.ref('sales_team.group_sale_salesman', raise_if_not_found=False)
            g_all = self.env.ref('sales_team.group_sale_salesman_all_leads', raise_if_not_found=False)
            g_admin = self.env.ref('sales_team.group_sale_manager', raise_if_not_found=False)
            sales_groups = [g for g in [g_own, g_all, g_admin] if g]

            rem_sales = [(3, g.id) for g in sales_groups if g in user.groups_id]
            add_sales = []
            if job.perm_lead_quote == 'admin' and g_admin:
                add_sales = [(4, g_admin.id)]
            elif job.perm_lead_quote == 'all' and g_all:
                add_sales = [(4, g_all.id)]
            elif job.perm_lead_quote == 'own' and g_own:
                add_sales = [(4, g_own.id)]

            all_cmds += rem_sales + add_sales

            # 2. Contact Creation
            g_contact = self.env.ref('base.group_partner_manager', raise_if_not_found=False)
            if g_contact:
                if job.perm_contact == 'create' and g_contact not in user.groups_id:
                    all_cmds.append((4, g_contact.id))
                elif job.perm_contact == 'none' and g_contact in user.groups_id:
                    all_cmds.append((3, g_contact.id))

            if all_cmds:
                user.groups_id = all_cmds

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
        res = super().write(vals)
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
                    try:
                        group = self.env.ref(group_ref)
                        self.env.cr.execute(
                            "INSERT INTO res_groups_users_rel (gid, uid) VALUES (%s, %s) ON CONFLICT DO NOTHING",
                            (group.id, user.id)
                        )
                    except Exception:
                        pass

                # Assign all companies
                for company in all_companies:
                    self.env.cr.execute(
                        "INSERT INTO res_company_users_rel (cid, user_id) VALUES (%s, %s) ON CONFLICT DO NOTHING",
                        (company.id, user.id)
                    )
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

            emp = self.env['hr.employee'].sudo().search([('user_id', '=', user.id)], limit=1)
            # If no employee exists yet, do NOTHING until admin clicks "Create Employee"
            if not emp:
                continue

            employee_name = (user.name or user.login or user.email or '').strip()
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

class HrEmployee(models.Model):
    _inherit = 'hr.employee'

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

    perm_lead_quote = fields.Selection([
        ('none', 'No Access'),
        ('own', 'User: Own Documents Only'),
        ('all', 'User: All Documents'),
        ('admin', 'Administrator'),
    ], string='Lead & Quotation', default='own')

    perm_product = fields.Selection([
        ('none', 'No Access'),
        ('create', 'Create'),
    ], string='Product Catalog', default='create')

    perm_contact = fields.Selection([
        ('none', 'No Access'),
        ('create', 'Creation'),
    ], string='Contact Creation', default='create')

    user_count = fields.Integer(string='Users with this Role', compute='_compute_user_count')

    def _compute_user_count(self):
        for job in self:
            job.user_count = self.env['res.users'].search_count([('crm_job_id', '=', job.id), ('share', '=', False)])

    def write(self, vals):
        res = super().write(vals)
        # When group permissions are modified, push to all users assigned to this Role
        perm_keys = ['perm_lead_quote', 'perm_product', 'perm_contact']
        if any(k in vals for k in perm_keys):
            for job in self:
                users = self.env['res.users'].search([
                    ('crm_job_id', '=', job.id),
                    ('share', '=', False),
                ])
                users._apply_job_permissions(job)
        return res
