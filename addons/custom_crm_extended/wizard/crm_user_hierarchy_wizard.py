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

            lines = []
            total = len(chain)
            for idx, person in enumerate(chain):
                is_target = (person.id == user.id)
                name = person.name or person.login or "Unnamed"
                initial = name[:1].upper() if name else "U"
                role_title = person.crm_job_id.name if person.crm_job_id else (person.crm_department_id.name if person.crm_department_id else ("Employee" if not person.crm_manager_id else "Team Member"))
                bg_color = palette[person.id % len(palette)]
                
                # Card styling
                if is_target:
                    card_style = "border: 2px solid #007bff; background: #f0f7ff; box-shadow: 0 2px 6px rgba(0,123,255,0.15);"
                    badge_tag = "<span style='font-size: 0.65rem; background: #007bff; color: white; padding: 2px 6px; border-radius: 4px; margin-left: 6px;'>Current</span>"
                else:
                    card_style = "border: 1px solid #e2e8f0; background: #ffffff;"
                    badge_tag = ""

                # Connecting vertical tree line
                connector = ""
                if idx < total - 1:
                    connector = """
                    <div style='display: flex; align-items: center; margin-left: 20px; height: 28px;'>
                        <div style='width: 2px; height: 100%; background: #cbd5e1;'></div>
                        <i class='fa fa-arrow-down' style='font-size: 0.75rem; color: #94a3b8; margin-left: 10px;'></i>
                    </div>
                    """

                lines.append(f"""
                <div style='display: flex; align-items: center; position: relative;'>
                    <!-- Avatar -->
                    <div style='width: 38px; height: 38px; border-radius: 8px; background: {bg_color}; color: #fff; display: flex; align-items: center; justify-content: center; font-weight: 700; font-size: 1rem; flex-shrink: 0;'>
                        {initial}
                    </div>
                    <!-- Details Card -->
                    <div style='margin-left: 12px; padding: 6px 14px; border-radius: 8px; {card_style} min-width: 200px;'>
                        <div style='font-weight: 600; font-size: 0.88rem; color: #1e293b; display: flex; align-items: center;'>
                            {name} {badge_tag}
                        </div>
                        <div style='font-size: 0.75rem; color: #64748b;'>
                            {role_title}
                        </div>
                    </div>
                </div>
                {connector}
                """)

            target_name = user.name or user.login or "Employee"
            wizard.hierarchy_html = f"""
            <div style='font-family: inherit; padding: 12px 16px;'>
                <!-- Header -->
                <div style='display: flex; align-items: center; justify-content: space-between; border-bottom: 2px solid #f1f5f9; padding-bottom: 10px; margin-bottom: 20px;'>
                    <div style='font-size: 0.85rem; font-weight: 700; letter-spacing: 0.5px; color: #334155; text-transform: uppercase;'>
                        <i class='fa fa-sitemap me-1' style='color: #007bff;'></i> Reporting Chain &mdash; {target_name}
                    </div>
                </div>
                <!-- Linear Reporting Chain -->
                <div style='padding-left: 10px;'>
                    {''.join(lines)}
                </div>
            </div>
            """