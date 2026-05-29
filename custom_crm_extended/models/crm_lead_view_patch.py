# -*- coding: utf-8 -*-
import re

from odoo import api, models

VIEW_PATCH_NAME = 'crm.lead.form.priority.dropdown.fix'
CONFIG_KEY = 'custom_crm_extended.priority_view_patch_version'
PATCH_VERSION = '1.2.2'

PRIORITY_FIX_ARCH = """
    <xpath expr="//field[@name='priority'][@widget='priority']" position="replace">
        <field name="x_priority_selection" string="Priority"/>
    </xpath>
    <xpath expr="//group[@string='Assignment']//field[@name='priority']" position="replace">
        <field name="x_priority_selection" string="Priority"/>
    </xpath>
    <xpath expr="//group[@string='ASSIGNMENT']//field[@name='priority']" position="replace">
        <field name="x_priority_selection" string="Priority"/>
    </xpath>
    <xpath expr="//field[@name='x_assign_to_id']/following-sibling::field[@name='priority']" position="replace">
        <field name="x_priority_selection" string="Priority"/>
    </xpath>
    <xpath expr="//field[@name='user_id']/following-sibling::field[@name='priority']" position="replace">
        <field name="x_priority_selection" string="Priority"/>
    </xpath>
"""


class CrmLeadViewPatch(models.AbstractModel):
    _name = 'crm.lead.view.patch'
    _description = 'Patch custom CRM lead form views (Assignment priority dropdown)'

    @api.model
    def _find_assignment_views(self):
        View = self.env['ir.ui.view'].sudo()
        candidates = View.search([
            ('model', '=', 'crm.lead'),
            ('type', '=', 'form'),
        ])
        return candidates.filtered(
            lambda v: v.arch_db
            and 'priority' in v.arch_db
            and (
                'ASSIGNMENT' in v.arch_db.upper()
                or 'Assign To' in v.arch_db
                or 'Assign to' in v.arch_db
                or 'widget="priority"' in v.arch_db
                or "widget='priority'" in v.arch_db
            )
        )

    @api.model
    def _patch_arch_db_direct(self, view):
        """Rewrite custom/Studio view XML: drop star widget, use dropdown field."""
        arch = view.arch_db or ''
        if not arch or 'priority' not in arch:
            return False

        new_arch = re.sub(
            r'(\<field\b[^>]*\bname=["\']priority["\'][^>]*?)\s+widget=["\']priority["\']([^>]*\>)',
            r'\1\2',
            arch,
            flags=re.IGNORECASE,
        )
        new_arch = re.sub(
            r'(\<field\b[^>]*?)\s+widget=["\']priority["\']([^>]*\bname=["\']priority["\'][^>]*\>)',
            r'\1\2',
            new_arch,
            flags=re.IGNORECASE,
        )

        is_assignment_view = (
            'ASSIGNMENT' in arch.upper()
            or 'Assign To' in arch
            or 'Assign to' in arch
        )
        if is_assignment_view:
            new_arch = re.sub(
                r'<field\b([^>]*?)\bname=["\']priority["\']([^>]*)/>',
                r'<field\1name="x_priority_selection"\2/>',
                new_arch,
                flags=re.IGNORECASE,
            )
            new_arch = re.sub(
                r'<field\b([^>]*?)\bname=["\']priority["\']([^>]*)>',
                r'<field\1name="x_priority_selection"\2>',
                new_arch,
                flags=re.IGNORECASE,
            )

        if new_arch == arch:
            return False

        view.write({'arch_db': new_arch})
        return True

    @api.model
    def ensure_assignment_priority_dropdown(self):
        View = self.env['ir.ui.view'].sudo()

        # Remove previous auto-patch inherits so we can re-apply on upgrade
        View.search([
            ('name', '=', VIEW_PATCH_NAME),
            ('model', '=', 'crm.lead'),
        ]).unlink()

        for view in self._find_assignment_views():
            self._patch_arch_db_direct(view)

        for parent in self._find_assignment_views():
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
