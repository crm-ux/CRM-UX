# -*- coding: utf-8 -*-
from odoo import models, fields, api


class CrmUserHierarchyWizard(models.TransientModel):
    _name = 'crm.user.hierarchy.wizard'
    _description = 'User Organization Hierarchy Wizard'

    user_id = fields.Many2one('res.users', string='Employee / User', required=True)
    hierarchy_html = fields.Html(string='Organization Hierarchy', compute='_compute_hierarchy_html')

    @api.depends('user_id')
    def _compute_hierarchy_html(self):
        for rec in self:
            if not rec.user_id:
                rec.hierarchy_html = ""
                continue

            target_user = rec.user_id

            # 1. Trace upward chain to find the Top Leader (Root)
            visited = set()
            chain = []
            curr = target_user
            while curr and curr.id not in visited:
                visited.add(curr.id)
                chain.insert(0, curr)
                curr = curr.crm_manager_id

            # Top leader
            top_user = chain[0] if chain else target_user

            # Color generator for user avatar boxes based on initial
            color_palette = [
                '#16a34a', '#9333ea', '#0284c7', '#ea580c', '#0d9488',
                '#e11d48', '#4f46e5', '#ca8a04', '#2563eb', '#7c3aed'
            ]

            def get_color(name_str):
                if not name_str:
                    return '#0284c7'
                idx = sum(ord(ch) for ch in name_str) % len(color_palette)
                return color_palette[idx]

            # Render tree node
            def render_node(user, current_id, is_child=False):
                is_active = (user.id == current_id)
                initial = (user.name or 'U')[:1].upper()
                bg_color = get_color(user.name)

                # Count direct subordinates
                sub_count = len(user.crm_subordinate_ids.filtered(lambda u: u.active and not u.share))
                badge_html = f'<span style="background-color: #dee2e6; color: #212529; border-radius: 50rem; min-width: 1.6rem; height: 1.35rem; display: inline-flex; align-items: center; justify-content: center; font-size: 0.75rem; font-weight: 600; padding: 0 0.4rem; margin-left: auto;">{sub_count}</span>' if sub_count > 0 else ''

                connector = '<span style="position: absolute; left: -1.25rem; top: -0.45rem; width: 0.95rem; height: 1.45rem; border-left: 1.5px solid #6c757d; border-bottom: 1.5px solid #6c757d; display: inline-block;"></span>' if is_child else ''

                # Avatar square
                avatar_border = 'box-shadow: 0 0 0 2px #38bdf8;' if is_active else ''
                avatar_box = f'<span style="display:inline-flex; align-items:center; justify-content:center; width:2rem; height:2rem; min-width:2rem; border-radius:0.35rem; background:{bg_color}; color:#ffffff; font-weight:700; font-size:0.95rem; margin-right:0.65rem; {avatar_border}">{initial}</span>'

                # Name and Job title
                role_name = user.crm_job_id.name if user.crm_job_id else (user.crm_department_id.name if user.crm_department_id else 'Employee')
                active_box_style = "background: #f0f9ff; border: 1.5px solid #0284c7; padding: 0.25rem 0.6rem; border-radius: 0.4rem;" if is_active else ""

                name_html = f'''
                    <div style="display:inline-flex; flex-direction:column; {active_box_style}">
                        <span style="font-weight: 700; color: #0f172a; font-size: 0.92rem; line-height: 1.2;">{user.name or 'Unknown'}</span>
                        <span style="font-size: 0.78rem; color: #64748b; font-weight: 500;">{role_name}</span>
                    </div>
                '''

                node_html = f'''
                    <div style="position: relative; margin: 0.65rem 0;">
                        {connector}
                        <div style="display: flex; align-items: center; width: 100%; min-height: 2.1rem;">
                            {avatar_box}
                            {name_html}
                            {badge_html}
                        </div>
                '''

                # Render subordinate direct reports
                subs = user.crm_subordinate_ids.filtered(lambda u: u.active and not u.share)
                if subs:
                    node_html += '<div style="position: relative; margin-left: 1.5rem; padding-left: 1.15rem; border-left: 1.5px solid #6c757d;">'
                    for idx, sub in enumerate(subs):
                        is_last = (idx == len(subs) - 1)
                        mask = '<span style="position: absolute; left: -1.15rem; top: 1rem; bottom: -0.55rem; width: 3px; background: #ffffff; margin-left: -2px;"></span>' if is_last else ''
                        node_html += mask
                        node_html += render_node(sub, current_id, is_child=True)
                    node_html += '</div>'

                node_html += '</div>'
                return node_html

            tree_content = render_node(top_user, target_user.id, is_child=False)

            rec.hierarchy_html = f'''
                <div style="padding: 1rem 1.2rem; background: #ffffff; border-radius: 0.5rem; font-family: inherit;">
                    <div style="display: flex; align-items: center; justify-content: space-between; border-bottom: 1.5px solid #e2e8f0; padding-bottom: 0.65rem; margin-bottom: 0.85rem;">
                        <span style="font-weight: 800; font-size: 0.85rem; letter-spacing: 0.05em; color: #0f172a; text-transform: uppercase;">ORGANIZATION CHART</span>
                        <span style="font-size: 0.78rem; font-weight: 700; color: #0284c7; display: flex; align-items: center; gap: 0.35rem;">
                            <i class="fa fa-sitemap"></i> FULL CHART
                        </span>
                    </div>
                    <div style="overflow-x: auto; padding: 0.25rem 0;">
                        {tree_content}
                    </div>
                </div>
            '''
