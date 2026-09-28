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
                job_name = person.crm_job_id.name if person.crm_job_id else ""
                dept_name = person.crm_department_id.name if person.crm_department_id else ""
                
                # Dynamic role subtitle
                if job_name and dept_name:
                    role_title = f"{job_name} &bull; {dept_name}"
                elif job_name:
                    role_title = job_name
                elif dept_name:
                    role_title = dept_name
                else:
                    role_title = "Manager" if person.crm_subordinate_ids else "Employee"

                # Dynamic Odoo avatar image
                avatar_url = f"/web/image?model=res.users&id={person.id}&field=avatar_128"
                
                # Subordinate count badge (Odoo theme pill)
                sub_count = len(person.crm_subordinate_ids.filtered(lambda u: u.active and not u.share))
                sub_badge = f"""
                <span class='badge rounded-pill bg-light text-dark border ms-auto' title='{sub_count} Direct Reports' style='font-size: 0.72rem; padding: 0.35rem 0.6rem;'>
                    {sub_count}
                </span>
                """ if sub_count > 0 else ""

                # Dynamic Theme-aware Card styling using Bootstrap & CSS variables
                if is_target:
                    card_classes = "border border-primary bg-primary-subtle shadow-sm"
                    name_classes = "text-primary fw-bold"
                else:
                    card_classes = "border border-secondary-subtle bg-body"
                    name_classes = "text-body fw-bold"

                is_last = (idx == total - 1)
                connector_line = "" if is_last else "<div class='position-absolute' style='left: 1.15rem; top: 2.4rem; bottom: -0.85rem; width: 2px; background: var(--border-color, #cbd5e1);'></div>"

                lines.append(f"""
                <div class='position-relative d-flex align-items-center mb-3'>
                    {connector_line}
                    <!-- Dynamic Theme Avatar -->
                    <img src='{avatar_url}' 
                         alt='{name}'
                         class='rounded-circle border border-2 border-secondary-subtle bg-light shadow-sm'
                         style='width: 2.4rem; height: 2.4rem; object-fit: cover; z-index: 1;' 
                         onerror="this.onerror=null; this.src='/web/static/img/placeholder.png';"/>
                    
                    <!-- Dynamic Odoo Employee Node Card -->
                    <div class='ms-3 p-2 px-3 rounded-2 {card_classes} d-flex align-items-center flex-grow-1' style='max-width: 22rem;'>
                        <div class='overflow-hidden text-truncate'>
                            <div class='{name_classes}' style='font-size: 0.88rem; line-height: 1.25;'>
                                {name}
                            </div>
                            <div class='text-muted' style='font-size: 0.74rem; margin-top: 0.15rem;'>
                                {role_title}
                            </div>
                        </div>
                        {sub_badge}
                    </div>
                </div>
                """)

            wizard.hierarchy_html = f"""
            <div class='p-3 text-body bg-body' style='font-family: inherit;'>
                <div class='ps-1'>
                    {''.join(lines)}
                </div>
            </div>
            """
