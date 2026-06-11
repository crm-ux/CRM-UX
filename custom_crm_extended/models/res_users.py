from odoo import models, api

class ResUsers(models.Model):
    _inherit = 'res.users'

    @api.model_create_multi
    def create(self, vals_list):
        users = super().create(vals_list)
        self._assign_default_groups(users)
        return users

    def _assign_default_groups(self, users):
        try:
            portal_group = self.env.ref('base.group_portal')
            public_group = self.env.ref('base.group_public')
            internal_group = self.env.ref('base.group_user')

            groups_to_add = [
                'sales_team.group_sale_salesman',
                'base.group_multi_company',
            ]
            all_companies = self.env['res.company'].sudo().search([])

            for user in users:
                # Skip portal and public users
                if portal_group in user.groups_id or public_group in user.groups_id:
                    continue
                # Only internal users
                if internal_group not in user.groups_id:
                    continue

                for group_ref in groups_to_add:
                    try:
                        group = self.env.ref(group_ref)
                        self.env.cr.execute(
                            "INSERT INTO res_groups_users_rel (gid, uid) VALUES (%s, %s) ON CONFLICT DO NOTHING",
                            (group.id, user.id)
                        )
                    except Exception:
                        pass

                # Assign all companies
                for company in all_companies:
                    self.env.cr.execute(
                        "INSERT INTO res_company_users_rel (cid, user_id) VALUES (%s, %s) ON CONFLICT DO NOTHING",
                        (company.id, user.id)
                    )
        except Exception:
            pass
