from odoo import models, api, fields

class ResPartnerPatch(models.Model):
    _inherit = 'res.partner'

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        to_update = records.filtered(lambda r: r.is_company and not r.customer_rank)
        if to_update:
            to_update.write({'customer_rank': 1})
        return records

    @api.depends_context('partner_display_name_hide_company', 'show_equipment_serial')
    def _compute_display_name(self):
        show_serial = self.env.context.get('show_equipment_serial')
        hide_company = self.env.context.get('partner_display_name_hide_company')

        if not show_serial and not hide_company:
            return super()._compute_display_name()

        # If only hide_company is requested
        if hide_company and not show_serial:
            for partner in self:
                partner.display_name = partner.name or ''
            return

        # When show_equipment_serial is requested (Service Ticket wizard/views)
        Equip = self.env['equipment.master'].sudo()
        equipments = Equip.search([('partner_id', 'in', self.ids)])

        partner_equip_map = {}
        for eq in equipments:
            if eq.partner_id.id not in partner_equip_map:
                partner_equip_map[eq.partner_id.id] = []
            if eq.serial_number:
                sn = str(eq.serial_number).strip()
                last6 = sn[-6:] if len(sn) >= 6 else sn
                if last6 and last6 not in partner_equip_map[eq.partner_id.id]:
                    partner_equip_map[eq.partner_id.id].append(last6)

        for partner in self:
            base_name = partner.name or ''
            serials = partner_equip_map.get(partner.id, [])
            if serials:
                if len(serials) == 1:
                    partner.display_name = f"{base_name} ...{serials[0]}"
                else:
                    partner.display_name = f"{base_name} ...[{', '.join(serials)}]"
            else:
                partner.display_name = base_name

    @api.model
    def name_search(self, name='', domain=None, operator='ilike', limit=100):
        if not self.env.context.get('show_equipment_serial'):
            return super().name_search(name=name, domain=domain, operator=operator, limit=limit)

        partners = self.search(domain or [], limit=limit)
        return [(p.id, p.display_name) for p in partners if not name or name.lower() in (p.display_name or '').lower()]



class ResCompanyDefaultCard(models.Model):
    _inherit = 'res.company'
    x_default_signature_card = fields.Binary(string='Default Quotation Signature Card')

class ResUsersNotificationPatch(models.Model):
    _inherit = 'res.users'
    x_signature_card = fields.Binary(string='Quotation Signature Card')
    notification_type = fields.Selection(
        selection_add=[],
        selection=[
            ('email', 'By Email'),
            ('inbox', 'In System'),
        ]
    )
