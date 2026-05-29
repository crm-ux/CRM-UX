# -*- coding: utf-8 -*-
from odoo import api, models

VIEW_PATCH_NAME = 'crm.lead.form.priority.dropdown.fix'
CONFIG_KEY = 'custom_crm_extended.priority_view_patch_version'
PATCH_VERSION = '1.2.1'

PRIORITY_FIX_ARCH = """
    <xpath expr="//field[@name='priority'][@widget='priority']" position="replace">
        <field name="priority" string="Priority"/>
    </xpath>
    <xpath expr="//group[@string='Assignment']//field[@name='priority']" position="replace">
        <field name="priority" string="Priority"/>
    </xpath>
    <xpath expr="//group[@string='ASSIGNMENT']//field[@name='priority']" position="replace">
        <field name="priority" string="Priority"/>
    </xpath>
    <xpath expr="//field[@name='x_assign_to_id']/following-sibling::field[@name='priority']" position="replace">
        <field name="priority" string="Priority"/>
    </xpath>
    <xpath expr="//field[@name='priority']" position="attributes">
        <attribute name="widget" remove="1"/>
    </xpath>
"""


class CrmLeadViewPatch(models.AbstractModel):
    _name = 'crm.lead.view.patch'
    _description = 'Patch custom CRM lead form views (Assignment priority dropdown)'

    @api.model
    def ensure_assignment_priority_dropdown(self):
        """Attach a high-priority inherit to DB/Studio views that define ASSIGNMENT."""
        View = self.env['ir.ui.view'].sudo()
        parents = View.search([
            ('model', '=', 'crm.lead'),
            ('type', '=', 'form'),
            ('arch_db', 'ilike', 'ASSIGNMENT'),
        ])
        parents |= View.search([
            ('model', '=', 'crm.lead'),
            ('type', '=', 'form'),
            ('arch_db', 'ilike', 'widget="priority"'),
            ('arch_db', 'ilike', 'Assign'),
        ])
        parents = parents.filtered(lambda v: 'priority' in (v.arch_db or ''))

        for parent in parents:
            if View.search_count([
                ('inherit_id', '=', parent.id),
                ('name', '=', VIEW_PATCH_NAME),
            ]):
                continue
            View.create({
                'name': VIEW_PATCH_NAME,
                'model': 'crm.lead',
                'inherit_id': parent.id,
                'priority': 1000,
                'mode': 'extension',
                'arch': PRIORITY_FIX_ARCH,
            })
