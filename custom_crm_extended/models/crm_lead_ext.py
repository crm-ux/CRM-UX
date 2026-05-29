from odoo import models

class CrmLead(models.Model):
    _inherit = 'crm.lead'

    def action_save_and_go_list(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Pipeline',
            'res_model': 'crm.lead',
            'view_mode': 'list,form',
            'target': 'current',
            'context': self.env.context,
        }
