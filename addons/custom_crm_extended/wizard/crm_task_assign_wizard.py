# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError
from dateutil.relativedelta import relativedelta

class CrmTaskAssignWizard(models.TransientModel):
    _name = 'crm.task.assign.wizard'
    _description = 'Assign Work Wizard'

    assigned_to_id = fields.Many2one('res.users', string='Assign To', required=True)
    name = fields.Char(string='Task Title', required=True)
    date_deadline = fields.Date(string='Deadline')
    instructions = fields.Text(string='Work Details / Instructions')
    attachment_name = fields.Char(string='Attachment Name')
    attachment_file = fields.Binary(string='Attachment', attachment=True)
    attachment_ids = fields.Many2many('ir.attachment', string='Attachments')
    wizard_attachment_ids = fields.One2many(
        'crm.task.assign.wizard.attachment',
        'wizard_id',
        string='Attachments'
    )

    # Company (Optional)
    company_id = fields.Many2one('res.company', string='Company')

    # Entity Linking (Optional)
    related_model = fields.Selection([
        ('crm.lead', 'Lead / Opportunity'),
        ('sale.order', 'Quotation / Sale Order'),
        ('res.partner', 'Customer / Contact'),
        ('equipment.master', 'Equipment Master'),
        ('service.ticket', 'Service Ticket'),
        ('amc.contract', 'AMC Contract'),
    ], string='Related Entity')

    lead_id = fields.Many2one('crm.lead', string='Linked Lead')
    order_id = fields.Many2one('sale.order', string='Linked Quotation')
    partner_id = fields.Many2one('res.partner', string='Linked Customer')
    equipment_id = fields.Many2one('equipment.master', string='Linked Equipment')
    ticket_id = fields.Many2one('service.ticket', string='Linked Service Ticket')
    amc_id = fields.Many2one('amc.contract', string='Linked AMC Contract')

    # Dynamic Allowed Domains for Security Isolation
    allowed_user_ids = fields.Many2many('res.users', compute='_compute_accessible_records', string='Allowed Assignees')
    allowed_lead_ids = fields.Many2many('crm.lead', compute='_compute_accessible_records', string='Allowed Leads')
    allowed_order_ids = fields.Many2many('sale.order', compute='_compute_accessible_records', string='Allowed Orders')
    allowed_partner_ids = fields.Many2many('res.partner', compute='_compute_accessible_records', string='Allowed Partners')
    allowed_equipment_ids = fields.Many2many('equipment.master', compute='_compute_accessible_records', string='Allowed Equipment')
    allowed_ticket_ids = fields.Many2many('service.ticket', compute='_compute_accessible_records', string='Allowed Tickets')
    allowed_amc_ids = fields.Many2many('amc.contract', compute='_compute_accessible_records', string='Allowed AMC')

    @api.depends('assigned_to_id', 'related_model', 'lead_id', 'order_id', 'partner_id', 'equipment_id', 'ticket_id', 'amc_id')
    def _compute_accessible_records(self):
        for wiz in self:
            all_users = self.env['res.users'].sudo().search([('active', '=', True), ('share', '=', False)])

            # -------------------------------------------------------------
            # Case 2: Record is pre-filled/selected -> Filter Employees who have access
            # -------------------------------------------------------------
            rec = False
            perm_field = 'perm_lead_quote'
            if wiz.related_model == 'crm.lead' and wiz.lead_id:
                rec = wiz.lead_id
                perm_field = 'perm_lead_quote'
            elif wiz.related_model == 'sale.order' and wiz.order_id:
                rec = wiz.order_id
                perm_field = 'perm_lead_quote'
            elif wiz.related_model == 'res.partner' and wiz.partner_id:
                rec = wiz.partner_id
                perm_field = 'perm_customer'
            elif wiz.related_model == 'equipment.master' and wiz.equipment_id:
                rec = wiz.equipment_id
                perm_field = 'perm_equipment'
            elif wiz.related_model == 'service.ticket' and wiz.ticket_id:
                rec = wiz.ticket_id
                perm_field = 'perm_service_ticket'
            elif wiz.related_model == 'amc.contract' and wiz.amc_id:
                rec = wiz.amc_id
                perm_field = 'perm_amc'

            if rec:
                valid_uids = []
                for u in all_users:
                    if u._is_admin() or u.has_group('base.group_system'):
                        valid_uids.append(u.id)
                        continue
                    try:
                        # Check if record is inside user's accessible domain
                        domain = u._get_hierarchy_domain(perm_field)
                        if domain and [(1, '=', 1)] == domain:
                            valid_uids.append(u.id)
                        elif domain and [(0, '=', 1)] == domain:
                            continue
                        else:
                            # Test if user has read permission on this record
                            if rec.with_user(u).check_access_rights('read', raise_exception=False):
                                if rec.sudo().search([('id', '=', rec.id)] + domain):
                                    valid_uids.append(u.id)
                    except Exception:
                        pass
                wiz.allowed_user_ids = all_users.filtered(lambda u: u.id in valid_uids)
            else:
                wiz.allowed_user_ids = all_users

            # -------------------------------------------------------------
            # Case 1: Employee is selected -> Filter Records they can access
            # -------------------------------------------------------------
            target_user = wiz.assigned_to_id or self.env.user
            if target_user._is_admin() or target_user.has_group('base.group_system'):
                wiz.allowed_lead_ids = self.env['crm.lead'].sudo().search([])
                wiz.allowed_order_ids = self.env['sale.order'].sudo().search([])
                wiz.allowed_partner_ids = self.env['res.partner'].sudo().search([])
                wiz.allowed_equipment_ids = self.env['equipment.master'].sudo().search([])
                wiz.allowed_ticket_ids = self.env['service.ticket'].sudo().search([])
                wiz.allowed_amc_ids = self.env['amc.contract'].sudo().search([])
            else:
                try:
                    lead_domain = target_user._get_hierarchy_domain('perm_lead_quote', 'user_id')
                    wiz.allowed_lead_ids = self.env['crm.lead'].sudo().search(lead_domain)
                except Exception:
                    wiz.allowed_lead_ids = self.env['crm.lead'].browse([])

                try:
                    order_domain = target_user._get_hierarchy_domain('perm_lead_quote', 'user_id')
                    wiz.allowed_order_ids = self.env['sale.order'].sudo().search(order_domain)
                except Exception:
                    wiz.allowed_order_ids = self.env['sale.order'].browse([])

                try:
                    cust_uids = target_user._get_accessible_user_ids('perm_customer')
                    if cust_uids:
                        wiz.allowed_partner_ids = self.env['res.partner'].sudo().search(['|', ('user_id', 'in', cust_uids), ('create_uid', 'in', cust_uids)])
                    else:
                        wiz.allowed_partner_ids = self.env['res.partner'].sudo().search([])
                except Exception:
                    wiz.allowed_partner_ids = self.env['res.partner'].browse([])

                try:
                    eq_domain = target_user._get_hierarchy_domain('perm_equipment', False)
                    wiz.allowed_equipment_ids = self.env['equipment.master'].sudo().search(eq_domain)
                except Exception:
                    wiz.allowed_equipment_ids = self.env['equipment.master'].browse([])

                try:
                    ticket_domain = target_user._get_hierarchy_domain('perm_service_ticket', 'engineer_id')
                    wiz.allowed_ticket_ids = self.env['service.ticket'].sudo().search(ticket_domain)
                except Exception:
                    wiz.allowed_ticket_ids = self.env['service.ticket'].browse([])

                try:
                    amc_domain = target_user._get_hierarchy_domain('perm_amc', False)
                    wiz.allowed_amc_ids = self.env['amc.contract'].sudo().search(amc_domain)
                except Exception:
                    wiz.allowed_amc_ids = self.env['amc.contract'].browse([])

    # Recurrence (Optional)
    is_recurring = fields.Boolean(string='Recurring Task', default=False)
    recurrence_period = fields.Selection([
        ('daily', 'Daily'),
        ('weekly', 'Weekly'),
        ('monthly', 'Monthly'),
        ('yearly', 'Yearly'),
    ], string='Repeat Every', default='monthly')
    recurrence_end_date = fields.Date(string='Repeat Until')

    @api.onchange('assigned_to_id')
    def _onchange_assigned_to_id_filter_records(self):
        self._compute_accessible_records()
        # If currently picked record is not accessible by the new assignee, clear it!
        if self.lead_id and self.lead_id not in self.allowed_lead_ids:
            self.lead_id = False
        if self.order_id and self.order_id not in self.allowed_order_ids:
            self.order_id = False
        if self.partner_id and self.partner_id not in self.allowed_partner_ids:
            self.partner_id = False
        if self.equipment_id and self.equipment_id not in self.allowed_equipment_ids:
            self.equipment_id = False
        if self.ticket_id and self.ticket_id not in self.allowed_ticket_ids:
            self.ticket_id = False
        if self.amc_id and self.amc_id not in self.allowed_amc_ids:
            self.amc_id = False

    @api.model
    def default_get(self, fields_list):
        res = super(CrmTaskAssignWizard, self).default_get(fields_list)
        # Prefill deadline if passed from calendar slot click (default_date_deadline, default_date_start, or initial_date)
        deadline = self.env.context.get('default_date_deadline') or self.env.context.get('default_date_start')
        if not deadline and self.env.context.get('initial_date'):
            deadline = self.env.context.get('initial_date')
        if deadline and 'date_deadline' in fields_list and not res.get('date_deadline'):
            # If string contains time (e.g. '2026-10-24 00:00:00'), slice to date YYYY-MM-DD
            res['date_deadline'] = str(deadline)[:10]

        # Auto-detect origin model and record if launched from Activity or record view
        origin_model = (
            self.env.context.get('default_related_model') or 
            self.env.context.get('active_model') or 
            self.env.context.get('default_res_model')
        )
        origin_id = (
            self.env.context.get('default_res_id') or 
            self.env.context.get('active_id') or 
            self.env.context.get('default_activity_record_id')
        )

        valid_models = {
            'crm.lead': 'lead_id',
            'sale.order': 'order_id',
            'res.partner': 'partner_id',
            'equipment.master': 'equipment_id',
            'service.ticket': 'ticket_id',
            'amc.contract': 'amc_id',
        }

        # Check explicit default fields like default_ticket_id
        for m, f in valid_models.items():
            if self.env.context.get(f'default_{f}'):
                origin_model = m
                origin_id = self.env.context.get(f'default_{f}')
                break

        # Smart Stage Detection: If origin is crm.lead, check if it's in Quote stages
        if origin_model == 'crm.lead' and origin_id:
            try:
                lead = self.env['crm.lead'].sudo().browse(int(origin_id))
                if lead.exists():
                    stage_seq = lead.x_stage_sequence or (lead.stage_id.sequence if lead.stage_id else 0)
                    latest_quote = lead.order_ids.filtered(lambda q: q.state != 'cancel')[:1] if hasattr(lead, 'order_ids') else False
                    if not latest_quote and hasattr(lead, 'sale_order_ids'):
                        latest_quote = lead.sale_order_ids.filtered(lambda q: q.state != 'cancel')[:1]
                    if not latest_quote and lead.sale_order_id:
                        latest_quote = lead.sale_order_id
                    if (stage_seq > 5 or stage_seq >= 50 or latest_quote):
                        origin_model = 'sale.order'
                        if latest_quote:
                            origin_id = latest_quote.id
            except Exception:
                pass

        if origin_model in valid_models:
            res['related_model'] = origin_model
            field_name = valid_models[origin_model]
            if origin_id:
                try:
                    res[field_name] = int(origin_id)
                except (ValueError, TypeError):
                    pass

        # Compute initial accessible employees based on prefilled record
        target_rec = False
        perm_field = 'perm_lead_quote'
        if res.get('related_model') == 'crm.lead' and res.get('lead_id'):
            target_rec = self.env['crm.lead'].sudo().browse(res['lead_id'])
            perm_field = 'perm_lead_quote'
        elif res.get('related_model') == 'sale.order' and res.get('order_id'):
            target_rec = self.env['sale.order'].sudo().browse(res['order_id'])
            perm_field = 'perm_lead_quote'
        elif res.get('related_model') == 'res.partner' and res.get('partner_id'):
            target_rec = self.env['res.partner'].sudo().browse(res['partner_id'])
            perm_field = 'perm_customer'
        elif res.get('related_model') == 'equipment.master' and res.get('equipment_id'):
            target_rec = self.env['equipment.master'].sudo().browse(res['equipment_id'])
            perm_field = 'perm_equipment'
        elif res.get('related_model') == 'service.ticket' and res.get('ticket_id'):
            target_rec = self.env['service.ticket'].sudo().browse(res['ticket_id'])
            perm_field = 'perm_service_ticket'
        elif res.get('related_model') == 'amc.contract' and res.get('amc_id'):
            target_rec = self.env['amc.contract'].sudo().browse(res['amc_id'])
            perm_field = 'perm_amc'

        all_users = self.env['res.users'].sudo().search([('active', '=', True), ('share', '=', False)])
        if target_rec and target_rec.exists():
            valid_uids = []
            for u in all_users:
                if u._is_admin() or u.has_group('base.group_system'):
                    valid_uids.append(u.id)
                    continue
                try:
                    user_domain = u._get_hierarchy_domain(perm_field)
                    if user_domain and [(1, '=', 1)] == user_domain:
                        valid_uids.append(u.id)
                    elif user_domain and [(0, '=', 1)] == user_domain:
                        continue
                    else:
                        match = target_rec.sudo().search([('id', '=', target_rec.id)] + user_domain)
                        if match:
                            valid_uids.append(u.id)
                except Exception:
                    pass
            res['allowed_user_ids'] = [(6, 0, valid_uids)]
        else:
            res['allowed_user_ids'] = [(6, 0, all_users.ids)]

        return res

    @api.onchange('related_model')
    def _onchange_related_model(self):
        # Do not wipe the preselected record when wizard first initializes with a pre-filled origin record!
        if self.env.context.get('default_res_id') or self.env.context.get('active_id'):
            return
        self.lead_id = False
        self.order_id = False
        self.partner_id = False
        self.equipment_id = False
        self.ticket_id = False
        self.amc_id = False

    def action_assign_work(self):
        self.ensure_one()

        # Validation: If Recurring is checked, Deadline cannot be empty
        if self.is_recurring and not self.date_deadline:
            raise UserError(_("Please set a Deadline for the task when enabling Recurring Task. The system uses the Deadline date as the recurring day for each cycle."))

        # Check sequential delivery: if employee already has active pending task, queue this one (is_unlocked = False)
        active_tasks_count = self.env['crm.task.management'].search_count([
            ('assigned_to_id', '=', self.assigned_to_id.id),
            ('state', 'in', ['pending', 'in_progress']),
            ('is_unlocked', '=', True),
        ])
        is_unlocked = (active_tasks_count == 0)

        # Generate a unique series group ID if this task is recurring
        series_group_id = f"SERIES_{self.env.user.id}_{int(fields.Datetime.now().timestamp())}" if self.is_recurring else False

        # 1. Create the persistent task management record (Initial occurrence)
        task_rec = self.env['crm.task.management'].sudo().create({
            'name': self.name.strip(),
            'assigned_to_id': self.assigned_to_id.id,
            'assigned_by_id': self.env.user.id,
            'date_assigned': fields.Datetime.now(),
            'date_deadline': self.date_deadline,
            'instructions': self.instructions.strip() if self.instructions else '',
            'attachment_name': self.attachment_name or '',
            'attachment_file': self.attachment_file or False,
            'attachment_ids': [(6, 0, self.attachment_ids.ids)] if self.attachment_ids else False,
            'company_id': self.company_id.id if self.company_id else False,
            'related_model': self.related_model or False,
            'lead_id': self.lead_id.id if self.lead_id else False,
            'order_id': self.order_id.id if self.order_id else False,
            'partner_id': self.partner_id.id if self.partner_id else False,
            'equipment_id': self.equipment_id.id if self.equipment_id else False,
            'ticket_id': self.ticket_id.id if self.ticket_id else False,
            'amc_id': self.amc_id.id if self.amc_id else False,
            'is_recurring': bool(self.is_recurring),
            'recurrence_period': self.recurrence_period if self.is_recurring else False,
            'recurring_group_id': series_group_id,
            'is_unlocked': is_unlocked,
            'state': 'pending',
        })

        if self.attachment_file and self.attachment_name:
            self.env['crm.task.attachment'].sudo().create({
                'task_id': task_rec.id,
                'name': self.attachment_name,
                'file': self.attachment_file,
            })

        for w_att in self.wizard_attachment_ids:
            if w_att.file:
                self.env['crm.task.attachment'].sudo().create({
                    'task_id': task_rec.id,
                    'name': w_att.name or 'attachment',
                    'file': w_att.file,
                })

        # When Recurring is checked:
        # The user-selected 'Deadline' is treated as the 'Repeat Until' (final deadline) of the recurring series!
        # Occurrences start from today (or the first cycle date) and repeat up until that final deadline.
        if self.is_recurring and self.date_deadline:
            end_date = fields.Date.from_string(str(self.date_deadline)[:10])
            today = fields.Date.today()
            target_day = end_date.day
            cycle = self.recurrence_period or 'monthly'

            # 1. Determine first occurrence date
            first_date = today
            if cycle == 'monthly':
                try:
                    first_date = today.replace(day=target_day)
                except ValueError:
                    first_date = today
                if first_date <= today:
                    first_date = first_date + relativedelta(months=1)
            elif cycle == 'daily':
                first_date = today + relativedelta(days=1)
            elif cycle == 'weekly':
                first_date = today + relativedelta(weeks=1)
            elif cycle == 'yearly':
                first_date = today + relativedelta(years=1)

            # Ensure initial task record has the proper first occurrence deadline
            task_rec.sudo().write({'date_deadline': first_date if first_date <= end_date else end_date})

            # 2. Pre-create intermediate occurrences strictly up to the final 'Repeat Until' deadline
            current_date = first_date
            count = 0
            while count < 60:
                if cycle == 'daily':
                    current_date = current_date + relativedelta(days=1)
                elif cycle == 'weekly':
                    current_date = current_date + relativedelta(weeks=1)
                elif cycle == 'yearly':
                    current_date = current_date + relativedelta(years=1)
                else:
                    current_date = current_date + relativedelta(months=1)

                if current_date > end_date:
                    break

                self.env['crm.task.management'].sudo().create({
                    'name': self.name.strip(),
                    'assigned_to_id': self.assigned_to_id.id,
                    'assigned_by_id': self.env.user.id,
                    'date_assigned': fields.Datetime.now(),
                    'date_deadline': current_date,
                    'instructions': self.instructions.strip() if self.instructions else '',
                    'attachment_name': self.attachment_name or '',
                    'attachment_file': self.attachment_file or False,
                    'attachment_ids': [(6, 0, self.attachment_ids.ids)] if self.attachment_ids else False,
                    'company_id': self.company_id.id if self.company_id else False,
                    'related_model': self.related_model or False,
                    'lead_id': self.lead_id.id if self.lead_id else False,
                    'order_id': self.order_id.id if self.order_id else False,
                    'partner_id': self.partner_id.id if self.partner_id else False,
                    'equipment_id': self.equipment_id.id if self.equipment_id else False,
                    'ticket_id': self.ticket_id.id if self.ticket_id else False,
                    'amc_id': self.amc_id.id if self.amc_id else False,
                    'is_recurring': True,
                    'recurrence_period': cycle,
                    'recurring_group_id': series_group_id,
                    'is_unlocked': True,
                    'state': 'pending',
                })
                count += 1

        # 2. Notification message to assigned user with Direct Clickable Link
        sender = self.env.user
        target_partner = self.assigned_to_id.partner_id
        if target_partner:
            # Direct mail message with clickable task link
            base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url', '')
            task_link = f"{base_url}/web#id={task_rec.id}&model=crm.task.management&view_type=form"

            attachment_ids = []
            if self.attachment_name and self.attachment_file:
                try:
                    att = self.env['ir.attachment'].sudo().create({
                        'name': self.attachment_name,
                        'datas': self.attachment_file,
                        'res_model': 'crm.task.management',
                        'res_id': task_rec.id,
                        'type': 'binary',
                    })
                    if att:
                        attachment_ids.append(att.id)
                except Exception:
                    pass

            body_text = f"<b>New Task Assigned:</b> <a href='{task_link}' style='font-weight:bold; color:#0b3d91;'>{self.name.strip()}</a>"
            if self.instructions:
                body_text += f"<br/>{self.instructions}"
            if task_rec.related_record_display:
                body_text += f"<br/><b>Related:</b> {task_rec.related_record_display}"
            if self.attachment_name:
                body_text += f"<br/><small style='color:#0b3d91;'>📎 Attached: {self.attachment_name}</small>"
            body_text += f"<br/><p><a href='{task_link}' class='btn btn-sm btn-primary' style='display:inline-block; padding:4px 10px; background:#0b3d91; color:#ffffff; border-radius:4px; text-decoration:none;'>Open Task Details</a></p>"

            msg_vals = {
                'subject': f"Task: {self.name.strip()}",
                'body': body_text,
                'model': 'crm.task.management',
                'res_id': task_rec.id,
                'message_type': 'comment',
                'author_id': sender.partner_id.id if sender.partner_id else False,
                'partner_ids': [(6, 0, [target_partner.id])],
            }
            if attachment_ids:
                msg_vals['attachment_ids'] = [(6, 0, attachment_ids)]
            self.env['mail.message'].sudo().create(msg_vals)

        return {'type': 'ir.actions.act_window_close'}


class CrmTaskAssignWizardAttachment(models.TransientModel):
    _name = 'crm.task.assign.wizard.attachment'
    _description = 'Assign Work Wizard Attachment'

    wizard_id = fields.Many2one('crm.task.assign.wizard', string='Wizard', ondelete='cascade')
    name = fields.Char(string='File Name')
    file = fields.Binary(string='File', attachment=True)

    def action_preview_file(self):
        return True

