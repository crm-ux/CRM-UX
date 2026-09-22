# -*- coding: utf-8 -*-
import logging
import re

_logger = logging.getLogger(__name__)

BROKEN_VIEW_NAMES = [
    'crm.lead.form.hide.default.priority.fix',
    'crm.lead.form.priority.dropdown.fix',
]


def pre_init_hook(env):
    """Remove broken auto-generated views so module upgrade can succeed."""
    View = env['ir.ui.view'].sudo()
    broken = View.search([
        ('model', '=', 'crm.lead'),
        ('name', 'in', BROKEN_VIEW_NAMES),
    ])
    if broken:
        broken.unlink()
        _logger.info('Removed %s broken CRM view(s) before upgrade.', len(broken))

    label_re = re.compile(
        r'<label\b[^>]*\bfor=["\']priority["\'][^>]*/>\s*',
        re.IGNORECASE,
    )
    for view in View.search([('model', '=', 'crm.lead'), ('type', '=', 'form')]):
        if not view.arch_db or 'for="priority"' not in view.arch_db:
            continue
        cleaned = label_re.sub('', view.arch_db)
        if cleaned != view.arch_db:
            view.write({'arch_db': cleaned})
            _logger.info('Cleaned orphan priority label in view id=%s', view.id)


def post_init_hook(env):
    """Strip star widget from custom Studio form views (safe: keeps labels)."""
    View = env['ir.ui.view'].sudo()
    for view in View.search([('model', '=', 'crm.lead'), ('type', '=', 'form')]):
        arch = view.arch_db or ''
        if 'widget="priority"' not in arch and "widget='priority'" not in arch:
            continue
        new_arch = re.sub(
            r'\s+widget=["\']priority["\']',
            '',
            arch,
            flags=re.IGNORECASE,
        )
        if new_arch != arch:
            view.write({'arch_db': new_arch})
            _logger.info('Removed priority star widget in view id=%s', view.id)

    # Restrict utm.source create/unlink to Administrators only
    Access = env['ir.model.access'].sudo()
    acc = Access.search([('name', '=', 'access_utm_source_user')], limit=1)
    if acc:
        acc.write({'perm_create': False, 'perm_unlink': False, 'perm_write': False})
        _logger.info('Restricted utm.source create/write/unlink for regular users.')

    # Auto-create linked hr.employee for all existing internal users
    internal_group = env.ref('base.group_user', raise_if_not_found=False)
    if internal_group:
        users = env['res.users'].sudo().search([
            ('share', '=', False),
            ('groups_id', 'in', [internal_group.id])
        ])
        for user in users:
            emp = env['hr.employee'].sudo().search([('user_id', '=', user.id)], limit=1)
            emp_vals = {
                'name': (user.name or user.login or '').strip(),
                'work_email': user.email or user.login,
                'company_id': user.company_id.id if user.company_id else False,
                'department_id': user.crm_department_id.id if user.crm_department_id else False,
                'job_id': user.crm_job_id.id if user.crm_job_id else False,
                'expense_manager_id': user.crm_expense_manager_id.id if user.crm_expense_manager_id else False,
                'category_ids': [(6, 0, user.crm_employee_tag_ids.ids)] if user.crm_employee_tag_ids else [(5, 0, 0)],
            }
            if user.crm_manager_id:
                mgr = env['hr.employee'].sudo().search([('user_id', '=', user.crm_manager_id.id)], limit=1)
                emp_vals['parent_id'] = mgr.id if mgr else False
            else:
                emp_vals['parent_id'] = False

            if not emp:
                emp_vals['user_id'] = user.id
                env['hr.employee'].with_context(skip_sync=True).sudo().create(emp_vals)
            else:
                emp.with_context(skip_sync=True).sudo().write(emp_vals)
        _logger.info('Synced and auto-created hr.employee for %s existing internal users.', len(users))

    _logger.info('custom_crm_extended 1.3.0 ready.')
