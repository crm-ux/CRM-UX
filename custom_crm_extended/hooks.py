# -*- coding: utf-8 -*-
from .models.crm_lead_view_patch import CONFIG_KEY, PATCH_VERSION


def post_init_hook(env):
    env['crm.lead.view.patch'].ensure_assignment_priority_dropdown()
    env['ir.config_parameter'].sudo().set_param(CONFIG_KEY, PATCH_VERSION)
