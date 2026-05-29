# -*- coding: utf-8 -*-
import logging

from odoo import api, SUPERUSER_ID

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    env['crm.lead.view.patch'].ensure_assignment_priority_dropdown()
    env['ir.config_parameter'].sudo().set_param(
        'custom_crm_extended.priority_view_patch_version',
        '1.2.4',
    )
    _logger.info('CRM priority hide/dropdown patch applied (v1.2.4).')
