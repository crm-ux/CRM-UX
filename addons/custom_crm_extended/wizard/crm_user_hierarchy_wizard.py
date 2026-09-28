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
            lines = []
            for idx, person in enumerate(chain):
                is_target = (person.id == user.id)
                name = person.name or person.login or "Unnamed"
                role_title = person.crm_job_id.name if person.crm_job_id else (person.crm_department_id.name if person.crm_department_id else ("Employee" if not person.crm_manager_id else "Team Member"))
                
                # Odoo avatar image
                avatar_url = f"/web/image?model=res.users&id={person.id}&field=avatar_128"
                
                # Subordinate count badge (Odoo style)
                sub_count = len(person.crm_subordinate_ids.filtered(lambda u: u.active and not u.share))
                sub_badge = f"""
                <span class='badge rounded-pill text-bg-light border ms-auto' style='font-size: 0.72rem; padding: 0.35rem 0.6rem; color: #475569;'>
                    {sub_count}
                </span>
                """ if sub_count > 0 else ""

                # Target employee highlight vs regular manager
                if is_target:
                    card_border = "border: 1.5px solid #007bff; background-color: #f8faff;"
                    name_color = "#007bff"
                else:
                    card_border = "border: 1px solid #e2e8f0; background-color: #ffffff;"
                    name_color = "#1e293b"

                is_last = (idx == total - 1)
                connector_line = "" if is_last else "<div style='position: absolute; left: 18px; top: 38px; bottom: -12px; width: 2px; background: #cbd5e1;'></div>"

                lines.append(f"""
                <div style='position: relative; display: flex; align-items: center; margin-bottom: 12px;'>
                    {connector_line}
                    <!-- Circular Avatar -->
                    <img src='{avatar_url}' 
                         alt='{name}'
                         style='width: 38px; height: 38px; border-radius: 50%; object-fit: cover; border: 1.5px solid #e2e8f0; background: #f1f5f9; z-index: 1;' 
                         onerror="this.onerror=null; this.src='/web/static/img/placeholder.png';"/>
                    
                    <!-- Odoo Employee Node Card -->
                    <div style='margin-left: 12px; padding: 6px 14px; border-radius: 6px; {card_border} display: flex; align-items: center; flex: 1; max-width: 320px;'>
                        <div>
                            <div style='font-weight: 600; font-size: 0.88rem; color: {name_color}; line-height: 1.2;'>
                                {name}
                            </div>
                            <div style='font-size: 0.74rem; color: #64748b; margin-top: 2px;'>
                                {role_title}
                            </div>
                        </div>
                        {sub_badge}
                    </div>
                </div>
                """)

            wizard.hierarchy_html = f"""
            <div style='padding: 10px 16px; font-family: inherit;'>
                <div style='padding-left: 6px;'>
                    {''.join(lines)}
                </div>
            </div>
            """