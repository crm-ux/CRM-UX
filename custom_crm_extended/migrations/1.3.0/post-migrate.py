# -*- coding: utf-8 -*-
import logging

from odoo import api, SUPERUSER_ID

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    View = env['ir.ui.view'].sudo()
    broken = View.search([
        ('model', '=', 'crm.lead'),
        ('name', 'in', [
            'crm.lead.form.hide.default.priority.fix',
            'crm.lead.form.priority.dropdown.fix',
        ]),
    ])
    if broken:
        broken.unlink()
    _logger.info('custom_crm_extended 1.3.0 migration complete.')
