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
        if self.crm_job_id and self._origin.id:
            # Safely apply to the real database record
            real_user = self.env['res.users'].browse(self._origin.id)

    def _apply_job_permissions(self, job):
        """Applies permissions defined on hr.job down to this user (1-way sync only)."""
        for user in self:
            if not user.id or user.has_group('base.group_system'):
                continue

            # 1. Lead & Quotation (Sales groups)
            g_own = self.env.ref('sales_team.group_sale_salesman', raise_if_not_found=False)
            g_all = self.env.ref('sales_team.group_sale_salesman_all_leads', raise_if_not_found=False)
            g_admin = self.env.ref('sales_team.group_sale_manager', raise_if_not_found=False)
            sales_gids = [g.id for g in [g_own, g_all, g_admin] if g]

            if sales_gids:
                self.env.cr.execute("DELETE FROM res_groups_users_rel WHERE uid = %s AND gid = ANY(%s)", (user.id, sales_gids))

            target_sale_gid = None
            if job.perm_lead_quote == 'admin' and g_admin:
                target_sale_gid = g_admin.id
            elif job.perm_lead_quote == 'all' and g_all:
                target_sale_gid = g_all.id
            elif job.perm_lead_quote == 'own' and g_own:
                target_sale_gid = g_own.id

            if target_sale_gid:
                self.env.cr.execute("INSERT INTO res_groups_users_rel (gid, uid) VALUES (%s, %s) ON CONFLICT DO NOTHING", (target_sale_gid, user.id))

            # 2. Contact Creation
            g_contact = self.env.ref('base.group_partner_manager', raise_if_not_found=False)
            if g_contact:
                if job.perm_contact == 'create':
                    self.env.cr.execute("INSERT INTO res_groups_users_rel (gid, uid) VALUES (%s, %s) ON CONFLICT DO NOTHING", (g_contact.id, user.id))
                elif job.perm_contact == 'none':
                    self.env.cr.execute("DELETE FROM res_groups_users_rel WHERE uid = %s AND gid = %s", (user.id, g_contact.id))

            # 3. Product Catalog
            # In Odoo, product rights are tied to sales / inventory
            # When perm_product == 'create', ensure target_sale_gid or sale manager exists
            if job.perm_product == 'create' and g_admin:
                self.env.cr.execute("INSERT INTO res_groups_users_rel (gid, uid) VALUES (%s, %s) ON CONFLICT DO NOTHING", (g_admin.id, user.id))

        # Invalidate cache so user form UI displays the updated dropdown values immediately
        self.env.registry.clear_cache()



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
        perm_keys = ['perm_lead_quote', 'perm_product', 'perm_contact']
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
    # No company selected by default; user manually selects
    company_id = fields.Many2one('res.company', string='Company', default=False)
