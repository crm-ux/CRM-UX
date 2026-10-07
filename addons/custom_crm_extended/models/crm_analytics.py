# -*- coding: utf-8 -*-
from datetime import datetime, date, timedelta
import calendar as _calendar
from odoo import api, fields, models, _


class DashboardStats(models.Model):
    _inherit = 'crm.lead'

    @api.model
    def get_dashboard_stats(self, user_id, is_admin, company_ids=None):
        """Return all dashboard stats in a single DB round-trip."""
        uid = user_id
        cr = self.env.cr

        # 1. Company filter: always allow unassigned/global records
        company_filter = ['|', ('company_id', '=', False), ('company_id', 'in', company_ids)] if company_ids else []
        shared_company_filter = company_filter

        # Auto-sync unlinked direct quotations into crm.lead so all quotes exist in the pipeline list view
        try:
            unlinked_quotes = self.env['sale.order'].sudo().search([
                ('opportunity_id', '=', False),
                ('state', '!=', 'cancel')
            ])
            for q in unlinked_quotes:
                lead_stage_seq = 90 if q.x_quote_stage == 'won' else 30
                lead_vals = {
                    'name': q.name or 'Direct Quotation',
                    'partner_id': q.partner_id.id if q.partner_id else False,
                    'user_id': q.user_id.id if q.user_id else False,
                    'company_id': q.company_id.id if q.company_id else False,
                    'expected_revenue': q.amount_total or 0.0,
                    'x_stage_sequence': lead_stage_seq,
                    'type': 'opportunity',
                }
                new_lead = self.env['crm.lead'].sudo().create(lead_vals)
                q.sudo().write({'opportunity_id': new_lead.id})
        except Exception:
            pass

        # 2. Hierarchy & Department filter
        target_user = self.env['res.users'].sudo().browse(uid)
        perm = target_user.perm_lead_quote or (target_user.crm_job_id.perm_lead_quote if target_user.crm_job_id else 'own')

        user_filter = []
        if not is_admin and not target_user._is_admin() and not target_user.has_group('base.group_system'):
            if perm in ('all', 'admin'):
                user_filter = []
            else:
                allowed_uids = target_user._get_accessible_user_ids('perm_lead_quote')
                # Strictly filter by assigned user_id (Salesperson) only
                user_filter = [('user_id', 'in', allowed_uids)]

        # Lead stage counts (evaluated with sudo to avoid double-filtering with ir.rule)
        lead_domain = [('active', '=', True)] + company_filter + user_filter
        leads = self.env['crm.lead'].sudo().read_group(
            lead_domain, ['x_stage_sequence', 'expected_revenue:sum'], ['x_stage_sequence'])
        lead_counts = {r['x_stage_sequence']: r['x_stage_sequence_count'] for r in leads}
        lead_values = {r['x_stage_sequence']: (r.get('expected_revenue') or 0.0) for r in leads}

        # Lead priority counts and values (strictly matching list view filter: [('x_lead_priority', '=', level)])
        lead_priority_domain = lead_domain + [('x_stage_sequence', '<', 30)]
        priority_counts = {'high': 0, 'medium': 0, 'low': 0}
        priority_values = {'high': 0.0, 'medium': 0.0, 'low': 0.0}
        p_leads = self.env['crm.lead'].sudo().search(lead_priority_domain)
        for pl in p_leads:
            p_level = pl.x_lead_priority
            if p_level in priority_counts:
                priority_counts[p_level] += 1
                # Revenue calculation: expected_revenue or fallback to order/products
                rev = pl.expected_revenue or 0.0
                if not rev and hasattr(pl, 'order_ids') and pl.order_ids:
                    rev = sum(pl.order_ids.filtered(lambda o: o.state != 'cancel').mapped('amount_total'))
                if not rev and hasattr(pl, 'lead_product_ids') and pl.lead_product_ids:
                    rev = sum(pl.lead_product_ids.mapped('x_subtotal') if hasattr(pl.lead_product_ids[0], 'x_subtotal') else [0.0])
                priority_values[p_level] += rev

        # Quote stage counts and values
        quote_domain = [('state', '!=', 'cancel')] + company_filter + user_filter
        quotes = self.env['sale.order'].sudo().read_group(quote_domain, ['x_quote_stage', 'amount_total:sum'], ['x_quote_stage'])
        quote_counts = {r['x_quote_stage']: r['x_quote_stage_count'] for r in quotes}
        quote_values = {r['x_quote_stage']: (r.get('amount_total') or 0.0) for r in quotes}

        # Revenue
        won_orders = self.env['sale.order'].sudo().search([
            ('x_quote_stage', '=', 'won'),
            ('amount_total', '>', 0)
        ] + company_filter + user_filter)
        won_revenue = sum(won_orders.mapped('amount_total'))

        # Check invoice date for Won orders & sum amounts
        invoice_created = 0
        invoice_created_val = 0.0
        invoice_pending = 0
        invoice_pending_val = 0.0
        for order in won_orders:
            inv_date = getattr(order, 'x_invoice_date', False) or getattr(order, 'invoice_date', False)
            amt = order.amount_total or 0.0
            if inv_date:
                invoice_created += 1
                invoice_created_val += amt
            else:
                invoice_pending += 1
                invoice_pending_val += amt

        pending_orders = self.env['sale.order'].sudo().search([
            ('x_quote_stage', 'not in', ['won', 'lost']),
            ('state', '!=', 'cancel')
        ] + company_filter + user_filter)
        quote_revenue = sum(pending_orders.mapped('amount_total'))
        today = date.today().strftime('%Y-%m-%d')
        today_orders = self.env['sale.order'].sudo().search([
            ('x_quote_stage', '=', 'won'),
            ('date_order', '>=', today + ' 00:00:00')
        ] + company_filter + user_filter)
        today_revenue = sum(today_orders.mapped('amount_total'))

        # Other counts
        customers = self.env['res.partner'].search_count([('customer_rank', '>', 0)] + shared_company_filter)
        products = self.env['product.template'].search_count([('sale_ok', '=', True)] + shared_company_filter)
        users = self.env['res.users'].search_count([('active', '=', True), ('share', '=', False)])
        exhibition = self.env['exhibition.contact'].search_count([])
        now = datetime.now()
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        last_day = _calendar.monthrange(now.year, now.month)[1]
        month_end = now.replace(day=last_day, hour=23, minute=59, second=59, microsecond=0)
        meetings_this_month = self.env['calendar.event'].search_count([
            ('start', '>=', month_start.strftime('%Y-%m-%d %H:%M:%S')),
            ('start', '<=', month_end.strftime('%Y-%m-%d %H:%M:%S')),
        ])
        upcoming_events = self.env['calendar.event'].search_count([
            ('start', '>=', now.strftime('%Y-%m-%d %H:%M:%S')),
            ('start', '<=', month_end.strftime('%Y-%m-%d %H:%M:%S')),
        ])

        # Hierarchy domains for Equipment, Service Ticket, AMC
        if not is_admin and not target_user._is_admin() and not target_user.has_group('base.group_system'):
            eq_filter = target_user._get_hierarchy_domain('perm_equipment', False)
            ticket_filter = target_user._get_hierarchy_domain('perm_service_ticket', 'engineer_id')
            amc_filter = target_user._get_hierarchy_domain('perm_amc', False)
        else:
            eq_filter = []
            ticket_filter = []
            amc_filter = []

        # Equipment counts: filtered by user's hierarchy (own, team, dept, all)
        equipment_counts = {
            'total': self.env['equipment.master'].sudo().search_count(shared_company_filter + eq_filter),
            'active': self.env['equipment.master'].sudo().search_count(shared_company_filter + eq_filter + [('equipment_status', '=', 'active')]),
            'inactive': self.env['equipment.master'].sudo().search_count(shared_company_filter + eq_filter + [('equipment_status', '=', 'inactive')]),
            'repair': self.env['equipment.master'].sudo().search_count(shared_company_filter + eq_filter + [('equipment_status', '=', 'under_repair')]),
        }

        # Service Ticket counts: filtered by user's hierarchy (own, team, dept, all)
        ticket_counts = {
            'total': self.env['service.ticket'].sudo().search_count(shared_company_filter + ticket_filter),
            'open': self.env['service.ticket'].sudo().search_count(shared_company_filter + ticket_filter + [('ticket_status', '=', 'open')]),
            'ongoing': self.env['service.ticket'].sudo().search_count(shared_company_filter + ticket_filter + [('ticket_status', '=', 'ongoing')]),
            'closed': self.env['service.ticket'].sudo().search_count(shared_company_filter + ticket_filter + [('ticket_status', '=', 'closed')]),
        }

        # Complaint Type Breakdown counts
        complaint_counts = {
            'breakdown': self.env['service.ticket'].sudo().search_count(shared_company_filter + ticket_filter + [('complaint_type', '=', 'breakdown')]),
            'pm': self.env['service.ticket'].sudo().search_count(shared_company_filter + ticket_filter + [('complaint_type', '=', 'pm')]),
            'free_call': self.env['service.ticket'].sudo().search_count(shared_company_filter + ticket_filter + [('complaint_type', '=', 'free_call')]),
        }

        # AMC Contract counts: filtered by user's hierarchy (own, team, dept, all)
        amc_counts = {
            'total': self.env['amc.contract'].sudo().search_count(shared_company_filter + amc_filter),
            'draft': self.env['amc.contract'].sudo().search_count(shared_company_filter + amc_filter + [('contract_status', '=', 'draft')]),
            'active': self.env['amc.contract'].sudo().search_count(shared_company_filter + amc_filter + [('contract_status', '=', 'active')]),
            'expired': self.env['amc.contract'].sudo().search_count(shared_company_filter + amc_filter + [('contract_status', '=', 'expired')]),
        }

        # AMC Renewals timeline calculation (Next 90 Days)
        d_today = date.today()
        d_30 = d_today + timedelta(days=30)
        d_60 = d_today + timedelta(days=60)

        active_amcs = self.env['amc.contract'].sudo().search(shared_company_filter + amc_filter + [('contract_status', 'in', ['active', 'renewed', 'expired'])])
        expired_count = 0
        expired_val = 0.0
        expiring_30 = 0
        expiring_30_val = 0.0
        expiring_60 = 0
        expiring_60_val = 0.0
        secure = 0
        secure_val = 0.0

        for a in active_amcs:
            try:
                raw_val = (a.contract_value or '0').replace(',', '').replace('₹', '').strip()
                c_val = float(raw_val) if raw_val else 0.0
            except Exception:
                c_val = 0.0

            end_dt = a.contract_end_date
            if a.contract_status == 'expired' or (end_dt and end_dt < d_today):
                expired_count += 1
                expired_val += c_val
            elif end_dt:
                if d_today <= end_dt <= d_30:
                    expiring_30 += 1
                    expiring_30_val += c_val
                elif d_30 < end_dt <= d_60:
                    expiring_60 += 1
                    expiring_60_val += c_val
                elif end_dt > d_60:
                    secure += 1
                    secure_val += c_val
            else:
                secure += 1
                secure_val += c_val

        amc_renewals = {
            'expired': expired_count,
            'expired_val': expired_val,
            'expiring_30': expiring_30,
            'expiring_30_val': expiring_30_val,
            'expiring_60': expiring_60,
            'expiring_60_val': expiring_60_val,
            'secure': secure,
            'secure_val': secure_val,
        }

        # Low Stock & Out of Stock from crm.product.stock
        out_of_stock_count = self.env['crm.product.stock'].sudo().search_count([('stock_status', '=', 'out_of_stock')])
        low_stock_count = self.env['crm.product.stock'].sudo().search_count([('stock_status', '=', 'low_stock')])
        total_registered_stock = self.env['crm.product.stock'].sudo().search_count([])

        # Top 3 low stock records (ordered by lowest percentage ratio: quantity / safety_stock)
        all_low_stock = self.env['crm.product.stock'].sudo().search([('stock_status', '=', 'low_stock')])
        # Calculate percentage ratio for each, sort lowest ratio first, then pick top 3
        sorted_low = sorted(
            all_low_stock,
            key=lambda r: (
                (r.quantity / r.safety_stock) if r.safety_stock > 0 else 1.0,
                r.quantity,
                r.id
            )
        )[:3]

        low_stock_items = []
        for r in sorted_low:
            low_stock_items.append({
                'id': r.id,
                'product_id': r.product_id.id,
                'display_name': r.product_id.display_name or r.product_id.name or 'Product',
                'quantity': r.quantity,
                'safety_stock': r.safety_stock,
                'stock_label': f"{r.quantity:g} / {r.safety_stock:g} Units" if r.safety_stock > 0 else f"{r.quantity:g} Units",
                'stock_status': r.stock_status,
            })

        # Equipment values (summing list_price of linked product model)
        equipment_values = {'total': 0.0, 'active': 0.0, 'inactive': 0.0, 'repair': 0.0}
        all_user_eqs = self.env['equipment.master'].sudo().search(shared_company_filter + eq_filter)
        for eq in all_user_eqs:
            eq_val = eq.name.list_price if eq.name else 0.0
            equipment_values['total'] += eq_val
            st = eq.equipment_status or 'active'
            if st == 'under_repair':
                equipment_values['repair'] += eq_val
            elif st in equipment_values:
                equipment_values[st] += eq_val

        # Service Ticket voucher expense values (summing service.ticket.voucher.line amount)
        ticket_values = {'total': 0.0, 'open': 0.0, 'ongoing': 0.0, 'closed': 0.0}
        all_user_tickets = self.env['service.ticket'].sudo().search(shared_company_filter + ticket_filter)
        for t in all_user_tickets:
            t_val = sum(t.voucher_line_ids.mapped('amount')) or 0.0
            ticket_values['total'] += t_val
            st = t.ticket_status or 'new'
            if st in ('new', 'contacted', 'open'):
                ticket_values['open'] += t_val
            elif st in ('ongoing', 'pending'):
                ticket_values['ongoing'] += t_val
            elif st == 'closed':
                ticket_values['closed'] += t_val

        # Product Stock total inventory valuation
        stock_total_val = 0.0
        all_user_stocks = self.env['crm.product.stock'].sudo().search([])
        for srec in all_user_stocks:
            stock_total_val += (srec.quantity or 0.0) * (srec.product_id.list_price or 0.0)

        # AMC Contract status values (summing contract_value for total, draft, active, expired)
        amc_values = {'total': 0.0, 'draft': 0.0, 'active': 0.0, 'expired': 0.0}
        all_user_amcs = self.env['amc.contract'].sudo().search(shared_company_filter + amc_filter)
        for a in all_user_amcs:
            try:
                raw_cval = (a.contract_value or '0').replace(',', '').replace('₹', '').strip()
                c_num = float(raw_cval) if raw_cval else 0.0
            except Exception:
                c_num = 0.0
            amc_values['total'] += c_num
            st = a.contract_status or 'draft'
            if st in amc_values:
                amc_values[st] += c_num

        return {
            'lead_counts': lead_counts,
            'lead_values': lead_values,
            'quote_counts': quote_counts,
            'quote_values': quote_values,
            'won_revenue': won_revenue,
            'quote_revenue': quote_revenue,
            'today_revenue': today_revenue,
            'customers': customers,
            'products': products,
            'users': users,
            'exhibition': exhibition,
            'priority_counts': priority_counts,
            'priority_values': priority_values,
            'meetings_this_month': meetings_this_month,
            'upcoming_events': upcoming_events,
            'invoice_created': invoice_created,
            'invoice_created_val': invoice_created_val,
            'invoice_pending': invoice_pending,
            'invoice_pending_val': invoice_pending_val,
            'equipment_counts': equipment_counts,
            'equipment_values': equipment_values,
            'ticket_counts': ticket_counts,
            'ticket_values': ticket_values,
            'stock_total_val': stock_total_val,
            'amc_counts': amc_counts,
            'amc_values': amc_values,
            'complaint_counts': complaint_counts,
            'amc_renewals': amc_renewals,
            'low_stock_items': low_stock_items,
            'out_of_stock_count': out_of_stock_count,
            'low_stock_count': low_stock_count,
            'total_registered_stock': total_registered_stock,
            'permissions': {
                'product_read': bool(
                    target_user.perm_product_read or target_user.perm_product_write or target_user.perm_product_create or
                    (target_user.crm_job_id and (target_user.crm_job_id.perm_product_read or target_user.crm_job_id.perm_product_write or target_user.crm_job_id.perm_product_create)) or
                    target_user._is_admin() or target_user.has_group('base.group_system')
                ),
                'customer_read': bool(
                    target_user.perm_customer_read or target_user.perm_customer_write or target_user.perm_customer_create or
                    (target_user.crm_job_id and (target_user.crm_job_id.perm_customer_read or target_user.crm_job_id.perm_customer_write or target_user.crm_job_id.perm_customer_create)) or
                    target_user._is_admin() or target_user.has_group('base.group_system')
                ),
                'lead_quote_read': bool(
                    target_user._is_admin() or target_user.has_group('base.group_system') or (
                        target_user.perm_lead_quote not in ('none', False) if target_user.perm_lead_quote
                        else (target_user.crm_job_id and target_user.crm_job_id.perm_lead_quote and target_user.crm_job_id.perm_lead_quote != 'none')
                    )
                ),
                'equipment_read': bool(
                    target_user._is_admin() or target_user.has_group('base.group_system') or (
                        (target_user.perm_equipment not in ('none', False) and target_user.perm_equipment_read) if target_user.perm_equipment
                        else (target_user.crm_job_id and target_user.crm_job_id.perm_equipment not in ('none', False) and target_user.crm_job_id.perm_equipment_read)
                    )
                ),
                'ticket_read': bool(
                    target_user._is_admin() or target_user.has_group('base.group_system') or (
                        (target_user.perm_service_ticket not in ('none', False) and target_user.perm_ticket_read) if target_user.perm_service_ticket
                        else (target_user.crm_job_id and target_user.crm_job_id.perm_service_ticket not in ('none', False) and target_user.crm_job_id.perm_ticket_read)
                    )
                ),
                'amc_read': bool(
                    target_user._is_admin() or target_user.has_group('base.group_system') or (
                        (target_user.perm_amc not in ('none', False) and target_user.perm_amc_read) if target_user.perm_amc
                        else (target_user.crm_job_id and target_user.crm_job_id.perm_amc not in ('none', False) and target_user.crm_job_id.perm_amc_read)
                    )
                ),
                'can_create_company': bool(
                    target_user._is_admin() or target_user.has_group('base.group_system') or (
                        target_user.perm_company == 'create' if target_user.perm_company in ('create', 'none')
                        else (target_user.crm_job_id and target_user.crm_job_id.perm_company == 'create')
                    )
                ),
                'can_export': bool(
                    target_user._is_admin() or target_user.has_group('base.group_system') or (
                        target_user.perm_export == 'export' if target_user.perm_export in ('export', 'none')
                        else (target_user.crm_job_id and target_user.crm_job_id.perm_export == 'export')
                    )
                ),
                'is_manager': bool(
                    target_user.crm_subordinate_ids or
                    target_user.perm_lead_quote in ('subordinates', 'department', 'all', 'admin') or
                    target_user.perm_equipment in ('subordinates', 'department', 'all', 'admin') or
                    (target_user.crm_job_id and (
                        target_user.crm_job_id.perm_lead_quote in ('subordinates', 'department', 'all', 'admin') or
                        target_user.crm_job_id.perm_equipment in ('subordinates', 'department', 'all', 'admin')
                    )) or
                    target_user._is_admin() or target_user.has_group('base.group_system')
                ),
                'scope_lead_quote': target_user.perm_lead_quote or (target_user.crm_job_id.perm_lead_quote if target_user.crm_job_id else 'own'),
                'scope_equipment': target_user.perm_equipment or (target_user.crm_job_id.perm_equipment if target_user.crm_job_id else 'own'),
                'scope_service_ticket': target_user.perm_service_ticket or (target_user.crm_job_id.perm_service_ticket if target_user.crm_job_id else 'own'),
                'scope_amc': target_user.perm_amc or (target_user.crm_job_id.perm_amc if target_user.crm_job_id else 'own'),
            },
            'accessible_uids': target_user._get_accessible_user_ids('perm_equipment') if (target_user.perm_equipment not in ('all', 'admin')) else [],
            'lead_uids': target_user._get_accessible_user_ids('perm_lead_quote') if ((target_user.perm_lead_quote or (target_user.crm_job_id.perm_lead_quote if target_user.crm_job_id else 'own')) not in ('all', 'admin')) else [],
            'eq_uids': target_user._get_accessible_user_ids('perm_equipment') if ((target_user.perm_equipment or (target_user.crm_job_id.perm_equipment if target_user.crm_job_id else 'own')) not in ('all', 'admin')) else [],
            'ticket_uids': target_user._get_accessible_user_ids('perm_service_ticket') if ((target_user.perm_service_ticket or (target_user.crm_job_id.perm_service_ticket if target_user.crm_job_id else 'own')) not in ('all', 'admin')) else [],
            'amc_uids': target_user._get_accessible_user_ids('perm_amc') if ((target_user.perm_amc or (target_user.crm_job_id.perm_amc if target_user.crm_job_id else 'own')) not in ('all', 'admin')) else [],
        }

    @api.model
    def get_customer_classification_stats(self, user_id=None, is_admin=False, company_ids=None):
        """Return customer classification analytics strictly respecting company and user permissions / View As."""
        uid = user_id or self.env.uid
        target_user = self.env['res.users'].sudo().browse(uid)

        # 1. Company filter (always allow unassigned / global records)
        company_filter = ['|', ('company_id', '=', False), ('company_id', 'in', company_ids)] if company_ids else []

        # 2. User permissions filter (View As / Rep vs Admin)
        user_filter = []
        is_user_admin = bool(is_admin) or (not user_id and (target_user._is_admin() or target_user.has_group('base.group_system')))
        if not is_user_admin:
            perm = target_user.perm_lead_quote or (target_user.crm_job_id.perm_lead_quote if target_user.crm_job_id else 'own')
            if perm not in ('all', 'admin'):
                allowed_uids = target_user._get_accessible_user_ids('perm_lead_quote')
                user_filter = [('user_id', 'in', allowed_uids)]

        # 3. Query leads
        lead_domain = [('active', '=', True)] + company_filter + user_filter
        leads = self.env['crm.lead'].sudo().search_read(
            lead_domain, ['id', 'x_customer_type']
        )

        total_pipeline = len(leads)
        unclassified_count = 0
        quad_counts = {
            'existing_existing': 0,
            'existing_new': 0,
            'new_existing': 0,
            'new_new': 0,
        }
        lead_type_map = {}
        for l in leads:
            ctype = l.get('x_customer_type')
            if not ctype:
                unclassified_count += 1
            elif ctype in quad_counts:
                quad_counts[ctype] += 1
                lead_type_map[l['id']] = ctype

        classified_count = total_pipeline - unclassified_count

        # 4. Query Won Orders strictly matching company and user permissions
        order_domain = [
            ('x_quote_stage', '=', 'won'),
            ('amount_total', '>', 0),
            ('state', '!=', 'cancel'),
        ] + company_filter + user_filter
        won_orders = self.env['sale.order'].sudo().search_read(
            order_domain, ['id', 'amount_total', 'opportunity_id']
        )

        total_won_val = 0.0
        quad_won = {
            'existing_existing': 0.0,
            'existing_new': 0.0,
            'new_existing': 0.0,
            'new_new': 0.0,
        }
        for o in won_orders:
            amt = o.get('amount_total') or 0.0
            total_won_val += amt
            opp = o.get('opportunity_id')
            opp_id = opp[0] if opp else False
            if opp_id and opp_id in lead_type_map:
                ctype = lead_type_map[opp_id]
                quad_won[ctype] += amt

        return {
            'total_pipeline': total_pipeline,
            'classified_count': classified_count,
            'unclassified_count': unclassified_count,
            'total_won_val': total_won_val,
            'counts': quad_counts,
            'won_values': quad_won,
            'user_filter_applied': bool(user_filter),
            'allowed_uids': user_filter[0][2] if user_filter else [],
        }

    @api.model
    def get_quote_discount_analytics(self, user_id=None, is_admin=False, company_ids=None):
        """Return Quote Pricing & Discount Impact analytics strictly respecting company, permissions and View As."""
        uid = user_id or self.env.uid
        target_user = self.env['res.users'].sudo().browse(uid)

        # 1. Company filter
        company_filter = ['|', ('company_id', '=', False), ('company_id', 'in', company_ids)] if company_ids else []

        # 2. User permissions filter
        user_filter = []
        is_user_admin = bool(is_admin) or (not user_id and (target_user._is_admin() or target_user.has_group('base.group_system')))
        if not is_user_admin:
            perm = target_user.perm_lead_quote or (target_user.crm_job_id.perm_lead_quote if target_user.crm_job_id else 'own')
            if perm not in ('all', 'admin'):
                allowed_uids = target_user._get_accessible_user_ids('perm_lead_quote')
                user_filter = [('user_id', 'in', allowed_uids)]

        # 3. Query quotes linked to active pipeline deals (last 5 stages: Quotes, Sent, Negotiation, Order Expected, Won)
        quote_domain = [
            ('state', '!=', 'cancel'),
            ('opportunity_id', '!=', False),
            ('opportunity_id.active', '=', True),
            ('x_quote_stage', 'in', ['draft', 'sent', 'negotiation', 'order_expected', 'won']),
        ] + company_filter + user_filter

        raw_quotes = self.env['sale.order'].sudo().search_read(
            quote_domain,
            ['id', 'opportunity_id', 'amount_total', 'amount_untaxed', 'x_flat_discount_pct', 'x_flat_discount', 'x_amount_after_discount', 'x_quote_stage', 'x_quote_version', 'write_date'],
            order='write_date desc, id desc'
        )

        # Pick only ONE final quotation per deal (opportunity)
        # Priority: 'won' quote first, otherwise latest revised/written quote
        opp_quote_map = {}
        for q in raw_quotes:
            opp = q.get('opportunity_id')
            opp_id = opp[0] if opp else False
            if not opp_id:
                continue
            if opp_id not in opp_quote_map:
                opp_quote_map[opp_id] = q
            else:
                existing = opp_quote_map[opp_id]
                # If current quote is 'won' and existing is not, prefer the won quote
                if q.get('x_quote_stage') == 'won' and existing.get('x_quote_stage') != 'won':
                    opp_quote_map[opp_id] = q
                elif existing.get('x_quote_stage') != 'won':
                    # Prefer higher quote version
                    q_ver = q.get('x_quote_version') or 1
                    ex_ver = existing.get('x_quote_version') or 1
                    if q_ver > ex_ver:
                        opp_quote_map[opp_id] = q

        quotes = list(opp_quote_map.values())
        final_quote_ids = [q['id'] for q in quotes]

        total_quotes = len(quotes)
        total_discount_amount = 0.0
        total_quote_value = 0.0
        discounted_quotes_count = 0

        tiers = {
            'full_price': {'count': 0, 'value': 0.0, 'discount': 0.0, 'pct': 0, 'ids': []},
            'small_disc': {'count': 0, 'value': 0.0, 'discount': 0.0, 'pct': 0, 'ids': []},
            'med_disc':   {'count': 0, 'value': 0.0, 'discount': 0.0, 'pct': 0, 'ids': []},
            'heavy_disc': {'count': 0, 'value': 0.0, 'discount': 0.0, 'pct': 0, 'ids': []},
        }

        for q in quotes:
            val = q.get('amount_total') or 0.0
            untaxed = q.get('amount_untaxed') or val
            disc_pct = float(q.get('x_flat_discount_pct') or 0.0)
            flat_disc = float(q.get('x_flat_discount') or 0.0)
            stored_disc = float(q.get('x_amount_after_discount') or 0.0)

            # Compute actual discount amount
            disc_amount = 0.0
            if flat_disc > 0:
                disc_amount = flat_disc
            elif stored_disc > 0 and disc_pct > 0:
                disc_amount = stored_disc
            elif disc_pct > 0:
                disc_amount = untaxed * (disc_pct / 100.0)

            total_quote_value += val
            total_discount_amount += disc_amount

            # Classify into 4 tiers
            if disc_pct <= 0.0 and flat_disc <= 0.0:
                tiers['full_price']['count'] += 1
                tiers['full_price']['value'] += val
                tiers['full_price']['ids'].append(q['id'])
            elif disc_pct <= 5.0 or (disc_pct == 0.0 and flat_disc > 0 and (val > 0 and (flat_disc / val) <= 0.05)):
                tiers['small_disc']['count'] += 1
                tiers['small_disc']['value'] += val
                tiers['small_disc']['discount'] += disc_amount
                tiers['small_disc']['ids'].append(q['id'])
                discounted_quotes_count += 1
            elif disc_pct <= 10.0 or (disc_pct == 0.0 and flat_disc > 0 and (val > 0 and (flat_disc / val) <= 0.10)):
                tiers['med_disc']['count'] += 1
                tiers['med_disc']['value'] += val
                tiers['med_disc']['discount'] += disc_amount
                tiers['med_disc']['ids'].append(q['id'])
                discounted_quotes_count += 1
            else:
                tiers['heavy_disc']['count'] += 1
                tiers['heavy_disc']['value'] += val
                tiers['heavy_disc']['discount'] += disc_amount
                tiers['heavy_disc']['ids'].append(q['id'])
                discounted_quotes_count += 1

        # Compute percentages for segmented meter
        if total_quotes > 0:
            tiers['full_price']['pct'] = round((tiers['full_price']['count'] / float(total_quotes)) * 100, 1)
            tiers['small_disc']['pct'] = round((tiers['small_disc']['count'] / float(total_quotes)) * 100, 1)
            tiers['med_disc']['pct'] = round((tiers['med_disc']['count'] / float(total_quotes)) * 100, 1)
            tiers['heavy_disc']['pct'] = round((tiers['heavy_disc']['count'] / float(total_quotes)) * 100, 1)

        return {
            'total_quotes': total_quotes,
            'total_quote_value': total_quote_value,
            'total_discount_amount': total_discount_amount,
            'discounted_quotes_count': discounted_quotes_count,
            'tiers': tiers,
            'final_quote_ids': final_quote_ids,
            'allowed_uids': user_filter[0][2] if user_filter else [],
            'user_filter_applied': bool(user_filter),
        }
