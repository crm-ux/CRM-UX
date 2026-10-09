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
    crm_department_ids = fields.Many2many('hr.department', 'res_users_hr_department_rel', 'user_id', 'department_id', string='Managed Sub-Departments')

    @api.model
    def get_my_profile_data(self, user_id=None):
        uid = int(user_id) if user_id else self.env.user.id
        u = self.browse(uid).sudo()
        if not u.exists():
            u = self.env.user.sudo()
        partner = u.partner_id.sudo() if u.partner_id else False

        img = False
        if u.image_128:
            img = u.image_128.decode('ascii') if isinstance(u.image_128, bytes) else str(u.image_128)

        # Look up employee linked to this user
        emp = self.env['hr.employee'].sudo().search([('user_id', '=', u.id)], limit=1)
        if not emp and getattr(u, 'employee_id', False):
            emp = u.employee_id.sudo()

        phone_val = getattr(partner, 'phone', '') or getattr(u, 'phone', '') or (emp and getattr(emp, 'work_phone', '')) or ''
        mobile_val = (emp and getattr(emp, 'mobile_phone', '')) or getattr(partner, 'mobile', '') or getattr(u, 'mobile', '') or ''

        return {
            'id': u.id,
            'name': u.name or getattr(partner, 'name', '') or '',
            'login': u.login or '',
            'email': getattr(partner, 'email', '') or getattr(u, 'email', '') or '',
            'phone': phone_val or '',
            'mobile': mobile_val or '',
            'has_image': bool(u.image_128),
            'job_title': (u.crm_job_id and u.crm_job_id.name) or (emp and emp.job_title) or '',
            'department': (u.crm_department_id and u.crm_department_id.name) or (emp and emp.department_id and emp.department_id.name) or '',
            'manager': (u.crm_manager_id and u.crm_manager_id.name) or (emp and emp.parent_id and emp.parent_id.name) or '',
            'expense_manager': (u.crm_expense_manager_id and u.crm_expense_manager_id.name) or '',
        }

    @api.model
    def save_my_profile_data(self, vals, user_id=None):
        uid = int(user_id) if user_id else self.env.user.id
        u = self.browse(uid).sudo()
        if not u.exists():
            u = self.env.user.sudo()

        new_login = vals.get('login', '').strip() if vals.get('login') else ''
        if new_login and new_login != u.login:
            existing = self.sudo().search([('login', '=ilike', new_login), ('id', '!=', u.id)], limit=1)
            if existing:
                return {'success': False, 'error': f"Login ID '{new_login}' is already in use by another user."}

        u_vals = {}
        p_vals = {}
        e_vals = {}
        emp = self.env['hr.employee'].sudo().search([('user_id', '=', u.id)], limit=1)
        if not emp and getattr(u, 'employee_id', False):
            emp = u.employee_id.sudo()

        for f in ['name', 'login', 'email', 'phone', 'mobile']:
            if f in vals and vals[f] is not None:
                val = vals[f].strip() if isinstance(vals[f], str) else vals[f]
                if hasattr(u, f):
                    u_vals[f] = val
                if u.partner_id and hasattr(u.partner_id, f) and f != 'login':
                    p_vals[f] = val
                if emp and f == 'mobile' and hasattr(emp, 'mobile_phone'):
                    e_vals['mobile_phone'] = val
                if emp and f == 'phone' and hasattr(emp, 'work_phone'):
                    e_vals['work_phone'] = val

        if u_vals:
            u.write(u_vals)
        if p_vals and u.partner_id:
            u.partner_id.sudo().write(p_vals)
        if e_vals and emp:
            emp.sudo().write(e_vals)

        return {'success': True}

    @api.model
    def check_can_assign_task(self, user_id=None):
        """Check if user has subordinates working under them or is an admin."""
        uid = int(user_id) if user_id else self.env.user.id
        u = self.browse(uid).sudo()
        if not u.exists():
            return False

        # Admin always has assign task rights
        if u.has_group('base.group_system') or u.id == 2:
            return True

        # Check subordinates via res.users (crm_manager_id)
        has_sub_users = bool(self.sudo().search_count([('crm_manager_id', '=', u.id), ('id', '!=', u.id)]))
        if has_sub_users:
            return True

        # Check subordinates via hr.employee (parent_id)
        emp = self.env['hr.employee'].sudo().search([('user_id', '=', u.id)], limit=1)
        if not emp and getattr(u, 'employee_id', False):
            emp = u.employee_id.sudo()
        if emp:
            has_sub_emps = bool(self.env['hr.employee'].sudo().search_count([('parent_id', '=', emp.id), ('id', '!=', emp.id)]))
            if has_sub_emps:
                return True

        return False

    @api.model
    def get_assignable_team_members(self, user_id=None, search_term=""):
        """Returns list of employees that this manager/admin can assign tasks to,
        filtered by subordinates, department, and managed sub-departments."""
        uid = int(user_id) if user_id else self.env.user.id
        u = self.browse(uid).sudo()
        if not u.exists():
            return []

        is_admin = u.has_group('base.group_system') or u.id == 2
        allowed_uids = set()

        if is_admin:
            # Admins can assign to all active internal users
            all_users = self.sudo().search([('active', '=', True), ('share', '=', False)])
            allowed_uids = set(all_users.ids)
        else:
            # 1. Direct and indirect subordinates from res.users
            allowed_uids.update(u.crm_subordinate_ids.ids)
            allowed_uids.update(u._get_all_subordinates().ids)

            # 2. Direct and indirect subordinates from hr.employee
            emp = self.env['hr.employee'].sudo().search([('user_id', '=', u.id)], limit=1)
            if not emp and getattr(u, 'employee_id', False):
                emp = u.employee_id.sudo()
            if emp:
                sub_emps = self.env['hr.employee'].sudo().search([('parent_id', 'child_of', emp.id)])
                for se in sub_emps:
                    if se.user_id:
                        allowed_uids.add(se.user_id.id)

            # 3. Department & Managed Sub-departments
            depts = u.crm_department_ids | u.crm_department_id
            if u.crm_job_id:
                if u.crm_job_id.department_id:
                    depts |= u.crm_job_id.department_id
                if u.crm_job_id.sub_department_ids:
                    depts |= u.crm_job_id.sub_department_ids
            if emp and emp.department_id:
                depts |= emp.department_id

            if depts:
                child_depts = self.env['hr.department'].sudo().search([('id', 'child_of', depts.ids)])
                dept_emps = self.env['hr.employee'].sudo().search([('department_id', 'in', child_depts.ids), ('user_id', '!=', False)])
                allowed_uids.update(dept_emps.mapped('user_id').ids)
                dept_users = self.sudo().search([('crm_department_id', 'in', child_depts.ids)])
                allowed_uids.update(dept_users.ids)

        if not allowed_uids:
            return []

        domain = [('id', 'in', list(allowed_uids)), ('active', '=', True), ('share', '=', False)]
        if search_term and search_term.strip():
            st = search_term.strip()
            domain.append('|')
            domain.append(('name', 'ilike', st))
            domain.append(('login', 'ilike', st))

        users = self.sudo().search(domain, order='name asc', limit=50)
        res = []
        for usr in users:
            e = self.env['hr.employee'].sudo().search([('user_id', '=', usr.id)], limit=1) or usr.employee_id
            job = (usr.crm_job_id and usr.crm_job_id.name) or (e and e.job_title) or ''
            dept = (usr.crm_department_id and usr.crm_department_id.name) or (e and e.department_id and e.department_id.name) or ''
            res.append({
                'id': usr.id,
                'name': usr.name,
                'email': usr.email or '',
                'login': usr.login or '',
                'job_title': job,
                'department': dept,
                'partner_id': usr.partner_id.id if usr.partner_id else usr.id,
            })
        return res

    def _get_all_subordinates(self):
        """Recursively retrieves all subordinate user IDs down the entire management chain."""
        subordinates = self.env['res.users']
        current_users = self.sudo()
        visited = set(self.ids)
        while current_users:
            next_users = self.env['res.users'].sudo().search([('crm_manager_id', 'in', current_users.ids), ('id', 'not in', list(visited))])
            if not next_users:
                break
            subordinates |= next_users
            visited.update(next_users.ids)
            current_users = next_users
        return subordinates

    def _get_accessible_user_ids(self, perm_field='perm_lead_quote'):
        """Return all user IDs that this user is permitted to see according to their hierarchy/department."""
        self.ensure_one()
        u = self.sudo()
        # 2. Check permission level
        perm = u.perm_lead_quote or (getattr(u.crm_job_id, perm_field, None) if u.crm_job_id else 'own')
        if not perm and perm_field != 'perm_lead_quote':
            perm = getattr(u, perm_field, None) or (getattr(u.crm_job_id, perm_field, None) if u.crm_job_id else 'own')
        if perm == 'none':
            return []

        uids = set([u.id])
        if perm in ('all', 'admin') or u.perm_lead_quote in ('all', 'admin'):
            all_users = self.env['res.users'].sudo().search([('share', '=', False)])
            return all_users.ids

        if perm in ('subordinates', 'department'):
            # 1. Direct and indirect subordinates
            uids.update(u.crm_subordinate_ids.ids)
            uids.update(u._get_all_subordinates().ids)

        if perm == 'department':
            depts = u.crm_department_ids | u.crm_department_id
            if u.crm_job_id:
                if u.crm_job_id.department_id:
                    depts |= u.crm_job_id.department_id
                if u.crm_job_id.sub_department_ids:
                    depts |= u.crm_job_id.sub_department_ids
            if u.employee_id and u.employee_id.department_id:
                depts |= u.employee_id.department_id

            all_dept_ids = self.env['hr.department'].sudo().search([('id', 'child_of', depts.ids)]).ids if depts else []
            if all_dept_ids:
                # 1. Direct from hr.employee (where Odoo stores real employee departments)
                dept_emps = self.env['hr.employee'].sudo().search([
                    ('department_id', 'in', all_dept_ids),
                    ('user_id', '!=', False)
                ])
                uids.update(dept_emps.mapped('user_id').ids)

                # 2. From res.users fields
                dept_users = self.env['res.users'].sudo().search([
                    '|', '|',
                    ('crm_department_id', 'in', all_dept_ids),
                    ('crm_job_id.department_id', 'in', all_dept_ids),
                    ('crm_job_id.sub_department_ids', 'in', all_dept_ids)
                ])
                uids.update(dept_users.ids)

        return list(uids)

    def _get_hierarchy_domain(self, perm_field, user_field='user_id'):
        """Return the exact record-rule domain based on user hierarchy permission."""
        self.ensure_one()
        perm = getattr(self, perm_field, None) or (getattr(self.crm_job_id, perm_field, None) if self.crm_job_id else 'own')
        if self._is_admin() or self.has_group('base.group_system') or perm in ('all', 'admin') or getattr(self, perm_field, None) in ('all', 'admin'):
            return [(1, '=', 1)]
        if perm in ('none', False):
            return [(0, '=', 1)]
        uids = self._get_accessible_user_ids(perm_field)
        if not uids:
            return [(0, '=', 1)]
        if perm_field == 'perm_lead_quote':
            return [
                '|',
                (user_field or 'user_id', 'in', uids),
                '&', (user_field or 'user_id', '=', False), ('create_uid', 'in', uids)
            ]
        if user_field:
            return [
                '|',
                (user_field, 'in', uids),
                '&', (user_field, '=', False), ('create_uid', 'in', uids)
            ]
        return [('create_uid', 'in', uids)]

    @api.model
    def get_accessible_employees(self, perm_field='perm_lead_quote'):
        """Returns list of {id, name} of accessible users for the current user if more than 1 user is accessible."""
        user = self.env.user
        if user._is_admin() or user.has_group('base.group_system'):
            all_users = self.sudo().search([('share', '=', False), ('active', '=', True)], order='name asc')
            return [{'id': u.id, 'name': u.name} for u in all_users]

        uids = user._get_accessible_user_ids(perm_field)
        if len(uids) <= 1:
            return []
        users = self.sudo().browse(uids).filtered(lambda u: u.active and not u.share)
        return [{'id': u.id, 'name': u.name} for u in users.sorted('name')]

    def action_view_user_hierarchy(self):
        self.ensure_one()
        wizard = self.env['crm.user.hierarchy.wizard'].create({
            'user_id': self.id,
        })
        return {
            'name': f"Organization Chart - {self.name or self.login}",
            'type': 'ir.actions.act_window',
            'res_model': 'crm.user.hierarchy.wizard',
            'res_id': wizard.id,
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'dialog_size': 'medium',
            },
        }

    def action_revoke_role(self):
        """Unassigns this role from the user."""
        for user in self:
            user.sudo().write({'crm_job_id': False})
        return True

    @api.model
    def check_perm_log(self, target_user_id=None):
        """Returns True if user is admin or has perm_log == 'log'."""
        user = self.browse(target_user_id) if target_user_id else self.env.user
        if not user or not user.exists():
            user = self.env.user
        if user._is_admin() or user.has_group('base.group_system'):
            return True
        if user.perm_log in ('log', 'none'):
            return user.perm_log == 'log'
        if user.crm_job_id and user.crm_job_id.perm_log:
            return user.crm_job_id.perm_log == 'log'
        return False

    perm_export = fields.Selection([
        ('none', 'No'),
        ('export', 'Yes'),
    ], string='Excel Export', default='none')

    perm_log = fields.Selection([
        ('none', 'No'),
        ('log', 'Yes'),
    ], string='Log View', default='none')

    perm_company = fields.Selection([
        ('none', 'No'),
        ('create', 'Yes'),
    ], string='Company Creation', default='none')

    perm_lead_quote = fields.Selection([
        ('none', 'No'),
        ('own', 'User: Own Documents Only'),
        ('subordinates', 'Manager: Assigned Team Only'),
        ('department', 'Department: All Department & Sub-Dept Records'),
        ('all', 'All: All Company Records'),
    ], string='Lead & Quotation', default='own')

    perm_service_ticket = fields.Selection([
        ('none', 'No'),
        ('own', 'User: Own Documents Only'),
        ('subordinates', 'Manager: Assigned Team Only'),
        ('department', 'Department: All Department & Sub-Dept Records'),
        ('all', 'All: All Company Records'),
    ], string='Service Ticket', default='own')

    perm_amc = fields.Selection([
        ('none', 'No'),
        ('own', 'User: Own Documents Only'),
        ('subordinates', 'Manager: Assigned Team Only'),
        ('department', 'Department: All Department & Sub-Dept Records'),
        ('all', 'All: All Company Records'),
    ], string='AMC Contract', default='own')

    perm_equipment = fields.Selection([
        ('none', 'No'),
        ('own', 'User: Own Documents Only'),
        ('subordinates', 'Manager: Assigned Team Only'),
        ('department', 'Department: All Department & Sub-Dept Records'),
        ('all', 'All: All Company Records'),
    ], string='Equipment Master', default='own')

    perm_product_create = fields.Boolean(string='Create Product', default=False)
    perm_product_write = fields.Boolean(string='Update Product', default=False)
    perm_product_read = fields.Boolean(string='View Product', default=False)
    perm_product_unlink = fields.Boolean(string='Delete Product', default=False)

    perm_customer_create = fields.Boolean(string='Create Customer', default=False)
    perm_customer_write = fields.Boolean(string='Update Customer', default=False)
    perm_customer_read = fields.Boolean(string='View Customer', default=False)
    perm_customer_unlink = fields.Boolean(string='Delete Customer', default=False)

    perm_equipment_create = fields.Boolean(string='Create Equipment', default=False)
    perm_equipment_write = fields.Boolean(string='Update Equipment', default=False)
    perm_equipment_read = fields.Boolean(string='View Equipment', default=False)
    perm_equipment_unlink = fields.Boolean(string='Delete Equipment', default=False)

    perm_ticket_create = fields.Boolean(string='Create Ticket', default=False)
    perm_ticket_write = fields.Boolean(string='Update Ticket', default=False)
    perm_ticket_read = fields.Boolean(string='View Ticket', default=False)
    perm_ticket_unlink = fields.Boolean(string='Delete Ticket', default=False)

    perm_amc_create = fields.Boolean(string='Create AMC', default=False)
    perm_amc_write = fields.Boolean(string='Update AMC', default=False)
    perm_amc_read = fields.Boolean(string='View AMC', default=False)
    perm_amc_unlink = fields.Boolean(string='Delete AMC', default=False)

    perm_exhibition_create = fields.Boolean(string='Create Exhibition Contact', default=False)
    perm_exhibition_write = fields.Boolean(string='Update Exhibition Contact', default=False)
    perm_exhibition_read = fields.Boolean(string='View Exhibition Contact', default=False)
    perm_exhibition_unlink = fields.Boolean(string='Delete Exhibition Contact', default=False)

    is_left_employee = fields.Boolean(
        string='Employee Left',
        default=False,
        tracking=True,
        copy=False,
        help='Indicates whether this employee has left the company.'
    )

    def action_mark_employee_left(self):
        """Mark employee as left, disable login, and auto-unassign from active managerial roles."""
        for user in self:
            if user._is_admin() or user.id == 2:
                continue
            user.write({
                'is_left_employee': True,
                'active': True,
            })
            # 1. Auto-unassign as Department Head
            depts_as_head = self.env['hr.department'].sudo().search([('manager_user_id', '=', user.id)])
            if depts_as_head:
                depts_as_head.write({'manager_user_id': False})

            # 2. Auto-unassign as Senior Manager on Department
            depts_as_senior = self.env['hr.department'].sudo().search([('senior_manager_user_id', '=', user.id)])
            if depts_as_senior:
                depts_as_senior.write({'senior_manager_user_id': False})

            # 3. Auto-unassign as standard hr.department manager
            if user.employee_id:
                depts_as_emp_mgr = self.env['hr.department'].sudo().search([('manager_id', '=', user.employee_id.id)])
                if depts_as_emp_mgr:
                    depts_as_emp_mgr.write({'manager_id': False})

            # 4. Trigger recomputation of default_manager_id on all roles linked to their department
            if user.crm_department_id:
                jobs = self.env['hr.job'].sudo().search([('department_id', '=', user.crm_department_id.id)])
                if jobs:
                    jobs._compute_default_manager_id()

            # 5. Clear as direct manager on any subordinates
            subordinates = self.env['res.users'].sudo().search([('crm_manager_id', '=', user.id)])
            if subordinates:
                subordinates.write({'crm_manager_id': False})

    def action_mark_employee_active(self):
        """Re-activate left employee and remove the Left Employee ribbon."""
        for user in self:
            user.write({
                'is_left_employee': False,
                'active': True,
            })

    def _check_credentials(self, password, env):
        """Prevent login if employee has been marked as left."""
        if self.is_left_employee:
            from odoo.exceptions import AccessDenied
            raise AccessDenied("This employee account has been deactivated (Marked as Left).")
        return super()._check_credentials(password, env)


    @api.onchange('crm_job_id')
    def _onchange_crm_job_id_sync_permissions(self):
        """When Job Position is selected on user form, apply permissions to this user."""
        if self.crm_job_id and self._origin.id:
            real_user = self.env['res.users'].browse(self._origin.id)
            real_user._apply_job_permissions(self.crm_job_id)

    def _apply_job_permissions(self, job):
        """Applies permissions defined on hr.job down to this user (1-way sync)."""
        sales_grp = self.env.ref('sales_team.group_sale_salesman', raise_if_not_found=False)
        for user in self:
            if not user.id or user._is_admin() or user.has_group('base.group_system'):
                continue

            user_vals = {
                'perm_lead_quote': job.perm_lead_quote,
                'perm_export': job.perm_export,
                'perm_log': job.perm_log,
                'perm_company': job.perm_company,
                'perm_service_ticket': job.perm_service_ticket,
                'perm_amc': job.perm_amc,
                'perm_equipment': job.perm_equipment,
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
                'perm_ticket_create': job.perm_ticket_create,
                'perm_ticket_write': job.perm_ticket_write,
                'perm_ticket_read': job.perm_ticket_read,
                'perm_ticket_unlink': job.perm_ticket_unlink,
                'perm_amc_create': job.perm_amc_create,
                'perm_amc_write': job.perm_amc_write,
                'perm_amc_read': job.perm_amc_read,
                'perm_amc_unlink': job.perm_amc_unlink,
                'perm_exhibition_create': job.perm_exhibition_create,
                'perm_exhibition_write': job.perm_exhibition_write,
                'perm_exhibition_read': job.perm_exhibition_read,
                'perm_exhibition_unlink': job.perm_exhibition_unlink,
            }
            user.sudo().with_context(skip_sync=True).write(user_vals)
            if sales_grp and job.perm_lead_quote in ('own', 'subordinates', 'department', 'all', 'admin'):
                sales_grp.sudo().write({'user_ids': [(4, user.id)]})
            export_grp = self.env.ref('base.group_allow_export', raise_if_not_found=False)
            if export_grp:
                if job.perm_export == 'export':
                    export_grp.sudo().write({'user_ids': [(4, user.id)]})
                else:
                    export_grp.sudo().write({'user_ids': [(3, user.id)]})

    @api.depends('crm_department_id', 'crm_job_id', 'crm_job_id.sub_department_ids')
    def _compute_department_scope(self):
        for user in self:
            depts = self.env['hr.department']
            if user.crm_department_id:
                depts |= user.crm_department_id
            if user.crm_job_id:
                if user.crm_job_id.department_id:
                    depts |= user.crm_job_id.department_id
                if user.crm_job_id.sub_department_ids:
                    depts |= user.crm_job_id.sub_department_ids
            user.crm_department_ids = depts

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
        for vals in vals_list:
            # 1. Use exact name as login username (never long email)
            if vals.get('name') and vals.get('login') == vals.get('email'):
                exact_name = vals['name'].strip()
                # If name already taken, keep original
                taken = self.sudo().search_count([('login', '=', exact_name)])
                if not taken:
                    vals['login'] = exact_name

        users = super().create(vals_list)
        self._assign_default_groups(users)
        for user, vals in zip(users, vals_list):
            if vals.get('crm_job_id'):
                job = self.env['hr.job'].browse(vals['crm_job_id'])
                user._apply_job_permissions(job)
            elif vals.get('perm_lead_quote'):
                user.write({'perm_lead_quote': vals['perm_lead_quote']})
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

        # Auto-grant base Sales group if user has any Lead & Quote permission
        if 'perm_lead_quote' in vals and vals.get('perm_lead_quote') in ('own', 'subordinates', 'department', 'all', 'admin'):
            sales_grp = self.env.ref('sales_team.group_sale_salesman', raise_if_not_found=False)
            if sales_grp and self.ids:
                sales_grp.sudo().write({'user_ids': [(4, uid) for uid in self.ids]})

        if 'crm_job_id' in vals and vals['crm_job_id']:
            job = self.env['hr.job'].browse(vals['crm_job_id'])
            self._apply_job_permissions(job)

        if 'perm_export' in vals:
            export_grp = self.env.ref('base.group_allow_export', raise_if_not_found=False)
            if export_grp and self.ids:
                if vals.get('perm_export') == 'export':
                    export_grp.sudo().write({'user_ids': [(4, uid) for uid in self.ids]})
                else:
                    export_grp.sudo().write({'user_ids': [(3, uid) for uid in self.ids]})

        if not self.env.context.get('skip_sync'):
            self.with_context(skip_sync=True)._sync_employee_records(self)
        return res


    def _assign_default_groups(self, users):
        try:
            all_companies = self.env['res.company'].sudo().search([])
            sales_grp = self.env.ref('sales_team.group_sale_salesman', raise_if_not_found=False)
            for user in users:
                if user.share or user._is_admin() or user.has_group('base.group_system'):
                    continue
                # Assign all companies if not already assigned
                c_ops = [(4, c.id) for c in all_companies if c not in user.company_ids]
                vals_to_sync = {}
                if c_ops:
                    vals_to_sync['company_ids'] = c_ops
                if vals_to_sync:
                    user.sudo().with_context(skip_sync=True).write(vals_to_sync)

                # Ensure base sales group is always active so quotation line access is never blocked
                if sales_grp and user not in sales_grp.users:
                    sales_grp.sudo().write({'user_ids': [(4, user.id)]})
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

    @api.onchange('crm_job_id')
    def _onchange_crm_job_id_defaults(self):
        if self.crm_job_id:
            dept = self.crm_job_id.department_id
            # Auto-assign Primary Department from Job Role
            if dept:
                self.crm_department_id = dept.id

            # Pre-fill Managed Sub-Departments from Job Role if defined
            if self.crm_job_id.sub_department_ids:
                self.crm_department_ids = [(6, 0, self.crm_job_id.sub_department_ids.ids)]

            # Directly use the Job Role's configured Reporting Manager (e.g. Administrator for Managers)
            if self.crm_job_id.default_manager_id:
                self.crm_manager_id = self.crm_job_id.default_manager_id.id
            else:
                self.crm_manager_id = False

    @api.model
    def action_get_my_profile_data(self):
        """Fetch sanitized profile data for the current user to display in My Profile modal."""
        user = self.env.user
        partner = user.partner_id
        
        # Available timezones and languages
        timezones = [(tz, tz) for tz in self.env['res.users']._fields['tz'].selection(self)] if hasattr(self.env['res.users']._fields.get('tz'), 'selection') else []
        langs = self.env['res.lang'].sudo().search_read([('active', '=', True)], ['code', 'name'])

        return {
            'id': user.id,
            'name': user.name or '',
            'login': user.login or '',
            'email': user.email or partner.email or '',
            'phone': partner.phone or '',
            'mobile': partner.mobile or '',
            'image_128': user.image_128.decode('utf-8') if user.image_128 else False,
            'tz': user.tz or 'Asia/Calcutta',
            'lang': user.lang or 'en_US',
            'notification_type': user.notification_type or 'email',
            'job_title': user.crm_job_id.name if user.crm_job_id else (user.employee_id.job_title if user.employee_id else ''),
            'department': user.crm_department_id.name if user.crm_department_id else (user.employee_id.department_id.name if user.employee_id else ''),
            'manager': user.crm_manager_id.name if user.crm_manager_id else (user.employee_id.parent_id.name if user.employee_id and user.employee_id.parent_id else ''),
            'expense_manager': user.crm_expense_manager_id.name if user.crm_expense_manager_id else '',
            'timezones': timezones,
            'langs': [{'code': l['code'], 'name': l['name']} for l in langs],
        }

    @api.model
    def action_save_my_profile_data(self, vals):
        """Allows user to safely update their own editable profile details."""
        user = self.env.user
        partner = user.partner_id

        user_vals = {}
        partner_vals = {}

        if 'name' in vals and vals['name']:
            user_vals['name'] = vals['name'].strip()
            partner_vals['name'] = vals['name'].strip()
        if 'email' in vals:
            user_vals['email'] = (vals['email'] or '').strip()
            partner_vals['email'] = (vals['email'] or '').strip()
        if 'phone' in vals:
            partner_vals['phone'] = (vals['phone'] or '').strip()
        if 'mobile' in vals:
            partner_vals['mobile'] = (vals['mobile'] or '').strip()
        if 'tz' in vals and vals['tz']:
            user_vals['tz'] = vals['tz']
        if 'lang' in vals and vals['lang']:
            user_vals['lang'] = vals['lang']
        if 'notification_type' in vals and vals['notification_type']:
            user_vals['notification_type'] = vals['notification_type']
        if 'image_1920' in vals:
            user_vals['image_1920'] = vals['image_1920']

        if user_vals:
            user.sudo().write(user_vals)
        if partner_vals:
            partner.sudo().write(partner_vals)

        return {'success': True}

    @api.model
    def action_change_own_password(self, old_passwd, new_passwd, confirm_passwd):
        """Allows the currently logged in user to safely change their own password."""
        user = self.env.user
        if not user or user._is_public():
            return {'success': False, 'message': 'You must be logged in to change your password.'}

        if not old_passwd:
            return {'success': False, 'message': 'Please enter your current password.'}
        if not new_passwd:
            return {'success': False, 'message': 'Please enter a new password.'}
        if len(new_passwd) < 4:
            return {'success': False, 'message': 'New password must be at least 4 characters.'}
        if new_passwd != confirm_passwd:
            return {'success': False, 'message': 'New password and Confirm password do not match.'}

        # Verify old password
        verified = False
        db = self.env.cr.dbname

        # 1. Try standard ResUsers authenticate
        try:
            uid = type(self).authenticate(db, user.login, old_passwd, {'interactive': True})
            if uid == user.id:
                verified = True
        except Exception:
            pass

        # 2. Try _check_credentials with interactive dict
        if not verified:
            try:
                user.sudo()._check_credentials(old_passwd, {'interactive': True})
                verified = True
            except Exception:
                pass

        # 3. Try _check_credentials with single password argument
        if not verified:
            try:
                user.sudo()._check_credentials(old_passwd)
                verified = True
            except Exception:
                pass

        # 4. Try passlib CryptContext directly against user password hash
        if not verified:
            try:
                from passlib.context import CryptContext
                crypt_context = CryptContext(schemes=['pbkdf2_sha512', 'plaintext'], deprecated=['plaintext'])
                self.env.cr.execute("SELECT password FROM res_users WHERE id = %s", (user.id,))
                row = self.env.cr.fetchone()
                if row and row[0]:
                    verified = crypt_context.verify(old_passwd, row[0])
            except Exception:
                pass

        if not verified:
            return {'success': False, 'message': 'Incorrect current password. Please try again.'}

        # Update password
        try:
            user.sudo().write({'password': new_passwd})
            return {'success': True, 'message': 'Password changed successfully!'}
        except Exception as e:
            return {'success': False, 'message': f'Failed to update password: {str(e)}'}

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

    # Job Position Hierarchy: Parent Job (Reporting Job) & Subordinate Jobs
    parent_job_id = fields.Many2one(
        'hr.job',
        string='Parent Job Position',
        compute='_compute_parent_job_id',
        store=True,
        readonly=False,
        help='The senior job position that this role reports to.'
    )

    child_job_ids = fields.One2many(
        'hr.job',
        'parent_job_id',
        string='Subordinate Roles'
    )

    job_hierarchy_html = fields.Html(
        string='Role Hierarchy',
        compute='_compute_job_hierarchy_html',
        help='Visual hierarchy tree of job positions.'
    )

    @api.depends('is_manager_role', 'department_id', 'department_id.parent_id')
    def _compute_parent_job_id(self):
        for job in self:
            if not job.department_id:
                job.parent_job_id = False
                continue

            # Top Director role itself (Managing Director) has no parent
            top_director = self.search([
                ('is_manager_role', '=', True),
                ('department_id.parent_id', '=', False)
            ], limit=1)

            if top_director and job.id == top_director.id:
                job.parent_job_id = False
                continue

            if job.is_manager_role:
                parent_dept = job.department_id.parent_id
                if parent_dept:
                    parent_job = self.search([
                        ('department_id', '=', parent_dept.id),
                        ('is_manager_role', '=', True)
                    ], limit=1)
                    job.parent_job_id = parent_job.id if parent_job else (top_director.id if top_director else False)
                else:
                    # Manager in top department reports to the top director
                    job.parent_job_id = top_director.id if (top_director and top_director.id != job.id) else False
            else:
                # Regular staff role reports to this department's Manager Role
                mgr_job = self.search([
                    ('department_id', '=', job.department_id.id),
                    ('is_manager_role', '=', True),
                    ('id', '!=', job.id)
                ], limit=1)
                job.parent_job_id = mgr_job.id if mgr_job else (top_director.id if top_director else False)

    def _compute_job_hierarchy_html(self):
        all_jobs = self.search([])
        for job in self:
            directors = all_jobs.filtered(lambda j: not j.parent_job_id and any(w in (j.name or '').lower() for w in ['director', 'managing', 'owner', 'ceo', 'head']))
            if not directors:
                directors = all_jobs.filtered(lambda j: not j.parent_job_id and j.is_manager_role)
            if not directors:
                directors = all_jobs.filtered(lambda j: j.is_manager_role and (not j.department_id or not j.department_id.parent_id))
            root = directors[0] if directors else (job.parent_job_id or job)

            def render_node(node, current_id, is_child=False):
                is_active = (node.id == current_id)
                name_style = "font-weight: 700; color: #1e3a8a; background: #e0f2fe; padding: 0.2rem 0.55rem; border-radius: 0.35rem; border-left: 3px solid #0284c7; white-space: nowrap; display: inline-block;" if is_active else "color: #212529; font-weight: 400; font-size: 0.875rem; white-space: nowrap; padding: 0.2rem 0.55rem; display: inline-block;"
                
                cnt = self.env['res.users'].sudo().search_count([('crm_job_id', '=', node.id), ('share', '=', False)])
                if node.is_manager_role and node.department_id and (node.department_id.manager_user_id or node.department_id.manager_id):
                    cnt = max(cnt, 1)

                connector = '<span style="position: absolute; left: -1.25rem; top: -0.45rem; width: 0.95rem; height: 1.35rem; border-left: 1.5px solid #6c757d; border-bottom: 1.5px solid #6c757d; display: inline-block;"></span>' if is_child else ''
                badge_style = "background-color: #dee2e6; color: #212529; border-radius: 50rem; min-width: 1.75rem; height: 1.45rem; display: inline-flex; align-items: center; justify-content: center; font-size: 0.78rem; font-weight: 600; padding: 0 0.45rem; margin-left: auto;"

                html = f'''
                    <div style="position: relative; margin: 0.55rem 0;">
                        {connector}
                        <div style="display: flex; align-items: center; justify-content: space-between; width: 100%; min-height: 1.75rem;">
                            <span style="{name_style}">{node.name or "Untitled"}</span>
                            <span style="{badge_style}">{cnt}</span>
                        </div>
                '''

                children = all_jobs.filtered(lambda j: j.parent_job_id.id == node.id and j.id != node.id)
                if children:
                    html += '<div style="position: relative; margin-left: 1.5rem; padding-left: 1.15rem; border-left: 1.5px solid #6c757d;">'
                    for idx, child in enumerate(children):
                        is_last_child = (idx == len(children) - 1)
                        bottom_mask = '<span style="position: absolute; left: -1.15rem; top: 0.95rem; bottom: -0.55rem; width: 3px; background: #ffffff; margin-left: -2px;"></span>' if is_last_child else ''
                        child_connector = '<span style="position: absolute; left: -1.15rem; top: 0.95rem; width: 1.05rem; height: 1.5px; background: #6c757d; display: inline-block;"></span>'
                        child_is_active = (child.id == current_id)
                        child_name_style = "font-weight: 700; color: #1e3a8a; background: #e0f2fe; padding: 0.2rem 0.55rem; border-radius: 0.35rem; border-left: 3px solid #0284c7; white-space: nowrap; display: inline-block;" if child_is_active else "color: #212529; font-weight: 400; font-size: 0.875rem; white-space: nowrap; padding: 0.2rem 0.55rem; display: inline-block;"
                        
                        child_cnt = self.env['res.users'].sudo().search_count([('crm_job_id', '=', child.id), ('share', '=', False)])
                        if child.is_manager_role and child.department_id and (child.department_id.manager_user_id or child.department_id.manager_id):
                            child_cnt = max(child_cnt, 1)

                        html += f'''
                            <div style="position: relative; margin: 0.55rem 0;">
                                {bottom_mask}
                                {child_connector}
                                <div style="display: flex; align-items: center; justify-content: space-between; width: 100%; min-height: 1.75rem;">
                                    <span style="{child_name_style}">{child.name or "Untitled"}</span>
                                    <span style="{badge_style}">{child_cnt}</span>
                                </div>
                        '''
                        sub_children = all_jobs.filtered(lambda j: j.parent_job_id.id == child.id and j.id != child.id)
                        if sub_children:
                            html += '<div style="position: relative; margin-left: 1.5rem; padding-left: 1.15rem; border-left: 1.5px solid #6c757d;">'
                            for s_idx, sc in enumerate(sub_children):
                                is_last_sub = (s_idx == len(sub_children) - 1)
                                sub_bottom_mask = '<span style="position: absolute; left: -1.15rem; top: 0.95rem; bottom: -0.55rem; width: 3px; background: #ffffff; margin-left: -2px;"></span>' if is_last_sub else ''
                                sc_connector = '<span style="position: absolute; left: -1.15rem; top: 0.95rem; width: 1.05rem; height: 1.5px; background: #6c757d; display: inline-block;"></span>'
                                sc_is_active = (sc.id == current_id)
                                sc_name_style = "font-weight: 700; color: #1e3a8a; background: #e0f2fe; padding: 0.2rem 0.55rem; border-radius: 0.35rem; border-left: 3px solid #0284c7; white-space: nowrap; display: inline-block;" if sc_is_active else "color: #212529; font-weight: 400; font-size: 0.875rem; white-space: nowrap; padding: 0.2rem 0.55rem; display: inline-block;"
                                sc_cnt = self.env['res.users'].sudo().search_count([('crm_job_id', '=', sc.id), ('share', '=', False)])
                                html += f'''
                                    <div style="position: relative; margin: 0.55rem 0;">
                                        {sub_bottom_mask}
                                        {sc_connector}
                                        <div style="display: flex; align-items: center; justify-content: space-between; width: 100%; min-height: 1.75rem;">
                                            <span style="{sc_name_style}">{sc.name or "Untitled"}</span>
                                            <span style="{badge_style}">{sc_cnt}</span>
                                        </div>
                                    </div>
                                '''
                            html += '</div>'
                        html += '</div>'
                    html += '</div>'
                html += '</div>'
                return html

            tree_html = render_node(root, job.id, is_child=False)
            job.job_hierarchy_html = f'''
                <div style="width: 100%; display: block; font-family: inherit; padding: 0.25rem 0 1rem 0;">
                    {tree_html}
                </div>
            '''
        
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

    @api.depends('user_ids', 'user_ids.is_left_employee', 'department_id', 'department_id.manager_id', 'department_id.manager_id.user_id')
    def _compute_assigned_employee_ids(self):
        for job in self:
            mgr_user_id = job.department_id.manager_id.user_id.id if (job.department_id and job.department_id.manager_id and job.department_id.manager_id.user_id) else False
            active_users = job.user_ids.filtered(lambda u: not u.is_left_employee)
            if mgr_user_id and not job.is_manager_role:
                # Exclude the department manager from regular employee list!
                emps = active_users.filtered(lambda u: u.id != mgr_user_id)
            else:
                emps = active_users
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
                vals_to_write = {'crm_job_id': job.id}
                if job.department_id:
                    vals_to_write['crm_department_id'] = job.department_id.id
                if job.default_manager_id:
                    vals_to_write['crm_manager_id'] = job.default_manager_id.id
                u.sudo().write(vals_to_write)
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
            top_director = self.search([
                ('is_manager_role', '=', True),
                ('department_id.parent_id', '=', False)
            ], limit=1)
            top_director_user = (dept.manager_user_id or dept.senior_manager_user_id) if (top_director and top_director.id == rec.id) else (top_director.default_manager_id if top_director else False)

            if rec.is_manager_role:
                if dept.senior_manager_user_id and not dept.senior_manager_user_id.is_left_employee:
                    rec.default_manager_id = dept.senior_manager_user_id.id
                elif dept.parent_id and dept.parent_id.manager_user_id and not dept.parent_id.manager_user_id.is_left_employee:
                    rec.default_manager_id = dept.parent_id.manager_user_id.id
                elif dept.parent_id and dept.parent_id.manager_id and dept.parent_id.manager_id.user_id and not dept.parent_id.manager_id.user_id.is_left_employee:
                    rec.default_manager_id = dept.parent_id.manager_id.user_id.id
                elif dept.manager_user_id and not dept.manager_user_id.is_left_employee and dept.manager_user_id.id != self.env.user.id:
                    rec.default_manager_id = dept.manager_user_id.id
                else:
                    admin_user = self.env.ref('base.user_admin', raise_if_not_found=False) or self.env['res.users'].browse(2)
                    rec.default_manager_id = self.env.ref('base.user_admin').id
            else:
                if dept.manager_user_id and not dept.manager_user_id.is_left_employee:
                    rec.default_manager_id = dept.manager_user_id.id
                elif dept.manager_id and dept.manager_id.user_id and not dept.manager_id.user_id.is_left_employee:
                    rec.default_manager_id = dept.manager_id.user_id.id
                else:
                    admin_user = self.env.ref('base.user_admin', raise_if_not_found=False) or self.env['res.users'].browse(2)
                    rec.default_manager_id = self.env.ref('base.user_admin').id

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
            elif dept.parent_id and dept.parent_id.manager_user_id:
                self.default_manager_id = dept.parent_id.manager_user_id.id
            elif dept.parent_id and dept.parent_id.manager_id and dept.parent_id.manager_id.user_id:
                self.default_manager_id = dept.parent_id.manager_id.user_id.id
            elif dept.manager_user_id:
                self.default_manager_id = dept.manager_user_id.id
            else:
                self.default_manager_id = self.env.ref('base.user_admin').id
        else:
            if dept.manager_user_id:
                self.default_manager_id = dept.manager_user_id.id
            elif dept.manager_id and dept.manager_id.user_id:
                self.default_manager_id = dept.manager_id.user_id.id
            else:
                self.default_manager_id = self.env.ref('base.user_admin').id

    perm_lead_quote = fields.Selection([
        ('none', 'No'),
        ('own', 'User: Own Documents Only'),
        ('subordinates', 'Manager: Assigned Team Only'),
        ('department', 'Department: All Department & Sub-Dept Records'),
        ('all', 'All: All Company Records'),
    ], string='Lead & Quotation', default='own')

    perm_service_ticket = fields.Selection([
        ('none', 'No'),
        ('own', 'User: Own Documents Only'),
        ('subordinates', 'Manager: Assigned Team Only'),
        ('department', 'Department: All Department & Sub-Dept Records'),
        ('all', 'All: All Company Records'),
    ], string='Service Ticket', default='none')

    perm_amc = fields.Selection([
        ('none', 'No'),
        ('own', 'User: Own Documents Only'),
        ('subordinates', 'Manager: Assigned Team Only'),
        ('department', 'Department: All Department & Sub-Dept Records'),
        ('all', 'All: All Company Records'),
    ], string='AMC Contract', default='none')

    perm_equipment = fields.Selection([
        ('none', 'No'),
        ('own', 'User: Own Documents Only'),
        ('subordinates', 'Manager: Assigned Team Only'),
        ('department', 'Department: All Department & Sub-Dept Records'),
        ('all', 'All: All Company Records'),
    ], string='Equipment Master', default='own')

    perm_product_create = fields.Boolean(string='Create Product', default=False)
    perm_product_write = fields.Boolean(string='Update Product', default=False)
    perm_product_read = fields.Boolean(string='View Product', default=False)
    perm_product_unlink = fields.Boolean(string='Delete Product', default=False)

    perm_exhibition_create = fields.Boolean(string='Create Exhibition Contact', default=False)
    perm_exhibition_write = fields.Boolean(string='Update Exhibition Contact', default=False)
    perm_exhibition_read = fields.Boolean(string='View Exhibition Contact', default=False)
    perm_exhibition_unlink = fields.Boolean(string='Delete Exhibition Contact', default=False)

    perm_customer_create = fields.Boolean(string='Create Customer', default=False)
    perm_customer_write = fields.Boolean(string='Update Customer', default=False)
    perm_customer_read = fields.Boolean(string='View Customer', default=False)
    perm_customer_unlink = fields.Boolean(string='Delete Customer', default=False)

    perm_equipment_create = fields.Boolean(string='Create Equipment', default=False)
    perm_equipment_write = fields.Boolean(string='Update Equipment', default=False)
    perm_equipment_read = fields.Boolean(string='View Equipment', default=False)
    perm_equipment_unlink = fields.Boolean(string='Delete Equipment', default=False)

    perm_ticket_create = fields.Boolean(string='Create Ticket', default=False)
    perm_ticket_write = fields.Boolean(string='Update Ticket', default=False)
    perm_ticket_read = fields.Boolean(string='View Ticket', default=False)
    perm_ticket_unlink = fields.Boolean(string='Delete Ticket', default=False)

    perm_amc_create = fields.Boolean(string='Create AMC', default=False)
    perm_amc_write = fields.Boolean(string='Update AMC', default=False)
    perm_amc_read = fields.Boolean(string='View AMC', default=False)
    perm_amc_unlink = fields.Boolean(string='Delete AMC', default=False)

    perm_export = fields.Selection([
        ('none', 'No'),
        ('export', 'Yes'),
    ], string='Excel Export', default='none')

    perm_log = fields.Selection([
        ('none', 'No'),
        ('log', 'Yes'),
    ], string='Log View', default='none')

    perm_company = fields.Selection([
        ('none', 'No'),
        ('create', 'Yes'),
    ], string='Company Creation', default='none')

    # Master "Select All" toggles for each entity
    perm_customer_all = fields.Boolean(string='All', default=False)
    perm_equipment_all = fields.Boolean(string='All', default=False)
    perm_ticket_all = fields.Boolean(string='All', default=False)
    perm_amc_all = fields.Boolean(string='All', default=False)
    perm_product_all = fields.Boolean(string='All', default=False)
    perm_exhibition_all = fields.Boolean(string='All', default=False)
    perm_master_select_all = fields.Boolean(string='Select All Masters', default=False)

    @api.onchange('perm_master_select_all')
    def _onchange_perm_master_select_all(self):
        val = self.perm_master_select_all
        self.perm_customer_all = val
        self.perm_equipment_all = val
        self.perm_ticket_all = val
        self.perm_amc_all = val
        self.perm_product_all = val
        self.perm_exhibition_all = val
        self._onchange_perm_customer_all()
        self._onchange_perm_equipment_all()
        self._onchange_perm_ticket_all()
        self._onchange_perm_amc_all()
        self._onchange_perm_product_all()
        self._onchange_perm_exhibition_all()

    @api.onchange('perm_customer_all')
    def _onchange_perm_customer_all(self):
        val = self.perm_customer_all
        self.perm_customer_create = val
        self.perm_customer_write = val
        self.perm_customer_read = val
        self.perm_customer_unlink = val

    @api.onchange('perm_equipment_all')
    def _onchange_perm_equipment_all(self):
        val = self.perm_equipment_all
        self.perm_equipment_create = val
        self.perm_equipment_write = val
        self.perm_equipment_read = val
        self.perm_equipment_unlink = val

    @api.onchange('perm_ticket_all')
    def _onchange_perm_ticket_all(self):
        val = self.perm_ticket_all
        self.perm_ticket_create = val
        self.perm_ticket_write = val
        self.perm_ticket_read = val
        self.perm_ticket_unlink = val

    @api.onchange('perm_amc_all')
    def _onchange_perm_amc_all(self):
        val = self.perm_amc_all
        self.perm_amc_create = val
        self.perm_amc_write = val
        self.perm_amc_read = val
        self.perm_amc_unlink = val

    @api.onchange('perm_product_all')
    def _onchange_perm_product_all(self):
        val = self.perm_product_all
        self.perm_product_create = val
        self.perm_product_write = val
        self.perm_product_read = val
        self.perm_product_unlink = val

    @api.onchange('perm_exhibition_all')
    def _onchange_perm_exhibition_all(self):
        val = self.perm_exhibition_all
        self.perm_exhibition_create = val
        self.perm_exhibition_write = val
        self.perm_exhibition_read = val
        self.perm_exhibition_unlink = val

    user_count = fields.Integer(string='Users with this Role', compute='_compute_user_count')

    def _compute_user_count(self):
        for job in self:
            job.user_count = self.env['res.users'].search_count([('crm_job_id', '=', job.id), ('share', '=', False)])

    def _compute_employees(self):
        super()._compute_employees()
        for job in self:
            # Count users assigned to this role
            crm_users = self.env['res.users'].search([('crm_job_id', '=', job.id), ('share', '=', False)])
            count = len(crm_users)
            # If manager role and department has a manager assigned, ensure count is at least 1
            if job.is_manager_role and job.department_id and (job.department_id.manager_user_id or job.department_id.manager_id):
                count = max(count, 1)
            job.no_of_employee = count

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
                            admin_user = self.env.ref('base.user_admin', raise_if_not_found=False) or self.env['res.users'].browse(2)
                            vals['default_manager_id'] = admin_user.id if admin_user else False
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
                            admin_user = self.env.ref('base.user_admin', raise_if_not_found=False) or self.env['res.users'].browse(2)
                            vals['default_manager_id'] = admin_user.id if admin_user else False
                else:
                    if dept and dept.manager_user_id:
                        vals['default_manager_id'] = dept.manager_user_id.id
                    elif dept and dept.manager_id and dept.manager_id.user_id:
                        vals['default_manager_id'] = dept.manager_id.user_id.id
                    else:
                        vals['default_manager_id'] = False

        res = super().write(vals)
        perm_keys = [
            'perm_lead_quote', 'perm_service_ticket', 'perm_amc', 'perm_equipment',
            'perm_product_create', 'perm_product_write', 'perm_product_read', 'perm_product_unlink',
            'perm_customer_create', 'perm_customer_write', 'perm_customer_read', 'perm_customer_unlink',
            'perm_equipment_create', 'perm_equipment_write', 'perm_equipment_read', 'perm_equipment_unlink',
            'perm_ticket_create', 'perm_ticket_write', 'perm_ticket_read', 'perm_ticket_unlink',
            'perm_amc_create', 'perm_amc_write', 'perm_amc_read', 'perm_amc_unlink',
            'perm_exhibition_create', 'perm_exhibition_write', 'perm_exhibition_read', 'perm_exhibition_unlink',
            'perm_export', 'perm_log', 'perm_company'
        ]
        if any(k in vals for k in perm_keys):
            for job in self:
                users = self.env['res.users'].search([
                    ('crm_job_id', '=', job.id),
                    ('share', '=', False),
                ])
                users._apply_job_permissions(job)
        return res

    @api.onchange('sub_department_ids', 'department_id')
    def _onchange_check_sub_departments(self):
        if self.sub_department_ids:
            ancestor_ids = set()
            if self.department_id:
                ancestor_ids.add(self.department_id.id)
                curr = self.department_id.parent_id
                while curr:
                    ancestor_ids.add(curr.id)
                    curr = curr.parent_id

            # Find all top-level departments (e.g. Management)
            top_level = self.env['hr.department'].search([('parent_id', '=', False)])
            for t in top_level:
                ancestor_ids.add(t.id)

            # Check if any forbidden department was picked
            invalid = self.sub_department_ids.filtered(lambda d: d.id in ancestor_ids)
            if invalid:
                invalid_names = ", ".join(invalid.mapped('name'))
                # Remove invalid from selection immediately
                self.sub_department_ids = self.sub_department_ids - invalid
                return {
                    'warning': {
                        'title': "Invalid Sub-Department Selection",
                        'message': f"Cannot select '{invalid_names}' as a managed sub-department!\n\nHierarchy flows downward only: top-level parent departments (like Management) or your own department cannot be managed as sub-departments."
                    }
                }


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

    @api.model_create_multi
    def create(self, vals_list):
        departments = super().create(vals_list)
        for dept in departments:
            dept._sync_head_to_user()
        return departments

    def write(self, vals):
        res = super().write(vals)
        if 'manager_user_id' in vals or 'parent_id' in vals:
            for dept in self:
                dept._sync_head_to_user()
        return res

    def _sync_head_to_user(self):
        if not self.manager_user_id:
            return
        user = self.manager_user_id.sudo()
        
        # Auto-link standard hr.department manager_id (Employee) if empty
        if not self.manager_id:
            emp = self.env['hr.employee'].sudo().search([('user_id', '=', user.id)], limit=1)
            if emp:
                self.sudo().write({'manager_id': emp.id})

        # Find the Manager role for this department
        mgr_job = self.env['hr.job'].search([
            ('department_id', '=', self.id),
            ('is_manager_role', '=', True)
        ], limit=1)
        
        # Determine senior manager (e.g. Administrator from Parent Dept)
        senior_mgr_id = False
        if mgr_job and mgr_job.default_manager_id:
            senior_mgr_id = mgr_job.default_manager_id.id
        elif self.parent_id and self.parent_id.manager_user_id:
            senior_mgr_id = self.parent_id.manager_user_id.id

        user_vals = {
            'crm_department_id': self.id,
        }
        if mgr_job:
            user_vals['crm_job_id'] = mgr_job.id
        if senior_mgr_id and senior_mgr_id != user.id:
            user_vals['crm_manager_id'] = senior_mgr_id

        user.with_context(skip_sync=True).write(user_vals)
        if mgr_job:
            user._apply_job_permissions(mgr_job)

        # Also sync to linked hr.employee record so both Employee profile and User profile match!
        emp = self.env['hr.employee'].sudo().search([('user_id', '=', user.id)], limit=1)
        if emp:
            emp_vals = {'department_id': self.id}
            if mgr_job:
                emp_vals['job_id'] = mgr_job.id
            if senior_mgr_id:
                senior_emp = self.env['hr.employee'].sudo().search([('user_id', '=', senior_mgr_id)], limit=1)
                if senior_emp:
                    emp_vals['parent_id'] = senior_emp.id
            emp.with_context(skip_sync=True).sudo().write(emp_vals)

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

    def _compute_total_employee(self):
        super()._compute_total_employee()
        for department in self:
            # Gather all users assigned to this department
            users = self.env['res.users'].sudo().search([
                ('crm_department_id', '=', department.id),
                ('share', '=', False)
            ])
            user_ids = set(users.ids)
            # Include Department Head if appointed
            if department.manager_user_id:
                user_ids.add(department.manager_user_id.id)
            if department.manager_id and department.manager_id.user_id:
                user_ids.add(department.manager_id.user_id.id)
            
            # The count should be at least the unique count of users + employees
            department.total_employee = max(department.total_employee, len(user_ids))

    department_hierarchy_html = fields.Html(
        string='Department Hierarchy',
        compute='_compute_department_hierarchy_html',
        help='Visual hierarchy tree of departments.'
    )

    def _compute_department_hierarchy_html(self):
        all_depts = self.search([])
        for dept in self:
            top_depts = all_depts.filtered(lambda d: not d.parent_id)
            root = top_depts[0] if top_depts else (dept.parent_id or dept)

            def render_node(node, current_id, is_child=False):
                is_active = (node.id == current_id)
                name_style = "font-weight: 700; color: #1e3a8a; background: #e0f2fe; padding: 0.2rem 0.55rem; border-radius: 0.35rem; border-left: 3px solid #0284c7; white-space: nowrap; display: inline-block;" if is_active else "color: #212529; font-weight: 400; font-size: 0.875rem; white-space: nowrap; padding: 0.2rem 0.55rem; display: inline-block;"
                
                connector = '<span style="position: absolute; left: -1.25rem; top: -0.45rem; width: 0.95rem; height: 1.35rem; border-left: 1.5px solid #6c757d; border-bottom: 1.5px solid #6c757d; display: inline-block;"></span>' if is_child else ''
                badge_style = "background-color: #dee2e6; color: #212529; border-radius: 50rem; min-width: 1.75rem; height: 1.45rem; display: inline-flex; align-items: center; justify-content: center; font-size: 0.78rem; font-weight: 600; padding: 0 0.45rem; margin-left: auto;"

                html = f'''
                    <div style="position: relative; margin: 0.55rem 0;">
                        {connector}
                        <div style="display: flex; align-items: center; justify-content: space-between; width: 100%; min-height: 1.75rem;">
                            <span style="{name_style}">{node.name or "Untitled"}</span>
                            <span style="{badge_style}">{node.total_employee}</span>
                        </div>
                '''

                children = all_depts.filtered(lambda d: d.parent_id.id == node.id and d.id != node.id)
                if children:
                    html += '<div style="position: relative; margin-left: 1.5rem; padding-left: 1.15rem; border-left: 1.5px solid #6c757d;">'
                    for idx, child in enumerate(children):
                        is_last_child = (idx == len(children) - 1)
                        bottom_mask = '<span style="position: absolute; left: -1.15rem; top: 0.95rem; bottom: -0.55rem; width: 3px; background: #ffffff; margin-left: -2px;"></span>' if is_last_child else ''
                        child_connector = '<span style="position: absolute; left: -1.15rem; top: 0.95rem; width: 1.05rem; height: 1.5px; background: #6c757d; display: inline-block;"></span>'
                        child_is_active = (child.id == current_id)
                        child_name_style = "font-weight: 700; color: #1e3a8a; background: #e0f2fe; padding: 0.2rem 0.55rem; border-radius: 0.35rem; border-left: 3px solid #0284c7; white-space: nowrap; display: inline-block;" if child_is_active else "color: #212529; font-weight: 400; font-size: 0.875rem; white-space: nowrap; padding: 0.2rem 0.55rem; display: inline-block;"
                        
                        html += f'''
                            <div style="position: relative; margin: 0.55rem 0;">
                                {bottom_mask}
                                {child_connector}
                                <div style="display: flex; align-items: center; justify-content: space-between; width: 100%; min-height: 1.75rem;">
                                    <span style="{child_name_style}">{child.name or "Untitled"}</span>
                                    <span style="{badge_style}">{child.total_employee}</span>
                                </div>
                        '''
                        sub_children = all_depts.filtered(lambda d: d.parent_id.id == child.id and d.id != child.id)
                        if sub_children:
                            html += '<div style="position: relative; margin-left: 1.5rem; padding-left: 1.15rem; border-left: 1.5px solid #6c757d;">'
                            for s_idx, sc in enumerate(sub_children):
                                is_last_sub = (s_idx == len(sub_children) - 1)
                                sub_bottom_mask = '<span style="position: absolute; left: -1.15rem; top: 0.95rem; bottom: -0.55rem; width: 3px; background: #ffffff; margin-left: -2px;"></span>' if is_last_sub else ''
                                sc_connector = '<span style="position: absolute; left: -1.15rem; top: 0.95rem; width: 1.05rem; height: 1.5px; background: #6c757d; display: inline-block;"></span>'
                                sc_is_active = (sc.id == current_id)
                                sc_name_style = "font-weight: 700; color: #1e3a8a; background: #e0f2fe; padding: 0.2rem 0.55rem; border-radius: 0.35rem; border-left: 3px solid #0284c7; white-space: nowrap; display: inline-block;" if sc_is_active else "color: #212529; font-weight: 400; font-size: 0.875rem; white-space: nowrap; padding: 0.2rem 0.55rem; display: inline-block;"
                                html += f'''
                                    <div style="position: relative; margin: 0.55rem 0;">
                                        {sub_bottom_mask}
                                        {sc_connector}
                                        <div style="display: flex; align-items: center; justify-content: space-between; width: 100%; min-height: 1.75rem;">
                                            <span style="{sc_name_style}">{sc.name or "Untitled"}</span>
                                            <span style="{badge_style}">{sc.total_employee}</span>
                                        </div>
                                    </div>
                                '''
                            html += '</div>'
                        html += '</div>'
                    html += '</div>'
                html += '</div>'
                return html

            tree_html = render_node(root, dept.id, is_child=False)
            dept.department_hierarchy_html = f'''
                <div style="width: 100%; max-width: clamp(18rem, 28vw, 32rem); display: block; font-family: inherit; padding: 0.25rem 0 1rem 0;">
                    {tree_html}
                </div>
            '''

    def name_get(self):
        """Display only the department's own name (e.g. 'Sales') rather than the full parent path."""
        result = []
        for dept in self:
            result.append((dept.id, dept.name or ''))
        return result

    @api.depends('name')
    def _compute_display_name(self):
        """Display_name override to prevent long slash-separated paths."""
        for dept in self:
            dept.display_name = dept.name or ''
