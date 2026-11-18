from lxml import etree
from odoo import fields, models, api, _
from odoo.exceptions import UserError

class ResPartner(models.Model):
    _inherit = 'res.partner'

    x_site_name = fields.Char(string='Site Name')
    x_building = fields.Char(string='Building')
    x_floor = fields.Char(string='Floor')
    x_department = fields.Char(string='Department')
    x_room_number = fields.Char(string='Room Number')


    @api.model
    def _user_can(self, perm_name, default=False):
        user = self.env.user
        if user._is_admin() or user.has_group('base.group_system'):
            return True
        if user.custom_perm_override:
            val = getattr(user, perm_name, None)
            return bool(val if val is not None else default)
        if user.crm_job_id and hasattr(user.crm_job_id, perm_name):
            return bool(getattr(user.crm_job_id, perm_name))
        val = getattr(user, perm_name, None)
        return bool(val if val is not None else default)

    @api.model
    def get_views(self, views, options=None):
        res = super(ResPartner, self).get_views(views, options=options)
        user = self.env.user
        if not user._is_admin() and not user.has_group('base.group_system'):
            can_create = self._user_can('perm_customer_create', False)
            can_write = self._user_can('perm_customer_write', False)
            can_delete = self._user_can('perm_customer_unlink', False)

            for vtype in ['form', 'list', 'tree', 'kanban']:
                if vtype in res.get('views', {}):
                    arch_str = res['views'][vtype].get('arch')
                    if arch_str:
                        doc = etree.fromstring(arch_str)
                        if not can_create:
                            doc.attrib['create'] = 'false'
                        if not can_write:
                            doc.attrib['edit'] = 'false'
                        if not can_delete:
                            doc.attrib['delete'] = 'false'
                        res['views'][vtype]['arch'] = etree.tostring(doc, encoding='unicode')
        return res

    @api.model
    def check_access_rights(self, operation, raise_exception=True):
        user = self.env.user
        # Strict permission check ONLY applies when directly interacting with Customer management, not when referenced by Lead, Quote, Equipment, Ticket, AMC
        active_model = self.env.context.get('active_model') or self.env.context.get('params', {}).get('model')
        if active_model and active_model != 'res.partner':
            return super(ResPartner, self).check_access_rights(operation, raise_exception=raise_exception)

        if not user._is_admin() and not user.has_group('base.group_system'):
            if operation == 'create' and not self._user_can('perm_customer_create', False):
                if raise_exception:
                    raise UserError(_("Access Denied: You do not have permission to create Customer / Contact records."))
                return False
            if operation == 'write' and not self._user_can('perm_customer_write', False):
                if raise_exception:
                    raise UserError(_("Access Denied: You do not have permission to update Customer / Contact records."))
                return False
            if operation == 'unlink' and not self._user_can('perm_customer_unlink', False):
                if raise_exception:
                    raise UserError(_("Access Denied: You do not have permission to delete Customer / Contact records."))
                return False
        return super(ResPartner, self).check_access_rights(operation, raise_exception=raise_exception)

    @api.model_create_multi
    def create(self, vals_list):
        user = self.env.user
        active_model = self.env.context.get('active_model') or self.env.context.get('params', {}).get('model')
        # Only block direct customer creation from customer menu
        if (not active_model or active_model == 'res.partner') and not user._is_admin() and not user.has_group('base.group_system'):
            if not self._user_can('perm_customer_create', False):
                raise UserError(_("Access Denied: You do not have permission to create Customer / Contact records."))
        return super(ResPartner, self).create(vals_list)

    def write(self, vals):
        user = self.env.user
        active_model = self.env.context.get('active_model') or self.env.context.get('params', {}).get('model')
        # Only block direct customer edits from customer menu
        if (not active_model or active_model == 'res.partner') and not user._is_admin() and not user.has_group('base.group_system'):
            other_partners = self.filtered(lambda p: p.id != user.partner_id.id)
            if other_partners and not self._user_can('perm_customer_write', False):
                raise UserError(_("Access Denied: You do not have permission to update Customer / Contact records."))
        return super(ResPartner, self).write(vals)

    def unlink(self):
        for rec in self:
            partner_ids = [rec.id] + rec.child_ids.ids
            associations = []

            # 1. Lead / Opportunity
            if 'crm.lead' in self.env:
                lead = self.env['crm.lead'].sudo().search([('partner_id', 'in', partner_ids)], limit=1)
                if lead:
                    associations.append(_("• Lead \"%(name)s\"") % {'name': lead.name or lead.display_name})

            # 2. Sales Order / Quotation
            if 'sale.order' in self.env:
                so = self.env['sale.order'].sudo().search([('partner_id', 'in', partner_ids)], limit=1)
                if so:
                    associations.append(_("• Sales Order \"%(name)s\"") % {'name': so.name or so.display_name})

            # 3. Service Ticket
            if 'service.ticket' in self.env:
                ticket_domain = [('partner_id', 'in', partner_ids)] if 'partner_id' in self.env['service.ticket']._fields else []
                if ticket_domain:
                    ticket = self.env['service.ticket'].sudo().search(ticket_domain, limit=1)
                    if ticket:
                        associations.append(_("• Service Ticket \"%(name)s\"") % {'name': ticket.name or ticket.display_name})

            # 4. Invoice / Bill
            if 'account.move' in self.env:
                move = self.env['account.move'].sudo().search([('partner_id', 'in', partner_ids)], limit=1)
                if move:
                    associations.append(_("• Invoice / Bill \"%(name)s\"") % {'name': move.name or move.display_name})

            if associations:
                assoc_text = "\n".join(associations)
                raise UserError(_(
                    "You cannot delete '%(contact)s' because it is associated with:\n\n"
                    "%(assoc_text)s\n\n"
                    "Please archive the record instead, or remove this contact from the above record(s) first."
                ) % {
                    'contact': rec.name or 'this contact',
                    'assoc_text': assoc_text,
                })

            user = self.env.user
            if not user._is_admin() and not user.has_group('base.group_system'):
                if not self._user_can('perm_customer_unlink', False):
                    raise UserError(_("Access Denied: You do not have permission to delete Customer / Contact records."))
        return super(ResPartner, self).unlink()
