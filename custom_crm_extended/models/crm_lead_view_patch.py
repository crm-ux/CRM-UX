# -*- coding: utf-8 -*-
import logging
import re

from odoo import api, models

_logger = logging.getLogger(__name__)

VIEW_PATCH_NAME = 'crm.lead.form.hide.default.priority.fix'
CONFIG_KEY = 'custom_crm_extended.priority_view_patch_version'
PATCH_VERSION = '1.2.6'

PRIORITY_FIX_ARCH = """
    <xpath expr="//form//field[@name='priority']" position="attributes">
        <attribute name="invisible">1</attribute>
    </xpath>
    <xpath expr="//field[@name='x_assign_to_id']" position="after">
        <field name="priority" invisible="1"/>
        <field name="x_priority_selection" string="Priority"/>
    </xpath>
"""


class CrmLeadViewPatch(models.AbstractModel):
    _name = 'crm.lead.view.patch'
    _description = 'Hide default priority stars; show dropdown on custom CRM views'

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
        arch = view.arch_db or ''
        if not arch or 'priority' not in arch:
            return False

        new_arch = re.sub(
            r'(\<field\b[^>]*\bname=["\']priority["\'][^>]*?)\s+widget=["\']priority["\']([^>]*\>)',
            r'\1 invisible="1"\2',
            arch,
            flags=re.IGNORECASE,
        )
        new_arch = re.sub(
            r'(\<field\b[^>]*?)\s+widget=["\']priority["\']([^>]*\bname=["\']priority["\'][^>]*\>)',
            r'\1 invisible="1"\2',
            new_arch,
            flags=re.IGNORECASE,
        )
        if 'invisible' not in new_arch and 'name="priority"' in new_arch:
            new_arch = re.sub(
                r'<field\b([^>]*?)\bname=["\']priority["\']([^>]*)/>',
                r'<field\1name="priority"\2 invisible="1"/>',
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
        self.ensure_crm_lead_form_js_class()
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

        _logger.info('Priority hide/dropdown patch done (%s DB view(s) updated).', patched)
        return patched

    @api.model
    def ensure_crm_lead_form_js_class(self):
        """Add js_class on custom Studio form views so New opens the wizard."""
        View = self.env['ir.ui.view'].sudo()
        forms = View.search([('model', '=', 'crm.lead'), ('type', '=', 'form')])
        for view in forms.filtered(lambda v: v.arch_db and '<form' in v.arch_db):
            if 'js_class="crm_lead_form"' in view.arch_db or "js_class='crm_lead_form'" in view.arch_db:
                continue
            arch = view.arch_db
            new_arch = re.sub(
                r'<form\b',
                '<form js_class="crm_lead_form"',
                arch,
                count=1,
                flags=re.IGNORECASE,
            )
            if new_arch != arch:
                view.write({'arch_db': new_arch})
                _logger.info('Added crm_lead_form js_class to view id=%s', view.id)
