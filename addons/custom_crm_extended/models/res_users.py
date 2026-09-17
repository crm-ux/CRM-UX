from odoo import models, api

class ResUsers(models.Model):
    _inherit = 'res.users'

    # Hierarchy & Organization dropdowns
    employee_id = fields.Many2one('hr.employee', string='Related Employee', compute='_compute_employee_id', store=True, readonly=False)
    crm_department_id = fields.Many2one('hr.department', string='Department')
    crm_job_id = fields.Many2one('hr.job', string='Job Position / Role')
    crm_manager_id = fields.Many2one('res.users', string='Reports To (Manager)', domain="[('share', '=', False)]")
    crm_employee_tag_ids = fields.Many2many('hr.employee.category', string='Employee Tags')

    @api.depends('name')
    def _compute_employee_id(self):
        for user in self:
            if not user.employee_id and user.id:
                emp = self.env['hr.employee'].sudo().search([('user_id', '=', user.id)], limit=1)
                user.employee_id = emp.id if emp else False


    @api.model_create_multi
    def create(self, vals_list):
        users = super().create(vals_list)
        self._assign_default_groups(users)
        self._sync_employee_records(users)
        return users

    def write(self, vals):
        res = super().write(vals)
        self._sync_employee_records(self)
        return res
    
    def _sync_employee_records(self, users):
        for user in users:
            if user.share:
                continue
            emp = self.env['hr.employee'].sudo().search([('user_id', '=', user.id)], limit=1)
            emp_vals = {
                'name': user.name,
                'work_email': user.email or user.login,
                'user_id': user.id,
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
            if user.crm_employee_tag_ids:
                emp_vals['category_ids'] = [(6, 0, user.crm_employee_tag_ids.ids)]
            if not emp:
                new_emp = self.env['hr.employee'].sudo().create(emp_vals)
                user.employee_id = new_emp.id
            else:
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
