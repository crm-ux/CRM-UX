# -*- coding: utf-8 -*-
import logging
import re

from odoo import api, models

_logger = logging.getLogger(__name__)

VIEW_PATCH_NAME = 'crm.lead.form.priority.dropdown.fix'
CONFIG_KEY = 'custom_crm_extended.priority_view_patch_version'
PATCH_VERSION = '1.2.3'

PRIORITY_FIX_ARCH = """
    <xpath expr="//field[@name='priority'][@widget='priority']" position="attributes">
        <attribute name="invisible">1</attribute>
    </xpath>
    <xpath expr="//field[@name='x_assign_to_id']/following-sibling::field[@name='priority']" position="attributes">
        <attribute name="invisible">1</attribute>
    </xpath>
    <xpath expr="//field[@name='x_assign_to_id']" position="after">
        <field name="x_priority_selection" string="Priority"/>
    </xpath>
"""


class CrmLeadViewPatch(models.AbstractModel):
    _name = 'crm.lead.view.patch'
    _description = 'Patch custom CRM lead form views (Assignment priority dropdown)'

    @api.model
    def _find_views_to_patch(self):
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
        """Rewrite Studio/DB view XML in place."""
        arch = view.arch_db or ''
        if not arch or 'priority' not in arch:
            return False

        new_arch = arch
        new_arch = re.sub(
            r'(\<field\b[^>]*\bname=["\']priority["\'][^>]*?)\s+widget=["\']priority["\']([^>]*\>)',
            r'\1\2',
            new_arch,
            flags=re.IGNORECASE,
        )
        new_arch = re.sub(
            r'(\<field\b[^>]*?)\s+widget=["\']priority["\']([^>]*\bname=["\']priority["\'][^>]*\>)',
            r'\1\2',
            new_arch,
            flags=re.IGNORECASE,
        )

        if (
            'ASSIGNMENT' in arch.upper()
            or 'Assign To' in arch
            or 'Assign to' in arch
            or 'widget="priority"' in arch
            or "widget='priority'" in arch
        ):
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
        _logger.info('Patched crm.lead form view id=%s name=%s', view.id, view.name)
        return True

    @api.model
    def ensure_assignment_priority_dropdown(self):
        View = self.env['ir.ui.view'].sudo()

        View.search([
            ('name', '=', VIEW_PATCH_NAME),
            ('model', '=', 'crm.lead'),
        ]).unlink()

        patched = 0
        for view in self._find_views_to_patch():
            if self._patch_arch_db_direct(view):
                patched += 1

        for parent in self._find_views_to_patch():
            if View.search_count([
                ('inherit_id', '=', parent.id),
                ('name', '=', VIEW_PATCH_NAME),
            ]):
                continue
            try:
                View.create({
                    'name': VIEW_PATCH_NAME,
                    'model': 'crm.lead',
                    'inherit_id': parent.id,
                    'priority': 9999,
                    'mode': 'extension',
                    'arch': PRIORITY_FIX_ARCH,
                })
            except Exception as exc:
                _logger.warning(
                    'Could not create priority fix inherit on view %s: %s',
                    parent.id,
                    exc,
                )

        _logger.info(
            'Assignment priority patch finished (%s DB view(s) updated).',
            patched,
        )
        return patched
