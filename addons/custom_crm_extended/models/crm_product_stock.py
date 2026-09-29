# -*- coding: utf-8 -*-
from odoo import models, fields, api

class CrmProductStock(models.Model):
    _name = 'crm.product.stock'
    _description = 'Product Stock Registry'
    _order = 'last_updated_date desc, id desc'

    product_id = fields.Many2one(
        'product.template',
        string='Product',
        required=True,
        ondelete='cascade',
        index=True
    )
    quantity = fields.Float(
        string='Quantity',
        default=0.0,
        required=True
    )
    last_updated_date = fields.Datetime(
        string='Last Updated',
        default=fields.Datetime.now,
        readonly=True
    )
    user_id = fields.Many2one(
        'res.users',
        string='Updated By',
        default=lambda self: self.env.user,
        readonly=True
    )

    _sql_constraints = [
        ('product_unique', 'unique(product_id)', 'This product already exists in the stock registry! Please update its quantity instead.')
    ]

    def write(self, vals):
        if 'quantity' in vals:
            vals['last_updated_date'] = fields.Datetime.now()
            vals['user_id'] = self.env.user.id
        return super().write(vals)

    def action_update_stock_wizard(self):
        """Opens wizard to update stock for this specific record."""
        return {
            'type': 'ir.actions.act_window',
            'name': 'Update Stock',
            'res_model': 'crm.product.stock.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_product_id': self.product_id.id,
                'default_quantity': self.quantity,
                'default_stock_id': self.id,
            }
        }


class CrmProductStockWizard(models.TransientModel):
    _name = 'crm.product.stock.wizard'
    _description = 'Update Product Stock Wizard'

    stock_id = fields.Many2one('crm.product.stock', string='Stock Record')
    product_id = fields.Many2one(
        'product.template',
        string='Product',
        required=True
    )
    quantity = fields.Float(
        string='Quantity',
        required=True,
        default=0.0
    )

    def action_save_stock(self):
        self.ensure_one()
        Stock = self.env['crm.product.stock']
        # Check if record already exists for this product
        existing = self.stock_id or Stock.search([('product_id', '=', self.product_id.id)], limit=1)
        if existing:
            existing.write({
                'quantity': self.quantity,
                'last_updated_date': fields.Datetime.now(),
                'user_id': self.env.user.id,
            })
        else:
            Stock.create({
                'product_id': self.product_id.id,
                'quantity': self.quantity,
                'last_updated_date': fields.Datetime.now(),
                'user_id': self.env.user.id,
            })
        return {'type': 'ir.actions.act_window_close'}
