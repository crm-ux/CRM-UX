# -*- coding: utf-8 -*-
from odoo import models, api

class GlobalAuditTrailPatch(models.AbstractModel):
    _inherit = 'base'

    @api.model
    def _get_real_human_user(self):
        """Find the real employee/user associated with the current record or context."""
        # 1. If currently executed by a human user, return that user
        if self.env.user and self.env.user.id != 1:
            return self.env.user

        # 2. If executed under system/bot (uid=1), resolve to the real human owner/creator of this record
        if hasattr(self, 'user_id') and self.user_id and self.user_id.id != 1:
            return self.user_id
        if hasattr(self, 'create_uid') and self.create_uid and self.create_uid.id != 1:
            return self.create_uid
        if hasattr(self, 'x_created_by_id') and self.x_created_by_id and self.x_created_by_id.id != 1:
            return self.x_created_by_id
        if hasattr(self, 'assigned_user_id') and self.assigned_user_id and self.assigned_user_id.id != 1:
            return self.assigned_user_id
        if hasattr(self, 'salesperson_id') and self.salesperson_id and self.salesperson_id.id != 1:
            return self.salesperson_id
        return False

    def write(self, vals):
        # If execution is by system user 1 (cron, background upgrade, mail automation),
        # prevent overwriting the real human user who modified this record.
        if self.env.uid == 1 and ('write_uid' not in vals):
            human_user = self._get_real_human_user()
            if human_user:
                vals['write_uid'] = human_user.id
        return super().write(vals)

