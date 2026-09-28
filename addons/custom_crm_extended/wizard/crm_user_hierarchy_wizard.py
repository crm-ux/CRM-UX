# -*- coding: utf-8 -*-
from odoo import models, fields, api


class CrmUserHierarchyWizard(models.TransientModel):
    _name = 'crm.user.hierarchy.wizard'
    _description = 'User Organization Hierarchy Wizard'

    user_id = fields.Many2one('res.users', string='Employee / User', required=True)
    hierarchy_html = fields.Html(string='Organization Hierarchy', compute='_compute_hierarchy_html')

    @api.depends('user_id')
    def _compute_hierarchy_html(self):
        for wizard in self:
            user = wizard.user_id
            if not user:
                wizard.hierarchy_html = "<div class='text-muted p-4'>No user selected.</div>"
                continue

            # 1. Build bottom-to-top direct reporting chain
            chain = []
            curr = user
            visited = set()
            while curr and curr.id not in visited:
                visited.add(curr.id)
                chain.append(curr)
                curr = curr.crm_manager_id

            # Reverse to display top-to-bottom: Top Owner -> Manager -> Target Employee
            chain.reverse()

            palette = [
                '#2563eb', '#059669', '#d97706', '#dc2626', '#7c3aed',
                '#0891b2', '#4f46e5', '#ca8a04', '#0d9488', '#e11d48',
                '#9333ea', '#16a34a', '#ea580c', '#0284c7', '#c026d3',
                '#65a30d', '#db2777', '#0369a1', '#b45309', '#475569'
            ]

            total = len(chain)
            lines = []
            for idx, person in enumerate(chain):
                is_target = (person.id == user.id)
                name = person.name or person.login or "Unnamed"
                initial = name[:1].upper() if name else "U"
                bg_color = palette[person.id % len(palette)]
                
                # Role subtitle (Admin has no subtitle just like the image)
                is_admin = person._is_admin() or person.has_group('base.group_system') or (person.id == 2)
                if is_admin:
                    role_html = ""
                    name_color = "#4338ca"  # Indigo for Admin
                else:
                    role = person.crm_job_id.name if person.crm_job_id else (person.crm_department_id.name if person.crm_department_id else "")
                    role_html = f"<div style='font-size: 0.76rem; color: #64748b; font-weight: 500; margin-top: 1px;'>{role}</div>" if role else ""
                    name_color = "#0f172a"

                # Avatar square with cyan border highlight for target person
                if is_target:
                    avatar_box = f"""
                    <div style='width: 2.3rem; height: 2.3rem; min-width: 2.3rem; border-radius: 0.45rem; background: {bg_color}; color: #ffffff; display: flex; align-items: center; justify-content: center; font-weight: 700; font-size: 1.05rem; box-shadow: 0 0 0 2px #ffffff, 0 0 0 4px #0ea5e9;'>
                        {initial}
                    </div>
                    """
                else:
                    avatar_box = f"""
                    <div style='width: 2.3rem; height: 2.3rem; min-width: 2.3rem; border-radius: 0.45rem; background: {bg_color}; color: #ffffff; display: flex; align-items: center; justify-content: center; font-weight: 700; font-size: 1.05rem;'>
                        {initial}
                    </div>
                    """

                # Stepped tree indentation + grey L-connector branch
                indent = idx * 2.2  # rem
                if idx > 0:
                    connector = """
                    <div style='position: absolute; left: -1.25rem; top: -0.7rem; width: 1.15rem; height: 1.85rem; border-left: 1.5px solid #cbd5e1; border-bottom: 1.5px solid #cbd5e1; pointer-events: none;'></div>
                    """
                else:
                    connector = ""

                lines.append(f"""
                <div style='position: relative; margin-left: {indent}rem; margin-bottom: 1.3rem; display: flex; align-items: center;'>
                    {connector}
                    {avatar_box}
                    <div style='margin-left: 0.75rem;'>
                        <div style='font-weight: 700; font-size: 0.95rem; color: {name_color}; line-height: 1.2;'>
                            {name}
                        </div>
                        {role_html}
                    </div>
                </div>
                """)

            wizard.hierarchy_html = f"""
            <style>
                .modal-header .btn-close {{ display: none !important; }}
                .modal-dialog {{ max-width: 28rem !important; }}
            </style>
            <div style='padding: 0.5rem 1rem; font-family: inherit;'>
                {''.join(lines)}
            </div>
            """


