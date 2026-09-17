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
            }
            if user.crm_department_id:
                emp_vals['department_id'] = user.crm_department_id.id
            if user.crm_job_id:
                emp_vals['job_id'] = user.crm_job_id.id
            if user.crm_manager_id:
                mgr = self.env['hr.employee'].sudo().search([('user_id', '=', user.crm_manager_id.id)], limit=1)
                if mgr:
                    emp_vals['parent_id'] = mgr.id
            if user.crm_expense_manager_id:
                emp_vals['expense_manager_id'] = user.crm_expense_manager_id.id
            if user.crm_employee_tag_ids:
                emp_vals['category_ids'] = [(6, 0, user.crm_employee_tag_ids.ids)]
            
            emp.sudo().write(emp_vals)

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
