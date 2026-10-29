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
        rec = self[:1]
        if hasattr(rec, 'user_id') and rec.user_id and rec.user_id[:1].id != 1:
            return rec.user_id[:1]
        if hasattr(rec, 'create_uid') and rec.create_uid and rec.create_uid[:1].id != 1:
            return rec.create_uid[:1]
        if hasattr(rec, 'x_created_by_id') and rec.x_created_by_id and rec.x_created_by_id[:1].id != 1:
            return rec.x_created_by_id[:1]
        if hasattr(rec, 'assigned_user_id') and rec.assigned_user_id and rec.assigned_user_id[:1].id != 1:
            return rec.assigned_user_id[:1]
        if hasattr(rec, 'salesperson_id') and rec.salesperson_id and rec.salesperson_id[:1].id != 1:
            return rec.salesperson_id[:1]
        return False

    def write(self, vals):
        # If execution is by system user 1 (cron, background upgrade, mail automation),
        # prevent overwriting the real human user who modified this record.
        if self.env.uid == 1 and ('write_uid' not in vals):
            human_user = self._get_real_human_user()
            if human_user:
                vals['write_uid'] = human_user.id
        return super().write(vals)

